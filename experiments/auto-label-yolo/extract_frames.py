#!/usr/bin/env python3
"""
Stage a: extract candidate frames from services/vision/input_videos/*.mp4 (or any video files)
for YOLO auto-labeling.

Reads each video with a plain cv2.VideoCapture (not services/vision's FileVideoSource, whose
realtime=False mode still loops forever at EOF -- see services/vision/annotate_video.py's own
comment on why it avoids that class for offline, as-fast-as-possible reads): a bare cap.read()
loop stops reliably and cleanly on ret=False at the real end of file. Reuses
services/vision/capture_dataset.py's frame_signature() for near-duplicate skipping, so visually
static stretches of video (vehicles stopped at a red light, empty road) don't flood the dataset
with near-identical frames.

  python experiments/auto-label-yolo/extract_frames.py \
      --videos services/vision/input_videos/*.mp4 \
      --out experiments/auto-label-yolo/dataset \
      --every-seconds 1.0 --min-diff 2.0
"""
import argparse
import sys
import time
from pathlib import Path
from typing import Any, Dict, List, Optional

import cv2
import numpy as np

REPO_ROOT = Path(__file__).resolve().parents[2]
VISION_DIR = REPO_ROOT / "services" / "vision"
if str(VISION_DIR) not in sys.path:
    sys.path.insert(0, str(VISION_DIR))

from capture_dataset import frame_signature  # noqa: E402

from common import write_json  # noqa: E402


def extract_video(video_path: Path, images_dir: Path, video_id: str,
                   every_seconds: float = 1.0, min_diff: float = 2.0,
                   max_frames: Optional[int] = None) -> Dict[str, Any]:
    """Saves every `step`-th source frame (step = round(fps * every_seconds)) to
    images_dir/<video_id>_<source_frame_index:06d>.jpg, skipping near-duplicates whose
    frame_signature() mean-abs-diff to the last SAVED frame is below min_diff (0 keeps all).
    Returns a per-video manifest; raises if the file cannot be opened."""
    images_dir.mkdir(parents=True, exist_ok=True)
    cap = cv2.VideoCapture(str(video_path))
    if not cap.isOpened():
        raise RuntimeError(f"cannot open video {video_path}")
    fps = cap.get(cv2.CAP_PROP_FPS) or 30.0
    total_frames = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))
    step = max(1, round(fps * every_seconds))

    saved: List[Dict[str, Any]] = []
    skipped = failed = 0
    last_signature = None
    frame_index = 0
    try:
        while True:
            ok, frame = cap.read()
            if not ok:
                break
            if frame_index % step == 0:
                if frame is None or frame.size == 0:
                    failed += 1
                else:
                    signature = frame_signature(frame)
                    diff = None if last_signature is None else float(np.mean(np.abs(signature - last_signature)))
                    if diff is None or diff >= min_diff:
                        name = f"{video_id}_{frame_index:06d}.jpg"
                        if not cv2.imwrite(str(images_dir / name), frame, [cv2.IMWRITE_JPEG_QUALITY, 95]):
                            raise RuntimeError(f"could not write {images_dir / name}")
                        saved.append({"file": name, "source_frame_index": frame_index,
                                      "timestamp_s": round(frame_index / fps, 3),
                                      "diff_to_previous": None if diff is None else round(diff, 2)})
                        last_signature = signature
                    else:
                        skipped += 1
                if max_frames is not None and len(saved) >= max_frames:
                    break
            frame_index += 1
    finally:
        cap.release()

    return {"video_id": video_id, "source_file": str(video_path), "fps": fps,
            "total_frames": total_frames, "every_seconds": every_seconds, "step": step,
            "min_diff": min_diff, "saved": saved, "skipped_near_duplicates": skipped,
            "failed_reads": failed}


def parse_args(argv: Optional[List[str]] = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Extract candidate frames for YOLO auto-labeling")
    parser.add_argument("--videos", nargs="+", required=True, type=Path,
                        help="Video file paths (e.g. services/vision/input_videos/*.mp4)")
    parser.add_argument("--out", type=Path, required=True, help="dataset root, e.g. .../dataset")
    parser.add_argument("--every-seconds", type=float, default=1.0, help="seconds between sampled frames")
    parser.add_argument("--min-diff", type=float, default=2.0, help="skip near-duplicates; 0 keeps all")
    parser.add_argument("--max-frames-per-video", type=int, help="cap saved frames per video (smoke test)")
    return parser.parse_args(argv)


def main(argv: Optional[List[str]] = None) -> int:
    args = parse_args(argv)
    images_dir = args.out / "images"
    videos: Dict[str, Any] = {}
    totals = {"videos": 0, "saved": 0, "skipped_near_duplicates": 0, "failed_reads": 0}
    for video_path in args.videos:
        video_id = video_path.stem
        manifest = extract_video(video_path, images_dir, video_id, every_seconds=args.every_seconds,
                                 min_diff=args.min_diff, max_frames=args.max_frames_per_video)
        videos[video_id] = manifest
        totals["videos"] += 1
        totals["saved"] += len(manifest["saved"])
        totals["skipped_near_duplicates"] += manifest["skipped_near_duplicates"]
        totals["failed_reads"] += manifest["failed_reads"]
        print(f"{video_id}: saved {len(manifest['saved'])} frames "
              f"({manifest['skipped_near_duplicates']} near-duplicates skipped, "
              f"{manifest['failed_reads']} failed reads)")

    write_json(args.out / "frames_manifest.json",
              {"created_at": time.strftime("%Y-%m-%dT%H:%M:%S"), "videos": videos, "totals": totals})
    print(f"Total: {totals['saved']} frames saved to {images_dir}")
    return 0 if totals["saved"] else 1


if __name__ == "__main__":
    sys.exit(main())
