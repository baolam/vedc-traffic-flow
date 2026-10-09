# Corrected SUMO holdout comparison

Candidate: fair_cycle_rl_seed43
Promotion gate passed: False. Existing deployment default is unchanged.

| Controller | Delay / scheduled vehicle (s) | Completed trips | P95 wait (s) |
|---|---:|---:|---:|
| fixed_time | 697.813 | 3717.7 | 1486.915 |
| actuated | 700.618 | 3775.0 | 1203.058 |
| max_queue | 909.110 | 2816.1 | 1482.245 |
| max_pressure | 903.323 | 2836.3 | 1478.192 |
| edgeflow | 864.587 | 3027.1 | 1418.291 |
| fair_cycle | 681.270 | 3915.0 | 1125.481 |
| shared_dqn_seed17 | 714.399 | 3562.7 | 1651.238 |
| fair_cycle_rl_seed17 | 710.882 | 3715.0 | 1196.559 |
| shared_dqn_seed29 | 710.959 | 3548.5 | 1650.160 |
| fair_cycle_rl_seed29 | 711.996 | 3706.3 | 1211.482 |
| shared_dqn_seed43 | 707.594 | 3572.5 | 1658.397 |
| fair_cycle_rl_seed43 | 712.227 | 3712.1 | 1207.559 |

Supplemental mirrored-direction results: [robustness.json](robustness.json).

Evidence: [frozen selection](frozen.json), [raw metrics](results.json), [promotion tests](promotion.json), [configuration](config.json).

actuated/balanced: delay regression >5%
actuated/balanced: throughput <98%
actuated/downstream_bottleneck: throughput <98%
fixed_time/directional_surge: throughput <98%
fixed_time/downstream_bottleneck: throughput <98%
fixed_time: overall delay regression exceeds 2%
