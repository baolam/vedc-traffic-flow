import sys
import os
from pathlib import Path
from typing import Dict, Any

# Ensure services/vision directory is in sys.path for IDE & module resolution
CURR_DIR = Path(__file__).resolve().parent
if str(CURR_DIR) not in sys.path:
    sys.path.insert(0, str(CURR_DIR))

def _get_contracts_dir() -> Path:
    env_dir = os.getenv("CONTRACTS_DIR")
    if env_dir and Path(env_dir).exists():
        return Path(env_dir)
    if Path("/contracts").exists():
        return Path("/contracts")
    curr = Path(__file__).resolve().parent
    for p in [curr] + list(curr.parents):
        if (p / "contracts").is_dir():
            return p / "contracts"
        if (p / "contracts_sdk.py").is_file():
            return p
    return Path("/contracts")

contracts_dir = _get_contracts_dir()
if str(contracts_dir) not in sys.path:
    sys.path.insert(0, str(contracts_dir))

try:
    import contracts_sdk
except ImportError:
    import contracts.contracts_sdk as contracts_sdk

def load_topology(topology_id: str = "four_intersection_v1") -> Dict[str, Any]:
    return contracts_sdk.load_topology(topology_id)

def load_schema(schema_name: str) -> Dict[str, Any]:
    return contracts_sdk.load_schema(schema_name)

def validate_payload(payload: Dict[str, Any], schema_name: str) -> None:
    contracts_sdk.validate_payload(payload, schema_name)
