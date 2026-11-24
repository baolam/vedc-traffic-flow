"""
Pytest-wide fixtures.

Points EDGEFLOW_DB_PATH at a fresh temp file *before* any test module is
collected, so `services/api/main.py`'s module-level `db = get_db()` (a
process-wide singleton, see services/api/db.py) opens an isolated SQLite file
per test session instead of the real dev DB at data/edgeflow.db. Without
this, repeated pytest runs share one WAL-mode file with whatever process ran
last, which is what caused the intermittent sqlite3.DatabaseError in
test_list_approaches.
"""
import os
import tempfile
from pathlib import Path

_tmp_dir = tempfile.mkdtemp(prefix="edgeflow_test_db_")
os.environ.setdefault("EDGEFLOW_DB_PATH", str(Path(_tmp_dir) / "test_edgeflow.db"))
