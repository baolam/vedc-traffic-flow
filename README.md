# EdgeFlow AI - Adaptive Traffic Signal Control System

**EdgeFlow AI** là hệ thống điều khiển tín hiệu giao thông thích ứng thời gian thực (Real-time Adaptive Traffic Signal Control System) dựa trên đồ thị mạng lưới giao thông $G=(V,E)$ và kiến trúc Microservices hướng sự kiện (Event-Driven Microservices). Hệ thống giúp tối ưu hóa luồng giao thông, giảm thiểu thời gian chờ và ùn tắc tại các nút giao thông đô thị.

---

## 🚀 Các Tính Năng Cốt Lõi (Key Features)

- **Network-Level Graph State Representation**: Biểu diễn toàn bộ mạng lưới giao thông dưới dạng đồ thị $G=(V,E)$, thu thập các chỉ số thời gian thực như độ dài hàng đợi (queue length), lưu lượng xe (flow rate), tốc độ trung bình (speed) và độ chiếm dụng (occupancy).
- **Max-Pressure Control Policy**: Tích hợp thuật toán điều khiển tối ưu hóa Max-Pressure giúp tự động chuyển pha đèn dựa trên chênh lệch áp lực luồng xe vào/ra tại từng nút giao.
- **Contract-First Microservice Architecture**: Đảm bảo tính nhất quán dữ liệu giữa các dịch vụ thông qua JSON Schema tập trung (`contracts/`) và trục giao tiếp không đồng bộ MQTT.
- **Digital Twin Traffic Simulation**: Tích hợp trình mô phỏng giao thông SUMO (Simulation of Urban MObility) qua TraCI làm môi trường mô phỏng kỹ thuật số để đánh giá benchmark.
- **Safety Actuator State Machine**: Đảm bảo an toàn giao thông tuyệt đối với máy trạng thái kiểm soát thời gian chuyển pha đèn an toàn (Green $\rightarrow$ Yellow $\rightarrow$ All-Red).
- **Real-Time Interactive Dashboard**: Giao diện React hiển thị trực quan bản đồ mạng lưới nút giao (bao gồm các Topology thực tế tại TP.HCM), thông số telemetry thời gian thực và biểu đồ hiệu năng.

---

## 🏗️ Kiến Trúc Hệ Thống (System Architecture)

```text
                       +-------------------+
                       |   IOC Dashboard   |
                       |  (React - :3000)  |
                       +---------+---------+
                                 | REST / WebSocket
                       +---------v---------+
                       |    API Backend    |
                       | (FastAPI - :8000) |
                       +---------+---------+
                                 | MQTT Broker (Mosquitto - :1883)
        +------------------------+------------------------+
        |                        |                        |
 +------v------+          +------v-------+         +------v------+
 |  Simulator  |--------->| Graph-Control|<--------|   Vision    |
 |    SUMO     |Telemetry |  G=(V,E)     |Telemetry| YOLO/Track  |
 +------^------+          | Fixed / MP   |         +-------------+
        |                 +------+-------+
        |                        | ControlCommand
        |                 +------v-------+
        +-----------------|   Actuator   |
         Actuator Adapter |   Adapter    |
                          +--------------+
```

### Chi tiết các Microservices (`services/`)

| Service | Công nghệ / Protocol | Vai trò & Trách nhiệm chính |
|---|---|---|
| **MQTT Broker** | Mosquitto (Port 1883) | Trục xương sống sự kiện (Telemetry, ControlCommand, ACK, Metrics) |
| **API Backend** | FastAPI / WebSocket (Port 8000) | Quản lý thí nghiệm, lưu trữ log lịch sử (SQLite), stream trạng thái WS |
| **Graph-Control** | Python / NetworkX | Quản lý đồ thị trạng thái $G_t$, tính toán áp lực Max-Pressure & ra lệnh điều khiển |
| **Simulator** | SUMO / TraCI | Mô phỏng giao thông kỹ thuật số, phát sinh dữ liệu telemetry thực tế |
| **Vision** | OpenCV / PyTorch / YOLO | Dịch vụ xử lý hình ảnh camera giao thông, trích xuất đếm xe & telemetry |
| **Actuator** | Python State Machine | Máy trạng thái an toàn điều khiển pha đèn (Green/Yellow/All-Red) & gửi ACK |
| **Dashboard** | React / Web (Port 3000) | Giao diện điều hành trực quan hóa mạng lưới, bản đồ & theo dõi telemetry |

---

## 📁 Cấu Trúc Thư Mục Dự Án (Repository Structure)

```text
edgeflow-ai/
├── contracts/               # JSON Schemas hợp đồng dữ liệu & định nghĩa Topology
│   ├── schemas/             # Telemetry, ControlCommand, ControlACK Schemas
│   └── topology/            # four_intersection_v1, hcm_realworld_v1, multi_phase_v1...
├── services/                # Mã nguồn các Microservices độc lập
│   ├── actuator/            # Safe Phase Actuator State Machine
│   ├── api/                 # FastAPI REST & WebSocket Backend
│   ├── dashboard/           # React Web Application
│   ├── graph-control/       # Graph Network Controller (Max-Pressure / Fixed-Time)
│   ├── simulator/           # SUMO Simulation Adapter
│   └── vision/              # Camera Traffic Perception Engine
├── src/                     # Các công cụ hỗ trợ & thu thập dữ liệu
│   ├── crawler/             # Thu thập dữ liệu camera giao thông TP.HCM
│   ├── graph/               # Xây dựng đồ thị mạng lưới camera (Delaunay / Distance)
│   └── visualization/       # Công cụ trực quan hóa đồ thị & bản đồ
├── data/                    # Dữ liệu thô và dữ liệu đã xử lý (HCM Camera Graph data)
├── infra/                   # Cấu hình hạ tầng (Mosquitto MQTT configuration)
├── output/                  # Chứa kết quả xuất file, đồ thị HTML
├── tests/                   # Bộ kiểm thử (Unit, Contract, Integration/Smoke tests)
├── docker-compose.yml       # Cấu hình khởi chạy đa dịch vụ Container
└── Makefile                 # (Tùy chọn) Phím tắt cho môi trường có Make
```

---

## ⚡ Hướng Dẫn Chạy Dự Án Bằng Docker (Quick Start)

Dự án sử dụng **Docker Compose v2** làm phương thức khởi chạy chính, tương thích hoàn toàn trên Windows, macOS và Linux mà không cần cài đặt `make`.

### 1. Yêu cầu môi trường
- **Docker** & **Docker Compose v2** (Docker Desktop trên Windows / macOS)
- **Python 3.9+** (để chạy bộ kiểm thử local nếu cần)

### 2. Thiết lập cấu hình
Tạo file cấu hình môi trường từ mẫu:
- **Bash / Terminal (Linux/macOS/Git Bash)**:
  ```bash
  cp .env.example .env
  ```
- **Windows PowerShell**:
  ```powershell
  Copy-Item .env.example .env
  ```

### 3. Khởi chạy hệ thống bằng Docker Compose

#### 🔹 Chạy Stack Mô phỏng (Simulation Stack - Khuyên dùng):
Khởi chạy MQTT Broker, API, Graph-Control, SUMO Simulator, Actuator và Dashboard:
```bash
docker compose --profile simulation up --build
```
*(Thêm tham số `-d` nếu muốn chạy nền: `docker compose --profile simulation up -d --build`)*

#### 🔹 Các lệnh quản lý Docker thông dụng:
- **Kiểm tra trạng thái các container**:
  ```bash
  docker compose ps
  ```
- **Xem log thời gian thực**:
  ```bash
  docker compose logs -f
  # Hoặc xem log của dịch vụ cụ thể (ví dụ: simulator, graph-control):
  docker compose logs -f simulator
  ```
- **Dừng toàn bộ hệ thống**:
  ```bash
  docker compose down
  ```

---

### 🌐 Địa Chỉ Truy Cập Sau Khi Chạy Docker

- 🖥️ **Dashboard UI (React)**: [http://localhost:3000](http://localhost:3000)
- 📡 **API Backend & Swagger Docs**: [http://localhost:8000/docs](http://localhost:8000/docs)
- 🔌 **MQTT Broker**: `localhost:1883`

---

## 🧪 Kiểm Thử & Đảm Bảo Chất Lượng (Testing)

Bạn có thể chạy kiểm thử trực tiếp bằng Python (`pytest`) mà không cần `make`:

```bash
# 1. Validate JSON Schemas và các Hợp đồng dữ liệu (Contract Tests)
python -m pytest tests/unit/test_contracts.py

# 2. Chạy toàn bộ Unit Tests (Graph Controller, Actuator State Machine, Simulator...)
python -m pytest tests/unit

# 3. Chạy Integration Tests cho các Microservices
python -m pytest tests/integration

# 4. Chạy Smoke Test kiểm tra hệ thống trên Docker
docker compose --profile simulation up -d --build
python -m pytest tests/integration/test_smoke.py
```

*(Lưu ý: Nếu môi trường của bạn có cài đặt `make`, bạn cũng có thể dùng các phím tắt như `make up-sim`, `make test`, `make contracts`)*.

---

## 📜 Tài Liệu Tham Khảo (Documentation Links)

- [ARCHITECTURE.md](ARCHITECTURE.md): Sơ đồ chi tiết kiến trúc microservice, MQTT Topic Tree và luồng dữ liệu.
- [DEVELOPMENT.md](DEVELOPMENT.md): Hướng dẫn chi tiết thiết lập môi trường phát triển.
- [AGENTS.md](AGENTS.md): Quy chuẩn kiến trúc & quy tắc phát triển dành cho Developers / Coding Agents.
- [CONTRIBUTING.md](CONTRIBUTING.md): Quy định đặt tên branch và quy trình đóng góp mã nguồn.

---

## 📄 Giấy Phép (License)
Dự án được phát triển dưới quy chuẩn mã nguồn mở cho hệ thống giao thông thông minh.
