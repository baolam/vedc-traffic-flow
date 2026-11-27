# RL benchmark inventory and proposed suite (Superseded)

> Historical design draft. The implemented contract is documented in [benchmarking.md](../benchmarking.md). Zero-shot transfer was dropped; all six maps are trained directly.

Status: design draft, 2026-11-17. Branch: `research/rl-benchmark-suite`.
This is a source inspection and proposal, not newly measured performance evidence.

## Agreed objectives

- Support both comparison of learning methods and qualification of one frozen deployment policy, with separate conclusions.
- Cover vehicle signal control in stages: demand and fairness, topology transfer, then telemetry and deployment faults.
- Allow several-hour release evaluations, keep a small developer suite, and budget training separately. Measure a pilot before promising turnaround.
- Pedestrians, transit priority and emergency preemption need additional scenarios before the suite can make claims about them.
- The eight proposed core cases are accepted. Preserve existing release thresholds, make EW surge mandatory, and add rule-only Fair-Cycle as a required comparator for fair-cycle RL. Its precise additional comparison thresholds remain to be defined.
- Report retraining per map and frozen-policy zero-shot transfer as separate experiments. Topology adaptation is a prerequisite for the latter.
- Add Hanoi and Jakarta, with one small/medium district or corridor per city. Keep Bangkok/Sathorn optional and outside the initial required matrix; see the source-backed [city-map research](SEA_CITY_MAP_CANDIDATES.md).
- Begin with controlled synthetic motorcycle-heavy demand on real geometry, then add field calibration when suitable data is available. Label the two evidence levels separately.
- Each new city area may contain up to 32 signalized junctions including boundary-buffer signals. Use up to four concurrent SUMO processes globally across training, validation and evaluation. Use available CPU, RAM and GPU resources for useful throughput; the earlier 16-junction/two-worker proposal is superseded.
- GPU training is authorized. Use CUDA for the learner and measure batched GPU inference where beneficial; standard SUMO traffic simulation remains on CPU.

## Existing benchmark inventory

| Path / track | Actual coverage | Interpretation and limits |
|---|---|---|
| `src/rl/evaluate.py` with `traffic_env.py` | Single-node synthetic queue environment; balanced, directional surge and downstream congestion; five default demand seeds; DQN, Fixed-Time and Max-Queue: 45 runs | Useful learning regression. Explicitly `valid_for_research=False`; instantaneous phase changes, no network propagation or physical clearance. CPU/GPU trainers are producers, not separate traffic benchmarks. |
| `src/rl/benchmark.py` | Corrected four-junction SUMO runtime; paired controller evaluation and release gates | Strongest traffic-scoring foundation. One topology and two NS/EW phases; runs policies directly in process. |
| `src/rl/campaign.py` | Baseline tuning, validation selection, freeze, resumable holdout and supplemental EW surge | Current complete matrix has six heuristic controllers and three seeds each of shared DQN and fair-cycle RL: 360 primary cases plus 120 supplemental cases. Supplemental EW surge does not affect promotion. |
| `src/rl/select_fair_cycle_pilot.py` | Selects among wait-penalty weights 0, 0.5 and 2 using validation constraints | Reward tuning, not independent final evaluation. |
| `src/tools/benchmark_models.py` | CPU update/inference p50 and p95; optional comparison to historical implementation | Fixed legacy 12→32→2 model, synthetic batches. Does not measure current shared/fair-cycle models or traffic quality. |
| `services/experiment-runner/batch_runner.py` and `batch_runner_parallel.py` | Generic deterministic/live SUMO matrices, frozen demand, multiple maps and heuristic controllers | Useful orchestration and map assets; not evidence of learned-policy transfer. Generic reports use different KPI definitions from the RL runtime. |
| `services/experiment-runner/sumo_runner.py`, `experiments/benchmark_hybrid_edgeflow_120s.py`, P1/P2 integration scripts | Legacy short heuristic comparisons; special dispatch into corrected RL runtime for research topology | Legacy path has a different horizon/protocol. Do not merge its scores with corrected RL results. |
| `tests/unit/test_rl_training.py`, `test_shared_dqn.py`, `test_fair_cycle.py`; `tests/integration/test_shared_sumo.py` | Learning/export parity, seed checks, action safety, topology contracts, deterministic SUMO and vehicle accounting | Correctness checks, not evidence of competitive traffic performance. Other integration benchmark tests exercise generic/legacy paths. |

### Existing corrected protocol worth preserving

`contracts/research.py:3` defines the research topology, timing, features, splits and scenarios. The runtime uses a one-second physical clock, five-second action intervals, 10–60 second greens, three-second yellow and two-second all-red. Both RL configs schedule 1,800 seconds of demand and allow a 600-second drain, with no separate warmup. Every controller receives the same physical actuator envelope.

The primary scenarios are balanced, NS-heavy surge and a J3 exit slowdown to 2 m/s during seconds 600–1200. EW-heavy surge is supplemental. Training randomizes demand intensity between 0.8 and 1.2; default evaluation uses 1.0. Demand seeds are separate from learner initialization seeds 17, 29 and 43.

`src/simulation/runtime.py:302` accounts for completed, unfinished and uninserted scheduled vehicles. Its accrued delay includes time loss and entry delay; it is finite-horizon accrued delay, not an estimate of eventual completed-trip delay. Version-2 wait metrics include vehicle P95, approach P95 and worst approach wait. Collisions, teleports and unexplained accounting losses invalidate cases.

`src/rl/benchmark.py:67` requires complete paired holdout data and matching demand/network/topology/timing inputs. Existing gates require:

- At least 5% aggregate delay improvement with a positive paired 95% bootstrap interval against EdgeFlow and Max-Pressure.
- No more than 2% aggregate delay regression against Actuated and tuned Fixed-Time.
- Per scenario, at most 5% delay regression, at least 98% of baseline completed trips, and wait regression no larger than 10% or one second, whichever is greater.

### Evidence and comparability problems

1. Published shared-DQN and fair-cycle reports both deny promotion. Shared DQN improves mean delay against EdgeFlow/Max-Pressure but fails tail-wait limits. Fair-cycle RL fixes much of that issue but loses throughput and balanced-demand performance against Actuated/tuned Fixed-Time. Strong simple baselines are essential.
2. Only `.gitkeep` is tracked under `models/` and `reports/`; the linked policies, frozen selections and raw RL metrics are absent from this checkout. Some relative links also point under `docs/engineering/`. Reported numerical results cannot be independently recalculated here.
3. Both holdout ranges 40001–40010 and 50001–50010 have been opened according to the reports. The latter remains the code's current holdout. Neither is a fresh final test for a design informed by those results.
4. Grid4x4, Cologne8, HCM and tabletop maps exist, but shared/fair-cycle policies require the corrected J1–J4 topology and feature/phase ordering. The research runtime also checks eight three-edge routes. A map configuration alone cannot provide transfer coverage.
5. Generic multi-network workloads are generated traffic on those maps; map names do not establish evaluation on native public benchmark demand. The committed generic artifact contains 60 heuristic cases with one seed, not the five-seed semifinal matrix.
6. Generic batch rankings use completed-trip mean waits and can substitute mean wait for missing P95. Preserve missing values explicitly; unfinished vehicles and metrics versions must be visible before comparing results.
7. The legacy GPU trainer exports different seed metadata from the field checked by the synthetic evaluator. Its overlap check is conditional, leaving a provenance gap for those exports.
8. Historical campaign reproduction commands omit the now-required fair-training-root argument. Derive current commands from the current entry points rather than copying the old report commands.

Sources: [shared-DQN report](SHARED_DQN_HOLDOUT_REPORT.md), [fair-cycle report](FAIR_CYCLE_DQN.md), [research protocol](../../../contracts/research.py), [corrected evaluator](../../../src/rl/benchmark.py), [generic batch report code](../../../services/experiment-runner/batch_runner.py).

## Proposed staged suite

### A. Developer regression

Keep synthetic/export/action-mask checks, then run three short corrected-SUMO cases: balanced, mirrored surge and temporary blockage, using development seeds and a development model. Verify executed controller identity, signal traces and complete accounting. This is a smoke check; shortened horizons cannot establish release performance. Use a checked-in tiny test policy fixture or a deterministic export fixture, not an absent historical trained model.

### B. Core demand and fairness

Use the corrected four-junction runtime and its metrics. Make eight explicit cases, rather than crossing every demand axis:

| Case | What it tests | Existing support |
|---|---|---|
| Balanced reference | Comparison to historical corrected protocol | Existing |
| NS-heavy demand with lightly used cross street | Directional efficiency and minority-approach starvation | Existing |
| Mirrored EW-heavy demand | Orientation bias | Existing; move into required evaluation |
| Temporary downstream bottleneck and recovery | Spillback avoidance and recovery after restriction ends | Existing event; add recovery summaries |
| Sparse/off-peak demand | Idle switching, unnecessary clearance and service to isolated arrivals | Intensity adjustment exists; calibrate a low-load workload |
| Near-capacity balanced demand | Stability near the onset of persistent queues | Intensity adjustment exists; calibrate capacity using development data |
| Sustained oversaturation | Fair service and honest accounting when demand exceeds capacity | Intensity adjustment exists; calibrate a workload distinct from the reference |
| Time-varying NS→EW peak followed by demand decay | Adaptation, orientation reversal and recovery | New piecewise demand generation required |

Do not assume intensity 1.0 is below capacity. Calibrate load regimes with development seeds and fixed reference controllers, then freeze identical demand for all methods. Retain per-approach tail metrics in every case; add maximum time without service while demand is present. Report queue/backlog over time, end-of-run uninserted/unfinished fractions and recovery after the blockage/peak. Recovery definitions and censoring when queues never recover must be explicit.

Start with three learner seeds per method and ten paired evaluation demand seeds. Compare against tuned Fixed-Time, Actuated, Max-Pressure and EdgeFlow. Include rule-only Fair-Cycle for fair-cycle RL so gains from learning can be distinguished from gains from its timing envelope. Keep Max-Queue and historical shared-DQN variants as diagnostics where useful.

For one learning method this proposed core is 8 cases × 10 demand seeds × (3 trained policies + 5 nonlearned controllers) = **640 case runs**. Each additional three-seed method adds 240. This excludes training, tuning and validation; ten demand seeds are a starting design, not a guarantee of statistical precision.

### C. Topology and traffic-model generalization

After explicit feature/action/runtime adaptation, select representative workloads on an isolated junction or short corridor, Grid4x4, and one irregular city map (Cologne8 or HCM). Audit routes, phase mappings, actual junction counts and workload provenance before admitting a map.

Use a small representative subset: balanced, directional shift and congestion/recovery, calibrated per network. Distinguish training and testing on different demands of the same map from transfer to a held-out map. Extend to turning movements and different phase counts as a separate capability milestone; current two-action policies cannot establish that coverage.

Also test heterogeneous vehicle lengths/speeds and routing where supported. A real map with synthetic demand establishes map diversity, not real-world validity. Treat zero-shot transfer and retraining on a new map as distinct experiments, as agreed. Release qualification applies to the maps and observation sources declared for the intended deployment.

For the requested Southeast Asian expansion, Hanoi and Jakarta are the accepted first two additions, with Bangkok/Sathorn optional. Each addition is one connected small/medium district or corridor. Whole-city simulation and additional districts are outside the initial suite. Candidate availability, evidence and limitations are recorded in [SEA_CITY_MAP_CANDIDATES.md](SEA_CITY_MAP_CANDIDATES.md).

Accepted operating bounds and resource plan:

- Use one small/medium connected city crop, with a hard admission cap of 32 signalized junctions including boundary-buffer signals. Choose the smallest crop that retains useful network interactions; 32 is a ceiling, not a required size. Preserve connected feeder approaches and downstream storage; do not shrink a crop by cutting routes at a controlled junction. Select the actual boundary after auditing the map; no specific district boundary has been verified yet.
- Use three representative workloads per city: balanced, directional shift and bottleneck/recovery. Keep motorcycle mix as a fixed, documented workload input initially; a large fleet-share sweep is diagnostic work outside the required matrix.
- Retain ten paired demand seeds and three learner seeds for method comparison. For one method, two cities × three workloads × ten demand seeds × (three learned policies + five nonlearned baselines) adds 480 cases to the 640-case core. Retrained and zero-shot policies are distinct variants and must be counted explicitly; they are not both included in that 480-case example. Reuse baseline evidence only when the exact scenario, demand, runtime and other frozen inputs match.
- Keep the city track separately runnable and execute one city first to validate the import and cost. Pilot balanced and congested demand with a fixed controller and the candidate, measuring per-case wall time and peak memory before admitting the full crop. A smaller crop must still retain the congestion/recovery behavior under test.
- Use up to four concurrent SUMO processes, one simulation per worker, counted globally across training, validation and evaluation. Avoid multiplying four outer jobs by independently spawned inner workers. Fill free slots with pending independent work when memory permits. Derive the campaign cap from measured memory and runtime. Preserve demand, safety, accounting, seeds and evaluation horizon when reducing cost; reduce map size or optional variants first.
- Run the learner on CUDA and evaluate batched GPU inference against the existing exported inference path for numerical parity and throughput. Retain the same model, actions, safety masks and metrics across devices. Use CPU for SUMO and preprocessing/routing; use RAM and VRAM for effective batching/replay within measured limits. Select the faster validated inference path rather than requiring GPU execution of tiny calls that add transfer overhead. Keep target-device latency measurements separate from accelerated research evaluation.

Hardware observed on 2026-11-17: 20 logical CPUs visible to this environment, 15 GiB system RAM, and an NVIDIA GeForce RTX 4070 Laptop GPU with 8,188 MiB VRAM. `nvidia-smi` succeeded outside the sandbox after the sandbox blocked NVML access. This establishes hardware visibility, not PyTorch CUDA readiness or sustained throughput; dependency/CUDA preflight and a pilot remain necessary. No SUMO executable was found on the current PATH. Existing training configs already request CUDA, but `train_shared.py` currently manages two hardcoded environment workers; four-process scheduling requires an explicit implementation change.

The [official SUMO FAQ](https://sumo.dlr.de/docs/FAQ.html#can_sumo_be_run_in_parallel_on_multiple_cores_or_computers) describes CPU simulation, independently controlled runs and parallel routing, with limited benefit from threading the microscopic simulation. The current SUMO workflow has no CUDA traffic-simulation backend. GPU acceleration applies to learning and suitable inference workloads; moving the whole operation to GPU would require a different simulator and is outside this proposal.

The several-hour release target is not yet a measured guarantee. Count tuning, retraining, zero-shot variants and validation separately from the test matrices above. A pilot that exceeds the resource budget requires a smaller valid crop or an explicit revision of the budget before a large run.

Motorcycle fidelity is a separate acceptance condition. The current corrected runtime generates a single car type (`src/simulation/runtime.py:37`); city geometry alone will not make it motorcycle-heavy. Define explicit motorcycle/car/bus demand, dimensions, gaps and lateral behavior, and audit vehicle-class lane permissions. SUMO's [sublane model](https://sumo.dlr.de/docs/Simulation/SublaneModel.html) supports side-by-side two-wheelers and needs calibrated lateral settings; finer resolution also raises computation cost. Keep published/observed demand separate from controlled synthetic motorcycle-share sensitivity tests. Report delay, P95 wait and completion by vehicle class as well as overall. Registered motorcycle ownership is not a substitute for measured flow or turning counts at the selected junctions.

### D. Observation faults and deployment

Test queue/occupancy bias and noise, missing/stale approach and downstream data, delayed/reordered messages, disconnect/reconnect and restart. Begin with one directional case and one bottleneck case, rather than a full Cartesian product. Pair each faulted run with a clean run under the same demand.

Measure safe fallback, recovery, starvation and traffic degradation through the documented MQTT/HTTP interfaces and actuator acknowledgements. In-process `run_case` cannot establish production communication behavior. Reuse existing sanitization, circuit-breaker and signal-loss checks; do not duplicate service implementations inside the suite.

Fair-cycle RL currently requires simulator-provided wait/backlog features that vision or physical sources may lack. Record required observations and supported sources for every policy. Missing required inputs must trigger an explicit unsupported result or tested fallback, rather than a successful-looking score.

Benchmark actual exported 28-feature shared and 52-feature fair-cycle models, including feature extraction, all-node inference, command generation and memory/CPU on the intended device. Report p50/p95/p99 and deadline misses under nominal and loaded conditions. Set deadlines from the control cadence and a measured pilot. Keep model-kernel timing, control-loop latency and traffic effectiveness as separate results.

## Evaluation and evidence rules

- Maintain separate method-quality and deployment-policy scorecards. Show every learner seed, aggregate variation across learner and demand seeds, per-case results, and paired baseline differences. Select the deployment checkpoint on validation only; never use test results to choose a winning learner seed.
- Keep scenario weights explicit and report normalized baseline-relative results when aggregating different maps. Resample demand seeds as paired blocks and preserve shared-seed dependence across scenarios; method-level uncertainty must also account for training seeds. Do not treat every rollout as an independent learner.
- Freeze fresh, disjoint development/training, validation and final-test assignments before new tuning. Old reported holdouts become regression data. Holdout-only regimes/maps must be labeled separately from familiar-demand test cases; new seeds alone do not establish out-of-distribution generalization.
- Freeze baseline parameters, candidate models, metrics version, scenario definitions, intensity, horizon and gates before final evaluation. Retain 1800+600 timing for historical core comparability; handle changed horizons and steady-state warmup as separately versioned experiments. Fixed-horizon observations are censored and must not be presented as eventual waits.
- Record commit and dirty state, dependencies/SUMO version, hardware, RNG seeds, hashes for model/network/topology/demand/runtime, actual controller identity, signal traces, raw trip/cohort records, failures and wall-clock duration. Package inspectable policy exports, frozen configuration and per-case metrics with the report; large artifacts can live in versioned external storage with content hashes.
- Missing, crashed, invalid or unsupported cases are visible and make the relevant qualification incomplete. They are not silently omitted from averages. Do not fabricate missing P95 from a mean.
- Reuse the current gate thresholds as a proposed starting point. Require mirrored surge and add a rule-only Fair-Cycle comparison for fair-cycle RL. Decide the final comparison thresholds, absolute service limits and mandatory release tracks before implementation; relative success against a poor baseline alone does not establish acceptable operation.
- Time a representative pilot before choosing concurrency and a release wall-clock cap. A time-limited incomplete campaign is resumable evidence, not a pass. Keep smoke, core release, transfer and fault tracks separately runnable and separately reported.

## Suggested implementation order and affected paths

First repair evidence/provenance and freeze a versioned protocol. Then extend the core scenarios, case-driven scoring and learner-seed reporting. Next adapt a representative new map; finally add deployment fault and target-device measurements. No service or contract changes are made by this proposal.

Expected implementation reach: `contracts/research.py` and canonical scenario definitions; `src/simulation/runtime.py` and demand generation; `src/rl/benchmark.py`, `campaign.py`, training validation/selection callers and configs; relevant unit/SUMO integration fixtures; `src/tools/benchmark_models.py`; report/artifact packaging and current reproduction documentation. Topology expansion additionally reaches canonical topology/model contracts, feature extraction and policy compatibility. Deployment tests must use service interfaces. Shared-contract and service edits need explicit scope authorization before implementation.

## Verification of this inspection

`make contracts` and `make test` were both attempted. Both stopped because `python` is unavailable; the available `python3` also has no `pytest`. No dependencies were installed for this inspection. Hardware inventory was inspected, but no CUDA computation, training, full benchmark, hardware performance test or recalculation of published scores was performed. Missing model/raw-result artifacts prevent reproducing the reported RL results from this checkout.

## Next design frontier

Core cases, existing gates, the additional rule-only comparator and separate retraining/zero-shot reporting are accepted. Hanoi and Jakarta are selected with one small/medium district per city; Bangkok is optional. Controlled synthetic motorcycle-heavy demand is accepted for the first version, with separately labeled field calibration later. The resource decision is settled: up to 32 signalized junctions per city crop, four concurrent SUMO processes globally, GPU learning and useful utilization of available hardware. Exact map boundaries require source inspection and a timed pilot. Deployment target devices, absolute service limits, precise transfer partitions, fault magnitudes, deadlines and evidence retention remain to be specified before qualification. These deployment decisions do not prevent preparation of the research suite.
