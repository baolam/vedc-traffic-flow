# Unified RL Campaign — First Report: Environment Design and Deterministic Baselines

- **Date:** 2026-11-22
- **Branch:** `research/rl-benchmark-suite` (campaign code at `ce40f40`)
- **Status:** interim diagnostic report. **One learner seed (17), validation seeds only.** The held-out test seeds were not opened. This is not the preregistered final report; that still needs all five learner seeds, a validation freeze and the test evaluation.
- **Supporting material:** [`rl_environment_design_20261122/`](rl_environment_design_20261122/) holds the experiment patches, evaluation scripts and raw result data.

## 1. Summary

1. The committed campaign learners barely beat the controllers they are built on. Both MAPPO variants (a residual on the native fair cycle) score within about 3 s of the native cycle on every map. Phase DQN passes the guardrail only on grid4x4 and HCM.
2. Diagnosis: the problem is the environment design more than the learning algorithm. The residual action space cannot change cycle length, and the native cycle (70/100/200 s) is far longer than the tuned Fixed-Time cycles. Phase DQN shares one network-wide reward across all nodes, so it gets no per-node credit assignment.
3. Four environment changes were tried; each is env-gated and **not merged**.
   - Cycle shorten/lengthen actions combined with wait-age and backlog observation features made local MAPPO the first learner to pass the guardrail on Jakarta (30.1 s).
   - A per-node reward with a tail penalty gave phase DQN its best results: HCM 89.2 s, passing (campaign DQN: 126.0 s), and Jakarta 40.4 s, passing. It also removed the campaign DQN's starvation of single approaches on cologne (worst-approach wait 560 s → 60 s).
   - Adding the new observation features to DQN made it **worse**.
4. **The deterministic controllers already in the repo beat every learned variant on 4 of 6 maps:**
   - max_pressure, flow_theory and EdgeFlow on HCM, cologne and grid4x4;
   - actuated on the 4-node map.

   Learned controllers lead only on Jakarta and Hanoi, by 1–2 s, which is within single-seed noise. No deterministic controller works everywhere: the pressure family gridlocks Hanoi.

## 2. Protocol

| Item | Value |
|---|---|
| Simulator | SUMO 1.28 via libsumo |
| Maps | `four_intersection_rl_v1` (4-node, 8 cases); `grid4x4_benchmark_v1`, `cologne8_benchmark_v1`, `hcm_neighborhood_v3_benchmark_v1` (HCM, engineering-repaired v3, *not qualified*), `hanoi_dong_da_v1`, `jakarta_menteng_v1` (3 cases each: balanced, directional_reversal, downstream_bottleneck) |
| Demand | calibrated per map and case (`workloads.json`); 1800 s demand + 600 s drain |
| Seeds | training seeds from `contracts/benchmark.py`; validation seeds 70001–70005; learner seed 17 |
| Reference | Fixed-Time with per-map tuned greens (20 s Jakarta/Hanoi, 30 s 4-node, 10 s others) |
| Score | equal-case mean of `delay_per_scheduled_s` (s; lower is better) |
| Guardrail (✓) | every run valid (no collision or teleport); completion ≥ 98 % of reference; per case, `p95_wait_s`, `worst_approach_wait_s` and `max_approach_p95_wait_s` ≤ reference + max(10 %, 1 s) (`src/rl/selection.py`) |
| Learned checkpoint | the selected (best guardrail-passing) validation checkpoint where one exists, else the final checkpoint |
| Recipes | DQN `unified_dqn_recipe_v3`; MAPPO `unified_mappo_recipe_v4` (no-op prior, `node_wait_v1` reward); 400-episode warmup; cycle rule `multiphase_cycle_v4` (adapt_share 1.0) |

## 3. Methods tried

| ID | Method | What changed | Gate |
|---|---|---|---|
| C | Campaign learners as committed | `phase_dqn_unified` (global `wait_tail_v1` reward) and `graph_mappo_unified` / `local_mappo_unified` (residual green transfers on the native fair cycle) | — |
| E1 | Running-vehicle pressure proxy | native-cycle pressure adds k · occupancy (k = 10, 20) | `EDGEFLOW_OCC_K` |
| E2 | Tail-aware MAPPO reward | reward −= λ · Σ max(0, oldest wait − T)/60 over the node's scope, λ = 0.05, T = 60 s | `EDGEFLOW_TAIL` |
| E3 | Fixed-Time-like native cycle | native cycle = phases · (g + clearance), g ∈ {10, 15, 20, 30} | `EDGEFLOW_CYCLE_G` |
| E4 | Cycle-length actions for MAPPO | two extra actions shorten/lengthen the node's green budget by 5 s per cycle (persistent offset) | `EDGEFLOW_CYCLE_ACTIONS=1` |
| E5 | E4 + observation v2 | two features per phase row: `wait_age` (oldest stopped or not-yet-entered wait / 60 s) and `external_backlog` (vehicles held outside the map / 20); observation `raw_two_hop_v2` (**contract change**) | patch B |
| E6 | Per-node DQN reward + tail | phase DQN reward = MAPPO's per-node `node_wait_v1` (own + fed approaches) + E2's tail term | `EDGEFLOW_DQN_NODE_REWARD=1` + `EDGEFLOW_TAIL=0.05,60` |
| E7 | E6 + observation v2 | E6 trained on `raw_two_hop_v2` | patch B |
| B | Deterministic baselines | every non-learned controller in `src/control/factory.py`, default parameters | clean `ce40f40` |

Patch A ([`patches/exp-a-…patch`](rl_environment_design_20261122/patches/exp-a-tail-occupancy-cycleg-dqn-node-reward.patch)) implements E1, E2, E3 and E6. Patch B ([`patches/exp-b-…patch`](rl_environment_design_20261122/patches/exp-b-cycle-actions-observation-v2.patch)) adds E4, E5 and E7 on top. Patch B changes `contracts/benchmark.py`, so it was applied only in a throwaway worktree.

## 4. Diagnosis of the committed campaign (C)

Seed-17 best validation scores (✓ = passes the guardrail):

| Map | Fixed-Time | Native cycle | Phase DQN | Graph MAPPO | Local MAPPO |
|---|---|---|---|---|---|
| HCM | 191.5 ✓ | 106.1 ✓ | 126.0 ✓ | 104.1 ✓ | 106.1 ✓ |
| Jakarta | 53.0 ✓ | 25.8 ✗ | 56.2 ✗ | 25.8 ✗ | 25.8 ✗ |
| Hanoi | 43.2 ✓ | 30.6 ✓ | 41.2 ✗ | run invalid (SUMO collision, seed 70004) | 30.7 ✓ |
| cologne | 71.4 ✓ | 58.1 ✗ | 48.3 ✗ | 55.3 ✗ | 55.4 ✗ |
| grid4x4 | 54.2 ✓ | 54.1 ✗ | 23.7 ✓ | 54.1 ✗ | 54.1 ✗ |
| 4-node | 76.6 ✓ | 80.2 ✗ | 117.4 ✗ | 78.5 ✗ | 79.1 ✗ |

Findings:

- **MAPPO ≈ native.** Its 65 actions only move green between phases inside a fixed cycle. A probe of the Jakarta policy found P(no-op) = 0.82: it learned that transfers do not pay.
- **Cycle length is a first-order lever the agent cannot touch.** The native cycle is max(70, 25 · phases) s, against tuned Fixed-Time cycles of 30–120 s. E3's fixed-g sweep below shows the best g depends on the map, so the cycle length has to adapt.
- **Phase DQN's reward is network-global.** Every node receives the same scalar, so a congested intersection cannot be distinguished from an idle one. On cologne it left single approaches waiting 555–662 s.

E3 cycle sweep (native cycle with green g; score and number of guardrail failures):

| Map | Fixed-Time | native (current) | g10 | g15 | g20 | g30 |
|---|---|---|---|---|---|---|
| Jakarta | 53.0 | 25.8 (6) | 69.8 (9) | **38.0 ✓** | 28.0 (2) | 25.8 (6) |
| Hanoi | 43.2 | 30.6 ✓ | 61.1 (9) | **29.2 ✓** | 31.3 ✓ | 34.3 (4) |
| grid4x4 | 54.2 | 54.1 (6) | 54.5 (2) | 46.6 (2) | 54.1 (6) | 71.9 (6) |
| cologne | 71.4 | 58.1 (7) | 71.4 (1) | 52.4 (5) | 54.1 (7) | 64.4 (7) |
| HCM | 191.5 | 106.1 ✓ | 197.5 (3) | 147.4 ✓ | 114.2 ✓ | 111.0 ✓ |
| 4-node | 76.6 | 80.2 (18) | 156.3 (20) | 104.1 (7) | 86.1 (8) | 80.2 (18) |

The remaining quick tests produced small or mixed results:

- **E1 (occupancy proxy, k = 10):** improved HCM (95.6) and cologne (56.6) and left Hanoi at 30.1, with no feasibility change. k = 20 was identical.
- **E2 (MAPPO tail reward):**
  - Hanoi graph MAPPO went to 29.5 ✓ with no collision, and Hanoi local to 29.9 ✓.
  - Jakarta was unchanged at 25.8 ✗.
  - The phase-DQN arm of E2 was invalid: the tail term was wired only into the pressure-reward branch, which phase DQN does not use. E6 fixes this.

## 5. Results across all methods

Final-checkpoint or selected scores, seed 17, all on the same validation seeds and guardrail. The **DQN campaign** row is C. The other learned rows:

- **DQN node+tail:** E6, the per-node reward with the tail term.
- **DQN node+tail+obs2:** E7, the same plus observation v2.
- **MAPPO cyc:** E4, the cycle-length actions.
- **MAPPO cyc+obs2:** E5, the cycle-length actions plus observation v2.

The legacy `fair_cycle` controller supports only 2-phase nodes, so it is not applicable to the 5 maps with 3+ phase intersections.

### 5.1 Best controller per map

| Map | Best deterministic | Best learned | Leader |
|---|---|---|---|
| HCM | max_pressure 72.0 ✓ | DQN node+tail 89.2 ✓ | deterministic (−17 s) |
| cologne | flow_theory 34.5 ✓ | DQN node+tail 38.0 ✗ | deterministic (first passing controller on cologne) |
| grid4x4 | max_pressure 20.1 ✓ | DQN node+tail+obs2 23.2 ✓ | deterministic |
| 4-node | actuated 68.7 ✓ | local MAPPO cyc 92.8 ✗ | deterministic (only controller that beats Fixed-Time) |
| Jakarta | max_pressure 31.9 ✓ | local MAPPO cyc+obs2 30.1 ✓ | learned, within noise |
| Hanoi | fair_cycle_native 30.6 ✓ | local MAPPO cyc+obs2 29.6 ✓ | learned, within noise |

### 5.2 Per-scenario metrics

Each cell is mean delay / p95 wait / worst-approach wait (s) over the five validation seeds. Rows are sorted by score.

**HCM**

| Controller | Score | Pass | balanced | directional_reversal | downstream_bottleneck |
|---|---|---|---|---|---|
| max_pressure | 72.0 | ✓ | 70.6 / 69.4 / 47.6 | 74.5 / 76.6 / 84.6 | 71.0 / 66.2 / 41.6 |
| flow_theory | 72.7 | ✓ | 70.6 / 67.2 / 41.0 | 74.0 / 71.9 / 66.0 | 73.6 / 68.8 / 41.8 |
| edgeflow | 73.6 | ✓ | 70.3 / 70.7 / 49.2 | 77.2 / 86.2 / 88.4 | 73.3 / 72.5 / 43.2 |
| DQN node+tail | 89.2 | ✓ | 85.9 / 90.2 / 56.2 | 94.7 / 103.0 / 79.2 | 87.0 / 89.5 / 65.0 |
| fair_cycle_native | 106.1 | ✓ | 103.0 / 148.2 / 111.8 | 109.1 / 165.3 / 147.4 | 106.1 / 151.0 / 112.0 |
| actuated | 107.0 | ✓ | 96.3 / 120.5 / 111.8 | 127.1 / 182.6 / 206.9 | 97.5 / 115.2 / 87.4 |
| max_queue | 109.6 | ✓ | 99.5 / 133.1 / 150.6 | 131.3 / 201.2 / 229.1 | 97.9 / 130.0 / 136.4 |
| DQN node+tail+obs2 | 109.6 | ✓ | 96.6 / 97.5 / 92.2 | 135.1 / 308.1 / 425.2 | 97.0 / 90.5 / 71.0 |
| DQN campaign | 126.0 | ✓ | 94.9 / 107.0 / 120.8 | 183.3 / 391.9 / 323.1 | 99.9 / 132.3 / 177.0 |
| local MAPPO cyc+obs2 | 141.9 | ✓ | 106.2 / 142.8 / 140.2 | 212.7 / 415.5 / 372.0 | 106.7 / 140.1 / 127.4 |
| graph MAPPO cyc | 149.7 | ✓ | 107.9 / 164.7 / 181.6 | 232.3 / 503.2 / 460.0 | 109.0 / 151.6 / 144.6 |
| graph MAPPO cyc+obs2 | 172.2 | ✗ | 133.5 / 259.1 / 265.0 | 257.0 / 540.5 / 473.6 | 126.0 / 217.2 / 240.6 |
| local MAPPO cyc | 173.1 | ✗ | 133.7 / 258.4 / 259.6 | 256.5 / 547.8 / 504.2 | 129.1 / 237.5 / 260.6 |
| fixed_time | 191.5 | ✓ | 122.8 / 210.2 / 211.8 | 316.9 / 673.2 / 675.9 | 134.9 / 264.1 / 254.0 |

**cologne**

| Controller | Score | Pass | balanced | directional_reversal | downstream_bottleneck |
|---|---|---|---|---|---|
| flow_theory | 34.5 | ✓ | 30.7 / 33.7 / 41.2 | 33.2 / 38.5 / 54.5 | 39.7 / 34.0 / 39.2 |
| max_pressure | 35.4 | ✓ | 30.7 / 30.8 / 32.4 | 35.9 / 36.2 / 37.5 | 39.6 / 31.4 / 32.8 |
| edgeflow | 37.4 | ✓ | 32.5 / 36.3 / 41.6 | 38.1 / 45.9 / 43.8 | 41.7 / 37.7 / 41.3 |
| max_queue | 37.4 | ✗ | 32.8 / 42.7 / 88.3 | 37.6 / 51.5 / 74.7 | 41.9 / 42.9 / 87.5 |
| DQN node+tail | 38.0 | ✗ | 32.6 / 39.3 / 60.4 | 39.4 / 48.4 / 61.4 | 41.9 / 38.8 / 57.4 |
| actuated | 38.1 | ✗ | 32.9 / 41.0 / 66.0 | 39.5 / 49.7 / 78.0 | 41.8 / 40.0 / 65.8 |
| DQN node+tail+obs2 | 40.8 | ✗ | 34.7 / 42.4 / 64.8 | 43.1 / 49.1 / 98.6 | 44.7 / 41.9 / 64.6 |
| local MAPPO cyc+obs2 | 49.0 | ✗ | 43.1 / 59.0 / 59.3 | 50.7 / 65.5 / 76.6 | 53.0 / 58.2 / 59.3 |
| graph MAPPO cyc+obs2 | 51.7 | ✗ | 44.0 / 59.5 / 59.3 | 55.6 / 70.0 / 65.3 | 55.5 / 59.2 / 59.3 |
| graph MAPPO cyc | 53.0 | ✗ | 44.3 / 60.8 / 59.3 | 59.3 / 74.9 / 65.3 | 55.4 / 60.4 / 59.3 |
| fair_cycle_native | 58.1 | ✗ | 51.6 / 87.5 / 81.8 | 57.6 / 90.4 / 84.4 | 65.0 / 88.0 / 82.0 |
| local MAPPO cyc | 59.7 | ✗ | 47.8 / 65.4 / 59.3 | 72.8 / 86.9 / 82.8 | 58.5 / 65.3 / 59.3 |
| fixed_time | 71.4 | ✓ | 49.6 / 65.2 / 52.5 | 106.3 / 159.0 / 262.9 | 58.4 / 64.3 / 55.9 |
| DQN campaign | 74.6 | ✗ | 47.4 / 52.5 / 563.9 | 121.0 / 382.8 / 662.1 | 55.4 / 51.8 / 555.4 |

**grid4x4**

| Controller | Score | Pass | balanced | directional_reversal | downstream_bottleneck |
|---|---|---|---|---|---|
| max_pressure | 20.1 | ✓ | 19.3 / 29.4 / 89.3 | 20.3 / 31.6 / 103.7 | 20.6 / 29.3 / 84.8 |
| edgeflow | 22.9 | ✓ | 22.0 / 39.8 / 79.4 | 23.3 / 40.9 / 94.7 | 23.4 / 39.3 / 89.1 |
| DQN node+tail+obs2 | 23.2 | ✓ | 22.1 / 37.0 / 86.6 | 24.0 / 41.5 / 223.3 | 23.3 / 36.8 / 97.2 |
| DQN campaign | 23.7 | ✓ | 22.6 / 39.4 / 122.2 | 25.1 / 44.7 / 146.2 | 23.4 / 36.5 / 134.6 |
| DQN node+tail | 24.7 | ✓ | 23.3 / 40.5 / 97.7 | 25.8 / 46.9 / 136.6 | 24.9 / 42.5 / 109.0 |
| flow_theory | 24.7 | ✗ | 23.9 / 49.9 / 151.3 | 24.9 / 51.4 / 210.8 | 25.2 / 49.5 / 158.6 |
| local MAPPO cyc / graph & local MAPPO cyc+obs2 | 48.6 | ✗ | 47.3 / 116.9 / 158.7 | 49.9 / 116.4 / 159.1 | 48.6 / 116.9 / 158.7 |
| graph MAPPO cyc | 51.4 | ✗ | 50.7 / 129.1 / 164.0 | 51.6 / 124.7 / 171.3 | 51.9 / 128.7 / 163.3 |
| fair_cycle_native | 54.1 | ✗ | 53.5 / 141.1 / 176.5 | 54.2 / 135.9 / 170.4 | 54.8 / 140.9 / 176.1 |
| fixed_time | 54.2 | ✓ | 43.7 / 93.9 / 148.3 | 74.6 / 218.8 / 338.8 | 44.4 / 92.1 / 140.2 |
| actuated | 75.4 | ✗ | 71.4 / 257.8 / 625.9 | 80.0 / 269.7 / 755.4 | 74.6 / 269.6 / 639.5 |
| max_queue | 460.5 | ✗ | 460.0 / 2007.7 / 2371.0 | 460.9 / 1882.7 / 2369.3 | 460.8 / 2007.7 / 2371.0 |

**Jakarta**

| Controller | Score | Pass | balanced | directional_reversal | downstream_bottleneck |
|---|---|---|---|---|---|
| flow_theory | 18.3 | ✗ | 14.8 / 32.8 / 66.9 | 23.9 / 58.3 / 86.8 | 16.1 / 33.6 / 65.4 |
| fair_cycle_native | 25.8 | ✗ | 19.2 / 43.8 / 63.5 | 37.5 / 74.2 / 96.6 | 20.6 / 43.5 / 63.5 |
| local MAPPO cyc+obs2 | 30.1 | ✓ | 16.1 / 30.1 / 51.7 | 56.9 / 126.4 / 168.9 | 17.4 / 29.8 / 52.4 |
| max_pressure | 31.9 | ✓ | 15.1 / 26.5 / 48.9 | 64.6 / 197.2 / 232.7 | 16.1 / 25.9 / 47.3 |
| max_queue | 31.9 | ✓ | 15.1 / 26.5 / 48.9 | 64.6 / 197.2 / 232.7 | 16.1 / 25.9 / 47.3 |
| edgeflow | 32.8 | ✓ | 15.1 / 26.5 / 48.9 | 67.2 / 197.0 / 228.1 | 16.1 / 25.9 / 47.3 |
| graph MAPPO cyc+obs2 | 33.6 | ✗ | 17.9 / 35.3 / 59.1 | 64.1 / 143.4 / 210.6 | 19.0 / 34.8 / 59.4 |
| actuated | 34.1 | ✓ | 15.1 / 26.6 / 50.7 | 71.2 / 209.5 / 238.5 | 16.0 / 25.0 / 49.0 |
| local MAPPO cyc | 34.9 | ✗ | 19.2 / 43.7 / 63.5 | 65.0 / 196.9 / 248.3 | 20.6 / 43.4 / 63.5 |
| DQN node+tail | 40.4 | ✓ | 15.0 / 26.6 / 50.9 | 89.7 / 278.1 / 334.1 | 16.3 / 26.6 / 52.1 |
| fixed_time | 53.0 | ✓ | 15.9 / 28.6 / 51.4 | 125.6 / 332.9 / 404.3 | 17.4 / 28.7 / 51.5 |
| DQN campaign | 56.2 | ✗ | 16.5 / 29.0 / 60.4 | 134.2 / 404.7 / 478.0 | 17.9 / 29.9 / 62.6 |
| graph MAPPO cyc | 60.9 | ✗ | 18.6 / 38.2 / 63.7 | 144.0 / 382.5 / 442.0 | 20.0 / 38.5 / 63.4 |
| DQN node+tail+obs2 | 79.5 | ✗ | 16.5 / 29.6 / 54.5 | 204.1 / 605.0 / 699.4 | 18.0 / 30.0 / 56.1 |

**Hanoi** (balanced and downstream_bottleneck are identical for every controller on this map)

| Controller | Score | Pass | balanced = downstream_bottleneck | directional_reversal |
|---|---|---|---|---|
| local MAPPO cyc+obs2 | 29.6 | ✓ | 22.4 / 51.2 / 68.9 | 43.9 / 137.1 / 179.3 |
| fair_cycle_native | 30.6 | ✓ | 23.3 / 52.1 / 70.5 | 45.3 / 138.4 / 192.9 |
| local MAPPO cyc | 31.1 | ✓ | 22.2 / 49.0 / 74.8 | 48.9 / 159.2 / 222.9 |
| graph MAPPO cyc | 31.7 | ✓ | 23.2 / 51.7 / 71.8 | 48.9 / 169.3 / 244.5 |
| graph MAPPO cyc+obs2 | 34.8 | ✓ | 19.6 / 39.3 / 71.3 | 65.3 / 259.5 / 368.0 |
| DQN campaign | 41.2 | ✗ | 19.2 / 45.2 / 106.6 | 85.1 / 475.4 / 536.6 |
| fixed_time | 43.2 | ✓ | 26.2 / 51.6 / 84.4 | 77.4 / 252.6 / 339.3 |
| DQN node+tail | 47.7 | ✗ | 20.8 / 44.1 / 71.5 | 101.5 / 459.4 / 517.0 |
| edgeflow | 83.3 | ✗ | 43.7 / 197.4 / 331.5 | 162.5 / 669.5 / 904.8 |
| actuated | 95.5 | ✗ | 72.5 / 348.4 / 442.1 | 141.6 / 866.3 / 989.9 |
| DQN node+tail+obs2 | 109.8 | ✗ | 45.6 / 196.0 / 424.4 | 238.1 / 1317.2 / 1412.9 |
| flow_theory | 290.6 | ✗ | 267.9 / 1878.9 / 2382.2 | 336.0 / 2155.3 / 2387.4 |
| max_pressure | 312.2 | ✗ | 281.2 / 1878.9 / 2382.2 | 374.2 / 2155.3 / 2387.4 |
| max_queue | 355.4 | ✗ | 318.9 / 1878.9 / 2382.2 | 428.6 / 2155.3 / 2387.4 |

**4-node** (8 cases). Scores:

- ✓: actuated 68.7, fixed_time 76.6.
- ✗: flow_theory 74.6, fair_cycle_native 80.2, fair_cycle 85.9, local MAPPO cyc 92.8, graph MAPPO cyc 95.1, DQN campaign 119.2, max_pressure 119.6, max_queue 120.1, edgeflow 120.2, DQN node+tail 120.4, DQN node+tail+obs2 138.6, graph/local MAPPO cyc+obs2 143.2.

| Case | fixed_time | actuated | flow_theory | fair_cycle_native | max_pressure | DQN node+tail | local MAPPO cyc |
|---|---|---|---|---|---|---|---|
| balanced | 36.3 / 44.1 / 39.8 | 37.3 / 39.2 / 41.3 | 30.5 / 37.3 / 44.5 | 48.0 / 74.7 / 73.4 | 34.5 / 39.6 / 48.0 | 38.5 / 41.3 / 44.6 | 42.1 / 58.2 / 57.9 |
| directional_surge | 34.2 / 42.1 / 38.8 | 24.2 / 26.8 / 32.2 | 21.6 / 35.0 / 61.8 | 33.8 / 66.6 / 60.7 | 25.0 / 29.4 / 40.7 | 35.2 / 41.4 / 39.8 | 33.7 / 44.5 / 60.3 |
| directional_surge_ew | 34.4 / 43.5 / 43.4 | 25.1 / 27.5 / 33.3 | 21.6 / 34.3 / 58.9 | 35.2 / 65.7 / 59.9 | 25.1 / 29.9 / 39.4 | 36.2 / 42.0 / 42.6 | 35.8 / 54.3 / 59.2 |
| downstream_bottleneck | 68.7 / 224.9 / 275.8 | 77.9 / 162.4 / 192.7 | 58.6 / 169.5 / 206.2 | 76.1 / 159.9 / 189.6 | 108.3 / 261.3 / 328.2 | 111.3 / 314.0 / 373.1 | 74.9 / 173.6 / 202.5 |
| sparse | 27.1 / 35.8 / 38.4 | 22.1 / 24.1 / 21.7 | 22.9 / 30.7 / 37.9 | 40.4 / 78.8 / 59.3 | 21.6 / 26.5 / 36.1 | 22.9 / 25.7 / 36.5 | 25.9 / 39.1 / 47.6 |
| near_capacity | 44.5 / 53.1 / 53.4 | 56.5 / 55.0 / 55.4 | 40.3 / 46.1 / 62.6 | 53.0 / 69.4 / 72.3 | 78.2 / 80.6 / 111.9 | 78.1 / 84.5 / 112.3 | 49.8 / 60.1 / 62.3 |
| oversaturated | 236.3 / 404.9 / 482.1 | 246.0 / 415.2 / 483.1 | 362.0 / 697.1 / 770.9 | 288.2 / 507.9 / 612.6 | 570.5 / 911.1 / 979.6 | 492.4 / 960.4 / 1044.1 | 297.6 / 522.6 / 616.7 |
| directional_reversal | 131.4 / 233.8 / 293.5 | 60.8 / 69.3 / 103.1 | 38.9 / 59.8 / 136.4 | 67.1 / 86.3 / 102.8 | 93.6 / 152.1 / 191.2 | 148.8 / 272.5 / 314.3 | 182.7 / 406.8 / 523.4 |

### 5.3 Cycle lengths chosen by the E4/E5 policies

Mean cycle in seconds, pooled over cases. Native cycles are 70 / 75 / 100 / 200 s for 2/3/4/8-phase nodes.

| Map | E4 graph | E4 local | E5 graph | E5 local |
|---|---|---|---|---|
| cologne (2/3/4-phase) | 33 / 47 / 64 | 32 / 47 / 65 | 35 / 47 / 64 | 35 / 47 / 65 |
| HCM (2/3/4-phase) | 35 / 49 / 67 | 32 / 47 / 65 | 32 / 47 / 65 | 32 / 47 / 68 |
| Jakarta (2/3-phase) | 33 / 75 | 68 / 75 | 36 / 49 | 36 / 75 |
| Hanoi (2/3-phase) | 70 / 75 | 40 / 55 | 40 / 64 | 70 / 75 |
| grid4x4 (8-phase) | 187 | 168 | 168 | 168 |
| 4-node (2-phase) | 38 | 46 | 32 | 32 |

## 6. Findings

1. **Action space (E3, E4).** Letting the agent change cycle length makes MAPPO move away from native for the first time. The policies shorten cycles almost everywhere and do not lengthen them when demand rises. Short cycles win the balanced and bottleneck cases but collapse the directional-reversal case (HCM, Jakarta, 4-node). On 4-node and grid4x4 the graph and local networks produce identical results to two decimals: both collapsed to the same state-independent rule (always shorten).
2. **Observation (E5).** With wait-age and backlog features MAPPO holds up under directional reversal on Jakarta and cologne, and local MAPPO gains the most. The same features made DQN worse (E7 vs E6 on HCM, Jakarta and Hanoi). A plausible cause, not yet confirmed, is that `wait_age` resets whenever the oldest vehicle leaves, which is noisy at DQN's 5 s decision step. `external_backlog` is simulation-only: a camera cannot count vehicles that have not entered the map.
3. **Reward (E6).** Per-node credit assignment is the most effective single change for phase DQN. It removed approach starvation (cologne worst-approach wait 560 s → 60 s, HCM 323 s → 79 s) and produced the best learned HCM and Jakarta-DQN results.
4. **Baselines (B).** The pressure family (max_pressure, flow_theory, EdgeFlow) is the strongest controller wherever it does not deadlock. On Hanoi it never serves some approaches for the full 2400 s, and only controllers that serve every phase each cycle pass there. Actuated is the only controller that beats Fixed-Time on the 4-node map. In the cologne balanced case max_pressure reaches a 32 s worst-approach wait, so the learned controllers' ~59 s there is not a structural floor.
5. **4-node** is limited by its oversaturated case. Every adaptive learned controller completes fewer trips than Fixed-Time there (e.g. DQN 3121 vs 3781 vehicles), which fails the 98 % completion rule independent of tails.

## 7. Limitations

- One learner seed and validation seeds only; differences below about 3 s (Jakarta, Hanoi) are not meaningful yet.
- Deterministic controllers ran with repository default parameters. Only Fixed-Time is tuned per map.
- E1–E7 are experiment patches, not committed code. E5 and E7 change the observation contract.
- MAPPO runs were capped at 512 episodes (two validation checkpoints after warmup); policies were still moving between them.
- The HCM map is the engineering-repaired v3 network and is not qualified.
- Scripts for E1, E3 and the E4 per-case/cycle-length evaluation were lost to a scratch-directory wipe. Their result data (`data/nativek.json`, `data/cycleg.json`) and the E4/E5 per-case results in `data/comparison.json` are preserved.

## 8. Next steps (proposed, not started)

1. Put the learned layer on top of max_pressure instead of the native cycle: a residual on its phase choice, or max_pressure plus a learned max-red / fairness override that targets its gridlock and tail failures.
2. Adopt E6 (per-node reward + tail) for phase DQN if it holds over more seeds. Do not adopt observation v2 for DQN.
3. Replace E4's ±5 s-per-cycle steps with a direct choice among a few cycle lengths, so a policy can return to a long cycle in one decision.
4. Run the remaining learner seeds (29, 43, 59, 71) before any of this enters the preregistered final report.

## 9. Reproduction

- Campaign and deterministic baselines: clean checkout of this branch, campaign root `artifacts/benchmarks/unified-v1` (gitignored; `unified_campaign --stage prepare/workloads/train`).
- Experiments: apply patch A (E1–E3, E6) or patch B (E4, E5, E7) in a separate worktree. Set the gates from §3 plus `EDGEFLOW_LIBSUMO=1`, then run `python -m src.benchmark.unified_campaign --stage train --seeds 17 --algorithms <alg> --root <experiment root>`. The root needs `prepared.json`, `workloads.json` and `references/` linked from the campaign root.
- Evaluation: `scripts/baselines.py`, `scripts/pc_dqn.py` and `scripts/pc_dqnobs.py` write per-case results, and `scripts/compile.py` builds `data/comparison.json`. Configure them with `REPO` (repository root), `WORKTREE` (patched checkout) and `EXP_ROOT` (experiment output root).
