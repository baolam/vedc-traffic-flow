# EdgeFlow AI — Adaptive Traffic Signal Control System

**EdgeFlow AI** là hệ thống điều khiển tín hiệu giao thông thích ứng thời gian thực (*Real-Time Adaptive Traffic Signal Control System*) dựa trên đồ thị mạng lưới $G=(V,E)$ và kiến trúc phân tán 3 tầng (**Laptop Server $\leftrightarrow$ Raspberry Pi 5 Edge AI $\leftrightarrow$ ESP32 Hardware Actuators**). Hệ thống giúp tối ưu hóa luồng giao thông, giảm thiểu thời gian chờ và chống ùn tắc lan truyền (*spillback*) tại các nút giao thông đô thị phức tạp.

---

## 🏛️ Kiến Trúc Hệ Thống 3 Tầng (3-Tier Distributed Architecture)

Hệ thống được thiết kế theo mô hình 3 tầng phân tán chuyên biệt, liên lạc thông suốt qua mạng cục bộ bằng giao thức **MQTT (Port 1883)** và **REST / WebSocket API**:

```
+-----------------------------------------------------------------------------------------+
|                                TẦNG 1: LAPTOP / SERVER CHÍNH                            |
|                            (Chạy toàn bộ dịch vụ Docker Compose)                         |
|                                                                                         |
|  • MQTT Broker (:1883)       : Trục xương sống sự kiện trung tâm (Eclipse Mosquitto)    |
|  • Graph-Control             : Bộ não tính toán thích ứng (EdgeFlow / Max-Pressure / RL)|
|  • API Backend (:8000)       : FastAPI Control Plane & Quản lý thực nghiệm               |
|  • IOC Dashboard (:3000)     : Giao diện điều hành trực quan thời gian thực (React)     |
|  • Simulator & Runner        : Digital Twin SUMO & Công cụ chạy Benchmark khoa học       |
+--------------------------------------------+--------------------------------------------+
                                             | Mạng WiFi Cục Bộ (MQTT 1883)
                     +-----------------------+-----------------------+
                     |                                               |
+--------------------v--------------------+     +--------------------v--------------------+
|       TẦNG 2: RASPBERRY PI 5 (EDGE AI)  |     |   TẦNG 3: MẠCH CHẤP HÀNH VẬT LÝ (ESP32)  |
|         (services/vision)               |     |        (src/hardware/firmware)          |
|                                         |     |                                         |
| • 📷 Camera Module 3 / USB (/dev/video0) |     | • 2x Board ESP32 NodeMCU (Nút J1 & J2)  |
| • 🧠 AI Thị Giác: YOLOv8 / OpenCV DNN   |     | • 💡 8 Cụm Đèn LED Sa bàn (24 LEDs)     |
| • 🚦 Trích xuất hàng đợi theo nhánh ROI |     | • 🛡️ Safe Clearance (Green->Yel->AllRed)|
| • 📡 Bắn Telemetry lên Laptop Broker    |     | • ⏱️ Watchdog Fallback 15s khi mất mạng |
| • 🌡️ Giám sát nhiệt độ CPU & Nghẽn nhiệt|     | • 🛑 Nút ngắt khẩn cấp Safe-Stop (GPIO 4)|
+-----------------------------------------+     +-----------------------------------------+
```

---

## 🚀 Các Tính Năng Cốt Lõi (Key Features)

- **Network-Level Graph State Representation**: Biểu diễn toàn bộ mạng lưới giao thông dưới dạng đồ thị động $G_t=(V,E,X_t)$, thu thập thời gian thực các chỉ số telemetry như độ dài hàng đợi (*queue length*), lưu lượng xe (*flow rate*), tốc độ trung bình (*speed*) và độ chiếm dụng (*occupancy*).
- **Novel EdgeFlow Controller (v2.5)**: Thuật toán điều khiển thích ứng độc quyền tích hợp **Rào cản phi tuyến chống tràn xe (Nonlinear Spillback Barrier)**, **Đồng pha làn sóng xanh (Platoon Progression)**, và **Chống bỏ quên pha (Service-Age Fairness)**.
- **Microservices & Schema Authority**: Đảm bảo tính toàn vẹn và đồng bộ dữ liệu tuyệt đối giữa Laptop, Raspberry Pi và ESP32 thông qua JSON Schema chuẩn hoá trong [`contracts/`](file:///e:/vedc-traffic-flow/contracts).
- **Dual Operating Modes**:
  1. **Chế độ Nghiên cứu Mô phỏng (SUMO Mode)**: Laptop chạy mô phỏng vi mô SUMO qua TraCI, benchmark ma trận hàng nghìn xe.
  2. **Chế độ Trình diễn Sa bàn Thực tế (Hardware Demo Mode)**: Raspberry Pi 5 ghi hình sa bàn, gửi Telemetry thay cho SUMO; 2 ESP32 chấp hành bật/tắt 8 cụm đèn LED vật lý theo thời gian thực.
- **Hardware Safety Failsafe**: ESP32 kiểm soát chuyển pha an toàn tuyệt đối ($\text{GREEN} \rightarrow \text{YELLOW (3.0s)} \rightarrow \text{ALL-RED (2.0s)} \rightarrow \text{GREEN}$), tự động chuyển sang chế độ dự phòng cục bộ khi mất kết nối mạng $> 5.0\text{s}$.
- **Real-Time IOC Dashboard**: Giao diện React hiển thị trực quan bản đồ mạng lưới giao thông, thông số telemetry thời gian thực, trạng thái các pha đèn và biểu đồ so sánh hiệu năng.

---

## 📁 Cấu Trúc Thư Mục Dự Án (Repository Structure)

```text
edgeflow-ai/
├── contracts/               # Hợp đồng dữ liệu canonical & định nghĩa Topology
│   ├── schemas/             # JSON Schemas (telemetry.json, control_command.json, control_ack.json)
│   ├── topology/            # File cấu hình Topology (four_intersection_v1, hcm_realworld_v1, grid4x4...)
│   └── contracts_sdk.py     # Python SDK kiểm thử & validate hợp đồng dữ liệu
│
├── services/                # [LAPTOP & PI] Các dịch vụ Microservices độc lập
│   ├── actuator/            # Safe Phase Actuator State Machine Service
│   ├── api/                 # FastAPI REST & WebSocket Backend Service (Control Plane)
│   ├── dashboard/           # React IOC Dashboard Web Application
│   ├── experiment-runner/   # Automated Experiment Benchmark Runner
│   ├── graph-control/       # Graph Network Adaptive Controller Service
│   ├── simulator/           # SUMO Digital Twin Simulation Adapter Service
│   └── vision/              # [RASPBERRY PI 5] Camera Traffic Perception Engine Service
│
├── src/                     # [RESEARCH LAB & HARDWARE] Mã nguồn nghiên cứu, công cụ & phần cứng
│   ├── crawler/             # Bộ thu thập dữ liệu camera giao thông TP.HCM (Playwright)
│   ├── graph/               # Thuật toán xây dựng đồ thị Delaunay & Converter SUMO .net.xml
│   ├── hardware/            # [ESP32] Firmware vi điều khiển, sơ đồ mạch điện & bảng BOM dự toán
│   ├── rl/                  # Pipeline huấn luyện Reinforcement Learning (DQN / Gym Env)
│   ├── tools/               # Công cụ import benchmark SUMO-RL & Launcher SUMO-GUI
│   └── visualization/       # Bản đồ tương tác Folium cho dữ liệu camera TP.HCM
│
├── data/                    # Dữ liệu thô và dữ liệu đồ thị camera TP.HCM
├── artifacts/               # Lưu trữ kết quả thí nghiệm & chỉ số benchmark
├── output/                  # Chứa file kết quả xuất bản đồ & biểu đồ
├── tests/                   # Bộ kiểm thử tự động (Unit, Contract, Integration tests)
├── docker-compose.yml       # Cấu hình Docker Compose chạy toàn bộ stack trên Laptop Server
├── docker-compose.rpi.yml   # Cấu hình Docker Compose phân tán dành riêng cho Raspberry Pi 5
├── .env.rpi.example         # File mẫu cấu hình biến môi trường cho Raspberry Pi
├── Makefile                 # Các lệnh phím tắt hỗ trợ phát triển & kiểm thử
├── AGENTS.md                # Quy chuẩn kiến trúc & Guardrails bất biến
├── ARCHITECTURE.md          # Chi tiết thiết kế kiến trúc 3 tầng & MQTT Topic Tree
├── DEVELOPMENT.md           # Hướng dẫn thiết lập môi trường phát triển & demo
└── CONTRIBUTING.md          # Quy trình đóng góp mã nguồn
```

---

## ⚡ Hướng Dẫn Khởi Chạy (Quick Start)

> [!TIP]
> **Hướng dẫn chi tiết toàn bộ các chế độ chạy:** Xem [`docs/SYSTEM_RUN_MODES.md`](file:///e:/vedc-traffic-flow/docs/SYSTEM_RUN_MODES.md) (Pure Simulation, 3-Tier Demo, Edge Control, Standalone Pi, Experiment & Benchmark).

### 1. Khởi chạy Server Chính trên Laptop (Docker Stack)
```bash
# Khởi động toàn bộ dịch vụ (Broker, Control, API, Dashboard)
docker-compose up -d

# Hoặc khởi chạy bằng Python cục bộ:
make run-server
```
Truy cập Dashboard điều hành tại: `http://localhost:3000` (hoặc `http://localhost:8000/dashboard`).

### 2. Khởi chạy Tầng Nhận Thức trên Raspberry Pi 5 (Docker hoặc Python)
Xem chi tiết hướng dẫn đầy đủ tại [`docs/RASPBERRY_PI_DISTRIBUTED_GUIDE.md`](file:///e:/vedc-traffic-flow/docs/RASPBERRY_PI_DISTRIBUTED_GUIDE.md).

```bash
# Cách 1: Chạy bằng Docker Compose (Khuyến nghị cho chạy phân tán):
# (Chỉ chạy Vision gửi dữ liệu về Broker Laptop)
docker compose -f docker-compose.rpi.yml --profile vision up -d

# (Hoặc chạy Standalone trọn gói Dashboard + Control + Vision trên Pi):
docker compose -f docker-compose.rpi.yml --profile standalone up -d

# Cách 2: Chạy trực tiếp bằng Python trên Pi 5:
cd services/vision
pip install -r requirements.txt
python main.py --video 0 --mqtt-host <IP_LAPTOP>
```

### 3. Nạp Firmware cho 2 Board ESP32 (Chấp hành Đèn)
- Mở file [`src/hardware/firmware/esp32_signal_controller.ino`](file:///e:/vedc-traffic-flow/src/hardware/firmware/esp32_signal_controller.ino) bằng Arduino IDE / PlatformIO.
- Chọn `NODE_ID` tương ứng: `"J1"` cho ngã tư 1 hoặc `"J2"` cho ngã tư 2.
- Nạp code vào ESP32 và cấp nguồn 5V. Hệ thống sẽ tự động kết nối và nhận lệnh chuyển pha an toàn.

---

## 🧪 Kiểm Thử Hệ Thống (Verification)

```bash
# Chạy kiểm thử Hợp đồng dữ liệu
pytest tests/unit/test_contracts.py

# Chạy toàn bộ Unit Tests
pytest tests/unit
```


## Shared Double DQN research track

For the isolated four-intersection SUMO benchmark, training, validation, reproducibility limits, and promotion gate, see [the shared DQN research guide](docs/SHARED_DQN_RESEARCH.md).

---
