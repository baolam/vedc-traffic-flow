from typing import Dict, List, Tuple, Any
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

    def setup_default_node_rois(self, node_id: str = "J1") -> None:
        """Configures default 4-approach ROIs for a 640x480 frame."""
        cx, cy = self.width // 2, self.height // 2
        
        # Define 4 quadrant approaches around intersection center
        self.rois = {
            f"{node_id}_W_IN": {
                "polygon": np.array([[0, cy], [cx - 50, cy], [cx - 50, cy + 50], [0, cy + 50]], np.int32),
                "box": (0, cy, cx - 50, cy + 50),
                "stop_line_x": cx - 50
            },
            f"{node_id}_E_IN": {
                "polygon": np.array([[cx + 50, cy - 50], [self.width, cy - 50], [self.width, cy], [cx + 50, cy]], np.int32),
                "box": (cx + 50, cy - 50, self.width, cy),
                "stop_line_x": cx + 50
            },
            f"{node_id}_N_IN": {
                "polygon": np.array([[cx - 50, 0], [cx, 0], [cx, cy - 50], [cx - 50, cy - 50]], np.int32),
                "box": (cx - 50, 0, cx, cy - 50),
                "stop_line_y": cy - 50
            },
            f"{node_id}_S_IN": {
                "polygon": np.array([[cx, cy + 50], [cx + 50, cy + 50], [cx + 50, self.height], [cx, self.height]], np.int32),
                "box": (cx, cy + 50, cx + 50, self.height),
                "stop_line_y": cy + 50
            },
        }

    def set_node_rois(self, node_id: str, polygons: Dict[str, Any]) -> None:
        """Adds calibrated approach polygons for one node (several nodes may share one camera)."""
        for approach_id, points in polygons.items():
            self.rois[approach_id] = {
                "node_id": node_id,
                "polygon": np.array(points, np.int32),
            }

    def approaches_for_node(self, node_id: str) -> List[str]:
        """Approach IDs belonging to a node, in insertion order."""
        return [app_id for app_id, info in self.rois.items()
                if info.get("node_id", node_id) == node_id and app_id.startswith(f"{node_id}_")]

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
