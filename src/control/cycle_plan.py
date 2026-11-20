"""Native-phase fair-cycle timing: cycle length, green allocation and legal 5 s transfers."""
from contracts.benchmark import CYCLE_RULE as R


def cycle_length(phases):
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
