"""Unified MAPPO (graph_mappo_unified / local_mappo_unified) for the shared train_run driver.

On-policy: `episodes_per_update` complete episodes per update. Each transition is one node's own cycle (asynchronous cycles),
the critic is centralized over the whole graph snapshot (training only), and GAE runs per node chain with
gamma_5 ** (dt / 5) and gae_lambda ** (dt / 5) for a cycle of dt simulated seconds. Rewards are per node
(node_wait_v1): waiting cost on the node's own approaches plus the downstream approaches its movements feed.
"""
import math
import copy
import json
import shutil
import uuid
from types import SimpleNamespace

import numpy as np
import torch
from torch import nn
from torch.nn import functional as F

from contracts.benchmark import (CYCLE_DQN as D, CYCLE_RULE, MAPPO_RECIPE, OBSERVATION_SPEC as OBS, SEEDS, TIMING,
                                 UNIFIED_DQN as U, UNIFIED_MAPPO as M)
from src.benchmark.evidence import file_hash, write_json
from src.control.cycle_dqn import GRID, NOOP, FairCycleNativeController, candidate_mask
from src.control.mappo_unified import HEADS, HIDDEN, NODE_DIM, REL_DIM, Graph, actor_logits, snapshot_features
from src.control.observation import flow_index
from src.rl.cycle_family import pad_greens
from src.rl.dqn_common import invalid_episode
from src.rl.graph_mappo import masked_distribution
from src.simulation.runtime import InvalidRun, SumoRuntime

HEAD_DIM = HIDDEN // HEADS


class GraphTensors:
    def __init__(self, graph, device):
        as_long = lambda a: torch.as_tensor(a, dtype=torch.long, device=device)  # noqa: E731
        self.senders, self.receivers, self.incoming = as_long(graph.senders), as_long(graph.receivers), as_long(graph.incoming)
        self.relation = torch.as_tensor(graph.relation, device=device)
        self.mask = torch.as_tensor(graph.incoming_mask, device=device)


class Attention(nn.Module):
    def __init__(self):
        super().__init__()
        self.node, self.relation = nn.Linear(HIDDEN, HIDDEN), nn.Linear(REL_DIM, HIDDEN)
        self.attention_receiver, self.attention_sender, self.attention_relation = (
            nn.Parameter(torch.empty(HEADS, HEAD_DIM)) for _ in range(3))
        for value in (self.attention_receiver, self.attention_sender, self.attention_relation):
            nn.init.xavier_uniform_(value)

    def forward(self, hidden, g):
        batch, nodes, _ = hidden.shape
        projected = self.node(hidden).reshape(batch, nodes, HEADS, HEAD_DIM)
        relation = self.relation(g.relation).reshape(-1, HEADS, HEAD_DIM)
        scores = ((projected[:, g.receivers] * self.attention_receiver).sum(-1)
                  + (projected[:, g.senders] * self.attention_sender).sum(-1)
                  + (relation * self.attention_relation).sum(-1))
        scores = F.leaky_relu(scores, 0.2)
        messages = projected[:, g.senders] + relation
        grouped = scores[:, g.incoming].masked_fill(~g.mask[None, :, :, None], -torch.inf)
        attention = torch.softmax(grouped, dim=2)
        aggregated = (attention.unsqueeze(-1) * messages[:, g.incoming]).sum(2)
        return torch.relu(hidden + aggregated.reshape(batch, nodes, HIDDEN))


class Actor(nn.Module):
    def __init__(self):
        super().__init__()
        self.encoder = nn.Linear(NODE_DIM, HIDDEN)
        self.attention = nn.ModuleList([Attention() for _ in range(M["layers"])])
        self.head = nn.Linear(HIDDEN, GRID)
        with torch.no_grad():  # P(no-op) starts at noop_prior on every node (see with_noop_prior)
            self.head.bias[NOOP] = math.log(M["noop_prior"] / (1 - M["noop_prior"]))

    def forward(self, x, g):
        hidden = torch.relu(self.encoder(x))
        for layer in self.attention:
            hidden = layer(hidden, g)
        return self.head(hidden)


class Critic(nn.Module):
    """Centralized value per node from its own encoding and the graph mean (training only)."""

    def __init__(self):
        super().__init__()
        self.encoder = nn.Linear(NODE_DIM, HIDDEN)
        self.value = nn.Sequential(nn.Linear(2 * HIDDEN, HIDDEN), nn.ReLU(), nn.Linear(HIDDEN, 1))

    def forward(self, x):
        encoded = torch.relu(self.encoder(x))
        mean = encoded.mean(dim=1, keepdim=True).expand_as(encoded)
        return self.value(torch.cat((encoded, mean), dim=-1)).squeeze(-1)


class MappoNet(nn.Module):
    """Actor + critic + Welford value statistics (buffers, so checkpoints carry them)."""

    def __init__(self):
        super().__init__()
        self.actor, self.critic = Actor(), Critic()
        for name in ("vn_mean", "vn_m2", "vn_count"):
            self.register_buffer(name, torch.zeros((), dtype=torch.float64))

    def scale(self):
        return torch.sqrt(self.vn_m2 / self.vn_count.clamp_min(1.)).clamp_min(1e-5)

    def normalize(self, values):
        return (values - self.vn_mean.to(values.dtype)) / self.scale().to(values.dtype)

    def denormalize(self, values):
        return values * self.scale().to(values.dtype) + self.vn_mean.to(values.dtype)

    @torch.no_grad()
    def update_statistics(self, values):
        values = values.to(torch.float64).reshape(-1)
        count = torch.tensor(float(values.numel()), dtype=torch.float64, device=values.device)
        mean, m2 = values.mean(), ((values - values.mean()) ** 2).sum()
        delta, total = mean - self.vn_mean, self.vn_count + count
        self.vn_mean += delta * count / total
        self.vn_m2 += m2 + delta.square() * self.vn_count * count / total
        self.vn_count.copy_(total)


class NullReplay:
    """MAPPO keeps no replay; checkpoints land on validation boundaries, where its rollout buffer is empty."""

    size = 0

    def __init__(self, _capacity=None):
        pass

    def state(self):
        return {}

    def load(self, _state):
        pass


def policy(logits, legal):
    """Masked categorical with the no-op prior offset (same as deployment's with_noop_prior)."""
    offset = torch.log(legal[..., :NOOP].sum(-1).clamp_min(1).to(logits.dtype))
    return masked_distribution(torch.cat((logits[..., :NOOP], logits[..., NOOP:] + offset[..., None]), -1), legal)


def reward_scopes(nodes):
    """node -> approaches whose waiting cost is its reward: its own plus the downstream approaches it feeds."""
    return {n["node_id"]: sorted(set(n["approaches"]) | {m["to_approach"] for p in n["phases"] for m in p["movements"]
                                                         if m.get("to_node") and m.get("to_approach")})
            for n in nodes}


def build_net(_architecture=None):
    return MappoNet()


def chain_gae(rewards, values, next_values, terminals, dt, gamma_5=0.99, gae_lambda=0.95, reference_s=5.0):
    """Advantages and returns along one node's cycle chain; discount and trace scale with elapsed seconds."""
    rewards, values, next_values = (np.asarray(a, np.float64) for a in (rewards, values, next_values))
    terminals, dt = np.asarray(terminals, bool), np.asarray(dt, np.float64)
    if not (len(rewards) == len(values) == len(next_values) == len(terminals) == len(dt)):
        raise ValueError("GAE chain arrays must have equal length")
    if (dt <= 0).any() or not all(np.isfinite(a).all() for a in (rewards, values, next_values, dt)):
        raise ValueError("GAE inputs must be finite with positive elapsed times")
    advantages, carry = np.zeros(len(rewards)), 0.0
    for k in range(len(rewards) - 1, -1, -1):
        gamma, trace = gamma_5 ** (dt[k] / reference_s), gae_lambda ** (dt[k] / reference_s)
        live = 0.0 if terminals[k] else 1.0
        carry = rewards[k] + gamma * live * next_values[k] - values[k] + gamma * trace * live * carry
        advantages[k] = carry
    return advantages, advantages + values


def ppo_update(ctx, batch):
    r, net, dev = ctx.recipe, ctx.net, ctx.device
    x, node = ctx.tensor(batch["x"]), ctx.tensor(batch["node"], torch.long)
    slot, old_logp = ctx.tensor(batch["slot"], torch.long), ctx.tensor(batch["logp"])
    legal, adv, ret = ctx.tensor(batch["mask"], torch.bool), ctx.tensor(batch["adv"]), ctx.tensor(batch["ret"])
    if not legal.gather(1, slot[:, None]).all():
        raise ValueError("Rollout contains an action that was illegal under its mask")
    if r["advantage_normalization"] and len(adv) > 1:
        adv = (adv - adv.mean()) / (adv.std() + 1e-8)
    if r["value_normalization"]:
        net.update_statistics(ret)
        target = net.normalize(ret.to(torch.float64)).float()
    else:
        target = ret
    stopped, stats = False, dict(actor_steps=0, critic_steps=0, kl=0.0, entropy=0.0, clip_fraction=0.0)
    for _ in range(r["update_epochs"]):
        for idx in torch.randperm(len(x), device=dev).chunk(r["num_minibatches"]):
            rows = torch.arange(len(idx), device=dev)
            ctx.optimizer.zero_grad(set_to_none=True)
            if not stopped:
                distribution = policy(net.actor(x[idx], ctx.graph)[rows, node[idx]], legal[idx])
                log_ratio = distribution.log_prob(slot[idx]) - old_logp[idx]
                ratio = log_ratio.exp()
                kl = ((ratio - 1.0) - log_ratio).mean()
                if float(kl.detach()) > r["target_kl"]:
                    stopped = True
                else:
                    clipped = ratio.clamp(1 - r["clip_epsilon"], 1 + r["clip_epsilon"])
                    entropy = distribution.entropy().mean()
                    loss = -torch.minimum(ratio * adv[idx], clipped * adv[idx]).mean() - r["entropy_coefficient"] * entropy
                    if not torch.isfinite(loss):
                        raise RuntimeError("Nonfinite MAPPO actor loss")
                    loss.backward()
                    nn.utils.clip_grad_norm_(net.actor.parameters(), r["max_gradient_norm"])
                    stats["actor_steps"] += 1
                    stats.update(kl=float(kl.detach()), entropy=float(entropy.detach()),
                                 clip_fraction=float(((ratio.detach() - 1).abs() > r["clip_epsilon"]).float().mean()))
            value_loss = F.huber_loss(net.critic(x[idx])[rows, node[idx]], target[idx])
            if not torch.isfinite(value_loss):
                raise RuntimeError("Nonfinite MAPPO critic loss")
            (r["value_coefficient"] * value_loss).backward()
            nn.utils.clip_grad_norm_(net.critic.parameters(), r["max_gradient_norm"])
            ctx.optimizer.step()
            stats["critic_steps"] += 1
    ctx.counters["updates"] += 1
    ctx.counters["mappo_last_update"] = dict(stats, actor_stopped_early=stopped)


def episode(ctx):
    r, c = ctx.recipe, ctx.counters
    if not hasattr(ctx, "rollout"):
        topology = json.loads(open(ctx.spec["topology_path"], encoding="utf-8").read())
        graph = Graph(topology, local_only=ctx.algorithm == "local_mappo_unified")
        ctx.graph = GraphTensors(graph, ctx.device)
        ctx.rollout = SimpleNamespace(buffer=[], episodes=0, graph=graph)
    rollout = ctx.rollout
    case = ctx.cases[c["episode"] % len(ctx.cases)]
    runtime = SumoRuntime(ctx.spec["topology_path"], ctx.spec["network_path"], ctx.output / f"episode-{uuid.uuid4().hex}",
                          seed=SEEDS["train"][c["episode"] % len(SEEDS["train"])], scenario=case,
                          demand_s=r["demand_s"], drain_s=r["drain_s"], benchmark_mode=True, trace=False,
                          intensity=ctx.spec.get("intensity_by_case", {}).get(case, 1.0),
                          wait_penalty_lambda=r["wait_penalty_lambda"], check_every=ctx.check_every)
    try:
        nodes, flow = runtime.topology["nodes"], flow_index(runtime.topology)
        index = {n["node_id"]: i for i, n in enumerate(nodes)}
        pending, chains, scopes = {}, {n["node_id"]: [] for n in nodes}, reward_scopes(nodes)

        def close(nid, next_value, terminal):
            p = pending.pop(nid)
            chains[nid].append(dict(p, reward=p["ret"], dt=runtime.time - p["t0"], next_value=next_value, terminal=terminal))
            c["inserts"] += 1

        def selector(node, view, base):
            nid, phases = node["node_id"], len(base)
            x = snapshot_features(nodes, view, controller.plans(), flow, acting=(nid, base))
            mask = candidate_mask(pad_greens(base), phases)
            with torch.no_grad():
                xt = ctx.tensor(x)[None]
                distribution = policy(ctx.net.actor(xt, ctx.graph)[:, index[nid]], ctx.tensor(mask[None], torch.bool))
                slot = distribution.sample()
                value = float(ctx.net.denormalize(ctx.net.critic(xt)[0, index[nid]].double()))
            if nid in pending:
                close(nid, value, False)
            pending[nid] = dict(x=x, node=index[nid], slot=int(slot), logp=float(distribution.log_prob(slot)),
                                value=value, mask=mask, t0=runtime.time, ret=0.0)
            return int(slot)

        controller = FairCycleNativeController(selector=selector)
        phase_ids = {n["node_id"]: [p["phase_id"] for p in n["phases"]] for n in nodes}
        done = False
        while not done:
            commands = controller.compute_commands(runtime.telemetry, runtime.topology, current_time_s=runtime.time)
            before = runtime.time
            try:
                _, _, terminated, truncated = runtime.step(
                    {nid: phase_ids[nid].index(commands[nid]["target_phase_id"]) for nid in phase_ids})
            except InvalidRun as error:
                invalid_episode(ctx, error)
                return False
            scale = 20 * (runtime.time - before)  # the runtime's scalar reward uses 20 * nodes * interval
            for nid, p in pending.items():  # R = sum gamma_5 ** ((t_k - t_start) / 5) * r_k over the node's cycle
                reward = -sum(runtime.approach_cost[a] for a in scopes[nid]) / scale
                p["ret"] += r["gamma_5"] ** ((before - p["t0"]) / r["reference_s"]) * reward
            c["sim_s"] += runtime.time - before
            c["decisions"] += 1
            done = terminated or truncated
        for nid in list(pending):  # the episode ended mid-cycle: terminal transition, no bootstrap
            close(nid, 0.0, True)
        for chain in chains.values():
            if not chain:
                continue
            columns = {k: [t[k] for t in chain] for k in ("reward", "value", "next_value", "terminal", "dt")}
            adv, ret = chain_gae(columns["reward"], columns["value"], columns["next_value"], columns["terminal"],
                                 columns["dt"], r["gamma_5"], r["gae_lambda"], r["reference_s"])
            rollout.buffer += [dict(t, adv=a, ret=g) for t, a, g in zip(chain, adv, ret)]
        rollout.episodes += 1
        c["visits"][case] += 1
        if rollout.episodes >= r["episodes_per_update"]:
            batch = {k: np.stack([t[k] for t in rollout.buffer]) for k in ("x", "node", "slot", "logp", "mask", "adv", "ret")}
            ppo_update(ctx, batch)
            rollout.buffer, rollout.episodes = [], 0
        return True
    finally:
        runtime.close()
        shutil.rmtree(runtime.output, ignore_errors=True)  # per-episode SUMO output is never read again


def actor_weights(actor):
    def linear(layer):
        return dict(weight=layer.weight.detach().cpu().numpy().tolist(), bias=layer.bias.detach().cpu().numpy().tolist())

    return dict(
        encoder=linear(actor.encoder), head=linear(actor.head),
        attention=[dict(node=linear(a.node), relation=linear(a.relation),
                        **{k: getattr(a, k).detach().cpu().numpy().tolist()
                           for k in ("attention_receiver", "attention_sender", "attention_relation")})
                   for a in actor.attention])


def probe_topology():
    """A small chain with real movement links, for the export parity check."""
    nodes = []
    for i in range(5):
        nxt = i + 1 if i < 4 else None
        nodes.append(dict(node_id=f"N{i}", phases=[dict(movements=[dict(to_node=f"N{nxt}" if nxt is not None else None)]),
                                                    dict(movements=[])]))
    return dict(nodes=nodes)


def export(spec, algorithm, net, seed, path):
    weights = actor_weights(net.actor)
    graph = Graph(probe_topology(), local_only=algorithm == "local_mappo_unified")
    x = np.random.default_rng(9182).random((len(graph.node_ids), NODE_DIM), dtype=np.float32)
    probe = copy.deepcopy(net).cpu()  # never move the training network off its device
    with torch.no_grad():
        expected = probe.actor(torch.as_tensor(x)[None], GraphTensors(graph, "cpu"))[0].numpy()
    np.testing.assert_allclose(actor_logits(weights, x, graph), expected, rtol=1e-4, atol=1e-5)
    architecture, reward = U["algorithms"][algorithm]
    artifact = dict(schema=M["schema"], algorithm=algorithm, architecture=architecture, reward_version=reward,
                    observation=OBS, timing=TIMING, cycle_rule=CYCLE_RULE, candidate_extras=D["extras"],
                    node_dim=NODE_DIM, topology_id=spec["id"], weights=weights,
                    provenance=dict(network_sha256=file_hash(spec["network_path"]),
                                    topology_sha256=file_hash(spec["topology_path"]),
                                    learner_seed=seed, final_test_opened=False))
    write_json(path, artifact)
    return artifact


FAMILY = SimpleNamespace(build_net=build_net, new_replay=NullReplay, update=lambda ctx: None, episode=episode,
                         export=export, recipe=MAPPO_RECIPE)
