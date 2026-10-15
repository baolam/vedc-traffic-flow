"""
Unit tests for Device Signal Loss & Abrupt Disconnection Resilience.

Verifies system safety invariants when hardware abruptly loses connection:
1. Camera disconnection / Frame grab failure -> Zero-confidence telemetry.
2. Camera packet loss / Timeout -> Gateway decision suppression.
3. Neighbor intersection camera death -> Correlated corridor safety halt.
4. ESP32 Actuator heartbeat timeout (>6s) -> Vision command lockout.
5. Actuator safe-stop / hardware fault -> Cache eviction and command refusal.
6. Delayed / buffered command recovery -> Expiration rejection (EXPIRED ACK).
"""

import time
import pytest
from contracts.contracts_sdk import load_topology, validate_payload
from src.control.gateway import ControlGateway
from src.control.controllers import FixedTimeController
from src.control.actuator import ActuatorStateMachine
from services.vision.main import build_telemetry


class TestDeviceSignalLossResilience:
    @pytest.fixture
    def setup_system(self):
        topology = load_topology("tabletop_j1_j2_v1")
        controller = FixedTimeController(cycle_time_s=60.0)
        gateway = ControlGateway(
            controller=controller,
            topology=topology,
            controller_id="failover-guard",
            state_max_age_ms=2000,   # 2.0s telemetry timeout
            command_ttl_ms=3000
        )
        actuator = ActuatorStateMachine(yellow_duration_s=3.0, all_red_duration_s=2.0)
        return gateway, actuator, topology

    # =========================================================================
    # Scenario 1: Camera Disconnection / Frame Failure
    # =========================================================================

    def test_camera_disconnect_yields_zero_confidence_telemetry(self, setup_system):
        """When camera is unplugged or fails to read frames, build_telemetry must report 0.0 confidence."""
        _, _, topology = setup_system
        node_j1 = next(n for n in topology["nodes"] if n["node_id"] == "J1")

        # Empty approaches list simulates camera frame grab failure
        telemetry = build_telemetry(node=node_j1, approaches=[], sim_time_s=10.0, timestamp_ms=10000)

        assert telemetry["node_id"] == "J1"
        assert telemetry["source_type"] == "vision"
        assert len(telemetry["approaches"]) == 4

        # Invariant: Never fabricate high-confidence queues on dead sensors
        for app in telemetry["approaches"]:
            assert app["confidence"] == 0.0
            assert app["queue_vehicles"] == 0.0
            assert app["flow_veh_per_s"] == 0.0

        validate_payload(telemetry, "telemetry")

    def test_gateway_halts_on_zero_confidence_telemetry(self, setup_system):
        """Gateway must reject zero-confidence camera observations and make no control decision."""
        gateway, _, topology = setup_system
        node_j1 = next(n for n in topology["nodes"] if n["node_id"] == "J1")
        now_ms = 100000

        # Ingest actuator health first
        gateway.ingest_health({
            "service": "esp32_actuator",
            "node_id": "J1",
            "status": "HEALTHY",
            "current_phase": "J1_PHASE_NS",
            "clearance": "GREEN",
            "safe_stop": False,
            "timestamp_ms": now_ms
        }, now_ms=now_ms)

        # Disconnected camera telemetry
        dead_telemetry = build_telemetry(node=node_j1, approaches=[], sim_time_s=100.0, timestamp_ms=now_ms)

        cmd = gateway.decision(dead_telemetry, now_ms=now_ms)
        assert cmd is None, "Gateway must not issue commands when camera confidence is 0"

    # =========================================================================
    # Scenario 2: Sudden Telemetry Packet Drop / Camera Network Timeout
    # =========================================================================

    def test_gateway_halts_when_camera_telemetry_expires(self, setup_system):
        """When camera stops sending data across network, gateway halts commands after state_max_age_ms."""
        gateway, _, _ = setup_system
        now_ms = 100000

        # Initial healthy state for J1 & J2
        gateway.ingest_health({
            "service": "esp32_actuator", "node_id": "J1", "status": "HEALTHY",
            "current_phase": "J1_PHASE_NS", "clearance": "GREEN", "safe_stop": False, "timestamp_ms": now_ms
        }, now_ms=now_ms)
        gateway.ingest_health({
            "service": "esp32_actuator", "node_id": "J2", "status": "HEALTHY",
            "current_phase": "J2_PHASE_NS", "clearance": "GREEN", "safe_stop": False, "timestamp_ms": now_ms
        }, now_ms=now_ms)

        telem_j2 = {
            "node_id": "J2", "source_type": "vision", "timestamp_ms": now_ms, "current_phase_id": "J2_PHASE_NS",
            "approaches": [{"approach_id": f"J2_{d}_IN", "queue_vehicles": 0.0, "confidence": 0.9,
                            "flow_veh_per_s": 0.0, "mean_speed_mps": 0.0, "occupancy_ratio": 0.0}
                           for d in ("N", "S", "E", "W")]
        }
        gateway.decision(telem_j2, now_ms=now_ms)

        # J1 transmits valid frame at t=now_ms
        telem_j1 = {
            "node_id": "J1", "source_type": "vision", "timestamp_ms": now_ms, "current_phase_id": "J1_PHASE_NS",
            "approaches": [{"approach_id": f"J1_{d}_IN", "queue_vehicles": 2.0, "confidence": 0.9,
                            "flow_veh_per_s": 0.1, "mean_speed_mps": 4.0, "occupancy_ratio": 0.1}
                           for d in ("N", "S", "E", "W")]
        }
        cmd_valid = gateway.decision(telem_j1, now_ms=now_ms)
        assert cmd_valid is not None

        # Camera J1 abruptly loses connection. Next check is at now_ms + 2500ms (> max_age 2000ms)
        later_ms = now_ms + 2500
        # Re-sending or querying with delayed/stale packet:
        cmd_stale = gateway.decision(telem_j1, now_ms=later_ms)
        assert cmd_stale is None, "Gateway must reject stale camera telemetry past timeout window"

    # =========================================================================
    # Scenario 3: Correlated Safety — Neighbor Intersection Camera Drops Signal
    # =========================================================================

    def test_gateway_halts_when_neighbor_camera_dies(self, setup_system):
        """In corridor topology, if neighbor J2 camera dies, J1 must halt decisions to prevent blind spillover."""
        gateway, _, _ = setup_system
        t0 = 100000

        # Actuators are healthy
        for nid in ("J1", "J2"):
            gateway.ingest_health({
                "service": "esp32_actuator", "node_id": nid, "status": "HEALTHY",
                "current_phase": f"{nid}_PHASE_NS", "clearance": "GREEN", "safe_stop": False, "timestamp_ms": t0
            }, now_ms=t0)

        # Both J1 & J2 cameras report at t0
        telem_j1 = {
            "node_id": "J1", "source_type": "vision", "timestamp_ms": t0, "current_phase_id": "J1_PHASE_NS",
            "approaches": [{"approach_id": f"J1_{d}_IN", "queue_vehicles": 3.0, "confidence": 0.9,
                            "flow_veh_per_s": 0.2, "mean_speed_mps": 3.0, "occupancy_ratio": 0.1}
                           for d in ("N", "S", "E", "W")]
        }
        telem_j2 = {
            "node_id": "J2", "source_type": "vision", "timestamp_ms": t0, "current_phase_id": "J2_PHASE_NS",
            "approaches": [{"approach_id": f"J2_{d}_IN", "queue_vehicles": 0.0, "confidence": 0.9,
                            "flow_veh_per_s": 0.0, "mean_speed_mps": 0.0, "occupancy_ratio": 0.0}
                           for d in ("N", "S", "E", "W")]
        }

        gateway.decision(telem_j2, now_ms=t0)
        assert gateway.decision(telem_j1, now_ms=t0) is not None

        # At t0 + 2500ms, J2 camera abruptly disconnects (no telemetry from J2). J1 camera is still alive.
        t1 = t0 + 2500
        for nid in ("J1", "J2"):
            gateway.ingest_health({
                "service": "esp32_actuator", "node_id": nid, "status": "HEALTHY",
                "current_phase": f"{nid}_PHASE_NS", "clearance": "GREEN", "safe_stop": False, "timestamp_ms": t1
            }, now_ms=t1)

        telem_j1_fresh = {
            "node_id": "J1", "source_type": "vision", "timestamp_ms": t1, "current_phase_id": "J1_PHASE_NS",
            "approaches": [{"approach_id": f"J1_{d}_IN", "queue_vehicles": 4.0, "confidence": 0.9,
                            "flow_veh_per_s": 0.2, "mean_speed_mps": 3.0, "occupancy_ratio": 0.15}
                           for d in ("N", "S", "E", "W")]
        }

        # J1 decision must be SUPPRESSED because downstream neighbor J2 state is dead/missing
        cmd_j1 = gateway.decision(telem_j1_fresh, now_ms=t1)
        assert cmd_j1 is None, "J1 cannot safely route traffic into unmonitored dead neighbor J2"

    # =========================================================================
    # Scenario 4: Actuator ESP32 Heartbeat Loss (>6s timeout)
    # =========================================================================

    def test_gateway_halts_when_actuator_heartbeat_stops(self, setup_system):
        """If ESP32 hardware actuator heartbeat drops for >6s, vision commands must be halted."""
        gateway, _, _ = setup_system
        t0 = 100000

        # Actuator heartbeats arrived at t0
        gateway.ingest_health({
            "service": "esp32_actuator", "node_id": "J1", "status": "HEALTHY",
            "current_phase": "J1_PHASE_NS", "clearance": "GREEN", "safe_stop": False, "timestamp_ms": t0
        }, now_ms=t0)
        gateway.ingest_health({
            "service": "esp32_actuator", "node_id": "J2", "status": "HEALTHY",
            "current_phase": "J2_PHASE_NS", "clearance": "GREEN", "safe_stop": False, "timestamp_ms": t0
        }, now_ms=t0)

        # Advance clock by 7 seconds (actuator heartbeat lost)
        t_heartbeat_lost = t0 + 7000

        telem_j1 = {
            "node_id": "J1", "source_type": "vision", "timestamp_ms": t_heartbeat_lost,
            "current_phase_id": "J1_PHASE_NS",
            "approaches": [{"approach_id": f"J1_{d}_IN", "queue_vehicles": 2.0, "confidence": 0.9,
                            "flow_veh_per_s": 0.1, "mean_speed_mps": 4.0, "occupancy_ratio": 0.1}
                           for d in ("N", "S", "E", "W")]
        }

        # Decision must return None because physical actuator is unresponsive
        cmd = gateway.decision(telem_j1, now_ms=t_heartbeat_lost)
        assert cmd is None, "Gateway must not command actuator whose heartbeat has timed out"

    # =========================================================================
    # Scenario 5: Actuator Enters Emergency Safe-Stop / Fault
    # =========================================================================

    def test_actuator_safe_stop_evicts_cache_and_halts_commands(self, setup_system):
        """When hardware triggers safe-stop, gateway immediately clears cached node state."""
        gateway, _, _ = setup_system
        now_ms = 100000

        # Normal healthy operation
        gateway.ingest_health({
            "service": "esp32_actuator", "node_id": "J1", "status": "HEALTHY",
            "current_phase": "J1_PHASE_NS", "clearance": "GREEN", "safe_stop": False, "timestamp_ms": now_ms
        }, now_ms=now_ms)
        gateway.ingest_health({
            "service": "esp32_actuator", "node_id": "J2", "status": "HEALTHY",
            "current_phase": "J2_PHASE_NS", "clearance": "GREEN", "safe_stop": False, "timestamp_ms": now_ms
        }, now_ms=now_ms)

        telem_j1 = {
            "node_id": "J1", "source_type": "vision", "timestamp_ms": now_ms, "current_phase_id": "J1_PHASE_NS",
            "approaches": [{"approach_id": f"J1_{d}_IN", "queue_vehicles": 2.0, "confidence": 0.9,
                            "flow_veh_per_s": 0.1, "mean_speed_mps": 4.0, "occupancy_ratio": 0.1}
                           for d in ("N", "S", "E", "W")]
        }
        telem_j2 = {
            "node_id": "J2", "source_type": "vision", "timestamp_ms": now_ms, "current_phase_id": "J2_PHASE_NS",
            "approaches": [{"approach_id": f"J2_{d}_IN", "queue_vehicles": 0.0, "confidence": 0.9,
                            "flow_veh_per_s": 0.0, "mean_speed_mps": 0.0, "occupancy_ratio": 0.0}
                           for d in ("N", "S", "E", "W")]
        }
        gateway.decision(telem_j2, now_ms=now_ms)
        gateway.decision(telem_j1, now_ms=now_ms)
        assert "J1" in gateway.state

        # Actuator J1 abruptly triggers SAFE STOP (e.g. physical conflict / button press)
        gateway.ingest_health({
            "service": "esp32_actuator",
            "node_id": "J1",
            "status": "FALLBACK_AUTONOMOUS",
            "safe_stop": True,
            "clearance": "RED",
            "timestamp_ms": now_ms + 100
        }, now_ms=now_ms + 100)

        # Cache must be evicted
        assert "J1" not in gateway.state, "J1 must be purged from state cache during safe-stop"

        # Subsequent decisions must be denied
        cmd_blocked = gateway.decision(telem_j1, now_ms=now_ms + 100)
        assert cmd_blocked is None

    # =========================================================================
    # Scenario 6: Network Reconnect Delivers Buffered / Expired Commands
    # =========================================================================

    def test_actuator_rejects_expired_command_after_network_reconnect(self, setup_system):
        """When network restores and delivers buffered old commands, actuator rejects with EXPIRED."""
        _, actuator, _ = setup_system

        # Controller generated command at t=100s with TTL 5s (expires at 105s)
        old_command = {
            "command_id": "cmd-delayed-101",
            "node_id": "J1",
            "target_phase_id": "J1_PHASE_EW",
            "min_green_s": 10.0,
            "max_green_s": 45.0,
            "controller": "max_pressure",
            "timestamp_ms": 100000,
            "expires_at_ms": 105000  # Expires at 105.0s
        }

        # Network connection dropped for 8 seconds and reconnected at t=108s
        reconnect_time_s = 108.0

        ack = actuator.process_command(old_command, now=reconnect_time_s)

        # Must reject: Stale commands must never execute after reconnect
        assert ack["status"] == "EXPIRED"
        assert "expired" in ack["reason"].lower()
        validate_payload(ack, "control_ack")
