"""Graph-control fairness guard: no road starves, whatever the controller decides."""
import copy
import importlib.util
import sys
from pathlib import Path

import pytest

_ROOT = Path(__file__).parents[2]
_PATH = _ROOT / "services" / "graph-control" / "fairness_guard.py"
_spec = importlib.util.spec_from_file_location("graph_control_fairness_guard", _PATH)
fg = importlib.util.module_from_spec(_spec)
sys.modules[_spec.name] = fg
_spec.loader.exec_module(fg)
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))
from src.control.controllers import EdgeFlowController, MaxPressureController  # noqa: E402

NS, EW = "J1_PHASE_NS", "J1_PHASE_EW"
APPS = {NS: ["J1_N_IN", "J1_S_IN"], EW: ["J1_E_IN", "J1_W_IN"]}
TOPOLOGY = {"nodes": [{"node_id": "J1", "phases": [
    {"phase_id": NS, "approaches": APPS[NS]}, {"phase_id": EW, "approaches": APPS[EW]}]}]}


class Clock:
    def __init__(self) -> None:
        self.t = 0.0

    def __call__(self) -> float:
        return self.t


def _tel(phase, queues, confidence=None, state="GREEN", speeds=None):
    confidence, speeds = confidence or {}, speeds or {}
    return {"node_id": "J1", "source_type": "vision", "current_phase_id": phase, "signal_state": state,
            "approaches": [{"approach_id": a, "queue_vehicles": float(queues.get(a, 0)),
                            "flow_veh_per_s": 0.0, "mean_speed_mps": speeds.get(a, 0.0), "occupancy_ratio": 0.0,
                            "confidence": confidence.get(a, 0.9)} for ps in APPS.values() for a in ps]}


def _guard(**cfg):
    clock = Clock()
    return fg.FairnessGuard(TOPOLOGY, fg.FairnessConfig(**cfg), clock=clock), clock


def _queue_seen(tel, approach):
    return next(a["queue_vehicles"] for a in tel["approaches"] if a["approach_id"] == approach)


def test_lane_that_never_discharges_under_green_is_marked_stuck_then_released():
    guard, clock = _guard(stuck_after_s=15)
    for t in range(16):                                  # N holds 6 vehicles through 15 s of green
        clock.t = t
        out = guard.filter("J1", _tel(NS, {"J1_N_IN": 6, "J1_S_IN": 0}))
    assert guard.snapshot("J1")["stuck"] == ["J1_N_IN"]
    assert _queue_seen(out, "J1_N_IN") == 1.0            # capped to the assumed demand
    clock.t = 16
    out = guard.filter("J1", _tel(NS, {"J1_N_IN": 5}))   # it moves again
    assert guard.snapshot("J1")["stuck"] == []
    assert _queue_seen(out, "J1_N_IN") == 5.0


def test_queue_that_drops_now_and_then_is_not_stuck():
    guard, clock = _guard(stuck_after_s=15)
    for t in range(60):                                  # arrivals ~ discharge: level stays near 4
        clock.t = t
        guard.filter("J1", _tel(NS, {"J1_N_IN": 4 + (t % 3 == 0) - (t % 3 == 1)}))
    assert guard.snapshot("J1")["stuck"] == []


def test_oversaturated_lane_whose_vehicles_move_is_not_stuck():
    guard, clock = _guard(stuck_after_s=15)
    for t in range(60):                                  # arrivals > discharge: queue only grows
        clock.t = t
        guard.filter("J1", _tel(NS, {"J1_N_IN": 5 + t}, speeds={"J1_N_IN": 0.1}))
    assert guard.snapshot("J1")["stuck"] == []


def test_without_a_speed_field_nothing_is_marked_stuck():
    guard, clock = _guard(stuck_after_s=15)
    for t in range(60):
        clock.t = t
        tel = _tel(NS, {"J1_N_IN": 6})
        for a in tel["approaches"]:
            del a["mean_speed_mps"]
        guard.filter("J1", tel)
    assert guard.snapshot("J1")["stuck"] == []


def test_stuck_is_only_judged_while_its_phase_is_green():
    guard, clock = _guard(stuck_after_s=15)
    for t in range(40):                                  # EW waits at red: its queue cannot drop
        clock.t = t
        guard.filter("J1", _tel(NS, {"J1_E_IN": 7}))
    assert guard.snapshot("J1")["stuck"] == []


def test_unobserved_approach_is_assumed_to_have_demand():
    guard, _ = _guard()
    out = guard.filter("J1", _tel(NS, {"J1_E_IN": 0}, confidence={"J1_E_IN": 0.0}))
    assert guard.snapshot("J1")["unobserved"] == ["J1_E_IN"]
    assert _queue_seen(out, "J1_E_IN") == 1.0


def test_filter_does_not_mutate_its_input():
    guard, _ = _guard()
    tel = _tel(NS, {"J1_E_IN": 0}, confidence={"J1_E_IN": 0.0})
    before = copy.deepcopy(tel)
    guard.filter("J1", tel)
    assert tel == before


def test_phase_with_demand_is_forced_after_max_red():
    guard, clock = _guard(max_red_s=60)
    for t in range(61):
        clock.t = t
        tel = guard.filter("J1", _tel(NS, {"J1_N_IN": 9, "J1_E_IN": 1}))
        target = guard.decide("J1", tel, NS)             # controller keeps choosing the busy road
    assert target == EW


def test_phase_without_demand_is_not_forced():
    guard, clock = _guard(max_red_s=60)
    for t in range(120):
        clock.t = t
        tel = guard.filter("J1", _tel(NS, {"J1_N_IN": 9}))
        assert guard.decide("J1", tel, NS) == NS


def test_phase_that_waited_keeps_green_for_its_owed_service():
    guard, clock = _guard(owed_after_s=30, serve_min_s=10, serve_max_s=30, sat_flow_vps=0.5)
    for t in range(41):                                  # EW waits 40 s
        clock.t = t
        guard.decide("J1", guard.filter("J1", _tel(NS, {"J1_N_IN": 9, "J1_E_IN": 6})), NS)
    decisions = []
    for t in range(41, 41 + 14):                         # EW green, controller wants NS back at once
        clock.t = t
        tel = guard.filter("J1", _tel(EW, {"J1_N_IN": 12, "J1_E_IN": 6}))
        decisions.append(guard.decide("J1", tel, NS))
    assert decisions[:12] == [EW] * 12                   # 6 vehicles / 0.5 veh/s = 12 s owed
    assert decisions[-1] == NS


def test_owed_service_ends_early_when_the_queue_is_served():
    guard, clock = _guard(owed_after_s=30)
    for t in range(41):
        clock.t = t
        guard.decide("J1", guard.filter("J1", _tel(NS, {"J1_N_IN": 9, "J1_E_IN": 6})), NS)
    clock.t = 41
    guard.decide("J1", guard.filter("J1", _tel(EW, {"J1_E_IN": 6})), NS)
    clock.t = 45
    assert guard.decide("J1", guard.filter("J1", _tel(EW, {"J1_N_IN": 5})), NS) == NS


def test_unknown_node_and_non_green_pass_through():
    guard, _ = _guard()
    tel = {"node_id": "J9", "current_phase_id": "X", "approaches": []}
    assert guard.filter("J9", tel) is tel
    assert guard.decide("J9", tel, "X") == "X"
    guard.filter("J1", _tel(NS, {}))
    assert guard.decide("J1", _tel(NS, {}, state="YELLOW"), EW) == EW


# ---- closed loop: real controllers + the ESP32 timing rules (min 5, max 60, yellow 3, all-red 2) ----
def _run(controller, arrivals, stalled=(), guard=None, clock=None, horizon=1200):
    queues = {a: 0 for ps in APPS.values() for a in ps}
    acc = {a: 0.0 for a in queues}
    phase, state, t_state, green_since, pending = NS, "G", 0, 0, None
    topo = {"nodes": [{"node_id": "J1", "phases": [
        {"phase_id": p, "approaches": a, "movements": [
            {"from_approach": x, "to_node": None, "turn_ratio": 1.0, "capacity_vehicles": 100} for x in a]}
        for p, a in APPS.items()]}]}
    for t in range(horizon):
        for a, rate in arrivals.items():                 # deterministic arrivals
            acc[a] += rate
            while acc[a] >= 1:
                acc[a] -= 1
                queues[a] += 1
        if state == "G" and t % 2 == 0:                  # 0.5 veh/s per approach
            for a in APPS[phase]:
                if a not in stalled and queues[a]:
                    queues[a] -= 1
        if clock is not None:
            clock.t = float(t)
        moving = {a: 0.1 for a in APPS[phase] if state == "G" and a not in stalled and queues[a]}
        tel = _tel(phase, queues, state={"G": "GREEN", "Y": "YELLOW", "AR": "ALL_RED"}[state], speeds=moving)
        if guard is not None:
            tel = guard.filter("J1", tel)
        cmd = controller.compute_command("J1", tel, topo, {"J1": tel}, current_time_s=float(t))
        target = cmd["target_phase_id"]
        if guard is not None:
            target = guard.decide("J1", tel, target)
        if state == "G":
            if (target != phase and t - green_since >= 5) or t - green_since >= 60:
                pending, state, t_state = (EW if phase == NS else NS), "Y", t
        elif state == "Y" and t - t_state >= 3:
            state, t_state = "AR", t
        elif state == "AR" and t - t_state >= 2:
            phase, state, green_since = pending, "G", t
    return queues


@pytest.mark.parametrize("make", [EdgeFlowController, lambda: MaxPressureController(min_green_s=5)])
def test_blocked_lane_no_longer_starves_the_cross_road(make):
    arrivals = {a: 0.1 for a in ("J1_N_IN", "J1_S_IN", "J1_E_IN", "J1_W_IN")}
    without = _run(make(), arrivals, stalled=("J1_N_IN",))
    guard, clock = _guard()
    with_guard = _run(make(), arrivals, stalled=("J1_N_IN",), guard=guard, clock=clock)
    assert without["J1_E_IN"] + without["J1_W_IN"] > 50       # the bug: green wasted on a blocked lane
    assert with_guard["J1_E_IN"] + with_guard["J1_W_IN"] <= 6
    assert with_guard["J1_S_IN"] <= 6                          # the healthy NS lane is still served


@pytest.mark.parametrize("make", [EdgeFlowController, lambda: MaxPressureController(min_green_s=5)])
def test_light_cross_road_is_served_when_main_road_is_saturated(make):
    arrivals = {"J1_N_IN": 0.6, "J1_S_IN": 0.6, "J1_E_IN": 0.05, "J1_W_IN": 0.05}
    without = _run(make(), arrivals)
    guard, clock = _guard()
    with_guard = _run(make(), arrivals, guard=guard, clock=clock)
    assert with_guard["J1_E_IN"] + with_guard["J1_W_IN"] < without["J1_E_IN"] + without["J1_W_IN"]
    assert with_guard["J1_E_IN"] + with_guard["J1_W_IN"] <= 10


def test_stuck_detection_can_be_switched_off_for_the_open_loop_video_demo():
    guard, clock = _guard(stuck_after_s=0)
    for t in range(60):
        clock.t = t
        guard.filter("J1", _tel(NS, {"J1_N_IN": 6}))
    assert guard.snapshot("J1")["stuck"] == []


def test_unobserved_phase_gets_a_fixed_time_green_when_served():
    guard, clock = _guard(owed_after_s=30, unobserved_serve_s=20)
    blind = {"J1_E_IN": 0.0}
    for t in range(41):
        clock.t = t
        guard.decide("J1", guard.filter("J1", _tel(NS, {"J1_N_IN": 9}, confidence=blind)), NS)
    decisions = []
    for t in range(41, 41 + 22):
        clock.t = t
        tel = guard.filter("J1", _tel(EW, {"J1_N_IN": 12}, confidence=blind))
        decisions.append(guard.decide("J1", tel, NS))
    assert decisions[:20] == [EW] * 20 and decisions[-1] == NS


# ---- inside the 5-layer NoiseShieldPipeline (graph-control main.py runs both) -----------------------
_ns_spec = importlib.util.spec_from_file_location(
    "gc_noise_shield_fair", _ROOT / "services" / "graph-control" / "noise_shield.py")
ns = importlib.util.module_from_spec(_ns_spec)
sys.modules[_ns_spec.name] = ns
_ns_spec.loader.exec_module(ns)


class _CountingController:
    """Always keeps NS green; counts calls and refuses current_time_s like an older controller."""

    def __init__(self) -> None:
        self.calls = 0

    def compute_command(self, node_id, telemetry, topology, network_state):
        self.calls += 1
        return {"command_id": f"c{self.calls}", "node_id": node_id, "target_phase_id": NS,
                "min_green_s": 5, "max_green_s": 60}


def test_fair_controller_forces_starved_phase_through_the_noise_shield():
    guard, clock = _guard(max_red_s=60)
    inner = _CountingController()
    shield = ns.NoiseShieldPipeline(republish_interval_s=0.0, debounce_ticks=2, clock=clock)
    state = {}
    targets = []
    for t in range(0, 70, 2):
        clock.t = float(t)
        tel = dict(_tel(NS, {"J1_N_IN": 6, "J1_S_IN": 4, "J1_E_IN": 2}), timestamp_ms=t * 1000)
        cmd = shield.process_telemetry("J1", tel, TOPOLOGY, state, fg.FairController(guard, inner))
        targets.append(cmd["target_phase_id"] if cmd else None)
    assert inner.calls == len(targets)          # fallback without current_time_s happens once per message
    assert targets[:30] == [NS] * 30            # the controller alone never serves EW
    assert EW in targets[30:]                   # max red (60 s) forces it, after the shield's debounce


def test_fair_controller_shows_neighbours_the_masked_view():
    guard, _ = _guard()
    state = {}
    fg.FairController(guard, _CountingController()).compute_command(
        "J1", _tel(NS, {"J1_E_IN": 3}, confidence={"J1_E_IN": 0.0}), TOPOLOGY, state)
    assert _queue_seen(state["J1"], "J1_E_IN") == 1.0
