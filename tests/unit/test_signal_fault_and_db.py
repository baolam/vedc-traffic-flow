"""
Unit tests for Dedicated Signal Fault MQTT Channels and Database Storage Engine.
"""

import os
import json
import time
import pytest
from pathlib import Path

from contracts import contracts_sdk, topics
from services.api.db import DatabaseManager


class TestSignalFaultAndDatabase:

    @pytest.fixture
    def temp_db(self, tmp_path):
        db_file = tmp_path / "test_edgeflow.db"
        db = DatabaseManager(db_path=str(db_file))
        yield db
        db.stop_worker()

    # =========================================================================
    # 1. Dedicated MQTT Topics & Contract Validation
    # =========================================================================

    def test_dedicated_mqtt_topics(self):
        """Verify dedicated topic patterns for each fault category."""
        assert topics.get_signal_fault_topic("J1", "disconnect") == "edgeflow/v1/signal_fault/J1/disconnect"
        assert topics.get_signal_fault_topic("J1", "feedback_error") == "edgeflow/v1/signal_fault/J1/feedback_error"
        assert topics.get_signal_fault_topic("J1", "emergency") == "edgeflow/v1/signal_fault/J1/emergency"
        assert topics.get_signal_fault_topic("J1", "hardware") == "edgeflow/v1/signal_fault/J1/hardware"

        assert topics.SIGNAL_FAULT_SUB_PATTERN == "edgeflow/v1/signal_fault/#"

    def test_signal_fault_schema_validation(self):
        """Verify SignalFaultEvent schema validation on valid and invalid payloads."""
        now_ms = int(time.time() * 1000)

        # Valid disconnect fault
        disconnect_evt = {
            "event_id": "evt-d-1",
            "node_id": "J1",
            "category": "disconnect",
            "fault_code": "ERR_COORDINATOR_TIMEOUT",
            "severity": "WARNING",
            "current_phase": "J1_PHASE_NS",
            "clearance_state": "GREEN",
            "reason": "Coordinator timed out after 5.0s",
            "timestamp_ms": now_ms
        }
        contracts_sdk.validate_payload(disconnect_evt, "signal_fault_event")

        # Valid emergency fault (safe-stop engaged)
        emergency_evt = {
            "event_id": "evt-e-1",
            "node_id": "J1",
            "category": "emergency",
            "fault_code": "ERR_SAFE_STOP_ENGAGED",
            "severity": "CRITICAL",
            "current_phase": "J1_PHASE_NS",
            "clearance_state": "FLASHING_YELLOW",
            "reason": "Safe-stop button pressed",
            "details": {"gpio": 16},
            "timestamp_ms": now_ms
        }
        contracts_sdk.validate_payload(emergency_evt, "signal_fault_event")

        # Valid feedback error
        feedback_evt = {
            "event_id": "evt-f-1",
            "node_id": "J1",
            "category": "feedback_error",
            "fault_code": "ERR_FEEDBACK_MISMATCH",
            "severity": "WARNING",
            "current_phase": "J1_PHASE_NS",
            "target_phase": "INVALID_PHASE",
            "clearance_state": "GREEN",
            "reason": "Target phase does not match topology",
            "timestamp_ms": now_ms
        }
        contracts_sdk.validate_payload(feedback_evt, "signal_fault_event")

    # =========================================================================
    # 2. Database Storage Engine CRUD & Aggregation
    # =========================================================================

    def test_database_fault_recording_and_queries(self, temp_db):
        """Verify recording and filtering of signal fault events in database."""
        now_ms = 1700000000000

        # Insert 3 different fault events synchronously
        temp_db.record_fault_event({
            "event_id": "evt-1",
            "node_id": "J1",
            "category": "disconnect",
            "fault_code": "ERR_COORDINATOR_TIMEOUT",
            "severity": "WARNING",
            "reason": "Coordinator lost",
            "timestamp_ms": now_ms
        }, sync=True)

        temp_db.record_fault_event({
            "event_id": "evt-2",
            "node_id": "J1",
            "category": "emergency",
            "fault_code": "ERR_SAFE_STOP_ENGAGED",
            "severity": "CRITICAL",
            "reason": "Safe-stop button pressed",
            "timestamp_ms": now_ms + 1000
        }, sync=True)

        temp_db.record_fault_event({
            "event_id": "evt-3",
            "node_id": "J2",
            "category": "feedback_error",
            "fault_code": "ERR_FEEDBACK_MISMATCH",
            "severity": "WARNING",
            "reason": "Phase mismatch",
            "timestamp_ms": now_ms + 2000
        }, sync=True)

        # Query all
        all_faults = temp_db.query_faults()
        assert len(all_faults) == 3

        # Filter by node_id
        j1_faults = temp_db.query_faults(node_id="J1")
        assert len(j1_faults) == 2

        # Filter by category
        emergencies = temp_db.query_faults(category="emergency")
        assert len(emergencies) == 1
        assert emergencies[0]["fault_code"] == "ERR_SAFE_STOP_ENGAGED"

        # Filter by severity
        criticals = temp_db.query_faults(severity="CRITICAL")
        assert len(criticals) == 1

    def test_database_telemetry_commands_acks_and_stats(self, temp_db):
        """Verify telemetry, commands, and ACKs recording and summary stats."""
        now_ms = 1700000000000

        temp_db.record_telemetry({
            "node_id": "J1",
            "source_type": "vision",
            "current_phase_id": "J1_PHASE_NS",
            "approaches": [
                {"approach_id": "J1_N_IN", "queue_vehicles": 5.0, "flow_veh_per_s": 0.5},
                {"approach_id": "J1_S_IN", "queue_vehicles": 3.0, "flow_veh_per_s": 0.3}
            ],
            "timestamp_ms": now_ms
        }, sync=True)

        temp_db.record_command({
            "command_id": "cmd-1",
            "node_id": "J1",
            "target_phase_id": "J1_PHASE_EW",
            "controller": "max_pressure",
            "min_green_s": 5.0,
            "max_green_s": 60.0,
            "timestamp_ms": now_ms
        }, sync=True)

        temp_db.record_ack({
            "command_id": "cmd-1",
            "node_id": "J1",
            "target_phase_id": "J1_PHASE_EW",
            "status": "APPLIED",
            "reason": "Clearance complete",
            "timestamp_ms": now_ms + 5000
        }, sync=True)

        # Query telemetry
        telemetry = temp_db.query_telemetry(node_id="J1")
        assert len(telemetry) == 1
        assert telemetry[0]["queue_vehicles"] == 8.0

        # Query commands & ACKs
        cmds = temp_db.query_commands(node_id="J1")
        assert len(cmds) == 1
        assert cmds[0]["controller"] == "max_pressure"

        acks = temp_db.query_acks(node_id="J1")
        assert len(acks) == 1
        assert acks[0]["status"] == "APPLIED"

        # Check aggregated stats
        stats = temp_db.query_stats()
        assert stats["total_commands"] == 1
        assert stats["total_acks"] == 1
        assert stats["total_telemetry_records"] == 1
        assert stats["command_success_rate_percent"] == 100.0

    def test_station_registry_replace_and_query(self, temp_db):
        """Verify the station_registry cache round-trips contracts_sdk.list_station_records()
        and that replace_station_registry() is a full replace, not an upsert."""
        records = contracts_sdk.list_station_records()
        temp_db.replace_station_registry(records)

        all_rows = temp_db.query_stations()
        assert len(all_rows) == len(records)

        hcm_rows = temp_db.query_stations(topology_id="hcm_corridor")
        assert len(hcm_rows) == 50
        assert all(r["lat"] is not None and r["lng"] is not None for r in hcm_rows)

        sim_rows = temp_db.query_stations(topology_id="four_intersection_v1")
        assert len(sim_rows) == 4
        assert all(r["lat"] is None for r in sim_rows)

        search_rows = temp_db.query_stations(q="J1")
        assert any(r["node_id"] == "J1" for r in search_rows)

        # A second rebuild from a smaller record set must not leave stale rows behind.
        temp_db.replace_station_registry(contracts_sdk.list_station_records("four_intersection_v1"))
        assert len(temp_db.query_stations()) == 4

    # =========================================================================
    # 3. Virtual ESP32 Simulator Fault Emission
    # =========================================================================

    def test_esp32_simulator_emits_disconnect_and_emergency_faults(self):
        """Verify virtual ESP32 simulator emits typed faults on timeout, emergency, and mismatch."""
        from src.hardware.demo.esp32_simulator import Esp32Logic
        import src.hardware.demo.mqtt_common as mc

        timing = mc.Timing()
        acks = []
        faults = []

        logic = Esp32Logic(
            node_id="J1",
            timing=timing,
            now=0.0,
            emit_ack=lambda *a: acks.append(a),
            emit_health=lambda: None,
            clock_synced=True,
            epoch_ms=lambda: 1700000000000,
            emit_fault=lambda f: faults.append(f)
        )

        # Boot = startup flash, then the 5 s watchdog runs: step the clock past both without commands
        t = 0.0
        while t < timing.boot_s + timing.watchdog_s + 1.0:
            t += 0.1
            logic.tick(t)
        assert logic.fallback is True

        # Check emitted fault
        disconnect_faults = [f for f in faults if f["category"] == "disconnect"]
        assert len(disconnect_faults) == 1
        assert disconnect_faults[0]["fault_code"] == "ERR_COORDINATOR_TIMEOUT"

        # Test safe-stop button pressed
        logic.set_safe_stop(True, t)
        emergency_faults = [f for f in faults if f["category"] == "emergency" and f["fault_code"] == "ERR_SAFE_STOP_ENGAGED"]
        assert len(emergency_faults) == 1
        assert emergency_faults[0]["severity"] == "CRITICAL"

        # Test safe-stop released
        logic.set_safe_stop(False, t + 1.0)
        release_faults = [f for f in faults if f["category"] == "emergency" and f["fault_code"] == "ERR_SAFE_STOP_RELEASED"]
        assert len(release_faults) == 1

        # Test unknown phase command -> feedback error
        invalid_cmd = {
            "command_id": "cmd-err",
            "node_id": "J1",
            "target_phase_id": "J1_INVALID_PHASE",
            "min_green_s": 5,
            "max_green_s": 60
        }
        logic.handle_command(json.dumps(invalid_cmd).encode(), t + 2.0)
        feedback_faults = [f for f in faults if f["category"] == "feedback_error"]
        assert len(feedback_faults) == 1
        assert feedback_faults[0]["fault_code"] == "ERR_FEEDBACK_MISMATCH"

    # =========================================================================
    # 4. REST API History Endpoints
    # =========================================================================

    def test_api_history_endpoints(self):
        """Verify API endpoints for historical data retrieval and fault injection."""
        from fastapi.testclient import TestClient
        from services.api.main import app

        client = TestClient(app)

        # Inject a fault via HTTP endpoint
        res = client.post("/api/v1/control/fault", json={
            "node_id": "J1",
            "category": "emergency",
            "fault_code": "ERR_SAFE_STOP_ENGAGED",
            "severity": "CRITICAL",
            "reason": "Test emergency injection via API",
            "timestamp_ms": int(time.time() * 1000)
        })
        assert res.status_code == 200
        data = res.json()
        assert data["status"] == "SUCCESS"

        # Query history faults
        res_faults = client.get("/api/v1/history/faults?node_id=J1&category=emergency")
        assert res_faults.status_code == 200
        faults_data = res_faults.json()
        assert faults_data["status"] == "SUCCESS"
        assert faults_data["total"] >= 1
        assert any(f["fault_code"] == "ERR_SAFE_STOP_ENGAGED" for f in faults_data["faults"])

        # Query history stats
        res_stats = client.get("/api/v1/history/stats")
        assert res_stats.status_code == 200
        stats = res_stats.json()
        assert "total_faults" in stats
        assert "faults_by_category" in stats

    def test_signal_fault_invalid_schema_rejection(self):
        """Verify strict schema rejections for invalid fault categories or codes."""
        import jsonschema

        # Invalid category
        with pytest.raises(jsonschema.ValidationError):
            contracts_sdk.validate_payload({
                "event_id": "err-1",
                "node_id": "J1",
                "category": "non_existent_category",
                "fault_code": "ERR_COORDINATOR_TIMEOUT",
                "severity": "WARNING",
                "timestamp_ms": 1000
            }, "signal_fault_event")

        # Invalid fault_code
        with pytest.raises(jsonschema.ValidationError):
            contracts_sdk.validate_payload({
                "event_id": "err-2",
                "node_id": "J1",
                "category": "disconnect",
                "fault_code": "CUSTOM_UNDEFINED_CODE",
                "severity": "WARNING",
                "timestamp_ms": 1000
            }, "signal_fault_event")

        # Invalid severity
        with pytest.raises(jsonschema.ValidationError):
            contracts_sdk.validate_payload({
                "event_id": "err-3",
                "node_id": "J1",
                "category": "disconnect",
                "fault_code": "ERR_COORDINATOR_TIMEOUT",
                "severity": "FATAL_UNKNOWN",
                "timestamp_ms": 1000
            }, "signal_fault_event")

    def test_database_time_range_and_pagination(self, temp_db):
        """Verify DB filtering by timestamp window and pagination (limit & offset)."""
        base_time = 1_000_000
        for i in range(10):
            temp_db.record_fault_event({
                "event_id": f"evt-seq-{i}",
                "node_id": "J1",
                "category": "hardware" if i % 2 == 0 else "disconnect",
                "fault_code": "ERR_HARDWARE_DEFECT" if i % 2 == 0 else "ERR_COORDINATOR_TIMEOUT",
                "severity": "WARNING",
                "timestamp_ms": base_time + (i * 1000)
            }, sync=True)

        # Time range: between index 2 and index 6 (inclusive)
        window = temp_db.query_faults(
            from_ms=base_time + 2000,
            to_ms=base_time + 6000
        )
        assert len(window) == 5

        # Pagination: limit 3, offset 2
        paged = temp_db.query_faults(limit=3, offset=2)
        assert len(paged) == 3
        # Should be sorted descending by timestamp
        assert paged[0]["timestamp_ms"] == base_time + 7000
        assert paged[1]["timestamp_ms"] == base_time + 6000
        assert paged[2]["timestamp_ms"] == base_time + 5000

    def test_database_async_batch_queue_worker(self, temp_db):
        """Verify asynchronous enqueueing handles high volume without dropping records."""
        total_items = 40
        for i in range(total_items):
            temp_db.record_fault_event({
                "event_id": f"evt-async-{i}",
                "node_id": "J1",
                "category": "disconnect",
                "fault_code": "ERR_COORDINATOR_TIMEOUT",
                "severity": "WARNING",
                "timestamp_ms": 2_000_000 + i
            }, sync=False)

        # Allow worker thread to drain queue
        time.sleep(0.5)
        records = temp_db.query_faults(limit=100)
        assert len(records) == total_items

    def test_network_state_includes_signal_faults(self):
        """Verify /api/v1/network/state includes live signal_faults field."""
        from fastapi.testclient import TestClient
        from services.api.main import app, LIVE_STATE

        client = TestClient(app)
        res = client.get("/api/v1/network/state")
        assert res.status_code == 200
        data = res.json()
        assert "signal_faults" in data
        assert isinstance(data["signal_faults"], dict)
