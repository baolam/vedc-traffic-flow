"""VehicleDetector model loading: a model that cannot run must fail at startup, not on frame 1."""
import sys
from pathlib import Path

import numpy as np
import pytest

ROOT_DIR = Path(__file__).resolve().parents[2]
VISION_DIR = ROOT_DIR / "services" / "vision"
if str(VISION_DIR) not in sys.path:
    sys.path.insert(0, str(VISION_DIR))

cv2 = pytest.importorskip("cv2")

from detector import VehicleDetector  # noqa: E402


class FakeNet:
    """Stands in for cv2.dnn.Net; `forward` returns a fixed tensor or raises."""

    def __init__(self, output=None, error=None):
        self.output, self.error, self.inputs = output, error, []

    def setPreferableBackend(self, _):
        pass

    def setPreferableTarget(self, _):
        pass

    def getUnconnectedOutLayersNames(self):
        return ("output0",)

    def setInput(self, blob):
        self.inputs.append(blob)

    def forward(self, _names):
        if self.error is not None:
            raise self.error
        return [self.output]


def raw_yolo_output(num_classes, boxes=()):
    """Raw YOLOv8/11 tensor (1, 4+C, N): each box is (cx, cy, w, h, class_id, score) in input pixels."""
    tensor = np.zeros((1, 4 + num_classes, 100), dtype=np.float32)
    for i, (cx, cy, w, h, class_id, score) in enumerate(boxes):
        tensor[0, :4, i] = (cx, cy, w, h)
        tensor[0, 4 + class_id, i] = score
    return tensor


@pytest.fixture
def model_file(tmp_path):
    path = tmp_path / "model.onnx"
    path.write_bytes(b"not-a-real-onnx")
    return path


def use_net(monkeypatch, net):
    monkeypatch.setattr(cv2.dnn, "readNet", lambda _path: net)
    return net


def test_opencv_that_cannot_run_the_graph_fails_at_load_with_version_hint(monkeypatch, model_file):
    monkeypatch.setattr(cv2, "__version__", "4.6.0")
    use_net(monkeypatch, FakeNet(error=cv2.error("(-215:Assertion failed) start <= (int)shape.size()")))

    with pytest.raises(RuntimeError, match=r"OpenCV 4\.6\.0 cannot run model\.onnx.*>= 4\.8"):
        VehicleDetector(model_path=str(model_file))


def test_recent_opencv_failure_points_to_input_size_not_os_upgrade(monkeypatch, model_file):
    # A static yolo11n_416.onnx loaded with the default DETECTOR_INPUT_SIZE=640 fails in a Reshape
    # on OpenCV 4.10 (checked 07/10); telling the user to reinstall Trixie would be wrong.
    monkeypatch.setattr(cv2, "__version__", "4.10.0")
    use_net(monkeypatch, FakeNet(error=cv2.error("(-215:Assertion failed) total(srcShape) == maskTotal")))

    with pytest.raises(RuntimeError, match=r"DETECTOR_INPUT_SIZE=640.*imgsz") as excinfo:
        VehicleDetector(model_path=str(model_file), input_size=640)
    assert "Trixie" not in str(excinfo.value)


def test_class_count_mismatch_fails_at_load_not_on_first_frame(monkeypatch, model_file):
    # A 1-class fine-tuned export loaded with the default 80-class COCO settings.
    use_net(monkeypatch, FakeNet(output=raw_yolo_output(num_classes=1)))

    with pytest.raises(ValueError, match="DETECTOR_NUM_CLASSES"):
        VehicleDetector(model_path=str(model_file))


def test_load_runs_one_blank_forward_at_model_input_size(monkeypatch, model_file):
    net = use_net(monkeypatch, FakeNet(output=raw_yolo_output(num_classes=80)))

    VehicleDetector(model_path=str(model_file), input_size=320)

    assert len(net.inputs) == 1
    assert net.inputs[0].shape == (1, 3, 320, 320)


def test_single_class_model_detects_and_maps_box_back_to_frame(monkeypatch, model_file):
    # 1280x720 frame letterboxed into 640x640: scale 0.5, top padding 140 px.
    use_net(monkeypatch, FakeNet(output=raw_yolo_output(num_classes=1, boxes=[(320, 320, 40, 20, 0, 0.9)])))
    detector = VehicleDetector(model_path=str(model_file), num_classes=1, vehicle_classes=(0,))

    boxes, _ = detector.detect(np.zeros((720, 1280, 3), dtype=np.uint8))

    assert boxes == [(600, 340, 80, 40)]
    assert detector.last_scores == pytest.approx([0.9])
