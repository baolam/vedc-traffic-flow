# Graph-MAPPO research protocol

`graph_mappo` uses two movement-aware graph-attention layers across J1–J4. `local_mappo` uses the same actor and centralized critic architecture, with self-relations only; its 52 local features retain the existing mapped downstream measurements. Both policies choose masked −5, 0, or +5 second NS residuals inside a 90-second cycle with a 25% minimum green share. EW receives the complementary adjustment. Existing 3-second yellow, 2-second all-red, minimum-green, and maximum-green safety rules remain active.

Graph, feature, timing, protocol, selection, and action metadata live in `contracts/research.py`. Exported actors use versioned JSON and NumPy-only inference. The critic and optimizer are training-only. Graph-control keeps its current deployment default.

## Setup

Install the research dependencies and use a local SUMO 1.25 installation:

```powershell
python -m pip install -e ".[research]"
```

Keep `sumo` available through the project's SUMO resolver and confirm the topology and network files in `configs/rl/graph_mappo_holdout.json` exist. Training uses 1,800 seconds of demand, a 600-second drain, zero wait penalty, and randomized demand intensity from 0.8 to 1.2.

## Ten-hour campaign

The checked-in campaign config runs the approved active-time schedule: 30 minutes of preflight, one hour for two seed-11 pilots, six hours for alternating graph/local runs at learner seeds 17, 29, and 43, then up to 2½ hours for validation selection and frozen holdout evaluation. Each main run is capped at one hour or 128 episodes. Both architectures use the normalized critic configs. The preflight freezes all seven baseline inputs, checks the matched fair-cycle validation cases, records SUMO and model hashes, and measures batched actor parity and throughput.

Start the campaign with:

```powershell
python -m src.rl.mappo_campaign run --config configs/rl/mappo_campaign.json --output artifacts/mappo/overnight
```

If the process is interrupted, resume the same output:

```powershell
python -m src.rl.mappo_campaign run --config configs/rl/mappo_campaign.json --output artifacts/mappo/overnight --resume
```

`campaign-state.json` records active elapsed budget, completed stages, run status, and remaining time. Training checkpoints are written after complete rollout updates; interrupted partial rollouts are discarded. Holdout stores each completed case atomically and resumes only with the same frozen actors, baselines, environment, and SUMO binary. A case cache hit requires matching protocol, implementation, environment, controller, model, package, and SUMO hashes.

The campaign freezes six validation-selected MAPPO actors and six latest-common-checkpoint actors for paired reporting. Holdout evaluates the six selected actors and seven frozen baselines on the ten holdout demand seeds across each primary scenario (390 cases, with at most two SUMO workers). The latest-common checkpoints are summarized from validation to show the effect of early selection. The report separates policy performance, graph contribution, and promotion status. Three learner seeds provide limited evidence about training variability. This protocol compares movement-aware communication with self-only communication; it does not compare road adjacency with all-to-all attention.

The existing `graph_mappo.json` and `local_mappo.json` retain the unnormalized critic for compatibility. The campaign deliberately selects the corresponding `*_normalized.json` configs for both pilots and main runs. Validation shares fair-cycle cases through the hash-checked cache. The deployment default remains unchanged.

## Verification

Run the repository contract and unit checks:

```powershell
python -m pytest tests/unit/test_contracts.py
python -m pytest tests/unit
```

Run real SUMO integration tests when the research dependencies are available:

```powershell
python -m pytest tests/integration
```

The tests cover canonical graph construction and ordering, masked PPO and elapsed-time GAE, graph/NumPy action parity, local-message isolation, call-order-independent inference, timing propagation, checkpoint resumption, zero-residual allocation parity, frozen baseline/actor rejection, paired promotion gates, and four-intersection clearance accounting.
