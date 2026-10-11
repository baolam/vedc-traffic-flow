"""Freeze validation-selected MAPPO actors and run a resumable holdout campaign."""

import argparse
import concurrent.futures
import hashlib
import json
import os
import shutil
import subprocess
import sys
import threading
import time
import traceback
from pathlib import Path

import numpy as np

from contracts.research import (GRAPH_MAPPO_PROTOCOL, GRAPH_MAPPO_SEED_SPLITS,
                                GRAPH_MAPPO_HORIZON, GRAPH_MAPPO_TIMING,
                                GRAPH_MAPPO_SELECTION_SPEC, RESEARCH_SCENARIOS)
from src.rl.benchmark import (graph_communication_comparison,
                              graph_mappo_promotion_gate, score)
from src.rl.evaluation import case_signature, evaluate_cases, run_case_cached
from src.simulation.runtime import file_hash

LEARNER_SEEDS = (17, 29, 43)
ARCHITECTURES = ("graph_mappo", "local_mappo")
BASELINES = ("fair_cycle", "fair_cycle_dqn", "fixed_time", "actuated",
             "max_queue", "max_pressure", "edgeflow")
CAMPAIGN_STAGES = (("preflight", 1800), ("pilots", 3600),
                   ("training", 21600), ("selection_holdout", 9000))
CAMPAIGN_BUDGET_S = sum(seconds for _, seconds in CAMPAIGN_STAGES)


def _write_json(path, value):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = Path(str(path) + ".tmp")
    temporary.write_text(json.dumps(value, indent=2, allow_nan=False), encoding="utf-8")
    temporary.replace(path)


def _resolve_config_paths(config, base):
    """Resolve file inputs relative to the config, so CLI cwd is immaterial."""
    config = json.loads(json.dumps(config))
    for section, keys in (("environment", ("topology_path", "network_path")),):
        for key in keys:
            value = config.get(section, {}).get(key)
            if value and not Path(value).is_absolute():
                config[section][key] = str((base / value).resolve())
    for spec in config.get("baselines", {}).values():
        value = spec.get("model_path")
        if value and not Path(value).is_absolute():
            spec["model_path"] = str((base / value).resolve())
    return config


def _canonical_hash(value):
    return hashlib.sha256(json.dumps(value, sort_keys=True, separators=(",", ":")).encode()).hexdigest()


def _baseline_identity(specs):
    identity = {}
    for name, spec in sorted(specs.items()):
        model_path = spec.get("model_path")
        identity[name] = {"type": spec["type"], "parameters": spec.get("parameters"),
                          "model_sha256": file_hash(model_path) if model_path else None}
    return _canonical_hash(identity)


def freeze_baseline_inputs(config, output):
    """Copy and hash baseline models before training can change their sources."""
    output = Path(output)
    output.mkdir(parents=True, exist_ok=True)
    specs = json.loads(json.dumps(config["baselines"]))
    if set(specs) != set(BASELINES):
        raise ValueError("Campaign requires all seven frozen baseline specifications")
    for name, spec in specs.items():
        model_path = spec.get("model_path")
        if model_path:
            source = Path(model_path)
            if not source.is_file():
                raise FileNotFoundError(f"Baseline model is missing: {source}")
            destination = output / "models" / f"{name}{source.suffix or '.json'}"
            destination.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(source, destination)
            spec["model_path"] = str(destination.resolve())
    environment = config["environment"]
    frozen = {"version": 1, "baseline_specs": specs,
              "baseline_sha256": _baseline_identity(specs),
              "environment": environment,
              "topology_sha256": file_hash(environment["topology_path"]),
              "network_sha256": file_hash(environment["network_path"])}
    from src.simulation.build_network import binary
    binary_path = binary("sumo")
    frozen["sumo_executable"] = str(Path(binary_path).resolve())
    frozen["sumo_sha256"] = file_hash(binary_path)
    _write_json(output / "baseline-inputs.json", frozen)
    return frozen
def _read_training(root, algorithm, seed):
    path = Path(root) / f"seed-{seed}" / "training.json"
    training = json.loads(path.read_text(encoding="utf-8"))
    if training.get("algorithm") != algorithm:
        raise ValueError(f"Unexpected learner in {path}")
    return training


def freeze_training_selections(graph_root, local_root, output, baseline_inputs=None):
    output = Path(output)
    output.mkdir(parents=True, exist_ok=True)
    training = {(algorithm, seed): _read_training(
        graph_root if algorithm == "graph_mappo" else local_root, algorithm, seed)
                for algorithm in ARCHITECTURES for seed in LEARNER_SEEDS}
    if any(item.get("selection_rule_version") != GRAPH_MAPPO_SELECTION_SPEC["version"]
           for item in training.values()):
        raise ValueError("Training summaries use an outdated or missing selection rule")
    common_counts_by_seed, latest_counts_by_seed = {}, {}
    selected, latest_common = {}, {}
    model_dir = output / "models"
    model_dir.mkdir(exist_ok=True)
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
                if row.get("selection_rule_version") != GRAPH_MAPPO_SELECTION_SPEC["version"]:
                    raise ValueError("A validated checkpoint uses an outdated selection rule")
                model_path = Path(row["model_path"])
                if not model_path.is_file() or file_hash(model_path) != row["sha256"]:
                    raise ValueError(f"Validated model changed or is missing: {model_path}")
            chosen_episode, chosen = min(rows.items(), key=lambda item: (
                item[1]["gate_violation"], item[1]["score"],
                max(metric["p95_wait_s"] for metric in item[1]["scenario_metrics"].values()),
                item[0]))
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
            latest_destination = model_dir / "latest-common" / f"{name}.json"
            latest_destination.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(latest_row["model_path"], latest_destination)
            if file_hash(latest_destination) != latest_row["sha256"]:
                raise ValueError("Latest common validation actor changed while being frozen")
            latest_common[name] = {"model_path": str(latest_destination.resolve()),
                                   "source_model_path": latest_row["model_path"],
                                   "sha256": latest_row["sha256"],
                                   "episodes": latest, "gate_violation": latest_row["gate_violation"],
                                   "score": latest_row["score"],
                                   "scenario_metrics": latest_row["scenario_metrics"]}
    frozen = {"selection_split": "validation", "protocol": GRAPH_MAPPO_PROTOCOL,
              "selection_rule_version": GRAPH_MAPPO_SELECTION_SPEC["version"],
              "paired_learner_seeds": list(LEARNER_SEEDS),
              "common_validated_episode_counts_by_seed": common_counts_by_seed,
              "latest_common_episode_count_by_seed": latest_counts_by_seed,
              "selected_models": selected, "latest_common_models": latest_common,
              "promoted": False}
    if baseline_inputs is not None:
        baseline_inputs = (json.loads(Path(baseline_inputs).read_text(encoding="utf-8"))
                           if isinstance(baseline_inputs, (str, Path)) else baseline_inputs)
        for name, spec in baseline_inputs["baseline_specs"].items():
            model_path = spec.get("model_path")
            if model_path and not Path(model_path).is_file():
                raise FileNotFoundError(f"Frozen baseline model is missing: {name}")
        if baseline_inputs["baseline_sha256"] != _baseline_identity(baseline_inputs["baseline_specs"]):
            raise ValueError("Frozen baseline model changed before selection was frozen")
        frozen["baseline_specs"] = baseline_inputs["baseline_specs"]
        frozen["baseline_sha256"] = baseline_inputs["baseline_sha256"]
        frozen["frozen_environment"] = {key: baseline_inputs[key] for key in
                                         ("environment", "topology_sha256", "network_sha256",
                                          "sumo_executable", "sumo_sha256")}
    _write_json(output / "frozen.json", frozen)
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


def _validate_frozen_baselines(config, frozen):
    baseline_specs = frozen.get("baseline_specs")
    if not isinstance(baseline_specs, dict) or set(baseline_specs) != set(BASELINES):
        raise ValueError("Frozen selection must include all seven baseline specifications")
    if frozen.get("baseline_sha256") != _baseline_identity(baseline_specs):
        raise ValueError("Frozen baseline configuration or model hash changed")
    for name, spec in baseline_specs.items():
        model_path = spec.get("model_path")
        if model_path and not Path(model_path).is_file():
            raise FileNotFoundError(f"Frozen baseline model is missing: {name}")
    environment = config["environment"]
    snapshot = frozen.get("frozen_environment")
    if not snapshot:
        raise ValueError("Frozen selection has no environment and SUMO provenance")
    source = snapshot.get("environment", {})
    for key, value in source.items():
        if environment.get(key) != value:
            raise ValueError(f"Holdout {key} differs from the frozen campaign")
    for key, digest_key in (("topology_path", "topology_sha256"),
                            ("network_path", "network_sha256")):
        path = environment.get(key)
        if (not path or not Path(path).is_file()
                or file_hash(path) != snapshot.get(digest_key)):
            raise ValueError(f"Holdout {key} differs from the frozen campaign")
    sumo_path = snapshot.get("sumo_executable")
    if (not sumo_path or not Path(sumo_path).is_file()
            or file_hash(sumo_path) != snapshot.get("sumo_sha256")):
        raise ValueError("SUMO executable differs from the frozen campaign")
    return baseline_specs


def _load_completed_holdout(path, controllers, cases):
    if not path.is_file():
        return {name: [] for name in controllers}, set()
    saved = json.loads(path.read_text(encoding="utf-8"))
    if set(saved) - set(controllers):
        raise ValueError("Resumed holdout contains unknown controllers")
    expected = set(cases)
    results, completed = {name: [] for name in controllers}, set()
    for name, rows in saved.items():
        for row in rows:
            key = (name, row.get("scenario"), row.get("seed"))
            if key not in expected or key in completed:
                raise ValueError("Resumed holdout contains duplicate or unexpected cases")
            if not row.get("valid") or any(row.get(field, 0) for field in
                                            ("collisions", "teleports", "accounting_losses")):
                raise ValueError("Resumed holdout contains an invalid or unsafe case")
            metric_fields = ("delay_per_scheduled_s", "completed", "p95_wait_s",
                             "worst_approach_wait_s", "max_approach_p95_wait_s",
                             "scheduled", "demand_s", "drain_s")
            if (any(field not in row or not np.isfinite(float(row[field]))
                    for field in metric_fields) or row["scheduled"] <= 0):
                raise ValueError("Resumed holdout contains missing or non-finite metrics")
            controller = controllers[name]
            expected_identity = {field: controller[field] for field in
                                 ("type", "parameters", "model_path") if field in controller}
            if row.get("controller") is not None and row["controller"] != expected_identity:
                raise ValueError("Resumed holdout case was produced by a different controller")
            model_path = controller.get("model_path")
            if model_path and row.get("model_sha256") != file_hash(model_path):
                raise ValueError("Resumed holdout actor hash differs from its frozen model")
            completed.add(key)
            results[name].append(row)
    for rows in results.values():
        rows.sort(key=lambda row: (tuple(RESEARCH_SCENARIOS).index(row["scenario"]), row["seed"]))
    return results, completed


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
    baseline_specs = _validate_frozen_baselines(config, frozen)
    if output.exists() and any(output.iterdir()) and not resume:
        raise ValueError("Holdout output already exists; pass --resume to continue it")
    if resume and not (output / "config.json").is_file():
        raise ValueError("Cannot resume holdout without its original campaign config")
    controllers = {name: {"name": name, "type": spec["type"], "model_path": spec["model_path"]}
                   for name, spec in frozen["selected_models"].items()}
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
                  "frozen_sha256": frozen_hash,
                  "baseline_sha256": frozen["baseline_sha256"],
                  "sumo_sha256": frozen["frozen_environment"]["sumo_sha256"],
                  "protocol": GRAPH_MAPPO_PROTOCOL}
    config_path = output / "config.json"
    if config_path.exists() and json.loads(config_path.read_text(encoding="utf-8")) != run_config:
        raise ValueError("Cannot resume holdout with changed configuration or selected actors")
    _write_json(config_path, run_config)
    cases = [(name, scenario, seed) for name in controllers
             for scenario in RESEARCH_SCENARIOS
             for seed in GRAPH_MAPPO_SEED_SPLITS["holdout"]]
    results, completed_cases = _load_completed_holdout(output / "results.json", controllers, cases)
    started = time.monotonic()
    deadline = started + max_seconds
    total = len(cases)
    pending = [case for case in cases if case not in completed_cases]
    errors = []
    pool = concurrent.futures.ThreadPoolExecutor(max_workers=2)
    active = {}
    next_case = 0
    try:
        while next_case < len(pending) or active:
            while next_case < len(pending) and len(active) < 2 and time.monotonic() < deadline:
                name, scenario, seed = pending[next_case]
                next_case += 1
                remaining = deadline - time.monotonic()
                if remaining <= 0:
                    break
                controller_timeout = min(case_timeout_s, remaining)
                future = pool.submit(_run_case_cached, config, controllers[name], scenario, seed,
                                     output / "cases", controller_timeout, deadline)
                active[future] = (name, scenario, seed)
            if not active:
                break
            done, _ = concurrent.futures.wait(
                active, timeout=max(0., min(.5, deadline - time.monotonic())),
                return_when=concurrent.futures.FIRST_COMPLETED)
            for future in done:
                name, scenario, seed = active.pop(future)
                try:
                    row = future.result()
                except Exception as error:
                    errors.append({"controller": name, "scenario": scenario,
                                   "seed": seed, "reason": str(error)})
                    continue
                results[name].append(row)
                results[name].sort(key=lambda item: (tuple(RESEARCH_SCENARIOS).index(item["scenario"]),
                                                     item["seed"]))
                completed_cases.add((name, scenario, seed))
                _write_json(output / "results.json", results)
                _write_json(output / "status.json", {
                    "status": "running", "promoted": False,
                    "completed_cases": len(completed_cases), "requested_cases": total,
                    "remaining_cases": total - len(completed_cases),
                    "workers": 2, "errors": errors})
            if errors or time.monotonic() >= deadline:
                for future in active:
                    future.cancel()
                break
    finally:
        pool.shutdown(wait=True, cancel_futures=True)

    _write_json(output / "results.json", results)
    if errors or completed_cases != set(cases):
        status = {"status": "incomplete", "promoted": False,
                  "completed_cases": len(completed_cases), "requested_cases": total,
                  "remaining_cases": total - len(completed_cases),
                  "reason": errors[0]["reason"] if errors else "Holdout budget expired; rerun with --resume.",
                  "errors": errors}
        _write_json(output / "status.json", status)
        return status

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
    _write_json(output / "summary.json", summary)
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
        pair = graph_contribution["learner_pairs"][seed]
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
    _write_json(output / "status.json", status)
    return status


def _sync_device(device):
    import torch
    if str(device).startswith("cuda") and torch.cuda.is_available():
        torch.cuda.synchronize(device)


def benchmark_batched_actor(config):
    """Measure batched actor throughput against repeated single-graph calls."""
    import statistics
    import torch
    from contracts.research import build_research_graph
    from src.rl.graph_mappo import GraphActor

    training_config = config["training_configs"]["graph_mappo"]
    model_config = json.loads(Path(training_config).read_text(encoding="utf-8"))
    device_name = model_config["training"].get("device", "cpu")
    if device_name == "cuda" and not torch.cuda.is_available():
        raise RuntimeError("Campaign requests CUDA but CUDA is unavailable")
    device = torch.device(device_name)
    env = model_config["environment"]
    topology = json.loads(Path(env["topology_path"]).read_text(encoding="utf-8"))
    actor = GraphActor(build_research_graph(topology), device=device).eval()
    generator = torch.Generator(device=device).manual_seed(19)
    timings, parity = {}, {}
    with torch.inference_mode():
        for batch_size in (1, 2, 32):
            observations = torch.randn(batch_size, 4, 52, generator=generator, device=device)
            for _ in range(4):
                actor(observations)
                _sync_device(device)
            batched_output = actor(observations)
            serial_output = torch.stack([actor(observations[index]) for index in range(batch_size)])
            parity[str(batch_size)] = float((batched_output - serial_output).abs().max().item())
            batched_times, serial_times = [], []
            for _ in range(15):
                _sync_device(device)
                start = time.perf_counter()
                actor(observations)
                _sync_device(device)
                batched_times.append(time.perf_counter() - start)
                start = time.perf_counter()
                for index in range(batch_size):
                    actor(observations[index])
                _sync_device(device)
                serial_times.append(time.perf_counter() - start)
            batched_median = statistics.median(batched_times)
            serial_median = statistics.median(serial_times)
            timings[str(batch_size)] = {"batched_median_s": batched_median,
                                       "serial_median_s": serial_median,
                                       "speedup": serial_median / max(batched_median, 1e-12)}
    return {"device": str(device), "timings": timings, "max_abs_parity_error": parity,
            "batch32_speedup": timings["32"]["speedup"]}


def run_preflight(config, output, frozen_baselines):
    output = Path(output)
    output.mkdir(parents=True, exist_ok=True)
    holdout_path = Path(config["holdout_config"])
    holdout = _resolve_config_paths(json.loads(holdout_path.read_text(encoding="utf-8")),
                                    Path(__file__).resolve().parents[2])
    if (holdout["environment"].get("cycle_time_s") != GRAPH_MAPPO_TIMING["cycle_time_s"]
            or holdout["environment"].get("min_green_share") != GRAPH_MAPPO_TIMING["min_green_share"]
            or holdout["environment"].get("demand_s") != GRAPH_MAPPO_HORIZON["demand_s"]
            or holdout["environment"].get("drain_s") != GRAPH_MAPPO_HORIZON["drain_s"]):
        raise ValueError("Preflight found a timing or horizon mismatch")
    if frozen_baselines["baseline_sha256"] != _baseline_identity(frozen_baselines["baseline_specs"]):
        raise ValueError("Frozen baseline preparation did not retain its source identity")
    baseline = frozen_baselines["baseline_specs"]["fair_cycle"]
    if baseline.get("parameters") != {"cycle_time_s": 90, "min_green_share": .25}:
        raise ValueError("Preflight requires the matched 90-second fair-cycle baseline")
    environment = holdout["environment"]
    evaluation = holdout.get("evaluation", {})
    validation_started = time.monotonic()
    rows, diagnostics = evaluate_cases(
        holdout, baseline, RESEARCH_SCENARIOS, GRAPH_MAPPO_SEED_SPLITS["validation"],
        output / "fair-cycle-validation", cache_root=output / "case-cache", workers=2,
        timeout_s=float(evaluation.get("case_timeout_s", 180.)),
        deadline=time.monotonic() + float(config.get("preflight_case_timeout_s", 1650.)))
    if len(rows) != len(RESEARCH_SCENARIOS) * len(GRAPH_MAPPO_SEED_SPLITS["validation"]):
        raise ValueError("Fair-cycle preflight did not complete its paired validation matrix")
    for row in rows:
        if (not row.get("valid") or row.get("controller_timing") != {
                "cycle_time_s": 90, "min_green_share": .25}
                or any(row.get(key, 0) for key in ("collisions", "teleports", "accounting_losses"))):
            raise ValueError("Fair-cycle preflight failed timing, safety, or accounting checks")
    speed = benchmark_batched_actor(config)
    if any(value > 1e-5 for value in speed["max_abs_parity_error"].values()):
        raise ValueError("Batched and single-graph actor outputs are not numerically equivalent")
    if speed["batch32_speedup"] < float(config.get("minimum_batch32_speedup", 2.)):
        raise ValueError("Batched actor throughput did not meet the configured 32-graph speedup target")
    _write_json(output / "preflight.json", {
        "status": "complete", "baseline_sha256": frozen_baselines["baseline_sha256"],
        "environment": environment, "fair_cycle_validation_cases": len(rows),
        "fair_cycle_evaluation": diagnostics,
        "fair_cycle_elapsed_s": time.monotonic() - validation_started,
        "batched_actor_benchmark": speed})
    return {"status": "complete", "fair_cycle_validation_cases": len(rows),
            "batched_actor_benchmark": speed}


def _campaign_initial_state(config_hash):
    return {"version": 1, "config_sha256": config_hash,
            "budget_seconds": CAMPAIGN_BUDGET_S, "active_elapsed_s": 0.,
            "stages": {name: {"status": "pending", "elapsed_s": 0.}
                       for name, _ in CAMPAIGN_STAGES},
            "training_runs": {}, "status": "incomplete", "updated_at": time.time()}


def _persist_campaign(path, state):
    state["updated_at"] = time.time()
    state["remaining_s"] = max(0., state["budget_seconds"] - state["active_elapsed_s"])
    _write_json(path, state)


def _start_campaign_heartbeat(state, state_path, stage_name):
    """Persist active campaign time while an in-process stage is running."""
    stopped = threading.Event()
    stage = state["stages"][stage_name]
    lock = threading.Lock()
    previous = [time.monotonic()]

    def tick():
        with lock:
            now = time.monotonic()
            delta = max(0., now - previous[0])
            previous[0] = now
            stage["elapsed_s"] += delta
            state["active_elapsed_s"] += delta
            _persist_campaign(state_path, state)

    def run():
        while not stopped.wait(5.):
            tick()

    thread = threading.Thread(target=run, name=f"campaign-clock-{stage_name}", daemon=True)
    thread.start()

    def stop():
        stopped.set()
        thread.join()
        tick()

    return stop


def _run_campaign_child(command, log_path, state, state_path, stage_name,
                        stage_budget, process_cap):
    stage = state["stages"][stage_name]
    remaining = min(stage_budget - stage["elapsed_s"],
                    state["budget_seconds"] - state["active_elapsed_s"], process_cap)
    if remaining <= 0:
        return {"status": "budget_exhausted", "returncode": None}
    log_path = Path(log_path)
    log_path.parent.mkdir(parents=True, exist_ok=True)
    started = time.monotonic()
    accounted_s = 0.
    job = None

    def account_elapsed():
        nonlocal accounted_s
        elapsed = time.monotonic() - started
        delta = max(0., elapsed - accounted_s)
        accounted_s = elapsed
        stage["elapsed_s"] += delta
        state["active_elapsed_s"] += delta
        _persist_campaign(state_path, state)

    with log_path.open("ab") as log:
        process = subprocess.Popen(command, stdout=log, stderr=subprocess.STDOUT,
                                   cwd=Path(__file__).resolve().parents[2])
        try:
            if os.name == "nt":
                from src.rl.evaluation import _WindowsJob
                job = _WindowsJob()
                job.assign(process.pid)
            while process.poll() is None:
                account_elapsed()
                elapsed = time.monotonic() - started
                if elapsed >= remaining and process.poll() is None:
                    # The learner has its own matching time cap and normally exits here.
                    # Keep a short allowance for checkpoint and result serialization.
                    process.wait(timeout=30)
                    break
                time.sleep(min(5., max(.1, remaining - elapsed)))
            account_elapsed()
            return {"status": "complete" if process.returncode == 0 else "failed",
                    "returncode": process.returncode,
                    "elapsed_s": min(time.monotonic() - started, remaining + 30.)}
        except subprocess.TimeoutExpired:
            if job is not None:
                job.terminate()
                job.close()
                job = None
            process.terminate()
            try:
                process.wait(timeout=10)
            except subprocess.TimeoutExpired:
                process.kill()
                process.wait()
            return {"status": "incomplete", "returncode": process.returncode,
                    "reason": "Campaign stage budget expired while learner was still running"}
        except BaseException:
            if job is not None:
                job.terminate()
                job.close()
                job = None
            if process.poll() is None:
                process.terminate()
                try:
                    process.wait(timeout=10)
                except subprocess.TimeoutExpired:
                    process.kill()
                    process.wait()
            raise
        finally:
            if job is not None:
                job.close()
            account_elapsed()


def _training_run(config_path, output, seed, run_seconds, state, state_path,
                  stage_name, stage_budget):
    output = Path(output)
    config = json.loads(Path(config_path).read_text(encoding="utf-8"))
    training_json = output / f"seed-{seed}" / "training.json"
    if training_json.is_file():
        prior = json.loads(training_json.read_text(encoding="utf-8"))
        if prior.get("status") in ("time_cap", "episode_cap", "time_cap_before_pending_validation",
                                    "time_cap_during_validation"):
            return {"status": "complete", "training": prior}
    checkpoint = output / f"seed-{seed}" / "checkpoint.pt"
    command = [sys.executable, "-m", "src.rl.train_mappo", "--config", str(Path(config_path).resolve()),
               "--output", str(output.resolve()), "--seed", str(seed)]
    if checkpoint.is_file():
        command.extend(("--resume", str(checkpoint.resolve())))
    result = _run_campaign_child(command, output / f"seed-{seed}" / "campaign.log",
                                 state, state_path, stage_name, stage_budget, run_seconds)
    state["training_runs"][f"{output.name}_seed{seed}"] = result
    _persist_campaign(state_path, state)
    if result["status"] != "complete":
        return result
    if training_json.is_file():
        result["training"] = json.loads(training_json.read_text(encoding="utf-8"))
    return result


def run_campaign(config_path, output, resume=False):
    config_path, output = Path(config_path).resolve(), Path(output).resolve()
    root = Path(__file__).resolve().parents[2]

    def resolve_root_path(value):
        path = Path(value)
        return path.resolve() if path.is_absolute() else (root / path).resolve()

    config = json.loads(config_path.read_text(encoding="utf-8"))
    if int(config.get("budget_seconds", CAMPAIGN_BUDGET_S)) != CAMPAIGN_BUDGET_S:
        raise ValueError("The research campaign budget is fixed at ten active hours")
    config_hash = _canonical_hash({"config": config, "config_file_sha256": file_hash(config_path),
                                  "training_config_hashes": {
                                      name: file_hash(resolve_root_path(path))
                                      for name, path in config["training_configs"].items()},
                                  "holdout_config_sha256": file_hash(resolve_root_path(
                                      config["holdout_config"]))})
    state_path = output / "campaign-state.json"
    if state_path.is_file():
        if not resume:
            raise ValueError("Campaign output already exists; pass --resume to continue")
        state = json.loads(state_path.read_text(encoding="utf-8"))
        if state.get("config_sha256") != config_hash:
            raise ValueError("Cannot resume campaign with changed protocol or input configs")
    else:
        if output.exists() and any(output.iterdir()):
            raise ValueError("Campaign output already contains files but no resumable state")
        output.mkdir(parents=True, exist_ok=True)
        state = _campaign_initial_state(config_hash)
        _persist_campaign(state_path, state)

    holdout_config = _resolve_config_paths(
        json.loads(resolve_root_path(config["holdout_config"]).read_text(encoding="utf-8")), root)
    preflight_stage = state["stages"]["preflight"]
    baseline_dir = output / "frozen-baselines"
    if baseline_dir.joinpath("baseline-inputs.json").is_file():
        baseline_inputs = json.loads(baseline_dir.joinpath("baseline-inputs.json").read_text(encoding="utf-8"))
        if baseline_inputs["baseline_sha256"] != _baseline_identity(baseline_inputs["baseline_specs"]):
            raise ValueError("Frozen baseline input changed during campaign resume")
    else:
        stop_clock = _start_campaign_heartbeat(state, state_path, "preflight")
        try:
            baseline_inputs = freeze_baseline_inputs(holdout_config, baseline_dir)
        finally:
            stop_clock()

    if preflight_stage["status"] != "complete":
        preflight_stage["status"] = "running"
        _persist_campaign(state_path, state)
        remaining = min(1800. - preflight_stage["elapsed_s"],
                        state["budget_seconds"] - state["active_elapsed_s"])
        if remaining <= 0:
            preflight_stage["status"] = "incomplete"
            _persist_campaign(state_path, state)
            return state
        stop_clock = _start_campaign_heartbeat(state, state_path, "preflight")
        try:
            preflight = run_preflight(config, output / "preflight", baseline_inputs)
            preflight_stage["status"] = preflight["status"]
            state["preflight"] = preflight
        except Exception as error:
            preflight_stage["status"] = "failed"
            state["failure"] = {"stage": "preflight", "reason": str(error),
                                 "traceback": traceback.format_exc()}
            stop_clock()
            _persist_campaign(state_path, state)
            return state
        stop_clock()
        _persist_campaign(state_path, state)

    training_config_paths = {}
    for architecture, source in config["training_configs"].items():
        training_config_paths[architecture] = resolve_root_path(source)

    pilots = state["stages"]["pilots"]
    if pilots["status"] != "complete":
        pilots["status"] = "running"
        _persist_campaign(state_path, state)
        for architecture in ARCHITECTURES:
            task_key = f"pilot_{architecture}_seed11"
            run_config_path = output / "run-configs" / f"{task_key}.json"
            if not run_config_path.exists():
                run_config = json.loads(training_config_paths[architecture].read_text(encoding="utf-8"))
                run_config["training"]["max_seconds"] = 1800
                run_config["training"]["max_episodes"] = 128
                _write_json(run_config_path, run_config)
            result = _training_run(run_config_path, output / "pilot" / architecture, 11,
                                   1800, state, state_path, "pilots", 3600)
            if result["status"] != "complete":
                pilots["status"] = "incomplete"
                state["failure"] = {"stage": "pilots", "task": task_key, **result}
                _persist_campaign(state_path, state)
                return state
        pilots["status"] = "complete"
        _persist_campaign(state_path, state)

    training_stage = state["stages"]["training"]
    if training_stage["status"] != "complete":
        training_stage["status"] = "running"
        order = [(architecture, seed) for seed in LEARNER_SEEDS for architecture in ARCHITECTURES]
        for architecture, seed in order:
            task_key = f"{architecture}_seed{seed}"
            run_config_path = output / "run-configs" / f"{task_key}.json"
            if not run_config_path.exists():
                run_config = json.loads(training_config_paths[architecture].read_text(encoding="utf-8"))
                run_config["training"]["max_seconds"] = 3600
                run_config["training"]["max_episodes"] = 128
                _write_json(run_config_path, run_config)
            result = _training_run(run_config_path, output / architecture, seed,
                                   3600, state, state_path, "training", 21600)
            if result["status"] != "complete":
                training_stage["status"] = "incomplete"
                state["failure"] = {"stage": "training", "task": task_key, **result}
                _persist_campaign(state_path, state)
                return state
        training_stage["status"] = "complete"
        _persist_campaign(state_path, state)

    selection_stage = state["stages"]["selection_holdout"]
    frozen_path = output / "frozen" / "frozen.json"
    if not frozen_path.is_file():
        stop_clock = _start_campaign_heartbeat(state, state_path, "selection_holdout")
        try:
            selected = freeze_training_selections(output / "graph_mappo", output / "local_mappo",
                                                  frozen_path.parent, baseline_inputs)
        finally:
            stop_clock()
        state["frozen_sha256"] = file_hash(frozen_path)
        _persist_campaign(state_path, state)
    else:
        selected = json.loads(frozen_path.read_text(encoding="utf-8"))
        if state.get("frozen_sha256") and file_hash(frozen_path) != state["frozen_sha256"]:
            raise ValueError("Frozen actor selection changed during campaign resume")
    if selection_stage["status"] != "complete":
        selection_stage["status"] = "running"
        _persist_campaign(state_path, state)
        remaining = min(9000. - selection_stage["elapsed_s"],
                        state["budget_seconds"] - state["active_elapsed_s"])
        holdout_dir = output / "holdout"
        prior_status = (json.loads((holdout_dir / "status.json").read_text(encoding="utf-8"))
                        if (holdout_dir / "status.json").is_file() else {})
        if prior_status.get("status") == "complete":
            selection_stage["status"] = "complete"
            state["holdout"] = prior_status
        elif remaining > 0:
            holdout_config["baselines"] = selected["baseline_specs"]
            stop_clock = _start_campaign_heartbeat(state, state_path, "selection_holdout")
            holdout_status = run_holdout(holdout_config, frozen_path, holdout_dir,
                                         max_seconds=remaining,
                                         resume=(holdout_dir / "config.json").is_file())
            stop_clock()
            state["holdout"] = holdout_status
            selection_stage["status"] = ("complete" if holdout_status["status"] == "complete"
                                          else "incomplete")
        else:
            selection_stage["status"] = "incomplete"
        _persist_campaign(state_path, state)

    state["status"] = ("complete" if all(state["stages"][name]["status"] == "complete"
                                          for name, _ in CAMPAIGN_STAGES) else "incomplete")
    _persist_campaign(state_path, state)
    return state


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    commands = parser.add_subparsers(dest="command", required=True)
    freeze = commands.add_parser("freeze", help="Select paired validation checkpoints and copy six actors")
    freeze.add_argument("--graph-training-root", required=True)
    freeze.add_argument("--local-training-root", required=True)
    freeze.add_argument("--output", required=True)
    freeze.add_argument("--config", help="holdout config used to freeze all seven baseline inputs")
    run = commands.add_parser("run", help="run or resume the ten-hour MAPPO research campaign")
    run.add_argument("--config", required=True)
    run.add_argument("--output", required=True)
    run.add_argument("--resume", action="store_true")
    evaluate = commands.add_parser("holdout", help="Run the frozen, resumable holdout matrix")
    evaluate.add_argument("--config", required=True)
    evaluate.add_argument("--frozen", required=True)
    evaluate.add_argument("--output", required=True)
    evaluate.add_argument("--max-seconds", type=int, default=9000)
    evaluate.add_argument("--resume", action="store_true",
                          help="continue an incomplete holdout with the same frozen inputs")
    args = parser.parse_args()
    if args.command == "freeze":
        baseline_inputs = None
        if args.config:
            config = _resolve_config_paths(json.loads(Path(args.config).read_text(encoding="utf-8")),
                                           Path(__file__).resolve().parents[2])
            baseline_inputs = freeze_baseline_inputs(
                config, Path(args.output).resolve().with_name(Path(args.output).name + "-baselines"))
        freeze_training_selections(args.graph_training_root, args.local_training_root,
                                   args.output, baseline_inputs)
    elif args.command == "holdout":
        config = json.loads(Path(args.config).read_text(encoding="utf-8"))
        config = _resolve_config_paths(config, Path(__file__).resolve().parents[2])
        run_holdout(config, args.frozen, args.output, args.max_seconds, args.resume)
    else:
        result = run_campaign(args.config, args.output, args.resume)
        print(json.dumps(result, indent=2), flush=True)
        if result.get("status") != "complete":
            raise SystemExit(2)


if __name__ == "__main__":
    main()
