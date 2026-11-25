# RL Research Loop — Round 3 Report (2026-11-25)

- **Branch:** `research/rl-benchmark-suite`. The driver, ledger and scripts are in [`../research/rl_loop/`](../research/rl_loop/). Earlier rounds: [round 1](RL_RESEARCH_LOOP_REPORT_20261124.md), [round 2](RL_RESEARCH_LOOP_ROUND2_REPORT_20261124.md).
- **Scope:** 30 iterations, it19–it48, as the user asked: "Run for 30 more iteration. Try some more new ideas." 15 new ideas were tested, plus one bug fix and 10 confirmation runs.
- **Protocol:** unchanged. Phase DQN, loop recipe v2, all six maps in parallel, a 40 min cap, validation seeds 70001–70005 only. Targets are fair: the best passing deterministic controller with or without the same max-red envelope. **The test seeds were never opened.**

## 1. Summary

1. **Hanoi is a robust win, and cologne a fragile one.** Results across three learner seeds (17 / 29 / 41) for the three main configurations:

   | Configuration | cologne | grid4x4 | HCM | Jakarta | Hanoi | 4-node |
   |---|---|---|---|---|---|---|
   | target | 34.5 | 20.1 | 72.0 | 23.3 | 33.6 | 68.7 |
   | A. flow_theory residual δ 0.20 (round-2 winner; it19 / it18 / it48) | **34.0 / 33.5 / 34.1** (3/3) | 23.1 / 23.9 / 23.0 (0/3) | 72.7 / 72.4 / 73.4 (0/3) | ✗ / ✗ / ✗ (0/3) | **31.0 / 29.0 / 30.2** (3/3) | ✗ / ✗ / ✗ (0/3) |
   | B. A + base-following exploration (it20 / it28 / it45) | 33.6 / 33.7 / 34.7 (2/3) | 23.2 / 23.5 / 23.4 (0/3) | 72.6 / 73.4 / 73.0 (0/3) | ✗ / ✗ / ✗ (0/3) | **29.0 / 29.1 / 32.2** (3/3) | ✗ / ✗ / ✗ (0/3) |
   | C. B + two-tier residual (it32 / it37 / it44) | 34.2 / 34.7 / 34.1 (2/3) | 20.7 / 21.0 / 21.0 (0/3) | 73.6 / 74.7 / 73.1 (0/3) | 23.8 / 23.7 / 23.7 (0/3) | **28.2 / 28.5 / 31.6** (3/3) | ✗ / ✗ / ✗ (0/3) |

   (n/3) is the number of seeds that pass the guardrail **and** score below the target. ✗ means no checkpoint passed the guardrail.

   - **Hanoi** wins on every seed of all three configurations, by 2.0–5.4 s. That is above the 3 s single-seed noise floor in most runs.
   - **cologne** wins 3/3 only under configuration A, and its margins are 0.4–1.0 s, inside the noise. One caveat: A's seed-29 run (it18) predates the R1 bug fix.
2. **The best new idea was the two-tier residual (R12, it32).** The learner follows flow_theory and may take max_pressure's phase if that looks more than 5 % better. It may take any other phase only if that looks more than 20 % better. This gives:
   - **Jakarta** passes the guardrail on all three seeds for the first time with a learned controller: 23.7–23.8, against the 23.3 target. Without the two-tier rule it fails on every seed.
   - **grid4x4** improves from about 23 to 20.7–21.0, against the 20.1 target. max_pressure inside the same envelope scores 20.7, so the learner is at the envelope's level.
   - **Hanoi** improves to 28.2 / 28.5 / 31.6.
   - **The cost:** cologne drops to 2/3 seeds and HCM is about 1 s worse.
3. **No configuration wins HCM, grid4x4, Jakarta or 4-node on more than one seed.**
   - Single-seed near misses, all refuted by a second seed:
     - HCM 71.6–71.9 (it25, it30, it36); the it36 rerun on seed 29 gave 74.4.
     - Jakarta 23.4 and grid4x4 20.3 (it39); the seed-29 rerun gave 23.6 and 20.5.
   - **Jakarta** loses only on directional_reversal: 39.6–40.1 against 38.8 for max_queue + max-red. On balanced and bottleneck it matches max_queue to 0.1 s (§3).
   - **4-node** is blocked by the max-red envelope itself, not by the learner. Actuated passes 4-node alone (68.7) but fails with max-red, and a residual on actuated stays at about 111 (it43).
4. **A bug was found and fixed (R1, it19).** The residual base controller was created once per process and never reset. flow_theory therefore carried stale phase-start timers across training episodes and validation runs. The fix changed scores by at most 0.7 s, so round 2's wins hold.
5. **Runs are deterministic for a fixed seed, code and gates.** it31 reproduced it20 exactly on every map that stopped before the cap. Same-seed differences between iterations are therefore caused by the change. The noise to beat is seed-to-seed spread, up to 3–4 s on Hanoi.

## 2. What was tried (round 3)

| # | Idea | Iterations | Outcome |
|---|---|---|---|
| R1 | Reset the residual base's timers between runs (bug fix) | it19 | kept (fix); wins hold |
| R2 | Guided exploration follows the residual base | it20, it28, it45 | **kept** after the seed-29 confirmation |
| R3 | Tail guard: no overrides past a 25 s wait | it21 | discarded: Hanoi fails, Jakarta still fails |
| R10 | max_queue as the base | it22 | discarded: 5/6 maps fail |
| R4 | Hold-only overrides (timing only) | it23 | discarded |
| R5 | No pressure shaping | it24 | no effect |
| R11 | Two-expert residual (overrides only to max_pressure) | it25, it26 | HCM 71.9 once, but Hanoi fails (needs free overrides) |
| R8 | 3-step returns | it27 | mixed; reverted |
| R6 | Tail-penalty λ 0.2 / 0.5 | it29, it30, it35 | small gains on some maps, losses on others |
| R7 | 50 min wall cap | it31 | no effect: grid4x4 peaks at episode 100–120, then declines |
| R12 | **Two-tier residual** (alt at 5 %, any phase at 20 %) | it32–34, it37, it39, it44, it47 | **kept**; alt margin 0.05 and free margin 0.20 are best |
| R13 | Slower target network | it36, it46 | HCM 71.6 once, not confirmed |
| R14 | max_queue as the alt | it38 | worse |
| R15 | Time-loss training cost (matching the delay score) | it40 | flat; reverted |
| — | Guided exploration 0.8; faster ε decay | it41, it42 | worse or flat |
| R9 | Residual on actuated (4-node probe) | it43 | 4-node still ~111; other maps collapse |

**Code kept (all env-gated, default off, no contract changes):**
- The R1 fix, in `base_index` / `controller_index`.
- `EDGEFLOW_EXPLORE_BASE`, `EDGEFLOW_RESIDUAL_ALT` and `EDGEFLOW_ALT_MARGIN`.
- `run.sh` `WALL=`.

Reverted: the tail guard, hold-only mode, n-step returns and the time-loss cost.

**Disk:** it47's first run died when the disk filled. 58 GB of resume-only `checkpoint.pt` files from finished, unreported iterations were deleted. Scores, histories and policies were kept.

## 3. Ledger (round 3)

Scores are in seconds; lower is better. **Bold** marks a score below the target. CONFIRM rows are confirmation runs on another learner seed.

| It | Seed | Change | cologne | grid4x4 | HCM | Jakarta | Hanoi | 4-node | Verdict |
|---|---|---|---|---|---|---|---|---|---|
| target | | best deterministic ± max-red | 34.5 | 20.1 | 72.0 | 23.3 | 33.6 | 68.7 | |
| it19 | 17 | R1: residual base resets per-node timers between runs (bug fix) | **34.0** | 23.1 | 72.7 | ✗ | **31.0** | ✗ | BASE |
| it20 | 17 | R2: guided exploration follows the residual base (flow_theory) | **33.6** | 23.2 | 72.6 | ✗ | **29.0** | ✗ | KEEP |
| it21 | 17 | R3: tail guard, no overrides past 25 s wait | **33.7** | 23.7 | 72.7 | ✗ | ✗ | ✗ | DISCARD |
| it22 | 17 | R10: max_queue residual base (+explore base), delta 0.20 | ✗ | ✗ | 83.2 | 24.0 | ✗ | ✗ | DISCARD |
| it23 | 17 | R4: hold-only residual (timing overrides only) | **33.7** | 24.3 | 73.2 | ✗ | ✗ | ✗ | DISCARD |
| it24 | 17 | R5: pressure shaping off (beta 0) under flow_theory base | **33.6** | 23.1 | 72.7 | ✗ | **31.1** | ✗ | DISCARD |
| it25 | 17 | R11: two-expert residual (flow_theory base, overrides only to max_pressure) | **33.6** | 21.7 | **71.9** | ✗ | ✗ | ✗ | DISCARD |
| it26 | 17 | R11 + R2: two-expert residual with base-following exploration | **33.4** | 22.0 | 72.9 | ✗ | ✗ | ✗ | DISCARD |
| it27 | 17 | R8: 3-step returns | **33.5** | 23.4 | 72.2 | ✗ | **32.0** | ✗ | DISCARD |
| it28 | 29 | CONFIRM it20 (explore follows flow_theory base) seed 29 | **33.7** | 23.5 | 73.4 | ✗ | **29.1** | ✗ | CONFIRM |
| it29 | 17 | R6: tail penalty lambda 0.2 (T 60) | **33.6** | 22.7 | 72.3 | ✗ | **28.7** | ✗ | DISCARD |
| it30 | 17 | R6: tail penalty lambda 0.5 (T 60) | **33.4** | 23.2 | **71.9** | ✗ | **30.5** | ✗ | DISCARD |
| it31 | 17 | R7: 50 min wall cap (grid/HCM were budget-limited) | **33.6** | 23.2 | 72.9 | ✗ | **29.0** | ✗ | DISCARD |
| it32 | 17 | R12: two-tier residual (alt max_pressure at 0.05, any phase at 0.20) | **34.2** | 20.7 | 73.6 | 23.8 | **28.2** | ✗ | KEEP |
| it33 | 17 | R12 sweep: alt margin 0.02 | 34.5 | 20.2 | 75.4 | 23.7 | **28.4** | ✗ | DISCARD |
| it34 | 17 | R12 sweep: alt margin 0.10 | **34.4** | 21.3 | 74.2 | 24.0 | **28.5** | ✗ | DISCARD |
| it35 | 17 | R6 on it32 base: tail lambda 0.2 | **34.1** | 21.0 | 74.1 | 23.6 | **29.3** | ✗ | DISCARD |
| it36 | 17 | R13: slower target net (sync every 2500 updates) | **33.9** | 21.2 | **71.6** | 25.0 | **28.6** | ✗ | DISCARD |
| it37 | 29 | CONFIRM it32 (two-tier residual) seed 29 | 34.7 | 21.0 | 74.7 | 23.7 | **28.5** | ✗ | CONFIRM |
| it38 | 17 | R14: two-tier residual, alt = max_queue | **34.3** | 23.0 | 75.2 | 23.7 | **28.2** | ✗ | DISCARD |
| it39 | 17 | two-tier sweep: free-override margin 0.30 | 34.5 | 20.3 | 73.8 | 23.4 | ✗ | ✗ | DISCARD |
| it40 | 17 | R15: time-loss node reward | **34.2** | 21.1 | 73.9 | 23.6 | **28.5** | ✗ | DISCARD |
| it41 | 17 | guided exploration share 0.8 | 34.9 | 21.1 | 74.1 | 23.5 | **29.0** | ✗ | DISCARD |
| it42 | 17 | faster epsilon decay (62500 sim s) | 34.5 | 20.6 | 73.5 | 23.8 | **29.8** | ✗ | DISCARD |
| it43 | 17 | R9: actuated residual (4-node probe) | ✗ | 40.5 | 90.7 | 25.6 | **31.7** | ✗ | DISCARD |
| it44 | 41 | CONFIRM it32 config seed 41 | **34.1** | 21.0 | 73.1 | 23.7 | **31.6** | ✗ | CONFIRM |
| it45 | 41 | CONFIRM it20 config seed 41 | 34.7 | 23.4 | 73.0 | ✗ | **32.2** | ✗ | CONFIRM |
| it46 | 29 | CONFIRM it36 config (slower target net) seed 29 | **34.0** | 21.2 | 74.4 | 23.7 | ✗ | ✗ | CONFIRM |
| it47 | 29 | CONFIRM it39 config (free-override margin 0.30) seed 29 | 34.6 | 20.5 | 73.2 | 23.6 | ✗ | ✗ | CONFIRM |
| it48 | 41 | CONFIRM it19 config (round-2 winner, fixed) seed 41 | **34.1** | 23.0 | 73.4 | ✗ | **30.2** | ✗ | CONFIRM |

## 4. Per-case metrics

Each cell shows delay / p95 wait / worst-approach wait, as the mean over 5 validation seeds. Every learned run here completed with 0 collisions and 0 teleports. Learned rows are the selected checkpoint, or the final checkpoint where no checkpoint passed.

### 4.1 Configuration C: two-tier residual (it32 seed 17, it37 seed 29, it44 seed 41)


**cologne8_benchmark_v1**

| Controller | Score | Pass | balanced | directional_reversal | downstream_bottleneck |
|---|---|---|---|---|---|
| learned, seed 17 (selected ep 140) | 34.2 | ✓ | 29.1 / 28.8 / 34.3 | 35.0 / 36.4 / 41.4 | 38.4 / 29.0 / 36.7 |
| learned, seed 29 (selected ep 180) | 34.7 | ✓ | 29.9 / 28.8 / 29.9 | 35.7 / 36.3 / 37.5 | 38.4 / 28.7 / 27.4 |
| learned, seed 41 (selected ep 100) | 34.1 | ✓ | 29.4 / 28.5 / 32.1 | 34.9 / 36.5 / 45.6 | 38.1 / 28.0 / 28.9 |
| best deterministic: flow_theory | 34.5 | ✓ | 30.7 / 33.7 / 41.2 | 33.2 / 38.5 / 54.5 | 39.7 / 34.0 / 39.2 |
| best deterministic + max-red: flow_theory | 34.5 | ✓ | 30.7 / 33.7 / 41.2 | 33.0 / 38.3 / 50.0 | 39.7 / 34.0 / 39.2 |

**four_intersection_rl_v1**

| Controller | Score | Pass | balanced | directional_surge | directional_surge_ew | downstream_bottleneck | sparse | near_capacity | oversaturated | directional_reversal |
|---|---|---|---|---|---|---|---|---|---|---|
| learned, seed 17 (final checkpoint (no feasible checkpoint)) | 107.1 | ✗ | 38.5 / 40.5 / 43.5 | 36.6 / 38.9 / 40.6 | 37.4 / 41.2 / 39.9 | 161.5 / 366.7 / 449.6 | 25.1 / 26.4 / 24.0 | 82.8 / 84.4 / 100.1 | 435.1 / 749.0 / 817.2 | 91.0 / 118.7 / 146.1 |
| learned, seed 29 (final checkpoint (no feasible checkpoint)) | 105.3 | ✗ | 39.8 / 42.7 / 45.4 | 34.5 / 38.3 / 40.9 | 35.4 / 38.7 / 38.3 | 169.3 / 382.0 / 460.9 | 23.7 / 25.9 / 22.6 | 81.5 / 83.9 / 112.7 | 435.4 / 752.1 / 815.6 | 92.1 / 116.0 / 144.8 |
| learned, seed 41 (final checkpoint (no feasible checkpoint)) | 107.4 | ✗ | 39.9 / 43.1 / 45.1 | 33.7 / 39.5 / 39.5 | 35.7 / 39.4 / 39.4 | 164.2 / 360.9 / 435.5 | 22.7 / 25.8 / 23.8 | 82.5 / 83.8 / 105.0 | 414.4 / 710.1 / 777.1 | 99.2 / 125.9 / 155.7 |
| best deterministic: actuated | 68.7 | ✓ | 37.3 / 39.2 / 41.3 | 24.2 / 26.8 / 32.2 | 25.1 / 27.5 / 33.3 | 77.9 / 162.4 / 192.7 | 22.1 / 24.1 / 21.7 | 56.5 / 55.0 / 55.4 | 246.0 / 415.2 / 483.1 | 60.8 / 69.3 / 103.1 |
| best deterministic + max-red: fixed_time | 76.6 | ✓ | 36.2 / 44.1 / 39.8 | 34.2 / 42.1 / 38.8 | 34.4 / 43.5 / 43.4 | 68.7 / 224.9 / 275.8 | 27.1 / 35.8 / 38.4 | 44.5 / 53.1 / 53.4 | 236.3 / 404.9 / 482.1 | 131.4 / 233.8 / 293.5 |

**grid4x4_benchmark_v1**

| Controller | Score | Pass | balanced | directional_reversal | downstream_bottleneck |
|---|---|---|---|---|---|
| learned, seed 17 (selected ep 180) | 20.7 | ✓ | 19.7 / 33.4 / 76.7 | 21.0 / 36.9 / 82.0 | 21.3 / 33.9 / 81.9 |
| learned, seed 29 (selected ep 191) | 21.0 | ✓ | 20.1 / 34.2 / 71.1 | 21.3 / 37.1 / 100.2 | 21.4 / 34.4 / 70.7 |
| learned, seed 41 (selected ep 180) | 21.0 | ✓ | 20.1 / 35.0 / 86.6 | 21.4 / 38.0 / 92.0 | 21.6 / 35.5 / 93.2 |
| best deterministic: max_pressure | 20.1 | ✓ | 19.3 / 29.4 / 89.3 | 20.3 / 31.6 / 103.7 | 20.6 / 29.3 / 84.8 |
| best deterministic + max-red: max_pressure | 20.7 | ✓ | 19.9 / 31.1 / 115.1 | 21.2 / 34.2 / 117.6 | 21.0 / 30.2 / 110.1 |

**hanoi_dong_da_v1**

| Controller | Score | Pass | balanced | directional_reversal | downstream_bottleneck |
|---|---|---|---|---|---|
| learned, seed 17 (selected ep 140) | 28.2 | ✓ | 18.1 / 47.0 / 85.0 | 48.3 / 173.3 / 216.4 | 18.1 / 47.0 / 85.0 |
| learned, seed 29 (selected ep 260) | 28.5 | ✓ | 18.4 / 49.3 / 86.9 | 48.8 / 185.4 / 226.7 | 18.4 / 49.3 / 86.9 |
| learned, seed 41 (selected ep 180) | 31.6 | ✓ | 19.7 / 48.2 / 81.0 | 55.4 / 190.4 / 236.2 | 19.7 / 48.2 / 81.0 |
| best deterministic: fixed_time | 43.9 | ✓ | 26.2 / 52.0 / 84.3 | 79.2 / 257.1 / 366.2 | 26.2 / 52.0 / 84.3 |
| best deterministic + max-red: fair_cycle_native | 33.6 | ✓ | 22.4 / 49.9 / 68.8 | 55.9 / 171.4 / 225.9 | 22.4 / 49.9 / 68.8 |

**hcm_neighborhood_v3_benchmark_v1**

| Controller | Score | Pass | balanced | directional_reversal | downstream_bottleneck |
|---|---|---|---|---|---|
| learned, seed 17 (selected ep 140) | 73.6 | ✓ | 71.4 / 65.8 / 36.0 | 75.5 / 72.9 / 50.9 | 74.0 / 66.1 / 38.6 |
| learned, seed 29 (selected ep 300) | 74.7 | ✓ | 72.8 / 68.0 / 46.0 | 77.7 / 75.3 / 52.2 | 73.6 / 70.4 / 41.4 |
| learned, seed 41 (selected ep 220) | 73.1 | ✓ | 72.1 / 68.9 / 41.4 | 74.6 / 70.4 / 52.6 | 72.8 / 66.2 / 38.4 |
| best deterministic: max_pressure | 72.0 | ✓ | 70.6 / 69.4 / 47.6 | 74.5 / 76.6 / 84.6 | 71.0 / 66.2 / 41.6 |
| best deterministic + max-red: max_pressure | 72.2 | ✓ | 70.5 / 69.4 / 47.6 | 74.9 / 79.3 / 81.4 | 71.0 / 66.2 / 41.6 |

**jakarta_menteng_v1**

| Controller | Score | Pass | balanced | directional_reversal | downstream_bottleneck |
|---|---|---|---|---|---|
| learned, seed 17 (selected ep 200) | 23.8 | ✓ | 15.0 / 26.9 / 46.1 | 40.1 / 79.9 / 107.0 | 16.4 / 26.5 / 48.1 |
| learned, seed 29 (selected ep 200) | 23.7 | ✓ | 15.0 / 26.9 / 46.1 | 39.8 / 79.8 / 106.5 | 16.4 / 26.5 / 48.1 |
| learned, seed 41 (selected ep 240) | 23.7 | ✓ | 14.9 / 26.7 / 45.5 | 39.6 / 79.0 / 107.1 | 16.5 / 27.1 / 46.3 |
| best deterministic: max_pressure | 32.2 | ✓ | 15.1 / 27.0 / 46.1 | 65.4 / 197.2 / 224.5 | 16.2 / 26.4 / 49.8 |
| best deterministic + max-red: max_queue | 23.3 | ✓ | 15.1 / 27.0 / 46.1 | 38.8 / 76.5 / 101.5 | 16.2 / 26.4 / 49.8 |

### 4.2 Configuration A: round-2 winner with the fix (it19 seed 17, it48 seed 41; maps with a passing policy)


**cologne8_benchmark_v1**

| Controller | Score | Pass | balanced | directional_reversal | downstream_bottleneck |
|---|---|---|---|---|---|
| learned, seed 17 (selected ep 260) | 34.0 | ✓ | 29.6 / 29.3 / 32.4 | 34.1 / 35.6 / 41.3 | 38.4 / 29.4 / 34.4 |
| learned, seed 41 (selected ep 400) | 34.1 | ✓ | 29.7 / 29.5 / 41.1 | 33.5 / 34.8 / 46.9 | 39.0 / 31.0 / 39.5 |
| best deterministic: flow_theory | 34.5 | ✓ | 30.7 / 33.7 / 41.2 | 33.2 / 38.5 / 54.5 | 39.7 / 34.0 / 39.2 |
| best deterministic + max-red: flow_theory | 34.5 | ✓ | 30.7 / 33.7 / 41.2 | 33.0 / 38.3 / 50.0 | 39.7 / 34.0 / 39.2 |

**grid4x4_benchmark_v1**

| Controller | Score | Pass | balanced | directional_reversal | downstream_bottleneck |
|---|---|---|---|---|---|
| learned, seed 17 (selected ep 181) | 23.1 | ✓ | 22.1 / 42.7 / 85.5 | 23.6 / 46.1 / 89.3 | 23.6 / 42.9 / 86.3 |
| learned, seed 41 (selected ep 120) | 23.0 | ✓ | 22.1 / 43.5 / 103.2 | 23.4 / 46.2 / 102.6 | 23.5 / 43.7 / 90.2 |
| best deterministic: max_pressure | 20.1 | ✓ | 19.3 / 29.4 / 89.3 | 20.3 / 31.6 / 103.7 | 20.6 / 29.3 / 84.8 |
| best deterministic + max-red: max_pressure | 20.7 | ✓ | 19.9 / 31.1 / 115.1 | 21.2 / 34.2 / 117.6 | 21.0 / 30.2 / 110.1 |

**hanoi_dong_da_v1**

| Controller | Score | Pass | balanced | directional_reversal | downstream_bottleneck |
|---|---|---|---|---|---|
| learned, seed 17 (selected ep 260) | 31.0 | ✓ | 18.0 / 43.7 / 74.5 | 57.1 / 219.7 / 264.4 | 18.0 / 43.7 / 74.5 |
| learned, seed 41 (selected ep 200) | 30.2 | ✓ | 19.1 / 47.1 / 77.9 | 52.5 / 202.6 / 253.7 | 19.1 / 47.1 / 77.9 |
| best deterministic: fixed_time | 43.9 | ✓ | 26.2 / 52.0 / 84.3 | 79.2 / 257.1 / 366.2 | 26.2 / 52.0 / 84.3 |
| best deterministic + max-red: fair_cycle_native | 33.6 | ✓ | 22.4 / 49.9 / 68.8 | 55.9 / 171.4 / 225.9 | 22.4 / 49.9 / 68.8 |

**hcm_neighborhood_v3_benchmark_v1**

| Controller | Score | Pass | balanced | directional_reversal | downstream_bottleneck |
|---|---|---|---|---|---|
| learned, seed 17 (selected ep 280) | 72.7 | ✓ | 70.1 / 69.2 / 40.0 | 75.2 / 71.0 / 64.4 | 72.9 / 69.4 / 42.8 |
| learned, seed 41 (selected ep 160) | 73.4 | ✓ | 72.0 / 69.6 / 41.6 | 75.2 / 72.9 / 54.7 | 72.9 / 67.8 / 35.0 |
| best deterministic: max_pressure | 72.0 | ✓ | 70.6 / 69.4 / 47.6 | 74.5 / 76.6 / 84.6 | 71.0 / 66.2 / 41.6 |
| best deterministic + max-red: max_pressure | 72.2 | ✓ | 70.5 / 69.4 / 47.6 | 74.9 / 79.3 / 81.4 | 71.0 / 66.2 / 41.6 |

## 5. Reading the tables

- **Hanoi (C).** It beats native + max-red on mean delay in every case: 18.1–19.7 against 22.4 on balanced and bottleneck, and 48–55 against 55.9 on reversal. Its tails are mixed:
  - On reversal, the learner's p95 wait is 173–190 s against 171 s, and its worst-approach wait 216–236 s against 226 s.
  - On balanced and bottleneck, its worst-approach wait is 81–87 s against 69 s.
  - The guardrail compares tails with tuned Fixed-Time, so these pass. Still, the learner trades some tail for mean.
- **cologne.** Delay ties or narrowly beats flow_theory. Tails are clearly better: worst-approach wait is 30–34 s against 41 s on balanced, and 27–37 s against 39 s on bottleneck.
- **Jakarta (C).** It matches max_queue + max-red within 0.1–0.2 s on balanced and bottleneck. The whole gap is on directional_reversal: 39.6–40.1 against 38.8.
- **HCM.** Delay is about 1–2 s above max_pressure, and the tails are better (§4).

## 6. Caveats

1. **Selection on validation seeds.** Round 3 chose ideas, margins and checkpoints using the same five validation seeds. The three learner seeds reduce training noise, but they do not remove this selection effect. Test seeds remain the honest check.
2. **The wins depend on the hand-written base controllers** (flow_theory, max_pressure) and on the max-red envelope. The learned part is a residual, and running it requires the base controllers at inference time.
3. **The configurations trade maps against each other.** A is best for cologne, and C is best for grid4x4, Jakarta and Hanoi. No single configuration dominates.
4. **A's seed-29 run (it18) predates the R1 fix.** Its seed-17 rerun (it19) moved scores by at most 0.7 s, so this probably does not matter.

## 7. Decisions for you

1. **Open the test seeds** for configurations A and C, all three learner seeds. The Hanoi win, and whether cologne holds, are the claims to check.
2. **The max-red envelope blocks 4-node.** Keeping it means no controller of the residual family can pass that map. A per-map envelope, or a softer T, would need your decision, because it changes every baseline.
3. **Promote the residual?** The two-tier residual (`EDGEFLOW_RESIDUAL_BASE`, `EDGEFLOW_RESIDUAL_ALT`, `EDGEFLOW_MP_MARGIN`, `EDGEFLOW_ALT_MARGIN`) is env-gated experiment code. Making it a controller option touches the controller contract (H6).
4. **Score tails?** The score is mean delay only. On cologne and HCM, the learner's advantage is mostly in tails.
