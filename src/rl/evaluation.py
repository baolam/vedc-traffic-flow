"""Hash-checked SUMO case caching and bounded process isolation."""

import concurrent.futures
import ctypes
import hashlib
import importlib.metadata
import json
import multiprocessing as mp
import os
import platform
import signal
import time
import traceback
from pathlib import Path

from contracts.research import GRAPH_MAPPO_PROTOCOL
from src.simulation.runtime import file_hash


IMPLEMENTATION_FILES = (
    "contracts/research.py", "contracts/scenarios.py", "contracts/contracts_sdk.py",
    "contracts/schemas/telemetry.json", "src/control/research.py", "src/control/controllers.py",
    "src/control/actuator.py", "src/control/fair_cycle.py", "src/control/graph_mappo.py",
    "src/control/graph_mappo_numpy.py", "src/control/factory.py", "src/rl/policy.py",
    "src/rl/sumo_env.py", "src/rl/benchmark.py", "src/rl/evaluation.py",
    "src/rl/mappo_campaign.py",
    "src/simulation/build_network.py", "src/simulation/runtime.py",
)


def _hash(value):
    return hashlib.sha256(json.dumps(value, sort_keys=True, separators=(",", ":")).encode()).hexdigest()


def case_signature(config, controller, scenario, seed):
    environment = config["environment"]
    effective_environment = {key: environment.get(key, default) for key, default in (
        ("topology_path", None), ("network_path", None), ("demand_s", 1800), ("drain_s", 600),
        ("intensity", 1.0), ("wait_penalty_lambda", 0.0))}
    if not effective_environment["topology_path"] or not effective_environment["network_path"]:
        raise ValueError("Evaluation requires topology and network paths")
    controller_identity = {key: controller[key] for key in ("type", "parameters") if key in controller}
    model_path = controller.get("model_path")
    package_versions = {}
    for package in ("eclipse-sumo", "traci", "numpy", "jsonschema"):
        try:
            package_versions[package] = importlib.metadata.version(package)
        except importlib.metadata.PackageNotFoundError:
            package_versions[package] = None
    from src.simulation.build_network import binary
    sumo_executable = str(Path(binary("sumo")).resolve())
    return _hash({
        "protocol": GRAPH_MAPPO_PROTOCOL, "scenario": scenario, "seed": int(seed),
        "environment": effective_environment,
        "topology_sha256": file_hash(effective_environment["topology_path"]),
        "network_sha256": file_hash(effective_environment["network_path"]),
        "controller": controller_identity,
        "model_sha256": file_hash(model_path) if model_path else None,
        "implementation": {path: file_hash(path) for path in IMPLEMENTATION_FILES},
        "runtime": {"python": platform.python_version(), "packages": package_versions,
                    "sumo_executable": sumo_executable,
                    "sumo_sha256": file_hash(sumo_executable)},
    })


def _case_process(start_event, result_pipe, config, controller, scenario, seed, output):
    if os.name != "nt":
        os.setsid()
    start_event.wait()
    try:
        from src.rl.benchmark import run_case
        result_pipe.send((True, run_case(config, controller, scenario, seed, output)))
    except BaseException:
        result_pipe.send((False, traceback.format_exc()))
    finally:
        result_pipe.close()


class _WindowsJob:
    """Own a worker and its descendants so an expired case leaves no SUMO process."""

    def __init__(self):
        self.kernel = ctypes.WinDLL("kernel32", use_last_error=True)
        self.kernel.CreateJobObjectW.restype = ctypes.c_void_p
        self.kernel.SetInformationJobObject.argtypes = [ctypes.c_void_p, ctypes.c_int,
                                                        ctypes.c_void_p, ctypes.c_uint32]
        self.kernel.AssignProcessToJobObject.argtypes = [ctypes.c_void_p, ctypes.c_void_p]
        self.kernel.OpenProcess.argtypes = [ctypes.c_uint32, ctypes.c_int, ctypes.c_uint32]
        self.kernel.OpenProcess.restype = ctypes.c_void_p
        self.kernel.CloseHandle.argtypes = [ctypes.c_void_p]
        self.kernel.TerminateJobObject.argtypes = [ctypes.c_void_p, ctypes.c_uint32]
        self.handle = self.kernel.CreateJobObjectW(None, None)
        if not self.handle:
            raise OSError(ctypes.get_last_error(), "CreateJobObjectW failed")

        class IoCounters(ctypes.Structure):
            _fields_ = [(name, ctypes.c_ulonglong) for name in
                        ("ReadOperationCount", "WriteOperationCount", "OtherOperationCount",
                         "ReadTransferCount", "WriteTransferCount", "OtherTransferCount")]

        class BasicLimit(ctypes.Structure):
            _fields_ = [("PerProcessUserTimeLimit", ctypes.c_longlong),
                        ("PerJobUserTimeLimit", ctypes.c_longlong), ("LimitFlags", ctypes.c_uint32),
                        ("MinimumWorkingSetSize", ctypes.c_size_t), ("MaximumWorkingSetSize", ctypes.c_size_t),
                        ("ActiveProcessLimit", ctypes.c_uint32), ("Affinity", ctypes.c_size_t),
                        ("PriorityClass", ctypes.c_uint32), ("SchedulingClass", ctypes.c_uint32)]

        class ExtendedLimit(ctypes.Structure):
            _fields_ = [("BasicLimitInformation", BasicLimit), ("IoInfo", IoCounters),
                        ("ProcessMemoryLimit", ctypes.c_size_t), ("JobMemoryLimit", ctypes.c_size_t),
                        ("PeakProcessMemoryUsed", ctypes.c_size_t), ("PeakJobMemoryUsed", ctypes.c_size_t)]

        self._limits = ExtendedLimit()
        self._limits.BasicLimitInformation.LimitFlags = 0x2000  # JOB_OBJECT_LIMIT_KILL_ON_JOB_CLOSE
        if not self.kernel.SetInformationJobObject(self.handle, 9, ctypes.byref(self._limits),
                                                   ctypes.sizeof(self._limits)):
            self.close()
            raise OSError(ctypes.get_last_error(), "SetInformationJobObject failed")

    def assign(self, pid):
        process = self.kernel.OpenProcess(0x0101 | 0x1000, False, pid)
        if not process:
            raise OSError(ctypes.get_last_error(), "OpenProcess for SUMO evaluation worker failed")
        try:
            if not self.kernel.AssignProcessToJobObject(self.handle, process):
                raise OSError(ctypes.get_last_error(), "AssignProcessToJobObject failed")
        finally:
            self.kernel.CloseHandle(process)

    def terminate(self):
        if self.handle:
            self.kernel.TerminateJobObject(self.handle, 1)

    def close(self):
        if self.handle:
            self.kernel.CloseHandle(self.handle)
            self.handle = None


def _stop_process_tree(process, job):
    if job is not None:
        job.terminate()
        job.close()
    elif process.is_alive():
        if os.name == "nt":
            process.kill()
        else:
            try:
                os.killpg(process.pid, signal.SIGKILL)
            except ProcessLookupError:
                pass
    process.join(5)
    if process.is_alive():
        process.kill()
        process.join(5)


def _run_isolated_case(config, controller, scenario, seed, output, timeout_s, worker=None):
    context = mp.get_context("spawn")
    start_event = context.Event()
    receive_pipe, send_pipe = context.Pipe(duplex=False)
    process = context.Process(target=worker or _case_process,
                              args=(start_event, send_pipe, config, controller,
                                    scenario, seed, str(output)))
    job = None
    process.start()
    send_pipe.close()
    try:
        if os.name == "nt":
            job = _WindowsJob()
            job.assign(process.pid)
        start_event.set()
        if not receive_pipe.poll(timeout_s):
            _stop_process_tree(process, job)
            job = None
            raise TimeoutError(f"SUMO case exceeded its {timeout_s:.1f}s deadline")
        ok, result = receive_pipe.recv()
        process.join(10)
        if process.is_alive():
            _stop_process_tree(process, job)
            job = None
            raise RuntimeError("SUMO case worker did not exit after returning a result")
        if not ok:
            raise RuntimeError(f"SUMO case failed:\n{result}")
        return result
    except BaseException:
        if process.is_alive():
            _stop_process_tree(process, job)
            job = None
        raise
    finally:
        receive_pipe.close()
        if job is not None:
            job.close()


def run_case_cached(config, controller, scenario, seed, cache_root, timeout_s=180., deadline=None):
    signature = case_signature(config, controller, scenario, seed)
    base = Path(cache_root) / signature[:2] / f"{scenario}-{seed}-{signature}"
    case_dir, suffix = base, 0
    while case_dir.exists():
        metrics_path, identity_path = case_dir / "metrics.json", case_dir / "identity.json"
        if metrics_path.is_file() and identity_path.is_file():
            identity = json.loads(identity_path.read_text(encoding="utf-8"))
            metrics = json.loads(metrics_path.read_text(encoding="utf-8"))
            if identity.get("signature") == signature:
                if not metrics.get("valid"):
                    raise ValueError(f"Refusing invalid cached case: {case_dir}")
                return metrics, True
        suffix += 1
        case_dir = Path(f"{base}-attempt{suffix}")

    remaining = timeout_s if deadline is None else min(timeout_s, deadline - time.monotonic())
    if remaining <= 0:
        raise TimeoutError("Evaluation budget expired before the next SUMO case")
    result = _run_isolated_case(config, controller, scenario, seed, case_dir, remaining)
    if not result.get("valid"):
        raise ValueError(f"Invalid SUMO case retained at {case_dir}")
    identity_path = case_dir / "identity.json"
    temporary = Path(str(identity_path) + ".tmp")
    temporary.write_text(json.dumps({"signature": signature}, indent=2), encoding="utf-8")
    temporary.replace(identity_path)
    return result, False


def evaluate_cases(config, controller, scenarios, seeds, output, *, cache_root=None,
                   workers=1, timeout_s=180., deadline=None):
    if workers <= 0 or timeout_s <= 0:
        raise ValueError("Evaluation workers and case timeout must be positive")
    cases = [(scenario, int(seed)) for scenario in scenarios for seed in seeds]
    root = Path(cache_root) if cache_root is not None else Path(output)
    results, hits = [None] * len(cases), [False] * len(cases)

    def execute(index, scenario, seed):
        row, hit = run_case_cached(config, controller, scenario, seed, root,
                                   timeout_s=timeout_s, deadline=deadline)
        return index, row, hit

    with concurrent.futures.ThreadPoolExecutor(max_workers=workers) as pool:
        futures = [pool.submit(execute, index, scenario, seed)
                   for index, (scenario, seed) in enumerate(cases)]
        for future in concurrent.futures.as_completed(futures):
            index, row, hit = future.result()
            results[index], hits[index] = row, hit
    return results, {"cache_hits": sum(hits), "cache_misses": len(hits) - sum(hits),
                     "cases": len(hits), "workers": workers}
