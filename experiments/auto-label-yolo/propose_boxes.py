#!/usr/bin/env python3
"""
Stage b: propose vehicle box + class for every extracted frame, using the project's own
VehicleDetector (services/vision/vision/detector.py) loaded with the COCO YOLOv8n model already
checked into git (services/vision/models/yolov8n.onnx). COCO class ids 2/3/5/7
(car/motorcycle/bus/truck) are remapped to compact YOLO training ids 0/1/2/3 via
common.COCO_TO_YOLO_CLASS.

  python experiments/auto-label-yolo/propose_boxes.py \
      --images experiments/auto-label-yolo/dataset/images \
      --model services/vision/models/yolov8n.onnx \
      --out experiments/auto-label-yolo/dataset/proposals.json
"""
import argparse
import sys
from pathlib import Path
from typing import Any, Dict, List, Optional

import cv2

REPO_ROOT = Path(__file__).resolve().parents[2]
VISION_DIR = REPO_ROOT / "services" / "vision"
if str(VISION_DIR) not in sys.path:
    sys.path.insert(0, str(VISION_DIR))

from vision.detector import VehicleDetector  # noqa: E402

from common import COCO_TO_YOLO_CLASS, write_json  # noqa: E402


def propose_for_image(detector: VehicleDetector, image_path: Path) -> Dict[str, Any]:
    frame = cv2.imread(str(image_path))
    if frame is None:
        return {"image": image_path.name, "width": None, "height": None, "detections": [],
                "error": "could not read image"}
    h, w = frame.shape[:2]
    boxes, _ = detector.detect(frame)
    detections = []
    for box, score, coco_class_id in zip(boxes, detector.last_scores, detector.last_class_ids):
        yolo_class_id = COCO_TO_YOLO_CLASS.get(coco_class_id)
        if yolo_class_id is None:
            continue  # outside the configured vehicle_classes mapping; should not happen
        detections.append({"coco_class_id": coco_class_id, "yolo_class_id": yolo_class_id,
                           "score": score, "box_xywh_px": list(box)})
    return {"image": image_path.name, "width": w, "height": h, "detections": detections}


def propose_dataset(images_dir: Path, model_path: Path, conf_threshold: float = 0.4,
                    nms_threshold: float = 0.45, input_size: int = 640,
                    limit: Optional[int] = None) -> Dict[str, Any]:
    detector = VehicleDetector(model_path=str(model_path), output_format="yolov8", num_classes=80,
                               vehicle_classes=tuple(COCO_TO_YOLO_CLASS), conf_threshold=conf_threshold,
                               nms_threshold=nms_threshold, input_size=input_size)
    image_paths = sorted(images_dir.glob("*.jpg"))
    if limit is not None:
        image_paths = image_paths[:limit]
    images = []
    for i, p in enumerate(image_paths, 1):
        images.append(propose_for_image(detector, p))
        if i % 100 == 0 or i == len(image_paths):
            print(f"  proposed {i}/{len(image_paths)} images", flush=True)
    return {"model": str(model_path), "model_sha256": detector.model_sha256,
            "conf_threshold": conf_threshold, "nms_threshold": nms_threshold,
            "input_size": input_size, "images": images}


def parse_args(argv: Optional[List[str]] = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Propose vehicle box+class for extracted frames")
    parser.add_argument("--images", type=Path, required=True)
    parser.add_argument("--model", type=Path, required=True)
    parser.add_argument("--out", type=Path, required=True)
    parser.add_argument("--conf", type=float, default=0.4, dest="conf_threshold")
    parser.add_argument("--nms", type=float, default=0.45, dest="nms_threshold")
    parser.add_argument("--input-size", type=int, default=640)
    parser.add_argument("--limit", type=int, help="only process the first N images (smoke test)")
    return parser.parse_args(argv)


def main(argv: Optional[List[str]] = None) -> int:
    args = parse_args(argv)
    result = propose_dataset(args.images, args.model, conf_threshold=args.conf_threshold,
                             nms_threshold=args.nms_threshold, input_size=args.input_size,
                             limit=args.limit)
    write_json(args.out, result)
    total_detections = sum(len(img["detections"]) for img in result["images"])
    print(f"Proposed {total_detections} boxes across {len(result['images'])} images -> {args.out}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
