# Shared Double DQN research track

The `shared_dqn` controller is an offline research candidate for the separate `four_intersection_rl_v1` SUMO benchmark. It observes all four canonical nodes, applies one shared policy, and executes through the same 10–60 second green bounds and 3 second yellow / 2 second all red actuator as the baselines. The legacy `presslight_rl` controller and demonstration topology remain available. New scores must be generated from this runtime; older reports do not establish a comparison.

## Environment and network

Install the CUDA-enabled PyTorch wheel that matches the host driver using PyTorch's official selector. In a clean Python 3.11 environment, install `src/rl/requirements-sumo.txt`. SUMO's Windows wheel supports Python 3.11; for newer interpreters, use a supported SUMO build or an isolated Python 3.11 environment. Confirm CUDA and SUMO through the installed tools, then build and validate the research network:

```powershell
python -m src.simulation.build_network
python -c "import torch, subprocess; from src.simulation.build_network import binary; print('CUDA:', torch.cuda.is_available()); subprocess.run([binary('sumo'), '--version'], check=True)"
```

The generated `networks/four_intersection_rl_v1/network.net.xml` is the benchmark input. The canonical contract stores approaches, two controlled phases per junction, connection indices, SUMO signal strings, downstream approach links, and eight routes that traverse two controlled junctions before leaving the network. The runner checks the generated SUMO links against this mapping before starting. Do not regenerate the network between training and evaluation; model metadata binds policies to the network and topology SHA-256 digests.

## Train

```powershell
python -m src.rl.train_shared --config configs/rl/shared_dqn.json --output artifacts/shared_dqn
```

The configuration starts learners with seeds 17, 29, and 43 sequentially. Each learner owns two independent SUMO workers and can use up to two hours or 100,000 joint decisions. The learner saves a complete episode-boundary checkpoint, JSON inference export, RNG states, optimizer, and replay after each paired worker episode. It records whether the decision or time cap ended a run. To resume an interrupted seed, pass that seed and its checkpoint, for example:

```powershell
python -m src.rl.train_shared --config configs/rl/shared_dqn.json --output artifacts/shared_dqn --seed 17 --resume artifacts/shared_dqn/seed-17/checkpoint.pt
```

Validation checkpoints are evaluated every 20 episodes on seeds 30001–30005. The training log selects the lowest equal-weight three-scenario validation delay. Training seeds come only from 20000–20999; holdout seeds 40001–40010 are reserved for the frozen campaign.

The shared MLP uses 28 canonical features, one 64-unit hidden layer, Adam, Double DQN targets, Huber loss, gradient clipping, legal-action masks, and a fixed 20 × 4 × 5 reward scale. Training samples balanced demand, directional surge, and a J3 southern-exit bottleneck, randomizing training intensity from 0.8× to 1.2×. Each episode schedules 1,800 seconds of demand and drains for up to 600 more seconds. A time-limit truncation bootstraps; a naturally completed episode does not.

## Evaluate and promote

```powershell
python -m src.rl.campaign --config configs/rl/shared_dqn.json --training-root artifacts/shared_dqn --output artifacts/shared_dqn_campaign --max-seconds 7200
```

The resumable campaign tunes feasible fixed-time cycles on training seeds; compares archived and default EdgeFlow configurations on validation data; compares Fixed-Time, Actuated, Max-Queue, Max-Pressure, EdgeFlow, and all three learners on identical validation seeds; freezes every selected model and baseline; then opens holdout data. Each result folder contains its frozen demand XML, SUMO trip information, signal trace, input/model hashes, versions, and metrics. If a run exceeds the campaign's time budget, it reports incomplete status; rerun with the same configuration and output path to continue. The campaign never treats incomplete evidence as a promotion.

Delay includes SUMO time loss and departure delay for inserted trips, plus elapsed queueing delay for vehicles that have not inserted. Completed, unfinished, and uninserted counts are reported separately. Flow comes from observed vehicles leaving each approach edge per elapsed simulation second; occupancy is normalized from SUMO percent, including values below one percent. Collisions, teleports, schema violations, unexplained accounting losses, invalid mappings, or model mismatches invalidate a run.

Promotion requires at least 5% lower equal-weight mean accrued delay than both EdgeFlow and Max-Pressure, positive paired 95% bootstrap intervals, no scenario delay regression greater than 5%, completed trips at least 98% of both baselines, and no P95 or worst-approach wait regression greater than the larger of 10% or one second. Holdout comparisons pair all 10 seeds in all three scenarios. Until `promotion.json` records a passed gate, retain the existing deployment controller.

## Verification

```powershell
$env:PYTEST_DISABLE_PLUGIN_AUTOLOAD = "1"
python -m pytest tests/unit/test_contracts.py -q -p no:cacheprovider
python -m pytest tests/unit -q -p no:cacheprovider
python -m pytest tests/integration/test_shared_sumo.py -q -p no:cacheprovider
```

The plugin environment can otherwise load unrelated global napari and scikit-learn plugins. API tests may skip if optional FastAPI test dependencies are not installed. The real-SUMO integration tests exercise deterministic reset, all three scenarios, clearance trace, min/max green, vehicle accounting, truncation, and feature parity.

## Known limits

This research release covers one four-junction synthetic network and two-phase straight-through movements. It does not make a deployment claim, change the default controller, or include Raspberry Pi/hardware deployment. The benchmark is sensitive to the synthetic demand rates and queue-discharge behavior; generalization requires separate public-network tests.
