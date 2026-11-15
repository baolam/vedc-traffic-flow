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
    # Pixels per metre at the stop lines: converts measured box motion to mean_speed_mps
    # (motion_estimator.py). ~1000 for the 1280 px sa ban video over ~1.2 m of tarp; recalibrate per camera.
    vision_px_per_m: float = Field(default_factory=lambda: float(os.getenv("VISION_PX_PER_M", "1000")))
    # Share of Canny edge pixels below which a ROI counts as covered/blind for a frame (roi_visibility.py);
    # its approach then reports confidence 0 instead of "0 vehicles". 0 = off.
    vision_blind_edge_ratio: float = Field(default_factory=lambda: float(os.getenv("VISION_BLIND_EDGE_RATIO", "0.01")))

    # Raspberry Pi 5 & Edge Hardware Telemetry Reporting
    enable_hardware_telemetry: bool = Field(default_factory=lambda: os.getenv("ENABLE_HARDWARE_TELEMETRY", "true").lower() == "true")

    # Optional Live Video Stream: pushes annotated camera frames (one JPEG per frame) to the
    # platform API over HTTP (services/vision/video_sync.py), alongside the normal MQTT
    # telemetry, so the dashboard can show a real live view (MJPEG) of this node. Off by default
    # -- enabling it is a deliberate choice for a demo/showcase node (e.g. the Raspberry Pi
    # vision demo, VISION_NODE_ID=J3), not something every deployment needs.
    video_sync_enabled: bool = Field(default_factory=lambda: os.getenv("VIDEO_SYNC_ENABLED", "false").lower() == "true")
    video_sync_api_url: str = Field(default_factory=lambda: os.getenv("VIDEO_SYNC_API_URL", "http://localhost:8000"))
    # Frames pushed to the API per second (capped independently of VISION_FPS/camera rate); higher
    # costs more LAN bandwidth and Pi CPU for JPEG encoding, with little visible smoothness gain.
    video_sync_fps: float = Field(default_factory=lambda: float(os.getenv("VIDEO_SYNC_FPS", "8.0")))
    video_sync_jpeg_quality: int = Field(default_factory=lambda: int(os.getenv("VIDEO_SYNC_JPEG_QUALITY", "70")))

    # MQTT client identity, keepalive and QoS (previously hardcoded in main.py; now explicit and
    # overridable). Defaults match what the service always did, so leaving these unset changes
    # nothing.
    mqtt_client_id: Optional[str] = Field(default_factory=lambda: os.getenv("MQTT_CLIENT_ID") or None)
    mqtt_keepalive_s: int = Field(default_factory=lambda: int(os.getenv("MQTT_KEEPALIVE_S", "60")))
    mqtt_qos_telemetry: int = Field(default_factory=lambda: int(os.getenv("MQTT_QOS_TELEMETRY", "0")))
    mqtt_qos_health: int = Field(default_factory=lambda: int(os.getenv("MQTT_QOS_HEALTH", "1")))

    # Optional Frame Archive (services/vision/storage/frame_archive.py): periodically saves
    # annotated frames/clips to local disk for later review. Off by default, same opt-in style
    # as VIDEO_SYNC_*; unlike video_sync it never leaves the device (no HTTP/MQTT), and it is
    # NOT a telemetry history log or an MQTT-outage durability buffer.
    frame_archive_enabled: bool = Field(
        default_factory=lambda: os.getenv("FRAME_ARCHIVE_ENABLED", "false").lower() == "true")
    frame_archive_dir: str = Field(
        default_factory=lambda: os.getenv(
            "FRAME_ARCHIVE_DIR", str(Path(__file__).resolve().parent / "frame_archive")))
    frame_archive_mode: str = Field(default_factory=lambda: os.getenv("FRAME_ARCHIVE_MODE", "snapshot"))  # "snapshot" | "clip"
    frame_archive_interval_s: float = Field(default_factory=lambda: float(os.getenv("FRAME_ARCHIVE_INTERVAL_S", "30.0")))
    frame_archive_clip_duration_s: float = Field(default_factory=lambda: float(os.getenv("FRAME_ARCHIVE_CLIP_DURATION_S", "10.0")))
    frame_archive_retention_hours: float = Field(default_factory=lambda: float(os.getenv("FRAME_ARCHIVE_RETENTION_HOURS", "24.0")))
    frame_archive_jpeg_quality: int = Field(default_factory=lambda: int(os.getenv("FRAME_ARCHIVE_JPEG_QUALITY", "80")))


settings = Settings()
