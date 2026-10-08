# Shared Double DQN SUMO holdout report

## Decision

**Do not promote the shared DQN.** The validation-selected policy, `shared_dqn_seed43`, lowered equal-weight accrued delay on the independent holdout by 17.96% against EdgeFlow and 22.14% against Max-Pressure. Both paired 95% bootstrap intervals exclude zero, and the delay, throughput, and simulator-validity rules passed. The policy failed the fairness guardrail: P95 and worst-approach waiting exceeded the allowed regression in balanced and downstream-bottleneck demand. Keep the existing controller default.

## Evaluation design

The benchmark used the corrected `four_intersection_rl_v1` SUMO network, 1-second simulation steps, 5-second decisions, green bounds from 10 to 60 seconds, 3-second yellow, and 2-second all-red. Each case scheduled 1,800 seconds of demand and drained for 600 seconds. Delay includes SUMO time loss, departure delay, and waiting-to-enter delay for uninserted vehicles. Validation seeds selected the model and baseline; holdout seeds 40001 through 40010 were opened only after freezing that selection.

Network SHA-256: `5bb656220f6e1dc1376692e4c7a29628a9cdb2d2bad6ef7beb56757717fc3f84`
Topology SHA-256: `1ac5b46a0144711312f4af971b3284de94f74ee1cece126768f9a0e3e3a49b16`

## Holdout delay

Equal-weight average accrued delay per scheduled vehicle, seconds; each scenario averages the ten paired holdout seeds.

| Controller | Balanced | Directional surge | Downstream bottleneck | Equal-weight mean |
|---|---:|---:|---:|---:|
| fixed_time | 596.58 | 730.64 | 779.22 | 702.14 |
| actuated | 566.95 | 784.97 | 766.46 | 706.13 |
| max_queue | 838.02 | 932.82 | 971.88 | 914.24 |
| max_pressure | 835.26 | 937.44 | 970.43 | 914.37 |
| edgeflow | 775.67 | 911.69 | 916.11 | 867.82 |
| shared_dqn_seed17 | 649.76 | 725.23 | 782.97 | 719.32 |
| shared_dqn_seed29 | 649.31 | 721.31 | 775.93 | 715.52 |
| shared_dqn_seed43 | 649.84 | 713.47 | 772.51 | 711.94 |

All three learner seeds are shown. Seed 43 was selected using validation only; the other two learner seeds are reported for transparency.

## Fairness guardrail

Mean wait metrics in seconds. The gate permits a regression no larger than 10% or one second, whichever is greater.

| Scenario | Method | P95 wait | Worst-approach wait |
|---|---|---:|---:|
| balanced | DQN candidate | 1876.74 | 2003.55 |
| balanced | EdgeFlow | 1222.37 | 1314.63 |
| balanced | Max-Pressure | 1296.98 | 1384.19 |
| directional_surge | DQN candidate | 1207.76 | 1449.90 |
| directional_surge | EdgeFlow | 1618.67 | 1724.08 |
| directional_surge | Max-Pressure | 1662.32 | 1770.17 |
| downstream_bottleneck | DQN candidate | 1901.51 | 2046.43 |
| downstream_bottleneck | EdgeFlow | 1429.46 | 1607.27 |
| downstream_bottleneck | Max-Pressure | 1511.40 | 1681.31 |

The candidate exceeded the P95 and worst-approach thresholds against both comparison baselines in balanced and downstream-bottleneck demand. It passed those two checks in directional surge.

## Paired delay test

| Comparison | Relative delay improvement | Paired 95% interval (seconds) | Result |
|---|---:|---:|---|
| edgeflow | 17.96% | [152.68, 158.90] | Passed |
| max_pressure | 22.14% | [200.08, 204.11] | Passed |

The campaign completed 240 holdout cases: eight controllers, three demand scenarios, and ten seeds. All cases were valid, with zero collisions, teleports, or unexplained accounting losses. The candidate also completed at least 98% of the comparison baselines' trips. Promotion remains denied because of the fairness failures above.

## Training and artifacts

Three PyTorch learner seeds (17, 29, 43) trained on the local CUDA GPU using the configured 100,000 joint-decision and 7,200-second caps. Each reached the decision cap. The in-memory count reached 100,000 mid-episode; the last full learner checkpoint is episode 208 at 99,840 decisions. Each validation-selected policy export is from episode 20. The training loop stopped mid-episode at the decision cap. Export hashes match the selected training artifacts.

| Seed | Validation score | Selected policy export | Final learner checkpoint |
|---:|---:|---|---|
| 17 | 716.791 | [`models/shared_dqn_seed17.json`](../models/shared_dqn_seed17.json) | `artifacts/rl_training_run1/seed-17/checkpoint.pt` |
| 29 | 714.155 | [`models/shared_dqn_seed29.json`](../models/shared_dqn_seed29.json) | `artifacts/rl_training_run1/seed-29/checkpoint.pt` |
| 43 | 710.142 | [`models/shared_dqn_seed43.json`](../models/shared_dqn_seed43.json) | `artifacts/rl_training_run1/seed-43/checkpoint.pt` |

Frozen selection, full raw holdout metrics, promotion details, benchmark config, and training manifests are retained in [`reports/shared_dqn_holdout/`](../reports/shared_dqn_holdout/). The runner's original case traces and per-run outputs remain in the ignored `artifacts/rl_campaign/` tree.

## Reproduction

Use the dedicated `.venv-rl` environment and run:

```powershell
.venv-rl\Scripts\python.exe -m src.rl.campaign --config configs/rl/shared_dqn.json --training-root artifacts/rl_training_run1 --output artifacts/rl_campaign --max-seconds 7200
```

Campaign results are immutable and resumable by rerunning the same command with the same configuration. The captured final status is complete and not promoted.
