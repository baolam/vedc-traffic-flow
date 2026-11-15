# Tối nay (15/10): test MQTT Pi ↔ laptop ↔ ESP32

Mục tiêu: chứng minh 3 thiết bị nói chuyện với nhau qua MQTT, và lệnh từ laptop làm đèn ESP32 đổi pha đúng thời gian an toàn. Chưa cần camera, YOLO hay video ngã tư.

Công cụ: `vedc-traffic-flow/src/hardware/demo/` (xem README trong đó). Đã kiểm trước trên Mac: 43 test pass (có broker mosquitto thật + ESP32 ảo), firmware J1 và J2 build được với code hiện tại.

**Chưa kiểm được (cần phần cứng):** firmware thật trả lời đúng như ESP32 ảo, Pi chạy được 2 script, Wi-Fi ổn định. Đó là việc của tối nay.

## 0. Trạng thái lúc chuẩn bị (08:37)

| Mục | Tình trạng |
|---|---|
| Laptop | IP `192.168.1.3` (DHCP: kiểm lại bằng `ipconfig getifaddr en0`, đổi mạng là đổi IP). mosquitto 2.1.2 đã cài (`/opt/homebrew/sbin/mosquitto`). Docker Desktop có nhưng CLI không nằm trong PATH |
| Pi | **Mac chưa thấy `edgeflow-pi.local`** (chưa bật, khác mạng, hoặc mDNS lỗi). Chưa biết Pi đã chạy `setup_pi.sh` chưa. Tôi chưa đụng vào Pi |
| ESP32 | **Chưa có `src/hardware/secrets.ini`**, tức chưa có SSID/mật khẩu Wi-Fi và IP broker (firmware mặc định trỏ `192.168.4.1`). Phải tạo rồi nạp lại cả 2 board |
| Code | F18–F30 vẫn chưa commit; tool demo là file mới chưa commit. `sync_to_pi.sh` gửi cả hai |

## A. Tập dượt không cần phần cứng (10 phút, làm ngay trên laptop)

```bash
cd ~/Documents/AI/VEDC/vedc-traffic-flow
uv venv -p 3.11 ~/edgeflow-demo && VIRTUAL_ENV=~/edgeflow-demo uv pip install paho-mqtt jsonschema
PY=~/edgeflow-demo/bin/python; D=src/hardware/demo

mosquitto -c infra/mosquitto/mosquitto.conf -v          # cửa sổ 1 (nếu macOS hỏi firewall: Allow)
$PY $D/esp32_simulator.py --node J1                      # cửa sổ 2: ESP32 ảo, thời gian thật
$PY $D/laptop_command_test.py test J1                    # cửa sổ 3: ~25 s, phải ra RESULT: PASS
```

Đạt khi: 10 dòng `[PASS]`, `switch_phase` ghi `APPLIED in ~5.0s`. Nếu đây đã lỗi thì lỗi nằm ở laptop, không phải phần cứng.

## B. ESP32: cấu hình mạng và nạp firmware

1. Wi-Fi **2.4 GHz** (ESP32 không bắt 5 GHz). Laptop, Pi và 2 ESP32 cùng một mạng, router không bật "client isolation".
2. Tạo `src/hardware/secrets.ini` từ `secrets.example.ini`: `WIFI_SSID`, `WIFI_PASS`, `MQTT_BROKER` = IP laptop. Nên đặt IP tĩnh/DHCP reservation cho laptop trên router, kẻo ESP32 trỏ vào IP cũ.
3. (Tuỳ chọn) `-D NTP_SERVER=\"<IP Pi>\"` để ESP32 lấy giờ từ Pi (chrony); không có thì bước `expired_command` sẽ `SKIP`, không phải lỗi.
4. Nạp từng board, dán nhãn ngay:

```bash
cd src/hardware
uvx --from platformio pio run -e J1 -t upload     # cắm board J1; không nạp được thì giữ nút BOOT khi thấy "Connecting..."
uvx --from platformio pio device monitor -e J1 | tee ~/edgeflow_runs/trace_J1.log
```

Đạt khi serial có `TRACE,…,R,R,ALL_RED` rồi sau 2 s `G,R,GREEN`, và `Connected! Subscribed to: edgeflow/v1/control/J1/command`. **Rút nguồn 5V ngoài khi đang cắm USB nạp.**

## C. Laptop ↔ ESP32 thật

```bash
mosquitto -c infra/mosquitto/mosquitto.conf -v      # nếu chưa chạy (đừng chạy cùng lúc với docker mqtt: trùng cổng 1883)
$PY $D/laptop_command_test.py status                # J1, J2 phải HEALTHY (vision báo MISSING là bình thường lúc này)
$PY $D/laptop_command_test.py send J1 EW            # ACCEPTED ngay, APPLIED sau ~5 s, đèn đổi
$PY $D/laptop_command_test.py cycle J1 J2 --period 12   # nhìn đèn đổi NS/EW trên sa bàn, Ctrl+C để dừng
mkdir -p ~/edgeflow_runs && $PY $D/laptop_command_test.py test J1 J2 --json ~/edgeflow_runs/test_$(date +%H%M).json
python src/hardware/verify_trace.py ~/edgeflow_runs/trace_J1.log     # chuỗi đèn thật phải [PASS]
```

Đạt khi `RESULT: PASS` cho cả J1 và J2, và `verify_trace.py` exit 0. Mỗi `[FAIL]` đều ghi lý do; đừng sửa test cho khớp, hãy xem firmware hay mạng sai.

## D. Pi gửi dữ liệu giả

Từ Mac (Pi phải ping/ssh được; nếu `.local` không phân giải thì dùng IP trong trang quản trị router):

```bash
bash infra/rpi/sync_to_pi.sh pi@<IP hoặc edgeflow-pi.local>      # gửi code + model, kiểm sha256
ssh pi@<...>
cd ~/vedc-traffic-flow
# Nếu đã chạy setup_pi.sh: PYP=.venv-pi/bin/python. Nếu chưa, venv tối thiểu (cần internet):
sudo apt install -y python3-venv && python3 -m venv ~/edgeflow-demo && ~/edgeflow-demo/bin/pip install paho-mqtt jsonschema
PYP=~/edgeflow-demo/bin/python
$PYP src/hardware/demo/pi_fake_telemetry.py --dry-run --duration 3                  # không cần mạng: in JSON, kiểm môi trường
$PYP src/hardware/demo/pi_fake_telemetry.py --mqtt-host 192.168.1.3 --scenario alternate
```

Trên laptop: `$PY $D/laptop_command_test.py monitor` phải thấy `edgeflow/v1/telemetry/J1` và `J2` mỗi giây, và `edgeflow/v1/health/vision` có `"mode":"FAKE_DATA"`. Tắt Pi giả (Ctrl+C) → health chuyển `OFFLINE`.

## E. Vòng kín: Pi giả → graph-control → ESP32

```bash
D=/Applications/Docker.app/Contents/Resources/bin/docker; open -a Docker   # chờ daemon lên
pkill mosquitto                                      # nhường cổng 1883 cho broker trong Docker
cp -n .env.example .env && sed -i '' -e 's/^EDGEFLOW_CONTROLLER=.*/EDGEFLOW_CONTROLLER=edgeflow/' \
  -e 's/^EDGEFLOW_TOPOLOGY=.*/EDGEFLOW_TOPOLOGY=tabletop_j1_j2_v1/' .env     # topology: KE_HOACH_DEPLOY.md G4
mosquitto_sub -h localhost -v -F '%U %t %p' -t 'edgeflow/v1/#' > ~/edgeflow_runs/closed_loop.log &   # chấm bằng flow_report.py
$D compose --profile hardware up -d --build
$D compose stop actuator                             # actuator ảo cũng ACK J1/J2, gây ACK trùng
$D compose logs -f graph-control
```

Rồi chạy Pi giả `--scenario ns_heavy` (hoặc `alternate`). Đạt khi:

- log graph-control có `Published ControlCommand to edgeflow/v1/control/J1/command`;
- ESP32 đổi pha theo lệnh (qua vàng 3 s, đỏ 2 s); `ns_heavy` thì pha NS được xanh lâu hơn EW;
- `status` luôn HEALTHY, không vào `FALLBACK_AUTONOMOUS`;
- telemetry `current_phase_id` đổi theo đèn thật (Pi giả đọc từ health của ESP32).

Đừng chạy `laptop_command_test.py test` lúc graph-control đang chạy: hai bên cùng ra lệnh sẽ lẫn.

Chấm tự động (17/10): `$PY $D/flow_report.py ~/edgeflow_runs/closed_loop.log --nodes J1,J2 --json ~/edgeflow_runs/closed_loop.json` phải ra `RESULT: PASS`. Trước khi có board, tập dượt cả vòng bằng `bash $D/closed_loop_rehearsal.sh` (README của demo).

## F. (Tuỳ chọn) Service vision thật với hình tổng hợp

Cần đã chạy `setup_pi.sh`. Tắt Pi giả trước (nếu không, 2 nguồn lẫn nhau; Pi giả tự từ chối khi vision thật đang chạy):

```bash
.venv-pi/bin/python services/vision/main.py --video synthetic --mqtt-host 192.168.1.3 --node-id J1
```

Health `edgeflow/v1/health/vision` có `status` HEALTHY và `phase_source` `esp32_health` cho J1 là đúng.

## G. Lưu bằng chứng (vào `~/edgeflow_runs/`)

`trace_J1.log`, `trace_J2.log`, `test_*.json`, output `status`, log graph-control, `DEPLOYED_FROM.txt` (trên Pi), ảnh/video đèn đổi pha.

## H. Sự cố thường gặp

| Triệu chứng | Nguyên nhân hay gặp |
|---|---|
| `status`: J1/J2 `MISSING` | ESP32 chưa vào Wi-Fi (xem serial: `Connecting to WiFi`), sai `MQTT_BROKER`, laptop đổi IP, firewall macOS chặn 1883, 5 GHz |
| `test`: `online` FAIL "no health" | như trên; hoặc board đang SAFE_STOP (nút khẩn cấp đang bấm) |
| `switch_phase` FAIL về thời gian | Wi-Fi trễ lớn; hoặc firmware bị sửa thời gian vàng/all-red. Kiểm bằng `verify_trace.py` (đo ngay trên serial) |
| Gửi `send` ra ACCEPTED nhưng không có APPLIED | Board vừa ở fallback và đang tự chuyển pha đó: chuyển pha do fallback tự khởi tạo không bao giờ có APPLIED. Gửi lại sau vài giây |
| Pi: `Cannot reach MQTT broker` | sai IP, broker chưa chạy, khác mạng, firewall |
| Pi giả báo "A real vision service is publishing" | `edgeflow-vision` đang chạy (systemd): `sudo systemctl stop edgeflow-vision` hoặc `--force` |
| `ping edgeflow-pi.local` lỗi | mDNS; thử `ssh`, hoặc tìm IP trong router, hoặc `arp -a` |
| Cổng 1883 đã bị dùng | mosquitto trên Mac và container `mqtt` chạy cùng lúc |

## Việc để lại sau tối nay

- Video ngã tư thật: chưa làm. Khi bàn tới, câu hỏi cần chốt là xuất file số liệu offline (JSONL/CSV) hay phát lại qua MQTT theo thời gian thực (`VIDEO_SOURCE=<file>` đã chạy được, thiếu ROI cho video đó).
- Cáp camera 22→15 pin, router 2.4 GHz, module đèn ×10: xem `MUA_SAM_CON_THIEU.md`.
