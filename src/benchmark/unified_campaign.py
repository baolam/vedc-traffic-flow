"""Resumable unified campaign: workloads -> train -> freeze -> evaluate -> report.

Every (map, algorithm, learner seed) run is kept in the aggregate; a run without a feasible
validation checkpoint is reported as such, never dropped or replaced by another seed.
"""
import argparse
import copy
import json
import traceback
from collections import defaultdict
from contextlib import ExitStack
from pathlib import Path

import numpy as np

from contracts.benchmark import SEEDS, UNIFIED_CAMPAIGN as C, UNIFIED_DQN
from .evidence import digest, file_hash, write_json
from .suite import expand, identity

PROTOCOL = dict(demand_s=1800, drain_s=600, trace=True, benchmark_mode=True)
ALGORITHMS = tuple(UNIFIED_DQN["algorithms"])


def load_suite(prepared, root, maps=None):
    suite = json.loads(Path(prepared).read_text())
    suite["maps"] = [m for m in suite["maps"] if not maps or m["id"] in maps]
    workloads = Path(root) / "workloads.json"
    saved = json.loads(workloads.read_text()) if workloads.exists() else {}
    for m in suite["maps"]:
        m.pop("models", None)  # legacy phase_dqn pilots must not leak into this campaign
        m.update(saved.get(m["id"], {}))
    return suite


def stage_workloads(suite, root):
    from .campaign import tune_and_calibrate

    path = Path(root) / "workloads.json"
    saved = json.loads(path.read_text()) if path.exists() else {}
    for m in suite["maps"]:
        if m["id"] not in saved:
            tune_and_calibrate(m, root, suite["workers"])
            saved[m["id"]] = {k: m[k] for k in ("controller_overrides", "intensity_by_case", "calibration_mode")}
            write_json(path, saved)  # per map, so an interrupted calibration resumes


def stage_train(suite, root, algorithms, seeds, recipe=None, wall_limit_s=None, device="cuda"):
    from src.rl.unified_train import train_run

    root = Path(root)
    ledger_path = root / "training-ledger.json"
    ledger = json.loads(ledger_path.read_text()) if ledger_path.exists() else {}
    for m in suite["maps"]:
        if "intensity_by_case" not in m:
            raise ValueError(f"Run the workloads stage first: {m['id']} has no calibrated demand")
        for algorithm in algorithms:
            for seed in seeds:
                key, out = f"{m['id']}/{algorithm}/{seed}", root / "training" / m["id"] / algorithm / str(seed)
                try:
                    r = train_run(m, algorithm, seed, out, recipe, wall_limit_s, device, suite["workers"],
                                  cases_root=root / "validation-cases" / m["id"])
                    ledger[key] = dict(status=r["status"], stop_reason=r["stop_reason"], converged=r["converged"],
                                       wall_s=r["counters"]["wall_s"], sim_s=r["counters"]["sim_s"])
                except Exception as error:  # recorded, reported, retried on the next invocation
                    out.mkdir(parents=True, exist_ok=True)
                    (out / "failure.txt").write_text(traceback.format_exc())
                    ledger[key] = dict(status="failed", error=repr(error))
                write_json(ledger_path, ledger)
    return ledger


def with_models(suite, root, algorithms, seeds):
    """Suite whose maps carry each selected trained policy as a learner-seeded extra controller."""
    suite, root, runs, missing = copy.deepcopy(suite), Path(root), {}, []
    for m in suite["maps"]:
        learned = []
        for algorithm in algorithms:
            for seed in seeds:
                key = f"{m['id']}/{algorithm}/{seed}"
                result = root / "training" / m["id"] / algorithm / str(seed) / "result.json"
                if not result.exists():
                    missing.append(key)
                    continue
                r = json.loads(result.read_text())
                runs[key] = dict(status=r["status"], stop_reason=r["stop_reason"], converged=r["converged"],
                                 counters=r["counters"], selected=r["selected"])
                if r["selected"]:
                    learned.append(dict(type=algorithm, model_path=r["selected"]["path"], learner_seed=seed,
                                        parameters={}))
        m["extra_controllers"] = [c for c in m.get("extra_controllers", []) if "learner_seed" not in c] + learned
    if missing:
        raise ValueError(f"Training incomplete, refusing to freeze: {missing}")
    return suite, runs


def stage_freeze(suite, root, algorithms, seeds):
    root = Path(root)
    frozen_suite, runs = with_models(suite, root, algorithms, seeds)
    paths = [c["model_path"] for m in frozen_suite["maps"] for c in m["extra_controllers"] if "model_path" in c]
    frozen = dict(
        artifact_root=str(root.resolve()), selection_split="validation", suite=frozen_suite, selections=runs,
        model_hashes={p: file_hash(p) for p in paths},
        campaign=dict(version=C["version"], algorithms=list(algorithms), learner_seeds=list(seeds)),
        case_identities=[identity(case, PROTOCOL) for case in expand(frozen_suite, "test")],
    )
    write_json(root / "freeze.json", frozen)
    return frozen


def stage_evaluate(suite, root, split, algorithms, seeds, protocol=None):
    from .campaign import load_frozen
    from .scheduling import run_tasks

    root, protocol = Path(root), dict(protocol or PROTOCOL)
    if split == "test":
        if not (root / "freeze.json").exists():
            raise ValueError("Final evaluation requires a validation-selection freeze")
        frozen = load_frozen(root / "freeze.json", protocol)
        suite, selections = frozen["suite"], frozen["selections"]
    else:
        suite, selections = with_models(suite, root, algorithms, seeds)
    tasks = [(c, protocol, str(root / "cases")) for c in expand(suite, split)]
    write_json(root / "evaluation.json", dict(identities=[identity(c, protocol) for c, _, _ in tasks],
                                              split=split, mode="unified", suite=suite, selections=selections))
    run_tasks(tasks, suite["workers"], continue_on_error=True)  # failures stay visible in the report


def _interval(values):
    from scipy.stats import t

    n = len(values)
    if n < 2:
        return None
    half = float(t.ppf(0.975, n - 1)) * float(np.std(values, ddof=1)) / np.sqrt(n)
    return [float(np.mean(values)) - half, float(np.mean(values)) + half]


def aggregate(rows, test_seeds, reference="fixed_time", training=None):
    """Per map/case/controller: mean delay over test seeds per training seed, then across training seeds."""
    cells = defaultdict(dict)
    groups = defaultdict(list)
    for r in rows:
        c = r["controller"]
        groups[(r["topology_id"], r["scenario"], c["type"], c.get("learner_seed"))].append(r)
    for (m, case, kind, learner), rs in groups.items():
        complete = len(rs) == len(test_seeds) and all(x["valid"] for x in rs)
        cells[(m, case, kind)]["model_free" if learner is None else str(learner)] = dict(
            mean_delay_s=float(np.mean([x["delay_per_scheduled_s"] for x in rs])) if complete else None,
            n_runs=len(rs), n_valid=sum(bool(x["valid"]) for x in rs), expected=len(test_seeds))
    for key, run in (training or {}).items():  # every expected training seed appears, evaluated or not
        m, kind, seed = key.split("/")
        for (cm, case, ck), per in cells.items():
            if (cm, ck) == (m, kind) and seed not in per:
                per[seed] = dict(mean_delay_s=None, n_runs=0, n_valid=0, expected=len(test_seeds), status=run["status"])
    entries = []
    for (m, case, kind), per in sorted(cells.items()):
        values = [v["mean_delay_s"] for v in per.values() if v["mean_delay_s"] is not None]
        entries.append(dict(map=m, scenario=case, controller=kind, learned="model_free" not in per, per_seed=per,
                            n_complete=len(values), mean_delay_s=float(np.mean(values)) if values else None,
                            std_across_training_seeds=float(np.std(values, ddof=1)) if len(values) > 1 else None,
                            ci95_t_over_training_seeds=_interval(values)))
    base = {(e["map"], e["scenario"]): e["mean_delay_s"] for e in entries if e["controller"] == reference}
    ratios = defaultdict(lambda: defaultdict(list))
    for e in entries:
        ref = base.get((e["map"], e["scenario"]))
        e["relative_to_" + reference] = e["mean_delay_s"] / ref if ref and e["mean_delay_s"] is not None else None
        if e["relative_to_" + reference] is not None:
            ratios[e["controller"]][e["map"]].append(e["relative_to_" + reference])
    maps = {e["map"] for e in entries}
    equal_map = {k: float(np.mean([np.mean(v) for v in per.values()])) for k, per in ratios.items()
                 if set(per) == maps}  # only controllers with every map covered
    return dict(entries=entries, equal_map_relative_delay=equal_map, reference=reference)


def stage_report(root):
    root = Path(root)
    request = json.loads((root / "evaluation.json").read_text())
    rows, missing = [], []
    for ident in request["identities"]:
        done = root / "cases" / digest(ident) / "complete.json"
        if done.exists():
            rows.append(json.loads(done.read_text())["metrics"])
        else:
            missing.append(ident["case"])
    result = aggregate(rows, SEEDS[request["split"]], training=request["selections"])
    result.update(split=request["split"], expected_cases=len(request["identities"]), completed_cases=len(rows),
                  missing_cases=missing,
                  training={k: v for k, v in request["selections"].items()},
                  final_test_opened=request["split"] == "test")
    write_json(root / "report_unified.json", result)
    lines = [f"# Unified campaign report ({result['split']})", "",
             f"Cases complete: {len(rows)}/{result['expected_cases']}; missing: {len(missing)}", "",
             "| map | scenario | controller | mean delay s | std over training seeds | complete seeds |",
             "|---|---|---|---|---|---|"]
    fmt = lambda v: "n/a" if v is None else f"{v:.2f}"  # noqa: E731
    lines += [f"| {e['map']} | {e['scenario']} | {e['controller']} | {fmt(e['mean_delay_s'])} | "
              f"{fmt(e['std_across_training_seeds'])} | {e['n_complete']}/{len(e['per_seed'])} |"
              for e in result["entries"]]
    unconverged = [k for k, v in result["training"].items() if not v["converged"]]
    lines += ["", f"Training runs not converged (budget-limited or no feasible checkpoint): {len(unconverged)}"]
    lines += [f"- {k}: {result['training'][k]['stop_reason']} ({result['training'][k]['status']})" for k in unconverged]
    (root / "report_unified.md").write_text("\n".join(lines) + "\n")
    return result


def main(argv=None):
    from .resources import coordinator

    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--prepared", required=True, help="audited prepared.json (maps, networks, topologies)")
    parser.add_argument("--root", required=True)
    parser.add_argument("--stage", required=True, choices=["workloads", "train", "freeze", "evaluate", "report"])
    parser.add_argument("--split", choices=["validation", "test"], default="validation")
    parser.add_argument("--maps", nargs="*")
    parser.add_argument("--algorithms", nargs="*", default=list(ALGORITHMS), choices=ALGORITHMS)
    parser.add_argument("--seeds", nargs="*", type=int, default=C["learner_seeds"])
    parser.add_argument("--recipe", default="{}", help="JSON overrides of the frozen recipe (recorded in artifacts)")
    parser.add_argument("--wall-limit-s", type=float)
    parser.add_argument("--device", default="cuda", choices=["cuda", "cpu"])
    parser.add_argument("--demand-s", type=int)
    parser.add_argument("--drain-s", type=int)
    a = parser.parse_args(argv)
    root = Path(a.root).resolve()
    root.mkdir(parents=True, exist_ok=True)
    suite = load_suite(a.prepared, root, a.maps)
    protocol = dict(PROTOCOL, **{k: v for k, v in (("demand_s", a.demand_s), ("drain_s", a.drain_s)) if v})
    if a.split == "test" and a.stage not in ("evaluate", "report"):
        raise ValueError("The test split is only for the evaluate and report stages")
    if a.split == "test" and (a.demand_s or a.drain_s):
        raise ValueError("The test split uses the frozen protocol; demand/drain overrides are not allowed")
    with ExitStack() as stack:
        if a.stage in ("workloads", "train", "evaluate"):
            stack.enter_context(coordinator())
        if a.stage == "workloads":
            stage_workloads(suite, root)
        elif a.stage == "train":
            stage_train(suite, root, a.algorithms, a.seeds, json.loads(a.recipe), a.wall_limit_s, a.device)
        elif a.stage == "freeze":
            stage_freeze(suite, root, a.algorithms, a.seeds)
        elif a.stage == "evaluate":
            stage_evaluate(suite, root, a.split, a.algorithms, a.seeds, protocol)
            stage_report(root)
        else:
            stage_report(root)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
