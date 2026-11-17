"""Paired benchmark CLI; final-test data requires a validation-frozen selection."""

import argparse
import csv
import json
import os
import platform
import subprocess
import tarfile
from contextlib import ExitStack
from .resources import coordinator
from pathlib import Path
from .evidence import digest, execute_case, file_hash, snapshot_source, write_json
from .suite import expand, identity, load_suite, preflight, resolved_protocol


def execute(task):
    case, protocol, root = task
    protocol = resolved_protocol(case, protocol)
    signature = identity(case, protocol)

    def run(output):
        from src.rl.benchmark import run_case

        environment = {k: case["map"][k] for k in ("network_path", "topology_path")}
        environment.update(protocol)
        import time

        start = time.perf_counter()
        result = run_case({"environment": environment}, case["controller"], case["scenario"], case["seed"], output)
        result["wall_seconds"] = time.perf_counter() - start
        try:
            import resource

            result["worker_peak_rss_kib"] = resource.getrusage(resource.RUSAGE_SELF).ru_maxrss
            result["sumo_children_peak_rss_kib"] = resource.getrusage(resource.RUSAGE_CHILDREN).ru_maxrss
        except ImportError:
            result["worker_peak_rss_kib"] = None
            result["sumo_children_peak_rss_kib"] = None
        write_json(Path(output) / "metrics.json", result)
        return result

    return execute_case(root, signature, run)


def report(root):
    root = Path(root)
    request = json.loads((root / "evaluation.json").read_text()) if (root / "evaluation.json").exists() else {}
    requested = request.get("identities", [])
    paths = [root / "cases" / digest(i) / "complete.json" for i in requested] if requested else []
    rows = [json.loads(p.read_text())["metrics"] for p in paths if p.exists()]
    failures = [
        root / "cases" / digest(i) / attempt / "failure.json"
        for i in requested
        for attempt in (root / "cases" / digest(i)).glob("attempt-*")
        if (attempt / "failure.json").exists()
    ]
    failed_cases = []
    for case_identity in requested:
        directory = root / "cases" / digest(case_identity)
        invalid = directory / "invalid.json"
        if invalid.exists():
            failed_cases.append(
                dict(
                    case=case_identity["case"],
                    identity_sha256=digest(case_identity),
                    reason=json.loads(invalid.read_text()).get("reason", "invalid result"),
                )
            )
        elif not (directory / "complete.json").exists() and not any(
            (attempt / "failure.json").exists() for attempt in directory.glob("attempt-*")
        ):
            failed_cases.append(
                dict(case=case_identity["case"], identity_sha256=digest(case_identity), reason="missing result")
            )
    gates = {}
    if request.get("split") == "test":
        from .scoring import qualification, BASELINES

        for mapping in request["suite"]["maps"]:
            local = [r for r in rows if r["topology_id"] == mapping["id"]]
            selected = request["selections"][mapping["id"]]["model_path"]
            candidate = [r for r in local if r["controller"].get("model_path") == selected]
            baselines = {name: [r for r in local if r["controller"]["type"] == name] for name in BASELINES}
            gates[mapping["id"]] = qualification(candidate, baselines, mapping["cases"])
    complete = bool(requested) and len(rows) == len(requested)
    groups = {}
    for row in rows:
        controller = row["controller"]
        key = (row["topology_id"], row["scenario"], controller["type"], controller.get("learner_seed"))
        groups.setdefault(key, []).append(row)
    methods = [
        dict(
            map=key[0],
            scenario=key[1],
            controller=key[2],
            learner_seed=key[3],
            demand_seeds=len(values),
            mean_delay_s=float(sum(r["delay_per_scheduled_s"] for r in values) / len(values)),
            mean_completion_rate=float(sum(r["completed"] / max(r["scheduled"], 1) for r in values) / len(values)),
            mean_p95_wait_s=float(sum(r["p95_wait_s"] for r in values) / len(values)),
        )
        for key, values in sorted(groups.items(), key=lambda item: tuple(str(v) for v in item[0]))
    ]
    public_rows = [
        {
            key: row[key]
            for key in (
                "topology_id",
                "scenario",
                "seed",
                "valid",
                "scheduled",
                "completed",
                "unfinished",
                "uninserted",
                "delay_per_scheduled_s",
                "p95_wait_s",
                "worst_approach_wait_s",
                "collisions",
                "teleports",
            )
        }
        | {
            "controller": {key: row["controller"].get(key) for key in ("type", "learner_seed")},
            "model_sha256": row.get("model_sha256"),
        }
        for row in rows
    ]
    result = dict(
        completed=len(rows),
        expected=len(requested),
        complete=complete,
        failed_attempts=len(failures),
        failed_cases=failed_cases,
        method_summary=methods,
        promoted=complete and bool(gates) and all(g["promoted"] for g in gates.values()),
        final_test_opened=request.get("split") == "test",
        mode=request.get("mode"),
        qualification=gates,
        runs=public_rows,
    )
    write_json(root / "report.json", result)
    lines = [
        "# Benchmark evidence",
        "",
        f"Completed cases: {len(rows)}/{len(requested)}",
        f"\nMode: {request.get('mode', 'not evaluated')}; split: {request.get('split', 'none')}",
        f"\nPromotion: {result['promoted']}",
        "",
        "| Map | Controller | Seed | Delay/scheduled (s) | Completed |",
        "|---|---|---|---:|---:|",
    ]
    for r in rows:
        lines.append(
            f"| {r['topology_id']} | {r['controller']['type']} | {r['seed']} | "
            f"{r['delay_per_scheduled_s']:.3f} | {r['completed']} |"
        )
    lines.extend(
        [
            "",
            "## Method summary",
            "",
            "| Map | Workload | Controller | Learner seed | Demand seeds | Mean delay (s) | "
            "Mean completion | Mean p95 wait (s) |",
            "|---|---|---|---:|---:|---:|---:|---:|",
        ]
    )
    for row in methods:
        lines.append(
            f"| {row['map']} | {row['scenario']} | {row['controller']} | "
            f"{row['learner_seed'] if row['learner_seed'] is not None else '—'} | {row['demand_seeds']} | "
            f"{row['mean_delay_s']:.3f} | {row['mean_completion_rate']:.3f} | "
            f"{row['mean_p95_wait_s']:.3f} |"
        )
    if failed_cases:
        lines.extend(
            [
                "",
                "## Invalid or missing cases",
                "",
                "| Map | Workload | Seed | Controller | Reason |",
                "|---|---|---:|---|---|",
            ]
        )
        for failure in failed_cases:
            case = failure["case"]
            lines.append(
                f"| {case['map']} | {case['scenario']} | {case['seed']} | "
                f"{case['controller']['type']} | {failure['reason']} |"
            )
    lines.extend(
        [
            "",
            "Delay is accrued over the finite horizon; unfinished trips remain in the ledger.",
            "Pilot completion is not final qualification. Raw identities and attempts are retained under cases/.",
        ]
    )
    (root / "report.md").write_text("\n".join(lines) + "\n")
    with (root / "runs.csv").open("w") as handle:
        fields = [
            "topology_id",
            "scenario",
            "seed",
            "valid",
            "delay_per_scheduled_s",
            "completed",
            "unfinished",
            "uninserted",
        ]
        writer = csv.DictWriter(handle, fieldnames=fields, extrasaction="ignore")
        writer.writeheader()
        writer.writerows(rows)
    return result


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--suite", required=True)
    parser.add_argument(
        "--stage",
        choices=["preflight", "prepare", "pilot", "pilot-evaluate", "train", "evaluate", "report", "export"],
        required=True,
    )
    parser.add_argument("--output-dir", default="artifacts/benchmarks/development")
    parser.add_argument("--split", choices=["development", "validation", "test"], default="development")
    parser.add_argument("--freeze")
    args = parser.parse_args(argv)
    with ExitStack() as stack:
        if args.stage in ("prepare", "pilot", "pilot-evaluate", "train", "evaluate"):
            stack.enter_context(coordinator())
        suite = load_suite(args.suite)
        root = Path(args.output_dir).resolve()
        root.mkdir(parents=True, exist_ok=True)
        if args.split == "test" and (args.stage != "evaluate" or not args.freeze):
            raise ValueError("Final evaluation requires --stage evaluate --freeze <validation selection>")
        if args.stage == "preflight":
            if (root / "prepared.json").exists():
                suite = json.loads((root / "prepared.json").read_text())
            result = preflight(suite)
            write_json(root / "preflight.json", result)
            print(json.dumps(result, indent=2))
            return 0 if result["ready"] else 1
        if args.stage == "report":
            result = report(root)
            print(
                json.dumps(
                    {
                        key: result[key]
                        for key in (
                            "completed",
                            "expected",
                            "complete",
                            "failed_attempts",
                            "failed_cases",
                            "promoted",
                            "final_test_opened",
                            "mode",
                            "qualification",
                        )
                    },
                    indent=2,
                )
            )
            return 0
        if args.stage == "export":
            files = sorted(
                p for p in root.rglob("*") if p.is_file() and p.name != "checksums.json" and p.suffix != ".tmp"
            )
            if any(p.is_symlink() for p in files):
                raise ValueError("Artifact export does not follow symlinks")
            write_json(root / "checksums.json", {str(p.relative_to(root)): file_hash(p) for p in files})
            with tarfile.open(str(root) + ".tar.gz", "w:gz") as archive:
                for p in files + [root / "checksums.json"]:
                    archive.add(p, arcname=str(p.relative_to(root)))
            return 0
        if args.stage == "prepare":
            from .prepare import prepare_map

            suite["maps"] = [prepare_map(m, root / "inputs" / m["id"]) for m in suite["maps"]]
            write_json(root / "prepared.json", suite)
            return 0
        prepared = root / "prepared.json"
        if not prepared.exists() and args.split != "test":
            raise ValueError("Run prepare first; execution requires audited maps")
        if prepared.exists():
            suite = json.loads(prepared.read_text())
        source_snapshot = (
            snapshot_source(root) if args.stage in ("pilot", "pilot-evaluate", "train", "evaluate", "report") else None
        )
        if args.stage == "train":
            from .campaign import run_training

            run_training(suite, root)
            return 0
        if args.stage == "pilot":
            if args.split != "development":
                raise ValueError("Pilots use development demand only")
            from .train import train_map
            from .calibration import calibrate

            for spec in suite["maps"]:
                calibrate(spec, root, {"type": "fixed_time"}, pilot=True, workers=suite["workers"])
                training_root = root / "pilot-training" / spec["id"] / Path(source_snapshot).name
                spec["models"] = {"11": train_map(spec, training_root, seed=11, seconds=120, decisions=200)}
                from .performance import measure_policy

                spec["inference_device"] = measure_policy(
                    spec["models"]["11"], training_root / "performance-input.json", training_root / "performance.json"
                )
            write_json(root / "pilot-suite.json", suite)
        elif args.stage == "pilot-evaluate":
            suite = json.loads((root / "pilot-suite.json").read_text())
        elif args.split == "development" and (root / "pilot-suite.json").exists():
            suite = json.loads((root / "pilot-suite.json").read_text())
        if args.split != "test" and any(not m.get("models") for m in suite["maps"]):
            raise ValueError("Train per-map policies before evaluating the complete suite")
        protocol = dict(demand_s=1800, drain_s=600, trace=True, benchmark_mode=True)
        selections = {}
        if args.split == "test":
            from .campaign import load_frozen

            frozen = load_frozen(args.freeze, protocol)
            suite = frozen["suite"]
            selections = frozen["selections"]
        if args.stage in ("pilot", "pilot-evaluate"):
            protocol.update(demand_s=180, drain_s=60)
        tasks = [(c, protocol, str(root / "cases")) for c in expand(suite, args.split)]
        write_json(
            root / "evaluation.json",
            dict(
                identities=[identity(c, protocol) for c, _, _ in tasks],
                split=args.split,
                mode=args.stage,
                suite=suite,
                selections=selections,
            ),
        )
        environment = dict(python=platform.python_version(), platform=platform.platform(), logical_cpus=os.cpu_count())
        for key, command in [("commit", ["git", "rev-parse", "HEAD"]), ("dirty", ["git", "status", "--porcelain"])]:
            environment[key] = subprocess.run(command, capture_output=True, text=True, check=True).stdout
        write_json(root / "environment.json", environment)
        try:
            from .scheduling import run_tasks

            run_tasks(tasks, suite["workers"], continue_on_error=args.stage in ("pilot", "pilot-evaluate"))
        finally:
            report(root)
        return 0


if __name__ == "__main__":
    raise SystemExit(main())
