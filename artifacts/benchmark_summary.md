# EdgeFlow AI - Benchmark Comparison Summary Report

**Generated at**: 2026-09-20T14:49:39Z | **Total Benchmark Runs**: 12

## 📊 KPI Comparison Table (Fixed-Time Baseline vs Max-Pressure Adaptive Control)

| Scenario | Controller | Avg Waiting Time (s) | Avg Queue (veh) | Max Queue (veh) | Throughput (veh/s) |
|---|---|---|---|---|---|
| **balanced** | `fixed_time` | 49.54s | 11.0 veh | 14 veh | 0.219 veh/s |
| **balanced** | `max_pressure` | 18.89s | 7.5 veh | 8 veh | 0.4206 veh/s |
| **directional_surge** | `fixed_time` | 49.54s | 11.0 veh | 14 veh | 0.219 veh/s |
| **directional_surge** | `max_pressure` | 18.89s | 7.5 veh | 8 veh | 0.4206 veh/s |
| **downstream_congestion** | `fixed_time` | 49.54s | 11.0 veh | 14 veh | 0.219 veh/s |
| **downstream_congestion** | `max_pressure` | 18.89s | 7.5 veh | 8 veh | 0.4206 veh/s |

## 🚀 EdgeFlow Max-Pressure Performance Gain Summary

| Scenario | Waiting Time Reduction (%) | Queue Length Reduction (%) | Throughput Gain (%) |
|---|---|---|---|
| **balanced** | **-61.87%** | **-31.82%** | **+92.05%** |
| **directional_surge** | **-61.87%** | **-31.82%** | **+92.05%** |
| **downstream_congestion** | **-61.87%** | **-31.82%** | **+92.05%** |
