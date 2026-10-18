"""
EdgeFlow AI - record tabletop frames for labelling and fine-tuning the vehicle detector.

Frames come from the same capture path as the service (Picamera2, locked focus, anti-flicker,
service frame size), so the training images match what the detector sees at run time.
One run = one recording session. Revised Plan (2): split train/val/test by session, never by
neighbouring frames, and lock the test split before tuning.

On the Pi (camera on its final stand, same LensPosition as .env.rpi):
  .venv-pi/bin/python services/vision/capture_dataset.py --session s01_low_daylight \
      --video picamera --width 1280 --height 720 --lens-position 2.0 \
      --every 1.0 --duration 120 --out ~/dataset --note "2-3 cars per approach, daylight"
Move the cars between shots; near-duplicate frames (static scene) are skipped.
"""

import argparse
import json
import re
import sys
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Callable, Dict, List, Optional, Tuple

import cv2
import numpy as np

CURR_DIR = Path(__file__).resolve().parent
if str(CURR_DIR) not in sys.path:
    sys.path.insert(0, str(CURR_DIR))

from video_source import BaseVideoSource, create_video_source  # noqa: E402

SESSION_NAME = re.compile(r"^[A-Za-z0-9][A-Za-z0-9_-]*$")
DIFF_SIZE = (160, 90)  # downscaled grayscale used only for the near-duplicate test


def frame_signature(frame: np.ndarray) -> np.ndarray:
    gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY) if frame.ndim == 3 else frame
    return cv2.resize(gray, DIFF_SIZE, interpolation=cv2.INTER_AREA).astype(np.float32)


def record_session(source: BaseVideoSource, out_dir: Path, session: str, every_s: float = 1.0,
                   duration_s: float = 120.0, max_frames: Optional[int] = None,
                   max_reads: Optional[int] = None, min_diff: float = 2.0, warmup_frames: int = 10,
                   size: Tuple[int, int] = (1280, 720), note: str = "",
                   source_info: Optional[Dict[str, Any]] = None,
                   sleep: Callable[[float], None] = time.sleep,
                   clock: Callable[[], float] = time.monotonic) -> Dict[str, Any]:
    """
    Saves frames to out_dir/<session>/<session>_NNNNNN.jpg plus session.json and returns the manifest.
    min_diff: mean absolute grey-level difference (0-255) to the last saved frame below which a
    frame counts as a near-duplicate and is skipped; 0 keeps every frame.
    """
    if not SESSION_NAME.match(session or ""):
        raise ValueError(f"Session name must be letters, digits, '_' or '-': {session!r}")
    session_dir = Path(out_dir).expanduser() / session
    session_dir.mkdir(parents=True, exist_ok=False)  # never mix two recordings in one session

    for _ in range(max(warmup_frames, 0)):  # let auto exposure and white balance settle
        source.read_frame()

    width, height = size
    frames: List[Dict[str, Any]] = []
    skipped = failed = reads = 0
    last_signature = None
    deadline = clock() + duration_s
    while clock() < deadline:
        if max_frames is not None and len(frames) >= max_frames:
            break
        if max_reads is not None and reads >= max_reads:
            break
        reads += 1
        ok, frame = source.read_frame()
        if not ok or frame is None:
            failed += 1
            sleep(every_s)
            continue
        if frame.shape[:2] != (height, width):
            frame = cv2.resize(frame, (width, height), interpolation=cv2.INTER_AREA)
        signature = frame_signature(frame)
        diff = None if last_signature is None else float(np.mean(np.abs(signature - last_signature)))
        if diff is not None and diff < min_diff:
            skipped += 1
            sleep(every_s)
            continue
        name = f"{session}_{len(frames) + 1:06d}.jpg"
        if not cv2.imwrite(str(session_dir / name), frame, [cv2.IMWRITE_JPEG_QUALITY, 95]):
            raise RuntimeError(f"Could not write {session_dir / name}")
        frames.append({"file": name, "captured_at_ms": int(time.time() * 1000),
                       "diff_to_previous": None if diff is None else round(diff, 2)})
        last_signature = signature
        sleep(every_s)

    manifest = {
        "session": session,
        "note": note,
        "created_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "source": dict(source_info or {}),
        "frame_size": [width, height],
        "every_s": every_s,
        "min_diff": min_diff,
        "frames": frames,
        "skipped_near_duplicates": skipped,
        "failed_reads": failed,
    }
    (session_dir / "session.json").write_text(json.dumps(manifest, indent=2), encoding="utf-8")
    return manifest


def parse_args(argv: Optional[List[str]] = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Record tabletop frames for detector fine-tuning")
    parser.add_argument("--session", required=True, help="e.g. s01_low_daylight (one folder per recording)")
    parser.add_argument("--out", type=Path, required=True, help="dataset root, e.g. ~/dataset")
    parser.add_argument("--video", default="picamera")
    parser.add_argument("--width", type=int, default=1280)
    parser.add_argument("--height", type=int, default=720)
    parser.add_argument("--lens-position", type=float, help="same value as CAMERA_LENS_POSITION")
    parser.add_argument("--flicker-period-us", type=int, default=10000)
    parser.add_argument("--every", type=float, default=1.0, help="seconds between saved frames")
    parser.add_argument("--duration", type=float, default=120.0, help="seconds to record")
    parser.add_argument("--max-frames", type=int)
    parser.add_argument("--min-diff", type=float, default=2.0, help="skip near-duplicates; 0 keeps all")
    parser.add_argument("--note", default="", help="queue level, lighting, anything unusual")
    return parser.parse_args(argv)


def main(argv: Optional[List[str]] = None) -> int:
    args = parse_args(argv)
    source = create_video_source(args.video, width=args.width, height=args.height,
                                 lens_position=args.lens_position, flicker_period_us=args.flicker_period_us)
    try:
        manifest = record_session(
            source, args.out, args.session, every_s=args.every, duration_s=args.duration,
            max_frames=args.max_frames, min_diff=args.min_diff, size=(args.width, args.height),
            note=args.note, source_info={"video": args.video, "lens_position": args.lens_position,
                                         "flicker_period_us": args.flicker_period_us})
    finally:
        source.release()
    print(f"Saved {len(manifest['frames'])} frames to {Path(args.out).expanduser() / args.session} "
          f"({manifest['skipped_near_duplicates']} near-duplicates skipped, {manifest['failed_reads']} failed reads)")
    return 0 if manifest["frames"] else 1


if __name__ == "__main__":
    sys.exit(main())
