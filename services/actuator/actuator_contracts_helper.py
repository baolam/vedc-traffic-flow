import json
from pathlib import Path
from typing import Dict, Any
import jsonschema

import os

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
    return Path("/contracts")

CONTRACTS_DIR = _get_contracts_dir()

def load_schema(schema_name: str) -> Dict[str, Any]:
    schema_file = CONTRACTS_DIR / "schemas" / f"{schema_name}.json"
    if not schema_file.exists():
        raise FileNotFoundError(f"Schema file not found: {schema_file}")
    with open(schema_file, "r", encoding="utf-8") as f:
        return json.load(f)

def validate_payload(payload: Dict[str, Any], schema_name: str) -> None:
    schema = load_schema(schema_name)
    jsonschema.validate(instance=payload, schema=schema)
