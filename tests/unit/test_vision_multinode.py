"""One camera covering several intersections: ROI calibration file, per-node telemetry, calibration tool."""
import importlib.util
import json
import sys
from pathlib import Path

import pytest

ROOT_DIR = Path(__file__).resolve().parents[2]
VISION_DIR = ROOT_DIR / "services" / "vision"
CONTRACTS_DIR = ROOT_DIR / "contracts"
for path in (VISION_DIR, CONTRACTS_DIR):
    if str(path) not in sys.path:
        sys.path.insert(0, str(path))

cv2 = pytest.importorskip("cv2")

import contracts_sdk  # noqa: E402
from perception_engine import PerceptionEngine  # noqa: E402
from roi_config import load_roi_config, parse_roi_config, save_roi_config, validate_against_topology  # noqa: E402

EXAMPLE_ROI = VISION_DIR / "rois" / "example_two_nodes_1280x720.json"
TOPOLOGY = contracts_sdk.load_topology("four_intersection_v1")


def load_module(name, filename):
    """Load a services/vision script by path; other services also ship a top-level main.py."""
    spec = importlib.util.spec_from_file_location(name, VISION_DIR / filename)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def square(x, y, size=20):
    return [[x, y], [x + size, y], [x + size, y + size], [x, y + size]]


@pytest.fixture
def two_node_engine():
    config = load_roi_config(EXAMPLE_ROI)
    engine = PerceptionEngine(video_source_str="synthetic", width=config.frame_size[0], height=config.frame_size[1])
    engine.setup_nodes(["J1", "J2"], config.nodes)
    yield engine
    engine.close()


def test_example_roi_matches_topology():
    config = load_roi_config(EXAMPLE_ROI)
    validate_against_topology(config, TOPOLOGY, ["J1", "J2"])
    assert config.frame_size == (1280, 720)
    assert len(config.sha256) == 64


def test_roi_point_outside_frame_is_rejected():
    with pytest.raises(ValueError, match="outside"):
        parse_roi_config({"frame_size": [100, 100], "nodes": {"J1": {"J1_N_IN": square(90, 90)}}})


def test_roi_polygon_needs_three_points():
    with pytest.raises(ValueError, match="at least 3"):
        parse_roi_config({"frame_size": [100, 100], "nodes": {"J1": {"J1_N_IN": [[0, 0], [5, 5]]}}})


def test_roi_missing_approach_is_rejected():
    config = parse_roi_config({"frame_size": [100, 100], "nodes": {"J1": {"J1_N_IN": square(0, 0)}}})
    with pytest.raises(ValueError, match="do not match topology approaches"):
        validate_against_topology(config, TOPOLOGY, ["J1"])


def test_roi_unknown_node_is_rejected():
    config = load_roi_config(EXAMPLE_ROI)
    with pytest.raises(ValueError, match="not in topology"):
        validate_against_topology(config, TOPOLOGY, ["J9"])


def test_save_and_load_round_trip(tmp_path):
    nodes = {"J1": {"J1_N_IN": square(0, 0), "J1_S_IN": square(30, 0), "J1_E_IN": square(0, 30),
                    "J1_W_IN": square(30, 30)}}
    path = tmp_path / "roi.json"
    save_roi_config(path, "cam", (100, 100), nodes)
    config = load_roi_config(path)
    validate_against_topology(config, TOPOLOGY, ["J1"])
    assert config.nodes["J1"]["J1_W_IN"] == tuple(tuple(p) for p in square(30, 30))
    assert json.loads(path.read_text())["camera"] == "cam"


def test_save_refuses_invalid_file(tmp_path):
    with pytest.raises(ValueError):
        save_roi_config(tmp_path / "bad.json", "cam", (100, 100), {"J1": {"J1_N_IN": square(95, 95)}})
    assert not (tmp_path / "bad.json").exists()


def test_several_nodes_without_roi_file_is_rejected():
    engine = PerceptionEngine(video_source_str="synthetic")
    with pytest.raises(ValueError, match="ROI calibration file"):
        engine.setup_nodes(["J1", "J2"])
    engine.close()


def test_one_frame_produces_telemetry_for_every_node(two_node_engine):
    per_node = two_node_engine.process_frame_nodes()
    assert set(per_node) == {"J1", "J2"}
    for node_id, approaches in per_node.items():
        assert {a["approach_id"] for a in approaches} == {f"{node_id}_{d}_IN" for d in "NSEW"}


def test_detections_land_in_the_right_node(two_node_engine, monkeypatch):
    # Centre (785, 385) lies inside J2_W_IN (x 660..910, y 360..410) of the example file.
    monkeypatch.setattr(two_node_engine, "detect_vehicles", lambda frame: [(775, 375, 20, 20)])
    per_node = two_node_engine.process_frame_nodes()
    queues = {a["approach_id"]: a["queue_vehicles"] for node in per_node.values() for a in node}
    assert queues["J2_W_IN"] == 1.0
    assert sum(queues.values()) == 1.0


def test_process_frame_by_node_in_multi_mode(two_node_engine):
    assert {a["approach_id"] for a in two_node_engine.process_frame(node_id="J2")} == {
        "J2_N_IN", "J2_S_IN", "J2_E_IN", "J2_W_IN"}
    with pytest.raises(ValueError):
        two_node_engine.process_frame(node_id="J3")


def test_single_node_default_rois_still_work():
    engine = PerceptionEngine(video_source_str="synthetic")
    engine.setup_nodes(["J1"])
    assert set(engine.process_frame_nodes()) == {"J1"}
    engine.close()


def test_main_helpers_build_valid_telemetry_per_node(two_node_engine):
    vision_main = load_module("vision_main_multinode", "main.py")
    cfg = vision_main.settings.model_copy(update={"vision_node_ids": "J1, J2"})
    assert vision_main.resolve_node_ids(cfg) == ["J1", "J2"]

    nodes = {n["node_id"]: n for n in TOPOLOGY["nodes"]}
    per_node = two_node_engine.process_frame_nodes()
    for node_id in ("J1", "J2"):
        payload = vision_main.build_telemetry(nodes[node_id], per_node[node_id], 1.0, 1727005820123)
        contracts_sdk.validate_payload(payload, "telemetry")
        assert payload["node_id"] == node_id


def test_missing_frame_reports_zero_confidence_not_traffic():
    vision_main = load_module("vision_main_missing", "main.py")
    node = next(n for n in TOPOLOGY["nodes"] if n["node_id"] == "J2")
    payload = vision_main.build_telemetry(node, [], 1.0, 1727005820123)
    contracts_sdk.validate_payload(payload, "telemetry")
    assert all(a["confidence"] == 0.0 and a["queue_vehicles"] == 0.0 for a in payload["approaches"])


def test_calibration_capture_and_overlay(tmp_path):
    tool = load_module("roi_calibrate_tool", "roi_calibrate.py")
    frame_path = tmp_path / "frame.png"
    frame = tool.capture_frame("synthetic", 1280, 720, frame_path, warmup_frames=1)
    assert frame.shape == (720, 1280, 3)
    assert cv2.imread(str(frame_path)).shape == (720, 1280, 3)

    overlay = tool.render_overlay(frame, load_roi_config(EXAMPLE_ROI))
    assert overlay.shape == frame.shape

    out = tmp_path / "overlay.png"
    assert tool.main(["check", "--config", str(EXAMPLE_ROI), "--nodes", "J1,J2",
                      "--image", str(frame_path), "--out", str(out)]) == 0
    assert out.exists()
