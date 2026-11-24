# RL Research Loop — Round 2 Report (2026-11-24)

- **Branch:** `research/rl-benchmark-suite`. Driver, ledger and scripts are in [`../research/rl_loop/`](../research/rl_loop/). Round 1 is [`RL_RESEARCH_LOOP_REPORT_20261124.md`](RL_RESEARCH_LOOP_REPORT_20261124.md).
- **Protocol:** unchanged from round 1. Phase DQN, loop recipe v2, all six maps in parallel, 40 min cap, validation seeds 70001–70005 only. **The test seeds were never opened.**
- **Fair targets:** for each map, the best passing deterministic controller, with or without the same max-red envelope the learner runs inside (`rl_loop/targets.json`). The envelope is T = 40 s and counts waits outside the map.

## 1. Summary

1. **Confirmed WINs on 2 maps.** One configuration passes the guardrail and beats the fair target on both learner seeds (17 and 29) on two maps:

   | Map | Seed 17 (it14) | Seed 29 (it18) | Target |
   |---|---|---|---|
   | **Hanoi** | 31.2 | 29.0 | 33.6 (fair_cycle_native + max-red) |
   | **cologne** | 34.3 | 33.5 | 34.5 (flow_theory + max-red) |

   - **The configuration:** a DQN residual on flow_theory, using the base gates plus `EDGEFLOW_RESIDUAL_BASE=flow_theory EDGEFLOW_MP_MARGIN=0.20`. The learner follows flow_theory's phase unless its own best legal Q-value is more than 20 % higher.
   - **The Hanoi margin is real:** 2.4–4.6 s.
   - **The cologne margin is not:** 0.2–1.0 s is below the 3 s single-seed noise floor. Its tails do improve clearly, with worst-approach wait 30–44 s against 39–54 s for flow_theory (§3).
2. **Hanoi also wins with a max_pressure base.** The same residual on max_pressure at δ = 0.10 (it11 and it17) gives 29.9 and 29.1. **Two different bases win Hanoi on both seeds.**
3. **No win on HCM, grid4x4, Jakarta or 4-node.**
   - **HCM:** 72.0 and 72.4 against 72.0, a tie.
   - **grid4x4:** the best learned score is 20.6 on both seeds (max_pressure base, δ 0.10), against 20.1. flow_theory is a poor base there (23–24).
   - **Jakarta:** at δ 0.20 on flow_theory, the delay beats the target (22.8–23.1 vs 23.3), but tails fail on both seeds. At δ 0.10 it passes but scores 23.8–24.5.
   - **4-node:** still fails the guardrail. The oversaturated case completes only 87 % of vehicles.
4. **Mechanism.** The wins come from a residual: a strong hand-written base plus learned exceptions. Pure DQN does not produce them. The override rate is about 2 % on cologne and about 35 % on Jakarta. Where the base already ties the target (HCM, grid4x4), a few overrides do not open a gap.

## 2. Ledger (round 2)

Scores are in seconds, lower is better. ✗ means no checkpoint passed the guardrail. Verdicts use the README rules (≥ 3 s gain or sign test, and no map may lose feasibility).

| It | Seed | Hypothesis | cologne | grid4x4 | HCM | Jakarta | Hanoi | 4-node | Verdict |
|---|---|---|---|---|---|---|---|---|---|
| target | | best deterministic ± max-red | 34.5 | 20.1 | 72.0 | 23.3 | 33.6 | 68.7 | |
| it08 | 17 | max_pressure residual δ 0.02 | 36.3 | 21.7 | 77.8 | 25.1 | 32.7 | ✗ | KEEP |
| it09 | 17 | δ 0.05 | 35.8 | 21.0 | 75.1 | 24.7 | 31.6 | ✗ | KEEP (sign test) |
| it10 | 17 | + residual-policy bootstrap target | 35.5 | 21.7 | 75.3 | 25.2 | 38.5 | ✗ | DISCARD (reverted) |
| it11 | 17 | δ 0.10 | 34.8 | 20.6 | 73.8 | 24.9 | **29.9** | ✗ | DISCARD (Jakarta +0.2) |
| it12 | 17 | δ 0.20 | 34.7 | 20.2 | 73.3 | 24.0 | ✗ | ✗ | DISCARD |
| it13 | 17 | flow_theory residual δ 0.10 | **33.9** | 22.5 | 73.7 | 24.5 | **31.4** | ✗ | DISCARD (grid) |
| it14 | 17 | flow_theory residual δ 0.20 | **34.3** | 23.3 | 72.0 | ✗ | **31.2** | ✗ | DISCARD (Jakarta ✗) |
| it15 | 17 | fair_cycle_native residual δ 0.10 | 37.3 | 25.5 | 80.0 | 24.8 | **32.4** | ✗ | DISCARD |
| it16 | 29 | confirm it13 | 34.5 | 22.9 | 74.4 | 23.8 | ✗ | ✗ | not confirmed |
| it17 | 29 | confirm it11 | 34.7 | 20.6 | 75.1 | 24.3 | **29.1** | ✗ | Hanoi confirmed |
| it18 | 29 | confirm it14 | **33.5** | 23.9 | 72.4 | ✗ | **29.0** | ✗ | cologne + Hanoi confirmed → stop |

**Bold** marks a score below the target. The stop rule ("confirmed WIN on 2 or more maps") was met at it18, so it19 was not used.

**Code added (all env-gated, default off, no contract changes):**
- `EDGEFLOW_MP_MARGIN` (residual action selection).
- `EDGEFLOW_RESIDUAL_BASE` (any factory controller as the residual base; sim time is passed through).
- `EDGEFLOW_RESIDUAL_TARGET`, tried in it10, then reverted.

## 3. Per-case metrics: the winning configuration (flow_theory residual, δ 0.20)

Cells show delay / p95 wait / worst-approach wait, each the mean over 5 validation seeds. Learned rows are the selected checkpoint. When no checkpoint passed, they are the final checkpoint, and their score is the best failing score. Every run in these tables completed with 0 collisions and 0 teleports. The only shortfall is 4-node's oversaturated case, which completed 3278 of 3782 vehicles (87 %).


**cologne8_benchmark_v1**

| Controller | Score | Pass | balanced | directional_reversal | downstream_bottleneck |
|---|---|---|---|---|---|
| learned, seed 17 (selected ep 100) | 34.3 | ✓ | 29.4 / 29.1 / 30.2 | 35.7 / 36.9 / 44.6 | 37.6 / 29.3 / 29.5 |
| learned, seed 29 (selected ep 280) | 33.5 | ✓ | 29.0 / 29.3 / 37.2 | 33.6 / 34.8 / 42.4 | 38.4 / 29.3 / 37.4 |
| best deterministic: flow_theory | 34.5 | ✓ | 30.7 / 33.7 / 41.2 | 33.2 / 38.5 / 54.5 | 39.7 / 34.0 / 39.2 |
| best deterministic + max-red: flow_theory | 34.5 | ✓ | 30.7 / 33.7 / 41.2 | 33.0 / 38.3 / 50.0 | 39.7 / 34.0 / 39.2 |

**four_intersection_rl_v1**

| Controller | Score | Pass | balanced | directional_surge | directional_surge_ew | downstream_bottleneck | sparse | near_capacity | oversaturated | directional_reversal |
|---|---|---|---|---|---|---|---|---|---|---|
| learned, seed 17 (final checkpoint (no feasible checkpoint)) | 106.5 | ✗ | 37.9 / 39.5 / 45.0 | 36.1 / 38.5 / 40.6 | 37.4 / 41.0 / 40.1 | 157.5 / 358.2 / 427.7 | 26.3 / 25.9 / 23.8 | 82.3 / 86.6 / 96.1 | 442.8 / 762.5 / 834.4 | 94.1 / 120.0 / 144.3 |
| learned, seed 29 (final checkpoint (no feasible checkpoint)) | 106.3 | ✗ | 39.8 / 43.2 / 46.2 | 34.2 / 37.8 / 38.8 | 34.7 / 37.7 / 41.2 | 159.9 / 356.4 / 430.8 | 24.1 / 26.6 / 22.8 | 82.6 / 86.3 / 100.8 | 438.1 / 746.9 / 817.2 | 98.4 / 126.1 / 155.3 |
| best deterministic: actuated | 68.7 | ✓ | 37.3 / 39.2 / 41.3 | 24.2 / 26.8 / 32.2 | 25.1 / 27.5 / 33.3 | 77.9 / 162.4 / 192.7 | 22.1 / 24.1 / 21.7 | 56.5 / 55.0 / 55.4 | 246.0 / 415.2 / 483.1 | 60.8 / 69.3 / 103.1 |
| best deterministic + max-red: fixed_time | 76.6 | ✓ | 36.2 / 44.1 / 39.8 | 34.2 / 42.1 / 38.8 | 34.4 / 43.5 / 43.4 | 68.7 / 224.9 / 275.8 | 27.1 / 35.8 / 38.4 | 44.5 / 53.1 / 53.4 | 236.3 / 404.9 / 482.1 | 131.4 / 233.8 / 293.5 |

**grid4x4_benchmark_v1**

| Controller | Score | Pass | balanced | directional_reversal | downstream_bottleneck |
|---|---|---|---|---|---|
| learned, seed 17 (selected ep 120) | 23.3 | ✓ | 22.5 / 44.4 / 89.4 | 23.6 / 45.7 / 91.0 | 23.6 / 43.3 / 85.4 |
| learned, seed 29 (selected ep 80) | 23.9 | ✓ | 22.9 / 46.7 / 119.9 | 24.8 / 51.3 / 114.3 | 24.3 / 46.9 / 129.1 |
| best deterministic: max_pressure | 20.1 | ✓ | 19.3 / 29.4 / 89.3 | 20.3 / 31.6 / 103.7 | 20.6 / 29.3 / 84.8 |
| best deterministic + max-red: max_pressure | 20.7 | ✓ | 19.9 / 31.1 / 115.1 | 21.2 / 34.2 / 117.6 | 21.0 / 30.2 / 110.1 |

**hanoi_dong_da_v1**

| Controller | Score | Pass | balanced | directional_reversal | downstream_bottleneck |
|---|---|---|---|---|---|
| learned, seed 17 (selected ep 280) | 31.2 | ✓ | 19.2 / 46.1 / 77.4 | 55.3 / 219.9 / 268.7 | 19.2 / 46.1 / 77.4 |
| learned, seed 29 (selected ep 300) | 29.0 | ✓ | 18.5 / 48.8 / 81.6 | 51.6 / 183.4 / 237.4 | 18.5 / 48.2 / 86.0 |
| best deterministic: fixed_time | 43.9 | ✓ | 26.2 / 52.0 / 84.3 | 79.2 / 257.1 / 366.2 | 26.2 / 52.0 / 84.3 |
| best deterministic + max-red: fair_cycle_native | 33.6 | ✓ | 22.4 / 49.9 / 68.8 | 55.9 / 171.4 / 225.9 | 22.4 / 49.9 / 68.8 |

**hcm_neighborhood_v3_benchmark_v1**

| Controller | Score | Pass | balanced | directional_reversal | downstream_bottleneck |
|---|---|---|---|---|---|
| learned, seed 17 (selected ep 300) | 72.0 | ✓ | 70.8 / 67.9 / 37.6 | 73.7 / 68.8 / 50.7 | 72.1 / 67.5 / 40.1 |
| learned, seed 29 (selected ep 240) | 72.4 | ✓ | 69.3 / 67.3 / 39.2 | 76.3 / 74.3 / 60.4 | 71.6 / 67.2 / 38.0 |
| best deterministic: max_pressure | 72.0 | ✓ | 70.6 / 69.4 / 47.6 | 74.5 / 76.6 / 84.6 | 71.0 / 66.2 / 41.6 |
| best deterministic + max-red: max_pressure | 72.2 | ✓ | 70.5 / 69.4 / 47.6 | 74.9 / 79.3 / 81.4 | 71.0 / 66.2 / 41.6 |

**jakarta_menteng_v1**

| Controller | Score | Pass | balanced | directional_reversal | downstream_bottleneck |
|---|---|---|---|---|---|
| learned, seed 17 (final checkpoint (no feasible checkpoint)) | 23.1 | ✗ | 15.8 / 34.7 / 57.4 | 36.4 / 74.9 / 98.8 | 17.1 / 34.4 / 59.8 |
| learned, seed 29 (final checkpoint (no feasible checkpoint)) | 22.8 | ✗ | 15.9 / 32.4 / 57.2 | 39.3 / 79.2 / 108.2 | 17.2 / 32.9 / 57.2 |
| best deterministic: max_pressure | 32.2 | ✓ | 15.1 / 27.0 / 46.1 | 65.4 / 197.2 / 224.5 | 16.2 / 26.4 / 49.8 |
| best deterministic + max-red: max_queue | 23.3 | ✓ | 15.1 / 27.0 / 46.1 | 38.8 / 76.5 / 101.5 | 16.2 / 26.4 / 49.8 |

## 4. Reading the tables

- **Hanoi.** The win is in delay on every case: 18.5–19.2 s against 22.4 for native + max-red on balanced and bottleneck, and 51.6–55.3 against 55.9 on reversal. On directional_reversal, however, the learned p95 (183–220 s) and worst-approach wait (237–269 s) are worse than native + max-red (171 / 226). The guardrail measures tails against tuned Fixed-Time, not against the best controller, so this passes. Still, it trades tail for mean on that case.
- **cologne.** The mean delay ties or narrowly beats flow_theory, and the tails are clearly better. Worst-approach wait is 30 s against 41 s on balanced and 30–37 s against 39 s on bottleneck. If the tails counted toward the score, the result would be stronger than the 0.2–1.0 s gain in delay suggests.
- **HCM.** Delay ties max_pressure, but the tails are much better: worst-approach wait is 38–39 s against 48 s on balanced and 51–60 s against 82–85 s on reversal.
- **Jakarta.** The delay is below max_queue + max-red, but the balanced-case tails fail. Worst-approach wait is 57 s against 46 s.
- **grid4x4.** flow_theory is the wrong base on this map. The max_pressure residual reaches 20.6 on both seeds, against a target of 20.1.

## 5. Caveats

1. **Selection on validation seeds.** Iterations 8–18 chose the base, the δ and the checkpoint on the same five validation seeds. The cologne margin especially is within noise. Test seeds are the honest check, and they need your approval to open.
2. **The base is hand-written.** The wins come from DQN residuals over flow_theory and max_pressure, inside the max-red envelope. The residual depends on running the base controller at inference time (one extra controller call per decision).
3. **Different maps favour different bases.** grid4x4 and Jakarta prefer max_pressure, and cologne prefers flow_theory. A per-map choice of base is itself a selection made on validation seeds.
4. **4-node is unsolved.** No configuration in either round passed its guardrail.

## 6. Decisions for you

1. **Open the test seeds** for the flow_theory δ 0.20 configuration (both seeds), and for the max_pressure δ 0.10 configuration on Hanoi and grid4x4.
2. **Promote the residual gates?** `EDGEFLOW_RESIDUAL_BASE` and `EDGEFLOW_MP_MARGIN` are env-gated experiment code. Making them part of the controller contract (the H6 question) needs your approval.
3. **Score tails?** The current score ranks on mean delay only. The learned controller's advantage on cologne and HCM is mostly in tails, which the score ignores.
