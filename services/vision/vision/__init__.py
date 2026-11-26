"""
EdgeFlow AI - Vision / YOLO perception module.
-----------------------------------------------
Everything needed to go from a video frame to per-approach traffic metrics: video ingestion,
vehicle detection, ROI-to-approach assignment, and metric extraction. This package's public
surface is re-exported here so callers (the Supervisor, and the CLI tools in services/vision/)
import from `vision` rather than reaching into its submodules directly.
"""

from .detector import VehicleDetector
from .video_source import BaseVideoSource, create_video_source
from .roi_manager import ROIManager
from .roi_config import (
    RoiConfig,
    load_roi_config,
    parse_roi_config,
    save_roi_config,
    validate_against_topology,
)
from .metrics_extractor import MetricsExtractor
from .engine import PerceptionEngine, build_engine_from_settings
from .roi_visibility import RoiVisibility
from .camera_tamper import CameraAlert, CameraTamperDetector

__all__ = [
    "VehicleDetector",
    "BaseVideoSource",
    "create_video_source",
    "ROIManager",
    "RoiConfig",
    "load_roi_config",
    "parse_roi_config",
    "save_roi_config",
    "validate_against_topology",
    "MetricsExtractor",
    "PerceptionEngine",
    "build_engine_from_settings",
    "RoiVisibility",
    "CameraAlert",
    "CameraTamperDetector",
]
