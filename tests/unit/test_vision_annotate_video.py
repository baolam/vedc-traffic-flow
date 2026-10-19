"""annotate_video.py: drawing and writing the dashboard's recorded vision clip (no model file needed)."""
import sys
from pathlib import Path

import cv2
import numpy as np

sys.path.insert(0, str(Path(__file__).parents[2] / "services" / "vision"))
from annotate_video import draw_frame, open_writer  # noqa: E402
from roi_manager import ROIManager  # noqa: E402


def _rois():
    rois = ROIManager(width=320, height=240)
    rois.set_node_rois("J1", {"J1_N_IN": [(10, 10), (100, 10), (100, 100), (10, 100)]})
    rois.set_node_rois("J2", {"J2_N_IN": [(200, 10), (300, 10), (300, 100), (200, 100)]})
    return rois


def test_draw_frame_marks_boxes_inside_and_outside_rois():
    rois = _rois()
    frame = np.zeros((240, 320, 3), np.uint8)
    boxes = [(40, 40, 20, 20), (150, 180, 20, 20)]          # first inside J1_N_IN, second outside every ROI
    assigned = rois.assign_detections(boxes)
    assert assigned["J1_N_IN"] == [(40, 40, 20, 20)]
    out = draw_frame(frame, rois, {"J1_N_IN": "J1", "J2_N_IN": "J2"},
                     {"J1": (255, 0, 0), "J2": (0, 0, 255)}, boxes, assigned, "caption")
    assert out.shape == frame.shape
    assert not np.array_equal(out, frame)
    assert tuple(out[180, 150]) == (160, 160, 160)          # outside box drawn grey
    assert tuple(out[40, 40]) == (60, 220, 60)              # counted box drawn green


def test_writer_produces_a_readable_mp4(tmp_path):
    path = tmp_path / "clip.mp4"
    writer, fourcc = open_writer(path, 10.0, (320, 240))
    for i in range(5):
        writer.write(np.full((240, 320, 3), i * 40, np.uint8))
    writer.release()
    assert fourcc in ("avc1", "mp4v")
    cap = cv2.VideoCapture(str(path))
    ok, frame = cap.read()
    cap.release()
    assert ok and frame.shape == (240, 320, 3)
