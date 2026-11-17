"""Development-only finite-horizon load calibration against a fixed controller."""

from pathlib import Path
from contracts.benchmark import SEEDS
from .evidence import write_json


def bracket_capacity(measure):
    """Find stable/unstable load bounds, then refine twice without test data."""
    lower = 0.25
    while not measure(lower):
        lower /= 2
        if lower < 0.01:
            raise ValueError("No stable development load above the minimum intensity")
    upper = lower * 2
    while measure(upper):
        lower = upper
        upper *= 2
        if upper > 8:
            raise ValueError("Capacity not bracketed below intensity 8; workload needs review")
    for _ in range(2):
        middle = (lower + upper) / 2
        if measure(middle):
            lower = middle
        else:
            upper = middle
    return lower, upper


def calibrate(mapping, root, controller, pilot=False, workers=4):
    root = Path(root)
    protocol = dict(demand_s=180 if pilot else 1800, drain_s=600, trace=False, benchmark_mode=True)
    observations = []

    def measure(intensity):
        config = dict(protocol, intensity=intensity)
        from .scheduling import run_tasks

        tasks = [
            (dict(map=mapping, scenario="balanced", seed=seed, controller=controller), config, str(root / "cases"))
            for seed in SEEDS["development"]
        ]
        rows = run_tasks(tasks, workers)
        stable = all(r["scheduled"] > 0 and r["completed"] >= 0.98 * r["scheduled"] for r in rows)
        observations.append(dict(intensity=intensity, stable=stable))
        return stable

    lower, upper = bracket_capacity(measure)
    if mapping["id"] == "four_intersection_rl_v1":
        factors = dict(sparse=lower, near_capacity=lower, oversaturated=upper)
    else:
        factors = dict(balanced=0.7 * lower, directional_reversal=lower, downstream_bottleneck=0.7 * lower)
    mapping["intensity_by_case"] = factors
    mapping["calibration_mode"] = "pilot" if pilot else "research"
    write_json(
        root / "calibration" / mapping["id"] / f"{mapping['calibration_mode']}.json",
        dict(stable_lower=lower, unstable_upper=upper, observations=observations, protocol=protocol),
    )
    return mapping
