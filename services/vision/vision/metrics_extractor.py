import time
from typing import Dict, List, Tuple, Any, Optional

class MetricsExtractor:
    """
    Translates vision detection bounding boxes and tracking history into
    canonical EdgeFlow telemetry metrics per approach (queue, flow, speed, occupancy, confidence).
    """
    def __init__(self, speed_scale_factor: float = 0.1):
        self.speed_scale_factor = speed_scale_factor
        self._history: Dict[str, Tuple[float, float]] = {}  # approach_id -> (timestamp_s, queue_vehicles)

    def compute_approach_metrics(
        self,
        approach_id: str,
        boxes: List[Tuple[int, int, int, int]],
        roi_area: float,
        detection_confidence: float = 0.95,
        timestamp_s: Optional[float] = None
    ) -> Dict[str, Any]:
        """
        Computes telemetry dict for one approach matching contracts/schemas/telemetry.json.
        """
        num_vehicles = len(boxes)
        
        # Calculate vehicle bounding box areas sum
        total_veh_area = sum(w * h for (_, _, w, h) in boxes)
        
        # Occupancy ratio bounded strictly between [0.0, 1.0]
        occupancy_ratio = min(max(total_veh_area / max(roi_area, 1.0), 0.0), 1.0)
        
        # Queue count: count of vehicles in ROI (in vision ROI, all detected vehicles in lane constitute queue/demand)
        queue_vehicles = float(num_vehicles)

        now = timestamp_s if timestamp_s is not None else time.time()

        # Dynamic flow estimation based on arrival & discharge dynamics
        if approach_id in self._history:
            prev_time, prev_q = self._history[approach_id]
            dt = max(0.05, now - prev_time)
            # Combine delta vehicles with queue throughput factor
            delta_q = abs(queue_vehicles - prev_q)
            dynamic_rate = (delta_q / dt) * 0.4 + (queue_vehicles * 0.06)
            flow_veh_per_s = round(min(max(dynamic_rate, 0.0), 2.5), 4)
        else:
            flow_veh_per_s = round(queue_vehicles * 0.08, 4)

        self._history[approach_id] = (now, queue_vehicles)

        # Estimated mean speed in m/s (scale from bounding box width / movement)
        mean_speed_mps = round(min(max(2.5 * (1.0 - occupancy_ratio * 0.8), 0.5), 15.0), 2)

        # Overall vision confidence ratio bounded [0.0, 1.0]
        confidence = round(min(max(detection_confidence, 0.0), 1.0), 2)

        return {
            "approach_id": approach_id,
            "queue_vehicles": queue_vehicles,
            "flow_veh_per_s": flow_veh_per_s,
            "mean_speed_mps": mean_speed_mps,
            "occupancy_ratio": round(occupancy_ratio, 4),
            "confidence": confidence
        }
