from types import SimpleNamespace
import numpy as np
import pytest
import torch

from contracts.benchmark import DQN_RECIPE, OBSERVATION_SPEC, UNIFIED_DQN
from src.control.unified_dqn import PHASE_ALGORITHMS, FEATURES, MAX_PHASES, UnifiedDQNController
from src.rl.unified_train import Replay, build_net, discount, export_artifact, node_pressure_reward, q_all
from tests.unit.test_observation import chain, telemetry, set_queue


def test_discount_is_physical_time_based():
    assert discount(DQN_RECIPE, 5) == pytest.approx(0.99)
    assert discount(DQN_RECIPE, 70) == pytest.approx(0.99 ** 14)
    assert discount(DQN_RECIPE, 70) == pytest.approx(0.869, abs=1e-3)


def test_node_pressure_reward_uses_incoming_minus_receiving():
    top = chain()
    tel = telemetry(top)
    set_queue(tel, "C", "C_W", 10)
    set_queue(tel, "C", "C_S", 10)
    set_queue(tel, "D", "D_W", 4)
    node = next(n for n in top["nodes"] if n["node_id"] == "C")
    assert node_pressure_reward(node, tel) == pytest.approx(-(20 - 4) / 20)
    last = next(n for n in top["nodes"] if n["node_id"] == "E")
    assert node_pressure_reward(last, tel) == pytest.approx(0.0)  # boundary: no receiving approaches


def test_replay_ring_and_state_roundtrip():
    r = Replay(3)
    row = dict(s=np.ones((MAX_PHASES, FEATURES)), action=1, reward=-1.0, s2=np.zeros((MAX_PHASES, FEATURES)),
               m2=np.ones(MAX_PHASES), terminal=False, dt=5.0)
    for i in range(5):
        r.add(**{**row, "reward": float(i)})
    assert r.size == 3 and sorted(r.a["reward"].tolist()) == [2.0, 3.0, 4.0]
    other = Replay(3)
    other.load(r.state())
    assert other.size == 3 and other.ptr == r.ptr
    assert other.sample(8, np.random.default_rng(0))["s"].shape == (8, MAX_PHASES, FEATURES)


@pytest.mark.parametrize("algorithm", PHASE_ALGORITHMS)
def test_exported_numpy_policy_matches_torch_and_loads(tmp_path, algorithm):
    architecture = UNIFIED_DQN["algorithms"][algorithm][0]
    net = build_net(architecture)
    (tmp_path / "n.net").write_text("n")
    (tmp_path / "t.json").write_text("t")
    spec = dict(id="chain", network_path=str(tmp_path / "n.net"), topology_path=str(tmp_path / "t.json"))
    export_artifact(spec, algorithm, net, 17, tmp_path / "m.json")  # raises on torch/numpy mismatch
    controller = UnifiedDQNController(str(tmp_path / "m.json"))
    top = chain()
    commands = controller.compute_commands(telemetry(top), {**top, "topology_id": "chain"})
    assert len(commands) == len(top["nodes"])
    x = torch.rand(4, MAX_PHASES, FEATURES)
    assert q_all(architecture, net, x).shape == (4, MAX_PHASES)
    assert OBSERVATION_SPEC["max_phases"] == MAX_PHASES


def test_trainer_refuses_algorithms_without_a_trainer(tmp_path):
    from src.rl.unified_train import train_run

    with pytest.raises(ValueError, match="No trainer"):
        train_run({}, "graph_mappo", 17, tmp_path)  # MAPPO has its own trainer, not this one


def test_validation_uses_light_checks_but_same_cases_and_seeds(monkeypatch, tmp_path):
    import src.benchmark.scheduling as scheduling
    from contracts.benchmark import DQN_RECIPE, SEEDS
    from src.rl.unified_train import TRAIN_CHECK_EVERY, evaluate_candidate

    seen = {}
    monkeypatch.setattr(scheduling, "run_tasks", lambda tasks, workers, continue_on_error=False: seen.update(tasks=tasks) or [])
    spec = dict(id="m", cases=["a", "b"])
    evaluate_candidate(spec, "phase_dqn_unified", 17, tmp_path / "m.json", DQN_RECIPE, tmp_path, 2)
    protocols = {tuple(sorted(t[1].items())) for t in seen["tasks"]}
    assert len(protocols) == 1 and dict(protocols.pop())["trace"] is False
    assert dict(seen["tasks"][0][1])["check_every"] == TRAIN_CHECK_EVERY
    assert {(t[0]["scenario"], t[0]["seed"]) for t in seen["tasks"]} == {(c, s) for c in "ab" for s in SEEDS["validation"]}


def test_invalid_validation_case_makes_candidate_infeasible_not_fatal(monkeypatch):
    import src.benchmark.scheduling as scheduling
    from src.rl import unified_train as ut
    from src.rl.selection import validation_score

    spec = dict(cases=["balanced"])
    good = dict(scenario="balanced", valid=True, scheduled=1, completed=1, collisions=0, teleports=0,
                accounting_losses=0, delay_per_scheduled_s=1.0, p95_wait_s=1, worst_approach_wait_s=1,
                max_approach_p95_wait_s=1)
    seen = {}

    def fake(tasks, workers, continue_on_error=False):
        seen["continue"] = continue_on_error
        return [None] + [dict(good, seed=t[0]["seed"]) for t in tasks[1:]]

    monkeypatch.setattr(scheduling, "run_tasks", fake)
    rows = ut.evaluate_candidate(spec, "phase_dqn_unified", 17, "x.json", ut.DQN_RECIPE, ".", 1)
    assert seen["continue"] and len(rows) == len(ut.SEEDS["validation"]) - 1
    ref = [dict(good, seed=s) for s in ut.SEEDS["validation"]]
    result = validation_score(rows, ref, ["balanced"], ut.SEEDS["validation"])
    assert not result["feasible"]


def test_max_pressure_residual_keeps_mp_unless_q_beats_it_by_margin(monkeypatch):
    import numpy as np
    from src.control import unified_dqn as ud

    q, mask = np.array([-100.0, -98.0, -90.0]), np.array([True, True, False])
    assert ud.residual_choice(q, mask, 0) == 1  # gate off (nan): plain masked greedy
    monkeypatch.setattr(ud, "MP_MARGIN", 0.05)
    assert ud.residual_choice(q, mask, 0) == 0  # Q gain 2 < 0.05 * 100: follow max_pressure
    monkeypatch.setattr(ud, "MP_MARGIN", 0.01)
    assert ud.residual_choice(q, mask, 0) == 1  # gain 2 > 1: deviate
    assert ud.residual_choice(q, mask, 2) == 1  # max_pressure's phase illegal: greedy
    q3, all3 = np.array([-100.0, -50.0, -90.0]), np.array([True, True, True])
    assert ud.residual_choice(q3, all3, 0, 2) == 2  # best phase 1 is not the alt's: the alt (gain 10) wins
    assert ud.residual_choice(q3, all3, 0, 0) == 0  # alt agrees with the base


def test_residual_base_resets_when_the_sim_clock_goes_back(monkeypatch):
    from src.control import unified_dqn as ud

    calls = []
    base = SimpleNamespace(reset=lambda: calls.append("reset"),
                           compute_command=lambda nid, t, topo, view, current_time_s: {"target_phase_id": "B"})
    monkeypatch.setattr(ud, "_BASES", {"max_pressure": [base, -1.0]})
    monkeypatch.setattr(ud, "RESIDUAL_BASE", "max_pressure")
    node = {"node_id": "J1", "phases": [{"phase_id": "A"}, {"phase_id": "B"}]}
    for t in (5000, 10000, 10000, 5000):
        assert ud.base_index(node, {"timestamp_ms": t}, {}, {}) == 1
    assert calls == ["reset"]
