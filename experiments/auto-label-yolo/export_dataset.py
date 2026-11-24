#!/usr/bin/env python3
"""
Stage d: write the final YOLO-format dataset (images/ + labels/*.txt), a review/*.jpg overlay
per image for fast visual QA, classes.txt, an Ultralytics-style data.yaml, and a provenance
manifest.json rolling up every upstream stage.

  python experiments/auto-label-yolo/export_dataset.py \
      --dataset-dir experiments/auto-label-yolo/dataset
"""
import argparse
import sys
import time
from pathlib import Path
from typing import Any, Dict, Optional

import cv2

from common import CLASS_NAMES, load_json, write_json, yolo_line, yolo_line_to_box

BOX_COLOR = (34, 197, 94)
TEXT_COLOR = (255, 255, 255)


def write_labels_and_review(images_dir: Path, refined_path: Path, labels_dir: Path,
                            review_dir: Path) -> Dict[str, Any]:
    labels_dir.mkdir(parents=True, exist_ok=True)
    review_dir.mkdir(parents=True, exist_ok=True)
    refined = load_json(refined_path)

    total_boxes = 0
    boxes_per_class = {name: 0 for name in CLASS_NAMES}
    images_with_zero_boxes = 0

    for entry in refined["images"]:
        stem = Path(entry["image"]).stem
        img_w, img_h = entry.get("width"), entry.get("height")
        label_path = labels_dir / f"{stem}.txt"
        if img_w and img_h:
            lines = [yolo_line(d["yolo_class_id"], tuple(d["box_xywh_px"]), img_w, img_h)
                    for d in entry["detections"]]
        else:
            lines = []
        label_path.write_text("\n".join(lines) + ("\n" if lines else ""), encoding="utf-8")
        if not lines:
            images_with_zero_boxes += 1
        total_boxes += len(lines)

        # Re-read the label file just written (not the in-memory detections) so the review image
        # is a correctness check of the on-disk YOLO format itself, not just of pipeline state.
        frame = cv2.imread(str(images_dir / entry["image"]))
        if frame is not None:
            for line in label_path.read_text(encoding="utf-8").splitlines():
                class_id, (x, y, w, h) = yolo_line_to_box(line, frame.shape[1], frame.shape[0])
                boxes_per_class[CLASS_NAMES[class_id]] += 1
                cv2.rectangle(frame, (x, y), (x + w, y + h), BOX_COLOR, 2)
                cv2.putText(frame, CLASS_NAMES[class_id], (x, max(0, y - 5)),
                           cv2.FONT_HERSHEY_SIMPLEX, 0.5, TEXT_COLOR, 1, cv2.LINE_AA)
            cv2.imwrite(str(review_dir / f"{stem}.jpg"), frame)

    return {"images": len(refined["images"]), "total_boxes": total_boxes,
            "boxes_per_class": boxes_per_class, "images_with_zero_boxes": images_with_zero_boxes}


def write_classes_and_datayaml(dataset_dir: Path) -> None:
    (dataset_dir / "classes.txt").write_text("\n".join(CLASS_NAMES) + "\n", encoding="utf-8")
    names_yaml = "\n".join(f"  {i}: {name}" for i, name in enumerate(CLASS_NAMES))
    (dataset_dir / "data.yaml").write_text(
        "path: .\n"
        "train: images\n"
        "val: images   # single-split placeholder -- split train/val by video_id before real fine-tuning\n"
        f"nc: {len(CLASS_NAMES)}\n"
        f"names:\n{names_yaml}\n", encoding="utf-8")


def write_manifest(dataset_dir: Path, export_counts: Dict[str, Any]) -> None:
    frames_manifest = load_json(dataset_dir / "frames_manifest.json") if (dataset_dir / "frames_manifest.json").exists() else None
    proposals = load_json(dataset_dir / "proposals.json") if (dataset_dir / "proposals.json").exists() else None
    refined = load_json(dataset_dir / "proposals_refined.json") if (dataset_dir / "proposals_refined.json").exists() else None
    write_json(dataset_dir / "manifest.json", {
        "created_at": time.strftime("%Y-%m-%dT%H:%M:%S"),
        "frame_extraction": frames_manifest.get("totals") if frames_manifest else None,
        "box_proposal": {"model": proposals.get("model"), "model_sha256": proposals.get("model_sha256"),
                         "conf_threshold": proposals.get("conf_threshold")} if proposals else None,
        "sam_refinement": {"sam_model": refined.get("sam_model"),
                           "total_detections_before": refined.get("total_detections_before"),
                           "total_detections_after": refined.get("total_detections_after")} if refined else None,
        "export": export_counts,
        "classes": CLASS_NAMES,
    })


def parse_args(argv=None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Export the final YOLO dataset from refined proposals")
    parser.add_argument("--dataset-dir", type=Path, required=True)
    parser.add_argument("--images", type=Path, help="default: <dataset-dir>/images")
    parser.add_argument("--refined", type=Path, help="default: <dataset-dir>/proposals_refined.json")
    return parser.parse_args(argv)


def main(argv: Optional[list] = None) -> int:
    args = parse_args(argv)
    dataset_dir = args.dataset_dir
    images_dir = args.images or dataset_dir / "images"
    refined_path = args.refined or dataset_dir / "proposals_refined.json"

    counts = write_labels_and_review(images_dir, refined_path, dataset_dir / "labels", dataset_dir / "review")
    write_classes_and_datayaml(dataset_dir)
    write_manifest(dataset_dir, counts)

    print(f"Exported {counts['total_boxes']} boxes across {counts['images']} images "
          f"({counts['images_with_zero_boxes']} with zero boxes) -> {dataset_dir}")
    print(f"Per-class: {counts['boxes_per_class']}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
