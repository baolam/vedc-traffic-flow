"""
EdgeFlow AI - Vision Perception Service Configuration.
Controls video ingestion, YOLO model weights, target node ID, and Raspberry Pi hardware telemetry.
"""

import os
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

    # Video Source (0 for /dev/video0, 'picamera', 'synthetic', or video path)
    video_source: str = Field(default_factory=lambda: os.getenv("VIDEO_SOURCE", "synthetic"))
    vision_fps: float = Field(default_factory=lambda: float(os.getenv("VISION_FPS", "10.0")))
    telemetry_period_s: float = Field(default_factory=lambda: float(os.getenv("TELEMETRY_PERIOD_S", "1.0")))

    # AI Detection Model Configs (YOLOv8 / YOLOv5 / ONNX / OpenCV DNN)
    detection_model_path: str = Field(default_factory=lambda: os.getenv("DETECTION_MODEL_PATH", ""))
    confidence_threshold: float = Field(default_factory=lambda: float(os.getenv("CONFIDENCE_THRESHOLD", "0.4")))
    detector_input_size: int = Field(default_factory=lambda: int(os.getenv("DETECTOR_INPUT_SIZE", "640")))
    detector_output_format: str = Field(default_factory=lambda: os.getenv("DETECTOR_OUTPUT_FORMAT", "yolov8"))
    detector_num_classes: int = Field(default_factory=lambda: int(os.getenv("DETECTOR_NUM_CLASSES", "80")))
    detector_vehicle_classes: str = Field(default_factory=lambda: os.getenv("DETECTOR_VEHICLE_CLASSES", "2,3,5,7"))
    motion_scale: float = Field(default_factory=lambda: float(os.getenv("MOTION_SCALE", "1.0")))

    # Raspberry Pi 5 & Edge Hardware Telemetry Reporting
    enable_hardware_telemetry: bool = Field(default_factory=lambda: os.getenv("ENABLE_HARDWARE_TELEMETRY", "true").lower() == "true")


settings = Settings()
