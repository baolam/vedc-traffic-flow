#!/usr/bin/env python3
"""
EdgeFlow AI — Experiment Execution Pipeline
Automation script to run SUMO simulations, configure vehicle raster assets/fleet compositions,
and compute comprehensive traffic performance metrics (tripinfo, summary, emissions).

Usage:
    python experiments/run_experiment_pipeline.py [--dir experiments/example] [--gui] [--seed 42]
"""

import os
import sys
import argparse
import subprocess
import shutil
import xml.etree.ElementTree as ET
from pathlib import Path
import csv
from typing import Dict, Any, Optional, Tuple


def find_repo_root() -> Path:
    """Locate repository root directory."""
    curr = Path(__file__).resolve().parent
    for p in [curr] + list(curr.parents):
        if (p / "contracts").is_dir() or (p / "services").is_dir():
            return p
    return curr.parent


def find_sumo_binary(use_gui: bool = False, custom_path: Optional[str] = None) -> str:
    """Auto-detect SUMO binary executable."""
    binary_name = "sumo-gui" if use_gui else "sumo"
    if sys.platform == "win32":
        binary_name += ".exe"

    if custom_path and os.path.exists(custom_path):
        return custom_path

    # Check PATH
    found = shutil.which("sumo-gui" if use_gui else "sumo")
    if found:
        return found

    # Check common fallback locations on Windows / Linux
    fallbacks = [
        Path(r"D:\sumo\bin") / binary_name,
        Path(r"C:\Program Files (x86)\Eclipse\Sumo\bin") / binary_name,
        Path(r"C:\Program Files\Eclipse\Sumo\bin") / binary_name,
        Path("/usr/bin") / ("sumo-gui" if use_gui else "sumo"),
        Path("/usr/local/bin") / ("sumo-gui" if use_gui else "sumo"),
    ]
    for fb in fallbacks:
        if fb.exists():
            return str(fb)

    raise FileNotFoundError(
        f"SUMO executable '{binary_name}' not found. "
        "Please install Eclipse SUMO or set the SUMO_HOME / PATH environment variable."
    )


def setup_vehicle_images(exp_dir: Path, seed: int = 42) -> bool:
    """Configure vehicle raster images and realistic fleet distribution in routes.rou.xml."""
    import random

    route_file = exp_dir / "routes.rou.xml"
    if not route_file.exists():
        print(f"[!] Warning: Route file '{route_file.name}' not found. Skipping vehicle image setup.")
        return False

    vehicles_dir = exp_dir / "vehicles"
    if not vehicles_dir.exists():
        print(f"[!] Warning: Vehicles image folder '{vehicles_dir}' not found. Skipping vehicle image setup.")
        return False

    try:
        tree = ET.parse(route_file)
        root = tree.getroot()

        # Remove existing vTypes if redefining
        ids = {"motorcycle", "car", "taxi", "bus", "truck"}
        for e in list(root):
            if e.tag == "vType" and e.get("id") in ids:
                root.remove(e)

        types = [
            ("motorcycle", "motorcycle", "motorcycle.png", "2.2", "0.9", "3.0", "5.0", "50"),
            ("car", "passenger", "car.png", "4.5", "1.8", "2.6", "4.5", "50"),
            ("taxi", "taxi", "taxi.png", "4.5", "1.8", "2.6", "4.5", "50"),
            ("bus", "bus", "bus.png", "12", "2.5", "1.2", "4.0", "40"),
            ("truck", "truck", "truck.png", "8", "2.4", "1.5", "4.0", "40"),
        ]

        for vid, vclass, image, length, width, accel, decel, maxspeed in reversed(types):
            ET.SubElement(root, "vType", {
                "id": vid,
                "vClass": vclass,
                "guiShape": "passenger" if vid in {"car", "taxi"} else vid,
                "imgFile": f"vehicles/{image}",
                "length": length,
                "width": width,
                "minGap": "1.5" if vid == "motorcycle" else "2.5",
                "accel": accel,
                "decel": decel,
                "maxSpeed": maxspeed,
                "color": "1,1,1",
            })

        random.seed(seed)
        weights = ["motorcycle"] * 65 + ["car"] * 25 + ["taxi"] * 4 + ["bus"] * 3 + ["truck"] * 3

        count = 0
        for tag in ("vehicle", "flow"):
            for v in root.findall(tag):
                v.set("type", random.choice(weights))
                count += 1

        ET.indent(tree, space="    ")
        tree.write(route_file, encoding="UTF-8", xml_declaration=True)
        print(f"[✓] Configured vehicle raster images and fleet composition for {count} elements (seed={seed}).")
        return True
    except Exception as err:
        print(f"[!] Error setting up vehicle images: {err}")
        return False


def run_sumo_simulation(exp_dir: Path, sumo_bin: str, use_gui: bool = False) -> Tuple[bool, Path, Path, Path]:
    """Execute SUMO simulation and output telemetry XMLs."""
    sumocfg = exp_dir / "simulation.sumocfg"
    if not sumocfg.exists():
        # Fallback search for any .sumocfg in exp_dir
        cfgs = list(exp_dir.glob("*.sumocfg"))
        if not cfgs:
            raise FileNotFoundError(f"No .sumocfg file found in '{exp_dir}'")
        sumocfg = cfgs[0]

    tripinfo_out = exp_dir / "tripinfo.xml"
    summary_out = exp_dir / "summary.xml"
    emission_out = exp_dir / "emission.xml"

    cmd = [
        sumo_bin,
        "-c", str(sumocfg),
        "--tripinfo-output", str(tripinfo_out),
        "--summary-output", str(summary_out),
        "--emission-output", str(emission_out),
    ]

    print(f"\n[🚀] Launching SUMO: {' '.join(cmd)}")
    result = subprocess.run(cmd, cwd=str(exp_dir))

    if result.returncode != 0:
        print(f"[❌] SUMO execution failed with exit code {result.returncode}")
        return False, tripinfo_out, summary_out, emission_out

    print(f"[✓] SUMO simulation completed successfully.")
    return True, tripinfo_out, summary_out, emission_out


def compute_and_export_metrics(exp_dir: Path, trip_file: Path, summary_file: Path, emission_file: Path) -> Path:
    """Parse output XMLs and calculate performance metrics, exporting to metrics.csv."""
    def safe_float(val, default=0.0):
        try:
            return float(val)
        except Exception:
            return default

    # 1. Trip metrics
    n = 0
    arrived = 0
    sum_duration = sum_wait = sum_speed = sum_timeloss = sum_route = 0.0
    if trip_file.exists():
        for e in ET.parse(trip_file).getroot().iter("tripinfo"):
            n += 1
            arrived += 1
            duration = safe_float(e.get("duration"))
            route_len = safe_float(e.get("routeLength"))
            sum_duration += duration
            sum_wait += safe_float(e.get("waitingTime"))
            sum_speed += (route_len / duration) if duration > 0 else 0.0
            sum_timeloss += safe_float(e.get("timeLoss"))
            sum_route += route_len

    avg_travel = sum_duration / n if n else 0.0
    avg_wait = sum_wait / n if n else 0.0
    avg_speed_ms = sum_speed / n if n else 0.0
    avg_speed_kmh = avg_speed_ms * 3.6
    avg_timeloss = sum_timeloss / n if n else 0.0

    # 2. Summary teleports
    teleports = 0
    if summary_file.exists():
        root = ET.parse(summary_file).getroot()
        for s in root.iter("step"):
            teleports = int(safe_float(s.get("teleports")))
        if teleports == 0:
            for e in root.iter():
                if "teleport" in e.tag.lower():
                    teleports = max(teleports, int(safe_float(e.get("teleports"))))

    # 3. Emissions
    co2 = fuel = 0.0
    emission_records = 0
    if emission_file.exists():
        for e in ET.parse(emission_file).getroot().iter("vehicle"):
            co2 += safe_float(e.get("CO2"))
            fuel += safe_float(e.get("fuel"))
            emission_records += 1

    # 4. Write CSV
    fields = [
        "vehicles_arrived", "average_travel_time_s", "average_waiting_time_s",
        "average_speed_kmh", "average_time_loss_s", "throughput_vehicles",
        "teleports", "total_co2_mg", "total_fuel_ml", "emission_vehicle_steps"
    ]
    values = [
        arrived, round(avg_travel, 3), round(avg_wait, 3), round(avg_speed_kmh, 3),
        round(avg_timeloss, 3), arrived, teleports, round(co2, 3), round(fuel, 3),
        emission_records
    ]

    csv_file = exp_dir / "metrics.csv"
    with csv_file.open("w", newline="", encoding="utf-8-sig") as fp:
        w = csv.writer(fp)
        w.writerow(fields)
        w.writerow(values)

    print("\n" + "=" * 55)
    print(" 📊 EDGEFLOW AI — EXPERIMENT PERFORMANCE METRICS")
    print("=" * 55)
    for k, v in zip(fields, values):
        print(f" • {k:<25}: {v}")
    print("=" * 55)
    print(f"[✓] Metrics successfully exported to: {csv_file}\n")
    return csv_file


def main():
    repo_root = find_repo_root()
    default_exp_dir = repo_root / "experiments" / "example"

    parser = argparse.ArgumentParser(description="EdgeFlow AI Experiment Execution Pipeline")
    parser.add_argument("--dir", type=str, default=str(default_exp_dir), help="Path to experiment directory")
    parser.add_argument("--gui", action="store_true", help="Launch SUMO-GUI instead of headless SUMO")
    parser.add_argument("--seed", type=int, default=42, help="Random seed for vehicle distribution")
    parser.add_argument("--skip-setup", action="store_true", help="Skip vehicle raster image configuration")
    parser.add_argument("--sumo-binary", type=str, default=None, help="Custom path to SUMO binary")

    args = parser.parse_args()

    exp_dir = Path(args.dir).resolve()
    if not exp_dir.exists():
        print(f"[❌] Error: Experiment directory '{exp_dir}' does not exist.")
        sys.exit(1)

    print(f"=======================================================")
    print(f" 🚥 EDGEFLOW AI EXPERIMENT PIPELINE")
    print(f" Target Directory: {exp_dir}")
    print(f" GUI Mode        : {args.gui}")
    print(f" Random Seed     : {args.seed}")
    print(f"=======================================================")

    # Step 1: Vehicle Image Setup
    if not args.skip_setup:
        setup_vehicle_images(exp_dir, seed=args.seed)

    # Step 2: Auto-detect SUMO & Run
    sumo_bin = find_sumo_binary(use_gui=args.gui, custom_path=args.sumo_binary)
    success, trip_out, summary_out, emission_out = run_sumo_simulation(exp_dir, sumo_bin, use_gui=args.gui)

    if not success:
        sys.exit(1)

    # Step 3: Calculate Metrics
    compute_and_export_metrics(exp_dir, trip_out, summary_out, emission_out)


if __name__ == "__main__":
    main()
