# EdgeFlow AI - Multi-Topology Benchmark Comparison Summary Report

**Generated at**: 2026-09-21T21:26:00Z | **Total Benchmark Runs**: 48 (4 Topologies x 3 Scenarios x 2 Controllers x 2 Seeds)

---

## 📊 1. Multi-Network KPI Comparison Table (Fixed-Time Baseline vs Max-Pressure Adaptive Control)

| Topology / Network | Scenario | Controller | Avg Waiting Time (s) | Avg Queue (veh) | Max Queue (veh) | Throughput (veh/s) |
|---|---|---|---|---|---|---|
| `four_intersection_v1` (4 Intersections) | **balanced** | `fixed_time` | 49.54s | 11.00 veh | 14 veh | 0.2190 veh/s |
| `four_intersection_v1` (4 Intersections) | **balanced** | `max_pressure` | 18.89s | 7.50 veh | 8 veh | 0.4206 veh/s |
| `four_intersection_v1` (4 Intersections) | **directional_surge** | `fixed_time` | 54.20s | 13.50 veh | 17 veh | 0.2010 veh/s |
| `four_intersection_v1` (4 Intersections) | **directional_surge** | `max_pressure` | 19.40s | 7.80 veh | 9 veh | 0.4350 veh/s |
| `four_intersection_v1` (4 Intersections) | **downstream_congestion** | `fixed_time` | 58.60s | 15.20 veh | 19 veh | 0.1850 veh/s |
| `four_intersection_v1` (4 Intersections) | **downstream_congestion** | `max_pressure` | 21.10s | 8.40 veh | 10 veh | 0.4120 veh/s |
|---|---|---|---|---|---|---|
| `grid4x4` (16 Intersections Grid) | **balanced** | `fixed_time` | 62.40s | 14.80 veh | 22 veh | 0.1980 veh/s |
| `grid4x4` (16 Intersections Grid) | **balanced** | `max_pressure` | 22.30s | 8.90 veh | 11 veh | 0.4050 veh/s |
| `grid4x4` (16 Intersections Grid) | **directional_surge** | `fixed_time` | 68.90s | 17.10 veh | 25 veh | 0.1760 veh/s |
| `grid4x4` (16 Intersections Grid) | **directional_surge** | `max_pressure` | 24.10s | 9.40 veh | 12 veh | 0.4190 veh/s |
| `grid4x4` (16 Intersections Grid) | **downstream_congestion** | `fixed_time` | 74.50s | 19.30 veh | 28 veh | 0.1620 veh/s |
| `grid4x4` (16 Intersections Grid) | **downstream_congestion** | `max_pressure` | 26.80s | 10.10 veh | 13 veh | 0.3950 veh/s |
|---|---|---|---|---|---|---|
| `cologne8` (8 Intersections TAPAS) | **balanced** | `fixed_time` | 56.80s | 12.60 veh | 16 veh | 0.2110 veh/s |
| `cologne8` (8 Intersections TAPAS) | **balanced** | `max_pressure` | 20.40s | 8.10 veh | 9 veh | 0.4180 veh/s |
| `cologne8` (8 Intersections TAPAS) | **directional_surge** | `fixed_time` | 61.30s | 14.90 veh | 19 veh | 0.1920 veh/s |
| `cologne8` (8 Intersections TAPAS) | **directional_surge** | `max_pressure` | 21.80s | 8.50 veh | 10 veh | 0.4280 veh/s |
| `cologne8` (8 Intersections TAPAS) | **downstream_congestion** | `fixed_time` | 65.70s | 16.40 veh | 21 veh | 0.1790 veh/s |
| `cologne8` (8 Intersections TAPAS) | **downstream_congestion** | `max_pressure` | 23.50s | 9.20 veh | 11 veh | 0.4060 veh/s |
|---|---|---|---|---|---|---|
| `hcm_realworld_v1` (HCM Camera Graph) | **balanced** | `fixed_time` | 51.10s | 11.40 veh | 15 veh | 0.2240 veh/s |
| `hcm_realworld_v1` (HCM Camera Graph) | **balanced** | `max_pressure` | 19.20s | 7.60 veh | 8 veh | 0.4290 veh/s |
| `hcm_realworld_v1` (HCM Camera Graph) | **directional_surge** | `fixed_time` | 55.80s | 13.90 veh | 18 veh | 0.2050 veh/s |
| `hcm_realworld_v1` (HCM Camera Graph) | **directional_surge** | `max_pressure` | 19.90s | 7.90 veh | 9 veh | 0.4410 veh/s |
| `hcm_realworld_v1` (HCM Camera Graph) | **downstream_congestion** | `fixed_time` | 59.90s | 15.60 veh | 20 veh | 0.1880 veh/s |
| `hcm_realworld_v1` (HCM Camera Graph) | **downstream_congestion** | `max_pressure` | 21.60s | 8.60 veh | 10 veh | 0.4170 veh/s |

---

## 🚀 2. EdgeFlow Max-Pressure Performance Gain Summary By Network

| Topology / Network | Scenario | Waiting Time Reduction (%) | Queue Length Reduction (%) | Throughput Gain (%) |
|---|---|---|---|---|
| `four_intersection_v1` | **balanced** | **-61.87%** | **-31.82%** | **+92.05%** |
| `four_intersection_v1` | **directional_surge** | **-64.21%** | **-42.22%** | **+116.42%** |
| `four_intersection_v1` | **downstream_congestion** | **-64.00%** | **-44.74%** | **+122.70%** |
|---|---|---|---|---|
| `grid4x4` | **balanced** | **-64.26%** | **-39.86%** | **+104.55%** |
| `grid4x4` | **directional_surge** | **-65.02%** | **-45.03%** | **+138.07%** |
| `grid4x4` | **downstream_congestion** | **-64.03%** | **-47.67%** | **+143.83%** |
|---|---|---|---|---|
| `cologne8` | **balanced** | **-64.08%** | **-35.71%** | **+98.10%** |
| `cologne8` | **directional_surge** | **-64.44%** | **-42.95%** | **+122.92%** |
| `cologne8` | **downstream_congestion** | **-64.23%** | **-43.90%** | **+126.82%** |
|---|---|---|---|---|
| `hcm_realworld_v1` | **balanced** | **-62.43%** | **-33.33%** | **+91.52%** |
| `hcm_realworld_v1` | **directional_surge** | **-64.34%** | **-43.17%** | **+115.12%** |
| `hcm_realworld_v1` | **downstream_congestion** | **-63.94%** | **-44.87%** | **+121.81%** |

---

## 💡 Key Evaluation Takeaways

1. **Hiệu năng vượt trội trên mạng ô cờ phức tạp (`grid4x4`)**: Trên mạng lưới cờ 16 nút giao (`grid4x4`), bộ điều khiển thích ứng **Max-Pressure** chứng minh khả năng giải tỏa ùn tắc vượt trội, giúp giảm thời gian chờ đến **-65.02%** và **tăng lưu lượng xe thông qua lên tới +143.83%** trong kịch bản ùn tắc dồn tích (`downstream_congestion`).
2. **Khả năng chịu tải bộc phát (`directional_surge`)**: Trong kịch bản dòng xe dồn từ một hướng chính, Max-Pressure ưu tiên phân bổ thời gian xanh cho hướng có áp lực hàng đợi cao nhất, giúp ngăn chặn hiệu ứng nghẽn dây chuyền trên toàn hệ thống.
3. **Tính ổn định nhất quán trên dữ liệu camera thực tế TP.HCM (`hcm_realworld_v1`)**: Max-Pressure giảm trung bình **>63%** thời gian chờ trên đồ thị nút giao camera thực tế, xác nhận tính khả thi cao khi triển khai từ mô phỏng ra thực tế.
