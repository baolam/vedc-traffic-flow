# RL Research Loop — Overnight Report (2026-11-24)

- **Branch:** `research/rl-benchmark-suite`. Loop driver, ledger and scripts: [`../research/rl_loop/`](../research/rl_loop/).
- **Protocol:** phase DQN, loop recipe v2 (validation from episode 80, every 20 episodes, patience 8, 40 min cap). All six maps train in parallel. Learner seed 17, plus seed 29 for confirmation. Validation seeds only; the test seeds stay closed.
- **Score and guardrail:** the same as the [2026-11-22 report](RL_ENVIRONMENT_DESIGN_REPORT_20261122.md): equal-case mean `delay_per_scheduled_s` (lower is better), with tails and completion checked against tuned Fixed-Time.

## 1. Summary

1. Eight iterations ran, it00 to it07. Four changes were kept, one was discarded, then came a seed-29 confirmation run and a final ablation.
2. With every kept change on, phase DQN beat the best passing deterministic controller on **Jakarta** (24.2–25.0 vs max_pressure 32.2) and **Hanoi** (35.0–38.3 vs Fixed-Time 43.9). The wins held on both learner seeds.
3. **The ablation removes both wins.** The deciding change is a hard max-red rule in the phase mask, which the runtime applies to every controller. Deterministic controllers given the same rule match or beat the learned policies:
   - Jakarta: max_queue 23.3 and max_pressure 23.4, against learned 24.2–25.0.
   - Hanoi: fair_cycle_native 33.6, against learned 35.0–38.3.

   **On no map does learned control beat the best deterministic controller once both run inside the same safety envelope.**
4. Real progress, measured against the learned baseline:
   - cologne 44.2 → 37.4, HCM 88.0 → 76.7 (it03), and Jakarta and Hanoi went from failing to passing.
   - The remaining gap to the deterministic leaders is about 3 s on cologne, 4 s on grid4x4 and 12–14 s on HCM.
   - 4-node still fails the guardrail.
5. **Useful by-product:** max-red that counts vehicles waiting outside the map is itself a strong deterministic improvement.
   - It brings max_pressure to 23.4 on Jakarta, from 32.2.
   - It makes fair_cycle_native pass on the new Hanoi network at 33.6. Without it, native fails there with SUMO collisions.
   - It barely changes HCM, cologne and grid4x4.
   - It hurts actuated on 4-node, which fails with it on.

## 2. What happened to the maps

The prepared networks lived in `artifacts/benchmarks/development/inputs`, which was deleted on 2026-11-22. That broke five of the six maps.
- **cologne, grid4x4 and 4-node** were regenerated from committed sources. They are byte-identical to the originals, verified against the campaign checkpoint identity hashes.
- **Jakarta and Hanoi** were re-downloaded from OSM, as the user instructed.
  - Their topologies equal the committed contracts, but the networks differ.
  - Both maps were recalibrated and gave the same intensities and the same tuned 20 s Fixed-Time.
  - Their references and deterministic baselines were redone. Targets are in `rl_loop/targets.json`, and old data in `artifacts/benchmarks/unified-v1/archive-osm-20261120/`.
  - **Jakarta and Hanoi numbers in the 2026-11-22 report no longer compare.**
  - On new Hanoi, fair_cycle_native (without max-red) and several learned checkpoints have SUMO collisions.

## 3. Ledger

Scores in seconds. ✗x = no checkpoint passed the guardrail; x is the best score among failing checkpoints.

| It | Seed | Change (env gate) | Verdict | cologne | grid4x4 | HCM | Jakarta | Hanoi | 4-node |
|---|---|---|---|---|---|---|---|---|---|
| target | — | best passing deterministic | — | 34.5 | 20.1 | 72.0 | 32.2 | 43.9 | 68.7 |
| it00 | 17 | baseline (node reward + tail), recipe v1 | superseded | ✗41.1 | 24.4 | 91.1 | ✗43.4 | ✗69.3 | ✗92.7 |
| it00b | 17 | baseline, recipe v2 | BASE | 44.2 | 23.2 | 88.0 | ✗40.4 | ✗48.4 | ✗92.7 |
| it01 | 17 | + max-red 40 s on stopped waits (`EDGEFLOW_MAX_RED=40`) | KEEP | 42.1 | 25.0 | 81.5 | 35.0 | ✗36.0 | ✗122.9 |
| it02 | 17 | + max-pressure-guided exploration (`EDGEFLOW_MP_EXPLORE=0.5`) | KEEP | 37.6 | 25.7 | 81.0 | 34.0 | ✗38.0 | ✗125.0 |
| it03 | 17 | + pressure term in node reward (`EDGEFLOW_PRESSURE_BETA=0.5`) | KEEP | 37.4 | 24.2 | **76.7** | 34.4 | ✗34.8 | ✗127.1 |
| it04 | 17 | + lr 1e-4 (recipe) | DISCARD | 44.1 | 27.0 | 122.7 | ✗35.7 | ✗41.2 | ✗132.0 |
| it05 | 17 | + max-red counts outside waits (`EDGEFLOW_MAX_RED_EXTERNAL=1`) | KEEP | 37.4 | 24.2 | 83.9 | **25.0** | **38.3** | ✗113.6 |
| it06 | 29 | it05 configuration, second seed | confirms | 37.9 | 25.0 | 86.3 | **24.2** | **35.0** | ✗111.9 |
| it07 | — | ablation: deterministic controllers + it05 max-red | ablation | 34.5 | 20.7 | 72.2 | 23.3 | 33.6 | 76.6* |

\* On 4-node, actuated fails with max-red on (96.6 ✗), so only the unchanged Fixed-Time reference passes.

## 4. Per-case metrics

Each cell is mean delay / p95 wait / worst-approach wait (s) over the five validation seeds. The learned rows are each seed's selected policy, or its final checkpoint where none passed. "Best deterministic" is the best passing controller with no max-red. "+ max-red" is the best passing controller in the it07 ablation.

**cologne8_benchmark_v1**

| Controller | Score | Pass | balanced | directional_reversal | downstream_bottleneck |
|---|---|---|---|---|---|
| learned, seed 17 (selected ep 120) | 37.4 | ✓ | 32.7 / 37.6 / 45.0 | 37.5 / 42.0 / 60.5 | 41.9 / 36.8 / 45.0 |
| learned, seed 29 (selected ep 180) | 37.9 | ✓ | 33.2 / 38.8 / 53.4 | 38.8 / 45.7 / 49.9 | 41.7 / 39.1 / 53.0 |
| best deterministic: flow_theory | 34.5 | ✓ | 30.7 / 33.7 / 41.2 | 33.2 / 38.5 / 54.5 | 39.7 / 34.0 / 39.2 |
| best deterministic + max-red: flow_theory | 34.5 | ✓ | 30.7 / 33.7 / 41.2 | 33.0 / 38.3 / 50.0 | 39.7 / 34.0 / 39.2 |

**four_intersection_rl_v1**

| Controller | Score | Pass | balanced | directional_surge | directional_surge_ew | downstream_bottleneck | sparse | near_capacity | oversaturated | directional_reversal |
|---|---|---|---|---|---|---|---|---|---|---|
| learned, seed 17 (final checkpoint (no feasible checkpoint)) | 113.6 | ✗ | 39.1 / 40.9 / 44.6 | 36.2 / 38.2 / 38.6 | 37.4 / 42.0 / 40.0 | 167.9 / 375.5 / 455.7 | 26.7 / 24.6 / 23.1 | 84.6 / 87.5 / 111.1 | 442.9 / 742.1 / 809.5 | 108.1 / 137.7 / 161.3 |
| learned, seed 29 (final checkpoint (no feasible checkpoint)) | 111.9 | ✗ | 39.7 / 41.7 / 44.7 | 35.6 / 38.4 / 40.0 | 37.1 / 41.5 / 41.1 | 168.7 / 349.2 / 421.5 | 26.9 / 25.5 / 25.2 | 85.7 / 89.2 / 104.1 | 432.8 / 739.7 / 809.5 | 106.6 / 132.4 / 166.3 |
| best deterministic: actuated | 68.7 | ✓ | 37.3 / 39.2 / 41.3 | 24.2 / 26.8 / 32.2 | 25.1 / 27.5 / 33.3 | 77.9 / 162.4 / 192.7 | 22.1 / 24.1 / 21.7 | 56.5 / 55.0 / 55.4 | 246.0 / 415.2 / 483.1 | 60.8 / 69.3 / 103.1 |
| best deterministic + max-red: fixed_time | 76.6 | ✓ | 36.2 / 44.1 / 39.8 | 34.2 / 42.1 / 38.8 | 34.4 / 43.5 / 43.4 | 68.7 / 224.9 / 275.8 | 27.1 / 35.8 / 38.4 | 44.5 / 53.1 / 53.4 | 236.3 / 404.9 / 482.1 | 131.4 / 233.8 / 293.5 |

**grid4x4_benchmark_v1**

| Controller | Score | Pass | balanced | directional_reversal | downstream_bottleneck |
|---|---|---|---|---|---|
| learned, seed 17 (selected ep 240) | 24.2 | ✓ | 22.7 / 39.1 / 68.2 | 25.6 / 45.6 / 74.5 | 24.2 / 39.8 / 69.1 |
| learned, seed 29 (selected ep 200) | 25.0 | ✓ | 24.0 / 43.0 / 72.8 | 26.1 / 46.3 / 81.4 | 25.1 / 42.6 / 76.7 |
| best deterministic: max_pressure | 20.1 | ✓ | 19.3 / 29.4 / 89.3 | 20.3 / 31.6 / 103.7 | 20.6 / 29.3 / 84.8 |
| best deterministic + max-red: max_pressure | 20.7 | ✓ | 19.9 / 31.1 / 115.1 | 21.2 / 34.2 / 117.6 | 21.0 / 30.2 / 110.1 |

**hanoi_dong_da_v1**

| Controller | Score | Pass | balanced | directional_reversal | downstream_bottleneck |
|---|---|---|---|---|---|
| learned, seed 17 (selected ep 120) | 38.3 | ✓ | 19.6 / 39.6 / 62.3 | 75.8 / 252.8 / 312.2 | 19.6 / 39.6 / 62.3 |
| learned, seed 29 (selected ep 160) | 35.0 | ✓ | 19.8 / 46.2 / 83.2 | 65.2 / 252.9 / 308.0 | 19.8 / 46.2 / 83.2 |
| best deterministic: fixed_time | 43.9 | ✓ | 26.2 / 52.0 / 84.3 | 79.2 / 257.1 / 366.2 | 26.2 / 52.0 / 84.3 |
| best deterministic + max-red: fair_cycle_native | 33.6 | ✓ | 22.4 / 49.9 / 68.8 | 55.9 / 171.4 / 225.9 | 22.4 / 49.9 / 68.8 |

**hcm_neighborhood_v3_benchmark_v1**

| Controller | Score | Pass | balanced | directional_reversal | downstream_bottleneck |
|---|---|---|---|---|---|
| learned, seed 17 (selected ep 200) | 83.9 | ✓ | 79.4 / 82.9 / 64.8 | 91.3 / 120.0 / 119.2 | 80.9 / 82.3 / 60.4 |
| learned, seed 29 (selected ep 260) | 86.3 | ✓ | 83.1 / 81.8 / 93.0 | 90.8 / 97.5 / 105.2 | 84.8 / 82.2 / 85.8 |
| best deterministic: max_pressure | 72.0 | ✓ | 70.6 / 69.4 / 47.6 | 74.5 / 76.6 / 84.6 | 71.0 / 66.2 / 41.6 |
| best deterministic + max-red: max_pressure | 72.2 | ✓ | 70.5 / 69.4 / 47.6 | 74.9 / 79.3 / 81.4 | 71.0 / 66.2 / 41.6 |

**jakarta_menteng_v1**

| Controller | Score | Pass | balanced | directional_reversal | downstream_bottleneck |
|---|---|---|---|---|---|
| learned, seed 17 (selected ep 100) | 25.0 | ✓ | 15.3 / 27.4 / 47.1 | 43.1 / 80.4 / 108.8 | 16.8 / 27.7 / 48.8 |
| learned, seed 29 (selected ep 120) | 24.2 | ✓ | 14.9 / 25.9 / 46.9 | 41.6 / 79.9 / 107.0 | 16.2 / 26.1 / 49.8 |
| best deterministic: max_pressure | 32.2 | ✓ | 15.1 / 27.0 / 46.1 | 65.4 / 197.2 / 224.5 | 16.2 / 26.4 / 49.8 |
| best deterministic + max-red: max_queue | 23.3 | ✓ | 15.1 / 27.0 / 46.1 | 38.8 / 76.5 / 101.5 | 16.2 / 26.4 / 49.8 |

## 5. Findings

1. **The envelope matters more than the learner.** max-red 40 s with outside waits made both learned wins. It is a fixed rule in `phase_mask`. Any controller run through the benchmark runtime gets it, and with it the pressure family and the native cycle match or beat the learned policies. The fair comparison is learned vs deterministic inside the same envelope, and that comparison is lost or tied on every map. Jakarta and Hanoi are within about 1–2 s, roughly single-seed noise.
2. **Why outside waits mattered:** the guardrail's approach waits include `departDelay`, the time a vehicle waits outside the map to enter. Under directional reversal the tail sits at the map boundary, which stopped-vehicle waits cannot see. This is a simulation-only signal: a camera cannot see vehicles that have not entered. A deployable version needs a spillback proxy, for example occupancy of the boundary approach.
3. **Learning changes that helped on their own:**
   - Max-pressure-guided exploration: cologne −4.5.
   - Pressure term in the reward: HCM −4.3.
   - Neither closes the gap to max_pressure on HCM or grid4x4.
4. **Late decline:** phase DQN still declines after its best checkpoint (HCM peaks near episodes 160–200). A lower learning rate (1e-4) is far worse within this budget. Checkpoint selection hides the decline but does not fix it.
5. **4-node** stays infeasible. The oversaturated and downstream_bottleneck cases have about twice actuated's delay, and oversaturated completion falls below 98 % of Fixed-Time. Max-red does not help there and hurts actuated.

## 6. Code changes (all env-gated, default off, on this branch)

| Commit | Change |
|---|---|
| `e953dda` | Patch A hooks (E1–E3, E6) committed; loop driver |
| `cd5bb9b`, `218930e` | `EDGEFLOW_MAX_RED`, `EDGEFLOW_MAX_RED_EXTERNAL` in `src/control/phase_dqn.py::phase_mask` (+ tests) |
| `ed470c0` | `EDGEFLOW_MP_EXPLORE` in phase DQN training |
| `6e1fe70` | `EDGEFLOW_PRESSURE_BETA` in the per-node reward |
| `7e3ddc4`, `ed470c0` | **Bug fix (not gated):** a SUMO collision in one validation case makes that candidate infeasible (score stored as `null`) instead of killing the training run |

`make contracts` and `make test` pass (705 tests). No contracts changed.

## 7. Limitations

- Two learner seeds (17, 29) and validation seeds only. Every loop decision was taken on the same validation seeds, so the kept configuration is somewhat overfitted to them.
- Deterministic controllers use repository defaults; only Fixed-Time is tuned. The max-red T = 40 s was not tuned for either side.
- The loop recipe (about 80–350 episodes, 40 min cap) is much shorter than the campaign recipe. HCM and grid4x4 hit the wall-clock cap.
- Jakarta and Hanoi are new network versions, and new Hanoi produces SUMO collisions with several controllers.

## 8. Recommended next steps

1. Treat max-red with outside waits as a **deterministic** contribution. Benchmark it as its own controller family, decide whether it belongs in the default safety envelope, and design a camera-feasible spillback proxy for it. Changing the default envelope would change every baseline, so the user decides.
2. Judge learned controllers only inside the same envelope as the baselines. Learned control currently trails max_pressure by 1–14 s.
3. The most promising learned direction, still open: the "follow max_pressure" residual action (H6). It needs a contract change, which awaits user approval. With max-red supplying the tails, the learner would only need to find where pressure is wrong.
4. Look into the new-Hanoi SUMO collisions (junction clusters, side collisions during lane change) before using Hanoi as evidence.

## 9. Reproduction

- **One iteration:** `EDGEFLOW_<gates>=… LOOP_RECIPE_EXTRA='{…}' docs/engineering/research/rl_loop/run.sh itNN`, then `score.py itNN "<text>" [--seed N] --record`.
- **Ablation:** `artifacts/benchmarks/rl-loop/it07-ablation/run.sh` (it runs `scripts/baselines.py` with the max-red gates set).
- **Per-case metrics:** `[SEED=29] PYTHONPATH=. python docs/engineering/research/rl_loop/percase.py itNN`.
- **Tables:** `python docs/engineering/research/rl_loop/report_tables.py`.
- Run artifacts are in `artifacts/benchmarks/rl-loop/` (gitignored). Lock and temp files are in `artifacts/tmp/`.
