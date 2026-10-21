"""Dựng cảnh sa bàn EdgeFlow AI trong Blender và render các góc nhìn cho mục 4.4 / 3.4.

Bản 2 tấm 600 × 600 (từ 18/10). Bản tấm A0 cũ: dung_canh_a0.py + bo_tri_a0.py.

Chạy (từ thư mục này):
  uv run -q --with pillow python tao_texture.py            # texture (PIL + rsvg-convert)
  /Applications/Blender.app/Contents/MacOS/Blender -b -P dung_canh.py -- \
      --views hero,pole,closeup,cam_J2,top,front,overview --samples 128

Kết quả: ../renders_2tam/raw/<view>.png, ../renders_2tam/anchors.json (tọa độ điểm neo để vẽ chú thích),
và sa_ban_2tam.blend (mở bằng Blender để chỉnh tiếp). Không ghi đè H4.x của bản A0 trong ../renders/.
Bố trí lấy từ bo_tri.py, vị trí thiết bị lấy từ in_sa_ban/_nguon/hinh_hoc.py (cùng nguồn với file in).
Đây là phương án ĐỀ XUẤT, chưa phải ảnh chụp sa bàn thật.
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
sys.path.insert(0, os.path.abspath(os.path.join(HERE, "..", "..", "..", "in_sa_ban", "_nguon")))
import bo_tri as L  # noqa: E402
import hinh_hoc as G  # noqa: E402
import linh_kien_3d as K  # noqa: E402
from linh_kien_3d import MM, box, cyl, empty, mat, plane, sphere, text, tube  # noqa: E402

TEX = os.path.join(HERE, "textures")
RENDERS = os.path.abspath(os.path.join(HERE, "..", "renders_2tam"))
Z_TOP = L.BASE_H + L.BOARD_T                         # mặt bạt
Z_POLE = Z_TOP + G.PLATE_T                           # mặt đế MDF của trụ
LENS_Z = Z_TOP + L.CAMERA_H                          # cao độ ống kính (mm, tính từ mặt bàn)
CAR_COLORS = ["#C8102E", "#F4F4F2", "#1F4E99", "#9EA3A8", "#161616", "#E87722", "#F2C500", "#2E7D32",
              "#0FA3B1", "#7A2E8E"]
# cây đặt trên các ô cỏ còn trống (ô sau-ngoài và ô trước-ngoài của J1, ô sau-ngoài của J2)
TREES = [(-545, 235), (-470, 255), (-500, -180), (-440, -250), (545, 235), (470, 255)]
POLE_J1_H = 200.0                                    # trụ J1 chỉ treo đèn: thanh nhôm 20 cm như bản in


def wxy(node: str, u: float, y: float) -> tuple[float, float]:
    """Tọa độ ghép (mm) của điểm (u, y) trong hệ cục bộ của tấm `node`."""
    return G.WORLD_X[node] + u * G.INWARD[node], y


def parse_args() -> argparse.Namespace:
    argv = sys.argv[sys.argv.index("--") + 1:] if "--" in sys.argv else []
    ap = argparse.ArgumentParser()
    ap.add_argument("--views", default="hero,pole,closeup,cam_J2,top,front,overview")
    ap.add_argument("--samples", type=int, default=128)
    ap.add_argument("--percent", type=int, default=100, help="tỉ lệ độ phân giải (thử nhanh: 30)")
    ap.add_argument("--video", action="store_true", help="cảnh cho video demo: bỏ camera trên trụ J2")
    ap.add_argument("--no-render", action="store_true")
    ap.add_argument("--save", default=os.path.join(HERE, "sa_ban_2tam.blend"))
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
    """Một tấm bạt 1200 × 600 trải trên bàn; decal lấy từ cùng SVG với file in."""
    plane("table", 14000, 14000, (0, 0, 0), mat("table", "#A99F92", 0.62))
    box("board_bat", (L.BOARD_W, L.BOARD_H, L.BOARD_T), (0, 0, L.BOARD_T / 2), mat("bat", "#EDEDE8", 0.7))
    plane("board_decal", L.BOARD_W, L.BOARD_H, (0, 0, Z_TOP + 0.05),
          K.img_mat("decal_bat", os.path.join(TEX, "decal_bat.png"), 0.7))
    mdf = mat("mdf", "#B8946A", 0.75)
    for node in G.NODES:  # đế MDF của trụ, nằm trên ô cỏ sau-trong
        x0, y0, x1, y1 = G.rect_x(node, G.plate_rect())
        box(f"plate_{node}", (x1 - x0, y1 - y0, G.PLATE_T),
            (G.WORLD_X[node] + (x0 + x1) / 2, (y0 + y1) / 2, Z_TOP + G.PLATE_T / 2), mdf, bevel=0.6)


def build_pole(node: str, m: dict) -> None:
    """Trụ giao thông của một nút: trụ nhôm 20 × 20 ở góc ngã tư, bắt ke góc; cần đèn Ø10 treo cụm đèn 4 mặt
    (4 module R/Y/G) ngay tâm ngã tư. Chỉ trụ ở CAMERA_NODES có thêm cần trên mang camera nhìn thẳng xuống."""
    alu = m["alu_dark"]
    tx, ty = L.pole_xy(node)
    jx, jy = L.JUNCTIONS[node]
    reach = L.arm_len()
    has_cam = node in L.CAMERA_NODES
    pole_h = L.ARM_Z + 10 if has_cam else POLE_J1_H
    for i, r in enumerate(G.bracket_rects()):  # 2 ke góc ở chân trụ, phía đối diện cần đèn
        x0, y0, x1, y1 = G.rect_x(node, r)
        x0, x1 = x0 + G.WORLD_X[node], x1 + G.WORLD_X[node]
        box(f"pole_{node}_bracket{i}", (x1 - x0, y1 - y0, 20), ((x0 + x1) / 2, (y0 + y1) / 2, Z_POLE + 10),
            alu, bevel=0.8)
    K.build_profile(f"pole_{node}", pole_h, (tx, ty, Z_POLE + pole_h / 2), "z", alu)
    box(f"pole_{node}_cap", (21, 21, 2), (tx, ty, Z_POLE + pole_h + 1), m["plastic_black"], bevel=0.6)

    if has_cam:  # cần trên (trục x cục bộ: từ trụ tới tâm ngã tư), có thanh giằng chéo
        arm = empty(f"arm_{node}", loc=(tx, ty, Z_POLE + L.ARM_Z), rot_z=L.arm_yaw(node) + 180)
        bar = reach + 24
        K.build_profile(f"arm_{node}_bar", bar, (bar / 2 - 10, 0, 0), "x", alu, arm)
        box(f"arm_{node}_endcap", (2, 21, 21), (bar - 9, 0, 0), m["plastic_black"], arm, bevel=0.5)
        box(f"arm_{node}_bracket", (40, 22, 3), (14, 0, -11.5), alu, arm, bevel=0.6)
        tube(f"arm_{node}_brace", [(10, 0, -78), (40, 0, -40), (72, 0, -10)], 2.2, alu, arm, order=2)
        box(f"cam_{node}_mount", (16, 16, 13), (reach, 0, -16.5), m["plastic_black"], arm, bevel=0.8)
        K.build_camera_module(f"camera_{node}", arm, loc=(reach, -2.5, L.CAMERA_H + 8.7 - L.ARM_Z))

    # cần đèn và cụm đèn 4 mặt: N ∥ S, E ∥ W như dây trên ESP32
    sarm = empty(f"sarm_{node}", loc=(tx, ty, Z_POLE + L.SIGNAL_ARM_H), rot_z=L.arm_yaw(node) + 180)
    box(f"sarm_{node}_clamp", (26, 26, 16), (0, 0, 0), alu, sarm, bevel=1.5)
    cyl(f"sarm_{node}_tube", 5, reach + 2, ((reach + 2) / 2 + 10, 0, 0), alu, sarm, rot=(0, 90, 0))
    sphere(f"sarm_{node}_tip", 5.2, (reach + 12, 0, 0), alu, sarm)
    drop = L.SIGNAL_ARM_H - (L.SIGNAL_H + 34)
    cyl(f"signal_{node}_rod", 2.2, drop + 4, (jx, jy, Z_POLE + L.SIGNAL_H + 34 + drop / 2), alu, segments=16)
    faces = [(a, L.FACE_YAW[a], L.light_state(node, a)) for a in "NSEW"]
    root = K.build_signal_cluster(f"signal_{node}", faces)
    root.location = (jx * MM, jy * MM, (Z_POLE + L.SIGNAL_H) * MM)

    # cáp 8 lõi từ cụm đèn: dọc mặt dưới cần, xuống mặt trụ, chui qua lỗ Ø10 ở chân trụ xuống dưới tấm
    ux, uy = (jx - tx) / reach, (jy - ty) / reach
    fx, fy = tx + ux * 12, ty + uy * 12
    ex, ey = wxy(node, G.CABLE_U, G.CABLE_Y)
    side = G.INWARD[node]
    z_arm = Z_POLE + L.SIGNAL_ARM_H
    tube(f"signal_{node}_cable", [(jx - ux * 4, jy - uy * 4, Z_POLE + L.SIGNAL_H + 35), (jx - ux * 6, jy - uy * 6, z_arm - 6),
                                  (fx + ux * 30, fy + uy * 30, z_arm - 6), (fx + ux * 2, fy + uy * 2, z_arm - 10),
                                  (fx, fy, z_arm - 30), (fx, fy, Z_POLE + 14), (fx, fy, Z_POLE + 2.5)],
         1.7, m["plastic_black"])
    # đoạn nằm trên đế và bạt: dán băng keo vải, vắt qua đường tới chỗ cáp rời breadboard
    sx, sy = wxy(node, G.POLE_U, G.POLE_Y)
    ground = [(fx, fy, Z_POLE + 2.5), (sx + side * 14, sy - 10, Z_POLE + 2.5),
              (wxy(node, G.POLE_U + 60, G.POLE_Y - 20)[0], sy - 20, Z_TOP + 2.5),
              (ex, sy - 60, Z_TOP + 2.5), (ex, ey + 40, Z_TOP + 2.5), (ex, ey, Z_TOP + 2.5)]
    tube(f"signal_{node}_cable_flat", ground, 2.2, m["plastic_black"], order=2)


def build_pi_cabinet(m: dict) -> None:
    """Pi 5 trong vỏ ABS ở ô cỏ trước-ngoài của J2 (trên ô in 'AI BIÊN · PI 5'); cổng mạng/USB quay ra mép Đông."""
    px, py = L.PI_XY
    pi = K.build_pi_case("pi5", loc=(px, py, Z_TOP))
    eth = mat("eth", "#2D6CDF", 0.5)
    edge = G.HALF + G.WORLD_X["J2"]
    for name, cm, r, y0, end in (("eth", eth, 2.6, py - 19, (770, -330, 22)),
                                 ("usb", m["plastic_white"], 1.9, py + 22, (700, -118, 24))):
        pts = [(px + 46, y0, Z_TOP + 13), (px + 70, y0 - 3, Z_TOP + 4), (edge - 6, y0 - 8, Z_TOP + 2.5),
               (edge + 14, y0 - 30, 3), (end[0] - 40, end[1] + 10, 3), end]
        tube(f"pi_cable_{name}", pts, r, cm)
    return pi


def build_cars() -> None:
    for i, (node, appr, dist) in enumerate(L.CARS):
        x, y, heading = L.car_pose(node, appr, dist)
        root = K.build_car(f"car{i:02d}_{node}_{appr}", CAR_COLORS[(i * 7) % len(CAR_COLORS)])
        root.location = (x * MM, y * MM, Z_TOP * MM)
        root.rotation_euler = (0, 0, math.radians(heading + ((i * 37) % 5 - 2) * 0.6))


def build_trees() -> None:
    for i, (x, y) in enumerate(TREES):
        K.build_tree(f"tree{i}", i, loc=(x, y, Z_TOP))


def node_electronics(node: str, m: dict) -> None:
    """ESP32 + 2 breadboard ở ô trước-trong, 7 dây tín hiệu nối cáp W (nằm trên bạt) ở cạnh breadboard, nút S1."""
    s = G.INWARD[node]
    bx0, by0, bx1, by1 = G.bb_rect()
    bbx, bby = wxy(node, (bx0 + bx1) / 2, (by0 + by1) / 2)
    pair = empty(f"{node}_bb", loc=(bbx, bby, Z_TOP), rot_z=90)       # trục dài breadboard dọc theo y
    tex = os.path.join(TEX, "breadboard.png")
    for k, off in enumerate((27.3, -27.3)):
        K.build_breadboard(f"{node}_bb{k}", tex, pair, loc=(0, off, 0))
    ex0, ey0, ex1, ey1 = G.esp32_rect()
    esp = empty(f"{node}_esp_root", loc=(*wxy(node, (ex0 + ex1) / 2, (ey0 + ey1) / 2), Z_TOP + 8.5), rot_z=90)
    K.build_esp32(f"{node}_esp32", esp)                               # USB ở −x → quay ra mép trước (−y)
    # 7 dây: GPIO 23/22/21 (N‖S), 19/18/5 (E‖W), GND → đầu cáp W cạnh breadboard
    hx, hy = wxy(node, G.CABLE_U, G.CABLE_Y)
    top_y = ey1 - 2
    for i, c in enumerate("RYGRYGK"):
        x0 = bbx - 11.4 + i * 3.8
        xe = hx + (i - 3) * 1.4
        pts = [(x0, top_y, Z_TOP + 8.7), (x0, top_y + 10, Z_TOP + 16 + i), (xe - s * (10 - i), hy - 14, Z_TOP + 20),
               (xe, hy, Z_TOP + 3), (xe, hy, Z_TOP + 2.5)]
        tube(f"{node}_w{i}", pts, 0.75, K.wire_mat(c))
    # nút dừng an toàn S1 (GPIO 4) giữa breadboard và lỗ cáp, hai dây tới ESP32
    sx, sy = wxy(node, G.CABLE_U, -195.0)
    K.build_button(f"{node}_stop", loc=(sx, sy, Z_TOP))
    for i, c in enumerate("BK"):
        pts = [(bbx + s * (14 + i * 4), top_y - 6, Z_TOP + 8.7), (bbx + s * (28 + i * 4), top_y - 16, Z_TOP + 16),
               (sx - s * 15, sy + 6 - i * 6, Z_TOP + 12), (sx - s * 11, sy + 6 - i * 6, Z_TOP + 6)]
        tube(f"{node}_bw{i}", pts, 0.75, K.wire_mat(c))


def build_power(m: dict) -> None:
    """J1: jack X1 + domino dán ở ô trước-trong, nguồn 5 V từ adapter đặt trước sa bàn. Dây P3 nối J1 → J2 nằm
    trên mặt bạt (dán băng keo vải), đi qua giữa bạt."""
    ux0, uy0, ux1, uy1 = G.x1_rect()
    x0, x1 = wxy("J1", ux0, 0)[0], wxy("J1", ux1, 0)[0]
    cx, y0, y1 = (x0 + x1) / 2, uy0, uy1
    box("dc_jack", (14, 20, 13), (cx, y0 + 10, Z_TOP + 6.5), m["plastic_black"], bevel=0.8)
    box("domino", (14, 10, 12), (cx, y1 - 6, Z_TOP + 6), m["domino"], bevel=0.6)
    for k in (-1, 1):
        cyl(f"domino_screw{k}", 2.0, 1.0, (cx + k * 3.5, y1 - 6, Z_TOP + 12.4), m["shield"], segments=14)
    # 5 V và GND từ domino sang ray nguồn phía ngoài của breadboard J1
    bx0 = wxy("J1", G.bb_rect()[0], 0)[0]
    for k, c in enumerate("RK"):
        pts = [(cx + 2 * k, y1 - 6, Z_TOP + 12), (cx + 8, y1 + 6 + k * 3, Z_TOP + 18), (bx0 - 4, y1 + 20 + k * 3, Z_TOP + 14),
               (bx0 + 2.6 + k * 2.54, y1 + 20 + k * 3, Z_TOP + 9.5), (bx0 + 2.6 + k * 2.54, y1 + 20 + k * 3, Z_TOP + 8.6)]
        tube(f"pw_J1_{c}", pts, 0.8, K.wire_mat(c))
    # P3: ray nguồn phía giữa bạt → chỗ cáp rời breadboard, rồi sang nút kia
    for node in G.NODES:
        s = G.INWARD[node]
        hx, hy = wxy(node, G.CABLE_U, G.CABLE_Y)
        rail_x = wxy(node, G.bb_rect()[2], 0)[0] - s * 2.6
        for k, c in enumerate("RK"):
            ry = G.bb_rect()[1] + 70 + k * 6
            pts = ([(rail_x - s * k * 2.54, ry, Z_TOP + 8.6), (rail_x - s * k * 2.54, ry, Z_TOP + 13),
                    (hx - s * 3, hy - 22 + k * 3, Z_TOP + 16), (hx + s * (k - 0.5) * 3, hy + 2, Z_TOP + 2)])
            tube(f"p3_{node}_{c}", pts, 0.8, K.wire_mat(c))
    ax, ay = wxy("J1", G.CABLE_U, G.CABLE_Y)
    bx_, by_ = wxy("J2", G.CABLE_U, G.CABLE_Y)
    for k, c in enumerate("RK"):                      # đoạn P3 nằm ngang qua giữa bạt
        tube(f"p3_mid_{c}", [(ax, ay + 2 - k * 3, Z_TOP + 1.5), ((ax + bx_) / 2, ay + 4 - k * 3, Z_TOP + 1.5),
                             (bx_, by_ + 2 - k * 3, Z_TOP + 1.5)], 0.8, K.wire_mat(c), order=2)
    # adapter 5 V đặt trước J1, cáp vòng qua mép trước vào miệng jack (quay ra mép trước)
    K.build_adapter("adapter_5v", loc=(-120, -430, 0), rot_z=12)
    tube("adapter_cable", [(-150, -425, 14), (-175, -370, 3), (-190, -318, 3), (cx - 1, -302, Z_TOP + 2),
                           (cx, y0 - 6, Z_TOP + 3), (cx, y0, Z_TOP + 6)], 1.6, m["plastic_black"])


def build_desk_items(m: dict) -> None:
    K.build_router("router", loc=(800, -330, 0), rot_z=10)
    K.build_power_strip("power_strip", loc=(860, -60, 0), rot_z=84)
    psu = K.build_adapter("pi_psu", loc=(700, -118, 0), rot_z=90, white=True)
    psu.scale = (0.62, 0.9, 0.95)
    K.build_laptop("laptop", os.path.join(TEX, "dashboard.png"), loc=(980, 190, 0), rot_z=24)


def build_scene() -> None:
    m = K.M()
    build_base(m)
    for node in L.JUNCTIONS:
        build_pole(node, m)
    build_pi_cabinet(m)
    build_cars()
    build_trees()
    for node in G.NODES:
        node_electronics(node, m)
    build_power(m)
    build_desk_items(m)
    lights()


# ------------------------------------------------------------------ máy quay
DESK = ["laptop", "router", "power_strip", "pi_psu", "adapter", "pi_cable"]
VIEWS = {
    "hero": dict(loc=(-700, -1250, 760), target=(60, -40, 70), lens=31, res=(2400, 1500)),
    "pole": dict(loc=(520, -420, 560), target=(215, 70, 300), lens=38, res=(2400, 1500),
                 focus=(215, 70, 300), fstop=11),
    "closeup": dict(loc=(-640, -640, 250), target=(-190, -230, 40), lens=50, res=(2400, 1500),
                    focus=(-190, -230, 30), fstop=7.1),
    "top": dict(loc=(0, 0, 2600), rot=(0, 0, 0), ortho=1.45, res=(2400, 1200)),
    "front": dict(loc=(0, -2600, 230), rot=(90, 0, 0), ortho=1.45, res=(2400, 900), transparent=True,
                  hide=["tree", "laptop", "router", "power_strip", "pi_psu", "adapter", "pi_cable"]),
    # camera của video demo: nhìn bao quát cả J1 và J2 (1280 × 720, ~1 px/mm trên mặt đường)
    # (chạy với --video: cả 2 trụ cao 20 cm như bản in, không có camera trên trụ; ẩn đồ để bàn ngoài sa bàn)
    "overview": dict(loc=(0, 0, Z_TOP + 1110), rot=(0, 0, 0), lens=31, sensor=36, res=(1280, 720), hide=DESK),
    "overview_tilt": dict(loc=(0, -900, Z_TOP + 700), target=(0, -10, Z_TOP), lens=27, sensor=36, res=(1280, 720),
                          hide=DESK),
}
for _n in L.CAMERA_NODES:  # góc nhìn mô phỏng của camera trên trụ: cạnh dài khung hình dọc theo cần
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
    a = {"pi": (px, py, Z_TOP + 30), "adapter": (-120, -430, 32), "router": (800, -330, 45),
         "strip": (860, -60, 42), "laptop_pos": (980, 190, 60)}
    for node, (jx, jy) in L.JUNCTIONS.items():
        tx, ty = L.pole_xy(node)
        bx0, by0, bx1, by1 = G.bb_rect()
        a[f"esp_{node}"] = (*wxy(node, (bx0 + bx1) / 2, by0 + 30), Z_TOP + 14)
        a[f"bb_{node}"] = (*wxy(node, (bx0 + bx1) / 2, by1 - 20), Z_TOP + 9)
        a[f"stop_{node}"] = (*wxy(node, G.CABLE_U, -195.0), Z_TOP + 24)
        a[f"cable_end_{node}"] = (*wxy(node, G.CABLE_U, G.CABLE_Y), Z_TOP)
        a[f"plate_{node}"] = (*wxy(node, G.PLATE_U0 + G.PLATE / 2, G.PLATE_U0 + G.PLATE / 2), Z_POLE)
        a[node] = (jx, jy - 75, Z_TOP)
        a[f"pole_{node}"] = (tx, ty, Z_TOP + (L.ARM_Z if node in L.CAMERA_NODES else POLE_J1_H) / 1.5)
        a[f"pole_base_{node}"] = (tx, ty, Z_TOP + 10)
        a[f"signal_{node}"] = (jx, jy, Z_TOP + L.SIGNAL_H)
        a[f"signal_arm_{node}"] = ((jx + tx) / 2, (jy + ty) / 2, Z_TOP + L.SIGNAL_ARM_H)
        a[f"board_under_{node}"] = (jx, jy, Z_TOP)
        if node in L.CAMERA_NODES:
            a[f"cam_{node}"] = (jx, jy, LENS_Z + 6)
            a[f"lens_{node}"] = (jx, jy, LENS_Z)
            a[f"arm_{node}"] = ((jx + tx) / 2, (jy + ty) / 2, Z_TOP + L.ARM_Z)
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
    a["seam_front"] = (0, -hh, Z_TOP)
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
    if args.video:
        L.CAMERA_NODES = ()
        VIEWS.pop("cam_J2", None)
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
