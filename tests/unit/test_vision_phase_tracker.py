"""O7: telemetry reports the phase each ESP32 actually shows, read from its health topic."""
import importlib.util
import json
import re
import sys
from pathlib import Path

import pytest

ROOT_DIR = Path(__file__).resolve().parents[2]
VISION_DIR = ROOT_DIR / "services" / "vision"
CONTRACTS_DIR = ROOT_DIR / "contracts"
FIRMWARE = ROOT_DIR / "src" / "hardware" / "firmware" / "esp32_signal_controller.ino"
for path in (VISION_DIR, CONTRACTS_DIR):
    if str(path) not in sys.path:
        sys.path.insert(0, str(path))

import contracts_sdk  # noqa: E402
from phase_tracker import PHASE_STALE_S, PhaseTracker  # noqa: E402

TOPOLOGY = contracts_sdk.load_topology("four_intersection_v1")
NODES = {n["node_id"]: n for n in TOPOLOGY["nodes"]}


class FakeClock:
    def __init__(self, now=100.0):
        self.now = now

    def __call__(self):
        return self.now


def esp32_health(node_id, phase=None, status="HEALTHY"):
    """Same shape as publishHealth()/the LWT in the ESP32 firmware."""
    message = {"node_id": node_id, "service": "esp32_actuator", "status": status}
    if phase is not None:
        message.update({"current_phase": phase, "clearance": "GREEN", "safe_stop": False})
    return json.dumps(message).encode()


@pytest.fixture
def clock():
    return FakeClock()


@pytest.fixture
def tracker(clock):
    return PhaseTracker([NODES["J1"], NODES["J2"]], clock=clock)


def test_subscribes_to_the_health_topic_of_each_tracked_node(tracker):
    assert sorted(tracker.topics) == ["edgeflow/v1/health/J1", "edgeflow/v1/health/J2"]


def test_without_device_report_the_first_phase_is_flagged_default(tracker):
    assert tracker.current("J1") == ("J1_PHASE_NS", "default")


def test_reports_the_phase_the_device_announced(tracker):
    assert tracker.update("edgeflow/v1/health/J1", esp32_health("J1", "J1_PHASE_EW"))

    assert tracker.current("J1") == ("J1_PHASE_EW", "esp32_health")
    assert tracker.current("J2") == ("J2_PHASE_NS", "default")


@pytest.mark.parametrize("topic, payload", [
    ("edgeflow/v1/health/J1", esp32_health("J2", "J2_PHASE_EW")),      # payload of another node
    ("edgeflow/v1/health/J1", esp32_health("J1", "J2_PHASE_EW")),      # phase of another node
    ("edgeflow/v1/health/J1", esp32_health("J1", "J1_PHASE_DIAGONAL")),  # phase not in the topology
    ("edgeflow/v1/health/J1", esp32_health("J1")),                     # no current_phase field
    ("edgeflow/v1/health/J1", b"{not json"),
    ("edgeflow/v1/health/J1", b"\xff\xfe"),
    ("edgeflow/v1/health/J1", b"[]"),
    ("edgeflow/v1/health/vision", esp32_health("J1", "J1_PHASE_EW")),  # vision's own health topic
    ("edgeflow/v1/health/J3", esp32_health("J3", "J3_PHASE_EW")),      # node this camera does not see
])
def test_ignores_foreign_or_malformed_reports(tracker, topic, payload):
    assert not tracker.update(topic, payload)
    assert tracker.current("J1") == ("J1_PHASE_NS", "default")


def test_report_goes_stale_after_missed_health_periods(tracker, clock):
    tracker.update("edgeflow/v1/health/J1", esp32_health("J1", "J1_PHASE_EW"))

    clock.now += PHASE_STALE_S
    assert tracker.current("J1") == ("J1_PHASE_EW", "esp32_health")
    clock.now += 0.1
    assert tracker.current("J1") == ("J1_PHASE_NS", "default")


def test_device_offline_will_drops_the_phase(tracker):
    tracker.update("edgeflow/v1/health/J1", esp32_health("J1", "J1_PHASE_EW"))

    assert tracker.update("edgeflow/v1/health/J1", esp32_health("J1", status="OFFLINE"))
    assert tracker.current("J1") == ("J1_PHASE_NS", "default")


def test_safe_stop_still_reports_the_held_phase(tracker):
    tracker.update("edgeflow/v1/health/J1", esp32_health("J1", "J1_PHASE_EW", status="SAFE_STOP"))
    assert tracker.current("J1") == ("J1_PHASE_EW", "esp32_health")


# --- telemetry and health of the vision service -------------------------------------------------

def load_vision_main():
    """services/vision/main.py by path (other services also ship a main.py); it needs OpenCV."""
    pytest.importorskip("cv2")
    spec = importlib.util.spec_from_file_location("vision_main_phase", VISION_DIR / "main.py")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_telemetry_carries_the_reported_phase():
    vision_main = load_vision_main()

    reported = vision_main.build_telemetry(NODES["J1"], [], 1.0, 1727005820123, current_phase_id="J1_PHASE_EW")
    unknown = vision_main.build_telemetry(NODES["J1"], [], 1.0, 1727005820123)

    contracts_sdk.validate_payload(reported, "telemetry")
    assert reported["current_phase_id"] == "J1_PHASE_EW"
    assert unknown["current_phase_id"] == "J1_PHASE_NS"


def test_vision_health_says_where_each_phase_came_from():
    vision_main = load_vision_main()
    snapshot = {"frames_ok": 3, "consecutive_failures": 0}

    payload = vision_main.build_health({"service": "vision"}, snapshot, {}, 1234,
                                       phase_sources={"J1": "esp32_health", "J2": "default"})

    assert payload["phase_source"] == {"J1": "esp32_health", "J2": "default"}


# --- firmware side of the same contract ---------------------------------------------------------

def test_firmware_health_matches_what_the_tracker_reads():
    source = FIRMWARE.read_text(encoding="utf-8")

    assert 'hDoc["current_phase"] = String(NODE_ID) + (currentPhase == PHASE_NS ? "_PHASE_NS" : "_PHASE_EW");' in source
    assert '\\"status\\":\\"OFFLINE\\"' in source  # LWT
    # Every switch to GREEN (command, max green, fallback, safe-stop release, boot) announces the new phase
    green_entry = re.search(r"ALL_RED finished -> GREEN active.*?\n    }\n", source, re.S)
    assert green_entry and "publishHealth(now);" in green_entry.group(0)
