"""FileVideoSource: plays a video file at its own fps (wait when ahead, drop frames when behind), loops at the end."""
import sys
from pathlib import Path

import numpy as np
import pytest

VISION_DIR = Path(__file__).resolve().parents[2] / "services" / "vision"
if str(VISION_DIR) not in sys.path:
    sys.path.insert(0, str(VISION_DIR))

cv2 = pytest.importorskip("cv2")

from video_source import FileVideoSource  # noqa: E402

FPS, FRAMES = 10, 20


class FakeClock:
    def __init__(self):
        self.now = 100.0
        self.slept = []

    def __call__(self):
        return self.now

    def sleep(self, seconds):
        self.slept.append(seconds)
        self.now += seconds


@pytest.fixture
def video(tmp_path):
    """20 frames of 32x32 whose blue channel is 10 * index, so the frame index can be read back."""
    path = tmp_path / "clip.avi"
    writer = cv2.VideoWriter(str(path), cv2.VideoWriter_fourcc(*"MJPG"), FPS, (32, 32))
    for i in range(FRAMES):
        writer.write(np.full((32, 32, 3), (10 * i, 0, 0), np.uint8))
    writer.release()
    return str(path)


def frame_index(frame):
    return round(float(frame[:, :, 0].mean()) / 10)


def test_reads_every_frame_in_order_and_waits_for_each_frames_time(video):
    clock = FakeClock()
    source = FileVideoSource(video, clock=clock, sleep=clock.sleep)
    indices = [frame_index(source.read_frame()[1]) for _ in range(5)]
    assert indices == [0, 1, 2, 3, 4]
    assert clock.now - 100.0 == pytest.approx(0.4, abs=0.02)   # frame 4 is due 0.4 s after frame 0


def test_slow_reader_skips_frames_instead_of_playing_in_slow_motion(video):
    clock = FakeClock()
    source = FileVideoSource(video, clock=clock, sleep=clock.sleep)
    assert frame_index(source.read_frame()[1]) == 0
    clock.now += 0.5                                           # inference took 0.5 s: 5 frames went by
    assert frame_index(source.read_frame()[1]) == 5


def test_loops_when_the_file_ends(video):
    clock = FakeClock()
    source = FileVideoSource(video, clock=clock, sleep=clock.sleep)
    for _ in range(FRAMES):
        source.read_frame()
    ok, frame = source.read_frame()
    assert ok and frame_index(frame) == 0


def test_skipping_past_the_end_restarts_the_clip(video):
    clock = FakeClock()
    source = FileVideoSource(video, clock=clock, sleep=clock.sleep)
    source.read_frame()
    clock.now += 5.0                                           # 50 frames due, the clip has 20
    ok, frame = source.read_frame()
    assert ok and frame_index(frame) == 0


def test_realtime_off_reads_without_waiting(video):
    clock = FakeClock()
    source = FileVideoSource(video, realtime=False, clock=clock, sleep=clock.sleep)
    assert [frame_index(source.read_frame()[1]) for _ in range(3)] == [0, 1, 2]
    assert clock.slept == []


def test_missing_file_reports_failure(tmp_path):
    source = FileVideoSource(str(tmp_path / "missing.mp4"))
    assert source.read_frame() == (False, None)
