"""Deployment-path tests for the vision service: Picamera2 source selection and CLI overrides."""
import sys
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

import importlib.util  # noqa: E402

import video_source  # noqa: E402
from video_source import Picamera2VideoSource, create_video_source  # noqa: E402


def load_vision_main():
    """Load services/vision/main.py by path; other services also ship a top-level main.py."""
    spec = importlib.util.spec_from_file_location("vision_main", VISION_DIR / "main.py")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


# Modes reported by Camera Module 3 (imx708): 1536x864 is a centre crop of the sensor, 2304x1296 is
# 2x2-binned full field of view (rpicam-hello --list-cameras).
IMX708_MODES = [
    {"size": (1536, 864), "fps": 120.13, "bit_depth": 10, "crop_limits": (768, 432, 3072, 1728)},
    {"size": (2304, 1296), "fps": 56.03, "bit_depth": 10, "crop_limits": (0, 0, 4608, 2592)},
    {"size": (4608, 2592), "fps": 14.35, "bit_depth": 10, "crop_limits": (0, 0, 4608, 2592)},
]


class FakePicamera2:
    """Minimal stand-in for picamera2.Picamera2 recording the calls the source makes."""

    def __init__(self):
        self.camera_controls = {"LensPosition": (0.0, 15.0, 1.0), "AeFlickerPeriod": (100, 1000000, 0)}
        self.sensor_modes = IMX708_MODES
        self.applied_controls = {}
        self.started = False
        self.closed = False

    def create_video_configuration(self, main, controls, buffer_count, sensor=None):
        return {"main": main, "controls": controls, "buffer_count": buffer_count, "sensor": sensor}

    def configure(self, config):
        self.config = config

    def start(self):
        self.started = True

    def set_controls(self, controls):
        self.applied_controls.update(controls)

    def capture_array(self, stream):
        return np.zeros((480, 640, 4), dtype=np.uint8)

    def stop(self):
        self.started = False

    def close(self):
        self.closed = True


@pytest.fixture
def fake_picamera2(monkeypatch):
    camera = FakePicamera2()
    picamera2_module = types.ModuleType("picamera2")
    picamera2_module.Picamera2 = lambda: camera
    libcamera_module = types.ModuleType("libcamera")
    libcamera_module.controls = types.SimpleNamespace(
        AfModeEnum=types.SimpleNamespace(Manual="AF_MANUAL"),
        AeFlickerModeEnum=types.SimpleNamespace(Manual="FLICKER_MANUAL"),
    )
    monkeypatch.setitem(sys.modules, "picamera2", picamera2_module)
    monkeypatch.setitem(sys.modules, "libcamera", libcamera_module)
    return camera


def test_picamera_source_uses_picamera2_not_v4l2(fake_picamera2):
    source = create_video_source("picamera", lens_position=2.0)
    assert isinstance(source, Picamera2VideoSource)
    assert fake_picamera2.started is True
    assert fake_picamera2.config["main"] == {"size": (640, 480), "format": "RGB888"}


def test_picamera_source_keeps_the_full_field_of_view(fake_picamera2):
    # Left to itself libcamera picks the cropped 1536x864 mode for a 1280x720 output.
    create_video_source("picamera", width=1280, height=720)
    assert fake_picamera2.config["sensor"] == {"output_size": (2304, 1296), "bit_depth": 10}


def test_full_fov_mode_selection_respects_frame_rate():
    assert video_source.pick_full_fov_mode(IMX708_MODES, min_fps=30) == IMX708_MODES[1]
    assert video_source.pick_full_fov_mode(IMX708_MODES, min_fps=10) == IMX708_MODES[1]  # smallest full-FOV
    # No full-FOV mode is fast enough: still keep the field of view, at the fastest such mode.
    assert video_source.pick_full_fov_mode(IMX708_MODES, min_fps=90) == IMX708_MODES[1]
    assert video_source.pick_full_fov_mode([], min_fps=30) is None


def test_picamera_without_mode_list_uses_libcamera_default(fake_picamera2):
    fake_picamera2.sensor_modes = []
    create_video_source("picamera")
    assert fake_picamera2.config["sensor"] is None


def test_picamera_source_locks_focus_and_flicker(fake_picamera2):
    create_video_source("csi", lens_position=2.5, flicker_period_us=10000)
    assert fake_picamera2.applied_controls == {
        "AfMode": "AF_MANUAL",
        "LensPosition": 2.5,
        "AeFlickerMode": "FLICKER_MANUAL",
        "AeFlickerPeriod": 10000,
    }


def test_picamera_source_keeps_autofocus_when_no_lens_position(fake_picamera2):
    create_video_source("picamera", lens_position=None, flicker_period_us=0)
    assert fake_picamera2.applied_controls == {}


def test_picamera_frame_is_three_channel_bgr(fake_picamera2):
    source = create_video_source("picamera")
    ok, frame = source.read_frame()
    assert ok is True
    assert frame.shape == (480, 640, 3)
    source.release()
    assert fake_picamera2.closed is True


def test_picamera_source_fails_loudly_without_picamera2(monkeypatch):
    monkeypatch.setitem(sys.modules, "picamera2", None)
    with pytest.raises(ImportError):
        create_video_source("picamera")


def test_numeric_source_still_uses_v4l2(monkeypatch):
    opened = []

    class FakeCapture:
        def __init__(self, index):
            opened.append(index)

        def isOpened(self):
            return False

    monkeypatch.setattr(video_source.cv2, "VideoCapture", FakeCapture)
    source = create_video_source("/dev/video2")
    assert isinstance(source, video_source.PiCameraVideoSource)
    assert opened == [2]


def test_cli_flags_override_settings():
    vision_main = load_vision_main()
    settings = vision_main.settings

    original = settings.model_dump()
    args = vision_main.parse_args(["--video", "picamera", "--mqtt-host", "10.0.0.5",
                                   "--mqtt-port", "1884", "--node-id", "J2", "--lens-position", "2.0"])
    cfg = vision_main.apply_cli_overrides(settings, args)
    assert cfg.video_source == "picamera"
    assert cfg.mqtt_host == "10.0.0.5"
    assert cfg.mqtt_port == 1884
    assert cfg.vision_node_id == "J2"
    assert cfg.camera_lens_position == 2.0
    assert settings.model_dump() == original  # overrides return a copy


def test_cli_without_flags_keeps_env_settings():
    vision_main = load_vision_main()
    settings = vision_main.settings

    cfg = vision_main.apply_cli_overrides(settings, vision_main.parse_args([]))
    assert cfg.model_dump() == settings.model_dump()
