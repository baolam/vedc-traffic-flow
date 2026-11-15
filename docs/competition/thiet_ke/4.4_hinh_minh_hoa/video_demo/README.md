# Video demo luồng hệ thống (render Blender, 18/10/2026)

Video render 3D mô phỏng hai ngã tư J1–J2 trên tấm bạt 1200 × 600, camera nghiêng bao quát cả hai nút.
Dùng làm nguồn video cho service vision (`VIDEO_SOURCE=<file>`) thay camera thật. **Vòng hở:** xe trong video dừng theo
đèn ẢO của mô phỏng, không dừng theo đèn LED thật trên sa bàn. Giây 0–40 đèn chạy chu kỳ cố định (xanh 20 s, vàng 3 s,
all-red 2 s); từ giây 40 "EdgeFlow AI kích hoạt" và mỗi nút chọn pha theo số xe trong ROI (xanh tối thiểu 5 s, tối đa 60 s).
**Sa bàn thật chỉ có đèn R/Y/G, không có bảng đếm giây** (đã kiểm danh sách mua, plan 22/09, firmware): số giây chỉ hiện trên khung dashboard, theo plan "hiện quyết định bên cạnh đèn LED thật"; khung này là bố cục minh họa, không phải ảnh chụp dashboard React thật. Cụm đèn 3D trong video tự đổi màu theo pha.
**Số xe và quy tắc chọn pha trong chú thích là mô phỏng minh họa**, không phải YOLO hay log graph-control thật.
Mô phỏng đã kiểm: 0 cặp xe đè nhau trong mọi khung hình. Phải ghi rõ trong
báo cáo: video là render 3D mô phỏng, không phải ảnh từ camera.

## File

| File | Nội dung |
|---|---|
| `video_demo_150s.mp4` | 1500 khung, 1280 × 720, 10 fps, 150 s (kịch bản seed 1) |
| `video_trinh_dien_150s.mp4` | **Bản trình diễn**: cùng video nhưng phủ chú thích (khung dashboard hiện trạng thái đèn, số giây và số xe chờ của từng nút; lúc "EdgeFlow AI kích hoạt" ở giây 40, ROI và số xe, chuỗi video → AI → điều khiển → đèn, nhật ký chuyển pha). Chỉ để thuyết trình, không đưa vào vision |
| `video_kiem_60s.mp4` | 600 khung, 60 s, kịch bản seed 2: **tập kiểm**, không dùng để huấn luyện |
| `rois_video.json` | 8 polygon ROI (J1/J2 × N/S/E/W) trên khung 1280 × 720, đúng định dạng `services/vision/rois/` |
| `nhan_train.json`, `nhan_val.json` | Hộp bao 2D từng xe theo khung (x0, y0, x1, y1, id), chiếu từ hộp 3D qua camera |
| `kich_ban_train.json`, `kich_ban_val.json` | Quỹ đạo từng xe và **số xe thật trong từng ROI theo khung** (`roi_truth`) để đối chiếu telemetry |
| `video_demo.blend` | Cảnh video (đã bỏ camera trên trụ) |
| `hud_video.py` | Script phủ chú thích và khung dashboard (`python hud_video.py <video sạch> kich_ban_train.json rois_video.json <ra>`). `hud_anchors.json` không còn dùng |
| `video_ml.py` | Ghép mp4, tạo dataset YOLO, huấn luyện, xuất ONNX, chấm đếm xe trong ROI. **Chưa chạy các bước train/export/score** |

Hộp bao nhãn không tính che khuất (cụm đèn, trụ che một vài xe) và xe nhô ra ngoài mép bạt có thể bị cắt.

## Sinh lại

```bash
cd thiet_ke_bao_cao/4.4_hinh_minh_hoa/blender
python3 video_mo_phong.py --seconds 150 --fps 10 --seed 1 --out ../video_demo/kich_ban_train.json
python3 video_mo_phong.py --seconds 60  --fps 10 --seed 2 --out ../video_demo/kich_ban_val.json
/Applications/Blender.app/Contents/MacOS/Blender -b -P dung_video.py -- \
    --scenario ../video_demo/kich_ban_train.json --frames-dir <thư mục khung> \
    --labels ../video_demo/nhan_train.json --rois ../video_demo/rois_video.json   # ~0,8 s/khung, ~20 phút
uv run -q --with opencv-python-headless --with numpy python ../video_demo/video_ml.py encode <thư mục khung> ../video_demo/video_demo_150s.mp4 10
```

## Model YOLO cho video này (huấn luyện 18/10)

- Model của đội trong git (`services/vision/models/yolov8n.onnx`) là **YOLOv8n COCO gốc** (metadata "trained on coco.yaml", 80 lớp). Chấm trên `video_kiem_60s.mp4`: đếm được **1 / 3604** xe trong ROI (recall 0%).
- Đã huấn luyện `yolo11n` 1 lớp `vehicle`: 500 ảnh train (video 150 s, bước 3), 200 ảnh val (video kiểm, kịch bản khác), 40 epoch, imgsz 640, M1 (MPS), ~25 phút. mAP50 0,995, mAP50-95 0,987 (`yolo11n_sa_ban_train_results.csv`). Trọng số: `yolo11n_sa_ban_best.pt`.
- Xuất ONNX opset 12 → `vedc-traffic-flow/models/yolo11n_sa_ban.onnx` (sha256 `3657e9d3…`, đã ghi vào `models/SHA256SUMS`).
- Chấm bằng `VehicleDetector` của repo (`score_any.py`) trên video kiểm: **precision 0,988, recall 0,990** (3609 xe đếm / 3604 xe thật trong ROI, 600 khung).
- **Giới hạn:** val là kịch bản khác nhưng cùng cảnh Blender, cùng camera, cùng kiểu xe; kết quả chỉ nói model đọc được video này, **không** chứng minh nhận ra xe thật hay sa bàn quay bằng camera thật. Ghi đúng như vậy trong báo cáo.
- Cấu hình chạy: `VIDEO_SOURCE=data/demo_video/video_demo_150s.mp4 VISION_NODE_IDS=J1,J2 ROI_CONFIG_PATH=services/vision/rois/rois_video_1280x720.json DETECTION_MODEL_PATH=models/yolo11n_sa_ban.onnx DETECTOR_NUM_CLASSES=1 DETECTOR_VEHICLE_CLASSES=0 VISION_FPS=10` (khối sẵn ở cuối `.env.rpi.example`).
- Vòng kín trên Mac (service vision thật đọc video, graph-control `edgeflow`, 2 ESP32 ảo, 90 s): `flow_report.py` PASS 16/16; mỗi nút đổi pha 6–7 lần, NS/EW xanh ~31 s mỗi hướng; pha trong telemetry khớp ESP32 81/81.

## Việc còn lại

1. Đo FPS và độ trễ của model này trên **Pi 5 thật** (chưa có số nào trên Pi).
2. Chạy `sync_to_pi.sh` + `preflight.sh` trên Pi thật với `VIDEO_SOURCE` là file.
3. Vòng kín với ESP32 thật, ghi `mosquitto_sub` suốt buổi, chấm bằng `flow_report.py`.
4. Câu hỏi đội: bỏ camera thật, bạt 1200 × 600, vị trí Pi và nút S1 trên bạt có ổn không.
