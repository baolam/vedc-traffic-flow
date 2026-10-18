"""Dataset recording for fine-tuning: frames come from the service capture path, one folder per session."""
import json
import sys
from pathlib import Path

import numpy as np
import pytest

ROOT_DIR = Path(__file__).resolve().parents[2]
VISION_DIR = ROOT_DIR / "services" / "vision"
CONTRACTS_DIR = ROOT_DIR / "contracts"
for path in (VISION_DIR, CONTRACTS_DIR):
    if str(path) not in sys.path:
        sys.path.insert(0, str(path))

cv2 = pytest.importorskip("cv2")

import capture_dataset  # noqa: E402
from video_source import SyntheticVideoSource  # noqa: E402


class ConstantSource:
    """A static scene: every frame identical, as when nobody moves the tabletop cars."""

    def __init__(self, shape=(480, 640, 3)):
        self.reads = 0
        self.frame = np.full(shape, 90, dtype=np.uint8)

    def read_frame(self):
        self.reads += 1
        return True, self.frame.copy()

    def release(self):
        pass


def no_sleep(_seconds):
    pass


def test_session_writes_frames_and_manifest(tmp_path):
    manifest = capture_dataset.record_session(
        SyntheticVideoSource(), tmp_path, "s01", every_s=0, max_frames=3, min_diff=0,
        warmup_frames=0, size=(640, 480), note="low queue, daylight",
        source_info={"video": "synthetic", "lens_position": 2.0}, sleep=no_sleep)

    session_dir = tmp_path / "s01"
    files = sorted(p.name for p in session_dir.glob("*.jpg"))
    assert files == ["s01_000001.jpg", "s01_000002.jpg", "s01_000003.jpg"]
    on_disk = json.loads((session_dir / "session.json").read_text())
    assert on_disk == manifest
    assert manifest["session"] == "s01"
    assert manifest["note"] == "low queue, daylight"
    assert manifest["source"]["lens_position"] == 2.0
    assert [f["file"] for f in manifest["frames"]] == files
    assert cv2.imread(str(session_dir / files[0])).shape == (480, 640, 3)


def test_near_duplicate_frames_are_skipped(tmp_path):
    source = ConstantSource()
    manifest = capture_dataset.record_session(
        source, tmp_path, "static", every_s=0, max_frames=5, max_reads=6, min_diff=2.0,
        warmup_frames=0, size=(640, 480), sleep=no_sleep)

    assert len(manifest["frames"]) == 1
    assert manifest["skipped_near_duplicates"] == 5


def test_frames_are_resized_to_the_service_geometry(tmp_path):
    source = ConstantSource(shape=(1080, 1920, 3))
    capture_dataset.record_session(source, tmp_path, "s02", every_s=0, max_frames=1, min_diff=0,
                                   warmup_frames=0, size=(1280, 720), sleep=no_sleep)
    assert cv2.imread(str(tmp_path / "s02" / "s02_000001.jpg")).shape == (720, 1280, 3)


def test_existing_session_is_never_overwritten(tmp_path):
    (tmp_path / "s01").mkdir()
    with pytest.raises(FileExistsError):
        capture_dataset.record_session(ConstantSource(), tmp_path, "s01", max_frames=1,
                                       warmup_frames=0, size=(640, 480), sleep=no_sleep)


@pytest.mark.parametrize("bad", ["", "../s01", "a/b", "s 01"])
def test_session_name_must_be_a_plain_identifier(tmp_path, bad):
    with pytest.raises(ValueError):
        capture_dataset.record_session(ConstantSource(), tmp_path, bad, max_frames=1,
                                       warmup_frames=0, size=(640, 480), sleep=no_sleep)


def test_camera_failure_is_recorded_not_hidden(tmp_path):
    class Flaky(ConstantSource):
        def read_frame(self):
            self.reads += 1
            if self.reads % 2:
                return False, None
            self.frame = self.frame + 10  # scene changes so frames are not duplicates
            return True, self.frame.copy()

    manifest = capture_dataset.record_session(Flaky(), tmp_path, "s03", every_s=0, max_frames=2,
                                              min_diff=0, warmup_frames=0, size=(640, 480), sleep=no_sleep)
    assert len(manifest["frames"]) == 2
    assert manifest["failed_reads"] == 2
