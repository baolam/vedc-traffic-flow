"""
EdgeFlow AI -- Vision Local Dashboard: standalone web UI served by this same process.

Deliberately free of any cv2/paho-mqtt import at module scope: it only reads/writes plain
attributes on the VisionSupervisor instance it's handed (identity, stats, cached last
telemetry/health, node list, pending_commands queue, local_db). This keeps every route except
the two ROI ones independently testable with no camera/MQTT hardware, and keeps the boundary
between "things that touch the camera/network" (supervisor.py) and "things that render a web
page" explicit. The ROI routes import vision.roi_config lazily (see get_roi/post_roi below)
because that module lives inside the `vision` package, whose __init__.py eagerly imports the
cv2-dependent detector/engine -- a real dependency on every actual deployment (cv2 is vision's
core dependency), just not one the rest of this file needs to pay for.
"""

import logging
import secrets
import sys
import threading
import time
from pathlib import Path
from typing import Any, Dict, Optional

# Ensure services/vision and repo root are in sys.path when running server.py directly
_curr_dir = Path(__file__).resolve().parent
_vision_dir = _curr_dir.parent
_repo_dir = _vision_dir.parent.parent
for _p in (str(_vision_dir), str(_repo_dir)):
    if _p not in sys.path:
        sys.path.insert(0, _p)

from fastapi import FastAPI, HTTPException, Request, Depends
from fastapi.responses import HTMLResponse, StreamingResponse, JSONResponse, FileResponse
from fastapi.security import HTTPBasic, HTTPBasicCredentials
from fastapi.middleware.cors import CORSMiddleware
import uvicorn

try:
    from vision_contracts_helper import load_topology, default_display_name
except ImportError:
    from services.vision.vision_contracts_helper import load_topology, default_display_name


def _roi_helpers():
    """Lazy import of vision.roi_config -- see module docstring."""
    try:
        from vision.roi_config import parse_roi_config, validate_against_topology, save_roi_config
    except ImportError:
        from services.vision.vision.roi_config import parse_roi_config, validate_against_topology, save_roi_config
    return parse_roi_config, validate_against_topology, save_roi_config


logger = logging.getLogger("vision-local-dashboard")

STATIC_DIR = Path(__file__).resolve().parent / "static"

# Settings the web UI is allowed to change at runtime, and their valid range. Kept narrow and
# explicit on purpose -- this is a direct-intervention surface on a physical device, not a
# generic settings editor.
_TUNABLE_SETTINGS = {
    "confidence_threshold": (0.0, 1.0),
}


class FrameCache:
    """Thread-safe {node_id: latest JPEG bytes}, written by the tick loop (supervisor.py, which
    already depends on cv2 and does the encoding), read by the /stream and /snapshot routes.
    Supports storing both annotated HUD frames and pristine raw frames (for ROI calibration)."""

    def __init__(self):
        self._lock = threading.Lock()
        self._frames: Dict[str, bytes] = {}
        self._raw_frames: Dict[str, bytes] = {}

    def update(self, node_id: str, jpeg_bytes: bytes, raw_bytes: Optional[bytes] = None):
        with self._lock:
            self._frames[node_id] = jpeg_bytes
            if raw_bytes is not None:
                self._raw_frames[node_id] = raw_bytes

    def get(self, node_id: str, raw: bool = False) -> Optional[bytes]:
        with self._lock:
            if raw and node_id in self._raw_frames:
                return self._raw_frames[node_id]
            return self._frames.get(node_id)


def create_app(supervisor: Any, frame_cache: FrameCache) -> FastAPI:
    """supervisor is a VisionSupervisor (or, in tests, any object exposing the same attributes:
    identity, stats, node_ids, active_nodes, cfg, pending_commands, local_db, roi_config,
    roi_config_path, last_telemetry, last_health)."""
    app = FastAPI(title="EdgeFlow AI -- Vision Local Dashboard")
    app.add_middleware(
        CORSMiddleware,
        allow_origins=["*"],
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )
    security = HTTPBasic(auto_error=False)

    def require_auth(credentials: Optional[HTTPBasicCredentials] = Depends(security)):
        password = getattr(supervisor.cfg, "local_dashboard_password", "")
        if not password:
            return  # Basic Auth disabled (empty password) -- logged as a warning on startup.
        username = getattr(supervisor.cfg, "local_dashboard_username", "admin")
        ok = bool(credentials) and secrets.compare_digest(credentials.username, username) \
            and secrets.compare_digest(credentials.password, password)
        if not ok:
            raise HTTPException(status_code=401, detail="Unauthorized", headers={"WWW-Authenticate": "Basic"})

    @app.get("/", response_class=HTMLResponse)
    def index(_: None = Depends(require_auth)):
        index_file = STATIC_DIR / "index.html"
        if not index_file.is_file():
            raise HTTPException(status_code=404, detail="Dashboard UI not built.")
        return HTMLResponse(index_file.read_text(encoding="utf-8"))

    @app.get("/app.js")
    def app_js(_: None = Depends(require_auth)):
        return HTMLResponse((STATIC_DIR / "app.js").read_text(encoding="utf-8"), media_type="application/javascript")

    @app.get("/style.css")
    def style_css(_: None = Depends(require_auth)):
        return HTMLResponse((STATIC_DIR / "style.css").read_text(encoding="utf-8"), media_type="text/css")

    @app.get("/api/status")
    def status(_: None = Depends(require_auth)):
        active_alerts = supervisor.get_active_alerts() if hasattr(supervisor, "get_active_alerts") else []
        return {
            "identity": supervisor.identity,
            "stats": supervisor.stats.snapshot(),
            "node_ids": supervisor.node_ids,
            "last_telemetry": supervisor.last_telemetry,
            "last_health": supervisor.last_health,
            "active_alerts": active_alerts,
            "occlusion_mode": getattr(supervisor, "occlusion_mode", "none"),
            "occlusion_target_roi": getattr(supervisor, "occlusion_target_roi", ""),
        }

    @app.get("/api/alerts")
    def alerts(node_id: Optional[str] = None, limit: int = 100, _: None = Depends(require_auth)):
        active_alerts = supervisor.get_active_alerts() if hasattr(supervisor, "get_active_alerts") else []
        records = supervisor.local_db.query_alerts(node_id=node_id, limit=limit)
        return {"active_alerts": active_alerts, "records": records}

    @app.get("/api/telemetry/history")
    def telemetry_history(node_id: Optional[str] = None, limit: int = 100, _: None = Depends(require_auth)):
        return {"records": supervisor.local_db.query_telemetry(node_id=node_id, limit=limit)}

    @app.get("/api/health/history")
    def health_history(limit: int = 100, _: None = Depends(require_auth)):
        return {"records": supervisor.local_db.query_health(limit=limit)}

    @app.get("/api/events")
    def events(limit: int = 100, _: None = Depends(require_auth)):
        return {"records": supervisor.local_db.query_events(limit=limit)}

    @app.get("/api/database/stats")
    def database_stats(_: None = Depends(require_auth)):
        stats = supervisor.local_db.get_stats() if hasattr(supervisor.local_db, "get_stats") else {}
        return stats

    @app.post("/api/database/prune")
    async def database_prune(request: Request, _: None = Depends(require_auth)):
        body = {}
        try:
            body = await request.json()
        except Exception:
            pass
        retention_days = body.get("retention_days")
        if retention_days is not None:
            try:
                retention_days = float(retention_days)
            except (ValueError, TypeError):
                raise HTTPException(status_code=400, detail="retention_days must be a number.")
        deleted = supervisor.local_db.prune(retention_days=retention_days)
        supervisor.local_db.record_event("database_pruned", {"deleted": deleted, "retention_days": retention_days})
        return {"ok": True, "deleted": deleted}

    @app.post("/api/database/vacuum")
    def database_vacuum(_: None = Depends(require_auth)):
        success = supervisor.local_db.vacuum() if hasattr(supervisor.local_db, "vacuum") else False
        supervisor.local_db.record_event("database_vacuumed", {"success": success})
        return {"ok": success}

    @app.get("/api/database/download")
    def database_download(_: None = Depends(require_auth)):
        db_path = getattr(supervisor.local_db, "db_path", None)
        if not db_path or not Path(db_path).is_file():
            raise HTTPException(status_code=404, detail="Database file not found on device.")
        return FileResponse(
            path=str(db_path),
            media_type="application/x-sqlite3",
            filename=f"vision_local_{int(time.time())}.db",
        )

    @app.post("/api/database/clear")
    async def database_clear(request: Request, _: None = Depends(require_auth)):
        body = {}
        try:
            body = await request.json()
        except Exception:
            pass
        tables = body.get("tables")
        deleted = supervisor.local_db.clear(tables=tables) if hasattr(supervisor.local_db, "clear") else {}
        supervisor.local_db.record_event("database_cleared", {"tables": tables, "deleted": deleted})
        return {"ok": True, "deleted": deleted}

    @app.get("/stream/{node_id}")
    def stream(node_id: str, _: None = Depends(require_auth)):
        boundary = "frame"

        def gen():
            last = None
            while True:
                jpeg = frame_cache.get(node_id)
                if jpeg is not None and jpeg is not last:
                    last = jpeg
                    yield (f"--{boundary}\r\nContent-Type: image/jpeg\r\nContent-Length: {len(jpeg)}\r\n\r\n"
                           .encode("ascii") + jpeg + b"\r\n")
                time.sleep(0.05)

        return StreamingResponse(gen(), media_type=f"multipart/x-mixed-replace; boundary={boundary}")

    @app.get("/snapshot/{node_id}")
    def snapshot(node_id: str, raw: bool = False, _: None = Depends(require_auth)):
        jpeg = frame_cache.get(node_id, raw=raw)
        if jpeg is None:
            raise HTTPException(status_code=404, detail="No frame captured yet.")
        return StreamingResponse(iter([jpeg]), media_type="image/jpeg")

    @app.post("/api/control/restart")
    def control_restart(_: None = Depends(require_auth)):
        supervisor.pending_commands.put({"type": "restart"})
        supervisor.local_db.record_event("restart_requested")
        return {"ok": True}

    @app.get("/api/videos")
    def list_input_videos(_: None = Depends(require_auth)):
        """Lists available video files in services/vision/input_videos."""
        v_dir = Path(__file__).resolve().parents[1] / "input_videos"
        videos = []
        if v_dir.is_dir():
            for f in sorted(v_dir.glob("*.mp4")):
                videos.append({
                    "name": f.name,
                    "path": str(f.resolve()),
                    "size_mb": round(f.stat().st_size / (1024 * 1024), 1)
                })
        current = getattr(supervisor.cfg, "video_source", "synthetic")
        return {
            "current_source": current,
            "videos": videos,
        }

    @app.post("/api/control/video-source")
    async def control_video_source(request: Request, _: None = Depends(require_auth)):
        body = await request.json()
        new_source = body.get("video_source")
        if not new_source:
            raise HTTPException(status_code=400, detail="video_source is required.")
        supervisor.pending_commands.put({"type": "update_settings", "fields": {"video_source": str(new_source)}})
        supervisor.local_db.record_event("video_source_changed", {"source": str(new_source)})
        return {"ok": True, "video_source": str(new_source)}

    @app.post("/api/control/settings")
    async def control_settings(request: Request, _: None = Depends(require_auth)):
        body = await request.json()
        fields = {}
        for key, value in body.items():
            if key not in _TUNABLE_SETTINGS:
                raise HTTPException(status_code=400, detail=f"Setting '{key}' cannot be changed from the dashboard.")
            lo, hi = _TUNABLE_SETTINGS[key]
            try:
                value = float(value)
            except (TypeError, ValueError):
                raise HTTPException(status_code=400, detail=f"'{key}' must be a number.")
            if not (lo < value < hi):
                raise HTTPException(status_code=400, detail=f"'{key}' must be between {lo} and {hi}.")
            fields[key] = value
        if not fields:
            raise HTTPException(status_code=400, detail="No recognized settings in request body.")
        supervisor.pending_commands.put({"type": "update_settings", "fields": fields})
        supervisor.local_db.record_event("settings_updated", fields)
        return {"ok": True, "applied": fields}

    @app.get("/api/control/occlusion-simulation")
    def get_occlusion_simulation(_: None = Depends(require_auth)):
        return {
            "mode": getattr(supervisor, "occlusion_mode", "none"),
            "target_roi": getattr(supervisor, "occlusion_target_roi", ""),
            "available_modes": [
                {"id": "none", "name_vi": "Bình thường (Tắt giả lập)", "name_en": "Normal (Simulation Off)"},
                {"id": "full_occlusion", "name_vi": "Che kín ống kính (Băng keo / Bìa / Tay)", "name_en": "Full Lens Covered"},
                {"id": "blackout", "name_vi": "Mất sáng toàn phần (Màn đêm / Mất tín hiệu)", "name_en": "Total Blackout"},
                {"id": "glare", "name_vi": "Lóa sáng cực độ (Đèn pha / Chiếu trực tiếp)", "name_en": "Blinding Glare"},
                {"id": "blur", "name_vi": "Mờ đục / Mất nét (Sương mù / Đọng nước)", "name_en": "Severe Blur / Defocus"},
                {"id": "roi_occlusion", "name_vi": "Che khuất nhánh đường (Vật cản ROI)", "name_en": "Partial Approach ROI Blind"}
            ]
        }

    @app.post("/api/control/occlusion-simulation")
    async def post_occlusion_simulation(request: Request, _: None = Depends(require_auth)):
        body = await request.json()
        mode = body.get("mode", "none")
        valid_modes = {"none", "full_occlusion", "blackout", "glare", "blur", "roi_occlusion"}
        if mode not in valid_modes:
            raise HTTPException(status_code=400, detail=f"Invalid occlusion mode '{mode}'. Valid modes: {valid_modes}")
        target_roi = str(body.get("target_roi", ""))
        supervisor.pending_commands.put({"type": "simulate_occlusion", "mode": mode, "target_roi": target_roi})
        if hasattr(supervisor, "occlusion_mode"):
            supervisor.occlusion_mode = mode
            supervisor.occlusion_target_roi = target_roi
        return {"ok": True, "mode": mode, "target_roi": target_roi}

    @app.get("/api/roi")
    def get_roi(_: None = Depends(require_auth)):
        roi = supervisor.roi_config
        if roi:
            current_nodes = {nid: {a: [list(p) for p in poly] for a, poly in apps.items()}
                             for nid, apps in roi.nodes.items()}
            camera_name = roi.camera
            frame_sz = list(roi.frame_size)
        else:
            # Fallback to active engine in-memory ROIs so UI is prepopulated with all approaches
            current_nodes = {}
            default_nid = supervisor.node_ids[0] if supervisor.node_ids else "J1"
            roi_mgr = getattr(supervisor.engine, "roi_manager", None)
            rois = getattr(roi_mgr, "rois", {}) if roi_mgr else {}
            for app_id, r in rois.items():
                nid = r.get("node_id", default_nid)
                poly = r.get("polygon")
                if poly is not None:
                    current_nodes.setdefault(nid, {})[app_id] = [list(map(int, pt)) for pt in poly]
            camera_name = "default"
            frame_sz = [supervisor.engine.width, supervisor.engine.height]

        return {
            "frame_size": [supervisor.engine.width, supervisor.engine.height],
            "approaches": {n["node_id"]: n.get("approaches", []) for n in supervisor.active_nodes},
            # Computed fully offline from the same topology data active_nodes already carries
            # (see contracts/naming.py) -- the static UI reads this purely for display, never
            # as a lookup key, so "approaches" above stays the untouched raw-id list it always
            # was.
            "approach_display_names": {
                n["node_id"]: {
                    a: default_display_name(a, n.get("approach_display_names", {}))
                    for a in n.get("approaches", [])
                }
                for n in supervisor.active_nodes
            },
            "current": {
                "camera": camera_name,
                "frame_size": frame_sz,
                "nodes": current_nodes,
            } if current_nodes else None,
        }

    @app.post("/api/roi")
    async def post_roi(request: Request, _: None = Depends(require_auth)):
        parse_roi_config, validate_against_topology, save_roi_config = _roi_helpers()
        data = await request.json()
        try:
            config = parse_roi_config(data)
            topology = load_topology(supervisor.cfg.edgeflow_topology)
            validate_against_topology(config, topology, supervisor.node_ids)
        except (ValueError, KeyError) as e:
            raise HTTPException(status_code=400, detail=str(e))
        path = supervisor.roi_config_path
        save_roi_config(path, data.get("camera", ""), tuple(data["frame_size"]), data["nodes"])
        supervisor.pending_commands.put({"type": "reload_roi", "roi_config_path": path})
        supervisor.local_db.record_event("roi_updated", {"path": path})
        return {"ok": True, "path": path}

    return app


class LocalDashboardServer:
    """Owns the FastAPI app + a uvicorn server run on a daemon thread, plus the frame cache the
    tick loop feeds. Starting/stopping this must never be able to take down the camera/telemetry
    pipeline -- any failure here is the caller's (supervisor.py's) responsibility to catch."""

    def __init__(self, supervisor: Any):
        self.frame_cache = FrameCache()
        app = create_app(supervisor, self.frame_cache)
        host = supervisor.cfg.local_dashboard_host
        port = supervisor.cfg.local_dashboard_port
        if not supervisor.cfg.local_dashboard_password:
            logger.warning("Local dashboard starting WITHOUT authentication (LOCAL_DASHBOARD_PASSWORD unset) "
                            f"on {host}:{port} -- set it for any real LAN deployment.")
        config = uvicorn.Config(app, host=host, port=port, log_level="warning")
        self._server = uvicorn.Server(config)
        self._thread = threading.Thread(target=self._server.run, daemon=True, name="vision-local-dashboard")

    def start(self):
        self._thread.start()

    def update_frame(self, node_id: str, jpeg_bytes: bytes, raw_bytes: Optional[bytes] = None):
        self.frame_cache.update(node_id, jpeg_bytes, raw_bytes)

    def stop(self):
        self._server.should_exit = True
        if self._thread.is_alive():
            self._thread.join(timeout=3.0)


if __name__ == "__main__":
    import argparse
    import cv2
    import numpy as np
    import queue
    import sys

    # Ensure services/vision is on sys.path
    _parent = str(Path(__file__).resolve().parents[1])
    if _parent not in sys.path:
        sys.path.insert(0, _parent)

    try:
        from local_dashboard.db import VisionLocalDB
    except ImportError:
        from services.vision.local_dashboard.db import VisionLocalDB

    parser = argparse.ArgumentParser(description="EdgeFlow AI - Vision Local Dashboard (Standalone Runner)")
    parser.add_argument("--host", default="0.0.0.0", help="Host interface (default: 0.0.0.0)")
    parser.add_argument("--port", type=int, default=8080, help="HTTP port (default: 8080)")
    parser.add_argument("--username", default="admin", help="Basic Auth username (default: admin)")
    parser.add_argument("--password", default="", help="Basic Auth password (default: empty for none)")
    parser.add_argument("--topology", default="four_intersection_v1", help="Topology contract name")
    parser.add_argument("--node-id", default="J1", help="Primary node ID (default: J1)")
    parser.add_argument("--db-path", default="", help="Path to SQLite database (default: services/vision/data/vision.db)")
    parser.add_argument("--fps", type=float, default=10.0, help="Simulated live frame rate (default: 10.0)")
    args = parser.parse_args()

    class StandaloneCfg:
        local_dashboard_host = args.host
        local_dashboard_port = args.port
        local_dashboard_username = args.username
        local_dashboard_password = args.password
        edgeflow_topology = args.topology

    class StandaloneStats:
        def __init__(self):
            self.fps = args.fps
            self.frames_ok = 0
            self.frames_failed = 0

        def snapshot(self):
            return {
                "processed_fps": round(self.fps, 1),
                "frames_ok": self.frames_ok,
                "frames_failed": self.frames_failed,
                "consecutive_failures": 0,
                "latency_ms": {"total_ms": {"p50": 14.5, "p95": 21.0}},
            }

    class StandaloneEngine:
        width = 640
        height = 480

    topology = load_topology(args.topology)
    topo_nodes = {n["node_id"]: n for n in topology.get("nodes", [])}
    if args.node_id not in topo_nodes:
        raise ValueError(f"Node '{args.node_id}' not found in topology '{args.topology}'")
    active_node = topo_nodes[args.node_id]

    db = VisionLocalDB(db_path=args.db_path or None)

    class StandaloneSupervisor:
        def __init__(self):
            self.cfg = StandaloneCfg()
            self.identity = {
                "service": "vision",
                "mode": "standalone_dashboard",
                "node_id": args.node_id,
                "confidence_threshold": 0.4,
            }
            self.stats = StandaloneStats()
            self.node_ids = [args.node_id]
            self.active_nodes = [active_node]
            self.engine = StandaloneEngine()
            self.roi_config = None
            self.roi_config_path = str(Path(__file__).resolve().parent.parent / "rois" / f"roi_{args.node_id}.json")
            self.pending_commands = queue.Queue()
            self.local_db = db
            self.last_telemetry = {
                args.node_id: {
                    "node_id": args.node_id,
                    "current_phase_id": f"{args.node_id}_PHASE_NS",
                    "approaches": [
                        {"approach_id": app_id, "queue_vehicles": 2.0, "mean_speed_mps": 4.5, "confidence": 1.0}
                        for app_id in active_node.get("approaches", [])
                    ],
                }
            }
            self.last_health = {
                "status": "HEALTHY",
                "runtime": self.stats.snapshot(),
                "hardware": {"cpu_temp_c": 47.5, "load_1m": 0.35, "free_mem_mb": 3500},
                "timestamp_ms": int(time.time() * 1000),
            }

    supervisor_instance = StandaloneSupervisor()
    server_instance = LocalDashboardServer(supervisor_instance)
    server_instance.start()

    print("=================================================================")
    print(" EdgeFlow AI - Vision Local Dashboard (Standalone Mode)")
    print(f" URL: http://{args.host}:{args.port}")
    if args.password:
        print(f" Authentication: ENABLED (User: {args.username})")
    else:
        print(" Authentication: DISABLED (Direct LAN access)")
    print(f" Target Node: {args.node_id} | Topology: {args.topology}")
    print(" Press Ctrl+C to stop.")
    print("=================================================================")

    # Background frame generation loop
    running = True
    step = 0
    dt = 1.0 / max(args.fps, 1.0)
    last_db_record = 0.0

    try:
        while running:
            # Check pending commands from dashboard UI
            while not supervisor_instance.pending_commands.empty():
                cmd = supervisor_instance.pending_commands.get_nowait()
                cmd_type = cmd.get("type")
                if cmd_type == "update_settings":
                    for k, v in cmd.get("fields", {}).items():
                        supervisor_instance.identity[k] = v
                    logger.info(f"[Dashboard Command] Settings updated: {cmd.get('fields')}")
                elif cmd_type == "restart":
                    logger.info("[Dashboard Command] Pipeline restart requested.")
                    supervisor_instance.local_db.record_event("restarted", {"trigger": "dashboard"})
                elif cmd_type == "reload_roi":
                    logger.info(f"[Dashboard Command] ROI reloaded from {cmd.get('roi_config_path')}")

            # Generate synthetic test frame with timestamp & visual elements
            frame = np.zeros((480, 640, 3), dtype=np.uint8)
            # Road background
            cv2.rectangle(frame, (180, 0), (460, 480), (40, 40, 40), -1)
            cv2.rectangle(frame, (0, 120), (640, 360), (40, 40, 40), -1)
            # Center intersection box
            cv2.rectangle(frame, (180, 120), (460, 360), (50, 50, 50), -1)
            # Animated vehicle
            car_y = int(80 + (step * 8) % 320)
            cv2.rectangle(frame, (230, car_y), (270, car_y + 50), (60, 180, 75), -1)
            cv2.putText(frame, "CAR #1", (220, car_y - 5), cv2.FONT_HERSHEY_SIMPLEX, 0.4, (255, 255, 255), 1)

            # Node & Status HUD
            cv2.putText(frame, f"NODE: {args.node_id} [STANDALONE DASHBOARD]", (20, 30),
                        cv2.FONT_HERSHEY_SIMPLEX, 0.55, (0, 255, 255), 1)
            cv2.putText(frame, time.strftime("%Y-%m-%d %H:%M:%S"), (20, 55),
                        cv2.FONT_HERSHEY_SIMPLEX, 0.45, (200, 200, 200), 1)

            ok, jpeg = cv2.imencode(".jpg", frame, [cv2.IMWRITE_JPEG_QUALITY, 75])
            if ok:
                server_instance.update_frame(args.node_id, jpeg.tobytes())
                supervisor_instance.stats.frames_ok += 1

            # Periodically record telemetry and health to local_db (every 2s)
            now = time.time()
            if now - last_db_record >= 2.0:
                last_db_record = now
                telem_payload = {
                    "node_id": args.node_id,
                    "current_phase_id": f"{args.node_id}_PHASE_NS",
                    "approaches": [
                        {"approach_id": app_id, "queue_vehicles": float((step % 5) + 1), "confidence": 1.0}
                        for app_id in active_node.get("approaches", [])
                    ],
                    "timestamp_ms": int(now * 1000),
                }
                supervisor_instance.local_db.record_telemetry(telem_payload)
                supervisor_instance.last_telemetry[args.node_id] = telem_payload

                health_payload = {
                    "status": "HEALTHY",
                    "runtime": supervisor_instance.stats.snapshot(),
                    "hardware": {"cpu_temp_c": 46.0 + (step % 4) * 0.5, "load_1m": 0.4},
                    "timestamp_ms": int(now * 1000),
                }
                supervisor_instance.local_db.record_health(health_payload)
                supervisor_instance.last_health = health_payload

            step += 1
            time.sleep(dt)

    except KeyboardInterrupt:
        logger.info("Stopping standalone dashboard...")
    finally:
        server_instance.stop()
        db.close()
        logger.info("Dashboard stopped.")
