"""
Unit tests for the 5-Layer Graph-Control Noise Immunity & Fault Resilience Pipeline.

Covers:
  1. Single-frame vision spike rejection (+20 vehicles impulse noise does not flip phase).
  2. Sustained genuine queue growth smoothly switches phase.
  3. Stale & out-of-order timestamp rejection + silent zombie neighbor TTL eviction.
  4. Dedicated `signal_fault` integration: J1 `emergency` halts commands to J1 AND triggers
     upstream spillback gating on neighbor J2 (both MaxPressure & EdgeFlow controllers).
  5. Feedback error cooldown (`ERR_CONFLICT_GUARD_TRIGGERED`) & disconnect cache reset.
  6. Partial single-approach low-confidence holdover & anti-starvation floor.
  7. K-tick debouncer & in-flight Yellow/All-Red clearance lock.
  8. Outbound command TTL (`expires_at_ms`) & high-rate duplicate coalescing.
"""

import importlib.util
import sys
from pathlib import Path
from typing import Dict, Any, Optional

import pytest

from contracts.contracts_sdk import load_topology, validate_payload
from src.control.controllers import MaxPressureController, EdgeFlowController

_GC_DIR = Path(__file__).resolve().parents[2] / "services" / "graph-control"

_ns_spec = importlib.util.spec_from_file_location("gc_noise_shield", _GC_DIR / "noise_shield.py")
noise_shield = importlib.util.module_from_spec(_ns_spec)
sys.modules[_ns_spec.name] = noise_shield
_ns_spec.loader.exec_module(noise_shield)

_rg_spec = importlib.util.spec_from_file_location("gc_runtime_guards_ni", _GC_DIR / "runtime_guards.py")
runtime_guards = importlib.util.module_from_spec(_rg_spec)
sys.modules[_rg_spec.name] = runtime_guards
_rg_spec.loader.exec_module(runtime_guards)


class ManualClock:
    def __init__(self, start_s: float = 1000.0) -> None:
        self.t = start_s

    def __call__(self) -> float:
        return self.t

    @property
    def ms(self) -> int:
        return int(self.t * 1000)

    def advance(self, dt_s: float) -> None:
        self.t += dt_s


def make_telemetry(
    node_id: str,
    phase_id: str,
    queues: Dict[str, float],
    timestamp_ms: int,
    occ: Optional[Dict[str, float]] = None,
    conf: Optional[Dict[str, float]] = None,
) -> Dict[str, Any]:
    occ = occ or {}
    conf = conf or {}
    approaches = []
    for suffix in ("N_IN", "S_IN", "E_IN", "W_IN"):
        aid = f"{node_id}_{suffix}"
        q = float(queues.get(aid, queues.get(suffix, 0.0)))
        o = float(occ.get(aid, occ.get(suffix, min(1.0, q / 25.0))))
        c = float(conf.get(aid, conf.get(suffix, 0.95)))
        approaches.append(
            {
                "approach_id": aid,
                "queue_vehicles": q,
                "flow_veh_per_s": round(min(0.5, q * 0.04), 3),
                "mean_speed_mps": 8.5,
                "occupancy_ratio": o,
                "confidence": c,
            }
        )
    payload = {
        "node_id": node_id,
        "source_type": "vision",
        "current_phase_id": phase_id,
        "timestamp_ms": timestamp_ms,
        "approaches": approaches,
    }
    validate_payload(payload, "telemetry")
    return payload


# =============================================================================
# 1. Spike Rejection & Sustained Real Demand
# =============================================================================

@pytest.mark.parametrize("controller_cls", [MaxPressureController, EdgeFlowController])
def test_single_frame_vision_spike_does_not_flip_phase(controller_cls):
    """A sudden +20 vehicle 1-frame camera glitch on EW must NOT flip NS green."""
    topology = load_topology("tabletop_j1_j2_v1")
    clock = ManualClock(start_s=100.0)
    controller = controller_cls()
    gate = runtime_guards.BlindNodeGate()
    shield = noise_shield.NoiseShieldPipeline(republish_interval_s=0.0, clock=clock)
    network_state: Dict[str, Any] = {}

    # Baseline ticks: NS has 7 vehicles, EW has 1 vehicle -> NS stays green
    for _ in range(3):
        clock.advance(2.5)
        tel = make_telemetry("J1", "J1_PHASE_NS", {"N_IN": 4.0, "S_IN": 3.0, "E_IN": 1.0, "W_IN": 0.0}, clock.ms)
        cmd = shield.process_telemetry("J1", tel, topology, network_state, controller, blind_gate=gate)
        assert cmd is not None
        assert cmd["target_phase_id"] == "J1_PHASE_NS"

    # Inject a massive +20 vehicle 1-frame false-positive spike on E_IN (1.0 -> 21.0)!
    clock.advance(1.0)
    spike_tel = make_telemetry("J1", "J1_PHASE_NS", {"N_IN": 4.0, "S_IN": 3.0, "E_IN": 21.0, "W_IN": 0.0}, clock.ms)
    cmd_spike = shield.process_telemetry("J1", spike_tel, topology, network_state, controller, blind_gate=gate)

    assert cmd_spike is not None
    assert cmd_spike["target_phase_id"] == "J1_PHASE_NS", "1-frame +20 spike must not cause a false phase flip"

    # Filtered queue stored in network_state must be physically clamped well below 21.0
    e_in_filtered = next(a for a in network_state["J1"]["approaches"] if a["approach_id"] == "J1_E_IN")
    assert e_in_filtered["queue_vehicles"] < 5.0

    # Next frame returns to normal -> still rock-solid on NS
    clock.advance(1.0)
    recover_tel = make_telemetry("J1", "J1_PHASE_NS", {"N_IN": 4.0, "S_IN": 3.0, "E_IN": 1.0, "W_IN": 0.0}, clock.ms)
    cmd_after = shield.process_telemetry("J1", recover_tel, topology, network_state, controller, blind_gate=gate)
    assert cmd_after["target_phase_id"] == "J1_PHASE_NS"


def test_sustained_real_demand_smoothly_switches_phase():
    """When EW congestion is real and persists across multiple ticks, the shield allows the switch."""
    topology = load_topology("tabletop_j1_j2_v1")
    clock = ManualClock(start_s=200.0)
    controller = MaxPressureController()
    shield = noise_shield.NoiseShieldPipeline(republish_interval_s=0.0, debounce_ticks=2, clock=clock)
    network_state: Dict[str, Any] = {}

    # Initial NS traffic
    tel0 = make_telemetry("J1", "J1_PHASE_NS", {"N_IN": 3.0, "S_IN": 2.0, "E_IN": 1.0, "W_IN": 0.0}, clock.ms)
    assert shield.process_telemetry("J1", tel0, topology, network_state, controller)["target_phase_id"] == "J1_PHASE_NS"

    # Sustained heavy EW queue (16 vehicles on E_IN, NS cleared to 1 vehicle)
    switched = False
    for _ in range(6):
        clock.advance(1.5)
        tel = make_telemetry("J1", "J1_PHASE_NS", {"N_IN": 1.0, "S_IN": 0.0, "E_IN": 16.0, "W_IN": 4.0}, clock.ms)
        cmd = shield.process_telemetry("J1", tel, topology, network_state, controller)
        if cmd["target_phase_id"] == "J1_PHASE_EW":
            switched = True
            break

    assert switched is True, "Sustained real queue must pass filter + debounce and switch to EW"


# =============================================================================
# 2. Stale / Out-of-Order Timestamps & Silent Zombie Neighbor TTL
# =============================================================================

def test_stale_and_out_of_order_timestamps_rejected():
    """Packets older than max_telemetry_age_ms or with non-monotonic timestamp_ms are dropped."""
    topology = load_topology("tabletop_j1_j2_v1")
    clock = ManualClock(start_s=500.0)
    controller = MaxPressureController()
    shield = noise_shield.NoiseShieldPipeline(
        max_telemetry_age_ms=5000, republish_interval_s=0.0, clock=clock
    )
    network_state: Dict[str, Any] = {}

    # 1. Stale packet (7 seconds old > 5s max age) -> rejected
    stale = make_telemetry("J1", "J1_PHASE_NS", {"N_IN": 5.0}, timestamp_ms=clock.ms - 7000)
    assert shield.process_telemetry("J1", stale, topology, network_state, controller) is None
    assert "J1" not in network_state

    # 2. Fresh valid packet -> admitted
    fresh = make_telemetry("J1", "J1_PHASE_NS", {"N_IN": 5.0}, timestamp_ms=clock.ms - 200)
    assert shield.process_telemetry("J1", fresh, topology, network_state, controller) is not None
    assert "J1" in network_state

    # 3. Duplicate timestamp -> rejected
    dup = make_telemetry("J1", "J1_PHASE_NS", {"E_IN": 20.0}, timestamp_ms=clock.ms - 200)
    assert shield.process_telemetry("J1", dup, topology, network_state, controller) is None

    # 4. Out-of-order delayed packet (older than previous accepted timestamp) -> rejected
    clock.advance(1.0)
    delayed = make_telemetry("J1", "J1_PHASE_NS", {"E_IN": 20.0}, timestamp_ms=clock.ms - 1500)
    assert shield.process_telemetry("J1", delayed, topology, network_state, controller) is None


def test_zombie_neighbor_evicted_after_ttl():
    """If neighbor J2 silently disconnects without sending blind packets, its stale congestion expires."""
    topology = load_topology("tabletop_j1_j2_v1")
    clock = ManualClock(start_s=1000.0)
    controller = MaxPressureController()
    shield = noise_shield.NoiseShieldPipeline(
        neighbor_ttl_s=8.0, debounce_ticks=1, republish_interval_s=0.0, clock=clock
    )
    network_state: Dict[str, Any] = {}

    # J2 reports severe congestion on J2_W_IN (25 vehicles).
    # In tabletop_j1_j2_v1, J1_PHASE_EW movement J1_W_IN -> J2_W_IN has turn_ratio=0.8.
    j2_jammed = make_telemetry("J2", "J2_PHASE_NS", {"W_IN": 25.0}, timestamp_ms=clock.ms)
    shield.process_telemetry("J2", j2_jammed, topology, network_state, controller)
    assert "J2" in network_state

    # At t=1001s (J2 still fresh): J1 has W_IN=10, N_IN=4.
    # Because J2_W_IN=25 -> EW pressure = 10 - 0.8*25 = -10 < NS pressure (4) -> J1 holds NS!
    clock.advance(1.0)
    for _ in range(4):
        clock.advance(0.5)
        j1_tel = make_telemetry("J1", "J1_PHASE_NS", {"N_IN": 4.0, "W_IN": 10.0}, timestamp_ms=clock.ms)
        cmd = shield.process_telemetry("J1", j1_tel, topology, network_state, controller)
    assert cmd["target_phase_id"] == "J1_PHASE_NS"

    # Now J2 goes completely silent for > 8.0s (zombie neighbor!)
    clock.advance(9.0)
    j1_tel_later = make_telemetry("J1", "J1_PHASE_NS", {"N_IN": 4.0, "W_IN": 10.0}, timestamp_ms=clock.ms)
    cmd_after_evict = shield.process_telemetry("J1", j1_tel_later, topology, network_state, controller)

    assert "J2" not in network_state, "Silent neighbor J2 must be evicted once neighbor_ttl_s expires"
    assert cmd_after_evict["target_phase_id"] == "J1_PHASE_EW", "J1 must stop gating EW once zombie J2 state is evicted"


# =============================================================================
# 3. Dedicated `signal_fault` Channel: Emergency Lockout & Neighbor Spillback Gating
# =============================================================================

@pytest.mark.parametrize("controller_cls", [MaxPressureController, EdgeFlowController])
def test_signal_fault_emergency_halts_j1_and_gates_upstream_neighbor_j2(controller_cls):
    """
    When J1 publishes ERR_SAFE_STOP_ENGAGED on edgeflow/v1/signal_fault/J1/emergency:
      1. Graph-control stops issuing commands to J1 (circuit breaker OPEN).
      2. A schema-valid virtual spillback barrier is maintained for J1 even past neighbor_ttl_s
         and even if J1's camera keeps sending 0-queue telemetry.
      3. Neighbor J2 (whose J2_PHASE_EW feeds into J1_E_IN) automatically gates EW and switches to NS!
      4. Upon ERR_SAFE_STOP_RELEASED, both J1 and J2 resume normal operation.
    """
    topology = load_topology("tabletop_j1_j2_v1")
    clock = ManualClock(start_s=2000.0)
    controller = controller_cls()
    shield = noise_shield.NoiseShieldPipeline(
        neighbor_ttl_s=8.0, debounce_ticks=1, clearance_lock_s=0.0, republish_interval_s=0.0, clock=clock
    )
    network_state: Dict[str, Any] = {}

    # Normal baseline: J1 is completely clear (0 vehicles); J2 has E_IN=9 (heading to J1) and N_IN=5 -> J2 serves EW
    j1_clear = make_telemetry("J1", "J1_PHASE_EW", {"E_IN": 0.0, "N_IN": 1.0}, timestamp_ms=clock.ms)
    assert shield.process_telemetry("J1", j1_clear, topology, network_state, controller) is not None

    for _ in range(4):
        clock.advance(1.5)
        j2_tel = make_telemetry("J2", "J2_PHASE_EW", {"E_IN": 9.0, "N_IN": 5.0}, timestamp_ms=clock.ms)
        j2_cmd = shield.process_telemetry("J2", j2_tel, topology, network_state, controller)
    assert j2_cmd["target_phase_id"] == "J2_PHASE_EW"

    # Operator presses emergency Safe-Stop button on J1!
    clock.advance(1.0)
    emergency_event = {
        "event_id": f"evt-J1-{clock.ms}",
        "node_id": "J1",
        "category": "emergency",
        "fault_code": "ERR_SAFE_STOP_ENGAGED",
        "severity": "CRITICAL",
        "current_phase": "J1_PHASE_EW",
        "clearance_state": "FLASHING_YELLOW",
        "reason": "Physical safe-stop button pressed by user",
        "timestamp_ms": clock.ms,
    }
    validate_payload(emergency_event, "signal_fault_event")
    shield.handle_fault(emergency_event, topology=topology, network_state=network_state)

    # Virtual barrier in network_state["J1"] must itself conform to canonical telemetry schema
    assert "J1" in network_state
    validate_payload(network_state["J1"], "telemetry")

    # Even 12s later (> neighbor_ttl_s) and even when J1 camera reports empty roads, J1 commands remain blocked
    # and the virtual barrier is NOT overwritten or pruned!
    clock.advance(12.0)
    j1_empty_cam = make_telemetry("J1", "J1_PHASE_EW", {"E_IN": 0.0, "N_IN": 0.0}, timestamp_ms=clock.ms)
    assert shield.process_telemetry("J1", j1_empty_cam, topology, network_state, controller) is None
    assert network_state["J1"]["approaches"][0]["occupancy_ratio"] >= 0.90

    # Neighbor J2 evaluates its traffic (E_IN=9 heading to J1, N_IN=5 cross-street) -> gates EW, switches to NS!
    clock.advance(6.0)
    j2_tel_during_fault = make_telemetry("J2", "J2_PHASE_EW", {"E_IN": 9.0, "N_IN": 5.0}, timestamp_ms=clock.ms)
    j2_cmd_gated = shield.process_telemetry("J2", j2_tel_during_fault, topology, network_state, controller)
    assert j2_cmd_gated is not None
    assert j2_cmd_gated["target_phase_id"] == "J2_PHASE_NS", (
        "Neighbor J2 must gate flow heading toward emergency-stopped J1 and serve cross-street NS"
    )

    # Operator releases Safe-Stop button on J1!
    clock.advance(2.0)
    release_event = {
        "event_id": f"evt-J1-rel-{clock.ms}",
        "node_id": "J1",
        "category": "emergency",
        "fault_code": "ERR_SAFE_STOP_RELEASED",
        "severity": "INFO",
        "current_phase": "J1_PHASE_NS",
        "clearance_state": "ALL_RED",
        "reason": "Safe-stop released",
        "timestamp_ms": clock.ms,
    }
    validate_payload(release_event, "signal_fault_event")
    shield.handle_fault(release_event, topology=topology, network_state=network_state)

    # J1 immediately receives adaptive commands again
    clock.advance(1.0)
    j1_resumed = make_telemetry("J1", "J1_PHASE_NS", {"N_IN": 6.0, "E_IN": 1.0}, timestamp_ms=clock.ms)
    cmd_resumed = shield.process_telemetry("J1", j1_resumed, topology, network_state, controller)
    assert cmd_resumed is not None
    assert cmd_resumed["target_phase_id"] == "J1_PHASE_NS"


# =============================================================================
# 4. Feedback Error Cooldown, Partial Blind Holdover, Debounce & Coalescing
# =============================================================================

def test_feedback_error_triggers_bounded_cooldown():
    """ERR_CONFLICT_GUARD_TRIGGERED pauses commands during ALL_RED recovery and auto-recovers."""
    topology = load_topology("tabletop_j1_j2_v1")
    clock = ManualClock(start_s=3000.0)
    controller = MaxPressureController()
    shield = noise_shield.NoiseShieldPipeline(
        feedback_cooldown_s=5.0, republish_interval_s=0.0, clock=clock
    )
    network_state: Dict[str, Any] = {}

    conflict_fault = {
        "event_id": "evt-conflict-1",
        "node_id": "J1",
        "category": "feedback_error",
        "fault_code": "ERR_CONFLICT_GUARD_TRIGGERED",
        "severity": "CRITICAL",
        "current_phase": "J1_PHASE_NS",
        "clearance_state": "ALL_RED",
        "reason": "Conflicting green requested -> forcing ALL_RED",
        "timestamp_ms": clock.ms,
    }
    validate_payload(conflict_fault, "signal_fault_event")
    shield.handle_fault(conflict_fault, topology=topology, network_state=network_state)

    # Blocked during 5.0s cooldown
    clock.advance(3.0)
    tel1 = make_telemetry("J1", "J1_PHASE_NS", {"N_IN": 5.0}, timestamp_ms=clock.ms)
    assert shield.process_telemetry("J1", tel1, topology, network_state, controller) is None

    # Automatically unblocked once cooldown expires (>5.0s)
    clock.advance(2.5)
    tel2 = make_telemetry("J1", "J1_PHASE_NS", {"N_IN": 5.0}, timestamp_ms=clock.ms)
    cmd = shield.process_telemetry("J1", tel2, topology, network_state, controller)
    assert cmd is not None


def test_partial_approach_low_confidence_holdover_prevents_starvation():
    """A single sun-glared camera approach (confidence=0.1, queue=0) holds prior demand instead of dropping to 0."""
    clock = ManualClock(start_s=4000.0)
    tf = noise_shield.TelemetryFilter(ema_alpha=0.6, min_approach_confidence=0.25, holdover_max_s=10.0)

    # Healthy initial observation: N_IN has 8 vehicles
    t1 = make_telemetry("J1", "J1_PHASE_EW", {"N_IN": 8.0, "E_IN": 2.0}, timestamp_ms=clock.ms)
    out1 = tf.filter("J1", t1, now_s=clock())
    n_q1 = next(a["queue_vehicles"] for a in out1["approaches"] if a["approach_id"] == "J1_N_IN")
    assert n_q1 == 8.0

    # Lens glare hits ONLY N_IN (confidence drops to 0.10, raw queue falsely reads 0.0)
    clock.advance(1.0)
    t2 = make_telemetry(
        "J1", "J1_PHASE_EW",
        queues={"N_IN": 0.0, "E_IN": 2.0},
        conf={"N_IN": 0.10, "S_IN": 0.95, "E_IN": 0.95, "W_IN": 0.95},
        timestamp_ms=clock.ms,
    )
    out2 = tf.filter("J1", t2, now_s=clock())
    n_q2 = next(a["queue_vehicles"] for a in out2["approaches"] if a["approach_id"] == "J1_N_IN")
    assert n_q2 == 8.0, "Degraded single approach must hold last good estimate rather than trusting 0"


def test_decision_stabilizer_clearance_lock_prevents_mid_yellow_reversal():
    """Once a phase switch NS -> EW is confirmed, clearance_lock_s prevents reverting to NS mid-yellow."""
    stab = noise_shield.DecisionStabilizer(debounce_ticks=2, clearance_lock_s=5.0)
    base_cmd = {
        "command_id": "c1",
        "node_id": "J1",
        "target_phase_id": "J1_PHASE_EW",
        "min_green_s": 10.0,
        "max_green_s": 60.0,
        "controller": "max_pressure",
    }

    # Tick 1 proposing EW (current NS): debounced -> stays NS
    c1 = stab.stabilize("J1", base_cmd, current_phase_id="J1_PHASE_NS", now_s=100.0)
    assert c1["target_phase_id"] == "J1_PHASE_NS"

    # Tick 2 proposing EW: confirmed -> commits EW and locks clearance for 5.0s [101.0, 106.0)
    c2 = stab.stabilize("J1", base_cmd, current_phase_id="J1_PHASE_NS", now_s=101.0)
    assert c2["target_phase_id"] == "J1_PHASE_EW"

    # Tick 3 at t=103.0s (still clearing Yellow->AllRed, hardware still reports NS):
    # even if raw controller tries to revert to NS, clearance lock keeps target EW!
    revert_cmd = dict(base_cmd, target_phase_id="J1_PHASE_NS")
    c3 = stab.stabilize("J1", revert_cmd, current_phase_id="J1_PHASE_NS", now_s=103.0)
    assert c3["target_phase_id"] == "J1_PHASE_EW"


def test_command_coalescer_stamps_ttl_and_suppresses_high_rate_duplicates():
    """Same-phase commands within republish_interval_s are suppressed; phase switches pass immediately."""
    topology = load_topology("tabletop_j1_j2_v1")
    clock = ManualClock(start_s=5000.0)
    controller = MaxPressureController()
    shield = noise_shield.NoiseShieldPipeline(
        debounce_ticks=1, command_ttl_ms=4000, republish_interval_s=2.0, clock=clock
    )
    network_state: Dict[str, Any] = {}

    # First packet -> emitted immediately with TTL stamp
    t1 = make_telemetry("J1", "J1_PHASE_NS", {"N_IN": 6.0}, timestamp_ms=clock.ms)
    cmd1 = shield.process_telemetry("J1", t1, topology, network_state, controller)
    assert cmd1 is not None
    assert cmd1["expires_at_ms"] == cmd1["timestamp_ms"] + 4000
    validate_payload(cmd1, "control_command")

    # 0.5s later, same target phase NS -> suppressed to prevent MQTT burst
    clock.advance(0.5)
    t2 = make_telemetry("J1", "J1_PHASE_NS", {"N_IN": 6.0}, timestamp_ms=clock.ms)
    assert shield.process_telemetry("J1", t2, topology, network_state, controller) is None

    # 2.1s after cmd1, same target phase NS -> republished as coordinator keep-alive (< 5s ESP32 watchdog)
    clock.advance(1.6)
    t3 = make_telemetry("J1", "J1_PHASE_NS", {"N_IN": 6.0}, timestamp_ms=clock.ms)
    cmd3 = shield.process_telemetry("J1", t3, topology, network_state, controller)
    assert cmd3 is not None
    assert cmd3["target_phase_id"] == "J1_PHASE_NS"


def test_graph_control_service_config_and_entrypoint_load(monkeypatch):
    """Verify services/graph-control/config.py and main.py load cleanly with all noise shield settings."""
    sibling_names = ("config", "graph_contracts_helper", "controller", "runtime_guards", "noise_shield")
    saved_modules = {k: sys.modules.get(k) for k in sibling_names}
    try:
        for k in sibling_names:
            sys.modules.pop(k, None)
        monkeypatch.syspath_prepend(str(_GC_DIR))
        cfg_spec = importlib.util.spec_from_file_location("gc_config_smoke", _GC_DIR / "config.py")
        cfg_mod = importlib.util.module_from_spec(cfg_spec)
        cfg_spec.loader.exec_module(cfg_mod)

        s = cfg_mod.Settings()
        assert s.noise_shield_enabled is True
        assert s.neighbor_ttl_s > 0
        assert s.command_ttl_ms > 0
        assert 0.0 < s.ema_alpha <= 1.0

        main_spec = importlib.util.spec_from_file_location("gc_main_smoke", _GC_DIR / "main.py")
        main_mod = importlib.util.module_from_spec(main_spec)
        main_spec.loader.exec_module(main_mod)
        assert callable(main_mod.main)
        assert callable(main_mod.create_controller)
    finally:
        for k, prev in saved_modules.items():
            if prev is None:
                sys.modules.pop(k, None)
            else:
                sys.modules[k] = prev


