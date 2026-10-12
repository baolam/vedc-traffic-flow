# Báo Cáo Tổng Hợp Hệ Thống, Benchmark Mới Nhất & Thiết Kế Kiến Trúc EdgeFlow AI

- **Dự án**: EdgeFlow AI — Adaptive Traffic Signal Control System
- **Thời gian lập**: 2026-10-12
- **Trạng thái xác thực**: Toàn bộ kiểm thử Unit (207/207), Contract (8/8) và Integration (6/6) đã vượt qua.

---

## 1. Tổng Hợp & Phân Tích Kết Quả Chạy Benchmark Mới Nhất

### 1.1. Bối cảnh & Đối soát số liệu kiểm toán
Dựa trên chiến dịch benchmark đối soát [`KIEM_TRA_SO_LIEU_SUMO_20261012.md`](file:///e:/vedc-traffic-flow/KIEM_TRA_SO_LIEU_SUMO_20261012.md) (`seed=101`, 60 runs bao gồm 4 mạng lưới × 3 kịch bản × 5 bộ điều khiển):

1. **Khắc phục lỗi Exporter**:
   - Trường `completion_rate` và trường `arrivals_measurement_veh_per_s` trong [`batch_runner.py`](file:///e:/vedc-traffic-flow/services/experiment-runner/batch_runner.py) đã được đồng bộ chính xác với cấu trúc `summary.json`. 
   - Loại bỏ hoàn toàn tình trạng số liệu Throughput xuất sai thành `0.0` và Completion Rate báo ảo `100%`.
2. **Hiện tượng nghẽn tràn hạ lưu (Spillback)**:
   - Số liệu đã phản ánh trung thực hiện tượng giải thuật tham lam đơn nút `max_queue` gây nghẽn nghiêm trọng tại hành lang TP.HCM ([`hcm_corridor`](file:///e:/vedc-traffic-flow/contracts/topology/hcm_corridor.json)), khiến Completion Rate tụt xuống **72.41% - 73.17%** và Throughput giảm **-26.09%**.

---

### 1.2. Bảng đối chiếu hiệu năng cốt lõi (Pilot Benchmark)

#### A. Phân đoạn Hành lang Đô thị TP.HCM (`hcm_corridor`)

| Kịch bản | Bộ điều khiển | Thời gian chờ TB | Chờ P95 | Hàng đợi TB | Hàng đợi P95 | Thông lượng (xe/s) | Tỷ lệ hoàn thành | Tăng thông lượng vs FT |
|:---|:---|:---:|:---:|:---:|:---:|:---:|:---:|:---:|
| **balanced** | `fixed_time` (Baseline) | 91.17s | 371.8s | 44.20 | 57.05 | 0.3833 | **100.0%** | Baseline |
| | `max_queue` | 14.52s | 37.0s | 47.60 | 52.00 | 0.2833 | **72.41%** | **-26.09%** *(Nghẽn mạng)* |
| | `max_pressure` | **14.10s** | 40.4s | **14.92** | **22.05** | **0.5333** | **100.0%** | **+39.13%** |
| | `flow_theory` | 15.54s | **34.0s** | 15.52 | 24.05 | 0.5167 | 82.76% | +34.80% |
| | **`edgeflow`** | 23.26s | 90.1s | 22.35 | 29.05 | 0.4500 | 93.10% | **+17.40%** |
| **directional_surge** | `fixed_time` (Baseline) | 100.41s | 297.0s | 39.88 | 49.10 | 0.5167 | **100.0%** | Baseline |
| | `max_queue` | 18.37s | 37.65s | 48.53 | 56.05 | 0.4667 | 73.17% | -9.68% |
| | `max_pressure` | 29.41s | 61.0s | 14.07 | 20.00 | 0.5500 | **100.0%** | +6.44% |
| | `flow_theory` | **13.58s** | **34.15s** | **10.45** | **18.00** | **0.7500** | 92.68% | **+45.15%** |
| | **`edgeflow`** | 34.45s | 78.25s | 22.13 | 32.00 | 0.5333 | 92.68% | +3.21% |
| **downstream_congestion** | `fixed_time` (Baseline) | 89.97s | 359.4s | 43.87 | 57.05 | 0.3833 | **100.0%** | Baseline |
| | `max_queue` | 14.52s | 37.0s | 47.60 | 52.00 | 0.2833 | 72.41% | -26.09% |
| | `max_pressure` | 15.31s | 44.6s | **14.50** | **22.05** | **0.5333** | **100.0%** | **+39.13%** |
| | `flow_theory` | **14.25s** | **33.55s** | 14.80 | 24.00 | 0.5167 | 82.76% | +34.80% |
| | **`edgeflow`** | 24.70s | 113.7s | 22.10 | 28.00 | 0.4500 | 93.10% | +17.40% |

#### B. Phân đoạn Lưới Ô Bàn Cờ (`grid4x4` - 16 nút giao)

| Kịch bản | Bộ điều khiển | Thời gian chờ TB | Chờ P95 | Hàng đợi TB | Hàng đợi P95 | Thông lượng (xe/s) | Tỷ lệ hoàn thành | Tăng thông lượng vs FT |
|:---|:---|:---:|:---:|:---:|:---:|:---:|:---:|:---:|
| **balanced** | `fixed_time` (Baseline) | 146.21s | 224.7s | 149.40 | 207.00 | 0.7333 | 100.0% | Baseline |
| | `max_queue` | **19.21s** | **38.9s** | **16.45** | **22.00** | **1.2000** | 100.0% | **+63.64%** |
| | `max_pressure` | 64.62s | 116.0s | 77.43 | 95.05 | 1.1500 | 100.0% | **+56.83%** |
| | `flow_theory` | 24.27s | 43.0s | 27.43 | 36.20 | 1.1500 | 100.0% | **+56.83%** |
| | **`edgeflow`** | 104.43s | 148.8s | 106.87 | 123.05 | 0.7500 | 100.0% | +2.28% |

---

### 1.3. Nhận định cốt lõi & Cải tiến đã tích hợp
1. **Hiện tượng phân hóa giữa Hành lang và Lưới ô bàn cờ**:
   - Ở mạng lưới ô bàn cờ (`grid4x4`), dung lượng các nhánh lớn và đối xứng giúp thuật toán tham lam `max_queue` xả xe rất nhanh.
   - Nhưng trên hành lang hẹp (`hcm_corridor`), `max_queue` không tính tới nhánh hạ lưu nên gây nghẽn dây chuyền làm tụt hơn 26% thông lượng.
2. **Thuật toán `max_pressure` & `flow_theory`**:
   - Nhờ xét chênh lệch áp lực upstream/downstream, `max_pressure` đạt tỷ lệ hoàn thành 100% trong mọi kịch bản trên hành lang.
3. **Cải tiến của EdgeFlow (v2.5)**:
   - Đã tích hợp **Time-Decaying Hysteresis** (giảm độ lì giữ pha khi hàng đợi phía sau tăng) và **Downstream Capacity Penalization** (phạt điểm nặng các pha đẩy xe vào nhánh hạ lưu đang đầy ứ) trong [`src/control/controllers.py`](file:///e:/vedc-traffic-flow/src/control/controllers.py).

---

## 2. Hướng Dẫn Vận Hành & Phát Triển (How to Run & Develop)

### 2.1. Hướng dẫn chạy (Execution Guide)

#### A. Chạy kiểm thử tự động
```powershell
# Chạy toàn bộ Unit Tests (207 tests)
.venv\Scripts\python.exe -m pytest tests/unit

# Chạy kiểm thử Hợp đồng Schemas (8 tests)
.venv\Scripts\python.exe -m pytest tests/unit/test_contracts.py

# Chạy kiểm thử tích hợp (6 tests)
.venv\Scripts\python.exe -m pytest tests/integration
```

#### B. Khởi chạy toàn bộ hạ tầng Microservices (Docker Compose)
```powershell
# Khởi động Broker MQTT, API, Dashboard, Control Core, Actuator, Simulator
docker-compose up -d --build

# Kiểm tra trạng thái các container
docker-compose ps
```

#### C. Chạy Benchmark thực nghiệm SUMO
Hệ thống hỗ trợ 2 cơ chế:
1. **Chạy song song tối ưu hóa tốc độ (Đa tiến trình)**:
   ```powershell
   .venv\Scripts\python.exe services/experiment-runner/batch_runner_parallel.py --config configs/benchmark_fast.json
   ```
2. **Chạy benchmark chuẩn hóa**:
   ```powershell
   .venv\Scripts\python.exe services/experiment-runner/batch_runner.py --output artifacts/
   ```

---

### 2.2. Hướng dẫn mở rộng mã nguồn (Developer Guide)

Theo quy định bất biến tại [`AGENTS.md`](file:///e:/vedc-traffic-flow/AGENTS.md):

#### A. Cách viết thêm một Controller mới
Mọi bộ điều khiển phải kế thừa [`BaseController`](file:///e:/vedc-traffic-flow/src/control/controllers.py) trong [`src/control/controllers.py`](file:///e:/vedc-traffic-flow/src/control/controllers.py):
```python
from typing import Dict, Any, List
from src.control.controllers import BaseController

class CustomAdaptiveController(BaseController):
    def __init__(self, node_id: str, phases: List[Dict[str, Any]], **kwargs):
        super().__init__(node_id, phases)
        # Khởi tạo tham số cấu hình riêng

    def compute_next_phase(
        self,
        current_phase_idx: int,
        phase_duration_s: float,
        telemetry: Dict[str, Any]
    ) -> int:
        # 1. Bảo đảm an toàn thời gian xanh tối thiểu
        if phase_duration_s < self.min_green_s:
            return current_phase_idx

        # 2. Tính toán điểm ưu tiên các pha
        # telemetry chứa: {link_id: {"queue": float, "flow": float, ...}}
        target_phase = current_phase_idx
        # ... logic tính toán ...
        return target_phase
```

#### B. Cách định nghĩa Topology hoặc Kịch bản mới
1. **Topology**: Khai báo file JSON cấu hình mạng lưới trong [`contracts/topology/`](file:///e:/vedc-traffic-flow/contracts/topology). Phải có đầy đủ `nodes`, `edges`, `links` và `phases`.
2. **Kiểm thử hợp đồng**: Bắt buộc chạy `.venv\Scripts\python.exe -m pytest tests/unit/test_contracts.py` sau khi sửa schema hoặc topology.

---

## 3. Sơ Đồ Tổ Chức Code Hệ Thống (Architectural Blueprint)

```
+========================================================================================================+
|                                  EDGEFLOW AI - ARCHITECTURE BLUEPRINT                                  |
+========================================================================================================+

                                +-----------------------------------+
                                |            CONTRACTS/             |
                                |    (Schema Authority - Single     |
                                |        Source of Truth)           |
                                +-----------------+-----------------+
                                                  |
              +-----------------------------------+-----------------------------------+
              |                                   |                                   |
              v                                   v                                   v
+-----------------------------+     +-----------------------------+     +-----------------------------+
|    TELEMETRY PRODUCERS      |     |     EDGE-AI CONTROL CORE    |     |      ACTUATION ENGINE       |
|                             |     |                             |     |                             |
| 1. services/simulator/      |     | 1. services/graph-control/  |     | 1. services/actuator/       |
|    • sumo_engine.py         |     |    • main.py                |     |    • main.py (State Machine)|
|    • traffic_engine.py      |     |    • graph_contracts_...py  |     |    • config.py              |
|                             |     |                             |     |                             |
| 2. services/vision/         |     | 2. src/control/             |     | 2. src/hardware/ (Physical) |
|    • main.py (YOLO/Camera)  |     |    • controllers.py         |     |    • firmware_esp32/        |
|    • vision_contracts_...py |     |      (Fixed/Queue/Pressure/ |     |      (Yellow/All-Red Safe   |
|                             |     |       Flow/EdgeFlow)        |     |       Clearance & Watchdog) |
+--------------+--------------+     +--------------+--------------+     +--------------^--------------+
               |                                   ^                                   |
               | [edgeflow/telemetry/{node_id}]    |                                   | [edgeflow/control/{node_id}]
               v                                   |                                   |
    +--------------------------------------------------------------------------------------+
    |                      ECLIPSE MOSQUITTO MQTT BROKER (:1883)                           |
    |                   (Trục xương sống giao tiếp tin cậy & phi ghép nối)                 |
    +--------------------------------------+-----------------------------------------------+
                                           |
                                           | [edgeflow/telemetry & control/*]
                                           v
                             +----------------------------+
                             |   OBSERVABILITY & SUITE    |
                             |                            |
                             | 1. services/api/ (FastAPI) |
                             |    • REST & WS: :8000      |
                             | 2. services/dashboard/     |
                             |    • React IOC: :3000      |
                             | 3. services/experiment-    |
                             |    runner/ (Benchmark)     |
                             +----------------------------+
```

### Chi tiết các thư mục mã nguồn:

- **`contracts/`**: Trung tâm thẩm quyền hợp đồng dữ liệu. Chứa JSON schemas, dataclasses ([`models.py`](file:///e:/vedc-traffic-flow/contracts/models.py)), kênh giao tiếp ([`topics.py`](file:///e:/vedc-traffic-flow/contracts/topics.py)), và các mạng lưới giao thông chuẩn hóa.
- **`services/`**: Các microservices độc lập:
  - `actuator`: Quản lý máy trạng thái chuyển đèn an toàn (`GREEN -> YELLOW -> ALL-RED`).
  - `api`: Control plane FastAPI cung cấp REST endpoints và WebSocket stream dữ liệu.
  - `dashboard`: Giao diện React hiển thị bản đồ trực quan và biểu đồ hiệu năng.
  - `experiment-runner`: Bộ công cụ thực thi benchmark ma trận (hỗ trợ đa tiến trình).
  - `graph-control`: Bộ não điều khiển nhận telemetry mạng lưới và xuất lệnh điều khiển tín hiệu.
  - `simulator`: Mô phỏng vi mô SUMO tích hợp cầu nối TraCI.
  - `vision`: Module camera AI YOLO trên Raspberry Pi trích xuất độ dài hàng đợi từ sa bàn.
- **`src/`**: Mã nguồn thuật toán & phần cứng:
  - `control/`: Thư viện các bộ điều khiển và lớp máy trạng thái chấp hành.
  - `hardware/`: Mã nguồn firmware vi điều khiển ESP32 và sơ đồ mạch LED.
  - `graph/`: Công cụ trích xuất và chuyển đổi mạng lưới SUMO sang biểu diễn đồ thị.
  - `rl/`: Môi trường huấn luyện học tăng cường.
- **`configs/`**: Cấu hình thí nghiệm benchmark (`benchmark_fast.json`).
- **`artifacts/`**: Báo cáo tổng hợp số liệu đo kiểm độ trễ và benchmark.
- **`tests/`**: Bộ kiểm thử tự động toàn diện (Unit, Contract, Integration).
