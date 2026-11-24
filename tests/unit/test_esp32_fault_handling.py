"""Fault scenarios of the virtual ESP32 (esp32_simulator.Esp32Logic), which mirrors esp32_signal_controller.ino.

Scenario numbers (K1..K12) refer to the fault table in NANG_CAP_FIRMWARE_KICH_BAN_LOI.md.
"""
import json
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]
DEMO_DIR = ROOT / "src" / "hardware"
for d in (DEMO_DIR / "demo", DEMO_DIR):
    if str(d) not in sys.path:
        sys.path.insert(0, str(d))

pytest.importorskip("jsonschema")

import mqtt_common as mc  # noqa: E402
import verify_trace as vt  # noqa: E402
from esp32_simulator import (ALL_RED, FLASH, GREEN, YELLOW, Esp32Logic,  # noqa: E402
                             parse_injection, schedule)

T = mc.Timing()
EPOCH = 1_700_000_000_000


class Rig:
    """Esp32Logic on a manual clock that records ACKs, health count, faults and a TRACE of head changes."""

    def __init__(self, link_up=True, reset_reason="POWERON", clock_synced=True, boot=True):
        self.now = 0.0
        self.acks, self.faults, self.healths, self.trace = [], [], 0, []
        self.logic = Esp32Logic("J1", T, 0.0, lambda *a: self.acks.append(a), self._health,
                                clock_synced=clock_synced, epoch_ms=lambda: EPOCH + int(self.now * 1000),
                                emit_fault=self.faults.append, reset_reason=reset_reason, link_up=link_up)
        self._record()
        if boot:
            self.advance(T.boot_s + 0.1)

    def _health(self):
        self.healths += 1

    def _record(self):
        ns, ew = self.logic.heads(self.now)
        label = {FLASH: "FLASH", GREEN: "GREEN", ALL_RED: "ALL_RED"}.get(self.logic.clear_state, "YELLOW")
        if self.logic.clear_state == YELLOW and self.logic.yellow_both:
            label = "FLASH_EXIT_YELLOW"
        if not self.trace or self.trace[-1][1:] != (ns, ew, label):
            self.trace.append((int(round(self.now * 1000)), ns, ew, label))

    def advance(self, seconds, step=0.05):
        end = self.now + seconds
        while self.now < end - 1e-9:
            self.now = min(self.now + step, end)
            self.logic.tick(self.now)
            self._record()

    def send(self, phase, cmd_id="c1", **extra):
        doc = {"command_id": cmd_id, "node_id": "J1", "target_phase_id": f"J1_PHASE_{phase}",
               "min_green_s": 5, "max_green_s": 60, "controller": "t", **extra}
        self.logic.handle_command(json.dumps(doc).encode(), self.now)
        self._record()
        return self.acks[-1][2] if self.acks else None

    def keepalive(self, seconds, every=1.0):
        """Coordinator alive: same-phase commands, as graph-control does every telemetry period."""
        for _ in range(int(seconds / every)):
            self.advance(every)
            self.send(self.logic.current_phase, cmd_id="keep")

    def codes(self):
        return [f["fault_code"] for f in self.faults]

    def trace_report(self):
        events = [vt.TraceEvent(t, "J1", ns, ew, label) for t, ns, ew, label in self.trace]
        return vt.check_node(events)


def test_every_fault_event_matches_the_contract():
    rig = Rig(reset_reason="BROWNOUT")
    rig.logic.set_safe_stop(True, rig.now)
    rig.advance(1)
    rig.logic.set_safe_stop(False, rig.now)
    rig.advance(T.boot_s)

    assert rig.faults
    for fault in rig.faults:
        mc.validate(fault, "signal_fault_event")
    assert len({f["event_id"] for f in rig.faults}) == len(rig.faults)


def test_boot_flashes_yellow_then_steady_yellow_both_heads_then_all_red_then_green():  # K7
    rig = Rig()
    labels = [label for _, _, _, label in rig.trace]

    assert labels[0] == "FLASH" and "FLASH_EXIT_YELLOW" in labels
    first_green = labels.index("GREEN")
    assert labels[first_green - 2:first_green] == ["FLASH_EXIT_YELLOW", "ALL_RED"]
    assert rig.trace_report().violations == []
    assert rig.logic.clear_state == GREEN and rig.logic.current_phase == "NS"


def test_commands_during_startup_flash_are_rejected_but_keep_the_watchdog_alive():
    rig = Rig(boot=False)
    rig.advance(1.0)

    assert rig.send("EW") == "REJECTED" and rig.acks[-1][3] == "Signal is in flashing mode (startup)"
    assert rig.logic.health(rig.now, 0.0)["status"] == "STARTING"


def test_abnormal_reset_is_reported_as_hardware_defect_once_the_link_is_up():  # K7, K12
    rig = Rig(link_up=False, reset_reason="BROWNOUT")
    assert rig.faults == [] and len(rig.logic.fault_queue) >= 1

    rig.logic.set_link(True, rig.now)
    boot = [f for f in rig.faults if f["fault_code"] == "ERR_HARDWARE_DEFECT"]
    assert boot and boot[0]["details"]["reset_reason"] == "BROWNOUT"
    assert boot[0]["details"]["queued_ms"] > 0
    assert boot[0]["timestamp_ms"] == pytest.approx(EPOCH, abs=2)  # time of the reset, not of the send
    assert "ERR_BROKER_DISCONNECT" not in rig.codes()  # first connection is not an outage


def test_normal_power_on_reports_no_fault():
    rig = Rig(reset_reason="POWERON")
    assert "ERR_HARDWARE_DEFECT" not in rig.codes()
    assert rig.logic.health(rig.now, 0.0)["reset_reason"] == "POWERON"


def test_link_loss_queues_faults_and_reports_the_outage_on_reconnect():  # K1, K2
    rig = Rig()
    rig.keepalive(3)
    sent_before = len(rig.faults)

    rig.logic.set_link(False, rig.now, wifi_lost=True)
    rig.advance(T.watchdog_s + 1)          # no commands reach the board
    assert rig.logic.fallback and len(rig.faults) == sent_before
    acks_before = len(rig.acks)
    rig.advance(T.fallback_green_s)
    assert len(rig.acks) == acks_before    # nothing leaves while the link is down

    rig.logic.set_link(True, rig.now)
    new = rig.faults[sent_before:]
    assert [f["fault_code"] for f in new] == ["ERR_COORDINATOR_TIMEOUT", "ERR_BROKER_DISCONNECT"]
    outage = new[1]["details"]
    assert outage["wifi_lost"] is True and outage["down_ms"] == pytest.approx((T.watchdog_s + 1 + T.fallback_green_s) * 1000, abs=60)
    assert new[0]["details"]["queued_ms"] > 0


def test_fault_queue_keeps_the_newest_eight_and_counts_the_dropped():
    rig = Rig()
    rig.logic.set_link(False, rig.now)
    for i in range(11):
        rig.send("XX", cmd_id=f"bad{i}")   # each raises ERR_FEEDBACK_MISMATCH
    rig.logic.set_link(True, rig.now)

    mismatches = [f for f in rig.faults if f["fault_code"] == "ERR_FEEDBACK_MISMATCH"]
    assert len(mismatches) == 7            # 8 slots: 7 mismatches + the outage event raised on reconnect
    assert mismatches[0]["details"]["dropped_before"] == 4


def test_coordinator_loss_with_link_up_reports_at_once():  # K3, K4
    rig = Rig()
    rig.keepalive(3)
    before = len(rig.faults)
    rig.advance(T.watchdog_s + 0.5)

    assert rig.codes()[before:] == ["ERR_COORDINATOR_TIMEOUT"]
    assert rig.logic.status == "FALLBACK_AUTONOMOUS"


def test_min_green_violation_is_reported_once_per_green_interval():  # K5d
    rig = Rig()
    rig.keepalive(1)
    for i in range(10):
        assert rig.send("EW", cmd_id=f"early{i}") == "REJECTED"
    assert rig.codes().count("ERR_MIN_GREEN_VIOLATION") == 1

    rig.keepalive(T.min_green_s + 1)
    assert rig.send("EW", cmd_id="go") == "ACCEPTED"
    rig.advance(T.clearance_s + 0.1)
    rig.send("NS", cmd_id="early-again")
    assert rig.codes().count("ERR_MIN_GREEN_VIOLATION") == 2


def test_dashboard_override_applied_is_reported_but_controller_commands_are_not():
    rig = Rig()
    rig.keepalive(T.min_green_s + 1)
    rig.send("EW", cmd_id="cmd-override-123")
    rig.advance(T.clearance_s + 0.1)
    rig.send("EW", cmd_id="gc-hold-1")      # graph-control re-send of the override: not reported again
    rig.send("EW", cmd_id="gc-normal")

    overrides = [f for f in rig.faults if f["fault_code"] == "ERR_EMERGENCY_OVERRIDE"]
    assert len(overrides) == 1 and overrides[0]["target_phase"] == "J1_PHASE_EW"


def test_safe_stop_mid_transition_fails_the_pending_command_and_release_goes_through_yellow():  # K6
    rig = Rig()
    rig.keepalive(T.min_green_s + 1)
    assert rig.send("EW", cmd_id="sw") == "ACCEPTED"
    rig.advance(1.0)
    rig.logic.set_safe_stop(True, rig.now)

    assert rig.acks[-1][:3] == ("sw", "J1_PHASE_EW", "FAILED")
    assert rig.send("EW", cmd_id="during") == "REJECTED" and "Safe-stop" in rig.acks[-1][3]
    rig.advance(3.0)
    rig.logic.set_safe_stop(False, rig.now)
    assert rig.logic.clear_state == YELLOW and rig.logic.heads(rig.now) == ("Y", "Y")
    rig.keepalive(T.clearance_s + 1)
    assert rig.logic.clear_state == GREEN and rig.logic.current_phase == "NS"   # last served phase
    assert rig.codes().count("ERR_SAFE_STOP_ENGAGED") == 1 and "ERR_SAFE_STOP_RELEASED" in rig.codes()
    assert rig.trace_report().violations == []


def test_conflict_guard_flashes_for_the_hold_time_then_recovers():  # K11
    rig = Rig()
    rig.keepalive(2)
    rig.logic.force_heads("G", "G", rig.now)

    assert "ERR_CONFLICT_GUARD_TRIGGERED" in rig.codes()
    assert rig.logic.clear_state == FLASH and rig.logic.status == "DEGRADED"
    rig.keepalive(T.fault_flash_hold_s + T.clearance_s + 1)
    assert rig.logic.clear_state == GREEN


def test_output_readback_fault_flashes_and_is_reported_at_most_once_a_minute():  # K8
    rig = Rig()
    rig.logic.output_fault = True
    rig.keepalive(30)

    assert rig.logic.clear_state == FLASH or rig.logic.clear_state in (YELLOW, ALL_RED)
    defects = [f for f in rig.faults if f["fault_code"] == "ERR_HARDWARE_DEFECT"]
    assert len(defects) == 1 and defects[0]["details"]["kind"] == "output_readback"

    rig.logic.output_fault = False
    rig.keepalive(T.fault_flash_hold_s + T.clearance_s + 1)
    assert rig.logic.clear_state == GREEN


def test_repeated_expired_commands_distrust_the_clock_and_stop_checking_expiry():  # K9
    rig = Rig()
    stale = EPOCH - 60_000
    statuses = [rig.send("NS", cmd_id=f"old{i}", expires_at_ms=stale) for i in range(4)]

    assert statuses == ["EXPIRED", "EXPIRED", "EXPIRED", "APPLIED"]
    clock = [f for f in rig.faults if f["details"].get("kind") == "clock"]
    assert len(clock) == 1 and "timestamp_ms" not in clock[0]   # clock no longer trusted for stamps
    assert rig.logic.health(rig.now, 0.0)["clock_synced"] is False


def test_unsynced_clock_never_changes_signal_timing():  # K9
    synced, unsynced = Rig(clock_synced=True), Rig(clock_synced=False)
    for rig in (synced, unsynced):
        rig.keepalive(T.min_green_s + 1)
        rig.send("EW", cmd_id="go")
        rig.advance(T.clearance_s + 0.1)
    assert synced.trace[-1][1:] == unsynced.trace[-1][1:]
    assert all("timestamp_ms" not in f for f in unsynced.faults)


@pytest.mark.parametrize("spec,expected", [
    ("wifi_drop@20+15", ("wifi_drop", 20.0, 15.0, "")),
    ("reboot@30=brownout", ("reboot", 30.0, 0.0, "BROWNOUT")),
    ("reboot@30", ("reboot", 30.0, 0.0, "PANIC")),
    ("kill@5.5+10", ("kill", 5.5, 10.0, "")),
])
def test_parse_injection(spec, expected):
    inj = parse_injection(spec)
    assert (inj.kind, inj.at_s, inj.duration_s, inj.arg) == expected


@pytest.mark.parametrize("spec", ["wifi_drop@20", "meteor@3+1", "safe_stop@x+1"])
def test_parse_injection_rejects_bad_specs(spec):
    with pytest.raises(ValueError):
        parse_injection(spec)


def test_schedule_orders_start_and_end_and_reboot_lasts_one_second():
    events = schedule([parse_injection("safe_stop@10+5"), parse_injection("reboot@12=PANIC")])
    assert [(t, w, i.kind) for t, w, i in events] == [
        (10.0, "start", "safe_stop"), (12.0, "start", "reboot"), (13.0, "end", "reboot"), (15.0, "end", "safe_stop")]


def test_emergency_flash_command_activates_and_resumes():
    rig = Rig()
    rig.keepalive(2)
    # Send emergency flash command
    ack = rig.send("FLASH", cmd_id="cmd-override-J1-flash", controller="emergency_flash")
    assert ack == "APPLIED"
    assert rig.logic.clear_state == FLASH
    assert rig.logic.flash_reason == "emergency"
    assert rig.logic.status == "EMERGENCY_FLASH"
    assert "ERR_EMERGENCY_OVERRIDE" in rig.codes()

    # Repeated flash command acknowledges already applied
    ack_dup = rig.send("FLASH", cmd_id="cmd-override-J1-flash-2", controller="emergency_flash")
    assert ack_dup == "APPLIED"

    # Advance in flash mode
    rig.advance(3.0)
    assert rig.logic.clear_state == FLASH

    # Operator resumes by commanding a green phase (e.g. NS)
    ack_resume = rig.send("NS", cmd_id="cmd-override-J1-resume")
    assert ack_resume == "ACCEPTED"
    assert rig.logic.clear_state == YELLOW
    assert rig.logic.yellow_both is True

    # Check safe clearance: YELLOW (3s) -> ALL_RED (2s) -> GREEN
    rig.advance(T.clearance_s + 0.1)
    assert rig.logic.clear_state == GREEN
    assert rig.logic.current_phase == "NS"
    assert rig.trace_report().violations == []


def test_verify_trace_flags_flashing_straight_to_red():
    bad = [vt.TraceEvent(0, "J1", "Y", "Y", "FLASH"), vt.TraceEvent(500, "J1", "R", "R", "ALL_RED"),
           vt.TraceEvent(2500, "J1", "G", "R", "GREEN")]
    short = [vt.TraceEvent(0, "J1", "Y", "Y", "FLASH"), vt.TraceEvent(500, "J1", "Y", "Y", "FLASH_EXIT_YELLOW"),
             vt.TraceEvent(1500, "J1", "R", "R", "ALL_RED"), vt.TraceEvent(3500, "J1", "G", "R", "GREEN")]

    assert any("without a steady yellow" in v for v in vt.check_node(bad).violations)
    assert any("flash-exit yellow 1000ms" in v for v in vt.check_node(short).violations)
