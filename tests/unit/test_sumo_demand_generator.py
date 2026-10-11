"""
Unit tests for SUMO Demand Generator and Scenario Routing (P0).
"""

import tempfile
from pathlib import Path
import pytest

from src.simulation.sumo_demand_generator import (
    SumoDemandGenerator,
    TOPOLOGY_ROUTE_REGISTRY,
)


def test_route_registry_covers_all_four_networks():
    required = ["four_intersection_v1", "grid4x4", "cologne8", "hcm_corridor"]
    for net_id in required:
        assert net_id in TOPOLOGY_ROUTE_REGISTRY
        routes = TOPOLOGY_ROUTE_REGISTRY[net_id]
        assert len(routes) >= 8
        # Each route has route_id, axis ('NS' or 'EW'), and non-empty edges
        for r in routes:
            assert "route_id" in r
            assert r["axis"] in ("NS", "EW")
            assert len(r["edges"]) >= 2


def test_frozen_demand_determinism():
    """Same (topology, scenario, seed) produces byte-identical files and identical SHA-256."""
    with tempfile.TemporaryDirectory() as tmp1, tempfile.TemporaryDirectory() as tmp2:
        out1 = SumoDemandGenerator.generate_frozen_demand(
            "grid4x4", "balanced", 303, Path(tmp1), warmup_s=60, duration_s=120, drain_s=30
        )
        out2 = SumoDemandGenerator.generate_frozen_demand(
            "grid4x4", "balanced", 303, Path(tmp2), warmup_s=60, duration_s=120, drain_s=30
        )
        assert out1["demand_rou_sha256"] == out2["demand_rou_sha256"]
        assert out1["total_scheduled_vehicles"] == out2["total_scheduled_vehicles"]
        assert out1["cohort_vehicles_count"] == out2["cohort_vehicles_count"]


def test_frozen_demand_seed_diversity():
    """Different seeds generate distinct demand files."""
    with tempfile.TemporaryDirectory() as tmp:
        p1 = Path(tmp) / "seed1"
        p2 = Path(tmp) / "seed2"
        out1 = SumoDemandGenerator.generate_frozen_demand(
            "four_intersection_v1", "balanced", 101, p1, warmup_s=0, duration_s=60, drain_s=30
        )
        out2 = SumoDemandGenerator.generate_frozen_demand(
            "four_intersection_v1", "balanced", 202, p2, warmup_s=0, duration_s=60, drain_s=30
        )
        assert out1["demand_rou_sha256"] != out2["demand_rou_sha256"]


def test_directional_surge_increases_cohort():
    """Directional surge increases scheduled vehicles on the primary corridor."""
    with tempfile.TemporaryDirectory() as tmp:
        p_bal = Path(tmp) / "bal"
        p_srg = Path(tmp) / "srg"
        out_bal = SumoDemandGenerator.generate_frozen_demand(
            "four_intersection_v1", "balanced", 404, p_bal, warmup_s=0, duration_s=60, drain_s=30
        )
        out_srg = SumoDemandGenerator.generate_frozen_demand(
            "four_intersection_v1", "directional_surge", 404, p_srg, warmup_s=0, duration_s=60, drain_s=30
        )
        assert out_srg["total_scheduled_vehicles"] > out_bal["total_scheduled_vehicles"]


def test_vehicle_ledger_structure():
    """Ledger must partition cohort vehicles from warmup vehicles."""
    with tempfile.TemporaryDirectory() as tmp:
        out = SumoDemandGenerator.generate_frozen_demand(
            "four_intersection_v1", "balanced", 505, Path(tmp), warmup_s=60, duration_s=120, drain_s=30
        )
        total = out["total_scheduled_vehicles"]
        cohort = out["cohort_vehicles_count"]
        warmup = out["warmup_vehicles_count"]
        assert total == cohort + warmup
        assert total > 0
