"""Dựng cảnh sa bàn EdgeFlow AI trong Blender và render các góc nhìn cho mục 4.4 / 3.4.

Chạy (từ thư mục này):
  python3 tao_texture.py                                   # texture (PIL, Python hệ thống)
  /Applications/Blender.app/Contents/MacOS/Blender -b -P dung_canh.py -- \
      --views hero,pole,closeup,cam_J1,cam_J2,top,front --samples 128
  /Applications/Blender.app/Contents/MacOS/Blender -b -P linh_kien_scene.py -- --samples 128

Kết quả: ../renders/raw/<view>.png, ../renders/anchors.json (tọa độ điểm neo để vẽ chú thích),
và sa_ban_edgeflow.blend (mở bằng Blender để chỉnh tiếp).
Bố trí lấy từ bo_tri.py. Đây là phương án ĐỀ XUẤT, chưa phải ảnh chụp sa bàn thật.
"""
from __future__ import annotations

import argparse
import json
import math
import os
import sys

import bpy
from bpy_extras.object_utils import world_to_camera_view
from mathutils import Euler, Vector

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import bo_tri_a0 as L  # noqa: E402
import linh_kien_3d as K  # noqa: E402
from linh_kien_3d import MM, box, cyl, empty, mat, plane, sphere, text, tube  # noqa: E402

TEX = os.path.join(HERE, "textures")
RENDERS = os.path.abspath(os.path.join(HERE, "..", "renders"))
Z_TOP = L.BASE_H + L.BOARD_T
APRON_Y = -L.BOARD_H / 2 - L.BASE_FRONT / 2 - 2      # tâm dải điện tử phía trước
LENS_Z = Z_TOP + L.CAMERA_H                          # cao độ ống kính (mm, tính từ mặt bàn)
CAR_COLORS = ["#C8102E", "#F4F4F2", "#1F4E99", "#9EA3A8", "#161616", "#E87722", "#F2C500", "#2E7D32",
              "#0FA3B1", "#7A2E8E"]
TREES = [(-470, 285), (-520, -320), (-140, 300), (120, 300), (-95, -300), (110, -255),
         (470, 290), (525, -320), (-480, -230)]


def parse_args() -> argparse.Namespace:
    argv = sys.argv[sys.argv.index("--") + 1:] if "--" in sys.argv else []
    ap = argparse.ArgumentParser()
    ap.add_argument("--views", default="hero,pole,closeup,cam_J1,cam_J2,top,front")
    ap.add_argument("--samples", type=int, default=128)
    ap.add_argument("--percent", type=int, default=100, help="tỉ lệ độ phân giải (thử nhanh: 30)")
    ap.add_argument("--no-render", action="store_true")
    ap.add_argument("--save", default=os.path.join(HERE, "sa_ban_edgeflow.blend"))
    return ap.parse_args(argv)


# ------------------------------------------------------------------ môi trường
def reset_scene() -> None:
    bpy.ops.wm.read_factory_settings(use_empty=True)


def setup_render(samples: int) -> None:
    sc = bpy.context.scene
    sc.render.engine = "CYCLES"
    prefs = bpy.context.preferences.addons["cycles"].preferences
    try:
        prefs.compute_device_type = "METAL"
        prefs.get_devices()
        for d in prefs.devices:
            d.use = d.type == "METAL"
        sc.cycles.device = "GPU"
    except Exception as exc:  # máy không có Metal thì chạy CPU
        print("GPU không dùng được, chạy CPU:", exc)
    sc.cycles.samples = samples
    sc.cycles.use_adaptive_sampling = True
    sc.cycles.use_denoising = True
    try:
        sc.cycles.denoiser = "OPENIMAGEDENOISE"
    except TypeError:
        pass
    sc.cycles.max_bounces = 8
    sc.render.image_settings.file_format = "PNG"
    sc.render.image_settings.color_depth = "8"
    try:
        sc.view_settings.view_transform = "AgX"
        sc.view_settings.look = "AgX - Punchy"
    except TypeError:
        pass

    w = bpy.data.worlds.new("World")
    sc.world = w
    try:
        w.use_nodes = True
    except AttributeError:
        pass
    bg = w.node_tree.nodes.get("Background")
    bg.inputs[0].default_value = (*K.hex_rgb("#C9C4BB"), 1.0)
    bg.inputs[1].default_value = 0.30


def area_light(name: str, loc, target, size: float, energy: float) -> None:
    ld = bpy.data.lights.new(name, "AREA")
    ld.size = size
    ld.energy = energy
    o = bpy.data.objects.new(name, ld)
    bpy.context.scene.collection.objects.link(o)
    o.location = Vector(loc)
    o.rotation_euler = (Vector(target) - o.location).to_track_quat("-Z", "Y").to_euler()


def lights() -> None:
    area_light("key", (-1.6, -1.3, 2.7), (0, -0.1, 0), 2.4, 260)
    area_light("fill", (2.2, -0.9, 1.7), (0, -0.1, 0.1), 2.2, 70)
    area_light("rim", (0.4, 2.4, 2.2), (0, 0, 0.2), 1.8, 110)


# ------------------------------------------------------------------ cảnh
def build_base(m: dict) -> None:
    plane("table", 14000, 14000, (0, 0, 0), mat("table", "#A99F92", 0.62))
    y0, y1 = -L.BOARD_H / 2 - L.BASE_FRONT, L.BOARD_H / 2 + L.BASE_BACK
    w = L.BOARD_W + 2 * L.BASE_MARGIN_X
    box("base", (w, y1 - y0, L.BASE_H), (0, (y0 + y1) / 2, L.BASE_H / 2), mat("base", "#F3F3F0", 0.5),
        bevel=3.0)
    box("board_foam", (L.BOARD_W, L.BOARD_H, L.BOARD_T), (0, 0, L.BASE_H + L.BOARD_T / 2),
        mat("foam", "#FAFAF8", 0.6), bevel=0.6)
    plane("board_decal", L.BOARD_W, L.BOARD_H, (0, 0, Z_TOP + 0.05),
          K.img_mat("decal", os.path.join(TEX, "decal_sa_ban.png"), 0.62))


def build_pole(node: str, m: dict) -> None:
    """Trụ giao thông của một nút: trụ nhôm 20 × 20 ở góc ngã tư; cần trên vươn chéo tới tâm ngã tư mang
    camera nhìn thẳng xuống; cần dưới Ø10 treo cụm đèn 4 mặt (4 module R/Y/G) ngay tâm ngã tư."""
    alu = m["alu_dark"]
    tx, ty = L.pole_xy(node)
    jx, jy = L.JUNCTIONS[node]
    reach = L.arm_len()
    pole_h = L.ARM_Z + 10
    box(f"pole_{node}_plate", (46, 46, 4), (tx, ty, Z_TOP + 2), alu, bevel=1.0)
    for i, (dx, dy) in enumerate(((-16, -16), (16, -16), (16, 16), (-16, 16))):
        cyl(f"pole_{node}_bolt{i}", 2.4, 2.0, (tx + dx, ty + dy, Z_TOP + 5), m["shield"], segments=12)
    K.build_profile(f"pole_{node}", pole_h, (tx, ty, Z_TOP + pole_h / 2), "z", alu)
    box(f"pole_{node}_cap", (21, 21, 2), (tx, ty, Z_TOP + pole_h + 1), m["plastic_black"], bevel=0.6)

    # cần trên (trục x cục bộ: từ trụ tới tâm ngã tư), có thanh giằng chéo
    arm = empty(f"arm_{node}", loc=(tx, ty, Z_TOP + L.ARM_Z), rot_z=L.arm_yaw(node) + 180)
    bar = reach + 24
    K.build_profile(f"arm_{node}_bar", bar, (bar / 2 - 10, 0, 0), "x", alu, arm)
    box(f"arm_{node}_endcap", (2, 21, 21), (bar - 9, 0, 0), m["plastic_black"], arm, bevel=0.5)
    box(f"arm_{node}_bracket", (40, 22, 3), (14, 0, -11.5), alu, arm, bevel=0.6)
    tube(f"arm_{node}_brace", [(10, 0, -78), (40, 0, -40), (72, 0, -10)], 2.2, alu, arm, order=2)
    box(f"cam_{node}_mount", (16, 16, 13), (reach, 0, -16.5), m["plastic_black"], arm, bevel=0.8)
    K.build_camera_module(f"camera_{node}", arm, loc=(reach, -2.5, L.CAMERA_H + 8.7 - L.ARM_Z))

    # cần đèn và cụm đèn 4 mặt: N ∥ S, E ∥ W như dây trên ESP32
    sarm = empty(f"sarm_{node}", loc=(tx, ty, Z_TOP + L.SIGNAL_ARM_H), rot_z=L.arm_yaw(node) + 180)
    box(f"sarm_{node}_clamp", (26, 26, 16), (0, 0, 0), alu, sarm, bevel=1.5)
    cyl(f"sarm_{node}_tube", 5, reach + 2, ((reach + 2) / 2 + 10, 0, 0), alu, sarm, rot=(0, 90, 0))
    sphere(f"sarm_{node}_tip", 5.2, (reach + 12, 0, 0), alu, sarm)
    drop = L.SIGNAL_ARM_H - (L.SIGNAL_H + 34)
    cyl(f"signal_{node}_rod", 2.2, drop + 4, (jx, jy, Z_TOP + L.SIGNAL_H + 34 + drop / 2), alu, segments=16)
    faces = [(a, L.FACE_YAW[a], L.light_state(node, a)) for a in "NSEW"]
    root = K.build_signal_cluster(f"signal_{node}", faces)
    root.location = (jx * MM, jy * MM, (Z_TOP + L.SIGNAL_H) * MM)

    # cáp 8 lõi từ cụm đèn: dọc mặt dưới cần, xuống mặt trụ, chui qua lỗ ở chân trụ xuống dưới sa bàn
    ux, uy = (jx - tx) / reach, (jy - ty) / reach
    fx, fy = tx + ux * 12, ty + uy * 12
    z_arm = Z_TOP + L.SIGNAL_ARM_H
    tube(f"signal_{node}_cable", [(jx - ux * 4, jy - uy * 4, Z_TOP + L.SIGNAL_H + 35), (jx - ux * 6, jy - uy * 6, z_arm - 6),
                                  (fx + ux * 30, fy + uy * 30, z_arm - 6), (fx + ux * 2, fy + uy * 2, z_arm - 10),
                                  (fx, fy, z_arm - 30), (fx, fy, Z_TOP + 8), (fx + ux * 3, fy + uy * 3, Z_TOP - 4)],
         1.7, m["plastic_black"])

    # cáp CSI 22 → 15 pin từ Pi
    tube(f"csi_{node}", [(x, y, Z_TOP + z) for x, y, z in L.csi_route(node)], 1.2, m["ribbon"])


def build_pi_cabinet(m: dict) -> None:
    """Pi 5 trong vỏ ABS, đặt ven đường giữa hai trụ như tủ điều khiển; cổng mạng/USB quay về phía sau."""
    px, py = L.PI_XY
    box("pi_plinth", (78, 106, 6), (px, py, Z_TOP + 3), m["alu_dark"], bevel=1.2)
    pi = K.build_pi_case("pi5", loc=(px, py, Z_TOP + 6))
    pi.rotation_euler = (0, 0, math.radians(90))
    eth = mat("eth", "#2D6CDF", 0.5)
    back = L.BOARD_H / 2 + L.BASE_BACK
    for dx, cm, r, end in ((19, eth, 2.6, (-405, 748, 14)), (-9, m["plastic_white"], 1.9, (360, 772, 26))):
        x = px + dx
        pts = [(x, py + 47, Z_TOP + 19), (x, py + 72, Z_TOP + 4), (x * 1.4, back - 30, Z_TOP + 2.5),
               (x * 1.5, back + 2, L.BASE_H + 3), (x * 1.6, back + 10, 20), (x * 2.2, back + 40, 3),
               (end[0] * 0.75, end[1] - 50, 3), end]
        tube(f"pi_cable_{'eth' if dx > 0 else 'usb'}", pts, r, cm)


def build_cars() -> None:
    for i, (node, appr, dist) in enumerate(L.CARS):
        x, y, heading = L.car_pose(node, appr, dist)
        root = K.build_car(f"car{i:02d}_{node}_{appr}", CAR_COLORS[(i * 7) % len(CAR_COLORS)])
        root.location = (x * MM, y * MM, Z_TOP * MM)
        root.rotation_euler = (0, 0, math.radians(heading + ((i * 37) % 5 - 2) * 0.6))


def build_trees() -> None:
    for i, (x, y) in enumerate(TREES):
        K.build_tree(f"tree{i}", i, loc=(x, y, Z_TOP))


def node_electronics(node: str, jx: float, m: dict, dark) -> None:
    root = empty(f"{node}_elec", loc=(jx, APRON_Y, L.BASE_H))
    bb = os.path.join(TEX, "breadboard.png")
    K.build_breadboard(f"{node}_bbN", bb, root, loc=(0, 27.3, 0))
    K.build_breadboard(f"{node}_bbS", bb, root, loc=(0, -27.3, 0))
    K.build_esp32(f"{node}_esp32", root, loc=(-8, 0, 8.5))
    slot_y = (-L.BOARD_H / 2 - 9) - APRON_Y
    box(f"{node}_slot", (86, 7, 1.0), (0, slot_y, 0.2), m["rubber"], root, bevel=0.4)
    # 6 dây tín hiệu + GND: GPIO 23/22/21 (NS), 19/18/5 (EW), GND
    for i, c in enumerate("RYGRYGK"):
        x0 = 14 - i * 5.08
        xs = -30 + i * 10
        pts = [(x0, 16.5, 8.7), (x0, 20, 20 + i * 1.5), (x0 * 0.7 + xs * 0.3, 40, 26), (xs, slot_y - 14, 12),
               (xs, slot_y, 2), (xs, slot_y, -6)]
        tube(f"{node}_w{i}", pts, 0.75, K.wire_mat(c), root)
    K.build_button(f"{node}_stop", root, loc=(128, 0, 0))
    for i, c in enumerate("BK"):
        pts = [(46 + i * 5, -18, 8.7), (52 + i * 5, -22, 22), (95, -10 + i * 6, 18), (114, -4 + i * 6, 10)]
        tube(f"{node}_bw{i}", pts, 0.75, K.wire_mat(c), root)
    text(f"{node}_label", node, 24, (-122, -36, 0.25), dark, root)
    text(f"{node}_stoplabel", "SAFE-STOP", 6.5, (128, -24, 0.25), dark, root)


def build_power(m: dict, dark) -> None:
    root = empty("power", loc=(0, APRON_Y, L.BASE_H))
    box("dc_jack", (14, 9, 11), (-30, -20, 5.5), m["plastic_black"], root, bevel=0.8)
    box("domino", (20, 10, 12), (0, -20, 6), m["domino"], root, bevel=0.6)
    for s in (-5, 5):
        cyl(f"domino_screw{s}", 2.0, 1.0, (s, -20, 12.4), m["shield"], root, segments=14)
    cyl("ptc", 4.2, 2.0, (24, -20, 7), m["ptc"], root, rot=(90, 0, 0))
    text("power_label", "NGUỒN 5 V", 8, (0, -40, 0.25), dark, root)
    # đường 5 V và GND tới ray nguồn của từng nút
    for node, jx in ((n, p[0]) for n, p in L.JUNCTIONS.items()):
        s = 1 if jx > 0 else -1
        for k, c in enumerate("RK"):
            yy = -6 - k * 4
            pts = [(s * 8, -20 + k * 3, 12), (s * 30, yy - 30, 10), (s * 120, -58 + k * 4, 6),
                   (jx - s * 75, -52 + k * 2.54, 9.5), (jx - s * 75, -52 + k * 2.54, 8.6)]
            tube(f"pw_{node}_{c}", pts, 0.8, K.wire_mat(c), root)
    K.build_adapter("adapter_5v", loc=(230, -800, 0), rot_z=12)
    tube("adapter_cable", [(190, -808, 10), (110, -770, 4), (10, -700, 4), (-22, -640, 6), (-26, -628, 48),
                           (-32, -580, 56), (-40, -544, 56)], 1.6, m["plastic_black"])


def build_desk_items(m: dict) -> None:
    K.build_router("router", loc=(-430, 760, 0), rot_z=12)
    K.build_power_strip("power_strip", loc=(440, 790, 0), rot_z=-4)
    psu = K.build_adapter("pi_psu", loc=(376, 790, 40), rot_z=86, white=True)
    psu.scale = (0.62, 0.9, 0.95)
    K.build_laptop("laptop", os.path.join(TEX, "dashboard.png"), loc=(1010, -260, 0), rot_z=24)


def build_scene() -> None:
    m = K.M()
    dark = mat("print_dark", "#2B2B2B", 0.6)
    build_base(m)
    for node in L.JUNCTIONS:
        build_pole(node, m)
    build_pi_cabinet(m)
    build_cars()
    build_trees()
    for node, (jx, _) in L.JUNCTIONS.items():
        node_electronics(node, jx, m, dark)
    build_power(m, dark)
    build_desk_items(m)
    lights()


# ------------------------------------------------------------------ máy quay
VIEWS = {
    "hero": dict(loc=(-900, -1500, 930), target=(75, -100, 150), lens=33.5, res=(2400, 1500)),
    "pole": dict(loc=(-20, -1000, 600), target=(-205, 40, 290), lens=41, res=(2400, 1500),
                 focus=(-235, 45, 290), fstop=11),
    "closeup": dict(loc=(-610, -1040, 360), target=(-250, -500, 75), lens=52, res=(2400, 1500),
                    focus=(-288, -522, 62), fstop=7.1),
    "top": dict(loc=(0, -105, 2600), rot=(0, 0, 0), ortho=1.62, res=(2400, 2080)),
    "front": dict(loc=(0, -2600, 250), rot=(90, 0, 0), ortho=1.46, res=(2400, 1000), transparent=True,
                  hide=["tree", "laptop", "router", "power_strip", "pi_psu", "adapter", "pi_cable"]),
}
for _n in L.JUNCTIONS:  # góc nhìn mô phỏng của từng camera trên trụ: cạnh dài khung hình dọc theo cần
    VIEWS[f"cam_{_n}"] = dict(loc=(*L.JUNCTIONS[_n], LENS_Z - 1.2), rot=(0, 0, L.arm_yaw(_n)), lens=2.75,
                              sensor=6.4512, res=(1920, 1080), node=_n)


def make_camera(name: str, v: dict) -> bpy.types.Object:
    cd = bpy.data.cameras.new(name)
    cd.clip_start = 0.001
    cd.clip_end = 30
    o = bpy.data.objects.new(name, cd)
    bpy.context.scene.collection.objects.link(o)
    o.location = Vector(v["loc"]) * MM
    if "ortho" in v:
        cd.type = "ORTHO"
        cd.ortho_scale = v["ortho"]
    else:
        cd.lens = v["lens"]
        if "sensor" in v:
            cd.sensor_fit = "HORIZONTAL"
            cd.sensor_width = v["sensor"]
    if "rot" in v:
        o.rotation_euler = tuple(math.radians(a) for a in v["rot"])
    else:
        o.rotation_euler = (Vector(v["target"]) * MM - o.location).to_track_quat("-Z", "Y").to_euler()
    if "focus" in v:
        cd.dof.use_dof = True
        cd.dof.focus_distance = (Vector(v["focus"]) * MM - o.location).length
        cd.dof.aperture_fstop = v["fstop"]
    return o


def _collect(name: str, objs) -> None:
    coll = bpy.data.collections.new(name)
    bpy.context.scene.collection.children.link(coll)
    for o in objs:
        for c in list(o.users_collection):
            c.objects.unlink(o)
        coll.objects.link(o)


def tidy_viewport(center=(0.05, -0.1, 0.22), distance: float = 2.2) -> None:
    """Mở .blend là thấy sa bàn: ẩn máy quay/đèn khỏi viewport (vẫn render), bật Material Preview
    để thấy decal mặt đường, đóng khung góc nhìn, khóa chọn mặt bàn."""
    sc = bpy.context.scene
    _collect("May_quay_render", [o for o in sc.objects if o.type == "CAMERA"])
    _collect("Den_studio", [o for o in sc.objects if o.type == "LIGHT"])
    for name in ("May_quay_render", "Den_studio"):
        bpy.context.view_layer.layer_collection.children[name].hide_viewport = True  # con mắt trong Outliner
    for name in ("table", "studio_floor"):
        if name in bpy.data.objects:
            bpy.data.objects[name].hide_select = True
    for o in sc.objects:
        o.select_set(False)
    bpy.context.view_layer.objects.active = None
    rot = Euler((math.radians(58), 0, math.radians(-32))).to_quaternion()
    for screen in bpy.data.screens:
        for area in screen.areas:
            for space in area.spaces:
                if space.type != "VIEW_3D":
                    continue
                space.clip_start = 0.002
                space.clip_end = 200
                space.shading.type = "MATERIAL"
                r3d = space.region_3d
                r3d.view_perspective = "PERSP"
                r3d.view_location = center
                r3d.view_distance = distance
                r3d.view_rotation = rot


def anchors_world() -> dict[str, tuple[float, float, float]]:
    px, py = L.PI_XY
    a = {
        "pi": (px, py, Z_TOP + 30),
        "esp_J1": (-296, APRON_Y, 62), "esp_J2": (264, APRON_Y, 62),
        "bb_J1": (-350, APRON_Y - 30, 59), "stop_J1": (-152, APRON_Y, 74), "stop_J2": (408, APRON_Y, 74),
        "slot_J1": (-280, -L.BOARD_H / 2 - 9, 51), "power": (0, APRON_Y - 20, 62),
        "adapter": (230, -800, 32), "router": (-430, 760, 45), "strip": (440, 790, 42),
    }
    for node, (jx, jy) in L.JUNCTIONS.items():
        tx, ty = L.pole_xy(node)
        a[node] = (jx, jy - 75, Z_TOP)
        a[f"pole_{node}"] = (tx, ty, Z_TOP + 300)
        a[f"pole_base_{node}"] = (tx, ty, Z_TOP + 4)
        a[f"cam_{node}"] = (jx, jy, LENS_Z + 6)
        a[f"lens_{node}"] = (jx, jy, LENS_Z)
        a[f"arm_{node}"] = ((jx + tx) / 2, (jy + ty) / 2, Z_TOP + L.ARM_Z)
        a[f"signal_{node}"] = (jx, jy, Z_TOP + L.SIGNAL_H)
        a[f"signal_arm_{node}"] = ((jx + tx) / 2, (jy + ty) / 2, Z_TOP + L.SIGNAL_ARM_H)
        a[f"board_under_{node}"] = (jx, jy, Z_TOP)
        route = L.csi_route(node)
        a[f"csi_{node}"] = (*[(route[1][i] + route[2][i]) / 2 for i in (0, 1)], Z_TOP + 2)
        a[f"csi_pole_{node}"] = (tx, ty + 11, Z_TOP + 200)
        reach = L.arm_len()
        a[f"sigcable_{node}"] = (tx + (jx - tx) / reach * 12, ty + (jy - ty) / reach * 12, Z_TOP + 80)
    for i, (node, appr, dist) in enumerate(L.CARS):
        x, y, _ = L.car_pose(node, appr, dist)
        a[f"car{i:02d}"] = (x, y, Z_TOP + 18)
    scr = bpy.data.objects.get("laptop_screen")
    if scr is not None:
        a["laptop"] = tuple(c / MM for c in scr.matrix_world.translation)
    # điểm đo cho bản vẽ bố trí và mặt đứng
    hw, hh = L.BOARD_W / 2, L.BOARD_H / 2
    for sx in (-1, 1):
        for sy in (-1, 1):
            a[f"board_{'E' if sx > 0 else 'W'}{'N' if sy > 0 else 'S'}"] = (sx * hw, sy * hh, Z_TOP)
    a["base_front_W"] = (-hw - L.BASE_MARGIN_X, -hh - L.BASE_FRONT, L.BASE_H)
    a["base_front_E"] = (hw + L.BASE_MARGIN_X, -hh - L.BASE_FRONT, L.BASE_H)
    a["board_top_center"] = (0, 0, Z_TOP)
    return a


def project(cam, pts: dict, res) -> dict:
    sc = bpy.context.scene
    out = {}
    for k, p in pts.items():
        co = world_to_camera_view(sc, cam, Vector(p) * MM)
        out[k] = [round(co.x * res[0], 1), round((1 - co.y) * res[1], 1), round(co.z, 4)]
    return out


def rois_world() -> dict:
    return {f"{n}_{a}_IN": [(x, y, Z_TOP) for x, y in L.roi_rect(n, a)] for n in L.JUNCTIONS for a in "NSEW"}


def render_views(views: list[str], cams: dict, percent: int, do_render: bool) -> None:
    sc = bpy.context.scene
    raw = K.ensure_dir(os.path.join(RENDERS, "raw"))
    anchors_path = os.path.join(RENDERS, "anchors.json")
    data = json.load(open(anchors_path)) if os.path.exists(anchors_path) else {}
    bpy.context.view_layer.update()
    world = anchors_world()
    for name in views:
        v = VIEWS[name]
        cam = cams[name]
        sc.camera = cam
        sc.render.resolution_x, sc.render.resolution_y = v["res"]
        sc.render.resolution_percentage = percent
        sc.render.film_transparent = v.get("transparent", False)
        res = (v["res"][0] * percent // 100, v["res"][1] * percent // 100)
        hidden = []
        for prefix in v.get("hide", []):
            for o in bpy.data.objects:
                if o.name.startswith(prefix):
                    o.hide_render = True
                    hidden.append(o)
        entry = {"res": res, "anchors": project(cam, world, res)}
        if "node" in v:  # mỗi camera chỉ báo cho nút của mình (VISION_NODE_IDS=J1 hoặc J2)
            entry["rois"] = {k: [project(cam, {"p": p}, res)["p"][:2] for p in pts]
                             for k, pts in rois_world().items() if k.startswith(v["node"])}
        data[name] = entry
        if do_render:
            sc.render.filepath = os.path.join(raw, f"{name}.png")
            print(f"[render] {name} {res}")
            bpy.ops.render.render(write_still=True)
        for o in hidden:
            o.hide_render = False
    with open(anchors_path, "w") as f:
        json.dump(data, f, indent=1)


def main() -> None:
    args = parse_args()
    reset_scene()
    setup_render(args.samples)
    build_scene()
    views = [v.strip() for v in args.views.split(",") if v.strip()]
    cams = {name: make_camera(name if name.startswith("cam_") else f"cam_{name}", v)
            for name, v in VIEWS.items()}  # .blend có sẵn mọi góc máy
    bpy.context.scene.camera = cams["hero"]
    tidy_viewport()
    bpy.ops.wm.save_as_mainfile(filepath=args.save)
    try:
        bpy.ops.file.make_paths_relative()
        bpy.ops.wm.save_mainfile()
    except RuntimeError as exc:
        print("không đổi được sang đường dẫn tương đối:", exc)
    render_views(views, cams, args.percent, not args.no_render)


if __name__ == "__main__":
    main()
