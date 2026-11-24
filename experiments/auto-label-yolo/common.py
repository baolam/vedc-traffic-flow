"""Shared constants and helpers for the auto-label-yolo pipeline (extract -> propose -> refine
-> export). Keeps the YOLO class taxonomy and label-line format in one place so all four stage
scripts agree on it.
"""
import json
from pathlib import Path
from typing import Any, Dict, Tuple

# COCO class id (matches services/vision/vision/detector.py's default vehicle_classes=(2,3,5,7))
# -> compact YOLO training id, in the order the COCO ids are given.
COCO_TO_YOLO_CLASS = {2: 0, 3: 1, 5: 2, 7: 3}
CLASS_NAMES = ["car", "motorcycle", "bus", "truck"]  # index == YOLO train id


def yolo_line(train_class_id: int, box_xywh_px: Tuple[int, int, int, int], img_w: int, img_h: int) -> str:
    """box_xywh_px: (x, y, w, h) top-left pixel box, the exact format VehicleDetector.detect()
    returns. Converts to a normalized YOLO detection label line: "class cx cy w h"."""
    x, y, w, h = box_xywh_px
    cx, cy = (x + w / 2) / img_w, (y + h / 2) / img_h
    return f"{train_class_id} {cx:.6f} {cy:.6f} {w / img_w:.6f} {h / img_h:.6f}"


def yolo_line_to_box(line: str, img_w: int, img_h: int) -> Tuple[int, Tuple[int, int, int, int]]:
    """Inverse of yolo_line(): parses one label line back into (class_id, (x, y, w, h)_px)."""
    class_id, cx, cy, w, h = line.split()
    class_id = int(class_id)
    w_px, h_px = float(w) * img_w, float(h) * img_h
    x_px = float(cx) * img_w - w_px / 2
    y_px = float(cy) * img_h - h_px / 2
    return class_id, (round(x_px), round(y_px), round(w_px), round(h_px))


def load_json(path: Path) -> Dict[str, Any]:
    return json.loads(Path(path).read_text(encoding="utf-8"))


def write_json(path: Path, data: Dict[str, Any]) -> None:
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, indent=2), encoding="utf-8")
