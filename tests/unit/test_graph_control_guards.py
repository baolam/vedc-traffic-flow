"""Graph-control runtime guards: blind telemetry gets no command (G1), and the controller follows the API policy."""
import importlib.util
import sys
from pathlib import Path

import pytest

_PATH = Path(__file__).parents[2] / "services" / "graph-control" / "runtime_guards.py"
_spec = importlib.util.spec_from_file_location("graph_control_runtime_guards", _PATH)
guards = importlib.util.module_from_spec(_spec)
sys.modules[_spec.name] = guards
_spec.loader.exec_module(guards)


def _telemetry(*confidences, node="J1"):
    return {"node_id": node, "source_type": "vision", "current_phase_id": f"{node}_PHASE_NS",
            "approaches": [{"approach_id": f"{node}_A{i}", "queue_vehicles": 1.0, "confidence": c}
                           for i, c in enumerate(confidences)]}


@pytest.mark.parametrize("payload, blind", [
    (_telemetry(0.0, 0.0, 0.0, 0.0), True),          # camera lost: vision reports zero confidence
    ({"node_id": "J1", "approaches": []}, True),     # broken video source: nothing observed at all
    (_telemetry(0.0, 0.0, 0.6, 0.0), False),         # partial view is still an observation
    ({"node_id": "J1", "approaches": [{"approach_id": "J1_N_IN", "queue_vehicles": 2.0}]}, False),  # simulator
])
def test_is_blind(payload, blind):
    assert guards.is_blind(payload) is blind


def test_blind_node_is_dropped_from_network_state_and_logged_once(caplog):
    gate = guards.BlindNodeGate()
    state = {"J1": _telemetry(1.0, 1.0, 1.0, 1.0), "J2": _telemetry(1.0, 1.0, 1.0, 1.0, node="J2")}
    with caplog.at_level("WARNING", logger="graph-control"):
        assert gate.admit("J1", _telemetry(0.0, 0.0, 0.0, 0.0), state) is False
        assert gate.admit("J1", _telemetry(0.0, 0.0, 0.0, 0.0), state) is False
    assert "J1" not in state and "J2" in state          # neighbours must not plan with J1's stale queues
    assert sum("J1" in r.message for r in caplog.records) == 1


def test_node_is_admitted_again_when_observations_return(caplog):
    gate = guards.BlindNodeGate()
    state = {}
    gate.admit("J1", _telemetry(0.0, 0.0, 0.0, 0.0), state)
    with caplog.at_level("INFO", logger="graph-control"):
        assert gate.admit("J1", _telemetry(0.9, 0.9, 0.9, 0.9), state) is True
    assert any("J1" in r.message for r in caplog.records)


class _Built:
    def __init__(self, name):
        self.name = name


def _follower(policy, start="edgeflow", fail=None):
    calls = []

    def build(name):
        calls.append(name)
        if name == fail:
            raise ValueError("no model file")
        return _Built(name)

    def fetch(url):
        if isinstance(policy, Exception):
            raise policy
        return policy

    return guards.PolicyFollower("http://api/policy", start, build, fetch=fetch), calls


def test_policy_switch_builds_the_new_controller():
    follower, calls = _follower({"active_controller": "fixed_time"})
    new = follower.poll_once()
    assert new.name == "fixed_time" and calls == ["fixed_time"]
    assert follower.current == "fixed_time"
    assert follower.poll_once() is None                  # same policy: nothing rebuilt
    assert calls == ["fixed_time"]


def test_policy_unchanged_keeps_controller():
    follower, calls = _follower({"active_controller": "edgeflow"})
    assert follower.poll_once() is None and calls == []


def test_policy_build_failure_keeps_the_running_controller():
    follower, calls = _follower({"active_controller": "presslight_rl"}, fail="presslight_rl")
    assert follower.poll_once() is None
    assert follower.current == "edgeflow"
    assert follower.poll_once() is None and calls == ["presslight_rl"]   # not retried every poll


def test_unreachable_api_keeps_controller():
    follower, calls = _follower(OSError("connection refused"))
    assert follower.poll_once() is None and follower.current == "edgeflow" and calls == []


def test_policy_names_are_normalised():
    follower, _ = _follower({"active_controller": "EdgeFlow"})
    assert follower.poll_once() is None                  # same controller, different case


class _Clock:
    def __init__(self):
        self.t = 1000.0

    def __call__(self):
        return self.t


def _override(node="J1", target="J1_PHASE_EW", command_id="cmd-override-J1-1"):
    return {"command_id": command_id, "node_id": node, "target_phase_id": target,
            "min_green_s": 5.0, "max_green_s": 60.0, "controller": "manual_override"}


def test_override_hold_resends_the_forced_phase_until_it_has_been_green_long_enough():
    clock = _Clock()
    hold = guards.ManualOverrideHold(15.0, clock=clock)
    assert hold.command_for("J1", "J1_PHASE_NS") is None          # no override: the controller decides
    assert hold.observe_command(_override()) is True

    # ESP32 still on NS (min green or clearance): keep asking for EW, with the device floor as min green
    cmd = hold.command_for("J1", "J1_PHASE_NS")
    assert cmd["target_phase_id"] == "J1_PHASE_EW" and cmd["controller"] == "manual_override"
    assert cmd["min_green_s"] == 5.0 and cmd["command_id"].startswith(guards.HOLD_ID_PREFIX)

    clock.t += 8                                                  # EW green from here on
    assert hold.command_for("J1", "J1_PHASE_EW")["target_phase_id"] == "J1_PHASE_EW"
    clock.t += 14.9
    assert hold.command_for("J1", "J1_PHASE_EW") is not None
    clock.t += 0.2
    assert hold.command_for("J1", "J1_PHASE_EW") is None           # held 15 s: controller resumes
    assert hold.command_for("J1", "J1_PHASE_EW") is None


def test_override_hold_ignores_its_own_resends_and_controller_commands():
    hold = guards.ManualOverrideHold(15.0, clock=_Clock())
    resend = _override(command_id=f"{guards.HOLD_ID_PREFIX}J1-5")
    controller_cmd = dict(_override(command_id="5f1c-uuid"), controller="edgeflow")
    assert hold.observe_command(resend) is False
    assert hold.observe_command(controller_cmd) is False
    assert hold.command_for("J1", "J1_PHASE_NS") is None


def test_override_hold_restarts_the_green_count_when_the_phase_leaves():
    clock = _Clock()
    hold = guards.ManualOverrideHold(15.0, clock=clock)
    hold.observe_command(_override(target="J1_PHASE_NS"))
    hold.command_for("J1", "J1_PHASE_NS")      # still reported as NS while it clears away from NS
    clock.t += 3
    hold.command_for("J1", "J1_PHASE_EW")      # EW took over: NS has not been held at all yet
    clock.t += 7
    assert hold.command_for("J1", "J1_PHASE_NS") is not None
    clock.t += 14
    assert hold.command_for("J1", "J1_PHASE_NS") is not None   # 14 s of real NS green, not 24


def test_override_hold_gives_up_when_the_phase_never_turns_green():
    clock = _Clock()
    hold = guards.ManualOverrideHold(15.0, clock=clock)
    hold.observe_command(_override())
    clock.t += guards.OVERRIDE_MAX_WAIT_S - 0.1
    assert hold.command_for("J1", "J1_PHASE_NS") is not None
    clock.t += 0.2
    assert hold.command_for("J1", "J1_PHASE_NS") is None


def test_override_hold_is_per_node_and_can_be_disabled():
    hold = guards.ManualOverrideHold(15.0, clock=_Clock())
    hold.observe_command(_override())
    assert hold.command_for("J2", "J2_PHASE_NS") is None
    assert guards.ManualOverrideHold(0.0).observe_command(_override()) is False
