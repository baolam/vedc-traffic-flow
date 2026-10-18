"""flow_report.py: PASS/FAIL of a closed-loop run (vision -> graph-control -> ESP32) from a mosquitto_sub log."""
import json
import sys
from pathlib import Path

import pytest

DEMO_DIR = Path(__file__).resolve().parents[2] / "src" / "hardware" / "demo"
if str(DEMO_DIR) not in sys.path:
    sys.path.insert(0, str(DEMO_DIR))

pytest.importorskip("jsonschema")

import flow_report as fr  # noqa: E402

T0 = 1_760_000_000.0


class Run:
    """Builds `mosquitto_sub -v -F '%U %t %p'` lines for one node, like the real system emits them."""

    def __init__(self, node="J1"):
        self.node, self.lines, self.n = node, [], 0

    def add(self, t, kind, payload):
        topic = {"telemetry": f"edgeflow/v1/telemetry/{self.node}",
                 "command": f"edgeflow/v1/control/{self.node}/command",
                 "ack": f"edgeflow/v1/control/{self.node}/ack",
                 "health": f"edgeflow/v1/health/{self.node}"}[kind]
        self.lines.append(f"{T0 + t:.6f} {topic} {json.dumps(payload)}")

    def health(self, t, phase, clearance="GREEN", status="HEALTHY"):
        self.add(t, "health", {"node_id": self.node, "service": "esp32_actuator", "status": status,
                               "current_phase": f"{self.node}_PHASE_{phase}", "clearance": clearance,
                               "safe_stop": status == "SAFE_STOP"})

    def telemetry(self, t, phase, confidence=1.0, approaches=True):
        appr = [{"approach_id": f"{self.node}_{d}_IN", "queue_vehicles": 2.0, "flow_veh_per_s": 0.1,
                 "mean_speed_mps": 1.0, "occupancy_ratio": 0.2, "confidence": confidence}
                for d in "NSEW"] if approaches else []
        self.add(t, "telemetry", {"node_id": self.node, "source_type": "vision", "approaches": appr,
                                  "current_phase_id": f"{self.node}_PHASE_{phase}"})

    def command(self, t, phase, *acks):
        """A command and its ACKs given as (delay_s, status[, reason])."""
        self.n += 1
        cid = f"c{self.n}"
        self.add(t, "command", {"command_id": cid, "node_id": self.node, "controller": "edgeflow",
                                "target_phase_id": f"{self.node}_PHASE_{phase}",
                                "min_green_s": 5.0, "max_green_s": 45.0})
        for delay, status, *reason in acks:
            self.add(t + delay, "ack", {"command_id": cid, "node_id": self.node, "status": status,
                                        "target_phase_id": f"{self.node}_PHASE_{phase}",
                                        "reason": reason[0] if reason else ""})
        return cid

    def controlled(self, start, stop, phase="NS", **telemetry_kw):
        """1 Hz telemetry, each answered at once by a command that keeps the current phase."""
        for s in range(start, stop):
            self.telemetry(s, phase, **telemetry_kw)
            self.command(s + 0.01, phase, (0.05, "APPLIED"))


def healthy_run():
    """30 s of control: NS green, one switch to EW at t=10 (ACCEPTED, APPLIED 5 s later)."""
    r = Run()
    r.health(0.0, "NS")
    r.controlled(1, 10, "NS")
    r.telemetry(10, "NS")
    r.command(10.01, "EW", (0.05, "ACCEPTED"), (5.0, "APPLIED"))
    for s in range(11, 15):  # during the clearance the controller keeps asking for EW
        r.telemetry(s, "NS")
        r.command(s + 0.01, "EW", (0.05, "ACCEPTED"))
    r.health(15.01, "EW")
    r.controlled(16, 30, "EW")
    r.health(20.0, "EW")
    r.health(25.0, "EW")
    return r


def report(lines, nodes=("J1",)):
    return fr.analyze(fr.parse_log(lines), list(nodes))


def status_of(rep, name, node="J1"):
    return next(c.status for c in rep.checks if c.name == name and c.node == node)


def test_a_healthy_closed_loop_passes_every_check():
    rep = report(healthy_run().lines)
    assert rep.result == "PASS", [c for c in rep.checks if c.status == "FAIL"]
    j1 = rep.nodes["J1"]
    assert j1["telemetry"] == 28 and j1["commands"] == 28
    assert j1["green_switches"] == 2
    # NS green from 0 to 10 (then 5 s clearance), EW green from 15 to the end of the log
    assert j1["green_s"]["J1_PHASE_NS"] == pytest.approx(10, abs=0.2)
    assert j1["green_s"]["J1_PHASE_EW"] == pytest.approx(14, abs=0.5)


def test_a_node_without_telemetry_fails_instead_of_passing_silently():
    rep = report(healthy_run().lines, nodes=("J1", "J2"))
    assert status_of(rep, "telemetry", "J2") == "FAIL"
    assert rep.result == "FAIL"


def test_telemetry_slower_than_one_message_per_second_fails():
    r = Run()
    r.health(0.0, "NS")
    for s in range(0, 30, 2):
        r.telemetry(s, "NS")
        r.command(s + 0.01, "NS", (0.05, "APPLIED"))
    assert status_of(report(r.lines), "telemetry") == "FAIL"


def test_a_command_the_device_never_answers_fails():
    r = healthy_run()
    r.command(29.5, "EW")  # no ACK at all
    r.health(33.0, "EW")    # the log goes on, so the missing ACK is not just the end of the recording
    assert status_of(report(r.lines), "acks") == "FAIL"


def test_min_green_rejections_are_device_protection_but_unknown_phase_is_a_failure():
    r = healthy_run()
    r.command(16.5, "NS", (0.05, "REJECTED", "Min green time not met (1.5s < 5.0s)"))
    assert status_of(report(r.lines), "acks") == "PASS"
    r.command(17.5, "XX", (0.05, "REJECTED", "Unknown target_phase_id for this node"))
    assert status_of(report(r.lines), "acks") == "FAIL"


def test_expired_commands_fail_because_the_clocks_disagree():
    r = healthy_run()
    r.command(29.5, "EW", (0.05, "EXPIRED", "Command expired before processing"))
    assert status_of(report(r.lines), "acks") == "FAIL"


def test_a_switch_must_take_yellow_plus_all_red_within_tolerance():
    r = Run()
    r.health(0.0, "NS")
    r.controlled(1, 8, "NS")
    r.command(8.01, "EW", (0.05, "ACCEPTED"), (9.0, "APPLIED"))  # 9 s instead of 5 s
    r.health(17.0, "EW")
    r.controlled(18, 25, "EW")
    rep = report(r.lines)
    assert status_of(rep, "switch_timing") == "FAIL"


def test_falling_back_while_commands_flow_fails():
    r = healthy_run()
    r.health(22.0, "EW", status="FALLBACK_AUTONOMOUS")
    assert status_of(report(r.lines), "fallback") == "FAIL"


def test_falling_back_after_the_camera_stops_is_the_expected_safe_behaviour():
    r = healthy_run()
    r.health(35.0, "EW", status="FALLBACK_AUTONOMOUS")  # telemetry ended at t=29
    rep = report(r.lines)
    assert status_of(rep, "fallback") == "PASS"
    assert rep.nodes["J1"]["fallback_entries"] == [pytest.approx(35.0, abs=0.01)]


def test_commands_answering_blind_telemetry_fail():
    r = Run()
    r.health(0.0, "NS")
    r.controlled(1, 10, "NS")
    r.controlled(10, 20, "NS", confidence=0.0)  # camera lost, controller keeps commanding
    assert status_of(report(r.lines), "blind_commands") == "FAIL"


def test_holding_commands_on_blind_telemetry_passes():
    r = Run()
    r.health(0.0, "NS")
    r.controlled(1, 10, "NS")
    for s in range(10, 20):
        r.telemetry(s, "NS", approaches=False)  # no frame in the period: no approach at all
    r.health(15.0, "NS", status="FALLBACK_AUTONOMOUS")
    rep = report(r.lines)
    assert status_of(rep, "blind_commands") == "PASS"
    assert status_of(rep, "fallback") == "PASS"  # the camera was blind, so falling back is correct


def test_telemetry_must_report_the_phase_the_esp32_is_showing():
    r = Run()
    r.health(0.0, "EW")
    for s in range(1, 20):
        r.telemetry(s, "NS")  # vision ignores the ESP32 health (the old phases[0] bug)
        r.command(s + 0.01, "NS", (0.05, "ACCEPTED"))
    assert status_of(report(r.lines), "phase_agreement") == "FAIL"


def test_telemetry_right_after_a_phase_change_is_not_counted_against_vision():
    r = healthy_run()
    r.health(15.6, "EW")
    r.telemetry(15.8, "NS")  # built before the new health reached the Pi
    assert status_of(report(r.lines), "phase_agreement") == "PASS"


def test_safe_stop_and_offline_are_reported_as_warnings():
    r = healthy_run()
    r.health(26.0, "EW", status="SAFE_STOP")
    rep = report(r.lines)
    assert status_of(rep, "device_status") == "WARN"


def test_parse_log_skips_lines_that_are_not_timestamped_json():
    lines = healthy_run().lines + ["", "garbage", "123.4 edgeflow/v1/health/J1 not-json",
                                   "edgeflow/v1/health/J1 {\"status\": \"HEALTHY\"}"]
    msgs = fr.parse_log(lines)
    assert len(msgs) == len(healthy_run().lines)


def test_main_writes_json_and_exits_non_zero_on_failure(tmp_path, capsys):
    log = tmp_path / "run.log"
    log.write_text("\n".join(healthy_run().lines) + "\n")
    out = tmp_path / "report.json"
    assert fr.main([str(log), "--nodes", "J1", "--json", str(out)]) == 0
    data = json.loads(out.read_text())
    assert data["result"] == "PASS" and data["nodes"]["J1"]["commands"] == 28
    assert fr.main([str(log), "--nodes", "J1,J2"]) == 1
    assert "RESULT: FAIL" in capsys.readouterr().out
