# EdgeFlow AI - Adaptive Traffic Signal Control System

**EdgeFlow AI** là hệ thống điều khiển tín hiệu giao thông thích ứng thời gian thực (Real-Time Adaptive Traffic Signal Control System) dựa trên đồ thị mạng lưới giao thông $G=(V,E)$ và kiến trúc Microservices hướng sự kiện (Event-Driven Microservices). Hệ thống giúp tối ưu hóa luồng giao thông, giảm thiểu thời gian chờ và chống ùn tắc tại các nút giao thông đô thị phức tạp.

---

## 🚀 Các Tính Năng Cốt Lõi (Key Features)

- **Network-Level Graph State Representation**: Biểu diễn toàn bộ mạng lưới giao thông dưới dạng đồ thị động $G_t=(V,E,X_t)$, thu thập thời gian thực các chỉ số telemetry như độ dài hàng đợi (queue length), lưu lượng xe (flow rate), tốc độ trung bình (speed) và độ chiếm dụng (occupancy).
- **Adaptive Control Policies**: Tích hợp các thuật toán điều khiển tiên tiến bao gồm **Max-Pressure Control Policy** (tự động chuyển pha đèn dựa trên chênh lệch áp lực luồng xe vào/ra) và **Fixed-Time Baseline Policy** để benchmark đánh giá hiệu năng.
- **Contract-First Microservices Architecture**: Đảm bảo tính toàn vẹn và đồng bộ dữ liệu giữa các dịch vụ độc lập thông qua tập JSON Schema trung tâm trong `contracts/` và đường truyền sự kiện bất đồng bộ MQTT.
- **Digital Twin Traffic Simulation**: Kết nối trực tiếp với trình mô phỏng giao thông SUMO (Simulation of Urban MObility) qua giao tiếp TraCI làm môi trường mô phỏng kỹ thuật số.
- **Safety Actuator State Machine**: Đảm bảo an toàn giao thông tuyệt đối với máy trạng thái kiểm soát chuyển pha an toàn (Green $\rightarrow$ Yellow $\rightarrow$ All-Red) và phản hồi xác thực lệnh (Control ACK).
- **Multi-Topology Support**: Hỗ trợ linh hoạt nhiều bản đồ nút giao khác nhau từ mô phỏng đến thực tế: `four_intersection_v1`, `three_way_junction_v1`, `multi_phase_v1`, `grid4x4`, `cologne8`, và `hcm_realworld_v1` (dữ liệu camera mạng lưới TP.HCM).
- **Real-Time IOC Dashboard**: Giao diện React hiển thị trực quan sơ đồ mạng lưới giao thông, thông số telemetry thời gian thực, trạng thái các pha đèn và biểu đồ so sánh hiệu năng.
- **Automated Experiment Runner**: Dịch vụ chuyên biệt hỗ trợ thực thi các kịch bản thực nghiệm tự động (`experiment-runner`), ghi nhận và xuất báo cáo đánh giá benchmark.

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
         +-----------------------+-----------------------+-----------------------+
         |                       |                       |                       |
  +------v------+         +------v-------+        +------v------+         +------v------+
  |  Simulator  |-------->| Graph-Control|<-------|   Vision    |         | Experiment  |
  |    SUMO     |Telemetry|   G=(V,E)    |Telemetry| YOLO/Track |         |   Runner    |
  +------^------+         | Fixed / MP   |        +-------------+         +-------------+
         |                +------+-------+
         |                       | ControlCommand
         |                +------v-------+
         +----------------|   Actuator   |
          Actuator Adapter|   Adapter    |
                          +--------------+
```

### Chi tiết các Dịch vụ Microservices (`services/`)

| Service | Công nghệ / Protocol | Cổng / Interface | Vai trò & Trách nhiệm chính |
|---|---|---|---|
| **MQTT Broker** | Eclipse Mosquitto | `1883` | Trục xương sống sự kiện (Telemetry, ControlCommand, ControlACK, Network State, Health, Metrics) |
| **API Backend** | FastAPI / SQLite / WebSockets | `8000` | Quản lý thí nghiệm, lưu trữ log lịch sử, cung cấp REST API và stream dữ liệu WebSocket |
| **Graph-Control** | Python / NetworkX | MQTT | Quản lý đồ thị trạng thái $G_t$, tính toán áp lực luồng xe (Max-Pressure / Fixed-Time) và phát ControlCommand |
| **Simulator** | SUMO / TraCI / Python | MQTT | Trình mô phỏng giao thông kỹ thuật số, phát sinh dữ liệu telemetry ground-truth |
| **Vision** | OpenCV / PyTorch / YOLO | MQTT | Dịch vụ thị giác máy tính xử lý video camera giao thông, đếm lượng xe và gửi telemetry |
| **Actuator** | Python Safe State Machine | MQTT | Máy trạng thái an toàn điều khiển pha đèn (Green/Yellow/All-Red), đảm bảo mìn-time và gửi ACK |
| **Dashboard** | React / Web UI | `3000` | Giao diện trung tâm điều hành (IOC Dashboard), trực quan hóa bản đồ, chỉ số thời gian thực |
| **Experiment Runner**| Python Automation | MQTT | Chạy các kịch bản thí nghiệm benchmark tự động, đo đạc chỉ số và thu thập log kết quả |

---

## 📁 Cấu Trúc Thư Mục Dự Án (Repository Structure)

```text
edgeflow-ai/
├── contracts/               # Hợp đồng dữ liệu canonical & định nghĩa Topology
│   ├── schemas/             # JSON Schemas (telemetry.json, control_command.json, control_ack.json)
│   ├── topology/            # File cấu hình Topology (four_intersection_v1, hcm_realworld_v1, grid4x4...)
│   └── contracts_sdk.py     # Python SDK kiểm thử & validate hợp đồng dữ liệu
├── services/                # Mã nguồn các dịch vụ Microservices độc lập
│   ├── actuator/            # Safe Phase Actuator State Machine Service
│   ├── api/                 # FastAPI REST & WebSocket Backend Service
│   ├── dashboard/           # React IOC Dashboard Web Application
│   ├── experiment-runner/   # Automated Experiment Benchmark Runner
│   ├── graph-control/       # Graph Network Controller Service
│   ├── simulator/           # SUMO Digital Twin Simulation Adapter Service
│   └── vision/              # Camera Traffic Perception Engine Service
├── src/                     # Các module công cụ & xử lý dữ liệu mạng lưới HCM
│   ├── crawler/             # Công cụ thu thập dữ liệu camera giao thông TP.HCM
│   ├── graph/               # Thuật toán xây dựng đồ thị nút giao camera (Delaunay / Distance)
│   └── visualization/       # Trực quan hóa bản đồ và xuất đồ thị HTML
├── data/                    # Dữ liệu thô và dữ liệu đã xử lý (HCM Camera Graph data)
├── infra/                   # Cấu hình hạ tầng (Mosquitto MQTT configuration)
├── artifacts/               # Lưu trữ kết quả thí nghiệm & chỉ số benchmark
├── output/                  # Chứa file kết quả xuất bản đồ & biểu đồ đồ thị
├── tests/                   # Bộ kiểm thử tự động (Unit, Contract, Integration, Smoke tests)
├── docker-compose.yml       # Cấu hình khởi chạy Container đa dịch vụ theo Profile
├── Makefile                 # Các lệnh phím tắt hỗ trợ phát triển & kiểm thử
├── AGENTS.md                # Quy chuẩn kiến trúc & Guardrails cho Coding Agents / Developers
├── ARCHITECTURE.md          # Chi tiết thiết kế kiến trúc & MQTT Topic Tree
├── DEVELOPMENT.md           # Hướng dẫn thiết lập môi trường phát triển cục bộ
└── CONTRIBUTING.md          # Quy trình đóng góp mã nguồn & quy chuẩn git branch
```

---

## ⚡ Hướng Dẫn Khởi Chạy (Quick Start)

Dự án hỗ trợ khởi chạy linh hoạt thông qua **Docker Compose v2** (khuyên dùng cho tất cả môi trường Windows, macOS, Linux) hoặc qua **Makefile** / **Python CLI**.

### 1. Yêu cầu môi trường
- **Docker** & **Docker Compose v2** (khuyên dùng Docker Desktop)
- **Python 3.9+** (để thực hiện kiểm thử hoặc phát triển local)

### 2. Thiết lập cấu hình môi trường
Tạo file cấu hình môi trường từ file mẫu `.env.example`:

- **Linux / macOS / Git Bash**:
  ```bash
  cp .env.example .env
  ```
- **Windows PowerShell**:
  ```powershell
  Copy-Item .env.example .env
  ```

### 3. Khởi chạy bằng Docker Compose Profiles

Tùy theo mục đích sử dụng, chọn Profile Docker Compose phù hợp:

#### 🔹 Chạy Stack Mô phỏng (Simulation Stack - Khuyên dùng):
Khởi chạy MQTT Broker, API Backend, Graph Controller, SUMO Simulator, Actuator và Dashboard UI:
```bash
docker compose --profile simulation up --build
```
*(Thêm cờ `-d` để chạy ẩn dưới nền: `docker compose --profile simulation up -d --build`)*

#### 🔹 Chạy các Profiles khác:
- **Profile Vision (Sử dụng camera thực tế)**:
  ```bash
  docker compose --profile vision up --build
  ```
- **Profile Thí nghiệm (Experiment Runner)**:
  ```bash
  docker compose --profile experiment up --build
  ```
- **Profile Môi trường Phát triển (Toàn bộ dịch vụ - Dev Stack)**:
  ```bash
  docker compose --profile dev up --build
  ```

#### 🔹 Quản lý Docker Containers:
- **Kiểm tra trạng thái dịch vụ**:
  ```bash
  docker compose ps
  ```
- **Xem log thời gian thực**:
  ```bash
  docker compose logs -f [tên_service]
  # Ví dụ: docker compose logs -f graph-control simulator
  ```
- **Dừng toàn bộ hệ thống**:
  ```bash
  docker compose down
  ```

---

## 🌐 Địa Chỉ Truy Cập Dịch Vụ

Sau khi khởi chạy Docker thành công, truy cập các địa chỉ sau:

- 🖥️ **IOC Dashboard UI (React)**: [http://localhost:3000](http://localhost:3000)
- 📡 **API Backend & OpenAPI Docs (FastAPI)**: [http://localhost:8000/docs](http://localhost:8000/docs)
- 🔌 **MQTT Broker**: `localhost:1883`

---

## 🧪 Kiểm Thử & Đảm Bảo Chất Lượng (Testing)

Hệ thống có quy trình kiểm thử tự động toàn diện từ Contract, Unit, Integration đến Smoke tests.

### Chạy trực tiếp bằng Python (`pytest`):
```bash
# 1. Kiểm thử hợp đồng dữ liệu JSON Schemas (Contract Tests)
python -m pytest tests/unit/test_contracts.py

# 2. Chạy toàn bộ Unit Tests (Graph Controller, Actuator State Machine, Simulator...)
python -m pytest tests/unit

# 3. Chạy Integration Tests giữa các Microservices
python -m pytest tests/integration

# 4. Kiểm thử Smoke Test trên hạ tầng Docker đang chạy
docker compose --profile simulation up -d --build
python -m pytest tests/integration/test_smoke.py
```

### Chạy bằng `Makefile` (Nếu môi trường hỗ trợ `make`):
```bash
make contracts       # Validate các JSON schemas & topology contracts
make test            # Chạy toàn bộ unit tests
make integration     # Chạy integration tests
make check-all       # Chạy tổng hợp contracts, unit tests và integration tests
make smoke           # Chạy smoke test tự động trên Docker
make up-sim          # Phím tắt khởi chạy simulation stack
make down            # Dừng Docker containers
make experiment EXP=<name> # Chạy kịch bản thực nghiệm chỉ định
```

---

## 🛡️ Nguyên Tắc Kiến Trúc & Guardrails

Dự án tuân thủ nghiêm ngặt các quy tắc kiến trúc ghi trong [AGENTS.md](AGENTS.md):
1. **Schema Authority**: Toàn bộ hợp đồng dữ liệu, enum và topology ID bắt buộc phải gốc từ `contracts/`. Không định nghĩa lại schema riêng lẻ trong các microservice.
2. **Microservice Isolation**: Không import trực tiếp mã nguồn giữa các dịch vụ với nhau. Mọi giao tiếp liên dịch vụ phải thông qua MQTT Topic hoặc REST/WebSocket API.
3. **Controller & Actuator Abstractions**: Mọi bộ điều khiển (Fixed-Time, Max-Pressure) phải tuân thủ chuẩn giao diện Controller chung. Actuator phải tiêu thụ chuẩn `ControlCommand` thống nhất.

---

## 📜 Tài Liệu Tham Khảo (Documentation Links)

- [ARCHITECTURE.md](ARCHITECTURE.md): Sơ đồ thiết kế chi tiết kiến trúc microservices, MQTT Topic Tree và luồng dữ liệu.
- [DEVELOPMENT.md](DEVELOPMENT.md): Hướng dẫn thiết lập môi trường phát triển cục bộ và cấu hình công cụ.
- [AGENTS.md](AGENTS.md): Bảng quy chuẩn kiến trúc & bất biến hệ thống dành cho Developers và AI Coding Agents.
- [CONTRIBUTING.md](CONTRIBUTING.md): Quy định đặt tên branch, quy trình commit và đóng góp mã nguồn.

---

## 📄 Giấy Phép (License)

Dự án EdgeFlow AI được phát triển dưới quy chuẩn mã nguồn mở phục vụ nghiên cứu và phát triển các Hệ Thống Giao Thông Thông Minh (ITS - Intelligent Transportation Systems).
