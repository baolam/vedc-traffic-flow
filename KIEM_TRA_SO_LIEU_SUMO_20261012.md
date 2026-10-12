# Báo Cáo Đối Soát & Đánh Giá Lại Số Liệu Benchmark SUMO

- **Mã chiến dịch đối soát**: `sumo_benchmark_20261011_210619_857e4f6147c5`
- **Mã Git commit**: `857e4f6147c5`
- **Thời gian lập**: `2026-10-12`
- **Tình trạng dữ liệu**: Đã phát hiện nguyên nhân 5 điểm bất thường, đã sửa lỗi exporter và tái tạo bảng số liệu trung thực.

---

## 1. Kết Luận Kiểm Tra & Đối Chiếu Thư Mục Số Liệu

Qua đối soát chi tiết giữa các file thô `summary.json`, `benchmark_runs.csv`, `telemetry.csv` và code exporter trong `services/experiment-runner/batch_runner.py`, xác nhận toàn bộ 5 phát hiện kiểm toán:

| STT | Vấn đề phát hiện | Bản chất kỹ thuật trong Code | Kết quả đối soát thực tế | Tình trạng xử lý |
|:---:|---|---|---|---|
| **1** | **Quy mô 60 lượt vs Protocol 240 lượt** | Đợt benchmark này chạy với cấu hình 1 seed (`seed=101`) nhằm kiểm tra sơ bộ (4 topologies × 3 scenarios × 5 controllers × 1 seed = 60 runs). Protocol nghiên cứu chính quy định 4–5 seeds (240 runs). | Xác nhận đúng: 60/60 runs trong đợt này là kết quả thử nghiệm sơ bộ. | Ghi nhận rõ phạm vi thử nghiệm sơ bộ (preliminary pilot). |
| **2** | **Tỷ lệ hoàn thành xuất sai (False 100%)** | `batch_runner.py` đọc nhầm key `completion_coverage` (không tồn tại trong `summary.json`), fallback về `1.0` (100%). Key thực tế là `completion_rate`. | **Có đúng 9 lượt chưa hoàn thành hết xe** (đều ở `hcm_corridor` do xe chưa drain kịp trong 600s). Ví dụ `flow_theory`: 24/29 = **82.76%**; `max_queue`: 21/29 = **72.41%**. | **Đã sửa exporter**: Bảng markdown và JSON đã cập nhật đúng % hoàn thành thực tế. |
| **3** | **Throughput bị xuất sai thành 0.0** | `batch_runner.py` đọc `r.get("throughput_veh_per_s")` tại root (giá trị `None`), fallback về `0.0`. Trường thông lượng thực tế nằm ở `r["kpis"]["arrivals_measurement_veh_per_s"]`. | Thông lượng thực tế dao động từ 0.28 đến 1.20 veh/s tùy kịch bản. Không có run nào có thông lượng bằng 0. | **Đã sửa exporter**: Bảng markdown và JSON đã hiển thị đúng thông lượng và % tăng trưởng. |
| **4** | **Tính nhất quán Chờ/P95 và Queue** | Giá trị trung bình Mean Wait, P95 Wait, Mean Queue, P95 Queue trong `benchmark_runs.csv` khớp hoàn toàn với `summary.json` của từng run. | Số liệu đo đạc thời gian chờ và hàng đợi hoàn toàn trung thực và nhất quán giữa CSV và JSON. | Dữ liệu đo đạc KPI chờ và hàng đợi đáng tin cậy. |
| **5** | **Đầu vào `flow_veh_per_s`** | Trong `src/simulation/sumo_live_backend.py` dòng 400: `"flow_veh_per_s": round(float(d["veh_count"]) / 10.0, 3)`. | Đây là công thức xấp xỉ thô mật độ xe tức thời trên link chia 10s, không phải lưu lượng thực từ cảm biến luồng. | Đã ghi nhận hạn chế; sẽ cải tiến cảm biến induction loop khi chạy đợt 240 runs. |

---

## 2. Chi Tiết 9 Lượt Chưa Hoàn Thành Xe Trên Hành Lang HCM (`hcm_corridor`)

| Experiment ID | Controller | Scenario | Scheduled | Completed | Active | Pending | Completion Rate Thực Tế |
|---|---|---|:---:|:---:|:---:|:---:|:---:|
| `hcm_corridor_balanced_max_queue_seed101` | `max_queue` | balanced | 29 | 21 | 3 | 5 | **72.41%** |
| `hcm_corridor_balanced_flow_theory_seed101` | `flow_theory` | balanced | 29 | 24 | 5 | 0 | **82.76%** |
| `hcm_corridor_balanced_edgeflow_seed101` | `edgeflow` | balanced | 29 | 27 | 2 | 0 | **93.10%** |
| `hcm_corridor_directional_surge_max_queue_seed101` | `max_queue` | directional_surge | 41 | 30 | 1 | 10 | **73.17%** |
| `hcm_corridor_directional_surge_flow_theory_seed101` | `flow_theory` | directional_surge | 41 | 38 | 3 | 0 | **92.68%** |
| `hcm_corridor_directional_surge_edgeflow_seed101` | `edgeflow` | directional_surge | 41 | 38 | 3 | 0 | **92.68%** |
| `hcm_corridor_downstream_congestion_max_queue_seed101` | `max_queue` | downstream_congestion | 29 | 21 | 3 | 5 | **72.41%** |
| `hcm_corridor_downstream_congestion_flow_theory_seed101` | `flow_theory` | downstream_congestion | 29 | 24 | 5 | 0 | **82.76%** |
| `hcm_corridor_downstream_congestion_edgeflow_seed101` | `edgeflow` | downstream_congestion | 29 | 27 | 2 | 0 | **93.10%** |

> **Nhận định cốt lõi**:
> - Trên `hcm_corridor`, duy nhất **`fixed_time`** và **`max_pressure`** đạt tỷ lệ hoàn thành **100%** (29/29 và 41/41 xe).
> - `max_queue` có tỷ lệ hoàn thành thấp nhất (**72.4% - 73.2%**), còn 8–11 xe bị nghẽn lại không thể thoát, dẫn tới Throughput giảm sâu **-26.09%**.
> - `flow_theory` đạt **82.8% - 92.7%**.
> - `edgeflow` đạt **92.7% - 93.1%**.

---

## 3. Bảng Dữ Liệu Sơ Bộ Đã Được Đính Chính (Corrected Benchmark Summary)

*(Trích xuất tự động sau khi sửa code exporter trong `batch_runner.py`)*

### A. Phân Đoạn Hành Lang TP.HCM (`hcm_corridor`)

| Scenario | Controller | Mean Wait | P95 Wait | Mean Queue | P95 Queue | Throughput (veh/s) | Completion Rate Thực | Throughput Gain vs FT |
|---|---|---|---|---|---|---|---|---|
| **balanced** | `fixed_time` | 91.17s | 371.8s | 44.20 | 57.05 | 0.3833 | **100.0%** | Baseline |
| **balanced** | `max_queue` | 14.52s | 37.0s | 47.60 | 52.00 | 0.2833 | **72.4%** | **-26.09%** |
| **balanced** | `max_pressure` | 14.10s | 40.4s | 14.92 | 22.05 | 0.5333 | **100.0%** | **+39.13%** |
| **balanced** | `flow_theory` | 15.54s | 34.0s | 15.52 | 24.05 | 0.5167 | **82.8%** | **+34.80%** |
| **balanced** | `edgeflow` | 23.26s | 90.1s | 22.35 | 29.05 | 0.4500 | **93.1%** | **+17.40%** |
| **directional_surge** | `fixed_time` | 100.41s | 297.0s | 39.88 | 49.10 | 0.5167 | **100.0%** | Baseline |
| **directional_surge** | `max_queue` | 18.37s | 37.65s | 48.53 | 56.05 | 0.4667 | **73.2%** | **-9.68%** |
| **directional_surge** | `max_pressure` | 29.41s | 61.0s | 14.07 | 20.00 | 0.5500 | **100.0%** | **+6.44%** |
| **directional_surge** | `flow_theory` | 13.58s | 34.15s | 10.45 | 18.00 | 0.7500 | **92.7%** | **+45.15%** |
| **directional_surge** | `edgeflow` | 34.45s | 78.25s | 22.13 | 32.00 | 0.5333 | **92.7%** | **+3.21%** |
| **downstream_congestion** | `fixed_time` | 89.97s | 359.4s | 43.87 | 57.05 | 0.3833 | **100.0%** | Baseline |
| **downstream_congestion** | `max_queue` | 14.52s | 37.0s | 47.60 | 52.00 | 0.2833 | **72.4%** | **-26.09%** |
| **downstream_congestion** | `max_pressure` | 15.31s | 44.6s | 14.50 | 22.05 | 0.5333 | **100.0%** | **+39.13%** |
| **downstream_congestion** | `flow_theory` | 14.25s | 33.55s | 14.80 | 24.00 | 0.5167 | **82.8%** | **+34.80%** |
| **downstream_congestion** | `edgeflow` | 24.70s | 113.7s | 22.10 | 28.00 | 0.4500 | **93.1%** | **+17.40%** |

### B. Phân Đoạn Lưới Ô Bàn Cờ (`grid4x4`)

| Scenario | Controller | Mean Wait | P95 Wait | Mean Queue | P95 Queue | Throughput (veh/s) | Completion Rate | Throughput Gain vs FT |
|---|---|---|---|---|---|---|---|---|
| **balanced** | `fixed_time` | 146.21s | 224.7s | 149.40 | 207.00 | 0.7333 | **100.0%** | Baseline |
| **balanced** | `max_queue` | 19.21s | 38.9s | 16.45 | 22.00 | 1.2000 | **100.0%** | **+63.64%** |
| **balanced** | `max_pressure` | 64.62s | 116.0s | 77.43 | 95.05 | 1.1500 | **100.0%** | **+56.83%** |
| **balanced** | `flow_theory` | 24.27s | 43.0s | 27.43 | 36.20 | 1.1500 | **100.0%** | **+56.83%** |
| **balanced** | `edgeflow` | 104.43s | 148.8s | 106.87 | 123.05 | 0.7500 | **100.0%** | **+2.28%** |

---

## 4. Khuyến Nghị Sử Dụng & Kế Hoạch Tiếp Theo

1. **Về Báo cáo 60 lượt này**:
   - Sử dụng bảng số liệu đã đính chính ở trên làm **kết quả thử nghiệm sơ bộ (preliminary pilot benchmark)**.
   - Bảng đã phản ánh chính xác hiện tượng nghẽn dồn toa (spillback) của `max_queue` tại HCM Corridor (làm giảm Throughput 26% và Completion Rate chỉ đạt 72.4%).
2. **Về Thuật toán EdgeFlow**:
   - Đã áp dụng cải tiến Time-Decaying Hysteresis và Pressure-Aware downstream resolution vào `src/control/controllers.py`.
3. **Kế hoạch thực thi Benchmark chính quy (240 runs)**:
   - Khi chạy chiến dịch chính quy 240 runs (5 seeds: 101–105), hệ thống sẽ sử dụng trực tiếp exporter đã sửa lỗi để tự động tạo báo cáo hoàn chỉnh, trung thực và khoa học.
