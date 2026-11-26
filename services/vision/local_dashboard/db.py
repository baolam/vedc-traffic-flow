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
            cursor.execute("""
            CREATE TABLE IF NOT EXISTS alert_log (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                alert_id TEXT NOT NULL,
                node_id TEXT NOT NULL,
                severity TEXT NOT NULL,
                tamper_type TEXT NOT NULL,
                status TEXT NOT NULL,
                reason TEXT,
                details_json TEXT,
                timestamp_ms INTEGER NOT NULL,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            );
            """)
            cursor.execute("CREATE INDEX IF NOT EXISTS idx_vision_telemetry_time ON telemetry_history(node_id, timestamp_ms);")
            cursor.execute("CREATE INDEX IF NOT EXISTS idx_vision_health_time ON health_history(timestamp_ms);")
            cursor.execute("CREATE INDEX IF NOT EXISTS idx_vision_events_time ON event_log(timestamp_ms);")
            cursor.execute("CREATE INDEX IF NOT EXISTS idx_vision_alerts_time ON alert_log(timestamp_ms);")
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

    def record_alert(self, alert: Dict[str, Any]):
        self._enqueue(
            "INSERT INTO alert_log (alert_id, node_id, severity, tamper_type, status, reason, details_json, timestamp_ms) "
            "VALUES (?, ?, ?, ?, ?, ?, ?, ?);",
            (
                alert.get("alert_id", ""),
                alert.get("node_id", ""),
                alert.get("severity", "WARNING"),
                alert.get("tamper_type", "unknown"),
                alert.get("status", "ACTIVE"),
                alert.get("reason", ""),
                json.dumps(alert.get("details", {})),
                alert.get("timestamp_ms") or int(time.time() * 1000),
            ),
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

    def query_alerts(self, node_id: Optional[str] = None, limit: int = 100) -> List[Dict[str, Any]]:
        sql = "SELECT * FROM alert_log WHERE 1=1"
        params: List[Any] = []
        if node_id:
            sql += " AND node_id = ?"
            params.append(node_id)
        sql += " ORDER BY timestamp_ms DESC LIMIT ?;"
        params.append(min(limit, 1000))
        with self._get_connection() as conn:
            rows = [dict(r) for r in conn.execute(sql, params).fetchall()]
        for r in rows:
            r["details"] = json.loads(r.pop("details_json") or "{}")
        return rows

    def get_stats(self) -> Dict[str, Any]:
        """Returns storage metrics, table row counts, and timestamps for internal DB."""
        file_size = self.db_path.stat().st_size if self.db_path.is_file() else 0
        wal_path = self.db_path.parent / f"{self.db_path.name}-wal"
        wal_size = wal_path.stat().st_size if wal_path.is_file() else 0

        counts = {}
        with self._get_connection() as conn:
            for tbl in ("telemetry_history", "health_history", "event_log", "alert_log"):
                try:
                    c = conn.execute(f"SELECT COUNT(*) FROM {tbl};").fetchone()[0]
                    counts[tbl] = c
                except sqlite3.OperationalError:
                    counts[tbl] = 0

            # Find earliest and latest timestamps across tables
            min_ts, max_ts = None, None
            try:
                row = conn.execute(
                    "SELECT MIN(timestamp_ms), MAX(timestamp_ms) FROM telemetry_history;"
                ).fetchone()
                if row and row[0] is not None:
                    min_ts, max_ts = row[0], row[1]
            except sqlite3.OperationalError:
                pass

        total_rows = sum(counts.values())
        return {
            "db_path": str(self.db_path),
            "file_size_bytes": file_size,
            "file_size_formatted": f"{file_size / (1024 * 1024):.2f} MB" if file_size >= 1048576 else f"{file_size / 1024:.1f} KB",
            "wal_size_bytes": wal_size,
            "wal_size_formatted": f"{wal_size / (1024 * 1024):.2f} MB" if wal_size >= 1048576 else f"{wal_size / 1024:.1f} KB",
            "table_counts": counts,
            "total_records": total_rows,
            "retention_days": self.retention_days,
            "earliest_timestamp_ms": min_ts,
            "latest_timestamp_ms": max_ts,
        }

    def prune(self, now_ms: Optional[int] = None, retention_days: Optional[float] = None) -> Dict[str, int]:
        """Delete rows older than retention_days -- keeps the SD card from filling up.
        Returns the number of deleted records per table."""
        days = retention_days if retention_days is not None else self.retention_days
        cutoff_ms = (now_ms or int(time.time() * 1000)) - int(days * 86400 * 1000)
        deleted = {}
        with self._get_connection() as conn:
            for tbl in ("telemetry_history", "health_history", "event_log", "alert_log"):
                cur = conn.execute(f"DELETE FROM {tbl} WHERE timestamp_ms < ?;", (cutoff_ms,))
                deleted[tbl] = cur.rowcount
            conn.commit()
        deleted["total_deleted"] = sum(deleted.values())
        return deleted

    def vacuum(self) -> bool:
        """Runs SQLite VACUUM to reclaim free space and defragment database pages."""
        try:
            with self._get_connection() as conn:
                conn.execute("VACUUM;")
            return True
        except Exception as e:
            logger.error(f"VACUUM failed: {e}")
            return False

    def clear(self, tables: Optional[List[str]] = None) -> Dict[str, int]:
        """Clears specified tables (or all tables if None). Returns deleted row counts."""
        target_tables = tables or ["telemetry_history", "health_history", "event_log", "alert_log"]
        deleted = {}
        with self._get_connection() as conn:
            for tbl in target_tables:
                if tbl in ("telemetry_history", "health_history", "event_log", "alert_log"):
                    cur = conn.execute(f"DELETE FROM {tbl};")
                    deleted[tbl] = cur.rowcount
            conn.commit()
        deleted["total_deleted"] = sum(deleted.values())
        return deleted


class NullLocalDB:
    """No-op stand-in used when LOCAL_DB_ENABLED=false, so callers never need an `if` check."""
    enabled = False

    def record_telemetry(self, *args, **kwargs):
        pass

    def record_health(self, *args, **kwargs):
        pass

    def record_event(self, *args, **kwargs):
        pass

    def record_alert(self, *args, **kwargs):
        pass

    def query_telemetry(self, *args, **kwargs):
        return []

    def query_health(self, *args, **kwargs):
        return []

    def query_events(self, *args, **kwargs):
        return []

    def query_alerts(self, *args, **kwargs):
        return []

    def prune(self, *args, **kwargs):
        return {"total_deleted": 0}

    def vacuum(self, *args, **kwargs):
        return True

    def clear(self, *args, **kwargs):
        return {"total_deleted": 0}

    def get_stats(self, *args, **kwargs):
        return {
            "db_path": "",
            "file_size_bytes": 0,
            "file_size_formatted": "0 KB",
            "wal_size_bytes": 0,
            "wal_size_formatted": "0 KB",
            "table_counts": {},
            "total_records": 0,
            "retention_days": 14.0,
            "earliest_timestamp_ms": None,
            "latest_timestamp_ms": None,
        }

    def close(self):
        pass
