"""
Pi <-> laptop <-> ESP32 demo tools over a real Mosquitto broker (skipped when `mosquitto` is not installed).
The ESP32 is the virtual one (esp32_simulator.py, timings 10x shorter), so this proves the tools agree with
each other and with the contracts; the real boards still have to pass `laptop_command_test.py test`.
"""
import json
import shutil
import socket
import subprocess
import sys
import threading
import time
from pathlib import Path

import pytest

DEMO_DIR = Path(__file__).resolve().parents[2] / "src" / "hardware" / "demo"
if str(DEMO_DIR) not in sys.path:
    sys.path.insert(0, str(DEMO_DIR))

pytest.importorskip("paho.mqtt.client")
pytest.importorskip("jsonschema")
if shutil.which("mosquitto") is None:
    pytest.skip("mosquitto broker not installed", allow_module_level=True)

import esp32_simulator as sim  # noqa: E402
import laptop_command_test as lct  # noqa: E402
import mqtt_common as mc  # noqa: E402
import pi_fake_telemetry as pft  # noqa: E402

SPEED = 10.0
TIMING = mc.Timing().scaled(1.0 / SPEED)


@pytest.fixture()
def broker(tmp_path):
    with socket.socket() as s:
        s.bind(("127.0.0.1", 0))
        port = s.getsockname()[1]
    conf = tmp_path / "mosquitto.conf"
    conf.write_text(f"listener {port} 127.0.0.1\nallow_anonymous true\n")
    proc = subprocess.Popen(["mosquitto", "-c", str(conf)], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    for _ in range(50):
        try:
            socket.create_connection(("127.0.0.1", port), timeout=0.2).close()
            break
        except OSError:
            time.sleep(0.1)
    yield port
    proc.terminate()
    proc.wait(timeout=5)


class Virtual:
    """A virtual ESP32 running in a thread against the test broker."""

    def __init__(self, port, node="J1", speed=SPEED):
        self.stop = threading.Event()
        args = sim.parse_args(["--node", node, "--mqtt-port", str(port), "--mqtt-host", "127.0.0.1",
                               "--speed", str(speed)])
        self.thread = threading.Thread(target=sim.run, args=(args, self.stop), daemon=True)

    def __enter__(self):
        self.thread.start()
        time.sleep(0.5)
        return self

    def __exit__(self, *exc):
        self.stop.set()
        self.thread.join(timeout=5)


def connect(port):
    return lct.connect_bus("127.0.0.1", port)


def verdicts(results):
    return {r.name: r.verdict for r in results}


def test_full_suite_passes_against_the_virtual_esp32(broker):
    with Virtual(broker):
        bus = connect(broker)
        try:
            results = lct.NodeSuite(bus, "J1", "four_intersection_v1", TIMING).run()
        finally:
            bus.client.loop_stop()

    assert all(r.verdict == "PASS" for r in results), [(r.name, r.detail) for r in results if r.verdict != "PASS"]
    assert len(results) == 10


def test_suite_also_covers_the_watchdog_when_asked(broker):
    with Virtual(broker):
        bus = connect(broker)
        try:
            results = lct.NodeSuite(bus, "J1", "four_intersection_v1", TIMING).run(with_watchdog=True)
        finally:
            bus.client.loop_stop()

    assert verdicts(results)["watchdog_fallback"] == "PASS", [(r.name, r.detail) for r in results]


def test_suite_flags_a_device_whose_clearance_is_not_3s_yellow_plus_2s_all_red(broker):
    with Virtual(broker, speed=SPEED * 4):   # clearance 0.125 s where the suite expects 0.5 s
        bus = connect(broker)
        try:
            results = lct.NodeSuite(bus, "J1", "four_intersection_v1", TIMING).run()
        finally:
            bus.client.loop_stop()

    assert verdicts(results)["switch_phase"] == "FAIL"


def test_suite_reports_a_missing_board_instead_of_hanging(broker):
    bus = connect(broker)
    try:
        started = time.monotonic()
        results = lct.NodeSuite(bus, "J1", "four_intersection_v1", TIMING).run()
    finally:
        bus.client.loop_stop()

    assert [(r.name, r.verdict) for r in results] == [("online", "FAIL")]
    assert "no health" in results[0].detail and time.monotonic() - started < 6


def test_status_lists_online_devices_and_flags_missing_ones(broker, capsys):
    with Virtual(broker):
        bus = connect(broker)
        try:
            args = lct.parse_args(["--mqtt-port", str(broker), "status", "--expect", "J1,J2", "--wait", "0.8"])
            code = lct.cmd_status(args, bus)
        finally:
            bus.client.loop_stop()

    out = capsys.readouterr().out
    assert code == 1 and "J1" in out and "esp32_actuator" not in out
    assert "J2       MISSING" in out and "J1       MISSING" not in out


def test_send_command_prints_accepted_then_applied(broker, capsys):
    with Virtual(broker):
        bus = connect(broker)
        try:
            with lct.Keepalive(bus, "J1", TIMING.keepalive_s):   # a coordinator is alive: no fallback cycle
                time.sleep(TIMING.min_green_s + TIMING.clearance_s)   # past boot and min green
                args = lct.parse_args(["--mqtt-port", str(broker), "send", "J1", "EW", "--min-green", "0.5",
                                       "--wait", "3"])
                code = lct.cmd_send(args, bus)
        finally:
            bus.client.loop_stop()

    out = capsys.readouterr().out
    assert code == 0 and "ACCEPTED" in out and "APPLIED" in out


def collect_telemetry(port, seconds, node_phase):
    """Telemetry published on the broker for `seconds`; node_phase receives each payload."""
    received = []
    client = mc.make_client("test-collector")
    client.on_message = lambda c, u, m: received.append((m.topic, json.loads(m.payload)))
    mc.connect(client, "127.0.0.1", port)
    client.subscribe(mc.topics.TELEMETRY_SUB_PATTERN)
    return client, received


def test_fake_pi_publishes_valid_telemetry_and_goes_offline_on_exit(broker):
    client, received = collect_telemetry(broker, 1, None)
    args = pft.parse_args(["--mqtt-host", "127.0.0.1", "--mqtt-port", str(broker), "--nodes", "J1,J2",
                           "--period", "0.1", "--duration", "0.6", "--scenario", "ew_heavy"])

    assert pft.run(args) == 0
    time.sleep(0.2)
    client.loop_stop()

    assert {m["node_id"] for _, m in received} == {"J1", "J2"} and len(received) >= 6
    for _, message in received:
        mc.validate(message, "telemetry")
    last_health = {}
    probe = mc.make_client("test-health-probe")
    probe.on_message = lambda c, u, m: last_health.update(json.loads(m.payload))
    mc.connect(probe, "127.0.0.1", broker)
    probe.subscribe(mc.topics.get_health_topic("vision"))
    time.sleep(0.4)
    probe.loop_stop()
    assert last_health["status"] == "OFFLINE" and last_health["mode"] == "FAKE_DATA"


def test_fake_pi_refuses_to_run_next_to_a_real_vision_service_unless_forced(broker):
    real = mc.make_client("real-vision")
    mc.connect(real, "127.0.0.1", broker)
    real.publish(mc.topics.get_health_topic("vision"),
                 json.dumps({"service": "vision", "status": "HEALTHY", "device": "raspberry_pi_5"}), qos=1, retain=True)
    time.sleep(0.3)
    base = ["--mqtt-host", "127.0.0.1", "--mqtt-port", str(broker), "--nodes", "J1", "--period", "0.1",
            "--duration", "0.3"]

    assert pft.run(pft.parse_args(base)) == 3
    assert pft.run(pft.parse_args(base + ["--force"])) == 0
    real.loop_stop()


def test_fake_pi_telemetry_follows_the_phase_the_esp32_switches_to(broker):
    client, received = collect_telemetry(broker, 0, None)
    pi_args = pft.parse_args(["--mqtt-host", "127.0.0.1", "--mqtt-port", str(broker), "--nodes", "J1",
                              "--period", "0.1", "--duration", "4"])
    pi = threading.Thread(target=pft.run, args=(pi_args,), daemon=True)
    with Virtual(broker):
        pi.start()
        bus = connect(broker)
        try:
            with lct.Keepalive(bus, "J1", TIMING.keepalive_s):
                time.sleep(TIMING.min_green_s + TIMING.clearance_s + 0.3)
                args = lct.parse_args(["--mqtt-port", str(broker), "send", "J1", "EW", "--min-green", "0.5",
                                       "--wait", "3"])
                assert lct.cmd_send(args, bus) == 0
                time.sleep(0.5)
        finally:
            bus.client.loop_stop()
        pi.join(timeout=6)
    client.loop_stop()

    phases = [m["current_phase_id"] for _, m in received]
    # NS first (default, no health yet), EW once the ESP32 reports it (later it falls back again: no coordinator)
    assert phases[0] == "J1_PHASE_NS" and "J1_PHASE_EW" in phases, "".join(p[-2:-1] for p in phases)
