import sys
import os
from pathlib import Path
from typing import Dict, Any

# Ensure contracts root is in sys.path for importing contracts_sdk
contracts_dir = Path(__file__).resolve().parents[2] / "contracts"
if str(contracts_dir) not in sys.path:
    sys.path.insert(0, str(contracts_dir))

try:
    import contracts_sdk
except ImportError:
    import contracts.contracts_sdk as contracts_sdk

def load_schema(schema_name: str) -> Dict[str, Any]:
    return contracts_sdk.load_schema(schema_name)

def validate_payload(payload: Dict[str, Any], schema_name: str) -> None:
    contracts_sdk.validate_payload(payload, schema_name)
