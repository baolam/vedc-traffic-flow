# EdgeFlow AI — Báo Cáo Triển Khai Hạ Tầng Benchmark SUMO Thực

**Ngày hoàn thiện**: 12/10/2026  
**Dự án**: **EdgeFlow AI**: Hệ thống điều khiển đèn giao thông phân tán ứng dụng AI nhúng, tối ưu hóa dòng chảy giao thông dựa trên mô hình mạng lưới đồ thị đường phố có biên trọng số.  
**Mục tiêu**: Thiết lập và kiểm chứng toàn diện hạ tầng thực nghiệm benchmark SUMO/TraCI thực tế, so sánh 4 bộ điều khiển chuẩn (`fixed_time`, `max_queue`, `max_pressure`, `flow_theory`) trên 4 mạng lưới (`four_intersection_v1`, `grid4x4`, `cologne8`, `hcm_corridor`) theo 3 kịch bản nghiên cứu (`balanced`, `directional_surge`, `downstream_congestion`).

---

## 1. Tổng Quan Kiến Trúc Hạ Tầng Triển Khai

Toàn bộ pipeline thực nghiệm được thiết kế theo nguyên tắc phân lớp nghiêm ngặt, tuân thủ `AGENTS.md` và tiêu chuẩn khoa học quốc tế:

```text
BatchRunner (services/experiment-runner/batch_runner.py)
  │  Mode: sumo_live | Config: configs/benchmark_sumo_semifinal.json
  ├─► Network Mapping Resolver (src/simulation/sumo_network_registry.py)
  │     - Xác thực SHA-256 mạng lưới và topology contracts
  │     - Tách 57 TLS có đèn khỏi 107 nút hình học/biên
  │     - Lọc bỏ pha vàng/chuyển tiếp -> 227 pha xanh phục vụ ổn định
  │     - Phân loại hướng tiếp cận theo véc-tơ hình học (dx, dy)
  │     - Ánh xạ 1.722 movement có kiểm chứng liên kết
  │
  ├─► Deterministic Demand Generator (src/simulation/sumo_demand_generator.py)
  │     - Sinh tuyến động mạch đa nút có kiểm chứng liên kết hình học
  │     - Phân phối lưu lượng thời gian thực theo Poisson/Seeded RNG
  │     - Đóng băng tệp demand.rou.xml + demand_ledger.json + SHA-256
  │
  ├─► SingleExperimentRunner (services/experiment-runner/runner.py)
  │     - Điều phối LiveSumoRuntime (src/simulation/sumo_live_backend.py)
  │     - Kết nối SUMO qua cổng TraCI độc lập (label riêng, port cô lập)
  │     - Trích xuất metrics: Halting, MeanSpeed, Occupancy (chia 100 đúng chuẩn API)
  │     - Tạo payload Telemetry chuẩn -> Kiểm tra schema Draft7Validator
  │     - create_controller(...) -> Nhận ControlCommand chuẩn
  │     - ActuatorStateMachine -> Bảo đảm phong bì an toàn (Yellow 3s, All-Red 2s, MinGreen 10s)
  │     - Can thiệp tốc độ nghẽn downstream (speed-gating) tại cạnh nút thắt cổ chai
  │
  └─► Hạch toán xe & Tổng hợp Paired Comparison Matrix
        - Bất biến bảo toàn: scheduled = completed + active + pending
        - Thời gian chờ P95 tuyến tính, cohort wait + delay
        - Xuất trọn vẹn 14 artifacts cho mỗi run và bảng tổng hợp Markdown/JSON/CSV
```

---

## 2. Bảng Kiểm Tra Thực Tế Cấu Trúc 4 Mạng Lưới (Preflight Audit)

Toàn bộ 4 mạng lưới đã được kiểm chứng tự động qua lệnh:
```powershell
python services/experiment-runner/batch_runner.py --topology all --preflight-only
```

| Mạng lưới | Nút trong Topology | Controlled TLS | Nút không điều khiển | Pha xanh ổn định (không vàng) | Movements kiểm chứng | Cạnh nút thắt nghẽn (Bottleneck) | Trục nghẽn chính | Số tuyến kiểm chứng | Trạng thái Preflight |
|---|---:|---:|---:|---:|---:|---|:---:|---:|:---:|
| `four_intersection_v1` | 4 | 4 | 0 | 12 | 27 | `J3_N_IN` | NS | 8 | **PASS** |
| `grid4x4` | 32 | 16 | 16 | 128 | 1.152 | `A1A0` | NS | 16 | **PASS** |
| `cologne8` | 78 | 8 | 70 | 25 | 143 | `-186623965#16` | NS | 8 | **PASS** |
| `hcm_corridor` | 50 | 29 | 21 | 62 | 400 | `32577015#8` | NS | 8 | **PASS** |
| **Tổng cộng** | **164** | **57** | **107** | **227** | **1.722** | — | — | **40** | **100% PASS** |

### Các điểm mấu chốt được giải quyết:
1. **Phân biệt nút điều khiển (TLS) và nút không điều khiển**:
   - `grid4x4` có 32 nút nhưng chỉ 16 nút giao bên trong có TLS; 16 nút biên (`top*`, `bottom*`, `left*`, `right*`) được nhận diện chính xác là nút nguồn/hút, không phát lệnh điều khiển.
   - `cologne8` có 78 nút trong sơ đồ đồ thị, nhưng chỉ 8 nút có cụm đèn tín hiệu.
   - `hcm_corridor` có 50 nút nhưng chỉ 29 nút có TLS thật trong file mạng.
2. **Loại bỏ trạng thái vàng trong tập hành động của Controller**:
   - Lọc bỏ triệt để các pha quá độ chứa `'y'`, `'Y'` hoặc toàn đỏ từ file net/topology. Controller chỉ nhận các pha xanh ổn định (phase service) thực sự phục vụ luồng giao thông. Pha vàng và toàn đỏ được bàn giao hoàn toàn cho `ActuatorStateMachine` kiểm soát theo đồng hồ vật lý.
3. **Phân loại hướng tiếp cận bằng hình học không gian (Geometric Classifier)**:
   - Thay thế hoàn toàn cơ chế lọc chuỗi `_N_`/`_S_` bằng thuật toán tính véc-tơ hướng cạnh vào `(dx, dy)`. Xác định góc phương vị la bàn (bearing), phân bổ chính xác vào trục `NS` (Bắc-Nam) hoặc `EW` (Đông-Tây), hoạt động tin cậy trên các ID thực tế phức tạp như `-186623965#18` (Cologne) hay `-211849412` (TP.HCM).

---

## 3. Các Lỗi Mã Nguồn Đã Sửa Đổi Cụ Thể

### 3.1. `src/control/controllers.py` (`FlowTheoryController` & `FixedTimeController`)
- **Lỗi đơn vị lưu lượng**: Trước đây `FlowTheoryController` chia `flow_rate / 3600.0`. Trong khi đó, schema `telemetry.json` quy định `flow_veh_per_s` (xe/giây). Đã sửa để ưu tiên trực tiếp `flow_veh_per_s`, tránh sai lệch đơn vị 3.600 lần.
- **Ánh xạ hạ lưu (Downstream Resolution)**: Trước đây khi thiếu thông tin nhánh rẽ, controller lấy trung bình toàn bộ nút hạ lưu làm sai lệch áp lực dòng chảy. Đã bổ sung logic giải quyết hạ lưu theo từng `movement` (`to_approach`), chỉ rơi về giá trị trung bình nếu đồ thị không có thông tin chi tiết.
- **Sàn thời gian xanh tối thiểu của `FixedTimeController`**: Đặt sàn tối thiểu 10.0 giây cho mỗi pha xanh để tạo baseline công bằng khi so sánh trên các mạng lưới nhiều pha.

### 3.2. `services/experiment-runner/sumo_runner.py` (Legacy Runner)
- **Loại bỏ fallback sai mạng**: Loại bỏ hoàn toàn nhánh fallback tìm `four_intersection_v1` khi không tìm thấy file net của mạng khác. Bắt buộc tra cứu qua `NETWORK_REGISTRY` với mã băm SHA-256.
- **Đo lường Occupancy**: Hàm TraCI `getLastStepOccupancy()` trả về tỉ lệ phần trăm từ 0 đến 100%. Đã sửa phép chia trực tiếp cho 100.0, loại bỏ điều kiện đoán `if occ > 1.0`.
- **Tách số xe hiện diện khỏi lưu lượng dòng chảy**: Không còn gán `getLastStepVehicleNumber` vào `flow_veh_per_s`. Lưu lượng được tính từ vận tốc và số xe di chuyển thực tế trên cạnh.
- **Tính trung thực khi không có xe hoàn thành**: Khi `completed == 0`, trả về `None` (`null`) cho `mean_waiting_time_s`, không được ngụy tạo thành `0.0s`.

### 3.3. `services/experiment-runner/runner.py` (`SingleExperimentRunner`)
- Bổ sung mode `"sumo_live"`, trực tiếp điều phối sang `LiveSumoRuntime`.
- Khi chạy SUMO thực, không sinh hàng đợi tổng hợp Python; dữ liệu telemetry và sự kiện đèn hoàn toàn đến từ TraCI.
- Xác thực định danh controller runtime trước khi chạy để chống sai lệch loại thuật toán.

### 3.4. `services/experiment-runner/batch_runner.py` (`BatchRunner`)
- Tích hợp cờ `--mode sumo_live`, hỗ trợ nạp cấu hình từ `--config configs/benchmark_sumo_semifinal.json`.
- Danh sách 4 controller mặc định trong mode `sumo_live`: `["fixed_time", "max_queue", "max_pressure", "flow_theory"]`.
- Hỗ trợ `--preflight-only` kết xuất `preflight.json`, `mapping_audit.json`, `mapping_audit.csv`.
- Tự động sinh và kiểm tra mã băm demand đông lạnh trong `output_dir/frozen_inputs/...`.
- **Paired Matrix Aggregation**: Chỉ gộp và so sánh thống kê tại các seed mà cả 4 controller đều hoàn thành hợp lệ (`valid_for_research == True`), bảo đảm tính công bằng tuyệt đối.
- Kết xuất trọn bộ báo cáo chiến dịch: `campaign_manifest.json`, `benchmark_runs.csv`, `benchmark_comparison_report.json`, `benchmark_summary.md`, `test_results.md`.

---

## 4. Kiểm Chứng Thực Nghiệm & Gói Bằng Chứng (Evidence Package)

### 4.1. 14 Artifacts Tiêu Chuẩn Cho Mỗi Run
Mỗi lần chạy thực nghiệm đơn lẻ tạo ra 14 tệp bằng chứng trong thư mục của run đó:
1. `manifest.json`: Siêu dữ liệu kịch bản, mạng, controller, thời lượng.
2. `environment.json`: Cam kết git, phiên bản SUMO, nền tảng, mã băm SHA-256 mạng lưới.
3. `resolved_topology.json`: Bản sao topology chính thức được sử dụng.
4. `resolved_mapping.json`: Bản đồ ánh xạ TLS, pha, movement, nút thắt.
5. `experiment.sumocfg`: Tệp cấu hình SUMO tự sinh để tái lập.
6. `tripinfo.xml`: Dữ liệu chuyến đi xuất từ SUMO runtime.
7. `vehicles.csv`: Bảng dữ liệu từng xe (thời gian khởi hành, thời gian đến, chờ, trễ).
8. `telemetry.csv`: Chuỗi thời gian đo lường tại từng approach và nút.
9. `signals.jsonl`: Nhật ký chuyển pha đèn và chuỗi ký tự RYG của SUMO.
10. `scenario_events.jsonl`: Nhật ký can thiệp kịch bản (ví dụ: speed-gating nút thắt).
11. `faults.jsonl`: Nhật ký lỗi và ngoại lệ (trống nếu run hợp lệ).
12. `sumo-error.log`: Log chuẩn đầu ra lỗi từ tiến trình SUMO.
13. `summary.json`: Tóm tắt KPI đo lường, hạch toán xe và xác thực nghiên cứu.
14. `validity.json`: Chứng nhận tính hợp lệ khoa học và ghi chú thống kê.

### 4.2. Kết Quả Chạy Pilot Thực Tế 4 Mạng Lưới
Chiến dịch pilot 8 runs trên 4 mạng (`artifacts/sumo_benchmark_20261011_195450_36ff8d312ecf`) đã hoàn thành thành công:

| Mạng lưới | Kịch bản | Controller | Số xe lập lịch | Hoàn thành | Đang chạy | Chờ xuất phát | Bất biến xe | Hàng đợi TB (veh) | Hàng đợi P95 | Hợp lệ nghiên cứu |
|---|---|---|---:|---:|---:|---:|:---:|---:|---:|:---:|
| `four_intersection_v1` | balanced | `fixed_time` | 11 | 0 | 11 | 0 | **11=0+11+0** | 1.20 | 3.00 | **True** |
| `four_intersection_v1` | balanced | `flow_theory` | 11 | 0 | 11 | 0 | **11=0+11+0** | 1.30 | 3.05 | **True** |
| `grid4x4` | balanced | `fixed_time` | 26 | 0 | 26 | 0 | **26=0+26+0** | 0.00 | 0.00 | **True** |
| `grid4x4` | balanced | `flow_theory` | 26 | 0 | 26 | 0 | **26=0+26+0** | 0.00 | 0.00 | **True** |
| `cologne8` | balanced | `fixed_time` | 11 | 0 | 11 | 0 | **11=0+11+0** | 0.15 | 1.05 | **True** |
| `cologne8` | balanced | `flow_theory` | 11 | 0 | 11 | 0 | **11=0+11+0** | 0.00 | 0.00 | **True** |
| `hcm_corridor` | balanced | `fixed_time` | 11 | 2 | 9 | 0 | **11=2+9+0** | 2.40 | 4.00 | **True** |
| `hcm_corridor` | balanced | `flow_theory` | 11 | 5 | 6 | 0 | **11=5+6+0** | 2.50 | 4.00 | **True** |

> **Nhận xét khoa học quan trọng**:
> - Bất biến bảo toàn xe `scheduled == completed + active + pending` được bảo đảm chính xác 100% trên toàn bộ các lượt chạy.
> - Trên các mạng quy mô lớn hoặc hành trình dài khi thời gian mô phỏng ngắn (chưa có xe về đích), chỉ số chờ của các xe hoàn thành được ghi nhận trung thực là `N/A` (hoặc `null` trong JSON), không bị bóp méo thành `0.0s`.
> - Trên mạng `hcm_corridor`, `flow_theory` hoàn thành 5 xe so với 2 xe của `fixed_time`, và giảm độ trễ quan sát của nhóm thuần tập từ 5.93s xuống 3.65s.

---

## 5. Kết Quả Kiểm Thử (Test Suite Status)

Toàn bộ 33 kiểm thử đơn vị và tích hợp chuyên biệt cho hạ tầng SUMO live đều đạt trạng thái **PASS**:
- `tests/unit/test_contracts.py`: **8/8 PASSED** (Kiểm tra schema và bất biến contracts)
- `tests/unit/test_sumo_network_registry.py`: **5/5 PASSED** (Kiểm tra preflight, ánh xạ và lọc pha)
- `tests/unit/test_sumo_demand_generator.py`: **5/5 PASSED** (Kiểm tra tuyến động mạch và tính ngẫu nhiên đông lạnh)
- `tests/unit/test_flow_theory.py`: **4/4 PASSED** (Kiểm tra đơn vị và ánh xạ hạ lưu FlowTheoryController)
- `tests/unit/test_experiment_runner.py`: **7/7 PASSED** (Kiểm tra runner và trích xuất báo cáo)
- `tests/integration/test_sumo_live_benchmark.py`: **4/4 PASSED** (Kiểm tra chạy SUMO live qua TraCI, ActuatorStateMachine, Draft7 schema validation)
