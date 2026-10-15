"""
EdgeFlow AI — Contracts Software Development Kit (Contracts SDK).

Single Source of Truth for:
  - Canonical JSON Schemas validation (telemetry, control_command, control_ack).
  - Network Topology contract loading & normalization ($G_t = (V, E)$).
  - Scenario Registry access (ScenarioProfile, flow rates).
"""

import json
import os
from pathlib import Path
from typing import Dict, Any, List, Optional, Union
import jsonschema

try:
    from .models import TopologyContract, NodeSpec, PhaseSpec, MovementSpec, EdgeSpec
    from .scenarios import ScenarioProfile, ScenarioRegistry, CANONICAL_SCENARIOS
except ImportError:  # legacy top-level imports
    from models import TopologyContract, NodeSpec, PhaseSpec, MovementSpec, EdgeSpec
    from scenarios import ScenarioProfile, ScenarioRegistry, CANONICAL_SCENARIOS


def get_contracts_dir() -> Path:
    """Locate the canonical contracts root directory."""
    env_dir = os.getenv("CONTRACTS_DIR")
    if env_dir and Path(env_dir).exists():
        return Path(env_dir)
    curr = Path(__file__).resolve().parent
    if (curr / "schemas").is_dir():
        return curr
    for p in list(curr.parents):
        if (p / "contracts" / "schemas").is_dir():
            return p / "contracts"
    return curr


CONTRACTS_DIR = get_contracts_dir()


def list_topologies() -> List[str]:
    """Return a list of available topology contract IDs in contracts/topology."""
    topo_dir = CONTRACTS_DIR / "topology"
    if not topo_dir.exists():
        return []
    topologies = [f.stem for f in topo_dir.glob("*.json")]
    return sorted(topologies)


def load_schema(schema_name: str) -> Dict[str, Any]:
    """Load JSON schema from contracts/schemas."""
    schema_file = CONTRACTS_DIR / "schemas" / f"{schema_name}.json"
    if not schema_file.exists():
        raise FileNotFoundError(f"Schema file not found: {schema_file}")
    with open(schema_file, "r", encoding="utf-8") as f:
        return json.load(f)


def validate_payload(payload: Dict[str, Any], schema_name: str) -> None:
    """Validate a payload dictionary against a registered JSON schema."""
    schema = load_schema(schema_name)
    jsonschema.validate(instance=payload, schema=schema)


def normalize_topology_phases(topology: Dict[str, Any]) -> Dict[str, Any]:
    """
    Enforce that every phase in every node has an explicit list of 'approaches'.
    If 'approaches' is missing in a phase, derive it based on approach naming heuristics.
    """
    for node in topology.get("nodes", []):
        all_node_approaches = node.get("approaches", [])
        phases = node.get("phases", [])
        for phase in phases:
            if "approaches" not in phase or phase["approaches"] is None:
                phase_id = phase.get("phase_id", "").upper()
                if "PHASE_NS" in phase_id or "_NS" in phase_id:
                    phase_approaches = [
                        app for app in all_node_approaches
                        if "_N_" in app.upper() or "_S_" in app.upper()
                        or app.upper().endswith("_N") or app.upper().endswith("_S")
                    ]
                elif "PHASE_EW" in phase_id or "_EW" in phase_id:
                    phase_approaches = [
                        app for app in all_node_approaches
                        if "_E_" in app.upper() or "_W_" in app.upper()
                        or app.upper().endswith("_E") or app.upper().endswith("_W")
                    ]
                else:
                    phase_approaches = list(all_node_approaches)
                phase["approaches"] = phase_approaches
    return topology


TOPOLOGY_ALIASES = {
    "four_intersection_v1": "corridor",
    "grid4": "corridor",
    "three_way_junction_v1": "junction",
    "single_intersection": "junction",
    "crossroad": "junction",
    "cologne8": "cologne",
    "grid4x4": "grid16",
    "example": "hcm_corridor",
    "hcm": "hcm_corridor",
    "hcm_demo": "hcm_corridor",
    "hcm-corridor": "hcm_corridor",
    "tabletop": "tabletop_j1_j2_v1",
    "tabletop_v1": "tabletop_j1_j2_v1",
}



def resolve_topology_id(topology_id: str) -> str:
    """Resolve alias or legacy topology ID to canonical 1-word topology ID."""
    target = topology_id.lower()
    return TOPOLOGY_ALIASES.get(target, topology_id)


def load_topology(topology_id: str = "corridor") -> Dict[str, Any]:
    """Load and normalize a topology JSON contract by ID or alias as a dictionary."""
    topo_file = CONTRACTS_DIR / "topology" / f"{topology_id}.json"
    if not topo_file.exists():
        canonical_id = resolve_topology_id(topology_id)
        topo_file = CONTRACTS_DIR / "topology" / f"{canonical_id}.json"
    if not topo_file.exists():
        raise FileNotFoundError(f"Topology file not found: {topology_id}")
    with open(topo_file, "r", encoding="utf-8") as f:
        topology = json.load(f)
    return normalize_topology_phases(topology)


def load_topology_contract(topology_id: str = "four_intersection_v1") -> TopologyContract:
    """Load and normalize a topology contract by ID as an OO TopologyContract instance."""
    raw_dict = load_topology(topology_id)
    return TopologyContract.from_dict(raw_dict)


def get_topology_summary(topology_id: str) -> Dict[str, Any]:
    """Get metadata summary for a given topology."""
    contract = load_topology_contract(topology_id)
    return contract.summary()


def list_scenarios() -> List[str]:
    """Return list of canonical traffic scenario names."""
    return ScenarioRegistry.list_scenarios()


def get_scenario(scenario_id: str) -> ScenarioProfile:
    """Retrieve ScenarioProfile instance for a scenario ID."""
    return ScenarioRegistry.get_scenario(scenario_id)
