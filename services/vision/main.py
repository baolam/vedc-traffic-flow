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
import signal
import logging
import argparse
import platform
import threading
from pathlib import Path
from typing import Dict, Any, List, Optional

import cv2

# Ensure services/vision directory is in sys.path for IDE & module resolution
CURR_DIR = Path(__file__).resolve().parent
if str(CURR_DIR) not in sys.path:
    sys.path.insert(0, str(CURR_DIR))

try:
    from config import settings
    from perception_engine import PerceptionEngine
    from hardware_monitor import get_hardware_diagnostics, get_runtime_hardware, is_raspberry_pi, read_board_model
    from vision_contracts_helper import load_topology, validate_payload, topics
    from roi_config import load_roi_config, validate_against_topology
    from runtime_stats import RuntimeStats
    from telemetry_window import TelemetryWindow
    from phase_tracker import PhaseTracker, SOURCE_DEVICE
except ImportError:
    from services.vision.config import settings
    from services.vision.perception_engine import PerceptionEngine
    from services.vision.hardware_monitor import (get_hardware_diagnostics, get_runtime_hardware,
                                                  is_raspberry_pi, read_board_model)
    from services.vision.vision_contracts_helper import load_topology, validate_payload, topics
    from services.vision.roi_config import load_roi_config, validate_against_topology
    from services.vision.runtime_stats import RuntimeStats
    from services.vision.telemetry_window import TelemetryWindow
    from services.vision.phase_tracker import PhaseTracker, SOURCE_DEVICE

logging.basicConfig(
    level=getattr(logging, settings.log_level.upper(), logging.INFO),
    format="%(asctime)s [%(levelname)s] [Vision-Pi] %(message)s"
)
logger = logging.getLogger("vision-service")

HEALTH_TOPIC = topics.get_health_topic("vision")
HEALTH_PERIOD_S = 10.0
STATS_WINDOW_S = 30.0
OFFLINE_PAYLOAD = json.dumps({"service": "vision", "status": "OFFLINE"})


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


def set_offline_will(client) -> None:
    """The broker publishes this retained OFFLINE when the service dies or drops off the network,
    so a stale retained HEALTHY never outlives the process."""
    client.will_set(HEALTH_TOPIC, OFFLINE_PAYLOAD, qos=1, retain=True)


def health_status(snapshot: Dict[str, Any]) -> str:
    """DEGRADED as soon as the camera misses a frame; STARTING until the first frame is processed."""
    if snapshot["consecutive_failures"] > 0:
        return "DEGRADED"
    return "HEALTHY" if snapshot["frames_ok"] > 0 else "STARTING"


def build_health(identity: Dict[str, Any], snapshot: Dict[str, Any],
                 hardware: Dict[str, Any], timestamp_ms: int,
                 phase_sources: Optional[Dict[str, str]] = None) -> Dict[str, Any]:
    """Retained health message carrying measured runtime figures only."""
    payload = {**identity, "status": health_status(snapshot), "timestamp_ms": timestamp_ms,
               "runtime": snapshot, "hardware": hardware}
    if phase_sources is not None:
        payload["phase_source"] = phase_sources  # per node: esp32_health, or default (not observed)
    if payload["status"] == "DEGRADED":
        payload["reason"] = f"camera: {snapshot['consecutive_failures']} consecutive frames without image"
    return payload


def format_runtime(snapshot: Dict[str, Any], hardware: Dict[str, Any]) -> str:
    """One journal line per health period, readable without an MQTT client."""
    latency = snapshot["latency_ms"]
    parts = [f"processed {snapshot['processed_fps']} fps ({snapshot['frames_ok']} ok / "
             f"{snapshot['frames_failed']} failed in {snapshot['window_s']}s)"]
    for key in ("capture_ms", "inference_ms", "total_ms", "age_at_publish_ms"):
        if key in latency:
            parts.append(f"{key[:-3]} p50/p95 {latency[key]['p50']}/{latency[key]['p95']} ms")
    if hardware:
        parts.append(f"temp {hardware.get('cpu_temp_c')} C, throttled {hardware.get('throttled_flags')}, "
                     f"5V {hardware.get('ext5v_v')}")
    return " | ".join(parts)


def _stop_on_sigterm(_signum, _frame):
    raise KeyboardInterrupt  # `systemctl stop` gets the same clean shutdown as Ctrl+C


def build_telemetry(node: Dict[str, Any], approaches: List[Dict[str, Any]],
                    sim_time_s: float, timestamp_ms: int,
                    current_phase_id: Optional[str] = None) -> Dict[str, Any]:
    """Canonical telemetry for one node; a missing frame yields zero-confidence approaches.
    current_phase_id is the phase the device reported (PhaseTracker); without one, the first phase."""
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
        "current_phase_id": current_phase_id or (phases[0]["phase_id"] if phases else f"{node_id}_PHASE_NS"),
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
    logger.info(f"Telemetry Period   : {cfg.telemetry_period_s}s (median over the frames of each period)")
    logger.info(f"Processing cap     : {cfg.vision_fps} fps (VISION_FPS, 0 = as fast as possible)")
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

    period_s = cfg.telemetry_period_s
    stats = RuntimeStats(window_s=STATS_WINDOW_S)
    identity = {
        "service": "vision",
        "device": "raspberry_pi_5" if is_raspberry_pi() else "generic_edge",
        "board_model": read_board_model(),
        "backend": engine.detector.backend,
        "model_sha256": engine.detector.model_sha256,
        "detector_input_size": cfg.detector_input_size,
        "video_source": cfg.video_source,
        "active_nodes": node_ids,
        "roi_sha256": roi_config.sha256 if roi_config else None,
        "telemetry_period_s": period_s,
        "vision_fps_cap": cfg.vision_fps,
        "opencv": cv2.__version__,
        "python": platform.python_version(),
    }
    # Set from the MQTT thread on every (re)connect; the main loop publishes, so stats stay single-threaded.
    health_request = threading.Event()
    # Phase each ESP32 shows, from edgeflow/v1/health/{node} (O7): fed by the MQTT thread
    phase_tracker = PhaseTracker(active_nodes)
    phase_sources: Dict[str, str] = {}  # last source logged per node

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
                for topic in phase_tracker.topics:
                    client.subscribe(topic)
                health_request.set()  # replaces a retained OFFLINE left by the will after a drop
            else:
                logger.warning(f"MQTT connection failed with return code {rc}")

        def on_message(client, userdata, msg):
            phase_tracker.update(msg.topic, msg.payload)

        mqtt_client.on_connect = on_connect
        mqtt_client.on_message = on_message
        set_offline_will(mqtt_client)
        logger.info(f"Connecting to MQTT broker at {mqtt_host}:{mqtt_port}...")
        mqtt_client.connect_async(mqtt_host, mqtt_port, 60)
        mqtt_client.loop_start()
    except Exception as e:
        logger.warning(f"MQTT client connection skipped ({e}). Operating in standalone edge perception mode.")

    sim_time_s = 0.0
    last_health_report = time.time()
    window = TelemetryWindow()
    frame_interval_s = 1.0 / cfg.vision_fps if cfg.vision_fps > 0 else 0.0
    next_publish = time.monotonic() + period_s
    signal.signal(signal.SIGTERM, _stop_on_sigterm)

    # 5. Continuous Vision Perception & Telemetry Loop
    try:
        logger.info("🚀 Starting Continuous Edge Vision Ingestion Loop...")
        while True:
            frame_started = time.monotonic()

            # One frame, one detection pass for every node this camera covers
            per_node = engine.process_frame_nodes()
            frame_info = engine.last_frame
            if frame_info:
                window.add(per_node, frame_info["captured_at_ms"])
                stats.record(True, {k: v for k, v in frame_info.items() if k != "captured_at_ms"})
            else:
                window.add_failure()
                stats.record(False)
                if stats.consecutive_failures == 1 or stats.consecutive_failures % 10 == 0:
                    logger.warning(f"No camera frame ({stats.consecutive_failures} in a row): "
                                   "the period's telemetry loses confidence, zero if no frame at all")

            # One telemetry message per node and period: medians over the period's frames (O14/O10)
            if time.monotonic() >= next_publish:
                sim_time_s += period_s
                publish_started = time.perf_counter()
                # Observation time is the capture time of the newest frame in the period
                timestamp_ms = window.last_capture_ms or int(time.time() * 1000)
                for node in active_nodes:
                    node_id = node["node_id"]
                    phase_id, source = phase_tracker.current(node_id)
                    if phase_sources.get(node_id) != source:
                        if source == SOURCE_DEVICE:
                            logger.info(f"[{node_id}] current_phase_id now follows the ESP32 health topic")
                        else:
                            logger.warning(f"[{node_id}] no fresh ESP32 health: telemetry reports the default "
                                           f"phase {phase_id}, so the EdgeFlow controller's green timing is a guess")
                        phase_sources[node_id] = source
                    telemetry_payload = build_telemetry(node, window.aggregate(node_id), sim_time_s, timestamp_ms,
                                                        current_phase_id=phase_id)
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
                publish_timings = {"publish_ms": (time.perf_counter() - publish_started) * 1000,
                                   "frames_per_publish": window.frames}
                if window.last_capture_ms is not None:
                    publish_timings["age_at_publish_ms"] = time.time() * 1000 - window.last_capture_ms
                stats.record_publish(publish_timings)
                window.reset()
                next_publish = max(next_publish + period_s, time.monotonic())

            # Health with measured runtime figures: on every (re)connect and every HEALTH_PERIOD_S
            if health_request.is_set() or time.time() - last_health_report >= HEALTH_PERIOD_S:
                health_request.clear()
                last_health_report = time.time()
                hardware = get_runtime_hardware() if cfg.enable_hardware_telemetry else {}
                snapshot = stats.snapshot()
                logger.info(f"Runtime: {format_runtime(snapshot, hardware)}")
                if mqtt_client and mqtt_client.is_connected():
                    sources = {node_id: phase_tracker.current(node_id)[1] for node_id in node_ids}
                    health = build_health(identity, snapshot, hardware, int(time.time() * 1000), sources)
                    mqtt_client.publish(HEALTH_TOPIC, json.dumps(health), qos=1, retain=True)

            # Cap processing at VISION_FPS without sleeping past the next publish; back off on camera errors
            wait = min(frame_interval_s - (time.monotonic() - frame_started), next_publish - time.monotonic())
            time.sleep(max(wait, 0.0 if frame_info else 0.05))

    except KeyboardInterrupt:
        logger.info("Stopping Raspberry Pi Vision Perception Service...")
    finally:
        engine.close()
        if mqtt_client:
            if mqtt_client.is_connected():
                # A clean DISCONNECT suppresses the will, so announce OFFLINE explicitly
                info = mqtt_client.publish(HEALTH_TOPIC, OFFLINE_PAYLOAD, qos=1, retain=True)
                try:
                    info.wait_for_publish(timeout=2.0)
                except TypeError:
                    pass  # paho-mqtt < 2.0 has no timeout argument; do not risk blocking shutdown
                except (RuntimeError, ValueError) as e:
                    logger.warning(f"OFFLINE health not confirmed: {e}")
            mqtt_client.disconnect()
            mqtt_client.loop_stop()
        logger.info("Perception Engine stopped safely.")


if __name__ == "__main__":
    main()
