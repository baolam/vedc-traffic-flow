"""
EdgeFlow AI - measured runtime figures for the vision health topic.

Revised Plan (2) asks to measure capture, preprocessing, inference and publishing separately
on the Pi. Everything reported here comes from frames the service actually processed; no
configured or assumed value (such as 1 / TELEMETRY_PERIOD_S) is passed off as a measurement.
"""

import time
from collections import deque
from typing import Any, Callable, Deque, Dict, List, Optional, Tuple

import numpy as np


def percentiles(values: List[float]) -> Dict[str, float]:
    return {"p50": round(float(np.percentile(values, 50)), 1),
            "p95": round(float(np.percentile(values, 95)), 1)}


class RuntimeStats:
    """Rolling window of processed frames: real FPS, stage latency p50/p95 and camera failures."""

    def __init__(self, window_s: float = 30.0, clock: Callable[[], float] = time.monotonic):
        if window_s <= 0:
            raise ValueError("window_s must be positive")
        self.window_s = window_s
        self.clock = clock
        self.started = clock()
        self.frames: Deque[Tuple[float, bool, Dict[str, float]]] = deque()
        self.publishes: Deque[Tuple[float, Dict[str, float]]] = deque()
        self.consecutive_failures = 0
        self.total_frames = 0
        self.total_failures = 0

    def record(self, ok: bool, timings: Optional[Dict[str, float]] = None) -> None:
        """One loop iteration: ok=False when the camera delivered no frame."""
        now = self.clock()
        self.frames.append((now, ok, dict(timings or {})))
        self.total_frames += 1
        if ok:
            self.consecutive_failures = 0
        else:
            self.total_failures += 1
            self.consecutive_failures += 1
        self._trim(now)

    def record_publish(self, timings: Dict[str, float]) -> None:
        """One telemetry publish: publish_ms, age_at_publish_ms, frames_per_publish."""
        now = self.clock()
        self.publishes.append((now, dict(timings)))
        self._trim(now)

    def _trim(self, now: float) -> None:
        while self.frames and now - self.frames[0][0] > self.window_s:
            self.frames.popleft()
        while self.publishes and now - self.publishes[0][0] > self.window_s:
            self.publishes.popleft()

    def snapshot(self) -> Dict[str, Any]:
        now = self.clock()
        self._trim(now)
        span = min(self.window_s, now - self.started)
        good_times = [t for t, ok, _ in self.frames if ok]
        good = [timings for _, ok, timings in self.frames if ok]
        events = good + [timings for _, timings in self.publishes]
        latency: Dict[str, Dict[str, float]] = {}
        for key in sorted({k for timings in events for k in timings}):
            latency[key] = percentiles([t[key] for t in events if key in t])
        # Rate between processed frames; one frame (e.g. right after start) gives no rate at all.
        elapsed = good_times[-1] - good_times[0] if len(good_times) >= 2 else 0.0
        return {
            "window_s": round(span, 1),
            "frames_ok": len(good),
            "frames_failed": len(self.frames) - len(good),
            "processed_fps": round((len(good_times) - 1) / elapsed, 2) if elapsed > 0 else None,
            "consecutive_failures": self.consecutive_failures,
            "total_frames": self.total_frames,
            "total_failures": self.total_failures,
            "latency_ms": latency,
        }
