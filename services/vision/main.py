"""
EdgeFlow AI - Raspberry Pi 5 & Edge Vision Perception Service.
----------------------------------------------------------------
This service is the official computer vision perception engine running on
Raspberry Pi 5 (with Camera Module 3 or USB Camera). In physical demonstrations,
this service replaces the SUMO simulator by extracting real-world vehicle queues
and traffic flow from tabletop corridors or live intersections and publishing
canonical Telemetry payloads over MQTT.

This module is a thin CLI entrypoint: it resolves config from CLI flags/env vars and hands
off to VisionSupervisor (supervisor.py), which owns construction and the tick loop for the
vision pipeline (vision/), the broker connection (connectivity/), the optional local video
stream (streaming/) and the optional local frame archive (storage/).
"""

import sys
import argparse
import logging
from pathlib import Path
from typing import List, Optional

# Ensure services/vision directory is in sys.path for IDE & module resolution
CURR_DIR = Path(__file__).resolve().parent
if str(CURR_DIR) not in sys.path:
    sys.path.insert(0, str(CURR_DIR))

try:
    from config import settings
    from supervisor import VisionSupervisor
except ImportError:
    from services.vision.config import settings
    from services.vision.supervisor import VisionSupervisor

logging.basicConfig(
    level=getattr(logging, settings.log_level.upper(), logging.INFO),
    format="%(asctime)s [%(levelname)s] [Vision-Pi] %(message)s"
)
logger = logging.getLogger("vision-service")


def parse_args(argv: Optional[List[str]] = None) -> argparse.Namespace:
    """CLI flags documented in README/DEVELOPMENT; each one overrides its env variable."""
    parser = argparse.ArgumentParser(description="EdgeFlow AI vision perception service")
    parser.add_argument("--video", help="VIDEO_SOURCE: 0, /dev/video0, picamera, synthetic or a file path")
    parser.add_argument("--mqtt-host", help="MQTT_HOST")
    parser.add_argument("--mqtt-port", type=int, help="MQTT_PORT")
    parser.add_argument("--node-id", help="VISION_NODE_ID")
    parser.add_argument("--node-ids", help="VISION_NODE_IDS: comma-separated nodes seen by this camera, e.g. J1,J2")
    parser.add_argument("--roi-config", help="ROI_CONFIG_PATH: calibrated ROI JSON (needed for several nodes)")
    parser.add_argument("--model", help="DETECTION_MODEL_PATH (.onnx)")
    parser.add_argument("--lens-position", type=float, help="CAMERA_LENS_POSITION in dioptres (Picamera2)")
    parser.add_argument("--topology", help="EDGEFLOW_TOPOLOGY, e.g. rpi_demo_v1")
    parser.add_argument("--video-sync", action="store_true", default=None,
                        help="Enable live video streaming sync to API (VIDEO_SYNC_ENABLED=true)")
    parser.add_argument("--no-video-sync", action="store_false", dest="video_sync",
                        help="Disable live video streaming sync (VIDEO_SYNC_ENABLED=false)")
    parser.add_argument("--video-sync-url", help="API base URL for video sync (VIDEO_SYNC_API_URL)")
    parser.add_argument("--video-sync-fps", type=float, help="Max FPS for video streaming (VIDEO_SYNC_FPS)")
    parser.add_argument("--video-sync-quality", type=int, help="JPEG quality 1-100 (VIDEO_SYNC_JPEG_QUALITY)")
    return parser.parse_args(argv)


def apply_cli_overrides(base, args: argparse.Namespace):
    """Return a settings copy with the CLI values that were actually given."""
    mapping = {
        "video": "video_source",
        "mqtt_host": "mqtt_host",
        "mqtt_port": "mqtt_port",
        "node_id": "vision_node_id",
        "node_ids": "vision_node_ids",
        "roi_config": "roi_config_path",
        "model": "detection_model_path",
        "lens_position": "camera_lens_position",
        "topology": "edgeflow_topology",
        "video_sync": "video_sync_enabled",
        "video_sync_url": "video_sync_api_url",
        "video_sync_fps": "video_sync_fps",
        "video_sync_quality": "video_sync_jpeg_quality",
    }
    updates = {field: getattr(args, arg) for arg, field in mapping.items() if getattr(args, arg) is not None}
    return base.model_copy(update=updates)


def main(argv: Optional[List[str]] = None):
    cfg = apply_cli_overrides(settings, parse_args(argv))
    supervisor = VisionSupervisor(cfg)
    supervisor.run()


if __name__ == "__main__":
    main()
