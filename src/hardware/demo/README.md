# Công cụ test MQTT: Raspberry Pi ↔ laptop ↔ ESP32

Ba script để thử đường truyền và điều khiển **trước khi** camera và model YOLO sẵn sàng. Chỉ cần `paho-mqtt` và `jsonschema` (đã có trong venv của `infra/rpi/setup_pi.sh`). Topic và schema lấy từ `contracts/`, không định nghĩa lại.

```
 Pi (dữ liệu giả)  --telemetry-->  Broker (laptop)  --command-->  ESP32 J1/J2
 pi_fake_telemetry.py              mosquitto :1883   laptop_command_test.py
                       <--health/ack--                <--ack/health--
```

| Script | Chạy ở đâu | Việc |
|---|---|---|
| `pi_fake_telemetry.py` | Pi (hoặc bất kỳ máy nào) | Phát telemetry J1/J2 hợp lệ theo kịch bản. Health gắn `"mode": "FAKE_DATA"`. Từ chối chạy khi `services/vision` thật đang HEALTHY (trừ khi `--force`) |
| `laptop_command_test.py` | Laptop | `status` (ai đang online), `send` (1 lệnh + ACK), `test` (bộ kiểm thử tự động), `cycle` (đổi pha theo giờ để nhìn đèn), `monitor` (xem mọi bản tin) |
| `esp32_simulator.py` | Laptop | ESP32 ảo bám sát firmware, để tập dượt khi chưa có board. **Không phải bằng chứng về firmware thật** |

## Chạy nhanh

```bash
# Venv tối thiểu (laptop hoặc Pi)
python3 -m venv ~/edgeflow-demo && ~/edgeflow-demo/bin/pip install paho-mqtt jsonschema
PY=~/edgeflow-demo/bin/python; D=src/hardware/demo; BROKER=192.168.1.3   # IP laptop chạy mosquitto

# Pi: dữ liệu giả, mỗi giây 1 bản tin cho J1 và J2
$PY $D/pi_fake_telemetry.py --mqtt-host $BROKER --scenario alternate
$PY $D/pi_fake_telemetry.py --dry-run --duration 3        # chỉ in ra, không cần broker

# Laptop
$PY $D/laptop_command_test.py --mqtt-host $BROKER status                  # J1, J2, vision có mặt chưa?
$PY $D/laptop_command_test.py --mqtt-host $BROKER send J1 EW              # 1 lệnh, in ACCEPTED -> APPLIED
$PY $D/laptop_command_test.py --mqtt-host $BROKER test J1 J2 --json run.json
$PY $D/laptop_command_test.py --mqtt-host $BROKER cycle J1 J2 --period 12 # đổi NS/EW để xem đèn
$PY $D/laptop_command_test.py --mqtt-host $BROKER monitor                 # như mosquitto_sub -v
```

`--mqtt-host` mặc định lấy từ biến môi trường `MQTT_HOST` (cổng: `MQTT_PORT`).

Kịch bản của Pi giả: `ns_heavy`, `ew_heavy`, `balanced`, `alternate` (đổi bên đông xe mỗi 60 s), `ramp` (hàng đợi NS tăng 0→15 trong 120 s), `camera_lost` (confidence 0, hàng đợi 0, giống camera hỏng). Như service thật, `current_phase_id` đi theo pha mà ESP32 báo trên `edgeflow/v1/health/{node}`.

## Bộ `test` kiểm tra gì

Mỗi node, theo thứ tự, kết thúc ở đúng pha ban đầu:

1. `online`: có health, không SAFE_STOP, đang GREEN.
2. `invalid_json`: JSON hỏng → REJECTED.
3. `unknown_phase`: pha lạ → REJECTED.
4. `other_node_ignored`: lệnh gửi cho node khác trên topic này → không có ACK.
5. `expired_command`: lệnh quá hạn → EXPIRED (bỏ qua nếu ESP32 chưa đồng bộ giờ SNTP).
6. `extend_active_phase`: cùng pha đang xanh → APPLIED.
7. `switch_phase`: đổi pha → ACCEPTED, rồi APPLIED sau **5 s ± 30%** (vàng 3 s + all-red 2 s).
8. `min_green_guard`: đổi ngay sau đó → REJECTED "Min green".
9. `during_clearance`: gửi lại lúc đang chuyển → ACCEPTED, rồi APPLIED.
10. `final_state`: HEALTHY, GREEN, đúng pha ban đầu.
11. (tuỳ chọn `--with-watchdog`) `watchdog_fallback`: im lặng > 5 s → `FALLBACK_AUTONOMOUS`, lệnh kế tiếp → HEALTHY. Có thể làm đổi pha nên không bật mặc định.

Exit 1 nếu có FAIL. File `--json` là bằng chứng cho báo cáo.

## Điều cần biết về firmware (đã mô phỏng đúng)

- Sau 5 s không có lệnh hợp lệ cho node đó, ESP32 vào **fallback** (15 s xanh mỗi pha). Chuyển pha do fallback tự làm thì **không có ACK APPLIED**. Vì vậy bộ `test` gửi lệnh keepalive (`target_phase_id` không tồn tại: bị REJECTED nhưng vẫn reset watchdog, không đổi đèn).
- Chỉ có 2 pha nên REJECTED "Clearance interval currently in progress" không thể xảy ra: gửi lúc đang chuyển luôn ra ACCEPTED.
- `expires_at_ms` chỉ có tác dụng khi ESP32 đã đồng bộ giờ (SNTP). Không có trong schema nhưng firmware đọc.
- Min green yêu cầu chỉ kéo dài được, không rút ngắn dưới 5 s của thiết bị.

## Kiểm vòng kín: telemetry → graph-control → đèn → ACK

Hai công cụ dưới đây kiểm **luồng điều khiển thật**: `services/graph-control` chạy đúng code sẽ chạy lúc demo, không phải lệnh gửi tay.

| Công cụ | Việc |
|---|---|
| `flow_report.py` | Đọc log MQTT của một lần chạy và chấm PASS/FAIL cho từng nút. Dùng được cho cả lần tập dượt lẫn phần cứng thật. Exit 1 nếu có FAIL, `--json` lưu làm bằng chứng |
| `closed_loop_rehearsal.sh` | Dựng cả vòng trên một laptop: Mosquitto riêng (cổng 18830), 2 ESP32 ảo, graph-control thật, nguồn telemetry (Pi giả hoặc service vision thật với video tổng hợp). Chạy xong thì gọi `flow_report.py` |

```bash
# Tập dượt (không cần phần cứng). Cần mosquitto và Python có gói của CI
PY=/tmp/edgeflow-venv/bin/python bash src/hardware/demo/closed_loop_rehearsal.sh                     # 60 s, Pi giả ns_heavy, max_pressure
PY=... bash src/hardware/demo/closed_loop_rehearsal.sh --controller edgeflow --source fake:camera_lost
PY=... bash src/hardware/demo/closed_loop_rehearsal.sh --source vision --model models/yolo11n.onnx    # service vision thật

# Phần cứng thật: ghi log ở bất kỳ máy nào tới được broker, trong suốt buổi chạy
mosquitto_sub -h <broker> -v -F '%U %t %p' -t 'edgeflow/v1/#' | tee ~/edgeflow_runs/run_$(date +%H%M).log
python src/hardware/demo/flow_report.py ~/edgeflow_runs/run_XXXX.log --nodes J1,J2 --json ~/edgeflow_runs/run_XXXX.json
```

Bắt buộc có `-F '%U %t %p'`: thiếu mốc giờ thì không chấm được gì.

`flow_report.py` kiểm, cho từng nút:

| Check | FAIL khi |
|---|---|
| `telemetry` | < 2 bản tin hoặc < 0,8 Hz (WARN nếu có khoảng trống > 3 s) |
| `commands` | có telemetry tin cậy mà graph-control không gửi lệnh nào (sai `EDGEFLOW_TOPOLOGY`, sai broker) |
| `acks` | lệnh không có ACK trong 2 s; EXPIRED (đồng hồ lệch); REJECTED vì lý do khác "Min green"/đang chuyển/safe-stop (ví dụ pha lạ). WARN khi một lệnh được ACK 2 lần (actuator ảo trong Docker chưa tắt, O4) |
| `switch_timing` | ACCEPTED → APPLIED ngoài 5 s ± 30% (WARN nếu không có lần đổi pha nào do lệnh) |
| `fallback` | ESP32 vào fallback trong khi telemetry tin cậy vẫn đang tới (lệnh không tới được thiết bị). Vào fallback **sau khi** camera/nguồn dừng là đúng |
| `blind_commands` | graph-control vẫn ra lệnh cho telemetry không có approach tin cậy (camera mất). Xem G1 trong `KE_HOACH_DEPLOY.md` |
| `phase_agreement` | < 95% bản tin telemetry mang đúng pha ESP32 đang báo (bỏ qua 1,5 s sau mỗi lần đổi pha) |
| `device_status` | chỉ WARN: có SAFE_STOP hoặc OFFLINE |

Thêm vào đó là thời gian xanh của từng pha, ước từ health mà ESP32 gửi mỗi lần vào GREEN. Đây là số liệu để so hướng đông xe với hướng vắng xe.

## Test tự động

```bash
python -m pytest tests/unit/test_demo_*.py            # logic thuần, chạy ở mọi nơi
python -m pytest tests/integration/test_demo_mqtt_roundtrip.py   # cần `mosquitto` trong PATH, tự bỏ qua nếu thiếu
```
