# EdgeFlow AI - Scientific Benchmark Comparison Summary Report (VEDC 2026)

**Generated at**: 2026-09-27T07:29:43Z | **Total Completed Runs**: 75
**Evaluation Mode**: Truthful Multi-Seed Paired Matrix (Seeds: [101, 202, 303, 404, 505])

## 📊 KPI Comparison Table Across Controllers

| Topology | Scenario | Controller | Avg Waiting Time (s) | Avg Queue (veh) | P95 Queue (veh) | Throughput (veh/s) | Mean Speed (m/s) |
|---|---|---|---|---|---|---|---|
| `four_intersection_v1` | **balanced** | `fixed_time` | 16.74s | 18.51 veh | 22.54 veh | 1.1431 veh/s | 5.35 m/s |
| `four_intersection_v1` | **balanced** | `max_queue` | 16.71s | 18.48 veh | 22.43 veh | 1.1433 veh/s | 5.35 m/s |
| `four_intersection_v1` | **balanced** | `max_pressure` | 16.72s | 18.49 veh | 22.51 veh | 1.1435 veh/s | 5.35 m/s |
| `four_intersection_v1` | **balanced** | `edgeflow` | 16.77s | 18.55 veh | 22.63 veh | 1.1431 veh/s | 5.35 m/s |
| `four_intersection_v1` | **balanced** | `presslight_rl` | 16.73s | 18.5 veh | 22.55 veh | 1.1436 veh/s | 5.35 m/s |
| `four_intersection_v1` | **directional_surge** | `fixed_time` | 18.53s | 20.56 veh | 24.65 veh | 1.1434 veh/s | 5.35 m/s |
| `four_intersection_v1` | **directional_surge** | `max_queue` | 18.51s | 20.53 veh | 24.58 veh | 1.1432 veh/s | 5.35 m/s |
| `four_intersection_v1` | **directional_surge** | `max_pressure` | 18.56s | 20.59 veh | 24.71 veh | 1.1433 veh/s | 5.35 m/s |
| `four_intersection_v1` | **directional_surge** | `edgeflow` | 18.56s | 20.59 veh | 24.73 veh | 1.1434 veh/s | 5.35 m/s |
| `four_intersection_v1` | **directional_surge** | `presslight_rl` | 18.58s | 20.61 veh | 24.74 veh | 1.1433 veh/s | 5.35 m/s |
| `four_intersection_v1` | **downstream_congestion** | `fixed_time` | 23.48s | 26.23 veh | 35.31 veh | 1.1433 veh/s | 5.35 m/s |
| `four_intersection_v1` | **downstream_congestion** | `max_queue` | 23.45s | 26.18 veh | 35.27 veh | 1.1434 veh/s | 5.35 m/s |
| `four_intersection_v1` | **downstream_congestion** | `max_pressure` | 23.48s | 26.21 veh | 35.32 veh | 1.1437 veh/s | 5.35 m/s |
| `four_intersection_v1` | **downstream_congestion** | `edgeflow` | 18.54s | 20.57 veh | 24.66 veh | 1.1435 veh/s | 5.35 m/s |
| `four_intersection_v1` | **downstream_congestion** | `presslight_rl` | 18.58s | 20.62 veh | 24.76 veh | 1.1433 veh/s | 5.35 m/s |

## 🚀 Performance Gains Relative to Fixed-Time Baseline

| Topology | Scenario | Controller | Waiting Time Reduction (%) | Queue Length Reduction (%) | Throughput Gain (%) |
|---|---|---|---|---|---|
| `four_intersection_v1` | **balanced** | `max_queue` | **0.18%** | **0.16%** | **+0.02%** |
| `four_intersection_v1` | **balanced** | `max_pressure` | **0.12%** | **0.11%** | **+0.03%** |
| `four_intersection_v1` | **balanced** | `edgeflow` | **-0.18%** | **-0.22%** | **+0.0%** |
| `four_intersection_v1` | **directional_surge** | `max_queue` | **0.11%** | **0.15%** | **+-0.02%** |
| `four_intersection_v1` | **directional_surge** | `max_pressure` | **-0.16%** | **-0.15%** | **+-0.01%** |
| `four_intersection_v1` | **directional_surge** | `edgeflow` | **-0.16%** | **-0.15%** | **+0.0%** |
| `four_intersection_v1` | **downstream_congestion** | `max_queue` | **0.13%** | **0.19%** | **+0.01%** |
| `four_intersection_v1` | **downstream_congestion** | `max_pressure` | **0.0%** | **0.08%** | **+0.03%** |
| `four_intersection_v1` | **downstream_congestion** | `edgeflow` | **21.04%** | **21.58%** | **+0.02%** |
