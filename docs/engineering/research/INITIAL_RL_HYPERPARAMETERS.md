# Initial RL hyperparameters and training protocol

Status: research recommendation, 2026-11-20. These are first configurations to freeze before training, not tuned results. No experiment or configuration change was made for this note. Values marked **proposal** are engineering judgments; citations establish provenance, not an assurance of convergence on all six maps.

## DQN evidence and algorithm identity

The [PressLight paper, sections 4 and 6](https://faculty.ist.psu.edu/jessieli/Publications/2019-KDD-presslight.pdf) motivates pressure reward and incoming/outgoing traffic state, and links the authors' implementation. Its coordination results do not establish universal optimizer settings for other maps, information sets, action spaces, or rewards. Using the project's agreed raw telemetry within two upstream/downstream hops is a deliberate observation adaptation; it must not be described as the original concise PressLight state.

The [author configuration](https://github.com/wingsweihua/presslight/blob/master/config.py) supplies the following defaults. They are repository defaults, not a verified immutable configuration for every published experiment; the generic environment defaults even contain a non-pressure reward, so a faithful reproduction also needs the actual experiment overrides.

| PressLight author-code setting | Value |
|---|---:|
| Learning rate | 0.001 |
| Discount | 0.8 per source decision |
| Replay memory | 10,000 samples |
| Samples selected per fitting round | 1,000 |
| Fitting minibatch | 20 |
| Maximum fitting epochs / fit patience | 100 / 10 |
| Hidden layers / width | 2 / 20 |
| Exploration | max(0.2, 0.8 × 0.95^round) |
| Target age | 5 training rounds in default lagged-round mode |
| Reward divisor | 20 |

The [author network](https://github.com/wingsweihua/presslight/blob/master/simple_dqn_agent.py) implements ReLU dense layers, a linear phase output, RMSprop and MSE. The [author learner](https://github.com/wingsweihua/presslight/blob/master/network_agent.py) uses the target network's maximum for its bootstrap, divides reward by the configured factor, and expresses epsilon and target age in rounds. Its fitting patience is supervised fit early stopping, not validation travel-time plateau detection. Do not translate five rounds into five gradient updates or call this source implementation Double DQN.

[Double DQN, equation 4 and supplementary hyperparameters](https://arxiv.org/pdf/1509.06461) separates online action selection from target-network evaluation. Its Atari baseline uses discount 0.99, RMSprop learning rate 0.00025, replay one million, minibatch 32, updates every four steps, and epsilon 1→0.1 over one million steps. Those are Atari settings, not traffic recommendations. Keep the selection/evaluation separation when calling a project controller Double DQN; using it for PressLight is a declared PressLight-inspired Double-DQN variant.

## Practical first DQN recipe

**Proposal:** retain the existing shared Double-DQN family's optimizer and small network as the project starting point for phase-selection variants, with cycle-specific overrides below. Keep each named controller's defining state, reward and action semantics. The existing PressLight-inspired Double-DQN variant remains a project variant in the results; an exact author-style PressLight reproduction would require the separate source recipe above and is not silently substituted.

| Setting | First project recipe | Provenance / unit |
|---|---|---|
| Shared network | one hidden layer, 64 ReLU units | existing project; scalar candidate scorer or legal-action outputs as appropriate |
| Optimizer | Adam, learning rate 0.0003 | existing project |
| Loss / gradient norm cap | Huber / 10 | existing project |
| Replay / minibatch | 200,000 / 256 | existing project; per-node transitions |
| Learning starts | 5,000 replay transitions and at least one complete episode per training demand case | existing shared threshold plus proposed coverage condition |
| Update frequency | one minibatch per four joint network decisions | existing shared learner default; proposal for first generalized family |
| Target update | hard copy every 1,000 optimizer updates | existing shared learner; explicitly gradient-update units |
| Exploration | epsilon 1→0.05 linearly over 125,000 accumulated simulated network-seconds, then 0.05 | proposal; equivalent to existing 25,000 decisions only at five seconds/decision; sample legal actions uniformly |
| Evaluation exploration | epsilon 0 | proposal; deterministic legal-action tie rule |
| Discount | 0.99 per 5 simulated seconds | existing physical-time convention; use elapsed-time conversion below |

Local evidence: [shared learner](../../../src/rl/shared_dqn.py), [shared trainer](../../../src/rl/train_shared.py), [shared config](../../../configs/rl/shared_dqn.json). The existing fair-cycle config instead uses learning-starts 1,024, updates each joint decision, target copies each 200 updates and epsilon decay over 1,786 decisions. These are historical project choices, not PressLight constants or evidence that shorter fair-cycle training is sufficient. Freeze one declared recipe for the generalized implementation before seeing validation outcomes; do not sweep these alternatives.

For the **cycle-residual DQN**, retain learning-starts 1,024 plus the coverage condition, one optimizer step per completed joint cycle decision, and target copies every 200 optimizer steps. Retain its existing wait-penalty coefficient 0.5 as the first recipe. Use the same physically timed exploration decay: 1,786 original 70-second decisions cover approximately 125,000 simulated seconds. Do not apply the phase-selection four-decision update interval and 1,000-update target interval blindly to whole cycles; doing so would drastically reduce learning and target refresh per simulated hour. These are separate first recipes, not a demand for equal training exposure.

The [current benchmark trainer](../../../src/benchmark/train.py) is another variant: 12-input scalar phase scorer, learning starts at 256 samples, updates each joint decision, target copies each 1,000 joint decisions, and final-training-checkpoint export. Its [phase observation](../../../src/control/phase_dqn.py) contains derived local/downstream features. It does not yet implement the agreed raw two-hop observation or validation-selected five-seed study. Existing execution is therefore not evidence that the proposed protocol is already implemented.

## Physical time and variable actions

**Proposal / mathematical consequence:** define a reference interval δ=5 seconds and gamma_5=0.99. For a transition lasting Δt seconds, bootstrap with `gamma_5 ** (Δt / 5)`. For subinterval rewards use `R = sum_k gamma_5 ** ((t_k-t_start)/5) * r_k`; each `r_k` must represent a declared cost integral over that subinterval, with consistent reward units and scale. Include clearance time. Do not merely use the last snapshot reward or an unweighted cycle mean when claiming the same objective across durations.

For a 70-second transition the multiplier is approximately 0.869, versus 0.99 for five seconds. The 0.99 convention has an exponential time constant of approximately 497.5 seconds. PressLight's source gamma 0.8 at its default 10-second decision interval would imply gamma_5≈0.894 and a much shorter time constant, approximately 44.8 seconds. Thus the project horizon is an explicit change, not a direct paper value. This conversion is derived from exponential discounting, not a reported PressLight experiment.

Duration-dependent discounting follows the semi-Markov treatment of temporally extended actions; the choice of 0.99 and the five-second reference interval here comes from this project. [Sutton, Precup and Singh, technical report](https://web.cs.umass.edu/publication/docs/1998/UM-CS-1998-074.pdf)

For P native phases, a fair residual action is a feasible ordered donor→recipient transfer of exactly five green seconds, plus no-op: at most `P*(P-1)+1` choices before masking. Preserve the heuristic base plan and feasibility constraints. A fixed three-output NS/EW head cannot express this action space. Use a shared candidate scorer or padded masked outputs; sample epsilon actions only among feasible candidates. This is a proposed generalization, not an optimizer hyperparameter or a source-paper claim.

## Count exposure before interpreting convergence

One completed network step is one **joint decision**; with N active node agents it normally contributes N replay transitions. Score rows for multiple candidate phases are not independent environment transitions. Two workers each completing a step contribute two joint decisions. Report simulated network-hours, joint decisions, replay insertions, optimizer updates, and complete episodes per map/case separately. Equal replay size across maps does not imply equal simulated exposure.

**Proposed DQN stopping rule, to preregister rather than tune:** validate deterministic policies every 20 complete training episodes using the same fixed validation cases and demand seeds. Allow stopping only after 250,000 accumulated simulated network-seconds, 100 complete episodes, every training case at least ten times, and the exploration decay has finished. Keep the checkpoint with the best prespecified equal-case validation score subject to the existing feasibility/accounting gates. Stop after ten consecutive validation checks without at least 1% relative improvement against the patience anchor; smaller improvements may still replace the selected best checkpoint but do not reset patience. Use an explicit near-zero score floor when calculating relative improvement.

Use an initial hard cap of 2,500,000 accumulated simulated network-seconds per map/training seed, with a separately declared operational time cap; hitting either before plateau is **budget-limited**, not converged. These numbers are practical proposals, not paper-backed optimum exposure. Count one simulated second once per network rollout, not once per node; sum independent workers' elapsed simulated seconds. At five seconds/decision the proposed minimum and cap correspond to 50,000 and 500,000 joint decisions; 70-second cycle transitions instead yield approximately 3,572 and 35,715 decisions. Record optimizer updates too, since the latter can still be undertrained despite equal simulated exposure. No equal training-time or sample budget is required between DQN and MAPPO. A plateau is a reproducible stopping criterion, not proof of optimality.

## Practical first Graph/Local MAPPO recipe

The [MAPPO paper, sections 5.1–5.5 and appendix C.4](https://arxiv.org/html/2103.01955v4) supports value normalization, centralized value information and restrained policy-data reuse. It reports five or ten epochs on harder tasks and usually one unsplit training batch. Its game-domain results guide a traffic starting point; they do not establish optimal traffic parameters. The [official configuration parser](https://raw.githubusercontent.com/marlbenchmark/on-policy/main/onpolicy/config.py) supplies common defaults including actor/critic learning rates 0.0005, PPO clip 0.2, entropy 0.01, gamma 0.99 and GAE lambda 0.95. Read executable defaults rather than help strings: that file's gradient-norm default is 10 and value coefficient 1, despite help strings saying 0.5.

**Proposal:** use the same optimization recipe for Graph and Local MAPPO. Preserve their declared communication difference and use the agreed global critic only during training. Values inherited from the project refer to [the normalized graph configuration](../../../configs/rl/graph_mappo_normalized.json) and [the updater](../../../src/rl/graph_mappo.py).

| Setting | First recipe | Provenance / unit |
|---|---|---|
| Actor/critic optimizer | Adam, learning rate 0.0003 each | retain project values; deliberate deviation from official 0.0005 |
| Hidden width | 64 | retain project; node count does not set width |
| Graph actor | two attention layers, four heads | retain project depth; enforce the agreed raw-telemetry two-hop boundary |
| Local actor | self-only communication ablation | remove neighbor-derived inputs as needed to make the ablation genuinely local |
| PPO clipping / entropy / value coefficient | 0.2 / 0.01 / 0.5 | retain project, not an exact official recipe |
| Update epochs | 5 | proposed low-reuse starting point guided by paper; existing project uses 4 |
| Training batch | one complete rollout batch per epoch | proposed paper-guided choice; existing project splits into minibatches of 32 joint transitions |
| Rollout collection | two SUMO workers, four complete episodes each | retain project; eight episodes per update, including all active nodes |
| Value normalization | enabled; retain running-value normalizer | project implementation is not claimed to be exact PopArt |
| Gradient cap / target KL | 0.5 / 0.03 | retain project; KL threshold limits actor updates, not whole-training convergence |
| Gamma | 0.99 per five simulated seconds | duration-adjusted bootstrap and reward integration as above |
| GAE lambda | 0.95 per five simulated seconds | proposal: elapsed-time trace factor `0.95 ** (delta_t / 5)`; derive advantages with recorded transition durations |
| Wait penalty | 0 | retain normalized MAPPO config; keep recorded reward definition |

Whole-rollout batching, physical-time GAE and variable phase actions require implementation changes; these settings are not a runnable patch to the existing frozen four-node protocol. A full-batch memory check belongs to the implementation smoke check. Do not split individual node rows in a way that destroys the joint graph snapshot used by the centralized critic.

**Proposed MAPPO stopping recipe:** validate after every 16 complete episodes, retain eight-episode update boundaries, allow plateau stopping after at least 64 complete episodes and ten exposures to each training demand case. Use five consecutive validation checks without at least 1% improvement against the patience anchor, with the same feasible-checkpoint ranking and small-improvement checkpoint retention as DQN. Initial episode safety cap: 512, plus a separately declared operational limit. These are operational first choices, not claims of known convergence speed. A capped run remains budget-limited. The DQN and MAPPO minima and caps intentionally differ.

## Accepted campaign design and reporting

The user accepted all algorithms on all six maps, shared weights with separate node observations/actions, upstream/downstream raw-telemetry access within two hops for algorithms that use communication, native map phases, five independent whole-system training runs, and ten matched held-out demand seeds. Local-only ablations retain their declared information restriction. Global critic information is allowed only during training. Fair-cycle residual actions transfer five seconds between legal phase pairs, plus no-op.

Each training run selects its own validation checkpoint using lowest equal-case mean delay subject to safety, completion and waiting-tail guardrails. Test demand seeds must remain untouched during training, early stopping and checkpoint selection. Keep all five training runs in the final aggregate; do not choose a winning training seed. The user explicitly wants the final report after **all five runs reach their stopping criteria**, and does not want an additional hyperparameter-search campaign.

**Proposed reporting detail:** for each map/case and training seed, average the ten test-demand results, then report the mean and standard deviation across the five training-seed means, alongside the five individual values. Preserve both seed axes in raw results. Use interval estimates that reflect training-seed variability and paired demand seeds; 50 evaluations of five policies are not 50 independent trained policies. The [RL evaluation paper](https://arxiv.org/abs/2108.13264) motivates reporting uncertainty when only a few training runs are available; this nested protocol is our study design, not a copied paper formula. Report model-free controllers once on the ten matching demand seeds rather than inventing five training replicas.

Do not pool raw delay across differently sized maps to produce a universal winner. Report map/case results first, then an explicitly defined equal-map aggregate of baseline-relative performance if needed. Publish learned-model learning curves, stopping reason, selected-checkpoint exposure, total compute, failures and missing results. A plateau is not proof of an optimum; the claim supported by this study is expected performance of validation-selected policies under a declared, literature-informed first recipe.

## Work still needed before execution

Only this research note has been added. No production configuration, contract, trainer or benchmark was changed. The existing variable-phase observations, graph batching, learner-seed orchestration, cycle feasibility, checkpoint selection, stopping logic and prepared-map integration still need to be implemented and verified under one campaign command. The inventory documents current prerequisites separately in [CURRENT_ALGORITHMS_AND_BENCHMARKS.md](CURRENT_ALGORITHMS_AND_BENCHMARKS.md).

Operational values above remain proposed until the end of the grilling session is confirmed. In particular, multiphase cycle length must include green-allocation slack: an eight-phase 120-second cycle gives every phase exactly its ten-second minimum and leaves no legal transfer.

**Proposed first cycle rule:** for P native phases at a node, use `max(70, 25*P)` seconds, including five seconds of clearance per phase, with an absolute ten-second minimum and sixty-second maximum green per phase. Allocate the remaining green by the controller's declared demand/wait-aware rule, quantize to five seconds and preserve the exact total budget. This gives 70 seconds for two phases and 200 for eight, retaining allocation slack. Twenty seconds green plus five clearance per phase is one of the existing fixed-time candidate settings; the max-with-70 rule and absolute minimum are our generalized first choice, not a literature-optimal cycle or a copy of the old two-phase minimum-share contract. The baseline Fair-Cycle, residual DQN and both MAPPO variants use the same cycle rule. Preserve valid native phase transitions and reject topologies whose clearance requirements cannot satisfy the declared timing. [existing timing candidates](../../../src/benchmark/campaign.py)

**Concrete implementation scope for final confirmation:** update controller observations/actions and inference in `src/control/`; preserve distinct learning methods while adding a common campaign interface, validation checkpoint selection and stopping in `src/rl/` and `src/benchmark/`; version canonical artifact/protocol contracts in `contracts/`; update only related campaign configs and tests. Use prepared inputs for all six maps, configurable five-seed training, deterministic ten-seed evaluation, resumable artifacts and hierarchical reporting. Keep old frozen protocols/artifacts identifiable rather than treating a generalized model as compatible with its predecessor. Run contract and unit checks plus real-SUMO tests for arbitrary phase counts, legal transfers, observation radius and learned-policy execution before starting the full campaign.

Reward/state changes and generalized action semantics must be versioned in model artifacts and labelled in algorithm names. No hyperparameter search or full benchmark was run.
