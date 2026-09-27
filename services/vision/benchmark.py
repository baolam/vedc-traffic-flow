"""Measure detector latency on decoded video frames; no MQTT or traffic KPI claims."""
import argparse
import json
import platform
import time
from pathlib import Path

import cv2
import numpy as np

try:
    from .detector import VehicleDetector
except ImportError:
    from detector import VehicleDetector


def benchmark(source, model=None, frames=300, warmup=20, input_size=640,
              output_format="yolov8", motion_scale=1.0, num_classes=80,
              vehicle_classes=(2, 3, 5, 7)):
    if frames < 1 or warmup < 0:
        raise ValueError("frames must be positive and warmup nonnegative")
    detector = VehicleDetector(model_path=model, input_size=input_size, output_format=output_format,
                                motion_scale=motion_scale, num_classes=num_classes,
                                vehicle_classes=vehicle_classes)
    cap = cv2.VideoCapture(int(source) if str(source).isdigit() else str(source))
    if not cap.isOpened():
        raise RuntimeError(f"Cannot open video source: {source}")
    samples, counts = [], []
    try:
        for i in range(frames + warmup):
            started = time.perf_counter()
            ok, frame = cap.read()
            read_ms = (time.perf_counter() - started) * 1000
            if not ok:
                break
            boxes, _ = detector.detect(frame)
            if i >= warmup:
                samples.append({**detector.last_timings, "capture_ms": read_ms,
                                "end_to_end_ms": (time.perf_counter() - started) * 1000})
                counts.append(len(boxes))
    finally:
        cap.release()
    if not samples:
        raise RuntimeError("No measured frames after warmup; use a longer video or smaller warmup")
    timings = {key: {"p50_ms": float(np.median([s[key] for s in samples])),
                     "p95_ms": float(np.percentile([s[key] for s in samples], 95))}
               for key in samples[0]}
    return {"backend": detector.backend, "model_sha256": detector.model_sha256,
            "source": str(source), "measured_frames": len(samples), "warmup_frames": warmup,
            "input_size": input_size, "motion_scale": motion_scale, "output_format": output_format,
            "num_classes": num_classes, "vehicle_classes": list(vehicle_classes),
            "opencv": cv2.__version__, "opencv_threads": cv2.getNumThreads(),
            "python": platform.python_version(), "platform": platform.platform(),
            "throughput_fps": 1000 / np.mean([s["end_to_end_ms"] for s in samples]),
            "timings": timings, "detections_per_frame": counts,
            "accuracy_evaluated": False, "samples": samples}


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--source", required=True)
    parser.add_argument("--model")
    parser.add_argument("--frames", type=int, default=300)
    parser.add_argument("--warmup", type=int, default=20)
    parser.add_argument("--input-size", type=int, default=640)
    parser.add_argument("--output-format", choices=["yolov8", "yolov5", "legacy"], default="yolov8")
    parser.add_argument("--num-classes", type=int, default=80)
    parser.add_argument("--vehicle-classes", type=int, nargs="+", default=[2, 3, 5, 7])
    parser.add_argument("--motion-scale", type=float, default=1.0)
    parser.add_argument("--threads", type=int)
    parser.add_argument("--output", default="artifacts/vision_performance.json")
    args = parser.parse_args()
    if args.threads is not None:
        if args.threads < 1:
            parser.error("threads must be positive")
        cv2.setNumThreads(args.threads)
    result = benchmark(args.source, args.model, args.frames, args.warmup, args.input_size,
                       args.output_format, args.motion_scale, args.num_classes, args.vehicle_classes)
    path = Path(args.output)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(result, indent=2), encoding="utf-8")
    print(json.dumps({k: v for k, v in result.items() if k not in ("samples", "detections_per_frame")}, indent=2))
