"""
EdgeFlow AI - measured vehicle motion per approach (replaces the occupancy-based speed formula).

Each frame, every vehicle box of an approach is matched to the nearest box of the same approach in
the previous frame; the displacement of the box centres over the frame interval is its speed.
The approach speed is the 75th percentile of the matched speeds: a discharging queue (front cars
moving) reads clearly above zero, a stopped queue reads close to zero, and one mismatched box does
not dominate. The graph-control fairness guard uses this to tell a blocked lane (queue neither
drops nor moves) from an oversaturated one (queue never drops but moves).

Units: pixels are converted with VISION_PX_PER_M, pixels per metre of the scene at the stop lines
(sa ban video 1280 px over ~1.2 m of tarp: ~1000). It is an estimate: perspective is ignored, so it
is accurate enough to separate "moving" from "stopped", not to measure real speeds.
"""
import math
from typing import Dict, List, Optional, Sequence, Tuple

Box = Tuple[int, int, int, int]  # x, y, w, h

# A box may move at most this many of its own sizes between two frames and still be the same car
MAX_JUMP_BOX_SIZES = 1.0
SPEED_PERCENTILE = 75.0


def _centre(box: Box) -> Tuple[float, float]:
    x, y, w, h = box
    return x + w / 2.0, y + h / 2.0


def _percentile(values: Sequence[float], q: float) -> float:
    ordered = sorted(values)
    pos = (len(ordered) - 1) * q / 100.0
    lo, hi = math.floor(pos), math.ceil(pos)
    return ordered[lo] + (ordered[hi] - ordered[lo]) * (pos - lo)


class MotionEstimator:
    def __init__(self, px_per_m: float = 1000.0) -> None:
        if px_per_m <= 0:
            raise ValueError("VISION_PX_PER_M must be positive")
        self.px_per_m = px_per_m
        self._previous: Dict[str, Tuple[float, List[Box]]] = {}

    def update(self, approach_id: str, boxes: Sequence[Box], t_s: float) -> float:
        """Speed (m/s) of the approach's vehicles since its previous frame; 0.0 when unknown."""
        previous: Optional[Tuple[float, List[Box]]] = self._previous.get(approach_id)
        self._previous[approach_id] = (t_s, list(boxes))
        if previous is None or not boxes or not previous[1]:
            return 0.0
        dt = t_s - previous[0]
        if dt <= 0:
            return 0.0
        prev_centres = [_centre(b) for b in previous[1]]
        speeds: List[float] = []
        for box in boxes:
            cx, cy = _centre(box)
            dist = min(math.hypot(cx - px, cy - py) for px, py in prev_centres)
            if dist <= MAX_JUMP_BOX_SIZES * max(box[2], box[3]):
                speeds.append(dist / dt / self.px_per_m)
        return round(_percentile(speeds, SPEED_PERCENTILE), 4) if speeds else 0.0

    def reset(self) -> None:
        self._previous.clear()
