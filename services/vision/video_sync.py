"""
EdgeFlow AI - Live Video Stream Push (Raspberry Pi -> Platform API).
-------------------------------------------------------------------
The vision service's canonical output is MQTT telemetry (see main.py); this module adds a
best-effort, OPT-IN side channel that also pushes the camera's annotated frames to the
platform's API over plain HTTP, one JPEG per frame, so the dashboard can show a genuine live
view (GET /api/v1/vision/live-stream/{node_id}, an MJPEG multipart stream the API re-serves
from whatever frame arrived last). It never touches MQTT or the telemetry contract -- disabling
it (VIDEO_SYNC_ENABLED=false, the default) leaves the perception loop exactly as it was.

Pushing runs on its own background thread with a 1-slot queue: a newer frame always replaces an
older unsent one (never queues up a backlog), so a slow/offline network only ever costs
freshness, never memory, and never blocks camera capture.
"""

import logging
import queue
import threading
import time
from typing import Any, Dict, List, Tuple

import cv2
import numpy as np

logger = logging.getLogger("vision-video-sync")


def draw_sync_overlay(frame: np.ndarray, rois: Dict[str, Dict[str, Any]],
                      assigned_boxes: Dict[str, List[Tuple[int, int, int, int]]],
                      node_id: str, timestamp_ms: int) -> np.ndarray:
    """Lightweight HUD (ROI polygons + detection boxes + node/time label) for the streamed frame --
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


class LiveStreamPusher:
    """JPEG-encodes each frame handed to it and pushes it to the platform API's live-frame
    endpoint. One instance per node_id. Frame rate to the API is capped by max_fps regardless
    of how often push_frame() is called (extra frames are simply dropped, not queued)."""

    def __init__(self, api_base_url: str, node_id: str, max_fps: float = 10.0, jpeg_quality: int = 70):
        self.api_base_url = api_base_url.rstrip("/")
        self.node_id = node_id
        self.min_interval_s = 1.0 / max(0.1, max_fps)
        self.jpeg_quality = jpeg_quality

        self._last_push_s = 0.0
        # maxsize=1: at most one frame ever waits for the network; a frame that arrives while
        # one is already queued replaces it, so the stream always pushes its FRESHEST frame.
        self._queue: "queue.Queue[bytes]" = queue.Queue(maxsize=1)
        self._stop = threading.Event()
        self._thread = threading.Thread(target=self._push_worker, daemon=True, name="video-live-stream")
        self._thread.start()

    def push_frame(self, frame: np.ndarray) -> None:
        """Call once per processed frame; silently rate-limits to max_fps and drops frames
        the network hasn't caught up with yet."""
        now = time.monotonic()
        if (now - self._last_push_s) < self.min_interval_s:
            return
        self._last_push_s = now
        ok, buf = cv2.imencode(".jpg", frame, [cv2.IMWRITE_JPEG_QUALITY, self.jpeg_quality])
        if not ok:
            return
        jpeg_bytes = buf.tobytes()
        try:
            self._queue.put_nowait(jpeg_bytes)
        except queue.Full:
            try:
                self._queue.get_nowait()
            except queue.Empty:
                pass
            try:
                self._queue.put_nowait(jpeg_bytes)
            except queue.Full:
                pass

    def _push_worker(self) -> None:
        try:
            import requests
        except ImportError:
            logger.error("Live video stream disabled: 'requests' is not installed in this "
                        "environment. Run: pip install -r services/vision/requirements.txt")
            return
        url = f"{self.api_base_url}/api/v1/vision/live-frame"
        params = {"node_id": self.node_id}
        consecutive_failures = 0
        while not self._stop.is_set():
            try:
                jpeg_bytes = self._queue.get(timeout=1.0)
            except queue.Empty:
                continue
            try:
                resp = requests.post(url, params=params, data=jpeg_bytes,
                                     headers={"Content-Type": "image/jpeg"}, timeout=2)
                if resp.status_code == 200:
                    if consecutive_failures > 0:
                        logger.info(f"Live frame push to {url} recovered after {consecutive_failures} failures")
                    consecutive_failures = 0
                else:
                    logger.warning(f"Live frame push rejected ({resp.status_code}): {resp.text[:200]}")
            except Exception as e:
                # WARNING (not debug): a network/connectivity problem here is silent otherwise --
                # the perception loop keeps running fine, so nothing else would ever surface it.
                # Logged on the 1st failure and every 20th after, to stay readable at ~2-10 fps.
                consecutive_failures += 1
                if consecutive_failures == 1 or consecutive_failures % 20 == 0:
                    logger.warning(f"Live frame push to {url} failed ({consecutive_failures} in a row): {e}")

    def close(self) -> None:
        self._stop.set()
        self._thread.join(timeout=2.0)
