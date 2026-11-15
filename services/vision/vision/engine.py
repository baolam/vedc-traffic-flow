import time
from typing import Dict, List, Any, Optional, Tuple
import logging
import numpy as np
import cv2

from .video_source import BaseVideoSource, create_video_source
from .roi_manager import ROIManager
from .metrics_extractor import MetricsExtractor
from .detector import VehicleDetector
from .motion_estimator import MotionEstimator
from .roi_visibility import RoiVisibility

logger = logging.getLogger("vision-service")


class PerceptionEngine:
    """
    Core Vision Perception Engine combining video frame ingestion, motion/contour tracking,
    ROI vehicle mapping, and traffic state metrics extraction.
    """
    def __init__(self, video_source_str: str = "synthetic", width: int = 640, height: int = 480,
                 model_path=None, input_size=640, output_format="yolov8", motion_scale=1.0,
                 conf_threshold=.4, num_classes=80, vehicle_classes=(2, 3, 5, 7),
                 lens_position=None, flicker_period_us=10000, px_per_m=1000.0,
                 blind_edge_ratio=0.01):
        self.video_source: BaseVideoSource = create_video_source(
            video_source_str, width=width, height=height,
            lens_position=lens_position, flicker_period_us=flicker_period_us)
        self.roi_manager = ROIManager(width=width, height=height)
        self.metrics_extractor = MetricsExtractor()
        # Measured box motion replaces the occupancy-based speed estimate (motion_estimator.py)
        self.motion = MotionEstimator(px_per_m)
        # A covered/blinded ROI reports confidence 0.0, not "0 vehicles" (roi_visibility.py)
        self.visibility = RoiVisibility(blind_edge_ratio)
        self.blind: set = set()
        self.detector = VehicleDetector(model_path=model_path, input_size=input_size,
                                        output_format=output_format, motion_scale=motion_scale,
                                        conf_threshold=conf_threshold, num_classes=num_classes,
                                        vehicle_classes=vehicle_classes)
        self.width = width
        self.height = height
        self.node_id = None
        self.node_ids: Optional[List[str]] = None
        # Last processed frame: wall-clock capture time (ms) plus measured stage timings; {} on failure.
        # A processed frame reports confidence 1.0; main.TelemetryWindow lowers it when frames are lost.
        self.last_frame: Dict[str, Any] = {}
        # Raw frame + its assigned detection boxes, kept only for an optional caller (video sync to the
        # platform, see services/vision/streaming/live_stream.py) -- None whenever nothing read this
        # frame yet or the last read failed. A plain attribute, not returned by process_frame_nodes(),
        # so callers that don't need pixels (the normal telemetry-only path) pay no extra cost.
        # (frame, boxes assigned to an approach, every detected box including ones outside any ROI)
        self.last_rendered: Optional[Tuple[np.ndarray, Dict[str, List[Tuple[int, int, int, int]]],
                                           List[Tuple[int, int, int, int]]]] = None

    def setup_topology(self, topology: Dict[str, Any], node_id: str = "J1") -> None:
        """Sets up the default (uncalibrated) ROIs for a single node."""
        self.roi_manager.setup_default_node_rois(node_id=node_id)
        self.node_id = node_id
        self.node_ids = [node_id]

    def setup_nodes(self, node_ids: List[str], roi_nodes: Optional[Dict[str, Dict[str, Any]]] = None) -> None:
        """
        Sets up ROIs for one or more nodes seen by this camera. Several nodes require
        calibrated polygons: the default single-node layout must never be reused for another node.
        """
        if not node_ids:
            raise ValueError("At least one node ID is required")
        if roi_nodes is None:
            if len(node_ids) > 1:
                raise ValueError("Several nodes on one camera need a ROI calibration file (ROI_CONFIG_PATH)")
            self.roi_manager.setup_default_node_rois(node_id=node_ids[0])
        else:
            self.roi_manager.rois = {}
            for node_id in node_ids:
                if node_id not in roi_nodes:
                    raise ValueError(f"No ROI polygons for node {node_id}")
                self.roi_manager.set_node_rois(node_id, roi_nodes[node_id])
        self.node_ids = list(node_ids)
        self.node_id = node_ids[0] if len(node_ids) == 1 else None

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
        if self.node_ids is not None and node_id not in self.node_ids:
            raise ValueError("A camera ROI mapping belongs to its configured nodes only")
        if self.node_ids is not None and len(self.node_ids) > 1:
            return self.process_frame_nodes().get(node_id, [])
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
        self._update_blind(frame)

        # Calculate approach metrics
        approaches_telemetry = []
        for app_id, app_boxes in assigned_boxes.items():
            roi_area = self.roi_manager.get_roi_area(app_id)
            metrics = self.metrics_extractor.compute_approach_metrics(
                approach_id=app_id,
                boxes=app_boxes,
                roi_area=roi_area,
                detection_confidence=0.0 if app_id in self.blind else 1.0
            )
            metrics["mean_speed_mps"] = self.motion.update(app_id, app_boxes, time.time())
            approaches_telemetry.append(metrics)

        return approaches_telemetry

    def process_frame_nodes(self) -> Dict[str, List[Dict[str, Any]]]:
        """
        Reads one frame, detects once, and returns approach metrics per configured node.
        Returns {} when no frame is available (the caller reports missing data).
        """
        started = time.perf_counter()
        ret, frame = self.video_source.read_frame()
        if not ret or frame is None:
            self.last_frame = {}
            self.last_rendered = None
            return {}
        frame_info = {"captured_at_ms": int(time.time() * 1000),
                      "capture_ms": (time.perf_counter() - started) * 1000}
        if frame.shape[:2] != (self.height, self.width):
            frame = cv2.resize(frame, (self.width, self.height), interpolation=cv2.INTER_AREA)

        all_boxes = self.detect_vehicles(frame)
        assigned_boxes = self.roi_manager.assign_detections(all_boxes)
        self._update_blind(frame)
        self.last_frame = {**frame_info, **self.detector.last_timings}
        self.last_rendered = (frame, assigned_boxes, all_boxes)
        results: Dict[str, List[Dict[str, Any]]] = {}
        t_s = frame_info["captured_at_ms"] / 1000.0
        for node_id in self.node_ids or []:
            rows = []
            for app_id in self.roi_manager.approaches_for_node(node_id):
                boxes = assigned_boxes.get(app_id, [])
                metrics = self.metrics_extractor.compute_approach_metrics(
                    approach_id=app_id,
                    boxes=boxes,
                    roi_area=self.roi_manager.get_roi_area(app_id),
                    detection_confidence=0.0 if app_id in self.blind else 1.0
                )
                metrics["mean_speed_mps"] = self.motion.update(app_id, boxes, t_s)
                rows.append(metrics)
            results[node_id] = rows
        return results

    def _update_blind(self, frame: np.ndarray) -> None:
        """Marks ROIs without texture this frame; logs each blind episode once (start and end)."""
        blind = self.visibility.blind_approaches(frame, self.roi_manager.rois)
        for app_id in sorted(blind - self.blind):
            logger.warning(f"{app_id}: ROI shows no texture (covered, blinded or dark): "
                           "confidence 0 while it lasts, its '0 vehicles' is unknown, not empty")
        for app_id in sorted(self.blind - blind):
            logger.info(f"{app_id}: ROI visible again")
        self.blind = blind

    def close(self) -> None:
        """Cleanup video source resources."""
        if self.video_source:
            self.video_source.release()


def build_engine_from_settings(settings, node_ids: List[str],
                               roi_nodes: Optional[Dict[str, Dict[str, Any]]] = None,
                               frame_size: Optional[Tuple[int, int]] = None) -> PerceptionEngine:
    """Builds a PerceptionEngine the same way every caller needs to: one VehicleDetector, one
    video source, ROIs for every node this camera covers. Centralizes what used to be
    independently duplicated in main.py, demo_video_pipeline.py and benchmark.py."""
    width, height = frame_size or (640, 480)
    engine = PerceptionEngine(
        video_source_str=settings.video_source,
        width=width,
        height=height,
        model_path=settings.detection_model_path or None,
        input_size=settings.detector_input_size,
        output_format=settings.detector_output_format,
        motion_scale=settings.motion_scale,
        conf_threshold=settings.confidence_threshold,
        num_classes=settings.detector_num_classes,
        vehicle_classes=tuple(int(c) for c in settings.detector_vehicle_classes.split(",")),
        lens_position=settings.camera_lens_position,
        flicker_period_us=settings.camera_flicker_period_us,
        px_per_m=getattr(settings, "vision_px_per_m", 1000.0),
        blind_edge_ratio=getattr(settings, "vision_blind_edge_ratio", 0.01),
    )
    engine.setup_nodes(node_ids, roi_nodes)
    return engine
