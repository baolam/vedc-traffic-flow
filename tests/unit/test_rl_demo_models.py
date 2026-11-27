"""The dashboard demo policies (models/rl_demo): every shipped model loads, matches its map and acts legally."""
import hashlib
import json
import math
from pathlib import Path

import pytest

from contracts.contracts_sdk import load_topology
from src.control import unified_dqn as ud
from src.control.factory import create_controller

ROOT = Path(__file__).resolve().parents[2]
MODELS = ROOT / "models" / "rl_demo"
MANIFEST = json.loads((MODELS / "manifest.json").read_text())
CASES = [(name, topo) for name, maps in MANIFEST.items() for topo in maps]


def telemetry(top, queue=2.0):
    return {n["node_id"]: {
        "node_id": n["node_id"], "timestamp_ms": 100_000, "current_phase_id": n["phases"][0]["phase_id"],
        "signal_state": "GREEN", "elapsed_green_s": 12.0,
        "phase_service_age_s": {p["phase_id"]: 3.0 for p in n["phases"]},
        "approaches": [{"approach_id": a, "queue_vehicles": queue, "occupancy_ratio": 0.1, "confidence": 1.0}
                       for a in n["approaches"]]} for n in top["nodes"]}


def test_manifest_covers_both_policies_on_all_six_maps():
    assert set(MANIFEST) == {"phase_dqn_baseline", "edgeflow_rl"}
    assert all(len(maps) == 6 for maps in MANIFEST.values())


@pytest.mark.parametrize("name,topology_id", CASES)
def test_demo_model_loads_matches_its_map_and_acts(name, topology_id):
    path = MODELS / name / f"{topology_id}.json"
    assert hashlib.sha256(path.read_bytes()).hexdigest() == MANIFEST[name][topology_id]["sha256"]
    top = load_topology(topology_id)
    contract = ROOT / "contracts" / "topology" / f"{topology_id}.json"
    c = create_controller(name, model_path=str(path))
    assert c.artifact["provenance"]["topology_sha256"] == hashlib.sha256(contract.read_bytes()).hexdigest()
    commands = c.compute_commands(telemetry(top), top)
    phases = {n["node_id"]: {p["phase_id"] for p in n["phases"]} for n in top["nodes"]}
    assert all(cmd["target_phase_id"] in phases[nid] for nid, cmd in commands.items())


def test_gates_are_per_instance_not_env(monkeypatch):
    path = lambda name: str(MODELS / name / "four_intersection_rl_v1.json")  # noqa: E731
    monkeypatch.setattr(ud, "MP_MARGIN", 0.5)  # an env gate left on by a training shell must not leak into the demo
    base, rl = create_controller("phase_dqn_baseline", model_path=path("phase_dqn_baseline")), \
        create_controller("edgeflow_rl", model_path=path("edgeflow_rl"))
    assert math.isnan(base.gates["mp_margin"]) and base.gates["max_red_s"] == 0
    assert rl.gates == {**ud.GATES_OFF, **ud.EDGEFLOW_RL_GATES}
    # max-red: an approach stopped > 40 s that the current phase does not serve must get the next green
    top = load_topology("four_intersection_rl_v1")
    tel = telemetry(top)
    node = top["nodes"][0]
    starved = next(a for a in node["approaches"] if a not in node["phases"][0]["approaches"])
    next(a for a in tel[node["node_id"]]["approaches"] if a["approach_id"] == starved)["oldest_stopped_wait_s"] = 50.0
    target = rl.compute_command(node["node_id"], tel[node["node_id"]], top, tel)["target_phase_id"]
    assert starved in next(p for p in node["phases"] if p["phase_id"] == target)["approaches"]
