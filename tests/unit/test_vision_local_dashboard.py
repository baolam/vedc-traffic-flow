"""
Unit tests for services/vision/local_dashboard/ -- the standalone device-local web dashboard.

Deliberately avoids importing services.vision.supervisor (and therefore cv2): server.py and
db.py are designed to be cv2-free, so they're tested here against a lightweight fake supervisor
stub exposing the same attributes the real VisionSupervisor provides.
"""

import json
import queue
import time

import pytest
from fastapi.testclient import TestClient

from services.vision.local_dashboard.db import VisionLocalDB, NullLocalDB
from services.vision.local_dashboard.server import create_app, FrameCache


class FakeDetector:
    conf_threshold = 0.4


class FakeEngine:
    width, height = 640, 480
    detector = FakeDetector()


class FakeStats:
    def snapshot(self):
        return {"processed_fps": 9.5, "frames_ok": 100, "frames_failed": 0,
                "consecutive_failures": 0, "latency_ms": {"total_ms": {"p50": 12, "p95": 20}}}


class FakeCfg:
    edgeflow_topology = "four_intersection_v1"
    local_dashboard_username = "admin"
    local_dashboard_password = "secret123"


class FakeSupervisor:
    def __init__(self, local_db):
        self.cfg = FakeCfg()
        self.identity = {"service": "vision", "confidence_threshold": 0.4}
        self.stats = FakeStats()
        self.node_ids = ["J1"]
        self.active_nodes = [{"node_id": "J1", "approaches": ["J1_N_IN", "J1_S_IN", "J1_E_IN", "J1_W_IN"]}]
        self.engine = FakeEngine()
        self.roi_config = None
        self.roi_config_path = "/tmp/does-not-matter.json"
        self.pending_commands = queue.Queue()
        self.local_db = local_db
        self.last_telemetry = {"J1": {"node_id": "J1", "current_phase_id": "J1_PHASE_NS", "approaches": []}}
        self.last_health = {"status": "HEALTHY", "hardware": {"cpu_temp_c": 45.0}}


@pytest.fixture
def temp_local_db(tmp_path):
    db = VisionLocalDB(db_path=str(tmp_path / "vision_test.db"), retention_days=14.0)
    yield db
    db.close()


@pytest.fixture
def client(temp_local_db):
    supervisor = FakeSupervisor(temp_local_db)
    app = create_app(supervisor, FrameCache())
    return TestClient(app), supervisor


class TestAuth:
    def test_status_requires_auth(self, client):
        c, _ = client
        res = c.get("/api/status")
        assert res.status_code == 401

    def test_status_with_correct_credentials(self, client):
        c, _ = client
        res = c.get("/api/status", auth=("admin", "secret123"))
        assert res.status_code == 200

    def test_status_with_wrong_password_rejected(self, client):
        c, _ = client
        res = c.get("/api/status", auth=("admin", "wrong"))
        assert res.status_code == 401

    def test_auth_disabled_when_password_empty(self, temp_local_db):
        supervisor = FakeSupervisor(temp_local_db)
        supervisor.cfg.local_dashboard_password = ""
        app = create_app(supervisor, FrameCache())
        c = TestClient(app)
        assert c.get("/api/status").status_code == 200


class TestStatus:
    def test_status_shape(self, client):
        c, supervisor = client
        res = c.get("/api/status", auth=("admin", "secret123"))
        body = res.json()
        assert body["identity"]["service"] == "vision"
        assert body["stats"]["processed_fps"] == 9.5
        assert body["node_ids"] == ["J1"]
        assert body["last_health"]["status"] == "HEALTHY"


class TestControls:
    def test_restart_enqueues_exactly_one_command(self, client):
        c, supervisor = client
        res = c.post("/api/control/restart", auth=("admin", "secret123"))
        assert res.status_code == 200
        assert supervisor.pending_commands.qsize() == 1
        assert supervisor.pending_commands.get_nowait() == {"type": "restart"}

    def test_settings_valid_value_enqueued(self, client):
        c, supervisor = client
        res = c.post("/api/control/settings", json={"confidence_threshold": 0.6}, auth=("admin", "secret123"))
        assert res.status_code == 200
        cmd = supervisor.pending_commands.get_nowait()
        assert cmd == {"type": "update_settings", "fields": {"confidence_threshold": 0.6}}

    def test_settings_out_of_range_rejected(self, client):
        c, supervisor = client
        res = c.post("/api/control/settings", json={"confidence_threshold": 1.5}, auth=("admin", "secret123"))
        assert res.status_code == 400
        assert supervisor.pending_commands.empty()

    def test_settings_unrecognized_field_rejected(self, client):
        c, supervisor = client
        res = c.post("/api/control/settings", json={"video_source": "picamera"}, auth=("admin", "secret123"))
        assert res.status_code == 400
        assert supervisor.pending_commands.empty()


class TestRoi:
    def test_get_roi_shape_with_no_current_config(self, client):
        c, _ = client
        res = c.get("/api/roi", auth=("admin", "secret123"))
        body = res.json()
        assert body["frame_size"] == [640, 480]
        assert body["approaches"]["J1"] == ["J1_N_IN", "J1_S_IN", "J1_E_IN", "J1_W_IN"]
        assert body["current"] is None

    def test_post_roi_invalid_rejected_and_not_enqueued(self, client, tmp_path):
        c, supervisor = client
        supervisor.roi_config_path = str(tmp_path / "roi.json")
        # Missing the J1_W_IN approach entirely -- validate_against_topology must reject this.
        payload = {
            "camera": "test",
            "frame_size": [640, 480],
            "nodes": {"J1": {
                "J1_N_IN": [[0, 0], [10, 0], [10, 10]],
                "J1_S_IN": [[0, 0], [10, 0], [10, 10]],
                "J1_E_IN": [[0, 0], [10, 0], [10, 10]],
            }},
        }
        res = c.post("/api/roi", json=payload, auth=("admin", "secret123"))
        assert res.status_code == 400
        assert not (tmp_path / "roi.json").exists()
        assert supervisor.pending_commands.empty()

    def test_post_roi_valid_saves_and_enqueues_reload(self, client, tmp_path):
        c, supervisor = client
        roi_path = str(tmp_path / "roi.json")
        supervisor.roi_config_path = roi_path
        payload = {
            "camera": "test",
            "frame_size": [640, 480],
            "nodes": {"J1": {
                "J1_N_IN": [[0, 0], [10, 0], [10, 10]],
                "J1_S_IN": [[0, 0], [10, 0], [10, 10]],
                "J1_E_IN": [[0, 0], [10, 0], [10, 10]],
                "J1_W_IN": [[0, 0], [10, 0], [10, 10]],
            }},
        }
        res = c.post("/api/roi", json=payload, auth=("admin", "secret123"))
        assert res.status_code == 200
        assert (tmp_path / "roi.json").is_file()
        cmd = supervisor.pending_commands.get_nowait()
        assert cmd == {"type": "reload_roi", "roi_config_path": roi_path}


class TestLocalDB:
    def test_telemetry_health_event_round_trip(self, temp_local_db):
        temp_local_db.record_telemetry({
            "node_id": "J1", "current_phase_id": "J1_PHASE_NS",
            "approaches": [{"approach_id": "J1_N_IN", "queue_vehicles": 3.0}],
            "timestamp_ms": 1700000000000,
        })
        temp_local_db.record_health({
            "status": "HEALTHY", "runtime": {"processed_fps": 10.0},
            "hardware": {"cpu_temp_c": 50.0}, "timestamp_ms": 1700000000000,
        })
        temp_local_db.record_event("restarted", {"reason": "test"})
        time.sleep(0.3)  # async write queue

        telemetry = temp_local_db.query_telemetry(node_id="J1")
        assert len(telemetry) == 1
        assert telemetry[0]["approaches"][0]["queue_vehicles"] == 3.0

        health = temp_local_db.query_health()
        assert len(health) == 1
        assert health[0]["hardware"]["cpu_temp_c"] == 50.0

        events = temp_local_db.query_events()
        assert len(events) == 1
        assert events[0]["event_type"] == "restarted"
        assert events[0]["detail"]["reason"] == "test"

    def test_prune_removes_old_rows(self, temp_local_db):
        now_ms = int(time.time() * 1000)
        old_ms = now_ms - 20 * 86400 * 1000
        temp_local_db.record_event("old_event")
        time.sleep(0.2)
        with temp_local_db._get_connection() as conn:
            conn.execute("UPDATE event_log SET timestamp_ms = ?;", (old_ms,))
            conn.commit()
        temp_local_db.prune(now_ms=now_ms)
        assert temp_local_db.query_events() == []

    def test_null_local_db_is_a_safe_no_op(self):
        db = NullLocalDB()
        db.record_telemetry({})
        db.record_health({})
        db.record_event("x")
        assert db.query_telemetry() == []
        assert db.query_health() == []
        assert db.query_events() == []
        db.close()
