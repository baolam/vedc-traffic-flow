"""
EdgeFlow AI - Video to Raspberry Pi 5 Vision Perception & Next-Step Control Demo.
================================================================================
Demonstrates the full end-to-end edge pipeline described in the VEDC 2026 report:
  1. Video Stream Ingestion (File .mp4, USB Camera, Picamera2 CSI, or Synthetic)
  2. Edge AI Vehicle Detection via YOLOv8n ONNX (OpenCV DNN)
  3. Spatial ROI Mapping to Traffic Node Approaches (e.g. J1_N_IN, J1_S_IN, etc.)
  4. Telemetry Extraction (queue_vehicles, flow, speed, occupancy, confidence)
  5. Schema-Validated Canonical Telemetry Generation (contracts/schemas/telemetry.json)
  6. Transmission to Next Step (EdgeFlow Traffic Controller / ControlGateway)
  7. Optimal Signal Timing & Phase Command Decision for ESP32 / Actuator
  8. Annotated Video Rendering & Export with Real-Time HUD
"""

import sys
import os
import json
import time
import logging
import argparse
from pathlib import Path
from typing import Dict, Any, List, Optional, Tuple

import cv2
import numpy as np

# Ensure repository root, services/vision, and contracts are in sys.path
CURR_DIR = Path(__file__).resolve().parent
REPO_ROOT = CURR_DIR.parents[1]
CONTRACTS_DIR = REPO_ROOT / "contracts"

for p in (CURR_DIR, REPO_ROOT, CONTRACTS_DIR):
    if str(p) not in sys.path:
        sys.path.insert(0, str(p))

from detector import VehicleDetector
from video_source import create_video_source
from roi_manager import ROIManager
from metrics_extractor import MetricsExtractor
from hardware_monitor import get_hardware_diagnostics, is_raspberry_pi
import contracts_sdk
from contracts_sdk import validate_payload, load_topology
from src.control.controllers import MaxPressureController, EdgeFlowController, FixedTimeController

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] [Vision-Pipeline] %(message)s"
)
logger = logging.getLogger("demo-video-pipeline")


def annotate_frame(
    frame: np.ndarray,
    boxes: List[Tuple[int, int, int, int]],
    scores: List[float],
    roi_manager: ROIManager,
    node_id: str,
    telemetry: Dict[str, Any],
    decision: Optional[Dict[str, Any]],
    fps: float,
    latency_ms: float,
    backend_name: str,
    frame_idx: int,
) -> np.ndarray:
    """Draws bounding boxes, approach ROIs, queue metrics, and HUD onto video frame."""
    canvas = frame.copy()
    h, w = canvas.shape[:2]

    # 1. Draw Approach ROIs (Color-coded)
    colors = {
        f"{node_id}_N_IN": (255, 128, 0),    # Blue/Orange
        f"{node_id}_S_IN": (0, 165, 255),    # Orange
        f"{node_id}_E_IN": (0, 200, 0),      # Green
        f"{node_id}_W_IN": (200, 0, 200),    # Magenta
    }

    for app_id, roi_info in roi_manager.rois.items():
        color = colors.get(app_id, (150, 150, 150))
        pts = roi_info.get("polygon")
        if pts is not None:
            cv2.polylines(canvas, [pts], isClosed=True, color=color, thickness=2)
            # Label ROI with approach name & queue count
            app_metrics = next((a for a in telemetry.get("approaches", []) if a["approach_id"] == app_id), None)
            q_val = app_metrics["queue_vehicles"] if app_metrics else 0.0
            cx = int(np.mean(pts[:, 0]))
            cy = int(np.mean(pts[:, 1]))
            label = f"{app_id}: {int(q_val)}v"
            cv2.putText(canvas, label, (cx - 35, cy), cv2.FONT_HERSHEY_SIMPLEX, 0.45, (255, 255, 255), 1, cv2.LINE_AA)

    # 2. Draw Detected Vehicles
    for i, (x, y, bw, bh) in enumerate(boxes):
        score = scores[i] if i < len(scores) else 0.90
        cv2.rectangle(canvas, (x, y), (x + bw, y + bh), (0, 255, 255), 2)
        score_label = f"Veh {score:.2f}"
        cv2.putText(canvas, score_label, (x, max(y - 5, 12)), cv2.FONT_HERSHEY_SIMPLEX, 0.4, (0, 255, 255), 1, cv2.LINE_AA)

    # 3. Draw Top HUD Banner (Solid background for crisp readability)
    hud_h = 75
    cv2.rectangle(canvas, (0, 0), (w, hud_h), (20, 20, 20), -1)
    cv2.line(canvas, (0, hud_h), (w, hud_h), (0, 200, 255), 2)

    # Line 1: Title and Hardware / Engine
    title_text = f"EdgeFlow AI | RasPi 5 Vision Engine | Node: {node_id} | Backend: {backend_name}"
    cv2.putText(canvas, title_text, (10, 20), cv2.FONT_HERSHEY_SIMPLEX, 0.5, (0, 255, 255), 1, cv2.LINE_AA)

    # Line 2: FPS, Latency, and Detections
    total_q = sum(a.get("queue_vehicles", 0) for a in telemetry.get("approaches", []))
    perf_text = f"Frame: {frame_idx:03d} | FPS: {fps:.1f} | Latency: {latency_ms:.1f}ms | Total Queue: {int(total_q)} veh"
    cv2.putText(canvas, perf_text, (10, 42), cv2.FONT_HERSHEY_SIMPLEX, 0.45, (255, 255, 255), 1, cv2.LINE_AA)

    # Line 3: Next Step Decision Output (Signal Controller / Gateway)
    if decision:
        target_phase = decision.get("target_phase_id", "HOLD")
        duration = decision.get("duration_s", decision.get("max_green_s", 30.0))
        decision_text = f"[NEXT STEP] Controller Selected Phase -> {target_phase} ({duration:.0f}s)"
        cv2.putText(canvas, decision_text, (10, 64), cv2.FONT_HERSHEY_SIMPLEX, 0.45, (50, 255, 50), 1, cv2.LINE_AA)
    else:
        cv2.putText(canvas, "[NEXT STEP] Telemetry Published -> Awaiting Gateway Decision",
                    (10, 64), cv2.FONT_HERSHEY_SIMPLEX, 0.45, (200, 200, 200), 1, cv2.LINE_AA)

    return canvas


def run_pipeline_demo(
    video_source_str: str,
    model_path: Optional[str] = None,
    topology_id: str = "tabletop_j1_j2_v1",
    node_id: str = "J1",
    max_frames: int = 50,
    conf_threshold: float = 0.30,
    output_video_path: Optional[str] = None,
    output_report_path: Optional[str] = None,
    controller_type: str = "max_pressure",
    enable_motion_fallback: bool = True,
    mqtt_host: Optional[str] = None,
    mqtt_port: int = 1883,
) -> Dict[str, Any]:
    """Runs end-to-end video ingestion, YOLO detection, telemetry generation, and next-step control decision."""

    logger.info("================================================================")
    logger.info("   EdgeFlow AI — Video to Raspberry Pi 5 Vision Pipeline Demo   ")
    logger.info("================================================================")

    # 1. Hardware Inspection
    hw = get_hardware_diagnostics()
    logger.info(f"Host Platform       : {hw['system_platform']} ({hw['device_model']})")
    logger.info(f"Target Intersection : {node_id} (Topology: {topology_id})")
    logger.info(f"Video Source        : {video_source_str}")
    logger.info(f"Target Max Frames   : {max_frames}")

    # Optional MQTT Client Setup
    mqtt_client = None
    if mqtt_host:
        try:
            import paho.mqtt.client as mqtt
            try:
                mqtt_client = mqtt.Client(mqtt.CallbackAPIVersion.VERSION1, client_id="vision-demo-pipeline")
            except AttributeError:
                mqtt_client = mqtt.Client(client_id="vision-demo-pipeline")
            mqtt_client.connect(mqtt_host, mqtt_port, 60)
            mqtt_client.loop_start()
            logger.info(f"MQTT Broker Client  : Connected to {mqtt_host}:{mqtt_port}")
        except Exception as e:
            logger.warning(f"MQTT Broker connection skipped ({e}). Continuing in standalone mode.")
            mqtt_client = None

    # 2. Resolve Model Path
    if not model_path:
        default_local = CURR_DIR / "models" / "yolov8n.onnx"
        default_repo = REPO_ROOT / "models" / "yolov8n.onnx"
        if default_local.is_file():
            model_path = str(default_local)
        elif default_repo.is_file():
            model_path = str(default_repo)

    if model_path and Path(model_path).is_file():
        logger.info(f"YOLO Model Weights  : {model_path} (YOLOv8n ONNX)")
    else:
        logger.warning("No ONNX model found; using motion contour detector as fallback.")
        model_path = None

    # 3. Initialize Detector, ROI Manager, Video Source, and Controller
    width, height = 640, 480
    detector = VehicleDetector(model_path=model_path, conf_threshold=conf_threshold, input_size=640)
    logger.info(f"Detector Initialized: [{detector.backend}]")

    fallback_detector = None
    if enable_motion_fallback and detector.backend != "motion_baseline":
        fallback_detector = VehicleDetector(model_path=None, motion_scale=1.0)

    video_source = create_video_source(video_source_str, width=width, height=height)
    roi_manager = ROIManager(width=width, height=height)
    roi_manager.setup_default_node_rois(node_id=node_id)
    metrics_extractor = MetricsExtractor()

    # Load Topology & Controller for Next Step
    topology = load_topology(topology_id)
    if controller_type == "max_pressure":
        controller = MaxPressureController(min_green_s=10.0, max_green_s=45.0)
    elif controller_type == "edgeflow":
        controller = EdgeFlowController()
    else:
        controller = FixedTimeController(cycle_time_s=60.0)

    # Video Writer Setup
    video_writer = None
    if output_video_path:
        out_p = Path(output_video_path)
        out_p.parent.mkdir(parents=True, exist_ok=True)
        fourcc = cv2.VideoWriter_fourcc(*"mp4v")
        video_writer = cv2.VideoWriter(str(out_p), fourcc, 15.0, (width, height))
        logger.info(f"Output Video File   : {out_p.resolve()}")

    # 4. Pipeline Execution Loop
    latencies = []
    frame_results = []
    total_detections = 0
    start_all = time.perf_counter()

    for idx in range(1, max_frames + 1):
        t0 = time.perf_counter()
        ret, frame = video_source.read_frame()
        if not ret or frame is None:
            logger.warning(f"Video stream ended at frame {idx - 1}.")
            break

        if frame.shape[:2] != (height, width):
            frame = cv2.resize(frame, (width, height), interpolation=cv2.INTER_AREA)

        # Step 2: YOLO Detection
        boxes, latency_ms = detector.detect(frame)
        scores = detector.last_scores

        # If zero detections (e.g. synthetic flat rectangle video) and fallback enabled, supplement with contours
        if not boxes and fallback_detector:
            f_boxes, _ = fallback_detector.detect(frame)
            if f_boxes:
                boxes = f_boxes
                scores = [0.85] * len(boxes)

        total_detections += len(boxes)

        # Step 3: Spatial ROI Assignment
        assigned = roi_manager.assign_detections(boxes)

        # Step 4: Extract Traffic Metrics
        approaches = []
        for app_id in roi_manager.approaches_for_node(node_id):
            app_boxes = assigned.get(app_id, [])
            roi_area = roi_manager.get_roi_area(app_id)
            m = metrics_extractor.compute_approach_metrics(
                approach_id=app_id,
                boxes=app_boxes,
                roi_area=roi_area,
                detection_confidence=float(scores[0]) if scores else 0.85
            )
            approaches.append(m)

        # Step 5: Build Canonical Telemetry Payload
        sim_time_s = round(idx * 0.1, 2)
        timestamp_ms = int(time.time() * 1000)
        telemetry = {
            "node_id": node_id,
            "source_type": "vision",
            "simulation_time_s": sim_time_s,
            "timestamp_ms": timestamp_ms,
            "current_phase_id": f"{node_id}_PHASE_NS",
            "approaches": approaches
        }

        # Validate Schema against contracts
        validate_payload(telemetry, "telemetry")

        # Publish Telemetry to MQTT Broker
        if mqtt_client and mqtt_client.is_connected():
            telemetry_topic = f"edgeflow/v1/telemetry/{node_id}"
            mqtt_client.publish(telemetry_topic, json.dumps(telemetry))

        # Step 6 & 7: Next Step Decision via Controller
        next_step_decision = controller.compute_command(
            node_id=node_id,
            telemetry=telemetry,
            topology=topology,
            current_time_s=sim_time_s
        )

        t1 = time.perf_counter()
        frame_latency_ms = (t1 - t0) * 1000
        latencies.append(frame_latency_ms)
        current_fps = 1000.0 / max(frame_latency_ms, 1.0)

        # Step 8: Annotate and Write Video Frame
        annotated = annotate_frame(
            frame=frame,
            boxes=boxes,
            scores=scores,
            roi_manager=roi_manager,
            node_id=node_id,
            telemetry=telemetry,
            decision=next_step_decision,
            fps=current_fps,
            latency_ms=frame_latency_ms,
            backend_name=detector.backend,
            frame_idx=idx,
        )

        if video_writer:
            video_writer.write(annotated)

        frame_results.append({
            "frame_idx": idx,
            "latency_ms": round(frame_latency_ms, 2),
            "detections": len(boxes),
            "total_queue": sum(a["queue_vehicles"] for a in approaches),
            "next_phase": next_step_decision.get("target_phase_id") if next_step_decision else None,
            "duration_s": next_step_decision.get("duration_s", next_step_decision.get("max_green_s", 30.0)) if next_step_decision else None,
        })

        if idx % 10 == 0 or idx == max_frames:
            q_sum = sum(a["queue_vehicles"] for a in approaches)
            dur = next_step_decision.get("duration_s", next_step_decision.get("max_green_s", 30.0)) if next_step_decision else 0
            decision_str = f"-> {next_step_decision['target_phase_id']} ({dur:.0f}s)" if next_step_decision else "-> HOLD"
            logger.info(f"Frame {idx:03d}/{max_frames:03d} | Detections: {len(boxes):2d} | Queue: {q_sum:3.0f} veh | "
                        f"Latency: {frame_latency_ms:5.1f}ms ({current_fps:4.1f} FPS) | Decision: {decision_str}")

    # 5. Cleanup
    total_time = time.perf_counter() - start_all
    video_source.release()
    if video_writer:
        video_writer.release()
    if mqtt_client:
        try:
            mqtt_client.loop_stop()
            mqtt_client.disconnect()
        except Exception:
            pass

    # 6. Summary Report
    avg_latency = float(np.mean(latencies)) if latencies else 0.0
    p50_latency = float(np.percentile(latencies, 50)) if latencies else 0.0
    p95_latency = float(np.percentile(latencies, 95)) if latencies else 0.0
    overall_fps = len(latencies) / max(total_time, 0.001)

    summary_report = {
        "status": "SUCCESS",
        "node_id": node_id,
        "topology_id": topology_id,
        "detector_backend": detector.backend,
        "model_path": model_path,
        "model_sha256": detector.model_sha256,
        "video_source": str(video_source_str),
        "frames_processed": len(latencies),
        "total_detections": total_detections,
        "metrics": {
            "avg_latency_ms": round(avg_latency, 2),
            "p50_latency_ms": round(p50_latency, 2),
            "p95_latency_ms": round(p95_latency, 2),
            "throughput_fps": round(overall_fps, 2),
        },
        "next_step_controller": controller_type,
        "mqtt": {
            "host": mqtt_host,
            "port": mqtt_port,
            "topic": f"edgeflow/v1/telemetry/{node_id}",
            "published": bool(mqtt_client and mqtt_client.is_connected())
        },
        "sample_telemetry": telemetry if latencies else None,
        "sample_decision": next_step_decision if latencies else None,
        "output_video": str(Path(output_video_path).resolve()) if output_video_path else None,
        "frame_log": frame_results,
    }

    if output_report_path:
        out_rep = Path(output_report_path)
        out_rep.parent.mkdir(parents=True, exist_ok=True)
        out_rep.write_text(json.dumps(summary_report, indent=2), encoding="utf-8")
        logger.info(f"Summary Report File : {out_rep.resolve()}")

    logger.info("================================================================")
    logger.info(f" Pipeline Finished Successfully in {total_time:.2f}s!")
    logger.info(f" - Frames Processed : {len(latencies)}")
    logger.info(f" - Throughput FPS   : {overall_fps:.2f} FPS")
    logger.info(f" - P50 / P95 Latency: {p50_latency:.1f}ms / {p95_latency:.1f}ms")
    logger.info(f" - MQTT Publishing  : {'ACTIVE (' + mqtt_host + ')' if mqtt_client and mqtt_client.is_connected() else 'STANDALONE (offline mode)'}")
    logger.info(f" - Final Decision   : Phase {next_step_decision.get('target_phase_id') if next_step_decision else 'N/A'}")
    logger.info("================================================================")

    return summary_report


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="EdgeFlow AI Video to Raspberry Pi Perception & Control Demo")
    parser.add_argument("--video", default="artifacts/yolo_demo_gpu.mp4",
                        help="Video source: file path (.mp4), 0 (USB cam), picamera, or synthetic")
    parser.add_argument("--model", default=None, help="Path to YOLO ONNX model (defaults to services/vision/models/yolov8n.onnx)")
    parser.add_argument("--frames", type=int, default=30, help="Number of frames to process (default: 30)")
    parser.add_argument("--conf", type=float, default=0.30, help="Confidence threshold for YOLO (default: 0.30)")
    parser.add_argument("--node-id", default="J1", help="Target intersection node ID (default: J1)")
    parser.add_argument("--topology", default="tabletop_j1_j2_v1", help="Canonical topology ID (default: tabletop_j1_j2_v1)")
    parser.add_argument("--controller", default="max_pressure", choices=["max_pressure", "edgeflow", "fixed_time"],
                        help="Next step controller algorithm to compute signal decisions")
    parser.add_argument("--output-video", default="artifacts/yolo_demo_annotated.mp4", help="Output annotated video path")
    parser.add_argument("--output-report", default="artifacts/yolo_demo_report.json", help="Output report JSON path")
    parser.add_argument("--no-fallback", action="store_true", help="Disable motion contour fallback on flat synthetic frames")
    parser.add_argument("--mqtt-host", default=None, help="MQTT Broker host (e.g. localhost, 192.168.1.100)")
    parser.add_argument("--mqtt-port", type=int, default=1883, help="MQTT Broker port (default: 1883)")

    args = parser.parse_args()

    report = run_pipeline_demo(
        video_source_str=args.video,
        model_path=args.model,
        topology_id=args.topology,
        node_id=args.node_id,
        max_frames=args.frames,
        conf_threshold=args.conf,
        output_video_path=args.output_video,
        output_report_path=args.output_report,
        controller_type=args.controller,
        enable_motion_fallback=not args.no_fallback,
        mqtt_host=args.mqtt_host,
        mqtt_port=args.mqtt_port,
    )
