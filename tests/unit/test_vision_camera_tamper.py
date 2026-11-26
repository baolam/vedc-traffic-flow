"""
Unit tests for Camera Tampering, Occlusion, Blindness Detection and Alerts System.
"""

import time
import pytest
import numpy as np
import cv2

from contracts import contracts_sdk, topics
from services.vision.vision.camera_tamper import CameraTamperDetector, CameraAlert
from services.vision.streaming.live_stream import draw_sync_overlay
from services.vision.local_dashboard.db import VisionLocalDB
from services.vision.connectivity.mqtt_gateway import MqttGateway


ROIS = {
    "J1_N_IN": {"polygon": np.array([[10, 10], [90, 10], [90, 60], [10, 60]], np.int32)},
    "J1_S_IN": {"polygon": np.array([[110, 10], [190, 10], [190, 60], [110, 60]], np.int32)},
}
NODE_IDS = ["J1"]
APPROACHES_BY_NODE = {"J1": ["J1_N_IN", "J1_S_IN"]}


def _road_frame() -> np.ndarray:
    """Frame with road and high-contrast white lane markings (healthy camera view)."""
    frame = np.full((120, 240, 3), 90, np.uint8)
    for x0 in range(15, 220, 20):
        frame[30:35, x0:x0 + 10] = 250
        frame[70:75, x0:x0 + 10] = 250
    return frame


def test_tamper_detector_healthy_frame():
    """A clear frame with road texture produces no alerts."""
    detector = CameraTamperDetector(min_duration_s=1.0)
    frame = _road_frame()
    active, new_evs, diag = detector.analyze(frame, ROIS, NODE_IDS, APPROACHES_BY_NODE, now_s=100.0)
    assert len(active) == 0
    assert len(new_evs) == 0
    assert len(diag["blind_approaches"]) == 0


def test_tamper_detector_blackout_debounce():
    """Blackout (e.g. lens covered completely) triggers CRITICAL alert after min_duration_s."""
    detector = CameraTamperDetector(min_duration_s=2.0, dark_threshold=15.0)
    black_frame = np.zeros((120, 240, 3), np.uint8)

    # Turn 1: t = 100.0 (first seen, not confirmed yet)
    active, new_evs, _ = detector.analyze(black_frame, ROIS, NODE_IDS, APPROACHES_BY_NODE, now_s=100.0)
    assert len(active) == 0
    assert len(new_evs) == 0

    # Turn 2: t = 101.0 (< 2.0s, still pending)
    active, new_evs, _ = detector.analyze(black_frame, ROIS, NODE_IDS, APPROACHES_BY_NODE, now_s=101.0)
    assert len(active) == 0
    assert len(new_evs) == 0

    # Turn 3: t = 102.5 (>= 2.0s, confirmed active alert)
    active, new_evs, _ = detector.analyze(black_frame, ROIS, NODE_IDS, APPROACHES_BY_NODE, now_s=102.5)
    assert len(active) == 1
    assert len(new_evs) == 1
    alert = active[0]
    assert alert.tamper_type == "blackout"
    assert alert.severity == "CRITICAL"
    assert alert.confirmed is True


def test_tamper_detector_glare():
    """Extreme glare / overexposure triggers glare alert."""
    detector = CameraTamperDetector(min_duration_s=1.0, glare_threshold=240.0)
    glare_frame = np.full((120, 240, 3), 252, np.uint8)

    detector.analyze(glare_frame, ROIS, NODE_IDS, APPROACHES_BY_NODE, now_s=100.0)
    active, new_evs, _ = detector.analyze(glare_frame, ROIS, NODE_IDS, APPROACHES_BY_NODE, now_s=101.5)
    assert len(active) == 1
    assert active[0].tamper_type == "glare"
    assert active[0].severity == "CRITICAL"


def test_tamper_detector_full_occlusion_cardboard():
    """Flat uniform cardboard or tape covering lens triggers full_occlusion."""
    detector = CameraTamperDetector(min_duration_s=1.0, full_occlusion_edge_ratio=0.005)
    # Uniform grey flat surface with no edges
    cardboard = np.full((120, 240, 3), 128, np.uint8)

    detector.analyze(cardboard, ROIS, NODE_IDS, APPROACHES_BY_NODE, now_s=100.0)
    active, new_evs, _ = detector.analyze(cardboard, ROIS, NODE_IDS, APPROACHES_BY_NODE, now_s=101.5)
    assert len(active) == 1
    assert active[0].tamper_type in ("full_occlusion", "all_approaches_blind")
    assert active[0].severity == "CRITICAL"


def test_tamper_detector_single_roi_blind():
    """Covering only one approach ROI triggers a WARNING alert."""
    detector = CameraTamperDetector(min_duration_s=1.0)
    frame = _road_frame()
    # Cover only J1_N_IN with flat color
    frame[5:65, 5:95] = (180, 180, 180)

    detector.analyze(frame, ROIS, NODE_IDS, APPROACHES_BY_NODE, now_s=100.0)
    active, new_evs, _ = detector.analyze(frame, ROIS, NODE_IDS, APPROACHES_BY_NODE, now_s=101.5)
    assert len(active) == 1
    assert active[0].tamper_type == "roi_blind"
    assert active[0].severity == "WARNING"
    assert "J1_N_IN" in active[0].blind_approaches
    assert "J1_S_IN" not in active[0].blind_approaches


def test_tamper_detector_recovery_resolution():
    """When view clears up, alert resolves after restore_duration_s."""
    detector = CameraTamperDetector(min_duration_s=1.0, restore_duration_s=1.0)
    black_frame = np.zeros((120, 240, 3), np.uint8)
    road = _road_frame()

    # Trigger and confirm
    detector.analyze(black_frame, ROIS, NODE_IDS, APPROACHES_BY_NODE, now_s=100.0)
    active, _, _ = detector.analyze(black_frame, ROIS, NODE_IDS, APPROACHES_BY_NODE, now_s=101.5)
    assert len(active) == 1

    # Camera clears up
    detector.analyze(road, ROIS, NODE_IDS, APPROACHES_BY_NODE, now_s=102.0)
    # Still clearing, within restore_duration_s
    active, new_evs, _ = detector.analyze(road, ROIS, NODE_IDS, APPROACHES_BY_NODE, now_s=102.5)
    assert len(active) == 1
    assert len(new_evs) == 0

    # Passed restore_duration_s (103.5 - 102.0 = 1.5s >= 1.0s)
    active, new_evs, _ = detector.analyze(road, ROIS, NODE_IDS, APPROACHES_BY_NODE, now_s=103.5)
    assert len(active) == 0
    assert len(new_evs) == 1
    assert new_evs[0].status == "RESOLVED"


def test_canonical_signal_fault_event_schema_compliance():
    """Alert event payload must pass canonical contracts_sdk validation for signal_fault_event."""
    alert = CameraAlert(
        alert_id="test-123",
        node_id="J1",
        tamper_type="full_occlusion",
        severity="CRITICAL",
        reason="Camera lens obstructed: low edge ratio",
        status="ACTIVE",
        blind_approaches=["J1_N_IN", "J1_S_IN"],
        details={"mean_brightness": 10.5, "edge_ratio": 0.001},
        first_detected_at=100.0,
        last_seen_at=102.0,
        confirmed=True,
    )
    payload = alert.to_signal_fault_event(current_phase="J1_PHASE_NS")
    contracts_sdk.validate_payload(payload, "signal_fault_event")
    assert payload["category"] == "camera"
    assert payload["fault_code"] == "ERR_CAMERA_OCCLUSION"
    assert payload["severity"] == "CRITICAL"
    assert payload["node_id"] == "J1"


def test_local_db_alert_storage(tmp_path):
    """VisionLocalDB records and queries camera alerts."""
    db_file = tmp_path / "test_vision.db"
    db = VisionLocalDB(db_path=str(db_file))

    alert_dict = {
        "alert_id": "alert-abc",
        "node_id": "J1",
        "severity": "CRITICAL",
        "tamper_type": "blackout",
        "status": "ACTIVE",
        "reason": "Camera covered",
        "details": {"brightness": 2.0},
        "timestamp_ms": int(time.time() * 1000),
    }
    db.record_alert(alert_dict)
    # Allow background queue worker to persist
    time.sleep(0.3)

    records = db.query_alerts(node_id="J1")
    assert len(records) >= 1
    assert records[0]["alert_id"] == "alert-abc"
    assert records[0]["tamper_type"] == "blackout"
    assert records[0]["details"]["brightness"] == 2.0
    db.close()


def test_draw_sync_overlay_with_alerts():
    """HUD overlay draws warning ribbon and red border for blind ROI."""
    frame = _road_frame()
    active_alerts = [{
        "alert_id": "a1",
        "tamper_type": "full_occlusion",
        "severity": "CRITICAL",
        "reason": "Lens blocked",
    }]
    annotated = draw_sync_overlay(
        frame=frame,
        rois=ROIS,
        assigned_boxes={"J1_N_IN": [(20, 20, 30, 25)]},
        node_id="J1",
        timestamp_ms=1700000000000,
        blind_approaches={"J1_N_IN"},
        active_alerts=active_alerts,
    )
    assert annotated.shape == frame.shape
    # Check that canvas was modified (HUD banner drawn in red)
    # The banner occupies (0, 0) to (canvas.shape[1], 24)
    assert annotated[10, 10, 2] > 150  # Red channel is high in BGR format


def test_occlusion_simulation_modes_and_detection():
    """PerceptionEngine occlusion simulation modes trigger corresponding tamper alerts."""
    from services.vision.vision.engine import PerceptionEngine

    # Create dummy engine instance with mocked detector/sources
    class DummyDetector:
        last_timings = {}
        def detect(self, f):
            return [], []

    class DummyVideoSource:
        def read_frame(self):
            return True, _road_frame()
        def release(self):
            pass

    engine = PerceptionEngine(
        video_source_str="synthetic",
        width=240,
        height=120,
    )
    engine.video_source = DummyVideoSource()
    engine.detector = DummyDetector()
    engine.setup_nodes(NODE_IDS)
    engine.roi_manager.rois = ROIS

    base_frame = _road_frame()
    detector = CameraTamperDetector(min_duration_s=1.0)

    # 1. Full Occlusion Simulation
    engine.occlusion_mode = "full_occlusion"
    sim_full = engine._apply_occlusion_simulation(base_frame)
    detector.analyze(sim_full, ROIS, NODE_IDS, APPROACHES_BY_NODE, now_s=100.0)
    active, _, _ = detector.analyze(sim_full, ROIS, NODE_IDS, APPROACHES_BY_NODE, now_s=101.5)
    assert len(active) == 1
    assert active[0].tamper_type in ("full_occlusion", "all_approaches_blind")

    # 2. Blackout Simulation
    detector = CameraTamperDetector(min_duration_s=1.0)
    engine.occlusion_mode = "blackout"
    sim_black = engine._apply_occlusion_simulation(base_frame)
    detector.analyze(sim_black, ROIS, NODE_IDS, APPROACHES_BY_NODE, now_s=100.0)
    active, _, _ = detector.analyze(sim_black, ROIS, NODE_IDS, APPROACHES_BY_NODE, now_s=101.5)
    assert len(active) == 1
    assert active[0].tamper_type == "blackout"

    # 3. Glare Simulation
    detector = CameraTamperDetector(min_duration_s=1.0)
    engine.occlusion_mode = "glare"
    sim_glare = engine._apply_occlusion_simulation(base_frame)
    detector.analyze(sim_glare, ROIS, NODE_IDS, APPROACHES_BY_NODE, now_s=100.0)
    active, _, _ = detector.analyze(sim_glare, ROIS, NODE_IDS, APPROACHES_BY_NODE, now_s=101.5)
    assert len(active) == 1
    assert active[0].tamper_type == "glare"

    # 4. ROI Occlusion Simulation
    detector = CameraTamperDetector(min_duration_s=1.0)
    engine.occlusion_mode = "roi_occlusion"
    engine.occlusion_target_roi = "J1_N_IN"
    sim_roi = engine._apply_occlusion_simulation(base_frame)
    detector.analyze(sim_roi, ROIS, NODE_IDS, APPROACHES_BY_NODE, now_s=100.0)
    active, _, _ = detector.analyze(sim_roi, ROIS, NODE_IDS, APPROACHES_BY_NODE, now_s=101.5)
    assert len(active) == 1
    assert "roi_blind" in active[0].tamper_type or "all_approaches_blind" in active[0].tamper_type

    # 5. None (Clear) Simulation restores healthy state
    engine.occlusion_mode = "none"
    sim_clear = engine._apply_occlusion_simulation(base_frame)
    np.testing.assert_array_equal(sim_clear, base_frame)
    detector.analyze(sim_clear, ROIS, NODE_IDS, APPROACHES_BY_NODE, now_s=102.0)
    active_after, _, _ = detector.analyze(sim_clear, ROIS, NODE_IDS, APPROACHES_BY_NODE, now_s=104.0)
    assert len(active_after) == 0
