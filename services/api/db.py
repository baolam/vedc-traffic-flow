"""
EdgeFlow AI — Database Storage Engine.

Provides persistent storage for:
- Signal Fault Events (disconnect, feedback_error, emergency, hardware)
- Telemetry history (flow rates, queues, phases)
- Control commands & ACKs
- Device health heartbeats

Uses SQLite with Write-Ahead Logging (WAL) by default, thread-safe with an
asynchronous background write queue to prevent MQTT and HTTP I/O blocking.
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

logger = logging.getLogger("edgeflow-db")

def _default_db_path() -> Path:
    """<repo>/data/edgeflow.db from a checkout; <dir of db.py>/data/edgeflow.db in the API container,
    where db.py sits at /app/db.py and has no grandparent (parents[2] raised IndexError at import)."""
    env_path = os.getenv("EDGEFLOW_DB_PATH")
    if env_path:
        return Path(env_path)
    if Path("/data").is_dir() or Path("/data").exists():
        return Path("/data/edgeflow.db")
    parents = Path(__file__).resolve().parents
    root = parents[2] if len(parents) > 2 else parents[0]
    return root / "data" / "edgeflow.db"


DEFAULT_DB_PATH = _default_db_path()
_get_default_db_path = _default_db_path


class DatabaseManager:
    """Thread-safe SQLite Database Manager with WAL mode and asynchronous batch queue."""

    def __init__(self, db_path: Optional[str] = None):
        self.db_path = Path(db_path or os.getenv("EDGEFLOW_DB_PATH") or DEFAULT_DB_PATH)
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        self._write_queue: queue.Queue = queue.Queue(maxsize=10000)
        self._stop_event = threading.Event()
        self._worker_thread: Optional[threading.Thread] = None
        self._lock = threading.Lock()
        self.init_db()
        self.start_worker()

    def _get_connection(self) -> sqlite3.Connection:
        conn = sqlite3.connect(str(self.db_path), timeout=10.0, check_same_thread=False)
        conn.row_factory = sqlite3.Row
        conn.execute("PRAGMA journal_mode=WAL;")
        conn.execute("PRAGMA synchronous=NORMAL;")
        return conn

    def init_db(self):
        """Initialize database schema tables and indexes."""
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("""
            CREATE TABLE IF NOT EXISTS signal_fault_events (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                event_id TEXT UNIQUE,
                node_id TEXT NOT NULL,
                category TEXT NOT NULL,
                fault_code TEXT NOT NULL,
                severity TEXT NOT NULL,
                current_phase TEXT,
                target_phase TEXT,
                clearance_state TEXT,
                reason TEXT,
                details_json TEXT,
                timestamp_ms INTEGER NOT NULL,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            );
            """)

            cursor.execute("""
            CREATE TABLE IF NOT EXISTS telemetry_history (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                node_id TEXT NOT NULL,
                source_type TEXT,
                current_phase_id TEXT,
                queue_vehicles REAL,
                flow_veh_per_s REAL,
                approaches_json TEXT,
                timestamp_ms INTEGER NOT NULL,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            );
            """)

            cursor.execute("""
            CREATE TABLE IF NOT EXISTS control_commands_history (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                command_id TEXT,
                node_id TEXT NOT NULL,
                target_phase_id TEXT NOT NULL,
                controller TEXT,
                min_green_s REAL,
                max_green_s REAL,
                timestamp_ms INTEGER NOT NULL,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            );
            """)

            cursor.execute("""
            CREATE TABLE IF NOT EXISTS control_acks_history (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                command_id TEXT NOT NULL,
                node_id TEXT NOT NULL,
                target_phase_id TEXT,
                status TEXT NOT NULL,
                reason TEXT,
                timestamp_ms INTEGER NOT NULL,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            );
            """)

            cursor.execute("""
            CREATE TABLE IF NOT EXISTS device_health_history (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                node_id TEXT NOT NULL,
                service TEXT NOT NULL,
                status TEXT NOT NULL,
                current_phase TEXT,
                clearance TEXT,
                safe_stop INTEGER,
                uptime_s INTEGER,
                wifi_rssi_dbm INTEGER,
                timestamp_ms INTEGER NOT NULL,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            );
            """)

            # Indexes for high-performance time-series queries
            cursor.execute("CREATE INDEX IF NOT EXISTS idx_faults_node_time ON signal_fault_events(node_id, timestamp_ms);")
            cursor.execute("CREATE INDEX IF NOT EXISTS idx_faults_category ON signal_fault_events(category, timestamp_ms);")
            cursor.execute("CREATE INDEX IF NOT EXISTS idx_telemetry_node_time ON telemetry_history(node_id, timestamp_ms);")
            cursor.execute("CREATE INDEX IF NOT EXISTS idx_commands_node_time ON control_commands_history(node_id, timestamp_ms);")
            cursor.execute("CREATE INDEX IF NOT EXISTS idx_acks_node_time ON control_acks_history(node_id, timestamp_ms);")
            cursor.execute("CREATE INDEX IF NOT EXISTS idx_health_node_time ON device_health_history(node_id, timestamp_ms);")
            conn.commit()
            logger.info(f"Database initialized successfully at {self.db_path} (WAL mode).")

    def start_worker(self):
        """Start background queue worker thread."""
        if self._worker_thread is None or not self._worker_thread.is_alive():
            self._stop_event.clear()
            self._worker_thread = threading.Thread(target=self._worker_loop, daemon=True, name="edgeflow-db-worker")
            self._worker_thread.start()

    def stop_worker(self):
        """Stop worker and flush queue."""
        self._stop_event.set()
        if self._worker_thread and self._worker_thread.is_alive():
            self._worker_thread.join(timeout=3.0)

    def _worker_loop(self):
        """Background thread consuming write tasks from queue."""
        conn = self._get_connection()
        while not self._stop_event.is_set() or not self._write_queue.empty():
            try:
                task = self._write_queue.get(timeout=0.2)
            except queue.Empty:
                continue

            try:
                sql, params = task
                conn.execute(sql, params)
                conn.commit()
            except Exception as e:
                logger.error(f"Error executing DB write task: {e}")
            finally:
                self._write_queue.task_done()
        conn.close()

    def _enqueue_or_execute(self, sql: str, params: tuple, sync: bool = False):
        if sync:
            with self._get_connection() as conn:
                conn.execute(sql, params)
                conn.commit()
        else:
            try:
                self._write_queue.put_nowait((sql, params))
            except queue.Full:
                logger.warning("DB write queue full, falling back to sync write.")
                with self._get_connection() as conn:
                    conn.execute(sql, params)
                    conn.commit()

    # -------------------------------------------------------------------------
    # Ingestion Methods
    # -------------------------------------------------------------------------

    def record_fault_event(self, fault: Dict[str, Any], sync: bool = False):
        """Record a SignalFaultEvent."""
        event_id = fault.get("event_id") or f"fault-{fault.get('node_id')}-{int(time.time() * 1000)}"
        sql = """
        INSERT OR REPLACE INTO signal_fault_events 
        (event_id, node_id, category, fault_code, severity, current_phase, target_phase, clearance_state, reason, details_json, timestamp_ms)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?);
        """
        params = (
            event_id,
            fault.get("node_id", "unknown"),
            fault.get("category", "disconnect"),
            fault.get("fault_code", "ERR_COORDINATOR_TIMEOUT"),
            fault.get("severity", "WARNING"),
            fault.get("current_phase"),
            fault.get("target_phase"),
            fault.get("clearance_state"),
            fault.get("reason"),
            json.dumps(fault.get("details", {}) or {}),
            int(fault.get("timestamp_ms") or int(time.time() * 1000))
        )
        self._enqueue_or_execute(sql, params, sync=sync)

    def record_telemetry(self, telemetry: Dict[str, Any], sync: bool = False):
        """Record a Telemetry snapshot."""
        approaches = telemetry.get("approaches", []) or []
        total_q = sum(float(a.get("queue_vehicles", 0.0)) for a in approaches)
        total_flow = sum(float(a.get("flow_veh_per_s", 0.0)) for a in approaches)

        sql = """
        INSERT INTO telemetry_history 
        (node_id, source_type, current_phase_id, queue_vehicles, flow_veh_per_s, approaches_json, timestamp_ms)
        VALUES (?, ?, ?, ?, ?, ?, ?);
        """
        params = (
            telemetry.get("node_id", "unknown"),
            telemetry.get("source_type", "vision"),
            telemetry.get("current_phase_id"),
            round(total_q, 2),
            round(total_flow, 3),
            json.dumps(approaches),
            int(telemetry.get("timestamp_ms") or int(time.time() * 1000))
        )
        self._enqueue_or_execute(sql, params, sync=sync)

    def record_command(self, cmd: Dict[str, Any], sync: bool = False):
        """Record an outgoing ControlCommand."""
        sql = """
        INSERT INTO control_commands_history 
        (command_id, node_id, target_phase_id, controller, min_green_s, max_green_s, timestamp_ms)
        VALUES (?, ?, ?, ?, ?, ?, ?);
        """
        params = (
            cmd.get("command_id", "unknown"),
            cmd.get("node_id", "unknown"),
            cmd.get("target_phase_id", "unknown"),
            cmd.get("controller", "unknown"),
            float(cmd.get("min_green_s", 5.0)),
            float(cmd.get("max_green_s", 60.0)),
            int(cmd.get("timestamp_ms") or int(time.time() * 1000))
        )
        self._enqueue_or_execute(sql, params, sync=sync)

    def record_ack(self, ack: Dict[str, Any], sync: bool = False):
        """Record an incoming ControlACK."""
        sql = """
        INSERT INTO control_acks_history 
        (command_id, node_id, target_phase_id, status, reason, timestamp_ms)
        VALUES (?, ?, ?, ?, ?, ?);
        """
        params = (
            ack.get("command_id", "unknown"),
            ack.get("node_id", "unknown"),
            ack.get("target_phase_id"),
            ack.get("status", "UNKNOWN"),
            ack.get("reason", ""),
            int(ack.get("timestamp_ms") or int(time.time() * 1000))
        )
        self._enqueue_or_execute(sql, params, sync=sync)

    def record_health(self, health: Dict[str, Any], sync: bool = False):
        """Record a device health heartbeat."""
        sql = """
        INSERT INTO device_health_history 
        (node_id, service, status, current_phase, clearance, safe_stop, uptime_s, wifi_rssi_dbm, timestamp_ms)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?);
        """
        params = (
            health.get("node_id") or health.get("service") or "unknown",
            health.get("service", "esp32_actuator"),
            health.get("status", "HEALTHY"),
            health.get("current_phase"),
            health.get("clearance"),
            1 if health.get("safe_stop") else 0,
            int(health.get("uptime_s", 0) or 0),
            int(health.get("wifi_rssi_dbm", 0) or 0),
            int(health.get("timestamp_ms") or int(time.time() * 1000))
        )
        self._enqueue_or_execute(sql, params, sync=sync)

    # -------------------------------------------------------------------------
    # Query Methods
    # -------------------------------------------------------------------------

    def query_faults(
        self,
        node_id: Optional[str] = None,
        category: Optional[str] = None,
        severity: Optional[str] = None,
        from_ms: Optional[int] = None,
        to_ms: Optional[int] = None,
        limit: int = 50,
        offset: int = 0
    ) -> List[Dict[str, Any]]:
        """Query signal fault events with filtering."""
        query = "SELECT * FROM signal_fault_events WHERE 1=1"
        params: List[Any] = []

        if node_id:
            query += " AND node_id = ?"
            params.append(node_id)
        if category:
            query += " AND category = ?"
            params.append(category)
        if severity:
            query += " AND severity = ?"
            params.append(severity)
        if from_ms is not None:
            query += " AND timestamp_ms >= ?"
            params.append(from_ms)
        if to_ms is not None:
            query += " AND timestamp_ms <= ?"
            params.append(to_ms)

        query += " ORDER BY timestamp_ms DESC LIMIT ? OFFSET ?;"
        params.extend([min(limit, 500), max(offset, 0)])

        with self._get_connection() as conn:
            cursor = conn.cursor()
            rows = cursor.execute(query, params).fetchall()
            results = []
            for r in rows:
                item = dict(r)
                if item.get("details_json"):
                    try:
                        item["details"] = json.loads(item["details_json"])
                    except Exception:
                        item["details"] = {}
                results.append(item)
            return results

    def query_telemetry(
        self,
        node_id: Optional[str] = None,
        from_ms: Optional[int] = None,
        to_ms: Optional[int] = None,
        limit: int = 100
    ) -> List[Dict[str, Any]]:
        """Query historical telemetry."""
        query = "SELECT * FROM telemetry_history WHERE 1=1"
        params: List[Any] = []

        if node_id:
            query += " AND node_id = ?"
            params.append(node_id)
        if from_ms is not None:
            query += " AND timestamp_ms >= ?"
            params.append(from_ms)
        if to_ms is not None:
            query += " AND timestamp_ms <= ?"
            params.append(to_ms)

        query += " ORDER BY timestamp_ms DESC LIMIT ?;"
        params.append(min(limit, 1000))

        with self._get_connection() as conn:
            cursor = conn.cursor()
            rows = cursor.execute(query, params).fetchall()
            results = []
            for r in rows:
                item = dict(r)
                if item.get("approaches_json"):
                    try:
                        item["approaches"] = json.loads(item["approaches_json"])
                    except Exception:
                        item["approaches"] = []
                results.append(item)
            return results

    def query_commands(self, node_id: Optional[str] = None, limit: int = 50) -> List[Dict[str, Any]]:
        query = "SELECT * FROM control_commands_history WHERE 1=1"
        params: List[Any] = []
        if node_id:
            query += " AND node_id = ?"
            params.append(node_id)
        query += " ORDER BY timestamp_ms DESC LIMIT ?;"
        params.append(min(limit, 500))

        with self._get_connection() as conn:
            return [dict(r) for r in conn.execute(query, params).fetchall()]

    def query_acks(self, node_id: Optional[str] = None, limit: int = 50) -> List[Dict[str, Any]]:
        query = "SELECT * FROM control_acks_history WHERE 1=1"
        params: List[Any] = []
        if node_id:
            query += " AND node_id = ?"
            params.append(node_id)
        query += " ORDER BY timestamp_ms DESC LIMIT ?;"
        params.append(min(limit, 500))

        with self._get_connection() as conn:
            return [dict(r) for r in conn.execute(query, params).fetchall()]

    def query_stats(self) -> Dict[str, Any]:
        """Aggregate statistical summary of operations and faults."""
        with self._get_connection() as conn:
            cursor = conn.cursor()

            # Fault counts by category
            fault_rows = cursor.execute(
                "SELECT category, COUNT(*) as cnt FROM signal_fault_events GROUP BY category;"
            ).fetchall()
            fault_counts = {r["category"]: r["cnt"] for r in fault_rows}

            total_faults = cursor.execute("SELECT COUNT(*) FROM signal_fault_events;").fetchone()[0]
            total_commands = cursor.execute("SELECT COUNT(*) FROM control_commands_history;").fetchone()[0]
            total_acks = cursor.execute("SELECT COUNT(*) FROM control_acks_history;").fetchone()[0]
            total_telemetry = cursor.execute("SELECT COUNT(*) FROM telemetry_history;").fetchone()[0]

            ack_status_rows = cursor.execute(
                "SELECT status, COUNT(*) as cnt FROM control_acks_history GROUP BY status;"
            ).fetchall()
            ack_status_counts = {r["status"]: r["cnt"] for r in ack_status_rows}

            applied_acks = ack_status_counts.get("APPLIED", 0)
            applied_rate = round((applied_acks / max(total_acks, 1)) * 100.0, 2)

            return {
                "total_faults": total_faults,
                "faults_by_category": {
                    "disconnect": fault_counts.get("disconnect", 0),
                    "feedback_error": fault_counts.get("feedback_error", 0),
                    "emergency": fault_counts.get("emergency", 0),
                    "hardware": fault_counts.get("hardware", 0),
                },
                "total_commands": total_commands,
                "total_acks": total_acks,
                "total_telemetry_records": total_telemetry,
                "ack_status_counts": ack_status_counts,
                "command_success_rate_percent": applied_rate,
            }


# Singleton instance
_DB_INSTANCE: Optional[DatabaseManager] = None
_INIT_LOCK = threading.Lock()


def get_db(db_path: Optional[str] = None) -> DatabaseManager:
    global _DB_INSTANCE
    with _INIT_LOCK:
        if _DB_INSTANCE is None:
            _DB_INSTANCE = DatabaseManager(db_path=db_path)
        return _DB_INSTANCE
