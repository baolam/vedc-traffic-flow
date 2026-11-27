"""Production services over isolated brokers; these are protocol, not traffic scores."""

import json
import shutil
import time
from pathlib import Path
import pytest
from src.benchmark.mqtt import harness

pytestmark = pytest.mark.skipif(shutil.which("mosquitto") is None, reason="Mosquitto required")


def wait_for(predicate, timeout=8):
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        if predicate():
            return
        time.sleep(0.05)
    raise AssertionError("Expected protocol event did not arrive")


def test_real_actuator_ack_and_injected_expiry(tmp_path):
    with harness(tmp_path) as bus:
        command = dict(
            command_id="bench-initial",
            node_id="J2",
            target_phase_id="J2_PHASE_NS",
            min_green_s=10,
            max_green_s=60,
            controller="benchmark",
        )
        bus.publish("command", "J2", command)

        def ack(status, identifier):
            return any(
                json.loads(e["payload"]).get("command_id") == identifier
                and json.loads(e["payload"]).get("status") == status
                for e in bus.events
                if e["topic"].endswith("/ack")
            )

        wait_for(lambda: ack("APPLIED", "bench-initial"))
        bus.delay = 1
        expired = dict(command, command_id="bench-expired", expires_at_ms=int(time.time() * 1000) + 200)
        bus.publish("command", "J2", expired)
        wait_for(lambda: ack("EXPIRED", "bench-expired"))
        bus.delay = 0
        time.sleep(10.1)
        switch = dict(command, command_id="bench-switch", target_phase_id="J2_PHASE_EW")
        bus.publish("command", "J2", switch)
        wait_for(lambda: ack("ACCEPTED", "bench-switch"))
        wait_for(lambda: ack("APPLIED", "bench-switch"))
        events = [
            json.loads(e["payload"])
            for e in bus.events
            if e["side"] == 1
            and e["topic"].endswith("/ack")
            and json.loads(e["payload"]).get("command_id") == "bench-switch"
        ]
        stamps = {e["status"]: e["timestamp_ms"] for e in events}
        assert 4500 <= stamps["APPLIED"] - stamps["ACCEPTED"] <= 6500


def test_real_graph_suppresses_blind_telemetry(tmp_path):
    fixture = json.loads(Path("tests/fixtures/telemetry_j1_normal.json").read_text())
    with harness(tmp_path) as bus:
        for _ in range(5):
            fixture["timestamp_ms"] = int(time.time() * 1000)
            bus.publish("telemetry", "J1", fixture)
            time.sleep(0.25)
        wait_for(lambda: any(e["topic"].endswith("/command") for e in bus.events))
        for app in fixture["approaches"]:
            app.update(confidence=0.0, queue_vehicles=0.0)
        for _ in range(4):
            fixture["timestamp_ms"] = int(time.time() * 1000)
            bus.publish("telemetry", "J1", fixture)
            time.sleep(0.25)
        start = time.time()
        for _ in range(6):
            fixture["timestamp_ms"] = int(time.time() * 1000)
            bus.publish("telemetry", "J1", fixture)
            time.sleep(0.25)
        assert not any(e["topic"].endswith("/command") and e["time"] >= start for e in bus.events)
