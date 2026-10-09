"""
EdgeFlow AI - Verify ESP32 signal output traces (evidence for the "Signal behavior" gate).

The firmware prints one line per output change:
    TRACE,<millis>,<node>,<ns>,<ew>,<label>     ns/ew in {R, Y, G, -}
    label in {GREEN, YELLOW, ALL_RED, SAFE_STOP, CONFLICT_GUARD}

Capture:  pio device monitor -e J1 | tee trace_J1.log
Check:    python src/hardware/verify_trace.py trace_J1.log --json trace_J1_report.json

Checks per node: no conflicting greens; GREEN only after an ALL_RED of at least 2 s;
GREEN -> YELLOW (same head) -> ALL_RED with yellow >= 3 s; green >= the device minimum.
Intervals cut short by the safe-stop button are reported, not counted as violations.
Exit code 1 when any violation is found.
"""

import argparse
import json
import re
import sys
from dataclasses import dataclass, field
from pathlib import Path
from typing import Dict, Iterable, List, Optional

TRACE_RE = re.compile(r"TRACE,(\d+),([A-Za-z0-9_]+),([RYG-]),([RYG-]),([A-Z_]+)")


@dataclass(frozen=True)
class TraceEvent:
    t_ms: int
    node: str
    ns: str
    ew: str
    label: str


@dataclass
class NodeReport:
    node: str
    events: int = 0
    duration_s: float = 0.0
    green_count: int = 0
    safe_stop_episodes: int = 0
    yellow_ms: List[int] = field(default_factory=list)
    all_red_ms: List[int] = field(default_factory=list)
    green_ms: List[int] = field(default_factory=list)
    violations: List[str] = field(default_factory=list)

    def summary(self) -> Dict[str, object]:
        def span(values: List[int]) -> Optional[List[int]]:
            return [min(values), max(values)] if values else None
        return {
            "node": self.node,
            "events": self.events,
            "duration_s": round(self.duration_s, 1),
            "phase_switches": self.green_count,
            "safe_stop_episodes": self.safe_stop_episodes,
            "yellow_ms_min_max": span(self.yellow_ms),
            "all_red_ms_min_max": span(self.all_red_ms),
            "green_ms_min_max": span(self.green_ms),
            "violations": self.violations,
            "passed": not self.violations,
        }


def parse_trace(lines: Iterable[str]) -> List[TraceEvent]:
    events = []
    for line in lines:
        match = TRACE_RE.search(line)
        if match:
            t_ms, node, ns, ew, label = match.groups()
            events.append(TraceEvent(int(t_ms), node, ns, ew, label))
    return events


def _green_head(event: TraceEvent) -> Optional[str]:
    return "ns" if event.ns == "G" else ("ew" if event.ew == "G" else None)


def _yellow_head(event: TraceEvent) -> Optional[str]:
    return "ns" if event.ns == "Y" else ("ew" if event.ew == "Y" else None)


def check_node(events: List[TraceEvent], yellow_ms: int = 3000, all_red_ms: int = 2000,
               min_green_ms: int = 5000, tolerance_ms: int = 50) -> NodeReport:
    report = NodeReport(node=events[0].node if events else "?", events=len(events))
    if not events:
        report.violations.append("no TRACE lines found")
        return report
    report.duration_s = (events[-1].t_ms - events[0].t_ms) / 1000.0

    for index, event in enumerate(events):
        where = f"t={event.t_ms}ms"
        prev = events[index - 1] if index > 0 else None
        nxt = events[index + 1] if index + 1 < len(events) else None
        duration = (nxt.t_ms - event.t_ms) if nxt else None

        if (event.ns == "G" and event.ew == "G") or event.label == "CONFLICT_GUARD":
            report.violations.append(f"{where}: conflicting green requested/shown")
            continue

        if event.label == "SAFE_STOP":
            if prev is None or prev.label != "SAFE_STOP":
                report.safe_stop_episodes += 1
            if nxt and nxt.label not in ("SAFE_STOP", "ALL_RED"):
                report.violations.append(f"{where}: safe-stop released into {nxt.label} without ALL_RED")
            continue

        if event.label == "GREEN":
            report.green_count += 1
            if prev is not None and prev.label != "ALL_RED":
                report.violations.append(f"{where}: GREEN entered from {prev.label}, not from ALL_RED")
            if nxt and nxt.label == "ALL_RED":
                report.violations.append(f"{where}: GREEN went to ALL_RED without YELLOW")
            if nxt and nxt.label == "YELLOW":
                report.green_ms.append(duration)
                if duration < min_green_ms - tolerance_ms:
                    report.violations.append(f"{where}: green {duration}ms < minimum {min_green_ms}ms")
                if _yellow_head(nxt) != _green_head(event):
                    report.violations.append(f"t={nxt.t_ms}ms: YELLOW on a head that was not GREEN")

        elif event.label == "YELLOW":
            if nxt and nxt.label not in ("ALL_RED", "SAFE_STOP"):
                report.violations.append(f"{where}: YELLOW followed by {nxt.label}, not ALL_RED")
            if nxt and nxt.label == "ALL_RED":
                report.yellow_ms.append(duration)
                if duration < yellow_ms - tolerance_ms:
                    report.violations.append(f"{where}: yellow {duration}ms < {yellow_ms}ms")

        elif event.label == "ALL_RED":
            if nxt and nxt.label == "GREEN":
                report.all_red_ms.append(duration)
                if duration < all_red_ms - tolerance_ms:
                    report.violations.append(f"{where}: all-red {duration}ms < {all_red_ms}ms")

    return report


def check_trace(events: List[TraceEvent], **limits) -> List[NodeReport]:
    by_node: Dict[str, List[TraceEvent]] = {}
    for event in events:
        by_node.setdefault(event.node, []).append(event)
    if not by_node:
        return [check_node([], **limits)]
    return [check_node(node_events, **limits) for node_events in by_node.values()]


def main(argv: Optional[List[str]] = None) -> int:
    parser = argparse.ArgumentParser(description="Verify ESP32 TRACE output timing")
    parser.add_argument("logfile", type=Path, help="serial log containing TRACE lines")
    parser.add_argument("--yellow-ms", type=int, default=3000)
    parser.add_argument("--all-red-ms", type=int, default=2000)
    parser.add_argument("--min-green-ms", type=int, default=5000)
    parser.add_argument("--tolerance-ms", type=int, default=50)
    parser.add_argument("--json", type=Path, help="write the report as JSON (run artifact)")
    args = parser.parse_args(argv)

    events = parse_trace(args.logfile.read_text(encoding="utf-8", errors="replace").splitlines())
    reports = check_trace(events, yellow_ms=args.yellow_ms, all_red_ms=args.all_red_ms,
                          min_green_ms=args.min_green_ms, tolerance_ms=args.tolerance_ms)
    summaries = [report.summary() for report in reports]
    for summary in summaries:
        status = "PASS" if summary["passed"] else "FAIL"
        print(f"[{status}] node {summary['node']}: {summary['events']} events over {summary['duration_s']}s, "
              f"{summary['phase_switches']} greens, yellow {summary['yellow_ms_min_max']} ms, "
              f"all-red {summary['all_red_ms_min_max']} ms, green {summary['green_ms_min_max']} ms, "
              f"safe-stop x{summary['safe_stop_episodes']}")
        for violation in summary["violations"]:
            print(f"    VIOLATION {violation}")
    if args.json:
        args.json.write_text(json.dumps({"logfile": str(args.logfile), "nodes": summaries}, indent=2) + "\n",
                             encoding="utf-8")
    return 0 if all(summary["passed"] for summary in summaries) else 1


if __name__ == "__main__":
    sys.exit(main())
