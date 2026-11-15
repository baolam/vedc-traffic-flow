"""Công cụ cho video demo: ghép khung hình thành mp4, tạo dataset YOLO từ nhãn Blender, huấn luyện, xuất ONNX, chấm.

  uv run -q --with opencv-python-headless --with numpy python video_ml.py encode  <thư mục khung> <ra.mp4> [fps]
  uv run -q --with opencv-python-headless --with numpy python video_ml.py dataset <dir dataset> \\
        <train.mp4> <nhan_train.json> <val.mp4> <nhan_val.json> [bước_train=3] [bước_val=3]
  uv run -q --with ultralytics python video_ml.py train <dir dataset> <dir chạy> [epochs=40] [imgsz=640]
  uv run -q --with ultralytics python video_ml.py export <best.pt> <ra.onnx> [imgsz=640]
  uv run -q --with opencv-python-headless --with numpy python video_ml.py score <model.onnx> <val.mp4> \\
        <kich_ban_val.json> <rois_video.json> <repo>

Dataset lấy khung từ chính file mp4 (miền ảnh giống lúc service vision đọc video), nhãn 1 lớp `vehicle` (id 0).
Tập kiểm là một kịch bản khác (seed khác), không dùng để huấn luyện.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path


def encode(frames_dir: str, out: str, fps: float = 10.0) -> None:
    import cv2
    files = sorted(Path(frames_dir).glob("f*.jpg"))
    first = cv2.imread(str(files[0]))
    h, w = first.shape[:2]
    writer = cv2.VideoWriter(out, cv2.VideoWriter_fourcc(*"mp4v"), fps, (w, h))
    for f in files:
        writer.write(cv2.imread(str(f)))
    writer.release()
    print(f"{len(files)} khung -> {out} ({w}x{h} @ {fps} fps)")


def _dump(video: str, labels_json: str, out_dir: Path, split: str, step: int) -> int:
    import cv2
    labels = json.loads(Path(labels_json).read_text())["labels"]
    cap = cv2.VideoCapture(video)
    (out_dir / "images" / split).mkdir(parents=True, exist_ok=True)
    (out_dir / "labels" / split).mkdir(parents=True, exist_ok=True)
    n, idx = 0, 0
    while True:
        ok, frame = cap.read()
        if not ok:
            break
        if idx % step == 0 and str(idx) in labels:
            h, w = frame.shape[:2]
            cv2.imwrite(str(out_dir / "images" / split / f"{split}_{idx:05d}.jpg"), frame,
                        [cv2.IMWRITE_JPEG_QUALITY, 95])
            rows = []
            for x0, y0, x1, y1, _ in labels[str(idx)]:
                rows.append(f"0 {(x0 + x1) / 2 / w:.6f} {(y0 + y1) / 2 / h:.6f} {(x1 - x0) / w:.6f} {(y1 - y0) / h:.6f}")
            (out_dir / "labels" / split / f"{split}_{idx:05d}.txt").write_text("\n".join(rows) + ("\n" if rows else ""))
            n += 1
        idx += 1
    return n


def dataset(out: str, tr_mp4: str, tr_json: str, va_mp4: str, va_json: str, st: int = 3, sv: int = 3) -> None:
    out_dir = Path(out)
    n_tr = _dump(tr_mp4, tr_json, out_dir, "train", st)
    n_va = _dump(va_mp4, va_json, out_dir, "val", sv)
    (out_dir / "data.yaml").write_text(f"path: {out_dir}\ntrain: images/train\nval: images/val\nnames:\n  0: vehicle\n")
    print(f"dataset: {n_tr} ảnh train, {n_va} ảnh val -> {out_dir}")


def train(data_dir: str, run_dir: str, epochs: int = 40, imgsz: int = 640) -> None:
    from ultralytics import YOLO
    model = YOLO("yolo11n.pt")
    model.train(data=str(Path(data_dir) / "data.yaml"), epochs=epochs, imgsz=imgsz, batch=16, device="mps",
                project=run_dir, name="sa_ban", exist_ok=True, workers=2, fliplr=0.5, flipud=0.0, mosaic=0.5,
                hsv_h=0.01, patience=15, plots=False)


def export(best: str, out: str, imgsz: int = 640) -> None:
    import shutil
    from ultralytics import YOLO
    path = YOLO(best).export(format="onnx", imgsz=imgsz, opset=12, simplify=False, dynamic=False, nms=False)
    shutil.copy(path, out)
    print("ONNX ->", out)


def score(model: str, video: str, scenario: str, rois: str, repo: str) -> None:
    """Chạy VehicleDetector của repo lên video, đếm xe trong từng ROI, so với số xe thật của kịch bản."""
    import cv2
    import numpy as np
    sys.path.insert(0, repo)
    from services.vision.detector import VehicleDetector
    det = VehicleDetector(model_path=model, conf_threshold=0.4, input_size=640, num_classes=1, vehicle_classes=(0,))
    truth = json.loads(Path(scenario).read_text())["roi_truth"]
    cfg = json.loads(Path(rois).read_text())
    polys = {k: np.array(p, np.int32) for node in cfg["nodes"].values() for k, p in node.items()}
    cap = cv2.VideoCapture(video)
    errs: dict[str, list[int]] = {k: [] for k in polys}
    tp = fp = fn = 0
    idx = 0
    while True:
        ok, frame = cap.read()
        if not ok or idx >= len(truth):
            break
        boxes, _ = det.detect(frame)       # (x, y, w, h); ROIManager gán theo tâm hộp, ta chấm đúng như vậy
        centres = [(x + w // 2, y + h // 2) for x, y, w, h in boxes]
        for k, poly in polys.items():
            n = sum(1 for c in centres if cv2.pointPolygonTest(poly, (float(c[0]), float(c[1])), False) >= 0)
            errs[k].append(abs(n - truth[idx][k]))
            tp += min(n, truth[idx][k])
            fp += max(n - truth[idx][k], 0)
            fn += max(truth[idx][k] - n, 0)
        idx += 1
    print(f"{idx} khung | precision {tp / max(tp + fp, 1):.3f} recall {tp / max(tp + fn, 1):.3f}")
    for k, e in errs.items():
        print(f"  {k}: sai số tuyệt đối trung bình {np.mean(e):.3f} xe, lớn nhất {max(e)}")


if __name__ == "__main__":
    cmd, args = sys.argv[1], sys.argv[2:]
    if cmd == "encode":
        encode(args[0], args[1], float(args[2]) if len(args) > 2 else 10.0)
    elif cmd == "dataset":
        dataset(*args[:5], *(int(a) for a in args[5:7]))
    elif cmd == "train":
        train(args[0], args[1], *(int(a) for a in args[2:4]))
    elif cmd == "export":
        export(args[0], args[1], *(int(a) for a in args[2:3]))
    elif cmd == "score":
        score(*args[:5])
    else:
        raise SystemExit(__doc__)
