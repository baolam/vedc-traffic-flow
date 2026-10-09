import pytest

from src.control.fair_cycle import FairCycleController


def fixture():
    node = {"node_id": "J1", "approaches": [f"J1_{d}_IN" for d in "NSEW"], "phases": [
        {"phase_id": "J1_PHASE_NS", "movements": [
            {"from_approach": "J1_N_IN", "to_node": None}, {"from_approach": "J1_S_IN", "to_node": None}]},
        {"phase_id": "J1_PHASE_EW", "movements": [
            {"from_approach": "J1_E_IN", "to_node": None}, {"from_approach": "J1_W_IN", "to_node": None}]},
    ]}
    topology = {"nodes": [node]}
    telemetry = {"node_id": "J1", "current_phase_id": "J1_PHASE_NS", "signal_state": "GREEN",
                 "elapsed_green_s": 0., "simulation_time_s": 0.,
                 "phase_service_age_s": {"J1_PHASE_NS": 0., "J1_PHASE_EW": 0.}, "approaches": [
                     {"approach_id": f"J1_{d}_IN", "queue_vehicles": 0., "occupancy_ratio": 0.,
                      "external_due_count": 0, "stopped_wait_sum_s": 0., "external_wait_sum_s": 0.,
                      "oldest_stopped_wait_s": 0., "oldest_external_wait_s": 0., "confidence": 1.}
                     for d in "NSEW"]}
    return node, topology, telemetry


@pytest.mark.parametrize("cycle,share", [(50, .25), (50, 1/3), (70, .25), (70, 1/3), (90, .25), (90, 1/3)])
def test_cycle_has_both_phase_minimum_and_respects_max_green(cycle, share):
    controller = FairCycleController(cycle, share)
    node, topology, telemetry = fixture()
    command = controller.compute_command("J1", telemetry, topology)
    ns, ew = controller.current_split("J1")
    assert ns + ew == cycle - 10
    assert min(ns, ew) >= controller.minimum_green_s
    assert max(ns, ew) <= 60


def test_wait_urgency_changes_split_and_schedule_holds_until_green_allocation():
    controller = FairCycleController(70, 1/3)
    node, topology, telemetry = fixture()
    telemetry["approaches"][2]["external_due_count"] = 40
    telemetry["approaches"][2]["external_wait_sum_s"] = 12000
    command = controller.compute_command("J1", telemetry, topology)
    split = controller.current_split("J1")
    assert split[1] > split[0]
    telemetry["elapsed_green_s"] = split[0] - 5
    assert controller.compute_command("J1", telemetry, topology)["target_phase_id"] == "J1_PHASE_NS"
    telemetry["elapsed_green_s"] = split[0]
    assert controller.compute_command("J1", telemetry, topology)["target_phase_id"] == "J1_PHASE_EW"


def test_cycle_rejects_unsupported_timing():
    with pytest.raises(ValueError):
        FairCycleController(30, .25)


def test_fair_feature_extractor_has_contract_order_and_finite_values():
    import numpy as np
    from contracts.research import FAIR_CYCLE_FEATURE_SPEC
    from src.control.research import extract_fair_cycle_features

    node, topology, telemetry = fixture()
    features = extract_fair_cycle_features(node, telemetry, {"J1": telemetry},
                                           (30, 30), (30, 30))
    assert features.shape == (len(FAIR_CYCLE_FEATURE_SPEC["ordering"]),)
    assert np.isfinite(features).all()


def test_fair_controller_artifact_has_three_bounded_actions(tmp_path):
    torch = pytest.importorskip("torch")
    from src.rl.shared_dqn import Learner
    from src.control.research import FairCycleRLController
    learner = Learner({"algorithm": "fair_cycle_dqn", "device": "cpu", "replay_capacity": 4,
                       "cycle_time_s": 70, "min_green_share": 1/3}, 17)
    artifact_path = tmp_path / "fair-cycle.json"
    learner.export(artifact_path, {"network_sha256": "net", "topology_sha256": "topo"})
    controller = FairCycleRLController(str(artifact_path))
    assert controller.policy.action_dim == 3
    assert controller.residual_mask_for(20) == [False, True, True]
    assert controller.residual_mask_for(40) == [True, True, False]


def test_east_west_surge_is_registered_and_mirrors_the_north_south_profile():
    from contracts.scenarios import ScenarioRegistry

    north = ScenarioRegistry.get_flow_rates("directional_surge")
    east = ScenarioRegistry.get_flow_rates("directional_surge_ew")
    for junction in range(1, 5):
        assert east[f"f_J{junction}_NS"] == north[f"f_J{junction}_EW"]
        assert east[f"f_J{junction}_EW"] == north[f"f_J{junction}_NS"]


def test_fair_dqn_uses_three_masked_actions_and_elapsed_discount():
    torch = pytest.importorskip("torch")
    import numpy as np
    from src.rl.shared_dqn import Learner

    learner = Learner({"algorithm": "fair_cycle_dqn", "device": "cpu", "replay_capacity": 2,
                       "batch_size": 1, "discount": .99}, 17)
    with torch.no_grad():
        for network in (learner.online, learner.target):
            for param in network.parameters():
                param.zero_()
        learner.online[2].bias.copy_(torch.tensor([0., 1., 5.]))
        learner.target[2].bias.copy_(torch.tensor([100., 200., 400.]))
    state = np.zeros(52, np.float32)
    learner.replay.add(state, 0, 0., state, False, [True, True, True], discount=.5)
    assert learner.update() == pytest.approx(199.5, abs=1e-4)
    assert learner.last_update_diagnostics["mean_abs_td_error"] == pytest.approx(200.)
