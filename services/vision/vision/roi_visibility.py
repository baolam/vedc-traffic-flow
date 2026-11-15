"""
EdgeFlow AI - per-ROI visibility: tells "this lane is empty" from "this lane cannot be seen".

A frame that is captured fine can still be blind for one approach: a sheet of cardboard, a hand,
a sticker on the lens, glare or a dark corner. The detector then finds no car there and the
approach would report "0 vehicles" with full confidence, so the controller would believe the lane
is empty and the fairness guard (graph-control) would never step in.

An empty lane still has texture (lane markings, kerbs, stop lines, crosswalk edges); a cover does
not. Each frame, the share of Canny edge pixels inside each ROI polygon is measured: below
VISION_BLIND_EDGE_RATIO the ROI is blind for that frame and its approach reports confidence 0.0.
Measured on the 5-node sa ban video (15/11): covered ROI 0.000, the 19 others never below 0.046
(empty or with cars), so the default 0.01 has margin on both sides. 0 disables the check.
Limit: a real camera ROI over plain, unmarked asphalt can be near edge-free: recheck the ratio of
every ROI on the real camera (roi_calibrate.py) before relying on it.
"""
from typing import Any, Dict, Set, Tuple

import cv2
import numpy as np

CANNY_LOW, CANNY_HIGH = 50, 150


class RoiVisibility:
    def __init__(self, min_edge_ratio: float = 0.01) -> None:
        if min_edge_ratio < 0:
            raise ValueError("VISION_BLIND_EDGE_RATIO must be >= 0")
        self.min_edge_ratio = min_edge_ratio
        # (approach, frame shape) -> (bounding rect, mask over that rect, pixel count)
        self._masks: Dict[Tuple[str, Tuple[int, int]], Tuple[Tuple[int, int, int, int], np.ndarray, int]] = {}

    @property
    def enabled(self) -> bool:
        return self.min_edge_ratio > 0

    def _mask(self, approach_id: str, polygon: np.ndarray, shape: Tuple[int, int]):
        key = (approach_id, shape)
        if key not in self._masks:
            h, w = shape
            x, y, bw, bh = cv2.boundingRect(polygon)
            x0, y0, x1, y1 = max(x, 0), max(y, 0), min(x + bw, w), min(y + bh, h)
            mask = np.zeros((max(y1 - y0, 0), max(x1 - x0, 0)), np.uint8)
            cv2.fillPoly(mask, [polygon - np.array([x0, y0], np.int32)], 255)
            self._masks[key] = ((x0, y0, x1, y1), mask > 0, int((mask > 0).sum()))
        return self._masks[key]

    def edge_ratios(self, frame: np.ndarray, rois: Dict[str, Dict[str, Any]]) -> Dict[str, float]:
        """Share of edge pixels inside each ROI (0.0 for a ROI that lies outside the frame)."""
        gray = frame if frame.ndim == 2 else cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
        edges = cv2.Canny(gray, CANNY_LOW, CANNY_HIGH)
        out = {}
        for approach_id, info in rois.items():
            (x0, y0, x1, y1), mask, n = self._mask(approach_id, info["polygon"], gray.shape[:2])
            out[approach_id] = float((edges[y0:y1, x0:x1][mask] > 0).sum()) / n if n else 0.0
        return out

    def blind_approaches(self, frame: np.ndarray, rois: Dict[str, Dict[str, Any]]) -> Set[str]:
        """Approaches whose ROI shows (almost) no texture in this frame; empty when the check is off."""
        if not self.enabled or frame is None:
            return set()
        return {a for a, r in self.edge_ratios(frame, rois).items() if r < self.min_edge_ratio}
