"""Paired, per-map research gates. Incomplete evidence is never a promotion."""

import numpy as np
from contracts.benchmark import SEEDS

BASELINES = ("fixed_time", "actuated", "max_pressure", "edgeflow")


def qualification(candidate, baselines, scenarios, seeds=None):
    seeds = SEEDS["test"] if seeds is None else seeds
    expected = {(scenario, seed) for scenario in scenarios for seed in seeds}

    def index(rows):
        indexed = {(r["scenario"], r["seed"]): r for r in rows}
        if len(rows) != len(expected) or set(indexed) != expected:
            raise ValueError("Every unique paired scenario/seed is required")
        return indexed

    try:
        c = index(candidate)
        indices = {name: index(baselines[name]) for name in BASELINES}
    except (ValueError, KeyError) as error:
        return dict(promoted=False, complete=False, reasons=[str(error)], comparisons={})
    reasons = []
    comparisons = {}
    normalized_violations = []
    for name, b in indices.items():
        differences = []
        base = []
        for scenario in scenarios:
            cr = [c[(scenario, seed)] for seed in seeds]
            br = [b[(scenario, seed)] for seed in seeds]
            for left, right in zip(cr, br):
                for key in (
                    "network_sha256",
                    "topology_sha256",
                    "demand_sha256",
                    "timing",
                    "scheduled",
                    "demand_s",
                    "drain_s",
                    "metrics_version",
                ):
                    if left[key] != right[key]:
                        reasons.append(f"{name}/{scenario}: unpaired {key}")
                if not left["valid"] or not right["valid"] or not left["scheduled"]:
                    reasons.append(f"{name}/{scenario}: invalid or empty run")
                if any(left[key] or right[key] for key in ("collisions", "teleports", "accounting_losses")):
                    reasons.append(f"{name}/{scenario}: simulator invalidity")
                normalized_violations.extend(
                    (
                        left["delay_per_scheduled_s"] / max(1.05 * right["delay_per_scheduled_s"], 1e-12),
                        0.98
                        * (right["completed"] / max(right["scheduled"], 1))
                        / max(left["completed"] / max(left["scheduled"], 1), 1e-12),
                        left["p95_wait_s"] / (right["p95_wait_s"] + max(0.1 * right["p95_wait_s"], 1.0)),
                        left["worst_approach_wait_s"]
                        / (right["worst_approach_wait_s"] + max(0.1 * right["worst_approach_wait_s"], 1.0)),
                        left["max_approach_p95_wait_s"]
                        / (right["max_approach_p95_wait_s"] + max(0.1 * right["max_approach_p95_wait_s"], 1.0)),
                    )
                )
            cm = {
                key: np.mean([r[key] for r in cr])
                for key in ("delay_per_scheduled_s", "p95_wait_s", "worst_approach_wait_s", "max_approach_p95_wait_s")
            }
            bm = {key: np.mean([r[key] for r in br]) for key in cm}
            cm["completion_rate"] = np.mean([r["completed"] / max(r["scheduled"], 1) for r in cr])
            bm["completion_rate"] = np.mean([r["completed"] / max(r["scheduled"], 1) for r in br])
            if cm["delay_per_scheduled_s"] > 1.05 * bm["delay_per_scheduled_s"]:
                reasons.append(f"{name}/{scenario}: delay regression >5%")
            if cm["completion_rate"] < 0.98 * bm["completion_rate"]:
                reasons.append(f"{name}/{scenario}: completion <98%")
            for key in ("p95_wait_s", "worst_approach_wait_s", "max_approach_p95_wait_s"):
                if cm[key] > bm[key] + max(0.1 * bm[key], 1.0):
                    reasons.append(f"{name}/{scenario}: {key} regression")
            differences.append(
                [right["delay_per_scheduled_s"] - left["delay_per_scheduled_s"] for left, right in zip(cr, br)]
            )
            base.extend(r["delay_per_scheduled_s"] for r in br)
        differences = np.asarray(differences)
        samples = np.random.default_rng(9182).integers(0, len(seeds), (10000, len(seeds)))
        interval = np.percentile(differences[:, samples].mean(axis=(0, 2)), [2.5, 97.5]).tolist()
        gain = float(differences.mean() / max(np.mean(base), 1e-12))
        comparisons[name] = dict(relative_delay_improvement=gain, paired_ci95_s=interval)
        if name in ("edgeflow", "max_pressure") and (gain < 0.05 or interval[0] <= 0):
            reasons.append(f"{name}: 5% improvement with positive interval required")
        if name in ("actuated", "fixed_time") and gain < -0.02:
            reasons.append(f"{name}: overall delay regression >2%")
    return dict(
        promoted=not reasons,
        complete=True,
        reasons=sorted(set(reasons)),
        comparisons=comparisons,
        selection_score=max(normalized_violations, default=float("inf")),
    )
