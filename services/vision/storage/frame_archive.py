"""
EdgeFlow AI - Local frame/clip archive (storage mechanism).
--------------------------------------------------------------
Periodically saves the already-annotated frame the Supervisor renders each tick (the same one
pushed to the live stream) to local disk, for later human review -- not a telemetry history log
and not an MQTT-outage durability buffer. Off by default; when enabled, retention is time-based
so the archive never grows unbounded.
"""

import logging
import os
import time
from pathlib import Path
from typing import Dict, Optional, Tuple

import cv2
import numpy as np

logger = logging.getLogger("vision-frame-archive")


class FrameArchive:
    """One instance per service process, shared across every node this camera covers. Call
    `maybe_capture()` once per tick per active node; it no-ops unless enabled and due."""

    def __init__(self, enabled: bool, base_dir: str, mode: str = "snapshot",
                interval_s: float = 30.0, clip_duration_s: float = 10.0,
                retention_hours: float = 24.0, jpeg_quality: int = 80):
        self.enabled = enabled
        self.base_dir = Path(base_dir)
        self.mode = mode  # "snapshot" | "clip"
        self.interval_s = max(interval_s, 0.1)
        self.clip_duration_s = max(clip_duration_s, 0.1)
        self.retention_hours = retention_hours
        self.jpeg_quality = jpeg_quality
        self._last_capture_s: Dict[str, float] = {}
        # node_id -> (writer, clip_started_monotonic)
        self._clip_writers: Dict[str, Tuple["cv2.VideoWriter", float]] = {}

        if self.enabled:
            logger.info(f"Frame Archive    : ENABLED -> {self.base_dir} (mode={self.mode}, "
                        f"every {self.interval_s}s, retention {self.retention_hours}h)")

    def maybe_capture(self, node_id: str, annotated_frame: np.ndarray, timestamp_ms: int) -> None:
        """No-op if disabled or if `interval_s` hasn't elapsed yet for this node."""
        if not self.enabled:
            return
        now = time.monotonic()
        last = self._last_capture_s.get(node_id, 0.0)
        if now - last < self.interval_s:
            return
        self._last_capture_s[node_id] = now
        if self.mode == "clip":
            self._append_clip_frame(node_id, annotated_frame, timestamp_ms, now)
        else:
            self._save_snapshot(node_id, annotated_frame, timestamp_ms)
        self._rotate(node_id)

    def _node_dir(self, node_id: str) -> Path:
        node_dir = self.base_dir / node_id
        node_dir.mkdir(parents=True, exist_ok=True)
        return node_dir

    def _save_snapshot(self, node_id: str, frame: np.ndarray, timestamp_ms: int) -> None:
        path = self._node_dir(node_id) / f"{timestamp_ms}.jpg"
        cv2.imwrite(str(path), frame, [cv2.IMWRITE_JPEG_QUALITY, self.jpeg_quality])

    def _append_clip_frame(self, node_id: str, frame: np.ndarray, timestamp_ms: int, now: float) -> None:
        entry = self._clip_writers.get(node_id)
        if entry is None or now - entry[1] >= self.clip_duration_s:
            if entry is not None:
                entry[0].release()
            h, w = frame.shape[:2]
            path = self._node_dir(node_id) / f"{timestamp_ms}.mp4"
            fps = max(1.0 / self.interval_s, 0.1)
            writer = cv2.VideoWriter(str(path), cv2.VideoWriter_fourcc(*"mp4v"), fps, (w, h))
            self._clip_writers[node_id] = (writer, now)
            entry = self._clip_writers[node_id]
        entry[0].write(frame)

    def _rotate(self, node_id: str) -> None:
        """Deletes files older than retention_hours in this node's directory. Stdlib only; the
        write rate is already throttled by interval_s/clip_duration_s, so running this on every
        capture is cheap."""
        if self.retention_hours <= 0:
            return
        cutoff = time.time() - self.retention_hours * 3600.0
        node_dir = self._node_dir(node_id)
        for entry in os.scandir(node_dir):
            if entry.is_file() and entry.stat().st_mtime < cutoff:
                try:
                    os.remove(entry.path)
                except OSError:
                    pass

    def close(self) -> None:
        """Flush any in-progress clip writer(s) on shutdown."""
        for writer, _ in self._clip_writers.values():
            writer.release()
        self._clip_writers.clear()
