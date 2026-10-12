"""
EdgeFlow AI - Raspberry Pi 5 & Edge Vision Perception Service.
----------------------------------------------------------------
This service is the official computer vision perception engine running on
Raspberry Pi 5 (with Camera Module 3 or USB Camera). In physical demonstrations,
this service replaces the SUMO simulator by extracting real-world vehicle queues
and traffic flow from tabletop corridors or live intersections and publishing
canonical Telemetry payloads over MQTT.

Architecture:
  Camera / Video Stream -> PerceptionEngine (YOLO / OpenCV DNN) -> ROIManager (Approaches)
  -> MetricsExtractor -> JSON Schema Validation -> MQTT Broker (edgeflow/v1/telemetry/{node_id})
"""

import sys
import os
import json
import time
import logging
import argparse
from pathlib import Path
from typing import Dict, Any, List, Optional

# Ensure services/vision directory is in sys.path for IDE & module resolution
CURR_DIR = Path(__file__).resolve().parent
if str(CURR_DIR) not in sys.path:
    sys.path.insert(0, str(CURR_DIR))

try:
    from config import settings
    from perception_engine import PerceptionEngine
    from hardware_monitor import get_hardware_diagnostics, is_raspberry_pi
    from vision_contracts_helper import load_topology, validate_payload, topics
    from roi_config import load_roi_config, validate_against_topology
except ImportError:
    from services.vision.config import settings
    from services.vision.perception_engine import PerceptionEngine
    from services.vision.hardware_monitor import get_hardware_diagnostics, is_raspberry_pi
    from services.vision.vision_contracts_helper import load_topology, validate_payload, topics
    from services.vision.roi_config import load_roi_config, validate_against_topology

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
    }
    updates = {field: getattr(args, arg) for arg, field in mapping.items() if getattr(args, arg) is not None}
    return base.model_copy(update=updates)


def resolve_node_ids(cfg) -> List[str]:
    """Nodes this camera reports on: VISION_NODE_IDS if set, else the single VISION_NODE_ID."""
    if cfg.vision_node_ids.strip():
        return [n.strip() for n in cfg.vision_node_ids.split(",") if n.strip()]
    return [cfg.vision_node_id]


def build_telemetry(node: Dict[str, Any], approaches: List[Dict[str, Any]],
                    sim_time_s: float, timestamp_ms: int) -> Dict[str, Any]:
    """Canonical telemetry for one node; a missing frame yields zero-confidence approaches."""
    node_id = node["node_id"]
    if not approaches:
        # Camera disconnection / failure: report 0.0 confidence (never fabricate high-confidence queues)
        approaches = [
            {
                "approach_id": app_id,
                "queue_vehicles": 0.0,
                "flow_veh_per_s": 0.0,
                "mean_speed_mps": 0.0,
                "occupancy_ratio": 0.0,
                "confidence": 0.0
            }
            for app_id in node.get("approaches", [f"{node_id}_N_IN", f"{node_id}_S_IN",
                                                   f"{node_id}_E_IN", f"{node_id}_W_IN"])
        ]
    phases = node.get("phases", [])
    return {
        "node_id": node_id,
        "source_type": "vision",
        "simulation_time_s": round(sim_time_s, 2),
        "timestamp_ms": timestamp_ms,
        "current_phase_id": phases[0]["phase_id"] if phases else f"{node_id}_PHASE_NS",
        "approaches": approaches
    }


def main(argv: Optional[List[str]] = None):
    """
    Main loop for EdgeFlow AI Vision Perception Service on Raspberry Pi / Edge Device.
    """
    cfg = apply_cli_overrides(settings, parse_args(argv))
    logger.info("=========================================================")
    logger.info("  EdgeFlow AI - Raspberry Pi 5 Edge Perception Engine   ")
    logger.info("=========================================================")
    
    # 1. Hardware Diagnostics & Device Inspection
    hw_diag = get_hardware_diagnostics()
    logger.info(f"Target Node IDs    : {', '.join(resolve_node_ids(cfg))}")
    logger.info(f"Host Platform      : {hw_diag['system_platform']} ({hw_diag['device_model']})")
    logger.info(f"Raspberry Pi Mode  : {'YES (Hardware Native)' if hw_diag['is_raspberry_pi'] else 'NO (Desktop / Virtual / CI)'}")
    logger.info(f"CPU Temperature    : {hw_diag['cpu_temp_c']} °C")
    logger.info(f"Video Source       : {cfg.video_source}")
    logger.info(f"Telemetry Period   : {cfg.telemetry_period_s}s")
    logger.info(f"Detection Model    : {cfg.detection_model_path or 'OpenCV MOG2 (Motion Baseline)'}")
    logger.info("=========================================================")

    # 2. Topology & Target Node Setup (unknown nodes are an error, never a silent substitute)
    topology_id = cfg.edgeflow_topology
    topology = load_topology(topology_id)
    topo_nodes = {n["node_id"]: n for n in topology.get("nodes", [])}
    node_ids = resolve_node_ids(cfg)
    unknown = [n for n in node_ids if n not in topo_nodes]
    if unknown:
        raise ValueError(f"Nodes {unknown} are not in topology '{topology_id}'")
    active_nodes = [topo_nodes[n] for n in node_ids]

    roi_config = None
    if cfg.roi_config_path:
        roi_config = load_roi_config(cfg.roi_config_path)
        validate_against_topology(roi_config, topology, node_ids)
        logger.info(f"ROI calibration  : {cfg.roi_config_path} (sha256 {roi_config.sha256[:12]}, "
                    f"{roi_config.frame_size[0]}x{roi_config.frame_size[1]})")
    elif len(node_ids) > 1:
        raise ValueError("Several nodes on one camera need ROI_CONFIG_PATH (see services/vision/roi_calibrate.py)")
    frame_w, frame_h = roi_config.frame_size if roi_config else (640, 480)

    # 3. Initialize Vision Perception Engine
    engine = PerceptionEngine(
        video_source_str=cfg.video_source,
        width=frame_w,
        height=frame_h,
        model_path=cfg.detection_model_path or None,
        input_size=cfg.detector_input_size,
        output_format=cfg.detector_output_format,
        motion_scale=cfg.motion_scale,
        conf_threshold=cfg.confidence_threshold,
        num_classes=cfg.detector_num_classes,
        vehicle_classes=tuple(int(c) for c in cfg.detector_vehicle_classes.split(",")),
        lens_position=cfg.camera_lens_position,
        flicker_period_us=cfg.camera_flicker_period_us,
    )
    engine.setup_nodes(node_ids, roi_config.nodes if roi_config else None)
    logger.info(f"Perception Engine initialized using backend: [{engine.detector.backend}]")

    # 4. MQTT Broker Client Setup
    mqtt_host = cfg.mqtt_host
    mqtt_port = cfg.mqtt_port
    mqtt_client = None

    try:
        import paho.mqtt.client as mqtt
        try:
            mqtt_client = mqtt.Client(mqtt.CallbackAPIVersion.VERSION1, client_id="vision-raspberry-pi-service")
        except AttributeError:
            mqtt_client = mqtt.Client(client_id="vision-raspberry-pi-service")

        def on_connect(client, userdata, flags, rc):
            if rc == 0:
                logger.info(f"Connected to MQTT Broker successfully at {mqtt_host}:{mqtt_port}")
                # Publish initial Health Status
                health_topic = topics.get_health_topic("vision")
                health_payload = {
                    "service": "vision",
                    "status": "HEALTHY",
                    "device": "raspberry_pi_5" if is_raspberry_pi() else "generic_edge",
                    "cpu_temp_c": hw_diag["cpu_temp_c"],
                    "backend": engine.detector.backend,
                    "active_nodes": node_ids,
                    "roi_sha256": roi_config.sha256 if roi_config else None,
                    "model_sha256": engine.detector.model_sha256,
                    "timestamp_ms": int(time.time() * 1000)
                }
                client.publish(health_topic, json.dumps(health_payload), retain=True)
            else:
                logger.warning(f"MQTT connection failed with return code {rc}")

        mqtt_client.on_connect = on_connect
        logger.info(f"Connecting to MQTT broker at {mqtt_host}:{mqtt_port}...")
        mqtt_client.connect_async(mqtt_host, mqtt_port, 60)
        mqtt_client.loop_start()
    except Exception as e:
        logger.warning(f"MQTT client connection skipped ({e}). Operating in standalone edge perception mode.")

    sim_time_s = 0.0
    period_s = cfg.telemetry_period_s
    last_health_report = time.time()

    # 5. Continuous Vision Perception & Telemetry Loop
    try:
        logger.info("🚀 Starting Continuous Edge Vision Ingestion Loop...")
        while True:
            start_tick = time.time()
            sim_time_s += period_s
            timestamp_ms = int(time.time() * 1000)

            # One frame, one detection pass, telemetry for every node this camera covers
            per_node = engine.process_frame_nodes()
            for node in active_nodes:
                node_id = node["node_id"]
                telemetry_payload = build_telemetry(node, per_node.get(node_id, []), sim_time_s, timestamp_ms)
                validate_payload(telemetry_payload, "telemetry")
                telemetry_topic = topics.get_telemetry_topic(node_id)
                approaches = telemetry_payload["approaches"]
                if mqtt_client and mqtt_client.is_connected():
                    mqtt_client.publish(telemetry_topic, json.dumps(telemetry_payload))
                    logger.debug(f"Published Vision Telemetry to {telemetry_topic} ({len(approaches)} approaches)")
                else:
                    total_q = sum(a.get("queue_vehicles", 0) for a in approaches)
                    logger.info(f"Extracted Telemetry [{node_id}]: Total Queue = {total_q:.1f} veh | "
                                f"Confidence = {approaches[0]['confidence'] if approaches else 0}")

            # Periodic hardware health report (every 10s)
            if cfg.enable_hardware_telemetry and (time.time() - last_health_report >= 10.0):
                last_health_report = time.time()
                current_temp = get_hardware_diagnostics()["cpu_temp_c"]
                if mqtt_client and mqtt_client.is_connected():
                    mqtt_client.publish(topics.get_health_topic("vision"), json.dumps({
                        "service": "vision",
                        "status": "HEALTHY",
                        "cpu_temp_c": current_temp,
                        "backend": engine.detector.backend,
                        "fps": round(1.0 / max(period_s, 0.001), 1),
                        "timestamp_ms": timestamp_ms
                    }))

            elapsed = time.time() - start_tick
            sleep_dur = max(period_s - elapsed, 0.02)
            time.sleep(sleep_dur)

    except KeyboardInterrupt:
        logger.info("Stopping Raspberry Pi Vision Perception Service...")
    finally:
        engine.close()
        if mqtt_client:
            mqtt_client.loop_stop()
        logger.info("Perception Engine stopped safely.")


if __name__ == "__main__":
    main()
