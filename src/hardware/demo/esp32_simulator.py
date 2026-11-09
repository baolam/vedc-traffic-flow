"""
EdgeFlow AI - virtual ESP32 signal controller (test double for laptop_command_test.py and the rehearsal).

Follows src/hardware/firmware/esp32_signal_controller.ino step by step: same command checks in the same
order, same ACK texts and statuses, GREEN -> YELLOW -> ALL_RED -> GREEN clearance, min/max green,
5 s coordinator watchdog with the autonomous fallback cycle, flashing yellow for startup / safe-stop /
fault left through a steady yellow on both heads, SignalFaultEvents queued while the link is down,
health on every GREEN and every 5 s. It is NOT evidence about the real firmware: the real boards still
have to pass laptop_command_test.py and verify_trace.py.

  python src/hardware/demo/esp32_simulator.py --node J1 --mqtt-host localhost
  python src/hardware/demo/esp32_simulator.py --node J1 --speed 10      # all timings 10x shorter
  python src/hardware/demo/esp32_simulator.py --node J3 --inject wifi_drop@20+15 --inject reboot@60=BROWNOUT

--inject KIND@T[+D][=ARG] (T, D in real seconds since start; repeatable):
  wifi_drop@T+D      link lost abruptly (broker publishes the LWT), back after D s
  kill@T+D           power cut: lights dead, link lost, POWERON boot after D s
  reboot@T[=REASON]  instant reset with esp_reset_reason REASON (default PANIC), back ~1 s later
  safe_stop@T+D      emergency button held for D s
  output_fault@T+D   head output readback mismatch (shorted pin) for D s
"""

import argparse
import json
import logging
import re
import signal
import socket
import sys
import threading
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Callable, Dict, List, Optional, Tuple

sys.path.insert(0, str(Path(__file__).resolve().parent))  # also with `python -I` or another cwd
import mqtt_common as mc  # noqa: E402

logger = logging.getLogger("esp32-sim")

GREEN, YELLOW, ALL_RED, FLASH = "GREEN", "YELLOW", "ALL_RED", "FLASHING_YELLOW"
STARTUP, SAFE_STOP, FAULT = "startup", "safe-stop", "fault"
ABNORMAL_RESETS = ("PANIC", "INT_WDT", "TASK_WDT", "WDT", "BROWNOUT")
OVERRIDE_ID_PREFIX = "cmd-override-"
FAULT_QUEUE_SIZE = 8
EXPIRED_DISTRUST_COUNT = 3
READBACK_TRIP_COUNT = 3
AckEmitter = Callable[[str, str, str, str], None]
FaultEmitter = Callable[[Dict[str, Any]], None]


class Esp32Logic:
    """The firmware state machine with an injectable clock: call handle_command() and tick(now).

    Outputs leave only while the link is up (set_link), like mqttClient.connected() in the firmware:
    ACKs and health are dropped while down, faults are queued (8 deep, oldest dropped) and flushed.
    """

    def __init__(self, node_id: str, timing: mc.Timing, now: float, emit_ack: AckEmitter,
                 emit_health: Callable[[], None], clock_synced: bool = True,
                 epoch_ms: Callable[[], int] = mc.now_ms, emit_fault: Optional[FaultEmitter] = None,
                 reset_reason: str = "POWERON", boot_count: int = 1, link_up: bool = True):
        self.node_id = node_id
        self.timing = timing
        self._emit_ack = emit_ack
        self._emit_health = emit_health
        self.clock_synced = clock_synced
        self.epoch_ms = epoch_ms
        self._emit_fault = emit_fault
        self.reset_reason = reset_reason
        self.boot_count = boot_count
        self.boot_time = now
        self.link_up = link_up
        self.link_ever_up = link_up
        self.link_down_since = now
        self.wifi_lost = False
        self.fault_queue: List[Dict[str, Any]] = []
        self.faults_dropped = 0
        self.fault_seq = 0
        # Boot state of the firmware: flashing yellow (startup), then YELLOW -> ALL_RED -> North-South green
        self.current_phase = "NS"
        self.pending_phase = "NS"
        self.clear_state = FLASH
        self.flash_reason: Optional[str] = STARTUP
        self.flash_start = now
        self.yellow_both = False
        self.phase_start = now
        self.state_start = now
        self.last_command = now
        self.last_health = now
        self.fallback = False
        self.safe_stop = False
        self.pending_command_id = ""
        self.pending_target = ""
        self.min_green_s = timing.min_green_s
        self.max_green_s = timing.max_green_s
        self.min_green_fault_sent = False
        self.consecutive_expired = 0
        self.clock_distrusted = False
        self.output_fault = False          # injected: head pins read back wrong
        self.readback_mismatches = 0
        self.last_readback = now
        self.last_readback_fault: Optional[float] = None
        if reset_reason in ABNORMAL_RESETS:
            self.raise_fault("hardware", "ERR_HARDWARE_DEFECT", "CRITICAL",
                             f"Abnormal reset: {reset_reason} (boot #{boot_count})", now,
                             details={"kind": "reset", "reset_reason": reset_reason})

    # ---- helpers -------------------------------------------------------------------------------
    def phase_id(self, phase: str) -> str:
        return f"{self.node_id}_PHASE_{phase}"

    @property
    def status(self) -> str:
        if self.safe_stop:
            return "SAFE_STOP"
        if self.clear_state == FLASH and self.flash_reason == FAULT:
            return "DEGRADED"
        if self.clear_state == FLASH and self.flash_reason == STARTUP:
            return "STARTING"
        return "FALLBACK_AUTONOMOUS" if self.fallback else "HEALTHY"

    def heads(self, now: float) -> Tuple[str, str]:
        """(ns, ew) colours the firmware writes: R, Y, G or '-' (dark half of a flash)."""
        if self.clear_state == FLASH:
            on = int((now - self.boot_time) / self.timing.flash_half_period_s) % 2 == 1
            return ("Y", "Y") if on else ("-", "-")
        if self.clear_state == YELLOW:
            if self.yellow_both:
                return "Y", "Y"
            return ("Y", "R") if self.current_phase == "NS" else ("R", "Y")
        if self.clear_state == ALL_RED:
            return "R", "R"
        return ("G", "R") if self.current_phase == "NS" else ("R", "G")

    def emit_ack(self, cmd_id: str, target: str, status: str, reason: str) -> None:
        if self.link_up:
            self._emit_ack(cmd_id, target, status, reason)

    def emit_health(self) -> None:
        if self.link_up:
            self._emit_health()

    def _parse_phase(self, target: str) -> Optional[str]:
        for phase in ("NS", "EW"):
            if target == self.phase_id(phase):
                return phase
        return None

    def _start_clearance(self, target: str, cmd_id: str, target_str: str, now: float) -> None:
        self.pending_phase, self.pending_command_id, self.pending_target = target, cmd_id, target_str
        self.yellow_both = False
        self.clear_state, self.state_start = YELLOW, now

    # ---- faults (raiseFault / sendFault / flushFaults) ----------------------------------------
    def raise_fault(self, category: str, code: str, severity: str, reason: str, now: float,
                    target: Optional[str] = None, details: Optional[Dict[str, Any]] = None) -> None:
        self.fault_seq += 1
        if len(self.fault_queue) == FAULT_QUEUE_SIZE:
            self.fault_queue.pop(0)
            self.faults_dropped += 1
        self.fault_queue.append({
            "category": category, "fault_code": code, "severity": severity, "reason": reason,
            "target_phase": target or "", "current_phase": self.phase_id(self.current_phase),
            "clearance_state": self.clear_state, "details": dict(details or {}),
            "occurred": now, "seq": self.fault_seq})
        self.flush_faults(now)

    def _fault_payload(self, item: Dict[str, Any], now: float, dropped: int) -> Dict[str, Any]:
        queued_ms = int(round((now - item["occurred"]) * 1000))
        details = dict(item["details"])
        details.update(uptime_ms=int((now - self.boot_time) * 1000),
                       occurred_uptime_ms=int((item["occurred"] - self.boot_time) * 1000),
                       queued_ms=queued_ms, boot_count=self.boot_count)
        if dropped:
            details["dropped_before"] = dropped
        payload = {"event_id": f"evt-{self.node_id}-b{self.boot_count}-{item['seq']}", "node_id": self.node_id,
                   "category": item["category"], "fault_code": item["fault_code"], "severity": item["severity"],
                   "current_phase": item["current_phase"], "clearance_state": item["clearance_state"],
                   "reason": item["reason"], "details": details}
        if item["target_phase"]:
            payload["target_phase"] = item["target_phase"]
        if self.clock_synced and not self.clock_distrusted:
            payload["timestamp_ms"] = self.epoch_ms() - queued_ms
        return payload

    def flush_faults(self, now: float) -> None:
        while self.link_up and self.fault_queue:
            dropped, self.faults_dropped = self.faults_dropped, 0
            payload = self._fault_payload(self.fault_queue.pop(0), now, dropped)
            if self._emit_fault:
                self._emit_fault(payload)

    # ---- link (onMqttConnected / noteMqttDown) ------------------------------------------------
    def set_link(self, up: bool, now: float, wifi_lost: bool = False) -> None:
        if up == self.link_up:
            return
        if not up:
            self.link_up, self.link_down_since, self.wifi_lost = False, now, wifi_lost
            return
        self.link_up = True
        self.emit_health()  # firmware order (onMqttConnected): health first, then the queued faults
        if self.link_ever_up:
            down_s = now - self.link_down_since
            self.raise_fault("disconnect", "ERR_BROKER_DISCONNECT", "WARNING",
                             f"Broker link was down {down_s:.1f}s ({'Wi-Fi lost' if self.wifi_lost else 'Wi-Fi up'})",
                             now, details={"down_ms": int(down_s * 1000), "wifi_lost": self.wifi_lost,
                                           "wifi_network": 1})
        self.link_ever_up = True
        self.flush_faults(now)

    # ---- flashing mode (enterFlash / exitFlash / serviceFlash) --------------------------------
    def enter_flash(self, reason: str, now: float) -> None:
        self.clear_state, self.flash_reason, self.flash_start, self.yellow_both = FLASH, reason, now, False
        if self.pending_command_id:
            self.emit_ack(self.pending_command_id, self.pending_target, "FAILED",
                          f"Signal entered flashing mode ({reason}) before the transition was applied")
            self.pending_command_id = self.pending_target = ""
        self.emit_health()

    def exit_flash(self, now: float) -> None:
        self.flash_reason = None
        self.pending_phase = self.current_phase
        self.yellow_both = True
        self.clear_state, self.state_start = YELLOW, now
        self.emit_health()

    def set_safe_stop(self, active: bool, now: float) -> None:
        if self.safe_stop == active:
            return
        self.safe_stop = active
        if active:
            self.raise_fault("emergency", "ERR_SAFE_STOP_ENGAGED", "CRITICAL",
                             "Safe-stop emergency switch engaged by user", now)
            self.enter_flash(SAFE_STOP, now)
        else:
            self.raise_fault("emergency", "ERR_SAFE_STOP_RELEASED", "INFO", "Safe-stop emergency switch released", now)
            self.exit_flash(now)

    def force_heads(self, ns: str, ew: str, now: float) -> None:
        """Test hook for writeHeads(): a conflicting double green trips the guard (only a bug can do this)."""
        if ns == "G" and ew == "G":
            self.raise_fault("feedback_error", "ERR_CONFLICT_GUARD_TRIGGERED", "CRITICAL",
                             "Conflicting green requested -> forced ALL_RED, flashing", now)
            if not self.safe_stop:
                self.enter_flash(FAULT, now)

    # ---- incoming command (onMqttCommand in the firmware) -----------------------------------
    def _expired(self, doc: Dict[str, Any], now: float) -> bool:
        expires = doc.get("expires_at_ms") or 0
        if not expires or not self.clock_synced or self.clock_distrusted or self.epoch_ms() <= expires:
            self.consecutive_expired = 0
            return False
        self.consecutive_expired += 1
        if self.consecutive_expired >= EXPIRED_DISTRUST_COUNT:
            self.clock_distrusted = True
            self.raise_fault("hardware", "ERR_HARDWARE_DEFECT", "WARNING",
                             "Repeated EXPIRED commands: device clock distrusted, expiry no longer checked",
                             now, details={"kind": "clock"})
        return True

    def _override_applied(self, cmd_id: str, target_str: str, now: float) -> None:
        if cmd_id.startswith(OVERRIDE_ID_PREFIX):
            self.raise_fault("emergency", "ERR_EMERGENCY_OVERRIDE", "INFO", "Operator phase override applied",
                             now, target=target_str)

    def handle_command(self, raw: bytes, now: float) -> None:
        doc = mc.parse_json(raw)
        if doc is None:
            self.emit_ack("unknown", "unknown", "REJECTED", "Invalid JSON payload format")
            return
        if doc.get("node_id") != self.node_id:
            return  # commands for other nodes are ignored silently
        self.last_command = now  # a well-formed command proves the coordinator is alive
        self.fallback = False
        cmd_id = doc["command_id"] if isinstance(doc.get("command_id"), str) else "unknown"
        target_str = doc["target_phase_id"] if isinstance(doc.get("target_phase_id"), str) else ""

        if self.safe_stop:
            self.emit_ack(cmd_id, target_str, "REJECTED", "Safe-stop is engaged")
            return
        if self.clear_state == FLASH:
            self.emit_ack(cmd_id, target_str, "REJECTED", f"Signal is in flashing mode ({self.flash_reason})")
            return
        if self._expired(doc, now):
            self.emit_ack(cmd_id, target_str, "EXPIRED", "Command expired before processing")
            return
        target = self._parse_phase(target_str)
        if target is None:
            self.emit_ack(cmd_id, target_str, "REJECTED", "Unknown target_phase_id for this node")
            self.raise_fault("feedback_error", "ERR_FEEDBACK_MISMATCH", "WARNING",
                             "Unknown target_phase_id for this node", now, target=target_str)
            return

        # Requested timings may lengthen but never shorten the device limits
        min_green = max(float(doc.get("min_green_s", self.timing.min_green_s)), 0.0)
        max_green = max(float(doc.get("max_green_s", self.timing.max_green_s)), 0.0)
        self.min_green_s = max(min_green, self.timing.min_green_s)
        self.max_green_s = min(max(max_green, self.min_green_s), self.timing.max_green_s)

        if target == self.current_phase:
            if self.clear_state == GREEN:
                self.emit_ack(cmd_id, target_str, "APPLIED", "Phase is already active. Green time extended.")
                self._override_applied(cmd_id, target_str, now)
            else:
                self.emit_ack(cmd_id, target_str, "ACCEPTED", "Transition currently clearing through Yellow/All-Red.")
            return
        if target == self.pending_phase and self.clear_state != GREEN:
            self.emit_ack(cmd_id, target_str, "ACCEPTED", "Phase transition is already pending and clearing.")
            return
        if self.clear_state != GREEN:
            self.emit_ack(cmd_id, target_str, "REJECTED", "Clearance interval currently in progress.")
            return
        elapsed = now - self.phase_start
        if elapsed < self.min_green_s:
            reason = f"Min green time not met ({elapsed:.1f}s < {self.min_green_s:.1f}s)"
            self.emit_ack(cmd_id, target_str, "REJECTED", reason)
            if not self.min_green_fault_sent:
                self.min_green_fault_sent = True
                self.raise_fault("feedback_error", "ERR_MIN_GREEN_VIOLATION", "INFO", reason, now, target=target_str)
            return
        self._start_clearance(target, cmd_id, target_str, now)
        self.emit_ack(cmd_id, target_str, "ACCEPTED",
                      "Clearance initiated: GREEN -> YELLOW (3s) -> ALL_RED (2s) -> TARGET")

    # ---- main loop body ---------------------------------------------------------------------
    def _service_flash(self, now: float) -> None:
        held = now - self.flash_start
        if (self.flash_reason == STARTUP and held >= self.timing.startup_flash_s) or \
                (self.flash_reason == FAULT and held >= self.timing.fault_flash_hold_s):
            self.exit_flash(now)

    def _run_state_machine(self, now: float) -> None:
        if self.clear_state == YELLOW and now - self.state_start >= self.timing.yellow_s:
            self.yellow_both = False
            self.clear_state, self.state_start = ALL_RED, now
        elif self.clear_state == ALL_RED and now - self.state_start >= self.timing.all_red_s:
            self.current_phase, self.clear_state = self.pending_phase, GREEN
            self.state_start = self.phase_start = now
            self.min_green_fault_sent = False
            if self.pending_command_id:  # APPLIED only once the output really changed
                self.emit_ack(self.pending_command_id, self.pending_target, "APPLIED",
                              "Physical clearance completed. Target phase is now active GREEN.")
                self._override_applied(self.pending_command_id, self.pending_target, now)
                self.pending_command_id = self.pending_target = ""
            self.emit_health()

        other = "EW" if self.current_phase == "NS" else "NS"
        if now - self.last_command > self.timing.watchdog_s:
            if not self.fallback:
                self.fallback = True
                self.raise_fault("disconnect", "ERR_COORDINATOR_TIMEOUT", "WARNING",
                                 "Coordinator timeout > 5.0s -> Switched to Autonomous Fallback Schedule", now)
                self.emit_health()
            if self.clear_state == GREEN and now - self.phase_start >= self.timing.fallback_green_s:
                self._start_clearance(other, "", self.phase_id(other), now)  # local cycle: no ACK
        elif self.clear_state == GREEN and now - self.phase_start >= self.max_green_s:
            self._start_clearance(other, "", self.phase_id(other), now)  # device-enforced max green

    def _service_readback(self, now: float) -> None:
        if now - self.last_readback < self.timing.readback_period_s:
            return
        self.last_readback = now
        if not self.output_fault:
            self.readback_mismatches = 0
            return
        self.readback_mismatches += 1
        if self.readback_mismatches < READBACK_TRIP_COUNT:
            return
        self.readback_mismatches = 0
        if self.last_readback_fault is None or now - self.last_readback_fault >= self.timing.readback_fault_repeat_s:
            self.last_readback_fault = now
            self.raise_fault("hardware", "ERR_HARDWARE_DEFECT", "CRITICAL",
                             "Output readback mismatch on GPIO 23 (shorted/bridged pin?)", now,
                             details={"kind": "output_readback", "gpio": 23})
        if not self.safe_stop:
            self.enter_flash(FAULT, now)
        else:
            self.flash_start = now

    def tick(self, now: float) -> None:
        if self.clear_state == FLASH:
            self._service_flash(now)
        else:
            self._run_state_machine(now)
        self._service_readback(now)
        if now - self.last_health >= self.timing.health_period_s:
            self.last_health = now
            self.emit_health()

    def health(self, now: float, started: float) -> Dict[str, Any]:
        payload: Dict[str, Any] = {
            "node_id": self.node_id, "service": "esp32_actuator", "status": self.status,
            "current_phase": self.phase_id(self.current_phase), "clearance": self.clear_state,
            "safe_stop": self.safe_stop, "uptime_s": int(now - started), "wifi_rssi_dbm": -55,
            "wifi_network": 1, "reset_reason": self.reset_reason, "boot_count": self.boot_count,
            "clock_synced": self.clock_synced and not self.clock_distrusted,
            "faults_queued": len(self.fault_queue),
        }
        if self.clock_synced:
            payload["timestamp_ms"] = self.epoch_ms()
        return payload


# ---- fault injection for the rehearsal ------------------------------------------------------------
INJECT_RE = re.compile(r"^(wifi_drop|kill|reboot|safe_stop|output_fault)@(\d+(?:\.\d+)?)(?:\+(\d+(?:\.\d+)?))?(?:=(\w+))?$")
NEEDS_DURATION = ("wifi_drop", "kill", "safe_stop", "output_fault")


@dataclass(frozen=True)
class Injection:
    kind: str
    at_s: float
    duration_s: float = 0.0
    arg: str = ""


def parse_injection(spec: str) -> Injection:
    m = INJECT_RE.match(spec.strip())
    if not m:
        raise ValueError(f"bad --inject '{spec}': expected KIND@T[+D][=ARG], KIND in "
                         "wifi_drop, kill, reboot, safe_stop, output_fault")
    kind, at, dur, arg = m.group(1), float(m.group(2)), float(m.group(3) or 0), m.group(4) or ""
    if kind in NEEDS_DURATION and dur <= 0:
        raise ValueError(f"--inject {spec}: {kind} needs +D (seconds)")
    if kind == "reboot":
        arg = (arg or "PANIC").upper()
    return Injection(kind, at, dur, arg)


def schedule(injections: List[Injection]) -> List[Tuple[float, str, Injection]]:
    """(time, 'start'|'end', injection), sorted. reboot ends 1 s after it starts (boot + Wi-Fi)."""
    events = []
    for inj in injections:
        events.append((inj.at_s, "start", inj))
        events.append((inj.at_s + (inj.duration_s if inj.kind != "reboot" else 1.0), "end", inj))
    return sorted(events, key=lambda e: (e[0], e[1] == "start"))


def run(args: argparse.Namespace, stop: Optional[threading.Event] = None) -> int:
    stop = stop or threading.Event()
    timing = mc.Timing().scaled(1.0 / args.speed)
    node = args.node
    started = time.monotonic()
    health_topic = mc.topics.get_health_topic(node)
    will = json.dumps({"node_id": node, "service": "esp32_actuator", "status": "OFFLINE"})
    client = mc.make_client(f"ESP32_Sim_{node}", will=None)
    client.will_set(health_topic, will, qos=0, retain=False)  # like the firmware: not retained
    lock = threading.Lock()
    pending = schedule([parse_injection(s) for s in args.inject])

    def publish(topic: str, payload: Dict[str, Any]) -> None:
        client.publish(topic, json.dumps(payload))

    def emit_ack(cmd_id: str, target: str, status: str, reason: str) -> None:
        ack = {"command_id": cmd_id, "node_id": node, "target_phase_id": target or "UNKNOWN", "status": status,
               "uptime_ms": int((time.monotonic() - started) * 1000), "reason": reason}
        if not args.no_clock:
            ack["timestamp_ms"] = mc.now_ms()
        logger.info("[ACK] %s %s (%s)", status, cmd_id, reason)
        publish(mc.topics.get_ack_topic(node), ack)

    def emit_fault(fault: Dict[str, Any]) -> None:
        cat = fault.get("category", "disconnect")
        logger.warning("[FAULT] [%s] %s: %s", cat.upper(), fault.get("fault_code"), fault.get("reason"))
        publish(mc.topics.get_signal_fault_topic(node, category=cat), fault)

    state: Dict[str, Any] = {"boots": 1, "boot_at": started}

    def new_logic(reset_reason: str) -> Esp32Logic:
        state["boot_at"] = time.monotonic()
        return Esp32Logic(node, timing, state["boot_at"], emit_ack,
                          lambda: publish(health_topic, state["logic"].health(time.monotonic(), state["boot_at"])),
                          clock_synced=not args.no_clock, emit_fault=emit_fault,
                          reset_reason=reset_reason, boot_count=state["boots"], link_up=False)

    state["logic"] = new_logic("POWERON")

    def on_connect(c, userdata, flags, rc):
        if rc == 0:
            c.subscribe(mc.topics.get_command_topic(node))
            logger.info("Connected, subscribed to %s", mc.topics.get_command_topic(node))
            with lock:
                if state["logic"] is not None:
                    state["logic"].set_link(True, time.monotonic())

    def on_message(c, userdata, msg):
        with lock:
            if state["logic"] is not None:
                state["logic"].handle_command(msg.payload, time.monotonic())

    def drop_link() -> None:
        """Abrupt loss (no DISCONNECT packet): the broker publishes the LWT, as for a real board.
        Called without `lock`: loop_stop() joins the paho thread, which may be waiting for it."""
        client.loop_stop()
        sock = client.socket()
        if sock is not None:
            try:
                sock.shutdown(socket.SHUT_RDWR)  # FIN now, even if paho still holds a reference
            except OSError:
                pass
            sock.close()

    def restore_link() -> None:
        try:
            client.reconnect()
        except OSError as e:
            logger.error("reconnect failed: %s", e)
        client.loop_start()

    def apply(when: str, inj: Injection, now: float) -> Optional[Callable[[], None]]:
        """Changes the board state (caller holds `lock`); returns the network action to run after releasing it."""
        logic = state["logic"]
        logger.warning("[INJECT] %s %s%s", inj.kind, when, f" ({inj.arg})" if inj.arg else "")
        if inj.kind == "safe_stop" and logic is not None:
            logic.set_safe_stop(when == "start", now)
        elif inj.kind == "output_fault" and logic is not None:
            logic.output_fault = when == "start"
        elif inj.kind == "wifi_drop":
            if when == "start":
                if logic is not None:
                    logic.set_link(False, now, wifi_lost=True)
                return drop_link
            return restore_link
        elif inj.kind in ("kill", "reboot"):
            if when == "start":
                state["logic"] = None  # lights dead, nothing ticks
                return drop_link
            state["boots"] += 1
            state["logic"] = new_logic("POWERON" if inj.kind == "kill" else inj.arg)
            return restore_link
        return None

    client.on_connect, client.on_message = on_connect, on_message
    try:
        mc.connect(client, args.mqtt_host, args.mqtt_port)
    except ConnectionError as e:
        logger.error(str(e))
        return 1
    logger.info("Virtual ESP32 %s running (timings %.1fx faster); boot: flashing %.1fs, yellow, all-red, GREEN NS",
                node, args.speed, timing.startup_flash_s)
    try:
        while not stop.is_set():
            now = time.monotonic()
            actions = []
            with lock:
                while pending and now - started >= pending[0][0]:
                    _, when, inj = pending.pop(0)
                    actions.append(apply(when, inj, now))
                if state["logic"] is not None:
                    state["logic"].tick(now)
            for action in actions:
                if action:
                    action()
            stop.wait(0.02)
    finally:
        client.disconnect()
        client.loop_stop()
    return 0


def parse_args(argv: Optional[List[str]] = None) -> argparse.Namespace:
    p = argparse.ArgumentParser(description="Virtual ESP32 signal controller for MQTT tests")
    p.add_argument("--node", default="J1")
    p.add_argument("--mqtt-host", default=mc.env_host())
    p.add_argument("--mqtt-port", type=int, default=mc.env_port())
    p.add_argument("--speed", type=float, default=1.0, help="shorten every timing by this factor (tests use 10+)")
    p.add_argument("--no-clock", action="store_true", help="behave like an ESP32 whose SNTP has not synced")
    p.add_argument("--inject", action="append", default=[], metavar="KIND@T[+D][=ARG]",
                   help="fault to inject (see module docstring); repeatable")
    args = p.parse_args(argv)
    for spec in args.inject:
        try:
            parse_injection(spec)
        except ValueError as e:
            p.error(str(e))
    return args


def main(argv: Optional[List[str]] = None) -> int:
    logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] [esp32-sim] %(message)s")
    args = parse_args(argv)
    stop = threading.Event()
    signal.signal(signal.SIGTERM, lambda *_: stop.set())
    signal.signal(signal.SIGINT, lambda *_: stop.set())
    return run(args, stop)


if __name__ == "__main__":
    sys.exit(main())
