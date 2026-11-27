# Current algorithms and benchmark inventory

Repository inspection: 2026-11-20. This note distinguishes executable source, current local prerequisites, and retained historical evidence. Small training/inference smoke checks and live-SUMO integration tests were run; no full training campaign, full benchmark, final holdout, dependency installation, or HCM qualification budget was consumed.

## Controllers and learning algorithms

The shared factory registers **14 names mapping to 12 controller classes**: `rl` aliases `presslight_rl`, while `local_mappo` shares the Graph-MAPPO implementation and selects its architecture from the artifact. Seven controllers run without learned weights. Names accepted by the factory are broader than the choices wired into older demo scripts. [registry](../../../src/control/factory.py:10), [demo registry](../../../run_demo.py:299)

| Controller key | Implemented decision rule | Current runnability |
|---|---|---|
| `fixed_time` | Clock-based phase schedule, configurable cycle and per-node green splits. | No model needed. [source](../../../src/control/controllers.py:49) |
| `actuated` | Demand calls, green extension, gap-out and maximum green. | No model needed. [source](../../../src/control/controllers.py:146) |
| `max_queue` | Select largest sum of upstream queues; preserve current phase on ties. | No model needed. [source](../../../src/control/controllers.py:305) |
| `max_pressure` | Movement upstream queue minus turn-weighted mapped downstream queue; queue-only fallback where movements are absent. | No model needed. [source](../../../src/control/controllers.py:362) |
| `flow_theory` | CTM-style sending/receiving capacity with downstream occupancy and directional two-hop congestion. | No model needed. [source](../../../src/control/controllers.py:1044) |
| `edgeflow` | Hybrid pressure/CTM control with spillback, progression, service-age and switching-margin terms; optional learned residual. | Default is model-free. `enable_ctm_gating`, `enable_multihop` and term weights allow ablations. Optional residual uses `parameters.rl_model_path`, rather than the factory's top-level `model_path`; failed residual loading is silently ignored, so verify the loaded policy before claiming a learned hybrid. [constructor](../../../src/control/controllers.py:471) |
| `fair_cycle` | Wait/backlog-aware cyclic allocation, serving both phases with a minimum green share; green allocations rounded to five seconds. | No model needed; two-phase topology and rich approach telemetry required. Cycles: 50/70/90 seconds; minimum share: 25% or one-third. [source](../../../src/control/fair_cycle.py:8) |
| `presslight_rl`, `rl` | NumPy MLP selects a phase using shared feature extraction. | Without weights executes and labels itself `pressure_heuristic`. Actual learned inference needs compatible JSON weights; the synthetic trainer below can create them. [source](../../../src/control/controllers.py:963) |
| `shared_dqn` | Shared masked two-action phase-selection policy, trained with Double DQN. | Requires explicit `shared_dqn_model` JSON for `four_intersection_rl_v1`; no saved trained actor found in this checkout. [source](../../../src/control/research.py:97) |
| `fair_cycle_rl` | Fair-cycle allocation plus masked -5/0/+5-second timing residual from a shared DQN. | Requires its own model contract and simulator wait/backlog fields. No saved trained actor found; historical guide paths are not sufficient. [source](../../../src/control/research.py:128), [telemetry limits](FAIR_CYCLE_DQN.md:11) |
| `phase_dqn` | Shared 12-input, 64-hidden-unit scalar phase scorer; batches all legal phase features, masks illegal actions. | **Existing pilot models are available**, one per suite map, with CPU NumPy or CUDA inference. These are pilot checkpoints, not promoted releases. [source](../../../src/control/phase_dqn.py:65) |
| `graph_mappo` | Shared graph-attention actor, centralized critic in training, masked joint timing residuals inside a fair cycle. | Requires frozen actor, complete fresh four-node snapshot, canonical graph and 90-second/25% cycle protocol. No saved trained actor found. [controller](../../../src/control/graph_mappo.py:21), [learning architecture](../../../src/rl/graph_mappo.py:22) |
| `local_mappo` | Self-only communication ablation of the same MAPPO policy. | Same artifact/protocol requirements; architecture comes from the JSON actor. No saved trained actor found. [alias](../../../src/control/graph_mappo.py:143) |

All controllers implement `compute_command`; `compute_commands` is the shared batch interface. Benchmark inference verifies the requested controller actually executed and validates learned model network/topology hashes. A model-free `presslight_rl` or the alias `rl` is therefore unsuitable for a learned-policy comparison in this strict runner. [interface](../../../src/control/controllers.py:26), [runtime checks](../../../src/rl/benchmark.py:15)

The current checkout has a loadable Phase-DQN pilot model at `artifacts/benchmarks/development/pilot-training/four_intersection_rl_v1/policy.json`, plus recipe-hash subdirectories for all six maps. Its successful constructor load was checked. `models/` contains only `.gitkeep`; configured historical fair-cycle/MAPPO baseline paths are missing, including `artifacts/fair-cycle-final-training/seed-43/policy-episode-300.json`. Training support exists, but these tracks need actors restored or trained before meaningful evaluation. [MAPPO baseline reference](../../../configs/rl/graph_mappo_holdout.json:18)

## Training and research evaluation entry points

| Entry point | Environment/algorithm | Config and limits |
|---|---|---|
| `python -m src.rl.train_dqn` | NumPy Double DQN/Adam on a single-node synthetic environment. | Defaults: 200 episodes, 120 steps, seed 42; JSON export compatible with PressLight inference. Small training and evaluation checks passed. Explicitly marks results `valid_for_research=false`. [trainer](../../../src/rl/train_dqn.py:157) |
| `python -m src.rl.train_gpu_dqn` | PyTorch version of synthetic PressLight training. | Defaults: 1000 episodes, 120 steps, batch 128; CUDA if available, otherwise CPU. Exports JSON for NumPy serving. This is still synthetic training. [device selection](../../../src/rl/train_gpu_dqn.py:91), [CLI](../../../src/rl/train_gpu_dqn.py:256) |
| `python -m src.rl.evaluate` | Synthetic paired evaluation of an exported PressLight model against Fixed-Time and Max-Queue. | Balanced, directional-surge and downstream-congestion scenarios; seed list and steps configurable. Queue differences and paired bootstrap intervals are synthetic diagnostics. [evaluation](../../../src/rl/evaluate.py:75) |
| `python -m src.rl.train_shared` | Real SUMO, two workers; shared phase Double DQN or fair-cycle residual Double DQN. | `configs/rl/shared_dqn.json` / `configs/rl/fair_cycle_dqn.json`; three learner seeds 17/29/43 by default, 7200 seconds or 100000 joint decisions per seed. Supports explicit seed/resume, time cap and wait-penalty override. Configured device is CUDA; CPU is an explicit config choice. [CLI](../../../src/rl/train_shared.py:192), [shared config](../../../configs/rl/shared_dqn.json:1), [fair-cycle config](../../../configs/rl/fair_cycle_dqn.json:1) |
| `python -m src.rl.select_fair_cycle_pilot` | Selects a fair-cycle reward-weight pilot using validation guardrails. | Needs completed pilot folders; `--config`, `--pilot-root`, `--output`. [CLI](../../../src/rl/select_fair_cycle_pilot.py:51) |
| `python -m src.rl.campaign` | Tunes/freezes baselines and selected shared/fair-cycle checkpoints before paired holdout promotion. | Needs actual training roots and saved validation checkpoints. Historical Shared-DQN and Fair-Cycle guides report denied promotion; those results do not imply actors are present locally. [campaign](../../../src/rl/campaign.py:135), [shared guide](SHARED_DQN_RESEARCH.md:1), [fair-cycle findings](FAIR_CYCLE_DQN.md:51) |
| `python -m src.rl.benchmark` | Standalone real-SUMO evaluation of a JSON config containing `environment` and named `controllers`. | `--config`, `--output`, validation/holdout split. Training-only configs lack the required `controllers` section. Holdout needs a validation selection manifest. [CLI](../../../src/rl/benchmark.py:269) |
| `python -m src.rl.train_mappo` | Graph-attention or local-only MAPPO, centralized critic, PPO clipping/GAE, optional value normalization. | `configs/rl/{graph,local}_mappo{,_normalized}.json`; default 128 episodes or 3600 seconds per learner seed, CUDA. Supports seed/resume/time/episode caps. [trainer](../../../src/rl/train_mappo.py:237), [normalized config](../../../configs/rl/graph_mappo_normalized.json:1) |
| `python -m src.rl.evaluate_mappo` | Validation or frozen-holdout evaluation of a MAPPO actor. | Requires `--config`, `--model`, `--output`; holdout selection manifest guard. [CLI](../../../src/rl/evaluate_mappo.py:19) |
| `python -m src.rl.mappo_campaign` | Staged Graph-vs-Local campaign, baseline freeze, validation selection, holdout, latency evidence. | `configs/rl/mappo_campaign.json` declares a 36000-second total budget; baseline actor paths must exist first. [config](../../../configs/rl/mappo_campaign.json:1), [baseline checks](../../../src/rl/mappo_campaign.py:71) |
| `src.benchmark.train.train_map` | Map-specific real-SUMO scalar Phase-DQN training. | Used by the six-map suite's pilot/train stages; not a separate CLI. Exports map-bound JSON and a resumable checkpoint. [implementation](../../../src/benchmark/train.py:24) |

For the shared/fair-cycle research environment, the three primary scenarios are balanced, directional surge and downstream bottleneck, with 1800 seconds of demand plus up to 600 seconds of drain. MAPPO adds stricter frozen timing/graph protocol. This research track and the later six-map benchmark use different seed partitions; do not mix their holdout evidence. [research contracts](../../../contracts/research.py:5), [suite contracts](../../../contracts/benchmark.py:3)

## Other runnable algorithm components

| Component | Implemented algorithm and how to exercise it |
|---|---|
| Vision detector | OpenCV DNN YOLO ONNX inference, with YOLOv8/YOLO11-style or YOLOv5-style output decoding and NMS. With no model, MOG2 background subtraction is a separately named motion baseline. Existing `services/vision/models/yolov8n.onnx` loaded and processed the bundled video. No Ultralytics or ONNX Runtime package is required for this serving path. [detector](../../../services/vision/vision/detector.py:13) |
| Vision motion/telemetry | Bounding-box-center displacement speed estimation, ROI aggregation and windowed telemetry. Exercised by the vision service/demo and unit tests; camera calibration remains necessary for physical speed/queue measurements. [motion](../../../services/vision/vision/motion_estimator.py:37), [service guide](../../../services/vision/README.md:1) |
| Nearest-neighbor camera graph | BallTree/Haversine spatial neighbors, followed by OSRM route filtering. `python -m src.graph.camera_graph_builder --input data/raw/cameras_hcm_full.json --output /tmp/camera-graph.pkl`; needs a reachable OSRM service, default localhost:5005. [source](../../../src/graph/camera_graph_builder.py:20) |
| Delaunay camera graph | Delaunay triangulation, distance cutoff and directed OSRM routes. `python -m src.graph.delaunay_builder --input data/raw/cameras_hcm_full.json --output /tmp/camera-delaunay.pkl`. Existing raw data and both processed graph files are present; live routing was not checked. Both graph builders swallow routing failures, so an output file alone does not establish useful connectivity. [source](../../../src/graph/delaunay_builder.py:28) |
| Production control guards | Timestamp freshness/neighbor eviction; physical slew clamps and confidence-weighted EMA; fault barriers; consecutive-decision debounce/clearance lock; command TTL/coalescing; fairness/service reservation. These wrap a controller in the live service and are not independent suite competitors. [noise shield](../../../services/graph-control/noise_shield.py:21), [fairness](../../../services/graph-control/fairness_guard.py:74) |
| Native SUMO baselines | Native Fixed-Time and Actuated signal programs in HCM engineering qualification; these are separate from the Python controller implementations. Existing campaign simulation budget is exhausted, as detailed below. [qualification config](../../../configs/hcm_qualification_v3.json:1) |

## Benchmark entry points

| Entry point | Purpose and configuration | Evidence/output |
|---|---|---|
| `python -m src.benchmark.cli` | Current six-map reproducible suite; `--suite`, `--stage`, `--split`, `--freeze`, `--output-dir`. Stages: preflight, prepare, pilot, pilot-evaluate, train, evaluate, report, export. | Audited inputs, source snapshots, hashed case identities, immutable attempts, metrics, JSON/CSV/Markdown reports and checksum archive. [CLI](../../../src/benchmark/cli.py:217), [evidence](../../../src/benchmark/evidence.py:18). |
| `services/experiment-runner/runner.py` | Single experiment flags include scenario/controller/topology/seed, warmup/duration/drain, output and execution mode; `--suite` forwards to current suite CLI. | Per-experiment environment/summary/telemetry/signal events/faults/validity. [dispatch](../../../services/experiment-runner/runner.py:703), [export](../../../services/experiment-runner/runner.py:593). |
| `services/experiment-runner/batch_runner.py` | Earlier matrix runner with `--config` JSON, `--preflight-only`, topology/scenarios/controllers/seeds and horizons. Four legacy topologies, five controllers, five default seeds. | Campaign manifest, frozen demand, paired comparison report, CSV and Markdown. [matrix](../../../services/experiment-runner/batch_runner.py:46), [manifest](../../../services/experiment-runner/batch_runner.py:386), [parser](../../../services/experiment-runner/batch_runner.py:680). |
| `services/experiment-runner/batch_runner_parallel.py` | Parallel form of earlier runner; `--workers` plus the batch flags. Default live-SUMO workers cap at four; other modes cap at 16, and explicit positive worker values are not capped. | Extends legacy campaign manifest with worker count and parallel execution flag. [workers](../../../services/experiment-runner/batch_runner_parallel.py:193), [manifest](../../../services/experiment-runner/batch_runner_parallel.py:204), [parser](../../../services/experiment-runner/batch_runner_parallel.py:455). |
| `python -m src.simulation.qualify_hcm` | Independent HCM geometry/engineering qualification, default `configs/hcm_qualification_v3.json`; inspect/prepare/repair/diagnostic/calibrate/qualify/report/all. | Durable two-hour campaign ledger, repair revisions, regression cases and qualification artifacts. Existing ledger must be preserved. [parser](../../../src/simulation/qualify_hcm.py:613), [budget](../../../src/simulation/qualify_hcm.py:243), [setup](../../HCM_BENCHMARK_V3_SETUP.md:18). |
| `experiments/benchmark_hybrid_edgeflow_120s.py` | Fixed one-map comparison: four controllers, three legacy scenarios, seed 101, 120-second duration. | Writes under `artifacts/benchmark_120s`; smaller exploratory comparison, not current suite holdout evidence. [constants/call](../../../experiments/benchmark_hybrid_edgeflow_120s.py:27). |
| `src/tools/benchmark_models.py` | CPU numerical DQN update/inference kernels, optional legacy baseline directory, default 300 iterations. | p50/p95 timings, optional speedups and forward agreement; explicitly excludes traffic effectiveness. [implementation](../../../src/tools/benchmark_models.py:21), [CLI](../../../src/tools/benchmark_models.py:69). |
| `services/vision/benchmark.py` | Capture plus detector timings for selected source/model; default 300 measured frames after 20 warmup frames, configurable source/format/input size/threads/camera controls. | Per-frame capture/inference/end-to-end samples and percentile summaries, default `artifacts/vision_performance.json`. [loop](../../../services/vision/benchmark.py:26), [CLI](../../../services/vision/benchmark.py:76). |

The Makefile exposes `contracts`, `test`, `integration`, `experiment`, `experiment-gui`, `create-scenario`, and `benchmark`; `make test` runs `tests/unit` only, while integration tests have a separate target. [Makefile](../../../Makefile:17)

## Current suite, partitions, stages and metrics

The YAML has four workers and six map entries. The corrected `four_intersection_rl_v1` has eight workloads and an extra Fair-Cycle comparator; Grid4x4, Cologne8, HCM corridor, Hanoi Dong Da and Jakarta Menteng each have balanced, directional reversal and downstream bottleneck workloads. Shared rule-based comparators are Fixed-Time, Actuated, Max-Pressure and EdgeFlow. Learned `phase_dqn` entries are appended from each prepared map's model registry. [suite YAML](../../../configs/benchmarks/suite_v1.yaml:1), [expansion](../../../src/benchmark/suite.py:24)

Canonical seeds are train 60000–60999, validation 70001–70005, test 80001–80010, development 90001–90003; learner seeds are 17, 29 and 43. Shared timing is one-second SUMO steps, five-second decisions, 10–60 second greens, three-second yellow and two-second all-red. The synthetic fleet is 65% motorcycles, 25% cars, 4% taxis, 3% buses and 3% trucks. [canonical protocol](../../../contracts/benchmark.py:3)

Stage order and effects:

1. `preflight` checks Python packages, simulator/broker binaries, map paths and CUDA, writes `preflight.json`, and exits nonzero unless every check passes. When `prepared.json` exists it checks that prepared suite. [preflight](../../../src/benchmark/suite.py:47), [CLI](../../../src/benchmark/cli.py:237)
2. `prepare` audits map/network topology, writes per-map inputs and `prepared.json`; city entries with a bounding box invoke the OSM download/build path. This is a writing/network stage, not a read-only probe. It can also create a missing canonical generated topology, so review this stage separately when keeping changes docs-only. [preparation](../../../src/benchmark/prepare.py:10), [canonical write](../../../src/benchmark/prepare.py:161), [city download](../../../src/benchmark/prepare.py:229)
3. `pilot` calibrates against Fixed-Time with development seeds, trains learner seed 11 with a 120-second/200-decision budget per map, measures inference placement, then evaluates shortened demand/drain of 180/60 seconds. `pilot-evaluate` reuses `pilot-suite.json`. Pilot calibration itself uses a 600-second drain. [pilot](../../../src/benchmark/cli.py:296), [calibration](../../../src/benchmark/calibration.py:30)
4. `train` requires audited prepared inputs and calls the current suite training campaign. That campaign tunes Fixed-Time on training seeds, calibrates, trains three learner seeds per map with budgets of 7200 seconds/100000 decisions each, performs validation, selects per-map policies and writes `freeze.json` plus updated `prepared.json`. Thus validation selection is already part of `train`; a later validation `evaluate` is a separate evaluation/report step. `evaluate` also requires models for every map outside the final split; normal evaluation uses 1800-second demand and 600-second drain. [stage dispatch](../../../src/benchmark/cli.py:283), [training/selection](../../../src/benchmark/campaign.py:23)
5. Validation/reporting and frozen model selection precede `evaluate --split test --freeze ...`. The CLI explicitly rejects a test request without that stage and freeze. Final seeds should remain unopened during development. [final split guard](../../../src/benchmark/cli.py:235), [frozen suite load](../../../src/benchmark/cli.py:318)
6. `report` reconstructs requested results from completed case evidence. `export` packages files with checksums and rejects symlink files. Case identities include content hashes, implementation/schema hashes, dependency versions and protocol. Failed attempts are retained; scientifically invalid cases cannot be silently retried under the same identity. [report](../../../src/benchmark/cli.py:46), [export](../../../src/benchmark/cli.py:266), [identity](../../../src/benchmark/suite.py:84), [attempts](../../../src/benchmark/evidence.py:49)

Current suite metrics are version 3: scheduled/departed/completed/unfinished/uninserted accounting; delay per scheduled vehicle; p95 waiting, worst approach wait and maximum approach p95 wait; per-signal green/clearance seconds; throughput; service gaps; backlog/recovery traces; and per-vehicle-class metrics. Delay includes SUMO timeLoss plus departure delay for inserted vehicles and accrued entry delay for uninserted vehicles, reducing survivor bias from completed-only averages. [metric computation](../../../src/simulation/runtime.py:383)

Qualification requires all paired scenario/seed combinations and identical network/topology/demand/timing/horizon/accounting metadata. Per-workload gates reject delay regression over 5%, completion below 98% of baseline, and excess waiting tails. Overall EdgeFlow and Max-Pressure comparisons require at least 5% delay improvement with a strictly positive paired 95% bootstrap interval; Fixed-Time/Actuated overall delay regression cannot exceed 2%. Collisions, teleports, accounting losses, invalid or empty runs block promotion. [qualification source](../../../src/benchmark/scoring.py:9)

## Earlier configurations and retained results

The earlier JSON batch protocol is separate from current YAML suite. `benchmark_sumo_semifinal.json` specifies four topologies, three scenarios, **five** controllers, seeds 101/202/303/404/505, 300-second warmup, 1800-second measurement and 600-second drain: 300 runs. `benchmark_fast.json` selects three controllers, seed 1310 and 180-second measurement: 36 runs. Both descriptions still claim four controllers, which disagrees with their actual lists. [semifinal](../../../configs/benchmark_sumo_semifinal.json:1), [fast](../../../configs/benchmark_fast.json:1)

The retained root comparison report is dated 2026-10-12, commit `857e4f6147c5`, `sumo_live`, and records 60/60 valid runs across four legacy maps, three scenarios, five controllers and seed 1310. It is historical, single-seed evidence, not the declared 300-run semifinal campaign or the 36-run current fast config. Its primary waiting KPI is explicitly completed-vehicle waiting, so compare completion coverage alongside it. [report header](../../../artifacts/benchmark_comparison_report.json:2), [KPI names](../../../artifacts/benchmark_comparison_report.json:75)

The retained current-suite pilot report records **368/369 cases complete**, mode `pilot-evaluate`, development split, promotion false. The missing/invalid case is Grid4x4 downstream bottleneck, seed 90001, Max-Pressure, with reason “Collision or teleport invalidates this run.” This means the pilot cannot be described as a fully valid completed campaign. [pilot report](../../../artifacts/benchmarks/development/report.md:3), [failed case](../../../artifacts/benchmarks/development/report.json:1)

The pilot's saved `preflight.json` says CUDA and Mosquitto were available and `ready=true`, but that is historical environment evidence; it does not establish readiness on the machine inspecting the checkout today. [saved preflight](../../../artifacts/benchmarks/development/preflight.json:1)

The committed HCM v3 campaign ledger charges **7207.400402754778 seconds**, exceeding the original 7200-second budget. Do not resume simulation or reset its output directory to obtain a fresh budget. Setup documentation says qualification is incomplete and publication of the engineering network does not imply qualification. [charged ledger](../../../artifacts/hcm-qualification-v3/campaign.json:1856), [budget origin](../../../artifacts/hcm-qualification-v3/campaign.json:1615), [qualification limits](../../HCM_BENCHMARK_V3_SETUP.md:20)

The retained end-to-end report says 30 cycles and mean 4.643 ms, p95 13.297 ms. Its test uses synthetic vision, a virtual actuator and JSON serialization/deserialization for the MQTT step, not physical camera/network/ESP32 transit. The watchdog result also has a verification weakness: the test sets `fallback_triggered=True` based on elapsed silence rather than asserting an observed fallback state. Treat the artifact as an in-process synthetic timing sample. [artifact](../../../artifacts/end_to_end_latency_report.json:1), [synthetic source](../../../tests/integration/test_end_to_end_latency.py:60), [serialization](../../../tests/integration/test_end_to_end_latency.py:129), [watchdog loop](../../../tests/integration/test_end_to_end_latency.py:177)

Legacy `experiments/example/metrics.py` and its copied package use the Windows absolute root `E:\\vedc-traffic-flow\\experiments\\example`; they need path adaptation on this checkout and are not current suite tooling. [example](../../../experiments/example/metrics.py:5), [copy](../../../experiments/sumo_metrics_package/metrics.py:5)

## Concrete command discrepancy

The documented commands use `make benchmark ARGS="..."`, but the current Makefile never expands `ARGS`; it supplies only the fixed suite and `--stage $(or $(STAGE),preflight)`. Consequently the documented prepare/train/evaluate commands silently request preflight unless `STAGE` is also set. `runner.py` does correctly forward `--suite` to the suite CLI, so the forwarding itself is not the bug. Use the module command directly for output/split/freeze arguments. [documented examples](../benchmarking.md:18), [Makefile target](../../../Makefile:52), [forwarder](../../../services/experiment-runner/runner.py:703)

## Commands for this checkout

Run from the repository root; the local Python and SUMO executables are in `.venv/bin`. Commands below are invocation recipes, not claims that every stage passed during this inventory. Stage prerequisites above still apply.

```bash
# Read-only interface inspection; does not run SUMO.
.venv/bin/python -m src.benchmark.cli --help

# Writes a readiness report; choose a separate output to preserve historical evidence.
PATH="$PWD/.venv/bin:$PATH" .venv/bin/python -m src.benchmark.cli \
  --suite configs/benchmarks/suite_v1.yaml --stage preflight \
  --output-dir /tmp/edgeflow-benchmark-preflight

# Preparation and pilot, only after prerequisites are satisfied.
PATH="$PWD/.venv/bin:$PATH" .venv/bin/python -m src.benchmark.cli \
  --suite configs/benchmarks/suite_v1.yaml --stage prepare \
  --output-dir artifacts/benchmarks/new-development
PATH="$PWD/.venv/bin:$PATH" .venv/bin/python -m src.benchmark.cli \
  --suite configs/benchmarks/suite_v1.yaml --stage pilot \
  --output-dir artifacts/benchmarks/new-development

# Earlier runner, mapping/preflight only.
PATH="$PWD/.venv/bin:$PATH" .venv/bin/python services/experiment-runner/batch_runner.py \
  --config configs/benchmark_sumo_semifinal.json --preflight-only \
  --output-dir /tmp/edgeflow-legacy-preflight

# CPU numeric benchmark; no SUMO traffic effectiveness claim.
.venv/bin/python src/tools/benchmark_models.py --output /tmp/edgeflow-model-performance.json

# Synthetic PressLight training and paired synthetic evaluation (not a SUMO score).
.venv/bin/python -m src.rl.train_dqn --episodes 200 --steps 120 \
  --output /tmp/edgeflow-presslight.json
.venv/bin/python -m src.rl.evaluate --model /tmp/edgeflow-presslight.json \
  --output /tmp/edgeflow-presslight-evaluation.json

# Real-SUMO single experiment: change controller to any model-free baseline.
PATH="$PWD/.venv/bin:$PATH" .venv/bin/python services/experiment-runner/runner.py \
  --mode sumo_live --topology four_intersection_v1 --scenario balanced \
  --controller max_pressure --warmup 30 --duration 120 --drain 60 \
  --output-dir /tmp/edgeflow-single-experiment

# Real-SUMO research training (run where CUDA is accessible; these are long jobs).
.venv/bin/python -m src.rl.train_shared --config configs/rl/shared_dqn.json \
  --output artifacts/new-shared-dqn --seed 17
.venv/bin/python -m src.rl.train_shared --config configs/rl/fair_cycle_dqn.json \
  --output artifacts/new-fair-cycle-dqn --seed 17
.venv/bin/python -m src.rl.train_mappo --config configs/rl/graph_mappo_normalized.json \
  --output artifacts/new-graph-mappo --seed 17
.venv/bin/python -m src.rl.train_mappo --config configs/rl/local_mappo_normalized.json \
  --output artifacts/new-local-mappo --seed 17

# Vision benchmark with a bundled video and existing ONNX model.
.venv/bin/python services/vision/benchmark.py \
  --source docs/competition/thiet_ke/4.4_hinh_minh_hoa/video_demo/video_kiem_60s.mp4 \
  --model services/vision/models/yolov8n.onnx --threads 2 \
  --output /tmp/edgeflow-vision-performance.json
```

The research requirements pin SUMO/TraCI/sumolib 1.25.0 and Gymnasium 1.2.3, plus PyTorch/NumPy/PyYAML/jsonschema/pytest/Paho ranges. Full suite preflight additionally requires a `mosquitto` binary and working CUDA. CPU SUMO integration and numerical kernels have narrower needs than that all-or-nothing preflight. [research requirements](../../../src/rl/requirements-sumo.txt:1), [preflight requirements](../../../src/benchmark/suite.py:47)

## Integration and verification entry points

| Test/script | What it establishes |
|---|---|
| `tests/integration/test_benchmark_suite.py` | Real SUMO map auditing, vehicle accounting, signal-second accounting and bottleneck execution; city tests depend on existing prepared inputs. Explicit skip if research SUMO package is absent. [tests](../../../tests/integration/test_benchmark_suite.py:10) |
| `tests/integration/test_benchmark_mqtt.py` | Actual production services over an isolated Mosquitto broker: applied/expired command ACKs, clearance timing, confidence-zero command suppression. Explicit skip when broker executable is absent. [tests](../../../tests/integration/test_benchmark_mqtt.py:10) |
| `tests/integration/test_sumo_live_benchmark.py` | Earlier live runtime/controller smoke checks, runner dispatch and two-controller batch pilot. [tests](../../../tests/integration/test_sumo_live_benchmark.py:46) |
| `tests/integration/test_p1_baseline_benchmark.py` | Standalone baseline benchmark helper with SUMO/TraCI availability check; uses legacy experiment runner, not current six-map suite. [helper](../../../tests/integration/test_p1_baseline_benchmark.py:46) |
| `tests/integration/test_end_to_end_latency.py` | Synthetic, in-process pipeline timing and an emulated watchdog check; mean threshold 50 ms. [assertions](../../../tests/integration/test_end_to_end_latency.py:48) |

Required repository checks are `PATH="$PWD/.venv/bin:$PATH" make contracts` and `PATH="$PWD/.venv/bin:$PATH" make test`; environment results and their actual outcomes are recorded separately below when available. [Makefile](../../../Makefile:17)

## Current environment and actual checks

The host has an **NVIDIA GeForce RTX 4070 Laptop GPU, 8188 MiB VRAM**. `nvidia-smi` and PyTorch initially failed inside the agent sandbox because GPU access was blocked by the operating system there. Outside the sandbox, `nvidia-smi` succeeded and `.venv/bin/python` reported PyTorch `2.15.0+cu132`, `cuda_available=True`, one GPU, and successfully summed a CUDA tensor. The GPU is available; GPU checks/training need an execution context that exposes it. No GPU training campaign was run.

The virtual environment is Python 3.11.18 with NumPy 2.2.6, Gymnasium, TraCI, sumolib, PyYAML, pytest, Paho, SciPy, scikit-learn and OpenCV 5.0.0. SUMO reports 1.25.0. `sumo`, `sumo-gui` and `netconvert` are in `.venv/bin`; system `python` is absent from the ordinary PATH, so activate the environment or use the explicit commands above. Ultralytics and ONNX Runtime are absent but the OpenCV detector works without them. GUI display, Docker daemon and physical devices were not checked.

A fresh **preflight outside the sandbox** completed and returned `ready=false`, `cuda=true`, all Python dependencies true, SUMO/netconvert present and `mosquitto=null`. Original suite paths for Hanoi/Jakarta are missing. However, all six network/topology pairs referenced by the existing `artifacts/benchmarks/development/prepared.json` exist: the prepared city inputs are already available under that artifact root. Reuse those audited inputs deliberately rather than treating the missing original city paths as evidence that no city maps exist. The existing prepared inputs were checked for existence, not freshly requalified. [fresh preflight](</tmp/edgeflow-investigation/suite-preflight/preflight.json>), [prepared registry](../../../artifacts/benchmarks/development/prepared.json:1)

| Check actually run | Result |
|---|---|
| `PATH="$PWD/.venv/bin:$PATH" make contracts` | 9 passed. |
| `PATH="$PWD/.venv/bin:$PATH" make test` | 566 passed; three warnings (MQTT callback version, HTTPX test-client deprecation, sandbox NVML). |
| `PATH="$PWD/.venv/bin:$PATH" .venv/bin/python -m pytest tests/integration/test_shared_sumo.py -q` | All seven cases passed: deterministic reset, signal clearance, fairness cycle, exported residual inference, zero-residual Graph-MAPPO and three scenario accounting checks. These test actors do not establish trained-model quality. |
| Factory construction | Seven model-free baselines and model-free PressLight instantiated; existing four-intersection Phase-DQN pilot model loaded. |
| Synthetic DQN smoke | Two episodes × 80 steps, batch 32; 33 optimizer updates, JSON export, paired evaluation with two seeds × 20 steps completed. These tiny runs are execution checks only. |
| Numerical performance smoke | 30 measured iterations completed; CPU update/inference p50/p95 written to `/tmp/edgeflow-investigation/model-performance.json`. |
| Motion detector benchmark smoke | Bundled video; 12 measured frames after two warmup frames completed. |
| YOLO ONNX benchmark smoke | Bundled video; four measured frames after one warmup, two OpenCV threads completed. Reports `accuracy_evaluated=false`; no detection-accuracy claim. |
| Host GPU | `nvidia-smi`, PyTorch CUDA device enumeration and a CUDA tensor operation passed outside the sandbox. |
| Full suite readiness | Fresh unprepared-suite preflight failed for missing Mosquitto and missing original Hanoi/Jakarta network paths; CUDA passed. |

Small execution artifacts live under `/tmp/edgeflow-investigation/`; they are not committed benchmark evidence. Only this inventory document was added to the repository. Full benchmark matrices, long learner runs, final holdouts, physical camera/ESP32 measurements, live OSRM and the exhausted HCM qualification campaign were not run.
