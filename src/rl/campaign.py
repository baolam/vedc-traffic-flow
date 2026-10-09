"""Tune baselines, freeze validation selections, evaluate all learners on holdout.

Each completed case is immutable and resumable. A failed or timed-out campaign
leaves an explicit incomplete status and never promotes a controller.
"""
import argparse
import hashlib
import json
import time
from pathlib import Path

import yaml

from contracts.research import RESEARCH_ROBUSTNESS_SCENARIOS, RESEARCH_SCENARIOS, SEED_SPLITS
from src.rl.benchmark import promotion_gate, run_case, score
from src.simulation.runtime import file_hash


def digest(value):
    return hashlib.sha256(json.dumps(value, sort_keys=True).encode()).hexdigest()


def fixed_candidates():
    candidates = {}
    for cycle in (30, 50, 70):
        for share in (.25, .5, .75):
            ns, ew = (cycle-10) * share, (cycle-10) * (1-share)
            if min(ns, ew) < 10:
                continue
            candidates[f"cycle{cycle}-ns{share}"] = {"type": "fixed_time", "parameters": {
                "cycle_time_s": cycle, "phase_splits": {f"J{i}": [ns, ew] for i in range(1,5)}}}
    return candidates


def fair_cycle_candidates():
    return {f"cycle{cycle}-min{share:g}": {"type": "fair_cycle", "parameters": {
        "cycle_time_s": cycle, "min_green_share": share}}
        for cycle in (50, 70, 90) for share in (.25, 1 / 3)}


def validation_violation(candidate, baselines):
    """Return the largest normalized breach of the frozen validation limits."""
    import numpy as np
    violation = 0.
    for name in ("actuated", "fixed_time"):
        base = baselines[name]
        for scenario in RESEARCH_SCENARIOS:
            c = [r for r in candidate if r["scenario"] == scenario]
            b = [r for r in base if r["scenario"] == scenario]
            if len(c) != len(b) or not c:
                return float("inf")
            means = lambda rows, key: float(np.mean([r[key] for r in rows]))
            ratios = [means(c, "delay_per_scheduled_s") / means(b, "delay_per_scheduled_s") / 1.05,
                      means(b, "completed") * .98 / max(1., means(c, "completed"))]
            for key in ("p95_wait_s", "worst_approach_wait_s", "max_approach_p95_wait_s"):
                ratios.append((means(c, key) - means(b, key)) /
                              max(.1 * means(b, key), 1.) if means(c, key) > means(b, key) else 0.)
            violation = max(violation, *(max(0., ratio - 1.) for ratio in ratios))
        delay_regression = score(candidate) / max(1e-12, score(base)) - 1.
        violation = max(violation, max(0., delay_regression - .02))
    return violation


def validation_summary_violation(candidate, baselines):
    """Apply the same limits to checkpoint aggregates recorded at training time."""
    import numpy as np
    violation = 0.
    for name in ("actuated", "fixed_time"):
        baseline_rows = baselines[name]
        for scenario in RESEARCH_SCENARIOS:
            b = [row for row in baseline_rows if row["scenario"] == scenario]
            c = candidate[scenario]
            means = {key: float(np.mean([row[key] for row in b])) for key in c}
            ratios = [c["delay_per_scheduled_s"] / max(1e-12, means["delay_per_scheduled_s"]) / 1.05,
                      means["completed"] * .98 / max(1., c["completed"])]
            for key in ("p95_wait_s", "worst_approach_wait_s", "max_approach_p95_wait_s"):
                tolerance = max(.1 * means[key], 1.)
                ratios.append(max(0., (c[key] - means[key]) / tolerance))
            violation = max(violation, *(max(0., ratio - 1.) for ratio in ratios))
        overall_candidate = float(np.mean([candidate[s]["delay_per_scheduled_s"] for s in RESEARCH_SCENARIOS]))
        overall_baseline = score(baseline_rows)
        violation = max(violation, max(0., overall_candidate / max(1e-12, overall_baseline) - 1.02))
    return violation


class Campaign:
    def __init__(self, config, output, max_seconds=7200):
        self.config, self.root = config, Path(output)
        self.root.mkdir(parents=True, exist_ok=True)
        path = self.root / "config.json"
        if path.exists() and json.loads(path.read_text()) != config:
            raise ValueError("Cannot resume with a different experiment configuration")
        path.write_text(json.dumps(config, indent=2))
        self.deadline = time.monotonic() + max_seconds

    def evaluate(self, name, controller, split, seeds=None, scenarios=None):
        seeds = list(seeds if seeds is not None else SEED_SPLITS[split])
        scenarios = list(scenarios if scenarios is not None else RESEARCH_SCENARIOS)
        if not set(seeds) <= set(SEED_SPLITS[split]):
            raise ValueError("Seed leakage across research splits")
        rows = []
        environment_hashes = {k: file_hash(self.config["environment"][k]) for k in ("network_path", "topology_path")}
        signature = digest({"config": self.config, "controller": controller, "split": split,
                            "scenarios": scenarios,
                            "inputs": environment_hashes,
                            "model_hash": file_hash(controller["model_path"]) if controller.get("model_path") else None,
                            "implementation": {path: file_hash(path) for path in (
                                "src/simulation/runtime.py", "src/control/controllers.py",
                                "src/control/fair_cycle.py", "src/control/research.py",
                                "src/control/factory.py", "src/rl/sumo_env.py",
                                "src/rl/shared_dqn.py", "src/rl/benchmark.py",
                                "contracts/research.py", "contracts/scenarios.py",
                                "contracts/schemas/telemetry.json")}})
        for scenario in scenarios:
            for seed in seeds:
                directory = self.root / split / name / f"{scenario}-{seed}"
                metrics, identity = directory / "metrics.json", directory / "identity.json"
                if metrics.exists():
                    if not identity.exists() or json.loads(identity.read_text())["signature"] != signature:
                        raise ValueError("Cached benchmark case does not match frozen inputs")
                    row = json.loads(metrics.read_text())
                    if not row["valid"]:
                        raise ValueError("Refusing an invalid cached case")
                else:
                    if time.monotonic() >= self.deadline:
                        raise TimeoutError("Evaluation budget exhausted; rerun the same command to resume")
                    if directory.exists():
                        raise ValueError(f"Incomplete case retained at {directory}; inspect failure before rerunning in a new output")
                    row = run_case(self.config, controller, scenario, seed, directory)
                    identity.write_text(json.dumps({"signature": signature}, indent=2))
                    print(f"{split}/{name}/{scenario}/{seed}: delay={row['delay_per_scheduled_s']:.2f}", flush=True)
                rows.append(row)
        return rows

    def run(self, training_root, fair_training_root=None):
        if fair_training_root is None:
            raise ValueError("A completed fair-cycle RL training root is required for the next campaign")
        frozen_path = self.root / "frozen.json"
        if frozen_path.exists():
            frozen = json.loads(frozen_path.read_text())
            if not any(spec.get("type") == "fair_cycle_rl" for spec in frozen.get("controllers", {}).values()):
                raise ValueError("This output contains an earlier DQN campaign; choose a fresh campaign directory")
        else:
            fixed = fixed_candidates()
            fixed_scores = {name: score(self.evaluate(name, spec, "train", SEED_SPLITS["train"][:3]))
                            for name, spec in fixed.items()}
            fixed_name = min(fixed_scores, key=fixed_scores.get)
            fair = fair_cycle_candidates()
            fair_train_scores = {name: score(self.evaluate(name, spec, "train", SEED_SPLITS["train"][:3]))
                                 for name, spec in fair.items()}
            fair_validation = {name: self.evaluate(name, spec, "validation") for name, spec in fair.items()}
            fair_name = min(fair_validation, key=lambda name: score(fair_validation[name]))
            archived = yaml.safe_load(Path("configs/controllers/edgeflow_v2.yaml").read_text())["parameters"]
            edges = {"edgeflow_default": {"type": "edgeflow"},
                     "edgeflow_archived": {"type": "edgeflow", "parameters": archived}}
            edge_scores = {name: score(self.evaluate(name, spec, "validation")) for name, spec in edges.items()}
            edge_name = min(edge_scores, key=edge_scores.get)
            controllers = {"fixed_time": fixed[fixed_name], "actuated": {"type": "actuated"},
                           "max_queue": {"type": "max_queue"}, "max_pressure": {"type": "max_pressure"},
                           "edgeflow": edges[edge_name], "fair_cycle": fair[fair_name]}
            validation_rows = {"fixed_time": self.evaluate("selected-fixed-time", controllers["fixed_time"], "validation"),
                               "actuated": self.evaluate("actuated-reference", controllers["actuated"], "validation")}
            validation_scores = {}
            model_hashes = {}
            learned = []
            for seed in (17, 29, 43):
                for kind, root in (("shared_dqn", training_root), ("fair_cycle_rl", fair_training_root)):
                    if root is None:
                        continue
                    folder = Path(root) / f"seed-{seed}"
                    training = json.loads((folder / "training.json").read_text())
                    if not training.get("validation"):
                        raise ValueError(f"{kind} seed {seed} has no validation checkpoint; training is incomplete")
                    checkpoints = training["validation"]
                    has_fair_metrics = all("scenario_metrics" in row for row in checkpoints)
                    if kind == "fair_cycle_rl" and not has_fair_metrics:
                        raise ValueError("Checkpoint validation lacks fairness metrics; retrain with the current evaluator")
                    selected = (min(checkpoints, key=lambda row: (
                        validation_summary_violation(row["scenario_metrics"], validation_rows), row["score"]))
                        if has_fair_metrics else min(checkpoints, key=lambda row: row["score"]))
                    model = selected["model_path"]
                    if file_hash(model) != selected["sha256"]:
                        raise ValueError("Selected training checkpoint changed")
                    key = f"{kind}_seed{seed}"
                    controllers[key] = {"type": kind, "model_path": model}
                    model_hashes[model] = file_hash(model)
                    validation_rows[key] = self.evaluate(key, controllers[key], "validation")
                    validation_scores[key] = score(validation_rows[key])
                    if kind == "fair_cycle_rl":
                        learned.append(key)
            violations = {name: validation_violation(validation_rows[name], validation_rows)
                          for name in learned}
            candidate = min(violations, key=lambda name: (violations[name], validation_scores[name]))
            frozen = {"selection_split": "validation", "candidate": candidate,
                      "model_hashes": model_hashes, "controllers": controllers,
                      "validation_scores": validation_scores, "fixed_training_scores": fixed_scores,
                      "fair_cycle_training_scores": fair_train_scores,
                      "fair_cycle_validation_scores": {k: score(v) for k, v in fair_validation.items()},
                      "validation_violations": violations,
                      "edgeflow_validation_scores": edge_scores, "config_sha256": digest(self.config)}
            frozen_path.write_text(json.dumps(frozen, indent=2))
        if digest(self.config) != frozen["config_sha256"]:
            raise ValueError("Frozen configuration changed")
        for path, expected in frozen["model_hashes"].items():
            if file_hash(path) != expected:
                raise ValueError("Frozen model changed after validation selection")
        results = {name: self.evaluate(name, spec, "holdout") for name, spec in frozen["controllers"].items()}
        gate = promotion_gate(results[frozen["candidate"]], results)
        robustness = {name: self.evaluate(name, spec, "holdout",
                                          scenarios=list(RESEARCH_ROBUSTNESS_SCENARIOS))
                      for name, spec in frozen["controllers"].items()}
        (self.root / "results.json").write_text(json.dumps(results, indent=2))
        (self.root / "robustness.json").write_text(json.dumps(robustness, indent=2))
        (self.root / "promotion.json").write_text(json.dumps(gate, indent=2))
        lines = ["# Corrected SUMO holdout comparison", "", f"Candidate: {frozen['candidate']}",
                 f"Promotion gate passed: {gate['promoted']}. Existing deployment default is unchanged.", "",
                 "| Controller | Delay / scheduled vehicle (s) | Completed trips | P95 wait (s) |",
                 "|---|---:|---:|---:|"]
        import numpy as np
        for name, rows in results.items():
            lines.append(f"| {name} | {score(rows):.3f} | {np.mean([r['completed'] for r in rows]):.1f} | "
                         f"{np.mean([r['p95_wait_s'] for r in rows]):.3f} |")
        lines.extend(["", "Supplemental mirrored-direction results: [robustness.json](robustness.json).",
                      "", "Evidence: [frozen selection](frozen.json), [raw metrics](results.json), "
                      "[promotion tests](promotion.json), [configuration](config.json).", "", *gate["reasons"]])
        (self.root / "report.md").write_text("\n".join(lines)+"\n")
        return gate


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--config", required=True)
    parser.add_argument("--output", required=True)
    parser.add_argument("--training-root", required=True)
    parser.add_argument("--fair-training-root")
    parser.add_argument("--max-seconds", type=int, default=7200)
    args = parser.parse_args()
    campaign = Campaign(json.loads(Path(args.config).read_text()), args.output, args.max_seconds)
    try:
        gate = campaign.run(args.training_root, args.fair_training_root)
        status = {"status": "complete", **gate}
    except BaseException as error:
        status = {"status": "incomplete", "promoted": False, "reason": str(error)}
        (campaign.root / "status.json").write_text(json.dumps(status, indent=2))
        raise
    (campaign.root / "status.json").write_text(json.dumps(status, indent=2))


if __name__ == "__main__":
    main()
