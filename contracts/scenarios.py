"""
EdgeFlow AI — Scenario Registry & Scenario Profiles.

Provides central definitions, metadata, and flow rate profiles for all
traffic scenarios (balanced, directional_surge, downstream_congestion, etc.).
"""

from dataclasses import dataclass, field
from typing import Dict, Any, List, Optional


@dataclass
class ScenarioProfile:
    """Represents a traffic scenario definition with metadata and demand rates."""
    scenario_id: str
    name: str
    description: str
    flow_rates: Dict[str, float] = field(default_factory=dict)
    default_duration_s: int = 300
    category: str = "synthetic"  # "synthetic", "benchmark", "realworld"
    supported_topologies: List[str] = field(default_factory=list)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "scenario_id": self.scenario_id,
            "name": self.name,
            "description": self.description,
            "flow_rates": dict(self.flow_rates),
            "default_duration_s": self.default_duration_s,
            "category": self.category,
            "supported_topologies": list(self.supported_topologies),
        }


# Canonical scenario profiles catalog
CANONICAL_SCENARIOS: Dict[str, ScenarioProfile] = {
    "balanced": ScenarioProfile(
        scenario_id="balanced",
        name="Balanced Traffic Demand",
        description="Equal baseline traffic arrival rate across all approaches (~1,260 veh/h per direction).",
        flow_rates={
            "f_J1_NS": 0.35, "f_J1_EW": 0.35,
            "f_J2_NS": 0.35, "f_J2_EW": 0.35,
            "f_J3_NS": 0.35, "f_J3_EW": 0.35,
            "f_J4_NS": 0.35, "f_J4_EW": 0.35,
        },
        default_duration_s=300,
        category="synthetic",
        supported_topologies=["corridor", "junction", "four_intersection_v1", "four_intersection_rl_v1", "three_way_junction_v1", "tabletop_j1_j2_v1"],
    ),
    "directional_surge": ScenarioProfile(
        scenario_id="directional_surge",
        name="Directional Surge (Peak Hour)",
        description="Heavy North-South corridor flow (~2,700 veh/h) vs light East-West cross flow (~540 veh/h).",
        flow_rates={
            "f_J1_NS": 0.75, "f_J1_EW": 0.15,
            "f_J2_NS": 0.70, "f_J2_EW": 0.15,
            "f_J3_NS": 0.70, "f_J3_EW": 0.15,
            "f_J4_NS": 0.65, "f_J4_EW": 0.15,
        },
        default_duration_s=300,
        category="synthetic",
        supported_topologies=["corridor", "four_intersection_v1", "four_intersection_rl_v1", "tabletop_j1_j2_v1"],
    ),
    "directional_surge_ew": ScenarioProfile(
        scenario_id="directional_surge_ew",
        name="East-West Directional Surge (Mirrored Peak Hour)",
        description="The directional surge profile with the heavy and light axes exchanged.",
        flow_rates={
            "f_J1_NS": 0.15, "f_J1_EW": 0.75,
            "f_J2_NS": 0.15, "f_J2_EW": 0.70,
            "f_J3_NS": 0.15, "f_J3_EW": 0.70,
            "f_J4_NS": 0.15, "f_J4_EW": 0.65,
        },
        default_duration_s=300,
        category="synthetic",
        supported_topologies=["four_intersection_rl_v1"],
    ),
    "downstream_congestion": ScenarioProfile(
        scenario_id="downstream_congestion",
        name="Downstream Bottleneck Congestion",
        description="Asymmetric flow creating network queue spillback and downstream bottleneck stress.",
        flow_rates={
            "f_J1_NS": 0.50, "f_J1_EW": 0.40,
            "f_J2_NS": 0.45, "f_J2_EW": 0.40,
            "f_J3_NS": 0.50, "f_J3_EW": 0.35,
            "f_J4_NS": 0.45, "f_J4_EW": 0.40,
        },
        default_duration_s=300,
        category="synthetic",
        supported_topologies=["corridor", "four_intersection_v1", "four_intersection_rl_v1", "tabletop_j1_j2_v1"],
    ),
    "grid4x4": ScenarioProfile(
        scenario_id="grid4x4",
        name="RESCO Grid 4x4 Network Benchmark",
        description="16-intersection grid network benchmark with multi-edge vehicle routing from RESCO dataset.",
        flow_rates={},
        default_duration_s=3600,
        category="benchmark",
        supported_topologies=["grid16", "grid4x4"],
    ),
    "cologne8": ScenarioProfile(
        scenario_id="cologne8",
        name="TAPAS Cologne Real-World City Graph",
        description="8-intersection real-world urban corridor scenario from TAPAS Cologne dataset.",
        flow_rates={},
        default_duration_s=3600,
        category="realworld",
        supported_topologies=["cologne", "cologne8"],
    ),
    "hcm_corridor": ScenarioProfile(
        scenario_id="hcm_corridor",
        name="TP.HCM Urban Corridor (29 Junction Network)",
        description="29-intersection TP.HCM urban corridor map with raster vehicle icons, map polygons, and emission telemetry.",
        flow_rates={},
        default_duration_s=3600,
        category="realworld",
        supported_topologies=["hcm_corridor", "hcm", "example"],
    ),
}

# Research-only name for the deterministic J3 exit bottleneck experiment.
CANONICAL_SCENARIOS["downstream_bottleneck"] = ScenarioProfile(
    scenario_id="downstream_bottleneck",
    name="J3 Southern Exit Bottleneck",
    description="Four-intersection research scenario with the J3 southern exit limited during seconds 600–1200.",
    flow_rates=dict(CANONICAL_SCENARIOS["downstream_congestion"].flow_rates),
    default_duration_s=2400,
    category="benchmark",
    supported_topologies=["four_intersection_rl_v1"],
)


class ScenarioRegistry:
    """Central Registry for searching, retrieving, and validating Scenario Profiles."""

    @classmethod
    def list_scenarios(cls) -> List[str]:
        return sorted(list(CANONICAL_SCENARIOS.keys()))

    @classmethod
    def get_scenario(cls, scenario_id: str) -> ScenarioProfile:
        sc = scenario_id.lower()
        if sc in CANONICAL_SCENARIOS:
            return CANONICAL_SCENARIOS[sc]
        # Return fallback generic profile if custom scenario
        return ScenarioProfile(
            scenario_id=sc,
            name=f"Custom Scenario ({sc})",
            description="Dynamically specified or imported scenario.",
            flow_rates={
                "f_J1_NS": 0.35, "f_J1_EW": 0.35,
                "f_J2_NS": 0.35, "f_J2_EW": 0.35,
                "f_J3_NS": 0.35, "f_J3_EW": 0.35,
                "f_J4_NS": 0.35, "f_J4_EW": 0.35,
            },
            default_duration_s=300,
            category="custom",
        )

    @classmethod
    def get_flow_rates(cls, scenario_id: str) -> Dict[str, float]:
        profile = cls.get_scenario(scenario_id)
        return dict(profile.flow_rates)
