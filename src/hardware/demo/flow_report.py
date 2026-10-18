#!/usr/bin/env python3
"""
EdgeFlow AI - verdict on a closed-loop run (vision -> graph-control -> ESP32) from its MQTT log.

Record the run on the laptop (any machine that reaches the broker), then judge it:

  mosquitto_sub -h <broker> -v -F '%U %t %p' -t 'edgeflow/v1/#' | tee run.log
  python src/hardware/demo/flow_report.py run.log --nodes J1,J2 --json run_report.json

The same checks apply to a rehearsal with the virtual ESP32 (closed_loop_rehearsal.sh) and to the real
boards. Only reads the log: no broker, no paho. Exit 1 when a check FAILs.
"""

import argparse
import collections
import json
import sys
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any, Dict, Iterable, List, Optional, Tuple

import mqtt_common as mc

MIN_TELEMETRY_HZ = 0.8          # vision publishes 1 message per node per TELEMETRY_PERIOD_S (1 s)
TELEMETRY_GAP_S = 3.0
ACK_TIMEOUT_S = 2.0             # an ACCEPTED/APPLIED/REJECTED arrives within milliseconds on a LAN
SWITCH_TOLERANCE = 0.3          # ACCEPTED -> APPLIED must take yellow + all-red, +-30 %
BLIND_COMMAND_WINDOW_S = 1.0    # graph-control answers a telemetry message within milliseconds
CONTROLLED_LOOKBACK_S = 2.0     # a fallback entry this soon after confident telemetry is a failure
PHASE_GRACE_S = 1.5             # telemetry built just before the new ESP32 phase reached the Pi
MIN_PHASE_AGREEMENT = 0.95
EXPECTED_REJECTS = ("Min green", "Clearance interval", "Phase transition")


@dataclass(frozen=True)
class Msg:
    t: float
    topic: str
    payload: Dict[str, Any]


@dataclass(frozen=True)
class Check:
    name: str
    node: str
    status: str  # PASS | WARN | FAIL
    detail: str


@dataclass
class Report:
    checks: List[Check] = field(default_factory=list)
    nodes: Dict[str, Dict[str, Any]] = field(default_factory=dict)
    vision: Optional[Dict[str, Any]] = None
    span_s: float = 0.0
    messages: int = 0

    @property
    def result(self) -> str:
        return "FAIL" if any(c.status == "FAIL" for c in self.checks) else "PASS"

    def to_dict(self) -> Dict[str, Any]:
        return {"result": self.result, "messages": self.messages, "span_s": round(self.span_s, 1),
                "checks": [asdict(c) for c in self.checks], "nodes": self.nodes, "vision": self.vision}


def parse_log(lines: Iterable[str]) -> List[Msg]:
    """`<unix time> <topic> <json>` lines (mosquitto_sub -F '%U %t %p'), sorted by time; others skipped."""
    msgs = []
    for line in lines:
        parts = line.strip().split(" ", 2)
        if len(parts) < 3:
            continue
        try:
            t, payload = float(parts[0]), json.loads(parts[2])
        except ValueError:
            continue
        if isinstance(payload, dict):
            msgs.append(Msg(t, parts[1], payload))
    return sorted(msgs, key=lambda m: m.t)


def is_blind(telemetry: Dict[str, Any]) -> bool:
    """No approach, or every approach at confidence 0: the camera saw nothing usable in the period."""
    approaches = telemetry.get("approaches") or []
    return not approaches or all(a.get("confidence", 1.0) <= 0.0 for a in approaches)


def _check_telemetry(tel: List[Msg]) -> Tuple[str, str]:
    if len(tel) < 2:
        return "FAIL", (f"{len(tel)} message(s): vision is not reporting this node "
                        "(VISION_NODE_IDS, ROI file, camera, broker address)")
    rate = (len(tel) - 1) / max(tel[-1].t - tel[0].t, 1e-9)
    gaps = sum(1 for a, b in zip(tel, tel[1:]) if b.t - a.t > TELEMETRY_GAP_S)
    detail = f"{len(tel)} msgs, {rate:.2f} Hz, {gaps} gap(s) > {TELEMETRY_GAP_S:.0f} s"
    if rate < MIN_TELEMETRY_HZ:
        return "FAIL", detail + f" (need >= {MIN_TELEMETRY_HZ} Hz)"
    return ("WARN" if gaps else "PASS"), detail


def _check_acks(cmds: List[Msg], acks: List[Msg], log_end: float) -> Tuple[str, str, Dict[str, int]]:
    by_id: Dict[str, List[Msg]] = collections.defaultdict(list)
    for a in acks:
        by_id[a.payload.get("command_id", "")].append(a)
    statuses = collections.Counter(a.payload.get("status") for a in acks)
    unanswered = [c for c in cmds if c.t + ACK_TIMEOUT_S <= log_end
                  and not any(c.t <= a.t <= c.t + ACK_TIMEOUT_S for a in by_id.get(c.payload.get("command_id"), []))]
    bad_rejects = collections.Counter(
        a.payload.get("reason", "")[:50] for a in acks
        if a.payload.get("status") == "REJECTED" and not a.payload.get("reason", "").startswith(EXPECTED_REJECTS)
        and not a.payload.get("reason", "").startswith("Safe-stop"))
    duplicated = sum(1 for items in by_id.values()
                     if any(n > 1 for n in collections.Counter(a.payload.get("status") for a in items).values()))
    detail = f"{dict(statuses)}; unanswered={len(unanswered)}"
    if bad_rejects:
        detail += f"; unexpected REJECTED={dict(bad_rejects)}"
    if duplicated:
        detail += f"; {duplicated} command(s) acknowledged twice (virtual actuator still running? O4)"
    if unanswered or bad_rejects or statuses.get("EXPIRED"):
        return "FAIL", detail + ("; EXPIRED means the device clock disagrees" if statuses.get("EXPIRED") else ""), statuses
    return ("WARN" if duplicated or statuses.get("FAILED") else "PASS"), detail, statuses


def _check_switches(acks: List[Msg], timing: mc.Timing) -> Tuple[str, str]:
    first: Dict[Tuple[str, str], float] = {}
    for a in acks:
        first.setdefault((a.payload.get("command_id", ""), a.payload.get("status", "")), a.t)
    delays = [first[(cid, "APPLIED")] - t for (cid, status), t in first.items()
              if status == "ACCEPTED" and (cid, "APPLIED") in first]
    if not delays:
        return "WARN", "no commanded phase switch in the log: timing not checked"
    lo, hi = timing.clearance_s * (1 - SWITCH_TOLERANCE), timing.clearance_s * (1 + SWITCH_TOLERANCE)
    bad = [round(d, 2) for d in delays if not lo <= d <= hi]
    detail = f"{len(delays)} switch(es), ACCEPTED->APPLIED {min(delays):.2f}-{max(delays):.2f} s (expect {lo:.1f}-{hi:.1f})"
    return ("FAIL", detail + f"; out of range: {bad}") if bad else ("PASS", detail)


def _green_time(health: List[Msg], log_end: float, timing: mc.Timing) -> Tuple[List[Tuple[float, str]], Dict[str, float]]:
    """Green starts (from the health the device sends on every GREEN entry) and green seconds per phase."""
    starts: List[Tuple[float, str]] = []
    for h in health:
        phase = h.payload.get("current_phase")
        if h.payload.get("clearance") == "GREEN" and phase and (not starts or starts[-1][1] != phase):
            starts.append((h.t, phase))
    served: Dict[str, float] = collections.defaultdict(float)
    for i, (t, phase) in enumerate(starts):
        end = starts[i + 1][0] - timing.clearance_s if i + 1 < len(starts) else log_end
        served[phase] += max(0.0, end - t)
    return starts, {p: round(s, 1) for p, s in served.items()}


def _fallback_entries(health: List[Msg]) -> List[float]:
    entries, previous = [], None
    for h in health:
        status = h.payload.get("status")
        if status == "FALLBACK_AUTONOMOUS" and previous != "FALLBACK_AUTONOMOUS":
            entries.append(h.t)
        previous = status
    return entries


def _phase_agreement(health: List[Msg], tel: List[Msg]) -> Tuple[str, str]:
    events = sorted([(h.t, 0, h) for h in health] + [(m.t, 1, m) for m in tel], key=lambda e: (e[0], e[1]))
    phase, changed_at, agree, compared = None, 0.0, 0, 0
    for t, kind, m in events:
        if kind == 0:
            new = m.payload.get("current_phase")
            if new and new != phase:
                phase, changed_at = new, t
        elif phase and t - changed_at >= PHASE_GRACE_S:
            compared += 1
            agree += m.payload.get("current_phase_id") == phase
    if not compared:
        return "WARN", "no ESP32 health with a phase for this node: cannot check"
    detail = f"telemetry current_phase_id == ESP32 phase in {agree}/{compared}"
    return ("PASS" if agree >= MIN_PHASE_AGREEMENT * compared else "FAIL"), detail


def _analyze_node(msgs: List[Msg], node: str, log_start: float, log_end: float, timing: mc.Timing):
    topics = mc.topics
    tel = [m for m in msgs if m.topic == topics.get_telemetry_topic(node)]
    cmds = [m for m in msgs if m.topic == topics.get_command_topic(node)]
    acks = [m for m in msgs if m.topic == topics.get_ack_topic(node)]
    health = [m for m in msgs if m.topic == topics.get_health_topic(node)]
    confident = [m for m in tel if not is_blind(m.payload)]
    blind = [m for m in tel if is_blind(m.payload)]
    checks = []

    def add(name: str, status: str, detail: str) -> None:
        checks.append(Check(name, node, status, detail))

    add("telemetry", *_check_telemetry(tel))
    if confident and not cmds:
        add("commands", "FAIL", f"0 commands for {len(confident)} confident telemetry: is graph-control running "
                                "with the same EDGEFLOW_TOPOLOGY and broker?")
    else:
        add("commands", "PASS", f"{len(cmds)} commands for {len(confident)} confident telemetry")
    ack_status, ack_detail, _ = _check_acks(cmds, acks, log_end)
    add("acks", ack_status, ack_detail)
    add("switch_timing", *_check_switches(acks, timing))

    entries = _fallback_entries(health)
    controlled = [t for t in entries if any(t - CONTROLLED_LOOKBACK_S <= m.t <= t for m in confident)]
    add("fallback", "FAIL" if controlled else "PASS",
        f"{len(entries)} fallback entr(y/ies)" + (f", {len(controlled)} while confident telemetry was flowing "
                                                  "(commands stopped reaching the device)" if controlled else ""))

    answered_blind = sum(1 for m in blind if any(m.t < c.t <= m.t + BLIND_COMMAND_WINDOW_S for c in cmds))
    add("blind_commands", "FAIL" if answered_blind else "PASS",
        f"{answered_blind} of {len(blind)} blind telemetry (camera lost) answered with a command"
        + ("; graph-control decides on zeros and the ESP32 fallback never engages" if answered_blind else ""))
    add("phase_agreement", *_phase_agreement(health, tel))

    alarms = [(round(h.t - log_start, 1), h.payload.get("status")) for h in health
              if h.payload.get("status") in ("SAFE_STOP", "OFFLINE")]
    add("device_status", "WARN" if alarms else "PASS", f"SAFE_STOP/OFFLINE at {alarms}" if alarms else "no SAFE_STOP/OFFLINE")

    starts, served = _green_time(health, log_end, timing)
    summary = {"telemetry": len(tel), "blind_telemetry": len(blind), "commands": len(cmds),
               "command_targets": dict(collections.Counter(c.payload.get("target_phase_id") for c in cmds)),
               "ack_statuses": dict(collections.Counter(a.payload.get("status") for a in acks)),
               "green_switches": len(starts), "green_s": served,
               "green_starts": [(round(t - log_start, 1), p) for t, p in starts],
               "fallback_entries": [round(t - log_start, 2) for t in entries]}
    return summary, checks


def analyze(msgs: List[Msg], nodes: List[str], timing: Optional[mc.Timing] = None) -> Report:
    timing = timing or mc.Timing()
    report = Report(messages=len(msgs))
    if not msgs:
        report.checks.append(Check("log", "-", "FAIL", "no timestamped message: record with -F '%U %t %p'"))
        return report
    start, end = msgs[0].t, msgs[-1].t
    report.span_s = end - start
    for node in nodes:
        summary, checks = _analyze_node(msgs, node, start, end, timing)
        report.nodes[node] = summary
        report.checks.extend(checks)
    vision = [m.payload for m in msgs if m.topic == mc.topics.get_health_topic(mc.HEALTH_VISION)]
    if vision:
        running = [v for v in vision if v.get("status") != "OFFLINE"] or vision
        report.vision = {k: running[-1].get(k) for k in ("status", "mode", "phase_source", "active_nodes")}
        report.vision["final_status"] = vision[-1].get("status")
    return report


def print_report(report: Report, name: str) -> None:
    print(f"EdgeFlow closed-loop report: {name} ({report.messages} messages, {report.span_s:.1f} s)")
    for c in report.checks:
        print(f"[{c.status}] {c.node:3s} {c.name:16s} {c.detail}")
    for node, s in report.nodes.items():
        print(f"{node}: green s per phase {s['green_s']} ({s['green_switches']} green starts), "
              f"fallback entries at {s['fallback_entries']} s")
    if report.vision:
        print(f"vision health (last): {report.vision}")
    print(f"RESULT: {report.result}")


def main(argv: Optional[List[str]] = None) -> int:
    p = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    p.add_argument("log", help="mosquitto_sub -v -F '%%U %%t %%p' -t 'edgeflow/v1/#' output")
    p.add_argument("--nodes", default="J1,J2", help="nodes that must be under closed-loop control")
    p.add_argument("--json", help="write the report here (evidence for the report)")
    args = p.parse_args(argv)
    with open(args.log, encoding="utf-8", errors="replace") as f:
        report = analyze(parse_log(f), [n.strip() for n in args.nodes.split(",") if n.strip()])
    print_report(report, args.log)
    if args.json:
        Path(args.json).write_text(json.dumps(report.to_dict(), indent=2, ensure_ascii=False))
    return 1 if report.result == "FAIL" else 0


if __name__ == "__main__":
    sys.exit(main())
