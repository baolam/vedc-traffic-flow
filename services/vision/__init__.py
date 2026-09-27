"""
EdgeFlow AI - Raspberry Pi 5 & Edge Vision Perception Service Package.
Provides video frame ingestion, YOLO/OpenCV vehicle detection, ROI mapping, and hardware monitoring.
"""

from .hardware_monitor import get_hardware_diagnostics, get_cpu_temperature, is_raspberry_pi

try:
    from .roi_manager import ROIManager
    from .metrics_extractor import MetricsExtractor
    from .detector import VehicleDetector
    from .perception_engine import PerceptionEngine
    from .video_source import BaseVideoSource, PiCameraVideoSource, WebcamVideoSource, FileVideoSource, SyntheticVideoSource
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
