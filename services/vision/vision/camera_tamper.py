"""
EdgeFlow AI - Camera Tampering, Occlusion & Blindness Detection System.
------------------------------------------------------------------------
Detects when the camera sensor or optical field of view is obstructed, covered,
tampered with, or blinded:
1. Full-frame Tampering:
   - Blackout / Covered lens (near-zero brightness or flat dark signal).
   - Glare / Blinded by high-intensity light (extreme overexposure/saturation).
   - Full Obstruction (cardboard, paper, hand, tape covering lens: near-zero edge density & low texture variance).
2. Per-ROI Occlusion / Blindness:
   - Individual approach traffic ROIs covered or blinded (no visible road texture/markings).
3. Temporal Debounce & State Machine:
   - Prevents transient false alarms (e.g., sudden headlight flashes, large shadows, momentary bus occlusions)
     by requiring an anomaly to persist for >= min_duration_s before confirming an ACTIVE alert.
   - Requires clear visibility to persist for >= restore_duration_s before resolving the alert.
   - Emits structured alert events compatible with EdgeFlow canonical SignalFaultEvent contracts.
"""

import time
import uuid
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional, Set, Tuple

import cv2
import numpy as np

from .roi_visibility import RoiVisibility

CANNY_LOW, CANNY_HIGH = 50, 150


@dataclass
class CameraAlert:
    """Represents an active or resolved camera tampering/occlusion alert."""
    alert_id: str
    node_id: str
    tamper_type: str  # "full_occlusion", "blackout", "glare", "roi_blind", "all_approaches_blind"
    severity: str     # "CRITICAL", "WARNING", "INFO"
    reason: str
    status: str       # "ACTIVE", "RESOLVED"
    blind_approaches: List[str] = field(default_factory=list)
    details: Dict[str, Any] = field(default_factory=dict)
    first_detected_at: float = 0.0
    last_seen_at: float = 0.0
    resolved_at: Optional[float] = None
    confirmed: bool = False
    reported_to_mqtt: bool = False

    def to_dict(self) -> Dict[str, Any]:
        return {
            "alert_id": self.alert_id,
            "node_id": self.node_id,
            "tamper_type": self.tamper_type,
            "severity": self.severity,
            "reason": self.reason,
            "status": self.status,
            "blind_approaches": list(self.blind_approaches),
            "details": dict(self.details),
            "first_detected_at": self.first_detected_at,
            "last_seen_at": self.last_seen_at,
            "resolved_at": self.resolved_at,
            "confirmed": self.confirmed,
            "timestamp_ms": int((self.resolved_at or self.last_seen_at) * 1000),
        }

    def to_signal_fault_event(self, current_phase: Optional[str] = None) -> Dict[str, Any]:
        """Convert to canonical EdgeFlow SignalFaultEvent payload with specialized camera fault codes."""
        now_ms = int(time.time() * 1000)
        # Dedicated camera fault codes:
        # ERR_CAMERA_BLIND: Glare overexposure, blackout, or heavy defocus
        # ERR_CAMERA_OCCLUSION: Physical lens obstruction, cardboard/hand/tape, or approach ROI blind
        if self.tamper_type in ("glare", "blackout", "blur"):
            fault_code = "ERR_CAMERA_BLIND"
        else:
            fault_code = "ERR_CAMERA_OCCLUSION"

        return {
            "event_id": f"flt-{self.alert_id}",
            "node_id": self.node_id,
            "category": "camera",
            "fault_code": fault_code,
            "severity": self.severity,
            "current_phase": current_phase,
            "target_phase": None,
            "clearance_state": "GREEN",
            "reason": self.reason,
            "details": {
                "alert_id": self.alert_id,
                "tamper_type": self.tamper_type,
                "status": self.status,
                "blind_approaches": self.blind_approaches,
                **self.details,
            },
            "timestamp_ms": now_ms,
        }


class CameraTamperDetector:
    """
    Real-time vision tamper, occlusion and blindness detector with debounced alert state machine.
    """

    def __init__(
        self,
        enabled: bool = True,
        min_edge_ratio: float = 0.01,
        full_occlusion_edge_ratio: float = 0.004,
        dark_threshold: float = 12.0,
        glare_threshold: float = 245.0,
        blur_threshold: float = 15.0,
        min_duration_s: float = 2.0,
        restore_duration_s: float = 1.5,
    ):
        self.enabled = enabled
        self.min_edge_ratio = min_edge_ratio
        self.full_occlusion_edge_ratio = full_occlusion_edge_ratio
        self.dark_threshold = dark_threshold
        self.glare_threshold = glare_threshold
        self.blur_threshold = blur_threshold
        self.min_duration_s = min_duration_s
        self.restore_duration_s = restore_duration_s

        self.roi_visibility = RoiVisibility(min_edge_ratio=min_edge_ratio)

        # Track active alerts: alert_key -> CameraAlert
        # alert_key format: "{node_id}:{tamper_type}:{approaches_key}"
        self._alerts: Dict[str, CameraAlert] = {}
        # Track when candidate conditions began clearing: alert_key -> clear_start_s
        self._clearing_since: Dict[str, float] = {}

    def analyze(
        self,
        frame: Optional[np.ndarray],
        rois: Dict[str, Dict[str, Any]],
        node_ids: List[str],
        approaches_by_node: Dict[str, List[str]],
        now_s: Optional[float] = None,
    ) -> Tuple[List[CameraAlert], List[CameraAlert], Dict[str, Any]]:
        """
        Analyzes the current frame for tampering or occlusion.

        Returns:
            active_alerts: All currently confirmed active alerts.
            new_events: Alerts that just transitioned to confirmed ACTIVE or RESOLVED (for publishing).
            diagnostics: Frame metrics (mean brightness, edge ratio, blind approaches, etc.).
        """
        if now_s is None:
            now_s = time.time()

        if not self.enabled or frame is None or frame.size == 0:
            return [], [], {"enabled": self.enabled, "frame_available": frame is not None}

        gray = frame if frame.ndim == 2 else cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
        h, w = gray.shape[:2]
        total_pixels = float(h * w)

        # Compute full-frame image statistics
        mean_brightness = float(np.mean(gray))
        std_brightness = float(np.std(gray))
        laplacian_var = float(cv2.Laplacian(gray, cv2.CV_64F).var()) if total_pixels > 0 else 0.0

        edges = cv2.Canny(gray, CANNY_LOW, CANNY_HIGH)
        edge_pixel_count = int(np.count_nonzero(edges))
        edge_ratio = float(edge_pixel_count) / total_pixels if total_pixels > 0 else 0.0

        # Compute per-ROI approach blindness
        blind_approaches = self.roi_visibility.blind_approaches(frame, rois) if rois else set()

        diagnostics = {
            "mean_brightness": round(mean_brightness, 2),
            "std_brightness": round(std_brightness, 2),
            "laplacian_var": round(laplacian_var, 2),
            "edge_ratio": round(edge_ratio, 5),
            "blind_approaches": sorted(list(blind_approaches)),
        }

        # Identify candidate conditions in the current frame
        detected_candidates: Dict[str, Dict[str, Any]] = {}

        # 1. Check Full-Frame Blackout
        if mean_brightness < self.dark_threshold:
            for node_id in node_ids:
                key = f"{node_id}:blackout:all"
                detected_candidates[key] = {
                    "node_id": node_id,
                    "tamper_type": "blackout",
                    "severity": "CRITICAL",
                    "reason": f"Camera blackout detected: mean brightness {mean_brightness:.1f} < threshold {self.dark_threshold:.1f}",
                    "blind_approaches": approaches_by_node.get(node_id, []),
                    "details": diagnostics,
                }

        # 2. Check Full-Frame Glare
        elif mean_brightness > self.glare_threshold:
            for node_id in node_ids:
                key = f"{node_id}:glare:all"
                detected_candidates[key] = {
                    "node_id": node_id,
                    "tamper_type": "glare",
                    "severity": "CRITICAL",
                    "reason": f"Camera glare/overexposure detected: mean brightness {mean_brightness:.1f} > threshold {self.glare_threshold:.1f}",
                    "blind_approaches": approaches_by_node.get(node_id, []),
                    "details": diagnostics,
                }

        # 3. Check Full-Frame Lens Occlusion (flat cardboard, tape, or severe defocus)
        elif edge_ratio < self.full_occlusion_edge_ratio and laplacian_var < self.blur_threshold and std_brightness < 25.0:
            for node_id in node_ids:
                key = f"{node_id}:full_occlusion:all"
                detected_candidates[key] = {
                    "node_id": node_id,
                    "tamper_type": "full_occlusion",
                    "severity": "CRITICAL",
                    "reason": (
                        f"Camera lens completely obstructed or covered: edge ratio {edge_ratio:.4f} < {self.full_occlusion_edge_ratio:.4f}, "
                        f"blur variance {laplacian_var:.1f}"
                    ),
                    "blind_approaches": approaches_by_node.get(node_id, []),
                    "details": diagnostics,
                }

        # 4. Check Per-Node ROI Approach Blindness (if not already full-frame occluded)
        if not detected_candidates:
            for node_id in node_ids:
                node_apps = approaches_by_node.get(node_id, [])
                if not node_apps:
                    continue
                node_blind = [app for app in node_apps if app in blind_approaches]
                if not node_blind:
                    continue

                if len(node_blind) == len(node_apps):
                    key = f"{node_id}:all_approaches_blind:all"
                    detected_candidates[key] = {
                        "node_id": node_id,
                        "tamper_type": "all_approaches_blind",
                        "severity": "CRITICAL",
                        "reason": f"All approach ROIs for node {node_id} are blinded or occluded: {', '.join(node_blind)}",
                        "blind_approaches": node_blind,
                        "details": diagnostics,
                    }
                else:
                    apps_key = "_".join(sorted(node_blind))
                    key = f"{node_id}:roi_blind:{apps_key}"
                    detected_candidates[key] = {
                        "node_id": node_id,
                        "tamper_type": "roi_blind",
                        "severity": "WARNING",
                        "reason": f"Approach ROI(s) for node {node_id} occluded or showing no texture: {', '.join(node_blind)}",
                        "blind_approaches": node_blind,
                        "details": diagnostics,
                    }

        # Update Alert State Machine with Debouncing
        new_events: List[CameraAlert] = []

        # A. Process newly seen or continuing candidate conditions
        for key, cand in detected_candidates.items():
            # If it was marked as clearing, cancel clearing
            self._clearing_since.pop(key, None)

            if key not in self._alerts:
                # Fresh candidate anomaly
                alert_id = f"cam-{uuid.uuid4().hex[:8]}"
                self._alerts[key] = CameraAlert(
                    alert_id=alert_id,
                    node_id=cand["node_id"],
                    tamper_type=cand["tamper_type"],
                    severity=cand["severity"],
                    reason=cand["reason"],
                    status="ACTIVE",
                    blind_approaches=cand["blind_approaches"],
                    details=cand["details"],
                    first_detected_at=now_s,
                    last_seen_at=now_s,
                    confirmed=False,
                    reported_to_mqtt=False,
                )
            else:
                alert = self._alerts[key]
                alert.last_seen_at = now_s
                alert.details = cand["details"]
                alert.reason = cand["reason"]

            alert = self._alerts[key]
            # Check if duration meets debounce requirement
            duration = now_s - alert.first_detected_at
            if duration >= self.min_duration_s and not alert.confirmed:
                alert.confirmed = True
                new_events.append(alert)

        # B. Process alerts that are no longer detected in this frame
        keys_to_remove: List[str] = []
        for key, alert in list(self._alerts.items()):
            if key not in detected_candidates:
                if key not in self._clearing_since:
                    self._clearing_since[key] = now_s

                clearing_duration = now_s - self._clearing_since[key]
                if clearing_duration >= self.restore_duration_s:
                    if alert.confirmed:
                        # Alert had been confirmed, so emit a resolution event
                        alert.status = "RESOLVED"
                        alert.resolved_at = now_s
                        alert.reason = f"Camera tamper condition resolved: {alert.tamper_type} cleared"
                        new_events.append(alert)
                    keys_to_remove.append(key)

        for key in keys_to_remove:
            self._alerts.pop(key, None)
            self._clearing_since.pop(key, None)

        confirmed_active = [a for a in self._alerts.values() if a.confirmed and a.status == "ACTIVE"]
        return confirmed_active, new_events, diagnostics
