import json
import pytest
from pathlib import Path
from services.vision.demo_video_pipeline import run_pipeline_demo


def test_demo_video_pipeline_synthetic_max_pressure(tmp_path):
    out_video = tmp_path / "out_annotated.mp4"
    out_report = tmp_path / "out_report.json"

    report = run_pipeline_demo(
        video_source_str="synthetic",
        topology_id="tabletop_j1_j2_v1",
        node_id="J1",
        max_frames=4,
        controller_type="max_pressure",
        output_video_path=str(out_video),
        output_report_path=str(out_report),
        enable_motion_fallback=True
    )

    assert report["status"] == "SUCCESS"
    assert report["node_id"] == "J1"
    assert report["topology_id"] == "tabletop_j1_j2_v1"
    assert report["frames_processed"] == 4
    assert report["next_step_controller"] == "max_pressure"
    assert "metrics" in report
    assert report["metrics"]["throughput_fps"] > 0
    assert out_video.exists()
    assert out_report.exists()

    with open(out_report, "r", encoding="utf-8") as f:
        loaded = json.load(f)
    assert loaded["node_id"] == "J1"
    assert len(loaded["frame_log"]) == 4


def test_demo_video_pipeline_synthetic_none_controller(tmp_path):
    report = run_pipeline_demo(
        video_source_str="synthetic",
        topology_id="tabletop_j1_j2_v1",
        node_id="J1",
        max_frames=2,
        controller_type="none",
        output_video_path=None,
        output_report_path=None,
        enable_motion_fallback=True
    )

    assert report["status"] == "SUCCESS"
    assert report["frames_processed"] == 2
    assert report["next_step_controller"] == "none"
    assert report["sample_decision"] is None
