"""
EdgeFlow AI - Vision Supervisor (composition root).
------------------------------------------------------
Owns the lifecycle of every vision sub-component -- the YOLO/vision pipeline (vision/), the
open connection to the broader system (connectivity/), the optional local video stream
(streaming/) and the optional local frame archive (storage/) -- and drives the single tick loop
that ties them together every period. main.py is just the thin CLI entrypoint that builds a
Settings object and hands it to VisionSupervisor.
"""

import logging
import platform
import signal
import time
from pathlib import Path
from typing import Any, Dict, List, Optional

import cv2

try:
    from vision import build_engine_from_settings
    from vision.roi_config import load_roi_config, validate_against_topology
    from connectivity.hardware_monitor import (get_hardware_diagnostics, get_runtime_hardware,
                                               is_raspberry_pi, read_board_model)
    from connectivity.phase_tracker import PhaseTracker, SOURCE_DEVICE
    from connectivity.mqtt_gateway import MqttGateway
    from streaming.live_stream import LiveStreamPusher, draw_sync_overlay
    from storage.frame_archive import FrameArchive
    from vision_contracts_helper import load_topology, topics
    from runtime_stats import RuntimeStats
    from telemetry_window import TelemetryWindow
except ImportError:
    from services.vision.vision import build_engine_from_settings
    from services.vision.vision.roi_config import load_roi_config, validate_against_topology
    from services.vision.connectivity.hardware_monitor import (get_hardware_diagnostics, get_runtime_hardware,
                                                                is_raspberry_pi, read_board_model)
    from services.vision.connectivity.phase_tracker import PhaseTracker, SOURCE_DEVICE
    from services.vision.connectivity.mqtt_gateway import MqttGateway
    from services.vision.streaming.live_stream import LiveStreamPusher, draw_sync_overlay
    from services.vision.storage.frame_archive import FrameArchive
    from services.vision.vision_contracts_helper import load_topology, topics
    from services.vision.runtime_stats import RuntimeStats
    from services.vision.telemetry_window import TelemetryWindow

logger = logging.getLogger("vision-service")

HEALTH_PERIOD_S = 10.0
STATS_WINDOW_S = 30.0


def resolve_node_ids(cfg) -> List[str]:
    """Nodes this camera reports on: VISION_NODE_IDS if set, else the single VISION_NODE_ID."""
    if cfg.vision_node_ids.strip():
        return [n.strip() for n in cfg.vision_node_ids.split(",") if n.strip()]
    return [cfg.vision_node_id]


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


class VisionSupervisor:
    """Composition root: constructs and owns every sub-component, and drives the tick loop."""

    def __init__(self, cfg):
        self.cfg = cfg

        # 1. Hardware Diagnostics & Device Inspection
        hw_diag = get_hardware_diagnostics()
        node_ids = resolve_node_ids(cfg)
        logger.info("=========================================================")
        logger.info("  EdgeFlow AI - Raspberry Pi 5 Edge Perception Engine   ")
        logger.info("=========================================================")
        logger.info(f"Target Node IDs    : {', '.join(node_ids)}")
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
        unknown = [n for n in node_ids if n not in topo_nodes]
        if unknown:
            raise ValueError(f"Nodes {unknown} are not in topology '{topology_id}'")
        self.active_nodes = [topo_nodes[n] for n in node_ids]
        self.node_ids = node_ids

        self.roi_config = None
        if cfg.roi_config_path:
            self.roi_config = load_roi_config(cfg.roi_config_path)
            validate_against_topology(self.roi_config, topology, node_ids)
            logger.info(f"ROI calibration  : {cfg.roi_config_path} (sha256 {self.roi_config.sha256[:12]}, "
                        f"{self.roi_config.frame_size[0]}x{self.roi_config.frame_size[1]})")
        elif len(node_ids) > 1:
            raise ValueError("Several nodes on one camera need ROI_CONFIG_PATH (see services/vision/roi_calibrate.py)")
        frame_size = self.roi_config.frame_size if self.roi_config else (640, 480)

        # 3. Initialize Vision Perception Engine (vision/)
        self.engine = build_engine_from_settings(
            cfg, node_ids, roi_nodes=self.roi_config.nodes if self.roi_config else None,
            frame_size=frame_size)
        logger.info(f"Perception Engine initialized using backend: [{self.engine.detector.backend}]")

        # Optional Live Video Stream (streaming/): pushes this camera's annotated frames to the
        # platform API over HTTP (one JPEG per frame, rate-capped), alongside (never instead of)
        # the MQTT telemetry below. Opt-in via VIDEO_SYNC_ENABLED.
        self.live_stream = None
        if cfg.video_sync_enabled:
            self.live_stream = LiveStreamPusher(
                api_base_url=cfg.video_sync_api_url,
                node_id=node_ids[0],
                max_fps=cfg.video_sync_fps,
                jpeg_quality=cfg.video_sync_jpeg_quality,
            )
            logger.info(f"Live Video Stream  : ENABLED -> {cfg.video_sync_api_url} "
                        f"(up to {cfg.video_sync_fps} fps, node {node_ids[0]})")

        # Optional Frame Archive (storage/): periodic annotated frame/clip snapshots to local
        # disk for later review. Opt-in via FRAME_ARCHIVE_ENABLED; a no-op when disabled.
        self.frame_archive = FrameArchive(
            enabled=cfg.frame_archive_enabled,
            base_dir=cfg.frame_archive_dir,
            mode=cfg.frame_archive_mode,
            interval_s=cfg.frame_archive_interval_s,
            clip_duration_s=cfg.frame_archive_clip_duration_s,
            retention_hours=cfg.frame_archive_retention_hours,
            jpeg_quality=cfg.frame_archive_jpeg_quality,
        )

        self.stats = RuntimeStats(window_s=STATS_WINDOW_S)
        self.window = TelemetryWindow()
        self.identity = {
            "service": "vision",
            "device": "raspberry_pi_5" if is_raspberry_pi() else "generic_edge",
            "board_model": read_board_model(),
            "backend": self.engine.detector.backend,
            "model_sha256": self.engine.detector.model_sha256,
            "model": Path(cfg.detection_model_path).name if cfg.detection_model_path else None,
            "detector_input_size": cfg.detector_input_size,
            "video_source": cfg.video_source,
            "active_nodes": node_ids,
            "roi_sha256": self.roi_config.sha256 if self.roi_config else None,
            "telemetry_period_s": cfg.telemetry_period_s,
            "vision_fps_cap": cfg.vision_fps,
            "opencv": cv2.__version__,
            "python": platform.python_version(),
        }
        # Phase each ESP32 shows, from edgeflow/v1/health/{node}: fed by the MQTT thread
        self.phase_tracker = PhaseTracker(self.active_nodes)
        self.phase_sources: Dict[str, str] = {}  # last source logged per node

        # 4. Open connection to the broader system (connectivity/)
        self.health_topic = topics.get_health_topic("vision")
        self.mqtt = MqttGateway(cfg, self.phase_tracker, self.health_topic)
        self.mqtt.connect()

    def run(self) -> None:
        """Continuous Vision Perception & Telemetry Loop."""
        cfg = self.cfg
        period_s = cfg.telemetry_period_s
        sim_time_s = 0.0
        last_health_report = time.time()
        frame_interval_s = 1.0 / cfg.vision_fps if cfg.vision_fps > 0 else 0.0
        next_publish = time.monotonic() + period_s
        signal.signal(signal.SIGTERM, _stop_on_sigterm)

        try:
            logger.info("🚀 Starting Continuous Edge Vision Ingestion Loop...")
            while True:
                frame_started = time.monotonic()

                # One frame, one detection pass for every node this camera covers
                per_node = self.engine.process_frame_nodes()
                frame_info = self.engine.last_frame
                if frame_info:
                    self.window.add(per_node, frame_info["captured_at_ms"])
                    self.stats.record(True, {k: v for k, v in frame_info.items() if k != "captured_at_ms"})
                    if (self.live_stream is not None or self.frame_archive.enabled) and self.engine.last_rendered is not None:
                        raw_frame, assigned_boxes, _all_boxes = self.engine.last_rendered
                        annotated = draw_sync_overlay(raw_frame, self.engine.roi_manager.rois, assigned_boxes,
                                                      self.node_ids[0], frame_info["captured_at_ms"])
                        if self.live_stream is not None:
                            self.live_stream.push_frame(annotated)
                        self.frame_archive.maybe_capture(self.node_ids[0], annotated, frame_info["captured_at_ms"])
                else:
                    self.window.add_failure()
                    self.stats.record(False)
                    if self.stats.consecutive_failures == 1 or self.stats.consecutive_failures % 10 == 0:
                        logger.warning(f"No camera frame ({self.stats.consecutive_failures} in a row): "
                                       "the period's telemetry loses confidence, zero if no frame at all")

                # One telemetry message per node and period: medians over the period's frames
                if time.monotonic() >= next_publish:
                    sim_time_s += period_s
                    publish_started = time.perf_counter()
                    # Observation time is the capture time of the newest frame in the period
                    timestamp_ms = self.window.last_capture_ms or int(time.time() * 1000)
                    for node in self.active_nodes:
                        node_id = node["node_id"]
                        phase_id, source = self.phase_tracker.current(node_id)
                        if self.phase_sources.get(node_id) != source:
                            if source == SOURCE_DEVICE:
                                logger.info(f"[{node_id}] current_phase_id now follows the ESP32 health topic")
                            else:
                                logger.warning(f"[{node_id}] no fresh ESP32 health: telemetry reports the default "
                                               f"phase {phase_id}, so the EdgeFlow controller's green timing is a guess")
                            self.phase_sources[node_id] = source
                        telemetry_payload = build_telemetry(node, self.window.aggregate(node_id), sim_time_s,
                                                            timestamp_ms, current_phase_id=phase_id)
                        approaches = telemetry_payload["approaches"]
                        if not self.mqtt.publish_telemetry(node_id, telemetry_payload):
                            total_q = sum(a.get("queue_vehicles", 0) for a in approaches)
                            logger.info(f"Extracted Telemetry [{node_id}]: Total Queue = {total_q:.1f} veh | "
                                        f"Confidence = {approaches[0]['confidence'] if approaches else 0}")
                    publish_timings = {"publish_ms": (time.perf_counter() - publish_started) * 1000,
                                       "frames_per_publish": self.window.frames}
                    if self.window.last_capture_ms is not None:
                        publish_timings["age_at_publish_ms"] = time.time() * 1000 - self.window.last_capture_ms
                    self.stats.record_publish(publish_timings)
                    self.window.reset()
                    next_publish = max(next_publish + period_s, time.monotonic())

                # Health with measured runtime figures: on every (re)connect and every HEALTH_PERIOD_S
                if self.mqtt.health_request.is_set() or time.time() - last_health_report >= HEALTH_PERIOD_S:
                    self.mqtt.health_request.clear()
                    last_health_report = time.time()
                    hardware = get_runtime_hardware() if cfg.enable_hardware_telemetry else {}
                    snapshot = self.stats.snapshot()
                    logger.info(f"Runtime: {format_runtime(snapshot, hardware)}")
                    sources = {node_id: self.phase_tracker.current(node_id)[1] for node_id in self.node_ids}
                    health = build_health(self.identity, snapshot, hardware, int(time.time() * 1000), sources)
                    self.mqtt.publish_health(health)

                # Cap processing at VISION_FPS without sleeping past the next publish; back off on camera errors
                wait = min(frame_interval_s - (time.monotonic() - frame_started), next_publish - time.monotonic())
                time.sleep(max(wait, 0.0 if frame_info else 0.05))

        except KeyboardInterrupt:
            logger.info("Stopping Raspberry Pi Vision Perception Service...")
        finally:
            self.shutdown()

    def shutdown(self) -> None:
        self.engine.close()
        if self.live_stream is not None:
            self.live_stream.close()
        self.frame_archive.close()
        self.mqtt.disconnect()
        logger.info("Perception Engine stopped safely.")
