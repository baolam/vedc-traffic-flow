import numpy as np
import pytest

from contracts.benchmark import CYCLE_DQN, OBSERVATION_SPEC
from src.control.cycle_dqn import CANDIDATE_DIM, GRID, NOOP, candidate_features, candidate_mask
from src.control.cycle_plan import legal_transfers

F, P_MAX = len(OBSERVATION_SPEC["features"]), OBSERVATION_SPEC["max_phases"]


def padded(greens):
    out = np.zeros(P_MAX, np.float32)
    out[: len(greens)] = greens
    return out


def test_dimensions_follow_the_contract():
    assert CANDIDATE_DIM == 2 * F + len(CYCLE_DQN["extras"]) and GRID == P_MAX * P_MAX + 1 and NOOP == GRID - 1


@pytest.mark.parametrize("greens", [[30, 30], [10, 50], [10, 10, 40], [20] * 8, [60, 10, 10, 10], [10, 60]])
def test_mask_matches_the_cycle_plan_rule_exactly(greens):
    mask = candidate_mask(padded(greens), len(greens))
    assert mask[NOOP]
    legal = {(s // P_MAX, s % P_MAX) for s in np.flatnonzero(mask[:NOOP])}
    assert legal == set(legal_transfers(greens))


def test_mask_has_only_noop_when_nothing_can_move():
    mask = candidate_mask(padded([10, 10]), 2)
    assert mask.sum() == 1 and mask[NOOP]


def test_features_are_finite_with_the_right_content():
    rng = np.random.default_rng(0)
    rows = rng.random((P_MAX, F)).astype(np.float32)
    greens = padded([30, 20, 10])
    feats = candidate_features(rows, greens, 3)
    assert feats.shape == (GRID, CANDIDATE_DIM) and np.isfinite(feats).all()
    slot = 0 * P_MAX + 1  # donor 0 -> recipient 1
    assert np.array_equal(feats[slot, :F], rows[0]) and np.array_equal(feats[slot, F : 2 * F], rows[1])
    donor_green, recipient_green = feats[slot, 2 * F + 1], feats[slot, 2 * F + 2]
    assert (donor_green, recipient_green) == (pytest.approx(30 / 60), pytest.approx(20 / 60))
    assert feats[NOOP, 2 * F] == 1 and not feats[NOOP, :2 * F].any()  # no-op: flagged, no rows
    assert feats[slot, 2 * F] == 0 and feats[slot, -1] == pytest.approx(75 / 200)  # 3 phases -> 75 s cycle


def test_batches_match_single_calls():
    rng = np.random.default_rng(1)
    rows = rng.random((4, P_MAX, F)).astype(np.float32)
    greens = np.stack([padded([30, 30]), padded([20, 20, 20]), padded([10, 40, 10, 20]), padded([20] * 8)])
    phases = np.array([2, 3, 4, 8])
    batch, mask = candidate_features(rows, greens, phases), candidate_mask(greens, phases)
    for i in range(4):
        assert np.array_equal(batch[i], candidate_features(rows[i], greens[i], phases[i]))
        assert np.array_equal(mask[i], candidate_mask(greens[i], phases[i]))
