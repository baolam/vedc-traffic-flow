"""
EdgeFlow AI -- Vision Local Dashboard: on-device SQLite history.

Stores, on this device only, exactly the canonical telemetry/health payloads this process
already publishes to MQTT (see supervisor.py), plus an operational event log for actions taken
through the local dashboard (restart, ROI reload, setting changes). Mirrors the shape/idioms of
services/api/db.py (WAL mode, async write queue so MQTT/camera timing is never blocked) but is a
separate, independent store -- not imported from services/api, per AGENTS.md's Microservice
Isolation rule.
"""

import os
import json
import sqlite3
import threading
import queue
import time
import logging
from pathlib import Path
from typing import Dict, Any, List, Optional

logger = logging.getLogger("vision-local-db")


def _default_db_path() -> Path:
    """<repo>/services/vision/data/vision.db from a checkout; /data/vision.db in a container."""
    env_path = os.getenv("LOCAL_DB_PATH")
    if env_path:
        return Path(env_path)
    if Path("/data").is_dir():
        return Path("/data/vision.db")
    return Path(__file__).resolve().parents[1] / "data" / "vision.db"


class VisionLocalDB:
    """Thread-safe SQLite store for this device's own telemetry/health history + event log."""

    def __init__(self, db_path: Optional[str] = None, retention_days: float = 14.0):
        self.enabled = True
        self.retention_days = retention_days
        self.db_path = Path(db_path) if db_path else _default_db_path()
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        self._write_queue: "queue.Queue" = queue.Queue(maxsize=5000)
        self._stop_event = threading.Event()
        self._worker_thread: Optional[threading.Thread] = None
        self._init_db()
        self._start_worker()

    def _get_connection(self) -> sqlite3.Connection:
        conn = sqlite3.connect(str(self.db_path), timeout=10.0, check_same_thread=False)
        conn.row_factory = sqlite3.Row
        conn.execute("PRAGMA journal_mode=WAL;")
        conn.execute("PRAGMA synchronous=NORMAL;")
        return conn

    def _init_db(self):
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("""
            CREATE TABLE IF NOT EXISTS telemetry_history (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                node_id TEXT NOT NULL,
                current_phase_id TEXT,
                approaches_json TEXT,
                timestamp_ms INTEGER NOT NULL,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            );
            """)
            cursor.execute("""
            CREATE TABLE IF NOT EXISTS health_history (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                status TEXT,
                runtime_json TEXT,
                hardware_json TEXT,
                timestamp_ms INTEGER NOT NULL,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            );
            """)
            cursor.execute("""
            CREATE TABLE IF NOT EXISTS event_log (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                event_type TEXT NOT NULL,
                detail_json TEXT,
                timestamp_ms INTEGER NOT NULL,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            );
            """)
            cursor.execute("CREATE INDEX IF NOT EXISTS idx_vision_telemetry_time ON telemetry_history(node_id, timestamp_ms);")
            cursor.execute("CREATE INDEX IF NOT EXISTS idx_vision_health_time ON health_history(timestamp_ms);")
            cursor.execute("CREATE INDEX IF NOT EXISTS idx_vision_events_time ON event_log(timestamp_ms);")
            conn.commit()
            logger.info(f"Vision local DB initialized at {self.db_path} (WAL mode).")

    def _start_worker(self):
        self._stop_event.clear()
        self._worker_thread = threading.Thread(target=self._worker_loop, daemon=True, name="vision-db-worker")
        self._worker_thread.start()

    def close(self):
        self._stop_event.set()
        if self._worker_thread and self._worker_thread.is_alive():
            self._worker_thread.join(timeout=3.0)

    def _worker_loop(self):
        conn = self._get_connection()
        while not self._stop_event.is_set() or not self._write_queue.empty():
            try:
                sql, params = self._write_queue.get(timeout=0.2)
            except queue.Empty:
                continue
            try:
                conn.execute(sql, params)
                conn.commit()
            except Exception as e:
                logger.error(f"Vision local DB write failed: {e}")
            finally:
                self._write_queue.task_done()
        conn.close()

    def _enqueue(self, sql: str, params: tuple):
        try:
            self._write_queue.put_nowait((sql, params))
        except queue.Full:
            logger.warning("Vision local DB write queue full, dropping record.")

    # -------------------------------------------------------------------------
    # Ingestion -- called with the same payloads already published to MQTT
    # -------------------------------------------------------------------------

    def record_telemetry(self, telemetry: Dict[str, Any]):
        """telemetry is the exact canonical payload supervisor.py already builds via build_telemetry()
        and publishes to MQTT -- same shape, just also kept here."""
        self._enqueue(
            "INSERT INTO telemetry_history (node_id, current_phase_id, approaches_json, timestamp_ms) VALUES (?, ?, ?, ?);",
            (telemetry.get("node_id"), telemetry.get("current_phase_id"),
             json.dumps(telemetry.get("approaches", [])), telemetry.get("timestamp_ms") or int(time.time() * 1000)),
        )

    def record_health(self, health: Dict[str, Any]):
        self._enqueue(
            "INSERT INTO health_history (status, runtime_json, hardware_json, timestamp_ms) VALUES (?, ?, ?, ?);",
            (health.get("status"), json.dumps(health.get("runtime", {})), json.dumps(health.get("hardware", {})),
             health.get("timestamp_ms") or int(time.time() * 1000)),
        )

    def record_event(self, event_type: str, detail: Optional[Dict[str, Any]] = None):
        self._enqueue(
            "INSERT INTO event_log (event_type, detail_json, timestamp_ms) VALUES (?, ?, ?);",
            (event_type, json.dumps(detail or {}), int(time.time() * 1000)),
        )

    # -------------------------------------------------------------------------
    # Queries
    # -------------------------------------------------------------------------

    def query_telemetry(self, node_id: Optional[str] = None, limit: int = 100) -> List[Dict[str, Any]]:
        sql = "SELECT * FROM telemetry_history WHERE 1=1"
        params: List[Any] = []
        if node_id:
            sql += " AND node_id = ?"
            params.append(node_id)
        sql += " ORDER BY timestamp_ms DESC LIMIT ?;"
        params.append(min(limit, 1000))
        with self._get_connection() as conn:
            rows = [dict(r) for r in conn.execute(sql, params).fetchall()]
        for r in rows:
            r["approaches"] = json.loads(r.pop("approaches_json") or "[]")
        return rows

    def query_health(self, limit: int = 100) -> List[Dict[str, Any]]:
        with self._get_connection() as conn:
            rows = [dict(r) for r in conn.execute(
                "SELECT * FROM health_history ORDER BY timestamp_ms DESC LIMIT ?;", (min(limit, 1000),)
            ).fetchall()]
        for r in rows:
            r["runtime"] = json.loads(r.pop("runtime_json") or "{}")
            r["hardware"] = json.loads(r.pop("hardware_json") or "{}")
        return rows

    def query_events(self, limit: int = 100) -> List[Dict[str, Any]]:
        with self._get_connection() as conn:
            rows = [dict(r) for r in conn.execute(
                "SELECT * FROM event_log ORDER BY timestamp_ms DESC LIMIT ?;", (min(limit, 1000),)
            ).fetchall()]
        for r in rows:
            r["detail"] = json.loads(r.pop("detail_json") or "{}")
        return rows

    def prune(self, now_ms: Optional[int] = None):
        """Delete rows older than retention_days -- keeps the SD card from filling up."""
        cutoff_ms = (now_ms or int(time.time() * 1000)) - int(self.retention_days * 86400 * 1000)
        with self._get_connection() as conn:
            conn.execute("DELETE FROM telemetry_history WHERE timestamp_ms < ?;", (cutoff_ms,))
            conn.execute("DELETE FROM health_history WHERE timestamp_ms < ?;", (cutoff_ms,))
            conn.execute("DELETE FROM event_log WHERE timestamp_ms < ?;", (cutoff_ms,))
            conn.commit()


class NullLocalDB:
    """No-op stand-in used when LOCAL_DB_ENABLED=false, so callers never need an `if` check."""
    enabled = False

    def record_telemetry(self, *args, **kwargs):
        pass

    def record_health(self, *args, **kwargs):
        pass

    def record_event(self, *args, **kwargs):
        pass

    def query_telemetry(self, *args, **kwargs):
        return []

    def query_health(self, *args, **kwargs):
        return []

    def query_events(self, *args, **kwargs):
        return []

    def prune(self, *args, **kwargs):
        pass

    def close(self):
        pass
