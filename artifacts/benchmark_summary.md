# EdgeFlow AI — Benchmark Comparison Report (P0 Validated)

**Generated**: 2026-10-11T10:11:45Z
**Valid Runs**: 300 | **Failed**: 0
**Seeds**: [101, 202, 303, 404, 505] | **Mode**: deterministic_sim

## KPI Comparison

| Topology | Scenario | Controller | Runs | Avg Wait (s) | Avg Queue | P95 Queue | Throughput (veh/s) | Speed (m/s) |
|---|---|---|---|---|---|---|---|---|
| `four_intersection_v1` | **balanced** | `fixed_time` | 5 | 9.37s | 8.25 | 17.67 | 3.7053 | 5.0 |
| `four_intersection_v1` | **balanced** | `max_queue` | 5 | 9.94s | 8.75 | 16.14 | 3.7053 | 5.0 |
| `four_intersection_v1` | **balanced** | `max_pressure` | 5 | 9.94s | 8.75 | 16.14 | 3.7053 | 5.0 |
| `four_intersection_v1` | **balanced** | `flow_theory` | 5 | 9.88s | 8.69 | 16.54 | 3.7053 | 5.0 |
| `four_intersection_v1` | **balanced** | `edgeflow` | 5 | 14.01s | 9.32 | 18.35 | 2.8021 | 4.27 |
| `four_intersection_v1` | **directional_surge** | `fixed_time` | 5 | 8.99s | 7.91 | 17.93 | 3.7053 | 5.0 |
| `four_intersection_v1` | **directional_surge** | `max_queue` | 5 | 6.69s | 7.36 | 13.78 | 4.6316 | 5.75 |
| `four_intersection_v1` | **directional_surge** | `max_pressure` | 5 | 6.69s | 7.36 | 13.78 | 4.6316 | 5.75 |
| `four_intersection_v1` | **directional_surge** | `flow_theory` | 5 | 6.69s | 7.36 | 13.78 | 4.6316 | 5.75 |
| `four_intersection_v1` | **directional_surge** | `edgeflow` | 5 | 6.69s | 7.36 | 13.78 | 4.6316 | 5.75 |
| `four_intersection_v1` | **downstream_congestion** | `fixed_time` | 5 | 10.08s | 8.87 | 19.58 | 3.7053 | 5.0 |
| `four_intersection_v1` | **downstream_congestion** | `max_queue` | 5 | 11.05s | 9.73 | 18.84 | 3.7053 | 5.0 |
| `four_intersection_v1` | **downstream_congestion** | `max_pressure` | 5 | 11.05s | 9.73 | 18.84 | 3.7053 | 5.0 |
| `four_intersection_v1` | **downstream_congestion** | `flow_theory` | 5 | 10.89s | 9.58 | 18.97 | 3.7053 | 5.0 |
| `four_intersection_v1` | **downstream_congestion** | `edgeflow` | 5 | 16.55s | 10.92 | 22.42 | 2.7789 | 4.25 |
| `grid4x4` | **balanced** | `fixed_time` | 5 | 0.87s | 0.95 | 4.97 | 37.0526 | 8.0 |
| `grid4x4` | **balanced** | `max_queue` | 5 | 0.0s | 0.0 | 0.0 | 46.3158 | 9.5 |
| `grid4x4` | **balanced** | `max_pressure` | 5 | 0.0s | 0.0 | 0.0 | 46.3158 | 9.5 |
| `grid4x4` | **balanced** | `flow_theory` | 5 | 0.0s | 0.0 | 0.0 | 46.3158 | 9.5 |
| `grid4x4` | **balanced** | `edgeflow` | 5 | 0.24s | 0.28 | 2.83 | 39.3684 | 8.38 |
| `grid4x4` | **directional_surge** | `fixed_time` | 5 | 0.19s | 0.21 | 1.55 | 37.0526 | 8.0 |
| `grid4x4` | **directional_surge** | `max_queue` | 5 | 0.0s | 0.0 | 0.0 | 46.3158 | 9.5 |
| `grid4x4` | **directional_surge** | `max_pressure` | 5 | 0.0s | 0.0 | 0.0 | 46.3158 | 9.5 |
| `grid4x4` | **directional_surge** | `flow_theory` | 5 | 0.0s | 0.0 | 0.0 | 46.3158 | 9.5 |
| `grid4x4` | **directional_surge** | `edgeflow` | 5 | 0.1s | 0.11 | 1.08 | 39.3684 | 8.38 |
| `grid4x4` | **downstream_congestion** | `fixed_time` | 5 | 0.97s | 1.07 | 5.55 | 37.0526 | 8.0 |
| `grid4x4` | **downstream_congestion** | `max_queue` | 5 | 0.0s | 0.0 | 0.0 | 46.3158 | 9.5 |
| `grid4x4` | **downstream_congestion** | `max_pressure` | 5 | 0.0s | 0.0 | 0.0 | 46.3158 | 9.5 |
| `grid4x4` | **downstream_congestion** | `flow_theory` | 5 | 0.0s | 0.0 | 0.0 | 46.3158 | 9.5 |
| `grid4x4` | **downstream_congestion** | `edgeflow` | 5 | 0.26s | 0.3 | 3.08 | 39.3684 | 8.38 |
| `cologne8` | **balanced** | `fixed_time` | 5 | 47.45s | 6.64 | 18.46 | 11.4921 | 2.57 |
| `cologne8` | **balanced** | `max_queue` | 5 | 33.97s | 6.47 | 18.46 | 15.6316 | 2.77 |
| `cologne8` | **balanced** | `max_pressure` | 5 | 33.97s | 6.47 | 18.46 | 15.6316 | 2.77 |
| `cologne8` | **balanced** | `flow_theory` | 5 | 33.97s | 6.47 | 18.46 | 15.6316 | 2.77 |
| `cologne8` | **balanced** | `edgeflow` | 5 | 40.21s | 6.51 | 18.46 | 13.2868 | 2.65 |
| `cologne8` | **directional_surge** | `fixed_time` | 5 | 18.86s | 2.64 | 7.39 | 11.4921 | 2.57 |
| `cologne8` | **directional_surge** | `max_queue` | 5 | 13.6s | 2.59 | 7.39 | 15.6316 | 2.77 |
| `cologne8` | **directional_surge** | `max_pressure` | 5 | 13.6s | 2.59 | 7.39 | 15.6316 | 2.77 |
| `cologne8` | **directional_surge** | `flow_theory` | 5 | 13.6s | 2.59 | 7.39 | 15.6316 | 2.77 |
| `cologne8` | **directional_surge** | `edgeflow` | 5 | 16.09s | 2.6 | 7.39 | 13.2868 | 2.65 |
| `cologne8` | **downstream_congestion** | `fixed_time` | 5 | 50.64s | 7.09 | 19.5 | 11.4921 | 2.57 |
| `cologne8` | **downstream_congestion** | `max_queue` | 5 | 36.23s | 6.9 | 19.5 | 15.6316 | 2.77 |
| `cologne8` | **downstream_congestion** | `max_pressure` | 5 | 36.23s | 6.9 | 19.5 | 15.6316 | 2.77 |
| `cologne8` | **downstream_congestion** | `flow_theory` | 5 | 36.23s | 6.9 | 19.5 | 15.6316 | 2.77 |
| `cologne8` | **downstream_congestion** | `edgeflow` | 5 | 42.87s | 6.94 | 19.5 | 13.2868 | 2.65 |
| `hcm_corridor` | **balanced** | `fixed_time` | 5 | 12.51s | 5.87 | 15.36 | 24.6921 | 3.79 |
| `hcm_corridor` | **balanced** | `max_queue` | 5 | 11.49s | 5.86 | 15.51 | 26.8632 | 3.98 |
| `hcm_corridor` | **balanced** | `max_pressure` | 5 | 11.49s | 5.86 | 15.51 | 26.8632 | 3.98 |
| `hcm_corridor` | **balanced** | `flow_theory` | 5 | 11.42s | 5.83 | 15.82 | 26.8632 | 3.98 |
| `hcm_corridor` | **balanced** | `edgeflow` | 5 | 16.07s | 6.2 | 16.03 | 20.2979 | 3.49 |
| `hcm_corridor` | **directional_surge** | `fixed_time` | 5 | 4.91s | 2.31 | 6.12 | 24.6921 | 3.79 |
| `hcm_corridor` | **directional_surge** | `max_queue` | 5 | 4.12s | 2.11 | 5.11 | 26.8632 | 3.98 |
| `hcm_corridor` | **directional_surge** | `max_pressure` | 5 | 4.12s | 2.11 | 5.11 | 26.8632 | 3.98 |
| `hcm_corridor` | **directional_surge** | `flow_theory` | 5 | 4.24s | 2.17 | 5.39 | 26.8632 | 3.98 |
| `hcm_corridor` | **directional_surge** | `edgeflow` | 5 | 5.26s | 2.01 | 4.62 | 20.1474 | 3.48 |
| `hcm_corridor` | **downstream_congestion** | `fixed_time` | 5 | 13.36s | 6.27 | 16.26 | 24.6921 | 3.79 |
| `hcm_corridor` | **downstream_congestion** | `max_queue` | 5 | 12.31s | 6.28 | 16.78 | 26.8632 | 3.98 |
| `hcm_corridor` | **downstream_congestion** | `max_pressure` | 5 | 12.31s | 6.28 | 16.78 | 26.8632 | 3.98 |
| `hcm_corridor` | **downstream_congestion** | `flow_theory` | 5 | 12.21s | 6.23 | 17.0 | 26.8632 | 3.98 |
| `hcm_corridor` | **downstream_congestion** | `edgeflow` | 5 | 17.33s | 6.7 | 17.48 | 20.3442 | 3.5 |

## Performance vs Fixed-Time Baseline

| Topology | Scenario | Controller | Wait Reduction (%) | Queue Reduction (%) | Throughput Gain (%) |
|---|---|---|---|---|---|
| `four_intersection_v1` | **balanced** | `max_queue` | **-6.08%** | **-6.06%** | **+0.00%** |
| `four_intersection_v1` | **balanced** | `max_pressure` | **-6.08%** | **-6.06%** | **+0.00%** |
| `four_intersection_v1` | **balanced** | `flow_theory` | **-5.44%** | **-5.33%** | **+0.00%** |
| `four_intersection_v1` | **balanced** | `edgeflow` | **-49.52%** | **-12.97%** | **-24.38%** |
| `four_intersection_v1` | **directional_surge** | `max_queue` | **25.58%** | **6.95%** | **+25.00%** |
| `four_intersection_v1` | **directional_surge** | `max_pressure` | **25.58%** | **6.95%** | **+25.00%** |
| `four_intersection_v1` | **directional_surge** | `flow_theory` | **25.58%** | **6.95%** | **+25.00%** |
| `four_intersection_v1` | **directional_surge** | `edgeflow` | **25.58%** | **6.95%** | **+25.00%** |
| `four_intersection_v1` | **downstream_congestion** | `max_queue` | **-9.62%** | **-9.7%** | **+0.00%** |
| `four_intersection_v1` | **downstream_congestion** | `max_pressure` | **-9.62%** | **-9.7%** | **+0.00%** |
| `four_intersection_v1` | **downstream_congestion** | `flow_theory` | **-8.04%** | **-8.0%** | **+0.00%** |
| `four_intersection_v1` | **downstream_congestion** | `edgeflow` | **-64.19%** | **-23.11%** | **-25.00%** |
| `grid4x4` | **balanced** | `max_queue` | **100.0%** | **100.0%** | **+25.00%** |
| `grid4x4` | **balanced** | `max_pressure` | **100.0%** | **100.0%** | **+25.00%** |
| `grid4x4` | **balanced** | `flow_theory` | **100.0%** | **100.0%** | **+25.00%** |
| `grid4x4` | **balanced** | `edgeflow` | **72.41%** | **70.53%** | **+6.25%** |
| `grid4x4` | **directional_surge** | `max_queue` | **100.0%** | **100.0%** | **+25.00%** |
| `grid4x4` | **directional_surge** | `max_pressure` | **100.0%** | **100.0%** | **+25.00%** |
| `grid4x4` | **directional_surge** | `flow_theory` | **100.0%** | **100.0%** | **+25.00%** |
| `grid4x4` | **directional_surge** | `edgeflow` | **47.37%** | **47.62%** | **+6.25%** |
| `grid4x4` | **downstream_congestion** | `max_queue` | **100.0%** | **100.0%** | **+25.00%** |
| `grid4x4` | **downstream_congestion** | `max_pressure` | **100.0%** | **100.0%** | **+25.00%** |
| `grid4x4` | **downstream_congestion** | `flow_theory` | **100.0%** | **100.0%** | **+25.00%** |
| `grid4x4` | **downstream_congestion** | `edgeflow` | **73.2%** | **71.96%** | **+6.25%** |
| `cologne8` | **balanced** | `max_queue` | **28.41%** | **2.56%** | **+36.02%** |
| `cologne8` | **balanced** | `max_pressure` | **28.41%** | **2.56%** | **+36.02%** |
| `cologne8` | **balanced** | `flow_theory` | **28.41%** | **2.56%** | **+36.02%** |
| `cologne8` | **balanced** | `edgeflow` | **15.26%** | **1.96%** | **+15.62%** |
| `cologne8` | **directional_surge** | `max_queue` | **27.89%** | **1.89%** | **+36.02%** |
| `cologne8` | **directional_surge** | `max_pressure` | **27.89%** | **1.89%** | **+36.02%** |
| `cologne8` | **directional_surge** | `flow_theory` | **27.89%** | **1.89%** | **+36.02%** |
| `cologne8` | **directional_surge** | `edgeflow` | **14.69%** | **1.52%** | **+15.62%** |
| `cologne8` | **downstream_congestion** | `max_queue` | **28.46%** | **2.68%** | **+36.02%** |
| `cologne8` | **downstream_congestion** | `max_pressure` | **28.46%** | **2.68%** | **+36.02%** |
| `cologne8` | **downstream_congestion** | `flow_theory` | **28.46%** | **2.68%** | **+36.02%** |
| `cologne8` | **downstream_congestion** | `edgeflow` | **15.34%** | **2.12%** | **+15.62%** |
| `hcm_corridor` | **balanced** | `max_queue` | **8.15%** | **0.17%** | **+8.79%** |
| `hcm_corridor` | **balanced** | `max_pressure` | **8.15%** | **0.17%** | **+8.79%** |
| `hcm_corridor` | **balanced** | `flow_theory` | **8.71%** | **0.68%** | **+8.79%** |
| `hcm_corridor` | **balanced** | `edgeflow` | **-28.46%** | **-5.62%** | **-17.80%** |
| `hcm_corridor` | **directional_surge** | `max_queue` | **16.09%** | **8.66%** | **+8.79%** |
| `hcm_corridor` | **directional_surge** | `max_pressure` | **16.09%** | **8.66%** | **+8.79%** |
| `hcm_corridor` | **directional_surge** | `flow_theory` | **13.65%** | **6.06%** | **+8.79%** |
| `hcm_corridor` | **directional_surge** | `edgeflow` | **-7.13%** | **12.99%** | **-18.41%** |
| `hcm_corridor` | **downstream_congestion** | `max_queue` | **7.86%** | **-0.16%** | **+8.79%** |
| `hcm_corridor` | **downstream_congestion** | `max_pressure` | **7.86%** | **-0.16%** | **+8.79%** |
| `hcm_corridor` | **downstream_congestion** | `flow_theory` | **8.61%** | **0.64%** | **+8.79%** |
| `hcm_corridor` | **downstream_congestion** | `edgeflow` | **-29.72%** | **-6.86%** | **-17.61%** |
