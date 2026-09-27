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
    from detector import VehicleDetector
except ImportError:
    from services.vision.video_source import BaseVideoSource, create_video_source
    from services.vision.roi_manager import ROIManager
    from services.vision.metrics_extractor import MetricsExtractor
    from services.vision.detector import VehicleDetector

class PerceptionEngine:
    """
    Core Vision Perception Engine combining video frame ingestion, motion/contour tracking,
    ROI vehicle mapping, and traffic state metrics extraction.
    """
    def __init__(self, video_source_str: str = "synthetic", width: int = 640, height: int = 480,
                 model_path=None, input_size=640, output_format="yolov8", motion_scale=1.0,
                 conf_threshold=.4, num_classes=80, vehicle_classes=(2, 3, 5, 7)):
        self.video_source: BaseVideoSource = create_video_source(video_source_str)
        self.roi_manager = ROIManager(width=width, height=height)
        self.metrics_extractor = MetricsExtractor()
        self.detector = VehicleDetector(model_path=model_path, input_size=input_size,
                                        output_format=output_format, motion_scale=motion_scale,
                                        conf_threshold=conf_threshold, num_classes=num_classes,
                                        vehicle_classes=vehicle_classes)
        self.width = width
        self.height = height
        self.node_id = None

    def setup_topology(self, topology: Dict[str, Any], node_id: str = "J1") -> None:
        """Sets up ROIs for the specified node in topology."""
        self.roi_manager.setup_default_node_rois(node_id=node_id)
        self.node_id = node_id

    def detect_vehicles(self, frame: np.ndarray) -> List[Tuple[int, int, int, int]]:
        """
        Detects vehicle bounding boxes (x, y, w, h) using OpenCV motion contours.
        """
        if frame is None:
            return []

        return self.detector.detect(frame)[0]

    def process_frame(self, node_id: str = "J1") -> List[Dict[str, Any]]:
        """
        Reads one frame, runs vehicle detection, maps to ROIs, and returns approach metrics list.
        """
        if self.node_id is not None and node_id != self.node_id:
            raise ValueError("A camera ROI mapping belongs to one configured node")
        ret, frame = self.video_source.read_frame()
        if not ret or frame is None:
            return []

        # ROI coordinates use the configured frame geometry, including real videos.
        if frame.shape[:2] != (self.height, self.width):
            frame = cv2.resize(frame, (self.width, self.height), interpolation=cv2.INTER_AREA)

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
