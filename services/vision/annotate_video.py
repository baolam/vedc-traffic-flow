#!/usr/bin/env python3
"""
Annotate a demo video with what the vision service sees: detections, calibrated approach ROIs and the
vehicle count per approach. Same detector, model and ROI file as services/vision/main.py.

The output is a recorded clip for the dashboard's vision panel (served by the API from
artifacts/yolo_demo_annotated.mp4); it is not a live stream, and the dashboard labels it as such.

  python services/vision/annotate_video.py \
      --video data/demo_video/video_demo_150s.mp4 \
      --rois services/vision/rois/rois_video_1280x720.json \
      --model models/yolo11n_sa_ban.onnx --num-classes 1 --vehicle-classes 0 --seconds 60
"""
import argparse
import json
import logging
import time
from pathlib import Path
from typing import Dict, List, Tuple

import cv2
import numpy as np

from detector import VehicleDetector
from roi_config import load_roi_config
from roi_manager import ROIManager

logger = logging.getLogger("annotate_video")

Box = Tuple[int, int, int, int]
NODE_COLORS = [(255, 191, 0), (0, 200, 255), (180, 105, 255), (60, 220, 60)]  # BGR per node
BOX_IN_ROI = (60, 220, 60)
BOX_OUTSIDE = (160, 160, 160)


def open_writer(path: Path, fps: float, size: Tuple[int, int]) -> Tuple[cv2.VideoWriter, str]:
    """H.264 ('avc1') plays in browsers; mp4v is the fallback and may only play in desktop players."""
    path.parent.mkdir(parents=True, exist_ok=True)
    for fourcc in ("avc1", "mp4v"):
        writer = cv2.VideoWriter(str(path), cv2.VideoWriter_fourcc(*fourcc), fps, size)
        if writer.isOpened():
            return writer, fourcc
        writer.release()
    raise RuntimeError(f"cannot open a video writer for {path}")


def draw_frame(frame: np.ndarray, rois: ROIManager, node_of: Dict[str, str], node_color: Dict[str, Tuple[int, int, int]],
               boxes: List[Box], assigned: Dict[str, List[Box]], caption: str) -> np.ndarray:
    out = frame.copy()
    overlay = out.copy()
    for app_id, info in rois.rois.items():
        cv2.fillPoly(overlay, [info["polygon"]], node_color[node_of[app_id]])
    out = cv2.addWeighted(overlay, 0.18, out, 0.82, 0)
    in_roi = {b for lst in assigned.values() for b in lst}
    for (x, y, w, h) in boxes:
        cv2.rectangle(out, (x, y), (x + w, y + h), BOX_IN_ROI if (x, y, w, h) in in_roi else BOX_OUTSIDE, 2)
    for app_id, info in rois.rois.items():
        poly = info["polygon"]
        cv2.polylines(out, [poly], True, node_color[node_of[app_id]], 2)
        cx, cy = poly.mean(axis=0).astype(int)
        label = f"{app_id.split('_', 1)[1].replace('_IN', '')}:{len(assigned.get(app_id, []))}"
        cv2.putText(out, label, (int(cx) - 22, int(cy) + 5), cv2.FONT_HERSHEY_SIMPLEX, 0.5, (0, 0, 0), 3, cv2.LINE_AA)
        cv2.putText(out, label, (int(cx) - 22, int(cy) + 5), cv2.FONT_HERSHEY_SIMPLEX, 0.5, (255, 255, 255), 1, cv2.LINE_AA)
    cv2.rectangle(out, (0, 0), (out.shape[1], 30), (15, 23, 42), -1)
    cv2.putText(out, caption, (10, 21), cv2.FONT_HERSHEY_SIMPLEX, 0.55, (230, 230, 230), 1, cv2.LINE_AA)
    return out


def annotate(args: argparse.Namespace) -> Dict[str, object]:
    roi_config = load_roi_config(args.rois)
    rois = ROIManager(width=roi_config.frame_size[0], height=roi_config.frame_size[1])
    node_of: Dict[str, str] = {}
    for node_id, polygons in roi_config.nodes.items():
        rois.set_node_rois(node_id, polygons)
        node_of.update({app_id: node_id for app_id in polygons})
    node_color = {n: NODE_COLORS[i % len(NODE_COLORS)] for i, n in enumerate(roi_config.nodes)}
    detector = VehicleDetector(model_path=args.model, conf_threshold=args.conf, input_size=args.input_size,
                               num_classes=args.num_classes,
                               vehicle_classes=tuple(int(c) for c in args.vehicle_classes.split(",")))

    cap = cv2.VideoCapture(args.video)
    if not cap.isOpened():
        raise SystemExit(f"cannot open video {args.video}")
    fps = cap.get(cv2.CAP_PROP_FPS) or 10.0
    size = (int(cap.get(cv2.CAP_PROP_FRAME_WIDTH)), int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT)))
    if size != roi_config.frame_size:
        raise SystemExit(f"video is {size[0]}x{size[1]} but the ROI file is for {roi_config.frame_size}")
    writer, fourcc = open_writer(Path(args.out), fps, size)
    max_frames = int(args.seconds * fps) if args.seconds > 0 else None

    counts: Dict[str, List[int]] = {app_id: [] for app_id in rois.rois}
    frames, started = 0, time.monotonic()
    model_name = Path(args.model).name
    while max_frames is None or frames < max_frames:
        ok, frame = cap.read()
        if not ok:
            break
        boxes, _ = detector.detect(frame)
        assigned = rois.assign_detections(boxes)
        for app_id in counts:
            counts[app_id].append(len(assigned.get(app_id, [])))
        caption = (f"EdgeFlow vision | {model_name} | t={frames / fps:5.1f}s | "
                   + "  ".join(f"{n}: {sum(len(assigned[a]) for a in node_of if node_of[a] == n)} xe trong ROI"
                               for n in roi_config.nodes))
        writer.write(draw_frame(frame, rois, node_of, node_color, boxes, assigned, caption))
        frames += 1
    writer.release()
    cap.release()
    elapsed = time.monotonic() - started

    processing_fps = round(frames / elapsed, 2) if elapsed > 0 else None
    report = {
        # Same envelope as demo_video_pipeline.py, which /api/v1/vision/demo-report also serves
        "status": "SUCCESS",
        "metrics": {"frames_processed": frames, "processing_fps_on_this_machine": processing_fps},
        "source": "services/vision/annotate_video.py (recorded clip, not a live stream)",
        "video": str(args.video),
        "model": model_name,
        "model_sha256": detector.model_sha256,
        "detector_backend": detector.backend,
        "roi_sha256": roi_config.sha256,
        "frames_processed": frames,
        "video_fps": fps,
        "codec": fourcc,
        "processing_fps_on_this_machine": processing_fps,
        "mean_vehicles_per_approach": {a: round(float(np.mean(c)), 2) if c else 0.0 for a, c in counts.items()},
    }
    Path(args.report).parent.mkdir(parents=True, exist_ok=True)
    Path(args.report).write_text(json.dumps(report, indent=2), encoding="utf-8")
    return report


def parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser(description="Annotate a demo video with detections and approach ROIs")
    p.add_argument("--video", required=True)
    p.add_argument("--rois", required=True, help="ROI JSON (services/vision/rois/...)")
    p.add_argument("--model", required=True, help="YOLO ONNX model")
    p.add_argument("--num-classes", type=int, default=80)
    p.add_argument("--vehicle-classes", default="2,3,5,7")
    p.add_argument("--conf", type=float, default=0.4)
    p.add_argument("--input-size", type=int, default=640)
    p.add_argument("--seconds", type=float, default=60.0, help="length to annotate (0 = whole video)")
    p.add_argument("--out", default="artifacts/yolo_demo_annotated.mp4")
    p.add_argument("--report", default="artifacts/yolo_demo_report.json")
    return p.parse_args()


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
    result = annotate(parse_args())
    logger.info(f"{result['frames_processed']} frames -> codec {result['codec']}, "
                f"{result['processing_fps_on_this_machine']} fps on this machine")
