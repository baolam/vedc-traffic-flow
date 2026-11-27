import numpy as np
import pytest

from contracts.benchmark import OBSERVATION_SPEC
from src.control.observation import flow_index, observe_node

FEATURES = OBSERVATION_SPEC["features"]


def chain(length=5):
    """A -> B -> C -> D -> E, each node two phases: through (west->east) and cross."""
    ids = "ABCDEFG"[:length]
    nodes = []
    for i, n in enumerate(ids):
        nxt = ids[i + 1] if i + 1 < length else None
        nodes.append({"node_id": n, "approaches": [f"{n}_W", f"{n}_S"], "phases": [
            {"phase_id": f"{n}_P0", "approaches": [f"{n}_W"], "movements": [
                {"from_approach": f"{n}_W", "to_node": nxt, "to_approach": f"{nxt}_W" if nxt else None}]},
            {"phase_id": f"{n}_P1", "approaches": [f"{n}_S"], "movements": [
                {"from_approach": f"{n}_S", "to_node": None, "to_approach": None}]}]})
    return {"topology_id": "chain", "nodes": nodes}


def telemetry(topology, queue=0.0):
    out = {}
    for n in topology["nodes"]:
        nid = n["node_id"]
        out[nid] = {"node_id": nid, "current_phase_id": f"{nid}_P0", "signal_state": "GREEN",
                    "elapsed_green_s": 12.0, "phase_service_age_s": {p["phase_id"]: 3.0 for p in n["phases"]},
                    "approaches": [{"approach_id": a, "queue_vehicles": queue, "occupancy_ratio": 0.1,
                                    "confidence": 1.0} for a in n["approaches"]]}
    return out


def set_queue(tel, node, approach, q):
    for a in tel[node]["approaches"]:
        if a["approach_id"] == approach:
            a["queue_vehicles"] = q


def obs(top, tel, node="C", radius=2):
    idx = flow_index(top)
    n = next(x for x in top["nodes"] if x["node_id"] == node)
    return observe_node(n, tel, idx, radius)


def col(name):
    return FEATURES.index(name)


def test_shape_and_values_are_finite_for_any_phase_count():
    top = chain()
    result = obs(top, telemetry(top, 4.0))
    assert result.shape == (2, len(FEATURES)) and np.isfinite(result).all()
    assert result[0, col("served_queue")] == pytest.approx(4 / 20)
    assert result[0, col("is_current")] == 1 and result[1, col("is_current")] == 0


def test_downstream_and_upstream_hops_are_read():
    top = chain()
    tel = telemetry(top)
    set_queue(tel, "D", "D_W", 10)  # hop-1 downstream of C phase 0
    set_queue(tel, "E", "E_W", 20)  # hop-2 downstream
    set_queue(tel, "B", "B_W", 6)   # hop-1 upstream
    set_queue(tel, "A", "A_W", 8)   # hop-2 upstream
    r = obs(top, tel)[0]
    assert r[col("down1_queue")] == pytest.approx(10 / 20) and r[col("down2_queue")] == pytest.approx(1.0)
    assert r[col("up1_queue")] == pytest.approx(6 / 20) and r[col("up2_queue")] == pytest.approx(8 / 20)


def test_nothing_beyond_radius_influences_the_observation():
    top = chain(7)  # A..G; node D has hop-3 nodes A and G on both sides
    base = obs(top, telemetry(top), node="D")
    far = telemetry(top)
    for node in ("A", "G"):
        far[node]["signal_state"] = "ALL_RED"
        for a in far[node]["approaches"]:
            a["queue_vehicles"], a["confidence"] = 99.0, 0.0  # unavailable far away must not raise
    assert np.array_equal(obs(top, far, node="D"), base)


def test_hop3_telemetry_is_not_required():
    top = chain(7)
    tel = telemetry(top)
    near = {k: v for k, v in tel.items() if k in "BCDEF"}
    assert np.array_equal(obs(top, near, node="D"), obs(top, tel, node="D"))


def test_radius_zero_is_local_only():
    top = chain()
    tel = telemetry(top)
    set_queue(tel, "D", "D_W", 10)
    set_queue(tel, "B", "B_W", 10)
    local = obs(top, {"C": tel["C"]}, radius=0)
    cols = [col(c) for c in ("down1_queue", "down2_queue", "up1_queue", "up2_queue")]
    assert (local[:, cols] == 0).all()


def test_missing_in_radius_telemetry_or_zero_confidence_raises():
    top = chain()
    tel = telemetry(top)
    with pytest.raises(ValueError):
        obs(top, {k: v for k, v in tel.items() if k != "D"}, radius=1)
    tel["D"]["approaches"][0]["confidence"] = 0.0
    with pytest.raises(ValueError):
        obs(top, tel, radius=1)
