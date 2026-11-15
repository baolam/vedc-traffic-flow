"""Vision motion estimator: measured box motion, the signal that separates a blocked lane from a busy one."""
import importlib.util
import sys
from pathlib import Path

import pytest

_PATH = Path(__file__).parents[2] / "services" / "vision" / "vision" / "motion_estimator.py"
_spec = importlib.util.spec_from_file_location("vision_motion_estimator", _PATH)
me = importlib.util.module_from_spec(_spec)
sys.modules[_spec.name] = me
_spec.loader.exec_module(me)


def test_first_frame_and_empty_roi_read_zero():
    est = me.MotionEstimator(px_per_m=1000)
    assert est.update("A", [(0, 0, 40, 20)], 0.0) == 0.0
    assert est.update("A", [], 0.5) == 0.0


def test_moving_boxes_give_their_speed_in_metres_per_second():
    est = me.MotionEstimator(px_per_m=1000)
    est.update("A", [(100, 100, 40, 20), (200, 100, 40, 20)], 0.0)
    speed = est.update("A", [(120, 100, 40, 20), (220, 100, 40, 20)], 0.25)  # 20 px in 0.25 s
    assert speed == pytest.approx(0.08)


def test_stopped_queue_reads_near_zero_despite_detection_jitter():
    est = me.MotionEstimator(px_per_m=1000)
    est.update("A", [(100, 100, 40, 20), (150, 100, 40, 20)], 0.0)
    assert est.update("A", [(101, 100, 40, 20), (150, 101, 40, 20)], 0.25) < 0.02


def test_far_jump_is_a_different_car_not_a_fast_one():
    est = me.MotionEstimator(px_per_m=1000)
    est.update("A", [(100, 100, 40, 20)], 0.0)
    assert est.update("A", [(400, 100, 40, 20)], 0.25) == 0.0


def test_approaches_are_tracked_separately_and_scale_must_be_positive():
    est = me.MotionEstimator(px_per_m=1000)
    est.update("A", [(100, 100, 40, 20)], 0.0)
    assert est.update("B", [(120, 100, 40, 20)], 0.25) == 0.0
    with pytest.raises(ValueError):
        me.MotionEstimator(px_per_m=0)
