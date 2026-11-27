"""Suite expansion and explicit dependency preflight."""

import importlib.metadata
import importlib.util
import shutil
from pathlib import Path
import yaml
from contracts.benchmark import SEEDS
from .evidence import file_hash


def load_suite(path):
    suite = yaml.safe_load(Path(path).read_text())
    from contracts.contracts_sdk import validate_payload

    validate_payload(suite, "benchmark_suite")
    if suite.get("version") != 1 or type(suite.get("workers")) is not int or not 1 <= suite["workers"] <= 4:
        raise ValueError("Expected suite version 1 and one to four workers")
    if not suite.get("maps") or len({m["id"] for m in suite["maps"]}) != len(suite["maps"]):
        raise ValueError("Map IDs must be nonempty and unique")
    return suite


def expand(suite, split="development"):
    if split not in SEEDS:
        raise ValueError("Unknown split")
    cases = []
    for mapping in suite["maps"]:
        controllers = [mapping.get("controller_overrides", {}).get(c["type"], c) for c in suite["controllers"]]
        controllers.extend(mapping.get("extra_controllers", []))
        controllers.extend(
            dict(
                type="phase_dqn",
                model_path=path,
                learner_seed=int(seed),
                parameters={"inference_device": mapping.get("inference_device", "cpu")},
            )
            for seed, path in mapping.get("models", {}).items()
        )
        for scenario in mapping["cases"]:
            for seed in SEEDS[split]:
                for controller in controllers:
                    cases.append(dict(map=mapping, scenario=scenario, seed=seed, controller=controller))
    return cases


def preflight(suite):
    dependencies = {}
    for name in ("numpy", "jsonschema", "traci", "sumolib", "gymnasium", "torch", "paho"):
        dependencies[name] = importlib.util.find_spec(name) is not None
    binaries = {name: shutil.which(name) for name in ("sumo", "netconvert", "mosquitto")}
    from src.simulation.build_network import binary

    for name in ("sumo", "netconvert"):
        if not binaries[name] and dependencies["sumolib"]:
            try:
                candidate = binary(name)
                binaries[name] = candidate if Path(candidate).is_file() else None
            except ImportError:
                pass
    maps = {m["id"]: all(Path(m[key]).is_file() for key in ("network_path", "topology_path")) for m in suite["maps"]}
    cuda = False
    if dependencies["torch"]:
        import torch

        cuda = torch.cuda.is_available()
    return dict(
        ready=all(dependencies.values()) and all(binaries.values()) and all(maps.values()) and cuda,
        dependencies=dependencies,
        binaries=binaries,
        maps=maps,
        cuda=cuda,
        final_test_opened=False,
    )


def resolved_protocol(case, config):
    result = dict(config)
    if "intensity" not in result:
        result["intensity"] = case["map"].get("intensity_by_case", {}).get(case["scenario"], 1.0)
    return result


def identity(case, config):
    inputs = {key: file_hash(case["map"][key]) for key in ("network_path", "topology_path")}
    controller = case["controller"]
    if controller.get("model_path"):
        inputs["model"] = file_hash(controller["model_path"])
    versions = {d.metadata["Name"]: d.version for d in importlib.metadata.distributions()}
    implementation = {
        str(p): file_hash(p)
        for folder in ("src/benchmark", "src/simulation", "src/control", "src/rl", "contracts")
        for p in Path(folder).rglob("*.py")
    }
    schemas = {str(p): file_hash(p) for p in Path("contracts/schemas").glob("*.json")}
    semantic = dict(
        map=case["map"]["id"],
        scenario=case["scenario"],
        seed=case["seed"],
        controller={k: v for k, v in controller.items() if k != "model_path"},
    )
    return dict(
        case=semantic,
        protocol=resolved_protocol(case, config),
        inputs=inputs,
        dependencies=versions,
        implementation=implementation,
        schemas=schemas,
    )
