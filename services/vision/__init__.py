"""
EdgeFlow AI - Raspberry Pi 5 & Edge Vision Perception Service Package.
Provides video frame ingestion, YOLO/OpenCV vehicle detection, ROI mapping, and hardware monitoring.
"""

from .connectivity.hardware_monitor import get_hardware_diagnostics, get_cpu_temperature, is_raspberry_pi

try:
    from .vision.roi_manager import ROIManager
    from .vision.metrics_extractor import MetricsExtractor
    from .vision.detector import VehicleDetector
    from .vision.engine import PerceptionEngine
    from .vision.video_source import BaseVideoSource, PiCameraVideoSource, WebcamVideoSource, FileVideoSource, SyntheticVideoSource
except (ImportError, AttributeError):
    ROIManager = None
    MetricsExtractor = None
    VehicleDetector = None
    PerceptionEngine = None
    BaseVideoSource = None

__all__ = [
    "get_hardware_diagnostics",
    "get_cpu_temperature",
    "is_raspberry_pi",
    "ROIManager",
    "MetricsExtractor",
    "VehicleDetector",
    "PerceptionEngine",
]
