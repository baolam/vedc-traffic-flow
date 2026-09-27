"""Numerical latency benchmark. Traffic effectiveness is evaluated separately."""
import argparse
import importlib.util
import json
import platform
import statistics
import sys
import time
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from src.rl.policy import NumpyPolicy
from src.rl.train_dqn import DQNAgent


def measure(fn, iterations=300):
    for _ in range(20):
        fn()
    samples = []
    for _ in range(iterations):
        started = time.perf_counter_ns()
        fn()
        samples.append((time.perf_counter_ns() - started) / 1e6)
    return {"p50_ms": statistics.median(samples), "p95_ms": float(np.percentile(samples, 95)),
            "iterations": iterations}


def benchmark(baseline_dir=None, batch_size=64, iterations=300):
    rng = np.random.default_rng(123)
    batch = (rng.random((batch_size, 12), dtype=np.float32), rng.integers(0, 2, batch_size),
             -rng.random(batch_size, dtype=np.float32), rng.random((batch_size, 12), dtype=np.float32),
             np.zeros(batch_size, dtype=np.float32))
    model = DQNAgent(12, 2, seed=123, lr=1e-5)
    weights = model.export_weights()
    policy = NumpyPolicy(weights)
    observation = batch[0][0].tolist()
    report = {"python": platform.python_version(), "numpy": np.__version__,
              "platform": platform.platform(), "batch_size": batch_size,
              "network": [12, 32, 2], "seed": 123, "scope": "CPU numerical kernels, not traffic KPIs",
              "optimized_update": measure(lambda: model.update(batch), iterations),
              "optimized_inference": measure(lambda: policy.predict(observation), iterations)}
    if baseline_dir:
        path = Path(baseline_dir) / "train_dqn.py"
        spec = importlib.util.spec_from_file_location("src.rl._legacy_training", path)
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
        legacy = module.DQNAgent(12, 2, lr=1e-5)
        for name in ("w1", "b1", "w2", "b2"):
            setattr(legacy, name, json.loads(json.dumps(weights[name])))
        transitions = [(s.tolist(), int(a), float(r), ns.tolist(), bool(d))
                       for s, a, r, ns, d in zip(*batch)]
        # Equal initial parameters; forward numerical agreement is checked separately.
        reference = np.asarray(legacy.forward(observation)[1])
        np.testing.assert_allclose(policy.predict(observation), reference, rtol=1e-5, atol=1e-6)
        report["baseline_inference"] = measure(lambda: legacy.forward(observation), iterations)
        report["baseline_update"] = measure(lambda: legacy.update(transitions), iterations)
        report["update_speedup"] = report["baseline_update"]["p50_ms"] / report["optimized_update"]["p50_ms"]
        report["inference_speedup"] = report["baseline_inference"]["p50_ms"] / report["optimized_inference"]["p50_ms"]
        report["max_forward_absolute_error"] = float(np.max(np.abs(policy.predict(observation) - reference)))
        report["note"] = "Same shape/batch/hardware; training algorithm changed from sequential SGD to batched Double DQN/Adam."
    return report


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--baseline-dir")
    parser.add_argument("--iterations", type=int, default=300)
    parser.add_argument("--output", default="artifacts/model_performance.json")
    args = parser.parse_args()
    if args.iterations < 1:
        parser.error("iterations must be positive")
    report = benchmark(args.baseline_dir, iterations=args.iterations)
    path = Path(args.output)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(report, indent=2, allow_nan=False), encoding="utf-8")
    print(json.dumps(report, indent=2))
