# EdgeFlow AI — Benchmark Comparison Report (P0 Validated)

**Generated**: 2026-10-11T03:27:11Z
**Valid Runs**: 45 | **Failed**: 0
**Seeds**: [42] | **Mode**: deterministic_sim

## KPI Comparison

| Topology | Scenario | Controller | Runs | Avg Wait (s) | Avg Queue | P95 Queue | Throughput (veh/s) | Speed (m/s) |
|---|---|---|---|---|---|---|---|---|
| `four_intersection_v1` | **balanced** | `fixed_time` | 1 | 130.4s | 107.1 | 199.85 | 3.2963 | 2.75 |
| `four_intersection_v1` | **balanced** | `max_queue` | 1 | 132.48s | 106.87 | 201.41 | 3.2375 | 2.75 |
| `four_intersection_v1` | **balanced** | `max_pressure` | 1 | 132.48s | 106.87 | 201.41 | 3.2375 | 2.75 |
| `four_intersection_v1` | **balanced** | `flow_theory` | 1 | 91.61s | 87.34 | 162.64 | 3.8261 | 4.7 |
| `four_intersection_v1` | **balanced** | `edgeflow` | 1 | 191.83s | 127.31 | 240.22 | 2.6635 | 2.52 |
| `four_intersection_v1` | **directional_surge** | `fixed_time` | 1 | 194.91s | 160.08 | 306.33 | 3.2963 | 3.56 |
| `four_intersection_v1` | **directional_surge** | `max_queue` | 1 | 95.88s | 105.47 | 199.93 | 4.4147 | 2.93 |
| `four_intersection_v1` | **directional_surge** | `max_pressure` | 1 | 95.88s | 105.47 | 199.93 | 4.4147 | 2.93 |
| `four_intersection_v1` | **directional_surge** | `flow_theory` | 1 | 187.42s | 153.94 | 303.28 | 3.2963 | 3.56 |
| `four_intersection_v1` | **directional_surge** | `edgeflow` | 1 | 104.72s | 112.12 | 208.73 | 4.297 | 2.91 |
| `four_intersection_v1` | **downstream_congestion** | `fixed_time` | 1 | 172.21s | 141.44 | 267.18 | 3.2963 | 2.61 |
| `four_intersection_v1` | **downstream_congestion** | `max_queue` | 1 | 166.18s | 138.93 | 262.03 | 3.3552 | 2.55 |
| `four_intersection_v1` | **downstream_congestion** | `max_pressure` | 1 | 166.15s | 138.9 | 261.85 | 3.3552 | 2.55 |
| `four_intersection_v1` | **downstream_congestion** | `flow_theory` | 1 | 123.72s | 119.77 | 226.83 | 3.8849 | 4.75 |
| `four_intersection_v1` | **downstream_congestion** | `edgeflow` | 1 | 220.21s | 157.65 | 296.46 | 2.8732 | 2.49 |
| `grid4x4` | **balanced** | `fixed_time` | 1 | 22.47s | 19.03 | 66.51 | 27.1946 | 6.59 |
| `grid4x4` | **balanced** | `max_queue` | 1 | 0.0s | 0.0 | 0.0 | 44.1472 | 9.5 |
| `grid4x4` | **balanced** | `max_pressure` | 1 | 0.0s | 0.0 | 0.0 | 44.1472 | 9.5 |
| `grid4x4` | **balanced** | `flow_theory` | 1 | 0.0s | 0.0 | 0.0 | 44.1472 | 9.5 |
| `grid4x4` | **balanced** | `edgeflow` | 1 | 19.44s | 16.32 | 56.0 | 26.9629 | 6.61 |
| `grid4x4` | **directional_surge** | `fixed_time` | 1 | 0.65s | 0.55 | 2.42 | 27.1946 | 6.99 |
| `grid4x4` | **directional_surge** | `max_queue` | 1 | 0.0s | 0.0 | 0.0 | 44.1472 | 9.5 |
| `grid4x4` | **directional_surge** | `max_pressure` | 1 | 0.0s | 0.0 | 0.0 | 44.1472 | 9.5 |
| `grid4x4` | **directional_surge** | `flow_theory` | 1 | 0.0s | 0.0 | 0.0 | 44.1472 | 9.5 |
| `grid4x4` | **directional_surge** | `edgeflow` | 1 | 0.74s | 0.59 | 2.44 | 25.4288 | 6.39 |
| `grid4x4` | **downstream_congestion** | `fixed_time` | 1 | 30.83s | 26.11 | 92.11 | 27.1946 | 6.17 |
| `grid4x4` | **downstream_congestion** | `max_queue` | 1 | 0.0s | 0.0 | 0.0 | 44.1472 | 9.5 |
| `grid4x4` | **downstream_congestion** | `max_pressure` | 1 | 0.0s | 0.0 | 0.0 | 44.1472 | 9.5 |
| `grid4x4` | **downstream_congestion** | `flow_theory` | 1 | 0.0s | 0.0 | 0.0 | 44.1472 | 9.5 |
| `grid4x4` | **downstream_congestion** | `edgeflow` | 1 | 26.73s | 22.76 | 82.43 | 27.34 | 6.28 |
| `cologne8` | **balanced** | `fixed_time` | 1 | 943.17s | 97.21 | 268.59 | 8.0661 | 2.36 |
| `cologne8` | **balanced** | `max_queue` | 1 | 486.36s | 92.59 | 268.59 | 14.8997 | 2.77 |
| `cologne8` | **balanced** | `max_pressure` | 1 | 486.36s | 92.59 | 268.59 | 14.8997 | 2.77 |
| `cologne8` | **balanced** | `flow_theory` | 1 | 486.36s | 92.59 | 268.59 | 14.8997 | 2.77 |
| `cologne8` | **balanced** | `edgeflow` | 1 | 747.45s | 94.17 | 268.59 | 9.8595 | 2.49 |
| `cologne8` | **directional_surge** | `fixed_time` | 1 | 362.4s | 37.35 | 107.38 | 8.0661 | 2.42 |
| `cologne8` | **directional_surge** | `max_queue` | 1 | 194.51s | 37.03 | 107.38 | 14.8997 | 2.77 |
| `cologne8` | **directional_surge** | `max_pressure` | 1 | 194.51s | 37.03 | 107.38 | 14.8997 | 2.77 |
| `cologne8` | **directional_surge** | `flow_theory` | 1 | 194.51s | 37.03 | 107.38 | 14.8997 | 2.77 |
| `cologne8` | **directional_surge** | `edgeflow` | 1 | 377.72s | 37.18 | 107.38 | 7.7037 | 2.4 |
| `cologne8` | **downstream_congestion** | `fixed_time` | 1 | 1013.25s | 104.43 | 286.5 | 8.0661 | 2.29 |
| `cologne8` | **downstream_congestion** | `max_queue` | 1 | 518.82s | 98.78 | 286.5 | 14.8997 | 2.77 |
| `cologne8` | **downstream_congestion** | `max_pressure` | 1 | 518.82s | 98.78 | 286.5 | 14.8997 | 2.77 |
| `cologne8` | **downstream_congestion** | `flow_theory` | 1 | 518.82s | 98.78 | 286.5 | 14.8997 | 2.77 |
| `cologne8` | **downstream_congestion** | `edgeflow` | 1 | 783.81s | 100.79 | 286.5 | 10.0637 | 2.46 |

## Performance vs Fixed-Time Baseline

| Topology | Scenario | Controller | Wait Reduction (%) | Queue Reduction (%) | Throughput Gain (%) |
|---|---|---|---|---|---|
| `four_intersection_v1` | **balanced** | `max_queue` | **-1.6%** | **0.21%** | **-1.78%** |
| `four_intersection_v1` | **balanced** | `max_pressure` | **-1.6%** | **0.21%** | **-1.78%** |
| `four_intersection_v1` | **balanced** | `flow_theory` | **29.75%** | **18.45%** | **+16.07%** |
| `four_intersection_v1` | **balanced** | `edgeflow` | **-47.11%** | **-18.87%** | **-19.20%** |
| `four_intersection_v1` | **directional_surge** | `max_queue` | **50.81%** | **34.11%** | **+33.93%** |
| `four_intersection_v1` | **directional_surge** | `max_pressure` | **50.81%** | **34.11%** | **+33.93%** |
| `four_intersection_v1` | **directional_surge** | `flow_theory` | **3.84%** | **3.84%** | **+0.00%** |
| `four_intersection_v1` | **directional_surge** | `edgeflow` | **46.27%** | **29.96%** | **+30.36%** |
| `four_intersection_v1` | **downstream_congestion** | `max_queue` | **3.5%** | **1.77%** | **+1.79%** |
| `four_intersection_v1` | **downstream_congestion** | `max_pressure` | **3.52%** | **1.8%** | **+1.79%** |
| `four_intersection_v1` | **downstream_congestion** | `flow_theory` | **28.16%** | **15.32%** | **+17.86%** |
| `four_intersection_v1` | **downstream_congestion** | `edgeflow` | **-27.87%** | **-11.46%** | **-12.84%** |
| `grid4x4` | **balanced** | `max_queue` | **100.0%** | **100.0%** | **+62.34%** |
| `grid4x4` | **balanced** | `max_pressure` | **100.0%** | **100.0%** | **+62.34%** |
| `grid4x4` | **balanced** | `flow_theory` | **100.0%** | **100.0%** | **+62.34%** |
| `grid4x4` | **balanced** | `edgeflow` | **13.48%** | **14.24%** | **-0.85%** |
| `grid4x4` | **directional_surge** | `max_queue` | **100.0%** | **100.0%** | **+62.34%** |
| `grid4x4` | **directional_surge** | `max_pressure` | **100.0%** | **100.0%** | **+62.34%** |
| `grid4x4` | **directional_surge** | `flow_theory` | **100.0%** | **100.0%** | **+62.34%** |
| `grid4x4` | **directional_surge** | `edgeflow` | **-13.85%** | **-7.27%** | **-6.49%** |
| `grid4x4` | **downstream_congestion** | `max_queue` | **100.0%** | **100.0%** | **+62.34%** |
| `grid4x4` | **downstream_congestion** | `max_pressure` | **100.0%** | **100.0%** | **+62.34%** |
| `grid4x4` | **downstream_congestion** | `flow_theory` | **100.0%** | **100.0%** | **+62.34%** |
| `grid4x4` | **downstream_congestion** | `edgeflow` | **13.3%** | **12.83%** | **+0.53%** |
| `cologne8` | **balanced** | `max_queue` | **48.43%** | **4.75%** | **+84.72%** |
| `cologne8` | **balanced** | `max_pressure` | **48.43%** | **4.75%** | **+84.72%** |
| `cologne8` | **balanced** | `flow_theory` | **48.43%** | **4.75%** | **+84.72%** |
| `cologne8` | **balanced** | `edgeflow` | **20.75%** | **3.13%** | **+22.23%** |
| `cologne8` | **directional_surge** | `max_queue` | **46.33%** | **0.86%** | **+84.72%** |
| `cologne8` | **directional_surge** | `max_pressure` | **46.33%** | **0.86%** | **+84.72%** |
| `cologne8` | **directional_surge** | `flow_theory` | **46.33%** | **0.86%** | **+84.72%** |
| `cologne8` | **directional_surge** | `edgeflow` | **-4.23%** | **0.46%** | **-4.49%** |
| `cologne8` | **downstream_congestion** | `max_queue` | **48.8%** | **5.41%** | **+84.72%** |
| `cologne8` | **downstream_congestion** | `max_pressure` | **48.8%** | **5.41%** | **+84.72%** |
| `cologne8` | **downstream_congestion** | `flow_theory` | **48.8%** | **5.41%** | **+84.72%** |
| `cologne8` | **downstream_congestion** | `edgeflow` | **22.64%** | **3.49%** | **+24.77%** |
