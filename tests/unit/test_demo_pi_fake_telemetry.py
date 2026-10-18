"""Fake Pi telemetry: scenarios stay schema-valid, follow the ESP32 phase, never mix into a real vision stream."""
import json
import random
import sys
from pathlib import Path

import pytest

DEMO_DIR = Path(__file__).resolve().parents[2] / "src" / "hardware" / "demo"
if str(DEMO_DIR) not in sys.path:
    sys.path.insert(0, str(DEMO_DIR))

pytest.importorskip("jsonschema")

import mqtt_common as mc  # noqa: E402
import pi_fake_telemetry as pft  # noqa: E402

NODE_J1 = mc.load_node("four_intersection_v1", "J1")


def queues(payload):
    """{'NS': total, 'EW': total} queue of a telemetry payload."""
    totals = {"NS": 0.0, "EW": 0.0}
    for a in payload["approaches"]:
        totals[pft.approach_axis(a["approach_id"])] += a["queue_vehicles"]
    return totals


@pytest.mark.parametrize("scenario", pft.SCENARIOS)
def test_every_scenario_produces_schema_valid_telemetry_for_all_approaches(scenario):
    payload = pft.build_fake_telemetry(NODE_J1, scenario, 37.0, 1_700_000_000_000, rng=random.Random(1))

    mc.validate(payload, "telemetry")
    assert payload["node_id"] == "J1" and payload["source_type"] == "vision"
    assert [a["approach_id"] for a in payload["approaches"]] == NODE_J1["approaches"]


def test_ns_heavy_loads_north_south_more_than_east_west():
    payload = pft.build_fake_telemetry(NODE_J1, "ns_heavy", 10.0, 0, rng=random.Random(2))

    totals = queues(payload)

    assert totals["NS"] > 3 * totals["EW"]


def test_alternate_flips_the_heavy_side_every_period():
    early = queues(pft.build_fake_telemetry(NODE_J1, "alternate", 5.0, 0, rng=random.Random(3)))
    later = queues(pft.build_fake_telemetry(NODE_J1, "alternate", pft.ALTERNATE_PERIOD_S + 5.0, 0,
                                            rng=random.Random(3)))

    assert early["NS"] > early["EW"] and later["EW"] > later["NS"]


def test_ramp_grows_ns_queue_then_restarts():
    at = lambda t: queues(pft.build_fake_telemetry(NODE_J1, "ramp", t, 0, rng=random.Random(4)))["NS"]  # noqa: E731

    assert at(10.0) < at(100.0)
    assert at(pft.RAMP_PERIOD_S + 5.0) < at(100.0)


def test_camera_lost_reports_zero_confidence_and_no_queue_instead_of_inventing_traffic():
    payload = pft.build_fake_telemetry(NODE_J1, "camera_lost", 20.0, 0, rng=random.Random(5))

    assert all(a["confidence"] == 0.0 and a["queue_vehicles"] == 0.0 for a in payload["approaches"])


def test_values_are_bounded_and_whole_vehicles():
    for t in range(0, 300, 7):
        for a in pft.build_fake_telemetry(NODE_J1, "ramp", float(t), 0, rng=random.Random(t))["approaches"]:
            assert a["queue_vehicles"] >= 0 and a["queue_vehicles"] == int(a["queue_vehicles"])
            assert 0.0 <= a["occupancy_ratio"] <= 1.0 and 0.0 <= a["confidence"] <= 1.0


def test_same_seed_repeats_the_same_run():
    a = pft.FakePi([NODE_J1], "balanced", seed=7).tick(1.0, 1.0, 5)
    b = pft.FakePi([NODE_J1], "balanced", seed=7).tick(1.0, 1.0, 5)

    assert a == b


def test_unknown_scenario_and_unknown_node_are_errors_not_substitutions():
    with pytest.raises(ValueError):
        pft.FakePi([NODE_J1], "gridlock")
    with pytest.raises(ValueError):
        mc.load_node("four_intersection_v1", "J9")
    with pytest.raises(ValueError):
        pft.approach_axis("J1_X")


def esp32_health(node, phase):
    return json.dumps({"node_id": node, "service": "esp32_actuator", "status": "HEALTHY",
                       "current_phase": phase}).encode()


def test_current_phase_follows_the_esp32_while_fresh_and_falls_back_to_default_when_stale():
    fake = pft.FakePi([NODE_J1], "balanced", seed=1)
    default = NODE_J1["phases"][0]["phase_id"]
    other = "J1_PHASE_EW" if default.endswith("NS") else "J1_PHASE_NS"

    assert fake.tick(0.0, 100.0, 1)[0][1]["current_phase_id"] == default

    fake.observe_health("edgeflow/v1/health/J1", esp32_health("J1", other), now_s=100.0)
    assert fake.tick(1.0, 101.0, 2)[0][1]["current_phase_id"] == other
    assert fake.tick(20.0, 100.0 + pft.PHASE_STALE_S + 1, 3)[0][1]["current_phase_id"] == default


def test_health_from_other_services_or_unknown_nodes_is_ignored():
    fake = pft.FakePi([NODE_J1], "balanced")
    not_esp32 = {"node_id": "J1", "service": "vision", "current_phase": "J1_PHASE_EW"}
    fake.observe_health("t", json.dumps(not_esp32).encode(), 1.0)
    fake.observe_health("t", esp32_health("J2", "J2_PHASE_EW"), 1.0)
    fake.observe_health("t", b"garbage", 1.0)

    assert fake.phases == {}


def test_tick_publishes_to_the_contract_topic_of_each_node():
    nodes = [mc.load_node("four_intersection_v1", n) for n in ("J1", "J2")]

    topics = [t for t, _ in pft.FakePi(nodes, "balanced").tick(0.0, 0.0, 1)]

    assert topics == ["edgeflow/v1/telemetry/J1", "edgeflow/v1/telemetry/J2"]


class FakeClient:
    """Minimal paho stand-in: a retained health message is delivered when its topic is subscribed."""

    def __init__(self, retained=None):
        self.retained, self.on_message = retained, None

    def subscribe(self, topic):
        if self.retained is not None and self.on_message:
            payload = json.dumps(self.retained).encode()
            self.on_message(self, None, type("M", (), {"topic": topic, "payload": payload})())

    def unsubscribe(self, topic):
        pass


def test_real_vision_service_is_detected_and_a_previous_fake_run_is_not():
    real = {"service": "vision", "status": "HEALTHY", "device": "raspberry_pi_5"}

    assert pft.real_vision_is_running(FakeClient(real), wait_s=0.01) == real
    assert pft.real_vision_is_running(FakeClient({**real, "mode": "FAKE_DATA"}), wait_s=0.01) is None
    assert pft.real_vision_is_running(FakeClient({"service": "vision", "status": "OFFLINE"}), wait_s=0.01) is None
    assert pft.real_vision_is_running(FakeClient(None), wait_s=0.01) is None


def test_dry_run_prints_valid_telemetry_without_a_broker(capsys):
    args = pft.parse_args(["--dry-run", "--duration", "0.05", "--period", "0.05", "--nodes", "J1,J2",
                           "--scenario", "ns_heavy", "--seed", "3"])

    assert pft.run(args) == 0

    lines = [json.loads(line) for line in capsys.readouterr().out.splitlines() if line.startswith("{")]
    assert {m["node_id"] for m in lines} == {"J1", "J2"}
    for message in lines:
        mc.validate(message, "telemetry")


def test_run_rejects_non_positive_period_and_unknown_node():
    assert pft.run(pft.parse_args(["--dry-run", "--period", "0"])) == 2
    with pytest.raises(ValueError):
        pft.run(pft.parse_args(["--dry-run", "--nodes", "J9", "--duration", "0.1"]))
