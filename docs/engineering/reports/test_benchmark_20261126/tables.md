### Score per map (equal-case mean delay ± 95 % CI over test seeds, s; ✓ = passes the guardrail vs tuned Fixed-Time; ✗* = fails only because SUMO rejected a run for a collision/teleport)

| Controller | cologne8 | grid4x4 | HCM | Jakarta | Hanoi | 4-node |
|---|---|---|---|---|---|---|
| fixed_time | 61.7 ± 6.2 ✓ | 57.3 ± 2.4 ✓ | 147.5 ± 9.7 ✓ | 54.7 ± 3.0 ✓ | 42.0 ± 2.0 ✓ | 76.5 ± 1.8 ✓ |
| actuated | 39.4 ± 1.2 ✗ | 73.0 ± 1.9 ✗ | 99.7 ± 3.2 ✓ | 33.6 ± 2.6 ✓ | 84.7 ± 5.8 ✗ | 69.4 ± 1.4 ✓ |
| max_queue | 37.8 ± 1.3 ✗ | 450.5 ± 8.8 ✗ | 100.3 ± 2.9 ✓ | 31.4 ± 2.8 ✓ | 339.4 ± 11.4 ✗ | 121.6 ± 2.4 ✗ |
| max_pressure | 35.5 ± 1.3 ✓ | 20.0 ± 0.2 ✗* | 72.4 ± 1.4 ✓ | 31.5 ± 2.8 ✓ | 304.3 ± 10.5 ✗ | 119.5 ± 2.6 ✗ |
| edgeflow | 36.8 ± 1.2 ✓ | 22.8 ± 0.3 ✓ | 72.3 ± 1.0 ✓ | 31.9 ± 2.6 ✓ | 77.5 ± 7.2 ✗ | 120.4 ± 2.7 ✗ |
| flow_theory | 35.0 ± 1.1 ✓ | 24.7 ± 0.2 ✓ | 73.0 ± 0.9 ✓ | 18.5 ± 0.9 ✗ | 284.2 ± 10.1 ✗ | 74.4 ± 1.6 ✗ |
| fair_cycle | n/a | n/a | n/a | n/a | n/a | 88.3 ± 2.1 ✗ |
| fair_cycle_native | 56.3 ± 1.5 ✗ | 53.2 ± 0.5 ✗ | 103.4 ± 1.9 ✓ | 26.3 ± 1.3 ✗ | 30.2 ± 1.5 ✗* | 81.1 ± 1.9 ✗ |
| fixed_time + max-red | 58.9 ± 4.4 ✓ | 43.6 ± 0.9 ✓ | 108.1 ± 5.3 ✓ | 28.6 ± 1.2 ✓ | 44.7 ± 7.9 ✗ | 110.1 ± 6.2 ✗ |
| actuated + max-red | 39.4 ± 1.3 ✗ | 61.9 ± 2.2 ✗ | 101.8 ± 3.6 ✓ | 24.2 ± 1.1 ✓ | 47.5 ± 2.0 ✗* | 104.7 ± 5.1 ✗ |
| max_queue + max-red | 37.8 ± 1.3 ✗ | 75.7 ± 2.8 ✗ | 100.1 ± 2.9 ✓ | 23.8 ± 1.3 ✓ | 66.0 ± 3.8 ✗* | 114.3 ± 4.2 ✗ |
| max_pressure + max-red | 35.4 ± 1.3 ✓ | 20.6 ± 0.3 ✓ | 72.5 ± 1.4 ✓ | 23.8 ± 1.3 ✓ | 51.2 ± 4.0 ✗ | 112.4 ± 4.9 ✗ |
| edgeflow + max-red | 36.8 ± 1.2 ✓ | 23.6 ± 0.4 ✓ | 72.2 ± 1.0 ✓ | 24.0 ± 1.2 ✓ | 57.9 ± 4.4 ✗ | 112.9 ± 4.4 ✗ |
| flow_theory + max-red | 35.0 ± 1.1 ✓ | 27.4 ± 0.5 ✓ | 73.1 ± 0.8 ✓ | 18.7 ± 1.1 ✗ | 49.2 ± 3.1 ✗ | 95.7 ± 5.0 ✗ |
| fair_cycle + max-red | n/a | n/a | n/a | n/a | n/a | 109.0 ± 6.0 ✗ |
| fair_cycle_native + max-red | 56.1 ± 1.2 ✗ | 44.4 ± 1.0 ✓ | 103.8 ± 1.6 ✓ | 26.1 ± 1.5 ✗ | 32.4 ± 2.0 ✗ | 106.8 ± 5.0 ✗ |
| phase DQN baseline, it00b-17 | 43.4 ± 1.6 ✗ | 23.1 ± 0.4 ✓ | 85.5 ± 1.4 ✓ | 48.1 ± 3.3 ✗ | 47.2 ± 2.7 ✗ | 104.1 ± 3.3 ✗ |
| phase DQN baseline, base-1604 | 44.4 ± 1.4 ✗ | 25.4 ± 0.3 ✓ | 89.0 ± 1.8 ✓ | 36.2 ± 3.0 ✓ | 70.4 ± 4.4 ✗ | 96.1 ± 2.3 ✗ |
| phase DQN baseline, base-2026 | 40.8 ± 1.6 ✗ | 24.9 ± 0.3 ✓ | 77.6 ± 0.8 ✓ | 33.6 ± 2.3 ✓ | 70.9 ± 3.9 ✗ | 102.1 ± 2.2 ✗ |
| phase DQN baseline, mean of 3 learner seeds | **42.8** (sd 1.9; 0/3 ✓) | **24.4** (sd 1.2; 3/3 ✓) | **84.0** (sd 5.8; 3/3 ✓) | **39.3** (sd 7.7; 2/3 ✓) | **62.8** (sd 13.5; 0/3 ✓) | **100.8** (sd 4.2; 0/3 ✓) |
| round-3 config C, it32-17 | 34.8 ± 1.1 ✓ | 20.7 ± 0.2 ✓ | 73.2 ± 0.9 ✓ | 23.9 ± 1.2 ✓ | 27.9 ± 1.3 ✗ | 121.0 ± 5.1 ✗ |
| round-3 config C, it37-29 | 34.6 ± 1.2 ✓ | 20.8 ± 0.2 ✓ | 75.2 ± 1.0 ✓ | 23.9 ± 1.2 ✓ | 29.4 ± 2.5 ✗ | 121.1 ± 4.9 ✗ |
| round-3 config C, it44-41 | 34.6 ± 1.2 ✓ | 21.0 ± 0.3 ✓ | 75.0 ± 1.1 ✓ | 23.9 ± 1.2 ✓ | 30.9 ± 1.6 ✗ | 121.0 ± 4.8 ✗ |
| round-3 config C, c-1604 | 34.9 ± 1.2 ✓ | 21.2 ± 0.3 ✓ | 74.4 ± 0.8 ✓ | 23.8 ± 1.2 ✓ | 32.5 ± 2.3 ✗* | 120.9 ± 5.1 ✗ |
| round-3 config C, c-2026 | 34.5 ± 1.1 ✓ | 21.3 ± 0.2 ✓ | 74.7 ± 1.0 ✓ | 23.9 ± 1.2 ✓ | 28.1 ± 1.4 ✓ | 122.4 ± 5.3 ✗ |
| round-3 config C, mean of 5 learner seeds | **34.7** (sd 0.1; 5/5 ✓) | **21.0** (sd 0.3; 5/5 ✓) | **74.5** (sd 0.8; 5/5 ✓) | **23.9** (sd 0.0; 5/5 ✓) | **29.7** (sd 1.9; 1/5 ✓) | **121.3** (sd 0.6; 0/5 ✓) |

### Equal-map relative delay vs tuned Fixed-Time (lower is better; per-case means over valid runs; only controllers that run on all six maps)

| Controller | relative delay | per map |
|---|---|---|
| round-3 config C, it32-17 | 0.725 | cologne8 0.60 · grid4x4 0.38 · HCM 0.57 · Jakarta 0.72 · Hanoi 0.69 · 4-node 1.39 |
| round-3 config C, c-2026 | 0.727 | cologne8 0.60 · grid4x4 0.39 · HCM 0.58 · Jakarta 0.72 · Hanoi 0.69 · 4-node 1.39 |
| round-3 config C, it37-29 | 0.733 | cologne8 0.60 · grid4x4 0.39 · HCM 0.58 · Jakarta 0.72 · Hanoi 0.73 · 4-node 1.39 |
| round-3 config C, it44-41 | 0.738 | cologne8 0.60 · grid4x4 0.39 · HCM 0.58 · Jakarta 0.72 · Hanoi 0.76 · 4-node 1.39 |
| round-3 config C, c-1604 | 0.749 | cologne8 0.60 · grid4x4 0.39 · HCM 0.58 · Jakarta 0.72 · Hanoi 0.82 · 4-node 1.39 |
| flow_theory + max-red | 0.751 | cologne8 0.61 · grid4x4 0.51 · HCM 0.57 · Jakarta 0.68 · Hanoi 1.18 · 4-node 0.97 |
| max_pressure + max-red | 0.791 | cologne8 0.62 · grid4x4 0.38 · HCM 0.56 · Jakarta 0.72 · Hanoi 1.23 · 4-node 1.24 |
| edgeflow + max-red | 0.814 | cologne8 0.64 · grid4x4 0.44 · HCM 0.56 · Jakarta 0.72 · Hanoi 1.29 · 4-node 1.24 |
| phase DQN baseline (it00b config), it00b-17 | 0.852 | cologne8 0.75 · grid4x4 0.43 · HCM 0.66 · Jakarta 1.02 · Hanoi 0.99 · 4-node 1.27 |
| phase DQN baseline (it00b config), base-2026 | 0.875 | cologne8 0.71 · grid4x4 0.46 · HCM 0.60 · Jakarta 0.80 · Hanoi 1.42 · 4-node 1.26 |
| edgeflow | 0.882 | cologne8 0.64 · grid4x4 0.42 · HCM 0.56 · Jakarta 0.78 · Hanoi 1.66 · 4-node 1.23 |
| phase DQN baseline (it00b config), base-1604 | 0.897 | cologne8 0.77 · grid4x4 0.47 · HCM 0.68 · Jakarta 0.81 · Hanoi 1.44 · 4-node 1.22 |
| fair_cycle_native + max-red | 0.928 | cologne8 0.98 · grid4x4 0.81 · HCM 0.81 · Jakarta 0.88 · Hanoi 0.84 · 4-node 1.24 |
| fixed_time + max-red | 0.930 | cologne8 0.97 · grid4x4 0.79 · HCM 0.80 · Jakarta 0.80 · Hanoi 1.03 · 4-node 1.19 |
| actuated + max-red | 0.933 | cologne8 0.68 · grid4x4 1.11 · HCM 0.78 · Jakarta 0.72 · Hanoi 1.17 · 4-node 1.13 |
| fair_cycle_native | 0.933 | cologne8 0.99 · grid4x4 0.99 · HCM 0.81 · Jakarta 0.90 · Hanoi 0.80 · 4-node 1.12 |
| fixed_time | 1.000 | cologne8 1.00 · grid4x4 1.00 · HCM 1.00 · Jakarta 1.00 · Hanoi 1.00 · 4-node 1.00 |
| max_queue + max-red | 1.058 | cologne8 0.66 · grid4x4 1.36 · HCM 0.76 · Jakarta 0.72 · Hanoi 1.58 · 4-node 1.28 |
| actuated | 1.109 | cologne8 0.69 · grid4x4 1.34 · HCM 0.76 · Jakarta 0.79 · Hanoi 2.16 · 4-node 0.91 |
| flow_theory | 1.909 | cologne8 0.61 · grid4x4 0.46 · HCM 0.56 · Jakarta 0.69 · Hanoi 8.32 · 4-node 0.82 |
| max_pressure | 2.053 | cologne8 0.62 · grid4x4 0.37 · HCM 0.56 · Jakarta 0.78 · Hanoi 8.77 · 4-node 1.23 |
| max_queue | 3.595 | cologne8 0.66 · grid4x4 8.39 · HCM 0.76 · Jakarta 0.78 · Hanoi 9.72 · 4-node 1.26 |

### Research qualification gate (learned controllers; paired over 20 test seeds)

Relative delay improvement vs each baseline (positive = learned better), with the paired bootstrap 95 % CI of the delay difference in s.

| Map | Policy | Seeds | Promoted | vs fixed_time | vs actuated | vs max_pressure | vs edgeflow | Blocking reasons |
|---|---|---|---|---|---|---|---|---|
| cologne8 | it00b-17 | 20 | no | +29.7 % [+14.0, +23.3] | -10.0 % [-4.6, -3.3] | -22.4 % [-8.6, -7.2] | -17.9 % [-7.4, -5.9] | actuated/balanced: delay regression >5%; actuated/directional_reversal: delay regression >5%; actuated/downstream_bottleneck: delay regression >5%; actuated: overall delay regression >2% (+30 more) |
| cologne8 | base-1604 | 20 | no | +28.0 % [+13.0, +22.3] | -12.6 % [-5.7, -4.2] | -25.3 % [-9.6, -8.3] | -20.7 % [-8.3, -6.9] | actuated/balanced: delay regression >5%; actuated/balanced: max_approach_p95_wait_s regression; actuated/balanced: worst_approach_wait_s regression; actuated/directional_reversal: delay regression >5% (+35 more) |
| cologne8 | base-2026 | 20 | no | +34.0 % [+16.6, +25.9] | -3.3 % [-2.1, -0.6] | -14.9 % [-6.0, -4.6] | -10.8 % [-4.8, -3.1] | actuated: overall delay regression >2%; edgeflow/balanced: delay regression >5%; edgeflow/balanced: max_approach_p95_wait_s regression; edgeflow/balanced: p95_wait_s regression (+23 more) |
| cologne8 | it32-17 | 20 | no | +43.7 % [+22.2, +32.4] | +11.9 % [+4.1, +5.3] | +2.0 % [+0.3, +1.1] | +5.5 % [+1.5, +2.6] | max_pressure/balanced: max_approach_p95_wait_s regression; max_pressure/balanced: worst_approach_wait_s regression; max_pressure/directional_reversal: max_approach_p95_wait_s regression; max_pressure/directional_reversal: worst_approach_wait_s regression (+3 more) |
| cologne8 | it37-29 | 20 | no | +43.9 % [+22.5, +32.3] | +12.2 % [+4.2, +5.4] | +2.3 % [+0.4, +1.3] | +5.8 % [+1.6, +2.7] | max_pressure: 5% improvement with positive interval required |
| cologne8 | it44-41 | 20 | no | +43.9 % [+22.5, +32.4] | +12.2 % [+4.2, +5.3] | +2.3 % [+0.4, +1.3] | +5.8 % [+1.6, +2.6] | max_pressure/directional_reversal: worst_approach_wait_s regression; max_pressure: 5% improvement with positive interval required |
| cologne8 | c-1604 | 20 | no | +43.5 % [+22.2, +32.2] | +11.6 % [+4.0, +5.1] | +1.7 % [+0.1, +1.0] | +5.2 % [+1.3, +2.5] | max_pressure: 5% improvement with positive interval required |
| cologne8 | c-2026 | 20 | no | +44.1 % [+22.5, +32.6] | +12.5 % [+4.3, +5.5] | +2.7 % [+0.6, +1.3] | +6.2 % [+1.7, +2.8] | max_pressure: 5% improvement with positive interval required |
| grid4x4 | it00b-17 | 16 | no | +60.2 % [+33.2, +37.2] | +68.6 % [+48.9, +52.2] | -15.3 % [-3.3, -2.8] | -1.6 % [-0.6, -0.1] | edgeflow/balanced: worst_approach_wait_s regression; edgeflow/directional_reversal: delay regression >5%; edgeflow/directional_reversal: max_approach_p95_wait_s regression; edgeflow/directional_reversal: p95_wait_s regression (+16 more) |
| grid4x4 | base-1604 | 16 | no | +56.3 % [+30.9, +34.9] | +65.5 % [+46.7, +49.9] | -26.5 % [-5.5, -5.1] | -11.6 % [-2.9, -2.4] | edgeflow/balanced: delay regression >5%; edgeflow/balanced: worst_approach_wait_s regression; edgeflow/directional_reversal: delay regression >5%; edgeflow/directional_reversal: max_approach_p95_wait_s regression (+17 more) |
| grid4x4 | base-2026 | 16 | no | +57.1 % [+31.3, +35.5] | +66.1 % [+47.1, +50.4] | -24.2 % [-5.1, -4.7] | -9.5 % [-2.4, -2.0] | edgeflow/balanced: delay regression >5%; edgeflow/balanced: max_approach_p95_wait_s regression; edgeflow/balanced: worst_approach_wait_s regression; edgeflow/directional_reversal: delay regression >5% (+20 more) |
| grid4x4 | it32-17 | 16 | no | +64.4 % [+35.5, +39.7] | +71.9 % [+51.3, +54.6] | -3.2 % [-0.8, -0.5] | +9.0 % [+1.9, +2.2] | max_pressure/balanced: max_approach_p95_wait_s regression; max_pressure/balanced: p95_wait_s regression; max_pressure/directional_reversal: p95_wait_s regression; max_pressure/downstream_bottleneck: max_approach_p95_wait_s regression (+2 more) |
| grid4x4 | it37-29 | 16 | no | +64.2 % [+35.3, +39.7] | +71.7 % [+51.2, +54.6] | -3.7 % [-0.9, -0.6] | +8.6 % [+1.8, +2.1] | max_pressure/balanced: max_approach_p95_wait_s regression; max_pressure/balanced: p95_wait_s regression; max_pressure/directional_reversal: p95_wait_s regression; max_pressure/downstream_bottleneck: max_approach_p95_wait_s regression (+2 more) |
| grid4x4 | it44-41 | 16 | no | +63.8 % [+35.1, +39.5] | +71.4 % [+51.0, +54.4] | -4.7 % [-1.1, -0.8] | +7.7 % [+1.6, +1.9] | edgeflow/balanced: max_approach_p95_wait_s regression; edgeflow/directional_reversal: max_approach_p95_wait_s regression; edgeflow/directional_reversal: worst_approach_wait_s regression; edgeflow/downstream_bottleneck: max_approach_p95_wait_s regression (+8 more) |
| grid4x4 | c-1604 | 16 | no | +63.4 % [+34.9, +39.2] | +71.1 % [+50.8, +54.1] | -6.0 % [-1.3, -1.0] | +6.6 % [+1.4, +1.6] | edgeflow/balanced: max_approach_p95_wait_s regression; edgeflow/balanced: worst_approach_wait_s regression; edgeflow/directional_reversal: max_approach_p95_wait_s regression; edgeflow/directional_reversal: worst_approach_wait_s regression (+13 more) |
| grid4x4 | c-2026 | 16 | no | +63.3 % [+34.8, +39.1] | +71.0 % [+50.7, +54.0] | -6.3 % [-1.4, -1.1] | +6.3 % [+1.3, +1.5] | edgeflow/directional_reversal: max_approach_p95_wait_s regression; edgeflow/directional_reversal: worst_approach_wait_s regression; max_pressure/balanced: delay regression >5%; max_pressure/balanced: max_approach_p95_wait_s regression (+8 more) |
| HCM | it00b-17 | 20 | no | +42.1 % [+53.8, +70.8] | +14.2 % [+11.5, +16.9] | -18.0 % [-14.5, -11.6] | -18.3 % [-14.4, -12.0] | edgeflow/balanced: delay regression >5%; edgeflow/balanced: max_approach_p95_wait_s regression; edgeflow/balanced: p95_wait_s regression; edgeflow/balanced: worst_approach_wait_s regression (+22 more) |
| HCM | base-1604 | 20 | no | +39.7 % [+50.5, +66.9] | +10.7 % [+8.2, +13.1] | -22.9 % [-18.6, -14.7] | -23.2 % [-18.4, -15.3] | edgeflow/balanced: delay regression >5%; edgeflow/balanced: max_approach_p95_wait_s regression; edgeflow/balanced: p95_wait_s regression; edgeflow/balanced: worst_approach_wait_s regression (+22 more) |
| HCM | base-2026 | 20 | no | +47.4 % [+61.6, +78.8] | +22.1 % [+19.3, +24.8] | -7.1 % [-6.4, -3.9] | -7.4 % [-6.2, -4.5] | edgeflow/balanced: delay regression >5%; edgeflow/balanced: max_approach_p95_wait_s regression; edgeflow/balanced: p95_wait_s regression; edgeflow/balanced: worst_approach_wait_s regression (+20 more) |
| HCM | it32-17 | 20 | no | +50.4 % [+66.0, +83.2] | +26.6 % [+23.9, +29.0] | -1.0 % [-1.8, +0.4] | -1.3 % [-1.7, -0.1] | edgeflow: 5% improvement with positive interval required; max_pressure: 5% improvement with positive interval required |
| HCM | it37-29 | 20 | no | +49.1 % [+63.8, +81.4] | +24.6 % [+21.6, +27.3] | -3.8 % [-4.0, -1.4] | -4.0 % [-3.9, -1.9] | edgeflow/downstream_bottleneck: delay regression >5%; edgeflow: 5% improvement with positive interval required; max_pressure: 5% improvement with positive interval required |
| HCM | it44-41 | 20 | no | +49.2 % [+64.1, +81.6] | +24.8 % [+22.0, +27.4] | -3.5 % [-3.7, -1.3] | -3.7 % [-3.8, -1.5] | edgeflow: 5% improvement with positive interval required; max_pressure: 5% improvement with positive interval required |
| HCM | c-1604 | 20 | no | +49.6 % [+64.5, +82.3] | +25.4 % [+22.5, +27.9] | -2.7 % [-3.2, -0.8] | -3.0 % [-3.1, -1.2] | edgeflow: 5% improvement with positive interval required; max_pressure: 5% improvement with positive interval required |
| HCM | c-2026 | 20 | no | +49.4 % [+64.4, +81.8] | +25.1 % [+22.4, +27.5] | -3.1 % [-3.4, -1.1] | -3.4 % [-3.3, -1.5] | edgeflow: 5% improvement with positive interval required; max_pressure: 5% improvement with positive interval required |
| Jakarta | it00b-17 | 20 | no | +12.0 % [+4.4, +8.7] | -43.2 % [-16.9, -12.2] | -52.9 % [-18.7, -14.5] | -50.7 % [-18.3, -14.1] | actuated/balanced: delay regression >5%; actuated/balanced: max_approach_p95_wait_s regression; actuated/balanced: p95_wait_s regression; actuated/balanced: worst_approach_wait_s regression (+43 more) |
| Jakarta | base-1604 | 20 | no | +33.8 % [+17.1, +20.0] | -7.7 % [-3.8, -1.3] | -14.9 % [-5.8, -3.6] | -13.3 % [-5.2, -3.3] | actuated/directional_reversal: delay regression >5%; actuated/directional_reversal: max_approach_p95_wait_s regression; actuated/directional_reversal: p95_wait_s regression; actuated/directional_reversal: worst_approach_wait_s regression (+14 more) |
| Jakarta | base-2026 | 20 | no | +38.5 % [+19.8, +22.3] | -0.1 % [-0.9, +0.8] | -6.8 % [-3.1, -1.2] | -5.3 % [-2.3, -1.0] | edgeflow/directional_reversal: delay regression >5%; edgeflow/directional_reversal: max_approach_p95_wait_s regression; edgeflow/directional_reversal: p95_wait_s regression; edgeflow/directional_reversal: worst_approach_wait_s regression (+6 more) |
| Jakarta | it32-17 | 20 | yes | +56.3 % [+28.8, +32.6] | +28.8 % [+8.2, +11.2] | +24.0 % [+6.0, +9.2] | +25.1 % [+6.8, +9.4] |  |
| Jakarta | it37-29 | 20 | yes | +56.3 % [+28.9, +32.6] | +29.0 % [+8.3, +11.2] | +24.2 % [+6.1, +9.2] | +25.2 % [+6.8, +9.4] |  |
| Jakarta | it44-41 | 20 | yes | +56.3 % [+28.8, +32.6] | +28.9 % [+8.2, +11.2] | +24.1 % [+6.0, +9.2] | +25.1 % [+6.7, +9.4] |  |
| Jakarta | c-1604 | 20 | yes | +56.4 % [+28.9, +32.7] | +29.1 % [+8.3, +11.3] | +24.3 % [+6.1, +9.3] | +25.4 % [+6.8, +9.5] |  |
| Jakarta | c-2026 | 20 | yes | +56.3 % [+28.8, +32.7] | +28.9 % [+8.2, +11.3] | +24.1 % [+6.0, +9.2] | +25.2 % [+6.7, +9.5] |  |
| Hanoi | it00b-17 | 19 | no | -12.1 % [-6.7, -3.5] | +44.5 % [+32.4, +42.7] | +84.6 % [+246.1, +266.8] | +39.2 % [+24.1, +37.1] | fixed_time/balanced: worst_approach_wait_s regression; fixed_time/directional_reversal: delay regression >5%; fixed_time/directional_reversal: max_approach_p95_wait_s regression; fixed_time/directional_reversal: p95_wait_s regression (+3 more) |
| Hanoi | base-1604 | 19 | no | -67.2 % [-31.5, -24.9] | +17.2 % [+9.4, +19.8] | +77.0 % [+222.5, +244.3] | +9.2 % [+0.6, +13.9] | actuated/directional_reversal: delay regression >5%; fixed_time/balanced: delay regression >5%; fixed_time/balanced: max_approach_p95_wait_s regression; fixed_time/balanced: p95_wait_s regression (+10 more) |
| Hanoi | base-2026 | 19 | no | -69.5 % [-31.3, -26.5] | +16.1 % [+8.8, +18.4] | +76.7 % [+223.2, +241.7] | +8.0 % [+0.1, +12.7] | actuated/directional_reversal: delay regression >5%; fixed_time/balanced: delay regression >5%; fixed_time/balanced: max_approach_p95_wait_s regression; fixed_time/balanced: p95_wait_s regression (+10 more) |
| Hanoi | it32-17 | 19 | no | +33.3 % [+12.8, +15.1] | +67.0 % [+51.5, +61.8] | +90.8 % [+265.7, +285.3] | +63.8 % [+43.1, +56.3] | fixed_time/balanced: max_approach_p95_wait_s regression; fixed_time/balanced: worst_approach_wait_s regression; fixed_time/downstream_bottleneck: max_approach_p95_wait_s regression; fixed_time/downstream_bottleneck: worst_approach_wait_s regression |
| Hanoi | it37-29 | 19 | no | +29.5 % [+9.8, +14.4] | +65.1 % [+48.9, +61.1] | +90.3 % [+264.0, +284.2] | +61.7 % [+40.6, +55.3] | fixed_time/balanced: max_approach_p95_wait_s regression; fixed_time/balanced: worst_approach_wait_s regression; fixed_time/downstream_bottleneck: max_approach_p95_wait_s regression; fixed_time/downstream_bottleneck: worst_approach_wait_s regression |
| Hanoi | it44-41 | 19 | no | +26.5 % [+9.6, +12.6] | +63.6 % [+48.8, +58.8] | +89.9 % [+262.9, +282.4] | +60.1 % [+40.4, +53.4] | fixed_time/balanced: max_approach_p95_wait_s regression; fixed_time/balanced: worst_approach_wait_s regression; fixed_time/downstream_bottleneck: max_approach_p95_wait_s regression; fixed_time/downstream_bottleneck: worst_approach_wait_s regression |
| Hanoi | c-1604 | 17 | no | +22.9 % [+7.4, +11.9] | +62.0 % [+48.0, +59.0] | +89.3 % [+263.1, +283.5] | +58.3 % [+39.6, +52.5] | fixed_time/balanced: max_approach_p95_wait_s regression; fixed_time/balanced: p95_wait_s regression; fixed_time/balanced: worst_approach_wait_s regression; fixed_time/downstream_bottleneck: max_approach_p95_wait_s regression (+2 more) |
| Hanoi | c-2026 | 19 | yes | +33.0 % [+12.7, +14.9] | +66.8 % [+51.4, +61.9] | +90.8 % [+265.6, +285.2] | +63.6 % [+42.7, +56.5] |  |
| 4-node | it00b-17 | 20 | no | -36.0 % [-30.4, -25.4] | -49.9 % [-37.4, -32.5] | +12.9 % [+12.2, +18.0] | +13.6 % [+13.0, +19.0] | actuated/balanced: max_approach_p95_wait_s regression; actuated/directional_reversal: delay regression >5%; actuated/directional_reversal: max_approach_p95_wait_s regression; actuated/directional_reversal: p95_wait_s regression (+71 more) |
| 4-node | base-1604 | 20 | no | -25.6 % [-20.7, -18.6] | -38.4 % [-27.8, -25.5] | +19.6 % [+21.9, +24.8] | +20.2 % [+22.8, +25.8] | actuated/balanced: max_approach_p95_wait_s regression; actuated/directional_reversal: delay regression >5%; actuated/directional_reversal: max_approach_p95_wait_s regression; actuated/directional_reversal: p95_wait_s regression (+60 more) |
| 4-node | base-2026 | 20 | no | -33.4 % [-27.3, -24.1] | -47.1 % [-34.3, -31.3] | +14.5 % [+15.5, +19.2] | +15.2 % [+16.3, +20.3] | actuated/balanced: max_approach_p95_wait_s regression; actuated/directional_reversal: delay regression >5%; actuated/directional_reversal: max_approach_p95_wait_s regression; actuated/directional_reversal: p95_wait_s regression (+69 more) |
| 4-node | it32-17 | 20 | no | -58.1 % [-49.2, -39.8] | -74.3 % [-56.5, -46.8] | -1.3 % [-6.7, +3.5] | -0.4 % [-5.7, +4.3] | actuated/balanced: max_approach_p95_wait_s regression; actuated/directional_reversal: delay regression >5%; actuated/directional_reversal: max_approach_p95_wait_s regression; actuated/directional_reversal: p95_wait_s regression (+70 more) |
| 4-node | it37-29 | 20 | no | -58.3 % [-49.4, -39.9] | -74.5 % [-56.5, -47.1] | -1.4 % [-6.7, +3.3] | -0.6 % [-5.7, +4.1] | actuated/balanced: max_approach_p95_wait_s regression; actuated/directional_reversal: delay regression >5%; actuated/directional_reversal: max_approach_p95_wait_s regression; actuated/directional_reversal: p95_wait_s regression (+68 more) |
| 4-node | it44-41 | 20 | no | -58.1 % [-49.1, -40.0] | -74.3 % [-56.3, -47.1] | -1.3 % [-6.6, +3.1] | -0.5 % [-5.6, +4.0] | actuated/balanced: max_approach_p95_wait_s regression; actuated/directional_reversal: delay regression >5%; actuated/directional_reversal: max_approach_p95_wait_s regression; actuated/directional_reversal: p95_wait_s regression (+68 more) |
| 4-node | c-1604 | 20 | no | -58.0 % [-49.5, -39.6] | -74.2 % [-56.6, -46.7] | -1.2 % [-6.8, +3.6] | -0.4 % [-5.8, +4.5] | actuated/balanced: max_approach_p95_wait_s regression; actuated/directional_reversal: delay regression >5%; actuated/directional_reversal: max_approach_p95_wait_s regression; actuated/directional_reversal: p95_wait_s regression (+68 more) |
| 4-node | c-2026 | 20 | no | -59.9 % [-51.0, -40.8] | -76.3 % [-58.1, -47.9] | -2.4 % [-8.2, +2.3] | -1.6 % [-7.3, +3.2] | actuated/balanced: max_approach_p95_wait_s regression; actuated/directional_reversal: delay regression >5%; actuated/directional_reversal: max_approach_p95_wait_s regression; actuated/directional_reversal: p95_wait_s regression (+69 more) |

### Learned vs the best guardrail-passing deterministic controller (paired over test seeds valid in both)

Learned minus deterministic equal-case delay, s (negative = learned better), mean ± t 95 % half-width over seeds. The deterministic side is the lowest-scoring controller, plain or with max-red, that passes the guardrail on that map.

| Map | Best deterministic | it00b-17 | base-1604 | base-2026 | it32-17 | it37-29 | it44-41 | c-1604 | c-2026 |
|---|---|---|---|---|---|---|---|---|---|
| cologne8 | flow_theory + max-red (35.0) | +8.4 ± 0.8 | +9.5 ± 0.8 | +5.8 ± 0.9 | -0.2 ± 0.4 | -0.3 ± 0.5 | -0.3 ± 0.4 | -0.1 ± 0.4 | -0.4 ± 0.4 |
| grid4x4 | max_pressure + max-red (20.6) | +2.5 ± 0.3 | +4.8 ± 0.2 | +4.4 ± 0.3 | +0.1 ± 0.2 | +0.2 ± 0.2 | +0.5 ± 0.3 | +0.7 ± 0.3 | +0.8 ± 0.2 |
| HCM | edgeflow + max-red (72.2) | +13.3 ± 1.3 | +16.9 ± 1.7 | +5.5 ± 0.9 | +1.0 ± 0.8 | +3.0 ± 1.1 | +2.8 ± 1.2 | +2.2 ± 1.0 | +2.5 ± 1.0 |
| Jakarta | max_pressure + max-red (23.8) | +24.3 ± 2.6 | +12.4 ± 2.0 | +9.8 ± 1.2 | +0.1 ± 0.2 | +0.1 ± 0.2 | +0.1 ± 0.3 | +0.0 ± 0.3 | +0.1 ± 0.3 |
| Hanoi | fixed_time (42.0) | +5.1 ± 1.7 | +28.3 ± 3.5 | +28.8 ± 2.7 | -14.2 ± 1.3 | -12.6 ± 2.5 | -11.2 ± 1.6 | -9.7 ± 2.3 | -14.0 ± 1.2 |
| 4-node | actuated (69.4) | +34.6 ± 2.7 | +26.7 ± 1.3 | +32.7 ± 1.7 | +51.6 ± 5.3 | +51.7 ± 5.1 | +51.6 ± 5.0 | +51.5 ± 5.4 | +53.0 ± 5.5 |

### cologne8 (`cologne8_benchmark_v1`)

Per case: mean delay / p95 wait / worst-approach wait / max approach-p95 wait (s), mean over 20 test seeds.

| Controller | Score | Pass | balanced | directional_reversal | downstream_bottleneck |
|---|---|---|---|---|---|
| fixed_time | 61.7 | ✓ | 44.0 / 57.4 / 48.8 / 45.9 | 86.2 / 132.4 / 154.2 / 57.8 | 55.0 / 57.1 / 48.6 / 45.9 |
| actuated | 39.4 | ✗ | 34.0 / 43.8 / 71.3 / 57.5 | 38.2 / 46.9 / 73.2 / 59.1 | 46.2 / 44.1 / 72.1 / 57.2 |
| max_queue | 37.8 | ✗ | 32.7 / 46.2 / 85.7 / 74.9 | 36.0 / 50.3 / 81.2 / 69.3 | 44.7 / 46.0 / 85.6 / 74.6 |
| max_pressure | 35.5 | ✓ | 30.1 / 30.0 / 30.8 / 22.9 | 33.5 / 33.8 / 40.6 / 30.4 | 42.7 / 30.2 / 32.4 / 22.6 |
| edgeflow | 36.8 | ✓ | 31.7 / 37.5 / 45.9 / 38.9 | 35.5 / 41.1 / 48.8 / 43.7 | 43.2 / 37.0 / 45.2 / 39.3 |
| flow_theory | 35.0 | ✓ | 30.0 / 31.9 / 39.2 / 30.6 | 32.6 / 35.1 / 46.9 / 38.2 | 42.3 / 32.8 / 41.1 / 31.8 |
| fair_cycle_native | 56.3 | ✗ | 51.4 / 84.5 / 85.6 / 77.9 | 52.7 / 81.9 / 86.4 / 75.8 | 64.8 / 84.7 / 85.5 / 77.9 |
| fixed_time + max-red | 58.9 | ✓ | 44.0 / 57.4 / 48.8 / 45.9 | 77.6 / 104.1 / 82.3 / 55.7 | 55.0 / 57.1 / 48.6 / 45.9 |
| actuated + max-red | 39.4 | ✗ | 33.9 / 44.0 / 70.9 / 56.4 | 38.0 / 46.9 / 71.9 / 58.3 | 46.3 / 44.4 / 71.8 / 56.5 |
| max_queue + max-red | 37.8 | ✗ | 32.8 / 46.1 / 85.6 / 74.6 | 35.7 / 49.5 / 81.1 / 69.6 | 44.8 / 46.0 / 85.6 / 74.6 |
| max_pressure + max-red | 35.4 | ✓ | 30.1 / 30.0 / 30.8 / 22.9 | 33.5 / 33.7 / 42.1 / 31.0 | 42.7 / 30.2 / 32.4 / 22.6 |
| edgeflow + max-red | 36.8 | ✓ | 31.7 / 37.6 / 45.6 / 38.8 | 35.4 / 40.9 / 47.4 / 42.1 | 43.2 / 36.9 / 44.6 / 39.1 |
| flow_theory + max-red | 35.0 | ✓ | 30.0 / 31.9 / 38.9 / 30.5 | 32.6 / 35.1 / 46.1 / 38.0 | 42.3 / 32.8 / 40.9 / 31.7 |
| fair_cycle_native + max-red | 56.1 | ✗ | 50.9 / 83.0 / 61.8 / 57.3 | 53.2 / 80.4 / 68.0 / 62.4 | 64.3 / 81.7 / 60.8 / 56.7 |
| phase DQN baseline (it00b config), it00b-17 | 43.4 | ✗ | 36.9 / 41.3 / 72.9 / 57.6 | 43.5 / 48.8 / 55.1 / 49.6 | 49.7 / 41.7 / 71.1 / 55.7 |
| phase DQN baseline (it00b config), base-1604 | 44.4 | ✗ | 38.5 / 44.5 / 98.3 / 76.2 | 44.5 / 49.2 / 80.7 / 58.5 | 50.3 / 43.8 / 112.6 / 76.4 |
| phase DQN baseline (it00b config), base-2026 | 40.8 | ✗ | 35.6 / 42.8 / 55.9 / 45.2 | 39.0 / 44.2 / 57.5 / 47.1 | 47.7 / 42.6 / 54.6 / 45.2 |
| round-3 config C, it32-17 | 34.8 | ✓ | 29.4 / 29.4 / 36.4 / 27.2 | 33.9 / 35.1 / 46.0 / 34.4 | 41.0 / 29.2 / 36.1 / 26.3 |
| round-3 config C, it37-29 | 34.6 | ✓ | 29.2 / 29.3 / 33.4 / 24.3 | 33.8 / 34.9 / 42.1 / 33.1 | 40.9 / 29.5 / 34.2 / 24.4 |
| round-3 config C, it44-41 | 34.6 | ✓ | 29.1 / 28.3 / 29.3 / 22.0 | 34.1 / 35.3 / 46.4 / 31.2 | 40.7 / 27.7 / 29.5 / 21.7 |
| round-3 config C, c-1604 | 34.9 | ✓ | 29.3 / 28.8 / 27.7 / 21.0 | 33.8 / 33.9 / 37.1 / 28.4 | 41.5 / 29.3 / 27.2 / 20.0 |
| round-3 config C, c-2026 | 34.5 | ✓ | 28.9 / 28.5 / 28.2 / 21.3 | 33.6 / 33.6 / 36.0 / 28.3 | 41.0 / 29.2 / 30.1 / 22.2 |

Other metrics, averaged over cases (recovery: bottleneck and reversal cases only, seeds that recovered; censored = runs that never recovered). Collisions / teleports / accounting losses are totals over valid runs; invalid = runs SUMO rejected for a collision or teleport (excluded from every mean).

| Controller | Completion % | Throughput veh/s | Unfinished | Uninserted | Peak backlog veh | Recovery s (censored) | Max service gap s | Clearance node-s | motorcycle delay | car delay | taxi delay | bus delay | truck delay | Coll / tele / acct / invalid | Wall s/run |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| fixed_time | 100.00 | 0.162 | 0.0 | 0.0 | 18 | 215.7 (1) | 44 | 5316 | 61.0 | 63.6 | 64.1 | 60.6 | 62.1 | 0 / 0 / 0 / 0 | 6.6 |
| actuated | 100.00 | 0.163 | 0.0 | 0.0 | 12 | 207.0 (0) | 70 | 2246 | 39.4 | 40.4 | 38.9 | 36.9 | 37.1 | 0 / 0 / 0 / 0 | 7.2 |
| max_queue | 100.00 | 0.163 | 0.0 | 0.0 | 11 | 151.0 (0) | 82 | 1766 | 37.9 | 38.2 | 38.0 | 35.4 | 36.5 | 0 / 0 / 0 / 0 | 8.2 |
| max_pressure | 100.00 | 0.163 | 0.0 | 0.0 | 10 | 183.9 (0) | 29 | 1944 | 35.3 | 36.3 | 35.5 | 32.8 | 34.1 | 0 / 0 / 0 / 0 | 7.2 |
| edgeflow | 100.00 | 0.164 | 0.0 | 0.0 | 11 | 165.0 (0) | 41 | 2117 | 36.8 | 37.5 | 36.0 | 33.6 | 35.0 | 0 / 0 / 0 / 0 | 7.9 |
| flow_theory | 100.00 | 0.164 | 0.0 | 0.0 | 10 | 123.1 (0) | 38 | 1828 | 34.9 | 36.0 | 35.0 | 32.0 | 33.2 | 0 / 0 / 0 / 0 | 7.7 |
| fair_cycle_native | 100.00 | 0.162 | 0.0 | 0.0 | 19 | 147.6 (1) | 81 | 2948 | 56.2 | 57.3 | 55.5 | 51.1 | 56.6 | 0 / 0 / 0 / 0 | 8.3 |
| fixed_time + max-red | 100.00 | 0.162 | 0.0 | 0.0 | 18 | 199.3 (1) | 45 | 5315 | 58.3 | 60.5 | 60.0 | 57.4 | 60.2 | 0 / 0 / 0 / 0 | 6.1 |
| actuated + max-red | 100.00 | 0.163 | 0.0 | 0.0 | 12 | 208.5 (0) | 70 | 2244 | 39.3 | 40.4 | 39.0 | 36.8 | 37.0 | 0 / 0 / 0 / 0 | 6.4 |
| max_queue + max-red | 100.00 | 0.163 | 0.0 | 0.0 | 11 | 143.5 (0) | 82 | 1766 | 37.8 | 38.1 | 38.0 | 35.4 | 36.6 | 0 / 0 / 0 / 0 | 6.2 |
| max_pressure + max-red | 100.00 | 0.163 | 0.0 | 0.0 | 10 | 185.8 (0) | 29 | 1943 | 35.3 | 36.3 | 35.6 | 32.8 | 34.1 | 0 / 0 / 0 / 0 | 6.2 |
| edgeflow + max-red | 100.00 | 0.164 | 0.0 | 0.0 | 11 | 166.1 (0) | 41 | 2116 | 36.8 | 37.6 | 35.9 | 33.6 | 34.9 | 0 / 0 / 0 / 0 | 6.4 |
| flow_theory + max-red | 100.00 | 0.164 | 0.0 | 0.0 | 10 | 123.0 (0) | 38 | 1828 | 34.8 | 36.0 | 35.1 | 32.1 | 33.2 | 0 / 0 / 0 / 0 | 6.5 |
| fair_cycle_native + max-red | 100.00 | 0.161 | 0.0 | 0.0 | 19 | 166.5 (0) | 62 | 2987 | 55.9 | 57.4 | 57.1 | 51.7 | 56.2 | 0 / 0 / 0 / 0 | 6.5 |
| phase DQN baseline (it00b config), it00b-17 | 100.00 | 0.163 | 0.0 | 0.0 | 13 | 183.8 (0) | 62 | 4758 | 43.0 | 44.7 | 43.4 | 40.5 | 43.9 | 0 / 0 / 0 / 0 | 4.1 |
| phase DQN baseline (it00b config), base-1604 | 99.99 | 0.162 | 0.0 | 0.0 | 13 | 187.8 (0) | 95 | 3894 | 44.0 | 45.9 | 45.1 | 41.9 | 43.9 | 0 / 0 / 0 / 0 | 3.8 |
| phase DQN baseline (it00b config), base-2026 | 100.00 | 0.163 | 0.0 | 0.0 | 12 | 204.2 (0) | 53 | 3161 | 40.6 | 41.8 | 40.2 | 38.2 | 39.5 | 0 / 0 / 0 / 0 | 3.0 |
| round-3 config C, it32-17 | 100.00 | 0.163 | 0.0 | 0.0 | 11 | 128.9 (0) | 35 | 1853 | 34.6 | 35.7 | 34.7 | 32.9 | 32.5 | 0 / 0 / 0 / 0 | 4.2 |
| round-3 config C, it37-29 | 100.00 | 0.163 | 0.0 | 0.0 | 10 | 124.5 (0) | 30 | 1835 | 34.6 | 35.5 | 34.1 | 31.5 | 32.9 | 0 / 0 / 0 / 0 | 4.3 |
| round-3 config C, it44-41 | 100.00 | 0.163 | 0.0 | 0.0 | 10 | 131.1 (0) | 30 | 1851 | 34.6 | 35.5 | 34.2 | 33.0 | 32.4 | 0 / 0 / 0 / 0 | 4.3 |
| round-3 config C, c-1604 | 100.00 | 0.163 | 0.0 | 0.0 | 11 | 146.8 (0) | 26 | 1850 | 34.7 | 35.8 | 34.7 | 33.3 | 33.0 | 0 / 0 / 0 / 0 | 4.2 |
| round-3 config C, c-2026 | 100.00 | 0.163 | 0.0 | 0.0 | 10 | 110.4 (0) | 25 | 1846 | 34.4 | 35.3 | 34.8 | 32.3 | 32.1 | 0 / 0 / 0 / 0 | 3.5 |

### grid4x4 (`grid4x4_benchmark_v1`)

Per case: mean delay / p95 wait / worst-approach wait / max approach-p95 wait (s), mean over 20 test seeds.

| Controller | Score | Pass | balanced | directional_reversal | downstream_bottleneck |
|---|---|---|---|---|---|
| fixed_time | 57.3 | ✓ | 45.8 / 102.4 / 164.2 / 136.9 | 79.3 / 239.2 / 377.2 / 339.3 | 47.0 / 101.4 / 169.5 / 141.1 |
| actuated | 73.0 | ✗ | 69.5 / 250.0 / 686.9 / 608.6 | 78.6 / 263.7 / 818.2 / 699.2 | 71.0 / 250.1 / 688.6 / 608.0 |
| max_queue | 450.5 | ✗ | 453.1 / 2008.9 / 2370.7 / 2338.8 | 444.1 / 1856.2 / 2362.6 / 2298.2 | 454.0 / 2009.7 / 2370.7 / 2338.8 |
| max_pressure | 20.0 | ✗* | 19.2 / 29.6 / 87.8 / 50.5 | 20.6 / 31.6 / 113.5 / 59.7 | 20.4 / 29.7 / 89.9 / 52.5 |
| edgeflow | 22.8 | ✓ | 22.1 / 39.9 / 81.0 / 57.8 | 22.9 / 40.2 / 88.5 / 60.8 | 23.3 / 40.2 / 82.2 / 58.6 |
| flow_theory | 24.7 | ✓ | 24.1 / 50.3 / 166.9 / 108.2 | 24.9 / 52.1 / 221.8 / 117.6 | 25.1 / 50.0 / 155.1 / 103.4 |
| fair_cycle_native | 53.2 | ✗ | 52.6 / 139.1 / 179.9 / 162.0 | 53.2 / 135.6 / 182.1 / 154.7 | 53.8 / 139.1 / 179.9 / 161.8 |
| fixed_time + max-red | 43.6 | ✓ | 40.4 / 89.1 / 166.0 / 135.2 | 49.0 / 111.0 / 224.6 / 197.7 | 41.5 / 89.2 / 164.6 / 133.4 |
| actuated + max-red | 61.9 | ✗ | 55.1 / 134.3 / 208.6 / 176.0 | 74.7 / 199.2 / 392.6 / 353.0 | 56.1 / 134.1 / 207.6 / 174.7 |
| max_queue + max-red | 75.7 | ✗ | 66.3 / 197.7 / 336.4 / 299.2 | 93.1 / 307.1 / 543.2 / 492.0 | 67.8 / 199.4 / 333.5 / 303.9 |
| max_pressure + max-red | 20.6 | ✓ | 19.6 / 30.7 / 110.9 / 70.0 | 21.5 / 35.5 / 124.8 / 86.2 | 20.6 / 30.3 / 111.6 / 67.7 |
| edgeflow + max-red | 23.6 | ✓ | 22.6 / 42.0 / 114.6 / 76.0 | 24.5 / 45.9 / 126.4 / 96.6 | 23.9 / 42.1 / 123.1 / 84.1 |
| flow_theory + max-red | 27.4 | ✓ | 26.3 / 63.6 / 143.5 / 120.4 | 28.7 / 73.0 / 146.9 / 126.2 | 27.5 / 63.9 / 142.3 / 121.9 |
| fair_cycle_native + max-red | 44.4 | ✓ | 41.9 / 96.5 / 133.8 / 112.2 | 48.1 / 118.9 / 202.0 / 178.3 | 43.2 / 96.3 / 135.4 / 112.9 |
| phase DQN baseline (it00b config), it00b-17 | 23.1 | ✓ | 21.9 / 36.3 / 107.5 / 61.1 | 24.4 / 43.5 / 138.1 / 74.1 | 23.0 / 36.4 / 111.2 / 61.7 |
| phase DQN baseline (it00b config), base-1604 | 25.4 | ✓ | 24.1 / 42.9 / 105.6 / 64.0 | 26.8 / 47.4 / 123.4 / 74.2 | 25.2 / 42.7 / 102.1 / 63.0 |
| phase DQN baseline (it00b config), base-2026 | 24.9 | ✓ | 23.7 / 41.7 / 98.6 / 65.3 | 26.2 / 46.4 / 128.6 / 72.6 | 24.9 / 42.0 / 100.3 / 67.3 |
| round-3 config C, it32-17 | 20.7 | ✓ | 19.9 / 34.2 / 87.9 / 65.9 | 21.2 / 36.8 / 89.9 / 65.4 | 21.1 / 34.2 / 87.9 / 63.2 |
| round-3 config C, it37-29 | 20.8 | ✓ | 20.0 / 34.2 / 75.9 / 58.0 | 21.2 / 37.5 / 87.5 / 64.1 | 21.2 / 34.6 / 78.7 / 59.6 |
| round-3 config C, it44-41 | 21.0 | ✓ | 20.2 / 35.7 / 93.9 / 68.9 | 21.6 / 38.4 / 102.1 / 76.0 | 21.3 / 35.6 / 93.6 / 70.6 |
| round-3 config C, c-1604 | 21.2 | ✓ | 20.3 / 35.8 / 96.3 / 67.5 | 22.0 / 40.3 / 105.3 / 82.3 | 21.5 / 36.3 / 97.4 / 69.6 |
| round-3 config C, c-2026 | 21.3 | ✓ | 20.5 / 36.3 / 90.0 / 67.5 | 22.0 / 39.5 / 98.3 / 74.6 | 21.5 / 35.7 / 87.8 / 63.4 |

Other metrics, averaged over cases (recovery: bottleneck and reversal cases only, seeds that recovered; censored = runs that never recovered). Collisions / teleports / accounting losses are totals over valid runs; invalid = runs SUMO rejected for a collision or teleport (excluded from every mean).

| Controller | Completion % | Throughput veh/s | Unfinished | Uninserted | Peak backlog veh | Recovery s (censored) | Max service gap s | Clearance node-s | motorcycle delay | car delay | taxi delay | bus delay | truck delay | Coll / tele / acct / invalid | Wall s/run |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| fixed_time | 100.00 | 1.042 | 0.0 | 0.0 | 96 | 230.4 (0) | 105 | 10552 | 56.7 | 58.6 | 55.9 | 60.7 | 59.6 | 0 / 0 / 0 / 1 | 21.9 |
| actuated | 100.00 | 0.988 | 0.0 | 0.0 | 119 | 123.0 (0) | 731 | 5014 | 72.6 | 73.5 | 69.0 | 80.3 | 75.0 | 0 / 0 / 0 / 2 | 23.2 |
| max_queue | 71.94 | 0.620 | 576.4 | 2.5 | 600 | — (40) | 2370 | 4947 | 452.7 | 446.7 | 417.0 | 463.9 | 457.9 | 0 / 0 / 0 / 0 | 47.1 |
| max_pressure | 100.00 | 1.088 | 0.0 | 0.0 | 30 | 180.6 (0) | 123 | 6970 | 19.9 | 20.2 | 20.2 | 21.3 | 20.0 | 0 / 0 / 0 / 1 | 12.2 |
| edgeflow | 100.00 | 1.085 | 0.0 | 0.0 | 34 | 152.4 (0) | 122 | 6596 | 22.6 | 22.9 | 22.6 | 24.3 | 22.6 | 0 / 0 / 0 / 0 | 18.0 |
| flow_theory | 100.00 | 1.082 | 0.0 | 0.0 | 38 | 121.8 (0) | 228 | 5889 | 24.6 | 24.9 | 24.2 | 26.4 | 24.7 | 0 / 0 / 0 / 0 | 14.1 |
| fair_cycle_native | 100.00 | 1.014 | 0.0 | 0.0 | 94 | 56.1 (0) | 190 | 6499 | 53.2 | 53.1 | 50.4 | 56.6 | 54.0 | 0 / 0 / 0 / 0 | 10.4 |
| fixed_time + max-red | 100.00 | 1.053 | 0.0 | 0.0 | 75 | 111.2 (0) | 258 | 9678 | 43.4 | 44.0 | 43.1 | 45.9 | 44.3 | 0 / 0 / 0 / 0 | 18.7 |
| actuated + max-red | 99.96 | 1.035 | 0.8 | 0.0 | 104 | 147.1 (0) | 488 | 5110 | 61.8 | 62.1 | 60.7 | 66.1 | 63.2 | 0 / 0 / 0 / 0 | 20.9 |
| max_queue + max-red | 100.00 | 0.978 | 0.0 | 0.0 | 125 | 182.8 (0) | 771 | 4284 | 75.4 | 76.0 | 73.1 | 81.1 | 78.9 | 0 / 0 / 0 / 0 | 18.1 |
| max_pressure + max-red | 100.00 | 1.084 | 0.0 | 0.0 | 32 | 179.6 (0) | 145 | 6928 | 20.5 | 20.7 | 20.7 | 22.1 | 20.4 | 0 / 0 / 0 / 0 | 10.8 |
| edgeflow + max-red | 100.00 | 1.081 | 0.0 | 0.0 | 37 | 154.4 (0) | 155 | 6554 | 23.5 | 23.8 | 23.1 | 25.7 | 23.9 | 0 / 0 / 0 / 0 | 19.4 |
| flow_theory + max-red | 100.00 | 1.076 | 0.0 | 0.0 | 48 | 141.5 (0) | 225 | 5809 | 27.4 | 27.7 | 26.6 | 29.7 | 27.6 | 0 / 0 / 0 / 0 | 12.5 |
| fair_cycle_native + max-red | 100.00 | 1.039 | 0.0 | 0.0 | 72 | 118.4 (0) | 271 | 6757 | 44.2 | 44.5 | 43.3 | 48.3 | 45.4 | 0 / 0 / 0 / 0 | 9.6 |
| phase DQN baseline (it00b config), it00b-17 | 100.00 | 1.082 | 0.0 | 0.0 | 37 | 152.9 (0) | 137 | 10103 | 22.9 | 23.3 | 23.0 | 24.5 | 23.0 | 0 / 0 / 0 / 0 | 16.2 |
| phase DQN baseline (it00b config), base-1604 | 100.00 | 1.079 | 0.0 | 0.0 | 40 | 112.2 (1) | 121 | 10125 | 25.2 | 25.5 | 25.0 | 27.3 | 25.8 | 0 / 0 / 0 / 0 | 16.1 |
| phase DQN baseline (it00b config), base-2026 | 100.00 | 1.080 | 0.0 | 0.0 | 39 | 91.2 (0) | 121 | 10123 | 24.8 | 25.0 | 24.8 | 27.0 | 25.5 | 0 / 0 / 0 / 0 | 13.1 |
| round-3 config C, it32-17 | 100.00 | 1.087 | 0.0 | 0.0 | 32 | 170.8 (1) | 128 | 6017 | 20.6 | 20.9 | 20.4 | 22.3 | 20.4 | 0 / 0 / 0 / 0 | 21.6 |
| round-3 config C, it37-29 | 100.00 | 1.088 | 0.0 | 0.0 | 32 | 170.4 (0) | 118 | 6098 | 20.7 | 21.0 | 20.5 | 22.5 | 20.5 | 0 / 0 / 0 / 0 | 21.8 |
| round-3 config C, it44-41 | 100.00 | 1.086 | 0.0 | 0.0 | 32 | 158.4 (0) | 138 | 6101 | 20.9 | 21.2 | 20.7 | 22.4 | 20.8 | 0 / 0 / 0 / 0 | 21.8 |
| round-3 config C, c-1604 | 100.00 | 1.087 | 0.0 | 0.0 | 33 | 182.0 (0) | 139 | 6136 | 21.1 | 21.4 | 21.1 | 23.1 | 21.0 | 0 / 0 / 0 / 0 | 21.7 |
| round-3 config C, c-2026 | 100.00 | 1.086 | 0.0 | 0.0 | 33 | 138.6 (0) | 127 | 6283 | 21.2 | 21.5 | 21.0 | 22.8 | 21.3 | 0 / 0 / 0 / 0 | 20.8 |

### HCM (`hcm_neighborhood_v3_benchmark_v1`)

Per case: mean delay / p95 wait / worst-approach wait / max approach-p95 wait (s), mean over 20 test seeds.

| Controller | Score | Pass | balanced | directional_reversal | downstream_bottleneck |
|---|---|---|---|---|---|
| fixed_time | 147.5 | ✓ | 104.1 / 148.3 / 159.7 / 130.1 | 233.0 / 507.4 / 456.2 / 419.0 | 105.6 / 149.1 / 172.2 / 136.2 |
| actuated | 99.7 | ✓ | 95.6 / 117.1 / 94.6 / 68.6 | 107.8 / 139.9 / 133.7 / 102.6 | 95.7 / 113.6 / 90.8 / 68.1 |
| max_queue | 100.3 | ✓ | 95.1 / 124.1 / 118.9 / 95.9 | 110.1 / 152.4 / 161.5 / 128.3 | 95.7 / 121.3 / 116.5 / 88.7 |
| max_pressure | 72.4 | ✓ | 70.4 / 68.1 / 47.0 / 32.2 | 74.9 / 74.0 / 57.9 / 39.9 | 72.0 / 68.1 / 45.8 / 31.0 |
| edgeflow | 72.3 | ✓ | 70.1 / 66.9 / 50.4 / 29.4 | 75.1 / 73.6 / 59.8 / 40.2 | 71.6 / 66.6 / 47.9 / 29.0 |
| flow_theory | 73.0 | ✓ | 70.8 / 67.9 / 42.2 / 27.8 | 75.6 / 73.0 / 55.6 / 38.5 | 72.8 / 68.5 / 41.1 / 30.1 |
| fair_cycle_native | 103.4 | ✓ | 103.0 / 141.5 / 91.0 / 71.4 | 101.9 / 138.6 / 106.5 / 78.1 | 105.3 / 142.2 / 94.4 / 74.5 |
| fixed_time + max-red | 108.1 | ✓ | 94.3 / 105.0 / 82.8 / 63.7 | 133.8 / 175.1 / 128.2 / 104.0 | 96.3 / 107.0 / 82.6 / 61.7 |
| actuated + max-red | 101.8 | ✓ | 96.4 / 122.7 / 107.4 / 80.6 | 111.8 / 147.9 / 149.2 / 117.5 | 97.3 / 118.2 / 100.3 / 73.9 |
| max_queue + max-red | 100.1 | ✓ | 94.8 / 122.9 / 119.0 / 93.9 | 110.1 / 153.8 / 158.4 / 130.3 | 95.3 / 119.1 / 111.2 / 87.1 |
| max_pressure + max-red | 72.5 | ✓ | 70.3 / 68.4 / 46.0 / 31.5 | 75.1 / 74.4 / 57.6 / 38.8 | 72.0 / 68.4 / 44.2 / 30.4 |
| edgeflow + max-red | 72.2 | ✓ | 70.1 / 67.0 / 48.8 / 30.5 | 74.8 / 72.5 / 58.3 / 40.5 | 71.6 / 66.6 / 47.9 / 29.0 |
| flow_theory + max-red | 73.1 | ✓ | 71.1 / 68.1 / 41.9 / 28.0 | 75.3 / 71.5 / 52.1 / 35.8 | 72.9 / 68.8 / 41.1 / 30.8 |
| fair_cycle_native + max-red | 103.8 | ✓ | 103.1 / 135.8 / 85.8 / 65.1 | 103.5 / 139.4 / 99.0 / 75.0 | 104.9 / 137.3 / 85.5 / 63.7 |
| phase DQN baseline (it00b config), it00b-17 | 85.5 | ✓ | 82.7 / 87.0 / 62.3 / 51.0 | 88.9 / 90.5 / 74.6 / 50.7 | 84.8 / 86.9 / 62.6 / 49.5 |
| phase DQN baseline (it00b config), base-1604 | 89.0 | ✓ | 85.0 / 81.4 / 58.2 / 38.3 | 95.3 / 104.2 / 100.0 / 71.2 | 86.8 / 81.9 / 61.7 / 40.4 |
| phase DQN baseline (it00b config), base-2026 | 77.6 | ✓ | 76.3 / 82.4 / 65.1 / 59.0 | 78.5 / 82.5 / 73.1 / 56.1 | 78.1 / 80.1 / 66.5 / 60.8 |
| round-3 config C, it32-17 | 73.2 | ✓ | 70.8 / 67.2 / 39.0 / 27.9 | 76.0 / 72.9 / 49.0 / 35.3 | 72.7 / 67.3 / 42.3 / 26.2 |
| round-3 config C, it37-29 | 75.2 | ✓ | 72.9 / 70.1 / 44.4 / 28.9 | 77.4 / 73.2 / 48.4 / 35.0 | 75.2 / 69.4 / 44.7 / 28.5 |
| round-3 config C, it44-41 | 75.0 | ✓ | 72.7 / 69.4 / 42.3 / 27.5 | 78.2 / 74.2 / 52.8 / 38.2 | 74.0 / 68.1 / 42.5 / 29.0 |
| round-3 config C, c-1604 | 74.4 | ✓ | 72.3 / 68.9 / 41.6 / 27.5 | 76.8 / 71.7 / 46.8 / 34.7 | 74.1 / 69.1 / 43.5 / 27.5 |
| round-3 config C, c-2026 | 74.7 | ✓ | 72.6 / 69.3 / 42.7 / 26.4 | 76.9 / 72.1 / 47.5 / 35.5 | 74.6 / 69.0 / 43.7 / 29.3 |

Other metrics, averaged over cases (recovery: bottleneck and reversal cases only, seeds that recovered; censored = runs that never recovered). Collisions / teleports / accounting losses are totals over valid runs; invalid = runs SUMO rejected for a collision or teleport (excluded from every mean).

| Controller | Completion % | Throughput veh/s | Unfinished | Uninserted | Peak backlog veh | Recovery s (censored) | Max service gap s | Clearance node-s | motorcycle delay | car delay | taxi delay | bus delay | truck delay | Coll / tele / acct / invalid | Wall s/run |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| fixed_time | 100.00 | 0.081 | 0.0 | 0.0 | 25 | 382.2 (1) | 42 | 19026 | 143.7 | 151.2 | 149.9 | 177.5 | 162.4 | 0 / 0 / 0 / 0 | 16.2 |
| actuated | 100.00 | 0.081 | 0.0 | 0.0 | 18 | 211.0 (1) | 45 | 6884 | 98.3 | 101.8 | 97.3 | 109.4 | 105.4 | 0 / 0 / 0 / 0 | 16.6 |
| max_queue | 100.00 | 0.082 | 0.0 | 0.0 | 18 | 265.5 (4) | 70 | 4864 | 99.4 | 102.1 | 99.3 | 107.4 | 102.4 | 0 / 0 / 0 / 0 | 16.3 |
| max_pressure | 100.00 | 0.083 | 0.0 | 0.0 | 13 | 188.8 (1) | 30 | 5337 | 71.3 | 74.2 | 75.3 | 75.7 | 77.6 | 0 / 0 / 0 / 0 | 15.3 |
| edgeflow | 100.00 | 0.083 | 0.0 | 0.0 | 13 | 182.6 (3) | 25 | 5675 | 71.3 | 73.6 | 74.6 | 76.7 | 74.9 | 0 / 0 / 0 / 0 | 13.9 |
| flow_theory | 100.00 | 0.083 | 0.0 | 0.0 | 13 | 182.5 (1) | 37 | 5251 | 72.3 | 74.3 | 72.3 | 77.0 | 72.8 | 0 / 0 / 0 / 0 | 11.7 |
| fair_cycle_native | 100.00 | 0.081 | 0.0 | 0.0 | 19 | 208.1 (1) | 59 | 8417 | 102.7 | 104.0 | 104.9 | 106.5 | 107.6 | 0 / 0 / 0 / 0 | 11.3 |
| fixed_time + max-red | 100.00 | 0.082 | 0.0 | 0.0 | 19 | 310.8 (1) | 48 | 18724 | 106.1 | 110.4 | 112.2 | 128.8 | 115.4 | 0 / 0 / 0 / 0 | 15.1 |
| actuated + max-red | 100.00 | 0.081 | 0.0 | 0.0 | 18 | 235.2 (2) | 50 | 6880 | 100.7 | 103.9 | 101.6 | 105.4 | 105.4 | 0 / 0 / 0 / 0 | 15.6 |
| max_queue + max-red | 100.00 | 0.082 | 0.0 | 0.0 | 18 | 269.6 (4) | 66 | 4867 | 98.8 | 102.9 | 100.9 | 105.2 | 101.7 | 0 / 0 / 0 / 0 | 15.2 |
| max_pressure + max-red | 100.00 | 0.083 | 0.0 | 0.0 | 13 | 203.8 (1) | 29 | 5338 | 71.3 | 74.4 | 74.9 | 75.7 | 77.0 | 0 / 0 / 0 / 0 | 11.2 |
| edgeflow + max-red | 100.00 | 0.083 | 0.0 | 0.0 | 13 | 181.7 (3) | 25 | 5669 | 71.2 | 73.7 | 74.3 | 76.9 | 74.1 | 0 / 0 / 0 / 0 | 11.2 |
| flow_theory + max-red | 100.00 | 0.083 | 0.0 | 0.0 | 13 | 183.2 (1) | 36 | 5252 | 72.4 | 74.4 | 72.3 | 77.0 | 73.3 | 0 / 0 / 0 / 0 | 10.3 |
| fair_cycle_native + max-red | 100.00 | 0.081 | 0.0 | 0.0 | 19 | 143.7 (1) | 52 | 8408 | 103.1 | 104.7 | 107.2 | 107.1 | 102.8 | 0 / 0 / 0 / 0 | 9.8 |
| phase DQN baseline (it00b config), it00b-17 | 100.00 | 0.082 | 0.0 | 0.0 | 14 | 187.1 (1) | 55 | 5566 | 83.0 | 88.8 | 89.2 | 104.3 | 94.7 | 0 / 0 / 0 / 0 | 13.4 |
| phase DQN baseline (it00b config), base-1604 | 100.00 | 0.082 | 0.0 | 0.0 | 15 | 214.8 (1) | 53 | 7033 | 87.5 | 91.3 | 89.7 | 101.2 | 90.2 | 0 / 0 / 0 / 0 | 11.0 |
| phase DQN baseline (it00b config), base-2026 | 100.00 | 0.082 | 0.0 | 0.0 | 13 | 172.3 (1) | 59 | 5587 | 76.1 | 79.5 | 76.5 | 87.9 | 84.1 | 0 / 0 / 0 / 0 | 8.0 |
| round-3 config C, it32-17 | 100.00 | 0.082 | 0.0 | 0.0 | 13 | 179.2 (3) | 30 | 5248 | 72.0 | 74.6 | 76.9 | 79.2 | 77.8 | 0 / 0 / 0 / 0 | 15.0 |
| round-3 config C, it37-29 | 100.00 | 0.083 | 0.0 | 0.0 | 13 | 173.8 (2) | 33 | 5174 | 74.0 | 77.1 | 78.2 | 79.5 | 79.7 | 0 / 0 / 0 / 0 | 15.1 |
| round-3 config C, it44-41 | 100.00 | 0.082 | 0.0 | 0.0 | 13 | 169.4 (0) | 30 | 5202 | 73.9 | 76.3 | 77.1 | 77.4 | 82.8 | 0 / 0 / 0 / 0 | 15.3 |
| round-3 config C, c-1604 | 100.00 | 0.082 | 0.0 | 0.0 | 13 | 219.9 (2) | 30 | 5200 | 73.5 | 76.0 | 76.2 | 76.7 | 76.6 | 0 / 0 / 0 / 0 | 15.1 |
| round-3 config C, c-2026 | 100.00 | 0.083 | 0.0 | 0.0 | 13 | 181.4 (2) | 30 | 5202 | 73.7 | 76.1 | 77.9 | 76.3 | 79.9 | 0 / 0 / 0 / 0 | 12.4 |

### Jakarta (`jakarta_menteng_v1`)

Per case: mean delay / p95 wait / worst-approach wait / max approach-p95 wait (s), mean over 20 test seeds.

| Controller | Score | Pass | balanced | directional_reversal | downstream_bottleneck |
|---|---|---|---|---|---|
| fixed_time | 54.7 | ✓ | 16.3 / 28.9 / 51.9 / 34.7 | 130.0 / 343.5 / 423.8 / 394.1 | 17.8 / 28.9 / 51.6 / 35.0 |
| actuated | 33.6 | ✓ | 15.0 / 26.7 / 47.0 / 32.3 | 69.4 / 201.4 / 234.1 / 221.3 | 16.4 / 26.1 / 45.6 / 31.6 |
| max_queue | 31.4 | ✓ | 15.0 / 26.9 / 46.9 / 33.5 | 62.9 / 183.5 / 215.3 / 202.1 | 16.3 / 26.1 / 46.3 / 32.4 |
| max_pressure | 31.5 | ✓ | 15.0 / 26.9 / 46.9 / 33.5 | 63.1 / 183.4 / 215.3 / 202.3 | 16.3 / 26.1 / 46.3 / 32.4 |
| edgeflow | 31.9 | ✓ | 15.0 / 26.9 / 46.9 / 33.5 | 64.4 / 186.2 / 218.0 / 204.2 | 16.4 / 26.2 / 46.3 / 32.3 |
| flow_theory | 18.5 | ✗ | 15.2 / 33.5 / 65.7 / 43.7 | 23.7 / 60.8 / 97.4 / 74.2 | 16.7 / 33.4 / 68.6 / 45.0 |
| fair_cycle_native | 26.3 | ✗ | 19.8 / 43.5 / 63.5 / 47.4 | 37.9 / 77.0 / 102.2 / 87.0 | 21.2 / 43.4 / 62.3 / 46.5 |
| fixed_time + max-red | 28.6 | ✓ | 16.3 / 29.0 / 50.4 / 34.4 | 51.9 / 98.9 / 144.4 / 122.5 | 17.7 / 28.9 / 50.5 / 34.3 |
| actuated + max-red | 24.2 | ✓ | 15.0 / 26.7 / 47.0 / 32.3 | 41.2 / 80.1 / 109.8 / 91.2 | 16.4 / 26.1 / 45.6 / 31.6 |
| max_queue + max-red | 23.8 | ✓ | 15.0 / 26.9 / 46.9 / 33.5 | 40.0 / 78.9 / 105.1 / 89.5 | 16.3 / 26.1 / 46.3 / 32.4 |
| max_pressure + max-red | 23.8 | ✓ | 15.0 / 26.9 / 46.9 / 33.5 | 40.0 / 78.9 / 105.1 / 89.5 | 16.3 / 26.1 / 46.3 / 32.4 |
| edgeflow + max-red | 24.0 | ✓ | 15.0 / 26.9 / 46.9 / 33.5 | 40.7 / 81.2 / 112.3 / 91.4 | 16.4 / 26.2 / 46.3 / 32.3 |
| flow_theory + max-red | 18.7 | ✗ | 15.0 / 32.4 / 55.9 / 40.6 | 24.6 / 56.0 / 77.2 / 64.1 | 16.5 / 32.0 / 55.2 / 40.5 |
| fair_cycle_native + max-red | 26.1 | ✗ | 19.3 / 42.4 / 57.4 / 45.2 | 38.2 / 75.2 / 102.2 / 85.2 | 20.9 / 42.7 / 57.6 / 45.7 |
| phase DQN baseline (it00b config), it00b-17 | 48.1 | ✗ | 18.1 / 46.6 / 85.1 / 63.9 | 106.4 / 336.3 / 405.0 / 378.9 | 19.9 / 48.7 / 85.0 / 65.5 |
| phase DQN baseline (it00b config), base-1604 | 36.2 | ✓ | 14.9 / 26.5 / 50.3 / 32.9 | 77.1 / 225.9 / 265.4 / 249.2 | 16.5 / 26.8 / 50.9 / 34.4 |
| phase DQN baseline (it00b config), base-2026 | 33.6 | ✓ | 15.4 / 27.5 / 50.0 / 34.6 | 68.8 / 210.6 / 248.4 / 234.5 | 16.7 / 26.9 / 47.9 / 33.6 |
| round-3 config C, it32-17 | 23.9 | ✓ | 15.0 / 26.9 / 47.8 / 33.4 | 40.4 / 79.4 / 105.3 / 89.7 | 16.4 / 26.0 / 47.2 / 31.9 |
| round-3 config C, it37-29 | 23.9 | ✓ | 15.0 / 26.8 / 47.6 / 33.4 | 40.3 / 79.4 / 105.3 / 89.7 | 16.4 / 25.9 / 46.8 / 31.8 |
| round-3 config C, it44-41 | 23.9 | ✓ | 15.0 / 26.7 / 47.0 / 33.2 | 40.4 / 79.2 / 105.1 / 89.0 | 16.4 / 26.0 / 46.3 / 31.9 |
| round-3 config C, c-1604 | 23.8 | ✓ | 15.0 / 26.8 / 47.5 / 33.4 | 40.1 / 78.6 / 105.0 / 89.0 | 16.4 / 25.9 / 46.9 / 32.0 |
| round-3 config C, c-2026 | 23.9 | ✓ | 15.0 / 26.8 / 47.5 / 33.4 | 40.3 / 78.8 / 104.7 / 88.8 | 16.4 / 26.1 / 47.3 / 32.0 |

Other metrics, averaged over cases (recovery: bottleneck and reversal cases only, seeds that recovered; censored = runs that never recovered). Collisions / teleports / accounting losses are totals over valid runs; invalid = runs SUMO rejected for a collision or teleport (excluded from every mean).

| Controller | Completion % | Throughput veh/s | Unfinished | Uninserted | Peak backlog veh | Recovery s (censored) | Max service gap s | Clearance node-s | motorcycle delay | car delay | taxi delay | bus delay | truck delay | Coll / tele / acct / invalid | Wall s/run |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| fixed_time | 100.00 | 0.495 | 0.0 | 0.0 | 56 | 187.3 (2) | 25 | 2921 | 54.6 | 54.1 | 57.0 | 56.7 | 56.0 | 0 / 0 / 0 / 0 | 8.1 |
| actuated | 100.00 | 0.499 | 0.0 | 0.0 | 44 | 176.2 (5) | 25 | 2208 | 33.6 | 33.1 | 35.0 | 34.6 | 34.9 | 0 / 0 / 0 / 0 | 8.3 |
| max_queue | 100.00 | 0.498 | 0.0 | 0.0 | 42 | 160.8 (4) | 25 | 1821 | 31.4 | 30.9 | 32.7 | 33.0 | 32.6 | 0 / 0 / 0 / 0 | 8.9 |
| max_pressure | 100.00 | 0.498 | 0.0 | 0.0 | 42 | 160.9 (4) | 25 | 1821 | 31.5 | 30.9 | 32.8 | 33.1 | 32.7 | 0 / 0 / 0 / 0 | 8.3 |
| edgeflow | 100.00 | 0.499 | 0.0 | 0.0 | 42 | 159.6 (4) | 24 | 1921 | 31.9 | 31.5 | 33.2 | 33.4 | 33.2 | 0 / 0 / 0 / 0 | 8.0 |
| flow_theory | 100.00 | 0.498 | 0.0 | 0.0 | 24 | 92.3 (5) | 59 | 1520 | 18.5 | 18.6 | 18.7 | 19.1 | 19.0 | 0 / 0 / 0 / 0 | 9.0 |
| fair_cycle_native | 100.00 | 0.496 | 0.0 | 0.0 | 30 | 95.7 (5) | 54 | 2185 | 26.3 | 26.0 | 26.5 | 28.5 | 26.9 | 0 / 0 / 0 / 1 | 6.8 |
| fixed_time + max-red | 100.00 | 0.497 | 0.0 | 0.0 | 32 | 88.8 (2) | 38 | 2901 | 28.7 | 28.4 | 29.1 | 29.5 | 28.9 | 0 / 0 / 0 / 0 | 7.2 |
| actuated + max-red | 100.00 | 0.498 | 0.0 | 0.0 | 29 | 96.5 (5) | 31 | 2181 | 24.2 | 24.0 | 24.9 | 25.7 | 24.4 | 0 / 0 / 0 / 0 | 7.0 |
| max_queue + max-red | 100.00 | 0.498 | 0.0 | 0.0 | 28 | 100.6 (4) | 31 | 1797 | 23.8 | 23.5 | 24.7 | 25.3 | 23.9 | 0 / 0 / 0 / 0 | 7.1 |
| max_pressure + max-red | 100.00 | 0.498 | 0.0 | 0.0 | 28 | 100.6 (4) | 31 | 1797 | 23.8 | 23.5 | 24.7 | 25.3 | 23.9 | 0 / 0 / 0 / 0 | 7.1 |
| edgeflow + max-red | 100.00 | 0.499 | 0.0 | 0.0 | 28 | 99.9 (4) | 32 | 1899 | 24.0 | 23.8 | 24.9 | 25.8 | 24.2 | 0 / 0 / 0 / 0 | 7.1 |
| flow_theory + max-red | 100.00 | 0.498 | 0.0 | 0.0 | 23 | 94.3 (3) | 48 | 1535 | 18.6 | 18.6 | 18.5 | 19.5 | 19.0 | 0 / 0 / 0 / 0 | 7.1 |
| fair_cycle_native + max-red | 100.00 | 0.495 | 0.0 | 0.0 | 30 | 89.4 (3) | 51 | 2199 | 26.2 | 25.7 | 26.8 | 27.9 | 25.9 | 0 / 0 / 0 / 1 | 6.1 |
| phase DQN baseline (it00b config), it00b-17 | 100.00 | 0.495 | 0.0 | 0.0 | 61 | 314.0 (4) | 31 | 1707 | 47.9 | 47.9 | 49.4 | 49.6 | 50.8 | 0 / 0 / 0 / 0 | 4.2 |
| phase DQN baseline (it00b config), base-1604 | 100.00 | 0.498 | 0.0 | 0.0 | 48 | 199.1 (4) | 30 | 1847 | 36.1 | 35.8 | 37.6 | 37.8 | 38.0 | 0 / 0 / 0 / 0 | 3.3 |
| phase DQN baseline (it00b config), base-2026 | 100.00 | 0.498 | 0.0 | 0.0 | 45 | 171.3 (4) | 29 | 1839 | 33.6 | 33.2 | 34.8 | 35.3 | 35.0 | 0 / 0 / 0 / 0 | 2.1 |
| round-3 config C, it32-17 | 100.00 | 0.498 | 0.0 | 0.0 | 29 | 113.4 (2) | 32 | 1805 | 23.9 | 23.7 | 24.7 | 25.3 | 24.0 | 0 / 0 / 0 / 0 | 4.2 |
| round-3 config C, it37-29 | 100.00 | 0.498 | 0.0 | 0.0 | 29 | 112.1 (2) | 32 | 1804 | 23.8 | 23.7 | 24.7 | 25.2 | 24.0 | 0 / 0 / 0 / 0 | 4.3 |
| round-3 config C, it44-41 | 100.00 | 0.498 | 0.0 | 0.0 | 29 | 112.0 (2) | 32 | 1892 | 23.9 | 23.7 | 24.7 | 25.2 | 24.0 | 0 / 0 / 0 / 0 | 4.3 |
| round-3 config C, c-1604 | 100.00 | 0.498 | 0.0 | 0.0 | 28 | 111.7 (2) | 32 | 1804 | 23.8 | 23.6 | 24.5 | 25.2 | 23.9 | 0 / 0 / 0 / 0 | 4.3 |
| round-3 config C, c-2026 | 100.00 | 0.498 | 0.0 | 0.0 | 29 | 111.6 (2) | 32 | 1804 | 23.9 | 23.7 | 24.6 | 25.2 | 24.0 | 0 / 0 / 0 / 0 | 2.8 |

### Hanoi (`hanoi_dong_da_v1`)

Per case: mean delay / p95 wait / worst-approach wait / max approach-p95 wait (s), mean over 20 test seeds.

| Controller | Score | Pass | balanced | directional_reversal | downstream_bottleneck |
|---|---|---|---|---|---|
| fixed_time | 42.0 | ✓ | 25.4 / 50.6 / 74.1 / 57.5 | 75.3 / 238.6 / 321.6 / 293.6 | 25.4 / 50.6 / 74.1 / 57.5 |
| actuated | 84.7 | ✗ | 59.5 / 267.1 / 398.4 / 350.3 | 135.0 / 769.0 / 892.5 / 864.3 | 59.5 / 267.1 / 398.4 / 350.3 |
| max_queue | 339.4 | ✗ | 299.9 / 1847.8 / 2375.6 / 2287.9 | 418.5 / 2145.8 / 2387.5 / 2347.5 | 299.9 / 1847.8 / 2375.6 / 2287.9 |
| max_pressure | 304.3 | ✗ | 271.9 / 1847.8 / 2375.6 / 2287.9 | 369.2 / 2145.8 / 2387.5 / 2347.5 | 271.9 / 1847.8 / 2375.6 / 2287.9 |
| edgeflow | 77.5 | ✗ | 36.4 / 157.4 / 281.6 / 231.3 | 159.7 / 634.3 / 873.8 / 813.5 | 36.4 / 157.4 / 281.6 / 231.3 |
| flow_theory | 284.2 | ✗ | 261.7 / 1847.8 / 2375.6 / 2287.9 | 329.2 / 2145.8 / 2387.5 / 2347.5 | 261.7 / 1847.8 / 2375.6 / 2287.9 |
| fair_cycle_native | 30.2 | ✗* | 23.2 / 52.0 / 69.9 / 56.9 | 44.3 / 130.7 / 191.2 / 163.9 | 23.2 / 52.0 / 69.9 / 56.9 |
| fixed_time + max-red | 44.7 | ✗ | 25.2 / 49.8 / 65.8 / 50.5 | 83.7 / 263.1 / 336.0 / 290.5 | 25.2 / 49.8 / 65.8 / 50.5 |
| actuated + max-red | 47.5 | ✗* | 31.0 / 79.6 / 120.1 / 87.2 | 80.3 / 260.0 / 328.6 / 297.5 | 31.0 / 79.6 / 120.1 / 87.2 |
| max_queue + max-red | 66.0 | ✗* | 40.5 / 114.0 / 168.7 / 133.9 | 117.0 / 459.9 / 602.8 / 548.4 | 40.5 / 114.0 / 168.7 / 133.9 |
| max_pressure + max-red | 51.2 | ✗ | 31.7 / 98.0 / 160.8 / 128.8 | 90.1 / 386.3 / 522.0 / 479.5 | 31.7 / 98.0 / 160.8 / 128.8 |
| edgeflow + max-red | 57.9 | ✗ | 30.2 / 88.6 / 151.8 / 119.8 | 113.1 / 438.0 / 589.3 / 530.1 | 30.2 / 88.6 / 151.8 / 119.8 |
| flow_theory + max-red | 49.2 | ✗ | 30.1 / 91.6 / 144.2 / 123.2 | 87.4 / 377.0 / 512.9 / 465.7 | 30.1 / 91.6 / 144.2 / 123.2 |
| fair_cycle_native + max-red | 32.4 | ✗ | 23.4 / 56.9 / 80.9 / 65.2 | 50.4 / 151.6 / 223.9 / 199.0 | 23.4 / 56.9 / 80.9 / 65.2 |
| phase DQN baseline (it00b config), it00b-17 | 47.2 | ✗ | 20.9 / 45.6 / 94.0 / 59.5 | 99.7 / 403.7 / 472.2 / 452.1 | 20.9 / 45.6 / 94.0 / 59.5 |
| phase DQN baseline (it00b config), base-1604 | 70.4 | ✗ | 29.0 / 74.2 / 156.1 / 97.8 | 153.2 / 559.9 / 609.6 / 583.8 | 29.0 / 74.2 / 156.1 / 97.8 |
| phase DQN baseline (it00b config), base-2026 | 70.9 | ✗ | 27.3 / 67.5 / 127.1 / 85.4 | 158.0 / 589.4 / 639.7 / 614.9 | 27.3 / 67.5 / 127.1 / 85.4 |
| round-3 config C, it32-17 | 27.9 | ✗ | 18.2 / 46.8 / 86.0 / 65.6 | 47.3 / 168.8 / 217.4 / 194.6 | 18.2 / 46.8 / 86.0 / 65.6 |
| round-3 config C, it37-29 | 29.4 | ✗ | 19.5 / 51.0 / 91.7 / 68.9 | 49.4 / 173.5 / 212.6 / 195.9 | 19.5 / 51.0 / 91.7 / 68.9 |
| round-3 config C, it44-41 | 30.9 | ✗ | 19.9 / 48.3 / 82.9 / 66.4 | 52.7 / 170.2 / 221.9 / 197.1 | 19.9 / 48.3 / 82.9 / 66.4 |
| round-3 config C, c-1604 | 32.5 | ✗* | 22.5 / 64.6 / 110.9 / 89.1 | 52.5 / 198.0 / 258.5 / 232.5 | 22.5 / 64.6 / 110.9 / 89.1 |
| round-3 config C, c-2026 | 28.1 | ✓ | 18.1 / 46.6 / 76.8 / 60.7 | 48.0 / 184.5 / 231.1 / 209.8 | 18.1 / 46.6 / 76.8 / 60.7 |

Other metrics, averaged over cases (recovery: bottleneck and reversal cases only, seeds that recovered; censored = runs that never recovered). Collisions / teleports / accounting losses are totals over valid runs; invalid = runs SUMO rejected for a collision or teleport (excluded from every mean).

| Controller | Completion % | Throughput veh/s | Unfinished | Uninserted | Peak backlog veh | Recovery s (censored) | Max service gap s | Clearance node-s | motorcycle delay | car delay | taxi delay | bus delay | truck delay | Coll / tele / acct / invalid | Wall s/run |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| fixed_time | 100.00 | 0.425 | 0.0 | 0.0 | 39 | 120.2 (7) | 50 | 3297 | 41.8 | 42.4 | 41.2 | 45.7 | 43.1 | 0 / 0 / 0 / 0 | 7.4 |
| actuated | 100.00 | 0.407 | 0.0 | 0.0 | 67 | 246.6 (0) | 239 | 2096 | 84.1 | 85.6 | 81.1 | 96.6 | 84.9 | 0 / 0 / 0 / 0 | 8.5 |
| max_queue | 83.70 | 0.274 | 9.2 | 118.7 | 173 | 86.2 (20) | 2385 | 1807 | 345.5 | 322.4 | 334.0 | 370.9 | 322.8 | 0 / 0 / 0 / 0 | 11.0 |
| max_pressure | 83.72 | 0.274 | 9.1 | 118.6 | 152 | 0.0 (20) | 2385 | 1971 | 310.2 | 287.9 | 303.0 | 328.9 | 286.3 | 0 / 0 / 0 / 0 | 10.6 |
| edgeflow | 100.00 | 0.414 | 0.0 | 0.0 | 67 | 125.3 (2) | 201 | 2026 | 78.0 | 75.5 | 83.6 | 81.2 | 71.4 | 0 / 0 / 0 / 2 | 8.8 |
| flow_theory | 83.72 | 0.274 | 9.1 | 118.6 | 137 | 6.3 (21) | 2386 | 1977 | 290.3 | 266.8 | 284.9 | 307.0 | 267.3 | 0 / 0 / 0 / 0 | 10.9 |
| fair_cycle_native | 100.00 | 0.423 | 0.0 | 0.0 | 34 | 142.6 (2) | 60 | 2673 | 30.0 | 30.5 | 29.7 | 33.1 | 30.1 | 0 / 0 / 0 / 2 | 6.3 |
| fixed_time + max-red | 99.76 | 0.422 | 1.0 | 0.9 | 41 | 106.1 (7) | 103 | 3331 | 44.1 | 44.9 | 45.4 | 50.4 | 48.4 | 0 / 0 / 0 / 0 | 7.2 |
| actuated + max-red | 100.00 | 0.421 | 0.0 | 0.0 | 47 | 96.3 (4) | 128 | 2099 | 47.1 | 47.9 | 47.7 | 52.1 | 47.4 | 0 / 0 / 0 / 2 | 7.1 |
| max_queue + max-red | 100.00 | 0.419 | 0.0 | 0.0 | 63 | 93.2 (5) | 155 | 1496 | 65.7 | 66.8 | 67.4 | 70.9 | 62.6 | 0 / 0 / 0 / 4 | 7.8 |
| max_pressure + max-red | 100.00 | 0.419 | 0.0 | 0.0 | 54 | 58.0 (4) | 134 | 1605 | 51.1 | 50.7 | 53.3 | 57.8 | 49.3 | 0 / 0 / 0 / 2 | 7.4 |
| edgeflow + max-red | 100.00 | 0.422 | 0.0 | 0.0 | 56 | 80.0 (2) | 148 | 1929 | 57.5 | 57.9 | 60.4 | 65.5 | 56.5 | 0 / 0 / 0 / 2 | 7.7 |
| flow_theory + max-red | 100.00 | 0.417 | 0.0 | 0.0 | 52 | 63.6 (3) | 138 | 1565 | 49.2 | 48.5 | 50.5 | 55.1 | 46.8 | 0 / 0 / 0 / 2 | 7.6 |
| fair_cycle_native + max-red | 100.00 | 0.422 | 0.0 | 0.0 | 39 | 81.7 (2) | 86 | 2689 | 32.2 | 32.5 | 32.8 | 38.5 | 32.3 | 0 / 0 / 0 / 0 | 6.1 |
| phase DQN baseline (it00b config), it00b-17 | 100.00 | 0.425 | 0.0 | 0.0 | 43 | 105.8 (6) | 106 | 5198 | 46.6 | 47.9 | 47.6 | 53.8 | 49.1 | 0 / 0 / 0 / 0 | 4.3 |
| phase DQN baseline (it00b config), base-1604 | 100.00 | 0.412 | 0.0 | 0.0 | 54 | 188.1 (6) | 141 | 5603 | 69.5 | 70.8 | 72.7 | 79.6 | 76.0 | 0 / 0 / 0 / 0 | 3.6 |
| phase DQN baseline (it00b config), base-2026 | 100.00 | 0.412 | 0.0 | 0.0 | 54 | 213.3 (3) | 123 | 5540 | 70.1 | 70.9 | 74.0 | 79.3 | 76.9 | 0 / 0 / 0 / 0 | 2.3 |
| round-3 config C, it32-17 | 100.00 | 0.424 | 0.0 | 0.0 | 35 | 87.5 (4) | 98 | 1987 | 27.7 | 28.1 | 28.5 | 30.7 | 27.1 | 0 / 0 / 0 / 0 | 4.4 |
| round-3 config C, it37-29 | 99.93 | 0.422 | 0.5 | 0.0 | 36 | 114.6 (6) | 99 | 1831 | 29.1 | 29.7 | 30.6 | 33.5 | 30.1 | 0 / 0 / 0 / 0 | 4.5 |
| round-3 config C, it44-41 | 100.00 | 0.425 | 0.0 | 0.0 | 35 | 93.0 (6) | 96 | 4226 | 30.5 | 31.1 | 31.4 | 36.2 | 31.0 | 0 / 0 / 0 / 0 | 4.4 |
| round-3 config C, c-1604 | 100.00 | 0.422 | 0.0 | 0.0 | 39 | 106.2 (2) | 114 | 1969 | 32.3 | 32.2 | 32.7 | 37.6 | 33.1 | 0 / 0 / 0 / 4 | 4.5 |
| round-3 config C, c-2026 | 100.00 | 0.425 | 0.0 | 0.0 | 35 | 120.2 (4) | 87 | 1849 | 28.0 | 28.0 | 27.8 | 32.1 | 28.0 | 0 / 0 / 0 / 0 | 3.0 |

### 4-node (`four_intersection_rl_v1`)

Per case: mean delay / p95 wait / worst-approach wait / max approach-p95 wait (s), mean over 20 test seeds.

| Controller | Score | Pass | balanced | directional_surge | directional_surge_ew | downstream_bottleneck | sparse | near_capacity | oversaturated | directional_reversal |
|---|---|---|---|---|---|---|---|---|---|---|
| fixed_time | 76.5 | ✓ | 37.0 / 45.0 / 42.7 / 36.2 | 35.0 / 43.4 / 43.3 / 36.0 | 35.0 / 43.0 / 40.6 / 36.1 | 66.5 / 198.4 / 266.6 / 240.7 | 26.8 / 36.0 / 38.8 / 35.7 | 44.6 / 53.0 / 57.0 / 38.0 | 234.1 / 417.6 / 526.1 / 485.8 | 133.2 / 245.1 / 311.4 / 282.1 |
| actuated | 69.4 | ✓ | 39.3 / 42.3 / 46.8 / 31.1 | 25.2 / 27.6 / 33.2 / 21.5 | 25.1 / 27.0 / 34.2 / 21.9 | 75.6 / 131.7 / 201.2 / 175.5 | 22.4 / 24.4 / 24.1 / 16.9 | 57.9 / 56.3 / 57.5 / 40.9 | 247.0 / 429.6 / 514.5 / 483.2 | 62.7 / 76.4 / 104.5 / 81.6 |
| max_queue | 121.6 | ✗ | 40.6 / 45.9 / 50.3 / 38.1 | 24.9 / 27.8 / 34.4 / 21.8 | 24.3 / 27.0 / 34.4 / 21.9 | 115.4 / 239.1 / 285.9 / 265.4 | 22.2 / 24.3 / 22.9 / 16.8 | 87.3 / 109.2 / 142.0 / 122.0 | 572.4 / 907.2 / 1019.2 / 994.5 | 85.6 / 133.0 / 169.0 / 150.3 |
| max_pressure | 119.5 | ✗ | 36.9 / 43.1 / 51.0 / 36.6 | 25.3 / 30.1 / 39.6 / 24.8 | 25.4 / 30.2 / 41.5 / 24.8 | 111.8 / 249.4 / 299.8 / 278.8 | 21.4 / 26.4 / 35.1 / 21.4 | 81.8 / 98.6 / 135.6 / 113.2 | 566.3 / 901.1 / 1001.9 / 976.9 | 86.8 / 145.3 / 195.0 / 173.2 |
| edgeflow | 120.4 | ✗ | 37.9 / 43.5 / 49.9 / 35.9 | 23.5 / 26.6 / 32.4 / 20.2 | 23.6 / 26.8 / 32.5 / 20.4 | 109.7 / 242.2 / 287.5 / 269.4 | 22.0 / 25.0 / 26.2 / 18.0 | 82.2 / 99.8 / 138.6 / 118.0 | 566.8 / 903.0 / 1000.4 / 976.5 | 97.8 / 165.8 / 212.3 / 191.2 |
| flow_theory | 74.4 | ✗ | 31.1 / 37.4 / 47.0 / 30.5 | 21.8 / 33.6 / 57.8 / 39.7 | 21.6 / 34.0 / 57.5 / 41.6 | 59.2 / 139.9 / 205.2 / 182.2 | 23.1 / 30.0 / 35.6 / 23.4 | 39.2 / 44.5 / 56.9 / 38.5 | 360.4 / 701.5 / 806.9 / 779.7 | 38.6 / 58.7 / 109.3 / 60.9 |
| fair_cycle | 88.3 | ✗ | 52.3 / 91.8 / 92.9 / 72.1 | 25.9 / 44.8 / 48.1 / 46.7 | 49.7 / 73.4 / 74.0 / 47.7 | 81.2 / 152.5 / 181.0 / 158.7 | 33.3 / 59.8 / 48.4 / 45.9 | 77.9 / 139.0 / 146.1 / 120.5 | 303.8 / 536.1 / 622.1 / 581.8 | 82.2 / 134.9 / 171.8 / 156.3 |
| fair_cycle_native | 81.1 | ✗ | 47.1 / 71.7 / 71.1 / 47.6 | 34.5 / 67.2 / 64.2 / 53.5 | 38.0 / 69.9 / 61.4 / 51.1 | 73.7 / 141.0 / 198.4 / 177.8 | 40.8 / 79.1 / 62.3 / 52.2 | 53.2 / 70.9 / 71.5 / 46.3 | 295.5 / 524.3 / 598.3 / 565.1 | 66.4 / 88.6 / 112.4 / 92.5 |
| fixed_time + max-red | 110.1 | ✗ | 37.0 / 45.0 / 42.4 / 36.2 | 35.0 / 43.2 / 41.8 / 36.0 | 35.0 / 43.0 / 40.3 / 36.1 | 110.8 / 220.7 / 265.4 / 227.8 | 26.8 / 36.0 / 38.8 / 35.7 | 44.7 / 53.2 / 51.1 / 37.8 | 490.1 / 872.1 / 955.8 / 914.0 | 101.4 / 141.8 / 176.4 / 155.2 |
| actuated + max-red | 104.7 | ✗ | 39.3 / 42.3 / 46.0 / 31.1 | 25.2 / 27.6 / 33.2 / 21.5 | 25.1 / 27.0 / 34.2 / 21.9 | 122.6 / 234.0 / 283.3 / 250.3 | 22.4 / 24.4 / 24.1 / 16.9 | 58.9 / 58.3 / 58.4 / 44.9 | 472.3 / 812.5 / 894.9 / 848.8 | 71.6 / 97.1 / 126.4 / 109.6 |
| max_queue + max-red | 114.3 | ✗ | 40.6 / 45.9 / 50.3 / 38.1 | 24.9 / 27.8 / 34.4 / 21.8 | 24.3 / 27.0 / 34.4 / 21.9 | 145.7 / 268.5 / 316.8 / 278.6 | 22.2 / 24.3 / 22.9 / 16.8 | 89.2 / 108.2 / 135.2 / 109.7 | 485.4 / 837.9 / 911.0 / 868.3 | 82.2 / 115.3 / 145.4 / 127.7 |
| max_pressure + max-red | 112.4 | ✗ | 36.9 / 43.2 / 50.5 / 36.9 | 25.3 / 30.1 / 39.3 / 25.0 | 25.4 / 30.2 / 40.8 / 24.8 | 145.1 / 276.3 / 322.6 / 288.2 | 21.5 / 26.4 / 34.3 / 21.6 | 82.8 / 95.3 / 120.4 / 97.4 | 479.8 / 826.2 / 908.9 / 863.7 | 82.3 / 116.9 / 147.1 / 128.8 |
| edgeflow + max-red | 112.9 | ✗ | 38.0 / 43.6 / 49.6 / 36.1 | 23.5 / 26.6 / 32.4 / 20.2 | 23.6 / 26.8 / 32.5 / 20.4 | 141.3 / 270.3 / 321.7 / 285.4 | 22.0 / 25.0 / 26.2 / 18.0 | 83.0 / 96.4 / 126.8 / 101.5 | 484.5 / 830.0 / 911.9 / 868.5 | 87.4 / 126.0 / 164.6 / 141.6 |
| flow_theory + max-red | 95.7 | ✗ | 31.0 / 37.3 / 46.0 / 30.6 | 21.9 / 34.8 / 49.6 / 40.4 | 21.6 / 34.4 / 49.4 / 41.2 | 100.4 / 205.8 / 246.7 / 219.2 | 23.1 / 30.0 / 35.6 / 23.4 | 39.6 / 45.1 / 52.1 / 38.7 | 483.1 / 839.7 / 920.6 / 881.0 | 44.8 / 66.1 / 77.1 / 63.4 |
| fair_cycle + max-red | 109.0 | ✗ | 45.8 / 75.5 / 53.4 / 46.9 | 25.9 / 44.8 / 48.1 / 46.7 | 48.2 / 70.7 / 52.7 / 45.4 | 107.9 / 204.4 / 243.4 / 212.0 | 33.3 / 59.8 / 48.4 / 45.9 | 57.7 / 80.3 / 65.0 / 53.1 | 476.0 / 835.3 / 912.3 / 865.3 | 76.8 / 114.0 / 145.0 / 124.6 |
| fair_cycle_native + max-red | 106.8 | ✗ | 44.8 / 66.0 / 57.8 / 45.6 | 32.9 / 62.0 / 53.8 / 49.4 | 36.5 / 64.6 / 55.2 / 49.7 | 114.3 / 219.1 / 271.2 / 234.2 | 37.3 / 71.3 / 54.1 / 48.1 | 50.5 / 65.3 / 57.3 / 45.4 | 470.5 / 826.3 / 904.3 / 863.4 | 67.4 / 91.6 / 110.5 / 95.5 |
| phase DQN baseline (it00b config), it00b-17 | 104.1 | ✗ | 40.4 / 45.1 / 49.5 / 35.9 | 36.6 / 39.9 / 42.2 / 29.6 | 36.4 / 39.5 / 42.5 / 30.2 | 109.0 / 272.4 / 331.2 / 308.3 | 26.1 / 25.9 / 25.0 / 17.0 | 79.3 / 97.5 / 136.6 / 111.8 | 373.9 / 671.2 / 784.5 / 757.9 | 130.8 / 237.2 / 282.8 / 264.0 |
| phase DQN baseline (it00b config), base-1604 | 96.1 | ✗ | 40.7 / 44.9 / 46.8 / 34.6 | 37.0 / 40.3 / 41.6 / 29.5 | 36.9 / 39.8 / 41.3 / 29.2 | 105.2 / 257.7 / 309.8 / 288.6 | 26.6 / 24.7 / 24.1 / 16.9 | 76.1 / 88.3 / 107.7 / 89.0 | 346.4 / 614.0 / 714.6 / 689.6 | 99.7 / 158.2 / 193.6 / 179.7 |
| phase DQN baseline (it00b config), base-2026 | 102.1 | ✗ | 41.0 / 45.4 / 48.7 / 35.4 | 36.9 / 40.6 / 41.5 / 29.9 | 37.0 / 40.1 / 41.4 / 29.3 | 107.8 / 268.4 / 319.5 / 300.1 | 26.5 / 24.8 / 24.1 / 16.9 | 79.4 / 97.0 / 127.4 / 106.2 | 377.3 / 697.6 / 792.3 / 767.9 | 111.0 / 184.8 / 221.3 / 204.9 |
| round-3 config C, it32-17 | 121.0 | ✗ | 41.0 / 45.6 / 48.5 / 36.6 | 36.0 / 40.4 / 40.6 / 28.9 | 36.0 / 39.7 / 42.6 / 29.3 | 151.4 / 291.9 / 341.2 / 306.5 | 24.2 / 26.0 / 24.8 / 17.0 | 87.1 / 104.8 / 125.5 / 102.5 | 490.5 / 837.2 / 911.5 / 870.3 | 101.6 / 140.1 / 177.3 / 158.6 |
| round-3 config C, it37-29 | 121.1 | ✗ | 40.7 / 45.8 / 48.9 / 37.2 | 36.0 / 40.1 / 40.5 / 28.6 | 35.5 / 39.3 / 41.0 / 29.1 | 151.5 / 282.6 / 332.8 / 295.6 | 22.9 / 25.8 / 23.7 / 17.0 | 87.0 / 102.9 / 126.9 / 100.7 | 490.8 / 837.5 / 915.8 / 869.1 | 104.5 / 144.5 / 183.1 / 162.1 |
| round-3 config C, it44-41 | 121.0 | ✗ | 40.7 / 46.1 / 50.7 / 38.4 | 35.1 / 40.4 / 40.1 / 29.3 | 34.7 / 39.3 / 40.6 / 28.8 | 153.3 / 289.3 / 330.7 / 297.1 | 22.1 / 25.1 / 22.9 / 16.8 | 88.3 / 106.6 / 135.4 / 109.0 | 487.0 / 833.0 / 911.9 / 868.8 | 106.7 / 149.5 / 189.3 / 166.3 |
| round-3 config C, c-1604 | 120.9 | ✗ | 40.5 / 45.6 / 48.2 / 36.2 | 35.8 / 41.4 / 40.9 / 29.1 | 35.2 / 40.1 / 40.0 / 29.4 | 151.7 / 288.0 / 328.0 / 298.2 | 22.7 / 25.4 / 23.7 / 16.9 | 87.6 / 103.6 / 128.4 / 104.0 | 491.0 / 838.5 / 914.9 / 869.7 | 102.7 / 139.3 / 177.0 / 157.0 |
| round-3 config C, c-2026 | 122.4 | ✗ | 40.2 / 45.2 / 48.0 / 36.1 | 34.0 / 39.1 / 40.5 / 28.8 | 33.8 / 39.5 / 41.0 / 29.2 | 155.5 / 299.3 / 343.5 / 304.7 | 22.8 / 25.7 / 24.3 / 17.4 | 86.7 / 102.4 / 129.4 / 103.7 | 501.7 / 860.5 / 939.7 / 897.1 | 104.3 / 145.1 / 184.2 / 163.6 |

Other metrics, averaged over cases (recovery: bottleneck and reversal cases only, seeds that recovered; censored = runs that never recovered). Collisions / teleports / accounting losses are totals over valid runs; invalid = runs SUMO rejected for a collision or teleport (excluded from every mean).

| Controller | Completion % | Throughput veh/s | Unfinished | Uninserted | Peak backlog veh | Recovery s (censored) | Max service gap s | Clearance node-s | motorcycle delay | car delay | taxi delay | bus delay | truck delay | Coll / tele / acct / invalid | Wall s/run |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| fixed_time | 99.97 | 0.906 | 1.0 | 0.0 | 160 | 352.6 (0) | 35 | 1112 | — | 76.5 | — | — | — | 0 / 0 / 0 / 0 | 9.7 |
| actuated | 99.98 | 0.912 | 0.9 | 0.0 | 133 | 279.4 (0) | 29 | 1887 | — | 69.4 | — | — | — | 0 / 0 / 0 / 0 | 9.7 |
| max_queue | 97.10 | 0.848 | 33.2 | 76.3 | 245 | 384.4 (0) | 24 | 2180 | — | 121.6 | — | — | — | 0 / 0 / 0 / 0 | 8.7 |
| max_pressure | 97.15 | 0.847 | 33.0 | 74.7 | 242 | 397.9 (0) | 32 | 2205 | — | 119.5 | — | — | — | 0 / 0 / 0 / 0 | 6.7 |
| edgeflow | 97.14 | 0.850 | 33.0 | 74.8 | 245 | 395.6 (0) | 27 | 2156 | — | 120.4 | — | — | — | 0 / 0 / 0 / 0 | 5.9 |
| flow_theory | 99.28 | 0.902 | 17.8 | 9.4 | 159 | 330.8 (1) | 50 | 1396 | — | 74.4 | — | — | — | 0 / 0 / 0 / 0 | 4.7 |
| fair_cycle | 99.67 | 0.891 | 11.3 | 1.2 | 184 | 385.4 (0) | 45 | 1128 | — | 88.3 | — | — | — | 0 / 0 / 0 / 0 | 4.7 |
| fair_cycle_native | 99.74 | 0.900 | 9.4 | 0.3 | 164 | 294.9 (0) | 53 | 1124 | — | 81.1 | — | — | — | 0 / 0 / 0 / 0 | 4.2 |
| fixed_time + max-red | 97.49 | 0.858 | 34.5 | 60.1 | 243 | 398.1 (0) | 46 | 1176 | — | 110.1 | — | — | — | 0 / 0 / 0 / 0 | 9.6 |
| actuated + max-red | 97.94 | 0.866 | 33.6 | 43.9 | 223 | 407.1 (0) | 37 | 1918 | — | 104.7 | — | — | — | 0 / 0 / 0 / 0 | 9.3 |
| max_queue + max-red | 97.78 | 0.855 | 35.9 | 47.7 | 238 | 414.2 (0) | 38 | 1933 | — | 114.3 | — | — | — | 0 / 0 / 0 / 0 | 6.0 |
| max_pressure + max-red | 97.85 | 0.856 | 34.2 | 46.3 | 232 | 423.9 (0) | 45 | 1950 | — | 112.4 | — | — | — | 0 / 0 / 0 / 0 | 5.8 |
| edgeflow + max-red | 97.84 | 0.858 | 34.5 | 46.7 | 236 | 415.8 (0) | 41 | 1897 | — | 112.9 | — | — | — | 0 / 0 / 0 / 0 | 5.0 |
| flow_theory + max-red | 97.77 | 0.868 | 34.1 | 50.1 | 214 | 404.1 (0) | 48 | 1371 | — | 95.7 | — | — | — | 0 / 0 / 0 / 0 | 4.0 |
| fair_cycle + max-red | 97.79 | 0.859 | 33.1 | 49.9 | 234 | 407.5 (0) | 52 | 1207 | — | 109.0 | — | — | — | 0 / 0 / 0 / 0 | 3.4 |
| fair_cycle_native + max-red | 97.86 | 0.861 | 33.8 | 46.9 | 229 | 384.9 (0) | 53 | 1179 | — | 106.8 | — | — | — | 0 / 0 / 0 / 0 | 3.0 |
| phase DQN baseline (it00b config), it00b-17 | 99.17 | 0.875 | 18.5 | 12.8 | 199 | 423.9 (0) | 26 | 2395 | — | 104.1 | — | — | — | 0 / 0 / 0 / 0 | 5.4 |
| phase DQN baseline (it00b config), base-1604 | 99.44 | 0.881 | 16.4 | 4.9 | 182 | 392.5 (0) | 26 | 2387 | — | 96.1 | — | — | — | 0 / 0 / 0 / 0 | 5.2 |
| phase DQN baseline (it00b config), base-2026 | 99.12 | 0.875 | 19.8 | 13.2 | 195 | 400.6 (0) | 25 | 2405 | — | 102.1 | — | — | — | 0 / 0 / 0 / 0 | 5.0 |
| round-3 config C, it32-17 | 97.74 | 0.848 | 35.1 | 49.1 | 245 | 412.1 (1) | 38 | 2295 | — | 121.0 | — | — | — | 0 / 0 / 0 / 0 | 6.0 |
| round-3 config C, it37-29 | 97.74 | 0.848 | 34.6 | 50.3 | 244 | 416.0 (0) | 38 | 2286 | — | 121.1 | — | — | — | 0 / 0 / 0 / 0 | 6.0 |
| round-3 config C, it44-41 | 97.77 | 0.848 | 34.9 | 48.4 | 242 | 410.5 (1) | 38 | 2291 | — | 121.0 | — | — | — | 0 / 0 / 0 / 0 | 6.0 |
| round-3 config C, c-1604 | 97.72 | 0.849 | 35.9 | 49.4 | 243 | 407.7 (1) | 38 | 2289 | — | 120.9 | — | — | — | 0 / 0 / 0 / 0 | 6.0 |
| round-3 config C, c-2026 | 97.57 | 0.848 | 34.9 | 55.9 | 250 | 426.1 (0) | 38 | 2231 | — | 122.4 | — | — | — | 0 / 0 / 0 / 0 | 6.0 |
