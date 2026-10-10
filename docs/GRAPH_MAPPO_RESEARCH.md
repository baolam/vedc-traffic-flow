# Graph-MAPPO research protocol

`graph_mappo` uses two movement-aware graph-attention layers across J1–J4. `local_mappo` uses the same actor and centralized critic weights, with self-relations only; its 52 local features still include the existing mapped downstream measurements. Both policies choose masked `−5`, `0`, or `+5` second NS residuals inside a 90-second cycle with a 25% minimum green share. The EW allocation receives the complementary adjustment. The existing 3-second yellow, 2-second all-red, minimum-green, and maximum-green safety envelope remains active.

The graph, feature, timing, protocol, and action metadata live in `contracts/research.py`. Exported actors use a versioned JSON format and NumPy-only runtime inference. The critic and optimizer state are training checkpoints only. Graph-control keeps its current deployment default.

## Setup

Use the project's research dependencies and a local SUMO 1.25 installation:

```powershell
python -m pip install -e ".[research]"
```

Make sure `sumo` is on `PATH` and the SUMO network contract at `networks/four_intersection_rl_v1/network.net.xml` is present. The configs use 1,800 seconds of demand, a 600-second drain, zero wait penalty, and randomized training intensity from 0.8 to 1.2.

## Run order

Run 30-minute pilots with learner seed 11, then alternate graph and local runs for learner seeds 17, 29, and 43. Each main run stops at one hour or 128 completed episodes. The trainer validates every 16 episodes and saves an atomic checkpoint after each completed rollout update. An interrupted partial rollout is discarded.

The critic-normalization pilot compares graph and local actors against their original unnormalized configurations:

```powershell
python -m src.rl.train_mappo --config configs/rl/graph_mappo.json --output artifacts/mappo/pilot-baseline-graph --seed 11 --max-seconds 1800
python -m src.rl.train_mappo --config configs/rl/local_mappo.json --output artifacts/mappo/pilot-baseline-local --seed 11 --max-seconds 1800
python -m src.rl.train_mappo --config configs/rl/graph_mappo_normalized.json --output artifacts/mappo/pilot-normalized-graph --seed 11 --max-seconds 1800
python -m src.rl.train_mappo --config configs/rl/local_mappo_normalized.json --output artifacts/mappo/pilot-normalized-local --seed 11 --max-seconds 1800
```

These four pilots fit a two-hour budget. They are diagnostic runs; compare common validated episode counts and do not use their seed-11 results as promotion evidence.

```powershell
python -m src.rl.train_mappo --config configs/rl/graph_mappo.json --output artifacts/mappo/pilot-graph --seed 11 --max-seconds 1800
python -m src.rl.train_mappo --config configs/rl/local_mappo.json --output artifacts/mappo/pilot-local --seed 11 --max-seconds 1800

python -m src.rl.train_mappo --config configs/rl/graph_mappo.json --output artifacts/mappo/graph --seed 17
python -m src.rl.train_mappo --config configs/rl/local_mappo.json --output artifacts/mappo/local --seed 17
python -m src.rl.train_mappo --config configs/rl/graph_mappo.json --output artifacts/mappo/graph --seed 29
python -m src.rl.train_mappo --config configs/rl/local_mappo.json --output artifacts/mappo/local --seed 29
python -m src.rl.train_mappo --config configs/rl/graph_mappo.json --output artifacts/mappo/graph --seed 43
python -m src.rl.train_mappo --config configs/rl/local_mappo.json --output artifacts/mappo/local --seed 43
```

Resume an interrupted learner from its last complete update, keeping its original config and seed:

```powershell
python -m src.rl.train_mappo --config configs/rl/graph_mappo.json --output artifacts/mappo/graph --seed 17 --resume artifacts/mappo/graph/seed-17/checkpoint.pt
```

After training, freeze six validation-selected actors. Selection is restricted to episode counts validated by both architectures for each learner pair. The latest common checkpoint metrics are retained alongside the selected checkpoints.

```powershell
python -m src.rl.mappo_campaign freeze --graph-training-root artifacts/mappo/graph --local-training-root artifacts/mappo/local --output artifacts/mappo/frozen
```

Run the new holdout matrix only after freezing. The checked-in holdout config contains the matched 90-second fair-cycle heuristic, the previously selected fair-cycle DQN, and the frozen Fixed-Time, Actuated, Max-Queue, Max-Pressure, and EdgeFlow baseline settings.

```powershell
python -m src.rl.mappo_campaign holdout --config configs/rl/graph_mappo_holdout.json --frozen artifacts/mappo/frozen/frozen.json --output artifacts/mappo/holdout --max-seconds 9000
```

The holdout command writes `status.json` and preserves completed cases. After an interruption, rerun the same command with `--resume`; it requires the same config and frozen selection. A case is reused only when protocol, implementation, environment, controller, and model hashes match. `report.md` separates policy performance, graph contribution, and each policy's promotion gate. Three learner seeds provide limited evidence about training variability. This protocol compares mapped road communication with self-only communication; it does not compare road adjacency with all-to-all attention.

The original `graph_mappo.json` and `local_mappo.json` keep the unnormalized critic for compatibility. The `*_normalized.json` variants enable running return normalization, share completed fair-cycle validation cases under `artifacts/mappo/validation-cache`, and evaluate at most two cases at once. Per-case timeouts default to 180 seconds. Timed-out cases remain incomplete and are never selected; reruns use the same hash-checked cache and retry path.

## Verification before training

Run the repository contract and unit checks:

```powershell
python -m pytest tests/unit/test_contracts.py
python -m pytest tests/unit
```

Also run the real SUMO integration suite in an environment with the research dependencies installed. The unit checks cover graph construction and ordering, masked PPO and elapsed-time GAE, graph/NumPy action parity, local-message isolation, call-order-independent inference, timing propagation, checkpoint resumption, zero-residual allocation parity, artifact rejection, and four-intersection clearance accounting.
