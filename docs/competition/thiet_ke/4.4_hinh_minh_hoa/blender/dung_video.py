"""Render video demo + nhãn YOLO tự sinh từ cảnh Blender (camera bao quát cả J1 và J2).

Chạy (đã có kịch bản từ video_mo_phong.py):
  /Applications/Blender.app/Contents/MacOS/Blender -b -P dung_video.py -- \\
      --scenario ../video_demo/kich_ban_train.json --frames-dir <thư mục khung hình> \\
      --labels ../video_demo/nhan_train.json --rois ../video_demo/rois_video.json [--first 0 --last 1499 --step 1]

Mỗi khung: đặt xe theo kịch bản, render EEVEE 1280 × 720, ghi hộp bao 2D của từng xe (chiếu 8 đỉnh hộp 3D qua
camera) và chiếu 4 đỉnh mỗi ROI (bo_tri.roi_rect) xuống khung hình. Cảnh dựng bằng cờ --video của dung_canh.py
(không camera trên trụ, 2 trụ cao 20 cm). Video là render 3D mô phỏng, vòng hở: xe không dừng theo đèn LED thật.
"""
from __future__ import annotations

import argparse
import json
import math
import os
import sys
import time

import bpy
from bpy_extras.object_utils import world_to_camera_view
from mathutils import Vector

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import dung_canh as D  # noqa: E402
import linh_kien_3d as K  # noqa: E402
from linh_kien_3d import MM  # noqa: E402

L, G = D.L, D.G
RES = (1280, 720)
CAR_BOX = (75.0, 31.0, 25.5)     # dài × rộng × cao của xe (mm), khớp K.build_car
HIDDEN_Z = -50.0                 # m: xe ngoài kịch bản được cất xuống dưới bàn


def parse_args() -> argparse.Namespace:
    argv = sys.argv[sys.argv.index("--") + 1:] if "--" in sys.argv else []
    ap = argparse.ArgumentParser()
    ap.add_argument("--scenario", required=True)
    ap.add_argument("--frames-dir", required=True)
    ap.add_argument("--labels", required=True)
    ap.add_argument("--rois", default="")
    ap.add_argument("--hud-anchors", default="")
    ap.add_argument("--first", type=int, default=0)
    ap.add_argument("--last", type=int, default=-1)
    ap.add_argument("--step", type=int, default=1)
    ap.add_argument("--samples", type=int, default=24)
    ap.add_argument("--no-render", action="store_true", help="chỉ sinh nhãn/ROI, không render ảnh")
    ap.add_argument("--save", default="")
    return ap.parse_args(argv)


def setup_eevee(samples: int) -> None:
    sc = bpy.context.scene
    sc.render.engine = "BLENDER_EEVEE"
    sc.eevee.taa_render_samples = samples
    sc.render.resolution_x, sc.render.resolution_y = RES
    sc.render.resolution_percentage = 100
    sc.render.image_settings.file_format = "JPEG"
    sc.render.image_settings.quality = 95
    try:
        sc.view_settings.view_transform = "AgX"
        sc.view_settings.look = "AgX - Punchy"
    except TypeError:
        pass
    w = bpy.data.worlds.new("World")
    sc.world = w
    w.use_nodes = True
    bg = w.node_tree.nodes.get("Background")
    bg.inputs[0].default_value = (*K.hex_rgb("#C9C4BB"), 1.0)
    bg.inputs[1].default_value = 0.30


def build_video_scene() -> None:
    L.CAMERA_NODES = ()
    m = K.M()
    D.build_base(m)
    for node in L.JUNCTIONS:
        D.build_pole(node, m)
    D.build_pi_cabinet(m)
    D.build_trees()
    for node in G.NODES:
        D.node_electronics(node, m)
    D.build_power(m)
    for o in bpy.data.objects:
        if o.name.startswith(("adapter", "pi_cable")) or "_cable_flat" in o.name:
            o.hide_render = True          # cáp dán trên mặt đường chỉ có trên sa bàn thật, không cần trong video
    D.lights()


LED_AXIS = {"N": "NS", "S": "NS", "E": "EW", "W": "EW"}


def make_led_materials() -> dict:
    """Mỗi (nút, trục, màu) một vật liệu riêng cho các đèn LED của cụm 4 mặt, để bật/tắt theo từng khung."""
    mats = {}
    for node in L.JUNCTIONS:
        for axis in ("NS", "EW"):
            for c in "RYG":
                m = K.mat(f"anim_{node}_{axis}_{c}", "#FFFFFF", 0.2, emit=K.LED_LIT[c], strength=0.0)
                mats[(node, axis, c)] = m.node_tree.nodes.get("Principled BSDF")
        for key, axis in LED_AXIS.items():
            for c in "RYG":
                for part in ("led", "dome"):
                    o = bpy.data.objects.get(f"signal_{node}_{key}_{part}{c}")
                    if o is not None:
                        o.data.materials[0] = bpy.data.materials[f"anim_{node}_{axis}_{c}"]
    return mats


def set_leds(mats: dict, hud_frame: dict) -> None:
    for node, st in hud_frame["nodes"].items():
        for axis in ("NS", "EW"):
            for c in "RYG":
                bsdf = mats[(node, axis, c)]
                on = st[axis] == c
                bsdf.inputs["Emission Strength"].default_value = 38.0 if on else 0.0
                bsdf.inputs["Base Color"].default_value = (1.0, 1.0, 1.0, 1.0) if on else (*K.hex_rgb(K.LED_OFF[c]), 1.0)


def make_cars(tracks: list[dict]) -> dict[int, bpy.types.Object]:
    cars = {}
    for tr in tracks:
        root = K.build_car(f"car{tr['id']:03d}", D.CAR_COLORS[tr["color"] % len(D.CAR_COLORS)])
        root.location = (0, 0, HIDDEN_Z)
        root.rotation_euler = (0, 0, math.radians(tr["heading"]))
        cars[tr["id"]] = root
    return cars


def place_cars(tracks: list[dict], cars: dict, frame: int) -> list[dict]:
    """Đặt xe cho `frame`; trả về các xe đang có mặt: id, vị trí, hướng."""
    live = []
    for tr in tracks:
        k = frame - tr["f0"]
        root = cars[tr["id"]]
        if 0 <= k < len(tr["x"]) and tr["vis"][k]:
            x, y = tr["x"][k], tr["y"][k]
            root.location = (x * MM, y * MM, D.Z_TOP * MM)
            live.append({"id": tr["id"], "x": x, "y": y, "heading": tr["heading"], "lane": tr["lane"],
                         "p": tr["p"][k]})
        else:
            root.location = (0, 0, HIDDEN_Z)
    return live


def bbox_px(cam, car: dict) -> tuple[float, float, float, float, float] | None:
    """Hộp bao 2D (x0, y0, x1, y1, tỉ lệ còn trong khung) của xe; None nếu ngoài khung."""
    sc = bpy.context.scene
    c, s = math.cos(math.radians(car["heading"])), math.sin(math.radians(car["heading"]))
    xs, ys = [], []
    for dx in (-CAR_BOX[0] / 2, CAR_BOX[0] / 2):
        for dy in (-CAR_BOX[1] / 2, CAR_BOX[1] / 2):
            for z in (0.0, CAR_BOX[2]):
                p = Vector(((car["x"] + dx * c - dy * s) * MM, (car["y"] + dx * s + dy * c) * MM,
                            (D.Z_TOP + z) * MM))
                co = world_to_camera_view(sc, cam, p)
                if co.z <= 0:
                    return None
                xs.append(co.x * RES[0])
                ys.append((1 - co.y) * RES[1])
    x0, x1, y0, y1 = min(xs), max(xs), min(ys), max(ys)
    full = max((x1 - x0) * (y1 - y0), 1e-6)
    cx0, cx1, cy0, cy1 = max(x0, 0), min(x1, RES[0]), max(y0, 0), min(y1, RES[1])
    if cx1 <= cx0 or cy1 <= cy0:
        return None
    return cx0, cy0, cx1, cy1, (cx1 - cx0) * (cy1 - cy0) / full


def project_hud_anchors(cam) -> dict:
    """Vị trí 2D (khung 1280 × 720) của các điểm gắn chú thích: biển đếm giây bên cạnh vạch dừng của 4 hướng."""
    sc = bpy.context.scene
    sd = L.stop_dist()
    out = {}
    for node, (jx, jy) in L.JUNCTIONS.items():
        pts = {"N": (jx - 90, jy + sd + 24), "S": (jx + 90, jy - sd - 24),
               "E": (jx + sd + 26, jy + 88), "W": (jx - sd - 26, jy - 88), "centre": (jx, jy)}
        out[node] = {}
        for k, (x, y) in pts.items():
            co = world_to_camera_view(sc, cam, Vector((x * MM, y * MM, (D.Z_TOP + 28) * MM)))
            out[node][k] = [round(co.x * RES[0], 1), round((1 - co.y) * RES[1], 1)]
    return out


def project_rois(cam) -> dict:
    sc = bpy.context.scene
    nodes: dict[str, dict] = {}
    for node in L.JUNCTIONS:
        polys = {}
        for appr in "NSEW":
            pts = []
            for x, y in L.roi_rect(node, appr):
                co = world_to_camera_view(sc, cam, Vector((x * MM, y * MM, D.Z_TOP * MM)))
                pts.append([int(round(min(max(co.x * RES[0], 0), RES[0]))),
                            int(round(min(max((1 - co.y) * RES[1], 0), RES[1])))])
            polys[f"{node}_{appr}_IN"] = pts
        nodes[node] = polys
    return {"camera": "blender_overview_tilt_render", "frame_size": list(RES), "nodes": nodes}


def main() -> None:
    args = parse_args()
    scen = json.load(open(args.scenario, encoding="utf-8"))
    tracks = scen["tracks"]
    last = scen["frames"] - 1 if args.last < 0 else min(args.last, scen["frames"] - 1)
    bpy.ops.wm.read_factory_settings(use_empty=True)
    setup_eevee(args.samples)
    build_video_scene()
    cam = D.make_camera("cam_video", D.VIEWS["overview_tilt"])
    bpy.context.scene.camera = cam
    cars = make_cars(tracks)
    leds = make_led_materials()
    hud = scen.get("hud", [])
    bpy.context.view_layer.update()
    if args.save:
        bpy.ops.wm.save_as_mainfile(filepath=args.save)
    if args.hud_anchors:
        json.dump(project_hud_anchors(cam), open(args.hud_anchors, "w", encoding="utf-8"), indent=1)
    if args.rois:
        json.dump(project_rois(cam), open(args.rois, "w", encoding="utf-8"), indent=2)
    os.makedirs(args.frames_dir, exist_ok=True)
    labels: dict[str, list] = {}
    t0 = time.time()
    for f in range(args.first, last + 1, args.step):
        bpy.context.scene.frame_set(f)
        live = place_cars(tracks, cars, f)
        if hud:
            set_leds(leds, hud[min(f, len(hud) - 1)])
        bpy.context.view_layer.update()
        boxes = []
        for car in live:
            b = bbox_px(cam, car)
            if b and b[4] >= 0.6 and (b[2] - b[0]) >= 8 and (b[3] - b[1]) >= 8:
                boxes.append([round(v, 1) for v in b[:4]] + [car["id"]])
        labels[str(f)] = boxes
        if not args.no_render:
            bpy.context.scene.render.filepath = os.path.join(args.frames_dir, f"f{f:05d}.jpg")
            bpy.ops.render.render(write_still=True)
        if (f - args.first) % (50 * args.step) == 0:
            print(f"[video] frame {f}/{last}  {time.time() - t0:.0f}s", flush=True)
    json.dump({"frame_size": list(RES), "labels": labels}, open(args.labels, "w", encoding="utf-8"),
              separators=(",", ":"))
    print(f"[video] xong {len(labels)} khung trong {time.time() - t0:.0f}s")


if __name__ == "__main__":
    main()
