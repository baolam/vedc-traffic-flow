import json

import jsonschema
import numpy as np
import pytest
import torch

from contracts.benchmark import MAPPO_RECIPE, OBSERVATION_SPEC, UNIFIED_MAPPO
from src.control.cycle_dqn import GRID, candidate_mask
from src.control.factory import create_controller
from src.control.mappo_unified import NODE_DIM, Graph, actor_logits, snapshot_features
from src.control.observation import flow_index
from src.rl import mappo_family as mf
from tests.unit.test_cycle_controller import run_cycles
from tests.unit.test_observation import chain, set_queue, telemetry

N = 5


def torch_logits(net, x, graph):
    with torch.no_grad():
        return net.actor(torch.as_tensor(x)[None], mf.GraphTensors(graph, "cpu"))[0].numpy()


def random_net(seed=0):
    torch.manual_seed(seed)
    net = mf.build_net()
    for p in net.actor.parameters():  # random head so logits differ per node and slot
        torch.nn.init.normal_(p, std=0.3) if p.ndim == 2 and p.shape[0] != p.shape[1] else None
    return net


def test_graph_edges_and_incoming_table():
    graph = Graph(chain(N))
    assert len(graph.senders) == N + 2 * (N - 1)  # self loops + both directions of each link
    local = Graph(chain(N), local_only=True)
    assert (local.senders == local.receivers).all() and len(local.senders) == N
    for g in (graph, local):
        assert g.incoming_mask.any(axis=1).all()  # every node keeps at least its self edge
        for i in range(N):
            assert (g.receivers[g.incoming[i][g.incoming_mask[i]]] == i).all()
    assert graph.relation[:N, 0].all() and not graph.relation[N:, 0].any()


def test_node_features_are_local_and_carry_plans():
    top = chain(N)
    tel = telemetry(top, 4.0)
    flow = flow_index(top)
    base = snapshot_features(top["nodes"], tel, {}, flow)
    assert base.shape == (N, NODE_DIM) and np.isfinite(base).all()
    set_queue(tel, "D", "D_W", 12)  # a neighbour of C changes ...
    moved = snapshot_features(top["nodes"], tel, {}, flow)
    assert np.array_equal(base[2], moved[2]) and not np.array_equal(base[3], moved[3])  # ... C's own features do not
    greens_slice = slice(OBSERVATION_SPEC["max_phases"] * len(OBSERVATION_SPEC["features"]), -2)
    planned = snapshot_features(top["nodes"], tel, {"B": [30, 40]}, flow, acting=("C", [20, 50]))
    assert planned[1, greens_slice][:2].tolist() == [0.5, pytest.approx(40 / 60)] or planned[1, greens_slice][0] == pytest.approx(30 / 60)
    assert planned[2, greens_slice][:2].tolist() == [pytest.approx(20 / 60), pytest.approx(50 / 60)]
    assert (planned[0, greens_slice] == 0).all()  # no plan yet -> zero greens


@pytest.mark.parametrize("local_only", [False, True])
@pytest.mark.parametrize("nodes", [3, 5, 7])
def test_numpy_actor_matches_torch_for_any_graph_size(local_only, nodes):
    net, graph = random_net(1), Graph(chain(nodes), local_only=local_only)
    x = np.random.default_rng(2).random((nodes, NODE_DIM), dtype=np.float32)
    np.testing.assert_allclose(actor_logits(mf.actor_weights(net.actor), x, graph), torch_logits(net, x, graph),
                               rtol=1e-4, atol=1e-5)


def test_two_attention_layers_give_exactly_two_hops_of_communication():
    net, weights = random_net(3), None
    weights = mf.actor_weights(net.actor)
    x = np.random.default_rng(4).random((N, NODE_DIM), dtype=np.float32)
    graph = Graph(chain(N))

    def shift(node):
        y = x.copy()
        y[node] += 1.0
        return actor_logits(weights, y, graph)[0]

    base = actor_logits(weights, x, graph)[0]
    assert not np.allclose(shift(1), base) and not np.allclose(shift(2), base)  # hops 1 and 2 reach node 0
    assert np.allclose(shift(3), base) and np.allclose(shift(4), base)  # hop 3+ cannot
    local = Graph(chain(N), local_only=True)
    base_local = actor_logits(weights, x, local)[0]
    for node in (1, 2, 3, 4):
        y = x.copy()
        y[node] += 1.0
        assert np.allclose(actor_logits(weights, y, local)[0], base_local)  # self-only: no communication


def test_gae_matches_the_definition_and_scales_with_elapsed_time():
    adv, ret = mf.chain_gae([1.0], [0.5], [2.0], [False], [5.0])
    assert adv[0] == pytest.approx(1.0 + 0.99 * 2.0 - 0.5) and ret[0] == pytest.approx(adv[0] + 0.5)
    adv, _ = mf.chain_gae([1.0], [0.5], [2.0], [False], [70.0])
    assert adv[0] == pytest.approx(1.0 + 0.99 ** 14 * 2.0 - 0.5)  # bootstrap discount is physical-time based
    adv, _ = mf.chain_gae([1.0, 2.0], [0.0, 0.0], [0.0, 0.0], [False, True], [5.0, 5.0], 0.5, 0.5)
    assert adv[1] == pytest.approx(2.0) and adv[0] == pytest.approx(1.0 + 0.5 * 0.5 * 2.0)  # carry gamma*lambda
    adv, _ = mf.chain_gae([1.0, 9.0], [0.0, 0.0], [5.0, 5.0], [True, False], [5.0, 5.0])
    assert adv[0] == pytest.approx(1.0)  # a terminal step neither bootstraps nor carries
    with pytest.raises(ValueError):
        mf.chain_gae([1.0], [0.0], [0.0], [False], [0.0])


class Ctx:
    """The pieces of the driver context ppo_update uses."""

    def __init__(self, nodes=N, **recipe):
        self.net = mf.build_net()
        self.recipe = {**MAPPO_RECIPE, "target_kl": 1.0, "num_minibatches": 1, **recipe}
        self.optimizer = torch.optim.Adam(self.net.parameters(), lr=3e-3)
        self.counters, self.device = dict(updates=0), "cpu"
        self.graph = mf.GraphTensors(Graph(chain(nodes)), "cpu")
        self.tensor = lambda a, dtype=torch.float32: torch.as_tensor(a, dtype=dtype)


def synthetic_batch(good=3, size=64, nodes=N, seed=0):
    rng = np.random.default_rng(seed)
    x = rng.random((size, nodes, NODE_DIM), dtype=np.float32)
    mask = candidate_mask(np.tile(np.array([30, 30, 0, 0, 0, 0, 0, 0], np.float32), (size, 1)), np.full(size, 2))
    legal = np.flatnonzero(mask[0])
    slot = rng.choice(legal, size)
    return dict(x=x, node=np.zeros(size, int), slot=slot, logp=np.full(size, -np.log(len(legal)), np.float32),
                mask=mask, adv=np.where(slot == legal[good % len(legal)], 1.0, -1.0), ret=np.full(size, 3.0)), legal[good % len(legal)]


def test_ppo_update_raises_the_probability_of_the_advantaged_action():
    ctx = Ctx(update_epochs=20)
    batch, best = synthetic_batch()
    probe = ctx.tensor(batch["x"])
    legal = ctx.tensor(batch["mask"], torch.bool)

    def probability():
        with torch.no_grad():
            logits = ctx.net.actor(probe, ctx.graph)[:, 0].masked_fill(~legal, -torch.inf)
            return float(torch.softmax(logits, -1)[:, best].mean())

    before = probability()
    mf.ppo_update(ctx, batch)
    assert probability() > before + 0.05
    assert ctx.counters["updates"] == 1 and ctx.counters["mappo_last_update"]["actor_steps"] > 0


def test_critic_learns_returns_and_normalizer_tracks_them():
    ctx = Ctx(update_epochs=40)
    batch, _ = synthetic_batch()
    batch["ret"] = np.full(64, 3.0)
    for _ in range(3):
        mf.ppo_update(ctx, batch)
    assert float(ctx.net.vn_mean) == pytest.approx(3.0) and float(ctx.net.vn_count) == 192
    with torch.no_grad():
        value = ctx.net.denormalize(ctx.net.critic(ctx.tensor(batch["x"]))[:, 0].double())
    assert float(value.mean()) == pytest.approx(3.0, abs=1.0)


def test_kl_limit_stops_the_actor_but_not_the_critic():
    ctx = Ctx(update_epochs=3, target_kl=-1.0)  # any KL exceeds the limit
    batch, _ = synthetic_batch()
    mf.ppo_update(ctx, batch)
    last = ctx.counters["mappo_last_update"]
    assert last["actor_stopped_early"] and last["actor_steps"] == 0 and last["critic_steps"] == 3


def test_illegal_rollout_action_is_rejected():
    ctx = Ctx()
    batch, _ = synthetic_batch()
    batch["slot"][0] = 7 * 8 + 7  # donor == recipient: never legal
    with pytest.raises(ValueError, match="illegal"):
        mf.ppo_update(ctx, batch)


def artifact_for(tmp_path, algorithm, topology_id="toy", seed=0):
    (tmp_path / "n.net").write_text("n")
    (tmp_path / "t.json").write_text("t")
    spec = dict(id=topology_id, network_path=str(tmp_path / "n.net"), topology_path=str(tmp_path / "t.json"))
    torch.manual_seed(seed)
    mf.export(spec, algorithm, mf.build_net(), 17, tmp_path / f"{algorithm}.json")  # parity asserted inside
    return str(tmp_path / f"{algorithm}.json")


@pytest.mark.parametrize("algorithm", ["graph_mappo_unified", "local_mappo_unified"])
@pytest.mark.parametrize("phases", [2, 4, 8])
def test_deployed_controller_keeps_the_cycle_budget(tmp_path, algorithm, phases):
    from src.control.cycle_plan import cycle_length

    controller = create_controller(algorithm, model_path=artifact_for(tmp_path, algorithm))
    greens = [g for _, g, _ in run_cycles(controller, phases)[:phases]]
    assert controller.controller_name == algorithm
    assert sum(greens) + 5 * phases == cycle_length(phases) and all(10 <= g <= 60 for g in greens)


def test_deployed_controller_rejects_bad_models_and_partial_snapshots(tmp_path):
    path = artifact_for(tmp_path, "graph_mappo_unified")
    good = json.loads(open(path).read())
    for key, value in (("cycle_rule", {}), ("node_dim", 3), ("observation", {})):
        bad = tmp_path / f"bad_{key}.json"
        bad.write_text(json.dumps({**good, key: value}))
        with pytest.raises((ValueError, jsonschema.ValidationError)):  # schema or spec check
            create_controller("graph_mappo_unified", model_path=str(bad))
    controller = create_controller("graph_mappo_unified", model_path=path)
    two = chain(2)
    two["topology_id"] = "toy"
    tel = telemetry(two)
    with pytest.raises(ValueError, match="complete network snapshot"):
        controller.compute_command("A", tel["A"], two, {}, 0)  # node B's telemetry is missing
    other = create_controller("graph_mappo_unified", model_path=artifact_for(tmp_path, "local_mappo_unified", "elsewhere"))
    with pytest.raises(ValueError, match="another map"):
        other.compute_command("A", tel["A"], two, tel, 0)
    assert UNIFIED_MAPPO["node_dim"] == NODE_DIM and GRID == 65


def test_minibatching_gives_one_optimizer_step_per_chunk():
    ctx = Ctx(update_epochs=2, num_minibatches=4)
    batch, _ = synthetic_batch(size=64)
    mf.ppo_update(ctx, batch)
    assert ctx.counters["mappo_last_update"]["critic_steps"] == 8


@pytest.mark.parametrize("phases", [2, 4, 8])
def test_fresh_policy_starts_near_the_noop_prior_and_deployment_uses_the_same_offset(phases):
    from src.control.mappo_unified import with_noop_prior

    torch.manual_seed(phases)
    net, graph = mf.build_net(), Graph(chain(N), local_only=False)
    x = np.random.default_rng(phases).random((N, NODE_DIM), dtype=np.float32)
    legal = candidate_mask(np.r_[[30.0] * phases, [0.0] * (8 - phases)], phases)
    logits = torch_logits(net, x, graph)[0]
    p_train = mf.policy(torch.as_tensor(logits), torch.as_tensor(legal)).probs.numpy()
    assert abs(p_train[GRID - 1] - UNIFIED_MAPPO["noop_prior"]) < 0.1  # same prior whatever the phase count
    deployed = np.where(legal, with_noop_prior(logits, legal), -np.inf)
    np.testing.assert_allclose(np.exp(deployed - deployed.max()) / np.exp(deployed - deployed.max()).sum(), p_train,
                               rtol=1e-5, atol=1e-6)


def test_node_reward_scope_is_own_plus_fed_downstream_approaches():
    scopes = mf.reward_scopes(chain(3)["nodes"])
    assert scopes == {"A": ["A_S", "A_W", "B_W"], "B": ["B_S", "B_W", "C_W"], "C": ["C_S", "C_W"]}


def test_episode_output_folder_is_removed_after_the_episode():
    import inspect
    from src.rl import cycle_family, unified_train
    for module in (mf, cycle_family, unified_train):
        assert "shutil.rmtree(runtime.output" in inspect.getsource(module)
