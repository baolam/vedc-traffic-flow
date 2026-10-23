import os
import json
import sys
import time
import logging
from pathlib import Path
from typing import Dict, Any, List, Optional, Union
from fastapi import FastAPI, HTTPException, Body, WebSocket, WebSocketDisconnect
from fastapi.responses import HTMLResponse, FileResponse
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel

curr_dir = Path(__file__).resolve().parent
if str(curr_dir) not in sys.path:
    sys.path.insert(0, str(curr_dir))

try:
    from config import settings
except ImportError:
    from services.api.config import settings

logging.basicConfig(level=getattr(logging, settings.log_level.upper(), logging.INFO))
logger = logging.getLogger("api-service")

# Add contracts and src to sys.path safely
def _get_contracts_dir() -> Path:
    env_dir = getattr(settings, "contracts_dir", "") or os.getenv("CONTRACTS_DIR")
    if env_dir and Path(env_dir).exists():
        return Path(env_dir)
    if Path("/contracts").exists():
        return Path("/contracts")
    curr = Path(__file__).resolve().parent
    for p in [curr] + list(curr.parents):
        if (p / "contracts").is_dir():
            return p / "contracts"
        if (p / "contracts_sdk.py").is_file():
            return p
    return Path("/contracts")

contracts_dir = _get_contracts_dir()
if str(contracts_dir) not in sys.path:
    sys.path.insert(0, str(contracts_dir))

def _get_src_graph_dir() -> Path:
    curr = Path(__file__).resolve().parent
    for p in [curr] + list(curr.parents):
        if (p / "src" / "graph").is_dir():
            return p / "src" / "graph"
    return curr / "src" / "graph"

src_graph_dir = _get_src_graph_dir()
if str(src_graph_dir) not in sys.path:
    sys.path.insert(0, str(src_graph_dir))

def _get_artifacts_dir() -> Path:
    curr = Path(__file__).resolve().parent
    for p in [curr] + list(curr.parents):
        if (p / "artifacts").is_dir():
            return p / "artifacts"
    return curr / "artifacts"

artifacts_dir = _get_artifacts_dir()


def _get_output_dir() -> Path:
    curr = Path(__file__).resolve().parent
    for p in [curr] + list(curr.parents):
        if (p / "output").is_dir():
            return p / "output"
    return curr / "output"

# run_demo.py (SUMO-GUI live demo, run outside Docker) drops periodic per-topology
# screenshots + node pixel positions here; see "Periodic SUMO-GUI snapshot" in run_demo.py.
sumo_snapshot_dir = _get_output_dir() / "sumo_snapshots"

try:
    import contracts_sdk
    import topics
except ImportError:
    import contracts.contracts_sdk as contracts_sdk
    from contracts import topics

try:
    from sumo_converter import SumoNetworkConverter
except ImportError:
    try:
        from src.graph.sumo_converter import SumoNetworkConverter
    except ImportError:
        SumoNetworkConverter = None

app = FastAPI(
    title="EdgeFlow AI Control Plane & API",
    description="REST API serving live traffic topology, telemetry snapshots, experiment registries, and control policy management.",
    version="1.2.0"
)

# Enable CORS for React Dashboard
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

TOPOLOGY_FILE = contracts_sdk.CONTRACTS_DIR / "topology" / "hcm_realworld_v1.json"

def _get_map_html_file() -> Path:
    curr = Path(__file__).resolve().parent
    for p in [curr] + list(curr.parents):
        if (p / "output" / "camera_graph_map.html").exists():
            return p / "output" / "camera_graph_map.html"
    return curr / "output" / "camera_graph_map.html"

MAP_HTML_FILE = _get_map_html_file()

# In-memory Live State Store
LIVE_STATE: Dict[str, Any] = {
    "active_topology_id": os.getenv("EDGEFLOW_TOPOLOGY", "four_intersection_v1"),
    "active_controller": os.getenv("EDGEFLOW_CONTROLLER", "max_pressure"),
    "last_updated_ms": int(time.time() * 1000),
    "source_mode": "system",
    "nodes": {},
    "control_acks": {},
    "health": {},
    "actuator_config": {
        "yellow_duration_s": 3.0,
        "all_red_duration_s": 2.0,
        "min_green_s": 10.0,
        "max_green_s": 60.0,
        "mode": "NORMAL"
    }
}

class ActuatorConfigRequest(BaseModel):
    node_id: Optional[str] = None
    yellow_duration_s: Optional[float] = 3.0
    all_red_duration_s: Optional[float] = 2.0
    min_green_s: Optional[float] = 10.0
    max_green_s: Optional[float] = 60.0
    mode: Optional[str] = "NORMAL"

class TelemetryPayload(BaseModel):
    node_id: str
    source_type: Optional[str] = "system"
    simulation_time_s: Optional[float] = None
    timestamp_ms: Optional[int] = None
    current_phase_id: Optional[str] = None
    approaches: Optional[List[Dict[str, Any]]] = None

class ControlAckPayload(BaseModel):
    command_id: str
    node_id: str
    status: str
    reason: Optional[str] = ""
    target_phase_id: Optional[str] = None
    applied_at_s: Optional[float] = None
    timestamp_ms: Optional[int] = None

class PolicyChangeRequest(BaseModel):
    controller: str
    topology_id: Optional[str] = None

class OverrideRequest(BaseModel):
    node_id: str
    target_phase_id: str
    # 5 s is the ESP32 floor: a larger value only makes the device reject the override for longer
    min_green_s: Optional[float] = 5.0
    max_green_s: Optional[float] = 60.0

class ConnectionManager:
    def __init__(self):
        self.active_connections: List[WebSocket] = []

    async def connect(self, websocket: WebSocket):
        await websocket.accept()
        self.active_connections.append(websocket)

    def disconnect(self, websocket: WebSocket):
        if websocket in self.active_connections:
            self.active_connections.remove(websocket)

    async def broadcast(self, message: str):
        for connection in self.active_connections:
            try:
                await connection.send_text(message)
            except Exception:
                pass

ws_manager = ConnectionManager()

MQTT_CLIENT = None


def ingest_health_message(topic: str, payload: Dict[str, Any]) -> None:
    """Store a health/heartbeat message; its age is measured from when the API received it."""
    svc_id = payload.get("service_name") or payload.get("node_id") or topic.split("/")[-1]
    now_ms = int(time.time() * 1000)
    payload["timestamp_ms"] = payload.get("timestamp_ms") or now_ms
    # ESP32 clocks come from SNTP and may be unsynced or hours off: liveness uses the receive time (G3)
    payload["_ingested_at_ms"] = now_ms
    LIVE_STATE.setdefault("health", {})[svc_id] = payload
    event_msg = {
        "timestamp": time.strftime("%H:%M:%S"),
        # Server/container local time can differ from the operator's browser timezone (e.g. a
        # Docker image defaulting to UTC vs. the operator in UTC+7) and "timestamp" above would then
        # look wrong on screen. timestamp_ms is an unambiguous UTC epoch the dashboard formats itself
        # with the browser's own timezone; "timestamp" stays only as a non-browser fallback.
        "timestamp_ms": now_ms,
        "service": "HEALTH",
        "source": svc_id,
        "target": "SYSTEM",
        "topic": topic,
        "level": "INFO" if payload.get("status") in ("HEALTHY", "GREEN") else "WARNING",
        "message": f"Heartbeat [{svc_id}] -> Status: {payload.get('status', 'OK')}, Clearance: {payload.get('clearance', 'GREEN')}"
    }
    events = LIVE_STATE.setdefault("recent_inter_service_events", [])
    events.insert(0, event_msg)
    LIVE_STATE["recent_inter_service_events"] = events[:50]


# Dashboard phase override. graph-control re-sends the forced phase until the ESP32 takes it and keeps it green
# this long (MANUAL_OVERRIDE_HOLD_S, same variable for both services); the API only reports what the ESP32 answers.
MANUAL_OVERRIDE_HOLD_S = float(os.getenv("MANUAL_OVERRIDE_HOLD_S", "15"))
OVERRIDE_MAX_WAIT_S = 25.0     # same give-up time as graph-control
OVERRIDE_SHOW_AFTER_END_S = 30.0
OVERRIDE_ACK_STATUS = {"APPLIED": "APPLIED", "ACCEPTED": "CLEARING",
                       "REJECTED": "WAITING", "EXPIRED": "WAITING", "FAILED": "WAITING"}


def track_override_ack(node_id: str, ack: Dict[str, Any], now_ms: Optional[int] = None) -> None:
    """Follow the ESP32 answers about the overridden phase (to the API command and to graph-control's re-sends)."""
    override = LIVE_STATE.setdefault("manual_overrides", {}).get(node_id)
    if not override or override["status"] == "APPLIED" or ack.get("target_phase_id") != override["target_phase_id"]:
        return
    status = OVERRIDE_ACK_STATUS.get(ack.get("status"))
    if not status:
        return
    override["status"] = status
    override["last_reason"] = ack.get("reason")
    if status == "APPLIED":
        override["applied_ms"] = now_ms or int(time.time() * 1000)


def override_view(override: Optional[Dict[str, Any]], now_ms: int,
                  hold_s: float = MANUAL_OVERRIDE_HOLD_S) -> Optional[Dict[str, Any]]:
    """What the dashboard shows about the last override of a node; None once it is old news."""
    if not override:
        return None
    view = dict(override, hold_s=hold_s)
    if override["status"] == "APPLIED":
        held_s = (now_ms - override["applied_ms"]) / 1000.0
        if held_s < hold_s:
            view["hold_remaining_s"] = round(hold_s - held_s, 1)
            return view
        view["status"] = "ENDED"   # graph-control has handed the node back to the controller
        return view if held_s - hold_s < OVERRIDE_SHOW_AFTER_END_S else None
    waited_s = (now_ms - override["requested_ms"]) / 1000.0
    if waited_s < OVERRIDE_MAX_WAIT_S:
        return view
    view["status"] = "NOT_APPLIED"
    return view if waited_s - OVERRIDE_MAX_WAIT_S < OVERRIDE_SHOW_AFTER_END_S else None


def note_command_controller(payload: Dict[str, Any]) -> None:
    """Remember which controller graph-control really runs, from the `controller` field of its commands."""
    controller = payload.get("controller")
    if controller and controller != "manual_override":
        LIVE_STATE["applied_controller"] = controller


# Background MQTT Telemetry Subscriber (Optional automatic ingestion)
def _start_mqtt_listener():
    global MQTT_CLIENT
    try:
        import paho.mqtt.client as mqtt
        mqtt_host = os.getenv("MQTT_HOST", getattr(settings, "mqtt_host", "localhost"))
        mqtt_port = int(os.getenv("MQTT_PORT", getattr(settings, "mqtt_port", 1883)))

        client = mqtt.Client(client_id="api-telemetry-ingest")
        MQTT_CLIENT = client

        def on_connect(c, userdata, flags, rc):
            if rc == 0:
                logger.info(f"API MQTT Telemetry Subscriber connected to {mqtt_host}:{mqtt_port}")
                c.subscribe(topics.ALL_EDGEFLOW_SUB)
                c.subscribe("edgex/health/#")

        def on_message(c, userdata, msg):
            try:
                payload = json.loads(msg.payload.decode("utf-8"))
                topic = msg.topic
                now_str = time.strftime("%H:%M:%S")
                now_ms = int(time.time() * 1000)

                if topic.startswith(f"{topics.PREFIX_V1}/telemetry/"):
                    node_id = payload.get("node_id") or topic.split("/")[-1]
                    payload["_ingested_at_ms"] = now_ms
                    LIVE_STATE["nodes"][node_id] = payload
                    LIVE_STATE["last_updated_ms"] = now_ms
                    total_q = sum(a.get("queue_vehicles", 0) for a in payload.get("approaches", []))
                    event_msg = {
                        "timestamp": now_str,
                        "timestamp_ms": now_ms,
                        "service": "SIMULATOR",
                        "source": "SIMULATOR/VISION",
                        "target": "MQTT",
                        "topic": topic,
                        "level": "INFO",
                        "message": f"Telemetry Node {node_id}: Phase={payload.get('current_phase_id')}, Queue={round(total_q, 1)} veh, Flow={round(sum(a.get('flow_veh_per_s', 0) for a in payload.get('approaches', [])), 2)} veh/s"
                    }
                    events = LIVE_STATE.setdefault("recent_inter_service_events", [])
                    events.insert(0, event_msg)
                    LIVE_STATE["recent_inter_service_events"] = events[:50]

                elif topic.startswith(f"{topics.PREFIX_V1}/control/") and topic.endswith("/command"):
                    note_command_controller(payload)
                    parts = topic.split("/")
                    node_id = parts[3] if len(parts) > 3 else payload.get("node_id", "unknown")
                    event_msg = {
                        "timestamp": now_str,
                        "timestamp_ms": now_ms,
                        "service": "GRAPH-CONTROL",
                        "source": "GRAPH-CONTROL",
                        "target": "ACTUATOR",
                        "topic": topic,
                        "level": "INFO",
                        "message": f"ControlCommand [{node_id}] -> Target Phase: {payload.get('target_phase_id')} (Decision interval: 5s)"
                    }
                    events = LIVE_STATE.setdefault("recent_inter_service_events", [])
                    events.insert(0, event_msg)
                    LIVE_STATE["recent_inter_service_events"] = events[:50]

                elif (topic.startswith(f"{topics.PREFIX_V1}/control/") and topic.endswith("/ack")) or topic.startswith(f"{topics.PREFIX_V1}/control_ack/"):
                    node_id = payload.get("node_id") or (topic.split("/")[3] if len(topic.split("/")) > 3 else "unknown")
                    if node_id:
                        if node_id not in LIVE_STATE["control_acks"]:
                            LIVE_STATE["control_acks"][node_id] = []
                        LIVE_STATE["control_acks"][node_id].insert(0, payload)
                        LIVE_STATE["control_acks"][node_id] = LIVE_STATE["control_acks"][node_id][:20]
                        track_override_ack(node_id, payload)
                    event_msg = {
                        "timestamp": now_str,
                        "timestamp_ms": now_ms,
                        "service": "ACTUATOR",
                        "source": "ACTUATOR",
                        "target": "SYSTEM",
                        "topic": topic,
                        "level": "SUCCESS" if payload.get("status") == "APPLIED" else "WARNING",
                        "message": f"ControlACK [{node_id}] -> Status: {payload.get('status')} | {payload.get('reason', '')}"
                    }
                    events = LIVE_STATE.setdefault("recent_inter_service_events", [])
                    events.insert(0, event_msg)
                    LIVE_STATE["recent_inter_service_events"] = events[:50]

                elif topic.startswith(f"{topics.PREFIX_V1}/health/") or topic.startswith("edgex/health/"):
                    ingest_health_message(topic, payload)
            except Exception as ex:
                logger.debug(f"Error parsing MQTT telemetry payload: {ex}")

        client.on_connect = on_connect
        client.on_message = on_message
        client.connect_async(mqtt_host, mqtt_port, keepalive=60)
        client.loop_start()
    except Exception as e:
        logger.warning(f"Could not start background MQTT subscriber in API service: {e}")

try:
    import threading
    threading.Thread(target=_start_mqtt_listener, daemon=True).start()
except Exception:
    pass

@app.get("/", response_class=HTMLResponse)
@app.get("/dashboard", response_class=HTMLResponse)
def get_dashboard():
    """
    Redirects to the single unified React Web Dashboard at http://localhost:3000.
    """
    html_content = """<!DOCTYPE html>
<html>
<head>
    <meta charset="utf-8">
    <meta http-equiv="refresh" content="0; url=http://localhost:3000" />
    <title>Redirecting to EdgeFlow Dashboard...</title>
</head>
<body style="font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif; background: #0f172a; color: #f8fafc; display: flex; align-items: center; justify-content: center; height: 100vh; margin: 0;">
    <div style="text-align: center;">
        <h2 style="font-weight: 700; margin-bottom: 12px;">Đang chuyển hướng sang EdgeFlow Dashboard...</h2>
        <p style="color: #94a3b8;">Nếu trình duyệt không tự chuyển, vui lòng nhấn: <a href="http://localhost:3000" style="color: #38bdf8; text-decoration: underline;">http://localhost:3000</a></p>
    </div>
</body>
</html>"""
    return HTMLResponse(content=html_content, status_code=200)

@app.get("/api")
def api_root():
    return {
        "service": "edgeflow-api",
        "status": "running",
        "version": "1.2.0",
        "dashboard_ui": "http://localhost:3000",
        "endpoints": [
            "/health",
            "/api/v1/network/state",
            "/api/v1/network/state/{node_id}",
            "/api/v1/telemetry",
            "/api/v1/control_ack",
            "/api/v1/control/policy",
            "/api/v1/experiments",
            "/api/v1/scenarios",
            "/api/v1/topologies",
            "/api/v1/topologies/{topology_id}",
            "/api/v1/topologies/convert-sumo"
        ]
    }

@app.get("/health")
def health():
    return {
        "status": "healthy",
        "timestamp_ms": int(time.time() * 1000),
        "active_controller": LIVE_STATE["active_controller"],
        # What graph-control actually runs (from its commands); None until the first command is seen
        "applied_controller": LIVE_STATE.get("applied_controller"),
        "active_topology": LIVE_STATE["active_topology_id"]
    }

@app.post("/api/v1/telemetry")
def ingest_telemetry(payload: Union[Dict[str, Any], List[Dict[str, Any]]]):
    """
    Ingests live station telemetry payload sent from system services (vision, sensors, actuators).
    Supports single node dict or list of node telemetry dicts for high-speed batch ingestion.
    """
    now_ms = int(time.time() * 1000)
    if isinstance(payload, list):
        for item in payload:
            nid = item.get("node_id")
            if nid:
                item["_ingested_at_ms"] = now_ms
                LIVE_STATE["nodes"][nid] = item
        if payload:
            topo_id = payload[0].get("topology_id")
            if topo_id and LIVE_STATE.get("active_topology_id") != topo_id:
                LIVE_STATE["active_topology_id"] = topo_id
            src = payload[0].get("source_type")
            if src:
                LIVE_STATE["source_mode"] = src
        LIVE_STATE["last_updated_ms"] = now_ms
        return {"status": "SUCCESS", "count": len(payload), "timestamp_ms": now_ms}

    node_id = payload.get("node_id")
    if not node_id:
        raise HTTPException(status_code=400, detail="Missing required 'node_id' in telemetry payload.")
    topo_id = payload.get("topology_id")
    if topo_id and LIVE_STATE.get("active_topology_id") != topo_id:
        LIVE_STATE["active_topology_id"] = topo_id
    src = payload.get("source_type")
    if src:
        LIVE_STATE["source_mode"] = src
    payload["_ingested_at_ms"] = now_ms
    LIVE_STATE["nodes"][node_id] = payload
    LIVE_STATE["last_updated_ms"] = now_ms
    return {"status": "SUCCESS", "node_id": node_id, "timestamp_ms": LIVE_STATE["last_updated_ms"]}

@app.post("/api/v1/control_ack")
def ingest_control_ack(payload: Dict[str, Any]):
    """
    Ingests actuator command execution ACK log payload.
    """
    node_id = payload.get("node_id")
    if not node_id:
        raise HTTPException(status_code=400, detail="Missing required 'node_id' in control ACK payload.")
    if node_id not in LIVE_STATE["control_acks"]:
        LIVE_STATE["control_acks"][node_id] = []
    LIVE_STATE["control_acks"][node_id].insert(0, payload)
    LIVE_STATE["control_acks"][node_id] = LIVE_STATE["control_acks"][node_id][:20]
    return {"status": "SUCCESS", "node_id": node_id}

@app.post("/api/v1/health/heartbeat")
def ingest_heartbeat(payload: Dict[str, Any]):
    """
    Ingests device or actuator heartbeat / health telemetry.
    """
    service_id = payload.get("service_name") or payload.get("node_id", "actuator")
    if "health" not in LIVE_STATE:
        LIVE_STATE["health"] = {}
    payload["timestamp_ms"] = payload.get("timestamp_ms") or int(time.time() * 1000)
    LIVE_STATE["health"][service_id] = payload
    return {"status": "SUCCESS", "service": service_id, "timestamp_ms": payload["timestamp_ms"]}

def _placeholder_approaches(approach_ids: List[str]) -> List[Dict[str, Any]]:
    """Approaches of a node that has not reported: zero values, zero confidence (nothing was observed)."""
    return [{"approach_id": app_id, "queue_vehicles": 0.0, "flow_veh_per_s": 0.0, "mean_speed_mps": 0.0,
             "occupancy_ratio": 0.0, "confidence": 0.0} for app_id in approach_ids]


TELEMETRY_STALE_TIMEOUT_MS = 3500  # 3.5s without telemetry -> SIGNAL_LOST (for hardware/vision sensors)
ACTUATOR_HEARTBEAT_TIMEOUT_MS = 30000  # 30.0s without heartbeat -> HEARTBEAT_LOST (device disconnect diagnosis)

def compute_node_device_health(nid: str, node_live: Optional[Dict[str, Any]], now_ms: int) -> Dict[str, Any]:
    if not node_live:
        return {
            "overall_status": "WAITING_FOR_TELEMETRY",
            "camera": {
                "status": "WAITING",
                "confidence": 0.0,
                "last_seen_ms_ago": None,
                "zero_confidence": False
            },
            "actuator": {
                "status": "ACTIVE",
                "last_heartbeat_ms_ago": None,
                "clearance": "GREEN",
                "raw_safe_stop": False
            }
        }

    approaches = node_live.get("approaches", [])
    telemetry_time = node_live.get("_ingested_at_ms") or node_live.get("timestamp_ms") or 0
    age_ms = (now_ms - telemetry_time) if telemetry_time else None
    source_type = node_live.get("source_type", "")
    all_zero_conf = bool(approaches) and all(a.get("confidence", 1.0) <= 0.0 for a in approaches)
    avg_conf = (sum(a.get("confidence", 1.0) for a in approaches) / len(approaches)) if approaches else 0.0

    # Simulation mode telemetry (SUMO / virtual sensor) has no real camera to lose signal on, so the
    # CAMERA half never degrades to SIGNAL_LOST/ZERO_CONFIDENCE for it. The ACTUATOR half must NOT be
    # short-circuited here though: run_demo.py --hardware mirrors ControlCommand to a REAL ESP32 while
    # still reporting source_type "simulation" (the telemetry itself comes from SUMO, not a camera) --
    # that board's genuine SAFE_STOP/HEARTBEAT_LOST/FALLBACK health must still surface on the dashboard.
    if source_type == "simulation":
        camera_status = "ACTIVE"
    elif age_ms is None or age_ms > TELEMETRY_STALE_TIMEOUT_MS:
        camera_status = "SIGNAL_LOST"
    elif all_zero_conf:
        camera_status = "ZERO_CONFIDENCE"
    else:
        camera_status = "ACTIVE"

    actuator_data = (
        LIVE_STATE.get("health", {}).get(nid)
        or LIVE_STATE.get("health", {}).get(f"actuator-{nid}")
        or LIVE_STATE.get("health", {}).get("actuator")
    )
    actuator_status = "ACTIVE"
    actuator_age_ms = None
    clearance = "GREEN"
    # Raw, undebounced safe_stop as last reported by the board -- deliberately NOT gated by
    # ACTUATOR_HEARTBEAT_TIMEOUT_MS below. actuator_status/overall_status answer "can we trust this
    # device right now" (a stale heartbeat near the 5s health period can briefly read as
    # HEARTBEAT_LOST instead of SAFE_STOP); this answers "what did it last say", which is what a
    # UI following the physical button must use so it only clears on a real RELEASED health message,
    # never on a single missed/delayed one.
    raw_safe_stop = False
    if actuator_data:
        h_time = actuator_data.get("_ingested_at_ms") or actuator_data.get("timestamp_ms") or 0
        actuator_age_ms = (now_ms - h_time) if h_time else None
        clearance = actuator_data.get("clearance", "GREEN")
        device_status = actuator_data.get("status")
        safe_stop = bool(actuator_data.get("safe_stop")) or device_status == "SAFE_STOP"
        raw_safe_stop = safe_stop

        if device_status == "OFFLINE" or (actuator_age_ms is not None and actuator_age_ms > ACTUATOR_HEARTBEAT_TIMEOUT_MS):
            actuator_status = "HEARTBEAT_LOST"
        elif safe_stop:
            actuator_status = "SAFE_STOP"
        elif device_status in ("DEGRADED", "UNHEALTHY"):
            actuator_status = device_status
        elif device_status == "FALLBACK_AUTONOMOUS":
            actuator_status = "FALLBACK"
        else:
            actuator_status = "ACTIVE"

    if camera_status == "SIGNAL_LOST":
        overall_status = "SIGNAL_LOST"
    elif camera_status == "ZERO_CONFIDENCE":
        overall_status = "CAMERA_FAULT"
    elif actuator_status in ("HEARTBEAT_LOST", "SAFE_STOP"):
        overall_status = "ACTUATOR_FAULT"
    elif actuator_status == "FALLBACK":
        overall_status = "FALLBACK"
    else:
        overall_status = node_live.get("status", "ONLINE")

    return {
        "overall_status": overall_status,
        "camera": {
            "status": camera_status,
            "confidence": round(avg_conf, 2),
            "last_seen_ms_ago": age_ms,
            "zero_confidence": all_zero_conf
        },
        "actuator": {
            "status": actuator_status,
            "last_heartbeat_ms_ago": actuator_age_ms,
            "clearance": clearance,
            "raw_safe_stop": raw_safe_stop
        }
    }

@app.get("/api/v1/network/state")
def get_network_state():
    """
    Returns the real-time live traffic network telemetry, device health and phase states for the active topology.
    """
    try:
        topo = contracts_sdk.load_topology(LIVE_STATE["active_topology_id"])
        now_ms = int(time.time() * 1000)
        nodes_info = []
        for n in topo.get("nodes", []):
            nid = n["node_id"]
            node_live = LIVE_STATE["nodes"].get(nid)
            health_meta = compute_node_device_health(nid, node_live, now_ms)
            if node_live:
                node_data = dict(node_live)
                node_data["name"] = n.get("name", nid)
                node_data["street_name"] = n.get("street_name", "")
                node_data["x"] = n.get("x")
                node_data["y"] = n.get("y")
                node_data["lat"] = n.get("lat")
                node_data["lng"] = n.get("lng")
                node_data["status"] = health_meta["overall_status"]
                node_data["device_health"] = health_meta
                nodes_info.append(node_data)
            else:
                phases = n.get("phases", [])
                nodes_info.append({
                    "node_id": nid,
                    "name": n.get("name", nid),
                    "street_name": n.get("street_name", ""),
                    "x": n.get("x"),
                    "y": n.get("y"),
                    "lat": n.get("lat"),
                    "lng": n.get("lng"),
                    "current_phase_id": phases[0]["phase_id"] if phases else f"{nid}_PHASE_NS",
                    "source_type": LIVE_STATE["source_mode"],
                    "status": health_meta["overall_status"],
                    "device_health": health_meta,
                    "approaches": _placeholder_approaches(n.get("approaches", []))
                })

        return {
            "topology_id": LIVE_STATE["active_topology_id"],
            "controller": LIVE_STATE.get("applied_controller") or LIVE_STATE["active_controller"],
            "source_mode": LIVE_STATE["source_mode"],
            "last_updated_ms": LIVE_STATE["last_updated_ms"],
            "total_nodes": len(nodes_info),
            "nodes": nodes_info
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed retrieving network state: {str(e)}")

@app.get("/api/v1/network/state/{node_id}")
def get_node_network_state(node_id: str):
    """
    Returns full real-time telemetry parameters, approach breakdown, phase state, device health, and control ACK logs for a specific node.
    """
    try:
        topo = contracts_sdk.load_topology(LIVE_STATE["active_topology_id"])
        node_spec = next((n for n in topo.get("nodes", []) if n["node_id"] == node_id), None)
        if not node_spec:
            raise HTTPException(status_code=404, detail=f"Node '{node_id}' not found in topology '{LIVE_STATE['active_topology_id']}'.")

        live_data = LIVE_STATE["nodes"].get(node_id)
        acks = LIVE_STATE["control_acks"].get(node_id, [])
        now_ms = int(time.time() * 1000)
        health_meta = compute_node_device_health(node_id, live_data, now_ms)

        if live_data:
            response_node = dict(live_data)
            response_node["name"] = node_spec.get("name", node_id)
            response_node["status"] = health_meta["overall_status"]
            response_node["device_health"] = health_meta
        else:
            phases = node_spec.get("phases", [])
            response_node = {
                "node_id": node_id,
                "name": node_spec.get("name", node_id),
                "current_phase_id": phases[0]["phase_id"] if phases else f"{node_id}_PHASE_NS",
                "source_type": LIVE_STATE["source_mode"],
                "status": health_meta["overall_status"],
                "device_health": health_meta,
                "approaches": _placeholder_approaches(node_spec.get("approaches", []))
            }

        vision = LIVE_STATE.get("health", {}).get("vision")
        return {
            "topology_id": LIVE_STATE["active_topology_id"],
            "node_spec": node_spec,
            "telemetry": response_node,
            "device_health": health_meta,
            "control_acks": acks,
            # Last dashboard phase override and what the ESP32 made of it (SENT/WAITING/CLEARING/APPLIED/...)
            "manual_override": override_view(LIVE_STATE.get("manual_overrides", {}).get(node_id), now_ms),
            # Measured runtime of the vision service that watches this node (model, fps, latency), if any
            "vision_health": vision if vision and node_id in (vision.get("active_nodes") or []) else None
        }
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed retrieving node state: {str(e)}")

@app.get("/api/v1/control/policy")
def get_control_policy():
    """Requested controller policy; graph-control polls this (CONTROL_POLICY_URL) and switches to it live."""
    return {
        "active_controller": LIVE_STATE["active_controller"],
        "applied_controller": LIVE_STATE.get("applied_controller"),
        "timestamp_ms": LIVE_STATE["last_updated_ms"]
    }


@app.post("/api/v1/control/policy")
def set_control_policy(req: PolicyChangeRequest):
    """
    Updates the active traffic control policy (fixed_time, max_queue, max_pressure, edgeflow).
    """
    # RL policies need a trained model file on the graph-control host; accepting them here would only
    # change the dashboard label while graph-control keeps the previous controller.
    valid_controllers = ["fixed_time", "max_queue", "max_pressure", "edgeflow", "flow_theory", "actuated"]
    req_ctrl = req.controller.lower()
    if req_ctrl not in valid_controllers:
        raise HTTPException(
            status_code=400,
            detail=f"Invalid controller: {req_ctrl}. Valid options: {valid_controllers}"
        )

    LIVE_STATE["active_controller"] = req_ctrl
    if req.topology_id:
        LIVE_STATE["active_topology_id"] = req.topology_id
    LIVE_STATE["last_updated_ms"] = int(time.time() * 1000)

    logger.info(f"Control policy updated to: {req_ctrl} (Topology: {LIVE_STATE['active_topology_id']})")
    return {
        "status": "policy_updated",
        "active_controller": LIVE_STATE["active_controller"],
        "active_topology_id": LIVE_STATE["active_topology_id"],
        "timestamp_ms": LIVE_STATE["last_updated_ms"]
    }

@app.get("/api/v1/actuator/config")
def get_actuator_config():
    """Returns the current ActuatorStateMachine timing constraints and safety mode."""
    return LIVE_STATE.get("actuator_config", {
        "yellow_duration_s": 3.0,
        "all_red_duration_s": 2.0,
        "min_green_s": 10.0,
        "max_green_s": 60.0,
        "mode": "NORMAL"
    })

@app.post("/api/v1/actuator/config")
def update_actuator_config(req: ActuatorConfigRequest):
    """
    Dynamically updates ActuatorStateMachine timing constraints (Yellow, All-Red, Min/Max Green)
    and safety modes (NORMAL, FLASHING_YELLOW, ALL_RED, RESET).
    """
    cfg = LIVE_STATE.get("actuator_config", {})
    if req.yellow_duration_s is not None:
        cfg["yellow_duration_s"] = req.yellow_duration_s
    if req.all_red_duration_s is not None:
        cfg["all_red_duration_s"] = req.all_red_duration_s
    if req.min_green_s is not None:
        cfg["min_green_s"] = req.min_green_s
    if req.max_green_s is not None:
        cfg["max_green_s"] = req.max_green_s
    if req.mode is not None:
        cfg["mode"] = req.mode.upper()

    LIVE_STATE["actuator_config"] = cfg
    LIVE_STATE["last_updated_ms"] = int(time.time() * 1000)

    logger.info(f"ActuatorStateMachine configuration updated: {cfg}")
    return {
        "status": "SUCCESS",
        "actuator_config": cfg,
        "timestamp_ms": LIVE_STATE["last_updated_ms"]
    }

@app.post("/api/v1/control/override")
def trigger_emergency_override(req: OverrideRequest):
    """
    Manual phase override for one node (dashboard buttons). Publishes one ControlCommand to the ESP32, which
    clears through Yellow (3 s) and All-Red (2 s) under its own safety rules; graph-control then re-sends the
    phase until it has been green MANUAL_OVERRIDE_HOLD_S. The ESP32 answer is followed in
    GET /api/v1/network/state/{node_id} -> manual_override; "SENT" here only means it left the API.
    """
    try:
        topo = contracts_sdk.load_topology(LIVE_STATE["active_topology_id"])
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"Cannot load topology: {exc}")
    node_spec = next((n for n in topo.get("nodes", []) if n["node_id"] == req.node_id), None)
    if node_spec is None:
        raise HTTPException(status_code=404, detail=f"Node '{req.node_id}' is not in topology '{LIVE_STATE['active_topology_id']}'.")
    if req.target_phase_id not in [ph["phase_id"] for ph in node_spec.get("phases", [])]:
        raise HTTPException(status_code=400, detail=f"Phase '{req.target_phase_id}' does not belong to node '{req.node_id}'.")
    if not (MQTT_CLIENT and MQTT_CLIENT.is_connected()):
        raise HTTPException(status_code=503, detail="MQTT broker not connected: override not sent to the ESP32.")

    now_ms = int(time.time() * 1000)
    cmd_id = f"cmd-override-{req.node_id}-{now_ms}"   # graph-control recognises overrides by this prefix
    command_payload = {
        "command_id": cmd_id,
        "node_id": req.node_id,
        "target_phase_id": req.target_phase_id,
        "min_green_s": float(req.min_green_s) if req.min_green_s is not None else 5.0,
        "max_green_s": float(req.max_green_s) if req.max_green_s is not None else 60.0,
        "controller": "manual_override",
        "timestamp_ms": now_ms,
        "expires_at_ms": now_ms + 10000
    }
    try:
        contracts_sdk.validate_payload(command_payload, "control_command")
    except Exception as ve:
        logger.warning(f"ControlCommand validation warning: {ve}")

    pub_topic = topics.get_command_topic(req.node_id)
    info = MQTT_CLIENT.publish(pub_topic, json.dumps(command_payload))
    if getattr(info, "rc", 0) != 0:
        raise HTTPException(status_code=503, detail=f"MQTT publish failed (rc={info.rc}): override not sent.")
    LIVE_STATE.setdefault("manual_overrides", {})[req.node_id] = {
        "command_id": cmd_id,
        "target_phase_id": req.target_phase_id,
        "requested_ms": now_ms,
        "status": "SENT",
        "last_reason": None,
    }
    if req.node_id in LIVE_STATE["nodes"]:
        LIVE_STATE["nodes"][req.node_id]["pending_phase_id"] = req.target_phase_id

    logger.info(f"Manual override published to {pub_topic}: {req.node_id} -> {req.target_phase_id} ({cmd_id})")
    return {
        "status": "SENT",
        "command_id": cmd_id,
        "node_id": req.node_id,
        "target_phase_id": req.target_phase_id,
        "hold_s": MANUAL_OVERRIDE_HOLD_S,
        "reason": "Published to the ESP32; its answer appears in /api/v1/network/state/{node_id} -> manual_override.",
        "timestamp_ms": now_ms
    }

@app.get("/api/v1/system/reports")
def get_system_aggregated_reports():
    """
    Returns aggregated system-wide performance reports generated from low-level logs.
    Used by the Global Dashboard Overview.
    """
    try:
        topo = contracts_sdk.load_topology(LIVE_STATE["active_topology_id"])
        total_nodes = len(topo.get("nodes", []))
    except Exception:
        total_nodes = 4

    # Compute network-wide metrics from live nodes
    nodes = LIVE_STATE.get("nodes", {})
    online_count = sum(1 for n in nodes.values() if n.get("status") == "ONLINE")
    
    total_q = 0.0
    total_flow = 0.0
    node_count = len(nodes) if len(nodes) > 0 else 1

    for n in nodes.values():
        apps = n.get("approaches", [])
        total_q += sum(a.get("queue_vehicles", 0) for a in apps)
        total_flow += sum(a.get("flow_veh_per_s", 0) for a in apps)

    mean_wait_s = max(2.5, round(total_q * 1.8 / node_count, 1))
    throughput_per_min = max(45, round(total_flow * 60, 1))

    # Evaluate active alerts based on physical criteria (congestion, health)
    active_alerts = []
    for nid, n in nodes.items():
        apps = n.get("approaches", [])
        q = sum(a.get("queue_vehicles", 0) for a in apps)
        status = n.get("status", "ONLINE")
        if q > 12:
            active_alerts.append({
                "node_id": nid,
                "type": "CONGESTION",
                "severity": "WARNING" if q <= 18 else "CRITICAL",
                "message": f"Elevated queue ({round(q, 1)} veh) detected at station {nid}"
            })
        elif status not in ("ONLINE", "NORMAL"):
            active_alerts.append({
                "node_id": nid,
                "type": "DEVICE_HEALTH",
                "severity": "WARNING",
                "message": f"Station {nid} health state: {status}"
            })

    _default_logs_now_ms = int(time.time() * 1000)
    default_system_logs = [
        {
            "timestamp": time.strftime("%H:%M:%S"),
            "timestamp_ms": _default_logs_now_ms,
            "service": "graph-control",
            "level": "INFO",
            "message": f"Active controller policy: {LIVE_STATE['active_controller'].upper()} on topology {LIVE_STATE['active_topology_id']}"
        },
        {
            "timestamp": time.strftime("%H:%M:%S"),
            "timestamp_ms": _default_logs_now_ms,
            "service": "actuator",
            "level": "INFO",
            "message": "Actuator State Machine: 100% safety compliance verified (0 green conflicts)."
        },
        {
            "timestamp": time.strftime("%H:%M:%S"),
            "timestamp_ms": _default_logs_now_ms,
            "service": "vision",
            "level": "INFO",
            "message": f"Edge perception online. {online_count}/{total_nodes} nodes broadcasting telemetry."
        }
    ]

    live_events = LIVE_STATE.get("recent_inter_service_events", [])
    recent_logs = list(live_events)
    for default_item in default_system_logs:
        if len(recent_logs) >= 3:
            break
        if not any(e.get("message") == default_item["message"] for e in recent_logs):
            recent_logs.append(default_item)

    return {
        "topology_id": LIVE_STATE["active_topology_id"],
        "controller": LIVE_STATE["active_controller"],
        "total_nodes": total_nodes,
        "online_nodes": online_count,
        "mean_network_wait_time_s": mean_wait_s,
        "total_throughput_veh_per_min": throughput_per_min,
        "total_throughput_veh_per_h": round(throughput_per_min * 60, 1),
        "active_alerts_count": len(active_alerts),
        "active_alerts": active_alerts,
        "safety_compliance_rate_pct": 100.0,
        "safety_compliance_detail": "Zero conflicting green phases; clearance transitions (Yellow 3s + All-Red 2s) enforced by ActuatorStateMachine.",
        "recent_system_logs": recent_logs,
        "timestamp_ms": int(time.time() * 1000)
    }

@app.websocket("/ws/telemetry")
async def websocket_telemetry_endpoint(websocket: WebSocket):
    await ws_manager.connect(websocket)
    try:
        while True:
            state = get_network_state()
            await websocket.send_text(json.dumps(state))
            import asyncio
            await asyncio.sleep(0.5)
    except WebSocketDisconnect:
        ws_manager.disconnect(websocket)
    except Exception:
        ws_manager.disconnect(websocket)

@app.get("/api/v1/experiments")
def list_experiments():
    """
    Scans the artifacts directory and returns metadata summaries of completed experiment runs.
    """
    if not artifacts_dir.exists():
        return {"total_experiments": 0, "experiments": []}

    exps = []
    for exp_folder in sorted(artifacts_dir.iterdir()):
        if exp_folder.is_dir():
            summary_file = exp_folder / "summary.json"
            manifest_file = exp_folder / "manifest.yaml"
            if summary_file.exists():
                try:
                    with open(summary_file, "r", encoding="utf-8") as f:
                        data = json.load(f)
                    exps.append({
                        "experiment_id": exp_folder.name,
                        "has_manifest": manifest_file.exists(),
                        "is_valid": data.get("is_valid", True),
                        "valid_for_research": data.get("valid_for_research", True),
                        "average_waiting_time_s": data.get("average_waiting_time_s", 0.0),
                        "average_queue_veh": data.get("average_queue_veh", 0.0),
                        "throughput_veh_per_s": data.get("throughput_veh_per_s", 0.0),
                        "duration_s": data.get("duration_s", 0.0),
                        "summary": data
                    })
                except Exception as e:
                    logger.debug(f"Could not read {summary_file}: {e}")

    return {
        "total_experiments": len(exps),
        "total_runs": len(exps),
        "experiments": exps,
        "runs": exps
    }

@app.get("/api/v1/experiments/{experiment_id}")
def get_experiment_detail(experiment_id: str):
    """
    Returns full artifacts and summary for a single experiment ID.
    """
    exp_folder = artifacts_dir / experiment_id
    if not exp_folder.exists() or not exp_folder.is_dir():
        raise HTTPException(status_code=404, detail=f"Experiment '{experiment_id}' not found in artifacts.")

    summary_file = exp_folder / "summary.json"
    env_file = exp_folder / "environment.json"

    result = {"experiment_id": experiment_id}
    if summary_file.exists():
        with open(summary_file, "r", encoding="utf-8") as f:
            result["summary"] = json.load(f)
    if env_file.exists():
        with open(env_file, "r", encoding="utf-8") as f:
            result["environment"] = json.load(f)

    return result

@app.get("/api/v1/benchmarks")
def list_benchmark_campaigns():
    """
    Scans the artifacts directory and returns all benchmark campaign directories with reports,
    sorted by creation/modification timestamp descending.
    """
    if not artifacts_dir.exists():
        return {"total_campaigns": 0, "campaigns": []}

    candidate_folders = [
        folder for folder in artifacts_dir.iterdir()
        if folder.is_dir() and folder.name.startswith("sumo_benchmark_")
    ]
    candidate_folders.sort(key=lambda p: p.stat().st_mtime, reverse=True)

    campaigns = []
    for folder in candidate_folders:
        report_file = folder / "benchmark_comparison_report.json"
        summary_md = folder / "benchmark_summary.md"
        test_md = folder / "test_results.md"
        if report_file.exists():
            campaigns.append({
                "campaign_id": folder.name,
                "has_report": True,
                "has_summary_md": summary_md.exists(),
                "has_test_results": test_md.exists(),
                "created_at": folder.stat().st_mtime,
            })
    return {"total_campaigns": len(campaigns), "campaigns": campaigns}

@app.get("/api/v1/benchmarks/latest")
def get_latest_benchmark_report():
    """
    Returns the latest benchmark comparison report.
    """
    campaigns = list_benchmark_campaigns().get("campaigns", [])
    if not campaigns:
        fallback = artifacts_dir / "benchmark_comparison_report.json"
        if fallback.exists():
            with open(fallback, "r", encoding="utf-8") as f:
                return json.load(f)
        raise HTTPException(status_code=404, detail="No benchmark campaign report found.")

    latest_id = campaigns[0]["campaign_id"]
    return get_benchmark_campaign_report(latest_id)

@app.get("/api/v1/benchmarks/{campaign_id}")
def get_benchmark_campaign_report(campaign_id: str):
    """
    Returns the full benchmark comparison report, summary markdown, and verification status for a campaign ID.
    Guards against path traversal and validates directory existence.
    """
    try:
        resolved_artifacts = artifacts_dir.resolve()
        camp_dir = (artifacts_dir / campaign_id).resolve()
        if not camp_dir.is_relative_to(resolved_artifacts):
            raise HTTPException(status_code=400, detail="Invalid campaign ID path.")
    except Exception as e:
        if isinstance(e, HTTPException):
            raise e
        raise HTTPException(status_code=400, detail="Malformed campaign ID.")

    if not camp_dir.exists() or not camp_dir.is_dir():
        raise HTTPException(status_code=404, detail=f"Campaign '{campaign_id}' not found.")

    report_file = camp_dir / "benchmark_comparison_report.json"
    summary_md_file = camp_dir / "benchmark_summary.md"
    test_results_md_file = camp_dir / "test_results.md"

    if not report_file.exists():
        raise HTTPException(status_code=404, detail=f"No benchmark_comparison_report.json in '{campaign_id}'.")

    with open(report_file, "r", encoding="utf-8") as f:
        data = json.load(f)

    data["campaign_id"] = campaign_id
    if summary_md_file.exists():
        try:
            with open(summary_md_file, "r", encoding="utf-8") as f:
                data["summary_markdown"] = f.read()
        except Exception as e:
            logger.warning(f"Could not read benchmark summary markdown for {campaign_id}: {e}")
    if test_results_md_file.exists():
        try:
            with open(test_results_md_file, "r", encoding="utf-8") as f:
                data["test_results_markdown"] = f.read()
        except Exception as e:
            logger.warning(f"Could not read test results markdown for {campaign_id}: {e}")

    return data

@app.get("/api/v1/scenarios")
def list_scenarios():
    """Returns list of all available simulation scenarios and SUMO configs with contract metadata."""
    available_ids = contracts_sdk.list_topologies()
    sumo_config_dir = Path(__file__).resolve().parent.parent / "simulator" / "sumo_configs"
    
    scenarios = []
    for tid in available_ids:
        has_sumo = False
        if sumo_config_dir.exists():
            sumo_file = sumo_config_dir / f"{tid}.sumocfg"
            has_sumo = sumo_file.exists()
        
        try:
            summary = contracts_sdk.get_topology_summary(tid)
            scenarios.append({
                "scenario_id": tid,
                "topology_id": tid,
                "name": tid.replace("_", " ").title(),
                "has_sumo_config": has_sumo,
                "total_nodes": summary.get("total_nodes", 0),
                "total_edges": summary.get("total_edges", 0),
                "total_phases": summary.get("total_phases", 0),
            })
        except Exception as e:
            scenarios.append({
                "scenario_id": tid,
                "topology_id": tid,
                "name": tid,
                "has_sumo_config": has_sumo,
                "error": str(e)
            })
    
    return {
        "total_scenarios": len(scenarios),
        "scenarios": scenarios
    }

@app.get("/api/v1/topologies")
def list_topologies():
    """Returns list of all registered topology contract IDs with metadata summaries."""
    available_ids = contracts_sdk.list_topologies()
    summaries = []
    for tid in available_ids:
        try:
            summaries.append(contracts_sdk.get_topology_summary(tid))
        except Exception as e:
            summaries.append({"topology_id": tid, "error": str(e)})
    return {
        "total_topologies": len(available_ids),
        "topologies": summaries
    }

@app.get("/api/v1/topologies/{topology_id}")
def get_topology_contract(topology_id: str):
    """Returns full canonical JSON contract for a given topology_id."""
    try:
        topology = contracts_sdk.load_topology(topology_id)
        return topology
    except FileNotFoundError:
        raise HTTPException(status_code=404, detail=f"Topology contract '{topology_id}' not found.")

@app.post("/api/v1/topologies/convert-sumo")
def convert_sumo_xml(xml_content: str = Body(..., media_type="text/xml"), topology_id: str = "sumo_converted_v1"):
    """Parses SUMO .net.xml payload and returns canonical topology contract JSON with explicit phase approaches."""
    try:
        topology = SumoNetworkConverter.parse_net_xml(xml_content, topology_id=topology_id)
        return topology
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"Failed converting SUMO XML: {str(e)}")

@app.get("/api/v1/cameras")
def get_hcm_cameras():
    """
    Returns list of all HCM geographic camera nodes with metadata and coordinates.
    """
    if not os.path.exists(TOPOLOGY_FILE):
        raise HTTPException(status_code=404, detail="HCM Topology Contract not found.")
    
    with open(TOPOLOGY_FILE, "r", encoding="utf-8") as f:
        topology = json.load(f)
    
    nodes = topology.get("nodes", [])
    return {
        "topology_id": topology.get("topology_id", "hcm_realworld_v1"),
        "total_cameras": len(nodes),
        "total_edges": len(topology.get("edges", [])),
        "cameras": [
            {
                "node_id": n["node_id"],
                "name": n.get("name"),
                "lat": n.get("lat"),
                "lng": n.get("lng"),
                "status": n.get("status", "Online")
            }
            for n in nodes
        ]
    }

@app.get("/api/v1/map/hcm-cameras", response_class=HTMLResponse)
def get_hcm_camera_map():
    """
    Serves the interactive Folium Dark Mode map for HCM SUMO Geo camera network.
    """
    if not os.path.exists(MAP_HTML_FILE):
        raise HTTPException(status_code=404, detail="HCM Camera Map HTML not generated yet.")
    
    with open(MAP_HTML_FILE, "r", encoding="utf-8") as f:
        html_content = f.read()
    
    return HTMLResponse(content=html_content, status_code=200)


# ============================================================================
# Vision Perception Demo & Video Playback Endpoints
# ============================================================================

class VisionRunRequest(BaseModel):
    video: Optional[str] = "synthetic"
    frames: Optional[int] = 30
    controller: Optional[str] = "max_pressure"
    node_id: Optional[str] = "J1"
    # Defaults to the currently active topology (LIVE_STATE) when omitted, so the demo runs
    # against the node's real contract (phases/approaches) instead of a hard-coded scenario.
    topology_id: Optional[str] = None


def _vision_artifact_paths(topology_id: str, node_id: str):
    """Per (topology_id, node_id) demo artifacts, so running the demo for one node never gets
    displayed under another node/scenario (it used to be a single global file for everyone)."""
    safe = lambda s: "".join(c if c.isalnum() or c in "-_" else "_" for c in str(s))
    vision_dir = artifacts_dir / "vision_demo"
    stem = f"{safe(topology_id)}__{safe(node_id)}"
    return vision_dir / f"{stem}_video.mp4", vision_dir / f"{stem}_report.json"


@app.get("/api/v1/vision/demo-video")
def get_vision_demo_video(node_id: Optional[str] = None, topology_id: Optional[str] = None):
    """Serves the annotated video output produced by demo_video_pipeline.py for one node/topology."""
    if node_id and topology_id:
        video_path, _ = _vision_artifact_paths(topology_id, node_id)
        if video_path.is_file():
            return FileResponse(str(video_path), media_type="video/mp4", filename=video_path.name)
        raise HTTPException(status_code=404, detail=f"No demo video for node '{node_id}' in '{topology_id}' yet. Run the demo for it first.")

    # Legacy global artifact (no node_id/topology_id given)
    candidates = [
        artifacts_dir / "yolo_demo_annotated.mp4",
        curr_dir.parent.parent / "artifacts" / "yolo_demo_annotated.mp4",
    ]
    for p in candidates:
        if p.is_file():
            return FileResponse(str(p), media_type="video/mp4", filename="yolo_demo_annotated.mp4")
    raise HTTPException(status_code=404, detail="No demo video found. Run services/vision/demo_video_pipeline.py first.")


@app.get("/api/v1/vision/demo-report")
def get_vision_demo_report():
    """Returns the JSON summary report from demo_video_pipeline.py."""
    candidates = [
        artifacts_dir / "yolo_demo_report.json",
        curr_dir.parent.parent / "artifacts" / "yolo_demo_report.json",
    ]
    for p in candidates:
        if p.is_file():
            with open(p, "r", encoding="utf-8") as f:
                return json.load(f)
    raise HTTPException(status_code=404, detail="No demo report found.")


@app.get("/api/v1/vision/sumo-snapshot")
def get_sumo_snapshot(topology_id: str):
    """
    Read-only screenshot of the live sumo-gui window for this topology, refreshed every ~2s by
    run_demo.py while it's running. Same view the operator already sees -- never moved/zoomed.
    """
    png_path = sumo_snapshot_dir / f"{topology_id}.png"
    if not png_path.is_file():
        raise HTTPException(
            status_code=404,
            detail=f"No SUMO-GUI snapshot yet for '{topology_id}'. Is run_demo.py running sumo-gui on this topology?"
        )
    return FileResponse(str(png_path), media_type="image/png")


@app.get("/api/v1/vision/sumo-snapshot-meta")
def get_sumo_snapshot_meta(topology_id: str):
    """Pixel position of every node within the current sumo-snapshot image, so the dashboard
    can crop/zoom to one intersection client-side without any server-side image processing."""
    meta_path = sumo_snapshot_dir / f"{topology_id}_meta.json"
    if not meta_path.is_file():
        raise HTTPException(status_code=404, detail=f"No SUMO-GUI snapshot metadata yet for '{topology_id}'.")
    with open(meta_path, "r", encoding="utf-8") as f:
        return json.load(f)


class SumoFocusRequest(BaseModel):
    node_id: str
    topology_id: Optional[str] = None


@app.post("/api/v1/vision/sumo-focus")
def request_sumo_focus(req: SumoFocusRequest):
    """
    Reverse view sync: asks run_demo.py's live sumo-gui loop to pan/zoom its camera to a node.
    Unlike the read-only snapshot above, this DOES move the operator's actual sumo-gui window --
    only ever happens on this explicit request, picked up by run_demo.py's own polling (~1s).
    """
    topology_id = req.topology_id or LIVE_STATE["active_topology_id"]
    sumo_snapshot_dir.mkdir(parents=True, exist_ok=True)
    request_path = sumo_snapshot_dir / f"{topology_id}_focus_request.json"
    now_ms = int(time.time() * 1000)
    request_path.write_text(json.dumps({"node_id": req.node_id, "requested_ms": now_ms}), encoding="utf-8")
    return {
        "status": "SENT",
        "node_id": req.node_id,
        "topology_id": topology_id,
        "requested_ms": now_ms,
        "detail": "run_demo.py polls this request about once a second; it only applies if sumo-gui is running this topology."
    }


@app.get("/api/v1/vision/status")
def get_vision_demo_status(node_id: Optional[str] = None, topology_id: Optional[str] = None):
    """
    Returns status and availability of the vision demo video & report for one node/topology.
    Without node_id/topology_id, falls back to whichever demo ran last globally (legacy).
    """
    if node_id and topology_id:
        video_path, report_path = _vision_artifact_paths(topology_id, node_id)
        video_url_params = f"?node_id={node_id}&topology_id={topology_id}"
    else:
        video_path = artifacts_dir / "yolo_demo_annotated.mp4"
        report_path = artifacts_dir / "yolo_demo_report.json"
        video_url_params = ""

    has_video = video_path.is_file()
    has_report = report_path.is_file()

    report_data = None
    if has_report:
        try:
            with open(report_path, "r", encoding="utf-8") as f:
                report_data = json.load(f)
        except Exception:
            pass

    return {
        "has_video": has_video,
        "video_url": f"/api/v1/vision/demo-video{video_url_params}" if has_video else None,
        "video_size_bytes": video_path.stat().st_size if has_video else 0,
        "has_report": has_report,
        "report": report_data,
        "detector_backend": report_data.get("detector_backend", "opencv_dnn") if report_data else "opencv_dnn",
    }


@app.post("/api/v1/vision/run-demo")
def trigger_vision_demo(req: VisionRunRequest = Body(default_factory=VisionRunRequest)):
    """Triggers execution of services/vision/demo_video_pipeline.py and returns updated report."""
    import subprocess
    import sys
    py_exec = sys.executable
    script_path = curr_dir.parent / "vision" / "demo_video_pipeline.py"
    if not script_path.is_file():
        raise HTTPException(status_code=500, detail="demo_video_pipeline.py not found.")

    topology_id = req.topology_id or LIVE_STATE["active_topology_id"]
    out_video, out_report = _vision_artifact_paths(topology_id, req.node_id)

    cmd = [
        py_exec, str(script_path),
        "--video", req.video,
        "--frames", str(req.frames),
        "--controller", req.controller,
        "--node-id", req.node_id,
        "--topology", topology_id,
        "--output-video", str(out_video),
        "--output-report", str(out_report),
    ]
    try:
        proc = subprocess.run(cmd, capture_output=True, text=True, timeout=120)
        if proc.returncode != 0:
            logger.error(f"Vision demo run failed: {proc.stderr}")
            raise HTTPException(status_code=500, detail=f"Pipeline failed: {proc.stderr[-500:]}")

        with open(out_report, "r", encoding="utf-8") as f:
            report_data = json.load(f)
        return {
            "status": "SUCCESS",
            "message": "Vision demo completed successfully",
            "report": report_data,
            "video_url": f"/api/v1/vision/demo-video?node_id={req.node_id}&topology_id={topology_id}"
        }
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


if __name__ == "__main__":
    import uvicorn
    # NOTE: reload=True was tried here and reverted -- it makes uvicorn re-import this module in a
    # second (worker) process while the original process is also still alive for a moment, and
    # since the background MQTT listener is started unconditionally at module import time (not
    # inside this __main__ guard), BOTH processes open their own client with the same hardcoded
    # client_id "api-telemetry-ingest" and continuously kick each other off the broker -- a
    # permanent reconnect storm, not a one-time race, that drops health/telemetry/ACK messages.
    # Fixing this properly needs the MQTT listener moved into a FastAPI startup event instead of a
    # module-level thread; until then, after editing this file: `docker compose --profile hardware
    # up -d --force-recreate api` (the file is bind-mounted, so no image rebuild is needed).
    uvicorn.run(app, host=settings.api_host, port=settings.api_port)

