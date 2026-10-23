"""
EdgeFlow AI - Optional Video Sync (Raspberry Pi -> Platform API).
-------------------------------------------------------------------
The vision service's canonical output is MQTT telemetry (see main.py); this module adds a
best-effort, OPT-IN side channel that also uploads short annotated video clips of what the
camera is seeing to the platform's API over HTTP, reusing the exact artifact path the API
already serves from `GET /api/v1/vision/demo-video` (see `_vision_artifact_paths` in
services/api/main.py). It never touches MQTT or the telemetry contract -- disabling it
(VIDEO_SYNC_ENABLED=false, the default) leaves the perception loop exactly as it was.

Uploading runs on its own background thread so a slow/offline network never blocks camera
capture; if uploads fall behind, the oldest pending clip is dropped rather than growing memory
or local disk without bound.
"""

import logging
import queue
import tempfile
import threading
import time
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

import cv2
import numpy as np

logger = logging.getLogger("vision-video-sync")


def draw_sync_overlay(frame: np.ndarray, rois: Dict[str, Dict[str, Any]],
                      assigned_boxes: Dict[str, List[Tuple[int, int, int, int]]],
                      node_id: str, timestamp_ms: int) -> np.ndarray:
    """Lightweight HUD (ROI polygons + detection boxes + node/time label) for the synced clip --
    intentionally much simpler than demo_video_pipeline.py's offline annotator, since this runs
    every frame on Pi-class hardware alongside the real-time detection loop."""
    canvas = frame.copy()
    for approach_id, roi in rois.items():
        polygon = roi.get("polygon")
        if polygon is not None:
            cv2.polylines(canvas, [polygon], True, (56, 189, 248), 1)
    for boxes in assigned_boxes.values():
        for (x, y, w, h) in boxes:
            cv2.rectangle(canvas, (x, y), (x + w, y + h), (34, 197, 94), 2)
    label = f"{node_id} | RPi5 Edge Vision | {time.strftime('%H:%M:%S', time.localtime(timestamp_ms / 1000))}"
    cv2.putText(canvas, label, (8, 20), cv2.FONT_HERSHEY_SIMPLEX, 0.5, (255, 255, 255), 1, cv2.LINE_AA)
    return canvas


class VideoSyncUploader:
    """Buffers annotated frames into short local .mp4 clips and uploads each finished clip to
    the platform API as soon as it closes. One instance per (node_id, topology_id)."""

    def __init__(self, api_base_url: str, node_id: str, topology_id: str,
                 width: int, height: int, fps: float = 10.0, clip_period_s: float = 10.0):
        self.api_base_url = api_base_url.rstrip("/")
        self.node_id = node_id
        self.topology_id = topology_id
        self.width = width
        self.height = height
        self.fps = max(1.0, fps)
        self.clip_period_s = clip_period_s

        self._writer: Optional[cv2.VideoWriter] = None
        self._clip_path: Optional[Path] = None
        self._clip_started = 0.0
        self._tmp_dir = Path(tempfile.gettempdir()) / "edgeflow_video_sync"
        self._tmp_dir.mkdir(parents=True, exist_ok=True)

        # maxsize=2: one clip allowed to sit queued behind the one currently uploading; a third
        # arrival means the network truly can't keep up, so the oldest queued clip is dropped.
        self._upload_queue: "queue.Queue[Path]" = queue.Queue(maxsize=2)
        self._stop = threading.Event()
        self._thread = threading.Thread(target=self._upload_worker, daemon=True, name="video-sync-upload")
        self._thread.start()

    def add_frame(self, frame: np.ndarray) -> None:
        """Call once per processed frame; rotates to a new clip file every clip_period_s."""
        now = time.monotonic()
        if self._writer is None or (now - self._clip_started) >= self.clip_period_s:
            self._rotate_clip(now)
        if self._writer is not None:
            self._writer.write(frame)

    def _rotate_clip(self, now: float) -> None:
        self._finish_clip()
        self._clip_path = self._tmp_dir / f"{self.node_id}_{int(now * 1000)}.mp4"
        fourcc = cv2.VideoWriter_fourcc(*"mp4v")
        self._writer = cv2.VideoWriter(str(self._clip_path), fourcc, self.fps, (self.width, self.height))
        self._clip_started = now

    def _finish_clip(self) -> None:
        if self._writer is None:
            return
        self._writer.release()
        self._writer = None
        clip_path, self._clip_path = self._clip_path, None
        if not (clip_path and clip_path.is_file() and clip_path.stat().st_size > 0):
            return
        try:
            self._upload_queue.put_nowait(clip_path)
        except queue.Full:
            try:
                stale = self._upload_queue.get_nowait()
                stale.unlink(missing_ok=True)
            except queue.Empty:
                pass
            try:
                self._upload_queue.put_nowait(clip_path)
            except queue.Full:
                clip_path.unlink(missing_ok=True)

    def _upload_worker(self) -> None:
        while not self._stop.is_set():
            try:
                clip_path = self._upload_queue.get(timeout=1.0)
            except queue.Empty:
                continue
            try:
                self._upload_one(clip_path)
            except Exception as e:
                logger.warning(f"Video sync upload error for {clip_path.name}: {e}")
            finally:
                clip_path.unlink(missing_ok=True)

    def _upload_one(self, clip_path: Path) -> None:
        import requests
        url = f"{self.api_base_url}/api/v1/vision/video-upload"
        params = {"node_id": self.node_id, "topology_id": self.topology_id}
        with open(clip_path, "rb") as f:
            resp = requests.post(url, params=params, files={"file": (clip_path.name, f, "video/mp4")}, timeout=15)
        if resp.status_code == 200:
            logger.info(f"Video clip synced to platform: {clip_path.name} "
                       f"({clip_path.stat().st_size // 1024} KB) -> {url}")
        else:
            logger.warning(f"Video sync upload rejected ({resp.status_code}): {resp.text[:200]}")

    def close(self) -> None:
        self._finish_clip()
        self._stop.set()
        self._thread.join(timeout=2.0)
