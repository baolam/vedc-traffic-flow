"""Render "dàn linh kiện chính" cho mục 3.4 (chạy riêng một lần Blender).

  /Applications/Blender.app/Contents/MacOS/Blender -b -P linh_kien_scene.py -- --samples 128
Kết quả: ../renders/raw/parts.png và khóa "parts" trong ../renders/anchors.json.
"""
from __future__ import annotations

import json
import math
import os
import sys

import bpy
from mathutils import Vector

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import dung_canh as D  # noqa: E402
import linh_kien_3d as K  # noqa: E402
from linh_kien_3d import MM, box, cyl, mat, plane  # noqa: E402

# (khóa, tâm x, tâm y) theo lưới 3 × 3, mm
GRID = {
    "router": (-185, 100), "pi5": (-5, 100), "adapter": (170, 100),
    "breadboard": (-180, -8), "esp32": (5, -5), "camera": (165, -5),
    "light": (-215, -112), "button": (-15, -100), "power": (160, -100),
}
LABEL_Y = {"router": -50, "pi5": -34, "adapter": -28, "breadboard": -33, "esp32": -18, "camera": -18,
           "light": -34, "button": -20, "power": -12}


def build_parts() -> dict:
    m = K.M()
    plane("studio_floor", 4000, 4000, (0, 0, 0), mat("studio", "#ECEAE6", 0.6))
    K.build_router("p_router", loc=(*GRID["router"], 0), rot_z=8)
    K.build_pi_board("p_pi5", loc=(*GRID["pi5"], 0), rot_z=-8)
    K.build_adapter("p_adapter", loc=(*GRID["adapter"], 0), rot_z=-10)
    ax, ay = GRID["adapter"]
    K.tube("p_adapter_cable", [(ax + 38, ay - 14, 8), (ax + 55, ay - 30, 4), (ax + 60, ay - 50, 3),
                               (ax + 45, ay - 62, 3)], 1.6, m["plastic_black"])
    bb = os.path.join(D.TEX, "breadboard.png")
    K.build_breadboard("p_breadboard", bb, loc=(*GRID["breadboard"], 0))
    K.build_esp32("p_esp32", loc=(*GRID["esp32"], 0))
    cam = K.build_camera_module("p_camera", loc=(GRID["camera"][0] - 30, GRID["camera"][1], 12))
    cam.rotation_euler = (math.radians(180), 0, math.radians(90))  # ống kính hướng lên
    box("p_camera_stand", (20, 20, 10), (GRID["camera"][0] - 30, GRID["camera"][1], 5), m["plastic_black"],
        bevel=1.0)
    K.build_ribbon("p_ribbon", 120, loc=(GRID["camera"][0] - 18, GRID["camera"][1] - 2, 0), rot_z=-6)
    # module rời (không cột, sẽ ốp vào cụm 4 mặt), đặt nằm ngửa: mặt LED hướng lên, đèn đỏ ở phía xa
    light = K.empty("p_light", loc=(*GRID["light"], 0.8))
    light.rotation_euler = (0, math.radians(-90), math.radians(-90))
    K.signal_face("p_light", "G", light, x0=0, zc=0)
    K.build_button("p_button", loc=(*GRID["button"], 0))
    px, py = GRID["power"]
    box("p_dcjack", (14, 9, 11), (px - 38, py, 5.5), m["plastic_black"], bevel=0.8)
    box("p_domino", (20, 10, 12), (px - 8, py, 6), m["domino"], bevel=0.6)
    for s in (-5, 5):
        cyl(f"p_screw{s}", 2.0, 1.0, (px - 8 + s, py, 12.4), m["shield"], segments=14)
    cyl("p_ptc", 4.2, 2.0, (px + 18, py, 4.2), m["ptc"], rot=(90, 0, 0))
    box("p_diode", (5.2, 2.6, 2.6), (px + 38, py, 1.3), m["plastic_black"], bevel=1.2)
    box("p_diode_band", (0.9, 2.7, 2.7), (px + 40, py, 1.3), mat("band", "#C8C8C8", 0.4))
    for s in (-1, 1):
        cyl(f"p_leg{s}", 0.35, 9, (px + 38 + s * 7.1, py, 1.3), m["shield"], rot=(0, 90, 0), segments=8)
    D.area_light("key", (-0.9, -0.8, 1.6), (0, 0, 0), 1.6, 120)
    D.area_light("fill", (1.1, -0.5, 1.1), (0, 0, 0), 1.6, 40)
    D.area_light("rim", (0.2, 1.3, 1.2), (0, 0, 0), 1.4, 55)
    return {k: (x, y + LABEL_Y[k], 0) for k, (x, y) in GRID.items()}


def main() -> None:
    argv = sys.argv[sys.argv.index("--") + 1:] if "--" in sys.argv else []
    samples = int(argv[argv.index("--samples") + 1]) if "--samples" in argv else 128
    percent = int(argv[argv.index("--percent") + 1]) if "--percent" in argv else 100
    D.reset_scene()
    D.setup_render(samples)
    bpy.context.scene.world.node_tree.nodes["Background"].inputs[0].default_value = (*K.hex_rgb("#ECEAE6"), 1)
    anchors = build_parts()
    v = dict(loc=(0, -330, 650), target=(-8, 14, 0), lens=38, res=(2400, 1600))
    cam = D.make_camera("cam_parts", v)
    sc = bpy.context.scene
    sc.camera = cam
    sc.render.resolution_x, sc.render.resolution_y = v["res"]
    sc.render.resolution_percentage = percent
    res = (v["res"][0] * percent // 100, v["res"][1] * percent // 100)
    bpy.context.view_layer.update()  # cập nhật matrix_world của camera trước khi chiếu điểm neo
    path = os.path.join(D.RENDERS, "anchors.json")
    data = json.load(open(path)) if os.path.exists(path) else {}
    data["parts"] = {"res": res, "anchors": D.project(cam, anchors, res)}
    json.dump(data, open(path, "w"), indent=1)
    sc.render.filepath = os.path.join(K.ensure_dir(os.path.join(D.RENDERS, "raw")), "parts.png")
    if "--no-render" not in argv:
        bpy.ops.render.render(write_still=True)
    D.tidy_viewport(center=(-0.01, 0.0, 0.03), distance=0.85)
    bpy.ops.wm.save_as_mainfile(filepath=os.path.join(HERE, "linh_kien.blend"))


if __name__ == "__main__":
    main()
