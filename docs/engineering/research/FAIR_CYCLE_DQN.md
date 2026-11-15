# Fair-cycle DQN research track

The first shared DQN improved mean delay against EdgeFlow and Max-Pressure on its holdout, but failed the P95 and worst-approach wait limits. In balanced demand it gave NS 1,801 green seconds and EW 300. Actuated also had better overall delay and P95. The next research controller therefore starts with a wait-aware cycle and lets one shared DQN adjust its NS/EW green split by at most five seconds.

`fair_cycle` evaluates cycle lengths 50, 70 and 90 seconds, with minimum green shares of 25% or one-third. It allocates remaining green according to local queues, due-but-uninserted demand, accumulated waits and mapped downstream occupancy. Both phases receive service every cycle. Yellow and all-red remain the existing three and two seconds. The 70-second cycle with one-third minimum share is the default for `fair_cycle_dqn`.

The learned action is `-5`, `0` or `+5` seconds for NS; EW receives the complementary adjustment. The action mask always allows zero and blocks splits outside the feasible cycle limits. Training and inference use `fair_cycle_dqn_v1` features and the `fair_cycle_dqn_model` artifact contract. The model is incompatible with the prior `shared_dqn_v1` feature contract; the old controller and artifacts remain available as the comparison method.

The simulator publishes optional per-approach current stopped wait and due entry-backlog metrics. The model requires these fields from simulation telemetry. Physical or vision sources that do not provide them cannot run this research controller. Metrics version 2 reports vehicle P95 wait, per-approach P95, maximum approach wait including entry delay, completed and unfinished trips, and actual green and clearance seconds. The legacy approach-wait maximum is retained under `legacy_worst_approach_wait_s`.

## Training and evaluation

The fair-cycle training config uses two SUMO workers, a 64-unit DQN, replay capacity 200,000, batch size 256, 1,024 transitions before learning, one update per joint cycle, and a two-hour cap per seed. A 70-second cycle decision discounts each five-second reward interval by `0.99` and uses the matching elapsed-time discount for the bootstrap target. The known 2,400-second horizon is observed and treated as terminal.

Pilot each reward weight with the same pilot seed and a 20-minute cap:

```powershell
python -m src.rl.train_shared --config configs/rl/fair_cycle_dqn.json --output artifacts/fair-pilots/lambda-0 --seed 11 --wait-penalty-lambda 0 --max-seconds 1200
python -m src.rl.train_shared --config configs/rl/fair_cycle_dqn.json --output artifacts/fair-pilots/lambda-0_5 --seed 11 --wait-penalty-lambda 0.5 --max-seconds 1200
python -m src.rl.train_shared --config configs/rl/fair_cycle_dqn.json --output artifacts/fair-pilots/lambda-2 --seed 11 --wait-penalty-lambda 2 --max-seconds 1200
```

Each validation record stores scenario-level delay, throughput, network P95, approach P95 and maximum wait. Select the pilot with the smallest normalized validation-gate violation, then the lowest equal-weight delay:

```powershell
python -m src.rl.select_fair_cycle_pilot --config configs/rl/shared_dqn.json --pilot-root artifacts/fair-pilots --output reports/fair_cycle_pilot_selection
```

Use `selected_lambda` from `selection.json` for the final three runs. The campaign selects each seed’s checkpoint by the same validation constraints before it freezes the candidate.

Train the three release seeds sequentially with the selected configuration:

```powershell
python -m src.rl.train_shared --config configs/rl/fair_cycle_dqn.json --output artifacts/fair-cycle-final-training/seed-17 --wait-penalty-lambda 0 --seed 17
python -m src.rl.train_shared --config configs/rl/fair_cycle_dqn.json --output artifacts/fair-cycle-final-training/seed-29 --wait-penalty-lambda 0 --seed 29
python -m src.rl.train_shared --config configs/rl/fair_cycle_dqn.json --output artifacts/fair-cycle-final-training/seed-43 --wait-penalty-lambda 0 --seed 43
```

Run the validation-freeze and holdout campaign with a new output directory. The previous 40001–40010 holdout is regression data; the new holdout is 50001–50010. The campaign also records an EW-oriented surge as supplemental robustness results, outside the three-scenario promotion aggregate:

```powershell
python -m src.rl.campaign --config configs/rl/shared_dqn.json --training-root artifacts/rl_training_run1 --fair-training-root artifacts/fair-cycle-final-training --output reports/fair_cycle_dqn_final --max-seconds 7200
```

The existing three shared-DQN runs are retained as reference controllers. The fair-cycle policy is promoted only if it clears the original EdgeFlow and Max-Pressure gates and the added Actuated and tuned Fixed-Time constraints. If no policy passes, the campaign reports the evidence and leaves the deployment default unchanged.

## Completed run and promotion status

The completed campaign froze `fair_cycle_rl_seed43` using validation results, then evaluated 12 controllers on 10 paired holdout seeds across balanced, directional-surge, and downstream-bottleneck demand. All 360 primary cases and 120 supplemental east-west-surge cases completed. The simulator reported no invalid cases, collisions, teleports, or vehicle-accounting losses.

The candidate's equal-weight accrued delay was 712.2 seconds per scheduled vehicle. It improved delay by 17.6% against EdgeFlow (paired 95% interval: 146.7 to 158.0 seconds) and 21.2% against Max-Pressure (187.5 to 194.9 seconds). Overall P95 wait was 1,207.6 seconds, compared with 1,418.3 for EdgeFlow and 1,478.2 for Max-Pressure. P95 improved against both required baselines and stayed within the wait guardrail against the other comparisons.

**Promotion was denied.** Against Actuated in balanced demand, candidate delay regressed 5.77% and completed trips reached only 96.29% of baseline. Completed trips were also below 98% of tuned Fixed-Time in directional-surge and downstream-bottleneck demand. The candidate therefore remains a research controller and the deployment default is unchanged. The supplemental east-west-surge results also show that the shared DQN without its fair-cycle envelope is brittle under mirrored directional demand; the fair-cycle RL candidate remained substantially more stable.

The full evidence is in [`reports/fair_cycle_dqn_final/report.md`](../reports/fair_cycle_dqn_final/report.md), with frozen selection, raw primary and supplemental metrics, paired promotion calculations, and the exact configuration alongside it.
