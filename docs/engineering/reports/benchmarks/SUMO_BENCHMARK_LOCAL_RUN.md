# Hướng Dẫn Chạy Benchmark SUMO Thực Tế (Local Run Guide)

Tài liệu này hướng dẫn chi tiết cách chạy thực nghiệm đo kiểm hiệu năng (benchmark) thực tế giữa 4 bộ điều khiển đèn giao thông:
- `fixed_time` (Chu kỳ cố định baseline)
- `max_queue` (Ưu tiên hàng đợi lớn nhất)
- `max_pressure` (Cân bằng áp lực mạng lưới)
- `flow_theory` (Lý thuyết dòng xe Greenshields & Webster)

trên 4 mạng lưới SUMO:
- `four_intersection_v1` (Lưới 4 nút giao tiêu chuẩn)
- `grid4x4` (Lưới Manhattan 16 nút giao)
- `cologne8` (Tiểu mạng TAPAS Cologne 8 nút giao)
- `hcm_corridor` (Hành lang trục chính TP.HCM 29 nút giao)

dưới 3 kịch bản:
- `balanced` (Lưu lượng cân bằng hai chiều)
- `directional_surge` (Đột biến dòng xe giờ cao điểm trên trục chính)
- `downstream_congestion` (Nghẽn cục bộ nhân tạo tại nút thắt cổ chai hạ lưu)

---

## 1. Yêu Cầu Môi Trường & Thiết Lập Ban Đầu

### 1.1. Kích hoạt Virtual Environment
Mở PowerShell tại thư mục gốc dự án `E:\vedc-traffic-flow`:

```powershell
# Kích hoạt môi trường Python 3.11 đã cài sẵn các gói
.\.venv\Scripts\Activate.ps1
```

### 1.2. Kiểm tra Cài đặt SUMO & TraCI
Hệ thống sử dụng Eclipse SUMO (đã có tại `D:\sumo` hoặc theo biến môi trường `SUMO_HOME`):

```powershell
# Kiểm tra phiên bản SUMO
sumo --version

# Kiểm tra thư viện TraCI và Sumolib trong Python
python -c "import traci, sumolib; print('TraCI version:', getattr(traci, '__version__', 'OK'))"
```

---

## 2. Bước 1: Kiểm Tra Toàn Vẹn Mạng Lưới (Preflight Audit)

Trước khi tiến hành chạy mô phỏng dài, hãy luôn chạy lệnh kiểm tra tĩnh (preflight) để xác thực tính tương thích của cả 4 mạng lưới:

```powershell
python services/experiment-runner/batch_runner.py --topology all --preflight-only
```

**Kết quả mong đợi**:
```text
================================================================================
 PREFLIGHT AUDIT SUMMARY
================================================================================
[PASS] four_intersection_v1   | TLS: 4  | Green Phases: 12 | Movements: 27 
[PASS] grid4x4                | TLS: 16 | Green Phases: 128 | Movements: 1152
[PASS] cologne8               | TLS: 8  | Green Phases: 25 | Movements: 143
[PASS] hcm_corridor           | TLS: 29 | Green Phases: 62 | Movements: 400
================================================================================
```

Lệnh này sinh ra các tệp kiểm toán trong thư mục chiến dịch:
- `preflight.json`: Báo cáo chi tiết mã băm SHA-256 mạng lưới và topology.
- `mapping_audit.json`: Bản đồ ánh xạ pha, movement, nút thắt cho từng nút.
- `mapping_audit.csv`: Bảng tra cứu số approach, pha xanh ổn định và movement.

---

## 3. Bước 2: Chạy Thử Nghiệm Một Lượt Đơn Lẻ (Single Run)

Bạn có thể chạy thử nghiệm nhanh một kịch bản cụ thể để kiểm tra kết nối TraCI thời gian thực và sinh trọn bộ 14 artifacts:

```powershell
python services/experiment-runner/runner.py `
  --mode sumo_live `
  --topology four_intersection_v1 `
  --scenario balanced `
  --controller flow_theory `
  --seed 101 `
  --warmup 30 `
  --duration 300 `
  --drain 60 `
  --output-dir artifacts/single_test
```

### Kiểm tra gói bằng chứng (14 Artifacts):
Tại thư mục `artifacts/single_test/<experiment_id>/`, kiểm tra các tệp:
- `summary.json`: Xem `valid_for_research`, `accounting` và `kpis`.
- `vehicles.csv`: Dữ liệu từng phương tiện hoàn thành.
- `telemetry.csv`: Dữ liệu hàng đợi, vận tốc và lưu lượng theo thời gian.
- `signals.jsonl`: Lịch sử các bước chuyển đèn tín hiệu từ TraCI.

---

## 4. Bước 3: Chạy Chiến Dịch Pilot Nhanh (Smoke Batch)

Để kiểm tra toàn bộ luồng paired matrix trên cả 4 mạng lưới với thời lượng ngắn:

```powershell
python services/experiment-runner/batch_runner.py `
  --topology all `
  --scenarios balanced `
  --controllers fixed_time flow_theory `
  --seeds 101 `
  --warmup 10 `
  --duration 60 `
  --drain 10 `
  --mode sumo_live
```

---

## 5. Bước 4: Chạy Chiến Dịch Benchmark Bán Kết Toàn Diện (Official Semi-Final Run)

Để thực hiện trọn vẹn ma trận thực nghiệm chuẩn cho báo cáo khoa học (4 mạng x 3 kịch bản x 4 bộ điều khiển x 5 seeds = 240 lượt chạy), sử dụng tệp cấu hình chính thức:

```powershell
python services/experiment-runner/batch_runner.py --config configs/benchmark_sumo_semifinal.json
```

### Tham số chính thức trong `configs/benchmark_sumo_semifinal.json`:
- **Topologies**: `four_intersection_v1`, `grid4x4`, `cologne8`, `hcm_corridor`
- **Scenarios**: `balanced`, `directional_surge`, `downstream_congestion`
- **Controllers**: `fixed_time`, `max_queue`, `max_pressure`, `flow_theory`
- **Seeds**: `101`, `202`, `303`, `404`, `505`
- **Thời lượng**: Khởi động (Warmup) = 300s, Cửa sổ đo lường (Measurement) = 1800s, Xả hàng đợi (Drain) = 600s. Tổng chân trời = 2700s (45 phút/lượt).

> [!TIP]
> Bạn có thể tùy chỉnh danh sách kịch bản hoặc giảm số hạt giống (`--seeds 101 202`) bằng cờ dòng lệnh ghi đè khi muốn chạy rút gọn:
> ```powershell
> python services/experiment-runner/batch_runner.py `
>   --config configs/benchmark_sumo_semifinal.json `
>   --seeds 101 `
>   --duration 600
> ```

---

## 6. Xem Và Phân Tích Báo Cáo Chiến Dịch

Sau khi chiến dịch hoàn tất, thư mục chiến dịch mới dạng `artifacts/sumo_benchmark_<YYYYMMDD_HHMMSS>_<commit>/` sẽ chứa:

1. **`campaign_manifest.json`**:
   - Ghi lại cấu hình chiến dịch, commit mã nguồn git, nền tảng hệ điều hành.
2. **`benchmark_runs.csv`**:
   - Bảng tổng hợp chi tiết từng lượt chạy: mã thí nghiệm, controller, seed, số xe lập lịch, số xe hoàn thành, số xe còn trên mạng, độ trễ và hàng đợi.
3. **`benchmark_comparison_report.json`**:
   - Dữ liệu so sánh gộp cặp (paired comparison) chuẩn hóa cho phân tích tự động.
4. **`benchmark_summary.md`**:
   - Bảng so sánh Markdown trực quan hiển thị mức giảm thời gian chờ (`Waiting Time Reduction %`), mức giảm hàng đợi (`Queue Reduction %`) và cải thiện thông lượng (`Throughput Gain %`) so với `fixed_time`.
5. **`test_results.md`**:
   - Báo cáo tuân thủ 6 bất biến khoa học (bảo toàn xe, định danh controller, phong bì an toàn actuator).

---

## 7. Xử Lý Sự Cố (Troubleshooting)

- **Lỗi `Connection closed by SUMO`**:
  - Thường xảy ra nếu SUMO thoát do lỗi cú pháp trong tệp cấu hình hoặc route. Hãy xem tệp `sumo-error.log` bên trong thư mục của lượt chạy đó để thấy thông báo lỗi cụ thể của SUMO.
- **Lỗi xung đột cổng / nhãn TraCI**:
  - `LiveSumoRuntime` tự động tạo nhãn phiên (`conn_label`) duy nhất bằng UUID và đóng kết nối TraCI an toàn trong khối `finally`. Nếu SUMO bị treo nền, hãy dùng PowerShell để dọn dẹp:
    ```powershell
    Get-Process sumo -ErrorAction SilentlyContinue | Stop-Process -Force
    ```
- **Dữ liệu thời gian chờ hiển thị `N/A`**:
  - Đây là hành vi đúng chuẩn khoa học: nếu thời gian mô phỏng quá ngắn dẫn đến chưa có phương tiện nào hoàn thành toàn bộ lộ trình (`completed_vehicles == 0`), hệ thống sẽ trả về `null`/`N/A` thay vì giả định sai lệch là `0.0s`.
