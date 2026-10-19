"""
Runtime guards of the graph-control loop.

- BlindNodeGate: telemetry that observed nothing (camera lost, broken video) gets no command, so the ESP32
  stops hearing from the coordinator and runs its own fixed 15 s/phase fallback after 5 s (G1).
- PolicyFollower: polls the API's requested controller (dashboard "Apply Policy") and rebuilds the controller
  when it changes, so the dashboard switch acts on the real lights instead of only on a label.
- ManualOverrideHold: a dashboard phase override pauses the controller on that node until the forced phase
  has really been green for a while.
"""
import json
import logging
import time
import urllib.request
from typing import Any, Callable, Dict, Optional, Set

logger = logging.getLogger("graph-control")


def is_blind(telemetry: Dict[str, Any]) -> bool:
    """True when the message carries no observation: no approach at all, or every approach at confidence 0.
    A missing confidence (simulator telemetry) counts as observed, as in src/control/gateway.py."""
    approaches = telemetry.get("approaches") or []
    return not approaches or all(a.get("confidence", 1.0) <= 0.0 for a in approaches)


class BlindNodeGate:
    """Decides which telemetry reaches the controller; logs each blind episode once per node."""

    def __init__(self) -> None:
        self._blind: Set[str] = set()

    def admit(self, node_id: str, telemetry: Dict[str, Any], network_state: Dict[str, Any]) -> bool:
        if is_blind(telemetry):
            # Neighbours must not plan with this node's last (stale) queues either
            network_state.pop(node_id, None)
            if node_id not in self._blind:
                self._blind.add(node_id)
                logger.warning(f"[{node_id}] telemetry has no observation (confidence 0 / no approach): "
                               "no command sent, the ESP32 falls back to its fixed cycle after 5 s")
            return False
        if node_id in self._blind:
            self._blind.discard(node_id)
            logger.info(f"[{node_id}] observations are back: adaptive control resumes")
        return True


def fetch_json(url: str, timeout_s: float = 2.0) -> Dict[str, Any]:
    with urllib.request.urlopen(url, timeout=timeout_s) as resp:  # noqa: S310 - URL comes from our own config
        return json.loads(resp.read().decode("utf-8"))


class PolicyFollower:
    """Follows the controller name published by the API; keeps the running controller on any failure."""

    def __init__(self, url: str, current: str, build: Callable[[str], Any],
                 fetch: Callable[[str], Dict[str, Any]] = fetch_json) -> None:
        self.url = url
        self.current = current.lower()
        self._build = build
        self._fetch = fetch
        self._failed: Optional[str] = None      # requested name that could not be built: not retried
        self._unreachable = False

    def poll_once(self) -> Optional[Any]:
        """Returns a newly built controller when the requested policy changed, else None."""
        try:
            requested = str(self._fetch(self.url).get("active_controller") or "").lower()
        except Exception as exc:  # noqa: BLE001 - the API may be down; control must go on
            if not self._unreachable:
                logger.warning(f"Policy URL {self.url} unreachable ({exc}); keeping controller '{self.current}'")
                self._unreachable = True
            return None
        if self._unreachable:
            logger.info(f"Policy URL {self.url} reachable again")
            self._unreachable = False
        if not requested or requested == self.current or requested == self._failed:
            return None
        try:
            controller = self._build(requested)
        except Exception as exc:  # noqa: BLE001 - unknown name, missing RL model file, ...
            logger.error(f"Cannot switch to controller '{requested}' ({exc}); keeping '{self.current}'")
            self._failed = requested
            return None
        logger.info(f"Controller switched live: '{self.current}' -> '{requested}' (requested by the API policy)")
        self.current, self._failed = requested, None
        return controller


# Command ids the API gives dashboard overrides (POST /api/v1/control/override); re-sends from here use HOLD_ID_PREFIX
OVERRIDE_ID_PREFIX = "cmd-override-"
HOLD_ID_PREFIX = "gc-hold-"
DEVICE_MIN_GREEN_S = 5.0   # the ESP32 never goes below this anyway
DEVICE_MAX_GREEN_S = 60.0
# Forced phase still not green after this long (unknown phase, ESP32 offline, safe-stop): give the node back
OVERRIDE_MAX_WAIT_S = 25.0


class ManualOverrideHold:
    """Dashboard phase override: the API publishes one command, then graph-control yields that node.

    Until the forced phase has been green for hold_s, every telemetry period re-sends it instead of the
    controller decision. The ESP32 keeps all its safety rules: a re-send it rejects (min green not met,
    clearance in progress) is accepted as soon as they allow, and once applied the re-sends extend that green.
    Without this the single API command was often rejected, and the controller took the phase back 5 s later.
    """

    def __init__(self, hold_s: float, clock: Callable[[], float] = time.time) -> None:
        self.hold_s = hold_s
        self._clock = clock
        self._holds: Dict[str, Dict[str, Any]] = {}

    def observe_command(self, command: Dict[str, Any]) -> bool:
        """Starts a hold for a dashboard override seen on the command topic; True if one started."""
        if self.hold_s <= 0 or not str(command.get("command_id", "")).startswith(OVERRIDE_ID_PREFIX):
            return False
        node_id, target = command.get("node_id"), command.get("target_phase_id")
        if not node_id or not target:
            return False
        self._holds[node_id] = {"target": target, "since": self._clock(), "green_since": None}
        logger.info(f"[{node_id}] manual override -> {target}: controller paused until it has been "
                    f"green {self.hold_s:.0f} s")
        return True

    def command_for(self, node_id: str, current_phase_id: Optional[str]) -> Optional[Dict[str, Any]]:
        """The command to publish instead of the controller's while a hold is active, else None."""
        hold = self._holds.get(node_id)
        if hold is None:
            return None
        now = self._clock()
        # Green time counts only while the ESP32 reports the forced phase (it still reports the old one
        # during yellow/all-red, which may briefly be the target too: restart the count when it leaves)
        if current_phase_id == hold["target"]:
            hold["green_since"] = hold["green_since"] or now
        else:
            hold["green_since"] = None
        held = hold["green_since"] is not None and now - hold["green_since"] >= self.hold_s
        gave_up = hold["green_since"] is None and now - hold["since"] >= OVERRIDE_MAX_WAIT_S
        if held or gave_up:
            del self._holds[node_id]
            outcome = f"held {self.hold_s:.0f} s" if held else f"not green after {OVERRIDE_MAX_WAIT_S:.0f} s"
            logger.info(f"[{node_id}] manual override {hold['target']} {outcome}: controller resumes")
            return None
        return {
            "command_id": f"{HOLD_ID_PREFIX}{node_id}-{int(now * 1000)}",
            "node_id": node_id,
            "target_phase_id": hold["target"],
            "min_green_s": DEVICE_MIN_GREEN_S,
            "max_green_s": DEVICE_MAX_GREEN_S,
            "controller": "manual_override",
        }
