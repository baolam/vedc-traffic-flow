"""Signal-trace verifier: accepts the firmware's clearance sequence, flags unsafe outputs."""
import json
import sys
from pathlib import Path

ROOT_DIR = Path(__file__).resolve().parents[2]
HARDWARE_DIR = ROOT_DIR / "src" / "hardware"
if str(HARDWARE_DIR) not in sys.path:
    sys.path.insert(0, str(HARDWARE_DIR))

from verify_trace import check_trace, main, parse_trace  # noqa: E402


def trace(*rows, node="J1"):
    """rows: (t_ms, ns, ew, label) -> serial log lines with unrelated noise mixed in."""
    lines = ["EdgeFlow AI - ESP32 Signal Actuator Node [J1]", "TRACE,millis,node,ns,ew,label"]
    for t_ms, ns, ew, label in rows:
        lines.append(f"TRACE,{t_ms},{node},{ns},{ew},{label}")
        lines.append("[ACK] ACCEPTED t1 (Clearance initiated)")
    return lines


GOOD_CYCLE = [
    (500, "R", "R", "ALL_RED"),     # boot state
    (2500, "G", "R", "GREEN"),
    (17500, "Y", "R", "YELLOW"),
    (20500, "R", "R", "ALL_RED"),
    (22500, "R", "G", "GREEN"),
    (37500, "R", "Y", "YELLOW"),
    (40500, "R", "R", "ALL_RED"),
    (42500, "G", "R", "GREEN"),
]


def single_report(rows):
    reports = check_trace(parse_trace(trace(*rows)))
    assert len(reports) == 1
    return reports[0]


def test_firmware_clearance_sequence_passes():
    report = single_report(GOOD_CYCLE)
    assert report.violations == []
    assert report.green_count == 3
    assert report.yellow_ms == [3000, 3000]
    assert report.all_red_ms == [2000, 2000, 2000]
    assert report.green_ms == [15000, 15000]


def test_header_and_noise_lines_are_ignored():
    events = parse_trace(trace(*GOOD_CYCLE))
    assert len(events) == len(GOOD_CYCLE)
    assert events[0].label == "ALL_RED"


def test_conflicting_green_is_a_violation():
    report = single_report(GOOD_CYCLE[:2] + [(3000, "G", "G", "GREEN")])
    assert any("conflicting green" in v for v in report.violations)


def test_conflict_guard_label_is_a_violation():
    report = single_report(GOOD_CYCLE[:2] + [(3000, "R", "R", "CONFLICT_GUARD")])
    assert any("conflicting green" in v for v in report.violations)


def test_short_yellow_is_a_violation():
    rows = list(GOOD_CYCLE)
    rows[3] = (19000, "R", "R", "ALL_RED")  # yellow lasted 1.5 s
    report = single_report(rows)
    assert any("yellow 1500ms" in v for v in report.violations)


def test_short_all_red_is_a_violation():
    rows = list(GOOD_CYCLE)
    rows[4] = (21000, "R", "G", "GREEN")  # all-red lasted 0.5 s
    report = single_report(rows)
    assert any("all-red 500ms" in v for v in report.violations)


def test_green_straight_to_red_skips_yellow():
    report = single_report([(0, "R", "R", "ALL_RED"), (2000, "G", "R", "GREEN"), (9000, "R", "R", "ALL_RED"),
                            (11000, "R", "G", "GREEN")])
    assert any("without YELLOW" in v for v in report.violations)


def test_green_not_from_all_red_is_a_violation():
    report = single_report([(0, "R", "R", "ALL_RED"), (2000, "G", "R", "GREEN"), (9000, "Y", "R", "YELLOW"),
                            (12000, "R", "G", "GREEN")])
    assert any("not from ALL_RED" in v for v in report.violations)


def test_yellow_on_wrong_head_is_a_violation():
    report = single_report([(0, "R", "R", "ALL_RED"), (2000, "G", "R", "GREEN"), (9000, "R", "Y", "YELLOW"),
                            (12000, "R", "R", "ALL_RED"), (14000, "R", "G", "GREEN")])
    assert any("not GREEN" in v for v in report.violations)


def test_short_green_is_a_violation():
    report = single_report([(0, "R", "R", "ALL_RED"), (2000, "G", "R", "GREEN"), (4000, "Y", "R", "YELLOW"),
                            (7000, "R", "R", "ALL_RED"), (9000, "R", "G", "GREEN")])
    assert any("green 2000ms" in v for v in report.violations)


def test_safe_stop_interrupting_yellow_then_release_via_all_red_passes():
    rows = [(0, "R", "R", "ALL_RED"), (2000, "G", "R", "GREEN"), (17000, "Y", "R", "YELLOW"),
            (18000, "Y", "Y", "SAFE_STOP"), (18500, "-", "-", "SAFE_STOP"), (19000, "Y", "Y", "SAFE_STOP"),
            (25000, "R", "R", "ALL_RED"), (27000, "G", "R", "GREEN")]
    report = single_report(rows)
    assert report.violations == []
    assert report.safe_stop_episodes == 1
    assert report.yellow_ms == []  # interrupted yellow is not counted as a short yellow


def test_safe_stop_released_straight_to_green_is_a_violation():
    rows = [(0, "R", "R", "ALL_RED"), (2000, "G", "R", "GREEN"), (9000, "Y", "Y", "SAFE_STOP"),
            (12000, "G", "R", "GREEN")]
    report = single_report(rows)
    assert any("without ALL_RED" in v for v in report.violations)


def test_nodes_are_checked_separately():
    lines = trace(*GOOD_CYCLE, node="J1") + trace(*GOOD_CYCLE, node="J2")
    reports = check_trace(parse_trace(lines))
    assert sorted(r.node for r in reports) == ["J1", "J2"]
    assert all(not r.violations for r in reports)


def test_empty_log_fails():
    reports = check_trace(parse_trace(["boot", "no trace here"]))
    assert reports[0].violations == ["no TRACE lines found"]


def test_cli_writes_json_and_exit_code(tmp_path):
    good = tmp_path / "good.log"
    good.write_text("\n".join(trace(*GOOD_CYCLE)), encoding="utf-8")
    report_path = tmp_path / "report.json"
    assert main([str(good), "--json", str(report_path)]) == 0
    assert json.loads(report_path.read_text())["nodes"][0]["passed"] is True

    bad = tmp_path / "bad.log"
    bad.write_text("\n".join(trace(*GOOD_CYCLE[:2], (3000, "G", "G", "GREEN"))), encoding="utf-8")
    assert main([str(bad)]) == 1
