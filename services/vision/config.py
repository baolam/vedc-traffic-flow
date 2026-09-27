import os
from pydantic import Field
from pydantic_settings import BaseSettings

class Settings(BaseSettings):
    edgeflow_env: str = Field(default_factory=lambda: os.getenv("EDGEFLOW_ENV", "dev"))
    log_level: str = Field(default_factory=lambda: os.getenv("LOG_LEVEL", "INFO"))
    mqtt_host: str = Field(default_factory=lambda: os.getenv("MQTT_HOST", "mqtt"))
    mqtt_port: int = Field(default_factory=lambda: int(os.getenv("MQTT_PORT", "1883")))
    edgeflow_topology: str = Field(default_factory=lambda: os.getenv("EDGEFLOW_TOPOLOGY", "four_intersection_v1"))
    
    # Vision Perception Specific Configs
    video_source: str = Field(default_factory=lambda: os.getenv("VIDEO_SOURCE", "synthetic"))
    vision_fps: float = Field(default_factory=lambda: float(os.getenv("VISION_FPS", "5.0")))
    telemetry_period_s: float = Field(default_factory=lambda: float(os.getenv("TELEMETRY_PERIOD_S", "1.0")))
    confidence_threshold: float = Field(default_factory=lambda: float(os.getenv("CONFIDENCE_THRESHOLD", "0.5")))
    detection_model_path: str = Field(default_factory=lambda: os.getenv("DETECTION_MODEL_PATH", ""))
    vision_node_id: str = "J1"
    detector_input_size: int = 640
    detector_output_format: str = "yolov8"
    detector_num_classes: int = 80
    detector_vehicle_classes: str = "2,3,5,7"
    motion_scale: float = 1.0

settings = Settings()
