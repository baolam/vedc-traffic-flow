# EdgeFlow AI — Benchmark Comparison Report (SUMO/TraCI Validated)

- **Execution Mode**: `sumo_live`
- **Git Commit**: `857e4f6147c5`
- **Timestamp**: `2026-10-12T14:02:47Z`
- **Valid Runs**: 60 / 60 (0 failed/invalid)

## Paired KPI Comparison (Mean over Common Seeds)

| Topology | Scenario | Controller | Paired Runs | Mean Wait (s) | P95 Wait (s) | Mean Queue (veh) | P95 Queue | Throughput (veh/s) | Completion Rate |
|---|---|---|---|---|---|---|---|---|---|
| `four_intersection_v1` | **balanced** | `fixed_time` | 1 | 17.33s | 37.4s | 7.6 | 11.0 | 0.4833 | 100.0% |
| `four_intersection_v1` | **balanced** | `max_queue` | 1 | 2.04s | 6.0s | 1.77 | 3.05 | 0.5167 | 100.0% |
| `four_intersection_v1` | **balanced** | `max_pressure` | 1 | 2.04s | 6.0s | 1.77 | 3.05 | 0.5167 | 100.0% |
| `four_intersection_v1` | **balanced** | `flow_theory` | 1 | 4.88s | 19.4s | 2.67 | 5.0 | 0.4667 | 100.0% |
| `four_intersection_v1` | **balanced** | `edgeflow` | 1 | 6.92s | 16.7s | 3.3 | 6.0 | 0.4667 | 100.0% |
| `four_intersection_v1` | **directional_surge** | `fixed_time` | 1 | 21.04s | 46.7s | 9.55 | 17.1 | 0.45 | 100.0% |
| `four_intersection_v1` | **directional_surge** | `max_queue` | 1 | 3.98s | 14.7s | 1.33 | 3.05 | 0.4833 | 100.0% |
| `four_intersection_v1` | **directional_surge** | `max_pressure` | 1 | 3.98s | 14.7s | 1.33 | 3.05 | 0.4833 | 100.0% |
| `four_intersection_v1` | **directional_surge** | `flow_theory` | 1 | 7.36s | 25.8s | 3.17 | 6.05 | 0.4333 | 100.0% |
| `four_intersection_v1` | **directional_surge** | `edgeflow` | 1 | 6.83s | 20.1s | 2.68 | 6.0 | 0.4167 | 100.0% |
| `four_intersection_v1` | **downstream_congestion** | `fixed_time` | 1 | 17.33s | 37.4s | 7.6 | 11.0 | 0.45 | 100.0% |
| `four_intersection_v1` | **downstream_congestion** | `max_queue` | 1 | 4.38s | 15.85s | 2.02 | 3.05 | 0.4333 | 100.0% |
| `four_intersection_v1` | **downstream_congestion** | `max_pressure` | 1 | 4.38s | 15.85s | 2.02 | 3.05 | 0.4333 | 100.0% |
| `four_intersection_v1` | **downstream_congestion** | `flow_theory` | 1 | 5.08s | 19.1s | 2.6 | 5.0 | 0.3833 | 100.0% |
| `four_intersection_v1` | **downstream_congestion** | `edgeflow` | 1 | 7.54s | 16.55s | 3.08 | 5.0 | 0.4 | 100.0% |
| `grid4x4` | **balanced** | `fixed_time` | 1 | 142.47s | 199.9s | 146.78 | 210.15 | 0.8167 | 100.0% |
| `grid4x4` | **balanced** | `max_queue` | 1 | 18.66s | 34.2s | 24.83 | 32.0 | 1.0667 | 100.0% |
| `grid4x4` | **balanced** | `max_pressure` | 1 | 57.56s | 108.8s | 78.87 | 93.0 | 1.1 | 100.0% |
| `grid4x4` | **balanced** | `flow_theory` | 1 | 29.53s | 68.5s | 32.3 | 37.05 | 1.25 | 100.0% |
| `grid4x4` | **balanced** | `edgeflow` | 1 | 104.71s | 155.1s | 115.3 | 128.0 | 0.7667 | 100.0% |
| `grid4x4` | **directional_surge** | `fixed_time` | 1 | 145.67s | 229.3s | 138.68 | 197.2 | 0.8833 | 100.0% |
| `grid4x4` | **directional_surge** | `max_queue` | 1 | 20.51s | 41.0s | 18.68 | 33.15 | 1.0167 | 100.0% |
| `grid4x4` | **directional_surge** | `max_pressure` | 1 | 63.31s | 120.85s | 75.57 | 90.05 | 0.9333 | 100.0% |
| `grid4x4` | **directional_surge** | `flow_theory` | 1 | 25.09s | 49.0s | 36.8 | 45.0 | 1.1167 | 100.0% |
| `grid4x4` | **directional_surge** | `edgeflow` | 1 | 99.84s | 142.0s | 97.33 | 113.05 | 0.8167 | 100.0% |
| `grid4x4` | **downstream_congestion** | `fixed_time` | 1 | 142.47s | 199.9s | 146.78 | 210.15 | 0.8167 | 100.0% |
| `grid4x4` | **downstream_congestion** | `max_queue` | 1 | 17.02s | 30.6s | 23.78 | 31.05 | 1.0667 | 100.0% |
| `grid4x4` | **downstream_congestion** | `max_pressure` | 1 | 57.15s | 105.2s | 80.07 | 95.05 | 1.0833 | 100.0% |
| `grid4x4` | **downstream_congestion** | `flow_theory` | 1 | 28.29s | 68.2s | 32.32 | 37.05 | 1.25 | 100.0% |
| `grid4x4` | **downstream_congestion** | `edgeflow` | 1 | 105.44s | 146.5s | 115.15 | 128.0 | 0.75 | 100.0% |
| `cologne8` | **balanced** | `fixed_time` | 1 | 114.17s | 251.75s | 29.82 | 47.0 | 0.5 | 100.0% |
| `cologne8` | **balanced** | `max_queue` | 1 | 6.04s | 33.25s | 2.15 | 3.0 | 0.4667 | 100.0% |
| `cologne8` | **balanced** | `max_pressure` | 1 | 7.88s | 39.35s | 2.47 | 4.0 | 0.5 | 100.0% |
| `cologne8` | **balanced** | `flow_theory` | 1 | 8.71s | 48.25s | 3.83 | 6.0 | 0.5 | 100.0% |
| `cologne8` | **balanced** | `edgeflow` | 1 | 7.54s | 19.7s | 6.68 | 12.0 | 0.5333 | 100.0% |
| `cologne8` | **directional_surge** | `fixed_time` | 1 | 150.15s | 333.2s | 33.68 | 55.15 | 0.4833 | 100.0% |
| `cologne8` | **directional_surge** | `max_queue` | 1 | 7.4s | 29.7s | 2.83 | 6.0 | 0.5833 | 100.0% |
| `cologne8` | **directional_surge** | `max_pressure` | 1 | 15.19s | 49.5s | 3.63 | 7.05 | 0.55 | 100.0% |
| `cologne8` | **directional_surge** | `flow_theory` | 1 | 5.02s | 23.8s | 1.92 | 5.0 | 0.5333 | 100.0% |
| `cologne8` | **directional_surge** | `edgeflow` | 1 | 12.81s | 32.0s | 4.42 | 8.0 | 0.5 | 100.0% |
| `cologne8` | **downstream_congestion** | `fixed_time` | 1 | 115.12s | 237.4s | 20.98 | 43.05 | 0.4667 | 100.0% |
| `cologne8` | **downstream_congestion** | `max_queue` | 1 | 7.83s | 41.05s | 2.38 | 4.0 | 0.4167 | 100.0% |
| `cologne8` | **downstream_congestion** | `max_pressure` | 1 | 10.62s | 43.25s | 2.42 | 4.0 | 0.4333 | 100.0% |
| `cologne8` | **downstream_congestion** | `flow_theory` | 1 | 8.62s | 46.4s | 3.75 | 6.0 | 0.45 | 100.0% |
| `cologne8` | **downstream_congestion** | `edgeflow` | 1 | 13.21s | 41.1s | 6.37 | 10.05 | 0.4833 | 100.0% |
| `hcm_corridor` | **balanced** | `fixed_time` | 1 | 132.29s | 397.4s | 35.62 | 49.0 | 0.4167 | 100.0% |
| `hcm_corridor` | **balanced** | `max_queue` | 1 | 18.6s | 63.9s | 49.7 | 53.0 | 0.2833 | 62.5% |
| `hcm_corridor` | **balanced** | `max_pressure` | 1 | 17.33s | 46.35s | 12.15 | 22.05 | 0.5667 | 100.0% |
| `hcm_corridor` | **balanced** | `flow_theory` | 1 | 10.71s | 17.0s | 7.25 | 12.05 | 0.4833 | 100.0% |
| `hcm_corridor` | **balanced** | `edgeflow` | 1 | 16.91s | 68.5s | 23.5 | 30.0 | 0.4 | 45.8% |
| `hcm_corridor` | **directional_surge** | `fixed_time` | 1 | 106.04s | 375.6s | 30.7 | 44.05 | 0.4667 | 100.0% |
| `hcm_corridor` | **directional_surge** | `max_queue` | 1 | 9.53s | 23.45s | 42.9 | 49.05 | 0.3667 | 68.1% |
| `hcm_corridor` | **directional_surge** | `max_pressure` | 1 | 22.96s | 45.8s | 10.08 | 19.1 | 0.5167 | 100.0% |
| `hcm_corridor` | **directional_surge** | `flow_theory` | 1 | 9.55s | 26.7s | 4.45 | 8.05 | 0.5333 | 100.0% |
| `hcm_corridor` | **directional_surge** | `edgeflow` | 1 | 32.68s | 90.4s | 13.37 | 19.1 | 0.4667 | 100.0% |
| `hcm_corridor` | **downstream_congestion** | `fixed_time` | 1 | 133.5s | 411.9s | 35.13 | 49.0 | 0.4167 | 100.0% |
| `hcm_corridor` | **downstream_congestion** | `max_queue` | 1 | 18.6s | 63.9s | 49.7 | 53.0 | 0.2833 | 62.5% |
| `hcm_corridor` | **downstream_congestion** | `max_pressure` | 1 | 17.96s | 46.65s | 12.0 | 22.05 | 0.5667 | 100.0% |
| `hcm_corridor` | **downstream_congestion** | `flow_theory` | 1 | 8.79s | 20.4s | 6.92 | 12.05 | 0.45 | 100.0% |
| `hcm_corridor` | **downstream_congestion** | `edgeflow` | 1 | 10.5s | 44.25s | 23.07 | 30.0 | 0.4 | 41.7% |

## Performance vs Fixed-Time Baseline

| Topology | Scenario | Controller | Waiting Time Reduction (%) | Queue Reduction (%) | Throughput Gain (%) |
|---|---|---|---|---|---|
| `four_intersection_v1` | **balanced** | `max_queue` | **+88.23%** | **+76.71%** | **+6.91%** |
| `four_intersection_v1` | **balanced** | `max_pressure` | **+88.23%** | **+76.71%** | **+6.91%** |
| `four_intersection_v1` | **balanced** | `flow_theory` | **+71.84%** | **+64.87%** | **-3.43%** |
| `four_intersection_v1` | **balanced** | `edgeflow` | **+60.07%** | **+56.58%** | **-3.43%** |
| `four_intersection_v1` | **directional_surge** | `max_queue` | **+81.08%** | **+86.07%** | **+7.40%** |
| `four_intersection_v1` | **directional_surge** | `max_pressure` | **+81.08%** | **+86.07%** | **+7.40%** |
| `four_intersection_v1` | **directional_surge** | `flow_theory` | **+65.02%** | **+66.81%** | **-3.71%** |
| `four_intersection_v1` | **directional_surge** | `edgeflow` | **+67.54%** | **+71.94%** | **-7.40%** |
| `four_intersection_v1` | **downstream_congestion** | `max_queue` | **+74.73%** | **+73.42%** | **-3.71%** |
| `four_intersection_v1` | **downstream_congestion** | `max_pressure` | **+74.73%** | **+73.42%** | **-3.71%** |
| `four_intersection_v1` | **downstream_congestion** | `flow_theory` | **+70.69%** | **+65.79%** | **-14.82%** |
| `four_intersection_v1` | **downstream_congestion** | `edgeflow` | **+56.49%** | **+59.47%** | **-11.11%** |
| `grid4x4` | **balanced** | `max_queue` | **+86.90%** | **+83.08%** | **+30.61%** |
| `grid4x4` | **balanced** | `max_pressure` | **+59.60%** | **+46.27%** | **+34.69%** |
| `grid4x4` | **balanced** | `flow_theory` | **+79.27%** | **+77.99%** | **+53.05%** |
| `grid4x4` | **balanced** | `edgeflow` | **+26.50%** | **+21.45%** | **-6.12%** |
| `grid4x4` | **directional_surge** | `max_queue` | **+85.92%** | **+86.53%** | **+15.10%** |
| `grid4x4` | **directional_surge** | `max_pressure` | **+56.54%** | **+45.51%** | **+5.66%** |
| `grid4x4` | **directional_surge** | `flow_theory` | **+82.78%** | **+73.46%** | **+26.42%** |
| `grid4x4` | **directional_surge** | `edgeflow` | **+31.46%** | **+29.82%** | **-7.54%** |
| `grid4x4` | **downstream_congestion** | `max_queue` | **+88.05%** | **+83.80%** | **+30.61%** |
| `grid4x4` | **downstream_congestion** | `max_pressure` | **+59.89%** | **+45.45%** | **+32.64%** |
| `grid4x4` | **downstream_congestion** | `flow_theory` | **+80.14%** | **+77.98%** | **+53.05%** |
| `grid4x4` | **downstream_congestion** | `edgeflow` | **+25.99%** | **+21.55%** | **-8.17%** |
| `cologne8` | **balanced** | `max_queue` | **+94.71%** | **+92.79%** | **-6.66%** |
| `cologne8` | **balanced** | `max_pressure` | **+93.10%** | **+91.72%** | **+0.00%** |
| `cologne8` | **balanced** | `flow_theory` | **+92.37%** | **+87.16%** | **+0.00%** |
| `cologne8` | **balanced** | `edgeflow` | **+93.40%** | **+77.60%** | **+6.66%** |
| `cologne8` | **directional_surge** | `max_queue` | **+95.07%** | **+91.60%** | **+20.69%** |
| `cologne8` | **directional_surge** | `max_pressure` | **+89.88%** | **+89.22%** | **+13.80%** |
| `cologne8` | **directional_surge** | `flow_theory` | **+96.66%** | **+94.30%** | **+10.35%** |
| `cologne8` | **directional_surge** | `edgeflow` | **+91.47%** | **+86.88%** | **+3.46%** |
| `cologne8` | **downstream_congestion** | `max_queue` | **+93.20%** | **+88.66%** | **-10.71%** |
| `cologne8` | **downstream_congestion** | `max_pressure` | **+90.77%** | **+88.47%** | **-7.16%** |
| `cologne8` | **downstream_congestion** | `flow_theory` | **+92.51%** | **+82.13%** | **-3.58%** |
| `cologne8` | **downstream_congestion** | `edgeflow` | **+88.53%** | **+69.64%** | **+3.56%** |
| `hcm_corridor` | **balanced** | `max_queue` | **+85.94%** | **-39.53%** | **-32.01%** |
| `hcm_corridor` | **balanced** | `max_pressure` | **+86.90%** | **+65.89%** | **+36.00%** |
| `hcm_corridor` | **balanced** | `flow_theory` | **+91.90%** | **+79.65%** | **+15.98%** |
| `hcm_corridor` | **balanced** | `edgeflow` | **+87.22%** | **+34.03%** | **-4.01%** |
| `hcm_corridor` | **directional_surge** | `max_queue` | **+91.01%** | **-39.74%** | **-21.43%** |
| `hcm_corridor` | **directional_surge** | `max_pressure` | **+78.35%** | **+67.17%** | **+10.71%** |
| `hcm_corridor` | **directional_surge** | `flow_theory` | **+90.99%** | **+85.50%** | **+14.27%** |
| `hcm_corridor` | **directional_surge** | `edgeflow` | **+69.18%** | **+56.45%** | **+0.00%** |
| `hcm_corridor` | **downstream_congestion** | `max_queue` | **+86.07%** | **-41.47%** | **-32.01%** |
| `hcm_corridor` | **downstream_congestion** | `max_pressure` | **+86.55%** | **+65.84%** | **+36.00%** |
| `hcm_corridor` | **downstream_congestion** | `flow_theory` | **+93.42%** | **+80.30%** | **+7.99%** |
| `hcm_corridor` | **downstream_congestion** | `edgeflow` | **+92.13%** | **+34.33%** | **-4.01%** |
