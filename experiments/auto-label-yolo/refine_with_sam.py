#!/usr/bin/env python3
"""
Stage c (optional): refine each proposed box into a tighter box by prompting Segment Anything
(via the lightweight `ultralytics` wrapper around MobileSAM/FastSAM/SAM) with that box and
taking the resulting mask's own tight bounding box as the final label. A degenerate/empty mask
means the proposal was likely a false positive, so that detection is dropped rather than kept.

MobileSAM (~40MB, auto-downloaded on first use) is the default: full SAM checkpoints (ViT-B/L/H,
375MB-2.4GB) are impractical on CPU-only torch (this machine has no CUDA wheel per uv.lock) for
thousands of frames.

  python experiments/auto-label-yolo/refine_with_sam.py \
      --images experiments/auto-label-yolo/dataset/images \
      --proposals experiments/auto-label-yolo/dataset/proposals.json \
      --out experiments/auto-label-yolo/dataset/proposals_refined.json
"""
import argparse
import sys
from pathlib import Path
from typing import Any, Dict, List, Optional

import numpy as np

from common import load_json, write_json


def box_xywh_to_xyxy(box_xywh_px):
    x, y, w, h = box_xywh_px
    return [x, y, x + w, y + h]


def mask_to_tight_xywh(mask: np.ndarray) -> Optional[tuple]:
    ys, xs = np.where(mask)
    if ys.size == 0 or xs.size == 0:
        return None
    x0, x1 = int(xs.min()), int(xs.max())
    y0, y1 = int(ys.min()), int(ys.max())
    w, h = x1 - x0 + 1, y1 - y0 + 1
    if w <= 0 or h <= 0:
        return None
    return (x0, y0, w, h)


def refine_image(model, image_path: Path, detections: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """Runs one SAM call for the whole image (all box prompts share one image-encoder pass),
    replaces each surviving detection's box_xywh_px with the prompted mask's tight box, and
    drops detections whose mask came back empty/degenerate."""
    if not detections:
        return []
    bboxes = [box_xywh_to_xyxy(d["box_xywh_px"]) for d in detections]
    results = model(str(image_path), bboxes=bboxes, verbose=False)
    masks = results[0].masks
    if masks is None:
        return []
    mask_data = masks.data.cpu().numpy().astype(bool)
    refined = []
    for detection, mask in zip(detections, mask_data):
        tight = mask_to_tight_xywh(mask)
        if tight is None:
            continue
        refined.append({**detection, "box_xywh_px": list(tight)})
    return refined


def refine_dataset(images_dir: Path, proposals_path: Path, sam_model: str = "mobile_sam.pt",
                   limit: Optional[int] = None) -> Dict[str, Any]:
    from ultralytics import SAM  # imported lazily: heavy torch import, only needed for this stage

    model = SAM(sam_model)
    proposals = load_json(proposals_path)
    images = proposals["images"]
    if limit is not None:
        images = images[:limit]

    out_images = []
    total_before = total_after = 0
    for i, entry in enumerate(images, 1):
        detections = entry["detections"]
        total_before += len(detections)
        if detections and entry.get("width"):
            refined = refine_image(model, images_dir / entry["image"], detections)
        else:
            refined = []
        total_after += len(refined)
        out_images.append({**entry, "detections": refined, "dropped_count": len(detections) - len(refined)})
        if i % 50 == 0 or i == len(images):
            print(f"  refined {i}/{len(images)} images", flush=True)

    return {"sam_model": sam_model, "source_proposals": str(proposals_path),
            "total_detections_before": total_before, "total_detections_after": total_after,
            "images": out_images}


def parse_args(argv: Optional[List[str]] = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Refine proposed boxes with SAM box prompts")
    parser.add_argument("--images", type=Path, required=True)
    parser.add_argument("--proposals", type=Path, required=True)
    parser.add_argument("--out", type=Path, required=True)
    parser.add_argument("--sam-model", default="mobile_sam.pt",
                        help="mobile_sam.pt (default, CPU-friendly) | FastSAM-s.pt | sam_b.pt")
    parser.add_argument("--limit", type=int, help="only process the first N images (smoke test)")
    return parser.parse_args(argv)


def main(argv: Optional[List[str]] = None) -> int:
    args = parse_args(argv)
    result = refine_dataset(args.images, args.proposals, sam_model=args.sam_model, limit=args.limit)
    write_json(args.out, result)
    print(f"Refined {result['total_detections_before']} -> {result['total_detections_after']} boxes "
          f"across {len(result['images'])} images -> {args.out}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
