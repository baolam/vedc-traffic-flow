"""Numerical protocol fixtures independent of the research controller runtime."""
import json
from pathlib import Path
import xml.etree.ElementTree as ET

import pytest

from contracts.hcm_qualification_v3 import PROTOCOL
from src.simulation.hcm_case import (bottleneck_speed_response, percentile95,
                                     reconcile_signals, vehicle_accounting)
from src.simulation.hcm_demand import allocate_counts, direction
from src.simulation.hcm_network import derived_phases, load_network, signal_kind, signal_paths, valid_route
from src.simulation.qualify_hcm import (Campaign, atomic_json, case_identity, choose_loads,
                                        compare_numeric, current_case, digest, file_hash,
                                        main, publish_directory, require_campaign_budget,
                                        valid_cache)


@pytest.fixture
def lane_network(tmp_path):
    path = tmp_path / "fixture.net.xml"
    path.write_text('''<net version="1.20">
      <edge id="a" from="n0" to="n1"><lane id="a_0" index="0" speed="10" length="40" allow="passenger bus motorcycle" shape="0,0 40,0"/></edge>
      <edge id="b" from="n1" to="n2"><lane id="b_0" index="0" speed="10" length="30" allow="bus" shape="40,0 70,0"/></edge>
      <edge id="c" from="n1" to="n3"><lane id="c_0" index="0" speed="10" length="20" allow="passenger bus motorcycle" shape="40,0 60,0"/></edge>
      <edge id="d" from="n3" to="n4"><lane id="d_0" index="0" speed="10" length="30" allow="passenger bus motorcycle" shape="60,0 90,0"/></edge>
      <edge id="e" from="n4" to="n5"><lane id="e_0" index="0" speed="10" length="50" allow="passenger bus motorcycle" shape="90,0 140,0"/></edge>
      <edge id="u" from="n1" to="n0"><lane id="u_0" index="0" speed="10" length="40" allow="passenger bus motorcycle" shape="40,0 0,0"/></edge>
      <junction id="n0" type="priority" x="0" y="0" incLanes="u_0"/>
      <junction id="n1" type="traffic_light" x="40" y="0" incLanes="a_0"/>
      <junction id="n2" type="priority" x="70" y="0" incLanes="b_0"/>
      <junction id="n3" type="priority" x="60" y="0" incLanes="c_0"/>
      <junction id="n4" type="traffic_light" x="90" y="0" incLanes="d_0"/>
      <junction id="n5" type="priority" x="140" y="0" incLanes="e_0"/>
      <connection from="a" to="b" fromLane="0" toLane="0" dir="r" tl="T1" linkIndex="0"/>
      <connection from="a" to="c" fromLane="0" toLane="0" dir="s" tl="T1" linkIndex="1"/>
      <connection from="a" to="u" fromLane="0" toLane="0" dir="t" tl="T1" linkIndex="2"/>
      <connection from="c" to="d" fromLane="0" toLane="0" dir="s"/>
      <connection from="d" to="e" fromLane="0" toLane="0" dir="s" tl="T2" linkIndex="0"/>
    </net>''', encoding="utf-8")
    tree = ET.parse(path)
    for node in tree.getroot().findall("junction"):
        node.set("intLanes", "")
        node.set("shape", "")
    for connection in tree.getroot().findall("connection"):
        connection.set("state", "M")
    tree.write(path, encoding="utf-8")
    return load_network(path)


def test_mixed_green_yellow_is_not_service_and_clearance_preserves_permissive():
    logic = ET.fromstring('<tlLogic id="T"><phase duration="4" state="Ggrr"/><phase duration="3" state="yGrr"/><phase duration="80" state="rrgG"/></tlLogic>')
    phases = derived_phases(logic)
    assert signal_kind("yGrr") == "yellow"
    assert [p["state"] for p in phases] == ["Ggrr", "yyrr", "rrrr", "rrgG", "rryy", "rrrr"]
    assert [p["duration"] for p in phases] == [10, 3, 2, 60, 3, 2]
    assert [p["source_index"] for p in phases[::3]] == [0, 2]


def test_class_specific_permissions_uturn_and_repeated_edges(lane_network):
    assert valid_route(lane_network, ["a", "b"], "bus")
    assert not valid_route(lane_network, ["a", "b"], "passenger")
    assert valid_route(lane_network, ["a", "c", "d", "e"], "motorcycle")
    assert not valid_route(lane_network, ["a", "u"], "passenger")
    assert not valid_route(lane_network, ["a", "c", "a"], "passenger")
    assert not valid_route(lane_network, ["a", "missing"], "passenger")


def test_graph_paths_cross_unsignalized_junction(lane_network):
    paths = signal_paths(lane_network, {"T1": "J01", "T2": "J02"})
    assert len(paths) == 1
    assert paths[0]["from_node"] == "J01" and paths[0]["to_node"] == "J02"
    assert paths[0]["sumo_road_path"] == ["c", "d"]
    assert paths[0]["length_m"] == 50


def test_exact_vehicle_and_signal_accounting_detects_silent_removal():
    scheduled = {"a", "b", "c", "d"}
    m = vehicle_accounting(scheduled, {"a", "b", "c"}, {"a", "b"}, {"c"})
    assert (m["scheduled"], m["completed"], m["running"], m["uninserted"]) == (4, 2, 1, 1)
    assert m["accounting_gate"]
    assert not vehicle_accounting(scheduled, {"a", "b", "c"}, {"a", "b"}, set())["accounting_gate"]
    counts = {"J01": {"green": 10, "yellow": 3, "all_red": 2}, "J02": {"green": 8, "yellow": 3, "all_red": 4}}
    reconciled = reconcile_signals(counts, 15)
    assert reconciled["network"] == {"green": 18, "yellow": 6, "all_red": 6}
    assert reconciled["gate"]
    assert not reconcile_signals(counts, 16)["gate"]


def test_exact_type_proportions_direction_and_percentile():
    assert allocate_counts(7, {"car": 1, "motorcycle": 2}) == {"car": 2, "motorcycle": 5}
    assert sum(allocate_counts(501, {"car": 156, "motorcycle": 642, "bus": 37}).values()) == 501
    corridor = {"forward_movements": [["a", "b"]], "reverse_movements": [["b", "a"]]}
    assert direction(["a", "b", "c"], corridor) == "forward"
    assert direction(["b", "a"], corridor) == "reverse"
    assert percentile95([0, 10, 20]) == 19


def test_bottleneck_response_compares_occupied_vehicle_speed_to_control():
    control = [[1199, 0, 0, 0], [1201, 0, 2, 10], [1800, 0, 1, 8]]
    treatment = [[1201, 0, 2, 6], [1800, 0, 1, 4]]
    response = bottleneck_speed_response(control, treatment, 0.20)
    assert response["relative_speed_reduction"] == pytest.approx(3/7)
    assert response["gate"]
    assert not bottleneck_speed_response([], [], 0.20)["gate"]


def test_resume_requires_complete_matching_hashes_and_rejects_corruption(tmp_path):
    atomic_json(tmp_path / "metrics.json", {"scheduled": 1})
    fingerprint = digest({"network": "v1", "demand": "d1", "protocol": PROTOCOL, "implementation": "i1", "environment": "e1", "controller": "c1"})
    assert not valid_cache(tmp_path, fingerprint)
    atomic_json(tmp_path / "complete.json", {"fingerprint": fingerprint, "files": {"metrics.json": file_hash(tmp_path / "metrics.json")}})
    assert valid_cache(tmp_path, fingerprint)
    for field in ("network", "demand", "protocol", "implementation", "environment", "controller"):
        assert not valid_cache(tmp_path, digest({field: "changed"}))
    atomic_json(tmp_path / "metrics.json", {"scheduled": 2})
    assert not valid_cache(tmp_path, fingerprint)


def test_exhausted_or_missing_budget_leaves_campaign_outputs_untouched(tmp_path):
    config = {"campaign_budget_s": 100, "case_timeout_s": 30}
    missing = tmp_path / "missing-output"
    with pytest.raises(FileNotFoundError, match="refusing to reset"):
        require_campaign_budget(missing, config, "all")
    assert not missing.exists()

    output = tmp_path / "campaign-output"
    output.mkdir()
    atomic_json(output / "campaign.json", {"simulation_wall_s": 100, "attempts": []})
    case = output / "cases/example"
    case.mkdir(parents=True)
    (case / "historical.txt").write_text("preserve")
    partial = output / "cases/example.partial"
    partial.mkdir()
    (partial / "worker.log").write_text("preserve")
    inputs = {key: tmp_path / f"{key}.xml" for key in ("network", "demand", "program", "topology")}
    for key, path in inputs.items():
        path.write_text(key)
    campaign = object.__new__(Campaign)
    campaign.output, campaign.config = output, config
    campaign.context, campaign.resume = {"identity": {"protocol": "test"}}, False
    campaign.ledger = {"simulation_wall_s": 100, "attempts": []}
    with pytest.raises(TimeoutError, match="budget exhausted"):
        campaign.case("example", {key: str(path) for key, path in inputs.items()})
    assert (case / "historical.txt").read_text() == "preserve"
    assert (partial / "worker.log").read_text() == "preserve"
    assert json.loads((output / "campaign.json").read_text())["simulation_wall_s"] == 100


def test_simulation_cli_refuses_missing_ledger_before_creating_output(tmp_path, capsys):
    config = tmp_path / "qualification.json"
    config.write_text('{"workers": 1, "case_timeout_s": 300, "campaign_budget_s": 7200}')
    output = tmp_path / "new-campaign"
    with pytest.raises(SystemExit) as raised:
        main(["--config", str(config), "--output", str(output), "--stage", "repair"])
    assert raised.value.code == 2
    assert "refusing to reset" in capsys.readouterr().err
    assert not output.exists()


def test_bottleneck_counterfactual_hash_invalidates_case_identity(tmp_path):
    files = {key: tmp_path / f"{key}.xml" for key in ("network", "demand", "program", "topology", "control")}
    for key, path in files.items():
        path.write_text(key, encoding="utf-8")
    spec = {key: str(files[key]) for key in ("network", "demand", "program", "topology")}
    spec["bottleneck_control_trace"] = str(files["control"])
    first = case_identity(spec, {"protocol": "hcm_qualification_v2"})
    files["control"].write_text("changed", encoding="utf-8")
    second = case_identity(spec, {"protocol": "hcm_qualification_v2"})
    assert first["files"]["bottleneck_control_trace"] != second["files"]["bottleneck_control_trace"]


def test_load_selection_does_not_relax_gates():
    def metrics(completed, waiting):
        return {"engineering_pass": True, "completion_fraction": completed, "uninserted_fraction": 0,
                "mean_stopped_wait_s_per_scheduled": waiting}
    calibration = {str(load): {f"{c}-{s}": metrics(.94, 20) for c in PROTOCOL["controllers"] for s in PROTOCOL["calibration_seeds"]}
                   for load in PROTOCOL["loads_vph"]}
    assert not choose_loads(calibration)["gate"]
    calibration["500"] = {k: metrics(1, 2) for k in calibration["500"]}
    calibration["2000"] = {k: metrics(.97, 20) for k in calibration["2000"]}
    selected = choose_loads(calibration)
    assert selected["light_vph"] == 500 and selected["primary_vph"] == 2000 and selected["gate"]


def test_numeric_repeat_tolerance():
    assert compare_numeric({"wait": [1.0]}, {"wait": [1.0+1e-8]})
    assert not compare_numeric({"wait": [1.0]}, {"wait": [1.0+1e-5]})


def test_calibration_selects_numeric_gates_separately_from_qualification_engineering():
    metrics = {"engineering_pass": False, "completion_fraction": 1, "uninserted_fraction": 0,
               "mean_stopped_wait_s_per_scheduled": 20}
    calibration = {str(load): {f"{c}-{s}": {**metrics, "completion_fraction": 1 if load == 500 else .9}
                   for c in PROTOCOL["controllers"] for s in PROTOCOL["calibration_seeds"]}
                   for load in PROTOCOL["loads_vph"]}
    selected = choose_loads(calibration)
    assert selected["gate"] and selected["light_vph"] == selected["primary_vph"] == 500


def test_atomic_case_publication_retries_transient_windows_lock(monkeypatch, tmp_path):
    source, target = tmp_path / "case.partial", tmp_path / "case"
    source.mkdir()
    (source / "metrics.json").write_text("{}")
    original = Path.rename
    calls = []

    def rename(path, destination):
        calls.append(path)
        if len(calls) == 1:
            raise PermissionError("temporary indexer lock")
        return original(path, destination)

    monkeypatch.setattr(Path, "rename", rename)
    monkeypatch.setattr("src.simulation.qualify_hcm.time.sleep", lambda _: None)
    publish_directory(source, target)
    assert len(calls) == 2 and (target / "metrics.json").exists()


def test_reporting_revalidates_frozen_inputs_not_only_raw_outputs(tmp_path):
    case = tmp_path / "case"
    case.mkdir()
    paths = {key: tmp_path / f"{key}.xml" for key in ("network", "demand", "program", "topology")}
    for path in paths.values():
        path.write_text("original")
    spec = {key: str(path) for key, path in paths.items()}
    identity = {"environment": "original", "implementation": "original", "protocol": PROTOCOL}
    sealed = case_identity(spec, identity)
    atomic_json(case / "metrics.json", {})
    atomic_json(case / "complete.json", {"fingerprint": digest(sealed), "identity": sealed,
                "files": {"metrics.json": file_hash(case / "metrics.json")}})
    assert current_case(case, identity)
    assert not current_case(case, {**identity, "implementation": "changed"})
    for path in paths.values():
        path.write_text("changed")
        assert not current_case(case, identity)
        path.write_text("original")
