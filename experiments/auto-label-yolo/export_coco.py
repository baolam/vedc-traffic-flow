#!/usr/bin/env python3
"""
Stage e (optional): convert the exported YOLO labels (dataset/labels/*.txt + classes.txt) into
one standard COCO-format annotations.json, so the pre-labeled dataset can be opened in any
COCO-aware manual annotation tool (X-AnyLabeling, CVAT, Label Studio, Roboflow, ...) for manual
review/correction, not just YOLO-aware ones.

Reads the on-disk YOLO labels (not in-memory pipeline state) so this is a conversion of the same
artifact export_dataset.py already validated, not a second source of truth. category id follows
COCO convention (1-indexed): category_id = yolo_class_id + 1.

  python experiments/auto-label-yolo/export_coco.py \
      --dataset-dir experiments/auto-label-yolo/dataset
"""
import argparse
import sys
from pathlib import Path
from typing import Any, Dict, List, Optional

import cv2

from common import CLASS_NAMES, write_json, yolo_line_to_box


def build_coco(images_dir: Path, labels_dir: Path) -> Dict[str, Any]:
    images: List[Dict[str, Any]] = []
    annotations: List[Dict[str, Any]] = []
    image_id = annotation_id = 0

    for image_path in sorted(images_dir.glob("*.jpg")):
        frame = cv2.imread(str(image_path))
        if frame is None:
            continue
        h, w = frame.shape[:2]
        image_id += 1
        images.append({"id": image_id, "file_name": image_path.name, "width": w, "height": h})

        label_path = labels_dir / f"{image_path.stem}.txt"
        if not label_path.exists():
            continue
        for line in label_path.read_text(encoding="utf-8").splitlines():
            if not line.strip():
                continue
            class_id, (x, y, box_w, box_h) = yolo_line_to_box(line, w, h)
            annotation_id += 1
            annotations.append({
                "id": annotation_id, "image_id": image_id, "category_id": class_id + 1,
                "bbox": [x, y, box_w, box_h], "area": box_w * box_h, "iscrowd": 0,
            })

    categories = [{"id": i + 1, "name": name, "supercategory": "vehicle"}
                  for i, name in enumerate(CLASS_NAMES)]
    return {"images": images, "annotations": annotations, "categories": categories}


def parse_args(argv: Optional[List[str]] = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Convert exported YOLO labels to COCO JSON")
    parser.add_argument("--dataset-dir", type=Path, required=True)
    parser.add_argument("--images", type=Path, help="default: <dataset-dir>/images")
    parser.add_argument("--labels", type=Path, help="default: <dataset-dir>/labels")
    parser.add_argument("--out", type=Path, help="default: <dataset-dir>/annotations_coco.json")
    return parser.parse_args(argv)


def main(argv: Optional[List[str]] = None) -> int:
    args = parse_args(argv)
    images_dir = args.images or args.dataset_dir / "images"
    labels_dir = args.labels or args.dataset_dir / "labels"
    out_path = args.out or args.dataset_dir / "annotations_coco.json"

    coco = build_coco(images_dir, labels_dir)
    write_json(out_path, coco)
    print(f"Wrote COCO annotations: {len(coco['images'])} images, {len(coco['annotations'])} "
          f"boxes, {len(coco['categories'])} categories -> {out_path}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
