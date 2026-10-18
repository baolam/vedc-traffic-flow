"""Measured runtime evidence on the Pi: health payload, LWT, stage timings, throttling, benchmark sources."""
import importlib.util
import json
import sys
import time
import types
from pathlib import Path

import numpy as np
import pytest

ROOT_DIR = Path(__file__).resolve().parents[2]
VISION_DIR = ROOT_DIR / "services" / "vision"
CONTRACTS_DIR = ROOT_DIR / "contracts"
for path in (VISION_DIR, CONTRACTS_DIR):
    if str(path) not in sys.path:
        sys.path.insert(0, str(path))

pytest.importorskip("cv2")

import benchmark  # noqa: E402
import hardware_monitor  # noqa: E402
from perception_engine import PerceptionEngine  # noqa: E402
from runtime_stats import RuntimeStats  # noqa: E402


def load_vision_main():
    """Load services/vision/main.py by path; other services also ship a top-level main.py."""
    spec = importlib.util.spec_from_file_location("vision_main", VISION_DIR / "main.py")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


class FakeClock:
    def __init__(self, now=100.0):
        self.now = now

    def __call__(self):
        return self.now


class FailingSource:
    """A camera that stopped delivering frames (cable pulled, libcamera error)."""

    def read_frame(self):
        return False, None

    def release(self):
        pass


# --- RuntimeStats -------------------------------------------------------------------------------

def test_processed_fps_counts_only_good_frames_over_elapsed_time():
    clock = FakeClock()
    stats = RuntimeStats(window_s=30.0, clock=clock)
    for i in range(10):
        clock.now += 0.5
        stats.record(True, {"inference_ms": 100.0 + i, "capture_ms": 5.0})
    clock.now += 0.5
    stats.record(False)

    snap = stats.snapshot()

    assert snap["frames_ok"] == 10
    assert snap["frames_failed"] == 1
    assert snap["processed_fps"] == pytest.approx(2.0)  # 10 frames 0.5 s apart
    assert snap["latency_ms"]["inference_ms"]["p50"] == pytest.approx(104.5)
    assert snap["latency_ms"]["inference_ms"]["p95"] == pytest.approx(108.6, abs=0.1)
    assert snap["latency_ms"]["capture_ms"]["p50"] == 5.0


def test_consecutive_failures_reset_on_next_good_frame():
    stats = RuntimeStats(clock=FakeClock())
    stats.record(False)
    stats.record(False)
    assert stats.snapshot()["consecutive_failures"] == 2
    stats.record(True, {"total_ms": 10.0})
    assert stats.snapshot()["consecutive_failures"] == 0
    assert stats.total_failures == 2


def test_frames_older_than_the_window_are_dropped():
    clock = FakeClock()
    stats = RuntimeStats(window_s=10.0, clock=clock)
    stats.record(True, {"total_ms": 999.0})
    clock.now += 20.0
    stats.record(True, {"total_ms": 10.0})

    snap = stats.snapshot()

    assert snap["frames_ok"] == 1
    assert snap["latency_ms"]["total_ms"]["p95"] == 10.0
    assert snap["window_s"] == 10.0


def test_empty_stats_report_no_fps_rather_than_a_guess():
    clock = FakeClock()
    stats = RuntimeStats(clock=clock)
    snap = stats.snapshot()
    assert snap["frames_ok"] == 0
    assert snap["processed_fps"] is None
    assert snap["latency_ms"] == {}


def test_single_frame_right_after_start_gives_no_fps():
    # Seen live: one frame 0.08 s after start was reported as 12.5 fps.
    clock = FakeClock()
    stats = RuntimeStats(clock=clock)
    clock.now += 0.08
    stats.record(True, {"total_ms": 60.0})
    assert stats.snapshot()["processed_fps"] is None


# --- hardware_monitor ---------------------------------------------------------------------------

@pytest.mark.parametrize("raw, flags", [
    ("throttled=0x0", []),
    ("throttled=0x50005", ["under_voltage_now", "throttled_now", "under_voltage_occurred", "throttled_occurred"]),
    ("throttled=0x80000", ["soft_temp_limit_occurred"]),
    (None, None),
    ("garbage", None),
])
def test_decode_throttled_bits(raw, flags):
    assert hardware_monitor.decode_throttled(raw) == flags


def test_parse_pi5_input_voltage():
    assert hardware_monitor.parse_ext5v("     EXT5V_V volt(24)=5.13600000V\n") == pytest.approx(5.136)
    assert hardware_monitor.parse_ext5v("") is None


def test_cpu_temperature_can_report_missing_instead_of_nominal(monkeypatch):
    monkeypatch.setattr(hardware_monitor.os.path, "exists", lambda _p: False)
    assert hardware_monitor.get_cpu_temperature(fallback=None) is None
    assert hardware_monitor.get_cpu_temperature() == 45.0  # legacy default kept for existing callers


# --- PerceptionEngine capture timing ------------------------------------------------------------

def test_engine_records_capture_time_and_stage_timings():
    engine = PerceptionEngine(video_source_str="synthetic")
    engine.setup_nodes(["J1"])
    before_ms = int(time.time() * 1000)

    result = engine.process_frame_nodes()

    assert result["J1"]
    assert before_ms <= engine.last_frame["captured_at_ms"] <= int(time.time() * 1000)
    for key in ("capture_ms", "preprocess_ms", "inference_ms", "postprocess_ms", "total_ms"):
        assert engine.last_frame[key] >= 0.0
    engine.close()


def test_engine_clears_frame_info_when_camera_fails():
    engine = PerceptionEngine(video_source_str="synthetic")
    engine.setup_nodes(["J1"])
    engine.process_frame_nodes()
    engine.video_source = FailingSource()

    assert engine.process_frame_nodes() == {}
    assert engine.last_frame == {}


# --- vision health topic ------------------------------------------------------------------------

def test_offline_will_is_retained_on_the_health_topic():
    vision_main = load_vision_main()
    calls = []
    client = types.SimpleNamespace(will_set=lambda *a, **k: calls.append((a, k)))

    vision_main.set_offline_will(client)

    (args, kwargs), = calls
    assert args[0] == "edgeflow/v1/health/vision"
    assert json.loads(args[1])["status"] == "OFFLINE"
    assert kwargs["retain"] is True


@pytest.mark.parametrize("snapshot, status", [
    ({"frames_ok": 0, "consecutive_failures": 0}, "STARTING"),
    ({"frames_ok": 8, "consecutive_failures": 0}, "HEALTHY"),
    ({"frames_ok": 8, "consecutive_failures": 3}, "DEGRADED"),
])
def test_health_status_follows_measured_frames(snapshot, status):
    assert load_vision_main().health_status(snapshot) == status


def test_health_payload_carries_measured_runtime_not_config():
    vision_main = load_vision_main()
    clock = FakeClock()
    stats = RuntimeStats(clock=clock)
    for _ in range(4):
        clock.now += 1.0
        stats.record(True, {"inference_ms": 200.0})
    clock.now += 1.0
    stats.record(False)
    identity = {"service": "vision", "model_sha256": "abc", "active_nodes": ["J1", "J2"]}
    hardware = {"cpu_temp_c": 61.2, "throttled_flags": []}

    payload = vision_main.build_health(identity, stats.snapshot(), hardware, timestamp_ms=1234)

    assert payload["status"] == "DEGRADED"
    assert "1 consecutive" in payload["reason"]
    assert payload["runtime"]["processed_fps"] == pytest.approx(1.0)
    assert payload["runtime"]["latency_ms"]["inference_ms"]["p50"] == 200.0
    assert payload["model_sha256"] == "abc"
    assert payload["hardware"]["cpu_temp_c"] == 61.2
    assert payload["timestamp_ms"] == 1234
    assert "fps" not in payload  # the old field was 1/TELEMETRY_PERIOD_S, a configured value


# --- benchmark sources --------------------------------------------------------------------------

def test_benchmark_reads_through_the_service_video_sources():
    result = benchmark.benchmark("synthetic", frames=3, warmup=1)

    assert result["measured_frames"] == 3
    assert result["frame_size"] == [640, 480]
    assert "capture_ms" in result["timings"]
    assert {"hardware_before", "hardware_after", "board_model", "numpy"} <= set(result)
    assert all("captured_at_ms" in s for s in result["samples"])


def test_benchmark_picamera_source_uses_picamera2(monkeypatch):
    captured = []

    class FakeCamera:
        camera_controls = {}

        def create_video_configuration(self, main, controls, buffer_count):
            return {"main": main}

        def configure(self, config):
            self.size = config["main"]["size"]

        def start(self):
            pass

        def capture_array(self, _stream):
            captured.append(1)
            return np.zeros((self.size[1], self.size[0], 3), dtype=np.uint8)

        def stop(self):
            pass

        def close(self):
            pass

    module = types.ModuleType("picamera2")
    module.Picamera2 = FakeCamera
    monkeypatch.setitem(sys.modules, "picamera2", module)

    result = benchmark.benchmark("picamera", frames=2, warmup=0, width=1280, height=720)

    assert len(captured) == 2
    assert result["frame_size"] == [1280, 720]


def test_benchmark_stops_when_the_camera_fails(monkeypatch):
    monkeypatch.setattr(benchmark, "create_video_source", lambda *a, **k: FailingSource())
    with pytest.raises(RuntimeError, match="No measured frames"):
        benchmark.benchmark("picamera", frames=2, warmup=0)


# --- O14/O10: several frames per telemetry period ------------------------------------------------

from telemetry_window import TelemetryWindow  # noqa: E402


def approach(app_id, queue, occupancy=0.1):
    return {"approach_id": app_id, "queue_vehicles": queue, "flow_veh_per_s": queue * 0.08,
            "mean_speed_mps": 2.0, "occupancy_ratio": occupancy, "confidence": 1.0}


def test_window_reports_per_approach_median_over_frames():
    window = TelemetryWindow()
    for i, queue in enumerate([3, 0, 4, 3, 3]):  # one frame missed every car on J1_N_IN
        window.add({"J1": [approach("J1_N_IN", queue), approach("J1_S_IN", 1)]}, captured_at_ms=1000 + i)

    rows = {a["approach_id"]: a for a in window.aggregate("J1")}

    assert rows["J1_N_IN"]["queue_vehicles"] == 3.0
    assert rows["J1_N_IN"]["flow_veh_per_s"] == pytest.approx(0.24)
    assert rows["J1_S_IN"]["queue_vehicles"] == 1.0
    assert window.last_capture_ms == 1004
    assert window.frames == 5


def test_window_confidence_is_share_of_frames_actually_processed():
    window = TelemetryWindow()
    window.add({"J1": [approach("J1_N_IN", 2)]}, captured_at_ms=1)
    window.add_failure()
    window.add({"J1": [approach("J1_N_IN", 2)]}, captured_at_ms=3)
    window.add_failure()

    (row,) = window.aggregate("J1")

    assert row["confidence"] == 0.5
    assert window.failed == 2


def test_window_without_processed_frames_reports_nothing():
    window = TelemetryWindow()
    window.add_failure()
    assert window.aggregate("J1") == []
    assert window.last_capture_ms is None


def test_window_reset_starts_a_new_period():
    window = TelemetryWindow()
    window.add({"J1": [approach("J1_N_IN", 5)]}, captured_at_ms=1)
    window.add_failure()
    window.reset()
    window.add({"J1": [approach("J1_N_IN", 1)]}, captured_at_ms=2)

    (row,) = window.aggregate("J1")
    assert row["queue_vehicles"] == 1.0 and row["confidence"] == 1.0


def test_publish_timings_are_reported_with_frame_timings():
    clock = FakeClock()
    stats = RuntimeStats(clock=clock)
    clock.now += 1.0
    stats.record(True, {"inference_ms": 100.0})
    stats.record_publish({"publish_ms": 2.0, "age_at_publish_ms": 400.0, "frames_per_publish": 5})

    latency = stats.snapshot()["latency_ms"]

    assert latency["inference_ms"]["p50"] == 100.0
    assert latency["age_at_publish_ms"]["p95"] == 400.0
    assert latency["frames_per_publish"]["p50"] == 5.0


def test_engine_reports_processed_frames_at_full_confidence():
    # The window decides confidence; a processed frame itself no longer carries a made-up 0.92.
    engine = PerceptionEngine(video_source_str="synthetic")
    engine.setup_nodes(["J1"])
    assert all(a["confidence"] == 1.0 for a in engine.process_frame_nodes()["J1"])
    engine.close()
