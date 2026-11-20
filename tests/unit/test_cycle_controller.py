import json

import numpy as np
import pytest

from contracts.benchmark import CYCLE_DQN, CYCLE_RULE, OBSERVATION_SPEC, TIMING, UNIFIED_DQN
from src.control.cycle_dqn import CANDIDATE_DIM, NOOP, FairCycleNativeController
from src.control.cycle_plan import cycle_length
from src.control.factory import create_controller


def topology(phases, topology_id="toy"):
    node = {"node_id": "J", "approaches": [f"A{i}" for i in range(phases)], "phases": [
        {"phase_id": f"P{i}", "approaches": [f"A{i}"],
         "movements": [{"from_approach": f"A{i}", "to_node": None, "to_approach": None}]} for i in range(phases)]}
    return {"topology_id": topology_id, "nodes": [node]}


def telemetry(top, idx, green, elapsed, t, queues):
    return {"J": {"node_id": "J", "current_phase_id": f"P{idx}", "signal_state": "GREEN" if green else "ALL_RED",
                  "elapsed_green_s": elapsed, "simulation_time_s": t,
                  "phase_service_age_s": {f"P{i}": 5.0 * i for i in range(len(queues))},
                  "approaches": [{"approach_id": f"A{i}", "queue_vehicles": q, "occupancy_ratio": 0.2,
                                  "confidence": 1.0, "external_due_count": 0, "stopped_wait_sum_s": 10.0 * q,
                                  "external_wait_sum_s": 0.0, "oldest_stopped_wait_s": 0.0,
                                  "oldest_external_wait_s": 0.0} for i, q in enumerate(queues)]}}


def run_cycles(controller, phases, cycles=3, queues=None):
    """Drive 5 s decisions against an ideal signal (5 s clearance per switch); return per-cycle greens."""
    top, queues = topology(phases), queues or [3 + 2 * i for i in range(phases)]
    idx, elapsed, t, seen, switches = 0, 0, 0, [], []
    while len(switches) < cycles * phases:
        tel = telemetry(top, idx, True, elapsed, t, queues)
        target = controller.compute_command("J", tel["J"], top, tel, t)["target_phase_id"]
        if target != f"P{idx}":
            switches.append((idx, elapsed, t))
            idx, elapsed = int(target[1:]), 0  # clearance consumes this 5 s step; next green starts at 0
        else:
            elapsed += 5
        t += 5
    return switches


@pytest.mark.parametrize("phases", [2, 3, 4, 8])
def test_native_cycle_has_exact_length_and_per_phase_greens(phases):
    switches = run_cycles(FairCycleNativeController(), phases)
    first = [g for _, g, _ in switches[:phases]]
    assert sum(first) + 5 * phases == cycle_length(phases)
    assert all(10 <= g <= 60 and g % 5 == 0 for g in first)
    assert [i for i, _, _ in switches[:phases]] == list(range(phases))  # native order, every phase served
    for cycle in range(1, 3):  # repeats with the same exact length
        starts = [t for i, _, t in switches if i == 0]
        assert starts[cycle] - starts[cycle - 1] == cycle_length(phases)


def test_busier_phases_get_more_green():
    switches = run_cycles(FairCycleNativeController(), 3, queues=[1, 4, 25])
    greens = [g for _, g, _ in switches[:3]]
    assert greens[2] > greens[0]


@pytest.mark.parametrize("phases", [2, 4, 8])
def test_transfer_conserves_the_cycle_and_moves_five_seconds(phases):
    from src.control.cycle_plan import legal_transfers

    chosen = []

    def first_legal(node, view, base):
        donor, recipient = legal_transfers(base)[0]
        chosen.append((donor, recipient))
        return donor * 8 + recipient

    plain = [g for _, g, _ in run_cycles(FairCycleNativeController(), phases)[:phases]]
    moved = [g for _, g, _ in run_cycles(FairCycleNativeController(selector=first_legal), phases)[:phases]]
    donor, recipient = chosen[0]
    expected = list(plain)
    expected[donor] -= 5
    expected[recipient] += 5
    assert moved == expected and sum(moved) == sum(plain)


def test_selector_sees_base_greens_and_runs_once_per_cycle():
    calls = []

    def selector(node, view, base):
        calls.append(tuple(base))
        return NOOP

    run_cycles(FairCycleNativeController(selector=selector), 4, cycles=3)
    assert len(calls) in (3, 4) and len(set(calls)) == 1  # one decision per cycle start


def test_illegal_transfer_is_rejected():
    c = FairCycleNativeController(selector=lambda n, v, base: 1 * 8 + 1)  # donor == recipient
    with pytest.raises(ValueError):
        run_cycles(c, 2)


def artifact(seed=0, **override):
    rng = np.random.default_rng(seed)
    a = dict(schema="unified_dqn_v1", algorithm="fair_cycle_unified", architecture="candidate_pair_scorer",
             reward_version="wait_tail_v1", observation=OBSERVATION_SPEC, timing=TIMING, topology_id="toy",
             cycle_rule=CYCLE_RULE, candidate_extras=CYCLE_DQN["extras"],
             weights=dict(w1=rng.normal(size=(UNIFIED_DQN["hidden"], CANDIDATE_DIM)).tolist(),
                          w2=rng.normal(size=(1, UNIFIED_DQN["hidden"])).tolist()),
             provenance=dict(network_sha256="n", topology_sha256="t", learner_seed=17))
    a.update(override)
    return a


def write(tmp_path, a, name="m.json"):
    path = tmp_path / name
    path.write_text(json.dumps(a))
    return str(path)


@pytest.mark.parametrize("phases", [2, 4, 8])
def test_learned_controller_keeps_the_cycle_budget_and_depends_on_weights(tmp_path, phases):
    runs = []
    for seed in (1, 2, 3):
        c = create_controller("fair_cycle_unified", model_path=write(tmp_path, artifact(seed), f"{seed}.json"))
        switches = run_cycles(c, phases)
        greens = [g for _, g, _ in switches[:phases]]
        assert sum(greens) + 5 * phases == cycle_length(phases) and all(10 <= g <= 60 for g in greens)
        runs.append(tuple(greens))
    assert len(set(runs)) > 1  # different weights choose different transfers


def test_learned_controller_rejects_bad_artifacts_and_other_maps(tmp_path):
    for bad in (artifact(cycle_rule=dict(CYCLE_RULE, base_s=80)), artifact(observation=dict(OBSERVATION_SPEC, radius_hops=1)),
                artifact(candidate_extras=["x"]), artifact(algorithm="phase_dqn_unified", architecture="scalar_phase_scorer")):
        with pytest.raises(ValueError):
            create_controller("fair_cycle_unified", model_path=write(tmp_path, bad))
    c = create_controller("fair_cycle_unified", model_path=write(tmp_path, artifact(topology_id="other")))
    with pytest.raises(ValueError):
        run_cycles(c, 2)
