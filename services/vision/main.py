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
from pathlib import Path
from typing import Dict, Any, List

# Ensure services/vision directory is in sys.path for IDE & module resolution
CURR_DIR = Path(__file__).resolve().parent
if str(CURR_DIR) not in sys.path:
    sys.path.insert(0, str(CURR_DIR))

try:
    from config import settings
    from perception_engine import PerceptionEngine
    from hardware_monitor import get_hardware_diagnostics, is_raspberry_pi
    from vision_contracts_helper import load_topology, validate_payload
except ImportError:
    from services.vision.config import settings
    from services.vision.perception_engine import PerceptionEngine
    from services.vision.hardware_monitor import get_hardware_diagnostics, is_raspberry_pi
    from services.vision.vision_contracts_helper import load_topology, validate_payload

logging.basicConfig(
    level=getattr(logging, settings.log_level.upper(), logging.INFO),
    format="%(asctime)s [%(levelname)s] [Vision-Pi] %(message)s"
)
logger = logging.getLogger("vision-service")


def main():
    """
    Main loop for EdgeFlow AI Vision Perception Service on Raspberry Pi / Edge Device.
    """
    logger.info("=========================================================")
    logger.info("  EdgeFlow AI - Raspberry Pi 5 Edge Perception Engine   ")
    logger.info("=========================================================")
    
    # 1. Hardware Diagnostics & Device Inspection
    hw_diag = get_hardware_diagnostics()
    logger.info(f"Target Node ID     : {settings.vision_node_id}")
    logger.info(f"Host Platform      : {hw_diag['system_platform']} ({hw_diag['device_model']})")
    logger.info(f"Raspberry Pi Mode  : {'YES (Hardware Native)' if hw_diag['is_raspberry_pi'] else 'NO (Desktop / Virtual / CI)'}")
    logger.info(f"CPU Temperature    : {hw_diag['cpu_temp_c']} °C")
    logger.info(f"Video Source       : {settings.video_source}")
    logger.info(f"Telemetry Period   : {settings.telemetry_period_s}s")
    logger.info(f"Detection Model    : {settings.detection_model_path or 'OpenCV MOG2 (Motion Baseline)'}")
    logger.info("=========================================================")

    # 2. Topology & Target Node Setup
    topology_id = settings.edgeflow_topology
    topology = load_topology(topology_id)
    nodes = topology.get("nodes", [])
    target_nodes = [n for n in nodes if n["node_id"] == settings.vision_node_id]
    if not target_nodes:
        # Fallback to first available node in topology
        if nodes:
            logger.warning(f"Node '{settings.vision_node_id}' not in topology. Defaulting to first node '{nodes[0]['node_id']}'.")
            target_nodes = [nodes[0]]
        else:
            raise ValueError(f"Topology '{topology_id}' has no nodes defined.")

    active_node = target_nodes[0]
    active_node_id = active_node.get("node_id", "J1")

    # 3. Initialize Vision Perception Engine
    engine = PerceptionEngine(
        video_source_str=settings.video_source,
        model_path=settings.detection_model_path or None,
        input_size=settings.detector_input_size,
        output_format=settings.detector_output_format,
        motion_scale=settings.motion_scale,
        conf_threshold=settings.confidence_threshold,
        num_classes=settings.detector_num_classes,
        vehicle_classes=tuple(int(c) for c in settings.detector_vehicle_classes.split(","))
    )
    engine.setup_topology(topology, node_id=active_node_id)
    logger.info(f"Perception Engine initialized using backend: [{engine.detector.backend}]")

    # 4. MQTT Broker Client Setup
    mqtt_host = settings.mqtt_host
    mqtt_port = settings.mqtt_port
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
                health_topic = "edgeflow/v1/health/vision"
                health_payload = {
                    "service": "vision",
                    "status": "HEALTHY",
                    "device": "raspberry_pi_5" if is_raspberry_pi() else "generic_edge",
                    "cpu_temp_c": hw_diag["cpu_temp_c"],
                    "backend": engine.detector.backend,
                    "active_node": active_node_id,
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
    period_s = settings.telemetry_period_s
    last_health_report = time.time()

    # 5. Continuous Vision Perception & Telemetry Loop
    try:
        logger.info("🚀 Starting Continuous Edge Vision Ingestion Loop...")
        while True:
            start_tick = time.time()
            sim_time_s += period_s
            timestamp_ms = int(time.time() * 1000)

            # Process frame and extract vehicle queue metrics
            approaches = engine.process_frame(node_id=active_node_id)
            if not approaches:
                # Camera disconnection / failure fallback: report 0.0 confidence (never fabricate fake high-confidence queues)
                node_approaches = active_node.get("approaches", [f"{active_node_id}_N_IN", f"{active_node_id}_S_IN", f"{active_node_id}_E_IN", f"{active_node_id}_W_IN"])
                approaches = [
                    {
                        "approach_id": app_id,
                        "queue_vehicles": 0.0,
                        "flow_veh_per_s": 0.0,
                        "mean_speed_mps": 0.0,
                        "occupancy_ratio": 0.0,
                        "confidence": 0.0
                    }
                    for app_id in node_approaches
                ]

            phases = active_node.get("phases", [])
            default_phase = phases[0]["phase_id"] if phases else f"{active_node_id}_PHASE_NS"

            # Construct canonical Telemetry message
            telemetry_payload = {
                "node_id": active_node_id,
                "source_type": "vision",
                "simulation_time_s": round(sim_time_s, 2),
                "timestamp_ms": timestamp_ms,
                "current_phase_id": default_phase,
                "approaches": approaches
            }

            # Validate against canonical contracts schema
            validate_payload(telemetry_payload, "telemetry")

            # Publish to MQTT Topic
            telemetry_topic = f"edgeflow/v1/telemetry/{active_node_id}"
            if mqtt_client and mqtt_client.is_connected():
                mqtt_client.publish(telemetry_topic, json.dumps(telemetry_payload))
                logger.debug(f"Published Vision Telemetry to {telemetry_topic} ({len(approaches)} approaches)")
            else:
                total_q = sum(a.get("queue_vehicles", 0) for a in approaches)
                logger.info(f"Extracted Telemetry [{active_node_id}]: Total Queue = {total_q:.1f} veh | Confidence = {approaches[0]['confidence'] if approaches else 0}")

            # Periodic hardware health report (every 10s)
            if settings.enable_hardware_telemetry and (time.time() - last_health_report >= 10.0):
                last_health_report = time.time()
                current_temp = get_hardware_diagnostics()["cpu_temp_c"]
                if mqtt_client and mqtt_client.is_connected():
                    mqtt_client.publish("edgeflow/v1/health/vision", json.dumps({
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
