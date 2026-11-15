"""
EdgeFlow AI - Per-camera ROI calibration file (one camera covering several intersections).

File format (JSON):
{
  "camera": "tabletop_cam_v1",              # free-form label
  "frame_size": [1280, 720],                # width, height the polygons were drawn on
  "nodes": {
    "J1": {"J1_N_IN": [[x, y], ...], "J1_S_IN": [...], "J1_E_IN": [...], "J1_W_IN": [...]},
    "J2": {...}
  }
}
Every approach of every configured node must have a polygon, so a missing ROI can never
silently become an empty queue. The file hash is reported in health messages as provenance.
"""

import hashlib
import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Dict, List, Sequence, Tuple, Union

Point = Tuple[int, int]
Polygon = Tuple[Point, ...]


@dataclass(frozen=True)
class RoiConfig:
    camera: str
    frame_size: Tuple[int, int]
    nodes: Dict[str, Dict[str, Polygon]]
    sha256: str


def _parse_polygon(raw: Any, frame_size: Tuple[int, int], where: str) -> Polygon:
    if not isinstance(raw, list) or len(raw) < 3:
        raise ValueError(f"{where}: polygon needs at least 3 [x, y] points")
    width, height = frame_size
    points = []
    for point in raw:
        if not (isinstance(point, (list, tuple)) and len(point) == 2):
            raise ValueError(f"{where}: each point must be [x, y]")
        x, y = int(point[0]), int(point[1])
        if not (0 <= x <= width and 0 <= y <= height):
            raise ValueError(f"{where}: point ({x}, {y}) is outside the {width}x{height} frame")
        points.append((x, y))
    return tuple(points)


def parse_roi_config(data: Dict[str, Any], sha256: str = "") -> RoiConfig:
    frame_size = data.get("frame_size")
    if not (isinstance(frame_size, list) and len(frame_size) == 2 and all(int(v) > 0 for v in frame_size)):
        raise ValueError("frame_size must be [width, height] with positive integers")
    size = (int(frame_size[0]), int(frame_size[1]))
    raw_nodes = data.get("nodes")
    if not isinstance(raw_nodes, dict) or not raw_nodes:
        raise ValueError("nodes must map node IDs to approach polygons")
    nodes = {}
    for node_id, approaches in raw_nodes.items():
        if not isinstance(approaches, dict) or not approaches:
            raise ValueError(f"node {node_id}: needs at least one approach polygon")
        nodes[node_id] = {
            approach_id: _parse_polygon(polygon, size, f"{node_id}/{approach_id}")
            for approach_id, polygon in approaches.items()
        }
    return RoiConfig(camera=str(data.get("camera", "")), frame_size=size, nodes=nodes, sha256=sha256)


def load_roi_config(path: Union[str, Path]) -> RoiConfig:
    raw = Path(path).read_bytes()
    return parse_roi_config(json.loads(raw), sha256=hashlib.sha256(raw).hexdigest())


def validate_against_topology(config: RoiConfig, topology: Dict[str, Any], node_ids: Sequence[str]) -> None:
    """Each requested node must exist in the topology and have exactly its approaches calibrated."""
    topo_nodes = {n["node_id"]: n for n in topology.get("nodes", [])}
    for node_id in node_ids:
        if node_id not in topo_nodes:
            raise ValueError(f"node {node_id} is not in topology {topology.get('topology_id')}")
        if node_id not in config.nodes:
            raise ValueError(f"node {node_id} has no ROI polygons in the calibration file")
        expected = set(topo_nodes[node_id].get("approaches", []))
        calibrated = set(config.nodes[node_id])
        if calibrated != expected:
            raise ValueError(f"node {node_id}: ROI approaches {sorted(calibrated)} "
                             f"do not match topology approaches {sorted(expected)}")


def save_roi_config(path: Union[str, Path], camera: str, frame_size: Tuple[int, int],
                    nodes: Dict[str, Dict[str, List[List[int]]]]) -> None:
    payload = {"camera": camera, "frame_size": list(frame_size), "nodes": nodes}
    parse_roi_config(payload)  # refuse to write an invalid file
    Path(path).write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")
