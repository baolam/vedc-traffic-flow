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
import threading
import time
from pathlib import Path
from typing import Any, Dict, Optional

from fastapi import FastAPI, HTTPException, Request, Depends
from fastapi.responses import HTMLResponse, StreamingResponse, JSONResponse
from fastapi.security import HTTPBasic, HTTPBasicCredentials
import uvicorn

try:
    from vision_contracts_helper import load_topology
except ImportError:
    from services.vision.vision_contracts_helper import load_topology


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
    already depends on cv2 and does the encoding), read by the /stream and /snapshot routes."""

    def __init__(self):
        self._lock = threading.Lock()
        self._frames: Dict[str, bytes] = {}

    def update(self, node_id: str, jpeg_bytes: bytes):
        with self._lock:
            self._frames[node_id] = jpeg_bytes

    def get(self, node_id: str) -> Optional[bytes]:
        with self._lock:
            return self._frames.get(node_id)


def create_app(supervisor: Any, frame_cache: FrameCache) -> FastAPI:
    """supervisor is a VisionSupervisor (or, in tests, any object exposing the same attributes:
    identity, stats, node_ids, active_nodes, cfg, pending_commands, local_db, roi_config,
    roi_config_path, last_telemetry, last_health)."""
    app = FastAPI(title="EdgeFlow AI -- Vision Local Dashboard")
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
        return {
            "identity": supervisor.identity,
            "stats": supervisor.stats.snapshot(),
            "node_ids": supervisor.node_ids,
            "last_telemetry": supervisor.last_telemetry,
            "last_health": supervisor.last_health,
        }

    @app.get("/api/telemetry/history")
    def telemetry_history(node_id: Optional[str] = None, limit: int = 100, _: None = Depends(require_auth)):
        return {"records": supervisor.local_db.query_telemetry(node_id=node_id, limit=limit)}

    @app.get("/api/health/history")
    def health_history(limit: int = 100, _: None = Depends(require_auth)):
        return {"records": supervisor.local_db.query_health(limit=limit)}

    @app.get("/api/events")
    def events(limit: int = 100, _: None = Depends(require_auth)):
        return {"records": supervisor.local_db.query_events(limit=limit)}

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
    def snapshot(node_id: str, _: None = Depends(require_auth)):
        jpeg = frame_cache.get(node_id)
        if jpeg is None:
            raise HTTPException(status_code=404, detail="No frame captured yet.")
        return StreamingResponse(iter([jpeg]), media_type="image/jpeg")

    @app.post("/api/control/restart")
    def control_restart(_: None = Depends(require_auth)):
        supervisor.pending_commands.put({"type": "restart"})
        supervisor.local_db.record_event("restart_requested")
        return {"ok": True}

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

    @app.get("/api/roi")
    def get_roi(_: None = Depends(require_auth)):
        roi = supervisor.roi_config
        return {
            "frame_size": [supervisor.engine.width, supervisor.engine.height],
            "approaches": {n["node_id"]: n.get("approaches", []) for n in supervisor.active_nodes},
            "current": {
                "camera": roi.camera,
                "frame_size": list(roi.frame_size),
                "nodes": {nid: {a: [list(p) for p in poly] for a, poly in apps.items()}
                          for nid, apps in roi.nodes.items()},
            } if roi else None,
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

    def update_frame(self, node_id: str, jpeg_bytes: bytes):
        self.frame_cache.update(node_id, jpeg_bytes)

    def stop(self):
        self._server.should_exit = True
        if self._thread.is_alive():
            self._thread.join(timeout=3.0)
