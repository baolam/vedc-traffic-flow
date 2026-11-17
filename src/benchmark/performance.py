"""Measure complete phase feature extraction, inference and command generation."""

import json
import time
from pathlib import Path
import numpy as np
from src.control.phase_dqn import PhaseDQNController, phase_features
from .evidence import write_json


def measure_policy(model, snapshot, output, iterations=100):
    data = json.loads(Path(snapshot).read_text())
    topology, state = data["topology"], data["telemetry"]
    timings = {}
    actions = {}
    policies = {}
    misses = {}
    import torch

    devices = ["cpu", "cuda"] if torch.cuda.is_available() else ["cpu"]
    for device in devices:
        policy = PhaseDQNController(model, inference_device=device)
        policies[device] = policy
        for _ in range(10):
            policy.compute_commands(state, topology)
        samples = []
        for _ in range(iterations):
            start = time.perf_counter_ns()
            commands = policy.compute_commands(state, topology)
            samples.append((time.perf_counter_ns() - start) / 1e6)
        misses[device] = sum(ms > 5000 for ms in samples)
        timings[device] = dict(
            p50_ms=float(np.percentile(samples, 50)),
            p95_ms=float(np.percentile(samples, 95)),
            p99_ms=float(np.percentile(samples, 99)),
            iterations=iterations,
        )
        actions[device] = {key: value["target_phase_id"] for key, value in commands.items()}
    if "cuda" in policies:
        inputs = np.concatenate([phase_features(n, state[n["node_id"]], state) for n in topology["nodes"]])
        np.testing.assert_allclose(
            policies["cpu"].policy.predict(inputs), policies["cuda"].policy.predict(inputs), rtol=1e-5, atol=1e-6
        )
        if actions["cpu"] != actions["cuda"]:
            raise ValueError("CPU/CUDA action parity failed")
    selected = min(timings, key=lambda device: timings[device]["p95_ms"])
    result = dict(
        scope="feature extraction + all-node inference + command generation",
        timings=timings,
        selected_device=selected,
        cuda=torch.version.cuda,
        gpu=torch.cuda.get_device_name() if torch.cuda.is_available() else None,
        deadline_misses=misses,
    )
    write_json(output, result)
    return selected
