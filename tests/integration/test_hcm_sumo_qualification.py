"""Real SUMO processes: HCM mapping, detectors and deterministic reset."""
import pytest

from src.simulation.qualify_hcm import (ROOT, Campaign, _sumo_integration_skip_reason,
                                        corrected_spec, demand_case, prepare, read_json, reproduce)


def test_hcm_real_sumo_detectors_and_clean_process_reset(tmp_path):
    output = ROOT / "artifacts/hcm-qualification-v3"
    config = read_json(ROOT / "configs/hcm_qualification_v3.json")
    reason = _sumo_integration_skip_reason(output, config, 2 * config["case_timeout_s"])
    if reason:
        pytest.skip(reason)
    context = prepare(config, output)
    campaign = Campaign(output, config, context, resume=False)
    assert context["audit"]["errors"] == []
    assert len(context["topology"]["nodes"]) == 29
    path, meta = demand_case(context, tmp_path, 500, 71001, "calibration")
    initial = path.read_bytes()
    demand_case(context, tmp_path, 500, 71001, "calibration")
    assert path.read_bytes() == initial and meta["coverage_gate"]
    spec = corrected_spec(context, path, meta, "native_actuated")
    # Real initialization and repeated transitions at every controller, with synthetic arrivals.
    spec["horizon_s"] = 180
    for name in ("first", "reset"):
        case = "verification-detectors-" + name
        directory = output / "cases" / case
        m = campaign.case(case, spec)
        assert m["engineering_pass"], m["engineering_gates"]
        assert sum(m["detector_hits"].values()) > 0
        assert sum(m["signal_seconds"]["network"].values()) == 29*180
        assert m["scheduled"] == m["completed"]+m["running"]+m["uninserted"]
    assert reproduce(output / "cases/verification-detectors-first", output / "cases/verification-detectors-reset")["gate"]
