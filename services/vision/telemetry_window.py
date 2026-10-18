"""
EdgeFlow AI - reduce the frames processed during one telemetry period to one value per approach.

The service processes frames continuously (up to VISION_FPS) and publishes once per
TELEMETRY_PERIOD_S. Each published field is the median over the period's frames, so one frame
that misses or double-counts a car does not move the queue. `confidence` is the share of the
period's frames that were actually captured and processed: 1.0 with a healthy camera (as the
simulator sends), lower when frames were lost, and no approaches at all when none was processed.
"""

from typing import Any, Dict, List, Optional

import numpy as np

MEDIAN_FIELDS = ("queue_vehicles", "flow_veh_per_s", "mean_speed_mps", "occupancy_ratio")


class TelemetryWindow:
    def __init__(self) -> None:
        self.reset()

    def reset(self) -> None:
        self.samples: List[Dict[str, List[Dict[str, Any]]]] = []
        self.failed = 0
        self.last_capture_ms: Optional[int] = None

    @property
    def frames(self) -> int:
        return len(self.samples)

    def add(self, per_node: Dict[str, List[Dict[str, Any]]], captured_at_ms: int) -> None:
        self.samples.append(per_node)
        self.last_capture_ms = captured_at_ms

    def add_failure(self) -> None:
        self.failed += 1

    def validity(self) -> float:
        total = self.frames + self.failed
        return self.frames / total if total else 0.0

    def aggregate(self, node_id: str) -> List[Dict[str, Any]]:
        """Per-approach medians for one node; [] when the period had no processed frame."""
        rows_by_approach: Dict[str, List[Dict[str, Any]]] = {}
        for per_node in self.samples:
            for row in per_node.get(node_id, []):
                rows_by_approach.setdefault(row["approach_id"], []).append(row)
        confidence = round(self.validity(), 3)
        return [
            {"approach_id": approach_id,
             **{key: round(float(np.median([r[key] for r in rows])), 3) for key in MEDIAN_FIELDS},
             "confidence": confidence}
            for approach_id, rows in rows_by_approach.items()
        ]
