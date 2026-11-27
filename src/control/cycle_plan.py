"""Native-phase fair-cycle timing: cycle length, green allocation and legal 5 s transfers."""
import os

from contracts.benchmark import CYCLE_RULE as R

_CYCLE_G = os.environ.get("EDGEFLOW_CYCLE_G")  # experiment: cycle = phases * (g + clearance)


def cycle_length(phases):
    if _CYCLE_G:
        return phases * (int(_CYCLE_G) + R["clearance_s"])
    return max(R["base_s"], R["per_phase_s"] * phases)


def green_budget(phases):
    budget = cycle_length(phases) - R["clearance_s"] * phases
    if phases < 2 or not R["min_green_s"] * phases <= budget <= R["max_green_s"] * phases:
        raise ValueError(f"Cycle timing infeasible for {phases} phases")
    return budget


def allocate_greens(weights):
    """Minimum green each, then 5 s units by D'Hondt on weights; ties go to the lowest index."""
    phases = len(weights)
    if any(w < 0 for w in weights):
        raise ValueError("Negative allocation weight")
    greens = [R["min_green_s"]] * phases
    for _ in range((green_budget(phases) - sum(greens)) // R["quantum_s"]):
        open_ = [i for i in range(phases) if greens[i] < R["max_green_s"]]
        best = max(open_, key=lambda i: (weights[i] / (greens[i] - R["min_green_s"] + R["quantum_s"]), -i))
        greens[best] += R["quantum_s"]
    return greens


def damped_greens(weights, share=None):
    """Greens `share` of the way from the equal split to the pressure split, quantized with the budget exact.

    Leftover quanta go to the largest remainders; equal remainders (common: half an odd quantum count) go to the
    phase the pressure split favours more, so rounding follows demand, never a fixed phase position.
    """
    share = R["adapt_share"] if share is None else share
    equal, full = allocate_greens([1.0] * len(weights)), allocate_greens(weights)
    target = [e + share * (f - e) for e, f in zip(equal, full)]
    q = R["quantum_s"]
    greens = [int(t // q) * q for t in target]
    left = (green_budget(len(weights)) - sum(greens)) // q
    for i in sorted(range(len(target)), key=lambda i: (-(target[i] - greens[i]), -(full[i] - equal[i]), -weights[i], i))[:left]:
        greens[i] += q
    assert sum(greens) == green_budget(len(weights)) and all(R["min_green_s"] <= g <= R["max_green_s"] for g in greens)
    return greens


def legal_transfers(greens):
    q = R["quantum_s"]
    return [(d, r) for d, a in enumerate(greens) for r, b in enumerate(greens)
            if d != r and a - q >= R["min_green_s"] and b + q <= R["max_green_s"]]


def apply_transfer(greens, donor, recipient):
    if (donor, recipient) not in legal_transfers(greens):
        raise ValueError("Illegal green transfer")
    out = list(greens)
    out[donor] -= R["quantum_s"]
    out[recipient] += R["quantum_s"]
    return out
