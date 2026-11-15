"""Vision ROI visibility: a covered or blinded ROI must lower that approach's confidence, not read "0 cars"."""
import importlib.util
import sys
from pathlib import Path

import numpy as np

_VISION = Path(__file__).parents[2] / "services" / "vision"


def _load(name: str, file: str):
    spec = importlib.util.spec_from_file_location(name, _VISION / file)
    mod = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = mod
    spec.loader.exec_module(mod)
    return mod


rv = _load("vision_roi_visibility", "vision/roi_visibility.py")
tw = _load("vision_telemetry_window", "telemetry_window.py")

ROIS = {
    "J1_N_IN": {"polygon": np.array([[10, 10], [90, 10], [90, 60], [10, 60]], np.int32)},
    "J1_S_IN": {"polygon": np.array([[110, 10], [190, 10], [190, 60], [110, 60]], np.int32)},
}


def _road_frame() -> np.ndarray:
    """Grey road with white dashed lane markings in both ROIs (what an empty sa ban lane looks like)."""
    frame = np.full((80, 200, 3), 90, np.uint8)
    for x0 in range(15, 190, 20):
        frame[33:37, x0:x0 + 10] = 240
    return frame


def test_textured_roi_is_visible():
    vis = rv.RoiVisibility(min_edge_ratio=0.01)
    assert vis.blind_approaches(_road_frame(), ROIS) == set()


def test_uniform_cover_over_one_roi_marks_only_that_roi_blind():
    frame = _road_frame()
    frame[5:65, 5:95] = (190, 205, 225)  # flat cardboard over J1_N_IN
    vis = rv.RoiVisibility(min_edge_ratio=0.01)
    assert vis.blind_approaches(frame, ROIS) == {"J1_N_IN"}


def test_dark_frame_marks_every_roi_blind():
    vis = rv.RoiVisibility(min_edge_ratio=0.01)
    assert vis.blind_approaches(np.zeros((80, 200, 3), np.uint8), ROIS) == {"J1_N_IN", "J1_S_IN"}


def test_zero_threshold_disables_the_check():
    vis = rv.RoiVisibility(min_edge_ratio=0.0)
    assert vis.blind_approaches(np.zeros((80, 200, 3), np.uint8), ROIS) == set()


def _row(app: str, conf: float, q: float = 0.0) -> dict:
    return {"approach_id": app, "queue_vehicles": q, "flow_veh_per_s": 0.0, "mean_speed_mps": 0.0,
            "occupancy_ratio": 0.0, "confidence": conf}


def test_window_confidence_is_frame_validity_times_roi_visibility():
    win = tw.TelemetryWindow()
    for k in range(10):
        covered = k < 8  # J1_N_IN covered in 8 of 10 frames
        win.add({"J1": [_row("J1_N_IN", 0.0 if covered else 1.0), _row("J1_S_IN", 1.0, q=2)]}, k)
    rows = {r["approach_id"]: r for r in win.aggregate("J1")}
    assert rows["J1_N_IN"]["confidence"] == 0.2
    assert rows["J1_S_IN"]["confidence"] == 1.0
    assert rows["J1_S_IN"]["queue_vehicles"] == 2.0


def test_window_confidence_unchanged_for_healthy_rois_with_lost_frames():
    win = tw.TelemetryWindow()
    for k in range(3):
        win.add({"J1": [_row("J1_N_IN", 1.0)]}, k)
    win.add_failure()
    assert win.aggregate("J1")[0]["confidence"] == 0.75
