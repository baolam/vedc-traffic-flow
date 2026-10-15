"""
EdgeFlow AI - Vision Perception Service Configuration.
Controls video ingestion, YOLO model weights, target node ID, and Raspberry Pi hardware telemetry.
"""

import os
from pathlib import Path
from typing import Optional

from pydantic import Field
from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    """
    Configuration settings for the Vision Perception & Raspberry Pi Edge Service.
    """
    # Environment & Networking
    edgeflow_env: str = Field(default_factory=lambda: os.getenv("EDGEFLOW_ENV", "dev"))
    log_level: str = Field(default_factory=lambda: os.getenv("LOG_LEVEL", "INFO"))
    mqtt_host: str = Field(default_factory=lambda: os.getenv("MQTT_HOST", "localhost"))
    mqtt_port: int = Field(default_factory=lambda: int(os.getenv("MQTT_PORT", "1883")))
    edgeflow_topology: str = Field(default_factory=lambda: os.getenv("EDGEFLOW_TOPOLOGY", "four_intersection_v1"))

    # Target Intersection Node ID on the Graph
    vision_node_id: str = Field(default_factory=lambda: os.getenv("VISION_NODE_ID", "J1"))
    # Several nodes seen by the same camera (e.g. "J1,J2"); overrides VISION_NODE_ID when set.
    # Requires ROI_CONFIG_PATH: a calibrated polygon file (services/vision/roi_calibrate.py).
    vision_node_ids: str = Field(default_factory=lambda: os.getenv("VISION_NODE_IDS", ""))
    roi_config_path: str = Field(default_factory=lambda: os.getenv("ROI_CONFIG_PATH", ""))

    # Video Source (0 for /dev/video0, 'picamera', 'synthetic', or video path)
    video_source: str = Field(default_factory=lambda: os.getenv("VIDEO_SOURCE", "synthetic"))
    vision_fps: float = Field(default_factory=lambda: float(os.getenv("VISION_FPS", "10.0")))
    telemetry_period_s: float = Field(default_factory=lambda: float(os.getenv("TELEMETRY_PERIOD_S", "1.0")))

    # Picamera2 (Camera Module 3) controls: fixed focus in dioptres (empty = autofocus)
    # and anti-flicker period in microseconds (10000 = 50 Hz mains, 0 = off)
    camera_lens_position: Optional[float] = Field(
        default_factory=lambda: float(os.environ["CAMERA_LENS_POSITION"]) if os.getenv("CAMERA_LENS_POSITION") else None)
    camera_flicker_period_us: int = Field(default_factory=lambda: int(os.getenv("CAMERA_FLICKER_PERIOD_US", "10000")))

    # AI Detection Model Configs (YOLOv8 / YOLOv5 / ONNX / OpenCV DNN)
    detection_model_path: str = Field(
        default_factory=lambda: os.getenv(
            "DETECTION_MODEL_PATH",
            str(Path(__file__).resolve().parent / "models" / "yolov8n.onnx")
            if (Path(__file__).resolve().parent / "models" / "yolov8n.onnx").is_file()
            else (str(Path(__file__).resolve().parents[2] / "models" / "yolov8n.onnx")
                  if (Path(__file__).resolve().parents[2] / "models" / "yolov8n.onnx").is_file() else "")
        )
    )
    confidence_threshold: float = Field(default_factory=lambda: float(os.getenv("CONFIDENCE_THRESHOLD", "0.4")))
    detector_input_size: int = Field(default_factory=lambda: int(os.getenv("DETECTOR_INPUT_SIZE", "640")))
    detector_output_format: str = Field(default_factory=lambda: os.getenv("DETECTOR_OUTPUT_FORMAT", "yolov8"))
    detector_num_classes: int = Field(default_factory=lambda: int(os.getenv("DETECTOR_NUM_CLASSES", "80")))
    detector_vehicle_classes: str = Field(default_factory=lambda: os.getenv("DETECTOR_VEHICLE_CLASSES", "2,3,5,7"))
    motion_scale: float = Field(default_factory=lambda: float(os.getenv("MOTION_SCALE", "1.0")))

    # Raspberry Pi 5 & Edge Hardware Telemetry Reporting
    enable_hardware_telemetry: bool = Field(default_factory=lambda: os.getenv("ENABLE_HARDWARE_TELEMETRY", "true").lower() == "true")


settings = Settings()
