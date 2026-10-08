import copy
import json
import random

import numpy as np
import pytest

from contracts.contracts_sdk import load_topology, list_scenarios, validate_payload
from contracts.research import FEATURE_SPEC, SEED_SPLITS, TOPOLOGY_ID
from src.control.research import SharedDQNController, action_mask, extract_features
from src.simulation.runtime import occupancy_ratio, validate_network


def state():
    topo = load_topology(TOPOLOGY_ID)
    data = {n["node_id"]: {"node_id": n["node_id"], "source_type": "simulation",
            "current_phase_id": n["phases"][0]["phase_id"], "signal_state": "GREEN",
            "pending_phase_id": None, "elapsed_green_s": 0.,
            "phase_service_age_s": {p["phase_id"]: 0. for p in n["phases"]},
            "approaches": [{"approach_id": a, "queue_vehicles": i+1., "occupancy_ratio": .005,
                            "confidence": 1., "mean_speed_mps": 3., "flow_veh_per_s": 0.}
                           for i, a in enumerate(n["approaches"])]} for n in topo["nodes"]}
    return topo, data


def test_masks_cover_minimum_maximum_and_uninterruptible_clearance():
    topo, data = state()
    node, tel = topo["nodes"][0], data["J1"]
    np.testing.assert_array_equal(action_mask(node, tel), [True, False])
    tel["elapsed_green_s"] = 10
    np.testing.assert_array_equal(action_mask(node, tel), [True, True])
    tel["elapsed_green_s"] = 60
    np.testing.assert_array_equal(action_mask(node, tel), [False, True])
    tel["signal_state"], tel["pending_phase_id"] = "YELLOW", "J1_PHASE_EW"
    np.testing.assert_array_equal(action_mask(node, tel), [False, True])
    tel["signal_state"] = "ALL_RED"
    np.testing.assert_array_equal(action_mask(node, tel), [False, True])
    tel["pending_phase_id"] = None
    with pytest.raises(ValueError):
        action_mask(node, tel)


def test_features_use_mapped_approach_and_reject_missing_invalid_data():
    topo, data = state()
    features = extract_features(topo["nodes"][0], data["J1"], data)
    assert features.shape == (28,)
    assert features[8] == pytest.approx(.05)  # J1_N_IN -> J3_N_IN, not node average.
    assert features[10] == 0  # Boundary exit has no downstream approach.
    validate_payload(data["J1"], "telemetry")
    del data["J1"]["elapsed_green_s"]
    with pytest.raises(KeyError):
        extract_features(topo["nodes"][0], data["J1"], data)


def test_low_occupancy_and_topology_mapping():
    assert occupancy_ratio(.5) == .005
    assert occupancy_ratio(1) == .01
    with pytest.raises(ValueError):
        occupancy_ratio(float("nan"))
    topo = load_topology(TOPOLOGY_ID)
    validate_network(topo, "networks/four_intersection_rl_v1/network.net.xml")
    topo["nodes"][0]["phases"][0]["sumo_state"] = "GGGG"
    with pytest.raises(ValueError):
        validate_network(topo, "networks/four_intersection_rl_v1/network.net.xml")


def test_typed_topology_preserves_research_mappings():
    from contracts.contracts_sdk import load_topology_contract
    topo = load_topology_contract(TOPOLOGY_ID).to_dict()
    validate_network(topo, "networks/four_intersection_rl_v1/network.net.xml")
    assert topo["nodes"][0]["phases"][0]["movements"][0]["to_approach"] == "J3_N_IN"


def test_shared_dqn_rejects_topology_feature_order_drift():
    from contracts.research import validate_research_topology
    topo = load_topology(TOPOLOGY_ID)
    topo["nodes"][0]["approaches"].reverse()
    with pytest.raises(ValueError):
        validate_research_topology(topo)


def test_seed_splits_are_disjoint():
    assert not set(SEED_SPLITS["train"]) & set(SEED_SPLITS["validation"])
    assert not set(SEED_SPLITS["holdout"]) & (set(SEED_SPLITS["train"]) | set(SEED_SPLITS["validation"]))
    assert "downstream_bottleneck" in list_scenarios()


def test_export_parity_corrupt_rejection_and_masked_inference(tmp_path):
    torch = pytest.importorskip("torch")
    from src.rl.shared_dqn import Learner
    learner = Learner({"device": "cpu", "replay_capacity": 100}, 17)
    path = tmp_path / "policy.json"
    artifact = learner.export(path, {"network_sha256": "test", "topology_sha256": "test"})
    policy = SharedDQNController(path)
    topo, data = state()
    x = np.stack([extract_features(n, data[n["node_id"]], data) for n in topo["nodes"]])
    np.testing.assert_allclose(policy.policy.predict(x), learner.online(torch.tensor(x)).detach().numpy(), atol=1e-6)
    assert policy.compute_command("J1", data["J1"], topo, data)["target_phase_id"] == "J1_PHASE_NS"
    artifact["weights"]["w1"][0][0] = float("nan")
    path.write_text(json.dumps(artifact))
    with pytest.raises(ValueError):
        SharedDQNController(path)
    with pytest.raises(FileNotFoundError):
        SharedDQNController(tmp_path / "missing.json")


def test_checkpoint_restores_update_replay_rng_and_masks(tmp_path):
    torch = pytest.importorskip("torch")
    from src.rl.shared_dqn import Learner
    config = {"device": "cpu", "replay_capacity": 16, "batch_size": 8}
    a = Learner(config, 17)
    for i in range(10):
        a.replay.add(np.full(28, i), i % 2, -i, np.ones(28), i == 9, [False, True])
    a.update()
    a.save(tmp_path / "checkpoint.pt")
    loss = a.update()
    values = (random.random(), np.random.random(), torch.rand(1))
    b = Learner(config, 17)
    b.load(tmp_path / "checkpoint.pt")
    assert b.update() == pytest.approx(loss)
    assert random.random() == values[0]
    assert np.random.random() == values[1]
    assert torch.equal(torch.rand(1), values[2])
    for p, q in zip(a.online.parameters(), b.online.parameters()):
        assert torch.equal(p, q)


def test_double_dqn_target_masks_illegal_action_and_bootstraps_truncation():
    torch = pytest.importorskip("torch")
    from src.rl.shared_dqn import Learner
    learner = Learner({"device": "cpu", "replay_capacity": 2, "batch_size": 1}, 17)
    with torch.no_grad():
        for network in (learner.online, learner.target):
            for param in network.parameters():
                param.zero_()
        learner.online[2].bias.copy_(torch.tensor([1000., 1.]))
        learner.target[2].bias.copy_(torch.tensor([100000., 2.]))
    # A time-limit truncation is not a natural terminal state: its future value is retained.
    learner.replay.add(np.zeros(28), 1, 0., np.zeros(28), False, [False, True])
    assert learner.update() == pytest.approx(.5 * (.99 * 2 - 1)**2, abs=1e-6)


def test_promotion_gate_requires_all_pairs_and_rejects_fairness_regression():
    from src.rl.benchmark import promotion_gate
    from contracts.research import RESEARCH_SCENARIOS
    rows = [{"scenario": s, "seed": seed, "valid": True, "demand_sha256": str(seed),
             "network_sha256": "net", "topology_sha256": "topo", "timing": {}, "scheduled": 100,
             "demand_s": 1800, "drain_s": 600, "delay_per_scheduled_s": 100., "completed": 100,
             "p95_wait_s": 100., "worst_approach_wait_s": 100., "max_approach_p95_wait_s": 100.,
             "collisions": 0, "teleports": 0,
             "accounting_losses": 0} for s in RESEARCH_SCENARIOS for seed in SEED_SPLITS["holdout"]]
    candidate = copy.deepcopy(rows)
    for row in candidate:
        row["delay_per_scheduled_s"] = 90.
    baselines = {"edgeflow": rows, "max_pressure": rows, "actuated": rows, "fixed_time": rows}
    assert promotion_gate(candidate, baselines)["promoted"]
    candidate[0]["p95_wait_s"] = 1000.
    assert not promotion_gate(candidate, baselines)["promoted"]
    with pytest.raises(ValueError):
        promotion_gate(candidate[:-1], baselines)
