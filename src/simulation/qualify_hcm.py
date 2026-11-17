"""Reproducible qualification of the reconstructed HCM neighborhood map.

python -m src.simulation.qualify_hcm --config configs/hcm_qualification_v3.json --output artifacts/hcm-qualification-v3 --resume
"""
import argparse
import hashlib
import importlib.metadata
import json
import math
import os
import platform
import shutil
import subprocess
import sys
import time
import uuid
from datetime import datetime, timezone
from pathlib import Path
import xml.etree.ElementTree as ET

from contracts.hcm_qualification_v3 import PROTOCOL, TOPOLOGY_ID
from .build_network import binary
from .hcm_case import bottleneck_speed_response, run_case
from .hcm_demand import generate_demand, route_pool, select_bottleneck, type_inventory
from .hcm_network import inspect_network, labeled_map, write_programs

ROOT = Path(__file__).resolve().parents[2]


def read_json(path):
    return json.loads(Path(path).read_text(encoding="utf-8"))


def atomic_json(path, data):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_name(path.name + ".tmp")
    temporary.write_text(json.dumps(data, indent=2, sort_keys=True, allow_nan=False) + "\n", encoding="utf-8")
    os.replace(temporary, path)


def digest(data):
    return hashlib.sha256(json.dumps(data, sort_keys=True, separators=(",", ":")).encode()).hexdigest()


def file_hash(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def publish_directory(source, target):
    # Windows indexers can briefly hold freshly written files without delete sharing.
    for attempt in range(30):
        try:
            source.rename(target)
            return
        except PermissionError:
            if attempt == 29:
                raise
            time.sleep(.1)


def environment():
    import sumo
    import sumolib
    import traci

    exe = Path(binary("sumo")).resolve()
    engine = Path(sumo.__file__).parent / "bin" / ("sumo.exe" if os.name == "nt" else "sumo")
    version = subprocess.run([str(exe), "--version"], capture_output=True, text=True, check=True).stdout
    packages = {name: importlib.metadata.version(name) for name in ("eclipse-sumo", "sumolib", "traci")}
    if len(set(packages.values())) != 1 or f"sumo {packages['traci']}" not in version:
        raise ValueError("SUMO executable, TraCI and sumolib versions must match")
    return {"python": sys.version, "python_executable": sys.executable, "platform": platform.platform(),
            "packages": packages, "sumo_executable": str(exe), "sumo_executable_sha256": file_hash(exe),
            "packaged_sumo_engine_sha256": file_hash(engine),
            "python_package_sha256": {name: digest({str(p.relative_to(Path(module.__file__).parent)): file_hash(p)
                for p in sorted(Path(module.__file__).parent.rglob("*.py"))})
                for name, module in (("traci", traci), ("sumolib", sumolib))},
            "sumo_version": version}


def netconvert_environment():
    exe = Path(binary("netconvert")).resolve()
    version = subprocess.run([str(exe), "--version"], capture_output=True, text=True, check=True).stdout
    if f"netconvert {importlib.metadata.version('traci')}" not in version:
        raise ValueError("SUMO/TraCI/netconvert versions must match")
    import sumo
    engine = Path(sumo.__file__).parent / "bin" / ("netconvert.exe" if os.name == "nt" else "netconvert")
    return {"version": version, "executable_sha256": file_hash(exe), "engine_sha256": file_hash(engine)}


def implementation_hash():
    paths = [ROOT / "contracts/hcm_qualification_v2.py", ROOT / "contracts/hcm_qualification_v3.py",
             ROOT / "contracts/topology/hcm_neighborhood_benchmark_v2.json",
             ROOT / "src/simulation/build_network.py",
             *sorted((ROOT / "src/simulation").glob("hcm_*.py")), Path(__file__)]
    return digest({str(p.relative_to(ROOT)): file_hash(p) for p in paths})


def imported_inputs(config):
    path = (ROOT / config["imported_config"]).resolve()
    root = ET.parse(path).getroot()
    result = {"config": path}
    for key, tag in (("network", "net-file"), ("routes", "route-files"), ("additional", "additional-files")):
        item = root.find(f"input/{tag}")
        values = [(path.parent / v.strip()).resolve() for v in item.get("value").split(",")] if item is not None else []
        if any(not p.is_file() for p in values):
            raise ValueError(f"Missing imported {tag}")
        result[key] = values[0] if key == "network" and len(values) == 1 else values
    if not isinstance(result["network"], Path):
        raise ValueError("Exactly one network is required")
    return result


def prepare(config, output, source_network=None):
    imported = imported_inputs(config)
    effective_network = Path(source_network) if source_network is not None else ROOT / config["repaired_network"]
    if not effective_network.is_file():
        raise ValueError("Repaired network missing; run --stage repair first")
    inputs = output / "inputs" / TOPOLOGY_ID / file_hash(effective_network)
    inputs.mkdir(parents=True, exist_ok=True)
    network = inputs / "network.net.xml"
    shutil.copyfile(effective_network, network)
    net, topology, audit = inspect_network(network)
    canonical_path = ROOT / "contracts" / "topology" / f"{TOPOLOGY_ID}.json"
    if source_network is None and canonical_path.exists() and digest(read_json(canonical_path)) != digest(topology):
        raise ValueError("Imported network differs from the canonical HCM topology; version it explicitly")
    atomic_json(inputs / "topology.json", topology)
    atomic_json(output / "audit.json", audit)
    labeled_map(net, topology, output / "map.svg")
    write_programs(topology, inputs)
    types, proportions = type_inventory(imported["routes"], imported["routes"])
    pools = {c: route_pool(net, c, topology["sumo_to_canonical"])
             for c in sorted({t.get("vClass", "passenger") for t in types.values()})}
    atomic_json(inputs / "route_population.json", pools)
    atomic_json(inputs / "vehicle_proportions.json", dict(proportions))
    env = environment()
    source_paths = [imported["config"], imported["network"], *imported["routes"], *imported["additional"]]
    identity = {"protocol": PROTOCOL, "implementation_sha256": implementation_hash(), "environment": env,
                "configuration": config, "canonical_topology_sha256": file_hash(canonical_path) if source_network is None and canonical_path.exists() else None,
                "imported_sha256": {str(p.relative_to(ROOT)): file_hash(p) for p in source_paths},
                "network_sha256": file_hash(network), "topology_sha256": file_hash(inputs / "topology.json"),
                "route_population_sha256": file_hash(inputs / "route_population.json"),
                "repair_inputs_sha256": file_hash(ROOT / config["repair_inputs"]),
                "repair_build_inputs_sha256": {p.name: file_hash(p) for pattern in ("*.con.xml", "*.tll.xml", "*.nod.xml")
                                               for p in sorted(effective_network.parent.glob(pattern))},
                "netconvert_environment": netconvert_environment(),
                "program_sha256": {c: file_hash(inputs / f"{c}.add.xml") for c in PROTOCOL["controllers"]}}
    atomic_json(output / "manifest.json", identity)
    return {"inputs": inputs, "imported": imported, "net": net, "topology": topology, "audit": audit,
            "types": types, "proportions": proportions, "pools": pools, "identity": identity}


def case_identity(spec, identity):
    files = {k: file_hash(spec[k]) for k in ("network", "demand", "program", "topology") if k in spec}
    if "bottleneck_control_trace" in spec:
        files["bottleneck_control_trace"] = file_hash(spec["bottleneck_control_trace"])
    if spec.get("diagnostic"):
        files.update(identity["imported_sha256"])
    return {"files": files, "spec": spec, "campaign": identity}


def valid_cache(directory, fingerprint):
    try:
        complete = read_json(directory / "complete.json")
        return (complete["fingerprint"] == fingerprint and bool(complete["files"])
                and all((directory / name).is_file() and file_hash(directory / name) == value
                        for name, value in complete["files"].items())
                and (directory / "metrics.json").is_file())
    except (OSError, ValueError, KeyError):
        return False


def current_case(directory, identity):
    try:
        complete = read_json(directory / "complete.json")
        fingerprint = digest(case_identity(complete["identity"]["spec"], identity))
        return complete if valid_cache(directory, fingerprint) else None
    except (OSError, ValueError, KeyError):
        return None


def campaign_seconds_remaining(output, config):
    ledger_path = Path(output) / "campaign.json"
    if not ledger_path.is_file():
        raise FileNotFoundError(f"Campaign ledger is missing: {ledger_path}; refusing to reset the simulation budget")
    ledger = read_json(ledger_path)
    try:
        spent = float(ledger["simulation_wall_s"])
    except (KeyError, TypeError, ValueError) as error:
        raise ValueError(f"Campaign ledger has no valid simulation charge: {ledger_path}") from error
    if not math.isfinite(spent) or spent < 0:
        raise ValueError(f"Campaign ledger has an invalid simulation charge: {ledger_path}")
    return float(config["campaign_budget_s"]) - spent


def require_campaign_budget(output, config, stage):
    remaining = campaign_seconds_remaining(output, config)
    reserve = 1800 if stage == "repair" else 0
    if remaining <= reserve:
        raise TimeoutError(
            f"Campaign budget exhausted for --stage {stage}: {remaining:.1f}s remain, "
            f"with {reserve}s reserved for final verification"
        )
    return remaining


def _sumo_integration_skip_reason(output, config, required_seconds):
    try:
        remaining = campaign_seconds_remaining(output, config)
    except FileNotFoundError as error:
        return str(error)
    if remaining < required_seconds:
        return f"campaign has {remaining:.1f}s left; {required_seconds:.0f}s is required for this check"
    try:
        environment()
        netconvert_environment()
    except (ImportError, FileNotFoundError, OSError, subprocess.SubprocessError, ValueError) as error:
        return f"matching SUMO, TraCI, sumolib and netconvert are unavailable: {error}"
    return None


def discard_partial(path, output):
    path, output = path.resolve(), output.resolve()
    if not path.is_relative_to(output / "cases") or not path.name.endswith(".partial"):
        raise ValueError("Refusing to discard a directory outside case staging")
    if path.exists():
        archive = output / "failures" / (path.name + "-orphan-" + uuid.uuid4().hex)
        archive.parent.mkdir(parents=True, exist_ok=True)
        publish_directory(path, archive)


def stop_process_tree(process):
    if process.poll() is None:
        if os.name == "nt":
            subprocess.run(["taskkill", "/PID", str(process.pid), "/T", "/F"], capture_output=True)
        else:
            import signal
            os.killpg(process.pid, signal.SIGKILL)
        process.wait(timeout=10)


class Campaign:
    def __init__(self, output, config, context, resume):
        self.output, self.config, self.context, self.resume = output, config, context, resume
        self.fingerprint = digest(context["identity"])
        path = output / "campaign.json"
        old = read_json(path) if path.exists() else {}
        origin = read_json(output / "budget-origin.json") if (output / "budget-origin.json").exists() else {}
        self.ledger = old or {"simulation_wall_s": origin.get("prior_simulation_wall_s", 0), "attempts": [], "budget_origin": origin}
        self.ledger["fingerprint"] = self.fingerprint
        for attempt in self.ledger["attempts"]:
            if attempt["status"] == "running":
                seconds = min(attempt["timeout_s"], max(0, time.time()-attempt["started_epoch"]))
                self.ledger["simulation_wall_s"] += seconds
                attempt.update(status="interrupted", elapsed_wall_s=seconds)
        atomic_json(path, self.ledger)

    def case(self, name, spec):
        fingerprint = digest(case_identity(spec, self.context["identity"]))
        directory = self.output / "cases" / name
        partial = directory.with_name(name + ".partial")
        if self.resume and valid_cache(directory, fingerprint):
            discard_partial(partial, self.output)
            print(f"cached {name}", flush=True)
            return read_json(directory / "metrics.json")
        verification_used = sum(a.get("elapsed_wall_s", 0) for a in self.ledger["attempts"]
                                if a["case"].startswith("repair-replay-") or a["case"].startswith("verification-"))
        reserve = max(0, 1800-verification_used) if name.startswith("repair-") and not name.startswith("repair-replay-") else 0
        remaining = self.config["campaign_budget_s"] - self.ledger["simulation_wall_s"] - reserve
        if remaining <= 0:
            raise TimeoutError("Original two-hour simulation budget exhausted (including the verification reserve)")
        discard_partial(partial, self.output)
        if directory.exists():
            archive = self.output / "invalidated" / f"{name}-{uuid.uuid4().hex}"
            archive.parent.mkdir(parents=True, exist_ok=True)
            publish_directory(directory, archive)
        timeout = min(self.config["case_timeout_s"], remaining)
        partial.mkdir(parents=True)
        atomic_json(partial / "spec.json", spec)
        attempt = {"case": name, "fingerprint": self.fingerprint, "status": "running", "started_epoch": time.time(), "timeout_s": timeout}
        self.ledger["attempts"].append(attempt)
        atomic_json(self.output / "campaign.json", self.ledger)
        print(f"running {name} (timeout {timeout:.0f}s)", flush=True)
        start, process = time.monotonic(), None
        try:
            with (partial / "worker.log").open("w", encoding="utf-8") as log:
                process = subprocess.Popen([sys.executable, "-m", "src.simulation.qualify_hcm",
                                            "--worker", str(partial / "spec.json")], cwd=ROOT,
                                           stdout=log, stderr=subprocess.STDOUT, start_new_session=os.name != "nt")
                code = process.wait(timeout=timeout)
            if code != 0:
                raise RuntimeError(f"Case worker exited {code}; see {partial / 'worker.log'}")
            result = read_json(partial / "metrics.json")
            hashes = {p.name: file_hash(p) for p in sorted(partial.iterdir()) if p.is_file()}
            atomic_json(partial / "complete.json", {"fingerprint": fingerprint, "identity": case_identity(spec, self.context["identity"]), "files": hashes})
            publish_directory(partial, directory)
            attempt["status"] = "completed"
            print(f"done {name}: {result.get('completed', '?')}/{result.get('scheduled', '?')} completed", flush=True)
            return result
        except BaseException as error:
            if process is not None:
                stop_process_tree(process)
            attempt["status"] = "interrupted" if isinstance(error, (KeyboardInterrupt, TimeoutError, subprocess.TimeoutExpired)) else "error"
            attempt["error"] = str(error)
            # Preserve diagnostic logs separately; staging is never an eligible completed case.
            failure = self.output / "failures" / f"{name}-{uuid.uuid4().hex}"
            failure.parent.mkdir(parents=True, exist_ok=True)
            if partial.exists():
                publish_directory(partial, failure)
            raise
        finally:
            elapsed = time.monotonic()-start
            attempt["elapsed_wall_s"] = elapsed
            self.ledger["simulation_wall_s"] += elapsed
            atomic_json(self.output / "campaign.json", self.ledger)


def demand_case(context, output, load, seed, condition):
    directory = context["inputs"] / "demand"
    directory.mkdir(exist_ok=True)
    path = directory / f"{condition}-{load}-{seed}.rou.xml"
    metadata = generate_demand(context["net"], context["topology"], context["types"], context["proportions"],
                               context["pools"], load, seed, condition, path)
    metadata["sha256"] = file_hash(path)
    if condition == "downstream_bottleneck":
        metadata["bottleneck"] = select_bottleneck(context["net"], path)
    atomic_json(path.with_suffix(".json"), metadata)
    return path, metadata


def corrected_spec(context, path, metadata, controller, bottleneck_control_trace=None):
    spec = {"network": str(context["inputs"] / "network.net.xml"), "demand": str(path),
            "topology": str(context["inputs"] / "topology.json"),
            "program": str(context["inputs"] / f"{controller}.add.xml"),
            "controller": controller, "seed": metadata["seed"], "condition": metadata["condition"],
            "bottleneck": metadata.get("bottleneck"), "audit_errors": context["audit"]["errors"],
            "demand_metadata": metadata, "repair_history": True}
    if bottleneck_control_trace is not None:
        spec["bottleneck_control_trace"] = str(bottleneck_control_trace)
    return spec


def load_gate(metrics, kind):
    return (metrics["completion_fraction"] >= PROTOCOL[f"{kind}_completion"]
            and metrics["uninserted_fraction"] <= PROTOCOL[f"{kind}_uninserted"])


def choose_loads(calibration):
    light, primary = [], []
    for load in PROTOCOL["loads_vph"]:
        cases = calibration[str(load)]
        if all(load_gate(m, "light") for m in cases.values()):
            light.append(load)
        if (all(load_gate(m, "primary") for m in cases.values())
                and all(m["mean_stopped_wait_s_per_scheduled"] >= PROTOCOL["primary_fixed_wait_s"]
                        for name, m in cases.items() if name.startswith("native_fixed"))):
            primary.append(load)
    return {"light_vph": min(light) if light else None, "primary_vph": max(primary) if primary else None,
            "gate": bool(light and primary), "selection_rule": "lowest light load and highest primary load by numeric suitability thresholds across both seeds/controllers; engineering gates apply separately to qualification cases"}


def calibrate(campaign):
    context, output = campaign.context, campaign.output
    freeze = read_json(output / "repair/freeze.json")
    if freeze["fingerprint"] != campaign.fingerprint:
        raise ValueError("Repair freeze changed; rerun repair regressions before evaluation")
    results = {}
    for load in PROTOCOL["loads_vph"]:
        results[str(load)] = {}
        for seed in PROTOCOL["calibration_seeds"]:
            path, metadata = demand_case(context, output, load, seed, "calibration")
            for controller in PROTOCOL["controllers"]:
                name = f"calibration-{load}-{seed}-{controller}"
                results[str(load)][f"{controller}-{seed}"] = campaign.case(name, corrected_spec(context, path, metadata, controller))
        atomic_json(output / "calibration.json", {"fingerprint": campaign.fingerprint, "results": results})
    selection = {**choose_loads(results), "fingerprint": campaign.fingerprint, "calibration_sha256": file_hash(output / "calibration.json")}
    atomic_json(output / "selection.json", selection)
    return selection


def compare_numeric(a, b, tolerance=PROTOCOL["numerical_tolerance"]):
    if isinstance(a, dict) and isinstance(b, dict):
        return set(a) == set(b) and all(compare_numeric(a[k], b[k], tolerance) for k in a)
    if isinstance(a, list) and isinstance(b, list):
        return len(a) == len(b) and all(compare_numeric(x, y, tolerance) for x, y in zip(a, b))
    if isinstance(a, (int, float)) and isinstance(b, (int, float)):
        return math.isclose(a, b, abs_tol=tolerance, rel_tol=0)
    return a == b


def reproduce(original, repeat):
    skipped = {"elapsed_wall_s", "simulation_seconds_per_wall_second"}
    metrics = compare_numeric({k: v for k, v in read_json(original / "metrics.json").items() if k not in skipped},
                              {k: v for k, v in read_json(repeat / "metrics.json").items() if k not in skipped})
    outcomes = compare_numeric(read_json(original / "vehicle_outcomes.json"), read_json(repeat / "vehicle_outcomes.json"))
    signals = file_hash(original / "signals.csv") == file_hash(repeat / "signals.csv")
    return {"metrics": metrics, "vehicle_outcomes": outcomes, "signal_traces": signals,
            "gate": metrics and outcomes and signals, "absolute_tolerance": PROTOCOL["numerical_tolerance"]}


def qualify(campaign, selection):
    context, output = campaign.context, campaign.output
    if (selection["fingerprint"] != campaign.fingerprint
            or not (output / "calibration.json").exists()
            or file_hash(output / "calibration.json") != selection["calibration_sha256"]):
        raise ValueError("Frozen calibration inputs changed; recalibrate before qualification")
    if not selection["gate"]:
        return
    bottleneck_controls = {}
    load = selection["primary_vph"]
    for seed in PROTOCOL["qualification_seeds"]:
        path, metadata = demand_case(context, output, load, seed, "downstream_bottleneck")
        edge_id = metadata["bottleneck"]["edge_id"]
        for controller in PROTOCOL["controllers"]:
            control_name = f"diagnostic-bottleneck-control-{load}-{seed}-{controller}"
            control_spec = corrected_spec(context, path, metadata, controller)
            control_spec.update({"condition": "bottleneck_control", "bottleneck": None,
                                 "observed_edge_id": edge_id})
            campaign.case(control_name, control_spec)
            bottleneck_controls[seed, controller] = output / "cases" / control_name / "bottleneck_trace.json"
    records = []
    for condition in PROTOCOL["conditions"]:
        load = selection["light_vph"] if condition == "light_uniform" else selection["primary_vph"]
        for seed in PROTOCOL["qualification_seeds"]:
            path, metadata = demand_case(context, output, load, seed, condition)
            for controller in PROTOCOL["controllers"]:
                name = f"qualification-{condition}-{load}-{seed}-{controller}"
                control_trace = (bottleneck_controls[seed, controller]
                                 if condition == "downstream_bottleneck" else None)
                campaign.case(name, corrected_spec(context, path, metadata, controller, control_trace))
                records.append({"case": name, "controller": controller, "condition": condition, "load_vph": load,
                                "seed": seed, "demand_metadata": str(path.with_suffix(".json").relative_to(output))})
            atomic_json(output / "qualification_cases.json", {"fingerprint": campaign.fingerprint, "cases": records})
    seed, load = PROTOCOL["qualification_seeds"][0], selection["primary_vph"]
    original_name = f"qualification-primary_uniform-{load}-{seed}-native_fixed"
    path = context["inputs"] / "demand" / f"primary_uniform-{load}-{seed}.rou.xml"
    metadata = read_json(path.with_suffix(".json"))
    repeat_name = "reproducibility-primary-fixed"
    campaign.case(repeat_name, corrected_spec(context, path, metadata, "native_fixed"))
    atomic_json(output / "reproducibility.json", {**reproduce(output / "cases" / original_name, output / "cases" / repeat_name),
                                                "fingerprint": campaign.fingerprint, "original": original_name, "repeat": repeat_name})


def stress_evidence(directory, condition, topology):
    backlog = read_json(directory / "backlog.json")
    start = 900 if condition == "directional_shift" else 1200
    peak = max(row[3] for row in backlog if row[0] >= start)
    end = backlog[-1][3]
    recovery = 1-end/peak if peak else 0
    if condition == "directional_shift":
        flows = read_json(directory / "movement_windows.json")
        counts = {}
        for window in ("forward_window", "reverse_window"):
            counts[window] = {d: sum(v["vehicles"] for v in flows if v["window"] == window
                                     and (v["from"], v["to"]) in set(map(tuple, topology["corridor"][d+"_movements"])))
                              for d in ("forward", "reverse")}
        response = counts["forward_window"]["forward"] > counts["forward_window"]["reverse"] and counts["reverse_window"]["reverse"] > counts["reverse_window"]["forward"]
        evidence = {"movement_counts": counts}
    else:
        trace = read_json(directory / "bottleneck_trace.json")
        before = [r[1] for r in trace if 900 < r[0] <= 1200]
        during = [r[1] for r in trace if 1200 < r[0] <= 1800]
        pre_mean, during_mean = sum(before)/len(before), sum(during)/len(during)
        spec = read_json(directory / "spec.json")
        control = read_json(spec["bottleneck_control_trace"])
        speed = bottleneck_speed_response(control, trace, PROTOCOL["bottleneck_speed_response_fraction"])
        queue_response = during_mean > pre_mean
        response = speed["gate"] or queue_response
        evidence = {"pre_queue_mean": pre_mean, "intervention_queue_mean": during_mean,
                    "queue_response": queue_response, **speed}
    return {**evidence, "response_gate": response, "peak_backlog": peak, "end_backlog": end,
            "recovered_fraction": recovery, "recovery_gate": peak > 0 and recovery >= PROTOCOL["stress_recovery"]}


def report(output, context, error=None):
    fingerprint = digest(context["identity"])
    selection_path = output / "selection.json"
    selection = read_json(selection_path) if selection_path.exists() else {}
    calibration_path = output / "calibration.json"
    if (selection.get("fingerprint") != fingerprint or not calibration_path.is_file()
            or selection.get("calibration_sha256") != file_hash(calibration_path)):
        selection = {}
    record_path = output / "qualification_cases.json"
    records = read_json(record_path) if record_path.exists() else {}
    if records.get("fingerprint") != fingerprint:
        records = {}
    gates = {"network_audit": {"pass": not context["audit"]["errors"], "evidence": "audit.json"},
             "calibrated_loads": {"pass": selection.get("gate"), "evidence": "selection.json"}}
    expected_names = []
    if selection.get("gate"):
        for condition in PROTOCOL["conditions"]:
            load = selection["light_vph"] if condition == "light_uniform" else selection["primary_vph"]
            expected_names.extend(f"qualification-{condition}-{load}-{s}-{c}" for s in PROTOCOL["qualification_seeds"] for c in PROTOCOL["controllers"])
    seen, rows, stress, paired = set(), [], {}, {}
    for record in records.get("cases", []):
        name = record["case"]
        directory = output / "cases" / name
        if name not in expected_names or name in seen or not (directory / "complete.json").exists():
            continue
        complete = current_case(directory, context["identity"])
        if not complete:
            continue
        seen.add(name)
        m = read_json(directory / "metrics.json")
        metadata = complete["identity"]["spec"]["demand_metadata"]
        condition, controller, seed = record["condition"], record["controller"], record["seed"]
        gates[name+":engineering"] = {"pass": m["engineering_pass"], "details": m["engineering_gates"], "evidence": f"cases/{name}/metrics.json"}
        gates[name+":demand_coverage"] = {"pass": metadata["coverage_gate"], "evidence": record["demand_metadata"]}
        if condition in ("light_uniform", "primary_uniform"):
            kind = "light" if condition == "light_uniform" else "primary"
            passed = load_gate(m, kind)
            if kind == "primary" and controller == "native_fixed":
                passed = passed and m["mean_stopped_wait_s_per_scheduled"] >= PROTOCOL["primary_fixed_wait_s"]
            gates[name+":load"] = {"pass": passed, "evidence": f"cases/{name}/metrics.json"}
        else:
            evidence = stress_evidence(directory, condition, context["topology"])
            stress.setdefault((condition, seed), []).append(evidence)
            gates[name+":stress_response"] = {"pass": evidence["response_gate"], "details": evidence,
                                               "evidence": f"cases/{name}/{'movement_windows.json' if condition == 'directional_shift' else 'bottleneck_trace.json'}"}
        paired.setdefault((condition, seed), []).append({k: complete["identity"]["files"][k] for k in ("network", "demand", "topology")})
        rows.append(f"| [{name}](cases/{name}/metrics.json) | {m['completed']} | {m['running']} | {m['uninserted']} | {m['mean_stopped_wait_s_per_scheduled']:.2f} | {'pass' if m['engineering_pass'] else 'FAIL'} |")
    all_cases = len(seen) == 40 and set(expected_names) == seen
    gates["all_40_qualification_cases"] = {"pass": all_cases, "completed": len(seen), "evidence": "qualification_cases.json"}
    gates["paired_identical_inputs"] = {"pass": len(paired) == 20 and all(len(v) == 2 and v[0] == v[1] for v in paired.values()), "evidence": "cases/*/complete.json"}
    for (condition, seed), values in sorted(stress.items()):
        gates[f"{condition}-{seed}:backlog_recovery"] = {"pass": len(values) == 2 and any(v["recovery_gate"] for v in values), "details": values,
                                                        "evidence": "cases/*/backlog.json"}
    repeat_path = output / "reproducibility.json"
    repeat = read_json(repeat_path) if repeat_path.exists() else {}
    if (repeat.get("fingerprint") != fingerprint or not current_case(output / "cases" / repeat.get("original", "missing"), context["identity"])
            or not current_case(output / "cases" / repeat.get("repeat", "missing"), context["identity"])):
        repeat = {}
    elif repeat:
        repeat = {**repeat, **reproduce(output / "cases" / repeat["original"], output / "cases" / repeat["repeat"])}
    gates["clean_process_reproducibility"] = {"pass": repeat.get("gate"), "evidence": "reproducibility.json"}
    repair_status_path = output / "repair/status.json"
    repair_status = read_json(repair_status_path) if repair_status_path.exists() else {}
    freeze_path = output / "repair/freeze.json"
    freeze = read_json(freeze_path) if freeze_path.exists() else {}
    gates["frozen_repair_and_40_regressions"] = {"pass": repair_status.get("status") == "repaired" and freeze.get("fingerprint") == fingerprint,
                                               "evidence": "repair/status.json"}
    interrupted = isinstance(error, (KeyboardInterrupt, TimeoutError, subprocess.TimeoutExpired))
    known_failure = bool(context["audit"]["errors"]) or (bool(selection) and not selection.get("gate"))
    status = ("incomplete" if interrupted or not all_cases or not repeat else
              "qualified" if all(g["pass"] for g in gates.values()) else "failed")
    if known_failure and not interrupted:
        status = "failed"
    result = {"status": status, "fingerprint": fingerprint, "protocol_id": PROTOCOL["protocol_id"],
              "generated_utc": datetime.now(timezone.utc).isoformat(), "gates": gates,
              "error": str(error) if error else None, "completed_qualification_cases": len(seen),
              "selected_loads": selection, "limitations": context["audit"]["limitations"]}
    atomic_json(output / "qualification_status.json", result)
    paragraphs = ["# HCM neighborhood benchmark qualification", "", f"**Status: {status.upper()}**", "",
                  "This suite qualifies reconstructed geometry and synthetic demand for signal-control experiments. It does not establish field calibration or MAPPO generalization.", "",
                  "[Repair manifest](repair/change-manifest.json) ? [Repair regressions](repair/replay40.json) ? [Preservation](preservation-after.json)", "",
                  "[Labeled network map](map.svg) · [Network audit](audit.json) · [Frozen protocol and environment](manifest.json) · [Calibration results](calibration.json) · [Load selection](selection.json) · [Gate evidence](qualification_status.json)", "",
                  f"Network: {context['audit']['controllers']} controllers, {context['audit']['road_edges']} road edges; 2–4 service stages. Derived programs retain protected G and permissive g, use 3 s full yellow and 2 s all-red after each stage, and clamp nominal greens to 10–60 s.", "",
                  "The native_fixed and native_actuated controllers are SUMO diagnostic baselines, separate from project controllers. Actuation uses a 3 s gap and a 30 s jam threshold to support mixed movements on shared lanes.", "",
                  PROTOCOL["corridor_definition"], PROTOCOL["route_population"], PROTOCOL["stress_response_definition"], "",
                  "Signal time is integrated over [0,4500) using the state SUMO applied during each completed step. Per-vehicle stopped waiting and departure delay come from SUMO tripinfo including unfinished trips; uninserted delay is censored at episode end. Stopped-vehicle seconds are independently integrated at 1 s resolution. Backlog includes running vehicles and scheduled vehicles due but not yet inserted.", "",
                  "## Acceptance evidence", "", "| Gate | Result | Evidence |", "|---|---|---|"]
    for name, gate in gates.items():
        decision = "pass" if gate["pass"] else "pending" if gate["pass"] is None else "FAIL"
        evidence = gate["evidence"]
        paragraphs.append(f"| {name} | {decision} | [{evidence}]({evidence}) |")
    paragraphs += ["", "## Qualification case outcomes", "", "| Case | Completed | Running | Uninserted | Mean stopped wait / scheduled (s) | Engineering |", "|---|---:|---:|---:|---:|---|", *rows, "", "## Limitations", "", *[f"- {x}" for x in result["limitations"]],
                   "- Short links and synthetic boundary OD sampling are explicit realism limits. Inferred signals and lane geometry were not corrected against field observations.",
                   "- No requirement favors actuated control, graph communication, or a learning algorithm. The four-intersection fixture and existing learning protocols are unchanged."]
    calibration = read_json(calibration_path) if calibration_path.exists() else {}
    if calibration.get("fingerprint") == fingerprint:
        paragraphs += ["", "## Calibration evidence", "", "| Load (veh/h) | Controller / seed | Completed | Uninserted | Mean wait (s) | Colliding vehicles | Teleports | Engineering |", "|---:|---|---:|---:|---:|---:|---:|---|"]
        for load, cases in calibration["results"].items():
            for name, metrics in cases.items():
                controller, seed = name.rsplit("-", 1)
                case_name = f"calibration-{load}-{seed}-{controller}"
            paragraphs.append(f"| {load} | [{name}](cases/{case_name}/metrics.json) | {metrics['completed']} / {metrics['scheduled']} | {metrics['uninserted']} | {metrics['mean_stopped_wait_s_per_scheduled']:.2f} | {metrics['collisions']} | {metrics['teleports']} | {'pass' if metrics['engineering_pass'] else 'FAIL'} |")
        if selection and not selection.get("gate"):
            paragraphs += ["", "Calibration could not select both eligible loads using the frozen gates. The 40 qualification cases and primary repeat were not launched; this is a failed load-selection gate, not a deadline interruption."]
    if error:
        paragraphs += ["", f"Campaign interruption/error: `{error}`. Completed cases remain inspectable; interrupted cases cannot qualify."]
    imported_replay = output / "cases" / "imported-configuration-3600s"
    if (imported_replay / "metrics.json").is_file():
        paragraphs += ["", "The imported configuration was replayed once for 3,600 simulated seconds as a diagnostic only. See [its summary](cases/imported-configuration-3600s/metrics.json) and [warnings](cases/imported-configuration-3600s/sumo-warnings.log). It is excluded from corrected-benchmark acceptance gates."]
    (output / "report.md").write_text("\n".join(paragraphs) + "\n", encoding="utf-8")
    if status == "qualified":
        frozen_files = {str(p.relative_to(output)): file_hash(p) for p in sorted(context["inputs"].rglob("*")) if p.is_file()}
        atomic_json(output / "candidate_benchmark.json", {"status": status, "topology_id": TOPOLOGY_ID,
                    "selection": selection, "identity": context["identity"], "files": frozen_files,
                    "qualification_status_sha256": file_hash(output / "qualification_status.json")})
    else:
        candidate = output / "candidate_benchmark.json"
        if candidate.exists():
            candidate.rename(output / f"candidate_benchmark-invalidated-{uuid.uuid4().hex}.json")
    print(f"qualification status: {status}", flush=True)
    return result


def diagnostic(spec, output):
    cmd = [binary("sumo"), "-c", spec["imported_config"], "--end", "3600", "--seed", str(spec["seed"]),
           "--no-step-log", "true", "--tripinfo-output", str(output / "tripinfo.xml"),
           "--tripinfo-output.write-unfinished", "true", "--summary-output", str(output / "summary.xml"),
           "--error-log", str(output / "sumo-warnings.log")]
    start = time.monotonic()
    result = subprocess.run(cmd, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True)
    (output / "sumo-stdout.log").write_text(result.stdout, encoding="utf-8")
    steps = ET.parse(output / "summary.xml").getroot().findall("step") if (output / "summary.xml").exists() else []
    atomic_json(output / "metrics.json", {"eligible": False, "diagnostic_only": True, "returncode": result.returncode,
                "elapsed_wall_s": time.monotonic()-start, "last_summary": steps[-1].attrib if steps else {},
                "warnings": (output / "sumo-warnings.log").read_text(encoding="utf-8") if (output / "sumo-warnings.log").exists() else result.stdout})


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--config", type=Path, default=ROOT / "configs/hcm_qualification_v3.json")
    parser.add_argument("--output", type=Path, default=ROOT / "artifacts/hcm-qualification-v3")
    parser.add_argument("--resume", action="store_true")
    parser.add_argument("--stage", choices=["inspect", "prepare", "repair", "diagnostic", "calibrate", "qualify", "report", "all"], default="all")
    parser.add_argument("--worker", type=Path, help=argparse.SUPPRESS)
    args = parser.parse_args(argv)
    if args.worker:
        spec = read_json(args.worker)
        if spec.get("diagnostic"):
            diagnostic(spec, args.worker.parent)
        else:
            run_case(spec, args.worker.parent)
        return 0
    output = args.output.resolve()
    config = read_json(args.config)
    if config.get("workers", 1) != 1:
        raise ValueError("Qualification uses one isolated worker")
    for key in ("case_timeout_s", "campaign_budget_s"):
        config.setdefault(key, PROTOCOL[key])
        if not 0 < config[key] <= PROTOCOL[key]:
            raise ValueError(f"{key} must be positive and <= {PROTOCOL[key]}")
    if args.stage in {"repair", "diagnostic", "calibrate", "qualify", "all"}:
        try:
            require_campaign_budget(output, config, args.stage)
        except (FileNotFoundError, TimeoutError, ValueError) as error:
            parser.error(str(error))
    output.mkdir(parents=True, exist_ok=True)
    error = None
    if args.stage == "repair":
        from .hcm_repair import repair
        try:
            context = repair(config, output, args.resume)
        except (Exception, KeyboardInterrupt) as caught:
            error = caught
            context = prepare(config, output, source_network=ROOT / config["repair_source_network"])
            atomic_json(output / "repair/status.json", {"status": "incomplete", "error": str(caught)})
        report(output, context, error)
        return 0 if error is None and read_json(output / "repair/status.json")["status"] == "repaired" else 2
    context = prepare(config, output)
    try:
        if args.stage in ("all", "diagnostic", "calibrate", "qualify"):
            campaign = Campaign(output, config, context, args.resume)
            if args.stage == "diagnostic":
                campaign.case("imported-configuration-3600s", {"diagnostic": True,
                             "imported_config": str(context["imported"]["config"]), "seed": 71001})
            selection = (calibrate(campaign) if args.stage in ("all", "calibrate") else
                         read_json(output / "selection.json") if args.stage == "qualify" else None)
            if args.stage in ("all", "qualify"):
                qualify(campaign, selection)
    except (Exception, KeyboardInterrupt) as caught:
        error = caught
        print(f"campaign stopped: {caught}", file=sys.stderr, flush=True)
    result = report(output, context, error)
    return 0 if args.stage in ("inspect", "prepare", "diagnostic", "report") and error is None else 0 if result["status"] == "qualified" else 2


if __name__ == "__main__":
    raise SystemExit(main())
