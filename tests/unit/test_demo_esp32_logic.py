"""Virtual ESP32 state machine: every ACK path of esp32_signal_controller.ino, on a manual clock."""
import json
import sys
from pathlib import Path

import pytest

DEMO_DIR = Path(__file__).resolve().parents[2] / "src" / "hardware" / "demo"
if str(DEMO_DIR) not in sys.path:
    sys.path.insert(0, str(DEMO_DIR))

pytest.importorskip("jsonschema")

import mqtt_common as mc  # noqa: E402
from esp32_simulator import ALL_RED, GREEN, YELLOW, Esp32Logic  # noqa: E402
import laptop_command_test as lct  # noqa: E402

TIMING = mc.Timing()


class Rig:
    """Esp32Logic + recorded outputs + a clock the test advances by hand."""

    def __init__(self, clock_synced=True, epoch_ms=lambda: 1_700_000_000_000):
        self.acks, self.healths, self.now = [], 0, 0.0
        self.logic = Esp32Logic("J1", TIMING, 0.0, lambda *a: self.acks.append(a),
                                lambda: setattr(self, "healths", self.healths + 1),
                                clock_synced=clock_synced, epoch_ms=epoch_ms)
        self.advance(TIMING.all_red_s)  # boot: ALL_RED then GREEN NS

    def advance(self, seconds, step=0.125):  # 1/8 s is exact in binary: no float drift
        end = self.now + seconds
        while self.now < end - 1e-9:
            self.now = min(self.now + step, end)
            self.logic.tick(self.now)

    def send(self, phase, cmd_id="c1", **extra):
        doc = {"command_id": cmd_id, "node_id": "J1", "target_phase_id": f"J1_PHASE_{phase}",
               "min_green_s": 5, "max_green_s": 60, "controller": "t", **extra}
        self.logic.handle_command(json.dumps(doc).encode(), self.now)
        return self.acks[-1][2] if self.acks else None

    def statuses(self):
        return [a[2] for a in self.acks]


def test_boot_is_all_red_then_north_south_green_and_announces_it():
    rig = Rig()

    assert rig.logic.clear_state == GREEN and rig.logic.current_phase == "NS"
    assert rig.healths >= 1


def test_phase_change_goes_yellow_then_all_red_then_applied_only_after_green():
    rig = Rig()
    rig.advance(TIMING.min_green_s)

    assert rig.send("EW") == "ACCEPTED" and rig.logic.clear_state == YELLOW
    rig.advance(TIMING.yellow_s)
    assert rig.logic.clear_state == ALL_RED and rig.statuses() == ["ACCEPTED"]
    rig.advance(TIMING.all_red_s)
    assert rig.logic.clear_state == GREEN and rig.logic.current_phase == "EW"
    assert rig.statuses() == ["ACCEPTED", "APPLIED"]


def test_switch_before_min_green_is_rejected_with_the_elapsed_time():
    rig = Rig()
    rig.advance(1.0)

    assert rig.send("EW") == "REJECTED"
    assert "Min green time not met" in rig.acks[-1][3]
    assert rig.logic.clear_state == GREEN


def test_requested_min_green_can_lengthen_but_not_shorten_the_device_floor():
    rig = Rig()
    rig.advance(3.0)

    assert rig.send("EW", min_green_s=0) == "REJECTED"   # 0 s requested, 5 s device floor wins
    rig.advance(3.0)
    assert rig.send("EW", cmd_id="c2", min_green_s=20) == "REJECTED"   # 6 s < 20 s requested
    assert rig.send("EW", cmd_id="c3", min_green_s=5) == "ACCEPTED"


def test_same_phase_while_green_extends_and_while_clearing_is_only_accepted():
    rig = Rig()
    assert rig.send("NS") == "APPLIED"

    rig.advance(TIMING.min_green_s)
    rig.send("EW", cmd_id="go")
    assert rig.send("NS", cmd_id="leaving") == "ACCEPTED"    # still the current phase, clearing
    assert rig.send("EW", cmd_id="again") == "ACCEPTED"      # already pending
    assert rig.acks[-1][3] == "Phase transition is already pending and clearing."


def test_unknown_phase_invalid_json_and_other_node_commands():
    rig = Rig()

    assert rig.send("XX") == "REJECTED" and "Unknown target_phase_id" in rig.acks[-1][3]
    rig.logic.handle_command(b"{oops", rig.now)
    assert rig.acks[-1][:3] == ("unknown", "unknown", "REJECTED")
    before = len(rig.acks)
    other_node = {"node_id": "J2", "command_id": "x", "target_phase_id": "J2_PHASE_EW"}
    rig.logic.handle_command(json.dumps(other_node).encode(), rig.now)
    assert len(rig.acks) == before


def test_expired_command_is_rejected_only_when_the_clock_is_synced():
    synced = Rig(clock_synced=True)
    unsynced = Rig(clock_synced=False)
    expired = 1_700_000_000_000 - 5_000

    assert synced.send("NS", expires_at_ms=expired) == "EXPIRED"
    assert unsynced.send("NS", expires_at_ms=expired) == "APPLIED"   # firmware cannot judge without SNTP


def test_command_for_this_node_resets_the_watchdog_even_when_it_is_rejected():
    rig = Rig()
    for _ in range(4):
        rig.advance(4.0)
        rig.send("XX")   # keepalive-style command
    assert not rig.logic.fallback and rig.logic.status == "HEALTHY"


def test_silence_triggers_autonomous_fallback_cycle_without_acks_and_a_command_ends_it():
    rig = Rig()
    rig.advance(TIMING.watchdog_s + 0.5)
    assert rig.logic.fallback and rig.logic.status == "FALLBACK_AUTONOMOUS"

    rig.advance(TIMING.fallback_green_s + TIMING.clearance_s + 1)
    assert rig.logic.current_phase == "EW" and rig.acks == []
    rig.send("EW")
    assert not rig.logic.fallback


def test_device_enforces_max_green_even_if_the_controller_keeps_asking():
    rig = Rig()
    for _ in range(int(TIMING.max_green_s / 2) + 4):
        rig.advance(2.0)
        rig.send("NS", cmd_id="keep")
        if rig.logic.current_phase == "EW":
            break
    assert rig.logic.current_phase == "EW"


def test_safe_stop_rejects_commands_and_reports_status():
    rig = Rig()
    rig.logic.safe_stop = True

    assert rig.send("EW") == "REJECTED" and "Safe-stop" in rig.acks[-1][3]
    assert rig.logic.health(rig.now, 0.0)["status"] == "SAFE_STOP"


def test_health_has_the_fields_the_vision_phase_tracker_reads():
    health = Rig().logic.health(10.0, 0.0)

    assert health["service"] == "esp32_actuator" and health["current_phase"] == "J1_PHASE_NS"
    assert health["clearance"] == GREEN and health["timestamp_ms"] == 1_700_000_000_000


def test_timing_scaled_shrinks_every_field():
    fast = TIMING.scaled(0.1)

    assert fast.yellow_s == pytest.approx(0.3) and fast.watchdog_s == pytest.approx(0.5)
    assert fast.clearance_s == pytest.approx(0.5)


def test_build_command_matches_the_contract_and_expiry_is_in_milliseconds():
    cmd = lct.build_command("J1", "J1_PHASE_EW", expires_in_s=10)

    mc.validate(cmd, "control_command")
    assert cmd["expires_at_ms"] - mc.now_ms() == pytest.approx(10_000, abs=500)
    assert "expires_at_ms" not in lct.build_command("J1", "J1_PHASE_EW")


def test_resolve_phase_accepts_short_names_and_rejects_unknown_ones():
    assert lct.resolve_phase("four_intersection_v1", "J1", "ew") == "J1_PHASE_EW"
    assert lct.resolve_phase("four_intersection_v1", "J1", "J1_PHASE_NS") == "J1_PHASE_NS"
    with pytest.raises(ValueError):
        lct.resolve_phase("four_intersection_v1", "J1", "DIAG")
    with pytest.raises(ValueError):
        lct.resolve_phase("four_intersection_v1", "J9", "NS")
