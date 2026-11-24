# RL Research Loop (1-hour iterations)

**Goal:** a learned controller that passes the guardrail and scores below the best passing deterministic controller on at least one map. The target is all six maps.
**Baseline:** phase DQN with the per-node reward and tail term (E6 in [the 2026-11-22 report](../../reports/RL_ENVIRONMENT_DESIGN_REPORT_20261122.md)).
**Driver:** `run.sh` (train) and `score.py` (verdict, ledger). Both use the existing campaign CLI and change nothing in `src/`.

## Targets (validation seeds, from `comparison.json`)

| Map | Best passing deterministic | E6 seed 17 | Gap |
|---|---|---|---|
| cologne | flow_theory 34.5 | 38.0 ✗ (one tail fails by ~2.6 s) | feasibility, then 3.5 s |
| Jakarta | max_pressure 31.9 | 40.4 ✓ | 8.5 s (all in directional_reversal) |
| HCM | max_pressure 72.0 | 89.2 ✓ | 17 s |
| grid4x4 | max_pressure 20.1 | 24.7 ✓ | 4.6 s |
| Hanoi | fair_cycle_native 30.6 | 47.7 ✗ | 17 s (pressure family gridlocks here) |
| 4-node | actuated 68.7 | 120.4 ✗ | 52 s (oversaturated case, completion < 98 %) |

## One iteration (60 min)

| Min | Step | Command |
|---|---|---|
| 0–10 | Choose the top open hypothesis from the backlog. Implement it as **one env-gated change** (default off, so the baseline is unchanged). Run `make contracts` and the unit tests the change touches. | — |
| 10–55 | Train all six maps in parallel: 6 jobs, CPU, 40 min wall limit plus a final validation. | `EDGEFLOW_<GATE>=… docs/engineering/research/rl_loop/run.sh itNN` |
| 55–60 | Score the run, record it in the ledger, then keep or revert the change. | `python docs/engineering/research/rl_loop/score.py itNN "<hypothesis>" --record` |

**Loop recipe:** `loop_dqn_recipe_v2` = DQN recipe v3 with `min_episodes 80, min_sim_s 0, validate_every 20, patience 8` (at least about 240 episodes; validation from episode 80 keeps the early DQN peak visible). Version 1 (`min_episodes 80, patience 4`) ended every map within 7–25 min. Maps with no passing checkpoint stopped at about episode 160 while still improving (Jakarta 58.8 → 43.4), so it00 was rerun as it00b under v2. The campaign's 400-episode warmup hides phase DQN's early peak (episodes 60–120). In-training validation already uses the validation seeds and the guardrail against tuned Fixed-Time, so the selected score in `result.json` compares directly with the deterministic table. No separate evaluation pass is needed.

**Panel:** all six maps, trained as 6 parallel jobs (user decision, 2026-11-24). The Jakarta and Hanoi OSM networks were re-downloaded on 2026-11-24 because the frozen originals were deleted with `artifacts/benchmarks/development`. Their topologies match the committed contracts, but the networks differ, so both maps were recalibrated with new workloads, references and deterministic baselines. Their targets come from `targets.json`, not from the report. The old data is in `artifacts/benchmarks/unified-v1/archive-osm-20261120/`. cologne, grid4x4 and 4-node were regenerated from committed sources and verified byte-identical.

## Decision rules

- **KEEP** when at least one panel map improves by ≥ 3 s (the single-seed noise floor) or becomes feasible, and no map loses feasibility. Otherwise **DISCARD**: `git revert` the change. The ledger keeps the commit hash, so the idea can be recovered. Kept changes stack: the next iteration runs with their gates on.
- **WIN** on a map: feasible, and the score is below the target. A win triggers a **confirmation iteration** in the next slot, rerunning the same gates with `SEED=29`. A win counts only when both seeds hold.
- **Promotion:** after two KEEPs, or any confirmed WIN, run grid4x4, Hanoi and 4-node with all kept gates on (`run.sh itNN grid4x4_benchmark_v1 hanoi_dong_da_v1 four_intersection_rl_v1`, one slot).
- **Stop and report to the user:** after a confirmed WIN on 2 or more maps, after 6 straight DISCARDs, or after 12 iterations. The report shows per-case metrics for every map, using `scripts/pc_dqn.py` on the kept policies.
- **Test seeds stay closed.** Every loop decision uses validation seeds, so repeated selection overfits them. Only the final candidate is opened on test seeds, and only with the user's approval.

## Hypothesis backlog (in priority order)

Each entry gives its mechanism and the failure it targets in the report.

| # | Hypothesis | Gate (proposed) | Why it should help | Size |
|---|---|---|---|---|
| H1 | **Max-red mask.** When an approach's oldest wait exceeds T (60/90 s), `phase_mask` allows only the phases that serve it. | `EDGEFLOW_MAX_RED=90` | Guardrail failures are tail failures: cologne misses by 2.6 s, and Hanoi and 4-node fail on worst-approach wait. A hard rule fixes tails without relying on reward. | ~10 lines in `phase_mask` |
| H2 | **Max-pressure-guided exploration.** Exploratory actions follow max_pressure's choice instead of a uniform random phase (with probability p, decaying). | `EDGEFLOW_MP_EXPLORE=0.5` | max_pressure leads on HCM, Jakarta and grid4x4. DQN's replay rarely contains its good trajectories. This adds them at zero inference cost. | ~15 lines in `phase_episode` |
| H3 | **Pressure term in the node reward:** reward −= β·|in − out| per node. | `EDGEFLOW_PRESSURE_BETA=0.1` | Gives the learner max_pressure's signal as shaping. | ~10 lines next to E6's reward |
| H4 | **Lower learning rate.** | `--recipe` `lr: 1e-4` | Q overestimation is suspected: phase DQN degrades after its peak. | 0 lines |
| H5 | **Tail sweep:** λ ∈ {0.1, 0.2}, T ∈ {45, 90}. | `EDGEFLOW_TAIL=` | E6 used a single setting that was never tuned. | 0 lines |
| H6 | **Max-pressure residual action:** an extra action "do what max_pressure does". | `EDGEFLOW_MP_ACTION=1` | The policy can match max_pressure in one action and learn only the exceptions, such as Hanoi's gridlock states. | bigger: needs the action head size, so it is a contract question; ask first |

Zero-code entries (H4, H5) can share a slot with a code hypothesis when CPU allows. The machine runs 3 jobs safely (6 crashed it twice), so a shared slot means 2 panel maps each. Add new hypotheses only with the report evidence that motivates them.

## Iteration 0 (baseline)

1. Commit patch A (`../../reports/rl_environment_design_20261122/patches/exp-a-…patch`). It applies cleanly to `4b2c5a8`, and all its gates default off. E6 needs it.
2. Run `run.sh it00`, then `score.py it00 "E6 baseline, loop recipe" --record`. The first ledger row is the BASE every later iteration is compared against, because the loop recipe differs from the campaign recipe.
3. Use the measured per-map wall time to check the 40 min budget, and adjust the panel or `--wall-limit-s` if a map does not reach its first validation plateau.

## Running it unattended

Claude can drive the loop with `/loop` in dynamic mode, waking once per iteration (`ScheduleWakeup` about 3000 s after launch). Each wake reads `ledger.jsonl`, scores the finished run, keeps or reverts, implements the next hypothesis and launches it. Run artifacts go to `artifacts/benchmarks/rl-loop/<iter>/` (gitignored). The ledger is committed.

## Status (2026-11-24)

The first 8 iterations are done. Results and the ablation are in [`RL_RESEARCH_LOOP_REPORT_20261124.md`](../../reports/RL_RESEARCH_LOOP_REPORT_20261124.md). The learned wins on Jakarta and Hanoi come from the max-red envelope: deterministic controllers given the same envelope match or beat them.

## Round 2 (it08–it19, started 2026-11-24)

- **Fair targets.** `targets.json` now holds, for each map, the best passing deterministic score with or without the max-red envelope. The user kept max-red (T = 40 s, outside waits counted) as part of the envelope. A WIN now means beating deterministic controllers that use the same envelope.
- **Base.** Every run keeps `EDGEFLOW_MAX_RED=40 EDGEFLOW_MAX_RED_EXTERNAL=1 EDGEFLOW_MP_EXPLORE=0.5 EDGEFLOW_PRESSURE_BETA=0.5`, and the KEEP/DISCARD verdict is measured against it05 (seed 17). T stays at 40 s: tuning it for the learner alone would be unfair.
- **H6-lite (`EDGEFLOW_MP_MARGIN=δ`).** A max_pressure residual with no contract change. The learner follows max_pressure's phase unless its best legal Q beats max_pressure's phase by δ·|Q|. The same rule applies to training's greedy actions and to controller inference.
- **Confirmation batching (round 2).** Small single-seed WINs are not confirmed one by one. The best configuration gets seed 29 in the final slots (it18–it19) instead, because 12 slots cannot pay for a confirmation after every WIN.
- **Consistent-direction KEEP (round 2).** A change is also kept when it improves every map that has a passing score on both sides (at least 3 maps) and no map loses the guardrail. That is a sign test, p ≈ 0.03 for 5 out of 5 maps. it09 was kept under this rule.
