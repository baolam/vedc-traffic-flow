import json
import numpy as np
import pytest
from src.benchmark.evidence import execute_case, snapshot_source
from src.benchmark.suite import expand, load_suite
from src.benchmark.resources import simulator_slot
from src.control.phase_dqn import phase_features, phase_mask


def test_default_suite_has_six_maps_and_paired_cases():
    suite = load_suite("configs/benchmarks/suite_v1.yaml")
    cases = expand(suite)
    assert len(suite["maps"]) == 6
    assert len(cases) == 23 * 3 * 4 + 8 * 3
    assert all(c["seed"] >= 90001 for c in cases)


def test_final_freeze_contains_only_validation_selected_learner():
    from contracts.benchmark import SEEDS
    from src.benchmark.campaign import freeze_models

    suite = load_suite("configs/benchmarks/suite_v1.yaml")
    mapping = suite["maps"][0]
    mapping["models"] = {"17": "seed17.json", "29": "seed29.json", "43": "seed43.json"}
    selection = {mapping["id"]: dict(learner_seed=29, model_path="seed29.json")}
    frozen = freeze_models(dict(suite, maps=[mapping]), selection)
    cases = expand(frozen, "test")
    learned = [case["controller"] for case in cases if case["controller"]["type"] == "phase_dqn"]
    assert len(learned) == len(mapping["cases"]) * len(SEEDS["test"])
    assert {policy["learner_seed"] for policy in learned} == {29}


def test_sumo_occupancy_clamps_only_rounding_noise():
    from src.simulation.runtime import occupancy_ratio

    assert occupancy_ratio(-1e-16) == 0
    assert occupancy_ratio(100 + 1e-8) == 1
    with pytest.raises(ValueError):
        occupancy_ratio(-1e-5)


def test_complete_case_is_reused_but_failed_attempt_is_preserved(tmp_path):
    calls = []

    def fail(output):
        calls.append(output)
        raise RuntimeError("interrupted")

    with pytest.raises(RuntimeError):
        execute_case(tmp_path, {"seed": 90001}, fail)
    assert len(list(tmp_path.glob("*/attempt-*/failure.json"))) == 1
    result = execute_case(tmp_path, {"seed": 90001}, lambda _: {"valid": True, "completed": 5})
    assert result["completed"] == 5
    assert execute_case(tmp_path, {"seed": 90001}, fail) == result
    assert len(calls) == 1


def test_source_snapshot_is_hash_addressed_and_verifiable(tmp_path):
    from src.benchmark.evidence import file_hash

    snapshot = __import__("pathlib").Path(snapshot_source(tmp_path))
    manifest = json.loads((snapshot / "manifest.json").read_text())
    assert manifest and all(file_hash(snapshot / path) == sha for path, sha in manifest.items())


def test_invalid_training_episode_is_terminal_in_replay():
    from collections import deque
    from src.benchmark.train import close_partial_episode

    replay = deque(
        [
            (np.array([1]), 0, np.array([2]), np.array([True]), False),
            (np.array([3]), 0, np.array([4]), np.array([True]), False),
            (np.array([5]), 0, np.array([6]), np.array([True]), False),
        ],
        maxlen=10,
    )
    close_partial_episode(replay, 2)
    assert [row[-1] for row in replay] == [False, True, True]


def test_pilot_worker_continues_after_invalid_case(monkeypatch):
    from queue import Queue
    import src.benchmark.cli as cli
    from src.benchmark.scheduling import _worker

    def execute(task):
        if task == "bad":
            raise ValueError("invalid case")
        return task

    monkeypatch.setattr(cli, "execute", execute)
    tasks, results = Queue(), Queue()
    tasks.put((0, "bad"))
    tasks.put((1, "good"))
    tasks.put(None)
    _worker(tasks, results, continue_on_error=True)
    first, second = results.get(), results.get()
    assert first[0] == 0 and first[2] and second == (1, "good", None)


def test_four_global_slots_and_invalid_limits():
    with (
        simulator_slot(timeout=0.1),
        simulator_slot(timeout=0.1),
        simulator_slot(timeout=0.1),
        simulator_slot(timeout=0.1),
    ):
        with pytest.raises(TimeoutError):
            with simulator_slot(timeout=0.1):
                pass
    with pytest.raises(ValueError):
        with simulator_slot(5):
            pass


def test_variable_phases_and_exact_features():
    node = dict(phases=[dict(phase_id=f"p{i}", approaches=[f"a{i}"], movements=[]) for i in range(3)])
    t = dict(
        current_phase_id="p0",
        signal_state="GREEN",
        elapsed_green_s=10,
        phase_service_age_s={"p0": 0, "p1": 60, "p2": 120},
        approaches=[
            dict(approach_id=f"a{i}", queue_vehicles=20 * i, occupancy_ratio=0.1 * i, confidence=1) for i in range(3)
        ],
    )
    x = phase_features(node, t, {})
    np.testing.assert_allclose(x[1], [1, 0.1, 0, 0, 2, 1, 1 / 6, 0, 1, 0, 0, 1])
    assert phase_mask(node, t).tolist() == [True, True, True]
    t["elapsed_green_s"] = 60
    assert phase_mask(node, t).tolist() == [False, True, True]
    t.update(signal_state="YELLOW", pending_phase_id="p2")
    assert phase_mask(node, t).tolist() == [False, False, True]


def test_gate_rejects_missing_pairs_and_unpaired_inputs():
    from src.benchmark.scoring import qualification, BASELINES

    row = dict(
        scenario="balanced",
        seed=80001,
        valid=True,
        scheduled=100,
        completed=100,
        unfinished=0,
        uninserted=0,
        delay_per_scheduled_s=100,
        p95_wait_s=10,
        worst_approach_wait_s=15,
        max_approach_p95_wait_s=12,
        network_sha256="n",
        topology_sha256="t",
        demand_sha256="d",
        timing={},
        demand_s=1800,
        drain_s=600,
        metrics_version=3,
        collisions=0,
        teleports=0,
        accounting_losses=0,
    )
    baseline = {name: [dict(row)] for name in BASELINES}
    candidate = dict(row, delay_per_scheduled_s=90)
    assert qualification([candidate], baseline, ["balanced"], [80001])["promoted"]
    assert not qualification([], baseline, ["balanced"], [80001])["complete"]
    changed = dict(candidate, demand_sha256="other")
    assert not qualification([changed], baseline, ["balanced"], [80001])["promoted"]
    unfair = dict(candidate, p95_wait_s=40)
    assert not qualification([unfair], baseline, ["balanced"], [80001])["promoted"]


def test_synthetic_demand_is_frozen_and_honors_fleet_routes(tmp_path):
    from src.benchmark.demand import generate_demand
    from contracts.benchmark import FLEET

    topology = dict(
        topology_id="example", routes=[dict(route_id="a", edges=["a", "b"], axis="NS", allowed_classes=list(FLEET))]
    )
    a = generate_demand(topology, "balanced", 90001, 1000, 1, tmp_path / "a.xml")
    b = generate_demand(topology, "balanced", 90001, 1000, 1, tmp_path / "b.xml")
    assert a == b and (tmp_path / "a.xml").read_bytes() == (tmp_path / "b.xml").read_bytes()
    assert len(a) > 0 and set(row["vehicle_class"] for row in a.values()) <= set(FLEET)
    topology["routes"][0]["allowed_classes"] = ["car"]
    with pytest.raises(ValueError, match="No permitted route"):
        generate_demand(topology, "balanced", 90001, 1000, 1, tmp_path / "bad.xml")


def test_calibration_brackets_known_capacity_and_rejects_unbracketed_load():
    from src.benchmark.calibration import bracket_capacity

    low, high = bracket_capacity(lambda load: load <= 0.7)
    assert low <= 0.7 < high and high - low <= 0.125
    with pytest.raises(ValueError, match="not bracketed"):
        bracket_capacity(lambda _: True)


def test_invalid_results_are_not_retried(tmp_path):
    calls = []

    def invalid(_):
        calls.append(1)
        return {"valid": False}

    with pytest.raises(ValueError):
        execute_case(tmp_path, {"seed": 90001}, invalid)
    with pytest.raises(ValueError, match="Scientifically invalid"):
        execute_case(tmp_path, {"seed": 90001}, invalid)
    assert len(calls) == 1


def test_phase_model_runs_through_shared_factory_without_pytorch(tmp_path):
    from contracts.benchmark import PHASE_FEATURES, PHASE_NORMALIZATION, TIMING
    from src.control.factory import create_controller

    weights = dict(w1=np.zeros((64, 12)).tolist(), b1=np.zeros(64).tolist(), w2=np.zeros((1, 64)).tolist(), b2=[0.0])
    artifact = dict(
        algorithm="phase_dqn_v1",
        features=PHASE_FEATURES,
        normalization=PHASE_NORMALIZATION,
        timing=TIMING,
        topology_id="test",
        weights=weights,
        provenance=dict(network_sha256="n", topology_sha256="t"),
    )
    model = tmp_path / "model.json"
    model.write_text(json.dumps(artifact))
    policy = create_controller("phase_dqn", model_path=str(model))
    node = dict(
        node_id="J1",
        approaches=["a", "b"],
        phases=[dict(phase_id="p0", approaches=["a"]), dict(phase_id="p1", approaches=["b"])],
    )
    state = dict(
        current_phase_id="p0",
        signal_state="GREEN",
        elapsed_green_s=60,
        phase_service_age_s={"p0": 0, "p1": 60},
        approaches=[dict(approach_id=a, confidence=1, occupancy_ratio=0, queue_vehicles=0) for a in ["a", "b"]],
    )
    command = policy.compute_command("J1", state, dict(topology_id="test", nodes=[node]), network_state={"J1": state})
    assert command["target_phase_id"] == "p1" and command["controller"] == "phase_dqn"
