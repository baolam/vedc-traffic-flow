"""Per-map masked phase Double DQN; checkpoints retain replay and RNG state."""

import copy
import json
import random
import time
import uuid
from collections import deque
from pathlib import Path
import numpy as np
from contracts.benchmark import PHASE_FEATURES, PHASE_NORMALIZATION, TIMING, SEEDS
from src.control.phase_dqn import phase_features, phase_mask
from src.simulation.runtime import InvalidRun, SumoRuntime
from .evidence import digest, file_hash, write_json
from contextlib import nullcontext


def close_partial_episode(replay, node_count):
    for index in range(max(0, len(replay) - node_count), len(replay)):
        *state, _ = replay[index]
        replay[index] = (*state, True)


def train_map(spec, output, seed=11, seconds=600, decisions=1000, device="cuda"):
    import torch
    from torch import nn

    random.seed(seed)
    np.random.seed(seed)
    torch.manual_seed(seed)
    if device == "cuda" and not torch.cuda.is_available():
        raise RuntimeError("CUDA training requested but unavailable")
    output = Path(output)
    output.mkdir(parents=True, exist_ok=True)
    net = nn.Sequential(nn.Linear(12, 64), nn.ReLU(), nn.Linear(64, 1)).to(device)
    target = copy.deepcopy(net)
    optimizer = torch.optim.Adam(net.parameters(), lr=3e-4)
    replay = deque(maxlen=200000)
    checkpoint = output / "checkpoint.pt"
    recipe = digest(
        dict(
            seed=seed,
            cases=spec["cases"],
            intensities=spec.get("intensity_by_case", {}),
            network=file_hash(spec["network_path"]),
            topology=file_hash(spec["topology_path"]),
            device=device,
            torch=torch.__version__,
            implementation={
                str(p): file_hash(p)
                for p in (
                    Path(__file__),
                    Path("src/benchmark/demand.py"),
                    Path("src/control/phase_dqn.py"),
                    Path("src/simulation/runtime.py"),
                    Path("contracts/benchmark.py"),
                )
            },
        )
    )
    step = 0
    episode = 0
    updates = 0
    elapsed = 0.0
    if checkpoint.exists():
        saved = torch.load(checkpoint, map_location=device, weights_only=False)
        if saved.get("recipe") != recipe:
            raise ValueError("Checkpoint training recipe changed; choose a new training output")
        if (
            saved["network_sha256"] != file_hash(spec["network_path"])
            or saved["topology_sha256"] != file_hash(spec["topology_path"])
            or saved["seed"] != seed
        ):
            raise ValueError("Training network changed")
        net.load_state_dict(saved["online"])
        target.load_state_dict(saved["target"])
        optimizer.load_state_dict(saved["optimizer"])
        replay.extend(saved["replay"])
        step, episode = saved["step"], saved["episode"]
        updates = saved["updates"]
        elapsed = saved["elapsed_s"]
        random.setstate(saved["python_rng"])
        np.random.set_state(saved["numpy_rng"])
        torch.set_rng_state(saved["torch_rng"].cpu())
        if device == "cuda":
            torch.cuda.set_rng_state(saved["cuda_rng"].cpu())
    start = time.monotonic()
    while step < decisions and elapsed + time.monotonic() - start < seconds:
        invalid_episode = None
        with nullcontext():
            runtime = SumoRuntime(
                spec["topology_path"],
                spec["network_path"],
                output / f"episode-{episode:06d}-{uuid.uuid4().hex}",
                seed=SEEDS["train"][episode % len(SEEDS["train"])],
                scenario=spec["cases"][episode % len(spec["cases"])],
                benchmark_mode=True,
                trace=False,
                intensity=spec.get("intensity_by_case", {}).get(spec["cases"][episode % len(spec["cases"])], 1.0),
            )
            try:
                done = False
                while not done:
                    observations = {
                        n["node_id"]: phase_features(n, runtime.telemetry[n["node_id"]], runtime.telemetry)
                        for n in runtime.topology["nodes"]
                    }
                    actions = {}
                    for node in runtime.topology["nodes"]:
                        nid = node["node_id"]
                        mask = phase_mask(node, runtime.telemetry[nid])
                        with torch.no_grad():
                            values = net(torch.as_tensor(observations[nid], device=device)).flatten().cpu().numpy()
                        epsilon = 1 - 0.95 * min(1, step / 25000)
                        actions[nid] = (
                            int(np.random.choice(np.flatnonzero(mask)))
                            if random.random() < epsilon
                            else int(np.argmax(np.where(mask, values, -np.inf)))
                        )
                    try:
                        _, reward, terminal, truncated = runtime.step(actions)
                    except InvalidRun as error:
                        close_partial_episode(replay, len(runtime.topology["nodes"]))
                        invalid_episode = str(error)
                        break
                    for node in runtime.topology["nodes"]:
                        nid = node["node_id"]
                        replay.append(
                            (
                                observations[nid][actions[nid]].copy(),
                                reward,
                                phase_features(node, runtime.telemetry[nid], runtime.telemetry),
                                phase_mask(node, runtime.telemetry[nid]),
                                terminal,
                            )
                        )
                    if len(replay) >= 256:
                        batch = random.sample(list(replay), 256)
                        next_features = nn.utils.rnn.pad_sequence(
                            [torch.as_tensor(row[2], device=device) for row in batch], batch_first=True
                        )
                        masks = nn.utils.rnn.pad_sequence(
                            [torch.as_tensor(row[3], device=device) for row in batch],
                            batch_first=True,
                            padding_value=False,
                        )
                        rewards = torch.tensor([row[1] for row in batch], device=device)
                        terminals = torch.tensor([row[4] for row in batch], device=device)
                        with torch.no_grad():
                            selected = net(next_features).squeeze(-1).masked_fill(~masks, -torch.inf).argmax(1)
                            future = target(next_features).squeeze(-1).gather(1, selected[:, None]).squeeze(1)
                            expected = rewards + 0.99 * (~terminals) * future
                        x = torch.as_tensor(np.stack([row[0] for row in batch]), device=device)
                        loss = nn.functional.smooth_l1_loss(net(x).flatten(), expected)
                        if not torch.isfinite(loss):
                            raise RuntimeError("Nonfinite training loss")
                        optimizer.zero_grad()
                        loss.backward()
                        nn.utils.clip_grad_norm_(net.parameters(), 10)
                        optimizer.step()
                        updates += 1
                    step += 1
                    if step % 1000 == 0:
                        target.load_state_dict(net.state_dict())
                    done = terminal or truncated or step >= decisions or elapsed + time.monotonic() - start >= seconds
                runtime.close()
            finally:
                runtime.close()
        episode += 1
        if invalid_episode:
            with (output / "invalid-episodes.jsonl").open("a") as handle:
                handle.write(json.dumps(dict(episode=episode - 1, reason=invalid_episode)) + "\n")
        write_json(output / "performance-input.json", dict(topology=runtime.topology, telemetry=runtime.telemetry))
        torch.save(
            dict(
                online=net.state_dict(),
                target=target.state_dict(),
                optimizer=optimizer.state_dict(),
                replay=list(replay),
                step=step,
                episode=episode,
                updates=updates,
                elapsed_s=elapsed + time.monotonic() - start,
                recipe=recipe,
                python_rng=random.getstate(),
                numpy_rng=np.random.get_state(),
                torch_rng=torch.get_rng_state(),
                cuda_rng=torch.cuda.get_rng_state() if device == "cuda" else None,
                network_sha256=file_hash(spec["network_path"]),
                topology_sha256=file_hash(spec["topology_path"]),
                seed=seed,
            ),
            output / "checkpoint.tmp",
        )
        (output / "checkpoint.tmp").replace(checkpoint)
    if updates == 0:
        raise RuntimeError("Training budget ended before any optimizer update; checkpoint retained")
    weights = {
        key: value.detach().cpu().tolist()
        for key, value in [("w1", net[0].weight), ("b1", net[0].bias), ("w2", net[2].weight), ("b2", net[2].bias)]
    }
    from src.rl.policy import NumpyPolicy

    probe = np.random.default_rng(9182).random((32, 12), dtype=np.float32)
    with torch.no_grad():
        reference = net(torch.as_tensor(probe, device=device)).cpu().numpy()
    exported = NumpyPolicy(weights).predict(probe)
    np.testing.assert_allclose(exported, reference, rtol=1e-5, atol=1e-6)
    if int(np.argmax(exported)) != int(np.argmax(reference)):
        raise ValueError("Exported policy action parity failed")
    artifact = dict(
        algorithm="phase_dqn_v1",
        features=PHASE_FEATURES,
        normalization=PHASE_NORMALIZATION,
        timing=TIMING,
        topology_id=spec["id"],
        weights=weights,
        provenance=dict(
            network_sha256=file_hash(spec["network_path"]),
            topology_sha256=file_hash(spec["topology_path"]),
            learner_seed=seed,
            updates=updates,
            device=device,
            gpu=torch.cuda.get_device_name() if device == "cuda" else None,
            training_seeds=SEEDS["train"][: min(episode, len(SEEDS["train"]))],
            decisions=step,
            recipe=recipe,
            selection="training_final_checkpoint",
            final_test_opened=False,
        ),
    )
    write_json(output / "policy.json", artifact)
    return str(output / "policy.json")
