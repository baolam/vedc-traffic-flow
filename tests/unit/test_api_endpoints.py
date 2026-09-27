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
