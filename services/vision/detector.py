"""Desktop/edge OpenCV detector with explicit YOLO export formats and timing.

Supported: raw YOLOv8/11 ONNX (4+C,N), YOLOv5 ONNX (N,5+C), and
legacy normalized YOLO rows (N,5+C). End-to-end/NMS exports are rejected.
"""
import time
from pathlib import Path

import cv2
import numpy as np


class VehicleDetector:
    def __init__(self, model_path=None, conf_threshold=.4, nms_threshold=.45,
                 input_size=640, output_format="yolov8", num_classes=80,
                 vehicle_classes=(2, 3, 5, 7), motion_scale=1.0):
        if (not 0 < conf_threshold < 1 or not 0 < nms_threshold < 1
                or input_size < 32 or not 0 < motion_scale <= 1 or num_classes < 1):
            raise ValueError("Invalid detector configuration")
        if output_format not in ("yolov8", "yolov5", "legacy"):
            raise ValueError("Unknown YOLO output format")
        self.conf_threshold, self.nms_threshold = conf_threshold, nms_threshold
        self.input_size, self.output_format, self.num_classes = input_size, output_format, num_classes
        self.vehicle_classes = np.asarray(vehicle_classes, dtype=np.int64)
        if self.vehicle_classes.size == 0 or np.any(self.vehicle_classes < 0) or np.any(self.vehicle_classes >= num_classes):
            raise ValueError("Vehicle classes must belong to the model class list")
        self.motion_scale = motion_scale
        self.kernel = cv2.getStructuringElement(cv2.MORPH_RECT, (5, 5))
        self.net = None
        self.last_scores = []
        self.last_timings = {}
        self.model_sha256 = None
        if model_path:
            import hashlib
            path = Path(model_path)
            if not path.is_file():
                raise FileNotFoundError(path)
            # A requested model must load successfully; no silent motion fallback.
            self.net = cv2.dnn.readNet(str(path))
            self.net.setPreferableBackend(cv2.dnn.DNN_BACKEND_OPENCV)
            self.net.setPreferableTarget(cv2.dnn.DNN_TARGET_CPU)
            self.output_names = self.net.getUnconnectedOutLayersNames()
            self.model_sha256 = hashlib.sha256(path.read_bytes()).hexdigest()
            self._self_test(path)
        else:
            self.bg_subtractor = cv2.createBackgroundSubtractorMOG2(history=500, varThreshold=25, detectShadows=False)

    def _self_test(self, path):
        """One blank forward at load: an OpenCV build that cannot execute the graph, or a
        class count that does not match the export, fails at startup instead of on frame 1."""
        blank = np.zeros((1, 3, self.input_size, self.input_size), dtype=np.float32)
        try:
            self.net.setInput(blank)
            outputs = self.net.forward(self.output_names)
        except cv2.error as exc:
            # Raw YOLOv8/11 ONNX hits a shape_utils assertion in OpenCV 4.6/4.7 (checked 4.6.0, 4.7.0).
            raise RuntimeError(
                f"OpenCV {cv2.__version__} cannot run {path.name}: {str(exc).strip()}. "
                "YOLOv8/YOLO11 ONNX needs OpenCV >= 4.8; Raspberry Pi OS Bookworm's python3-opencv "
                "is 4.6, use Raspberry Pi OS Trixie (4.10)") from exc
        try:
            self.postprocess(outputs, (self.input_size, self.input_size, 3), (1.0, 0, 0))
        except ValueError as exc:
            raise ValueError(f"{path.name} does not match DETECTOR_OUTPUT_FORMAT="
                             f"{self.output_format}/DETECTOR_NUM_CLASSES={self.num_classes}: {exc}") from exc

    @property
    def backend(self):
        return "opencv_dnn" if self.net is not None else "motion_baseline"

    def preprocess(self, frame):
        h, w = frame.shape[:2]
        scale = min(self.input_size / w, self.input_size / h)
        size = (max(1, round(w * scale)), max(1, round(h * scale)))
        resized = cv2.resize(frame, size, interpolation=cv2.INTER_LINEAR)
        left = (self.input_size - size[0]) // 2
        top = (self.input_size - size[1]) // 2
        padded = cv2.copyMakeBorder(resized, top, self.input_size - size[1] - top,
                                    left, self.input_size - size[0] - left, cv2.BORDER_CONSTANT,
                                    value=(114, 114, 114))
        blob = cv2.dnn.blobFromImage(padded, 1 / 255., (self.input_size, self.input_size), swapRB=True)
        return blob, (scale, left, top)

    def postprocess(self, outputs, frame_shape, transform):
        offset = 4 if self.output_format == "yolov8" else 5
        columns = self.num_classes + offset
        rows = []
        for output in outputs:
            array = np.asarray(output, dtype=np.float32)
            if array.ndim == 3 and array.shape[0] == 1:
                array = array[0]
            if array.ndim != 2:
                raise ValueError(f"Unsupported YOLO tensor shape {array.shape}")
            if self.output_format == "yolov8" and array.shape[0] == columns:
                array = array.T
            if array.shape[1] != columns:
                raise ValueError(f"Expected {columns} output columns, got {array.shape}; check output_format/num_classes")
            rows.append(array)
        if not rows:
            self.last_scores = []
            return []
        predictions = np.concatenate(rows, axis=0)
        class_ids = np.argmax(predictions[:, offset:], axis=1)
        scores = predictions[np.arange(len(predictions)), offset + class_ids]
        if offset == 5:
            scores = scores * predictions[:, 4]
        keep = ((scores >= self.conf_threshold) & np.isin(class_ids, self.vehicle_classes)
                & np.isfinite(predictions).all(axis=1))
        selected, scores, class_ids = predictions[keep, :4].copy(), scores[keep], class_ids[keep]
        if not len(selected):
            self.last_scores = []
            return []
        if self.output_format == "legacy":
            selected *= self.input_size
        scale, left, top = transform
        h, w = frame_shape[:2]
        xy1 = (selected[:, :2] - selected[:, 2:] / 2 - (left, top)) / scale
        xy2 = (selected[:, :2] + selected[:, 2:] / 2 - (left, top)) / scale
        xy1 = np.clip(xy1, (0, 0), (w, h))
        xy2 = np.clip(xy2, (0, 0), (w, h))
        boxes = np.column_stack((xy1, xy2 - xy1)).round().astype(np.int32)
        positive = (boxes[:, 2:] > 0).all(axis=1)
        boxes, scores, class_ids = boxes[positive], scores[positive], class_ids[positive]
        # Class-aware NMS avoids one class suppressing a different nearby vehicle.
        retained = []
        for class_id in np.unique(class_ids):
            indices = np.flatnonzero(class_ids == class_id)
            nms = cv2.dnn.NMSBoxes(boxes[indices].tolist(), scores[indices].tolist(),
                                   self.conf_threshold, self.nms_threshold)
            if len(nms):
                retained.extend(indices[np.asarray(nms).reshape(-1)].tolist())
        retained.sort(key=lambda i: float(scores[i]), reverse=True)
        self.last_scores = [float(scores[i]) for i in retained]
        return [tuple(int(x) for x in boxes[i]) for i in retained]

    def detect(self, frame):
        if frame is None or frame.size == 0:
            self.last_scores, self.last_timings = [], {}
            return [], 0.0
        started = time.perf_counter()
        if self.net is not None:
            blob, transform = self.preprocess(frame)
            preprocessed = time.perf_counter()
            self.net.setInput(blob)
            outputs = self.net.forward(self.output_names)
            inferred = time.perf_counter()
            boxes = self.postprocess(outputs, frame.shape, transform)
        else:
            h, w = frame.shape[:2]
            size = (max(1, round(w * self.motion_scale)), max(1, round(h * self.motion_scale)))
            small = cv2.resize(frame, size, interpolation=cv2.INTER_AREA) if size != (w, h) else frame
            preprocessed = time.perf_counter()
            mask = self.bg_subtractor.apply(small)
            inferred = time.perf_counter()
            _, mask = cv2.threshold(mask, 200, 255, cv2.THRESH_BINARY)
            mask = cv2.dilate(mask, self.kernel, iterations=2)
            contours, _ = cv2.findContours(mask, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
            sx, sy = w / size[0], h / size[1]
            boxes = []
            for contour in contours:
                if cv2.contourArea(contour) >= 200 / (sx * sy):
                    x, y, bw, bh = cv2.boundingRect(contour)
                    boxes.append((round(x * sx), round(y * sy), round(bw * sx), round(bh * sy)))
            self.last_scores = []  # Motion contours have no learned confidence score.
        finished = time.perf_counter()
        self.last_timings = {"preprocess_ms": (preprocessed - started) * 1000,
                             "inference_ms": (inferred - preprocessed) * 1000,
                             "postprocess_ms": (finished - inferred) * 1000,
                             "total_ms": (finished - started) * 1000}
        return boxes, self.last_timings["total_ms"]
