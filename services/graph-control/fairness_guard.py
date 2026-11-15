"""
Fairness guard of the graph-control loop: keeps any controller from starving a road.

It sits between the telemetry and the controller and works with every controller in the registry:

1. filter(): cleans what the controller sees.
   - Unobserved approach (confidence below a threshold while the rest of the camera still sees):
     its "0 vehicles" means "unknown", not "empty". It is given a small assumed demand so it is
     still served every cycle (detector-failure recall in traffic engineering).
   - Stuck approach (green, queue > 0, the queue has not dropped once AND no vehicle has moved
     (mean_speed_mps <= stuck_speed_mps) for stuck_after_s: broken-down car, parked car or false
     detection inside the ROI, frozen video): its queue is
     capped to the assumed demand so it stops winning green it cannot use. The max-red rule still
     gives it a green now and then; as soon as its queue drops or it moves, the mark is cleared.
     Motion is what separates a stuck lane from an oversaturated one (arrivals > discharge: the
     queue never drops, but the vehicles move). Without a measured speed nothing is marked.
2. decide(): bounds what the controller may do.
   - Max red: a phase with demand that has been red for max_red_s gets the next green.
   - Owed service: a phase that waited owed_after_s keeps its green for a time sized to its queue
     (serve_min_s..serve_max_s) instead of being taken back after the 5 s device minimum.

The ESP32 keeps the last word on timing (min/max green, clearance, FORCED_SERVICE_GREEN_MS).
Every intervention is logged once per episode, so the operator sees why a phase was forced.
"""
import logging
import time
from dataclasses import dataclass, field
from typing import Any, Callable, Dict, List, Optional, Set

logger = logging.getLogger("graph-control")


@dataclass(frozen=True)
class FairnessConfig:
    max_red_s: float = 60.0            # longest a phase with demand waits (counted from its green end)
    owed_after_s: float = 30.0         # a phase that waited this long is owed a full service
    sat_flow_vps: float = 0.5          # discharge estimate per approach, sizes the owed service
    serve_min_s: float = 15.0          # = firmware FORCED_SERVICE_GREEN_MS: never ask back sooner than the device allows
    serve_max_s: float = 30.0
    stuck_after_s: float = 15.0        # green, queue > 0, no drop and no motion this long -> stuck; 0 = off
    stuck_speed_mps: float = 0.02      # at or below: nothing moves in the ROI (sa ban scale: 2 cm/s)
    unobserved_confidence: float = 0.2  # approach confidence below this -> unobserved
    assumed_queue: float = 1.0         # demand given to an unobserved or stuck approach
    unobserved_serve_s: float = 20.0   # green kept for a phase whose demand cannot be seen (fixed-time like)


@dataclass
class _NodeState:
    phase: Optional[str] = None
    green_start: float = 0.0
    waited_s: float = 0.0                                       # red time before the current green
    red_since: Dict[str, float] = field(default_factory=dict)  # phase -> time its green ended
    protect_until: float = -1.0
    reserve_pending: bool = False                               # new green: size its owed service
    prev_queue: Dict[str, float] = field(default_factory=dict)
    last_drop: Dict[str, float] = field(default_factory=dict)  # approach -> last drop during green
    stuck: Set[str] = field(default_factory=set)
    unobserved: Set[str] = field(default_factory=set)
    forcing: Optional[str] = None                               # phase forced by max red (for logs)


def _phase_approaches(phase: Dict[str, Any]) -> List[str]:
    apps = list(phase.get("approaches") or [])
    if not apps:
        apps = list(dict.fromkeys(m["from_approach"] for m in phase.get("movements", [])
                                  if m.get("from_approach")))
    return apps


def _queues(telemetry: Dict[str, Any]) -> Dict[str, float]:
    return {a["approach_id"]: float(a.get("queue_vehicles", 0.0)) for a in telemetry.get("approaches", [])}


class FairnessGuard:
    def __init__(self, topology: Dict[str, Any], config: FairnessConfig = FairnessConfig(),
                 clock: Callable[[], float] = time.time) -> None:
        self.cfg = config
        self._clock = clock
        self._phases: Dict[str, Dict[str, List[str]]] = {
            n["node_id"]: {p["phase_id"]: _phase_approaches(p) for p in n.get("phases", [])}
            for n in topology.get("nodes", [])}
        self._nodes: Dict[str, _NodeState] = {}

    # ---- 1. what the controller sees ------------------------------------------------------------
    def filter(self, node_id: str, telemetry: Dict[str, Any]) -> Dict[str, Any]:
        """Returns the telemetry the controller should plan with (a new dict; the input is untouched)."""
        phases = self._phases.get(node_id)
        if not phases:
            return telemetry
        now = self._clock()
        st = self._nodes.setdefault(node_id, _NodeState())
        self._track_phase(node_id, st, telemetry.get("current_phase_id"), phases, now)
        self._track_unobserved(node_id, st, telemetry)
        self._track_stuck(node_id, st, telemetry, phases, now)
        masked = st.stuck | st.unobserved
        if not masked:
            return telemetry
        out = dict(telemetry)
        out["approaches"] = [self._masked(a) if a["approach_id"] in masked else a
                             for a in telemetry.get("approaches", [])]
        return out

    def _masked(self, approach: Dict[str, Any]) -> Dict[str, Any]:
        return dict(approach, queue_vehicles=self.cfg.assumed_queue, occupancy_ratio=0.0, flow_veh_per_s=0.0)

    def _track_phase(self, node_id: str, st: _NodeState, phase: Optional[str],
                     phases: Dict[str, List[str]], now: float) -> None:
        if phase is None or phase == st.phase:
            return
        if st.phase is None:  # first message: no history, every other phase starts waiting now
            st.red_since = {p: now for p in phases if p != phase}
        else:
            st.red_since[st.phase] = now
        st.waited_s = now - st.red_since.pop(phase, now)
        st.phase, st.green_start = phase, now
        st.protect_until, st.last_drop, st.forcing = -1.0, {}, None
        st.reserve_pending = True

    def _track_unobserved(self, node_id: str, st: _NodeState, telemetry: Dict[str, Any]) -> None:
        now_unobserved = {a["approach_id"] for a in telemetry.get("approaches", [])
                          if float(a.get("confidence", 1.0)) < self.cfg.unobserved_confidence}
        for app in sorted(now_unobserved - st.unobserved):
            logger.warning(f"[{node_id}] {app} unobserved (low confidence): assumed "
                           f"{self.cfg.assumed_queue:g} vehicle so it is still served every cycle")
        for app in sorted(st.unobserved - now_unobserved):
            logger.info(f"[{node_id}] {app} observed again")
        st.unobserved = now_unobserved

    def _track_stuck(self, node_id: str, st: _NodeState, telemetry: Dict[str, Any],
                     phases: Dict[str, List[str]], now: float) -> None:
        queues = _queues(telemetry)
        # No speed field = no evidence of motion: treated as moving, so nothing is ever marked on a guess
        speeds = {a["approach_id"]: float(a.get("mean_speed_mps", float("inf")))
                  for a in telemetry.get("approaches", [])}
        green = telemetry.get("signal_state", "GREEN") == "GREEN"
        if self.cfg.stuck_after_s <= 0:   # disabled (open-loop video demo: its cars ignore our lights)
            green = False
        for app in phases.get(st.phase, []) if green else []:
            if app in st.unobserved or app not in queues:
                continue
            q = queues[app]
            if q <= 0.0 or q < st.prev_queue.get(app, q) or speeds.get(app, 0.0) > self.cfg.stuck_speed_mps:
                st.last_drop[app] = now
                if app in st.stuck:
                    st.stuck.discard(app)
                    logger.info(f"[{node_id}] {app} discharges again: stuck mark cleared")
            elif app not in st.stuck and now - st.last_drop.get(app, st.green_start) >= self.cfg.stuck_after_s:
                st.stuck.add(app)
                logger.warning(f"[{node_id}] {app} queue {q:g} has neither dropped nor moved in "
                               f"{self.cfg.stuck_after_s:g} s of green: marked STUCK (blocked lane or "
                               "false detection), its demand is capped")
        st.prev_queue = queues

    # ---- 2. what the controller may do ----------------------------------------------------------
    def decide(self, node_id: str, filtered: Dict[str, Any], target: str) -> str:
        """Returns the phase to command: the controller's target unless a fairness bound overrides it."""
        phases, st = self._phases.get(node_id), self._nodes.get(node_id)
        current = filtered.get("current_phase_id")
        if not phases or st is None or current not in phases:
            return target
        if filtered.get("signal_state", "GREEN") != "GREEN":
            return target
        now, queues = self._clock(), _queues(filtered)

        def demand(phase: str) -> float:
            return sum(queues.get(a, 0.0) for a in phases[phase])

        if st.reserve_pending:
            st.reserve_pending = False
            self._reserve_service(node_id, st, current, phases, queues, now)

        overdue = [(now - since, p) for p, since in st.red_since.items()
                   if p != current and p in phases and demand(p) > 0.0 and now - since >= self.cfg.max_red_s]
        if overdue:
            waited, phase = max(overdue)
            if st.forcing != phase:
                st.forcing = phase
                logger.warning(f"[{node_id}] {phase} has waited {waited:.0f} s with demand "
                               f"(limit {self.cfg.max_red_s:g} s): forced next")
            return phase
        if now < st.protect_until and demand(current) > 0.0:
            return current
        return target

    def _reserve_service(self, node_id: str, st: _NodeState, phase: str, phases: Dict[str, List[str]],
                         queues: Dict[str, float], now: float) -> None:
        per_approach = max((queues.get(a, 0.0) for a in phases[phase]), default=0.0)
        if st.waited_s < self.cfg.owed_after_s or per_approach <= 0.0:
            return
        serve = min(self.cfg.serve_max_s, max(self.cfg.serve_min_s, per_approach / self.cfg.sat_flow_vps))
        if st.unobserved & set(phases[phase]):  # its queue is a guess: serve it like a fixed-time plan
            serve = max(serve, self.cfg.unobserved_serve_s)
        st.protect_until = now + serve
        logger.info(f"[{node_id}] {phase} waited {st.waited_s:.0f} s with {per_approach:g} vehicles: "
                    f"green kept at least {serve:.0f} s")

    def snapshot(self, node_id: str) -> Dict[str, Any]:
        """Current marks of a node (logs, tests, dashboard)."""
        st = self._nodes.get(node_id) or _NodeState()
        return {"stuck": sorted(st.stuck), "unobserved": sorted(st.unobserved),
                "protected": st.protect_until > self._clock(), "forcing": st.forcing}


class FairController:
    """
    Wraps any controller so the fairness guard runs inside the NoiseShieldPipeline (noise_shield.py):
    the pipeline cleans the telemetry (stale packets, slew-rate clamp, EMA), this wrapper masks
    unobserved/stuck approaches before the controller plans and bounds its target afterwards, and the
    pipeline then debounces and TTL-stamps the result. Works for every controller, swapped or not.
    """

    def __init__(self, guard: FairnessGuard, inner: Any) -> None:
        self.guard = guard
        self.inner = inner

    def compute_command(self, node_id: str, telemetry: Dict[str, Any], topology: Dict[str, Any],
                        network_state: Dict[str, Any], **kwargs: Any) -> Optional[Dict[str, Any]]:
        filtered = self.guard.filter(node_id, telemetry)
        # Neighbours plan with the same masked view this node does
        network_state[node_id] = filtered
        args = dict(node_id=node_id, telemetry=filtered, topology=topology, network_state=network_state)
        try:
            cmd = self.inner.compute_command(**args, **kwargs)
        except TypeError:
            if not kwargs:
                raise
            # Controller without current_time_s: retried here so the guard's state ticks once per message
            cmd = self.inner.compute_command(**args)
        if not cmd:
            return cmd
        target = self.guard.decide(node_id, filtered, cmd["target_phase_id"])
        return cmd if target == cmd["target_phase_id"] else {**cmd, "target_phase_id": target}
