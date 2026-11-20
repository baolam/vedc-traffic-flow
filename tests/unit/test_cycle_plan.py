import pytest

from contracts.benchmark import CYCLE_RULE
from src.control.cycle_plan import allocate_greens, apply_transfer, cycle_length, green_budget, legal_transfers


@pytest.mark.parametrize("phases,cycle", [(2, 70), (3, 75), (4, 100), (8, 200)])
def test_cycle_length_rule(phases, cycle):
    assert cycle_length(phases) == cycle
    assert green_budget(phases) == cycle - 5 * phases


@pytest.mark.parametrize("phases", range(2, 9))
def test_allocation_exact_budget_bounds_quantum(phases):
    for weights in ([1] * phases, [0] * phases, [100] + [0] * (phases - 1), list(range(1, phases + 1))):
        greens = allocate_greens(weights)
        assert sum(greens) == green_budget(phases)
        assert all(10 <= g <= 60 and g % 5 == 0 for g in greens)


def test_allocation_follows_weights_and_is_deterministic():
    greens = allocate_greens([5, 1])
    assert greens[0] > greens[1] and greens == allocate_greens([5, 1])


@pytest.mark.parametrize("phases", range(2, 9))
def test_eight_phase_cycle_has_legal_transfers(phases):
    assert legal_transfers(allocate_greens([1] * phases))


def test_no_transfer_when_everything_at_bounds():
    assert legal_transfers([10, 10]) == [] and legal_transfers([60, 60]) == []


def test_transfer_conserves_budget_and_rejects_illegal():
    greens = [30, 30]
    after = apply_transfer(greens, 0, 1)
    assert after == [25, 35] and sum(after) == sum(greens) and greens == [30, 30]
    with pytest.raises(ValueError):
        apply_transfer([10, 50], 0, 1)


def test_infeasible_phase_count_rejected():
    with pytest.raises(ValueError):
        allocate_greens([1])
    assert CYCLE_RULE["version"] == "multiphase_cycle_v1"
