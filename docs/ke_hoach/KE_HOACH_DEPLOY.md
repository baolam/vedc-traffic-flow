# EdgeFlow AI: kế hoạch deploy lên thiết bị (Pi 5, 2× ESP32, laptop)

Cập nhật 19/10/2026 (mục 0.7: rà toàn bộ luồng trên Docker, sửa G1–G3 + dashboard + compose, chưa commit). Trước đó 17/10 (mục 0: pull `e422ce7`, chạy thử cả vòng điều khiển, G1–G6, F31–F32). Lần trước là 07/10 (F18–F30, mục 7b, mục 8, O14–O16). Nằm ngoài git. Dựa trên repo `vedc-traffic-flow` ở commit `e422ce7` (main, 16/10) và Revised Plan (2).

**Trạng thái git:**

- F1–F17 đã vào `main`. Hiển commit `b841bbb` (05/10), baolam merge qua **PR #1** thành `343433b` (07/10 16:23). Nhánh `deploy/hardware-prep` local và remote đều nằm trọn trong `main`.
- F18–F30 (phiên 07/10), bộ công cụ test MQTT `src/hardware/demo/` (15/10) và F31–F32 (17/10) đang **để trong working tree của `main`, chưa commit**, để cả đội xem trước:

```bash
cd vedc-traffic-flow && git status && git diff      # 12 file sửa + các file mới
```

- **Repo GitHub là private**: Pi không `git clone` được nếu không có credential. Code và model lên Pi bằng `infra/rpi/sync_to_pi.sh` từ Mac (F28).

> Hook RTK **giấu merge commit** khỏi `git log` (lần này `343433b` không hiện ra, nhìn như `b841bbb` chưa vào `main`). Khi cần lịch sử chính xác, dùng `rtk proxy git log --format='%h %p %s'`.

---

## 0. Cập nhật 17/10: pull `e422ce7` và kiểm luồng điều khiển đèn

### 0.1 Pull

- `main` fast-forward từ `48e8103` lên **`e422ce7`** (baolam, 16/10: "integrate vision edge pipeline, hardware fail-safe resilience, and realtime dashboard monitoring").
- Commit này không đụng file nào mà F18–F30 đang sửa, nên pull không cần stash. `stash@{0}` (15/10) vẫn để nguyên.
- Test sau pull, gồm cả phần chưa commit (Python 3.11):
  - Unit: **349 passed**, gồm 333 test cũ và 16 test mới của F31.
  - Integration: 11 passed, 5 skipped (thiếu binary SUMO và gymnasium).
  - `make contracts`: 8 passed.
- CI giờ cài thêm `torch traci sumolib`. Thiếu 3 gói này thì 2 test SUMO lỗi ngay khi collect.
- Firmware J1/J2 vẫn build SUCCESS, flash 777.397 B (không đổi).

Những gì `e422ce7` thêm có liên quan tới deploy:

| Thêm | Ảnh hưởng tới Pi/ESP32/laptop |
|---|---|
| `contracts/topology/tabletop_j1_j2_v1.json` | Topology đúng với sa bàn: chỉ có J1 và J2. Approach và phase ID **giống hệt** `four_intersection_v1`, nên ROI, firmware và vision không phải sửa. Có ghi luồng xe J1_W_IN → J2_W_IN và J2_E_IN → J1_E_IN. Nên dùng file này trên mọi máy khi chạy phần cứng (G4) |
| `contracts/schemas/health.json` (bắt buộc `service`, `status`) | Health của ESP32 đã khớp. Hiện chỉ `ControlGateway` validate theo schema này |
| `src/control/gateway.py` (`ControlGateway`) | Lớp lọc an toàn đặt trước controller. **Graph-control chưa dùng**, chỉ có trong test (G5) |
| `services/api/main.py`: trạng thái camera/actuator cho dashboard | Có 2 lỗi khi chạy với ESP32 (G2, G3) |
| `services/vision/demo_video_pipeline.py` | Demo offline: file video → YOLO → video có chú thích + JSON, có thể phát telemetry. Dùng client_id riêng nên không đá service chính, nhưng **đừng chạy cùng lúc** với service vision (2 nguồn telemetry cho cùng một nút) |
| `services/vision/models/yolov8n.onnx` (12,3 MB, nằm trong git); `config.py` lấy file này làm mặc định khi không đặt `DETECTION_MODEL_PATH` | Trên Pi, `.env.rpi` đặt rõ model nên không đổi gì. Nhưng nếu chạy tay mà quên `set -a; . ./.env.rpi; set +a`, service giờ chạy **YOLOv8n 640 COCO**, không còn chạy motion baseline như F29 ghi |

### 0.2 Luồng điều khiển đèn đã được viết chưa?

**Có, đủ mọi mắt xích.** Hôm nay cả vòng được chạy thử lần đầu; trước đây mới test từng đoạn riêng:

```
camera → services/vision (Pi) → telemetry/{J1,J2} → services/graph-control (max_pressure | edgeflow)
       → control/{J}/command → ESP32 (vàng 3 s, đỏ 2 s, min/max green, watchdog 5 s → fallback 15 s/pha)
       → control/{J}/ack + health/{J} → vision lấy pha thật (F30) · API/dashboard hiển thị
```

| Mắt xích | Code | Đã kiểm tới đâu |
|---|---|---|
| Vision: 2 nút, 1 camera, ROI, pha thật | `services/vision` (F14, F26, F27, F30) | Mac và Pi giả. **Chưa** chạy với camera thật |
| Ra quyết định | `services/graph-control/main.py` | Hôm nay, chạy process thật trong vòng kín |
| Firmware | `src/hardware/firmware/esp32_signal_controller.ino` | Build được; logic kiểm qua ESP32 ảo. **Chưa** chạy trên board |
| API / dashboard | `services/api` | Hôm nay: trạng thái từng nút. Chưa mở giao diện React |

Cách kiểm: chạy vòng kín trên Mac với một Mosquitto riêng và 2 ESP32 ảo (`esp32_simulator.py`, theo đúng luật của firmware). Graph-control và API chạy đúng code của repo, topology `tabletop_j1_j2_v1`. Bảng dưới chấm bằng `flow_report.py` (F31):

| Lần | Nguồn telemetry | Controller | Kết quả |
|---|---|---|---|
| 1 | Pi giả `ns_heavy`, 120 s | edgeflow | **PASS**. Mỗi nút: 120 telemetry → 120 lệnh, 0 REJECTED, không vào fallback; vào fallback đúng 5 s sau khi nguồn dừng. Đổi pha ACCEPTED → APPLIED trong 5,01 s. NS (đông xe) xanh ~95 s, EW ~12 s. Pha trong telemetry khớp ESP32 116/116 |
| 2 | Pi giả `camera_lost`, 45 s | edgeflow | **FAIL (G1)**: cả 45/45 bản tin confidence 0 đều được trả bằng lệnh NS. ESP32 không vào fallback |
| 3 | Service vision thật, video tổng hợp, `yolo11n.onnx`, 5 fps, 60 s | max_pressure | **PASS**. Mỗi nút 59 telemetry, pha khớp 59/59, health của vision có `phase_source` = `esp32_health` cho J1 và J2 |
| 4 | Service vision thật, nguồn video hỏng, 25 s | edgeflow | **FAIL (G1)**: 0 frame, telemetry không có approach nào, nhưng graph-control vẫn gửi 24 lệnh NS |

Ở lần 3, model COCO không thấy xe nên mọi hàng đợi bằng 0. `max_pressure` khi hòa thì giữ pha đầu (NS) cho tới khi ESP32 tự cắt ở max green 60 s, nên EW chỉ được 5 s mỗi chu kỳ. **Demo bằng model chưa fine-tune sẽ trông như vậy** (O3).

### 0.3 Chỗ hở tìm ra (G1–G7)

G1–G3, G5 và phần `.gitignore` của G7 nằm trong phần của người khác, nên **chưa sửa**. Đề xuất bên dưới để gửi cho đội.

| # | Ở đâu | Vấn đề | Hậu quả | Đề xuất |
|---|---|---|---|---|
| G1 | `services/graph-control/main.py`, `on_message` | Không xét `confidence`. Telemetry không có approach, hoặc mọi approach có confidence 0, vẫn được đưa vào controller và sinh lệnh | Khi rút camera, đèn bị điều khiển theo số 0: NS giữ tới max green (45–60 s), EW 5 s mỗi chu kỳ. Fallback 15 s/pha của ESP32 **không bao giờ chạy**. Trái plan: thiếu dữ liệu thì báo thiếu, không ra quyết định trên số bịa. Hàng "Lỗi cố ý: rút camera" ở mục 4 sẽ không đạt | Trước `compute_command`: nếu `not approaches or all(confidence <= 0)` thì bỏ nút đó khỏi `network_state`, không gửi lệnh, log 1 lần. ESP32 tự vào fallback sau 5 s. `ControlGateway` của baolam đã dùng đúng điều kiện này. Sửa khoảng 10 dòng |
| G2 | `services/api/main.py`, `compute_node_device_health` | `safe_stop = ... or clearance != "GREEN"` | Mỗi lần đổi pha bình thường (vàng + đỏ 5 s), bản health nào rơi vào lúc chuyển pha cũng làm dashboard báo actuator `SAFE_STOP` và nút `ACTUATOR_FAULT`. Đo được ở lần 1: 10/60 bản health (17%), tức **gần như lần đổi pha nào cũng nháy lỗi** | Chỉ coi là safe-stop khi `safe_stop` là true hoặc `status == "SAFE_STOP"`. Vàng/đỏ hiển thị riêng |
| G3 | `services/api/main.py` | Tuổi heartbeat của ESP32 tính từ `timestamp_ms` do chính ESP32 gửi (giờ SNTP), so với giờ laptop, timeout 6 s | ESP32 lấy giờ từ Pi mà Pi sai giờ (RTC không pin, hội trường không có internet) thì dashboard báo `HEARTBEAT_LOST` mãi | API tính theo giờ nhận bản tin, như đã làm cho telemetry (`_ingested_at_ms`). Trong lúc chờ sửa: **không** đặt `-D NTP_SERVER` cho ESP32 (khi đó health không có `timestamp_ms` và API dùng giờ của nó), hoặc chỉnh giờ Pi theo laptop trước khi demo |
| G4 | Cấu hình | Laptop `.env`, `.env.rpi` và compose đều mặc định `four_intersection_v1` (J1–J4) | Dashboard hiện J3/J4 "chờ telemetry"; controller coi J3/J4 là hàng xóm không có dữ liệu | Đặt `EDGEFLOW_TOPOLOGY=tabletop_j1_j2_v1` ở **cả** laptop `.env` lẫn `.env.rpi`. Đã sửa `.env.rpi.example` (F32) |
| G5 | `src/control/gateway.py` | Đã viết nhưng không nối vào service. Nếu nối nguyên trạng: (a) J1 cần trạng thái mới của J2 vì có luồng J1_W_IN → J2, nên khi chỉ 1 nút có camera thì **cả hai nút đều không nhận lệnh**; (b) so `timestamp_ms` của Pi với giờ laptop, lệch quá 3 s là bỏ hết telemetry; (c) bỏ lệnh trong lúc ESP32 đang chuyển pha, có thể làm ESP32 thoáng vào fallback | Bán kết: không nối, chỉ lấy điều kiện của G1. Muốn nối thì phải xử lý (a)–(c) trước |
| G7 | `.gitignore` của `e422ce7`: `models/*`, chỉ chừa `.gitkeep` | `models/SHA256SUMS` (F24, vốn định cho vào git) giờ bị ignore | Không commit được SHA256SUMS cho cả đội. `sync_to_pi.sh` lấy file theo git nên **không gửi SHA256SUMS lên Pi**; trên Pi, `sha256sum -c` và bước kiểm model của `preflight.sh` sẽ hỏng | Đã vá phía script (F33). Còn lại, cần đội đồng ý: thêm `!models/SHA256SUMS` vào `.gitignore` |
| G6 | Quyết định 16/10: chỉ 1 camera | Camera gắn trên trụ của một nút chỉ thấy một ngã tư | Nút kia không có telemetry nên không nhận lệnh, chạy fallback cố định 15 s/pha. **Không thể hiện được phối hợp 2 nút**, vốn là điểm chính của đề tài | (a) Đặt camera ở vị trí bao quát cả 2 ngã tư; code đã hỗ trợ (`VISION_NODE_IDS=J1,J2` + ROI, F14). (b) Hoặc chấp nhận, và trình bày nút kia là "chạy chu kỳ cố định an toàn khi không có quan sát" |

### 0.4 Đã làm thêm (phạm vi của Hiển, chưa commit)

| # | Thay đổi |
|---|---|
| F31 | `src/hardware/demo/flow_report.py`: chấm một lần chạy từ log `mosquitto_sub -v -F '%U %t %p'`, 8 check mỗi nút (telemetry, commands, acks, switch_timing, fallback, blind_commands, phase_agreement, device_status) kèm thời gian xanh của từng pha; `--json` để lưu làm bằng chứng. `closed_loop_rehearsal.sh`: dựng cả vòng trên laptop bằng 2 ESP32 ảo và graph-control thật, chạy xong thì gọi `flow_report.py`. 16 test mới (`tests/unit/test_demo_flow_report.py`). Shellcheck sạch, chạy được trên bash 3.2 của macOS, không để lại process. Chạy trên log của 4 lần ở 0.2: lần 1 và 3 PASS, lần 2 và 4 FAIL đúng ở `blind_commands`. Hướng dẫn trong `src/hardware/demo/README.md` |
| F32 | `.env.rpi.example`: `EDGEFLOW_TOPOLOGY=tabletop_j1_j2_v1`, kèm ghi chú rằng laptop phải đặt cùng giá trị |
| F33 | `infra/rpi/sync_to_pi.sh` (G7): gửi thẳng `models/*.onnx` và `models/SHA256SUMS`, chỉ khi file bị git ignore, nên không bao giờ gửi trùng. Đã kiểm danh sách file: 405 file, có SHA256SUMS và 4 model, không file nào trùng, không có `.env.rpi`/`secrets.ini`. Shellcheck sạch. Chưa chạy lại với Pi thật |

### 0.5 Thứ tự còn lại (bán kết 19–24/10)

1. Nạp ESP32 J1/J2, rồi `laptop_command_test.py test J1 J2` và `verify_trace.py` (KE_HOACH_TOI_NAY.md, mục B–C).
2. Pi: làm theo mục 8.
3. Laptop: `.env` có `EDGEFLOW_TOPOLOGY=tabletop_j1_j2_v1`, chạy `docker compose --profile hardware up -d`. (Từ 19/10, chưa commit: actuator ảo không còn trong profile `hardware`, không cần `docker compose stop actuator`.)
4. Vòng kín thật: ghi `mosquitto_sub -v -F '%U %t %p' -t 'edgeflow/v1/#'` suốt buổi. `flow_report.py --nodes J1,J2` phải PASS. Nếu giữ phương án 1 camera (G6), chỉ đưa vào `--nodes` nút có camera.
5. Gửi G1–G3 cho baolam. Khi G1 chưa sửa, thử "rút camera" sẽ FAIL ở `blind_commands`. Đó là lỗi đã biết; ghi trung thực vào báo cáo.

### 0.6 Kiểm tra sẵn sàng deploy, 18/10 tối (HEAD `9ff2b4d` = `origin/main`)

- **Git:** F18–F33 và bộ `src/hardware/demo/` đã vào `main` (Hiển, 18/10) và đã push; mô tả "chưa commit" ở trên đã cũ. Chưa commit: `video_source.py` (phát video đúng fps, lặp) + test, và phần ghi ở dưới.
- **Test:** unit + integration 371 test, 0 fail, 5 skip (thiếu SUMO, gymnasium). `test_suite_also_covers_the_watchdog_when_asked` fail 1 lần trong lần chạy gộp đầu, pass 6 lần sau: nhiều khả năng nhạy thời gian, chưa chứng minh. Firmware J1/J2 build SUCCESS (flash 777 389 B). `docker compose config` hợp lệ cho cả 2 file compose; **chưa build/chạy image** (daemon Docker tắt, đĩa còn ~8 GB).
- **Model "đã sẵn sàng" của đội: không có trong git.** Mọi nhánh remote và toàn bộ lịch sử chỉ có `services/vision/models/yolov8n.onnx` = YOLOv8n COCO gốc (80 lớp). Chấm trên video kiểm: 1/3604 xe (recall 0%). Nếu đội có model riêng thì nằm ngoài git (Drive/máy cá nhân): cần xin file và chạy `score_any.py` (xem README video_demo).
- **Đã làm:** huấn luyện `yolo11n_sa_ban.onnx` 1 lớp (precision 0,988, recall 0,990 trên video kiểm; chi tiết ở README video_demo), ghi sha256 vào `models/SHA256SUMS` (5/5 khớp). Thêm `services/vision/rois/rois_video_1280x720.json`, `data/demo_video/video_demo_150s.mp4` (chưa commit, 10 MB: cân nhắc có đưa vào git hay chỉ để `sync_to_pi.sh` gửi), khối "video-file demo" cuối `.env.rpi.example`, và `preflight.sh` hiểu chế độ video (không đòi camera/picamera2/focus, FAIL nếu thiếu file video). Laptop `.env` đã đặt `EDGEFLOW_TOPOLOGY=tabletop_j1_j2_v1` (G4).
- **Vòng kín với service vision thật đọc video demo** (edgeflow, 90 s): PASS 16/16. Với COCO của đội thì mọi hàng đợi bằng 0 (O3).
- **Chưa kiểm được (cần phần cứng):** mọi thứ trên Pi 5 thật (FPS/độ trễ model, `setup_pi.sh`, systemd, preflight), 2 ESP32 thật cùng lúc trong vòng kín, dashboard React với dữ liệu thật, `docker compose --profile hardware` trên laptop. G1–G3, G5 vẫn mở (thuộc phần của baolam).
- **Cấu hình mạng:** `src/hardware/secrets.ini` đang trỏ WiFi "Bep" và broker 192.168.1.11 (mạng nhà). Hội trường sẽ khác: phải sửa `secrets.ini` và nạp lại 2 board, và `MQTT_HOST` trong `.env.rpi`.

### 0.7 Rà toàn bộ luồng và sửa nốt, 19/10 (HEAD vẫn `9ff2b4d`, remote không có commit mới)

**Git:** `origin/main` = `9ff2b4d`. Nhánh `feat/yolo-vision-mqtt` (Thịnh, 15/10) chưa merge, nhưng nội dung đã nằm trên `main` qua `e422ce7`, bản trên `main` mới hơn. Nhánh `rl_implementation` (Phúc) chưa merge, không liên quan demo. Hiển quyết: **sửa cả code của baolam (api, graph-control, dashboard, compose), để chưa commit** cho baolam duyệt; demo dùng **`edgeflow`**; chưa commit gì.

**Lần đầu chạy đúng đường deploy của laptop:** `docker compose --profile hardware build` + `up -d` (4 image build được), service vision chạy native đọc video demo bằng `yolo11n_sa_ban.onnx` (đóng vai Pi), 2 ESP32 ảo, dashboard mở bằng Chrome (Playwright).

| Lần | Nội dung | Kết quả |
|---|---|---|
| run1 (trước khi sửa) | Docker, max_pressure, video, 150 s | PASS 16/16. Nhưng dashboard: **7/20 mẫu báo `ACTUATOR_FAULT`** khi ESP32 vàng/đỏ (G2); mở lần đầu vẽ 4 nút `four_intersection_v1`; khung vision ghi cứng "LIVE 30 FPS YOLOv8 640x480"; ô "phần cứng" thật ra là độ trễ trình duyệt → API |
| run2 (sau khi sửa) | Docker, **edgeflow**, video, 150 s | PASS 16/16, 296/296 lệnh `controller: edgeflow`, đổi pha 5,01–5,09 s, pha khớp 133/133 và 135/135. ESP32 chỉ từ chối 2 lệnh/nút (max_pressure: 44 và 35, đều do min green). **Dashboard 0/60 mẫu có badge lỗi** |
| run3b | Docker, J1 mất camera 30–60 s, đổi policy lúc 15 s và 75 s | PASS 16/16. J1: 30 telemetry mù → **0 lệnh**, ESP32 vào fallback lúc 35,3 s; API báo `CAMERA_FAULT` + actuator `FALLBACK`; J2 vẫn thích ứng. Lệnh đổi sang `fixed_time` từ 17,2 s, về `edgeflow` từ 78,0 s |

**Đã sửa (chưa commit):**

| Ở đâu | Sửa gì |
|---|---|
| `services/graph-control/runtime_guards.py` (mới) + `main.py` | **G1**: telemetry không có approach hoặc mọi confidence = 0 thì không vào controller, bỏ khỏi `network_state`, không gửi lệnh, log 1 lần mỗi đợt → ESP32 tự vào fallback sau 5 s. **Policy chạy thật**: nếu đặt `CONTROL_POLICY_URL` (compose đặt sẵn `http://api:8000/api/v1/control/policy`), graph-control hỏi API mỗi 2 s và đổi controller ngay khi dashboard bấm "Apply Policy"; build lỗi hoặc API chết thì giữ controller cũ. Không đặt thì như cũ (script rehearsal không đổi) |
| `services/api/main.py` | **G2**: chỉ `safe_stop=true` hoặc `status=SAFE_STOP` mới là safe-stop; vàng/đỏ là chuyển pha bình thường. **G3**: tuổi heartbeat tính theo giờ API nhận (`_ingested_at_ms`). LWT `OFFLINE` của ESP32 → `HEARTBEAT_LOST` ngay. `FALLBACK_AUTONOMOUS` → actuator/nút `FALLBACK`. Nút chưa có telemetry: confidence 0, tốc độ 0 (trước là 1,0 và 13,89 m/s bịa). `GET /api/v1/control/policy`; policy chỉ nhận `edgeflow/max_pressure/max_queue/fixed_time` (RL cần file model, trước đây nhận rồi chỉ đổi nhãn). `/health` có `applied_controller` lấy từ trường `controller` trong lệnh. `/network/state/{node}` kèm `vision_health` |
| `services/dashboard/src` | Overview mở theo topology của API; badge `FALLBACK 15s`; placeholder không còn "ONLINE/13,9 m/s/100%". Header và Control Panel hiện controller đang chạy thật. Khung vision lấy fps, model, inference p50 từ health của vision và ghi "video chú thích ghi sẵn". Ô phần cứng = tuổi heartbeat ESP32. Bỏ "100% Interlocked", "Safety Compliance 100% (0 conflicts)" (ghi cứng) → "Interlock trên ESP32 (vàng 3 s + đỏ 2 s)". Chế độ ROI hết hiện số xe giả `|| 3.2`. Khóa (disabled, có ghi chú) các điều khiển không tới được đèn: min/max green, engine, thời gian vàng/đỏ, 3 nút Normal/Chớp vàng/All-red. Bỏ lựa chọn PressLight RL |
| `docker-compose.yml` | `actuator` ảo **không còn trong profile `hardware`**: không cần `docker compose stop actuator` nữa. Thêm `CONTROL_POLICY_URL` cho graph-control |
| `.env` laptop, `.env.rpi.example` | `EDGEFLOW_CONTROLLER=edgeflow` |
| `services/vision/main.py` | Health có thêm `model` (tên file) |
| `services/vision/annotate_video.py` (mới) | Video chú thích (box, ROI, số xe/nhánh) bằng đúng detector + ROI + model của service → `artifacts/yolo_demo_annotated.mp4` (H.264, dashboard phát được). Đã tạo bản 60 s (gitignored) |
| `src/hardware/set_network.sh` (mới) | Đổi mạng bằng 1 lệnh: ghi `secrets.ini` (lấy IP laptop từ route mặc định), build J1+J2, in bước nạp board và dòng `MQTT_HOST` cho Pi. Từ chối SSID/mật khẩu có dấu nháy. Đã kiểm SSID có dấu cách nằm đúng trong `firmware.bin`, rồi trả `secrets.ini` thật về nguyên trạng và build lại |
| `src/hardware/demo/pi_fake_telemetry.py` | client_id theo danh sách nút: 2 Pi giả (J1 mất camera, J2 bình thường) không đá nhau khỏi broker (lần đầu run3 bị 89 lần) |
| `models/` (gitignored) | `yolo11n_sa_ban_416.onnx`, `_320.onnx` từ cùng `best.pt`, sha256 trong `SHA256SUMS` (7/7 OK). Video kiểm: 640 = P 0,988 / R 0,990 / 36,5 ms; **416 = 0,963 / 0,990 / 19,4 ms**; 320 = 0,982 / 0,962 / 13,4 ms (ms đo trên Mac, chỉ so tương đối). `.env.rpi.example` ghi sẵn phương án 416 |

**Test:** 397 test, 0 fail, 5 skip (thiếu SUMO/gymnasium); `make contracts` 8/8. Test mới: `test_api_device_health.py` (13), `test_graph_control_guards.py` (11), `test_vision_annotate_video.py` (2). Dashboard dev server: "Compiled successfully" (không cảnh báo). Firmware J1/J2 build SUCCESS, flash 777 389 B.

**Kiểm 3 ảnh đội gửi (câu trả lời AI của thành viên):**

- "MOG2 là cơ chế dự phòng khi model không bắt được box": **sai**. MOG2 chỉ chạy khi không cấu hình model (`detector.py` dòng 38: "no silent motion fallback").
- "Hạ `CONFIDENCE_THRESHOLD` xuống 0,25–0,30 là đủ": **sai với video này**. YOLOv8n COCO: ngưỡng 0,25 recall 0,4%, ngưỡng 0,1 recall 2,4%. Ngưỡng là biến môi trường, không sửa `config.py`.
- "Fine-tune 1 lớp thì nhanh hơn trên Pi": gần như không. Thời gian nằm ở backbone; đổi cỡ đầu vào (416) mới nhanh gấp ~2.
- "Điền IP laptop vào firmware và `config.py` của Pi": thực tế là `secrets.ini` (giờ dùng `set_network.sh`) và `MQTT_HOST` trong `.env.rpi`.
- "Dựng camera trên trụ, kéo ROI bằng `roi_calibrate.py`": không còn dùng; demo đọc video, ROI có sẵn `rois_video_1280x720.json`.
- "Firmware: vàng 3 s, đỏ 2 s, safe-stop GPIO4, watchdog 5 s → 15 s/pha": **đúng**, và đã kiểm trên 2 board thật từng cái (18/10).
- "Toàn bộ 100% sẵn sàng": trước hôm nay thì chưa (G1, G2, dashboard ghi cứng số, actuator ảo trùng ACK). Giờ phần mềm đã chạy đủ vòng trên laptop; phần cứng thật vẫn chưa chạy chung.

**Còn lại, chỉ làm được khi có phần cứng:**

1. Pi 5: `sync_to_pi.sh` → `setup_pi.sh --service` → `.env.rpi` (bỏ dấu `#` khối video demo, `MQTT_HOST`) → `preflight.sh` → đọc dòng `Runtime: processed … fps` trong `journalctl -u edgeflow-vision`. Dưới ~3 fps thì đổi sang model 416.
2. Cắm cùng lúc 2 ESP32 + đèn LED, `laptop_command_test.py test J1 J2`, rồi vòng kín thật ghi `mosquitto_sub -v -F '%U %t %p' -t 'edgeflow/v1/#'` và chấm `flow_report.py --nodes J1,J2`.
3. Mạng hotspot: iPhone bật "Maximize Compatibility" (ESP32 chỉ thấy 2.4 GHz), Android chọn băng 2.4 GHz; tên hotspot không có dấu nháy (tên iPhone mặc định thường có `'`). Kết nối laptop vào hotspot → `bash src/hardware/set_network.sh "<SSID>" "<pass>"` → nạp J1, J2 → Pi vào hotspot (`sudo nmcli dev wifi connect …`), sửa `MQTT_HOST` → `sudo systemctl restart edgeflow-vision`. IP laptop đổi thì chạy lại.
4. G5 (`ControlGateway`) vẫn chưa nối, cố ý: G1 đã lấy đúng điều kiện cần cho bán kết.

**Kiểm lại chiều 19/10 (Docker đang chạy đúng code working tree, `cmp` từng file):**

| Lần | Kịch bản | Kết quả |
|---|---|---|
| run5 | vision thật đọc video 150 s + 2 ESP32 ảo, `edgeflow` | PASS 16/16; vision 9,4–10 fps, inference p50 ~35 ms (Mac); API 59/59 mẫu `ONLINE/ACTIVE/ACTIVE` cả J1, J2 |
| run6 | J1 mất camera 30–60 s + đổi `fixed_time` → `edgeflow` qua API | PASS 16/16; CAMERA_FAULT sau 2,6 s, ESP32 FALLBACK ở 35,1 s, hồi lại 63 s; đổi thuật toán có hiệu lực ≤ 3,3 s / ≤ 4,4 s |
| run7 | bấm "đổi pha tay" qua `POST /api/v1/control/override` | J1 (đang xanh lâu): vàng 3 s → đỏ 2 s → xanh hướng mới sau 5,1 s, `edgeflow` lấy lại quyền theo luật bình thường. J2 ("Force Priority"): **ESP32 REJECTED** "Min green time not met (0.1s < 10.0s)" nhưng API trả `ACCEPTED` và dashboard vẫn báo thành công |

**Nút đổi pha tay: đã sửa (Hiển chọn "sửa đầy đủ", 19/10; chưa commit).** Lỗi cũ: firmware coi `manual_override` như lệnh thường; dashboard gửi `min_green_s=10` nên phần lớn lần bấm bị ESP32 từ chối, API trả `ACCEPTED` trước khi ESP32 trả lời, `fetch(...).catch(() => {})` nuốt lỗi, đếm ngược vàng/đỏ chỉ là hẹn giờ trên trình duyệt, và `edgeflow` lấy lại pha sau 5 s. Sửa (firmware giữ nguyên mọi luật an toàn):

- `services/graph-control/runtime_guards.py` `ManualOverrideHold`: graph-control nghe thêm `control/+/command`; thấy lệnh `cmd-override-*` của API thì thay quyết định của controller bằng pha được ép, gửi lại mỗi giây (`gc-hold-*`, min green 5 s) cho tới khi ESP32 báo pha đó xanh đủ `MANUAL_OVERRIDE_HOLD_S` (mặc định 15 s, đặt trong `docker-compose.yml` cho cả api và graph-control); quá 25 s chưa xanh thì bỏ. Lệnh tay đi trước cả BlindNodeGate, có giới hạn thời gian.
- API: kiểm node/pha theo topology (404/400), MQTT chưa nối hoặc publish lỗi thì 503; trả `SENT`, không tự ghi ACK `ACCEPTED` thay ESP32; `track_override_ack` + `override_view` → `manual_override` trong `/api/v1/network/state/{node}` (SENT → WAITING kèm lý do ESP32 → CLEARING → APPLIED còn x s → ENDED / NOT_APPLIED). Mặc định `min_green_s` 5.
- Dashboard: `src/utils/manualOverride.js`; trang J1/J2 và Control hiện đúng trạng thái đó, khóa nút khi lệnh đang chạy, báo lỗi API; nút đổi tên "Force N-S Priority". Kèm: một luật "Attention" chung (hàng chờ > 12 xe hoặc không ONLINE, bỏ luật tốc độ < 5 m/s); ô nguồn dữ liệu ghi "Live MQTT telemetry"; khung J1 đổi thành "Áp Lực Hàng Chờ" và "Max-pressure sẽ chọn (tham khảo…)"; banner sự cố bỏ câu "Control Gateway đã tự động khóa lệnh" (G5 chưa nối) và nói đúng hành vi fallback.
- Test: 412 test, 0 fail, 5 skip (thêm `tests/unit/test_api_manual_override.py`, 5 test hold trong `test_graph_control_guards.py`, sửa `test_trigger_emergency_override_endpoint` theo hành vi mới); `make contracts` 8 passed; dashboard "Compiled successfully".
- Kiểm vòng kín: run8 PASS 16/16. J1 (NS đã xanh lâu): nhận ngay, EW xanh sau 5,0 s, giữ 15,0 s, `edgeflow` trở lại ở +21 s. J2 "Force Priority" bấm ngay sau một lần đổi pha: ESP32 từ chối 6 lần (min green), graph-control gửi lại, nhận ở +5,9 s, xanh ở +11,0 s, giữ 15 s (lần trước lệnh này mất hẳn). Bấm thật trên trang J2 (Playwright): banner "Đang chuyển" → "đang xanh theo lệnh tay, giữ thêm 11,5 s" → "Đã hết ưu tiên". run9: bấm "Force N-S Priority" trên trang Control, J2 từ EW sang NS, giữ 15 s; Overview "All Normal".
- Ghi chú: test API mở MQTT với client id `api-telemetry-ingest` giống container API, nên đừng chạy pytest khi đang chạy vòng kín trên stack Docker (broker đá container API ra).

**Trình tự ngày demo (laptop):** `open -a Docker` → `docker compose --profile hardware up -d` (không còn bước stop actuator) → mở `http://localhost:3000` → Pi bật (systemd tự chạy) → cắm nguồn 2 ESP32 → kiểm dashboard J1/J2 `ONLINE`, header "EdgeFlow AI". Build image ở nhà trước: hội trường có thể không có internet. Muốn so thuật toán trực tiếp: Control & Tuning → chọn `fixed_time` → Apply (đèn đổi kiểu sau ~2 s), xong chọn lại `edgeflow`.

---

## 1. Kiến trúc demo (Mode 2: 3 tầng)

```
               Router Wi-Fi 2.4 GHz (LAN riêng, ví dụ 192.168.1.0/24, tắt client isolation)
     ┌──────────────────────┬─────────────────────────┬──────────────────────┐
     │ LAN/Wi-Fi            │ LAN (khuyến nghị)       │ Wi-Fi 2.4 GHz        │ Wi-Fi 2.4 GHz
┌────┴─────────────┐  ┌─────┴──────────────────┐  ┌───┴──────────────┐  ┌────┴─────────────┐
│ Laptop .100      │  │ Raspberry Pi 5 .101    │  │ ESP32 J1         │  │ ESP32 J2         │
│ mosquitto :1883  │◄─┤ vision (native,systemd)│  │ firmware J1      │  │ firmware J2      │
│ graph-control    │  │ Camera Module 3 Wide   │  │ 4 module đèn     │  │ 4 module đèn     │
│ api :8000        │  │ chrony (NTP cho LAN)   │  │ safe-stop GPIO4  │  │ safe-stop GPIO4  │
│ dashboard :3000  │  └────────────────────────┘  └──────────────────┘  └──────────────────┘
└──────────────────┘
telemetry/{J1,J2} ──► graph-control ──► control/{J1,J2}/command ──► ESP32 ──► control/{J}/ack, health/{J}
```

**IP cố định qua DHCP reservation trên router:**

- Laptop: `192.168.1.100`. Trùng mặc định của `MQTT_HOST` trong `.env.rpi.example`.
- Pi: `192.168.1.101`.
- ESP32 dùng DHCP thường.

Nếu router mặc định là `192.168.0.x`, có hai cách: đổi dải LAN của router, hoặc sửa `MQTT_HOST` và `secrets.ini` cho khớp.

---

## 2. Rà soát repo: những gì chặn việc deploy

### 2.1 Đã sửa trên nhánh `deploy/hardware-prep`

| # | Vấn đề (file trên `main`) | Hậu quả nếu deploy nguyên trạng | Đã sửa |
|---|---|---|---|
| F1 | `services/vision/video_source.py`: `picamera` được map vào `cv2.VideoCapture(0)` | Trên Pi 5, OpenCV không đọc được camera CSI qua V4L2. Service vẫn chạy nhưng **mọi frame đều lỗi**, nên chỉ phát hàng đợi 0 với confidence 0 | Thêm `Picamera2VideoSource`, chọn khi `VIDEO_SOURCE=picamera`/`csi`. Khóa `LensPosition` (`CAMERA_LENS_POSITION`) và chống nhấp nháy 50 Hz (`CAMERA_FLICKER_PERIOD_US=10000`). Nếu thiếu picamera2 thì báo lỗi rõ ràng, không lặng lẽ fallback |
| F2 | `services/vision/main.py` không có argparse, trong khi README/DEVELOPMENT dạy `python main.py --video 0 --mqtt-host … --node-id J1` | Các flag **bị bỏ qua mà không báo gì**: service kết nối `localhost` và đọc `synthetic`, người chạy tưởng đã dùng camera thật | Thêm `--video --mqtt-host --mqtt-port --node-id --model --lens-position`. Mỗi flag ghi đè biến môi trường tương ứng (trả về bản sao settings, không sửa object gốc) |
| F3 | Firmware: PubSubClient buffer mặc định 256 byte | ACK ACCEPTED dài ~255 byte, sát giới hạn. Các ACK có `reason` dài hơn **publish thất bại mà không báo gì**, nên mất bằng chứng ACCEPTED/APPLIED | `setBufferSize(1024)`. Khi publish lỗi thì in `ERROR` ra serial |
| F4 | Firmware: thả nút safe-stop xong không ghi lại đầu ra | Sau khi thả nút, đèn có thể đứng ở trạng thái nhấp nháy dở (cả hai hướng tắt hoặc cùng vàng), **không có đèn đỏ**, cho tới lần chuyển pha kế tiếp | Đọc nút có chống dội. Khi bấm: báo FAILED cho lệnh đang chờ, gửi health `SAFE_STOP` và tiếp tục duy trì MQTT. Khi thả: vào ALL_RED 2 s rồi mới xanh lại, đúng yêu cầu "restart in a defined state" của plan |
| F5 | Firmware: "watchdog" chỉ là timeout mạng. Không có watchdog phần cứng | Vòng lặp treo (Wi-Fi, MQTT) thì board đứng im, đèn giữ nguyên trạng thái cuối | Thêm task watchdog 10 s. Khi reset, board khởi động ở ALL_RED rồi chuyển sang NS GREEN |
| F6 | Firmware: thử kết nối MQTT ở **mọi vòng lặp**, mỗi lần có thể chặn vài giây | Khi broker chết, pha vàng và all-red bị kéo dài, nên output trace không còn đúng 3 s / 2 s | Thử lại mỗi 2 s và **chỉ thử khi đang GREEN**. Thêm LWT `OFFLINE` trên topic health |
| F7 | Firmware: `max_green` nhận vào nhưng không bao giờ được áp dụng. `min_green` cho phép controller gửi 0 | Hướng còn lại có thể bị đỏ mãi. Optimizer rút ngắn được thời gian an toàn, trái plan ("device configuration owns mandatory safety timing") | Kẹp min/max về giới hạn của thiết bị (min ≥ 5 s, max ≤ 60 s). Hết max green thì thiết bị tự chuyển pha |
| F8 | Firmware: `expires_at_ms` được so với `millis()` và đọc vào biến 32 bit | Khi controller bắt đầu gửi epoch ms, giá trị bị tràn và lệnh hợp lệ có thể bị EXPIRED ngẫu nhiên | Đọc bằng `uint64_t`. Chỉ xét hết hạn khi đồng hồ đã đồng bộ qua SNTP (`NTP_SERVER`, mặc định là broker). ACK có `timestamp_ms` theo UTC kèm `uptime_ms` |
| F9 | Firmware: `target_phase_id` lạ bị âm thầm coi là pha NS. Fallback gửi ACK APPLIED với id giả `local_fallback_tick`. Watchdog được reset kể cả khi JSON lỗi | Sai ngữ nghĩa ACK, làm nhiễu bằng chứng | Chỉ chấp nhận `<NODE>_PHASE_NS` hoặc `<NODE>_PHASE_EW`, còn lại REJECTED. Chuyển pha trong fallback không gửi ACK. Chỉ reset watchdog khi nhận lệnh hợp lệ cho đúng nút |
| F10 | Không có cách build firmware tái lập. J1 và J2 phải sửa tay `#define`. SSID và broker hard-code | Dễ nạp nhầm ID cho board | Thêm `src/hardware/platformio.ini` với 2 env `J1`/`J2`. `secrets.example.ini` → `secrets.ini` (git-ignored) chứa SSID, mật khẩu, broker |
| F11 | Không có bằng chứng timing phía MCU | Plan yêu cầu "MCU or logic-analyzer output traces" | Mỗi lần đèn đổi, firmware in một dòng `TRACE,<millis>,<node>,<ns>,<ew>,<label>` ra serial. Có chốt chặn: nếu có yêu cầu 2 hướng cùng xanh thì ép về đỏ và in `ERROR` |
| F12 | Không có script cài đặt Pi | Cài `opencv-python-headless`/`numpy` bằng pip sẽ đè bản apt mà picamera2 dùng, gây lỗi ABI | `infra/rpi/setup_pi.sh`: cài apt, tạo venv `--system-site-packages`, chỉ pip các gói thuần Python, cấu hình chrony làm NTP cho LAN. Có `infra/rpi/edgeflow-vision.service` (systemd, `Restart=on-failure` với giới hạn số lần khởi động lại, tránh vòng crash vô hạn làm đầy log) |
| F13 | `.env.rpi.example`: `VIDEO_SOURCE=/dev/video0`, model `/models/yolov8n.onnx` (đường dẫn Docker) | Không chạy được với camera CSI | Đổi sang `VIDEO_SOURCE=picamera`, thêm biến camera, model `models/yolo11n.onnx` cho chạy native. `.gitignore` thêm `.env.rpi`, `.venv-pi/`, `.pio/`, `src/hardware/secrets.ini` |
| F14 | **Một camera chỉ phát telemetry cho 1 nút** (O1 cũ). Graph-control chỉ gửi lệnh khi nhận telemetry, nên J2 không bao giờ nhận lệnh | J2 luôn chạy fallback, không có phối hợp 2 nút | `VISION_NODE_IDS=J1,J2` + `ROI_CONFIG_PATH` (file ROI JSON cho từng approach, kiểm tra khớp topology, ghi sha256 vào health). Mỗi frame chỉ chạy detect 1 lần rồi phát telemetry cho từng nút. Nhiều nút mà không có file ROI thì báo lỗi, không dùng lại ROI của J1. Nút không có trong topology cũng báo lỗi, không còn âm thầm lấy nút đầu tiên. Công cụ `services/vision/roi_calibrate.py` gồm `capture` (chụp frame trên Pi), `draw` (vẽ polygon trên Mac), `check` (kiểm tra và xuất ảnh overlay). File mẫu `rois/example_two_nodes_1280x720.json` **chỉ để thử, phải vẽ lại khi có camera thật** |
| F15 | Không có cách kiểm tra tự động log `TRACE` | Bằng chứng timing phải soi bằng mắt | `src/hardware/verify_trace.py <log> --json report.json`: phát hiện 2 hướng cùng xanh, vàng < 3 s, all-red < 2 s, xanh < min green, bỏ qua pha vàng, xanh không qua all-red, thả safe-stop không qua all-red. Có vi phạm thì exit code 1 |
| F16 | `detector.py`: model chỉ được `readNet`, không chạy thử. Trên OpenCV < 4.8, `readNet` vẫn thành công nhưng `forward()` lỗi assertion `shape_utils.hpp … in function 'total'` | Health gửi `HEALTHY` (retained), rồi service **crash ở frame đầu** với thông báo khó hiểu. `DETECTOR_NUM_CLASSES` sai (ví dụ model fine-tune 1 lớp) cũng chỉ lộ ra ở frame đầu | Khi load, chạy 1 lần `forward` trên ảnh rỗng và kiểm số cột output. OpenCV cũ thì báo `RuntimeError` ghi rõ "cần OpenCV ≥ 4.8, dùng Raspberry Pi OS Trixie". Sai số lớp thì báo `ValueError` nêu tên `DETECTOR_OUTPUT_FORMAT`/`DETECTOR_NUM_CLASSES`. Test mới: `tests/unit/test_vision_detector.py` (4 test) |
| F17 | `setup_pi.sh` cài `python3-opencv` từ apt mà không kiểm tra phiên bản. **Bookworm ra 4.6.0**, không chạy được YOLOv8/YOLO11 ONNX (xem mục 7) | Cài xong không báo lỗi gì, service chết khi bật | Script dừng với exit 1 nếu OpenCV < 4.8, kèm hướng dẫn: cài Trixie, hoặc trên Bookworm thì `pip install --no-deps opencv-python-headless==4.10.0.84` (giữ numpy apt cho picamera2). Ghi chú đầu file đổi sang Trixie |
| F18 | `benchmark.py` mở nguồn bằng `cv2.VideoCapture` (phiên 07/10, chưa commit) | Trên Pi 5 **không đo được FPS với camera thật**, vì OpenCV không đọc được camera CSI. Đây chính là việc mở số 3 (đo FPS trên Pi) | Dùng chung `create_video_source` với service: `--source picamera`, `--width/--height`, `--lens-position`. Kết quả ghi thêm `frame_size`, `captured_at_ms` từng frame, `board_model`, nhiệt độ/throttling/điện áp trước và sau khi đo, phiên bản numpy. Camera lỗi thì dừng và báo lỗi |
| F19 | Health của vision: `fps = 1/TELEMETRY_PERIOD_S` (số cấu hình), không có LWT, `cpu_temp_c` = 45,0 giả khi không đọc được (O11 một phần, O12) | Dashboard thấy `HEALTHY` sau khi service đã chết. Số FPS báo cáo không phải số đo | `services/vision/runtime_stats.py`: cửa sổ 30 s gồm FPS thật đã xử lý, p50/p95 của capture/preprocess/inference/postprocess/publish và `age_at_publish_ms` (từ lúc chụp tới lúc publish xong), số frame lỗi. Health retained gửi mỗi 10 s và **mỗi lần kết nối lại**. Trạng thái: `STARTING`, `HEALTHY`, `DEGRADED` (kèm `reason` khi camera mất frame), `OFFLINE` (LWT, hoặc gửi chủ động khi tắt). Phần `hardware` gồm nhiệt độ, cờ `get_throttled` đã giải mã, điện áp USB-C của Pi 5 (`pmic_read_adc EXT5V_V`), load, RAM trống; giá trị nào không đo được thì là `null`. Bắt SIGTERM để `systemctl stop` tắt gọn (nhả camera, gửi OFFLINE). Mỗi chu kỳ in 1 dòng `Runtime: …` ra journal |
| F20 | Telemetry `timestamp_ms` lấy lúc **bắt đầu** vòng lặp, trước khi đọc frame | Lệch giữa thời điểm quan sát và thời gian ghi trong bản tin bằng thời gian chờ camera | `timestamp_ms` = thời điểm chụp frame (`engine.last_frame["captured_at_ms"]`). Camera lỗi thì dùng giờ hiện tại, approach có confidence 0 như cũ |
| F21 | Đặt `DETECTOR_INPUT_SIZE` khác cỡ lúc export (ví dụ dùng `yolo11n_416.onnx` mà vẫn để 640) thì F16 báo **"cần OpenCV ≥ 4.8, dùng Trixie"** | Trên Pi đã chạy Trixie, thông báo này dẫn người đọc đi cài lại OS vô ích (đã tái hiện trên OpenCV 4.10 ngày 07/10: lỗi ở node `Reshape` của attention) | Thông báo theo phiên bản: OpenCV < 4.8 vẫn hướng dẫn nâng OS; từ 4.8 trở lên thì nói rõ "static ONNX chỉ chạy ở imgsz lúc export, kiểm `DETECTOR_INPUT_SIZE=…`". Gợi ý đặt **trước** chuỗi lỗi gốc của OpenCV |
| F22 | Không có cách kiểm tra Pi trước khi chạy | Lỗi cáp camera, sai model, thiếu nguồn, broker không tới được chỉ lộ ra khi service đã chạy | `infra/rpi/preflight.sh` (chỉ đọc, không mở camera stream, không publish): OS Trixie, Pi 5, `get_throttled`, điện áp USB-C, nhiệt độ, dung lượng đĩa, các import của venv, OpenCV ≥ 4.8, `rpicam-hello --list-cameras` (phân biệt `imx708_wide`), service đang giữ camera, `.env.rpi` (nguồn video, khóa nét), sha256 của model so với `models/SHA256SUMS`, **chạy self-test của detector với đúng tham số trong `.env.rpi`**, ROI (`roi_calibrate.py check`, cảnh báo nếu còn dùng file mẫu), TCP tới broker, chrony. In PASS/WARN/FAIL, có FAIL thì exit 1. Shellcheck sạch, chạy được cả bash 3.2 |
| F23 | Không có công cụ thu dữ liệu fine-tune | Ảnh chụp bằng đường khác (rpicam-vid, điện thoại) lệch miền với ảnh service thấy lúc chạy | `services/vision/capture_dataset.py`: chụp qua đúng `Picamera2VideoSource` (cùng cỡ frame, LensPosition, chống nhấp nháy), mỗi phiên một thư mục `<out>/<session>/`, không ghi đè phiên cũ, bỏ frame gần trùng (chênh lệch xám trung bình < `--min-diff`), ghi `session.json` (ghi chú, nguồn, số frame bỏ qua, số lần đọc lỗi). Đúng yêu cầu của plan: chia train/val/test theo phiên |
| F25 | Picamera2 để libcamera tự chọn chế độ sensor. Với đầu ra 1280×720, chế độ gần nhất của Camera Module 3 là **1536×864, crop vùng giữa (768,432)/3072×1728** | Bản Wide 120° mất khoảng 1/3 góc nhìn mỗi chiều, có thể không phủ hết 2 ngã tư. ROI, dataset và benchmark đều bị ảnh hưởng vì cùng đi qua một đường camera | `pick_full_fov_mode`: trong `camera.sensor_modes`, chọn chế độ nhỏ nhất **nhìn toàn bộ sensor** (crop lớn nhất) đạt FPS yêu cầu, tức 2304×1296 binning 2×2 @ 56 fps, rồi truyền `sensor={"output_size", "bit_depth"}`. Không có danh sách chế độ thì giữ mặc định. In chế độ đã chọn ra log. **Chưa kiểm trên camera thật**: buổi đầu so frame của `roi_calibrate.py capture` với `rpicam-still` (luôn đủ góc) |
| F26 | O14: chỉ xử lý 1 frame mỗi `TELEMETRY_PERIOD_S`, `VISION_FPS` không có tác dụng | Không đạt "≥ 5 processed frames per second" của plan. Một frame bỏ sót xe là hàng đợi nhảy theo | Xử lý liên tục, giới hạn bởi `VISION_FPS` (0 = không giới hạn). Mỗi `TELEMETRY_PERIOD_S` gửi 1 bản tin/nút, mỗi trường của approach là **trung vị** trên các frame trong kỳ (`services/vision/telemetry_window.py`). `timestamp_ms` = lúc chụp frame mới nhất. Health có thêm `frames_per_publish`, `age_at_publish_ms` đo theo từng lần publish, và `vision_fps_cap`. Chạy thử trên Mac với `VISION_FPS=5`: xử lý 5,0 fps, telemetry đúng 1 Hz, mỗi bản tin gộp ~5 frame |
| F27 | O10: `confidence = 0.92` gán cứng; graph-control nhân áp lực với giá trị này | Số không đo được lại đi thẳng vào quyết định điều khiển | `confidence` = **tỉ lệ frame trong kỳ được chụp và xử lý thành công**: 1.0 khi camera khỏe (giống SUMO gửi 1.0 và giá trị mặc định của graph-control), thấp hơn khi mất frame, không có approach nào (confidence 0) khi cả kỳ không có frame. Frame xử lý được tự nó mang 1.0, bỏ hẳn 0.92. Đúng tinh thần H3 của plan (xử lý theo chất lượng quan sát) |
| F24 | Chỉ có model 640, chưa biết Pi chạy được bao nhiêu FPS | Nếu 640 < 5 FPS thì phải export lại trên Mac giữa buổi làm việc với Pi | Đã export sẵn `yolo11n_480/416/320.onnx` (cùng `.pt`, cùng lệnh, mục 7b) và kiểm bằng detector của repo trên OpenCV 4.10. `models/SHA256SUMS` (file mới, được git theo dõi; còn `.onnx` vẫn bị ignore) để `preflight.sh` đối chiếu bản trên Pi |
| F28 | Checklist dạy `git clone https://github.com/baolam/vedc-traffic-flow.git` trên Pi, nhưng **repo là private**: API GitHub trả 404, `git ls-remote` không credential thì đòi đăng nhập | Buổi đầu dừng ngay bước 1 ở màn hình đòi username. GitHub không nhận mật khẩu, phải có PAT hoặc SSH key trên Pi. Kể cả clone được thì phần chưa commit vẫn phải chép riêng | `infra/rpi/sync_to_pi.sh` (chạy trên Mac): gửi qua ssh mọi file git theo dõi, file đã sửa, file mới không bị ignore, cộng `models/*.onnx`. Sau đó chạy `sha256sum -c models/SHA256SUMS` trên Pi và ghi `DEPLOYED_FROM.txt` (commit + `git status --short`) làm bằng chứng phiên bản. **Không** gửi `.env.rpi`, `.venv-pi`, dataset; **không** xóa gì trên Pi. Dùng chung 1 kết nối ssh, nên hỏi mật khẩu tối đa 1 lần |
| F29 | systemd đọc `.env.rpi` theo cách riêng: **giữ comment cuối dòng trong giá trị**, nên `CAMERA_LENS_POSITION=2.0 # 50cm` thành chuỗi `2.0 # 50cm`. `preflight.sh` thì tự cắt comment nên vẫn báo PASS. Ngoài ra `main.py` chạy tay **không đọc `.env.rpi`** (config chỉ đọc biến môi trường), nên lệnh chạy tay trong README và ở cuối `setup_pi.sh` chạy **motion baseline** thay cho YOLO | Service crash lúc import, systemd thử lại 10 lần rồi bỏ, trong khi preflight vẫn xanh. Chạy tay thì ra số của motion baseline mà tưởng là YOLO | `preflight.sh` đọc `.env.rpi` đúng như systemd rồi dựng `Settings` của service một lần. Comment cuối dòng: FAIL, nêu số dòng. Sai kiểu (ví dụ `VISION_FPS=10,0`): FAIL, nêu tên biến. Đạt thì in cấu hình service sẽ nhận (nguồn video, nút, broker, model và cỡ). `ENV_FILE` tương đối được đổi thành tuyệt đối. Khi chrony chưa đồng bộ, in giờ của Pi kèm lệnh đặt giờ từ laptop (RTC của Pi 5 không kèm pin, offline có thể khởi động sai giờ). README và `setup_pi.sh` dạy chạy tay bằng `set -a; . ./.env.rpi; set +a` |
| F30 | O7: telemetry của vision luôn gửi `current_phase_id = phases[0]`. Mô phỏng (`EdgeFlowController` thật, ESP32 mô phỏng theo luật của firmware, 10 phút, NS 4 xe/hướng, EW 1 xe/hướng): **NS đông xe chỉ được 101 s xanh, EW vắng xe được 420 s** | Nếu demo bằng `EDGEFLOW_CONTROLLER=edgeflow`, ưu tiên bị đảo ngược. Controller tưởng NS luôn xanh nên điểm thưởng thời gian chờ của EW (`0.06 × tuổi^1.1`) tăng mãi. `max_pressure` không đọc trường này nên không bị ảnh hưởng | Hiển chọn 07/10, không đổi contract. `services/vision/phase_tracker.py`: vision subscribe `edgeflow/v1/health/{node}` của từng nút mà camera thấy và đưa `current_phase` của ESP32 vào `current_phase_id`. Bỏ qua bản tin của nút khác, pha không có trong topology, JSON lỗi. Không có báo cáo trong 15 s (3 kỳ health) hoặc nhận LWT `OFFLINE` thì quay về `phases[0]`, log cảnh báo, và health của vision ghi `phase_source: default` cho nút đó (bình thường là `esp32_health`). Firmware gửi health **ngay khi vào GREEN**, gồm mọi đường: lệnh, hết max green, fallback, thả safe-stop, khởi động. Nhờ vậy vision biết pha mới trong 1 kỳ telemetry thay vì chờ tới 5 s. Với telemetry báo pha thật, cùng mô phỏng cho NS 460 s, EW 60 s |

**Kiểm chứng F28–F29 (07/10, chiều), trên "Pi giả" vì chưa cắm Pi:**

- Môi trường: container `debian:trixie-slim` **arm64** (cùng kiến trúc với Pi 5), `python3-opencv` từ apt (Python 3.13.5, OpenCV 4.10.0, numpy 2.2.4, đúng bản của Trixie). Venv tạo **y như `setup_pi.sh`**, chỉ có 4 gói pip: paho-mqtt 2.1.0, pydantic 2.13.5, pydantic-settings 2.15.0, jsonschema 4.26.0. Lệnh `ssh` được thay bằng shim chạy lệnh trong container. Không có `picamera2`/`vcgencmd`/`rpicam-*` (chỉ có trong kho của Raspberry Pi).
- `sync_to_pi.sh`: **284/284 file trùng từng byte** với Mac (so 2 danh sách sha256), có cả file chưa commit và 4 model. `sha256sum -c` OK. Không có file `._*`. Đồng bộ lần hai vẫn giữ `.env.rpi` và `.venv-pi` trên Pi.
- `preflight.sh`: `.env.rpi` đúng thì PASS và in đúng cấu hình. Comment cuối dòng thì FAIL `line 40: CAMERA_LENS_POSITION='2.0   # 50 cm above the table'`. `VISION_FPS=10,0` thì FAIL `VISION_FPS='10,0': Input should be a valid number`. Self-test model 640 PASS trên OpenCV apt. 3 FAIL còn lại là phần chỉ Pi thật mới có.
- Service, nạp `.env.rpi` như systemd, `--video synthetic`, 2 nút + ROI mẫu, broker trên Mac: mỗi nút 18 bản tin trong khoảng 19 s; health có `model_sha256`, `roi_sha256`; SIGTERM để lại `OFFLINE`. Vậy **venv tối thiểu của Pi đủ dependency** cho service.
- `pytest tests/unit/test_vision_*.py` trong container: **68 passed**.
- Inference 640 trong container: p50 khoảng 185 ms. Đây **không phải số đo trên Pi** (Docker VM trên M1), chỉ cho thấy OpenCV bản apt chậm hơn nhiều so với bản pip trên Mac (49 ms). Nếu Pi cũng cỡ đó thì model 640 khó đạt 5 FPS, nên phải đo cả 4 cỡ (mục 8 bước 7).

**Kiểm chứng F30 (07/10, tối):**

- `tests/unit/test_vision_phase_tracker.py` (18 test mới): đọc pha từ health, bỏ qua bản tin lạ hoặc lỗi (9 trường hợp), hết hạn sau 15 s, LWT OFFLINE, safe-stop vẫn giữ pha, `build_telemetry` và `build_health` mang pha thật. Có 1 test đọc thẳng file `.ino` để chốt định dạng health và việc gửi health khi vào GREEN, để firmware và vision không lệch nhau.
- `pytest tests/unit` trên Mac (Python 3.11): **208 passed, 11 skipped** (trước F30 là 190). `make contracts`: 8 passed. Trên "Pi giả" Trixie arm64: `test_vision_*.py` **86 passed**.
- Firmware build J1 và J2: SUCCESS, không cảnh báo, flash 777.397 B (tăng 4 B).
- Chạy thật trên Mac: vision 2 nút + broker cục bộ, giả ESP32 bằng `mosquitto_pub` với đúng payload health của firmware. J1 báo EW, telemetry J1 đổi sang EW trong cùng giây. Báo NS (trạng thái fallback) thì đổi NS. LWT OFFLINE thì về `default`. Báo EW rồi im lặng thì sau đúng 15 s về `default`. J2 không có health nên luôn `default`. Log ghi từng lần đổi nguồn. Health của vision: `phase_source: {J1: esp32_health, J2: default}`.
- **Chưa** chạy vòng kín với ESP32 thật và graph-control `edgeflow`: làm ở mục 4, hàng "Pha thật".

**Kiểm chứng đã làm (07/10, sau F18–F24):**

- `pytest tests/unit` trên `main` + thay đổi chưa commit: **181 passed, 11 skipped**, giống nhau trên Python 3.11 + OpenCV 5.0 và Python 3.13 + OpenCV 4.10 + numpy 2.2 (bộ của Trixie). `main` sau khi pull là 149 passed (thêm 2 test contracts của baolam). 32 test mới: `test_vision_runtime.py` (22), `test_vision_capture_dataset.py` (9), 1 test trong `test_vision_detector.py`. `make contracts`: 8 passed.
- Chạy thật trên Mac với Mosquitto cục bộ, model `yolo11n.onnx`, 2 nút + file ROI mẫu: J1 và J2 mỗi nút 25 bản tin telemetry trong 13 s. Health retained có số đo thật. `kill -TERM` để lại `OFFLINE` retained. `kill -9` thì broker tự phát LWT `OFFLINE`. Nguồn video hỏng thì health chuyển `DEGRADED` với `reason: "camera: 2 consecutive frames without image"`.
- Lỗi tìm ra khi chạy thật và đã sửa: bản health đầu tiên báo 12,53 fps từ **1 frame** trong 0,08 s. Giờ FPS = (n−1)/(t_cuối − t_đầu), cần ≥ 2 frame.
- Tên gói mà `setup_pi.sh` cài đều có trên Trixie arm64 (kiểm chỉ mục gói 07/10): `python3-picamera2` 0.3.37, `rpicam-apps` 1.13.0, `python3-libcamera` 0.7.2, `python3-opencv` 4.10.0, `chrony` 4.6.1, `mosquitto-clients` 2.0.21, `python3-venv` 3.13.5.

**Kiểm chứng của phiên 04–05/10 (F1–F17):**

- `pytest tests/unit`: **147 passed, 11 skipped** trên Python 3.11 (danh sách gói của CI). Kết quả **giống hệt** trên Python 3.13 + numpy 2.2 + OpenCV 4.10, tức bộ thư viện của Raspberry Pi OS Trixie. Trên `main` là 105 passed. Có thêm 42 test mới: `test_vision_deploy.py` (Picamera2 giả lập, CLI), `test_vision_multinode.py` (ROI và nhiều nút), `test_verify_trace.py` (kiểm tra trace), `test_vision_detector.py` (tự kiểm model khi load).
- Chạy thật trên Mac với Mosquitto cục bộ: vision (`--video synthetic --node-ids J1,J2 --roi-config …`) phát `telemetry/J1` và `telemetry/J2` mỗi giây. Bản tin health có `active_nodes` và `roi_sha256`.
- Firmware: build PlatformIO cho cả J1 và J2 (xem mục 6).
- **Chưa** chạy trên phần cứng thật vì chưa có board trong tay.

### 2.2 Chưa sửa: cần cả đội quyết định hoặc cần có phần cứng

| # | Vấn đề | Vì sao chưa sửa | Đề xuất |
|---|---|---|---|
| O1 | ~~Một camera chỉ phát cho 1 nút~~ | **Đã xử lý bằng F14** | Còn lại: vẽ ROI thật sau khi gắn camera (mục 3.2 bước 7) |
| O2 | ROI mặc định là 4 dải hard-code | Đã có công cụ vẽ ROI (F14), chỉ chờ camera thật | Chụp frame bằng `roi_calibrate.py capture` trên Pi, vẽ bằng `draw` trên Mac |
| O3 | Repo **không có file model** (`*.onnx`/`*.pt` bị `.gitignore` chặn). Mặc định dùng lớp COCO 2,3,5,7 (car, motorcycle, bus, truck) | Cần dữ liệu sa bàn | **Bước 1 xong 05/10** (mục 7): đã export `models/yolo11n.onnx` trên Mac, so khớp với onnxruntime và Ultralytics. **COCO không thấy xe nhỏ nhìn từ trên cao** (0/hàng chục xe trên ảnh New York chụp từ trên xuống), nên gần như chắc chắn phải fine-tune. Còn lại: đo FPS trên Pi; fine-tune trên ≥300 frame sa bàn theo plan. Nếu chỉ có 1 lớp thì đặt `DETECTOR_NUM_CLASSES=1`, `DETECTOR_VEHICLE_CLASSES=0` (sai thì F16 báo ngay lúc start). NCNN chưa được code hỗ trợ, chỉ thêm khi ONNX quá chậm |
| O4 | Laptop `--profile hardware` vẫn chạy **actuator ảo**, nó subscribe `control/+/command` và ACK cho cả J1/J2 | Đổi profile trong compose ảnh hưởng cả đội | Khi demo phần cứng: `docker compose --profile hardware up -d && docker compose stop actuator`. Lâu dài thì bỏ `hardware` khỏi profile của `actuator` |
| O5 | `docker-compose.rpi.yml` service `vision`: image `python:3.11-slim` không có libcamera/Picamera2. `DETECTION_MODEL_PATH` trỏ `models/…` trong `/app`, nhưng thư mục model lại mount ở `/models` | Docker trên Pi chỉ dùng được với camera USB hoặc file | Trên Pi chạy native (F12). Compose của Pi chỉ dùng cho broker/standalone |
| O6 | Topology `four_intersection_v1` có J1–J4, trong khi sa bàn thật chỉ có J1–J2 | Thuộc `contracts/` (cần owner đồng ý) | Trước mắt không gây lỗi, vì không có telemetry J3/J4 thì không có lệnh J3/J4. Nên có topology `corridor_j1_j2_v1` cho phần chạy phần cứng |
| O7 | ~~Telemetry của vision luôn gửi `current_phase_id = phases[0]`~~ **Đã xử lý bằng F30** (Hiển chọn 07/10: sửa vision + firmware) | Còn phải kiểm trên phần cứng thật | Mục 4, hàng "Pha thật". Graph-control không cần sửa |
| O8 | Tài liệu lệch nhau: watchdog 5 s hay 15 s, min green 5 s hay 10 s, "USB Type-C", topic `feedback/`, `make run-server` không tồn tại, schematic ghi diode 1N4007 | Tài liệu của cả đội | Sửa một lượt cùng lúc với PR deploy |
| O9 | Safe-stop dùng nút thường mở kéo xuống GND. Đứt dây thì **không** dừng được (không fail-safe) | Đổi logic sẽ làm lệch tài liệu và test | Chấp nhận cho bán kết. Chung kết cân nhắc nút nấm thường đóng (NC) và đảo logic |
| O10 | ~~`perception_engine.py` gán cứng `detection_confidence=0.92`~~ **Đã xử lý bằng F27** (Hiển quyết 07/10) | cho **mọi** approach, kể cả khi dùng motion baseline (không có điểm tin cậy). `graph-control/controller.py:547-593` **nhân áp lực của từng approach với `confidence`** | Đổi ý nghĩa của `confidence` sẽ đổi hành vi điều khiển. Đây là quyết định của cả đội | Cần chốt `confidence` nghĩa là gì: điểm trung bình của các box (approach không có xe thì lấy bao nhiêu?) hay độ tin cậy của khung hình. Trước khi chốt, **không được ghi 0.92 vào báo cáo như một kết quả đo** |
| O11 | `metrics_extractor.py`: `mean_speed_mps` suy từ occupancy theo công thức tự đặt, còn `flow_veh_per_s = queue × 0.08`. ~~Health gửi `fps = 1/TELEMETRY_PERIOD_S`~~ (**đã sửa bằng F19**) | Không phải số đo. Trái với nguyên tắc "không thay dữ liệu thiếu bằng số trông hợp lý" | Ghi rõ trong báo cáo đây là ước lượng, hoặc bỏ đi. FPS thật lấy từ `detector.last_timings` |
| O12 | ~~Vision gửi health `HEALTHY` dạng retained mà không đặt LWT~~ | **Đã sửa bằng F19** | Đã kiểm bằng `kill -9` trên Mac |
| O13 | File mới `docs/HUONG_DAN_TRIEN_KHAI_VA_BAO_CAO_DU_AN_EDGEFLOW_AI.docx` (untracked, 04/10 23:21, "v2.5-Final") **lệch code ở nhiều chỗ**: nói đã có `models/yolov8n.onnx` 12,85 MB và `.pt` (không tồn tại); "108/108 tests" (`main` là 105 passed / 11 skipped); cây topic `control/commands/J1`, `control/acks/J1`, `health/actuator` (code là `control/{node}/command`, `control/{node}/ack`, `health/{node}`); `docker-compose up -d` không kèm `--profile` (mọi service trong compose đều có profile nên **không chạy gì cả**); chạy vision trên Pi bằng Docker và `VIDEO_SOURCE=/dev/video0` (không dùng được với camera CSI, xem O5/F1); `graph-control/main.py --config …` (main.py không có argparse, flag bị bỏ qua); sửa `#define` bằng Arduino IDE (đã thay bằng env PlatformIO, F10); "MicroUSB/Type-C" | Không rõ ai viết. **Đã vào `main`** qua commit `b841bbb` của Hiển (05/10), có lẽ do `git add` cả thư mục | Không nộp hay trình bày file này khi chưa sửa. Nếu không ai nhận viết thì nên đề xuất gỡ khỏi repo trong PR kế tiếp. Số benchmark −21,04% có nguồn là `artifacts/benchmark_summary.md`, nhưng plan (2) đánh giá là **chưa kiểm chứng** |
| O14 | **Đã xử lý bằng F26** (Hiển quyết 07/10, chọn phương án (b)). Mô tả cũ: vision chỉ xử lý **1 frame mỗi `TELEMETRY_PERIOD_S`** (mặc định 1 s). `VISION_FPS=10.0` trong `.env.rpi` **không được code nào đọc**, giống loại lỗi F2 | Plan yêu cầu "≥ 5 processed frames per second". Muốn đạt thì service phải xử lý liên tục rồi gộp nhiều frame thành 1 bản tin telemetry/giây (ví dụ lấy trung vị số xe mỗi approach). Việc này **đổi ý nghĩa đầu vào của graph-control**, nên cần cả đội quyết | Đo trước bằng `benchmark.py` trên Pi (F18): nếu Pi đạt ≥ 5 FPS thì đó là năng lực. Sau đó chọn: (a) giữ 1 frame/giây và báo cáo trung thực; (b) xử lý liên tục rồi lấy trung vị trong cửa sổ, giảm nhiễu do bỏ sót xe từng frame. Dù chọn cách nào cũng phải bỏ `VISION_FPS` hoặc làm cho nó có tác dụng thật |
| O15 | Không có tracking (ID xe bền vững). Plan mục vision: "assign persistent track IDs" | Thời gian còn lại ít, không thể thêm tracking mà không đo lại toàn bộ | Bán kết: ghi rõ là đếm theo từng frame, không có tracking |
| O16 | Thay đổi của baolam ngày 05–07/10: `contracts_sdk.load_topology` có alias (`four_intersection_v1` → `corridor` khi thiếu file), mặc định đổi sang `corridor`; graph-control thêm `flow`/`flow_rl` | Đã kiểm: vision và graph-control vẫn truyền `four_intersection_v1`, file đó vẫn còn và **giống hệt** `corridor.json` (chỉ khác `topology_id`). `from models import …` trong SDK vẫn chạy vì helper chèn `contracts/` vào đầu `sys.path`. Không ảnh hưởng tới Pi/ESP32 | Không cần làm gì. Nếu sau này xóa `four_intersection_v1.json` thì alias vẫn trả về nội dung của `corridor` (J1–J4 không đổi) |

---

## 3. Deploy theo từng thiết bị

### 3.1 Laptop (broker + control + dashboard)

```bash
cd vedc-traffic-flow
cp .env.example .env                       # MQTT_HOST=mqtt (tên service trong Docker)
sed -i '' 's/^EDGEFLOW_TOPOLOGY=.*/EDGEFLOW_TOPOLOGY=tabletop_j1_j2_v1/' .env   # G4: trùng với .env.rpi
docker compose --profile hardware up -d --build
docker compose stop actuator               # O4: tránh ACK trùng với ESP32
docker compose logs -f graph-control
# Kiểm tra broker từ máy khác trong LAN:
mosquitto_sub -h 192.168.1.100 -t 'edgeflow/v1/#' -v
```

Trên macOS cần mở firewall cho cổng 1883 (Docker Desktop thường tự hỏi).

### 3.2 Raspberry Pi 5 (vision)

1. Ghi **Raspberry Pi OS 64-bit bản Trixie** bằng Raspberry Pi Imager. **Không dùng Bookworm**: OpenCV apt của nó là 4.6, không chạy được model (mục 7). `setup_pi.sh` sẽ dừng lại nếu gặp OpenCV < 4.8.
   - Bật SSH.
   - Đặt hostname `edgeflow-pi`.
   - Nhập Wi-Fi của router.
2. Cắm camera bằng **cáp 22→15 pin**: mặt tiếp xúc của cáp quay đúng chiều, khóa cổng CAM/DISP 0 của Pi 5.
3. Lấy code và cài đặt. **Không `git clone` trên Pi: repo private** (F28).

   ```bash
   # Trên Mac, trong vedc-traffic-flow/: code (kể cả phần chưa commit) + 4 model, kiểm sha256 trên Pi
   bash infra/rpi/sync_to_pi.sh             # mặc định pi@edgeflow-pi.local; host khác: thêm pi@<ip>
   # Trên Pi
   cd ~/vedc-traffic-flow && bash infra/rpi/setup_pi.sh   # apt (cần internet), venv, .env.rpi, chrony
   nano .env.rpi    # MQTT_HOST=192.168.1.100, CAMERA_LENS_POSITION=…; comment để trên dòng riêng (F29)
   ```

4. Model: `sync_to_pi.sh` đã gửi cả 4 file trong `models/` (`yolo11n.onnx` 640 và `yolo11n_480/416/320.onnx`, mục 7 và 7b) và kiểm sha256. Chạy `bash infra/rpi/preflight.sh`: script đọc `.env.rpi` đúng như systemd, đối chiếu sha256 với `models/SHA256SUMS` và chạy thử model với đúng `DETECTOR_INPUT_SIZE` trong `.env.rpi`.
5. Chạy thử bằng tay, rồi bật dịch vụ:

   ```bash
   # main.py không tự đọc .env.rpi; thiếu dòng set -a thì chạy motion baseline thay cho YOLO (F29)
   set -a; . ./.env.rpi; set +a; .venv-pi/bin/python services/vision/main.py
   bash infra/rpi/setup_pi.sh --service && journalctl -u edgeflow-vision -f
   vcgencmd get_throttled               # phải là 0x0; khác 0 nghĩa là thiếu nguồn hoặc quá nhiệt
   ```

6. Lấy nét: chụp thử `rpicam-still -o test.jpg --autofocus-mode manual --lens-position 2.0`, chỉnh số tới khi ảnh nét. LensPosition tính bằng dioptre, bằng 1/khoảng cách (m).
7. Vẽ ROI cho cả J1 và J2 (sau khi camera đã cố định trên giá):

   ```bash
   # Trên Pi
   .venv-pi/bin/python services/vision/roi_calibrate.py capture --video picamera --width 1280 --height 720 --lens-position 2.0 --out frame.png
   # Trên Mac (có màn hình), sau khi scp frame.png về
   python services/vision/roi_calibrate.py draw --image frame.png --nodes J1,J2 --out services/vision/rois/tabletop.json
   python services/vision/roi_calibrate.py check --config services/vision/rois/tabletop.json --nodes J1,J2 --image frame.png --out roi_overlay.png
   ```

   Chép `tabletop.json` lên Pi, rồi trong `.env.rpi` đặt `VISION_NODE_IDS=J1,J2` và `ROI_CONFIG_PATH=services/vision/rois/tabletop.json`. Ảnh `roi_overlay.png` đưa luôn vào báo cáo.

### 3.3 ESP32 J1/J2 (firmware)

```bash
cd vedc-traffic-flow/src/hardware
cp secrets.example.ini secrets.ini      # sửa WIFI_SSID / WIFI_PASS / MQTT_BROKER=192.168.1.100
                                        # (tùy chọn) -D NTP_SERVER=\"192.168.1.101\" để lấy giờ từ Pi
uvx --from platformio pio run -e J1 -t upload      # cắm board J1 bằng cáp micro-USB truyền dữ liệu
uvx --from platformio pio run -e J2 -t upload      # đổi sang board J2
uvx --from platformio pio device monitor -e J1     # xem log, các dòng TRACE
```

- Nếu không nạp được: giữ nút **BOOT** khi thấy dòng `Connecting...`.
- **Rút nguồn 5V ngoài khi đang cắm USB nạp firmware.**
- Dán nhãn J1/J2 lên board ngay sau khi nạp.

**Đấu dây cho mỗi nút** (chi tiết trong `src/hardware/schematic_and_pinout.md`):

- GPIO 23/22/21 → chân R/Y/G của module **Bắc và Nam**, mắc song song.
- GPIO 19/18/5 → chân R/Y/G của module **Đông và Tây**.
- GND của mọi module → GND của ESP32.
- GPIO 4 → nút tự giữ → GND.
- 5V từ adapter (qua jack → domino, diode Schottky) → chân 5V/VIN. GND chung.

---

## 4. Kiểm thử theo cổng nghiệm thu của plan

| Kiểm thử | Cách làm | Đạt khi |
|---|---|---|
| Bring-up ESP32 (chưa cần mạng) | Cấp nguồn, xem serial | `TRACE …,R,R,ALL_RED`, sau 2 s là `G,R,GREEN`. Sau 5 s vào fallback, đổi pha mỗi 15 s, vàng đúng 3000 ms ±20, all-red 2000 ms ±20 |
| Lệnh MQTT tay | `mosquitto_pub -h <broker> -t edgeflow/v1/control/J1/command -m '{"command_id":"t1","node_id":"J1","target_phase_id":"J1_PHASE_EW","min_green_s":10,"max_green_s":60,"controller":"manual"}'` và `mosquitto_sub -t 'edgeflow/v1/control/J1/ack' -v` | Nhận ACCEPTED ngay, APPLIED sau ~5 s. Pha cùng hướng trả APPLIED. Phase lạ trả REJECTED. Chưa đủ min green trả REJECTED |
| Safe-stop | Bấm nút tự giữ, rồi thả | Bấm: vàng nhấp nháy, health `SAFE_STOP`, lệnh đến bị REJECTED. Thả: ALL_RED 2 s rồi xanh |
| Kiểm tra trace tự động | `pio device monitor -e J1 \| tee trace_J1.log`, rồi `python src/hardware/verify_trace.py trace_J1.log --json trace_J1.json` | `[PASS]`, exit 0 |
| Output trace độc lập | Logic analyzer CH0–5 nối GPIO 23/22/21/19/18/5, CH6 nối GPIO 4, chạy PulseView | Không có khoảnh khắc nào 2 hướng cùng xanh. Vàng ≥ 3 s, all-red ≥ 2 s |
| Pi inference | `journalctl -u edgeflow-vision`, ghi riêng thời gian preprocess, inference, postprocess (`detector.last_timings`) | ≥ 5 FPS, P95 từ lúc chụp tới lúc quyết định ≤ 1 s (mục tiêu của plan) |
| Pha thật (F30) | Vòng kín với `EDGEFLOW_CONTROLLER=edgeflow`; `mosquitto_sub -t edgeflow/v1/health/vision -t 'edgeflow/v1/telemetry/+' -v` | Health của vision có `phase_source` = `esp32_health` cho J1 và J2. `current_phase_id` trong telemetry đổi theo đèn thật trong ≤ 1 s sau khi vào xanh. Hướng nhiều xe được xanh lâu hơn |
| Vòng kín | Laptop + Pi + 2 ESP32. Ghi `mosquitto_sub -h <broker> -v -F '%U %t %p' -t 'edgeflow/v1/#' \| tee run.log`, rồi `python src/hardware/demo/flow_report.py run.log --nodes J1,J2 --json run.json` (F31) | `RESULT: PASS`: telemetry ≥ 0,8 Hz mỗi nút, mọi lệnh có ACK, đổi pha 5 s ± 30%, ESP32 không vào fallback khi telemetry đang tới, pha trong telemetry khớp ESP32 ≥ 95% |
| Lỗi cố ý | Rút camera; tắt broker (`docker compose stop mqtt`); rút nguồn ESP32 rồi cắm lại | Camera mất: confidence 0, dashboard báo `CAMERA_FAULT`, ESP32 vào fallback sau 5 s (**chỉ đạt sau khi sửa G1**; trước đó `flow_report` FAIL ở `blind_commands`). Broker mất: ESP32 vào fallback sau 5 s, có lệnh lại thì quay về điều khiển. Mất nguồn: khởi động lại ở ALL_RED |
| Chạy liên tục 30 phút | Ghi log serial + MQTT (`mosquitto_sub -v -t 'edgeflow/v1/#' > run.log`) | Không reset ngoài ý muốn, không có `ERROR`, Pi không throttle |

Lưu log serial (`pio device monitor -e J1 | tee trace_J1.csv`), log MQTT và file PulseView vào thư mục artifact của từng lần chạy. Báo cáo bán kết cần các bằng chứng này.

---

## 5. Thứ tự làm (tính từ 04/10, cập nhật 07/10)

> 07/10: Pi đã về. Đã qua mốc 05–08/10 mà chưa có clip sa bàn nào. Thời gian còn lại tới lúc chốt số liệu (09/10) chỉ đủ cho **1 vòng** thu dữ liệu, fine-tune và đo. Buổi đầu với Pi làm theo mục 8, không làm lan man.

1. **Hôm nay:** đặt hàng (MUA_SAM_CON_THIEU.md). Cả đội review nhánh `deploy/hardware-prep`, Hiển commit và mở PR khi đã đồng ý.
2. **Khi có ESP32 + module đèn** (không cần Pi): nạp J1/J2, chạy hàng kiểm thử 1–4 ở mục 4 với broker trên laptop.
3. **Khi có cáp camera:** ghi Trixie, chạy `setup_pi.sh`, chép `models/yolo11n.onnx` lên Pi (đã export ngày 05/10), đo FPS. Gắn camera lên giá, chụp frame, làm O1 + O2 (ROI cho J1 và J2).
4. **05–08/10:** quay 6–10 clip, gán nhãn ≥ 300 frame, fine-tune nếu COCO không nhận xe 1:64. Chạy kiểm thử lỗi và chạy liên tục 30 phút.
5. **09–11/10:** chốt code, lấy hình từ artifact, viết sơ đồ mạch và pin map cho báo cáo.

---

## 6. Kết quả build firmware (04/10/2026, trên Mac, PlatformIO 6.2 qua `uvx`)

| Bản build | Kết quả | RAM | Flash |
|---|---|---|---|
| Firmware gốc trên `main`, env J1 | ✅ SUCCESS | 44.896 B (13,7%) | 758.493 B (57,9%) |
| Nhánh `deploy/hardware-prep`, env J1 | ✅ SUCCESS, 0 cảnh báo | 45.188 B (13,8%) | 777.393 B (59,3%) |
| Nhánh `deploy/hardware-prep`, env J2 | ✅ SUCCESS, 0 cảnh báo | 45.188 B (13,8%) | 777.393 B (59,3%) |

- Môi trường build: platform `espressif32@7.1.3`, Arduino-ESP32 core 2.0.17, PubSubClient 2.8, ArduinoJson 6.21.
- Lần build đầu phải tải toolchain (~1,5 GB vào `~/.platformio`, mất khoảng 10 phút). Các lần sau chỉ mất 10–20 giây.
- Đã kiểm tra trong file binary:
  - Bản J1 chỉ chứa chuỗi `J1`, bản J2 chỉ chứa chuỗi `J2`, nên không thể nạp nhầm ID.
  - Khi có `secrets.ini`, địa chỉ broker trong đó thay hẳn địa chỉ mặc định `192.168.4.1`.
- **Chưa kiểm** những gì cần board thật:
  - Nạp firmware và chạy thực tế.
  - Đo timing bằng logic analyzer.
  - Watchdog phần cứng reset đúng.
  - Kết nối Wi-Fi/MQTT với router.

  Đây là những việc đầu tiên cần làm khi có ESP32 và module đèn (mục 4).

---

## 7. Kiểm model YOLO11n trên nhiều bản OpenCV (05/10/2026, trên Mac M1 Pro)

**Cách tạo model** (Ultralytics 8.4.173, torch 2.14.1, onnx 1.23.1, onnxslim 0.1.97):

```bash
yolo export model=yolo11n.pt format=onnx imgsz=640 opset=12   # output (1, 84, 8400), 10,2 MB
```

- `yolo11n.pt`: sha256 `0ebbc80d4a7680d14987a577cd21342b65ecfd94632bd9a8da63ae6417644ee1`, tải từ `github.com/ultralytics/assets/releases/download/v8.4.0/`.
- `models/yolo11n.onnx`: sha256 `2afc768afdfefaaaca71179dfd79a0b7db7647341cec9705f3f507522d03f05f`. Service ghi giá trị này vào health (`model_sha256`), dùng để đối chiếu với file trên Pi.

**Cách kiểm:**

- Chạy `VehicleDetector` của repo (ngưỡng 0,4, 4 luồng) trên 5 ảnh: `bus.jpg` của Ultralytics, 3 ảnh tắc đường và 1 ảnh New York chụp từ trên cao, lấy từ Wikimedia Commons (CC0/CC BY/CC BY-SA). Ảnh chỉ dùng để test, không đưa vào repo.
- So **tensor thô** với onnxruntime trên cùng blob.
- So **box cuối** với `YOLO("yolo11n.onnx").predict(conf=0.4, iou=0.45, classes=[2,3,5,7])`. Khớp nghĩa là IoU ≥ 0,9.

| OpenCV | Tương ứng | Load | Forward | Lệch tối đa so với onnxruntime | Box khớp | Inference p50 (Mac, 4 luồng) |
|---|---|---|---|---|---|---|
| 4.6.0 | apt **Bookworm** | ✅ | ❌ assertion `shape_utils.hpp:171 … 'total'` trên mọi ảnh | – | – | – |
| 4.7.0 | – | ✅ | ❌ cùng lỗi | – | – | – |
| 4.8.0 | sàn của `requirements.txt` | ✅ | ✅ | ≤ 0,011 | 36/37 | ~68 ms tổng |
| 4.10.0 | apt **Trixie** | ✅ | ✅ | ≤ 0,015 | 36/37 | ~51 ms |
| 4.10.0 (pip, `--no-deps`) + numpy 1.24.2 | phương án dự phòng cho Bookworm | ✅ | ✅ | ≤ 0,012 | 36/37 | – |
| 5.0.0 | bản mới nhất trên pip | ✅ | ✅ | ≤ 0,004 | 37/37 | ~31 ms |

- **YOLOv8n cũng lỗi y hệt trên 4.6.** Bỏ onnxslim hay hạ xuống opset 11 đều không cứu được: bản không slim còn lỗi ngay lúc load, ở node `Add` của head. Nên vấn đề nằm ở bản OpenCV, không phải ở YOLO11.
- Box duy nhất không khớp (ảnh `jam.jpg`, OpenCV 4.8/4.10) có score 0,414, sát ngưỡng 0,4, và IoU 0,84 với box tham chiếu. Sai khác do số học, **không phải lỗi postprocess**.
- **Ảnh New York chụp từ trên cao có hàng chục ô tô nhỏ, nhưng cả `.pt` lẫn `.onnx` đều ra 0 box.** Đây là bằng chứng mạnh rằng YOLO11n COCO không dùng được nguyên trạng cho xe 1:64 nhìn từ trên xuống. Cần quay clip sa bàn, gán nhãn ≥ 300 frame và fine-tune theo plan.
- Chạy trọn `services/vision/main.py --model models/yolo11n.onnx --video <file>` trên Python 3.13 + OpenCV 4.10: load, kể cả bước tự kiểm, mất ~180 ms, sau đó telemetry ra đều.
- **Số đo trên Mac không phải số đo trên Pi.** Pi 5 chậm hơn M1 Pro vài lần, chưa đo được, nên phải đo thật bằng `benchmark.py` hoặc `detector.last_timings` khi có Pi. Nếu ở 640 thấp hơn 5 FPS thì thử `imgsz=480/416`. Lưu ý xe nhỏ sẽ khó thấy hơn khi giảm độ phân giải.

### 7b. Model export ở các cỡ nhỏ hơn (07/10/2026, cùng môi trường như trên)

Mục đích: đo FPS trên Pi theo từng cỡ **ngay trong buổi đầu**, để chọn `imgsz` trước khi fine-tune. Độ trễ phụ thuộc kiến trúc và cỡ đầu vào, không phụ thuộc trọng số, nên số đo trên bản COCO dùng lại được cho bản fine-tune cùng cỡ.

```bash
yolo export model=yolo11n.pt format=onnx imgsz=<480|416|320> opset=12   # cùng yolo11n.pt sha256 0ebbc80d…
```

| File (trong `models/`, bị gitignore) | sha256 | `DETECTOR_INPUT_SIZE` | bus.jpg: số box / score | Inference p50 trên Mac (OpenCV 4.10) |
|---|---|---|---|---|
| `yolo11n.onnx` | `2afc768a…f03f05f` | 640 | 1 / 0,94 | 49 ms |
| `yolo11n_480.onnx` | `d65b920f…bc4950` | 480 | 1 / 0,88 | 36 ms |
| `yolo11n_416.onnx` | `3361d7c1…fbccc20` | 416 | 1 / 0,90 | 28 ms |
| `yolo11n_320.onnx` | `81f30e06…eee7e6` | 320 | 1 / 0,85 | 19 ms |

- Giá trị sha256 đầy đủ nằm trong `models/SHA256SUMS` (đã kiểm bằng `shasum -a 256 -c`).
- **Bắt buộc đặt `DETECTOR_INPUT_SIZE` đúng cỡ lúc export.** Export ONNX là shape cố định, nên lệch cỡ thì OpenCV 4.10 lỗi ở `Reshape` (F21 giờ báo đúng nguyên nhân).
- Số đo trên Mac chỉ để so tương đối giữa các cỡ. Pi 5 chậm hơn nhiều, phải đo thật.

---

## 8. Buổi đầu với Pi: checklist theo thứ tự

Chuẩn bị trên Mac trước khi cầm Pi:

- [ ] Có cáp camera 22→15 pin cho Pi 5 (MUA_SAM_CON_THIEU.md mục 2.1 #1). Không có cáp thì chỉ làm được bước 1–3 và 6.
- [ ] Ghi thẻ microSD bằng Raspberry Pi Imager: **Raspberry Pi OS (64-bit) Trixie**. Trong phần tùy chỉnh:
  - Hostname `edgeflow-pi`, **user `pi`** (mọi lệnh trong file này dùng `pi@`).
  - Bật SSH kiểu **public key**, dán `~/.ssh/id_ed25519.pub` của Mac, để `sync_to_pi.sh` không phải hỏi mật khẩu.
  - Wi-Fi của một mạng **có internet** cho buổi đầu: `setup_pi.sh` cần apt. Router demo không có internet thì dùng hotspot điện thoại cho buổi này.

Trên Pi (truy cập bằng `ssh pi@edgeflow-pi.local`):

1. `sudo apt update && sudo apt full-upgrade -y && sudo reboot`.
2. Trên Mac, trong `vedc-traffic-flow/`: `bash infra/rpi/sync_to_pi.sh`. Script gửi code (kể cả phần chưa commit) và 4 model, kiểm sha256 trên Pi, ghi `DEPLOYED_FROM.txt`. **Không `git clone` trên Pi vì repo private** (F28). Mỗi lần sửa code trên Mac thì chạy lại lệnh này. Script không xóa file trên Pi.
3. Trên Pi: `cd ~/vedc-traffic-flow && bash infra/rpi/setup_pi.sh`, rồi sửa `.env.rpi` (`MQTT_HOST`, `CAMERA_LENS_POSITION`). Comment phải nằm trên dòng riêng: systemd giữ `# …` cuối dòng trong giá trị (F29).
4. Kiểm góc nhìn (F25), cần venv của bước 3: `rpicam-still -o full.jpg` rồi `.venv-pi/bin/python services/vision/roi_calibrate.py capture --video picamera --width 1280 --height 720 --out frame.png`. Hai ảnh phải cùng góc nhìn, và log phải có dòng `Sensor mode 2304x1296 … (full field of view)`.
5. `bash infra/rpi/preflight.sh`. Sửa cho tới khi **0 FAIL**. Lưu output vào artifact.
6. Lấy nét: `rpicam-still -o focus.jpg --autofocus-mode manual --lens-position 2.0`, thử vài giá trị tới khi xe nét, ghi lại vào `.env.rpi`.
7. Đo FPS cho cả 4 cỡ, mỗi cỡ 300 frame, cùng cỡ chụp với file ROI (1280×720):

   ```bash
   for sz in 640 480 416 320; do m=models/yolo11n_$sz.onnx; [ $sz = 640 ] && m=models/yolo11n.onnx
     .venv-pi/bin/python services/vision/benchmark.py --source picamera --width 1280 --height 720 \
       --lens-position 2.0 --model $m --input-size $sz --frames 300 --output artifacts/pi_bench_$sz.json; done
   vcgencmd get_throttled     # phải là 0x0; khác 0 thì số đo không hợp lệ (thiếu nguồn hoặc quá nhiệt)
   ```

   Chọn cỡ lớn nhất đạt ≥ 5 FPS (`throughput_fps`). Đây cũng là `imgsz` dùng khi fine-tune. Đặt `DETECTION_MODEL_PATH` và `DETECTOR_INPUT_SIZE` tương ứng.
8. Gắn camera lên giá cố định, chụp frame, vẽ ROI cho J1 và J2 (mục 3.2 bước 7), rồi chạy lại `preflight.sh`.
9. Thu dữ liệu: 6–10 phiên × ~2 phút, mỗi phiên một điều kiện khác (ít xe/nhiều xe, xe chồng nhau, ít nhất 2 kiểu ánh sáng). Di chuyển xe giữa các lần chụp:

   ```bash
   .venv-pi/bin/python services/vision/capture_dataset.py --session s01_low_daylight --out ~/dataset \
     --video picamera --width 1280 --height 720 --lens-position 2.0 --every 1.0 --duration 120 --note "…"
   ```

   Chép `~/dataset` về Mac bằng tar-over-ssh. **Khóa phiên test trước khi fine-tune** (ví dụ 2 phiên), gán nhãn ≥ 300 frame, 1 lớp `vehicle`. Train bằng Ultralytics ở đúng `imgsz` đã chọn, export `opset=12`, ghi sha256 vào `models/SHA256SUMS`, đặt `DETECTOR_NUM_CLASSES=1`, `DETECTOR_VEHICLE_CLASSES=0`. Model mới lên Pi bằng `sync_to_pi.sh` như code.
10. Chạy service dưới systemd (`setup_pi.sh --service`), xem `journalctl -u edgeflow-vision -f`: dòng `Runtime:` mỗi 10 s cho FPS và `age_at_publish` p95. Health retained: `mosquitto_sub -h <laptop> -t edgeflow/v1/health/vision -v`.
11. Lưu vào artifact của buổi: output `preflight.sh`, `artifacts/pi_bench_*.json`, ảnh `roi_overlay.png`, log journal, các `session.json`, và `DEPLOYED_FROM.txt` (phiên bản code đang chạy).

**Ở hội trường (router demo không có internet):** RTC của Pi 5 không kèm pin, nên Pi có thể khởi động sai giờ, và chrony sẽ phát giờ sai đó cho 2 ESP32. Điều khiển vẫn chạy, vì graph-control không lọc theo `timestamp_ms`. Nhưng mốc giờ trong log bằng chứng sẽ lệch với laptop, và từ `e422ce7` **API tính tuổi heartbeat của ESP32 theo `timestamp_ms` của ESP32**: Pi lệch quá 6 s là dashboard báo `HEARTBEAT_LOST` (G3). Trước khi ghi log, chạy trên Mac: `ssh -t pi@edgeflow-pi.local "sudo date -s @$(date +%s)"`. `preflight.sh` in giờ của Pi khi chrony chưa đồng bộ.
