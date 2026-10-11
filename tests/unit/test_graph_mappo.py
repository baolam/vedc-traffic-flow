import copy
import json
import os
import random
from pathlib import Path
import threading
import time

import numpy as np
import pytest

from contracts.contracts_sdk import load_topology
from contracts.research import (GRAPH_MAPPO_ACTIONS, GRAPH_MAPPO_NODE_ORDER,
                                GRAPH_MAPPO_RELATION_FEATURE_SPEC, GRAPH_MAPPO_SEED_SPLITS,
                                GRAPH_MAPPO_SELECTION_SPEC, RESEARCH_SCENARIOS,
                                TOPOLOGY_ID, build_research_graph)


def telemetry_snapshot(topology, now=0.):
    state = {}
    for node in topology["nodes"]:
        nid = node["node_id"]
        state[nid] = {
            "node_id": nid, "simulation_time_s": now,
            "current_phase_id": node["phases"][0]["phase_id"],
            "pending_phase_id": None, "signal_state": "GREEN", "elapsed_green_s": 0.,
            "phase_service_age_s": {phase["phase_id"]: 0. for phase in node["phases"]},
            "approaches": [{"approach_id": app, "queue_vehicles": float(index),
                            "occupancy_ratio": index / 100., "confidence": 1.,
                            "stopped_wait_sum_s": 0., "oldest_stopped_wait_s": 0.,
                            "external_due_count": 0., "external_wait_sum_s": 0.,
                            "oldest_external_wait_s": 0.}
                           for index, app in enumerate(node["approaches"])]}
    return state


def _sleeping_case_worker(start_event, result_pipe, *unused):
    if os.name != "nt":
        os.setsid()
    start_event.wait()
    time.sleep(30)


def actor_pair(topology, seed=17):
    torch = pytest.importorskip("torch")
    from src.rl.graph_mappo import GraphActor, actor_weights
    graph = build_research_graph(topology)
    torch.manual_seed(seed)
    graph_actor = GraphActor(graph, local_only=False, device="cpu").eval()
    torch.manual_seed(seed)
    local_actor = GraphActor(graph, local_only=True, device="cpu").eval()
    return graph, graph_actor, local_actor, actor_weights(graph_actor), actor_weights(local_actor)


def test_canonical_graph_keeps_movement_identity_direction_and_boundaries():
    topology = load_topology(TOPOLOGY_ID)
    graph = build_research_graph(topology)
    assert graph["node_order"] == list(GRAPH_MAPPO_NODE_ORDER)
    assert len(graph["senders"]) == 20  # 8 internal movements in both directions plus four self relations.
    assert sum(graph["self_relations"]) == 4
    assert len(set(graph["relation_ids"])) == len(graph["relation_ids"])
    assert len(graph["relation_features"][0]) == len(GRAPH_MAPPO_RELATION_FEATURE_SPEC["ordering"])
    assert graph["relation_features"][-1][-1] == 1.
    assert not any(row[10] for row, is_self in zip(graph["relation_features"], graph["self_relations"]) if is_self)
    assert sum(row[12] for row in graph["relation_features"]) == 8
    assert sum(row[13] for row in graph["relation_features"]) == 8

    duplicate = copy.deepcopy(topology)
    movement = duplicate["nodes"][0]["phases"][1]["movements"][0]
    movement.update(to_node="J3", to_approach="J3_N_IN")
    more = build_research_graph(duplicate)
    assert len(more["relation_ids"]) == len(graph["relation_ids"]) + 2
    assert len(set(more["relation_ids"])) == len(more["relation_ids"])

    duplicate["nodes"].reverse()
    with pytest.raises(ValueError):
        build_research_graph(duplicate)


def test_graph_actor_matches_numpy_and_local_actor_cannot_read_neighbors():
    torch = pytest.importorskip("torch")
    from src.control.graph_mappo_numpy import NumpyGraphActor
    from src.rl.graph_mappo import GraphActor

    topology = load_topology(TOPOLOGY_ID)
    graph, graph_actor, local_actor, graph_weights, local_weights = actor_pair(topology)
    rng = np.random.default_rng(91)
    observations = rng.normal(size=(4, 52)).astype(np.float32)
    with torch.no_grad():
        expected = graph_actor(torch.as_tensor(observations)).numpy()
        local_before = local_actor(torch.as_tensor(observations)).numpy()
    portable = NumpyGraphActor(graph_weights, graph)
    local_portable = NumpyGraphActor(local_weights, graph, local_only=True)
    np.testing.assert_allclose(portable.logits(observations), expected, rtol=1e-5, atol=2e-6)
    np.testing.assert_allclose(local_portable.logits(observations), local_before, rtol=1e-5, atol=2e-6)

    changed = observations.copy()
    changed[3] += 3.
    with torch.no_grad():
        local_after = local_actor(torch.as_tensor(changed)).numpy()
        graph_after = graph_actor(torch.as_tensor(changed)).numpy()
    np.testing.assert_allclose(local_before[0], local_after[0], rtol=0, atol=1e-7)
    assert not np.allclose(expected[0], graph_after[0])

    disconnected = copy.deepcopy(graph)
    keep = [index for index, (source, target, is_self) in enumerate(
        zip(graph["senders"], graph["receivers"], graph["self_relations"]))
            if is_self or (source != 3 and target != 3)]
    for key in ("senders", "receivers", "relation_features", "relation_ids", "self_relations"):
        disconnected[key] = [disconnected[key][index] for index in keep]
    isolated_actor = GraphActor(disconnected, device="cpu").eval()
    with torch.no_grad():
        isolated_before = isolated_actor(torch.as_tensor(observations)).numpy()
        isolated_after = isolated_actor(torch.as_tensor(changed)).numpy()
    np.testing.assert_allclose(isolated_before[0], isolated_after[0], rtol=0, atol=1e-7)

    masks = np.ones((4, 3), dtype=bool)
    masks[:, 0] = False
    masks[:, 2] = False
    np.testing.assert_array_equal(portable.deterministic_actions(observations, masks), np.ones(4, dtype=int))
    with pytest.raises(ValueError):
        portable.deterministic_actions(observations, np.zeros((4, 3), dtype=bool))


def test_time_scaled_gae_bootstraps_elapsed_time_and_stops_at_terminal():
    from src.rl.graph_mappo import generalized_advantage_estimate

    rewards = np.asarray([1., 2.])
    values = np.zeros((2, 4))
    next_values = np.asarray([[3., 3., 3., 3.], [100., 100., 100., 100.]])
    advantages, returns = generalized_advantage_estimate(
        rewards, values, next_values, [False, True], [5., 90.])
    last = 2.
    first = 1. + .99 * 3. + .99 * (.95 ** (5. / 90.)) * last
    np.testing.assert_allclose(advantages[:, 0], [first, last], rtol=1e-6)
    np.testing.assert_allclose(returns, advantages)


def test_running_value_normalizer_tracks_returns_and_rejects_invalid_values():
    torch = pytest.importorskip("torch")
    from src.rl.graph_mappo import RunningValueNormalizer

    normalizer = RunningValueNormalizer()
    raw = torch.tensor([1., 2., 3.])
    normalizer.update(raw)
    assert normalizer.count.item() == 3
    assert normalizer.mean.item() == 2
    torch.testing.assert_close(normalizer.variance, torch.tensor(2 / 3, dtype=torch.float64))
    torch.testing.assert_close(normalizer.denormalize(normalizer.normalize(raw)), raw)
    with pytest.raises(ValueError, match="finite return targets"):
        normalizer.update(torch.tensor([float("nan")]))


def test_validation_case_cache_shares_fair_cycle_cases_across_architecture_configs(tmp_path, monkeypatch):
    from src.rl import evaluation

    graph_config = {"environment": {"topology_path": "contracts/topology/four_intersection_rl_v1.json",
                                    "network_path": "networks/four_intersection_rl_v1/network.net.xml",
                                    "mode": "graph_mappo", "demand_s": 1800, "drain_s": 600}}
    local_config = copy.deepcopy(graph_config)
    local_config["environment"]["mode"] = "local_mappo"
    controller = {"type": "fair_cycle", "parameters": {"cycle_time_s": 90,
                                                          "min_green_share": .25}}
    signature = evaluation.case_signature(graph_config, controller, "balanced", 31001)
    assert evaluation.case_signature(local_config, controller, "balanced", 31001) == signature
    calls = []

    def fake_run_case(config, controller_spec, scenario, seed, output, timeout_s):
        output = Path(output)
        output.mkdir(parents=True)
        metrics = {"valid": True, "scenario": scenario, "seed": seed,
                   "delay_per_scheduled_s": 10., "controller": controller_spec}
        (output / "metrics.json").write_text(json.dumps(metrics))
        calls.append(output)
        return metrics

    monkeypatch.setattr(evaluation, "_run_isolated_case", fake_run_case)
    root = tmp_path / "cache"
    partial = root / signature[:2] / f"balanced-31001-{signature}"
    partial.mkdir(parents=True)
    (partial / "failure.json").write_text("partial")

    first, hit = evaluation.run_case_cached(graph_config, controller, "balanced", 31001, root)
    second, second_hit = evaluation.run_case_cached(local_config, controller, "balanced", 31001, root)
    assert first["valid"] and second["valid"]
    assert not hit and second_hit
    assert len(calls) == 1 and calls[0].name.endswith("-attempt1")


def test_case_cache_signature_changes_when_resolved_sumo_binary_changes(tmp_path, monkeypatch):
    from src.rl import evaluation
    from src.simulation import build_network

    sumo = tmp_path / "sumo.exe"
    sumo.write_text("sumo version one")
    monkeypatch.setattr(build_network, "binary", lambda name: str(sumo))
    config = {"environment": {"topology_path": "contracts/topology/four_intersection_rl_v1.json",
                              "network_path": "networks/four_intersection_rl_v1/network.net.xml",
                              "demand_s": 1800, "drain_s": 600}}
    controller = {"type": "fair_cycle", "parameters": {"cycle_time_s": 90,
                                                             "min_green_share": .25}}
    before = evaluation.case_signature(config, controller, "balanced", 60001)
    sumo.write_text("sumo version two")
    after = evaluation.case_signature(config, controller, "balanced", 60001)
    assert before != after


def test_isolated_evaluation_worker_is_terminated_at_case_deadline(tmp_path):
    from src.rl.evaluation import _run_isolated_case

    started = time.monotonic()
    with pytest.raises(TimeoutError, match="deadline"):
        _run_isolated_case({}, {}, "balanced", 31001, tmp_path / "timeout", .2,
                           worker=_sleeping_case_worker)
    assert time.monotonic() - started < 6.


def test_parallel_evaluation_preserves_case_order_and_caps_worker_count(tmp_path, monkeypatch):
    from src.rl import evaluation

    guard = threading.Lock()
    active = maximum = 0

    def fake_case(config, controller, scenario, seed, root, timeout_s=180., deadline=None):
        nonlocal active, maximum
        with guard:
            active += 1
            maximum = max(maximum, active)
        time.sleep(.02)
        with guard:
            active -= 1
        return {"scenario": scenario, "seed": seed}, False

    monkeypatch.setattr(evaluation, "run_case_cached", fake_case)
    rows, diagnostics = evaluation.evaluate_cases(
        {}, {"type": "fair_cycle"}, ("balanced", "directional_surge"), (1, 2),
        tmp_path, workers=2)
    assert [(row["scenario"], row["seed"]) for row in rows] == [
        ("balanced", 1), ("balanced", 2), ("directional_surge", 1), ("directional_surge", 2)]
    assert maximum == 2
    assert diagnostics["cases"] == 4


def test_masked_ppo_update_keeps_graphs_together_and_reports_diagnostics():
    torch = pytest.importorskip("torch")
    from src.rl.graph_mappo import (CentralizedCritic, GraphActor, MAPPOUpdater,
                                    masked_distribution)

    topology = load_topology(TOPOLOGY_ID)
    graph = build_research_graph(topology)
    actor = GraphActor(graph, device="cpu")
    critic = CentralizedCritic(device="cpu")
    observations = np.random.default_rng(4).normal(size=(8, 4, 52)).astype(np.float32)
    masks = np.ones((8, 4, 3), dtype=bool)
    masks[:, :, 0] = False
    with torch.no_grad():
        logits = actor(torch.as_tensor(observations))
        distribution = masked_distribution(logits, masks)
        actions = distribution.sample()
        old_log_probs = distribution.log_prob(actions)
    updater = MAPPOUpdater(actor, critic, {"minibatch_size": 4, "update_epochs": 2})
    diagnostics = updater.update(observations, actions.numpy(), masks, old_log_probs.numpy(),
                                 np.ones((8, 4), dtype=np.float32),
                                 np.zeros((8, 4), dtype=np.float32))
    assert updater.updates == 1
    assert diagnostics["actor_gradient_norm"] >= 0.
    assert diagnostics["critic_gradient_norm"] >= 0.
    assert diagnostics["entropy"] >= 0.
    assert all(np.isfinite(value) for value in diagnostics.values() if isinstance(value, (int, float)))


def test_batched_graph_attention_matches_serial_logits_and_gradients():
    torch = pytest.importorskip("torch")
    from src.rl.graph_mappo import GraphActor

    actor = GraphActor(build_research_graph(load_topology(TOPOLOGY_ID)), device="cpu")
    observations = torch.randn(7, 4, 52, generator=torch.Generator().manual_seed(23))
    batch_logits = actor(observations)
    serial_logits = torch.stack([actor(item) for item in observations])
    torch.testing.assert_close(batch_logits, serial_logits, rtol=1e-6, atol=1e-7)
    (batch_logits.square().sum()).backward()
    batched_gradients = [parameter.grad.detach().clone() for parameter in actor.parameters()]
    actor.zero_grad(set_to_none=True)
    torch.stack([actor(item) for item in observations]).square().sum().backward()
    for expected, parameter in zip(batched_gradients, actor.parameters()):
        torch.testing.assert_close(parameter.grad, expected, rtol=2e-5, atol=2e-6)


def test_ppo_kl_stop_skips_actor_updates_but_finishes_critic_epochs():
    torch = pytest.importorskip("torch")
    from src.rl.graph_mappo import (CentralizedCritic, GraphActor, MAPPOUpdater,
                                    masked_distribution)

    graph = build_research_graph(load_topology(TOPOLOGY_ID))
    actor, critic = GraphActor(graph), CentralizedCritic()
    observations = np.random.default_rng(18).normal(size=(8, 4, 52)).astype(np.float32)
    masks = np.ones((8, 4, 3), dtype=bool)
    with torch.no_grad():
        logits = actor(torch.as_tensor(observations))
        actions = torch.zeros((8, 4), dtype=torch.long)
        log_probs = masked_distribution(logits, masks).log_prob(actions) - 1.
    original_actor = [parameter.detach().clone() for parameter in actor.parameters()]
    original_critic = [parameter.detach().clone() for parameter in critic.parameters()]
    updater = MAPPOUpdater(actor, critic, {"minibatch_size": 4, "update_epochs": 3,
                                           "target_kl": .01})
    metrics = updater.update(observations, actions.numpy(), masks, log_probs.numpy(),
                             np.ones((8, 4), dtype=np.float32),
                             np.ones((8, 4), dtype=np.float32))
    assert metrics["actor_stopped_early"]
    assert metrics["actor_steps"] == 0
    assert metrics["critic_steps"] == 6
    assert metrics["stopping_kl"] > .01
    assert metrics["final_approx_kl"] > .01
    assert all(torch.equal(before, after) for before, after in
               zip(original_actor, actor.parameters()))
    assert any(not torch.equal(before, after) for before, after in
               zip(original_critic, critic.parameters()))


def test_joint_controller_is_call_order_independent_and_rejects_incomplete_snapshot(tmp_path):
    pytest.importorskip("torch")
    from src.control.graph_mappo import GraphMAPPOController
    from src.rl.graph_mappo import GraphActor
    from src.rl.train_mappo import export_actor
    from src.simulation.runtime import file_hash

    topology = load_topology(TOPOLOGY_ID)
    graph = build_research_graph(topology)
    actor = GraphActor(graph, device="cpu").eval()
    artifact_path = tmp_path / "graph-mappo.json"
    export_actor(artifact_path, actor, "graph_attention", 17, {},
                 {"network_sha256": "a" * 64,
                  "topology_sha256": file_hash("contracts/topology/four_intersection_rl_v1.json"),
                  "implementation_sha256": "c" * 64},
                 {"joint_decisions": 0, "episodes": 0, "elapsed_s": 0.})
    state = telemetry_snapshot(topology)

    def run(order):
        controller = GraphMAPPOController(str(artifact_path))
        result = {}
        for node_id in order:
            command = controller.compute_command(node_id, state[node_id], topology, state, 0.)
            result[node_id] = command["target_phase_id"]
        controller.reset()
        assert not controller._state
        return result

    forward = run(GRAPH_MAPPO_NODE_ORDER)
    reverse = run(tuple(reversed(GRAPH_MAPPO_NODE_ORDER)))
    assert forward == reverse
    assert all(phase.endswith("PHASE_NS") or "PHASE_NS" in phase for phase in forward.values())
    controller = GraphMAPPOController(str(artifact_path))
    with pytest.raises(ValueError, match="complete four-intersection"):
        controller.compute_command("J1", state["J1"], {**topology}, {"J1": state["J1"]}, 0.)

    artifact = json.loads(artifact_path.read_text())
    artifact["weights"]["head"]["bias"][0] += 1.
    artifact_path.write_text(json.dumps(artifact))
    with pytest.raises(ValueError, match="provenance hash"):
        GraphMAPPOController(str(artifact_path))


def test_fair_cycle_features_reject_missing_required_wait_measurement():
    from src.control.research import extract_fair_cycle_features

    topology = load_topology(TOPOLOGY_ID)
    state = telemetry_snapshot(topology)
    del state["J1"]["approaches"][0]["stopped_wait_sum_s"]
    with pytest.raises(KeyError):
        extract_fair_cycle_features(topology["nodes"][0], state["J1"], state,
                                    (40, 40), (40, 40))


def test_zero_residual_actor_matches_the_fair_cycle_allocation_and_clearance_totals(tmp_path):
    torch = pytest.importorskip("torch")
    from src.control.fair_cycle import FairCycleController
    from src.control.graph_mappo import GraphMAPPOController
    from src.rl.graph_mappo import GraphActor
    from src.rl.train_mappo import export_actor
    from src.simulation.runtime import file_hash, reconcile_signal_seconds

    topology = load_topology(TOPOLOGY_ID)
    graph = build_research_graph(topology)
    actor = GraphActor(graph, device="cpu")
    with torch.no_grad():
        for parameter in actor.parameters():
            parameter.zero_()
        actor.head.bias.copy_(torch.tensor([0., 1., 0.]))
    path = tmp_path / "zero-residual.json"
    export_actor(path, actor, "graph_attention", 17, {},
                 {"network_sha256": "a" * 64,
                  "topology_sha256": file_hash("contracts/topology/four_intersection_rl_v1.json"),
                  "implementation_sha256": "c" * 64},
                 {"joint_decisions": 1, "episodes": 1, "elapsed_s": 1.})
    snapshot = telemetry_snapshot(topology)
    graph_policy = GraphMAPPOController(str(path))
    fair_cycle = FairCycleController(90, .25)
    for node_id in GRAPH_MAPPO_NODE_ORDER:
        graph_policy.compute_command(node_id, snapshot[node_id], topology, snapshot, 0.)
        fair_cycle.compute_command(node_id, snapshot[node_id], topology, snapshot, 0.)
        assert graph_policy.current_split(node_id) == fair_cycle.current_split(node_id)

    green = {node_id: {"NS": 70} for node_id in GRAPH_MAPPO_NODE_ORDER}
    clearance = {node_id: 20 for node_id in GRAPH_MAPPO_NODE_ORDER}
    total, by_node = reconcile_signal_seconds(green, clearance, 90, GRAPH_MAPPO_NODE_ORDER)
    assert total == 80  # 20 seconds at each of four signals, in node-seconds.
    assert set(by_node.values()) == {20}
    with pytest.raises(RuntimeError, match="does not reconcile"):
        reconcile_signal_seconds(green, clearance, 91, GRAPH_MAPPO_NODE_ORDER)


def test_new_promotion_and_graph_contribution_gates_use_paired_holdout_blocks():
    from src.rl.benchmark import (graph_communication_comparison,
                                  graph_mappo_promotion_gate)

    def rows(delay, controller_timing=None, completed=100., wait=10.):
        return [{"scenario": scenario, "seed": seed,
                 "demand_sha256": f"{scenario}-{seed}", "network_sha256": "network",
                 "topology_sha256": "topology", "scheduled": 100,
                 "demand_s": 1800, "drain_s": 600, "valid": True,
                 "collisions": 0, "teleports": 0, "accounting_losses": 0,
                 "delay_per_scheduled_s": delay, "completed": completed,
                 "p95_wait_s": wait, "worst_approach_wait_s": wait,
                 "max_approach_p95_wait_s": wait,
                 "controller_timing": controller_timing}
                for scenario in RESEARCH_SCENARIOS
                for seed in GRAPH_MAPPO_SEED_SPLITS["holdout"]]

    timing = {"cycle_time_s": 90, "min_green_share": .25}
    candidate = rows(90., timing)
    references = {name: rows(100., timing if name == "fair_cycle" else None)
                  for name in ("fair_cycle", "edgeflow", "max_pressure", "actuated", "fixed_time")}
    assert graph_mappo_promotion_gate(candidate, references)["promoted"]
    references["fair_cycle"] = rows(90.5, timing)
    assert not graph_mappo_promotion_gate(candidate, references)["promoted"]

    graph_models, local_models = {}, {}
    for learner_seed in (17, 29, 43):
        graph_models[learner_seed] = rows(98.)
        local_models[learner_seed] = rows(100.)
    comparison = graph_communication_comparison(graph_models, local_models)
    assert comparison["graph_value_claim_supported"]
    graph_models[17] = rows(98., completed=90., wait=20.)
    assert not graph_communication_comparison(graph_models, local_models)["graph_value_claim_supported"]


def test_validation_selection_uses_overall_fair_cycle_target_and_requires_complete_pairs():
    from src.rl.train_mappo import validation_violation

    timing = {"cycle_time_s": 90, "min_green_share": .25}

    def rows(delay):
        return [{"scenario": scenario, "seed": seed, "valid": True,
                 "collisions": 0, "teleports": 0, "accounting_losses": 0,
                 "delay_per_scheduled_s": delay, "completed": 100.,
                 "p95_wait_s": 10., "worst_approach_wait_s": 10.,
                 "max_approach_p95_wait_s": 10., "demand_sha256": f"{scenario}-{seed}",
                 "network_sha256": "network", "topology_sha256": "topology",
                 "timing": {"step_s": 1}, "scheduled": 100, "demand_s": 1800,
                 "drain_s": 600, "controller_timing": timing}
                for scenario in RESEARCH_SCENARIOS
                for seed in GRAPH_MAPPO_SEED_SPLITS["validation"]]

    violation, metrics = validation_violation(rows(99.), rows(100.))
    assert violation == 0.
    assert set(metrics) == set(RESEARCH_SCENARIOS)
    with pytest.raises(ValueError, match="every unique scenario/seed pair"):
        validation_violation(rows(99.)[:-1], rows(100.))
    duplicated = rows(99.)
    duplicated[-1] = duplicated[0]
    with pytest.raises(ValueError, match="every unique scenario/seed pair"):
        validation_violation(duplicated, rows(100.))


def test_holdout_resumes_atomic_case_ledger_with_two_workers(tmp_path, monkeypatch):
    from src.rl import mappo_campaign
    from src.simulation.runtime import file_hash

    topology = Path("contracts/topology/four_intersection_rl_v1.json").resolve()
    network = Path("networks/four_intersection_rl_v1/network.net.xml").resolve()
    sumo = tmp_path / "sumo.exe"
    sumo.write_text("sumo fixture")
    baseline_specs = {name: {"type": name} for name in mappo_campaign.BASELINES}
    dqn = tmp_path / "fair-cycle-dqn.json"
    dqn.write_text("frozen baseline")
    baseline_specs["fair_cycle_dqn"] = {"type": "fair_cycle_rl", "model_path": str(dqn)}
    for name, spec in baseline_specs.items():
        spec.setdefault("type", name)
    environment = {"topology_path": str(topology), "network_path": str(network),
                   "demand_s": 1800, "drain_s": 600, "cycle_time_s": 90,
                   "min_green_share": .25}
    frozen_baselines = {"baseline_specs": baseline_specs,
                        "baseline_sha256": mappo_campaign._baseline_identity(baseline_specs),
                        "environment": {key: environment[key] for key in
                                        ("topology_path", "network_path", "demand_s", "drain_s")},
                        "topology_sha256": file_hash(topology),
                        "network_sha256": file_hash(network),
                        "sumo_executable": str(sumo.resolve()), "sumo_sha256": file_hash(sumo)}
    actors = {}
    for architecture in ("graph_mappo", "local_mappo"):
        for seed in mappo_campaign.LEARNER_SEEDS:
            name = f"{architecture}_seed{seed}"
            actor = tmp_path / f"{name}.json"
            actor.write_text(name)
            actors[name] = {"type": architecture, "model_path": str(actor.resolve()),
                            "sha256": file_hash(actor), "episodes": 16,
                            "gate_violation": 0., "score": 90.}
    latest = {name: {"model_path": spec["model_path"], "sha256": spec["sha256"],
                     "episodes": 32, "gate_violation": 0., "score": 90.,
                     "scenario_metrics": {"balanced": {"p95_wait_s": 10.,
                                                            "delay_per_scheduled_s": 80.}}}
              for name, spec in actors.items()}
    frozen = {"selection_split": "validation", "protocol": mappo_campaign.GRAPH_MAPPO_PROTOCOL,
              "selected_models": actors, "latest_common_models": latest,
              "baseline_specs": baseline_specs,
              "baseline_sha256": frozen_baselines["baseline_sha256"],
              "frozen_environment": {"environment": frozen_baselines["environment"],
                                     "topology_sha256": frozen_baselines["topology_sha256"],
                                     "network_sha256": frozen_baselines["network_sha256"],
                                     "sumo_executable": frozen_baselines["sumo_executable"],
                                     "sumo_sha256": frozen_baselines["sumo_sha256"]}}
    frozen_path = tmp_path / "frozen.json"
    frozen_path.write_text(json.dumps(frozen))
    config = {"environment": environment, "baselines": baseline_specs,
              "evaluation": {"case_timeout_s": 20}}
    lock = threading.Lock()
    active = maximum = 0

    def fake_case(unused_config, controller, scenario, seed, unused_root,
                  timeout_s=180., deadline=None):
        nonlocal active, maximum
        with lock:
            active += 1
            maximum = max(maximum, active)
        time.sleep(.01)
        with lock:
            active -= 1
        identity = {key: controller[key] for key in ("type", "parameters", "model_path")
                    if key in controller}
        row = {"controller": identity, "scenario": scenario, "seed": seed,
                "demand_sha256": f"{scenario}-{seed}", "network_sha256": "network",
                "topology_sha256": "topology", "scheduled": 100, "demand_s": 1800,
                "drain_s": 600, "valid": True, "collisions": 0, "teleports": 0,
                "accounting_losses": 0, "delay_per_scheduled_s": 80.,
                "completed": 100., "p95_wait_s": 10., "worst_approach_wait_s": 10.,
                "max_approach_p95_wait_s": 10.,
                "controller_timing": {"cycle_time_s": 90, "min_green_share": .25}}
        if controller.get("model_path"):
            row["model_sha256"] = file_hash(controller["model_path"])
        return row

    monkeypatch.setattr(mappo_campaign, "_run_case_cached", fake_case)
    output = tmp_path / "holdout"
    first = mappo_campaign.run_holdout(config, frozen_path, output, max_seconds=.08)
    assert first["status"] == "incomplete"
    assert 0 < first["completed_cases"] < first["requested_cases"]
    second = mappo_campaign.run_holdout(config, frozen_path, output,
                                        max_seconds=20., resume=True)
    assert second["status"] == "complete"
    assert second["completed_cases"] == 390
    assert maximum == 2
    assert json.loads((output / "results.json").read_text())


def test_freeze_selects_only_checkpoint_counts_validated_by_both_architectures(tmp_path):
    from src.rl.mappo_campaign import freeze_training_selections
    from src.simulation.runtime import file_hash

    graph_root, local_root = tmp_path / "graph", tmp_path / "local"
    for algorithm, root in (("graph_mappo", graph_root), ("local_mappo", local_root)):
        for learner_seed in (17, 29, 43):
            folder = root / f"seed-{learner_seed}"
            folder.mkdir(parents=True)
            counts = ([16, 32] if algorithm == "graph_mappo"
                      else ([16] if learner_seed == 29 else [16, 32]))
            validation = []
            for episode_count in counts:
                model = folder / f"policy-{episode_count}.json"
                model.write_text(f"{algorithm}-{learner_seed}-{episode_count}")
                validation.append({"episodes": episode_count, "model_path": str(model),
                                   "sha256": file_hash(model), "gate_violation": 0.1 if episode_count == 16 else 0.,
                                   "score": float(episode_count), "scenario_metrics": {
                                       "balanced": {"p95_wait_s": 10.}},
                                   "selection_rule_version": GRAPH_MAPPO_SELECTION_SPEC["version"]})
            (folder / "training.json").write_text(json.dumps({"algorithm": algorithm,
                                                                "selection_rule_version": GRAPH_MAPPO_SELECTION_SPEC["version"],
                                                                "validation": validation}))
    frozen = freeze_training_selections(graph_root, local_root, tmp_path / "frozen")
    assert frozen["common_validated_episode_counts_by_seed"] == {
        "17": [16, 32], "29": [16], "43": [16, 32]}
    assert frozen["latest_common_episode_count_by_seed"] == {"17": 32, "29": 16, "43": 32}
    assert len(frozen["selected_models"]) == 6
    assert all(Path(row["model_path"]).is_file()
               for row in frozen["latest_common_models"].values())
    assert all(frozen["selected_models"][f"{architecture}_seed{seed}"]["episodes"] ==
               (16 if seed == 29 else 32)
               for architecture in ("graph_mappo", "local_mappo") for seed in (17, 29, 43))


def test_freeze_baseline_inputs_copies_models_and_pins_sumo(tmp_path, monkeypatch):
    from src.rl import mappo_campaign
    from src.simulation import build_network
    from src.simulation.runtime import file_hash

    sumo = tmp_path / "sumo.exe"
    sumo.write_text("frozen SUMO")
    source_model = tmp_path / "baseline.json"
    source_model.write_text("baseline weights")
    baseline_specs = {name: {"type": name} for name in mappo_campaign.BASELINES}
    baseline_specs["fair_cycle_dqn"] = {"type": "fair_cycle_rl", "model_path": str(source_model)}
    config = {"environment": {"topology_path": "contracts/topology/four_intersection_rl_v1.json",
                              "network_path": "networks/four_intersection_rl_v1/network.net.xml",
                              "demand_s": 1800, "drain_s": 600,
                              "cycle_time_s": 90, "min_green_share": .25,
                              "wait_penalty_lambda": 0.},
              "baselines": baseline_specs}
    monkeypatch.setattr(build_network, "binary", lambda name: str(sumo))
    frozen = mappo_campaign.freeze_baseline_inputs(config, tmp_path / "baseline-snapshot")
    frozen_model = Path(frozen["baseline_specs"]["fair_cycle_dqn"]["model_path"])
    assert frozen_model != source_model
    assert file_hash(frozen_model) == file_hash(source_model)
    assert frozen["sumo_sha256"] == file_hash(sumo)
    source_model.write_text("changed source")
    assert file_hash(frozen_model) != file_hash(source_model)


def test_individual_holdout_evaluation_accepts_only_a_frozen_actor(tmp_path):
    from src.rl.evaluate_mappo import is_frozen_model
    from src.simulation.runtime import file_hash

    model = tmp_path / "graph.json"
    model.write_text("frozen actor")
    frozen = {"selected_models": {"graph_mappo_seed17": {
        "type": "graph_mappo", "sha256": file_hash(model)}}}
    assert is_frozen_model(frozen, model, {"algorithm": "graph_mappo"})
    assert not is_frozen_model(frozen, model, {"algorithm": "local_mappo"})
    model.write_text("changed actor")
    assert not is_frozen_model(frozen, model, {"algorithm": "graph_mappo"})


def test_mappo_checkpoint_restores_network_optimizers_and_rng(tmp_path):
    torch = pytest.importorskip("torch")
    from src.rl.graph_mappo import (CentralizedCritic, GraphActor, MAPPOUpdater,
                                    masked_distribution, seed_everything)
    from src.rl.train_mappo import load_training_checkpoint, save_training_checkpoint

    topology = load_topology(TOPOLOGY_ID)
    graph = build_research_graph(topology)
    config = {"training": "checkpoint-fixture"}
    provenance = {"network_sha256": "net", "topology_sha256": "topo"}
    seed_everything(43)
    actor_a, critic_a = GraphActor(graph), CentralizedCritic()
    updater_a = MAPPOUpdater(actor_a, critic_a, {"minibatch_size": 4, "update_epochs": 1,
                                                "value_normalization": True})
    observations = np.random.default_rng(43).normal(size=(4, 4, 52)).astype(np.float32)
    masks = np.ones((4, 4, 3), dtype=bool)
    with torch.no_grad():
        logits = actor_a(torch.as_tensor(observations))
        distribution = masked_distribution(logits, masks)
        actions = distribution.sample()
        old_log_prob = distribution.log_prob(actions).numpy()
    advantages = np.ones((4, 4), dtype=np.float32)
    returns = np.zeros((4, 4), dtype=np.float32)
    batch = (observations, actions.numpy(), masks, old_log_prob, advantages, returns)
    updater_a.update(*batch)
    checkpoint = tmp_path / "checkpoint.pt"
    save_training_checkpoint(checkpoint, config, 43, provenance, actor_a, critic_a, updater_a,
                             {"episodes": 8, "validation": []})
    expected_diagnostics = updater_a.update(*batch)
    expected_random = (random.random(), np.random.random(), torch.rand(1))
    expected_actor = [parameter.detach().clone() for parameter in actor_a.parameters()]
    expected_critic = [parameter.detach().clone() for parameter in critic_a.parameters()]

    actor_b, critic_b = GraphActor(graph), CentralizedCritic()
    updater_b = MAPPOUpdater(actor_b, critic_b, {"minibatch_size": 4, "update_epochs": 1,
                                                "value_normalization": True})
    progress = load_training_checkpoint(checkpoint, config, 43, provenance,
                                        actor_b, critic_b, updater_b, torch.device("cpu"))
    assert progress == {"episodes": 8, "validation": []}
    assert updater_b.update(*batch) == expected_diagnostics
    assert random.random() == expected_random[0]
    assert np.random.random() == expected_random[1]
    assert torch.equal(torch.rand(1), expected_random[2])
    assert all(torch.equal(left, right) for left, right in zip(actor_b.parameters(), expected_actor))
    assert all(torch.equal(left, right) for left, right in zip(critic_b.parameters(), expected_critic))
    assert updater_a.value_normalizer.count.item() == updater_b.value_normalizer.count.item()

    legacy = torch.load(checkpoint, weights_only=False)
    legacy["version"] = 1
    legacy.pop("value_normalizer")
    legacy_path = tmp_path / "legacy-checkpoint.pt"
    torch.save(legacy, legacy_path)
    actor_c, critic_c = GraphActor(graph), CentralizedCritic()
    updater_c = MAPPOUpdater(actor_c, critic_c, {"minibatch_size": 4, "update_epochs": 1})
    with pytest.raises(ValueError, match="Version 1 checkpoint"):
        load_training_checkpoint(legacy_path, config, 43, provenance,
                                 actor_c, critic_c, MAPPOUpdater(actor_c, critic_c,
                                                               {"value_normalization": True}),
                                 torch.device("cpu"))
    load_training_checkpoint(legacy_path, config, 43, provenance,
                             actor_c, critic_c, updater_c, torch.device("cpu"))
