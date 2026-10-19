"""Dashboard phase override through the API: honest status that follows the ESP32 answers."""
import json

import pytest

try:
    from fastapi.testclient import TestClient
    import services.api.main as api
    client = TestClient(api.app)
    API_AVAILABLE = True
except Exception:  # noqa: BLE001 - optional dependencies
    API_AVAILABLE = False
    client = None

pytestmark = pytest.mark.skipif(not API_AVAILABLE, reason="FastAPI or TestClient dependencies unavailable")

T0 = 1_800_000_000_000


class _FakeMqtt:
    def __init__(self, connected=True, rc=0):
        self.connected, self.rc, self.published = connected, rc, []

    def is_connected(self):
        return self.connected

    def publish(self, topic, payload):
        self.published.append((topic, json.loads(payload)))
        return type("Info", (), {"rc": self.rc})()


@pytest.fixture(autouse=True)
def tabletop(monkeypatch):
    monkeypatch.setitem(api.LIVE_STATE, "active_topology_id", "tabletop_j1_j2_v1")
    monkeypatch.setitem(api.LIVE_STATE, "manual_overrides", {})
    monkeypatch.setitem(api.LIVE_STATE, "control_acks", {})


def _post(**body):
    return client.post("/api/v1/control/override", json={"node_id": "J1", "target_phase_id": "J1_PHASE_EW", **body})


def test_override_is_published_with_the_device_floor_and_reported_as_sent(monkeypatch):
    mqtt = _FakeMqtt()
    monkeypatch.setattr(api, "MQTT_CLIENT", mqtt)
    res = _post()
    assert res.status_code == 200
    data = res.json()
    assert data["status"] == "SENT" and data["command_id"].startswith("cmd-override-J1-")
    topic, cmd = mqtt.published[0]
    assert topic.endswith("/control/J1/command")
    assert cmd["controller"] == "manual_override" and cmd["min_green_s"] == 5.0
    # No made-up ESP32 ACK: the ack list only holds what the device sent
    assert api.LIVE_STATE["control_acks"] == {}
    assert api.LIVE_STATE["manual_overrides"]["J1"]["status"] == "SENT"


@pytest.mark.parametrize("mqtt, body, code", [
    (None, {}, 503),                                          # broker down: nothing reached the ESP32
    (_FakeMqtt(connected=False), {}, 503),
    (_FakeMqtt(rc=4), {}, 503),                               # publish refused
    (_FakeMqtt(), {"target_phase_id": "J2_PHASE_EW"}, 400),   # phase of another node
    (_FakeMqtt(), {"node_id": "J9"}, 404),
])
def test_override_errors_are_reported(monkeypatch, mqtt, body, code):
    monkeypatch.setattr(api, "MQTT_CLIENT", mqtt)
    assert _post(**body).status_code == code
    assert api.LIVE_STATE["manual_overrides"] == {}


def _start(target="J1_PHASE_EW"):
    api.LIVE_STATE["manual_overrides"]["J1"] = {"command_id": "cmd-override-J1-1", "target_phase_id": target,
                                                "requested_ms": T0, "status": "SENT", "last_reason": None}
    return api.LIVE_STATE["manual_overrides"]["J1"]


def _ack(status, target="J1_PHASE_EW", reason="r"):
    return {"command_id": "x", "node_id": "J1", "target_phase_id": target, "status": status, "reason": reason}


def test_ack_sequence_rejected_then_clearing_then_applied():
    override = _start()
    api.track_override_ack("J1", _ack("REJECTED", reason="Min green time not met (0.1s < 5.0s)"), T0 + 100)
    assert override["status"] == "WAITING" and "Min green" in override["last_reason"]
    api.track_override_ack("J1", _ack("ACCEPTED", target="J1_PHASE_NS"), T0 + 900)   # controller's own command
    assert override["status"] == "WAITING"
    api.track_override_ack("J1", _ack("ACCEPTED"), T0 + 4000)
    assert override["status"] == "CLEARING"
    api.track_override_ack("J1", _ack("APPLIED"), T0 + 9000)
    assert override["status"] == "APPLIED" and override["applied_ms"] == T0 + 9000
    api.track_override_ack("J1", _ack("REJECTED"), T0 + 9500)                         # later noise
    assert override["status"] == "APPLIED"


def test_view_counts_the_hold_down_then_ends():
    override = _start()
    api.track_override_ack("J1", _ack("APPLIED"), T0 + 2000)
    view = api.override_view(override, T0 + 7000, hold_s=15.0)
    assert view["status"] == "APPLIED" and view["hold_remaining_s"] == 10.0
    assert api.override_view(override, T0 + 18000, hold_s=15.0)["status"] == "ENDED"
    assert api.override_view(override, T0 + 2000 + 15000 + api.OVERRIDE_SHOW_AFTER_END_S * 1000 + 1, hold_s=15.0) is None


def test_view_reports_an_override_the_esp32_never_applied():
    override = _start()
    api.track_override_ack("J1", _ack("REJECTED", reason="Safe-stop is engaged"), T0 + 100)
    assert api.override_view(override, T0 + 10_000)["status"] == "WAITING"
    late = api.override_view(override, T0 + int(api.OVERRIDE_MAX_WAIT_S * 1000))
    assert late["status"] == "NOT_APPLIED" and late["last_reason"] == "Safe-stop is engaged"


def test_node_state_exposes_the_override(monkeypatch):
    _start()
    data = client.get("/api/v1/network/state/J1").json()
    assert data["manual_override"]["target_phase_id"] == "J1_PHASE_EW"
    assert client.get("/api/v1/network/state/J2").json()["manual_override"] is None
