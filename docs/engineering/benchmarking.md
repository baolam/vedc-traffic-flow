# Reproducible RL signal-control benchmarks

The benchmark CLI prepares maps, trains map-specific phase-scoring Double DQN policies, runs paired controller comparisons, and writes immutable case evidence. The current contract is `configs/benchmarks/suite_v1.yaml` and `contracts/benchmark.py`.

## Included suite

The required maps are the corrected four-junction reference, Grid4x4 (16 signals), Cologne8 (8), the existing HCMC corridor (29), Hanoi Dong Da (9 controllable plus 18 static signals), and Jakarta Menteng (8 controllable plus 9 static). Each crop stays within 32 signalized junctions, counting static signals. Static controllers keep their imported SUMO programs. Hanoi and Jakarta use OpenStreetMap geometry with generated synthetic demand; this tests controller behavior on those road layouts, not measured local traffic. The synthetic fleet mix is 65% motorcycle, 25% car, 4% taxi, 3% bus and 3% truck.

Each map has its own trained policy. Zero-shot transfer is outside this suite. Training, validation-based model selection, and final holdout evaluation are separate stages. Final test seeds (80001–80010) are generated only after a validation freeze. A pilot is development evidence and never qualifies a policy for release.

The workloads cover balanced flow, directional peaks/reversal, downstream bottlenecks, sparse traffic, near-capacity flow, and overload where applicable. One-second SUMO steps, five-second decisions, 10–60 second greens, three-second yellow, and two-second all-red are shared across learned and rule-based controllers. Every run accounts for scheduled, departed, arrived, unfinished, and uninserted vehicles; collisions, teleports, or unexplained accounting losses invalidate the case.

## Commands

Run from the repository root with the research dependencies, SUMO, `netconvert`, and a local Mosquitto executable available:

```bash
make benchmark ARGS="--suite configs/benchmarks/suite_v1.yaml --stage preflight"
make benchmark ARGS="--suite configs/benchmarks/suite_v1.yaml --stage prepare"
make benchmark ARGS="--suite configs/benchmarks/suite_v1.yaml --stage pilot --output-dir artifacts/benchmarks/development"
make benchmark ARGS="--suite configs/benchmarks/suite_v1.yaml --stage pilot-evaluate --output-dir artifacts/benchmarks/development"
make benchmark ARGS="--suite configs/benchmarks/suite_v1.yaml --stage train --output-dir artifacts/benchmarks/research"
make benchmark ARGS="--suite configs/benchmarks/suite_v1.yaml --stage evaluate --split validation --output-dir artifacts/benchmarks/research"
make benchmark ARGS="--suite configs/benchmarks/suite_v1.yaml --stage report --output-dir artifacts/benchmarks/research"
```

Training runs three learner seeds per map. Validation chooses one final checkpoint per map and writes `freeze.json`. Only then run the untouched final split:

```bash
make benchmark ARGS="--suite configs/benchmarks/suite_v1.yaml --stage evaluate --split test --freeze artifacts/benchmarks/research/freeze.json --output-dir artifacts/benchmarks/release"
```

`workers` is capped at four SUMO processes across benchmark campaigns on this host. Each process takes a host-local lease, and overlapping campaign commands are rejected. Training currently uses one SUMO environment at a time per learner; CUDA accelerates learning and can accelerate inference when end-to-end measurement shows a benefit. SUMO itself runs on CPU. A resumed training command consumes only the remaining wall-clock budget from its checkpoint.

## Evidence and interpretation

Every run is keyed by a content identity containing map/network hashes, workload and seed, controller/model hash, timing and horizon, dependency versions, implementation hashes, and schema hashes. Attempts and scientifically invalid outcomes are preserved; invalid cases cannot be silently retried. Reports include JSON, CSV and Markdown. `--stage export` makes a checksum-indexed archive of the selected artifact root.

The pilot uses shortened demand and a small learner budget to expose integration and resource issues. It does not establish convergence or deployment performance. Research promotion requires complete paired validation/test cases on every declared workload, no simulator/accounting faults, per-workload delay/completion/wait gates, and a paired bootstrap improvement over EdgeFlow and Max-Pressure. A real deployment claim additionally requires the isolated MQTT fault-integration checks and a target-hardware timing limit agreed for the deployment.

Run the focused infrastructure checks with:

```bash
make contracts
make test
.venv/bin/python -m pytest tests/integration/test_benchmark_suite.py tests/integration/test_benchmark_mqtt.py tests/integration/test_shared_sumo.py
```

Full training and final testing are intentionally not part of infrastructure completion. Do not open final seeds for development debugging.
