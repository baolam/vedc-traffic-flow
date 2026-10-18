# EdgeFlow AI — Vision Perception & Raspberry Pi 5 Edge Service

> [!IMPORTANT]
> **Raspberry Pi 5 Role in EdgeFlow AI**:
> This service acts as the **Edge Vision Perception Engine** deployed on **Raspberry Pi 5** (with Camera Module 3 or USB Camera). In physical demonstrations (VEDC Semifinal Tabletop Corridor), this service replaces the SUMO simulator by extracting live vehicle queue metrics from the sa bàn and emitting canonical `Telemetry` messages over MQTT.

---

## 🏗️ Architecture

```
                                  [ Tabletop Corridor / Camera Feed ]
                                                   |
                                                   v
                          +-------------------------------------------------+
                          |             Raspberry Pi 5 (Edge AI)            |
                          |                                                 |
                          |  +--------------------+   +-------------------+ |
                          |  | Camera VideoSource |-->|  YOLOv8 / OpenCV  | |
                          |  +--------------------+   +-------------------+ |
                          |                                     |           |
                          |  +--------------------+   +---------v---------+ |
                          |  |  Hardware Monitor  |   |    ROI Manager    | |
                          |  |  (CPU Temp / Diag) |   |  (Queue by Phase) | |
                          |  +--------------------+   +---------+---------+ |
                          |            |                        |           |
                          |  +---------v----------+   +---------v---------+ |
                          |  | Health Heartbeat   |   | Canonical Payload | |
                          |  | edgeflow/v1/health |   | edgeflow/v1/telem | |
                          |  +--------------------+   +-------------------+ |
                          +------------------------+------------------------+
                                                   | MQTT (1883)
                                                   v
                                     [ Local Broker / Coordinator ]
```

---

## ⚙️ Configuration (`config.py`)

All settings can be customized via environment variables:

| Environment Variable | Default | Description |
|---|---|---|
| `VIDEO_SOURCE` | `synthetic` | `0` (for `/dev/video0`), `picamera`, `synthetic`, or path to `.mp4` file |
| `VISION_NODE_ID` | `J1` | Target intersection node ID in the canonical topology contract |
| `DETECTION_MODEL_PATH` | `""` | Path to YOLO `.onnx` or weights (falls back to OpenCV MOG2 if empty) |
| `CONFIDENCE_THRESHOLD` | `0.4` | Confidence score cutoff for vehicle bounding boxes |
| `TELEMETRY_PERIOD_S` | `1.0` | Ingestion & Telemetry publish period in seconds |
| `ENABLE_HARDWARE_TELEMETRY` | `true` | Periodic CPU temperature (°C) & health telemetry reporting |
| `MQTT_HOST` | `localhost` | Host of MQTT Broker (Mosquitto) |
| `MQTT_PORT` | `1883` | Port of MQTT Broker |

---

## 🚀 Running on Raspberry Pi 5

### 1. Bare-metal Execution (Recommended for Physical Demo)
Raspberry Pi OS **Trixie** 64-bit, Camera Module 3 on the CSI port. Do not `pip install -r requirements.txt`
on the Pi (a pip numpy/OpenCV breaks the apt picamera2), and do not use `--video 0`: on Pi 5 the CSI camera
is only readable through Picamera2 (`--video picamera`).
```bash
bash infra/rpi/sync_to_pi.sh               # on the Mac: the repo is private, so push the tree + models over ssh
bash infra/rpi/setup_pi.sh                 # apt packages, venv with system site-packages, .env.rpi, chrony
bash infra/rpi/preflight.sh                # OS, OpenCV >= 4.8, camera, .env.rpi as systemd reads it, model, ROI, broker
# Manual run: main.py reads environment variables only, never .env.rpi by itself (systemd loads it for the service)
set -a; . ./.env.rpi; set +a; .venv-pi/bin/python services/vision/main.py
bash infra/rpi/setup_pi.sh --service       # then run it under systemd: journalctl -u edgeflow-vision -f
```
Keep comments in `.env.rpi` on their own lines: systemd keeps `KEY=value  # comment` as part of the value
(preflight fails on it).

Measure before choosing the model input size (stop the service first, it holds the camera):
```bash
.venv-pi/bin/python services/vision/benchmark.py --source picamera --width 1280 --height 720 \
    --model models/yolo11n_416.onnx --input-size 416 --frames 300 --output artifacts/pi_bench_416.json
```
Record dataset frames for fine-tuning through the same capture path (one folder per session):
```bash
.venv-pi/bin/python services/vision/capture_dataset.py --session s01_low_daylight --out ~/dataset \
    --video picamera --width 1280 --height 720 --lens-position 2.0 --every 1.0 --duration 120
```

### 2. Docker Execution on Raspberry Pi 5
Sử dụng file cấu hình tối ưu sẵn [`docker-compose.rpi.yml`](file:///e:/vedc-traffic-flow/docker-compose.rpi.yml):

```bash
# Khởi chạy Vision Perception kết nối tới Broker trên Laptop:
docker compose -f docker-compose.rpi.yml --profile vision up -d

# Hoặc khởi chạy trọn gói Standalone Edge Gateway (Vision + Control + Dashboard trên Pi):
docker compose -f docker-compose.rpi.yml --profile standalone up -d
```
Xem hướng dẫn chi tiết tại [`docs/RASPBERRY_PI_DISTRIBUTED_GUIDE.md`](file:///e:/vedc-traffic-flow/docs/RASPBERRY_PI_DISTRIBUTED_GUIDE.md).

---

## 📊 Hardware Monitoring & Failsafe
- **Health topic** `edgeflow/v1/health/vision` (retained, every 10 s and on each reconnect): `status`
  (`STARTING`/`HEALTHY`/`DEGRADED` with a `reason`, `OFFLINE` from the MQTT will or on shutdown), model and
  ROI sha256, and **measured** `runtime` figures over the last 30 s: processed FPS, p50/p95 of capture,
  preprocess, inference, postprocess, publish and `age_at_publish_ms`; `hardware`: SoC temperature,
  `vcgencmd get_throttled` flags, Pi 5 USB-C input voltage, load and free memory (`null` where not measurable).
  The same summary is logged once per period (`journalctl -u edgeflow-vision`).
- **Telemetry time**: `timestamp_ms` is the capture time of the newest frame in the period.
- **Current phase**: `current_phase_id` is the phase the ESP32 reports on `edgeflow/v1/health/{node}` (sent every
  5 s and on each switch to GREEN). Without a report in the last 15 s, or after the device's `OFFLINE` will, it is
  the topology's first phase and the vision health shows `phase_source: default` for that node (else
  `esp32_health`). The EdgeFlow controller times green and service age from this field: a fixed phase inverts
  its priorities.
- **Frames vs. telemetry**: frames are processed continuously up to `VISION_FPS`; every `TELEMETRY_PERIOD_S`
  one message per node carries the per-approach **median** over that period's frames. `confidence` is the share
  of the period's frames actually captured and processed (1.0 with a healthy camera, as the simulator sends).
- **Camera field of view**: Picamera2 is pinned to the full-sensor mode (2304x1296 binned on Camera Module 3).
  Left alone, libcamera picks the 1536x864 centre-crop mode for a 1280x720 output and the Wide lens loses
  a third of its view in each direction.
- **Camera Failure State**: If the camera is disconnected or blocked, the service emits `confidence: 0.0` with zero queues (never fabricates fake traffic).
