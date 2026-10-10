"""Train graph_mappo or local_mappo with isolated SUMO workers.

Example: python -m src.rl.train_mappo --config configs/rl/graph_mappo.json --output artifacts/graph_mappo
"""

import argparse
import copy
import hashlib
import json
import multiprocessing as mp
import random
import time
import traceback
from pathlib import Path

import numpy as np
import torch

from contracts.research import (FAIR_CYCLE_FEATURE_SPEC, GRAPH_MAPPO_ACTIONS,
                                GRAPH_MAPPO_FEATURE_SPEC,
                                GRAPH_MAPPO_HORIZON, GRAPH_MAPPO_MODEL_SPEC,
                                GRAPH_MAPPO_NODE_ORDER, GRAPH_MAPPO_PROTOCOL,
                                GRAPH_MAPPO_RELATION_FEATURE_SPEC, GRAPH_MAPPO_SEED_SPLITS,
                                GRAPH_MAPPO_TIMING, RESEARCH_SCENARIOS, TOPOLOGY_ID,
                                build_research_graph)
from src.rl.graph_mappo import (CentralizedCritic, GraphActor, MAPPOUpdater,
                                actor_weights, generalized_advantage_estimate,
                                masked_distribution, seed_everything)
from src.rl.evaluation import evaluate_cases
from src.simulation.runtime import file_hash


def worker(pipe, environment, output):
    from src.rl.sumo_env import FairCycleSumoEnv

    options = dict(environment)
    options.pop("mode", None)
    env = FairCycleSumoEnv(**options, output=output)
    try:
        while True:
            command, payload = pipe.recv()
            if command == "close":
                break
            try:
                result = env.reset(**payload) if command == "reset" else env.step(payload)
                pipe.send((True, result))
            except BaseException:
                pipe.send((False, traceback.format_exc()))
                break
    finally:
        env.close()
        pipe.close()


def receive(pipe):
    if not pipe.poll(180):
        raise RuntimeError("MAPPO SUMO worker timed out")
    ok, result = pipe.recv()
    if not ok:
        raise RuntimeError(f"MAPPO SUMO worker failed:\n{result}")
    return result


def _canonical_hash(value):
    return hashlib.sha256(json.dumps(value, sort_keys=True, separators=(",", ":")).encode()).hexdigest()


def _implementation_hash():
    paths = ("contracts/research.py", "contracts/scenarios.py", "contracts/contracts_sdk.py",
             "contracts/schemas/telemetry.json", "src/control/research.py",
             "src/control/controllers.py", "src/control/actuator.py", "src/control/fair_cycle.py",
             "src/control/graph_mappo.py", "src/control/graph_mappo_numpy.py",
             "src/control/factory.py", "src/rl/sumo_env.py", "src/rl/graph_mappo.py",
             "src/rl/train_mappo.py", "src/simulation/build_network.py", "src/simulation/runtime.py")
    return _canonical_hash({path: file_hash(path) for path in paths})


def export_actor(path, actor, architecture, seed, config, provenance, progress):
    weights = actor_weights(actor)
    artifact = {
        "algorithm": "graph_mappo" if architecture == "graph_attention" else "local_mappo",
        "artifact_version": 2,
        "architecture": architecture,
        "model_spec": GRAPH_MAPPO_MODEL_SPEC,
        "weights": weights,
        "feature_spec": GRAPH_MAPPO_FEATURE_SPEC,
        "relation_feature_spec": GRAPH_MAPPO_RELATION_FEATURE_SPEC,
        "node_order": list(GRAPH_MAPPO_NODE_ORDER),
        "topology_id": TOPOLOGY_ID,
        "timing": GRAPH_MAPPO_TIMING,
        "horizon": GRAPH_MAPPO_HORIZON,
        "training_seeds": [seed],
        "learner_seed": seed,
        "protocol": GRAPH_MAPPO_PROTOCOL,
        "provenance": {**provenance, "actor_sha256": _canonical_hash(weights),
                       "joint_decisions": progress["joint_decisions"],
                       "episodes": progress["episodes"], "elapsed_s": progress["elapsed_s"],
                       "training_config_sha256": _canonical_hash(config)},
    }
    Path(path).write_text(json.dumps(artifact, indent=2, allow_nan=False), encoding="utf-8")
    return artifact


def save_training_checkpoint(path, config, seed, provenance, actor, critic, updater, progress):
    state = {"version": 2, "config": config, "seed": seed, "provenance": provenance,
             "actor": actor.state_dict(), "critic": critic.state_dict(),
             "actor_optimizer": updater.actor_optimizer.state_dict(),
             "critic_optimizer": updater.critic_optimizer.state_dict(), "updates": updater.updates,
             "value_normalizer": (updater.value_normalizer.state_dict()
                                  if updater.value_normalizer else None),
             "progress": progress, "python_rng": random.getstate(),
             "numpy_rng": np.random.get_state(), "torch_rng": torch.get_rng_state(),
             "cuda_rng": torch.cuda.get_rng_state_all() if torch.cuda.is_available() else []}
    path = Path(path)
    temporary = Path(str(path) + ".tmp")
    torch.save(state, temporary)
    temporary.replace(path)


def load_training_checkpoint(path, config, seed, provenance, actor, critic, updater, device):
    state = torch.load(path, map_location=device, weights_only=False)
    version = state.get("version")
    if version not in (1, 2) or state.get("seed") != seed or state.get("config") != config:
        raise ValueError("Resume checkpoint does not match seed, config or version")
    if version == 1 and updater.value_normalizer is not None:
        raise ValueError("Version 1 checkpoint cannot resume with value normalization enabled")
    if version == 2 and ((updater.value_normalizer is None) != (state.get("value_normalizer") is None)):
        raise ValueError("Checkpoint value normalization does not match training configuration")
    if state["provenance"] != provenance:
        raise ValueError("Network, topology or implementation changed since checkpoint")
    actor.load_state_dict(state["actor"])
    critic.load_state_dict(state["critic"])
    updater.actor_optimizer.load_state_dict(state["actor_optimizer"])
    updater.critic_optimizer.load_state_dict(state["critic_optimizer"])
    updater.updates = state["updates"]
    if updater.value_normalizer is not None:
        updater.value_normalizer.load_state_dict(state["value_normalizer"])
    random.setstate(state["python_rng"])
    np.random.set_state(state["numpy_rng"])
    torch.set_rng_state(state["torch_rng"].cpu())
    if state["cuda_rng"] and torch.cuda.is_available():
        torch.cuda.set_rng_state_all([value.cpu() for value in state["cuda_rng"]])
    return state["progress"]


def _scenario_metrics(rows):
    result = {}
    for scenario in RESEARCH_SCENARIOS:
        subset = [row for row in rows if row["scenario"] == scenario]
        if not subset:
            raise ValueError(f"Validation omitted required scenario {scenario}")
        result[scenario] = {key: float(np.mean([row[key] for row in subset])) for key in
                            ("delay_per_scheduled_s", "completed", "p95_wait_s",
                             "worst_approach_wait_s", "max_approach_p95_wait_s")}
    return result


def validation_violation(rows, baseline_rows):
    candidate = _scenario_metrics(rows)
    baseline = _scenario_metrics(baseline_rows)
    violation = 0.
    for scenario in RESEARCH_SCENARIOS:
        current, reference = candidate[scenario], baseline[scenario]
        violation = max(violation,
                        max(0., (current["delay_per_scheduled_s"] / max(reference["delay_per_scheduled_s"], 1e-12) - .99) / .01),
                        max(0., (0.98 * reference["completed"] - current["completed"]) / max(1., 0.02 * reference["completed"])))
        for key in ("p95_wait_s", "worst_approach_wait_s", "max_approach_p95_wait_s"):
            tolerance = max(0.1 * reference[key], 1.)
            violation = max(violation, max(0., (current[key] - reference[key]) / tolerance))
    return float(violation), candidate


def train(config, output, seed, resume=None):
    from src.rl.benchmark import score

    output = Path(output)
    output.mkdir(parents=True, exist_ok=bool(resume))
    config_path = output / "config.json"
    if resume and json.loads(config_path.read_text(encoding="utf-8")) != config:
        raise ValueError("Resume requires the original environment and training configuration")
    config_path.write_text(json.dumps(config, indent=2), encoding="utf-8")
    training = config["training"]
    algorithm = training["algorithm"]
    if algorithm not in ("graph_mappo", "local_mappo"):
        raise ValueError("MAPPO training algorithm must be graph_mappo or local_mappo")
    architecture = "graph_attention" if algorithm == "graph_mappo" else "self_only"
    if (config["environment"].get("cycle_time_s") != GRAPH_MAPPO_TIMING["cycle_time_s"]
            or config["environment"].get("min_green_share") != GRAPH_MAPPO_TIMING["min_green_share"]
            or config["environment"].get("demand_s") != GRAPH_MAPPO_HORIZON["demand_s"]
            or config["environment"].get("drain_s") != GRAPH_MAPPO_HORIZON["drain_s"]):
        raise ValueError("MAPPO environment timing and horizon must match its versioned contract")
    device = torch.device(training.get("device", "cuda"))
    if device.type == "cuda" and not torch.cuda.is_available():
        raise RuntimeError("CUDA MAPPO training requested but unavailable")
    seed_everything(seed)
    topology = json.loads(Path(config["environment"]["topology_path"]).read_text(encoding="utf-8"))
    graph = build_research_graph(topology)
    actor = GraphActor(graph, local_only=architecture == "self_only", device=device)
    critic = CentralizedCritic(device=device)
    updater = MAPPOUpdater(actor, critic, training)
    env_config = {**config["environment"], "trace": False, "discount": training.get("discount", .99)}
    provenance = {"network_sha256": file_hash(env_config["network_path"]),
                  "topology_sha256": file_hash(env_config["topology_path"]),
                  "implementation_sha256": _implementation_hash()}
    progress = {"episodes": 0, "joint_decisions": 0, "elapsed_s": 0., "schedule_cursor": 0,
                "simulated_seconds": 0., "action_counts": [0, 0, 0], "validation": [],
                "diagnostics": []}
    if resume:
        progress = load_training_checkpoint(resume, config, seed, provenance,
                                            actor, critic, updater, device)

    ctx = mp.get_context("spawn")
    pipes, processes = [], []
    for worker_id in range(2):
        parent, child = ctx.Pipe()
        process = ctx.Process(target=worker, args=(child, env_config, str(output / f"worker{worker_id}")))
        process.start()
        child.close()
        pipes.append(parent)
        processes.append(process)

    initial_elapsed = progress["elapsed_s"]
    started = time.monotonic()
    max_seconds = int(training.get("max_seconds", 3600))
    max_episodes = int(training.get("max_episodes", 128))
    episodes_per_worker = int(training.get("episodes_per_worker", 4))
    validation_interval = int(training.get("validation_interval", 16))
    if episodes_per_worker != 4:
        raise ValueError("The graph-MAPPO protocol collects four complete episodes per worker")
    if max_episodes <= 0 or max_episodes % 8 or validation_interval <= 0 or validation_interval % 8:
        raise ValueError("Episode and validation limits must be positive multiples of eight")
    if max_seconds <= 0:
        raise ValueError("Training time budget must be positive")
    status = ("episode_cap" if progress["episodes"] >= max_episodes else
              "time_cap" if progress["elapsed_s"] >= max_seconds else "incomplete")

    def elapsed():
        return initial_elapsed + time.monotonic() - started

    evaluation = config.get("evaluation", {})
    validation_cache = Path(evaluation.get("cache_dir", "artifacts/mappo/validation-cache"))
    validation_workers = int(evaluation.get("workers", 2))
    case_timeout_s = float(evaluation.get("case_timeout_s", 180.))
    if validation_workers <= 0 or case_timeout_s <= 0:
        raise ValueError("Evaluation workers and per-case timeout must be positive")
    run_deadline = started + max(0., max_seconds - initial_elapsed)

    def save_checkpoint():
        progress["elapsed_s"] = elapsed()
        save_training_checkpoint(output / "checkpoint.pt", config, seed, provenance,
                                 actor, critic, updater, progress)

    def new_episode(worker_id):
        scenarios = list(RESEARCH_SCENARIOS)
        scenario = scenarios[progress["schedule_cursor"] % len(scenarios)]
        progress["schedule_cursor"] += 1
        demand_seed = int(np.random.choice(GRAPH_MAPPO_SEED_SPLITS["train"]))
        intensity = float(np.random.uniform(.8, 1.2))
        pipes[worker_id].send(("reset", {"seed": demand_seed,
                                         "options": {"scenario": scenario, "intensity": intensity}}))
        return receive(pipes[worker_id])

    def validate_latest_update():
        episode_count = progress["episodes"]
        validation_started = time.monotonic()
        actor_path = output / f"policy-episode-{episode_count}.json"
        export_actor(actor_path, actor, architecture, seed, config, provenance,
                     {**progress, "elapsed_s": elapsed()})
        controller_spec = {"type": algorithm, "model_path": str(actor_path.resolve())}
        rows, candidate_diagnostics = evaluate_cases(
            config, controller_spec, RESEARCH_SCENARIOS, GRAPH_MAPPO_SEED_SPLITS["validation"],
            output / "validation-cases" / algorithm, cache_root=validation_cache,
            workers=validation_workers, timeout_s=case_timeout_s, deadline=run_deadline)
        baseline_controller = {"type": "fair_cycle", "parameters": {
            "cycle_time_s": GRAPH_MAPPO_TIMING["cycle_time_s"],
            "min_green_share": GRAPH_MAPPO_TIMING["min_green_share"]}}
        baseline_rows, baseline_diagnostics = evaluate_cases(
            config, baseline_controller, RESEARCH_SCENARIOS, GRAPH_MAPPO_SEED_SPLITS["validation"],
            output / "validation-cases" / "fair_cycle", cache_root=validation_cache,
            workers=validation_workers, timeout_s=case_timeout_s, deadline=run_deadline)
        violation, metrics = validation_violation(rows, baseline_rows)
        progress["validation"].append({"episodes": episode_count,
                                        "model_path": str(actor_path.resolve()),
                                        "sha256": file_hash(actor_path), "score": score(rows),
                                        "gate_violation": violation,
                                        "scenario_metrics": metrics,
                                        "evaluation": {"elapsed_s": time.monotonic() - validation_started,
                                                       "candidate": candidate_diagnostics,
                                                       "fair_cycle": baseline_diagnostics}})
        save_checkpoint()
        export_actor(output / "latest.json", actor, architecture, seed, config,
                     provenance, {**progress, "elapsed_s": elapsed()})

    try:
        def validate_or_stop():
            nonlocal status
            try:
                validate_latest_update()
                return True
            except TimeoutError as error:
                status = "time_cap_during_validation" if elapsed() >= max_seconds else "validation_case_timeout"
                progress["validation_error"] = str(error)
                save_checkpoint()
                return False

        if progress["episodes"] // validation_interval > len(progress["validation"]):
            if elapsed() < max_seconds:
                validate_or_stop()
            else:
                status = "time_cap_before_pending_validation"
        while status == "incomplete" and progress["episodes"] < max_episodes and elapsed() < max_seconds:
            progress_before_rollout = copy.deepcopy(progress)
            python_rng_before = random.getstate()
            numpy_rng_before = np.random.get_state()
            torch_rng_before = torch.get_rng_state()
            cuda_rng_before = torch.cuda.get_rng_state_all() if torch.cuda.is_available() else []
            episode_counts = [0, 0]
            episode_records = [None, None]
            observations, infos = [None, None], [None, None]
            for worker_id in range(2):
                observations[worker_id], infos[worker_id] = new_episode(worker_id)
                episode_records[worker_id] = []
            completed_episodes = []
            interrupted = False
            while any(count < episodes_per_worker for count in episode_counts):
                if elapsed() >= max_seconds:
                    interrupted = True
                    break
                active = [index for index, count in enumerate(episode_counts) if count < episodes_per_worker]
                batch_observations = np.stack([
                    [observations[index][node_id] for node_id in GRAPH_MAPPO_NODE_ORDER] for index in active])
                batch_masks = np.stack([
                    [infos[index]["action_masks"][node_id] for node_id in GRAPH_MAPPO_NODE_ORDER]
                    for index in active])
                with torch.no_grad():
                    logits = actor(torch.as_tensor(batch_observations, device=device))
                    distribution = masked_distribution(logits, batch_masks)
                    actions = distribution.sample()
                    log_probs = distribution.log_prob(actions)
                    values = updater.predict_values(torch.as_tensor(batch_observations, device=device))
                for row, worker_id in enumerate(active):
                    action_map = {node_id: int(actions[row, index].item())
                                  for index, node_id in enumerate(GRAPH_MAPPO_NODE_ORDER)}
                    pipes[worker_id].send(("step", action_map))
                step_results = {worker_id: receive(pipes[worker_id]) for worker_id in active}
                for row, worker_id in enumerate(active):
                    next_observations, reward, terminated, truncated, info = step_results[worker_id]
                    next_batch = np.stack([next_observations[node_id] for node_id in GRAPH_MAPPO_NODE_ORDER])
                    with torch.no_grad():
                        next_values = updater.predict_values(
                            torch.as_tensor(next_batch, device=device)).cpu().numpy()
                    done = bool(terminated or truncated)
                    elapsed_s = float(info["elapsed_s"])
                    episode_records[worker_id].append({
                        "observation": batch_observations[row].copy(),
                        "action": actions[row].cpu().numpy().astype(np.int64),
                        "mask": batch_masks[row].copy(),
                        "old_log_prob": log_probs[row].cpu().numpy().astype(np.float32),
                        "value": values[row].cpu().numpy().astype(np.float32),
                        "reward": float(reward), "next_value": next_values.astype(np.float32),
                        "terminal": done, "elapsed_s": elapsed_s})
                    for action in action_map.values():
                        progress["action_counts"][action] += 1
                    progress["simulated_seconds"] += elapsed_s
                    observations[worker_id], infos[worker_id] = next_observations, info
                    if done:
                        if not episode_records[worker_id]:
                            raise RuntimeError("Completed SUMO episode has no graph transitions")
                        completed_episodes.append(episode_records[worker_id])
                        episode_counts[worker_id] += 1
                        if episode_counts[worker_id] < episodes_per_worker:
                            observations[worker_id], infos[worker_id] = new_episode(worker_id)
                            episode_records[worker_id] = []
            if interrupted:
                progress = progress_before_rollout
                random.setstate(python_rng_before)
                np.random.set_state(numpy_rng_before)
                torch.set_rng_state(torch_rng_before.cpu())
                if cuda_rng_before and torch.cuda.is_available():
                    torch.cuda.set_rng_state_all([value.cpu() for value in cuda_rng_before])
                status = "budget_exhausted_mid_rollout; partial rollout discarded"
                break

            all_observations, all_actions, all_masks, all_log_probs = [], [], [], []
            all_advantages, all_returns = [], []
            for episode in completed_episodes:
                values = np.stack([item["value"] for item in episode])
                next_values = np.stack([item["next_value"] for item in episode])
                advantages, returns = generalized_advantage_estimate(
                    [item["reward"] for item in episode], values, next_values,
                    [item["terminal"] for item in episode], [item["elapsed_s"] for item in episode],
                    discount=training.get("discount", .99), gae_lambda=training.get("gae_lambda", .95))
                all_observations.extend(item["observation"] for item in episode)
                all_actions.extend(item["action"] for item in episode)
                all_masks.extend(item["mask"] for item in episode)
                all_log_probs.extend(item["old_log_prob"] for item in episode)
                all_advantages.extend(advantages)
                all_returns.extend(returns)
            all_advantages = np.asarray(all_advantages, dtype=np.float32)
            all_advantages = (all_advantages - all_advantages.mean()) / (all_advantages.std() + 1e-8)
            return_targets = np.asarray(all_returns, dtype=np.float32)
            update_diagnostics = updater.update(
                np.asarray(all_observations, dtype=np.float32), np.asarray(all_actions, dtype=np.int64),
                np.asarray(all_masks, dtype=bool), np.asarray(all_log_probs, dtype=np.float32),
                all_advantages, return_targets)
            progress["episodes"] += 2 * episodes_per_worker
            progress["joint_decisions"] += len(all_observations)
            progress["diagnostics"].append({"episodes": progress["episodes"], "update": updater.updates,
                                            **update_diagnostics,
                                            "return_mean": float(return_targets.mean()),
                                            "return_std": float(return_targets.std()),
                                            "return_min": float(return_targets.min()),
                                            "return_max": float(return_targets.max()),
                                            "action_distribution": [count / max(1, sum(progress["action_counts"]))
                                                                    for count in progress["action_counts"]],
                                            "simulated_seconds": progress["simulated_seconds"],
                                            "simulation_seconds_per_wall_second": progress["simulated_seconds"] / max(elapsed(), 1.)})
            actor.eval()
            save_checkpoint()
            progress_for_artifact = {**progress, "elapsed_s": elapsed()}
            export_actor(output / "latest.json", actor, architecture, seed, config,
                         provenance, progress_for_artifact)
            print(json.dumps({"algorithm": algorithm, "seed": seed, "episodes": progress["episodes"],
                              "updates": updater.updates, "elapsed_s": round(elapsed(), 1),
                              "diagnostics": update_diagnostics,
                              "action_counts": progress["action_counts"]}), flush=True)

            if progress["episodes"] // validation_interval > len(progress["validation"]):
                if elapsed() < max_seconds:
                    validate_or_stop()
                else:
                    status = "time_cap_before_pending_validation"
            if progress["episodes"] >= max_episodes:
                status = "episode_cap"
            elif elapsed() >= max_seconds:
                status = "time_cap"

        if progress["episodes"] < max_episodes and elapsed() >= max_seconds and status == "incomplete":
            status = "time_cap"
        if progress["episodes"] == 0:
            status = status if status != "incomplete" else "no_completed_update"
    except BaseException as error:
        (output / "failure.json").write_text(json.dumps({"status": "failed", "reason": str(error)}),
                                             encoding="utf-8")
        raise
    finally:
        for pipe, process in zip(pipes, processes):
            if process.is_alive():
                try:
                    pipe.send(("close", None))
                except (BrokenPipeError, EOFError):
                    pass
                process.join(15)
                if process.is_alive():
                    process.terminate()
                    process.join(5)
            pipe.close()

    progress["elapsed_s"] = elapsed()
    selected = min(progress["validation"], key=lambda row: (
        row["gate_violation"], row["score"],
        max(values["p95_wait_s"] for values in row["scenario_metrics"].values()))) if progress["validation"] else None
    if progress["episodes"] > 0:
        export_actor(output / "final.json", actor, architecture, seed, config, provenance, progress)
    result = {"status": status, "algorithm": algorithm, "seed": seed,
              "episodes": progress["episodes"], "joint_decisions": progress["joint_decisions"],
              "updates": updater.updates, "elapsed_s": progress["elapsed_s"],
              "validation": progress["validation"], "selected": selected,
              "promoted": False, "action_counts": progress["action_counts"],
              "diagnostics": progress["diagnostics"], "provenance": provenance,
              "runtime": {"torch": torch.__version__, "cuda": torch.version.cuda,
                          "device": str(device)}}
    (output / "training.json").write_text(json.dumps(result, indent=2), encoding="utf-8")
    return result


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--config", required=True)
    parser.add_argument("--output", required=True)
    parser.add_argument("--resume")
    parser.add_argument("--seed", type=int)
    parser.add_argument("--max-seconds", type=int)
    parser.add_argument("--max-episodes", type=int)
    args = parser.parse_args()
    config = json.loads(Path(args.config).read_text(encoding="utf-8"))
    if args.max_seconds is not None:
        config["training"]["max_seconds"] = args.max_seconds
    if args.max_episodes is not None:
        config["training"]["max_episodes"] = args.max_episodes
    if args.resume and args.seed is None:
        parser.error("--resume requires --seed")
    seeds = [args.seed] if args.seed is not None else GRAPH_MAPPO_PROTOCOL["learner_seeds"]
    for seed in seeds:
        train(config, Path(args.output) / f"seed-{seed}", seed, args.resume)


if __name__ == "__main__":
    main()
