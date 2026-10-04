"""
EdgeFlow AI - ROI calibration tool for one camera covering several intersections.

Workflow (camera mounted on its final rigid stand, focus locked):
  1. On the Pi (headless):  python services/vision/roi_calibrate.py capture --video picamera \
                               --width 1280 --height 720 --lens-position 2.0 --out frame.png
  2. Copy frame.png to a machine with a display, then draw one polygon per approach:
                            python services/vision/roi_calibrate.py draw --image frame.png \
                               --nodes J1,J2 --out services/vision/rois/tabletop.json
     Left click adds a point, Enter closes the polygon, u undoes, Esc aborts.
  3. Check and render an overlay for the report:
                            python services/vision/roi_calibrate.py check --config services/vision/rois/tabletop.json \
                               --nodes J1,J2 --image frame.png --out roi_overlay.png
  4. Run vision with VISION_NODE_IDS=J1,J2 and ROI_CONFIG_PATH=<the JSON file>.
Recalibrate whenever the camera moves.
"""

import argparse
import sys
import time
from pathlib import Path
from typing import Dict, List, Optional

import cv2
import numpy as np

CURR_DIR = Path(__file__).resolve().parent
if str(CURR_DIR) not in sys.path:
    sys.path.insert(0, str(CURR_DIR))

from roi_config import RoiConfig, load_roi_config, save_roi_config, validate_against_topology  # noqa: E402
from video_source import create_video_source  # noqa: E402
from vision_contracts_helper import load_topology  # noqa: E402

NODE_COLORS = [(0, 200, 255), (255, 120, 0), (0, 255, 120), (200, 0, 255)]


def capture_frame(video: str, width: int, height: int, out: Path,
                  lens_position: Optional[float] = None, warmup_frames: int = 10) -> np.ndarray:
    """Grabs one frame after a short warm-up (auto exposure settles) and writes it to disk."""
    source = create_video_source(video, width=width, height=height, lens_position=lens_position)
    try:
        frame = None
        for _ in range(max(warmup_frames, 1)):
            ok, candidate = source.read_frame()
            if ok and candidate is not None:
                frame = candidate
            time.sleep(0.05)
    finally:
        source.release()
    if frame is None:
        raise RuntimeError(f"No frame could be read from video source '{video}'")
    if frame.shape[:2] != (height, width):
        frame = cv2.resize(frame, (width, height), interpolation=cv2.INTER_AREA)
    if not cv2.imwrite(str(out), frame):
        raise RuntimeError(f"Could not write {out}")
    return frame


def render_overlay(image: np.ndarray, config: RoiConfig) -> np.ndarray:
    """Draws every calibrated polygon with its approach ID onto a copy of the image."""
    if image.shape[:2] != (config.frame_size[1], config.frame_size[0]):
        image = cv2.resize(image, config.frame_size, interpolation=cv2.INTER_AREA)
    overlay = image.copy()
    for index, (node_id, approaches) in enumerate(sorted(config.nodes.items())):
        color = NODE_COLORS[index % len(NODE_COLORS)]
        for approach_id, polygon in approaches.items():
            points = np.array(polygon, np.int32)
            cv2.fillPoly(overlay, [points], color)
            cv2.polylines(image, [points], True, color, 2)
            cx, cy = points.mean(axis=0).astype(int)
            cv2.putText(image, approach_id, (int(cx) - 30, int(cy)), cv2.FONT_HERSHEY_SIMPLEX, 0.45,
                        (255, 255, 255), 1, cv2.LINE_AA)
    return cv2.addWeighted(overlay, 0.25, image, 0.75, 0)


def draw_polygons(image: np.ndarray, approach_order: List[str]) -> Dict[str, List[List[int]]]:
    """Interactive OpenCV window: one polygon per approach ID, in the given order."""
    window = "EdgeFlow ROI calibration"
    polygons: Dict[str, List[List[int]]] = {}
    current: List[List[int]] = []

    def on_mouse(event, x, y, flags, param):
        if event == cv2.EVENT_LBUTTONDOWN:
            current.append([int(x), int(y)])

    cv2.namedWindow(window, cv2.WINDOW_NORMAL)
    cv2.setMouseCallback(window, on_mouse)
    try:
        for approach_id in approach_order:
            current.clear()
            while True:
                canvas = image.copy()
                for done in polygons.values():
                    cv2.polylines(canvas, [np.array(done, np.int32)], True, (0, 200, 255), 2)
                if current:
                    cv2.polylines(canvas, [np.array(current, np.int32)], False, (0, 255, 0), 2)
                cv2.putText(canvas, f"{approach_id}: click points, Enter=done, u=undo, Esc=abort",
                            (10, 25), cv2.FONT_HERSHEY_SIMPLEX, 0.6, (0, 255, 0), 2, cv2.LINE_AA)
                cv2.imshow(window, canvas)
                key = cv2.waitKey(30) & 0xFF
                if key in (13, 10) and len(current) >= 3:
                    polygons[approach_id] = [list(p) for p in current]
                    break
                if key == ord("u") and current:
                    current.pop()
                if key == 27:
                    raise KeyboardInterrupt("ROI calibration aborted")
    finally:
        cv2.destroyWindow(window)
    return polygons


def topology_approaches(topology_id: str, node_ids: List[str]) -> Dict[str, List[str]]:
    topo_nodes = {n["node_id"]: n for n in load_topology(topology_id).get("nodes", [])}
    missing = [n for n in node_ids if n not in topo_nodes]
    if missing:
        raise ValueError(f"Nodes {missing} are not in topology {topology_id}")
    return {n: list(topo_nodes[n].get("approaches", [])) for n in node_ids}


def parse_args(argv: Optional[List[str]] = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="EdgeFlow AI ROI calibration")
    sub = parser.add_subparsers(dest="command", required=True)

    cap = sub.add_parser("capture", help="grab one frame from the camera")
    cap.add_argument("--video", default="picamera")
    cap.add_argument("--width", type=int, default=1280)
    cap.add_argument("--height", type=int, default=720)
    cap.add_argument("--lens-position", type=float)
    cap.add_argument("--out", type=Path, default=Path("frame.png"))

    draw = sub.add_parser("draw", help="draw approach polygons on a captured frame")
    draw.add_argument("--image", type=Path, required=True)
    draw.add_argument("--nodes", required=True, help="comma-separated, e.g. J1,J2")
    draw.add_argument("--topology", default="four_intersection_v1")
    draw.add_argument("--camera", default="tabletop_cam")
    draw.add_argument("--out", type=Path, required=True)

    check = sub.add_parser("check", help="validate a ROI file and optionally render an overlay")
    check.add_argument("--config", type=Path, required=True)
    check.add_argument("--nodes", required=True)
    check.add_argument("--topology", default="four_intersection_v1")
    check.add_argument("--image", type=Path)
    check.add_argument("--out", type=Path)
    return parser.parse_args(argv)


def main(argv: Optional[List[str]] = None) -> int:
    args = parse_args(argv)
    if args.command == "capture":
        frame = capture_frame(args.video, args.width, args.height, args.out, args.lens_position)
        print(f"Saved {args.out} ({frame.shape[1]}x{frame.shape[0]})")
        return 0

    node_ids = [n.strip() for n in args.nodes.split(",") if n.strip()]
    if args.command == "draw":
        image = cv2.imread(str(args.image))
        if image is None:
            raise FileNotFoundError(args.image)
        order = topology_approaches(args.topology, node_ids)
        nodes = {node_id: draw_polygons(image, approaches) for node_id, approaches in order.items()}
        save_roi_config(args.out, args.camera, (image.shape[1], image.shape[0]), nodes)
        print(f"Saved {args.out}")
        return 0

    config = load_roi_config(args.config)
    validate_against_topology(config, load_topology(args.topology), node_ids)
    print(f"OK: {args.config} covers {', '.join(node_ids)} at {config.frame_size[0]}x{config.frame_size[1]} "
          f"(sha256 {config.sha256})")
    if args.image and args.out:
        image = cv2.imread(str(args.image))
        if image is None:
            raise FileNotFoundError(args.image)
        cv2.imwrite(str(args.out), render_overlay(image, config))
        print(f"Overlay written to {args.out}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
