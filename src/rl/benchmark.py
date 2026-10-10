"""Paired research evaluation and conservative release gates."""
import argparse
import json
import time
from pathlib import Path
import numpy as np

from contracts.research import (GRAPH_MAPPO_SEED_SPLITS, RESEARCH_SCENARIOS,
                                GRAPH_MAPPO_HORIZON, GRAPH_MAPPO_TIMING, SEED_SPLITS)
from src.control.factory import create_controller
from src.simulation.runtime import SumoRuntime, file_hash


def run_case(config, controller, scenario, seed, output):
    runtime = None
    try:
        policy = create_controller(controller["type"], controller.get("parameters"), controller.get("model_path"))
        policy.reset()
        environment = {key: value for key, value in config["environment"].items()
                       if key in ("topology_path", "network_path", "demand_s", "drain_s", "intensity",
                                  "trace", "wait_penalty_lambda")}
        runtime = SumoRuntime(**environment, output=output, scenario=scenario, seed=seed)
        if controller["type"] in ("shared_dqn", "fair_cycle_rl", "graph_mappo", "local_mappo"):
            for key in ("network_sha256", "topology_sha256"):
                if policy.artifact["provenance"][key] != runtime.metadata[key]:
                    raise ValueError(f"Model {key} mismatch")
        if controller["type"] in ("graph_mappo", "local_mappo"):
            if (config["environment"].get("cycle_time_s") != GRAPH_MAPPO_TIMING["cycle_time_s"]
                    or config["environment"].get("min_green_share") != GRAPH_MAPPO_TIMING["min_green_share"]
                    or config["environment"].get("demand_s") != GRAPH_MAPPO_HORIZON["demand_s"]
                    or config["environment"].get("drain_s") != GRAPH_MAPPO_HORIZON["drain_s"]):
                raise ValueError("Evaluation environment timing/horizon does not match the MAPPO artifact")
        done = False
        while not done:
            actions = {}
            for node in runtime.topology["nodes"]:
                nid = node["node_id"]
                cmd = policy.compute_command(nid, runtime.telemetry[nid], runtime.topology,
                                             network_state=runtime.telemetry, current_time_s=runtime.time)
                if cmd is None or cmd["controller"] != controller["type"]:
                    raise ValueError("Requested controller did not execute")
                actions[nid] = [p["phase_id"] for p in node["phases"]].index(cmd["target_phase_id"])
            _, _, terminated, truncated = runtime.step(actions)
            done = terminated or truncated
        metrics = runtime.finish()
        metrics["controller"] = controller
        if controller["type"] in ("fair_cycle_rl", "graph_mappo", "local_mappo"):
            metrics["controller_timing"] = {"cycle_time_s": policy.cycle_time_s,
                                             "min_green_share": policy.min_green_share}
        elif controller["type"] == "fair_cycle":
            metrics["controller_timing"] = {"cycle_time_s": policy.cycle_time_s,
                                             "min_green_share": policy.min_green_share}
        if controller.get("model_path"):
            metrics["model_sha256"] = file_hash(controller["model_path"])
        (Path(output) / "metrics.json").write_text(json.dumps(metrics, indent=2))
        return metrics
    except BaseException as error:
        if runtime:
            runtime.fail(error)
        else:
            Path(output).mkdir(parents=True, exist_ok=True)
            (Path(output) / "failure.json").write_text(json.dumps({"valid": False, "reason": str(error)}))
        raise


def evaluate_policy(config, controller, seeds, output):
    rows = []
    for scenario in RESEARCH_SCENARIOS:
        for seed in seeds:
            row = run_case(config, controller, scenario, seed, Path(output) / f"{scenario}-{seed}")
            rows.append(row)
    return rows


def score(rows):
    return float(np.mean([np.mean([r["delay_per_scheduled_s"] for r in rows if r["scenario"] == s])
                          for s in RESEARCH_SCENARIOS]))


def promotion_gate(candidate, baselines, bootstrap_samples=10000):
    reasons, comparisons = [], {}
    expected = {(s, seed) for s in RESEARCH_SCENARIOS for seed in SEED_SPLITS["holdout"]}
    def indexed(rows):
        pairs = {(r["scenario"], r["seed"]): r for r in rows}
        if len(rows) != len(expected) or set(pairs) != expected:
            raise ValueError("Promotion requires every unique holdout scenario/seed pair")
        return pairs
    cand = indexed(candidate)
    required = ("edgeflow", "max_pressure", "actuated", "fixed_time")
    missing = set(required) - set(baselines)
    if missing:
        raise ValueError(f"Promotion requires reference controllers: {sorted(missing)}")
    for name in required:
        baseline = indexed(baselines[name])
        differences, base_delays = [], []
        for scenario in RESEARCH_SCENARIOS:
            c = [cand[(scenario, seed)] for seed in SEED_SPLITS["holdout"]]
            b = [baseline[(scenario, seed)] for seed in SEED_SPLITS["holdout"]]
            for cr, br in zip(c, b):
                if any(cr[key] != br[key] for key in ("demand_sha256", "network_sha256", "topology_sha256", "timing", "scheduled", "demand_s", "drain_s")):
                    raise ValueError("Unpaired benchmark inputs")
                if not cr["valid"] or not br["valid"] or any(cr[k] or br[k] for k in ("collisions", "teleports", "accounting_losses")):
                    reasons.append(f"{name}/{scenario}: invalid run")
            cm = {key: np.mean([r[key] for r in c]) for key in ("delay_per_scheduled_s", "completed", "p95_wait_s", "worst_approach_wait_s")}
            bm = {key: np.mean([r[key] for r in b]) for key in cm}
            if cm["delay_per_scheduled_s"] > 1.05 * bm["delay_per_scheduled_s"]:
                reasons.append(f"{name}/{scenario}: delay regression >5%")
            if cm["completed"] < .98 * bm["completed"]:
                reasons.append(f"{name}/{scenario}: throughput <98%")
            for key in ("p95_wait_s", "worst_approach_wait_s", "max_approach_p95_wait_s"):
                if key not in c[0] or key not in b[0]:
                    raise ValueError(f"Version 2 wait metrics required: {key}")
                cm[key] = np.mean([r[key] for r in c])
                bm[key] = np.mean([r[key] for r in b])
                if cm[key] > bm[key] + max(.1 * bm[key], 1.):
                    reasons.append(f"{name}/{scenario}: {key} regression")
            differences.append([br["delay_per_scheduled_s"]-cr["delay_per_scheduled_s"] for cr, br in zip(c,b)])
            base_delays.append([br["delay_per_scheduled_s"] for br in b])
        difference, base = np.asarray(differences), np.asarray(base_delays)
        rng = np.random.default_rng(9182)
        # Resample seed blocks, preserving the shared seed across all scenarios.
        indices = rng.integers(0, difference.shape[1], (bootstrap_samples, difference.shape[1]))
        samples = difference[:, indices].mean(axis=(0, 2))
        interval = np.percentile(samples, [2.5, 97.5]).tolist()
        improvement = float(difference.mean() / max(base.mean(), 1e-12))
        comparisons[name] = {"relative_delay_improvement": improvement, "paired_delay_improvement_ci95_s": interval}
        if name in ("edgeflow", "max_pressure") and (improvement < .05 or interval[0] <= 0):
            reasons.append(f"{name}: required 5% improvement and positive paired interval not reached")
        if name in ("actuated", "fixed_time") and improvement < -.02:
            reasons.append(f"{name}: overall delay regression exceeds 2%")
    return {"promoted": not reasons, "reasons": sorted(set(reasons)), "comparisons": comparisons}


def graph_mappo_promotion_gate(candidate, baselines, bootstrap_samples=10000):
    """Apply all existing release gates plus the matched fair-cycle improvement gate."""
    required = ("fair_cycle", "edgeflow", "max_pressure", "actuated", "fixed_time")
    missing = set(required) - set(baselines)
    if missing:
        raise ValueError(f"Graph-MAPPO promotion requires reference controllers: {sorted(missing)}")
    expected = {(scenario, seed) for scenario in RESEARCH_SCENARIOS
                for seed in GRAPH_MAPPO_SEED_SPLITS["holdout"]}

    def indexed(rows):
        mapping = {(row["scenario"], row["seed"]): row for row in rows}
        if len(rows) != len(expected) or set(mapping) != expected:
            raise ValueError("Graph-MAPPO promotion requires every unique new holdout scenario/seed pair")
        return mapping

    current = indexed(candidate)
    reasons, comparisons = [], {}
    for name in required:
        reference = indexed(baselines[name])
        differences, base_values = [], []
        for scenario in RESEARCH_SCENARIOS:
            candidates = [current[(scenario, seed)] for seed in GRAPH_MAPPO_SEED_SPLITS["holdout"]]
            baseline = [reference[(scenario, seed)] for seed in GRAPH_MAPPO_SEED_SPLITS["holdout"]]
            for left, right in zip(candidates, baseline):
                for key in ("demand_sha256", "network_sha256", "topology_sha256", "scheduled", "demand_s", "drain_s"):
                    if left.get(key) != right.get(key):
                        raise ValueError(f"Unpaired graph-MAPPO benchmark inputs: {key}")
                if name == "fair_cycle" and left.get("controller_timing") != right.get("controller_timing"):
                    raise ValueError("Graph-MAPPO and fair-cycle reference timing are not matched")
                if (not left["valid"] or not right["valid"]
                        or any(left.get(key, 0) or right.get(key, 0)
                               for key in ("collisions", "teleports", "accounting_losses"))):
                    reasons.append(f"{name}/{scenario}: invalid run or safety/accounting failure")
            current_summary = {key: float(np.mean([row[key] for row in candidates])) for key in
                               ("delay_per_scheduled_s", "completed", "p95_wait_s",
                                "worst_approach_wait_s", "max_approach_p95_wait_s")}
            base_summary = {key: float(np.mean([row[key] for row in baseline])) for key in current_summary}
            if current_summary["delay_per_scheduled_s"] > 1.05 * base_summary["delay_per_scheduled_s"]:
                reasons.append(f"{name}/{scenario}: delay regression exceeds 5%")
            if current_summary["completed"] < .98 * base_summary["completed"]:
                reasons.append(f"{name}/{scenario}: throughput below 98%")
            for key in ("p95_wait_s", "worst_approach_wait_s", "max_approach_p95_wait_s"):
                if current_summary[key] > base_summary[key] + max(.1 * base_summary[key], 1.):
                    reasons.append(f"{name}/{scenario}: {key} guardrail failed")
            differences.append([right["delay_per_scheduled_s"] - left["delay_per_scheduled_s"]
                                for left, right in zip(candidates, baseline)])
            base_values.append([row["delay_per_scheduled_s"] for row in baseline])
        difference = np.asarray(differences, dtype=np.float64)
        base = np.asarray(base_values, dtype=np.float64)
        per_seed = difference.mean(axis=0)
        rng = np.random.default_rng(9182)
        draws = rng.integers(0, len(per_seed), (bootstrap_samples, len(per_seed)))
        samples = per_seed[draws].mean(axis=1)
        interval = np.percentile(samples, [2.5, 97.5]).tolist()
        base_mean = float(base.mean())
        improvement = float(difference.mean() / max(base_mean, 1e-12))
        comparisons[name] = {"relative_delay_improvement": improvement,
                             "paired_delay_improvement_ci95_s": interval}
        if name in ("edgeflow", "max_pressure") and (improvement < .05 or interval[0] <= 0):
            reasons.append(f"{name}: required 5% delay improvement and positive paired interval not reached")
        if name in ("actuated", "fixed_time") and improvement < -.02:
            reasons.append(f"{name}: overall delay regression exceeds 2%")
        if name == "fair_cycle" and (improvement < .01 or interval[0] <= 0):
            reasons.append("fair_cycle: required 1% delay improvement and positive paired interval not reached")
    return {"promoted": not reasons, "reasons": sorted(set(reasons)), "comparisons": comparisons}


def graph_communication_comparison(graph_models, local_models, bootstrap_samples=10000):
    """Compare paired learner seeds, resampling demand-seed blocks across scenarios."""
    seeds = (17, 29, 43)
    if set(graph_models) != set(seeds) or set(local_models) != set(seeds):
        raise ValueError("Graph contribution requires graph/local results for learner seeds 17, 29 and 43")
    pairs = {}
    block_differences = []
    demand_seeds = GRAPH_MAPPO_SEED_SPLITS["holdout"]
    for learner_seed in seeds:
        graph = {(row["scenario"], row["seed"]): row for row in graph_models[learner_seed]}
        local = {(row["scenario"], row["seed"]): row for row in local_models[learner_seed]}
        if set(graph) != set(local) or set(graph) != {(s, d) for s in RESEARCH_SCENARIOS for d in demand_seeds}:
            raise ValueError(f"Incomplete graph/local holdout pair for learner seed {learner_seed}")
        by_demand = []
        guardrails_pass = True
        for demand_seed in demand_seeds:
            diffs = []
            for scenario in RESEARCH_SCENARIOS:
                graph_row, local_row = graph[(scenario, demand_seed)], local[(scenario, demand_seed)]
                for key in ("demand_sha256", "network_sha256", "topology_sha256"):
                    if graph_row.get(key) != local_row.get(key):
                        raise ValueError("Graph/local holdout runs do not share frozen inputs")
                if (graph_row["completed"] < .98 * local_row["completed"]
                        or any(graph_row[key] > local_row[key] + max(.1 * local_row[key], 1.)
                               for key in ("p95_wait_s", "worst_approach_wait_s", "max_approach_p95_wait_s"))):
                    guardrails_pass = False
                diffs.append(local_row["delay_per_scheduled_s"] - graph_row["delay_per_scheduled_s"])
            by_demand.append(float(np.mean(diffs)))
        by_demand = np.asarray(by_demand)
        rng = np.random.default_rng(9182 + learner_seed)
        draws = rng.integers(0, len(by_demand), (bootstrap_samples, len(by_demand)))
        intervals = np.percentile(by_demand[draws].mean(axis=1), [2.5, 97.5]).tolist()
        local_mean = float(np.mean([row["delay_per_scheduled_s"] for row in local.values()]))
        relative = float(by_demand.mean() / max(local_mean, 1e-12))
        pairs[learner_seed] = {"mean_delay_improvement_s": float(by_demand.mean()),
                               "relative_delay_improvement": relative,
                               "paired_delay_improvement_ci95_s": intervals,
                               "fairness_throughput_guardrails_pass": guardrails_pass,
                               "graph_value_claim_supported": bool(relative >= .01 and intervals[0] > 0
                                                                    and guardrails_pass)}
        block_differences.append(by_demand)
    pooled = np.mean(np.stack(block_differences), axis=0)
    rng = np.random.default_rng(9182)
    draws = rng.integers(0, len(pooled), (bootstrap_samples, len(pooled)))
    interval = np.percentile(pooled[draws].mean(axis=1), [2.5, 97.5]).tolist()
    local_mean = float(np.mean([row["delay_per_scheduled_s"] for seed in seeds
                                for row in local_models[seed]]))
    relative = float(pooled.mean() / max(local_mean, 1e-12))
    all_guardrails = all(row["fairness_throughput_guardrails_pass"] for row in pairs.values())
    return {"mean_delay_improvement_s": float(pooled.mean()),
            "relative_delay_improvement": relative,
            "paired_delay_improvement_ci95_s": interval,
            "fairness_throughput_guardrails_pass": all_guardrails,
            "graph_value_claim_supported": bool(relative >= .01 and interval[0] > 0 and all_guardrails),
            "learner_pairs": pairs}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--config", required=True)
    parser.add_argument("--output", required=True)
    parser.add_argument("--split", choices=("validation", "holdout"), default="validation")
    args = parser.parse_args()
    config = json.loads(Path(args.config).read_text())
    root = Path(args.output)
    root.mkdir(parents=True, exist_ok=False)
    frozen = config.get("frozen_selection")
    if args.split == "holdout":
        if not frozen or frozen["selection_split"] != "validation":
            raise ValueError("Freeze validation-selected policies/baselines before holdout")
        for path, expected in frozen["model_hashes"].items():
            if file_hash(path) != expected:
                raise ValueError("Frozen model changed")
    (root / "config.json").write_text(json.dumps(config, indent=2))
    results = {}
    for name, controller in config["controllers"].items():
        print(f"Evaluating {name} on {args.split}", flush=True)
        results[name] = evaluate_policy(config, controller, SEED_SPLITS[args.split], root / name)
        (root / "results.json").write_text(json.dumps(results, indent=2))
    if args.split == "holdout":
        gate = promotion_gate(results[frozen["candidate"]], results)
        (root / "promotion.json").write_text(json.dumps(gate, indent=2))
    else:
        gate = {"promoted": False, "reasons": ["Validation only; holdout gate not evaluated"]}
    lines = ["# Corrected SUMO comparison", "", f"Promotion: {gate['promoted']}", "",
             "| Controller | Equal-weight accrued delay / scheduled vehicle (s) |", "|---|---:|"]
    lines.extend(f"| {name} | {score(rows):.3f} |" for name, rows in results.items())
    lines.extend(["", "Raw evidence: [results.json](results.json), [configuration](config.json).",
                  "", *gate["reasons"]])
    (root / "report.md").write_text("\n".join(lines) + "\n")


if __name__ == "__main__":
    main()
