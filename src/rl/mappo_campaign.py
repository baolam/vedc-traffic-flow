"""Freeze validation-selected MAPPO actors and run a resumable holdout campaign."""

import argparse
import json
import os
import shutil
import time
from pathlib import Path

import numpy as np

from contracts.research import (GRAPH_MAPPO_PROTOCOL, GRAPH_MAPPO_SEED_SPLITS,
                                GRAPH_MAPPO_HORIZON, GRAPH_MAPPO_TIMING,
                                RESEARCH_SCENARIOS)
from src.rl.benchmark import (graph_communication_comparison,
                              graph_mappo_promotion_gate, score)
from src.rl.evaluation import case_signature, run_case_cached
from src.simulation.runtime import file_hash

LEARNER_SEEDS = (17, 29, 43)
ARCHITECTURES = ("graph_mappo", "local_mappo")
BASELINES = ("fair_cycle", "fair_cycle_dqn", "fixed_time", "actuated",
             "max_queue", "max_pressure", "edgeflow")
def _read_training(root, algorithm, seed):
    path = Path(root) / f"seed-{seed}" / "training.json"
    training = json.loads(path.read_text(encoding="utf-8"))
    if training.get("algorithm") != algorithm:
        raise ValueError(f"Unexpected learner in {path}")
    return training


def freeze_training_selections(graph_root, local_root, output):
    output = Path(output)
    output.mkdir(parents=True, exist_ok=False)
    training = {(algorithm, seed): _read_training(
        graph_root if algorithm == "graph_mappo" else local_root, algorithm, seed)
                for algorithm in ARCHITECTURES for seed in LEARNER_SEEDS}
    common_counts_by_seed, latest_counts_by_seed = {}, {}
    selected, latest_common = {}, {}
    model_dir = output / "models"
    model_dir.mkdir()
    for seed in LEARNER_SEEDS:
        common_counts = set.intersection(*(
            {int(row["episodes"]) for row in training[(algorithm, seed)]["validation"]}
            for algorithm in ARCHITECTURES))
        if not common_counts:
            raise ValueError(f"No shared validated episode count for learner seed {seed}")
        latest = max(common_counts)
        common_counts_by_seed[str(seed)] = sorted(common_counts)
        latest_counts_by_seed[str(seed)] = latest
        for algorithm in ARCHITECTURES:
            rows = {int(row["episodes"]): row for row in training[(algorithm, seed)]["validation"]
                    if int(row["episodes"]) in common_counts}
            for row in rows.values():
                model_path = Path(row["model_path"])
                if not model_path.is_file() or file_hash(model_path) != row["sha256"]:
                    raise ValueError(f"Validated model changed or is missing: {model_path}")
            chosen_episode, chosen = min(rows.items(), key=lambda item: (
                item[1]["gate_violation"], item[1]["score"],
                max(metric["p95_wait_s"] for metric in item[1]["scenario_metrics"].values())))
            name = f"{algorithm}_seed{seed}"
            destination = model_dir / f"{name}.json"
            shutil.copy2(chosen["model_path"], destination)
            digest = file_hash(destination)
            if digest != chosen["sha256"]:
                raise ValueError("Selected validation actor changed while being frozen")
            selected[name] = {"type": algorithm, "model_path": str(destination.resolve()),
                              "sha256": digest, "learner_seed": seed,
                              "episodes": chosen_episode, "gate_violation": chosen["gate_violation"],
                              "score": chosen["score"]}
            latest_row = rows[latest]
            latest_common[name] = {"model_path": latest_row["model_path"],
                                   "sha256": latest_row["sha256"],
                                   "episodes": latest, "gate_violation": latest_row["gate_violation"],
                                   "score": latest_row["score"],
                                   "scenario_metrics": latest_row["scenario_metrics"]}
    frozen = {"selection_split": "validation", "protocol": GRAPH_MAPPO_PROTOCOL,
              "paired_learner_seeds": list(LEARNER_SEEDS),
              "common_validated_episode_counts_by_seed": common_counts_by_seed,
              "latest_common_episode_count_by_seed": latest_counts_by_seed,
              "selected_models": selected, "latest_common_models": latest_common,
              "promoted": False}
    (output / "frozen.json").write_text(json.dumps(frozen, indent=2), encoding="utf-8")
    return frozen


def _case_signature(config, controller, scenario, seed):
    return case_signature(config, controller, scenario, seed)


def _run_case_cached(config, controller, scenario, seed, root, timeout_s=180., deadline=None):
    spec = {key: value for key, value in controller.items() if key != "name"}
    metrics, _ = run_case_cached(config, spec, scenario, seed, root,
                                 timeout_s=timeout_s, deadline=deadline)
    return metrics


def _freeze_inputs(frozen):
    for name, spec in frozen["selected_models"].items():
        if not Path(spec["model_path"]).is_file() or file_hash(spec["model_path"]) != spec["sha256"]:
            raise ValueError(f"Frozen actor changed after validation: {name}")


def run_holdout(config, frozen_path, output, max_seconds=9000, resume=False):
    if max_seconds <= 0:
        raise ValueError("Holdout time budget must be positive")
    frozen_path, output = Path(frozen_path), Path(output)
    frozen = json.loads(frozen_path.read_text(encoding="utf-8"))
    if frozen.get("selection_split") != "validation":
        raise ValueError("Holdout requires actors frozen on validation")
    if frozen.get("protocol") != GRAPH_MAPPO_PROTOCOL:
        raise ValueError("Frozen actors use a different Graph-MAPPO protocol")
    environment = config["environment"]
    if (environment.get("cycle_time_s") != GRAPH_MAPPO_TIMING["cycle_time_s"]
            or environment.get("min_green_share") != GRAPH_MAPPO_TIMING["min_green_share"]
            or environment.get("demand_s") != GRAPH_MAPPO_HORIZON["demand_s"]
            or environment.get("drain_s") != GRAPH_MAPPO_HORIZON["drain_s"]):
        raise ValueError("Holdout environment timing/horizon does not match the frozen MAPPO protocol")
    _freeze_inputs(frozen)
    if output.exists() and any(output.iterdir()) and not resume:
        raise ValueError("Holdout output already exists; pass --resume to continue it")
    if resume and not (output / "config.json").is_file():
        raise ValueError("Cannot resume holdout without its original campaign config")
    controllers = {name: {"name": name, "type": spec["type"], "model_path": spec["model_path"]}
                   for name, spec in frozen["selected_models"].items()}
    baseline_specs = config.get("baselines", {})
    missing = set(BASELINES) - set(baseline_specs)
    if missing:
        raise ValueError(f"Holdout config lacks frozen baselines: {sorted(missing)}")
    controllers.update({name: {"name": name, **spec} for name, spec in baseline_specs.items()})
    if set(controllers) != {*[f"{arch}_seed{seed}" for arch in ARCHITECTURES for seed in LEARNER_SEEDS], *BASELINES}:
        raise ValueError("Holdout controllers must be the six selected policies and seven frozen baselines")
    evaluation = config.get("evaluation", {})
    case_timeout_s = float(evaluation.get("case_timeout_s", 180.))
    if case_timeout_s <= 0:
        raise ValueError("Holdout per-case timeout must be positive")
    output.mkdir(parents=True, exist_ok=True)
    frozen_hash = file_hash(frozen_path)
    run_config = {"environment": config["environment"], "baselines": baseline_specs,
                  "evaluation": {"case_timeout_s": case_timeout_s},
                  "frozen_sha256": frozen_hash, "protocol": GRAPH_MAPPO_PROTOCOL}
    config_path = output / "config.json"
    if config_path.exists() and json.loads(config_path.read_text(encoding="utf-8")) != run_config:
        raise ValueError("Cannot resume holdout with changed configuration or selected actors")
    config_path.write_text(json.dumps(run_config, indent=2), encoding="utf-8")
    results, completed = {}, 0
    started = time.monotonic()
    deadline = started + max_seconds
    total = len(controllers) * len(RESEARCH_SCENARIOS) * len(GRAPH_MAPPO_SEED_SPLITS["holdout"])
    for name, controller in controllers.items():
        rows = []
        for scenario in RESEARCH_SCENARIOS:
            for seed in GRAPH_MAPPO_SEED_SPLITS["holdout"]:
                if time.monotonic() - started >= max_seconds:
                    status = {"status": "incomplete", "promoted": False,
                              "completed_cases": completed, "requested_cases": total,
                              "remaining_cases": total - completed,
                              "reason": "Holdout budget expired; rerun with the same frozen inputs to resume."}
                    results[name] = rows
                    (output / "results.json").write_text(json.dumps(results, indent=2), encoding="utf-8")
                    (output / "status.json").write_text(json.dumps(status, indent=2), encoding="utf-8")
                    return status
                try:
                    row = _run_case_cached(config, controller, scenario, seed, output / "cases",
                                           timeout_s=case_timeout_s, deadline=deadline)
                except Exception as error:
                    results[name] = rows
                    (output / "results.json").write_text(json.dumps(results, indent=2), encoding="utf-8")
                    status = {"status": "incomplete", "promoted": False,
                              "completed_cases": completed, "requested_cases": total,
                              "remaining_cases": total - completed,
                              "reason": str(error)}
                    (output / "status.json").write_text(json.dumps(status, indent=2), encoding="utf-8")
                    return status
                rows.append(row)
                completed += 1
                results[name] = rows
                (output / "results.json").write_text(json.dumps(results, indent=2), encoding="utf-8")
                (output / "status.json").write_text(json.dumps({"status": "running", "promoted": False,
                    "completed_cases": completed, "requested_cases": total}, indent=2), encoding="utf-8")

    references = {name: results[name] for name in ("fair_cycle", "edgeflow", "max_pressure", "actuated", "fixed_time")}
    promotions, graph_rows, local_rows = {}, {}, {}
    for seed in LEARNER_SEEDS:
        graph_name, local_name = f"graph_mappo_seed{seed}", f"local_mappo_seed{seed}"
        graph_rows[seed], local_rows[seed] = results[graph_name], results[local_name]
    for name in [f"{arch}_seed{seed}" for arch in ARCHITECTURES for seed in LEARNER_SEEDS]:
        promotions[name] = graph_mappo_promotion_gate(results[name], references)
    graph_contribution = graph_communication_comparison(graph_rows, local_rows)
    summary = {"policy_performance": {name: score(rows) for name, rows in results.items()},
               "graph_contribution": graph_contribution,
               "promotion_status": promotions,
               "any_policy_promoted": any(row["promoted"] for row in promotions.values()),
               "selected_models": frozen["selected_models"],
               "latest_common_validation": frozen["latest_common_models"],
               "holdout_protocol": GRAPH_MAPPO_PROTOCOL}
    (output / "summary.json").write_text(json.dumps(summary, indent=2), encoding="utf-8")
    lines = ["# Graph-MAPPO research campaign", "",
             "## Policy performance", "",
             "| Controller | Mean delay / scheduled vehicle (s) |",
             "|---|---:|"]
    lines.extend(f"| {name} | {value:.3f} |" for name, value in summary["policy_performance"].items())
    latest_common = summary["latest_common_validation"]
    lines.extend(["", "## Latest common checkpoints (validation only)", "",
                  "These validation-only results use each paired seed's latest checkpoint validated by both architectures; they are not holdout results.", "",
                  "| Learner seed | Controller | Selected episode | Latest common episode | Gate violation | Mean scenario delay (s) |",
                  "|---:|---|---:|---:|---:|---:|"])
    for seed in LEARNER_SEEDS:
        for architecture in ARCHITECTURES:
            name = f"{architecture}_seed{seed}"
            selected = summary["selected_models"][name]
            common = latest_common[name]
            scenario_delays = [metric["delay_per_scheduled_s"]
                               for metric in common["scenario_metrics"].values()]
            mean_scenario_delay = sum(scenario_delays) / len(scenario_delays)
            lines.append(f"| {seed} | {architecture} | {selected['episodes']} | {common['episodes']} | "
                         f"{common['gate_violation']:.3f} | {mean_scenario_delay:.3f} |")
    lines.extend(["", "## Graph communication", "",
                  f"Mean paired delay improvement: {graph_contribution['relative_delay_improvement']:.2%}; "
                  f"95% interval (seconds per vehicle): {graph_contribution['paired_delay_improvement_ci95_s']}.",
                  f"Graph value claim supported: {graph_contribution['graph_value_claim_supported']}.",
                  "", "| Learner seed | Mean paired improvement (s) | Relative improvement | 95% interval (s) | Guardrails pass |",
                  "|---:|---:|---:|---|---:|"])
    for seed in LEARNER_SEEDS:
        pair = graph_contribution["learner_pairs"][str(seed)]
        lines.append(f"| {seed} | {pair['mean_delay_improvement_s']:.3f} | "
                     f"{pair['relative_delay_improvement']:.2%} | "
                     f"{pair['paired_delay_improvement_ci95_s']} | "
                     f"{pair['fairness_throughput_guardrails_pass']} |")
    lines.extend(["", "Three learner seeds provide limited evidence about training variability.", "",
                  "## Promotion status", "",
                  f"Any selected policy passed every holdout gate: {summary['any_policy_promoted']}.",
                  "Each policy gate is recorded in [summary.json](summary.json).",
                  "The deployment default was not changed.", "",
                  f"Evidence: [frozen validation selection]({os.path.relpath(frozen_path.resolve(), output.resolve()).replace(os.sep, '/') }), "
                  "[raw holdout runs](results.json), [campaign configuration](config.json)."])
    (output / "report.md").write_text("\n".join(lines) + "\n", encoding="utf-8")
    status = {"status": "complete", "completed_cases": total, "requested_cases": total,
              "promoted": summary["any_policy_promoted"]}
    (output / "status.json").write_text(json.dumps(status, indent=2), encoding="utf-8")
    return status


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    commands = parser.add_subparsers(dest="command", required=True)
    freeze = commands.add_parser("freeze", help="Select paired validation checkpoints and copy six actors")
    freeze.add_argument("--graph-training-root", required=True)
    freeze.add_argument("--local-training-root", required=True)
    freeze.add_argument("--output", required=True)
    evaluate = commands.add_parser("holdout", help="Run the frozen, resumable holdout matrix")
    evaluate.add_argument("--config", required=True)
    evaluate.add_argument("--frozen", required=True)
    evaluate.add_argument("--output", required=True)
    evaluate.add_argument("--max-seconds", type=int, default=9000)
    evaluate.add_argument("--resume", action="store_true",
                          help="continue an incomplete holdout with the same frozen inputs")
    args = parser.parse_args()
    if args.command == "freeze":
        freeze_training_selections(args.graph_training_root, args.local_training_root, args.output)
    else:
        config = json.loads(Path(args.config).read_text(encoding="utf-8"))
        run_holdout(config, args.frozen, args.output, args.max_seconds, args.resume)


if __name__ == "__main__":
    main()
