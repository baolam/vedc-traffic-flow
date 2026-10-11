"""Repair invariants and complete vehicle footprints, independent of SUMO runs."""
import copy
import json
from pathlib import Path
import xml.etree.ElementTree as ET

import pytest

from contracts.hcm_qualification_v3 import PROTOCOL, TOPOLOGY_ID, REPAIR_ORDER
from src.simulation import hcm_repair
from src.simulation.hcm_repair import (connection_mapping, footprint, internal_owner,
                                       polygons_overlap, validate_changes)
from src.simulation.qualify_hcm import ROOT, case_identity, digest, implementation_hash


@pytest.fixture
def source():
    return ET.parse(ROOT / "networks/hcm_neighborhood_benchmark_v2/network.net.xml").getroot()


def test_reference_specs_work_without_temporary_workspaces():
    reference = hcm_repair.V2_REFERENCE
    records = hcm_repair.read(hcm_repair.reference_file("qualification_cases.json"))["cases"]
    assert len(records) == 40
    diagnostics = list((reference / "diagnostics").glob("qualification-*"))
    assert len(diagnostics) == 6
    for directory in diagnostics:
        assert hcm_repair.reference_file(f"diagnostics/{directory.name}/collisions.xml").is_file()
    for record in records:
        spec = hcm_repair.reference_spec(record["case"])
        for key in ("network", "demand", "program", "topology", "bottleneck_control_trace"):
            if key in spec:
                assert Path(spec[key]).is_relative_to(reference)
                assert Path(spec[key]).is_file()


@pytest.mark.parametrize("invalid", [False, "missing", "outside"])
def test_reference_spec_relocates_windows_paths_and_rejects_bad_inputs(tmp_path, monkeypatch, invalid):
    original = "C:\\old\\workspaces\\hcm-benchmark-v2\\artifacts\\hcm-qualification-v2"
    case = tmp_path / "cases/example"
    case.mkdir(parents=True)
    demand = tmp_path / "inputs/demand.rou.xml"
    demand.parent.mkdir()
    demand.write_text("<routes/>")
    path = original + "\\inputs\\demand.rou.xml"
    if invalid == "missing":
        path = original + "\\inputs\\missing.rou.xml"
    elif invalid == "outside":
        path = original + "\\..\\outside.rou.xml"
    raw = json.dumps({"demand": path})
    (case / "spec.json").write_text(raw)
    spec_path = "cases/example/spec.json"
    demand_path = "inputs/demand.rou.xml"
    (tmp_path / "relocation.json").write_text(json.dumps({"original_output": original,
        "files": {spec_path: hcm_repair.sha(case / "spec.json"),
                  demand_path: hcm_repair.sha(demand)}}))
    monkeypatch.setattr(hcm_repair, "V2_REFERENCE", tmp_path)
    if invalid:
        with pytest.raises(ValueError):
            hcm_repair.reference_spec("example")
    else:
        assert hcm_repair.reference_spec("example")["demand"] == str(demand.resolve())
    assert (case / "spec.json").read_text() == raw


def test_reference_file_rejects_changed_fixture(tmp_path, monkeypatch):
    reference = tmp_path / "reference"
    reference.mkdir()
    file = reference / "trace.xml"
    file.write_text("original")
    expected = hcm_repair.sha(file)
    (reference / "relocation.json").write_text(json.dumps({"files": {"trace.xml": expected}}))
    file.write_text("changed")
    monkeypatch.setattr(hcm_repair, "V2_REFERENCE", reference)
    with pytest.raises(ValueError, match="missing or changed"):
        hcm_repair.reference_file("trace.xml")


def test_protocol_retains_gates_and_uses_independent_seeds():
    from contracts.hcm_qualification_v2 import PROTOCOL as old
    changed = {k for k in PROTOCOL if PROTOCOL[k] != old[k]}
    assert changed == {"topology_id", "protocol_id", "calibration_seeds", "qualification_seeds"}
    assert PROTOCOL["calibration_seeds"] == [73001, 73002]
    assert PROTOCOL["qualification_seeds"] == list(range(74001, 74006))
    assert TOPOLOGY_ID.endswith("v3") and REPAIR_ORDER[0] == ("J14", "J17")


def test_conflict_indices_use_junction_index_not_tls_index():
    path = ROOT / "networks/hcm_neighborhood_benchmark_v2/network.net.xml"
    from src.simulation.hcm_network import load_network
    net = load_network(path)
    mappings = connection_mapping(path)
    assert mappings and all(m["internal_lanes"] for m in mappings)
    # Request bit zero is at the right-hand end of SUMO's bitstring.
    xml = ET.parse(path).getroot()
    for junction in xml.findall("junction"):
        if junction.get("id").startswith(":"):
            continue
        node = net.getNode(junction.get("id"))
        for request in junction.findall("request"):
            i = int(request.get("index"))
            for j, flag in enumerate(reversed(request.get("foes"))):
                assert bool(node.areFoes(i, j)) == (flag == "1")


def test_permissive_turn_waiting_pocket_can_overlap_bus_exit():
    waiting = footprint((0, 0), 90, 4.5, 1.8)
    bus = footprint((0, 5), 0, 12, 2.5)
    assert polygons_overlap(waiting, bus)
    assert not polygons_overlap(footprint((-5, 0), 90, 4.5, 1.8), bus)


def test_bus_tail_is_checked_when_front_has_left_junction():
    bus = footprint((0, 8), 0, 12, 2.5)
    cross_traffic = footprint((3, -2), 90, 4.5, 1.8)
    assert polygons_overlap(bus, cross_traffic)
    assert not polygons_overlap(footprint((0, 8), 0, 4.5, 1.8), cross_traffic)


def test_j17_entry_waiting_keeps_full_bus_clear_of_opposing_lane():
    import math
    start, end = (277.26, 301.29), (272.10, 289.06)
    length = math.dist(start, end)
    front = tuple(a+(b-a)/length for a, b in zip(start, end))
    angle = math.degrees(math.atan2(end[0]-start[0], end[1]-start[1]))
    bus = footprint(front, angle, 12, 2.5)
    assert not polygons_overlap(bus, footprint((281.78, 304), 21.75, 4.5, 1.8))


def test_adjacent_link_cannot_store_bus_at_red_downstream(source):
    for eid in ("32576061#1", "-32576061#1"):
        edge = source.find(f"edge[@id='{eid}']")
        assert {edge.get("from"), edge.get("to")} == {"366426721", "5750600545"}
        assert float(edge.find("lane").get("length")) < 12 + 2.5
    downstream_red = footprint((0, .2), 0, 12, 2.5)
    upstream_turn = footprint((3, -3), 90, 4.5, 1.8)
    assert polygons_overlap(downstream_red, upstream_turn)


@pytest.mark.parametrize("edit", ["permission", "controller", "movement", "unrelated", "relocation"])
def test_reject_semantic_or_unrelated_edits(source, edit):
    after = copy.deepcopy(source)
    if edit == "permission":
        after.find("edge[@id='32576061#1']/lane").set("allow", "passenger")
    elif edit == "controller":
        after.find("tlLogic").set("id", "changed")
    elif edit == "movement":
        after.find("connection[@from='32576061#1']").set("linkIndex", "999")
    elif edit == "unrelated":
        after.find("junction[@id='2217938327']").set("shape", "0,0 0,1 1,1")
    else:
        after.find("junction[@id='366426721']").set("x", "999")
    with pytest.raises(ValueError):
        validate_changes(source, after, {"366426721", "5750600545"})


def test_local_geometry_edits_are_reviewable(source):
    after = copy.deepcopy(source)
    after.find("junction[@id='366426721']").set("shape", "270,280 270,284 274,284")
    changes = validate_changes(source, after, {"366426721", "5750600545"})
    assert len(changes) == 1 and changes[0]["before"] != changes[0]["after"]


def test_internal_owner_handles_cluster_ids():
    jid = "cluster_2217938303_2217938318"
    assert internal_owner(":"+jid+"_14_0", {jid}) == jid
    assert internal_owner(":366426721_2_0", {jid}) is None


def test_repair_inputs_builder_network_and_environment_invalidate_cache(tmp_path):
    files = {key: tmp_path / (key+".xml") for key in ("network", "demand", "program", "topology")}
    for name, path in files.items():
        path.write_text(name)
    spec = {key: str(path) for key, path in files.items()}
    identity = {"protocol": PROTOCOL, "implementation_sha256": implementation_hash(),
                "repair_inputs_sha256": "first", "netconvert_environment": "matching"}
    original = digest(case_identity(spec, identity))
    for field in ("protocol", "implementation_sha256", "repair_inputs_sha256", "netconvert_environment"):
        assert digest(case_identity(spec, {**identity, field: "changed"})) != original
    files["network"].write_text("repaired")
    assert digest(case_identity(spec, identity)) != original


def test_supported_builder_retains_semantics_and_rebuilds_explicit_yield(tmp_path):
    from src.simulation.hcm_repair import build, xml_value
    source_path = ROOT / "networks/hcm_neighborhood_benchmark_v2/network.net.xml"
    topology = json.loads((ROOT / "contracts/topology/hcm_neighborhood_benchmark_v2.json").read_text())
    settings = json.loads((ROOT / "configs/hcm_repair_v3.json").read_text())
    settings.update(controllers=[c for group in REPAIR_ORDER for c in group],
                    stop_line_waiting=[c for group in REPAIR_ORDER for c in group])
    network = build(source_path, tmp_path, settings, topology)
    original, repaired = ET.parse(source_path).getroot(), ET.parse(network).getroot()
    assert [xml_value(t) for t in original.findall("tlLogic")] == [xml_value(t) for t in repaired.findall("tlLogic")]
    # The supported prohibition must become a real response dependency.
    if settings.get("yield_to", {}).get("J17:1") == ["J17:4"]:
        request = repaired.find("junction[@id='5750600545']/request[@index='1']")
        assert request.get("response")[-1-4] == "1"
    for movement, position in settings.get("cont_positions", {}).items():
        controller, index = movement.split(":")
        tls = next(n["sumo_tls_id"] for n in topology["nodes"] if n["node_id"] == controller)
        connection = repaired.find(f"connection[@tl='{tls}'][@linkIndex='{index}']")
        assert float(connection.get("contPos")) == position
    manifest = json.loads((tmp_path / "manifest.json").read_text())
    assert manifest["changes"] and manifest["input_sha256"]["connections.con.xml"]


def test_orphaned_case_preserves_raw_history(tmp_path):
    from src.simulation.qualify_hcm import discard_partial
    partial = tmp_path / "cases/interrupted.partial"
    partial.mkdir(parents=True)
    (partial / "fcd.xml.gz").write_bytes(b"retained raw history")
    discard_partial(partial, tmp_path)
    assert not partial.exists()
    archived = list((tmp_path / "failures").glob("interrupted.partial-orphan-*/fcd.xml.gz"))
    assert len(archived) == 1 and archived[0].read_bytes() == b"retained raw history"
    outside = tmp_path / "unrelated.partial"
    outside.mkdir()
    with pytest.raises(ValueError):
        discard_partial(outside, tmp_path)
    assert outside.exists()
