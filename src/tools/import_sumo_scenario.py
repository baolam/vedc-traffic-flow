import os
import sys
import json
import urllib.request
import argparse
import logging
from pathlib import Path
from typing import Dict, Any, Optional

# Add src/graph to path to import SumoNetworkConverter
ROOT_DIR = Path(__file__).resolve().parents[2]
GRAPH_DIR = ROOT_DIR / "src" / "graph"
if str(GRAPH_DIR) not in sys.path:
    sys.path.insert(0, str(GRAPH_DIR))

from sumo_converter import SumoNetworkConverter

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
logger = logging.getLogger("import_sumo_scenario")

# Standard public repository URLs for RESCO benchmarks & SUMO open scenarios
SUMO_RL_BASE_URL = "https://raw.githubusercontent.com/LucasAlegre/sumo-rl/main/sumo_rl/nets"

PRESET_URLS = {
    "resco_grid4x4": {
        "net": f"{SUMO_RL_BASE_URL}/RESCO/grid4x4/grid4x4.net.xml",
        "rou": f"{SUMO_RL_BASE_URL}/RESCO/grid4x4/grid4x4_1.rou.xml",
        "scenario_id": "grid4x4"
    },
    "grid4x4": {
        "net": f"{SUMO_RL_BASE_URL}/RESCO/grid4x4/grid4x4.net.xml",
        "rou": f"{SUMO_RL_BASE_URL}/RESCO/grid4x4/grid4x4_1.rou.xml",
        "scenario_id": "grid4x4"
    },
    "resco_cologne8": {
        "net": f"{SUMO_RL_BASE_URL}/RESCO/cologne8/cologne8.net.xml",
        "rou": f"{SUMO_RL_BASE_URL}/RESCO/cologne8/cologne8_1.rou.xml",
        "scenario_id": "cologne8"
    },
    "cologne8": {
        "net": f"{SUMO_RL_BASE_URL}/RESCO/cologne8/cologne8.net.xml",
        "rou": f"{SUMO_RL_BASE_URL}/RESCO/cologne8/cologne8_1.rou.xml",
        "scenario_id": "cologne8"
    },
    "resco_arterial4x4": {
        "net": f"{SUMO_RL_BASE_URL}/RESCO/arterial4x4/arterial4x4.net.xml",
        "rou": f"{SUMO_RL_BASE_URL}/RESCO/arterial4x4/arterial4x4_1.rou.xml",
        "scenario_id": "arterial4x4"
    },
    "arterial4x4": {
        "net": f"{SUMO_RL_BASE_URL}/RESCO/arterial4x4/arterial4x4.net.xml",
        "rou": f"{SUMO_RL_BASE_URL}/RESCO/arterial4x4/arterial4x4_1.rou.xml",
        "scenario_id": "arterial4x4"
    },
    "resco_ingolstadt21": {
        "net": f"{SUMO_RL_BASE_URL}/RESCO/ingolstadt21/ingolstadt21.net.xml",
        "rou": f"{SUMO_RL_BASE_URL}/RESCO/ingolstadt21/ingolstadt21_1.rou.xml",
        "scenario_id": "ingolstadt21"
    },
    "ingolstadt21": {
        "net": f"{SUMO_RL_BASE_URL}/RESCO/ingolstadt21/ingolstadt21.net.xml",
        "rou": f"{SUMO_RL_BASE_URL}/RESCO/ingolstadt21/ingolstadt21_1.rou.xml",
        "scenario_id": "ingolstadt21"
    },
    "single_intersection": {
        "net": f"{SUMO_RL_BASE_URL}/2way-single-intersection/single-intersection.net.xml",
        "rou": f"{SUMO_RL_BASE_URL}/2way-single-intersection/single-intersection-vhvh.rou.xml",
        "scenario_id": "single_intersection"
    },
    "tapas_cologne": {
        "net": f"{SUMO_RL_BASE_URL}/RESCO/cologne8/cologne8.net.xml",
        "rou": f"{SUMO_RL_BASE_URL}/RESCO/cologne8/cologne8_1.rou.xml",
        "scenario_id": "tapas_cologne"
    }
}


def download_file(url: str, dest_path: Path) -> bool:
    """Download a file from web URL."""
    try:
        logger.info(f"Downloading from {url} -> {dest_path}...")
        dest_path.parent.mkdir(parents=True, exist_ok=True)
        req = urllib.request.Request(url, headers={'User-Agent': 'Mozilla/5.0'})
        with urllib.request.urlopen(req) as response, open(dest_path, 'wb') as out_file:
            out_file.write(response.read())
        logger.info(f"Successfully downloaded {dest_path.name}")
        return True
    except Exception as e:
        logger.error(f"Failed to download from {url}: {e}")
        return False


def generate_sumocfg(scenario_id: str, net_path: Path, rou_path: Path, config_dest: Path):
    """Generate SUMO .sumocfg file linking .net.xml and .rou.xml."""
    config_dest.parent.mkdir(parents=True, exist_ok=True)
    try:
        rel_net = os.path.relpath(net_path, config_dest.parent).replace("\\", "/")
        rel_rou = os.path.relpath(rou_path, config_dest.parent).replace("\\", "/")
    except ValueError:
        rel_net = str(net_path).replace("\\", "/")
        rel_rou = str(rou_path).replace("\\", "/")

    sumocfg_content = f"""<?xml version="1.0" encoding="UTF-8"?>
<configuration xmlns:xsi="http://www.w3.org/2001/XMLSchema-instance" xsi:noNamespaceSchemaLocation="http://sumo.dlr.de/xsd/sumoConfiguration.xsd">
    <input>
        <net-file value="{rel_net}"/>
        <route-files value="{rel_rou}"/>
    </input>
    <time>
        <begin value="0"/>
        <end value="3600"/>
    </time>
    <report>
        <no-step-log value="true"/>
    </report>
</configuration>
"""
    with open(config_dest, "w", encoding="utf-8") as f:
        f.write(sumocfg_content)
    logger.info(f"Created SUMO config file: {config_dest}")


def update_env_file(env_path: Path, scenario_id: str):
    """Update EDGEFLOW_TOPOLOGY in .env file."""
    if not env_path.exists():
        logger.warning(f"File .env not found at {env_path}, skipping .env update.")
        return

    lines = env_path.read_text(encoding="utf-8").splitlines()
    updated = False
    new_lines = []
    for line in lines:
        if line.strip().startswith("EDGEFLOW_TOPOLOGY="):
            new_lines.append(f"EDGEFLOW_TOPOLOGY={scenario_id}")
            updated = True
        else:
            new_lines.append(line)

    if not updated:
        new_lines.append(f"EDGEFLOW_TOPOLOGY={scenario_id}")

    env_path.write_text("\n".join(new_lines) + "\n", encoding="utf-8")
    logger.info(f"Updated {env_path.name} with EDGEFLOW_TOPOLOGY={scenario_id}")


def import_scenario(
    preset: Optional[str] = None,
    net_path: Optional[str] = None,
    rou_path: Optional[str] = None,
    url: Optional[str] = None,
    scenario_id: Optional[str] = None,
    update_env: bool = True
) -> str:
    """Import SUMO scenario, convert to EdgeFlow AI Topology Contract JSON, and generate .sumocfg."""
    if preset:
        if preset not in PRESET_URLS:
            raise ValueError(f"Unknown preset '{preset}'. Available presets: {list(PRESET_URLS.keys())}")
        preset_info = PRESET_URLS[preset]
        scenario_id = scenario_id or preset_info["scenario_id"]
        net_url = preset_info["net"]
        rou_url = preset_info["rou"]

        target_dir = ROOT_DIR / "services" / "simulator" / "sumo_configs" / scenario_id
        target_dir.mkdir(parents=True, exist_ok=True)

        local_net = target_dir / f"{scenario_id}.net.xml"
        local_rou = target_dir / f"{scenario_id}.rou.xml"

        if not download_file(net_url, local_net):
            raise RuntimeError(f"Could not download net file for preset {preset}")
        if not download_file(rou_url, local_rou):
            logger.warning(f"Could not download rou file from {rou_url}. Generating default route file at {local_rou}...")
            local_rou.write_text('<?xml version="1.0" encoding="UTF-8"?>\n<routes>\n</routes>\n', encoding="utf-8")

    elif net_path:
        local_net = Path(net_path).resolve()
        if not local_net.exists():
            raise FileNotFoundError(f"Input SUMO .net.xml file not found: {net_path}")
        scenario_id = scenario_id or local_net.stem.replace(".net", "")
        target_dir = ROOT_DIR / "services" / "simulator" / "sumo_configs" / scenario_id
        target_dir.mkdir(parents=True, exist_ok=True)

        if rou_path and Path(rou_path).exists():
            local_rou = Path(rou_path).resolve()
        else:
            local_rou = target_dir / f"{scenario_id}.rou.xml"
            local_rou.write_text('<?xml version="1.0" encoding="UTF-8"?>\n<routes>\n</routes>\n', encoding="utf-8")

    else:
        raise ValueError("Must specify either --preset or --net")

    # 1. Convert SUMO .net.xml to EdgeFlow AI Topology Contract JSON
    logger.info(f"Parsing SUMO network XML and generating topology JSON for '{scenario_id}'...")
    xml_content = local_net.read_text(encoding="utf-8")
    topology = SumoNetworkConverter.parse_net_xml(xml_content, topology_id=scenario_id)

    topology_out = ROOT_DIR / "contracts" / "topology" / f"{scenario_id}.json"
    topology_out.parent.mkdir(parents=True, exist_ok=True)
    with open(topology_out, "w", encoding="utf-8") as f:
        json.dump(topology, f, indent=2, ensure_ascii=False)
    logger.info(f"Successfully generated Topology Contract: {topology_out} (Nodes: {len(topology['nodes'])})")

    # 2. Generate .sumocfg in services/simulator/sumo_configs/<scenario_id>.sumocfg
    sumocfg_out = ROOT_DIR / "services" / "simulator" / "sumo_configs" / f"{scenario_id}.sumocfg"
    generate_sumocfg(scenario_id, local_net, local_rou, sumocfg_out)

    # 3. Update .env if requested
    if update_env:
        update_env_file(ROOT_DIR / ".env", scenario_id)

    logger.info(f"SUMO Scenario '{scenario_id}' imported successfully!")
    logger.info(f"EDGEFLOW_TOPOLOGY in .env updated to: {scenario_id}")
    return scenario_id


def main():
    parser = argparse.ArgumentParser(description="Import SUMO Traffic Scenario (RESCO / Open Scenarios) into EdgeFlow AI.")
    parser.add_argument("--preset", choices=list(PRESET_URLS.keys()), help="Preset scenario to download from public repositories")
    parser.add_argument("--net", help="Path to local SUMO .net.xml file")
    parser.add_argument("--rou", help="Path to local SUMO .rou.xml file")
    parser.add_argument("--scenario-id", help="Custom scenario ID name")
    parser.add_argument("--no-env", action="store_true", help="Do not update .env file with EDGEFLOW_TOPOLOGY")

    args = parser.parse_args()
    try:
        import_scenario(
            preset=args.preset,
            net_path=args.net,
            rou_path=args.rou,
            scenario_id=args.scenario_id,
            update_env=not args.no_env
        )
    except Exception as e:
        logger.error(f"Error importing SUMO scenario: {e}")
        sys.exit(1)


if __name__ == "__main__":
    main()
