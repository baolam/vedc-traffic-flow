import sys
import os
import pytest
from pathlib import Path

# Add services/vision and contracts to sys.path
ROOT_DIR = Path(__file__).resolve().parents[2]
VISION_DIR = ROOT_DIR / "services" / "vision"
CONTRACTS_DIR = ROOT_DIR / "contracts"

if str(VISION_DIR) not in sys.path:
    sys.path.insert(0, str(VISION_DIR))
if str(CONTRACTS_DIR) not in sys.path:
    sys.path.insert(0, str(CONTRACTS_DIR))

import contracts_sdk
from video_source import SyntheticVideoSource, create_video_source
from roi_manager import ROIManager
from metrics_extractor import MetricsExtractor
from perception_engine import PerceptionEngine

def test_synthetic_video_source():
    source = SyntheticVideoSource(width=640, height=480)
    ret, frame = source.read_frame()
    assert ret is True
    assert frame is not None
    assert frame.shape == (480, 640, 3)
    source.release()

def test_create_video_source_factory():
    source = create_video_source("synthetic")
    assert isinstance(source, SyntheticVideoSource)
    source.release()

def test_roi_manager_assignment():
    roi = ROIManager(width=640, height=480)
    roi.setup_default_node_rois(node_id="J1")
    
    # Bounding box in West approach quadrant: x=100, y=260, w=30, h=20 -> center = (115, 270)
    boxes = [(100, 260, 30, 20)]
    assigned = roi.assign_detections(boxes)
    
    assert "J1_W_IN" in assigned
    assert len(assigned["J1_W_IN"]) == 1
    assert assigned["J1_W_IN"][0] == (100, 260, 30, 20)

def test_metrics_extractor():
    extractor = MetricsExtractor()
    boxes = [(100, 260, 40, 30), (150, 260, 40, 30)]
    roi_area = 10000.0
    
    metrics = extractor.compute_approach_metrics(
        approach_id="J1_W_IN",
        boxes=boxes,
        roi_area=roi_area,
        detection_confidence=0.95
    )
    
    assert metrics["approach_id"] == "J1_W_IN"
    assert metrics["queue_vehicles"] == 2.0
    assert 0.0 <= metrics["occupancy_ratio"] <= 1.0
    assert 0.0 <= metrics["confidence"] <= 1.0
    assert metrics["mean_speed_mps"] > 0.0

def test_perception_engine_flow():
    engine = PerceptionEngine(video_source_str="synthetic", width=640, height=480)
    topology = contracts_sdk.load_topology("four_intersection_v1")
    engine.setup_topology(topology, node_id="J1")
    
    approaches = engine.process_frame(node_id="J1")
    assert isinstance(approaches, list)
    assert len(approaches) > 0
    engine.close()

def test_vision_telemetry_schema_validation():
    engine = PerceptionEngine(video_source_str="synthetic")
    approaches = engine.process_frame(node_id="J1")
    
    telemetry_payload = {
        "node_id": "J1",
        "source_type": "vision",
        "simulation_time_s": 10.0,
        "timestamp_ms": 1727005820123,
        "current_phase_id": "J1_PHASE_NS",
        "approaches": approaches
    }
    
    # Must pass JSON schema validation without exception
    contracts_sdk.validate_payload(telemetry_payload, "telemetry")
    engine.close()
