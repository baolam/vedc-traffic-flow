# Báo Cáo Tri Thức Toàn Diện Dự Án: EdgeFlow AI (VEDC 2026)
**Tài liệu bàn giao & Hướng dẫn dành cho Kỹ sư & AI Coding Agents**

---

## 1. 📌 TỔNG QUAN DỰ ÁN & BỐI CẢNH

- **Tên dự án**: **EdgeFlow AI** (Hệ thống điều khiển tín hiệu giao thông thích ứng thời gian thực dựa trên đồ thị mạng lưới & Edge AI).
- **Cuộc thi / Bối cảnh**: Dự án phục vụ cuộc thi **VEDC 2026** (Vietnam Embedded & AI Design Contest).
- **Vấn đề giải quyết**: Chấm dứt tình trạng lãng phí thời gian và ùn tắc tại các nút giao đô thị do chu kỳ đèn cố định (Fixed-Time) bằng cách điều khiển thích ứng (Adaptive Control) dựa trên dữ liệu hàng đợi và lưu lượng xe thực tế.
- **Mô hình toán học cốt lõi**:
  - Mạng lưới giao thông biểu diễn dạng Đồ thị động $G_t = (V, E, X_t)$:
    - $V$: Tập các nút giao thông (Intersections / Junctions: `J1`, `J2`, ...).
    - $E$: Tập các hướng tiếp cận / cung đường kết nối (`J1_N_IN`, `J1_S_IN`, ...).
    - $X_t$: Vector trạng thái thời gian thực (Độ dài hàng đợi $Q$, Lưu lượng xe $F$, Tốc độ trung bình $V$, Mật độ chiếm dụng $O$).
  - Thuật toán điều khiển chính:
    - **Max-Pressure Control Policy**: Tối ưu hóa chuyển pha dựa trên tổng áp lực luồng xe: $P(\text{phase}) = \sum_{a \in \text{approaches}} Q(a)$.
    - **Fixed-Time Baseline Controller**: Điều khiển tuần tự chu kỳ cố định làm đường chuẩn so sánh benchmark.

---

## 2. 🏗️ KIẾN TRÚC HỆ THỐNG & ĐƯỜNG TRUYỀN SỰ KIỆN

Dự án áp dụng kiến trúc **Contract-First Event-Driven Microservices**, đảm bảo tính độc lập và khả năng mở rộng cao:

```
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
  | SUMO/TraCI  |Telemetry|   G=(V,E)    |Telemetry| YOLO/Track |         |   Runner    |
  +------^------+         | Fixed / MP   |        +-------------+         +-------------+
         |                +------+-------+
         |                       | ControlCommand
         |                +------v-------+
         +----------------|   Actuator   |
          Actuator Adapter| StateMachine |
                          +--------------+
```

### 📡 Cây Chủ Đề MQTT (MQTT Topic Tree)
| Topic | Nguồn $\rightarrow$ Đích | JSON Schema | Ý nghĩa |
|---|---|---|---|
| `edgeflow/v1/telemetry/{node_id}` | Simulator / Vision $\rightarrow$ Graph-Control | `telemetry.json` | Cập nhật số liệu hàng đợi, lưu lượng, tốc độ thời gian thực |
| `edgeflow/v1/control/{node_id}/command` | Graph-Control $\rightarrow$ Actuator | `control_command.json` | Lệnh chuyển pha đèn tối ưu từ Controller |
| `edgeflow/v1/control/{node_id}/ack` | Actuator $\rightarrow$ System | `control_ack.json` | Xác nhận thực thi lệnh (`APPLIED` / `REJECTED`) |
| `edgeflow/v1/network/state` | Graph-Control $\rightarrow$ API / UI | Graph Object ($G_t$) | Trạng thái mạng lưới toàn cục |
| `edgeflow/v1/metrics/network` | Experiment Runner $\rightarrow$ UI | Metric Summary | Chỉ số hiệu năng (Waiting Time, Queue, Throughput) |
| `edgeflow/v1/health/{service}` | Tất cả Microservices | Health Check | Giám sát trạng thái hoạt động của từng container |

---

## 3. 🔍 CHI TIẾT TỪNG DỊCH VỤ & MODULE

### 1. `contracts/` - Trung Tâm Schema & Định Nghĩa Topology
- **`schemas/`**: Chứa 3 schema chuẩn: `telemetry.json`, `control_command.json`, `control_ack.json`.
- **`topology/`**: File JSON mô tả cấu trúc mạng lưới (`four_intersection_v1`, `three_way_junction_v1`, `multi_phase_v1`, `grid4x4`, `cologne8`, `hcm_realworld_v1`).
- **`contracts_sdk.py`**: Cung cấp hàm nạp schema, kiểm thử tính hợp lệ (`validate_payload`) và hàm tự động chuẩn hóa pha `normalize_topology_phases`.

### 2. `services/graph-control/` - Bộ Não Điều Khiển Mạng Lưới
- Lớp trừu tượng [BaseController](file:///d:/FPT%20University/VEDC/VEDC_src/vedc-traffic-flow/services/graph-control/controller.py#L5-L10).
- [MaxPressureController](file:///d:/FPT%20University/VEDC/VEDC_src/vedc-traffic-flow/services/graph-control/controller.py#L38-L79): Tính toán áp lực từng pha dựa trên `phase.approaches` và chọn pha có độ dài hàng đợi lớn nhất.
- [FixedTimeController](file:///d:/FPT%20University/VEDC/VEDC_src/vedc-traffic-flow/services/graph-control/controller.py#L12-L36): Luân phiên các pha theo chu kỳ đều đặn.

### 3. `services/actuator/` - Máy Trạng Thái An Toàn Chuyển Pha
- [ActuatorStateMachine](file:///d:/FPT%20University/VEDC/VEDC_src/vedc-traffic-flow/services/actuator/state_machine.py#L20-L101):
  - Kiểm tra điều kiện thời gian đèn xanh tối thiểu `min_green_s` (mặc định 10s).
  - Quản lý quy trình dọn đường an toàn: $\text{GREEN} \rightarrow \text{YELLOW (3s)} \rightarrow \text{ALL-RED (2s)} \rightarrow \text{GREEN (pha mới)}$.
  - Phát bản tin xác thực `control_ack` lên MQTT.

### 4. `services/simulator/` - Trình Mô Phỏng Kỹ Thuật Số (Digital Twin)
- **Chế độ SUMO (`USE_SUMO=true`)**: Sử dụng TraCI kết nối với SUMO, đồng bộ thời gian thực trạng thái xe và điều khiển đèn qua `traci.trafficlight.setPhase`.
- **Chế độ Nội bộ (`USE_SUMO=false`)**: Giả lập toán học nhẹ nhàng, độc lập để phục vụ kiểm thử nhanh và CI/CD mà không cần cài đặt SUMO binary.

### 5. `services/vision/` - Xử Lý Video / Camera Giao Thông
- [PerceptionEngine](file:///d:/FPT%20University/VEDC/VEDC_src/vedc-traffic-flow/services/vision/perception_engine.py): Tích hợp Object Detection (YOLO) và phân vùng ROI (Region of Interest) để đếm xe, tính vận tốc và xuất bản telemetry.

### 6. `services/api/` - Control Plane & REST API (FastAPI)
- Phục vụ API cung cấp danh sách kịch bản (`/api/v1/scenarios`), chi tiết topology (`/api/v1/topologies/{id}`), công cụ chuyển đổi SUMO net.xml (`/api/v1/topologies/convert-sumo`), danh sách camera HCM và bản đồ tương tác Dark Mode Folium.

### 7. `services/dashboard/` - Giao Diện Giám Sát IOC (React)
- Trực quan hóa sơ đồ mạng lưới giao thông (SVG Topology Map), bảng điều khiển chuyển đổi kịch bản (Control Panel), phân tích đồ thị hàng đợi thời gian thực và bản đồ camera TP.HCM.

### 8. `services/experiment-runner/` - Chạy Thực Nghiệm Tự Động & Benchmark
- Tự động hóa các đợt thí nghiệm so sánh giữa Fixed-Time và Max-Pressure theo nhiều random seed khác nhau, tự động xuất báo cáo `metrics.csv`, `events.jsonl`, `summary.json` và `environment.json` vào thư mục `artifacts/`.

### 9. `src/` - Các Công Cụ Tiện Ích & Đồ Thị Mạng Lưới
- `src/crawler/`: Thu thập dữ liệu camera giao thông TP.HCM.
- `src/graph/`: Thuật toán tạo đồ thị mạng lưới camera (BallTree Nearest Neighbors & Delaunay Triangulation).
- `src/tools/import_sumo_scenario.py`: Tải các bộ kịch bản chuẩn thế giới (`grid4x4`, `cologne8`, `ingolstadt21`) và tự động cấu hình hệ thống.

---

## 4. 🛡️ QUY CHUẨN KIẾN TRÚC BẤT BIẾN (GUARDRAILS)

Các Agent khi tiếp tục làm việc trên dự án phải tuân thủ nghiêm ngặt các điều sau (theo [AGENTS.md](file:///d:/FPT%20University/VEDC/VEDC_src/vedc-traffic-flow/AGENTS.md)):
1. **Schema Authority**: Toàn bộ hợp đồng dữ liệu, enum và topology ID bắt buộc phải gốc từ `contracts/`. Không tự tạo lại schema trong service con.
2. **Microservice Isolation**: Không import trực tiếp file mã nguồn giữa các thư mục microservice với nhau. Giao tiếp bắt buộc qua MQTT hoặc HTTP API.
3. **Controller & Actuator Abstraction**: Mọi thuật toán điều khiển mới phải kế thừa `BaseController` trong `controller.py`. Mọi cơ chế chấp hành tín hiệu phải tiêu thụ chuẩn `ControlCommand`.
4. **Kiểm thử**: Đảm bảo toàn bộ test suite vượt qua 100% trước khi hoàn thành task.

---

## 5. ⚡ HƯỚNG DẪN KHỞI CHẠY & KIỂM THỬ

### Khởi chạy hệ thống bằng Docker Compose:
```bash
# Khởi tạo file cấu hình
Copy-Item .env.example .env

# Chạy cụm mô phỏng đầy đủ (Khuyên dùng)
docker compose --profile simulation up --build -d

# Xem log thời gian thực
docker compose logs -f graph-control simulator

# Dừng hệ thống
docker compose down
```

### Chạy kiểm thử tự động (Pytest):
```bash
# Chạy toàn bộ 52 Unit & Contract Tests
python -m pytest tests/unit

# Chạy Integration Tests
python -m pytest tests/integration
```
*(Trạng thái hiện tại: **52/52 tests passed** hoàn hảo).*

---

## 6. 🚀 HƯỚNG DẪN TRIỂN KHAI TIẾP TIẾN ĐỘ DỰ ÁN (ROADMAP & NEXT ACTIONS)

Dưới đây là các hạng mục ưu tiên cao để Agent/Kỹ sư tiếp theo có thể lập tức triển khai:

1. **Phát triển Thuật toán RL / Multi-Agent Reinforcement Learning**:
   - Thêm class `RLController` trong `services/graph-control/controller.py` kế thừa từ `BaseController`.
   - Kết nối mô hình Deep Q-Network (DQN) hoặc PPO để huấn luyện chính sách chọn pha đèn thích ứng dựa trên trạng thái đồ thị $G_t$.
2. **Tích hợp Phần cứng Nhúng (Hardware-in-the-Loop - HIL)**:
   - Viết adapter kết nối với mạch vi điều khiển (ESP32 / Raspberry Pi) điều khiển hệ thống đèn LED tín hiệu mô hình thực tế, nhận lệnh qua MQTT topic `edgeflow/v1/control/{node_id}/command` và gửi lại `control_ack`.
3. **Mở rộng Kịch bản Giao thông TP.HCM trong SUMO**:
   - Sử dụng `src/tools/import_sumo_scenario.py` để bổ sung các nút giao thực tế tại TP.HCM (như Vòng xoay Dân Chủ, Ngã 6 Phù Đổng) vào hệ thống mô phỏng SUMO.
4. **Tối ưu hóa Mô hình Thị giác Máy tính (Edge AI)**:
   - Tối ưu hóa `services/vision/` với định dạng mô hình TensorRT hoặc ONNX Runtime để đạt tốc độ xử lý trên 30 FPS trên các thiết bị biên như NVIDIA Jetson.
5. **Nâng cấp Giao diện So sánh Hiệu năng (Benchmark Dashboard)**:
   - Thêm trang so sánh side-by-side kết quả thực nghiệm giữa Fixed-Time và Max-Pressure/RL ngay trên Dashboard React.
