import sys
import os
from pathlib import Path
from typing import Dict, List, Any, Tuple
import numpy as np
import cv2

# Ensure services/vision directory is in sys.path for IDE & module resolution
CURR_DIR = Path(__file__).resolve().parent
if str(CURR_DIR) not in sys.path:
    sys.path.insert(0, str(CURR_DIR))

try:
    from video_source import BaseVideoSource, create_video_source
    from roi_manager import ROIManager
    from metrics_extractor import MetricsExtractor
except ImportError:
    from services.vision.video_source import BaseVideoSource, create_video_source
    from services.vision.roi_manager import ROIManager
    from services.vision.metrics_extractor import MetricsExtractor

class PerceptionEngine:
    """
    Core Vision Perception Engine combining video frame ingestion, motion/contour tracking,
    ROI vehicle mapping, and traffic state metrics extraction.
    """
    def __init__(self, video_source_str: str = "synthetic", width: int = 640, height: int = 480):
        self.video_source: BaseVideoSource = create_video_source(video_source_str)
        self.roi_manager = ROIManager(width=width, height=height)
        self.metrics_extractor = MetricsExtractor()
        self.bg_subtractor = cv2.createBackgroundSubtractorMOG2(history=500, varThreshold=25, detectShadows=False)
        self.width = width
        self.height = height

    def setup_topology(self, topology: Dict[str, Any], node_id: str = "J1") -> None:
        """Sets up ROIs for the specified node in topology."""
        self.roi_manager.setup_default_node_rois(node_id=node_id)

    def detect_vehicles(self, frame: np.ndarray) -> List[Tuple[int, int, int, int]]:
        """
        Detects vehicle bounding boxes (x, y, w, h) using OpenCV motion contours.
        """
        if frame is None:
            return []

        # Apply background subtraction
        fg_mask = self.bg_subtractor.apply(frame)

        # Threshold and morphology filtering
        _, thresh = cv2.threshold(fg_mask, 200, 255, cv2.THRESH_BINARY)
        kernel = cv2.getStructuringElement(cv2.MORPH_RECT, (5, 5))
        dilated = cv2.dilate(thresh, kernel, iterations=2)

        contours, _ = cv2.findContours(dilated, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)

        boxes: List[Tuple[int, int, int, int]] = []
        min_area = 200  # Filter out tiny noise

        for cnt in contours:
            if cv2.contourArea(cnt) >= min_area:
                x, y, w, h = cv2.boundingRect(cnt)
                boxes.append((x, y, w, h))

        return boxes

    def process_frame(self, node_id: str = "J1") -> List[Dict[str, Any]]:
        """
        Reads one frame, runs vehicle detection, maps to ROIs, and returns approach metrics list.
        """
        ret, frame = self.video_source.read_frame()
        if not ret or frame is None:
            return []

        # Detect vehicle boxes
        boxes = self.detect_vehicles(frame)

        # Map boxes to ROIs
        assigned_boxes = self.roi_manager.assign_detections(boxes)

        # Calculate approach metrics
        approaches_telemetry = []
        for app_id, app_boxes in assigned_boxes.items():
            roi_area = self.roi_manager.get_roi_area(app_id)
            metrics = self.metrics_extractor.compute_approach_metrics(
                approach_id=app_id,
                boxes=app_boxes,
                roi_area=roi_area,
                detection_confidence=0.92
            )
            approaches_telemetry.append(metrics)

        return approaches_telemetry

    def close(self) -> None:
        """Cleanup video source resources."""
        if self.video_source:
            self.video_source.release()
