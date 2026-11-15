"""Chấm một model lên video kiểm: số xe thật (roi_truth) so với số hộp có tâm nằm trong ROI."""
import json, sys, cv2, numpy as np
repo, model, video, scen, rois, ncls, vcls = sys.argv[1:8]
sys.path.insert(0, repo)
from services.vision.detector import VehicleDetector
det = VehicleDetector(model_path=model, conf_threshold=0.4, input_size=640, num_classes=int(ncls),
                      vehicle_classes=tuple(int(c) for c in vcls.split(",")))
truth = json.load(open(scen))["roi_truth"]; cfg = json.load(open(rois))
polys = {k: np.array(p, np.int32) for n in cfg["nodes"].values() for k, p in n.items()}
cap = cv2.VideoCapture(video); tp = fp = fn = 0; idx = 0; tot_truth = tot_det = 0
while True:
    ok, fr = cap.read()
    if not ok or idx >= len(truth): break
    boxes, _ = det.detect(fr)
    cs = [(x + w // 2, y + h // 2) for x, y, w, h in boxes]
    for k, poly in polys.items():
        n = sum(1 for c in cs if cv2.pointPolygonTest(poly, (float(c[0]), float(c[1])), False) >= 0)
        t = truth[idx][k]; tp += min(n, t); fp += max(n - t, 0); fn += max(t - n, 0); tot_truth += t; tot_det += n
    idx += 1
print(f"{idx} khung | xe thật trong ROI {tot_truth} | model đếm {tot_det} | precision {tp/max(tp+fp,1):.3f} recall {tp/max(tp+fn,1):.3f}")
