import pytest

from src.rl.selection import validation_score
from src.rl.stopping import Plateau


def test_plateau_small_improvements_keep_checkpoint_but_do_not_reset_patience():
    p = Plateau(patience=3)
    assert p.update(100.0) == dict(improved_best=True, stop=False)
    assert p.update(99.5)["improved_best"] and not p.update(99.4)["stop"]  # <1% vs anchor 100: stale 1 then 2
    out = p.update(99.3)
    assert out["improved_best"] and out["stop"] and p.best == 99.3  # stale reached 3


def test_plateau_real_improvement_resets_anchor():
    p = Plateau(patience=2)
    p.update(100.0)
    p.update(100.5)
    assert p.update(90.0) == dict(improved_best=True, stop=False)
    assert p.stale == 0 and p.anchor == 90.0


def test_infeasible_checks_never_become_best_but_count_as_stale():
    p = Plateau(patience=2)
    p.update(100.0)
    assert p.update(1.0, feasible=False) == dict(improved_best=False, stop=False)
    assert p.update(1.0, feasible=False)["stop"] and p.best == 100.0


def test_plateau_state_roundtrip_and_near_zero_floor():
    p = Plateau(patience=5)
    p.update(0.0)
    q = Plateau(patience=5)
    q.load(p.state())
    assert q.state() == p.state()
    assert q.update(0.0)["stop"] is False and q.stale == 1  # no divide-by-zero, no false improvement


def row(scenario, seed, delay, **kw):
    base = dict(scenario=scenario, seed=seed, valid=True, collisions=0, teleports=0, accounting_losses=0,
                scheduled=100, completed=100, delay_per_scheduled_s=delay, p95_wait_s=10.0,
                worst_approach_wait_s=20.0, max_approach_p95_wait_s=15.0)
    base.update(kw)
    return base


CASES, SEEDS = ["a", "b"], [1, 2]


def rows(delay_a, delay_b, **kw):
    return [row(s, k, d, **kw) for s, d in (("a", delay_a), ("b", delay_b)) for k in SEEDS]


def test_score_is_equal_case_mean_and_feasible():
    r = validation_score(rows(10, 30), rows(12, 40), CASES, SEEDS)
    assert r["feasible"] and r["score"] == pytest.approx(20.0)


@pytest.mark.parametrize("bad", [dict(collisions=1), dict(valid=False), dict(completed=90),
                                 dict(p95_wait_s=50.0)])
def test_guardrail_violations_are_infeasible(bad):
    r = validation_score(rows(10, 30, **bad), rows(12, 40), CASES, SEEDS)
    assert not r["feasible"] and r["reasons"] and r["score"] == pytest.approx(20.0)


def test_incomplete_pairs_are_infeasible_with_infinite_score():
    r = validation_score(rows(10, 30)[:-1], rows(12, 40), CASES, SEEDS)
    assert not r["feasible"] and r["score"] == float("inf")
