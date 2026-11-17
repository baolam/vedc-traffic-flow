"""Render local before/after lanes and complete 12 m bus waiting envelopes."""
from pathlib import Path
import sys
import json
import math
import xml.etree.ElementTree as ET

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib.patches import Polygon

from contracts.hcm_qualification_v3 import REPAIR_ORDER
from src.simulation.hcm_repair import footprint


def main():
    output = ROOT / "artifacts/hcm-qualification-v3"
    status = json.loads((output / "repair/status.json").read_text())
    revision = (output / status["revision"] if "revision" in status else
                sorted((output / "repair/revisions").iterdir())[-1])
    source = ROOT / "networks/hcm_neighborhood_benchmark_v2/network.net.xml"
    roots = [ET.parse(p).getroot() for p in (source, revision / "network.net.xml")]
    topology = json.loads((ROOT / "contracts/topology/hcm_neighborhood_benchmark_v2.json").read_text())
    mapping = {n["node_id"]: n["sumo_tls_id"] for n in topology["nodes"]}
    destination = output / "repair/diagrams"
    destination.mkdir(exist_ok=True)
    for group in REPAIR_ORDER:
        junctions = {mapping[n] for n in group}
        centers = [(float(j.get("x")), float(j.get("y"))) for j in roots[0].findall("junction") if j.get("id") in junctions]
        limits = (min(x for x, y in centers)-27, max(x for x, y in centers)+27,
                  min(y for x, y in centers)-27, max(y for x, y in centers)+27)
        fig, axes = plt.subplots(1, 2, figsize=(12, 7), constrained_layout=True)
        for panel, (root, ax) in enumerate(zip(roots, axes)):
            lanes = {l.get("id"): l for e in root.findall("edge") for l in e.findall("lane")}
            continuation = {c.get("from"): c.get("via") for c in root.findall("connection") if c.get("via")}
            for e in root.findall("edge"):
                for lane in e.findall("lane"):
                    points = [tuple(map(float, xy.split(",")[:2])) for xy in lane.get("shape").split()]
                    internal = e.get("function") == "internal"
                    ax.plot(*zip(*points), color="#da7b19" if internal else "#43667e", lw=1 if internal else 2.5, alpha=.8)
            for c in root.findall("connection"):
                if c.get("tl") not in junctions or c.get("dir") == "t":
                    continue
                lane_id = c.get("via")
                if not lane_id:
                    continue
                lane = lanes[lane_id]
                if not continuation.get(lane_id.rsplit("_", 1)[0]):
                    continue
                points = [tuple(map(float, xy.split(",")[:2])) for xy in lane.get("shape").split()]
                p, q = points[-2:]
                angle = math.degrees(math.atan2(q[0]-p[0], q[1]-p[1]))
                ax.add_patch(Polygon(footprint(q, angle, 12, 2.5), facecolor="#c73531", edgecolor="#c73531", alpha=.15))
                ax.scatter(*q, color="#c73531", s=16, zorder=4)
            for canonical in group:
                node = root.find(f"junction[@id='{mapping[canonical]}']")
                ax.annotate(canonical, (float(node.get("x")), float(node.get("y"))),
                            xytext=(5, 5), textcoords="offset points", weight="bold",
                            bbox={"facecolor": "white", "alpha": .8, "edgecolor": "none"})
            ax.set(xlim=limits[:2], ylim=limits[2:], aspect="equal",
                   title="Imported v2" if panel == 0 else "Local v3 repair", xlabel="Local x (m)", ylabel="Local y (m)")
            ax.grid(alpha=.15)
        fig.suptitle(" / ".join(group) + ": internal waiting and bus footprints", fontsize=16)
        fig.supxlabel("Blue: roads · Orange: internal connectors · Red: interior waiting point and 12 × 2.5 m bus envelope\n"
                      "Rectangles show local tangent envelopes; actual curved-body collision endpoints remain in raw SUMO evidence.", fontsize=9)
        stem = destination / ("-".join(group)+"-before-after")
        fig.savefig(stem.with_suffix(".svg"))
        fig.savefig(stem.with_suffix(".png"), dpi=160)
        plt.close(fig)
    print(destination)


if __name__ == "__main__":
    main()
