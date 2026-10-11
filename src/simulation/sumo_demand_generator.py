"""
EdgeFlow AI — Deterministic Frozen Demand & Scenario Generator (P0/P1).

Generates reproducible, byte-frozen SUMO demand for:
  - four_intersection_v1
  - grid4x4
  - cologne8
  - hcm_corridor

Guarantees:
  1. Every (topology, scenario, seed) generates identical byte-for-byte demand.rou.xml.
  2. SHA-256 hash verified before and after every controller execution.
  3. Controller execution order has ZERO impact on demand.
  4. Complete scheduled-vehicle accounting ledger (warmup cohort vs measurement cohort).
  5. Realistic continuous multi-TLS arterial routes.
  6. Precise scenario interventions:
     - balanced: equal base demand distribution across arterial corridors.
     - directional_surge: demand surge on the primary corridor during surge window.
     - downstream_congestion: standard demand paired with physical speed-gating on bottleneck edge.
"""

import os
import sys
import json
import random
import hashlib
import logging
from pathlib import Path
from typing import Dict, Any, List, Tuple
import xml.etree.ElementTree as ET

logger = logging.getLogger("demand-generator")

REPO_ROOT = Path(__file__).resolve().parents[2]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from src.simulation.sumo_network_registry import NETWORK_REGISTRY, NetworkMappingResolver


# ==============================================================================
# Verified Arterial Route Libraries
# ==============================================================================

# 1. four_intersection_v1 (8 continuous routes, 4 NS, 4 EW)
FOUR_INT_ROUTES = [
    {"route_id": "r_J1_NS", "axis": "NS", "edges": ["J1_N_IN", "J3_N_IN"]},
    {"route_id": "r_J2_NS", "axis": "NS", "edges": ["J2_N_IN", "J4_N_IN"]},
    {"route_id": "r_J3_NS", "axis": "NS", "edges": ["J3_S_IN", "J1_S_IN"]},
    {"route_id": "r_J4_NS", "axis": "NS", "edges": ["J4_S_IN", "J2_S_IN"]},
    {"route_id": "r_J1_EW", "axis": "EW", "edges": ["J1_W_IN", "J2_W_IN"]},
    {"route_id": "r_J2_EW", "axis": "EW", "edges": ["J2_E_IN", "J1_E_IN"]},
    {"route_id": "r_J3_EW", "axis": "EW", "edges": ["J3_W_IN", "J4_W_IN"]},
    {"route_id": "r_J4_EW", "axis": "EW", "edges": ["J4_E_IN", "J3_E_IN"]},
]

# 2. grid4x4 (16 arterial routes, 8 NS, 8 EW across all rows and columns)
GRID4X4_ROUTES = [
    # North-South columns
    {"route_id": "r_col0_sb", "axis": "NS", "edges": ["top0A3", "A3A2", "A2A1", "A1A0", "A0bottom0"]},
    {"route_id": "r_col0_nb", "axis": "NS", "edges": ["bottom0A0", "A0A1", "A1A2", "A2A3", "A3top0"]},
    {"route_id": "r_col1_sb", "axis": "NS", "edges": ["top1B3", "B3B2", "B2B1", "B1B0", "B0bottom1"]},
    {"route_id": "r_col1_nb", "axis": "NS", "edges": ["bottom1B0", "B0B1", "B1B2", "B2B3", "B3top1"]},
    {"route_id": "r_col2_sb", "axis": "NS", "edges": ["top2C3", "C3C2", "C2C1", "C1C0", "C0bottom2"]},
    {"route_id": "r_col2_nb", "axis": "NS", "edges": ["bottom2C0", "C0C1", "C1C2", "C2C3", "C3top2"]},
    {"route_id": "r_col3_sb", "axis": "NS", "edges": ["top3D3", "D3D2", "D2D1", "D1D0", "D0bottom3"]},
    {"route_id": "r_col3_nb", "axis": "NS", "edges": ["bottom3D0", "D0D1", "D1D2", "D2D3", "D3top3"]},
    # East-West rows
    {"route_id": "r_row0_eb", "axis": "EW", "edges": ["left0A0", "A0B0", "B0C0", "C0D0", "D0right0"]},
    {"route_id": "r_row0_wb", "axis": "EW", "edges": ["right0D0", "D0C0", "C0B0", "B0A0", "A0left0"]},
    {"route_id": "r_row1_eb", "axis": "EW", "edges": ["left1A1", "A1B1", "B1C1", "C1D1", "D1right1"]},
    {"route_id": "r_row1_wb", "axis": "EW", "edges": ["right1D1", "D1C1", "C1B1", "B1A1", "A1left1"]},
    {"route_id": "r_row2_eb", "axis": "EW", "edges": ["left2A2", "A2B2", "B2C2", "C2D2", "D2right2"]},
    {"route_id": "r_row2_wb", "axis": "EW", "edges": ["right2D2", "D2C2", "C2B2", "B2A2", "A2left2"]},
    {"route_id": "r_row3_eb", "axis": "EW", "edges": ["left3A3", "A3B3", "B3C3", "C3D3", "D3right3"]},
    {"route_id": "r_row3_wb", "axis": "EW", "edges": ["right3D3", "D3C3", "C3B3", "B3A3", "A3left3"]},
]

# 3. cologne8 (verified multi-TLS arterial routes across the subnetwork)
COLOGNE8_ROUTES = [
    {
        "route_id": "r_col_arterial_1",
        "axis": "NS",
        "edges": [
            "-186623965#18", "-186623965#16", "-186623965#14", "186623965#9"
        ]
    },
    {
        "route_id": "r_col_arterial_2",
        "axis": "NS",
        "edges": [
            "-22917421#14", "-186623965#16", "-186623965#14"
        ]
    },
    {
        "route_id": "r_col_arterial_3",
        "axis": "NS",
        "edges": [
            "186623965#15", "-186623965#16", "155600123#0"
        ]
    },
    {
        "route_id": "r_col_arterial_4",
        "axis": "NS",
        "edges": [
            "22917421#3", "-186623965#16", "42925825#0"
        ]
    },
    {
        "route_id": "r_col_transverse_1",
        "axis": "EW",
        "edges": [
            "-132042183", "132042183", "-23283472#2", "23283473"
        ]
    },
    {
        "route_id": "r_col_transverse_2",
        "axis": "EW",
        "edges": [
            "-133081985#0", "23283435#1", "-23283579#1", "-23283579#0"
        ]
    },
    {
        "route_id": "r_col_transverse_3",
        "axis": "EW",
        "edges": [
            "-133081985#0", "133081985#0", "133081985#1", "8716807#0"
        ]
    },
    {
        "route_id": "r_col_transverse_4",
        "axis": "EW",
        "edges": [
            "-133081985#0", "133081985#0", "133081985#1", "28675510#0"
        ]
    },
]

# 4. hcm_corridor (verified arterial corridor routes along the primary spine and side feeders)
HCM_ROUTES = [
    {
        "route_id": "r_hcm_spine_sb",
        "axis": "NS",
        "edges": [
            "32577015#5", "32577015#6", "32577015#7", "32577015#8",
            "32577015#9", "290729095#0", "32576064#1"
        ]
    },
    {
        "route_id": "r_hcm_spine_nb",
        "axis": "NS",
        "edges": [
            "-32576064#1", "-290729095#0", "-32577015#9", "-32577015#8",
            "-32577015#7", "-32577015#6", "-32577015#5"
        ]
    },
    {
        "route_id": "r_hcm_arterial_3",
        "axis": "NS",
        "edges": [
            "-32576061#6", "-32576061#5", "-32576061#4", "-32576061#3",
            "-32576061#2", "-32576061#1", "-32576061#0"
        ]
    },
    {
        "route_id": "r_hcm_arterial_4",
        "axis": "NS",
        "edges": [
            "32576061#0", "32576061#1", "32576061#2", "32576061#3",
            "32576061#4", "32576061#5", "32576061#6"
        ]
    },
    {
        "route_id": "r_hcm_cross_1",
        "axis": "EW",
        "edges": [
            "211849500#1", "32577015#9", "-32576061#6"
        ]
    },
    {
        "route_id": "r_hcm_cross_2",
        "axis": "EW",
        "edges": [
            "-211849412", "-32576065#0"
        ]
    },
    {
        "route_id": "r_hcm_cross_3",
        "axis": "EW",
        "edges": [
            "-211849413#0", "32576061#4"
        ]
    },
    {
        "route_id": "r_hcm_cross_4",
        "axis": "EW",
        "edges": [
            "-1060982830", "-32576061#4", "-32576061#3"
        ]
    },
]

TOPOLOGY_ROUTE_REGISTRY: Dict[str, List[Dict[str, Any]]] = {
    "four_intersection_v1": FOUR_INT_ROUTES,
    "grid4x4": GRID4X4_ROUTES,
    "cologne8": COLOGNE8_ROUTES,
    "hcm_corridor": HCM_ROUTES,
}


# ==============================================================================
# Deterministic Demand Generator
# ==============================================================================

class SumoDemandGenerator:
    """
    Generates deterministic, verified route files (.rou.xml) and vehicle ledgers.
    """

    @classmethod
    def generate_frozen_demand(
        cls,
        topology_id: str,
        scenario: str,
        seed: int,
        output_dir: Path,
        warmup_s: int = 300,
        duration_s: int = 1800,
        drain_s: int = 600,
    ) -> Dict[str, Any]:
        """
        Generate frozen demand for (topology, scenario, seed).
        Writes:
          - demand.rou.xml
          - demand_ledger.json
          - scenario.json
          - hashes.json
        """
        if topology_id not in TOPOLOGY_ROUTE_REGISTRY:
            raise ValueError(f"Topology '{topology_id}' not in route registry")

        net_info = NETWORK_REGISTRY[topology_id]
        routes_list = TOPOLOGY_ROUTE_REGISTRY[topology_id]
        output_dir.mkdir(parents=True, exist_ok=True)

        # Time windows
        total_horizon_s = warmup_s + duration_s + drain_s
        demand_end_s = warmup_s + duration_s  # No new vehicles generated after this point

        # Surge & congestion windows
        if duration_s <= 120:
            # Short smoke window
            surge_start_s = warmup_s + 10.0
            surge_end_s = warmup_s + min(40.0, duration_s * 0.8)
            congestion_start_s = warmup_s + 15.0
            congestion_end_s = warmup_s + min(45.0, duration_s * 0.8)
        elif duration_s < 1200:
            # Intermediate duration (e.g. 180s, 300s, 600s fast benchmarks):
            # Scale intervention window to the active cohort measurement interval [warmup .. warmup + duration]
            surge_start_s = warmup_s + round(0.20 * duration_s, 1)
            surge_end_s = warmup_s + round(0.70 * duration_s, 1)
            congestion_start_s = warmup_s + round(0.20 * duration_s, 1)
            congestion_end_s = warmup_s + round(0.70 * duration_s, 1)
        else:
            # Standard research protocol (e.g. 1800s benchmark)
            surge_start_s = warmup_s + 300.0
            surge_end_s = warmup_s + 900.0
            congestion_start_s = warmup_s + 300.0
            congestion_end_s = warmup_s + 900.0

        scenario_spec = {
            "scenario": scenario,
            "topology_id": topology_id,
            "seed": seed,
            "warmup_s": warmup_s,
            "duration_s": duration_s,
            "drain_s": drain_s,
            "total_horizon_s": total_horizon_s,
            "demand_end_s": demand_end_s,
            "surge_window": {
                "start_s": surge_start_s,
                "end_s": surge_end_s,
                "surge_axis": net_info["primary_surge_axis"],
                "multiplier": 2.2,
            },
            "downstream_congestion_intervention": {
                "bottleneck_edge": net_info["bottleneck_edge"],
                "normal_speed_mps": net_info["normal_speed_mps"],
                "congested_speed_mps": net_info["congested_speed_mps"],
                "start_s": congestion_start_s,
                "end_s": congestion_end_s,
            },
        }

        # Deterministic RNG seeded once
        rng = random.Random(seed)

        # Base arrival interval per route:
        # e.g. base headway ~ 10-18 seconds per route -> ~0.06-0.10 veh/s per route.
        # Across 8-16 routes, network load is ~0.6 - 1.2 veh/s.
        base_mean_headway_s = 14.0

        scheduled_vehicles: List[Dict[str, Any]] = []
        global_veh_idx = 0

        for r_entry in routes_list:
            rid = r_entry["route_id"]
            axis = r_entry["axis"]
            is_surge_corridor = (axis == net_info["primary_surge_axis"])

            # Poisson arrival process (exponential inter-arrival times)
            curr_time = rng.uniform(0.5, 5.0)

            while curr_time < demand_end_s:
                # Check if in surge window for directional_surge
                if scenario == "directional_surge" and is_surge_corridor and (surge_start_s <= curr_time < surge_end_s):
                    rate_multiplier = 2.2
                else:
                    rate_multiplier = 1.0

                headway = rng.expovariate(rate_multiplier / base_mean_headway_s)
                curr_time += max(1.0, headway)
                if curr_time >= demand_end_s:
                    break

                global_veh_idx += 1
                vid = f"veh_{topology_id}_{global_veh_idx:06d}"
                is_cohort = (warmup_s <= curr_time < demand_end_s)

                scheduled_vehicles.append({
                    "vehicle_id": vid,
                    "depart_time_s": round(curr_time, 2),
                    "route_id": rid,
                    "corridor_axis": axis,
                    "is_cohort": is_cohort,
                })

        # Sort all scheduled departures strictly by departure time then ID
        scheduled_vehicles.sort(key=lambda v: (v["depart_time_s"], v["vehicle_id"]))

        # Build SUMO routes XML
        root = ET.Element("routes")
        root.set("xmlns:xsi", "http://www.w3.org/2001/XMLSchema-instance")

        # Standard passenger car vehicle type
        ET.SubElement(
            root,
            "vType",
            id="car",
            accel="2.6",
            decel="4.5",
            sigma="0.5",
            length="5.0",
            minGap="2.5",
            maxSpeed="13.89",
            guiShape="passenger",
        )

        # Routes definition
        for r_entry in routes_list:
            ET.SubElement(
                root,
                "route",
                id=r_entry["route_id"],
                edges=" ".join(r_entry["edges"]),
            )

        # Vehicle instances
        for v in scheduled_vehicles:
            ET.SubElement(
                root,
                "vehicle",
                id=v["vehicle_id"],
                type="car",
                route=v["route_id"],
                depart=f"{v['depart_time_s']:.2f}",
                departLane="best",
                departSpeed="max",
            )

        # Indent and write XML
        tree = ET.ElementTree(root)
        ET.indent(tree, space="  ", level=0)
        rou_xml_path = output_dir / "demand.rou.xml"
        tree.write(rou_xml_path, encoding="utf-8", xml_declaration=True)

        # Write demand ledger
        cohort_count = sum(1 for v in scheduled_vehicles if v["is_cohort"])
        warmup_count = len(scheduled_vehicles) - cohort_count

        ledger_data = {
            "topology_id": topology_id,
            "scenario": scenario,
            "seed": seed,
            "total_scheduled_vehicles": len(scheduled_vehicles),
            "cohort_vehicles_count": cohort_count,
            "warmup_vehicles_count": warmup_count,
            "warmup_s": warmup_s,
            "duration_s": duration_s,
            "drain_s": drain_s,
            "scheduled_vehicles": scheduled_vehicles,
        }
        ledger_path = output_dir / "demand_ledger.json"
        with open(ledger_path, "w", encoding="utf-8") as f:
            json.dump(ledger_data, f, indent=2)

        # Write scenario.json
        scenario_path = output_dir / "scenario.json"
        with open(scenario_path, "w", encoding="utf-8") as f:
            json.dump(scenario_spec, f, indent=2)

        # Compute file hashes
        rou_sha256 = cls.compute_sha256(rou_xml_path)
        ledger_sha256 = cls.compute_sha256(ledger_path)
        hashes_data = {
            "demand_rou_sha256": rou_sha256,
            "demand_ledger_sha256": ledger_sha256,
        }
        hashes_path = output_dir / "hashes.json"
        with open(hashes_path, "w", encoding="utf-8") as f:
            json.dump(hashes_data, f, indent=2)

        logger.info(
            f"Frozen demand generated for ({topology_id}, {scenario}, seed={seed}): "
            f"Total={len(scheduled_vehicles)} (Cohort={cohort_count}, Warmup={warmup_count}), "
            f"SHA256={rou_sha256[:16]}..."
        )

        return {
            "demand_rou_path": str(rou_xml_path.resolve()),
            "demand_ledger_path": str(ledger_path.resolve()),
            "scenario_path": str(scenario_path.resolve()),
            "hashes_path": str(hashes_path.resolve()),
            "demand_rou_sha256": rou_sha256,
            "total_scheduled_vehicles": len(scheduled_vehicles),
            "cohort_vehicles_count": cohort_count,
            "warmup_vehicles_count": warmup_count,
            "scenario_spec": scenario_spec,
        }

    @staticmethod
    def compute_sha256(file_path: Path) -> str:
        h = hashlib.sha256()
        with open(file_path, "rb") as f:
            while chunk := f.read(65536):
                h.update(chunk)
        return h.hexdigest()
