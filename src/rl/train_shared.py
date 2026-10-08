"""Two isolated SUMO workers feeding a shared GPU Double DQN learner."""
import argparse
import json
import multiprocessing as mp
import time
from pathlib import Path

from contracts.research import RESEARCH_SCENARIOS, SEED_SPLITS
from src.rl.shared_dqn import Learner
from src.simulation.runtime import file_hash


def worker(pipe, env_config, output):
    from src.rl.sumo_env import FairCycleSumoEnv, SumoNetworkEnv
    env_config = dict(env_config)
    mode = env_config.pop("mode", "shared_dqn")
    env_type = FairCycleSumoEnv if mode == "fair_cycle_dqn" else SumoNetworkEnv
    if mode == "fair_cycle_dqn":
        env_config.update(cycle_time_s=70, min_green_share=1/3,
                          discount=env_config.pop("discount", .99))
    env = env_type(**env_config, output=output)
    try:
        while True:
            command, args = pipe.recv()
            if command == "close":
                break
            try:
                result = env.reset(**args) if command == "reset" else env.step(args)
                pipe.send((True, result))
            except BaseException as error:
                import traceback
                pipe.send((False, traceback.format_exc()))
                break
    finally:
        env.close()
        pipe.close()


def receive(pipe):
    if not pipe.poll(180):
        raise RuntimeError("SUMO worker timeout")
    ok, result = pipe.recv()
    if not ok:
        raise RuntimeError(f"SUMO worker failed:\n{result}")
    return result


def validation_summary(rows):
    import numpy as np
    summary = {}
    for scenario in RESEARCH_SCENARIOS:
        current = [row for row in rows if row["scenario"] == scenario]
        summary[scenario] = {key: float(np.mean([row[key] for row in current])) for key in (
            "delay_per_scheduled_s", "completed", "p95_wait_s", "worst_approach_wait_s",
            "max_approach_p95_wait_s")}
    return summary


def train(config, output, seed, resume=None):
    import numpy as np
    from src.rl.benchmark import evaluate_policy, score
    output = Path(output)
    output.mkdir(parents=True, exist_ok=bool(resume))
    if resume and json.loads((output / "config.json").read_text()) != config:
        raise ValueError("Resume requires the original environment and training configuration")
    (output / "config.json").write_text(json.dumps(config, indent=2))
    learner = Learner(config["training"], seed)
    if resume:
        learner.load(resume)
    env_config = dict(config["environment"])
    env_config["trace"] = False
    if env_config.get("mode") == "fair_cycle_dqn":
        env_config["discount"] = config["training"].get("discount", .99)
    provenance = {k: file_hash(env_config[v]) for k, v in (
        ("network_sha256", "network_path"), ("topology_sha256", "topology_path"))}
    if resume:
        previous = json.loads((output / "latest.json").read_text())["provenance"]
        if any(previous[k] != v for k, v in provenance.items()):
            raise ValueError("Network or topology changed since the saved checkpoint")
    ctx = mp.get_context("spawn")
    pipes, processes = [], []
    for wid in range(2):
        parent, child = ctx.Pipe()
        process = ctx.Process(target=worker, args=(child, env_config, str(output / f"worker{wid}")))
        process.start()
        child.close()
        pipes.append(parent)
        processes.append(process)
    initial_elapsed = learner.elapsed_s
    start = time.monotonic()
    train_cfg = config["training"]
    max_decisions = train_cfg.get("max_joint_decisions", 100000)
    max_seconds = train_cfg.get("max_seconds", 7200)
    validation_interval = train_cfg.get("validation_interval", 20)
    last_validation = learner.episodes // validation_interval
    status = "incomplete"
    try:
        while learner.decisions < max_decisions and initial_elapsed + time.monotonic()-start < max_seconds:
            # Paired episode boundaries make full RNG/replay resumption reproducible.
            for i, pipe in enumerate(pipes):
                scenario = list(RESEARCH_SCENARIOS)[(learner.episodes+i) % 3]
                demand_seed = int(np.random.choice(SEED_SPLITS["train"]))
                intensity = float(np.random.uniform(.8, 1.2))
                pipe.send(("reset", {"seed": demand_seed, "options": {"scenario": scenario, "intensity": intensity}}))
            observations, infos = zip(*(receive(pipe) for pipe in pipes))
            observations, infos = list(observations), list(infos)
            active = {0, 1}
            while active:
                actions = {}
                for i in sorted(active):
                    actions[i] = learner.actions(observations[i], infos[i]["action_masks"])
                    pipes[i].send(("step", actions[i]))
                for i in sorted(active.copy()):
                    next_obs, reward, terminated, truncated, info = receive(pipes[i])
                    for nid in observations[i]:
                        elapsed_s = info.get("elapsed_s")
                        discount = (train_cfg.get("discount", .99) ** (elapsed_s / 5.)
                                    if elapsed_s is not None else None)
                        learner.replay.add(observations[i][nid], actions[i][nid], reward, next_obs[nid],
                                           terminated or (truncated and learner.algorithm == "fair_cycle_dqn"),
                                           info["action_masks"][nid], discount=discount)
                    learner.decisions += 1
                    update_interval = train_cfg.get("update_interval", 4)
                    if learner.replay.size >= train_cfg.get("learning_starts", 5000) and learner.decisions % update_interval == 0:
                        learner.update()
                    observations[i], infos[i] = next_obs, info
                    if terminated or truncated:
                        learner.episodes += 1
                        active.remove(i)
                # Hard budget cutoff: discard live simulator state and retain last boundary checkpoint.
                if learner.decisions >= max_decisions or initial_elapsed + time.monotonic()-start >= max_seconds:
                    if active:
                        learner.elapsed_s = initial_elapsed + time.monotonic()-start
                        status = "budget_exhausted_mid_episode; resume from last complete boundary"
                        return _finish(learner, output, provenance, status)
            learner.elapsed_s = initial_elapsed + time.monotonic()-start
            learner.save(output / "checkpoint.pt")
            learner.export(output / "latest.json", provenance)
            print(json.dumps({"seed": seed, "episodes": learner.episodes, "decisions": learner.decisions,
                              "updates": learner.updates, "elapsed_s": round(learner.elapsed_s, 1),
                              "last_update": learner.last_update_diagnostics,
                              "action_counts": learner.action_counts}), flush=True)
            if learner.episodes // validation_interval > last_validation:
                last_validation = learner.episodes // validation_interval
                checkpoint = output / f"policy-episode-{learner.episodes}.json"
                learner.export(checkpoint, provenance)
                controller_type = "fair_cycle_rl" if learner.algorithm == "fair_cycle_dqn" else "shared_dqn"
                rows = evaluate_policy(config, {"type": controller_type, "model_path": str(checkpoint)},
                                       SEED_SPLITS["validation"], output / f"validation-{learner.episodes}")
                learner.validation.append({"episodes": learner.episodes, "model_path": str(checkpoint),
                                           "sha256": file_hash(checkpoint), "score": score(rows),
                                           "scenario_metrics": validation_summary(rows)})
                learner.elapsed_s = initial_elapsed + time.monotonic()-start
                learner.save(output / "checkpoint.pt")
        status = "decision_cap" if learner.decisions >= max_decisions else "time_cap"
        return _finish(learner, output, provenance, status)
    except BaseException as error:
        (output / "failure.json").write_text(json.dumps({"status": "failed", "reason": str(error)}))
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


def _finish(learner, output, provenance, status):
    import platform
    import torch
    learner.export(output / "final.json", provenance)
    result = {"status": status, "seed": learner.seed, "episodes": learner.episodes,
              "decisions": learner.decisions, "updates": learner.updates,
              "elapsed_s": learner.elapsed_s, "validation": learner.validation, "promoted": False,
              "action_counts": learner.action_counts,
              "last_update_diagnostics": learner.last_update_diagnostics,
              "runtime": {"python": platform.python_version(), "torch": torch.__version__,
                          "cuda": torch.version.cuda,
                          "gpu": torch.cuda.get_device_name(0) if torch.cuda.is_available() else None}}
    if learner.validation:
        result["selected"] = min(learner.validation, key=lambda row: row["score"])
    (output / "training.json").write_text(json.dumps(result, indent=2))
    return result


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--config", required=True)
    parser.add_argument("--output", required=True)
    parser.add_argument("--resume")
    parser.add_argument("--seed", type=int)
    parser.add_argument("--wait-penalty-lambda", type=float)
    parser.add_argument("--max-seconds", type=int)
    args = parser.parse_args()
    config = json.loads(Path(args.config).read_text())
    if args.wait_penalty_lambda is not None:
        config["environment"]["wait_penalty_lambda"] = args.wait_penalty_lambda
    if args.max_seconds is not None:
        config["training"]["max_seconds"] = args.max_seconds
    if args.resume and args.seed is None:
        parser.error("--resume requires --seed")
    for seed in ([args.seed] if args.seed else [17, 29, 43]):
        train(config, Path(args.output) / f"seed-{seed}", seed, args.resume)


if __name__ == "__main__":
    main()
