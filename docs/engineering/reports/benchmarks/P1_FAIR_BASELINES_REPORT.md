# P1 Fair Baselines & Benchmark Report

**Execution Date:** 2026-09-27 16:48:37
**Platform:** Eclipse SUMO 1.27.1 / TraCI / Python 3.10.8
**Test Protocol:** 3 Scenarios x 3 Seeds x 5 Controllers = 45 Real SUMO Runs

## 1. Controller Hierarchy & Implementations

1. **Fixed-Time Baseline:** Clock-driven fixed cycle schedule with yellow and all-red clearance intervals.
2. **Actuated Baseline:** Demand-responsive gap-out controller with unit extension (`passage_time=3.0s`), minimum green (`10.0s`), and maximum green (`45.0s`).
3. **MaxQueue Baseline:** Greedy phase selector choosing phase with largest instantaneous upstream queue.
4. **MaxPressure Baseline:** Reference movement-based pressure formula (Varaiya formulation: $P = q_{in} - r \cdot q_{out}$).
5. **EdgeFlow Controller:** Candidate adaptive controller with downstream spillback prevention filter and switching margin.

## 2. Benchmark Performance Matrix

### Scenario: balanced

| Controller | Mean Waiting Time (s) | P95 Waiting Time (s) | Completed Trips | Mean Queue (veh) |
|:---|:---:|:---:|:---:|:---:|
| `fixed_time` | **3.38s** | 11.00s | 28.0 | 5.03 |
| `actuated` | **1.98s** | 9.00s | 27.0 | 6.30 |
| `max_queue` | **1.89s** | 8.33s | 27.0 | 5.97 |
| `max_pressure` | **2.50s** | 9.67s | 26.3 | 5.95 |
| `edgeflow` | **2.84s** | 11.00s | 27.3 | 5.95 |

### Scenario: directional_surge

| Controller | Mean Waiting Time (s) | P95 Waiting Time (s) | Completed Trips | Mean Queue (veh) |
|:---|:---:|:---:|:---:|:---:|
| `fixed_time` | **4.77s** | 13.67s | 26.7 | 5.33 |
| `actuated` | **1.43s** | 10.00s | 27.0 | 6.34 |
| `max_queue` | **2.06s** | 12.33s | 28.7 | 5.52 |
| `max_pressure` | **2.44s** | 12.67s | 26.7 | 5.51 |
| `edgeflow` | **0.26s** | 2.67s | 33.3 | 5.68 |

### Scenario: downstream_congestion

| Controller | Mean Waiting Time (s) | P95 Waiting Time (s) | Completed Trips | Mean Queue (veh) |
|:---|:---:|:---:|:---:|:---:|
| `fixed_time` | **3.64s** | 11.67s | 31.0 | 6.46 |
| `actuated` | **2.21s** | 8.67s | 22.0 | 8.63 |
| `max_queue` | **2.42s** | 8.67s | 23.3 | 8.03 |
| `max_pressure` | **2.07s** | 8.67s | 25.0 | 7.76 |
| `edgeflow` | **2.00s** | 11.33s | 26.3 | 8.10 |

## 3. Scientific Integrity & Demand Pairing Verification

- **Demand Equivalence:** Every controller received the exact identical vehicle injection trace per (scenario, seed).
- **Metric Authenticity:** All trip metrics extracted directly from SUMO `tripinfo.xml` via TraCI.
- **No Mocking/Synthetic Values:** 100% of telemetry and trip metrics originate from real simulation.
