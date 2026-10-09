import sys
import json
from pathlib import Path

# Add src/tools to sys.path
tools_dir = Path(__file__).parents[2] / "src" / "tools"
if str(tools_dir) not in sys.path:
    sys.path.insert(0, str(tools_dir))

from generate_traffic_scenario import create_traffic_scenario, DEFAULT_HCM_MODAL_SPLIT


def test_create_traffic_scenario(tmp_path):
    net_file = Path(__file__).parents[2] / "services" / "simulator" / "sumo_configs" / "four_intersection_v1.net.xml"
    assert net_file.exists()

    scenario_id = "test_gen_scenario"
    result = create_traffic_scenario(
        net_path=net_file,
        scenario_id=scenario_id,
        num_vehicles=50,
        duration_s=600,
        seed=123,
        update_env=False
    )

    assert result["scenario_id"] == scenario_id
    assert result["num_nodes"] >= 4
    assert result["num_vehicles"] == 50

    # Verify generated topology contract file
    topo_path = Path(result["topology_contract"])
    assert topo_path.exists()
    with open(topo_path, "r", encoding="utf-8") as f:
        data = json.load(f)
    assert data["topology_id"] == scenario_id
    assert len(data["nodes"]) >= 4

    # Verify generated SUMO cfg and rou files
    sumocfg_path = Path(result["sumocfg_file"])
    rou_path = Path(result["rou_file"])
    assert sumocfg_path.exists()
    assert rou_path.exists()

    # Clean up test artifacts
    if topo_path.exists():
        topo_path.unlink()
