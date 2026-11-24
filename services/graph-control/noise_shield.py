"""
5-Layer Noise Immunity & Fault Resilience Pipeline for EdgeFlow Graph-Control.

Layers:
  1. TemporalSanitizer   — Monotonic timestamp check, packet age guard, zombie neighbor TTL eviction.
  2. TelemetryFilter     — Physical slew-rate spike clamping + confidence-weighted EMA + partial-blind holdover.
  3. FaultCircuitBreaker — Dedicated `signal_fault` isolation (emergency lockout, upstream spillback gating,
                           feedback mismatch cooldown, disconnect cache eviction).
  4. DecisionStabilizer  — K-consecutive tick debouncer + in-flight clearance lock (Yellow + All-Red).
  5. CommandCoalescer    — Outbound TTL stamping (`expires_at_ms`) + redundant same-phase command deduplication.
"""

import copy
import logging
import time
from typing import Any, Callable, Dict, List, Optional, Set, Tuple

logger = logging.getLogger("graph-control")


class TemporalSanitizer:
    """Layer 1: Rejects stale/out-of-order packets and evicts silent zombie neighbors."""

    def __init__(
        self,
        max_telemetry_age_ms: int = 5000,
        neighbor_ttl_s: float = 8.0,
        future_skew_tolerance_ms: int = 2000,
    ) -> None:
        self.max_telemetry_age_ms = max_telemetry_age_ms
        self.neighbor_ttl_s = neighbor_ttl_s
        self.future_skew_tolerance_ms = future_skew_tolerance_ms
        self._last_timestamp_ms: Dict[str, int] = {}
        self._last_sim_time_s: Dict[str, float] = {}
        self._ingested_at_s: Dict[str, float] = {}

    def admit_packet(self, node_id: str, telemetry: Dict[str, Any], now_ms: int) -> bool:
        """Return True if packet is fresh and strictly newer than previous packets for node_id."""
        ts_raw = telemetry.get("timestamp_ms")
        if ts_raw is not None:
            ts_ms = int(ts_raw)
            if self.max_telemetry_age_ms > 0:
                age_ms = now_ms - ts_ms
                if age_ms > self.max_telemetry_age_ms or ts_ms > now_ms + self.future_skew_tolerance_ms:
                    logger.warning(
                        f"[{node_id}] Dropped stale/skewed telemetry (timestamp_ms={ts_ms}, now_ms={now_ms})"
                    )
                    return False
            prev_ms = self._last_timestamp_ms.get(node_id)
            if prev_ms is not None and ts_ms <= prev_ms:
                logger.warning(
                    f"[{node_id}] Dropped out-of-order/duplicate telemetry (timestamp_ms={ts_ms} <= {prev_ms})"
                )
                return False
            self._last_timestamp_ms[node_id] = ts_ms
            return True

        sim_raw = telemetry.get("simulation_time_s")
        if sim_raw is not None:
            sim_s = float(sim_raw)
            prev_s = self._last_sim_time_s.get(node_id)
            # Allow sim_s == 0.0 for explicit simulation resets, reject backwards jumps otherwise
            if prev_s is not None and sim_s < prev_s and sim_s > 0.0:
                logger.warning(
                    f"[{node_id}] Dropped out-of-order simulation telemetry (sim_s={sim_s} < {prev_s})"
                )
                return False
            self._last_sim_time_s[node_id] = sim_s

        return True

    def mark_ingested(self, node_id: str, now_s: float) -> None:
        self._ingested_at_s[node_id] = now_s

    def evict_node(self, node_id: str, network_state: Dict[str, Any], reset_monotonic: bool = False) -> None:
        network_state.pop(node_id, None)
        self._ingested_at_s.pop(node_id, None)
        if reset_monotonic:
            self._last_timestamp_ms.pop(node_id, None)
            self._last_sim_time_s.pop(node_id, None)

    def prune_stale_neighbors(
        self,
        network_state: Dict[str, Any],
        now_s: float,
        protected_nodes: Optional[Set[str]] = None,
    ) -> List[str]:
        """Evict neighbor states that have not refreshed within neighbor_ttl_s."""
        if self.neighbor_ttl_s <= 0:
            return []
        protected = protected_nodes or set()
        evicted: List[str] = []
        for nid in list(network_state.keys()):
            if nid in protected:
                continue
            last_s = self._ingested_at_s.get(nid)
            if last_s is not None and (now_s - last_s) > self.neighbor_ttl_s:
                network_state.pop(nid, None)
                self._ingested_at_s.pop(nid, None)
                evicted.append(nid)
                logger.warning(
                    f"[{nid}] Evicted zombie neighbor state after {self.neighbor_ttl_s:.1f}s of silence"
                )
        return evicted


class TelemetryFilter:
    """Layer 2: Physical slew-rate clamping + confidence-weighted EMA + partial-blind protection."""

    def __init__(
        self,
        ema_alpha: float = 0.5,
        max_queue_rise_per_s: float = 2.5,
        max_queue_drop_per_s: float = 3.5,
        max_single_step_jump: float = 4.0,
        min_approach_confidence: float = 0.25,
        fallback_demand_floor_veh: float = 1.0,
        holdover_max_s: float = 10.0,
    ) -> None:
        self.ema_alpha = max(0.01, min(1.0, ema_alpha))
        self.max_queue_rise_per_s = max(0.1, max_queue_rise_per_s)
        self.max_queue_drop_per_s = max(0.1, max_queue_drop_per_s)
        self.max_single_step_jump = max(0.5, max_single_step_jump)
        self.min_approach_confidence = max(0.0, min(1.0, min_approach_confidence))
        self.fallback_demand_floor_veh = max(0.0, fallback_demand_floor_veh)
        self.holdover_max_s = max(0.0, holdover_max_s)
        # Keyed by (node_id, approach_id)
        self._estimates: Dict[Tuple[str, str], Dict[str, float]] = {}

    def reset_node(self, node_id: str) -> None:
        for key in [k for k in self._estimates if k[0] == node_id]:
            del self._estimates[key]

    @staticmethod
    def _obs_time_s(telemetry: Dict[str, Any], fallback_now_s: float) -> float:
        if telemetry.get("timestamp_ms") is not None:
            return float(telemetry["timestamp_ms"]) / 1000.0
        if telemetry.get("simulation_time_s") is not None:
            return float(telemetry["simulation_time_s"])
        return fallback_now_s

    def filter(self, node_id: str, telemetry: Dict[str, Any], now_s: float) -> Dict[str, Any]:
        """Return a sanitized deep copy of telemetry with clamped and smoothed approach metrics."""
        cleaned = copy.deepcopy(telemetry)
        t_obs = self._obs_time_s(cleaned, now_s)

        for app in cleaned.get("approaches", []):
            app_id = app.get("approach_id", "")
            if not app_id:
                continue

            raw_q = max(0.0, float(app.get("queue_vehicles", app.get("queue_length_veh", 0.0))))
            raw_flow = max(0.0, float(app.get("flow_veh_per_s", 0.0)))
            raw_occ = min(1.0, max(0.0, float(app.get("occupancy_ratio", app.get("occupancy", 0.0)))))
            conf = min(1.0, max(0.0, float(app.get("confidence", 1.0))))

            key = (node_id, app_id)
            prev = self._estimates.get(key)

            if prev is None:
                init_q = raw_q if conf >= self.min_approach_confidence else max(raw_q, self.fallback_demand_floor_veh)
                self._estimates[key] = {
                    "q": init_q,
                    "flow": raw_flow,
                    "occ": raw_occ,
                    "last_s": t_obs,
                    "last_good_s": t_obs,
                }
                q_out, flow_out, occ_out = init_q, raw_flow, raw_occ
            else:
                raw_dt = t_obs - prev["last_s"]
                dt = max(0.2, min(3.0, raw_dt)) if raw_dt >= 0 else 0.5

                if conf < self.min_approach_confidence:
                    # Partial sensor degradation on this single approach: hold previous estimate
                    # and prevent indefinite starvation if degraded beyond holdover_max_s
                    degraded_s = max(0.0, t_obs - prev["last_good_s"])
                    q_out = (
                        max(prev["q"], self.fallback_demand_floor_veh)
                        if degraded_s >= self.holdover_max_s
                        else prev["q"]
                    )
                    flow_out = prev["flow"]
                    occ_out = prev["occ"]
                    prev["q"] = q_out
                    prev["last_s"] = t_obs
                else:
                    # 1. Physical Slew-Rate Clamping (rejects single-frame YOLO spikes)
                    max_rise = min(self.max_single_step_jump, self.max_queue_rise_per_s * dt)
                    max_drop = min(self.max_single_step_jump * 1.5, self.max_queue_drop_per_s * dt)
                    clamped_q = min(prev["q"] + max_rise, max(prev["q"] - max_drop, raw_q))
                    clamped_flow = min(prev["flow"] + 0.8 * dt, max(prev["flow"] - 1.0 * dt, raw_flow))
                    clamped_occ = min(prev["occ"] + 0.25 * dt, max(prev["occ"] - 0.30 * dt, raw_occ))

                    # 2. Confidence-Weighted EMA
                    alpha = self.ema_alpha * conf
                    q_out = max(0.0, alpha * clamped_q + (1.0 - alpha) * prev["q"])
                    flow_out = max(0.0, alpha * clamped_flow + (1.0 - alpha) * prev["flow"])
                    occ_out = min(1.0, max(0.0, alpha * clamped_occ + (1.0 - alpha) * prev["occ"]))

                    prev["q"] = q_out
                    prev["flow"] = flow_out
                    prev["occ"] = occ_out
                    prev["last_s"] = t_obs
                    prev["last_good_s"] = t_obs

            app["queue_vehicles"] = round(q_out, 4)
            if "flow_veh_per_s" in app:
                app["flow_veh_per_s"] = round(flow_out, 4)
            if "occupancy_ratio" in app:
                app["occupancy_ratio"] = round(occ_out, 4)
            if "occupancy" in app:
                app["occupancy"] = round(occ_out, 4)

        return cleaned


class FaultCircuitBreaker:
    """Layer 3: Isolates faulted intersections and injects virtual spillback barriers for neighbors."""

    def __init__(
        self,
        feedback_cooldown_s: float = 5.0,
        virtual_barrier_occupancy: float = 0.95,
        virtual_barrier_queue_veh: float = 25.0,
    ) -> None:
        self.feedback_cooldown_s = max(0.0, feedback_cooldown_s)
        self.virtual_barrier_occupancy = min(1.0, max(0.0, virtual_barrier_occupancy))
        self.virtual_barrier_queue_veh = max(1.0, virtual_barrier_queue_veh)
        # node_id -> {"reason": str, "category": str, "until_s": Optional[float], "reported_phase": Optional[str]}
        self._tripped: Dict[str, Dict[str, Any]] = {}
        self._active_barriers: Set[str] = set()

    @property
    def active_barriers(self) -> Set[str]:
        return set(self._active_barriers)

    def _build_virtual_barrier(self, node_id: str, topology: Dict[str, Any], now_s: float, current_phase: Optional[str]) -> Optional[Dict[str, Any]]:
        node_spec = next((n for n in topology.get("nodes", []) if n.get("node_id") == node_id), None)
        if not node_spec:
            return None
        phases = node_spec.get("phases", [])
        default_phase = current_phase or (phases[0]["phase_id"] if phases else f"{node_id}_PHASE_NS")
        approaches = [
            {
                "approach_id": app_id,
                "queue_vehicles": self.virtual_barrier_queue_veh,
                "flow_veh_per_s": 0.0,
                "mean_speed_mps": 0.0,
                "occupancy_ratio": self.virtual_barrier_occupancy,
                "confidence": 1.0,
            }
            for app_id in node_spec.get("approaches", [])
        ]
        return {
            "node_id": node_id,
            "source_type": "physical",
            "current_phase_id": default_phase,
            "timestamp_ms": int(now_s * 1000),
            "approaches": approaches,
        }

    def observe_fault(
        self,
        fault: Dict[str, Any],
        topology: Dict[str, Any],
        network_state: Dict[str, Any],
        now_s: float,
        on_node_reset: Optional[Callable[[str], None]] = None,
    ) -> None:
        """React to canonical SignalFaultEvent messages from edgeflow/v1/signal_fault/#."""
        node_id = fault.get("node_id")
        if not node_id:
            return
        category = str(fault.get("category", "")).lower()
        fault_code = str(fault.get("fault_code", ""))
        reported_phase = fault.get("current_phase")

        if category == "emergency":
            severity = str(fault.get("severity", "")).upper()
            if fault_code == "ERR_SAFE_STOP_ENGAGED" or (fault_code == "ERR_EMERGENCY_OVERRIDE" and severity != "INFO"):
                self._tripped[node_id] = {
                    "category": "emergency",
                    "fault_code": fault_code,
                    "until_s": None,  # Latched until explicit release
                    "reported_phase": reported_phase,
                }
                barrier = self._build_virtual_barrier(node_id, topology, now_s, reported_phase)
                if barrier is not None:
                    network_state[node_id] = barrier
                    self._active_barriers.add(node_id)
                logger.warning(
                    f"[{node_id}] Circuit breaker OPEN ({fault_code}): commands halted & upstream spillback barrier active"
                )
            elif fault_code == "ERR_SAFE_STOP_RELEASED" or (fault_code == "ERR_EMERGENCY_OVERRIDE" and severity == "INFO"):
                self._tripped.pop(node_id, None)
                if node_id in self._active_barriers:
                    self._active_barriers.discard(node_id)
                    network_state.pop(node_id, None)
                if on_node_reset:
                    on_node_reset(node_id)
                logger.info(f"[{node_id}] Circuit breaker CLOSED ({fault_code}): adaptive control resuming")

        elif category == "feedback_error":
            cooldown = (
                self.feedback_cooldown_s
                if fault_code == "ERR_CONFLICT_GUARD_TRIGGERED"
                else min(2.0, self.feedback_cooldown_s)
            )
            if cooldown > 0 and self._tripped.get(node_id, {}).get("category") != "emergency":
                self._tripped[node_id] = {
                    "category": "feedback_error",
                    "fault_code": fault_code,
                    "until_s": now_s + cooldown,
                    "reported_phase": reported_phase,
                }
                logger.warning(
                    f"[{node_id}] Feedback fault ({fault_code}): pausing commands for {cooldown:.1f}s cooldown"
                )

        elif category == "disconnect":
            if node_id not in self._active_barriers:
                network_state.pop(node_id, None)
            if on_node_reset:
                on_node_reset(node_id)
            logger.warning(f"[{node_id}] Disconnect fault ({fault_code}): evicted stale neighbor cache")

        elif category == "hardware":
            if fault_code == "ERR_HARDWARE_DEFECT" and self.feedback_cooldown_s > 0:
                if self._tripped.get(node_id, {}).get("category") != "emergency":
                    self._tripped[node_id] = {
                        "category": "hardware",
                        "fault_code": fault_code,
                        "until_s": now_s + self.feedback_cooldown_s,
                        "reported_phase": reported_phase,
                    }

    def is_blocked(self, node_id: str, now_s: float) -> bool:
        """True when commands to node_id must be suppressed due to emergency or active fault cooldown."""
        entry = self._tripped.get(node_id)
        if entry is None:
            return False
        until_s = entry.get("until_s")
        if until_s is not None and now_s >= until_s:
            del self._tripped[node_id]
            logger.info(f"[{node_id}] Fault cooldown expired: adaptive commands re-enabled")
            return False
        return True

    def reported_phase_for(self, node_id: str) -> Optional[str]:
        entry = self._tripped.get(node_id)
        return entry.get("reported_phase") if entry else None


class DecisionStabilizer:
    """Layer 4: K-consecutive tick debouncer and in-flight clearance lock against phase chattering."""

    def __init__(self, debounce_ticks: int = 2, clearance_lock_s: float = 5.0) -> None:
        self.debounce_ticks = max(1, int(debounce_ticks))
        self.clearance_lock_s = max(0.0, float(clearance_lock_s))
        # node_id -> {"candidate": Optional[str], "count": int, "locked_target": Optional[str], "lock_until_s": float}
        self._state: Dict[str, Dict[str, Any]] = {}

    def reset_node(self, node_id: str) -> None:
        self._state.pop(node_id, None)

    def stabilize(
        self,
        node_id: str,
        command: Dict[str, Any],
        current_phase_id: Optional[str],
        now_s: float,
    ) -> Dict[str, Any]:
        st = self._state.setdefault(
            node_id,
            {"candidate": None, "count": 0, "locked_target": None, "lock_until_s": 0.0},
        )
        proposed = command["target_phase_id"]

        # Release in-flight clearance lock once the hardware reports it reached the locked target
        if st["locked_target"] and current_phase_id == st["locked_target"]:
            st["locked_target"] = None
            st["lock_until_s"] = 0.0

        # Maintain in-flight clearance target while Yellow -> All-Red is still clearing
        if st["locked_target"] and now_s < st["lock_until_s"]:
            if proposed != st["locked_target"]:
                out = dict(command)
                out["target_phase_id"] = st["locked_target"]
                return out
            return command

        st["locked_target"] = None

        # No switch requested (or current_phase_id unknown): clear candidate streak and pass through
        if not current_phase_id or proposed == current_phase_id:
            st["candidate"] = None
            st["count"] = 0
            return command

        # Phase switch proposed: require K consecutive confirmations
        if st["candidate"] == proposed:
            st["count"] += 1
        else:
            st["candidate"] = proposed
            st["count"] = 1

        if st["count"] < self.debounce_ticks:
            out = dict(command)
            out["target_phase_id"] = current_phase_id
            return out

        # Confirmed! Commit transition and engage clearance lock
        st["candidate"] = None
        st["count"] = 0
        if self.clearance_lock_s > 0:
            st["locked_target"] = proposed
            st["lock_until_s"] = now_s + self.clearance_lock_s
        return command


class CommandCoalescer:
    """Layer 5: Stamps command TTL (`expires_at_ms`) and suppresses high-rate duplicate commands."""

    def __init__(self, command_ttl_ms: int = 4000, republish_interval_s: float = 2.0) -> None:
        self.command_ttl_ms = max(0, int(command_ttl_ms))
        self.republish_interval_s = max(0.0, float(republish_interval_s))
        # node_id -> {"target_phase_id": str, "sent_at_s": float}
        self._last_sent: Dict[str, Dict[str, Any]] = {}

    def reset_node(self, node_id: str) -> None:
        self._last_sent.pop(node_id, None)

    def prepare_outbound(
        self,
        command: Dict[str, Any],
        now_s: float,
        now_ms: Optional[int] = None,
    ) -> Optional[Dict[str, Any]]:
        node_id = command["node_id"]
        target = command["target_phase_id"]
        last = self._last_sent.get(node_id)

        if (
            last is not None
            and last["target_phase_id"] == target
            and self.republish_interval_s > 0
            and (now_s - last["sent_at_s"]) < self.republish_interval_s
        ):
            return None

        stamp_ms = now_ms if now_ms is not None else int(now_s * 1000)
        out = dict(command)
        out.setdefault("timestamp_ms", stamp_ms)
        if self.command_ttl_ms > 0:
            out.setdefault("expires_at_ms", stamp_ms + self.command_ttl_ms)

        self._last_sent[node_id] = {"target_phase_id": target, "sent_at_s": now_s}
        return out


class NoiseShieldPipeline:
    """Unified 5-layer anti-noise orchestrator wrapping any BaseController."""

    def __init__(
        self,
        enabled: bool = True,
        max_telemetry_age_ms: int = 5000,
        neighbor_ttl_s: float = 8.0,
        ema_alpha: float = 0.5,
        max_queue_rise_per_s: float = 2.5,
        max_queue_drop_per_s: float = 3.5,
        max_single_step_jump: float = 4.0,
        min_approach_confidence: float = 0.25,
        fallback_demand_floor_veh: float = 1.0,
        holdover_max_s: float = 10.0,
        feedback_cooldown_s: float = 5.0,
        debounce_ticks: int = 2,
        clearance_lock_s: float = 5.0,
        command_ttl_ms: int = 4000,
        republish_interval_s: float = 2.0,
        clock: Callable[[], float] = time.time,
    ) -> None:
        self.enabled = enabled
        self._clock = clock
        self.temporal = TemporalSanitizer(
            max_telemetry_age_ms=max_telemetry_age_ms,
            neighbor_ttl_s=neighbor_ttl_s,
        )
        self.telemetry_filter = TelemetryFilter(
            ema_alpha=ema_alpha,
            max_queue_rise_per_s=max_queue_rise_per_s,
            max_queue_drop_per_s=max_queue_drop_per_s,
            max_single_step_jump=max_single_step_jump,
            min_approach_confidence=min_approach_confidence,
            fallback_demand_floor_veh=fallback_demand_floor_veh,
            holdover_max_s=holdover_max_s,
        )
        self.circuit_breaker = FaultCircuitBreaker(
            feedback_cooldown_s=feedback_cooldown_s,
        )
        self.stabilizer = DecisionStabilizer(
            debounce_ticks=debounce_ticks,
            clearance_lock_s=clearance_lock_s,
        )
        self.coalescer = CommandCoalescer(
            command_ttl_ms=command_ttl_ms,
            republish_interval_s=republish_interval_s,
        )

    def reset_node(self, node_id: str) -> None:
        self.telemetry_filter.reset_node(node_id)
        self.stabilizer.reset_node(node_id)
        self.coalescer.reset_node(node_id)

    def handle_fault(
        self,
        fault: Dict[str, Any],
        topology: Dict[str, Any],
        network_state: Dict[str, Any],
        now_s: Optional[float] = None,
    ) -> None:
        if not self.enabled:
            return
        t_s = self._clock() if now_s is None else now_s
        node_id = fault.get("node_id")
        if node_id and str(fault.get("category", "")).lower() == "disconnect":
            self.temporal.evict_node(node_id, network_state, reset_monotonic=False)
        self.circuit_breaker.observe_fault(
            fault=fault,
            topology=topology,
            network_state=network_state,
            now_s=t_s,
            on_node_reset=self.reset_node,
        )

    @staticmethod
    def _invoke_controller(
        controller: Any,
        node_id: str,
        telemetry: Dict[str, Any],
        topology: Dict[str, Any],
        network_state: Dict[str, Any],
        now_s: float,
    ) -> Optional[Dict[str, Any]]:
        cmd_time_s = (
            float(telemetry["simulation_time_s"])
            if telemetry.get("simulation_time_s") is not None
            else now_s
        )
        try:
            return controller.compute_command(
                node_id=node_id,
                telemetry=telemetry,
                topology=topology,
                network_state=network_state,
                current_time_s=cmd_time_s,
            )
        except TypeError:
            return controller.compute_command(
                node_id=node_id,
                telemetry=telemetry,
                topology=topology,
                network_state=network_state,
            )

    def process_telemetry(
        self,
        node_id: str,
        telemetry: Dict[str, Any],
        topology: Dict[str, Any],
        network_state: Dict[str, Any],
        controller: Any,
        blind_gate: Optional[Any] = None,
        manual_hold: Optional[Any] = None,
        now_s: Optional[float] = None,
        now_ms: Optional[int] = None,
    ) -> Optional[Dict[str, Any]]:
        t_s = self._clock() if now_s is None else now_s
        t_ms = int(t_s * 1000) if now_ms is None else now_ms

        if not self.enabled:
            admitted = blind_gate.admit(node_id, telemetry, network_state) if blind_gate else True
            if admitted:
                network_state[node_id] = telemetry
            override_cmd = manual_hold.command_for(node_id, telemetry.get("current_phase_id")) if manual_hold else None
            if override_cmd is not None:
                return override_cmd
            if not admitted:
                return None
            return self._invoke_controller(
                controller=controller,
                node_id=node_id,
                telemetry=telemetry,
                topology=topology,
                network_state=network_state,
                now_s=t_s,
            )

        # Layer 1a: Drop stale or out-of-order packets before they touch any state
        if not self.temporal.admit_packet(node_id, telemetry, now_ms=t_ms):
            return None

        # Layer 1b: Evict silent zombie neighbors (preserving active emergency spillback barriers)
        self.temporal.prune_stale_neighbors(
            network_state, now_s=t_s, protected_nodes=self.circuit_breaker.active_barriers
        )

        # Layer 3: Fault circuit breaker check (emergency Safe-Stop or active feedback cooldown)
        if self.circuit_breaker.is_blocked(node_id, now_s=t_s):
            # Do NOT overwrite virtual spillback barrier in network_state[node_id] while Safe-Stop is engaged
            return None

        # Blind camera gate (G1 invariant)
        admitted = blind_gate.admit(node_id, telemetry, network_state) if blind_gate else True
        if not admitted:
            self.temporal.evict_node(node_id, network_state)
            self.reset_node(node_id)
            if manual_hold is not None:
                override_cmd = manual_hold.command_for(node_id, telemetry.get("current_phase_id"))
                if override_cmd is not None:
                    return self.coalescer.prepare_outbound(override_cmd, now_s=t_s, now_ms=t_ms)
            return None

        # Layer 2: Slew-rate clamp + Confidence-weighted EMA
        clean_telemetry = self.telemetry_filter.filter(node_id, telemetry, now_s=t_s)
        network_state[node_id] = clean_telemetry
        self.temporal.mark_ingested(node_id, now_s=t_s)

        # Operator manual override outranks adaptive controller (when node is not in hardware Safe-Stop)
        if manual_hold is not None:
            override_cmd = manual_hold.command_for(node_id, clean_telemetry.get("current_phase_id"))
            if override_cmd is not None:
                self.stabilizer.reset_node(node_id)
                return self.coalescer.prepare_outbound(override_cmd, now_s=t_s, now_ms=t_ms)

        # Core Algorithm Inference
        raw_cmd = self._invoke_controller(
            controller=controller,
            node_id=node_id,
            telemetry=clean_telemetry,
            topology=topology,
            network_state=network_state,
            now_s=t_s,
        )
        if not raw_cmd:
            return None

        # Layer 4: Multi-tick confirmation & clearance lock
        stable_cmd = self.stabilizer.stabilize(
            node_id=node_id,
            command=raw_cmd,
            current_phase_id=clean_telemetry.get("current_phase_id"),
            now_s=t_s,
        )

        # Layer 5: TTL stamp & rate-limited command deduplication
        return self.coalescer.prepare_outbound(stable_cmd, now_s=t_s, now_ms=t_ms)
