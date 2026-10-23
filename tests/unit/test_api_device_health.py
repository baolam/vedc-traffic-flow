"""Device health the API derives from ESP32 health messages (dashboard status per node)."""
import time

import pytest

try:
    from fastapi.testclient import TestClient
    from services.api.main import app, LIVE_STATE, compute_node_device_health
    client = TestClient(app)
    API_AVAILABLE = True
except Exception:  # noqa: BLE001 - optional dependencies
    API_AVAILABLE = False
    client = None

pytestmark = pytest.mark.skipif(not API_AVAILABLE, reason="FastAPI or TestClient dependencies unavailable")

NOW_MS = 1_800_000_000_000


def _telemetry(confidence=1.0):
    return {"node_id": "J1", "current_phase_id": "J1_PHASE_NS", "_ingested_at_ms": NOW_MS - 500,
            "approaches": [{"approach_id": "J1_N_IN", "queue_vehicles": 2.0, "confidence": confidence}]}


@pytest.fixture(autouse=True)
def clean_health():
    saved = dict(LIVE_STATE["health"])
    LIVE_STATE["health"].clear()
    yield
    LIVE_STATE["health"].clear()
    LIVE_STATE["health"].update(saved)


def _esp32(**fields):
    payload = {"node_id": "J1", "service": "esp32_actuator", "status": "HEALTHY", "clearance": "GREEN",
               "safe_stop": False, "_ingested_at_ms": NOW_MS - 1000}
    payload.update(fields)
    LIVE_STATE["health"]["J1"] = payload


@pytest.mark.parametrize("clearance", ["YELLOW", "ALL_RED"])
def test_normal_phase_change_is_not_a_fault(clearance):
    """Yellow 3 s + all-red 2 s happen on every switch; they are not a safe-stop (G2)."""
    _esp32(clearance=clearance)
    health = compute_node_device_health("J1", _telemetry(), NOW_MS)
    assert health["actuator"]["status"] == "ACTIVE"
    assert health["actuator"]["clearance"] == clearance
    assert health["overall_status"] != "ACTUATOR_FAULT"


def test_safe_stop_flag_is_a_fault():
    _esp32(safe_stop=True, status="SAFE_STOP", clearance="YELLOW")
    health = compute_node_device_health("J1", _telemetry(), NOW_MS)
    assert health["actuator"]["status"] == "SAFE_STOP"
    assert health["overall_status"] == "ACTUATOR_FAULT"


def test_offline_will_is_reported_at_once():
    """The ESP32 last-will message (status OFFLINE) must not read as a healthy actuator."""
    _esp32(status="OFFLINE")
    health = compute_node_device_health("J1", _telemetry(), NOW_MS)
    assert health["actuator"]["status"] == "HEARTBEAT_LOST"
    assert health["overall_status"] == "ACTUATOR_FAULT"


def test_fallback_mode_is_visible_but_not_a_fault():
    _esp32(status="FALLBACK_AUTONOMOUS")
    health = compute_node_device_health("J1", _telemetry(), NOW_MS)
    assert health["actuator"]["status"] == "FALLBACK"
    assert health["overall_status"] == "FALLBACK"


def _sumo_telemetry(confidence=1.0):
    """run_demo.py --hardware: telemetry still comes from SUMO (source_type simulation), but a REAL
    ESP32 is mirrored and answers over MQTT health -- its status must not be hidden by sim mode."""
    t = _telemetry(confidence)
    t["source_type"] = "simulation"
    return t


def test_hardware_mirrored_safe_stop_surfaces_through_simulation_telemetry():
    """Regression: compute_node_device_health() used to short-circuit the whole actuator block to
    ACTIVE whenever source_type == "simulation", hiding a real ESP32's SAFE_STOP/HEARTBEAT_LOST/
    FALLBACK during a run_demo.py --hardware run (telemetry is simulated, the board is real)."""
    _esp32(safe_stop=True, status="SAFE_STOP")
    health = compute_node_device_health("J1", _sumo_telemetry(), NOW_MS)
    assert health["actuator"]["status"] == "SAFE_STOP"
    assert health["overall_status"] == "ACTUATOR_FAULT"
    # Camera half still reads as simulated/active: there is no real camera to lose signal on.
    assert health["camera"]["status"] == "ACTIVE"


def test_hardware_mirrored_heartbeat_lost_surfaces_through_simulation_telemetry():
    _esp32(status="OFFLINE")
    health = compute_node_device_health("J1", _sumo_telemetry(), NOW_MS)
    assert health["actuator"]["status"] == "HEARTBEAT_LOST"
    assert health["overall_status"] == "ACTUATOR_FAULT"


def test_heartbeat_age_uses_receive_time_not_device_clock():
    """An ESP32 whose SNTP clock is hours off still counts as alive when its messages arrive (G3)."""
    _esp32(timestamp_ms=NOW_MS - 3 * 3600 * 1000, _ingested_at_ms=NOW_MS - 1000)
    health = compute_node_device_health("J1", _telemetry(), NOW_MS)
    assert health["actuator"]["status"] == "ACTIVE"
    assert health["actuator"]["last_heartbeat_ms_ago"] == 1000


def test_silent_esp32_is_lost():
    _esp32(_ingested_at_ms=NOW_MS - 7000)
    health = compute_node_device_health("J1", _telemetry(), NOW_MS)
    assert health["actuator"]["status"] == "HEARTBEAT_LOST"


def test_mqtt_health_ingest_stamps_receive_time():
    from services.api.main import ingest_health_message
    before = int(time.time() * 1000)
    ingest_health_message("edgeflow/v1/health/J1",
                          {"node_id": "J1", "service": "esp32_actuator", "status": "HEALTHY", "timestamp_ms": 5})
    stored = LIVE_STATE["health"]["J1"]
    assert stored["_ingested_at_ms"] >= before
    assert stored["timestamp_ms"] == 5      # the device's own value is kept as sent


def test_node_without_telemetry_reports_no_confidence():
    """A node that never reported must not show invented queues, speeds or a confident camera."""
    saved = LIVE_STATE["nodes"].pop("J2", None)
    try:
        topo = LIVE_STATE["active_topology_id"]
        LIVE_STATE["active_topology_id"] = "tabletop_j1_j2_v1"
        data = client.get("/api/v1/network/state/J2").json()
        for approach in data["telemetry"]["approaches"]:
            assert approach["confidence"] == 0.0
            assert approach["mean_speed_mps"] == 0.0
    finally:
        LIVE_STATE["active_topology_id"] = topo
        if saved is not None:
            LIVE_STATE["nodes"]["J2"] = saved


def test_node_state_carries_vision_health():
    LIVE_STATE["health"]["vision"] = {"service": "vision", "status": "HEALTHY", "active_nodes": ["J1", "J2"],
                                      "runtime": {"processed_fps": 9.5}}
    topo = LIVE_STATE["active_topology_id"]
    LIVE_STATE["active_topology_id"] = "tabletop_j1_j2_v1"
    try:
        data = client.get("/api/v1/network/state/J1").json()
    finally:
        LIVE_STATE["active_topology_id"] = topo
    assert data["vision_health"]["runtime"]["processed_fps"] == 9.5


def test_policy_can_be_read_back_for_graph_control():
    saved = LIVE_STATE["active_controller"]
    try:
        assert client.post("/api/v1/control/policy", json={"controller": "fixed_time"}).status_code == 200
        assert client.get("/api/v1/control/policy").json()["active_controller"] == "fixed_time"
    finally:
        LIVE_STATE["active_controller"] = saved


def test_policy_rejects_controllers_that_need_a_model_file():
    """RL controllers need a trained model on the graph-control host; accepting them would only change a label."""
    assert client.post("/api/v1/control/policy", json={"controller": "presslight_rl"}).status_code == 400


def test_health_reports_controller_seen_in_commands():
    from services.api.main import note_command_controller
    saved = dict(LIVE_STATE)
    try:
        note_command_controller({"controller": "edgeflow"})
        note_command_controller({"controller": "manual_override"})   # an operator override is not the policy
        assert client.get("/health").json()["applied_controller"] == "edgeflow"
    finally:
        LIVE_STATE.pop("applied_controller", None)
        if "applied_controller" in saved:
            LIVE_STATE["applied_controller"] = saved["applied_controller"]
