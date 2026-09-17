import json
from pathlib import Path
from typing import Dict, Any
import jsonschema

CONTRACTS_DIR = Path(__file__).resolve().parents[2] / "contracts"

def load_topology(topology_id: str = "four_intersection_v1") -> Dict[str, Any]:
    topo_file = CONTRACTS_DIR / "topology" / f"{topology_id}.json"
    if not topo_file.exists():
        raise FileNotFoundError(f"Topology file not found: {topo_file}")
    with open(topo_file, "r", encoding="utf-8") as f:
        return json.load(f)

def load_schema(schema_name: str) -> Dict[str, Any]:
    schema_file = CONTRACTS_DIR / "schemas" / f"{schema_name}.json"
    if not schema_file.exists():
        raise FileNotFoundError(f"Schema file not found: {schema_file}")
    with open(schema_file, "r", encoding="utf-8") as f:
        return json.load(f)

def validate_payload(payload: Dict[str, Any], schema_name: str) -> None:
    schema = load_schema(schema_name)
    jsonschema.validate(instance=payload, schema=schema)
