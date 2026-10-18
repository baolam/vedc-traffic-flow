"""
EdgeFlow AI - virtual ESP32 signal controller (test double for laptop_command_test.py).

Follows src/hardware/firmware/esp32_signal_controller.ino step by step: same command checks in the same
order, same ACK texts and statuses, GREEN -> YELLOW -> ALL_RED -> GREEN clearance, min/max green,
5 s coordinator watchdog with the autonomous fallback cycle, health on every GREEN and every 5 s.
It lets the laptop side be rehearsed (and tested automatically) when no board is connected.
It is NOT evidence about the real firmware: the real boards still have to pass laptop_command_test.py.

  python src/hardware/demo/esp32_simulator.py --node J1 --mqtt-host localhost
  python src/hardware/demo/esp32_simulator.py --node J1 --speed 10      # all timings 10x shorter
"""

import argparse
import json
import logging
import signal
import sys
import threading
import time
from pathlib import Path
from typing import Any, Callable, Dict, List, Optional

sys.path.insert(0, str(Path(__file__).resolve().parent))  # also with `python -I` or another cwd
import mqtt_common as mc  # noqa: E402

logger = logging.getLogger("esp32-sim")

GREEN, YELLOW, ALL_RED = "GREEN", "YELLOW", "ALL_RED"
AckEmitter = Callable[[str, str, str, str], None]


class Esp32Logic:
    """The firmware state machine with an injectable clock: call handle_command() and tick(now)."""

    def __init__(self, node_id: str, timing: mc.Timing, now: float, emit_ack: AckEmitter,
                 emit_health: Callable[[], None], clock_synced: bool = True,
                 epoch_ms: Callable[[], int] = mc.now_ms):
        self.node_id = node_id
        self.timing = timing
        self.emit_ack = emit_ack
        self.emit_health = emit_health
        self.clock_synced = clock_synced
        self.epoch_ms = epoch_ms
        # Boot state of the firmware: ALL_RED first, then North-South green
        self.current_phase = "NS"
        self.pending_phase = "NS"
        self.clear_state = ALL_RED
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

    # ---- helpers -------------------------------------------------------------------------------
    def phase_id(self, phase: str) -> str:
        return f"{self.node_id}_PHASE_{phase}"

    @property
    def status(self) -> str:
        return "SAFE_STOP" if self.safe_stop else ("FALLBACK_AUTONOMOUS" if self.fallback else "HEALTHY")

    def _parse_phase(self, target: str) -> Optional[str]:
        for phase in ("NS", "EW"):
            if target == self.phase_id(phase):
                return phase
        return None

    def _start_clearance(self, target: str, cmd_id: str, target_str: str, now: float) -> None:
        self.pending_phase, self.pending_command_id, self.pending_target = target, cmd_id, target_str
        self.clear_state, self.state_start = YELLOW, now

    # ---- incoming command (onMqttCommand in the firmware) -----------------------------------
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
        expires = doc.get("expires_at_ms") or 0
        if expires > 0 and self.clock_synced and self.epoch_ms() > expires:
            self.emit_ack(cmd_id, target_str, "EXPIRED", "Command expired before processing")
            return
        target = self._parse_phase(target_str)
        if target is None:
            self.emit_ack(cmd_id, target_str, "REJECTED", "Unknown target_phase_id for this node")
            return

        # Requested timings may lengthen but never shorten the device limits
        min_green = max(float(doc.get("min_green_s", self.timing.min_green_s)), 0.0)
        max_green = max(float(doc.get("max_green_s", self.timing.max_green_s)), 0.0)
        self.min_green_s = max(min_green, self.timing.min_green_s)
        self.max_green_s = min(max(max_green, self.min_green_s), self.timing.max_green_s)

        if target == self.current_phase:
            if self.clear_state == GREEN:
                self.emit_ack(cmd_id, target_str, "APPLIED", "Phase is already active. Green time extended.")
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
            self.emit_ack(cmd_id, target_str, "REJECTED",
                          f"Min green time not met ({elapsed:.1f}s < {self.min_green_s:.1f}s)")
            return
        self._start_clearance(target, cmd_id, target_str, now)
        self.emit_ack(cmd_id, target_str, "ACCEPTED",
                      "Clearance initiated: GREEN -> YELLOW (3s) -> ALL_RED (2s) -> TARGET")

    # ---- main loop body ---------------------------------------------------------------------
    def tick(self, now: float) -> None:
        if not self.safe_stop:
            if self.clear_state == YELLOW and now - self.state_start >= self.timing.yellow_s:
                self.clear_state, self.state_start = ALL_RED, now
            elif self.clear_state == ALL_RED and now - self.state_start >= self.timing.all_red_s:
                self.current_phase, self.clear_state = self.pending_phase, GREEN
                self.state_start = self.phase_start = now
                if self.pending_command_id:  # APPLIED only once the output really changed
                    self.emit_ack(self.pending_command_id, self.pending_target, "APPLIED",
                                  "Physical clearance completed. Target phase is now active GREEN.")
                    self.pending_command_id = self.pending_target = ""
                self.emit_health()
                self.last_health = now

            other = "EW" if self.current_phase == "NS" else "NS"
            if now - self.last_command > self.timing.watchdog_s:
                if not self.fallback:
                    self.fallback = True
                    self.emit_health()
                if self.clear_state == GREEN and now - self.phase_start >= self.timing.fallback_green_s:
                    self._start_clearance(other, "", self.phase_id(other), now)  # local cycle: no ACK
            elif self.clear_state == GREEN and now - self.phase_start >= self.max_green_s:
                self._start_clearance(other, "", self.phase_id(other), now)  # device-enforced max green

        if now - self.last_health >= self.timing.health_period_s:
            self.last_health = now
            self.emit_health()

    def health(self, now: float, started: float) -> Dict[str, Any]:
        payload: Dict[str, Any] = {
            "node_id": self.node_id, "service": "esp32_actuator", "status": self.status,
            "current_phase": self.phase_id(self.current_phase), "clearance": self.clear_state,
            "safe_stop": self.safe_stop, "uptime_s": int(now - started), "wifi_rssi_dbm": -55,
        }
        if self.clock_synced:
            payload["timestamp_ms"] = self.epoch_ms()
        return payload


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

    def publish(topic: str, payload: Dict[str, Any]) -> None:
        client.publish(topic, json.dumps(payload))

    def emit_ack(cmd_id: str, target: str, status: str, reason: str) -> None:
        ack = {"command_id": cmd_id, "node_id": node, "target_phase_id": target or "UNKNOWN", "status": status,
               "uptime_ms": int((time.monotonic() - started) * 1000), "reason": reason}
        if not args.no_clock:
            ack["timestamp_ms"] = mc.now_ms()
        logger.info("[ACK] %s %s (%s)", status, cmd_id, reason)
        publish(mc.topics.get_ack_topic(node), ack)

    logic = Esp32Logic(node, timing, time.monotonic(), emit_ack,
                       lambda: publish(health_topic, logic.health(time.monotonic(), started)),
                       clock_synced=not args.no_clock)

    def on_connect(c, userdata, flags, rc):
        if rc == 0:
            c.subscribe(mc.topics.get_command_topic(node))
            logger.info("Connected, subscribed to %s", mc.topics.get_command_topic(node))
            with lock:
                logic.emit_health()

    def on_message(c, userdata, msg):
        with lock:
            logic.handle_command(msg.payload, time.monotonic())

    client.on_connect, client.on_message = on_connect, on_message
    try:
        mc.connect(client, args.mqtt_host, args.mqtt_port)
    except ConnectionError as e:
        logger.error(str(e))
        return 1
    logger.info("Virtual ESP32 %s running (timings %.1fx faster); boot: ALL_RED %.1fs then GREEN NS",
                node, args.speed, timing.all_red_s)
    try:
        while not stop.is_set():
            with lock:
                logic.tick(time.monotonic())
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
    return p.parse_args(argv)


def main(argv: Optional[List[str]] = None) -> int:
    logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] [esp32-sim] %(message)s")
    args = parse_args(argv)
    stop = threading.Event()
    signal.signal(signal.SIGTERM, lambda *_: stop.set())
    signal.signal(signal.SIGINT, lambda *_: stop.set())
    return run(args, stop)


if __name__ == "__main__":
    sys.exit(main())
