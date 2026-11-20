"""Cycle-residual DQN (fair_cycle_unified): asynchronous per-node cycle transitions.

A node's transition spans one of its own cycles: reward is the physically discounted sum of the network
reward over that cycle, bootstrapped with gamma_5 ** (cycle_seconds / 5). One optimizer step is taken per
n_nodes completed cycle transitions (the joint-decision-equivalent). Rollouts drive the same
FairCycleNativeController selector hook that the deployed controller uses.
"""
import copy
import json
import uuid
from types import SimpleNamespace

import numpy as np
import torch
from torch import nn

from contracts.benchmark import CYCLE_DQN as D, CYCLE_RECIPE, CYCLE_RULE, OBSERVATION_SPEC as OBS, SEEDS, TIMING, UNIFIED_DQN as U
from src.benchmark.evidence import file_hash, write_json
from src.control.cycle_dqn import (CANDIDATE_DIM, GRID, FairCycleNativeController, candidate_features,
                                   candidate_mask)
from src.control.observation import flow_index, observe_node
from src.control.unified_dqn import FEATURES, MAX_PHASES, pad_rows
from src.rl.dqn_common import invalid_episode, optimize_step
from src.rl.policy import NumpyPolicy
from src.simulation.runtime import InvalidRun, SumoRuntime


def build_net(_architecture=None):
    return nn.Sequential(nn.Linear(CANDIDATE_DIM, U["hidden"]), nn.ReLU(), nn.Linear(U["hidden"], 1))


class CycleReplay:
    FIELDS = dict(s_rows=(MAX_PHASES, FEATURES), s2_rows=(MAX_PHASES, FEATURES), s_greens=(MAX_PHASES,),
                  s2_greens=(MAX_PHASES,))

    def __init__(self, capacity):
        self.capacity, self.size, self.ptr = capacity, 0, 0
        self.a = {k: np.zeros((capacity, *shape), np.float32) for k, shape in self.FIELDS.items()}
        self.a.update(s_p=np.zeros(capacity, np.int64), s2_p=np.zeros(capacity, np.int64),
                      action=np.zeros(capacity, np.int64), reward=np.zeros(capacity, np.float32),
                      terminal=np.zeros(capacity, bool), dt=np.zeros(capacity, np.float32))

    def add(self, **row):
        for key, value in row.items():
            self.a[key][self.ptr] = value
        self.ptr = (self.ptr + 1) % self.capacity
        self.size = min(self.size + 1, self.capacity)

    def sample(self, n, rng):
        index = rng.integers(0, self.size, n)
        return {k: v[index] for k, v in self.a.items()}

    def state(self):
        return dict(arrays={k: v[: self.size].copy() for k, v in self.a.items()}, ptr=self.ptr, size=self.size)

    def load(self, state):
        for key, value in state["arrays"].items():
            self.a[key][: len(value)] = value
        self.ptr, self.size = state["ptr"], state["size"]


def pad_greens(greens):
    out = np.zeros(MAX_PHASES, np.float32)
    out[: len(greens)] = greens
    return out


def q_candidates(net, rows, greens, phases, device):
    """Q over the GRID candidate slots for one node state or a batch of them."""
    features = torch.as_tensor(candidate_features(rows, greens, phases), device=device)
    return net(features).squeeze(-1)


def update(ctx):
    r, b = ctx.recipe, ctx.replay.sample(ctx.recipe["batch"], ctx.rng)
    action, terminal = ctx.tensor(b["action"], torch.int64), ctx.tensor(b["terminal"], torch.bool)
    mask2 = ctx.tensor(candidate_mask(b["s2_greens"], b["s2_p"]), torch.bool)
    with torch.no_grad():
        choice = q_candidates(ctx.net, b["s2_rows"], b["s2_greens"], b["s2_p"], ctx.device).masked_fill(
            ~mask2, -torch.inf).argmax(1, keepdim=True)
        future = q_candidates(ctx.target, b["s2_rows"], b["s2_greens"], b["s2_p"], ctx.device).gather(1, choice).squeeze(1)
        gamma = r["gamma_5"] ** (ctx.tensor(b["dt"]) / r["reference_s"])
        expected = ctx.tensor(b["reward"]) + gamma * (~terminal) * future
    q = q_candidates(ctx.net, b["s_rows"], b["s_greens"], b["s_p"], ctx.device).gather(1, action[:, None]).squeeze(1)
    optimize_step(ctx, nn.functional.smooth_l1_loss(q, expected))


def episode(ctx):
    r, c, rng = ctx.recipe, ctx.counters, ctx.rng
    case = ctx.cases[c["episode"] % len(ctx.cases)]
    runtime = SumoRuntime(ctx.spec["topology_path"], ctx.spec["network_path"], ctx.output / f"episode-{uuid.uuid4().hex}",
                          seed=SEEDS["train"][c["episode"] % len(SEEDS["train"])], scenario=case,
                          demand_s=r["demand_s"], drain_s=r["drain_s"], benchmark_mode=True, trace=False,
                          intensity=ctx.spec.get("intensity_by_case", {}).get(case, 1.0),
                          wait_penalty_lambda=r["wait_penalty_lambda"], check_every=ctx.check_every)
    try:
        nodes, flow = runtime.topology["nodes"], flow_index(runtime.topology)
        pending, completed = {}, [0]

        def finish(nid, rows, greens, phases, terminal):
            p = pending.pop(nid)
            ctx.replay.add(s_rows=p["rows"], s_greens=p["greens"], s_p=p["p"], action=p["slot"], reward=p["ret"],
                           terminal=terminal, dt=runtime.time - p["t0"], s2_rows=rows, s2_greens=greens, s2_p=phases)
            c["inserts"] += 1
            completed[0] += 1
            ready = ctx.replay.size >= r["learning_starts"] and min(c["visits"].values()) >= 1
            if ready and completed[0] % len(nodes) == 0:  # one optimizer step per joint-decision-equivalent
                ctx.update()

        def selector(node, view, base):
            nid, phases = node["node_id"], len(base)
            rows, greens = pad_rows(observe_node(node, view, flow)), pad_greens(base)
            if nid in pending:
                finish(nid, rows, greens, phases, False)
            mask = candidate_mask(greens, phases)
            if rng.random() < ctx.epsilon():
                slot = int(rng.choice(np.flatnonzero(mask)))
            else:
                with torch.no_grad():
                    q = q_candidates(ctx.net, rows, greens, phases, ctx.device).cpu().numpy()
                slot = int(np.argmax(np.where(mask, q, -np.inf)))
            pending[nid] = dict(rows=rows, greens=greens, p=phases, slot=slot, t0=runtime.time, ret=0.0)
            return slot

        controller = FairCycleNativeController(selector=selector)
        index = {n["node_id"]: [p["phase_id"] for p in n["phases"]] for n in nodes}
        done = False
        while not done:
            commands = controller.compute_commands(runtime.telemetry, runtime.topology, current_time_s=runtime.time)
            actions = {nid: index[nid].index(commands[nid]["target_phase_id"]) for nid in index}
            before = runtime.time
            try:
                _, reward, terminated, truncated = runtime.step(actions)
            except InvalidRun as error:
                invalid_episode(ctx, error)
                return False
            dt = runtime.time - before
            for p in pending.values():  # R = sum gamma_5 ** ((t_k - t_start) / 5) * r_k over the node's cycle
                p["ret"] += r["gamma_5"] ** ((before - p["t0"]) / r["reference_s"]) * reward
            c["sim_s"] += dt
            c["decisions"] += 1
            done = terminated or truncated
        for nid in list(pending):  # the episode ended mid-cycle: a terminal transition with zero next state
            p = pending[nid]
            finish(nid, np.zeros_like(p["rows"]), np.zeros_like(p["greens"]), p["p"], True)
        c["visits"][case] += 1
        return True
    finally:
        runtime.close()


def export(spec, algorithm, net, seed, path):
    weights = {k: v.detach().cpu().tolist() for k, v in
               (("w1", net[0].weight), ("b1", net[0].bias), ("w2", net[2].weight), ("b2", net[2].bias))}
    probe = np.random.default_rng(9182).random((16, GRID, CANDIDATE_DIM), dtype=np.float32)
    with torch.no_grad():
        expected = copy.deepcopy(net).cpu()(torch.as_tensor(probe)).squeeze(-1).numpy()  # never move the training net
    got = NumpyPolicy(weights).predict(probe.reshape(-1, CANDIDATE_DIM)).reshape(16, GRID)
    np.testing.assert_allclose(got, expected, rtol=1e-4, atol=1e-5)
    architecture, reward = U["algorithms"][algorithm]
    artifact = dict(schema=U["schema"], algorithm=algorithm, architecture=architecture, reward_version=reward,
                    observation=OBS, timing=TIMING, topology_id=spec["id"], weights=weights,
                    cycle_rule=CYCLE_RULE, candidate_extras=D["extras"],
                    provenance=dict(network_sha256=file_hash(spec["network_path"]),
                                    topology_sha256=file_hash(spec["topology_path"]),
                                    learner_seed=seed, final_test_opened=False))
    write_json(path, artifact)
    return artifact


FAMILY = SimpleNamespace(build_net=build_net, new_replay=CycleReplay, update=update, episode=episode,
                         export=export, recipe=CYCLE_RECIPE)
