from typing import Dict, List, Tuple, Any, Optional
import numpy as np
import cv2

class ROIManager:
    """
    Manages Region of Interest (ROI) boundaries per approach ID for intersection nodes.
    Determines which approach polygon/box each detected vehicle belongs to.
    """
    def __init__(self, width: int = 640, height: int = 480):
        self.width = width
        self.height = height
        self.rois: Dict[str, Dict[str, Any]] = {}

    def setup_default_node_rois(self, node_id: str = "J1", approach_ids: Optional[List[str]] = None) -> None:
        """
        Configures up to 4 quadrant ROIs for a 640x480 demo frame, one per real approach_id
        from the node's topology contract (falls back to the synthetic J1-style N/S/E/W IDs
        only when no real approach list is given, e.g. standalone/offline testing).

        The quadrant *positions* are still a fixed synthetic layout (this is one canned demo
        video, not real per-node footage); what changed is that each quadrant is now labeled
        with the node's actual approach_id, so downstream telemetry/reports key on IDs that
        really exist in the topology contract instead of inventing "{node_id}_N_IN" etc. for
        every node regardless of its real approach naming (SUMO-derived topologies use raw
        edge IDs, not a N/S/E/W convention).
        """
        cx, cy = self.width // 2, self.height // 2
        ids = list(approach_ids) if approach_ids else [
            f"{node_id}_N_IN", f"{node_id}_S_IN", f"{node_id}_E_IN", f"{node_id}_W_IN"
        ]
        ids = ids[:4]

        slots = [
            {  # west quadrant
                "polygon": np.array([[0, cy], [cx - 50, cy], [cx - 50, cy + 50], [0, cy + 50]], np.int32),
                "box": (0, cy, cx - 50, cy + 50),
                "stop_line_x": cx - 50
            },
            {  # east quadrant
                "polygon": np.array([[cx + 50, cy - 50], [self.width, cy - 50], [self.width, cy], [cx + 50, cy]], np.int32),
                "box": (cx + 50, cy - 50, self.width, cy),
                "stop_line_x": cx + 50
            },
            {  # north quadrant
                "polygon": np.array([[cx - 50, 0], [cx, 0], [cx, cy - 50], [cx - 50, cy - 50]], np.int32),
                "box": (cx - 50, 0, cx, cy - 50),
                "stop_line_y": cy - 50
            },
            {  # south quadrant
                "polygon": np.array([[cx, cy + 50], [cx + 50, cy + 50], [cx + 50, self.height], [cx, self.height]], np.int32),
                "box": (cx, cy + 50, cx + 50, self.height),
                "stop_line_y": cy + 50
            },
        ]

        self.rois = {app_id: slots[i] for i, app_id in enumerate(ids)}

    def set_node_rois(self, node_id: str, polygons: Dict[str, Any]) -> None:
        """Adds calibrated approach polygons for one node (several nodes may share one camera)."""
        for approach_id, points in polygons.items():
            self.rois[approach_id] = {
                "node_id": node_id,
                "polygon": np.array(points, np.int32),
            }

    def approaches_for_node(self, node_id: str) -> List[str]:
        """
        Approach IDs belonging to a node, in insertion order. Real approach_ids (e.g. raw SUMO
        edge IDs) don't necessarily start with "{node_id}_", so membership is tracked via the
        "node_id" tag set by set_node_rois, or assumed to all belong to node_id when untagged
        (setup_default_node_rois holds exactly one node's ROIs at a time).
        """
        return [app_id for app_id, info in self.rois.items()
                if info.get("node_id", node_id) == node_id]

    def assign_detections(self, detections: List[Tuple[int, int, int, int]]) -> Dict[str, List[Tuple[int, int, int, int]]]:
        """
        Assigns a list of bounding boxes (x, y, w, h) to approach IDs based on center point containment.
        Returns dict mapping approach_id -> list of detection boxes.
        """
        result: Dict[str, List[Tuple[int, int, int, int]]] = {app_id: [] for app_id in self.rois}
        
        for (x, y, w, h) in detections:
            center_x = x + w // 2
            center_y = y + h // 2
            
            for app_id, roi_info in self.rois.items():
                poly = roi_info["polygon"]
                # pointPolygonTest returns >= 0 if inside or on edge
                if cv2.pointPolygonTest(poly, (float(center_x), float(center_y)), False) >= 0:
                    result[app_id].append((x, y, w, h))
                    break

        return result

    def get_roi_area(self, approach_id: str) -> float:
        """Returns area of ROI polygon in square pixels."""
        if approach_id in self.rois:
            poly = self.rois[approach_id]["polygon"]
            return float(cv2.contourArea(poly))
        return 10000.0
