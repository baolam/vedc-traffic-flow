"""Training-only tuning, validation-only selection, and immutable test inputs."""

import json
import copy
from pathlib import Path
from contracts.benchmark import LEARNER_SEEDS, SEEDS
from .evidence import digest, file_hash, write_json
from .scoring import qualification
from .suite import expand, identity


def freeze_models(suite, selections):
    frozen = copy.deepcopy(suite)
    for mapping in frozen["maps"]:
        selection = selections[mapping["id"]]
        seed = str(selection["learner_seed"])
        if mapping.get("models", {}).get(seed) != selection["model_path"]:
            raise ValueError("Selected model does not match its learner seed")
        mapping["models"] = {seed: selection["model_path"]}
    return frozen


def run_training(suite, root):
    from .scheduling import run_tasks
    from .train import train_map

    root = Path(root)
    protocol = dict(demand_s=1800, drain_s=600, trace=True, benchmark_mode=True)
    for mapping in suite["maps"]:
        topology = json.loads(Path(mapping["topology_path"]).read_text())
        candidates = []
        for green in (10, 20, 30):
            controller = dict(
                type="fixed_time",
                parameters=dict(phase_splits={n["node_id"]: [green] * len(n["phases"]) for n in topology["nodes"]}),
            )
            tasks = [
                (dict(map=mapping, scenario=s, seed=seed, controller=controller), protocol, str(root / "cases"))
                for s in ["balanced"]
                for seed in SEEDS["train"][:3]
            ]
            rows = run_tasks(tasks, suite["workers"])
            candidates.append((sum(r["delay_per_scheduled_s"] for r in rows) / len(rows), green, controller))
        chosen = min(candidates, key=lambda r: (r[0], r[1]))[2]
        mapping["controller_overrides"] = {"fixed_time": chosen}
        from .calibration import calibrate

        calibrate(mapping, root, chosen, workers=suite["workers"])
        mapping["models"] = {
            str(seed): train_map(
                mapping, root / "training" / mapping["id"] / str(seed), seed, seconds=7200, decisions=100000
            )
            for seed in LEARNER_SEEDS
        }
        from .performance import measure_policy

        first = str(LEARNER_SEEDS[0])
        mapping["inference_device"] = measure_policy(
            mapping["models"][first],
            root / "training" / mapping["id"] / first / "performance-input.json",
            root / "training" / mapping["id"] / first / "performance.json",
        )
    validation = {}
    cases = expand(suite, "validation")
    evaluated = run_tasks([(case, protocol, str(root / "cases")) for case in cases], suite["workers"])
    for case, row in zip(cases, evaluated):
        validation[digest(case)] = row
    selections = {}
    for mapping in suite["maps"]:
        rows = [r for r in validation.values() if r["topology_id"] == mapping["id"]]
        baselines = {
            name: [r for r in rows if r["controller"]["type"] == name]
            for name in ("fixed_time", "actuated", "max_pressure", "edgeflow")
        }
        scores = []
        for seed, path in mapping["models"].items():
            candidate = [r for r in rows if r["controller"].get("model_path") == path]
            gate = qualification(candidate, baselines, mapping["cases"], SEEDS["validation"])
            scores.append(
                (
                    gate.get("selection_score", float("inf")),
                    sum(r["delay_per_scheduled_s"] for r in candidate) / max(len(candidate), 1),
                    int(seed),
                )
            )
        selected = str(min(scores)[2])
        selections[mapping["id"]] = dict(learner_seed=int(selected), model_path=mapping["models"][selected])
    final_suite = freeze_models(suite, selections)
    frozen = dict(
        artifact_root=str(root.resolve()),
        selection_split="validation",
        suite=final_suite,
        selections=selections,
        model_hashes={path: file_hash(path) for m in final_suite["maps"] for path in m["models"].values()},
        case_identities=[identity(case, protocol) for case in expand(final_suite, "test")],
    )
    write_json(root / "prepared.json", suite)
    write_json(root / "freeze.json", frozen)
    return frozen


def load_frozen(path, protocol):
    frozen = json.loads(Path(path).read_text())
    old = frozen["artifact_root"]
    new = str(Path(path).resolve().parent)

    def relocate(value):
        if isinstance(value, str) and value.startswith(old + "/"):
            return new + value[len(old) :]
        if isinstance(value, dict):
            return {relocate(k): relocate(v) for k, v in value.items()}
        if isinstance(value, list):
            return [relocate(v) for v in value]
        return value

    frozen = relocate(frozen)
    if frozen["selection_split"] != "validation":
        raise ValueError("Selection must be made on validation")
    for model, expected in frozen["model_hashes"].items():
        if file_hash(model) != expected:
            raise ValueError("Frozen model changed")
    current = [identity(case, protocol) for case in expand(frozen["suite"], "test")]
    if current != frozen["case_identities"]:
        raise ValueError("Frozen inputs, protocol, dependencies or implementation changed")
    return frozen
