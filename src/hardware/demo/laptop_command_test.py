"""
EdgeFlow AI - laptop-side MQTT tool to drive and test the ESP32 signal controllers.

  status    who is online? (health of J1/J2/vision: status, phase, Wi-Fi signal, uptime)
  send      one ControlCommand, then print the ACKs it triggers (ACCEPTED -> APPLIED / REJECTED ...)
  test      automatic suite per node: checks every ACK the firmware must give and the 3 s yellow + 2 s
            all-red clearance timing; exit 1 on any FAIL, optional JSON report as evidence
  cycle     toggle the phase on a timer (to watch the LEDs on the model)
  monitor   print every edgeflow/v1/# message as it arrives

  python src/hardware/demo/laptop_command_test.py --mqtt-host localhost status
  python src/hardware/demo/laptop_command_test.py send J1 EW
  python src/hardware/demo/laptop_command_test.py test J1 J2 --json report.json

Stop graph-control first (docker compose stop graph-control) unless you want its commands mixed in.
The `test` suite sends harmless keepalive commands (unknown phase, REJECTED by design) so the ESP32
watchdog (5 s without a command -> autonomous fallback) never trips while the suite waits.
"""

import argparse
import json
import logging
import sys
import threading
import time
from pathlib import Path
import uuid
from dataclasses import dataclass, field
from typing import Any, Dict, Iterable, List, Optional, Sequence

sys.path.insert(0, str(Path(__file__).resolve().parent))  # also with `python -I` or another cwd
import mqtt_common as mc  # noqa: E402

logger = logging.getLogger("laptop-test")

FINAL_STATUSES = ("APPLIED", "REJECTED", "EXPIRED", "FAILED")
KEEPALIVE_PREFIX = "ka-"
EXPIRED_AGE_MS = 10_000


@dataclass(frozen=True)
class Ack:
    t: float                       # arrival time (time.monotonic)
    payload: Dict[str, Any]

    @property
    def command_id(self) -> str:
        return str(self.payload.get("command_id", ""))

    @property
    def status(self) -> str:
        return str(self.payload.get("status", ""))

    @property
    def reason(self) -> str:
        return str(self.payload.get("reason", ""))


@dataclass
class StepResult:
    name: str
    verdict: str                   # PASS | FAIL | SKIP
    detail: str = ""

    @property
    def failed(self) -> bool:
        return self.verdict == "FAIL"


@dataclass
class Bus:
    """MQTT connection that records ACKs and the latest health of every device."""
    client: Any
    acks: Dict[str, List[Ack]] = field(default_factory=dict)       # node -> ACKs in arrival order
    health: Dict[str, Dict[str, Any]] = field(default_factory=dict)
    health_seen: Dict[str, float] = field(default_factory=dict)
    seen_messages: List[Any] = field(default_factory=list)
    cond: threading.Condition = field(default_factory=threading.Condition)
    echo: Any = None

    def on_message(self, client, userdata, msg) -> None:
        data = mc.parse_json(msg.payload)
        parts = msg.topic.split("/")
        with self.cond:
            if len(parts) == 5 and parts[2] == "control" and parts[4] == "ack" and data is not None:
                self.acks.setdefault(parts[3], []).append(Ack(time.monotonic(), data))
            elif len(parts) == 4 and parts[2] == "health" and data is not None:
                self.health[parts[3]] = data
                self.health_seen[parts[3]] = time.monotonic()
            self.cond.notify_all()
        if self.echo:
            self.echo(msg.topic, msg.payload)

    def publish(self, topic: str, payload: Any) -> None:
        raw = payload if isinstance(payload, (bytes, str)) else json.dumps(payload)
        self.client.publish(topic, raw)

    def wait_ack(self, node: str, command_id: str, statuses: Iterable[str], timeout_s: float,
                 after: float = 0.0) -> Optional[Ack]:
        """First ACK of the command with one of the statuses that arrived after `after`, or None on timeout."""
        wanted = tuple(statuses)
        deadline = time.monotonic() + timeout_s
        with self.cond:
            while True:
                for ack in self.acks.get(node, []):
                    if ack.t >= after and ack.command_id == command_id and ack.status in wanted:
                        return ack
                remaining = deadline - time.monotonic()
                if remaining <= 0:
                    return None
                self.cond.wait(remaining)

    def acks_since(self, node: str, after: float) -> List[Ack]:
        with self.cond:
            return [a for a in self.acks.get(node, [])
                    if a.t >= after and not a.command_id.startswith(KEEPALIVE_PREFIX)]

    def wait_health(self, node: str, predicate, timeout_s: float, after: float = 0.0) -> Optional[Dict[str, Any]]:
        """Health of the node that arrived after `after` and satisfies the predicate, else None."""
        deadline = time.monotonic() + timeout_s
        with self.cond:
            while True:
                data = self.health.get(node)
                if data and self.health_seen.get(node, 0.0) >= after and predicate(data):
                    return data
                remaining = deadline - time.monotonic()
                if remaining <= 0:
                    return None
                self.cond.wait(remaining)


def connect_bus(host: str, port: int, echo=None) -> Bus:
    client = mc.make_client(f"laptop-command-test-{uuid.uuid4().hex[:6]}")
    bus = Bus(client, echo=echo)
    client.on_message = bus.on_message
    client.on_connect = lambda c, u, f, rc: rc == 0 and (c.subscribe(mc.topics.ACK_SUB_PATTERN),
                                                         c.subscribe(mc.topics.HEALTH_SUB_PATTERN))
    mc.connect(client, host, port)
    return bus


def resolve_phase(topology: str, node_id: str, token: str) -> str:
    """'NS'/'EW' (or a full phase id) -> the node's phase_id from the topology contract."""
    phases = [p["phase_id"] for p in mc.load_node(topology, node_id).get("phases", [])]
    for phase_id in phases:
        if token == phase_id or phase_id.endswith(f"_PHASE_{token.upper()}"):
            return phase_id
    raise ValueError(f"Node {node_id} has no phase '{token}' (has: {', '.join(phases)})")


def build_command(node_id: str, target_phase_id: str, min_green_s: float = 5.0, max_green_s: float = 60.0,
                  controller: str = "manual_test", expires_in_s: Optional[float] = None,
                  command_id: Optional[str] = None) -> Dict[str, Any]:
    """ControlCommand per contracts/schemas/control_command.json; expires_at_ms is read by the firmware."""
    cmd: Dict[str, Any] = {
        "command_id": command_id or f"t-{uuid.uuid4().hex[:8]}",
        "node_id": node_id,
        "target_phase_id": target_phase_id,
        "min_green_s": float(min_green_s),
        "max_green_s": float(max_green_s),
        "controller": controller,
    }
    if expires_in_s is not None:
        cmd["expires_at_ms"] = mc.now_ms() + int(expires_in_s * 1000)
    mc.validate(cmd, "control_command")
    return cmd


def send_command(bus: Bus, cmd: Dict[str, Any]) -> float:
    """Publish and return the send time (monotonic), to match ACKs that arrive after it."""
    sent = time.monotonic()
    bus.publish(mc.topics.get_command_topic(cmd["node_id"]), cmd)
    return sent


class Keepalive:
    """Background commands that reset the firmware watchdog without touching the lights."""

    def __init__(self, bus: Bus, node_id: str, period_s: float):
        self.bus, self.node_id, self.period_s = bus, node_id, period_s
        self._stop = threading.Event()
        self._thread = threading.Thread(target=self._run, daemon=True)

    def _run(self) -> None:
        count = 0
        while not self._stop.is_set():
            count += 1
            cmd = {"command_id": f"{KEEPALIVE_PREFIX}{count}", "node_id": self.node_id,
                   "target_phase_id": f"{self.node_id}_KEEPALIVE", "min_green_s": 5.0, "max_green_s": 60.0,
                   "controller": "manual_test"}
            self.bus.publish(mc.topics.get_command_topic(self.node_id), cmd)
            self._stop.wait(self.period_s)

    def __enter__(self) -> "Keepalive":
        self._thread.start()
        return self

    def __exit__(self, *exc) -> None:
        self._stop.set()
        self._thread.join(timeout=2.0)

    def pause(self) -> None:
        self._stop.set()
        self._thread.join(timeout=2.0)


def ok(name: str, detail: str = "") -> StepResult:
    return StepResult(name, "PASS", detail)


def bad(name: str, detail: str) -> StepResult:
    return StepResult(name, "FAIL", detail)


def other_phase(phase_id: str) -> str:
    return phase_id[:-2] + ("EW" if phase_id.endswith("NS") else "NS")


class NodeSuite:
    """Every ACK and timing the firmware must produce for one node, in an order that ends where it began."""

    def __init__(self, bus: Bus, node_id: str, topology: str, timing: mc.Timing):
        self.bus, self.node, self.timing = bus, node_id, timing
        self.ack_timeout = max(2.0, timing.keepalive_s)
        self.tolerance = max(0.3, 0.3 * timing.clearance_s)
        self.phase_a = ""
        self.phase_b = ""
        self.clock_synced = False
        self.node_topology = mc.load_node(topology, node_id)

    def command(self, phase_id: str, **kwargs) -> Dict[str, Any]:
        kwargs.setdefault("min_green_s", self.timing.min_green_s)
        return build_command(self.node, phase_id, **kwargs)

    def expect(self, name: str, cmd: Dict[str, Any], statuses: Sequence[str], reason_has: str = "") -> StepResult:
        sent = send_command(self.bus, cmd)
        ack = self.bus.wait_ack(self.node, cmd["command_id"], statuses, self.ack_timeout, after=sent)
        if ack is None:
            got = [f"{a.status}" for a in self.bus.acks_since(self.node, sent)]
            return bad(name, f"expected {'/'.join(statuses)} within {self.ack_timeout:.0f}s, got {got or 'no ACK'}")
        if reason_has and reason_has.lower() not in ack.reason.lower():
            return bad(name, f"{ack.status} but reason '{ack.reason}' lacks '{reason_has}'")
        return ok(name, f"{ack.status}: {ack.reason}")

    def wait_green(self, timeout_s: float, after: float = 0.0, phase: str = "",
                   status: str = "") -> Optional[Dict[str, Any]]:
        """A health report received after `after` that shows GREEN (optionally this phase / this status)."""
        return self.bus.wait_health(
            self.node, lambda h: h.get("clearance") == "GREEN" and h.get("status") != "SAFE_STOP"
            and (not phase or h.get("current_phase") == phase) and (not status or h.get("status") == status),
            timeout_s, after=after)

    # ---- steps ---------------------------------------------------------------------------------
    def step_online(self) -> StepResult:
        started = time.monotonic()  # only reports received from now on count: a cached one may be stale
        health = self.bus.wait_health(self.node, lambda h: h.get("service") == "esp32_actuator"
                                      and h.get("status") != "OFFLINE", self.timing.health_period_s + 2.0,
                                      after=started)
        if not health:
            return bad("online", f"no health from {self.node} in {self.timing.health_period_s + 2:.0f}s: "
                                 "board powered? Wi-Fi/broker IP in secrets.ini? broker reachable?")
        if health.get("status") == "SAFE_STOP":
            return bad("online", f"{self.node} is in SAFE_STOP (emergency button engaged): release it first")
        health = self.wait_green(self.timing.clearance_s + self.timing.health_period_s + 2.0, after=started)
        if not health:
            return bad("online", "device never reported GREEN")
        self.phase_a = health["current_phase"]
        self.phase_b = other_phase(self.phase_a)
        self.clock_synced = "timestamp_ms" in health
        return ok("online", f"{self.node} {health['status']}, GREEN on {self.phase_a}, "
                            f"RSSI {health.get('wifi_rssi_dbm')} dBm, "
                            f"clock {'synced' if self.clock_synced else 'NOT synced'}")

    def step_invalid_json(self) -> StepResult:
        sent = time.monotonic()
        self.bus.publish(mc.topics.get_command_topic(self.node), b"{not json")
        ack = self.bus.wait_ack(self.node, "unknown", ("REJECTED",), self.ack_timeout, after=sent)
        return (ok("invalid_json", f"REJECTED: {ack.reason}") if ack
                else bad("invalid_json", "malformed JSON got no REJECTED ACK"))

    def step_unknown_phase(self) -> StepResult:
        cmd = self.command(f"{self.node}_PHASE_XX")
        return self.expect("unknown_phase", cmd, ("REJECTED",), "Unknown target_phase_id")

    def step_other_node_ignored(self) -> StepResult:
        other = "J2" if self.node != "J2" else "J1"
        cmd = build_command(other, f"{other}_PHASE_NS")
        sent = send_command_to(self.bus, self.node, cmd)
        self.bus.wait_ack(self.node, cmd["command_id"], FINAL_STATUSES, self.timing.keepalive_s / 2, after=sent)
        stray = [a for a in self.bus.acks_since(self.node, sent) if a.command_id == cmd["command_id"]]
        return (bad("other_node_ignored", f"firmware answered a command for {other}: {stray[0].status}") if stray
                else ok("other_node_ignored", "command addressed to another node got no ACK"))

    def step_expired(self) -> StepResult:
        if not self.clock_synced:
            return StepResult("expired_command", "SKIP", "ESP32 clock not synced (no SNTP): expiry cannot be enforced")
        cmd = self.command(self.phase_a, expires_in_s=-EXPIRED_AGE_MS / 1000)
        return self.expect("expired_command", cmd, ("EXPIRED",), "expired")

    def step_extend(self) -> StepResult:
        return self.expect("extend_active_phase", self.command(self.phase_a), ("APPLIED",), "already active")

    def step_switch(self) -> StepResult:
        """Switch to the other phase; retry once if the green is younger than the minimum green."""
        for attempt in (1, 2):
            cmd = self.command(self.phase_b)
            sent = send_command(self.bus, cmd)
            first = self.bus.wait_ack(self.node, cmd["command_id"], ("ACCEPTED", "REJECTED"),
                                      self.ack_timeout, after=sent)
            if first is None:
                return bad("switch_phase", "no ACCEPTED/REJECTED for the phase change")
            if first.status == "REJECTED" and "min green" in first.reason.lower() and attempt == 1:
                time.sleep(self.timing.min_green_s + 0.3)
                continue
            if first.status != "ACCEPTED":
                return bad("switch_phase", f"{first.status}: {first.reason}")
            applied = self.bus.wait_ack(self.node, cmd["command_id"], FINAL_STATUSES,
                                        self.timing.clearance_s + self.tolerance + 2.0, after=sent)
            if applied is None or applied.status != "APPLIED":
                return bad("switch_phase", f"ACCEPTED but then {applied.status if applied else 'no APPLIED ACK'}")
            took = applied.t - first.t
            if abs(took - self.timing.clearance_s) > self.tolerance:
                return bad("switch_phase", f"ACCEPTED->APPLIED took {took:.2f}s, expected "
                                           f"{self.timing.clearance_s:.1f}s +-{self.tolerance:.1f}")
            self.phase_a, self.phase_b = self.phase_b, self.phase_a
            return ok("switch_phase", f"ACCEPTED -> APPLIED in {took:.2f}s (yellow {self.timing.yellow_s:g}s + "
                                      f"all-red {self.timing.all_red_s:g}s)")
        return bad("switch_phase", "still below the minimum green after waiting")

    def step_min_green(self) -> StepResult:
        return self.expect("min_green_guard", self.command(self.phase_b), ("REJECTED",), "min green")

    def step_clearing(self) -> StepResult:
        """A switch while clearing: the leaving phase answers 'clearing', the target answers 'pending'."""
        time.sleep(self.timing.min_green_s + 0.3)
        go = self.command(self.phase_b)
        sent = send_command(self.bus, go)
        if not self.bus.wait_ack(self.node, go["command_id"], ("ACCEPTED",), self.ack_timeout, after=sent):
            return bad("during_clearance", "switch command was not ACCEPTED")
        leaving = self.expect("during_clearance", self.command(self.phase_a), ("ACCEPTED",), "clearing")
        pending = self.expect("during_clearance", self.command(self.phase_b), ("ACCEPTED",), "pending")
        applied = self.bus.wait_ack(self.node, go["command_id"], FINAL_STATUSES,
                                    self.timing.clearance_s + self.tolerance + 2.0, after=sent)
        if leaving.failed or pending.failed or applied is None or applied.status != "APPLIED":
            return bad("during_clearance", f"leaving: {leaving.detail}; pending: {pending.detail}; "
                                           f"final: {applied.status if applied else 'no APPLIED'}")
        self.phase_a, self.phase_b = self.phase_b, self.phase_a
        return ok("during_clearance", "repeat requests while clearing were ACCEPTED, switch then APPLIED")

    def step_final_health(self) -> StepResult:
        health = self.wait_green(self.timing.health_period_s + 2.0, phase=self.phase_a, status="HEALTHY")
        if not health:
            seen = self.bus.health.get(self.node, {})
            return bad("final_state", f"expected HEALTHY on {self.phase_a}, last health: "
                                      f"{seen.get('status')} {seen.get('current_phase')} {seen.get('clearance')}")
        return ok("final_state", f"HEALTHY, GREEN on {self.phase_a}")

    def run(self, with_watchdog: bool = False) -> List[StepResult]:
        with Keepalive(self.bus, self.node, self.timing.keepalive_s) as keepalive:
            results = [self.step_online()]
            if results[0].failed:
                return results
            for step in (self.step_invalid_json, self.step_unknown_phase, self.step_other_node_ignored,
                         self.step_expired, self.step_extend, self.step_switch, self.step_min_green,
                         self.step_clearing, self.step_final_health):
                results.append(step())
            if with_watchdog:
                keepalive.pause()
                results.append(self.step_watchdog())
        return results

    def step_watchdog(self) -> StepResult:
        """No command for > watchdog: health must show the fallback; the next command must end it."""
        since = time.monotonic()
        health = self.bus.wait_health(self.node, lambda h: h.get("status") == "FALLBACK_AUTONOMOUS",
                                      self.timing.watchdog_s + self.timing.health_period_s + 2.0, after=since)
        if not health:
            return bad("watchdog_fallback", "no FALLBACK_AUTONOMOUS health after the coordinator went silent")
        sent = time.monotonic()
        send_command(self.bus, self.command(self.phase_a))
        back = self.bus.wait_health(self.node, lambda h: h.get("status") == "HEALTHY",
                                    self.timing.health_period_s + 2.0, after=sent)
        return (ok("watchdog_fallback", "fallback after silence, HEALTHY again after the next command") if back
                else bad("watchdog_fallback", "stayed in fallback after a valid command"))


def send_command_to(bus: Bus, topic_node: str, cmd: Dict[str, Any]) -> float:
    """Publish a command on another node's topic (to check the firmware ignores it)."""
    sent = time.monotonic()
    bus.publish(mc.topics.get_command_topic(topic_node), cmd)
    return sent


def print_results(node: str, results: List[StepResult]) -> None:
    print(f"\n== {node}")
    for r in results:
        print(f"  [{r.verdict}] {r.name}: {r.detail}")


# ---- subcommands ------------------------------------------------------------------------------
def cmd_status(args, bus: Bus) -> int:
    time.sleep(args.wait)
    expected = [d.strip() for d in args.expect.split(",") if d.strip()]
    missing = 0
    print(f"{'device':8} {'status':20} {'phase':14} {'clearance':10} {'rssi':>5} {'uptime':>8} {'age':>6}")
    for device in expected:
        data, seen = bus.health.get(device), bus.health_seen.get(device)
        if not data or data.get("status") == "OFFLINE":
            print(f"{device:8} {'MISSING' if not data else 'OFFLINE':20}")
            missing += 1
            continue
        phase = data.get("current_phase") or data.get("mode", "")
        age = time.monotonic() - seen
        print(f"{device:8} {data.get('status', '?'):20} {phase:14} {str(data.get('clearance', '')):10} "
              f"{str(data.get('wifi_rssi_dbm', '')):>5} {str(data.get('uptime_s', '')):>8} {age:5.1f}s")
    return 1 if missing else 0


def cmd_send(args, bus: Bus) -> int:
    phase_id = resolve_phase(args.topology, args.node, args.phase)
    cmd = build_command(args.node, phase_id, args.min_green, args.max_green, expires_in_s=args.expires_in)
    sent = send_command(bus, cmd)
    print(f"sent {json.dumps(cmd)}")
    deadline = time.monotonic() + args.wait
    last = None
    while time.monotonic() < deadline:
        ack = bus.wait_ack(args.node, cmd["command_id"], ("ACCEPTED", "APPLIED", "REJECTED", "EXPIRED", "FAILED"),
                           deadline - time.monotonic(), after=sent if last is None else last.t + 1e-6)
        if ack is None:
            break
        last = ack
        print(f"  +{ack.t - sent:5.2f}s  {ack.status:9} {ack.reason}")
        if ack.status in FINAL_STATUSES:
            return 0 if ack.status == "APPLIED" else 1
    print("  no final ACK: the ESP32 may be offline (try `status`), or it was already switching to that phase "
          "on its own (autonomous fallback after 5 s without a coordinator: such a transition never gets APPLIED)")
    return 1


def cmd_test(args, bus: Bus) -> int:
    timing = mc.Timing().scaled(1.0 / args.speed)
    report: Dict[str, Any] = {"started_ms": mc.now_ms(), "broker": f"{args.mqtt_host}:{args.mqtt_port}", "nodes": {}}
    failed = False
    for node in args.nodes:
        results = NodeSuite(bus, node, args.topology, timing).run(with_watchdog=args.with_watchdog)
        print_results(node, results)
        failed |= any(r.failed for r in results)
        report["nodes"][node] = [r.__dict__ for r in results]
    print("\nRESULT:", "FAIL" if failed else "PASS")
    if args.json:
        with open(args.json, "w", encoding="utf-8") as f:
            json.dump(report, f, indent=2)
        print(f"report written to {args.json}")
    return 1 if failed else 0


def cmd_cycle(args, bus: Bus) -> int:
    period = max(args.period, mc.Timing().min_green_s + mc.Timing().clearance_s + 1.0)
    phases = {n: [resolve_phase(args.topology, n, "NS"), resolve_phase(args.topology, n, "EW")] for n in args.nodes}
    print(f"toggling {', '.join(args.nodes)} every {period:.0f}s (Ctrl+C to stop)")
    step = 0
    try:
        while not args.rounds or step < args.rounds:
            for node in args.nodes:
                cmd = build_command(node, phases[node][(step + 1) % 2])
                send_command(bus, cmd)
                print(f"{time.strftime('%H:%M:%S')} -> {node} {cmd['target_phase_id']}")
            step += 1
            time.sleep(period)
    except KeyboardInterrupt:
        pass
    return 0


def cmd_monitor(args, bus: Bus) -> int:
    bus.echo = lambda topic, payload: print(f"{time.strftime('%H:%M:%S')} {topic} {payload.decode('utf-8', 'replace')}")
    bus.client.subscribe(mc.topics.ALL_EDGEFLOW_SUB)
    try:
        time.sleep(args.duration if args.duration else 10 ** 9)
    except KeyboardInterrupt:
        pass
    return 0


def parse_args(argv: Optional[List[str]] = None) -> argparse.Namespace:
    p = argparse.ArgumentParser(description="Drive and test the ESP32 signal controllers over MQTT")
    p.add_argument("--mqtt-host", default=mc.env_host(), help="broker (env MQTT_HOST, default localhost)")
    p.add_argument("--mqtt-port", type=int, default=mc.env_port())
    p.add_argument("--topology", default="four_intersection_v1")
    sub = p.add_subparsers(dest="command", required=True)

    s = sub.add_parser("status", help="show who is online")
    s.add_argument("--expect", default="J1,J2,vision", help="devices that must be present (default J1,J2,vision)")
    s.add_argument("--wait", type=float, default=6.0, help="seconds to listen (ESP32 health every 5 s)")

    s = sub.add_parser("send", help="send one command and print its ACKs")
    s.add_argument("node")
    s.add_argument("phase", help="NS, EW or a full phase id")
    s.add_argument("--min-green", type=float, default=5.0)
    s.add_argument("--max-green", type=float, default=60.0)
    s.add_argument("--expires-in", type=float, default=None, help="seconds until the command expires")
    s.add_argument("--wait", type=float, default=10.0)

    s = sub.add_parser("test", help="automatic ACK + timing suite")
    s.add_argument("nodes", nargs="+")
    s.add_argument("--json", help="write a JSON report here")
    s.add_argument("--with-watchdog", action="store_true", help="also test the 5 s fallback (may change the phase)")
    s.add_argument("--speed", type=float, default=1.0, help="only for the virtual ESP32 started with --speed")

    s = sub.add_parser("cycle", help="toggle NS/EW on a timer")
    s.add_argument("nodes", nargs="+")
    s.add_argument("--period", type=float, default=12.0)
    s.add_argument("--rounds", type=int, default=0, help="0 = until Ctrl+C")

    s = sub.add_parser("monitor", help="print all edgeflow/v1/# traffic")
    s.add_argument("--duration", type=float, default=0.0)
    return p.parse_args(argv)


COMMANDS = {"status": cmd_status, "send": cmd_send, "test": cmd_test, "cycle": cmd_cycle, "monitor": cmd_monitor}


def main(argv: Optional[List[str]] = None) -> int:
    logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
    args = parse_args(argv)
    try:
        bus = connect_bus(args.mqtt_host, args.mqtt_port)
    except ConnectionError as e:
        print(f"ERROR: {e}", file=sys.stderr)
        return 1
    try:
        return COMMANDS[args.command](args, bus)
    except ValueError as e:
        print(f"ERROR: {e}", file=sys.stderr)
        return 2
    finally:
        bus.client.disconnect()
        bus.client.loop_stop()


if __name__ == "__main__":
    sys.exit(main())
