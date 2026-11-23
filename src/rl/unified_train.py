"""Unified Double-DQN trainer for the unified_dqn_v1 family (one map, one learner seed per run).

Physical-time discounting, validation-selected checkpoints, plateau stopping and resume live here.
Test seeds are never touched: validation uses SEEDS["validation"] only.
"""
import copy
import json
import os
import shutil
import random
import time
import uuid
from pathlib import Path
from types import SimpleNamespace

import numpy as np
import torch
from torch import nn

from contracts.benchmark import DQN_RECIPE, OBSERVATION_SPEC as OBS, SEEDS, TIMING, UNIFIED_DQN as U
from src.benchmark.evidence import digest, file_hash, write_json
from src.control.observation import flow_index, observe_node
from src.control.phase_dqn import phase_mask
from src.control.controllers import MaxPressureController
from src.control.unified_dqn import FEATURES, MAX_PHASES, PHASE_ALGORITHMS, input_dim, output_dim, pad_rows
from src.control.mappo_unified import MAPPO_ALGORITHMS
from src.rl import cycle_family, mappo_family
from src.rl.dqn_common import invalid_episode, optimize_step, tail_penalty
from src.rl.policy import NumpyPolicy
from src.rl.selection import validation_score
from src.rl.stopping import Plateau
from src.simulation.runtime import InvalidRun, SumoRuntime

NODE_REWARD = os.environ.get("EDGEFLOW_DQN_NODE_REWARD") == "1"  # experiment: per-node reward for wait_tail_v1
MP_EXPLORE = float(os.environ.get("EDGEFLOW_MP_EXPLORE", 0))  # experiment: share of exploratory actions from max_pressure


TRAIN_CHECK_EVERY = 25  # schema/readback cadence in training rollouts only; evaluation checks every step


def build_net(architecture):
    return nn.Sequential(nn.Linear(input_dim(architecture), U["hidden"]), nn.ReLU(),
                         nn.Linear(U["hidden"], output_dim(architecture)))


def q_all(architecture, net, rows):
    """Q for every padded phase slot: rows (..., MAX_PHASES, FEATURES) -> (..., MAX_PHASES)."""
    return net(rows).squeeze(-1) if architecture == "scalar_phase_scorer" else net(rows.flatten(-2))


def discount(recipe, dt):
    """Per-transition bootstrap factor for a transition lasting dt simulated seconds."""
    return recipe["gamma_5"] ** (dt / recipe["reference_s"])


def node_pressure_reward(node, telemetry):
    """node_pressure_v1: -|incoming queue - distinct receiving-approach queue| / 20 (hop-1 downstream)."""
    queue = lambda nid, app: next(a["queue_vehicles"] for a in telemetry[nid]["approaches"]  # noqa: E731
                                  if a["approach_id"] == app)
    nid = node["node_id"]
    receiving = {(m["to_node"], m["to_approach"]) for p in node["phases"] for m in p.get("movements", [])
                 if m.get("to_node") is not None}
    pressure = (sum(queue(nid, a) for a in node["approaches"]) - sum(queue(n, a) for n, a in receiving))
    return -abs(pressure) / OBS["normalization"]["queue_vehicles"]


class Replay:
    def __init__(self, capacity):
        self.capacity, self.size, self.ptr = capacity, 0, 0
        shapes = dict(s=(MAX_PHASES, FEATURES), s2=(MAX_PHASES, FEATURES), m2=(MAX_PHASES,))
        self.a = dict(s=np.zeros((capacity, *shapes["s"]), np.float32), s2=np.zeros((capacity, *shapes["s2"]), np.float32),
                      m2=np.zeros((capacity, *shapes["m2"]), bool), action=np.zeros(capacity, np.int64),
                      reward=np.zeros(capacity, np.float32), terminal=np.zeros(capacity, bool),
                      dt=np.zeros(capacity, np.float32))

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


def export_artifact(spec, algorithm, net, seed, path):
    architecture, reward = U["algorithms"][algorithm]
    weights = {k: v.detach().cpu().tolist() for k, v in
               (("w1", net[0].weight), ("b1", net[0].bias), ("w2", net[2].weight), ("b2", net[2].bias))}
    probe = torch.as_tensor(np.random.default_rng(9182).random((16, MAX_PHASES, FEATURES), dtype=np.float32))
    with torch.no_grad():
        expected = q_all(architecture, copy.deepcopy(net).cpu(), probe).numpy()  # never move the training net
    policy = NumpyPolicy(weights)
    got = (policy.predict(probe.numpy().reshape(-1, FEATURES)).reshape(16, MAX_PHASES)
           if architecture == "scalar_phase_scorer" else policy.predict(probe.numpy().reshape(16, -1)))
    np.testing.assert_allclose(got, expected, rtol=1e-4, atol=1e-5)
    artifact = dict(schema=U["schema"], algorithm=algorithm, architecture=architecture, reward_version=reward,
                    observation=OBS, timing=TIMING, topology_id=spec["id"], weights=weights,
                    provenance=dict(network_sha256=file_hash(spec["network_path"]),
                                    topology_sha256=file_hash(spec["topology_path"]),
                                    learner_seed=seed, final_test_opened=False))
    write_json(path, artifact)
    return artifact


def evaluate_candidate(spec, algorithm, seed, path, recipe, root, workers):
    from src.benchmark.scheduling import run_tasks

    # Validation only ranks checkpoints: no signal trace, thinned schema/readback checks (check_every). Final test
    # evaluation keeps the full per-step checks; tests/unit/test_unified_train.py pins metric equivalence.
    protocol = dict(demand_s=recipe["demand_s"], drain_s=recipe["drain_s"], trace=False, benchmark_mode=True,
                    check_every=TRAIN_CHECK_EVERY)
    controller = dict(type=algorithm, model_path=str(path), learner_seed=seed, parameters={})
    tasks = [(dict(map=spec, scenario=c, seed=s, controller=controller), protocol, str(root))
             for c in spec["cases"] for s in SEEDS["validation"]]
    # A collision/teleport (InvalidRun) fails that case only: the candidate scores as incomplete -> infeasible.
    return [r for r in run_tasks(tasks, workers, continue_on_error=True) if r is not None]


def reference_rows(spec, recipe, root, workers):
    from src.benchmark.scheduling import run_tasks

    protocol = dict(demand_s=recipe["demand_s"], drain_s=recipe["drain_s"], trace=True, benchmark_mode=True)
    controller = spec.get("controller_overrides", {}).get("fixed_time", dict(type="fixed_time"))
    return run_tasks([(dict(map=spec, scenario=c, seed=s, controller=controller), protocol, str(root))
                      for c in spec["cases"] for s in SEEDS["validation"]], workers)


def phase_update(ctx):
    r, arch = ctx.recipe, ctx.architecture
    batch = ctx.replay.sample(r["batch"], ctx.rng)
    s, s2, m2 = ctx.tensor(batch["s"]), ctx.tensor(batch["s2"]), ctx.tensor(batch["m2"], torch.bool)
    action = ctx.tensor(batch["action"], torch.int64)
    with torch.no_grad():
        choice = q_all(arch, ctx.net, s2).masked_fill(~m2, -torch.inf).argmax(1, keepdim=True)
        future = q_all(arch, ctx.target, s2).gather(1, choice).squeeze(1)
        gamma = r["gamma_5"] ** (ctx.tensor(batch["dt"]) / r["reference_s"])
        expected = ctx.tensor(batch["reward"]) + gamma * (~ctx.tensor(batch["terminal"], torch.bool)) * future
    optimize_step(ctx, nn.functional.smooth_l1_loss(
        q_all(arch, ctx.net, s).gather(1, action[:, None]).squeeze(1), expected))


def phase_episode(ctx):
    r, c, rng, arch = ctx.recipe, ctx.counters, ctx.rng, ctx.architecture
    case = ctx.cases[c["episode"] % len(ctx.cases)]
    runtime = SumoRuntime(ctx.spec["topology_path"], ctx.spec["network_path"], ctx.output / f"episode-{uuid.uuid4().hex}",
                          seed=SEEDS["train"][c["episode"] % len(SEEDS["train"])], scenario=case,
                          demand_s=r["demand_s"], drain_s=r["drain_s"], benchmark_mode=True,
                          trace=False, intensity=ctx.spec.get("intensity_by_case", {}).get(case, 1.0),
                          check_every=ctx.check_every)
    try:
        nodes = runtime.topology["nodes"]
        flow = flow_index(runtime.topology)
        scopes = mappo_family.reward_scopes(nodes) if NODE_REWARD else None

        def node_reward(nid, dt):  # experiment: MAPPO's node_wait_v1 (own + fed approaches) plus the tail term
            items = {a["approach_id"]: a for t in runtime.telemetry.values() for a in t["approaches"]}
            return (-sum(runtime.approach_cost[a] for a in scopes[nid]) / (20 * dt)
                    - tail_penalty([items[a] for a in scopes[nid]]))

        mp = MaxPressureController() if MP_EXPLORE else None

        def explore(n, m):  # experiment: exploration follows max_pressure's (legal) choice with prob MP_EXPLORE
            if mp is not None and rng.random() < MP_EXPLORE:
                nid = n["node_id"]
                target = mp.compute_command(nid, runtime.telemetry[nid], runtime.topology, runtime.telemetry)["target_phase_id"]
                a = [p["phase_id"] for p in n["phases"]].index(target)
                if m[a]:
                    return a
            return int(rng.choice(np.flatnonzero(m)))

        def observe():  # computed once per step and reused as the next step's state
            return ([pad_rows(observe_node(n, runtime.telemetry, flow)) for n in nodes],
                    [np.pad(phase_mask(n, runtime.telemetry[n["node_id"]]), (0, MAX_PHASES - len(n["phases"])))
                     for n in nodes])

        done = False
        rows, masks = observe()
        while not done:
            with torch.no_grad():
                q = q_all(arch, ctx.net, ctx.tensor(np.stack(rows))).masked_fill(
                    ~ctx.tensor(np.stack(masks), torch.bool), -torch.inf).argmax(1).cpu().numpy()
            eps, draws = ctx.epsilon(), rng.random(len(nodes))
            actions = [explore(nodes[i], m) if draws[i] < eps else int(q[i]) for i, m in enumerate(masks)]
            before = runtime.time
            try:
                _, reward, terminated, truncated = runtime.step({n["node_id"]: actions[i] for i, n in enumerate(nodes)})
            except InvalidRun as error:
                invalid_episode(ctx, error)
                return False
            dt = runtime.time - before
            next_rows, next_masks = observe()
            for i, n in enumerate(nodes):
                ctx.replay.add(s=rows[i], action=actions[i],
                               reward=node_reward(n["node_id"], dt) if NODE_REWARD and ctx.reward_version == "wait_tail_v1"
                               else reward if ctx.reward_version == "wait_tail_v1"
                               else node_pressure_reward(n, runtime.telemetry) - tail_penalty(
                                   [a for a in runtime.telemetry[n["node_id"]]["approaches"]]),
                               s2=next_rows[i], m2=next_masks[i], terminal=terminated, dt=dt)
            rows, masks = next_rows, next_masks
            c["sim_s"] += dt
            c["decisions"] += 1
            c["inserts"] += len(nodes)
            ready = ctx.replay.size >= r["learning_starts"] and min(c["visits"].values()) >= 1
            if ready and c["decisions"] % r["update_every_decisions"] == 0:
                ctx.update()
            done = terminated or truncated
        c["visits"][case] += 1
        return True
    finally:
        runtime.close()
        shutil.rmtree(runtime.output, ignore_errors=True)  # per-episode SUMO output is never read again


PHASE_FAMILY = SimpleNamespace(build_net=build_net, new_replay=Replay, update=phase_update, episode=phase_episode,
                               export=export_artifact, recipe=DQN_RECIPE)


def train_run(spec, algorithm, seed, output, recipe=None, wall_limit_s=None, device="cuda", workers=4,
              cases_root=None, reference=None):
    """Train one learner seed on one map; returns the result summary (also written to result.json)."""
    if algorithm in PHASE_ALGORITHMS:
        family = PHASE_FAMILY
    elif algorithm == "fair_cycle_unified":
        family = cycle_family.FAMILY
    elif algorithm in MAPPO_ALGORITHMS:
        family = mappo_family.FAMILY
    else:
        raise ValueError(f"No trainer for {algorithm}")
    recipe = {**family.recipe, **(recipe or {})}
    architecture, reward_version = U["algorithms"][algorithm]
    if device == "cuda" and not torch.cuda.is_available():
        raise RuntimeError("CUDA training requested but unavailable")
    output = Path(output)
    output.mkdir(parents=True, exist_ok=True)
    random.seed(seed)
    np.random.seed(seed)
    torch.manual_seed(seed)
    rng = np.random.default_rng(seed)
    cases = spec["cases"]
    net, plateau = family.build_net(architecture).to(device), Plateau(recipe["patience"], recipe["rel_improvement"])
    target = copy.deepcopy(net)
    optimizer = torch.optim.Adam(net.parameters(), lr=recipe["lr"])
    replay = family.new_replay(recipe["replay"])
    counters = dict(sim_s=0.0, decisions=0, inserts=0, updates=0, episode=0, wall_s=0.0,
                    visits={c: 0 for c in cases}, invalid_episodes=0)
    history, best = [], None
    identity = digest(dict(algorithm=algorithm, seed=seed, recipe=recipe, cases=cases,
                           network=file_hash(spec["network_path"]), topology=file_hash(spec["topology_path"]),
                           intensity=spec.get("intensity_by_case", {}), device=device))
    checkpoint = output / "checkpoint.pt"
    if checkpoint.exists():
        saved = torch.load(checkpoint, map_location=device, weights_only=False)
        if saved["identity"] != identity:
            raise ValueError("Checkpoint recipe, map or seed changed; choose a new output directory")
        net.load_state_dict(saved["net"])
        target.load_state_dict(saved["target"])
        optimizer.load_state_dict(saved["optimizer"])
        replay.load(saved["replay"])
        counters, history, best = saved["counters"], saved["history"], saved["best"]
        plateau.load(saved["plateau"])
        random.setstate(saved["python_rng"])
        np.random.set_state(saved["numpy_rng"])
        torch.set_rng_state(saved["torch_rng"].cpu())
        rng.bit_generator.state = saved["rng"]
        if (output / "result.json").exists():
            return json.loads((output / "result.json").read_text())
    cases_root = Path(cases_root or output / "validation-cases")
    reference_file = output / "reference.json"
    if reference is not None:  # precomputed once per map by the campaign (safe for concurrent runs)
        write_json(reference_file, reference)
    elif not reference_file.exists():
        write_json(reference_file, reference_rows(spec, recipe, cases_root, workers))
    reference = json.loads(reference_file.read_text())

    def epsilon():
        return max(recipe["epsilon_end"], 1 - (1 - recipe["epsilon_end"]) * counters["sim_s"] / recipe["epsilon_decay_sim_s"])

    def tensor(x, dtype=torch.float32):
        return torch.as_tensor(x, dtype=dtype, device=device)

    ctx = SimpleNamespace(spec=spec, algorithm=algorithm, architecture=architecture, reward_version=reward_version,
                          recipe=recipe, device=device, rng=rng, counters=counters, output=output, cases=cases,
                          net=net, target=target, optimizer=optimizer, replay=replay, epsilon=epsilon, tensor=tensor,
                          check_every=TRAIN_CHECK_EVERY)
    ctx.update = lambda: family.update(ctx)

    def validate():
        candidate = output / "candidates" / f"episode-{counters['episode']:06d}.json"
        family.export(spec, algorithm, net, seed, candidate)
        rows = evaluate_candidate(spec, algorithm, seed, candidate, recipe, cases_root, workers)
        result = validation_score(rows, reference, cases, SEEDS["validation"])
        decision = plateau.update(result["score"], result["feasible"])
        entry = dict(episode=counters["episode"], sim_s=counters["sim_s"], decisions=counters["decisions"],
                     updates=counters["updates"], feasible=result["feasible"],
                     score=result["score"] if np.isfinite(result["score"]) else None,  # inf = invalid/incomplete; JSON-safe
                     reasons=result["reasons"], improved_best=decision["improved_best"], stale=plateau.stale)
        history.append(entry)
        nonlocal best
        if decision["improved_best"]:
            best = dict(episode=counters["episode"], score=result["score"], path=str(candidate), counters=copy.deepcopy(counters))
        else:
            candidate.unlink()
        write_json(output / "history.json", history)
        return decision["stop"]

    def save():
        torch.save(dict(identity=identity, net=net.state_dict(), target=target.state_dict(),
                        optimizer=optimizer.state_dict(), replay=replay.state(), counters=counters, history=history,
                        best=best, plateau=plateau.state(), python_rng=random.getstate(),
                        numpy_rng=np.random.get_state(), torch_rng=torch.get_rng_state(),
                        rng=rng.bit_generator.state), output / "checkpoint.tmp")
        (output / "checkpoint.tmp").replace(checkpoint)

    start, base_wall, stop_reason = time.monotonic(), counters["wall_s"], None
    while stop_reason is None:
        family.episode(ctx)
        counters["episode"] += 1
        counters["wall_s"] = base_wall + time.monotonic() - start
        capped_episodes = bool(recipe.get("cap_episodes")) and counters["episode"] >= recipe["cap_episodes"]
        capped = counters["sim_s"] >= recipe["cap_sim_s"] or capped_episodes
        timed_out = wall_limit_s is not None and counters["wall_s"] >= wall_limit_s
        mature = (counters["sim_s"] >= max(recipe["min_sim_s"], recipe["epsilon_decay_sim_s"])
                  and counters["episode"] >= recipe["min_episodes"]
                  and min(counters["visits"].values()) >= recipe["min_case_visits"])
        # No validation during warmup: its candidates cannot be selected or stop the run; caps still validate once.
        due = counters["episode"] % recipe["validate_every_episodes"] == 0
        if (mature and due) or capped or timed_out:
            plateau_stop = validate()
            if mature and plateau_stop:
                stop_reason = "plateau"
            elif capped:
                stop_reason = "budget_limited_episodes" if capped_episodes else "budget_limited_simulated_seconds"
            elif timed_out:
                stop_reason = "budget_limited_wall_clock"
        if due or capped or timed_out:
            save()  # warmup intervals still checkpoint so a restart does not lose them
    converged = stop_reason == "plateau" and best is not None  # a plateau with no feasible checkpoint is not convergence
    summary = dict(algorithm=algorithm, topology_id=spec["id"], learner_seed=seed, stop_reason=stop_reason,
                   converged=converged, status="selected" if best is not None else "no_feasible_checkpoint",
                   counters=counters, selected=None, recipe=recipe["version"])
    if best is not None:
        artifact = json.loads(Path(best["path"]).read_text())
        artifact["training"] = dict(stop_reason=stop_reason, converged=converged,
                                    selected_episode=best["episode"], validation_score=best["score"],
                                    exposure_at_selection=best["counters"], exposure_total=counters,
                                    recipe=recipe, recipe_version=recipe["version"])
        write_json(output / "policy.json", artifact)
        summary["selected"] = dict(episode=best["episode"], score=best["score"], path=str(output / "policy.json"))
    write_json(output / "result.json", summary)
    return summary
