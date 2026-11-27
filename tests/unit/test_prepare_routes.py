import xml.etree.ElementTree as ET

import pytest

from src.benchmark.prepare import prepare_map

LANE = '<lane id="{id}_0" index="0" shape="0,0 10,0"/>'


def network(path):
    """in_a, in_a2 -> A -> mid -> B -> out_b ; in_b2 -> B.  mid is fed by controlled signal A."""
    edges = "".join(f'<edge id="{e}">{LANE.format(id=e)}</edge>' for e in ("in_a", "in_a2", "mid", "in_b2", "out_b"))
    conns = "".join(f'<connection from="{f}" to="{t}" fromLane="0" toLane="0" tl="{tl}" linkIndex="{i}"/>'
                    for f, t, tl, i in (("in_a", "mid", "A", 0), ("in_a2", "mid", "A", 1),
                                        ("mid", "out_b", "B", 0), ("in_b2", "out_b", "B", 1)))
    logic = "".join(f'<tlLogic id="{n}" type="static" programID="0" offset="0">'
                    '<phase duration="20" state="Gr"/><phase duration="3" state="yr"/>'
                    '<phase duration="20" state="rG"/><phase duration="3" state="ry"/></tlLogic>' for n in "AB")
    path.write_text(f"<net>{edges}{conns}{logic}</net>")


def routes(tmp_path, monkeypatch, **extra):
    monkeypatch.chdir(tmp_path)  # prepare_map writes the canonical topology relative to the cwd
    network(tmp_path / "n.net.xml")
    spec = dict(id="toy_v1", network_path=str(tmp_path / "n.net.xml"), cases=["balanced"], **extra)
    prepared = prepare_map(spec, tmp_path / "out")
    import json
    return json.loads(open(prepared["topology_path"]).read())["routes"]


def test_default_routes_start_at_every_approach(tmp_path, monkeypatch):
    assert len(routes(tmp_path, monkeypatch)) == 4


def test_boundary_routes_skip_approaches_fed_by_another_controlled_signal(tmp_path, monkeypatch):
    found = routes(tmp_path, monkeypatch, route_origins="boundary")
    assert len(found) == 3
    assert all(r["edges"][0] != "mid" for r in found)


def test_unknown_route_origin_mode_is_rejected(tmp_path, monkeypatch):
    with pytest.raises(ValueError):
        routes(tmp_path, monkeypatch, route_origins="everywhere")
