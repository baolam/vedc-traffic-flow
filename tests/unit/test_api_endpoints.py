import pytest

try:
    from fastapi.testclient import TestClient
    from services.api.main import app, LIVE_STATE
    client = TestClient(app)
    API_AVAILABLE = True
except Exception as e:
    API_AVAILABLE = False
    client = None

pytestmark = pytest.mark.skipif(not API_AVAILABLE, reason="FastAPI or TestClient dependencies unavailable in this python environment")


def test_api_root():
    response = client.get("/api")
    assert response.status_code == 200
    data = response.json()
    assert data["service"] == "edgeflow-api"
    assert data["status"] == "running"
    assert "endpoints" in data


def test_health_check():
    response = client.get("/health")
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "healthy"
    assert "timestamp_ms" in data
    assert "active_controller" in data


def test_get_dashboard_html():
    response = client.get("/dashboard")
    assert response.status_code == 200
    assert "text/html" in response.headers["content-type"]


def test_get_network_state():
    response = client.get("/api/v1/network/state")
    assert response.status_code == 200
    data = response.json()
    assert "topology_id" in data
    assert "controller" in data
    assert "nodes" in data
    assert len(data["nodes"]) > 0


def test_get_topologies_list():
    response = client.get("/api/v1/topologies")
    assert response.status_code == 200
    data = response.json()
    assert "topologies" in data
    assert len(data["topologies"]) > 0
    ids = [t["id"] for t in data["topologies"]]
    assert "four_intersection_v1" in ids


def test_get_specific_topology():
    response = client.get("/api/v1/topologies/four_intersection_v1")
    assert response.status_code == 200
    data = response.json()
    assert data["topology_id"] == "four_intersection_v1"
    assert "nodes" in data


def test_get_unknown_topology_returns_404():
    response = client.get("/api/v1/topologies/non_existent_topology_xyz")
    assert response.status_code == 404


def test_policy_change():
    payload = {"controller": "max_pressure", "topology_id": "four_intersection_v1"}
    response = client.post("/api/v1/control/policy", json=payload)
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "policy_updated"
    assert LIVE_STATE["active_controller"] == "max_pressure"

    # Reset back to edgeflow
    client.post("/api/v1/control/policy", json={"controller": "edgeflow"})


def test_policy_change_invalid_controller():
    payload = {"controller": "invalid_unknown_ai_controller"}
    response = client.post("/api/v1/control/policy", json=payload)
    assert response.status_code == 400


def test_get_scenarios():
    response = client.get("/api/v1/scenarios")
    assert response.status_code == 200
    data = response.json()
    assert "scenarios" in data
    assert len(data["scenarios"]) >= 3


def test_get_experiments():
    response = client.get("/api/v1/experiments")
    assert response.status_code == 200
    data = response.json()
    assert "total_runs" in data
    assert "runs" in data


def test_vision_demo_status_and_report():
    response = client.get("/api/v1/vision/status")
    assert response.status_code == 200
    data = response.json()
    assert "has_video" in data
    assert "has_report" in data
    assert "detector_backend" in data

    if data["has_report"]:
        res_rep = client.get("/api/v1/vision/demo-report")
        assert res_rep.status_code == 200
        rep = res_rep.json()
        assert rep["status"] == "SUCCESS"
        assert "metrics" in rep

    if data["has_video"]:
        res_vid = client.get("/api/v1/vision/demo-video")
        assert res_vid.status_code == 200
        assert "video/mp4" in res_vid.headers["content-type"]


def test_network_state_device_health_and_staleness():
    import time
    now_ms = int(time.time() * 1000)
    # 1. Fresh active telemetry
    client.post("/api/v1/telemetry", json={
        "node_id": "J1",
        "timestamp_ms": now_ms,
        "current_phase_id": "J1_PHASE_NS",
        "approaches": [
            {"approach_id": "J1_N_IN", "queue_vehicles": 3.0, "confidence": 0.95}
        ]
    })
    res = client.get("/api/v1/network/state/J1")
    assert res.status_code == 200
    data = res.json()
    assert data["telemetry"]["status"] == "ONLINE"
    assert data["device_health"]["camera"]["status"] == "ACTIVE"
    assert data["device_health"]["camera"]["confidence"] == 0.95

    # 2. Zero-confidence telemetry (simulating camera frame failure / disconnect)
    client.post("/api/v1/telemetry", json={
        "node_id": "J1",
        "timestamp_ms": now_ms,
        "approaches": [
            {"approach_id": "J1_N_IN", "queue_vehicles": 0.0, "confidence": 0.0}
        ]
    })
    res2 = client.get("/api/v1/network/state/J1")
    data2 = res2.json()
    assert data2["telemetry"]["status"] == "CAMERA_FAULT"
    assert data2["device_health"]["camera"]["status"] == "ZERO_CONFIDENCE"

    # 3. Ingest stale telemetry (>3.5s ago)
    LIVE_STATE["nodes"]["J1"]["_ingested_at_ms"] = now_ms - 5000
    LIVE_STATE["nodes"]["J1"]["timestamp_ms"] = now_ms - 5000
    res3 = client.get("/api/v1/network/state/J1")
    data3 = res3.json()
    assert data3["telemetry"]["status"] == "SIGNAL_LOST"
    assert data3["device_health"]["camera"]["status"] == "SIGNAL_LOST"

    # 4. Ingest heartbeat
    res_hb = client.post("/api/v1/health/heartbeat", json={
        "service_name": "J1",
        "status": "HEALTHY",
        "clearance": "GREEN"
    })
    assert res_hb.status_code == 200
    res4 = client.get("/api/v1/network/state/J1")
    data4 = res4.json()
    assert data4["device_health"]["actuator"]["status"] == "ACTIVE"


