"""
Signal phase each ESP32 actually shows, read from its health topic (O7).

Telemetry carries current_phase_id, and the EdgeFlow controller uses it for elapsed green and the
service-age fairness bonus. A fixed phases[0] makes that controller believe one phase is always
green and inverts its priorities, so vision reports the phase the device last announced on
edgeflow/v1/health/{node}. Only while that report is missing, stale or OFFLINE does it fall back
to the topology's first phase, flagged "default" so the health topic shows it is not observed.
"""

import json
import threading
import time
from typing import Callable, Dict, Iterable, List, Tuple

HEALTH_TOPIC_FMT = "edgeflow/v1/health/{node_id}"
# The firmware publishes health every 5 s and on each switch to GREEN: three missed reports = unknown
PHASE_STALE_S = 15.0
SOURCE_DEVICE = "esp32_health"
SOURCE_DEFAULT = "default"


class PhaseTracker:
    """Thread-safe: update() runs on the MQTT thread, current() on the main loop."""

    def __init__(self, nodes: Iterable[Dict], stale_after_s: float = PHASE_STALE_S,
                 clock: Callable[[], float] = time.monotonic):
        self._phases: Dict[str, List[str]] = {
            n["node_id"]: [p["phase_id"] for p in n.get("phases", [])] for n in nodes}
        self._node_by_topic = {HEALTH_TOPIC_FMT.format(node_id=n): n for n in self._phases}
        self._stale_after_s = stale_after_s
        self._clock = clock
        self._lock = threading.Lock()
        self._latest: Dict[str, Tuple[str, float]] = {}

    @property
    def topics(self) -> List[str]:
        return list(self._node_by_topic)

    def update(self, topic: str, payload: bytes) -> bool:
        """Record one device health message; foreign or malformed ones are ignored (False)."""
        node_id = self._node_by_topic.get(topic)
        if node_id is None:
            return False
        try:
            message = json.loads(payload)
        except ValueError:  # includes undecodable bytes
            return False
        if not isinstance(message, dict) or message.get("node_id") != node_id:
            return False
        if message.get("status") == "OFFLINE":  # the device's LWT: whatever it showed is unknown now
            with self._lock:
                self._latest.pop(node_id, None)
            return True
        phase = message.get("current_phase")
        if phase not in self._phases[node_id]:
            return False
        with self._lock:
            self._latest[node_id] = (phase, self._clock())
        return True

    def current(self, node_id: str) -> Tuple[str, str]:
        """(phase_id, source): the fresh device report, else the first topology phase as "default"."""
        with self._lock:
            latest = self._latest.get(node_id)
        if latest is not None and self._clock() - latest[1] <= self._stale_after_s:
            return latest[0], SOURCE_DEVICE
        phases = self._phases.get(node_id) or [f"{node_id}_PHASE_NS"]
        return phases[0], SOURCE_DEFAULT
