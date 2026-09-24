# EdgeFlow AI - Multi-Topology Benchmark Comparison Summary Report

**Generated at**: 2026-09-24T15:03:09Z | **Total Benchmark Runs**: 18

## 📊 KPI Comparison Table Across Networks (Fixed-Time Baseline vs Max-Pressure Adaptive Control)

| Topology | Scenario | Controller | Avg Waiting Time (s) | Avg Queue (veh) | Max Queue (veh) | Throughput (veh/s) |
|---|---|---|---|---|---|---|
| `four_intersection_v1` | **balanced** | `fixed_time` | 49.54s | 11.0 veh | 14 veh | 0.219 veh/s |
| `four_intersection_v1` | **balanced** | `max_pressure` | 18.89s | 7.5 veh | 8 veh | 0.4206 veh/s |
| `four_intersection_v1` | **balanced** | `flow_theory` | 49.54s | 11.0 veh | 14 veh | 0.219 veh/s |
| `four_intersection_v1` | **directional_surge** | `fixed_time` | 49.54s | 11.0 veh | 14 veh | 0.219 veh/s |
| `four_intersection_v1` | **directional_surge** | `max_pressure` | 18.89s | 7.5 veh | 8 veh | 0.4206 veh/s |
| `four_intersection_v1` | **directional_surge** | `flow_theory` | 49.54s | 11.0 veh | 14 veh | 0.219 veh/s |
| `four_intersection_v1` | **downstream_congestion** | `fixed_time` | 49.54s | 11.0 veh | 14 veh | 0.219 veh/s |
| `four_intersection_v1` | **downstream_congestion** | `max_pressure` | 18.89s | 7.5 veh | 8 veh | 0.4206 veh/s |
| `four_intersection_v1` | **downstream_congestion** | `flow_theory` | 49.54s | 11.0 veh | 14 veh | 0.219 veh/s |

## 🚀 EdgeFlow Max-Pressure Performance Gain Summary By Network

| Topology | Scenario | Waiting Time Reduction (%) | Queue Length Reduction (%) | Throughput Gain (%) |
|---|---|---|---|---|
| `four_intersection_v1` | **balanced** | **-61.87%** | **-31.82%** | **+92.05%** |
| `four_intersection_v1` | **directional_surge** | **-61.87%** | **-31.82%** | **+92.05%** |
| `four_intersection_v1` | **downstream_congestion** | **-61.87%** | **-31.82%** | **+92.05%** |
