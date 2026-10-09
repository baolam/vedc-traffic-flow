"""Compatibility imports for the shared control library."""
import sys
from pathlib import Path

_root = next(p for p in Path(__file__).resolve().parents if (p / "src" / "control").is_dir())
if str(_root) not in sys.path:
    sys.path.insert(0, str(_root))
from src.control.actuator import *  # noqa: F401,F403
