"""Measure detector latency on frames from the service video sources; no MQTT or traffic KPI claims.

On the Pi, `--source picamera` reads Camera Module 3 through Picamera2 exactly like the service
(cv2.VideoCapture cannot open the CSI camera on Pi 5). Use the service frame size, e.g.
--width 1280 --height 720 when the ROI file is calibrated at 1280x720. File sources loop at EOF.
"""
import argparse
import json
import platform
import time
from pathlib import Path

import cv2
import numpy as np

try:
    from .detector import VehicleDetector
    from .hardware_monitor import get_runtime_hardware, read_board_model
    from .video_source import create_video_source
except ImportError:
    from detector import VehicleDetector
    from hardware_monitor import get_runtime_hardware, read_board_model
    from video_source import create_video_source


def benchmark(source, model=None, frames=300, warmup=20, input_size=640,
              output_format="yolov8", motion_scale=1.0, num_classes=80,
              vehicle_classes=(2, 3, 5, 7), width=640, height=480,
              lens_position=None, flicker_period_us=10000):
    if frames < 1 or warmup < 0:
        raise ValueError("frames must be positive and warmup nonnegative")
    detector = VehicleDetector(model_path=model, input_size=input_size, output_format=output_format,
                                motion_scale=motion_scale, num_classes=num_classes,
                                vehicle_classes=vehicle_classes)
    hardware_before = get_runtime_hardware()
    video = create_video_source(str(source), width=width, height=height,
                                lens_position=lens_position, flicker_period_us=flicker_period_us)
    samples, counts, frame_size = [], [], None
    try:
        for i in range(frames + warmup):
            started = time.perf_counter()
            ok, frame = video.read_frame()
            read_ms = (time.perf_counter() - started) * 1000
            if not ok or frame is None:
                break
            captured_at_ms = int(time.time() * 1000)
            frame_size = [int(frame.shape[1]), int(frame.shape[0])]
            boxes, _ = detector.detect(frame)
            if i >= warmup:
                samples.append({**detector.last_timings, "capture_ms": read_ms,
                                "end_to_end_ms": (time.perf_counter() - started) * 1000,
                                "captured_at_ms": captured_at_ms})
                counts.append(len(boxes))
    finally:
        video.release()
    if not samples:
        raise RuntimeError("No measured frames after warmup; check the camera, use a longer video or smaller warmup")
    timings = {key: {"p50_ms": float(np.median([s[key] for s in samples])),
                     "p95_ms": float(np.percentile([s[key] for s in samples], 95))}
               for key in samples[0] if key != "captured_at_ms"}
    return {"backend": detector.backend, "model_sha256": detector.model_sha256,
            "source": str(source), "frame_size": frame_size, "measured_frames": len(samples),
            "warmup_frames": warmup, "lens_position": lens_position,
            "input_size": input_size, "motion_scale": motion_scale, "output_format": output_format,
            "num_classes": num_classes, "vehicle_classes": list(vehicle_classes),
            "opencv": cv2.__version__, "opencv_threads": cv2.getNumThreads(), "numpy": np.__version__,
            "python": platform.python_version(), "platform": platform.platform(),
            "board_model": read_board_model(), "hardware_before": hardware_before,
            "hardware_after": get_runtime_hardware(),
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
    parser.add_argument("--width", type=int, default=640, help="capture width (match the ROI file)")
    parser.add_argument("--height", type=int, default=480, help="capture height (match the ROI file)")
    parser.add_argument("--lens-position", type=float, help="Picamera2 fixed focus in dioptres")
    parser.add_argument("--flicker-period-us", type=int, default=10000)
    parser.add_argument("--threads", type=int)
    parser.add_argument("--output", default="artifacts/vision_performance.json")
    args = parser.parse_args()
    if args.threads is not None:
        if args.threads < 1:
            parser.error("threads must be positive")
        cv2.setNumThreads(args.threads)
    result = benchmark(args.source, args.model, args.frames, args.warmup, args.input_size,
                       args.output_format, args.motion_scale, args.num_classes, args.vehicle_classes,
                       args.width, args.height, args.lens_position, args.flicker_period_us)
    path = Path(args.output)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(result, indent=2), encoding="utf-8")
    print(json.dumps({k: v for k, v in result.items() if k not in ("samples", "detections_per_frame")}, indent=2))
