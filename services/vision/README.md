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
```bash
# On Raspberry Pi 5 terminal (pointed to Laptop Server MQTT Broker)
pip install -r requirements.txt
python main.py --video 0 --mqtt-host <LAPTOP_SERVER_IP> --node-id J1
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
- **CPU Temperature**: Automatically reads `/sys/class/thermal/thermal_zone0/temp` and publishes status to `edgeflow/v1/health/vision`.
- **Camera Failure State**: If the camera is disconnected or blocked, the service emits `confidence: 0.0` with zero queues (never fabricates fake traffic).
