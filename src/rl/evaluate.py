"""Held-out paired evaluation in the synthetic training environment, not SUMO."""
import argparse
import hashlib
import json
import time
from pathlib import Path

import numpy as np

from .policy import NumpyPolicy
from .traffic_env import TrafficSignalEnv


def evaluate(model_path, seeds=(10001, 10002, 10003, 10004, 10005), steps=180,
             output_path="artifacts/rl_evaluation.json"):
    weights = json.loads(Path(model_path).read_text(encoding="utf-8"))
    policy = NumpyPolicy(weights)
    training_range = weights.get("training", {}).get("training_seeds")
    if not seeds or len(set(seeds)) != len(seeds):
        raise ValueError("Provide distinct evaluation seeds")
    if training_range and any(training_range[0] <= s <= training_range[1] for s in seeds):
        raise ValueError("Evaluation seeds overlap training seeds")
    rows = []
    for scenario in TrafficSignalEnv.SCENARIOS:
        for seed in seeds:
            for controller in ("fixed_time", "max_queue", "dqn"):
                env = TrafficSignalEnv(max_steps=steps)
                obs, _ = env.reset(seed=seed, scenario=scenario)
                if policy.feature_spec and policy.feature_spec != env.feature_spec:
                    raise ValueError("Evaluation feature specification differs from model")
                digest = hashlib.sha256(env.arrivals.tobytes() + env.receiving.tobytes()).hexdigest()
                queues, latencies, actions = [], [], []
                for _ in range(steps):
                    start = time.perf_counter_ns()
                    if controller == "dqn":
                        action = int(np.argmax(policy.predict(obs)))
                    elif controller == "max_queue":
                        action = int(np.argmax(env.served @ env.queue))
                    else:
                        action = int(env.simulation_time_s // 15) % env.action_space_n
                    latencies.append((time.perf_counter_ns() - start) / 1e6)
                    obs, _, _, _, info = env.step(action)
                    queues.append(info["total_queue"])
                    actions.append(action)
                rows.append({"scenario": scenario, "seed": seed, "controller": controller,
                             "demand_sha256": digest, "mean_queue": float(np.mean(queues)),
                             "p95_queue": float(np.percentile(queues, 95)),
                             "throughput_veh_per_s": info["total_discharged"] / info["simulation_time_s"],
                             "waiting_vehicle_seconds": info["waiting_vehicle_seconds"],
                             "inference_p50_ms": float(np.median(latencies)),
                             "inference_p95_ms": float(np.percentile(latencies, 95)),
                             "queues": queues, "actions": actions})
    comparisons = []
    rng = np.random.default_rng(0)
    for scenario in TrafficSignalEnv.SCENARIOS:
        by_key = {(r["controller"], r["seed"]): r for r in rows if r["scenario"] == scenario}
        for baseline in ("fixed_time", "max_queue"):
            delta = np.array([by_key[("dqn", s)]["mean_queue"] - by_key[(baseline, s)]["mean_queue"]
                              for s in seeds])
            boot = rng.choice(delta, (5000, len(delta)), replace=True).mean(axis=1)
            comparisons.append({"scenario": scenario, "baseline": baseline,
                                "paired_queue_differences_dqn_minus_baseline": delta.tolist(),
                                "mean_difference": float(delta.mean()),
                                "bootstrap_95_interval": np.percentile(boot, [2.5, 97.5]).tolist()})
    report = {"source_mode": "synthetic_training", "valid_for_research": False,
              "limitations": "Single node, instantaneous phases, exogenous downstream state; not SUMO or hardware.",
              "model_sha256": hashlib.sha256(Path(model_path).read_bytes()).hexdigest(),
              "seeds": list(seeds), "steps": steps, "runs": rows, "paired_comparisons": comparisons}
    path = Path(output_path)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(report, indent=2, allow_nan=False), encoding="utf-8")
    return report


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--model", required=True)
    parser.add_argument("--seeds", nargs="+", type=int, default=[10001, 10002, 10003, 10004, 10005])
    parser.add_argument("--steps", type=int, default=180)
    parser.add_argument("--output", default="artifacts/rl_evaluation.json")
    args = parser.parse_args()
    report = evaluate(args.model, args.seeds, args.steps, args.output)
    print(json.dumps(report["paired_comparisons"], indent=2))
