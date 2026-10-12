"""Real SUMO regression: 12 m buses queue toward both adjacent controllers."""
import pytest

from src.simulation.hcm_repair import adjacent_red_probe
from src.simulation.qualify_hcm import ROOT, Campaign, _sumo_integration_skip_reason, prepare, read_json


def test_both_directions_queue_toward_red_and_clear_without_collision():
    output = ROOT / "artifacts/hcm-qualification-v3"
    config = read_json(ROOT / "configs/hcm_qualification_v3.json")
    reason = _sumo_integration_skip_reason(output, config, 2 * config["case_timeout_s"])
    if reason:
        pytest.skip(reason)
    context = prepare(config, output)
    campaign = Campaign(output, config, context, resume=True)
    result = adjacent_red_probe(campaign, context)
    assert result["pass"], result
    assert result["metrics"]["scheduled"] == result["metrics"]["completed"] == 48
