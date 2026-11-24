#!/usr/bin/env python3
"""
Stitches the dataset/review/*.jpg overlay frames (box + class label already drawn by
export_dataset.py) back into a playable .mp4 per source video, so the auto-labeled result can be
watched instead of flipped through one image at a time.

Each review frame represents 1 sampled second of the source video (per extract_frames.py's
default --every-seconds), so --fps controls playback speed, not real time: --fps 5 plays back
5x faster than the original footage (1 frame = 1 real second shown for 1/5 second). A small
caption bar (source video id + original timestamp, pulled from frames_manifest.json) is burned
in for orientation, same spirit as services/vision/annotate_video.py's caption bar.

  python experiments/auto-label-yolo/make_preview_video.py \
      --dataset-dir experiments/auto-label-yolo/dataset \
      --video-id all --fps 5
"""
import argparse
import sys
from pathlib import Path
from typing import Dict, List, Optional, Tuple

import cv2

from common import load_json


def open_writer(path: Path, fps: float, size: Tuple[int, int]) -> Tuple[cv2.VideoWriter, str]:
    """H.264 ('avc1') plays in browsers; mp4v is the fallback (desktop players only)."""
    path.parent.mkdir(parents=True, exist_ok=True)
    for fourcc in ("avc1", "mp4v"):
        writer = cv2.VideoWriter(str(path), cv2.VideoWriter_fourcc(*fourcc), fps, size)
        if writer.isOpened():
            return writer, fourcc
        writer.release()
    raise RuntimeError(f"cannot open a video writer for {path}")


def timestamp_lookup(dataset_dir: Path, video_id: str) -> Dict[str, float]:
    manifest_path = dataset_dir / "frames_manifest.json"
    if not manifest_path.exists():
        return {}
    manifest = load_json(manifest_path)
    video = manifest.get("videos", {}).get(video_id, {})
    return {Path(f["file"]).stem: f["timestamp_s"] for f in video.get("saved", [])}


def build_preview(dataset_dir: Path, video_id: str, out_path: Path, fps: float = 5.0) -> Dict[str, object]:
    review_dir = dataset_dir / "review"
    frames = sorted(review_dir.glob(f"{video_id}_*.jpg"))
    if not frames:
        raise FileNotFoundError(f"no review frames found for video_id={video_id!r} under {review_dir}")
    timestamps = timestamp_lookup(dataset_dir, video_id)

    first = cv2.imread(str(frames[0]))
    h, w = first.shape[:2]
    writer, fourcc = open_writer(out_path, fps, (w, h))
    try:
        for frame_path in frames:
            frame = cv2.imread(str(frame_path))
            if frame is None:
                continue
            ts = timestamps.get(frame_path.stem)
            caption = f"video {video_id} | t={ts:5.1f}s" if ts is not None else f"video {video_id} | {frame_path.stem}"
            cv2.rectangle(frame, (0, 0), (w, 26), (15, 23, 42), -1)
            cv2.putText(frame, caption, (8, 18), cv2.FONT_HERSHEY_SIMPLEX, 0.55, (230, 230, 230), 1, cv2.LINE_AA)
            writer.write(frame)
    finally:
        writer.release()
    return {"video_id": video_id, "frames": len(frames), "fps": fps, "fourcc": fourcc, "out": str(out_path)}


def discover_video_ids(dataset_dir: Path) -> List[str]:
    stems = {p.name.split("_", 1)[0] for p in (dataset_dir / "review").glob("*.jpg")}
    return sorted(stems)


def parse_args(argv: Optional[List[str]] = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Stitch review overlay frames into a playable preview video")
    parser.add_argument("--dataset-dir", type=Path, required=True)
    parser.add_argument("--video-id", default="all", help="e.g. '1', or 'all' for every source video found")
    parser.add_argument("--out-dir", type=Path, help="default: <dataset-dir>/preview")
    parser.add_argument("--fps", type=float, default=5.0, help="playback fps (not real-time; see module docstring)")
    return parser.parse_args(argv)


def main(argv: Optional[List[str]] = None) -> int:
    args = parse_args(argv)
    out_dir = args.out_dir or args.dataset_dir / "preview"
    video_ids = discover_video_ids(args.dataset_dir) if args.video_id == "all" else [args.video_id]
    if not video_ids:
        print(f"No review frames found under {args.dataset_dir / 'review'}", file=sys.stderr)
        return 1
    for video_id in video_ids:
        result = build_preview(args.dataset_dir, video_id, out_dir / f"{video_id}.mp4", fps=args.fps)
        print(f"video {video_id}: {result['frames']} frames -> {result['out']} "
              f"({result['fourcc']}, {args.fps} fps)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
