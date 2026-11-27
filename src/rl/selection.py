"""Validation score and guardrails for checkpoint selection; test seeds never enter here."""
import numpy as np

TAILS = ("p95_wait_s", "worst_approach_wait_s", "max_approach_p95_wait_s")


def validation_score(rows, reference, cases, seeds):
    """Equal-case mean delay; feasible only if complete, valid and no worse than the reference tails."""
    expected = {(c, s) for c in cases for s in seeds}
    index = {(r["scenario"], r["seed"]): r for r in rows}
    ref = {(r["scenario"], r["seed"]): r for r in reference}
    if len(rows) != len(expected) or set(index) != expected or set(ref) != expected:
        return dict(score=float("inf"), feasible=False, reasons=["incomplete validation pairs"])
    reasons, means = [], []
    for case in cases:
        got = [index[(case, s)] for s in seeds]
        base = [ref[(case, s)] for s in seeds]
        if any(not r["valid"] or not r["scheduled"] or r["collisions"] or r["teleports"] or r["accounting_losses"]
               for r in got):
            reasons.append(f"{case}: invalid run or simulator invalidity")
        means.append(float(np.mean([r["delay_per_scheduled_s"] for r in got])))
        rate = lambda rs: np.mean([r["completed"] / max(r["scheduled"], 1) for r in rs])  # noqa: E731
        if rate(got) < 0.98 * rate(base):
            reasons.append(f"{case}: completion below 98% of reference")
        for key in TAILS:
            b, c = np.mean([r[key] for r in base]), np.mean([r[key] for r in got])
            if c > b + max(0.1 * b, 1.0):
                reasons.append(f"{case}: {key} regression")
    return dict(score=float(np.mean(means)), feasible=not reasons, reasons=reasons)
