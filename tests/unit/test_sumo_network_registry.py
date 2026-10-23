"""
Unit tests for SUMO Network Registry and Multi-Level Topology Mapping (P0).
"""

import math
import pytest
from pathlib import Path

from src.simulation.sumo_network_registry import (
    NETWORK_REGISTRY,
    NetworkMappingResolver,
    run_preflight_check,
    classify_edge_geometry,
)


def test_registry_contains_four_required_networks():
    """Requirement: four_intersection_v1, tabletop_j1_j2_v1, grid4x4, cologne8, hcm_corridor."""
    required = ["four_intersection_v1", "tabletop_j1_j2_v1", "grid4x4", "cologne8", "hcm_corridor"]
    for net_id in required:
        assert net_id in NETWORK_REGISTRY


def test_preflight_all_networks_pass():
    """Preflight check across all 5 canonical topologies must pass with 0 failures."""
    res = run_preflight_check()
    assert res["status"] == "PASS"
    assert len(res["failed_topologies"]) == 0
    assert len(res["verified_topologies"]) == 5

    summary = res["summary"]
    assert summary["total_controlled_tls"] == 59
    assert summary["total_stable_green_phases"] > 0
    assert summary["total_verified_movements"] > 0


def test_geometric_direction_classification():
    """Verify geometry-based axis and side classification without relying on '_N_'/'_S_' strings."""
    class DummyNode:
        def __init__(self, nid):
            self._nid = nid
        def getID(self):
            return self._nid

    class DummyEdge:
        def __init__(self, shape):
            self._shape = shape
        def getShape(self):
            return self._shape

    # Vehicle traveling South (dy < 0, abs(dy) > abs(dx)): comes FROM NORTH
    e_southbound = DummyEdge([(100.0, 200.0), (100.0, 50.0)])
    geo_sb = classify_edge_geometry(e_southbound)
    assert geo_sb["axis"] == "NS"
    assert geo_sb["from_side"] == "NORTH"
    assert geo_sb["vector"] == (0.0, -150.0)

    # Vehicle traveling North (dy > 0, abs(dy) > abs(dx)): comes FROM SOUTH
    e_northbound = DummyEdge([(100.0, 0.0), (100.0, 100.0)])
    geo_nb = classify_edge_geometry(e_northbound)
    assert geo_nb["axis"] == "NS"
    assert geo_nb["from_side"] == "SOUTH"

    # Vehicle traveling East (dx > 0, abs(dx) > abs(dy)): comes FROM WEST
    e_eastbound = DummyEdge([(0.0, 50.0), (150.0, 50.0)])
    geo_eb = classify_edge_geometry(e_eastbound)
    assert geo_eb["axis"] == "EW"
    assert geo_eb["from_side"] == "WEST"

    # Vehicle traveling West (dx < 0, abs(dx) > abs(dy)): comes FROM EAST
    e_westbound = DummyEdge([(200.0, 50.0), (50.0, 50.0)])
    geo_wb = classify_edge_geometry(e_westbound)
    assert geo_wb["axis"] == "EW"
    assert geo_wb["from_side"] == "EAST"


def test_controlled_vs_uncontrolled_nodes_distinction():
    """Verify controlled TLS vs geometry/priority nodes distinction."""
    # grid4x4 has 16 controlled TLS, 16 boundary nodes
    res_grid = NetworkMappingResolver("grid4x4")
    m_grid = res_grid.mapping
    assert len(m_grid["controlled_tls_ids"]) == 16
    assert len(m_grid["uncontrolled_node_ids"]) == 16
    assert "A0" in m_grid["controlled_tls_ids"]
    assert "bottom0" in m_grid["uncontrolled_node_ids"]
    assert m_grid["nodes"]["bottom0"]["is_controlled_tls"] is False

    # cologne8 has 8 controlled TLS, 70 geometry nodes
    res_col = NetworkMappingResolver("cologne8")
    m_col = res_col.mapping
    assert len(m_col["controlled_tls_ids"]) == 8
    assert len(m_col["uncontrolled_node_ids"]) == 70

    # hcm_corridor has 29 controlled TLS, 21 geometry nodes
    res_hcm = NetworkMappingResolver("hcm_corridor")
    m_hcm = res_hcm.mapping
    assert len(m_hcm["controlled_tls_ids"]) == 29
    assert len(m_hcm["uncontrolled_node_ids"]) == 21


def test_stable_green_phases_contain_no_yellow():
    """Verify that NO yellow or transition state is included in the controller action set."""
    for net_id in ["four_intersection_v1", "tabletop_j1_j2_v1", "grid4x4", "cologne8", "hcm_corridor"]:
        resolver = NetworkMappingResolver(net_id)
        for nid in resolver.mapping["controlled_tls_ids"]:
            node_data = resolver.mapping["nodes"][nid]
            phases = node_data["phases"]
            assert len(phases) > 0, f"Node {nid} in {net_id} has no stable green phases!"
            for p in phases:
                state = p["state"]
                assert "y" not in state and "Y" not in state, (
                    f"Yellow state '{state}' found in action phase {p['phase_id']} of node {nid}!"
                )
                assert "G" in state or "g" in state, (
                    f"All-red state '{state}' found in action phase {p['phase_id']} of node {nid}!"
                )
