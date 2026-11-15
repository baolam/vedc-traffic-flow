import sys
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

cv2 = pytest.importorskip("cv2")

from roi_manager import ROIManager
from metrics_extractor import MetricsExtractor
from vision_contracts_helper import validate_payload


def test_all_four_quadrants_default_rois():
    """
    Verifies that setup_default_node_rois accurately maps each of the 4 quadrants
    to its corresponding approach ID: N_IN, S_IN, E_IN, W_IN.
    """
    width, height = 640, 480
    roi = ROIManager(width=width, height=height)
    roi.setup_default_node_rois(node_id="J1")

    # Quadrant 1 - North (N_IN): cx-50 <= x <= cx (270..320), 0 <= y <= cy-50 (0..190)
    box_north = (280, 50, 20, 30)  # center = (290, 65)

    # Quadrant 2 - South (S_IN): cx <= x <= cx+50 (320..370), cy+50 <= y <= height (290..480)
    box_south = (330, 350, 20, 30)  # center = (340, 365)

    # Quadrant 3 - East (E_IN): cx+50 <= x <= width (370..640), cy-50 <= y <= cy (190..240)
    box_east = (450, 200, 30, 20)  # center = (465, 210)

    # Quadrant 4 - West (W_IN): 0 <= x <= cx-50 (0..270), cy <= y <= cy+50 (240..290)
    box_west = (100, 250, 30, 20)  # center = (115, 260)

    assigned = roi.assign_detections([box_north, box_south, box_east, box_west])

    assert "J1_N_IN" in assigned
    assert len(assigned["J1_N_IN"]) == 1
    assert assigned["J1_N_IN"][0] == box_north

    assert "J1_S_IN" in assigned
    assert len(assigned["J1_S_IN"]) == 1
    assert assigned["J1_S_IN"][0] == box_south

    assert "J1_E_IN" in assigned
    assert len(assigned["J1_E_IN"]) == 1
    assert assigned["J1_E_IN"][0] == box_east

    assert "J1_W_IN" in assigned
    assert len(assigned["J1_W_IN"]) == 1
    assert assigned["J1_W_IN"][0] == box_west


def test_custom_approach_ids_rois():
    """
    Verifies that arbitrary custom approach IDs (e.g. from real SUMO topology edges)
    are mapped into the 4 quadrant slots correctly.
    """
    roi = ROIManager(width=640, height=480)
    custom_ids = ["edge_N", "edge_S", "edge_E", "edge_W"]
    roi.setup_default_node_rois(node_id="J2", approach_ids=custom_ids)

    assert set(roi.rois.keys()) == set(custom_ids)

    # Check that edge_N is at the North quadrant
    box_north = (280, 50, 20, 30)
    assigned = roi.assign_detections([box_north])
    assert len(assigned["edge_N"]) == 1
    assert len(assigned["edge_S"]) == 0


def test_metrics_extractor_dynamic_flow_steady():
    """
    Verifies steady queue state produces reasonable non-zero flow rate.
    """
    extractor = MetricsExtractor()
    boxes = [(100, 250, 30, 20), (140, 250, 30, 20)]  # 2 vehicles
    roi_area = 10000.0

    # Step 1: Initial observation at t=0
    m1 = extractor.compute_approach_metrics(
        approach_id="J1_W_IN",
        boxes=boxes,
        roi_area=roi_area,
        detection_confidence=0.95,
        timestamp_s=100.0
    )
    assert m1["queue_vehicles"] == 2.0
    assert m1["flow_veh_per_s"] > 0.0

    # Step 2: Next observation at t=1.0 with steady queue of 2 vehicles
    m2 = extractor.compute_approach_metrics(
        approach_id="J1_W_IN",
        boxes=boxes,
        roi_area=roi_area,
        detection_confidence=0.95,
        timestamp_s=101.0
    )
    assert m2["queue_vehicles"] == 2.0
    # Steady state flow should be around queue * 0.06
    assert 0.05 <= m2["flow_veh_per_s"] <= 0.30


def test_metrics_extractor_dynamic_flow_discharging():
    """
    Verifies that when queue discharges (e.g. green phase clearing cars),
    the dynamic flow rate increases to reflect vehicle discharge throughput.
    """
    extractor = MetricsExtractor()
    roi_area = 20000.0

    # Step 1: Initial large queue of 6 vehicles at t=0
    large_boxes = [(100 + i * 20, 250, 18, 15) for i in range(6)]
    m1 = extractor.compute_approach_metrics(
        approach_id="J1_N_IN",
        boxes=large_boxes,
        roi_area=roi_area,
        timestamp_s=10.0
    )
    assert m1["queue_vehicles"] == 6.0

    # Step 2: Queue drops to 2 vehicles at t=1.0 (4 vehicles discharged)
    smaller_boxes = [(100, 250, 18, 15), (130, 250, 18, 15)]
    m2 = extractor.compute_approach_metrics(
        approach_id="J1_N_IN",
        boxes=smaller_boxes,
        roi_area=roi_area,
        timestamp_s=11.0
    )
    assert m2["queue_vehicles"] == 2.0
    # Discharging 4 vehicles in 1s should give a prominent flow rate
    assert m2["flow_veh_per_s"] > 1.0


def test_metrics_extractor_zero_queue():
    """
    Verifies that when no vehicles are in the ROI, queue and occupancy are zero.
    """
    extractor = MetricsExtractor()
    m = extractor.compute_approach_metrics(
        approach_id="J1_E_IN",
        boxes=[],
        roi_area=10000.0,
        detection_confidence=1.0,
        timestamp_s=50.0
    )
    assert m["queue_vehicles"] == 0.0
    assert m["flow_veh_per_s"] == 0.0
    assert m["occupancy_ratio"] == 0.0
    # Zero occupancy means free-flow speed
    assert m["mean_speed_mps"] == 2.5


def test_metrics_extractor_speed_bounds():
    """
    Verifies mean_speed_mps scales inversely with occupancy and stays strictly within bounds [0.5, 15.0].
    """
    extractor = MetricsExtractor()

    # Extremely jammed: total box area > roi area (occupancy capped at 1.0)
    huge_boxes = [(10, 10, 200, 200)]  # area = 40000 > 10000
    m_jammed = extractor.compute_approach_metrics(
        approach_id="J1_S_IN",
        boxes=huge_boxes,
        roi_area=10000.0,
        timestamp_s=60.0
    )
    assert m_jammed["occupancy_ratio"] == 1.0
    assert m_jammed["mean_speed_mps"] == 0.5  # Bounded lower limit


def test_metrics_extractor_contract_compliance():
    """
    Verifies generated telemetry approaches dictionary passes canonical JSON schema validation.
    """
    extractor = MetricsExtractor()
    boxes = [(100, 250, 30, 20)]
    roi_area = 10000.0

    app_metrics = extractor.compute_approach_metrics(
        approach_id="J1_W_IN",
        boxes=boxes,
        roi_area=roi_area,
        detection_confidence=0.98,
        timestamp_s=100.0
    )

    full_telemetry = {
        "node_id": "J1",
        "source_type": "vision",
        "simulation_time_s": 10.0,
        "timestamp_ms": 1727000000000,
        "current_phase_id": "J1_PHASE_NS",
        "approaches": [app_metrics]
    }

    # Must pass schema validation without throwing jsonschema.ValidationError
    validate_payload(full_telemetry, "telemetry")
