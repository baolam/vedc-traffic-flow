import json
import os
from pathlib import Path
from typing import Dict, Any, List
import jsonschema

def get_contracts_dir() -> Path:
    env_dir = os.getenv("CONTRACTS_DIR")
    if env_dir and Path(env_dir).exists():
        return Path(env_dir)
    if Path("/contracts").exists():
        return Path("/contracts")
    curr = Path(__file__).resolve().parent
    for p in [curr] + list(curr.parents):
        if (p / "contracts").is_dir():
            return p / "contracts"
    return Path("/contracts")

CONTRACTS_DIR = get_contracts_dir()

def list_topologies() -> List[str]:
    """Return a list of available topology contract IDs in contracts/topology."""
    topo_dir = CONTRACTS_DIR / "topology"
    if not topo_dir.exists():
        return []
    topologies = []
    for f in topo_dir.glob("*.json"):
        topologies.append(f.stem)
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
    If 'approaches' is missing in a phase, derive it based on approach naming heuristics
    so that downstream services always consume clean, explicit 'approaches' per phase.
    """
    for node in topology.get("nodes", []):
        node_id = node.get("node_id", "")
        all_node_approaches = node.get("approaches", [])
        phases = node.get("phases", [])
        for phase in phases:
            if "approaches" not in phase or phase["approaches"] is None:
                phase_id = phase.get("phase_id", "").upper()
                phase_approaches = []
                if "PHASE_NS" in phase_id or "_NS" in phase_id:
                    phase_approaches = [
                        app for app in all_node_approaches 
                        if "_N_" in app.upper() or "_S_" in app.upper() or app.upper().endswith("_N") or app.upper().endswith("_S")
                    ]
                elif "PHASE_EW" in phase_id or "_EW" in phase_id:
                    phase_approaches = [
                        app for app in all_node_approaches 
                        if "_E_" in app.upper() or "_W_" in app.upper() or app.upper().endswith("_E") or app.upper().endswith("_W")
                    ]
                else:
                    # Default: fall back to assigning all approaches if unspecified
                    phase_approaches = list(all_node_approaches)
                phase["approaches"] = phase_approaches
    return topology

def load_topology(topology_id: str = "four_intersection_v1") -> Dict[str, Any]:
    """Load and normalize a topology JSON contract by ID."""
    topo_file = CONTRACTS_DIR / "topology" / f"{topology_id}.json"
    if not topo_file.exists():
        raise FileNotFoundError(f"Topology file not found: {topo_file}")
    with open(topo_file, "r", encoding="utf-8") as f:
        topology = json.load(f)
    return normalize_topology_phases(topology)

def get_topology_summary(topology_id: str) -> Dict[str, Any]:
    """Get metadata summary for a given topology."""
    topology = load_topology(topology_id)
    nodes = topology.get("nodes", [])
    edges = topology.get("edges", [])
    total_phases = sum(len(n.get("phases", [])) for n in nodes)
    return {
        "topology_id": topology.get("topology_id", topology_id),
        "version": topology.get("version", "1.0"),
        "total_nodes": len(nodes),
        "total_edges": len(edges),
        "total_phases": total_phases
    }
