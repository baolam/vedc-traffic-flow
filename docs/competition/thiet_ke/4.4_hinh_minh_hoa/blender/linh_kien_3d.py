"""Các khối 3D dùng chung (Blender bpy/bmesh). Đơn vị đầu vào: mm. Mỗi hàm build_* trả về một Empty
làm gốc; hình học con đặt theo tọa độ cục bộ (z = 0 là mặt đáy của linh kiện).
"""
from __future__ import annotations

import math
import os

import bmesh
import bpy

MM = 0.001
FONT_REG = "/System/Library/Fonts/Supplemental/Arial.ttf"
FONT_BOLD = "/System/Library/Fonts/Supplemental/Arial Bold.ttf"
_MATS: dict[str, bpy.types.Material] = {}


# ------------------------------------------------------------------ vật liệu
def _lin(c: float) -> float:
    return c / 12.92 if c <= 0.04045 else ((c + 0.055) / 1.055) ** 2.4


def hex_rgb(h: str) -> tuple[float, float, float]:
    h = h.lstrip("#")
    return tuple(_lin(int(h[i:i + 2], 16) / 255) for i in (0, 2, 4))


def _set(node, name: str, value) -> None:
    if name in node.inputs:
        node.inputs[name].default_value = value


def mat(name: str, color: str = "#808080", rough: float = 0.5, metal: float = 0.0, coat: float = 0.0,
        emit: tuple[float, float, float] | None = None, strength: float = 0.0, alpha: float = 1.0,
        transmission: float = 0.0) -> bpy.types.Material:
    if name in _MATS:
        return _MATS[name]
    m = bpy.data.materials.new(name)
    try:
        m.use_nodes = True
    except AttributeError:
        pass
    b = m.node_tree.nodes.get("Principled BSDF")
    _set(b, "Base Color", (*hex_rgb(color), 1.0))
    _set(b, "Roughness", rough)
    _set(b, "Metallic", metal)
    _set(b, "Coat Weight", coat)
    _set(b, "Coat Roughness", 0.05)
    _set(b, "Transmission Weight", transmission)
    if emit is not None:
        _set(b, "Emission Color", (*emit, 1.0))
        _set(b, "Emission Strength", strength)
    if alpha < 1.0:
        _set(b, "Alpha", alpha)
    _MATS[name] = m
    return m


def img_mat(name: str, path: str, rough: float = 0.55, emissive: float = 0.0) -> bpy.types.Material:
    if name in _MATS:
        return _MATS[name]
    m = bpy.data.materials.new(name)
    try:
        m.use_nodes = True
    except AttributeError:
        pass
    nt = m.node_tree
    b = nt.nodes.get("Principled BSDF")
    tex = nt.nodes.new("ShaderNodeTexImage")
    tex.image = bpy.data.images.load(path, check_existing=True)
    tex.interpolation = "Cubic"
    nt.links.new(tex.outputs["Color"], b.inputs["Base Color"])
    _set(b, "Roughness", rough)
    if emissive > 0:
        nt.links.new(tex.outputs["Color"], b.inputs["Emission Color"])
        _set(b, "Emission Strength", emissive)
    _MATS[name] = m
    return m


# ------------------------------------------------------------------ hình học
def _collection() -> bpy.types.Collection:
    return bpy.context.scene.collection


def empty(name: str, loc=(0, 0, 0), rot_z: float = 0.0, parent=None) -> bpy.types.Object:
    e = bpy.data.objects.new(name, None)
    e.empty_display_size = 0.02
    _collection().objects.link(e)
    if parent is not None:
        e.parent = parent
    e.location = tuple(v * MM for v in loc)
    e.rotation_euler = (0, 0, math.radians(rot_z))
    return e


def _finish(name: str, bm: bmesh.types.BMesh, material, loc, rot, parent, sharp_deg: float = 32.0):
    for f in bm.faces:
        f.smooth = True
    lim = math.radians(sharp_deg)
    for e in bm.edges:
        if len(e.link_faces) == 2 and e.calc_face_angle(0.0) > lim:
            e.smooth = False
    me = bpy.data.meshes.new(name)
    bm.to_mesh(me)
    bm.free()
    o = bpy.data.objects.new(name, me)
    _collection().objects.link(o)
    if material is not None:
        me.materials.append(material)
    if parent is not None:
        o.parent = parent
    o.location = tuple(v * MM for v in loc)
    o.rotation_euler = tuple(math.radians(a) for a in rot)
    return o


def _bevel(o, width_mm: float, segments: int = 3) -> None:
    if width_mm <= 0:
        return
    m = o.modifiers.new("Bevel", "BEVEL")
    m.width = width_mm * MM
    m.segments = segments
    m.limit_method = "ANGLE"
    m.harden_normals = True


def box(name, dims, loc, material, parent=None, bevel: float = 0.0, rot=(0, 0, 0), segments: int = 3):
    bm = bmesh.new()
    bmesh.ops.create_cube(bm, size=1.0)
    for v in bm.verts:
        v.co.x *= dims[0] * MM
        v.co.y *= dims[1] * MM
        v.co.z *= dims[2] * MM
    o = _finish(name, bm, material, loc, rot, parent)
    _bevel(o, min(bevel, min(dims) / 2.05), segments)
    return o


def cyl(name, radius, depth, loc, material, parent=None, rot=(0, 0, 0), segments: int = 32,
        radius2: float | None = None, bevel: float = 0.0):
    bm = bmesh.new()
    bmesh.ops.create_cone(bm, cap_ends=True, cap_tris=False, segments=segments, radius1=radius * MM,
                          radius2=(radius if radius2 is None else radius2) * MM, depth=depth * MM)
    o = _finish(name, bm, material, loc, rot, parent)
    _bevel(o, bevel, 2)
    return o


def sphere(name, radius, loc, material, parent=None, scale=(1, 1, 1), segs: int = 24):
    bm = bmesh.new()
    bmesh.ops.create_uvsphere(bm, u_segments=segs, v_segments=segs // 2, radius=radius * MM)
    for v in bm.verts:
        v.co.x *= scale[0]
        v.co.y *= scale[1]
        v.co.z *= scale[2]
    return _finish(name, bm, material, loc, (0, 0, 0), parent, sharp_deg=80)


def ico(name, radius, loc, material, parent=None, subdiv: int = 2):
    bm = bmesh.new()
    bmesh.ops.create_icosphere(bm, subdivisions=subdiv, radius=radius * MM)
    return _finish(name, bm, material, loc, (0, 0, 0), parent, sharp_deg=5)


def plane(name, w, h, loc, material, parent=None, rot=(0, 0, 0)):
    bm = bmesh.new()
    bmesh.ops.create_grid(bm, x_segments=1, y_segments=1, size=0.5)
    for v in bm.verts:
        v.co.x *= w * MM
        v.co.y *= h * MM
    uv = bm.loops.layers.uv.new("UVMap")
    for f in bm.faces:
        for lp in f.loops:
            lp[uv].uv = (lp.vert.co.x / (w * MM) + 0.5, lp.vert.co.y / (h * MM) + 0.5)
    return _finish(name, bm, material, loc, rot, parent)


def tube(name, pts, radius, material, parent=None, order: int = 3):
    """Dây/cáp: NURBS đi qua gần các điểm điều khiển (mm, tọa độ cục bộ của parent)."""
    cu = bpy.data.curves.new(name, "CURVE")
    cu.dimensions = "3D"
    cu.bevel_depth = radius * MM
    cu.bevel_resolution = 3
    cu.use_fill_caps = True
    sp = cu.splines.new("NURBS")
    sp.points.add(len(pts) - 1)
    for i, p in enumerate(pts):
        sp.points[i].co = (p[0] * MM, p[1] * MM, p[2] * MM, 1.0)
    sp.use_endpoint_u = True
    sp.order_u = min(order, len(pts))
    sp.resolution_u = 12
    o = bpy.data.objects.new(name, cu)
    _collection().objects.link(o)
    cu.materials.append(material)
    if parent is not None:
        o.parent = parent
    return o


def text(name, body, size, loc, material, parent=None, rot=(0, 0, 0), bold: bool = True,
         extrude: float = 0.0, align: str = "CENTER"):
    cu = bpy.data.curves.new(name, "FONT")
    cu.body = body
    cu.font = bpy.data.fonts.load(FONT_BOLD if bold else FONT_REG, check_existing=True)
    cu.size = size * MM
    cu.align_x = align
    cu.align_y = "CENTER"
    cu.extrude = extrude * MM
    o = bpy.data.objects.new(name, cu)
    _collection().objects.link(o)
    cu.materials.append(material)
    if parent is not None:
        o.parent = parent
    o.location = tuple(v * MM for v in loc)
    o.rotation_euler = tuple(math.radians(a) for a in rot)
    return o


# ------------------------------------------------------------------ bảng màu dùng chung
def M():
    return {
        "pcb_black": mat("pcb_black", "#151617", 0.38),
        "pcb_green": mat("pcb_green", "#1F6B3B", 0.35),
        "pcb_blue": mat("pcb_blue", "#123A6B", 0.35),
        "shield": mat("shield", "#C9CDD2", 0.28, 1.0),
        "gold": mat("gold", "#D4A93C", 0.25, 1.0),
        "plastic_black": mat("plastic_black", "#1B1B1C", 0.45),
        "plastic_white": mat("plastic_white", "#F1F1EE", 0.38),
        "abs_dark": mat("abs_dark", "#2A2C30", 0.5),
        "alu": mat("alu", "#B9BDC3", 0.32, 0.85),
        "alu_dark": mat("alu_dark", "#33363B", 0.35, 0.7),
        "pole": mat("pole", "#8E949A", 0.35, 0.6),
        "rubber": mat("rubber", "#121212", 0.8),
        "red_cap": mat("red_cap", "#D01E1E", 0.22, coat=0.6),
        "glass_dark": mat("glass_dark", "#18202B", 0.06, coat=1.0),
        "lens": mat("lens", "#0B0D12", 0.05, coat=1.0),
        "ribbon": mat("ribbon", "#E9E1CF", 0.55),
        "domino": mat("domino", "#2F8A5A", 0.45),
        "ptc": mat("ptc", "#E3B21C", 0.4),
    }


LED_LIT = {"R": (1.0, 0.07, 0.04), "Y": (1.0, 0.62, 0.02), "G": (0.08, 1.0, 0.32)}
LED_OFF = {"R": "#4A1010", "Y": "#4A3A0E", "G": "#0F3D1E"}
WIRE = {"R": "#D7263D", "Y": "#F2C14E", "G": "#2BA84A", "K": "#1B1B1B", "B": "#2E6FD8",
        "W": "#EDEDED", "O": "#F08A24"}


def wire_mat(code: str) -> bpy.types.Material:
    return mat(f"wire_{code}", WIRE[code], 0.45)


# ------------------------------------------------------------------ linh kiện
def build_car(name: str, color: str, parent=None) -> bpy.types.Object:
    m = M()
    paint = mat(f"paint_{color}", color, 0.25, 0.25, coat=1.0)
    root = empty(name, parent=parent)
    box(f"{name}_body", (75, 31, 11), (0, 0, 9.5), paint, root, bevel=3.2)
    box(f"{name}_cabin", (38, 27, 9.5), (-5, 0, 19.5), m["glass_dark"], root, bevel=3.5)
    box(f"{name}_roof", (31, 25, 1.6), (-6, 0, 24.4), paint, root, bevel=0.7)
    for i, (x, y) in enumerate(((24, 13.5), (24, -13.5), (-23, 13.5), (-23, -13.5))):
        cyl(f"{name}_wheel{i}", 6.4, 5.2, (x, y, 6.4), m["rubber"], root, rot=(90, 0, 0), bevel=0.8)
    lamp = mat("car_tail", "#B3121A", 0.3, emit=(0.8, 0.02, 0.02), strength=0.6)
    for s in (1, -1):
        box(f"{name}_tail{s}", (1.2, 6, 2.2), (-37.6, s * 10, 11), lamp, root)
        box(f"{name}_head{s}", (1.2, 6, 2.2), (37.6, s * 10, 11), mat("car_head", "#F4F2E8", 0.2), root)
    return root


def build_light(name: str, state: str, parent=None) -> bpy.types.Object:
    """Cột + module đèn R/Y/G, mặt đèn quay về +x cục bộ."""
    m = M()
    root = empty(name, parent=parent)
    cyl(f"{name}_base", 6, 1.6, (0, 0, 0.8), m["pole"], root)
    cyl(f"{name}_pole", 2.2, 98, (0, 0, 49), m["pole"], root, segments=20)
    signal_face(name, state, root, x0=3.2, zc=76)
    return root


def signal_face(name: str, state: str, parent, x0: float, zc: float) -> None:
    """Một module R/Y/G (PCB 21 × 56 mm): mặt LED quay về +x cục bộ, PCB ở x0, tâm cao zc."""
    m = M()
    box(f"{name}_pcb", (1.6, 21, 56), (x0, 0, zc), m["pcb_black"], parent, bevel=0.4)
    box(f"{name}_visor", (6, 23, 1.2), (x0 + 3.3, 0, zc + 28.6), m["plastic_black"], parent)
    for i, c in enumerate("RYG"):
        z = zc + 17 - i * 17
        lm = (mat(f"led_{c}_on", "#FFFFFF", 0.2, emit=LED_LIT[c], strength=38.0) if c == state
              else mat(f"led_{c}_off", LED_OFF[c], 0.15, coat=1.0))
        cyl(f"{name}_led{c}", 2.6, 3.0, (x0 + 2.3, 0, z), lm, parent, rot=(0, 90, 0), segments=20)
        sphere(f"{name}_dome{c}", 2.6, (x0 + 3.8, 0, z), lm, parent, scale=(0.9, 1, 1), segs=16)


def build_signal_cluster(name: str, faces: list[tuple[str, float, str]], parent=None) -> bpy.types.Object:
    """Cụm đèn 4 mặt: 4 module R/Y/G ốp quanh lõi hộp 22 × 22 mm; gốc ở tâm cụm.
    faces: (tên, góc quay mặt quanh z theo độ, trạng thái R/Y/G)."""
    m = M()
    root = empty(name, parent=parent)
    box(f"{name}_core", (22, 22, 62), (0, 0, 0), m["plastic_black"], root, bevel=1.2)
    box(f"{name}_cap", (27, 27, 3), (0, 0, 32.5), m["plastic_black"], root, bevel=1.0)
    for key, yaw, state in faces:
        face = empty(f"{name}_{key}", rot_z=yaw, parent=root)
        signal_face(f"{name}_{key}", state, face, x0=11.8, zc=0)
    return root


def build_breadboard(name: str, tex_path: str, parent=None, loc=(0, 0, 0)) -> bpy.types.Object:
    m = M()
    root = empty(name, loc=loc, parent=parent)
    box(f"{name}_body", (165.1, 54.6, 8.5), (0, 0, 4.25), m["plastic_white"], root, bevel=0.8)
    plane(f"{name}_top", 165.1, 54.6, (0, 0, 8.52), img_mat("breadboard_top", tex_path, 0.45), root)
    return root


def build_esp32(name: str, parent=None, loc=(0, 0, 0)) -> bpy.types.Object:
    """NodeMCU-32S: PCB 48,3 × 25,4 mm, module ESP-WROOM-32 ở đầu +x, micro-USB ở đầu −x."""
    m = M()
    root = empty(name, loc=loc, parent=parent)
    for s in (1, -1):
        box(f"{name}_hdr{s}", (48, 2.5, 2.5), (0, s * 11.43, 1.25), m["plastic_black"], root)
    box(f"{name}_pcb", (48.3, 25.4, 1.6), (0, 0, 3.3), m["pcb_black"], root, bevel=0.3)
    box(f"{name}_modpcb", (25.5, 18, 0.8), (11.2, 0, 4.5), m["pcb_blue"], root)
    box(f"{name}_shield", (17.6, 16, 3.0), (7.6, 0, 6.4), m["shield"], root, bevel=0.3)
    box(f"{name}_usb", (6, 7.6, 2.8), (-22.6, 0, 5.5), m["shield"], root, bevel=0.4)
    for s in (1, -1):
        box(f"{name}_btn{s}", (4, 3.2, 1.6), (-16.5, s * 8.5, 4.9), m["shield"], root)
        cyl(f"{name}_btnc{s}", 1.0, 1.0, (-16.5, s * 8.5, 6.0), m["plastic_black"], root, segments=12)
    box(f"{name}_ldo", (6.5, 3.6, 1.6), (-9, 3, 4.9), m["plastic_black"], root)
    box(f"{name}_ch340", (5, 4, 1.4), (-9, -5, 4.8), m["plastic_black"], root)
    box(f"{name}_led", (1.6, 0.8, 0.6), (-4, 9.5, 4.4), mat("esp_led", "#3070FF", 0.3, emit=(0.2, 0.4, 1.0),
                                                            strength=1.2), root)
    return root


def build_button(name: str, parent=None, loc=(0, 0, 0)) -> bpy.types.Object:
    m = M()
    root = empty(name, loc=loc, parent=parent)
    box(f"{name}_house", (28, 28, 18), (0, 0, 9), m["plastic_black"], root, bevel=2.0)
    cyl(f"{name}_ring", 10.5, 2.0, (0, 0, 19), m["shield"], root, bevel=0.5)
    cyl(f"{name}_cap", 9.0, 6.0, (0, 0, 23), m["red_cap"], root, bevel=1.8)
    return root


def build_pi_case(name: str, parent=None, loc=(0, 0, 0)) -> bpy.types.Object:
    """Pi 5 trong vỏ ABS 91 × 62 × 35 mm; cổng USB/Ethernet ở đầu +x."""
    m = M()
    root = empty(name, loc=loc, parent=parent)
    box(f"{name}_case", (91, 62, 35), (0, 0, 17.5), m["abs_dark"], root, bevel=3.0)
    cyl(f"{name}_grille", 15, 0.6, (-8, 0, 35.1), m["plastic_black"], root)
    for i in range(5):
        box(f"{name}_slot{i}", (2.2, 26, 0.6), (-16 + i * 4, 0, 35.2), m["rubber"], root)
    box(f"{name}_eth", (2, 16, 13.5), (45.6, -19, 13), m["shield"], root)
    for j, y in enumerate((0.5, 18)):
        box(f"{name}_usb{j}", (2, 13.5, 14.5), (45.6, y, 13.5), m["shield"], root)
        box(f"{name}_usbin{j}", (2.2, 11, 2.2), (45.7, y, 9.5),
            mat("usb3_blue", "#2B5FD9", 0.4) if j == 0 else m["plastic_black"], root)
    box(f"{name}_led", (0.8, 2, 1.2), (-45.6, 20, 5), mat("pi_led", "#33FF66", 0.3, emit=(0.1, 1, 0.3),
                                                          strength=8.0), root)
    return root


def build_camera_module(name: str, parent=None, loc=(0, 0, 0)) -> bpy.types.Object:
    """Camera Module 3 Wide: PCB 25 × 24 mm, ống kính hướng xuống −z."""
    m = M()
    root = empty(name, loc=loc, parent=parent)
    box(f"{name}_pcb", (25, 24, 1.0), (0, 0, 0), m["pcb_green"], root, bevel=0.3)
    box(f"{name}_holder", (8.5, 8.5, 4.5), (0, 2.5, -2.75), m["plastic_black"], root, bevel=0.4)
    cyl(f"{name}_barrel", 3.6, 2.4, (0, 2.5, -6.2), m["plastic_black"], root)
    sphere(f"{name}_glass", 3.0, (0, 2.5, -7.4), m["lens"], root, scale=(1, 1, 0.45), segs=20)
    box(f"{name}_conn", (22, 5.5, 2.2), (0, -9, 1.6), m["plastic_black"], root)
    return root


def build_router(name: str, parent=None, loc=(0, 0, 0), rot_z: float = 0.0) -> bpy.types.Object:
    m = M()
    root = empty(name, loc=loc, rot_z=rot_z, parent=parent)
    box(f"{name}_body", (125, 90, 28), (0, 0, 14), m["plastic_white"], root, bevel=6.0)
    for s in (1, -1):
        cyl(f"{name}_ant{s}", 4.2, 115, (s * 48, 42, 75), m["plastic_black"], root,
            rot=(-12, s * 8, 0), bevel=1.5)
    for i in range(4):
        cyl(f"{name}_led{i}", 1.2, 0.8, (-30 + i * 14, -45.3, 18), mat("router_led", "#22DD66", 0.3,
                                                                       emit=(0.1, 1, 0.35), strength=10.0),
            root, rot=(90, 0, 0), segments=12)
    return root


def build_laptop(name: str, screen_tex: str, parent=None, loc=(0, 0, 0), rot_z: float = 0.0,
                 open_deg: float = 108.0) -> bpy.types.Object:
    m = M()
    root = empty(name, loc=loc, rot_z=rot_z, parent=parent)
    box(f"{name}_base", (315, 218, 14), (0, 0, 7), m["alu"], root, bevel=4.0)
    box(f"{name}_kbd", (272, 98, 0.6), (0, 35, 14.1), mat("kbd", "#26282C", 0.6), root, bevel=0.2)
    box(f"{name}_pad", (110, 66, 0.4), (0, -55, 14.05), mat("pad", "#A9ADB3", 0.25, 0.7), root, bevel=0.3)
    hinge = empty(f"{name}_hinge", loc=(0, 109, 14), parent=root)
    hinge.rotation_euler = (math.radians(-(open_deg - 90)), 0, 0)  # nghiêng nắp ra sau
    box(f"{name}_lid", (315, 6, 212), (0, 3, 106), m["alu"], hinge, bevel=3.0)
    box(f"{name}_bezel", (305, 0.6, 200), (0, -0.25, 108), mat("bezel", "#0B0B0D", 0.3), hinge)
    plane(f"{name}_screen", 288, 180, (0, -0.65, 110), img_mat("screen", screen_tex, 0.2, emissive=1.6),
          hinge, rot=(90, 0, 0))
    return root


def build_tree(name: str, seed: int, parent=None, loc=(0, 0, 0)) -> bpy.types.Object:
    root = empty(name, loc=loc, parent=parent)
    greens = ["#4E8A3B", "#5B9A45", "#3F7633", "#6AA24E"]
    leaf = mat(f"leaf{seed % 4}", greens[seed % 4], 0.85)
    cyl(f"{name}_trunk", 2.6, 26, (0, 0, 13), mat("trunk", "#6B4F32", 0.8), root, segments=12)
    r = 19 + (seed * 7) % 8
    ico(f"{name}_crown", r, (0, 0, 26 + r * 0.85), leaf, root, subdiv=2)
    ico(f"{name}_crown2", r * 0.7, (r * 0.45, r * 0.2, 26 + r * 1.25), leaf, root, subdiv=1)
    return root


def build_adapter(name: str, parent=None, loc=(0, 0, 0), rot_z: float = 0.0, white: bool = False):
    m = M()
    root = empty(name, loc=loc, rot_z=rot_z, parent=parent)
    box(f"{name}_brick", (82, 46, 30), (0, 0, 15), m["plastic_white"] if white else m["plastic_black"], root,
        bevel=4.0)
    return root


def build_power_strip(name: str, parent=None, loc=(0, 0, 0), rot_z: float = 0.0):
    m = M()
    root = empty(name, loc=loc, rot_z=rot_z, parent=parent)
    box(f"{name}_body", (300, 58, 40), (0, 0, 20), m["plastic_white"], root, bevel=5.0)
    for i in range(4):
        cyl(f"{name}_sock{i}", 15, 1.0, (-105 + i * 64, 0, 40.3), mat("socket", "#DCDCD8", 0.5), root)
        for s in (1, -1):
            cyl(f"{name}_hole{i}{s}", 2.2, 1.2, (-105 + i * 64 + s * 9.5, 0, 40.6), m["rubber"], root,
                segments=10)
    box(f"{name}_switch", (16, 26, 8), (128, 0, 42), mat("sw_red", "#C62828", 0.3), root, bevel=2.0)
    return root


def build_profile(name: str, length: float, loc, axis: str, material, parent=None):
    """Thanh nhôm định hình 20 × 20 (giản lược, có rãnh)."""
    dims = {"x": (length, 20, 20), "y": (20, length, 20), "z": (20, 20, length)}[axis]
    o = box(name, dims, loc, material, parent, bevel=1.2)
    groove = M()["rubber"]
    for s in (1, -1):
        if axis == "z":
            box(f"{name}_g{s}", (0.6, 6, length - 4), (loc[0] + s * 10, loc[1], loc[2]), groove, parent)
        elif axis == "y":
            box(f"{name}_g{s}", (0.6, length - 4, 6), (loc[0] + s * 10, loc[1], loc[2]), groove, parent)
    return o


def ensure_dir(path: str) -> str:
    os.makedirs(path, exist_ok=True)
    return path


def build_pi_board(name: str, parent=None, loc=(0, 0, 0), rot_z: float = 0.0) -> bpy.types.Object:
    """Raspberry Pi 5 trần (85 × 56 mm) có tản nhiệt + quạt; cổng USB/Ethernet ở đầu +x."""
    m = M()
    root = empty(name, loc=loc, rot_z=rot_z, parent=parent)
    box(f"{name}_pcb", (85, 56, 1.4), (0, 0, 0.7), mat("pi_pcb", "#1C7A3F", 0.35), root, bevel=2.5)
    box(f"{name}_ram", (12, 14, 1.2), (-2, 8, 2.0), m["plastic_black"], root, bevel=0.3)
    box(f"{name}_rp1", (8, 8, 1.0), (18, -8, 1.9), m["plastic_black"], root, bevel=0.3)
    box(f"{name}_sink", (24, 24, 7), (-17, -4, 5.0), m["alu_dark"], root, bevel=0.8)
    cyl(f"{name}_fan", 9.5, 1.2, (-17, -4, 9.1), m["plastic_black"], root, segments=28)
    cyl(f"{name}_hub", 3.5, 1.4, (-17, -4, 9.5), m["abs_dark"], root, segments=20)
    box(f"{name}_eth", (21, 16, 13.5), (34, -19, 8.2), m["shield"], root, bevel=0.4)
    for j, y in enumerate((0.5, 18)):
        box(f"{name}_usb{j}", (17, 13.5, 15.5), (36, y, 9.2), m["shield"], root, bevel=0.4)
        box(f"{name}_usbin{j}", (0.6, 11, 2.2), (44.7, y, 6.0),
            mat("usb3_blue", "#2B5FD9", 0.4) if j == 0 else m["plastic_black"], root)
    box(f"{name}_hdr", (51, 5, 8.5), (-6, 24.5, 5.6), m["plastic_black"], root)
    for i in range(20):
        for r in (-1.27, 1.27):
            box(f"{name}_pin{i}{r}", (0.64, 0.64, 6), (-30.2 + i * 2.54, 24.5 + r, 12.5), m["gold"], root)
    for k, x in enumerate((-29, -15.5)):
        box(f"{name}_hdmi{k}", (7.5, 6, 3.4), (x, -25.5, 3.1), m["shield"], root, bevel=0.3)
    box(f"{name}_usbc", (9, 7.5, 3.4), (-37.5, -25, 3.1), m["shield"], root, bevel=1.2)
    for k, x in enumerate((2, 12)):
        box(f"{name}_fpc{k}", (9, 4, 2.2), (x, -24.5, 2.5), mat("fpc_white", "#EDEDE6", 0.4), root)
    return root


def build_ribbon(name: str, length: float, parent=None, loc=(0, 0, 0), rot_z: float = 0.0):
    """Cáp FPC 22→15 pin nằm cong nhẹ trên mặt bàn."""
    root = empty(name, loc=loc, rot_z=rot_z, parent=parent)
    pts = [(0, 0, 0.6), (length * 0.3, 8, 0.6), (length * 0.6, -6, 0.6), (length, 0, 0.6)]
    cu = bpy.data.curves.new(name, "CURVE")
    cu.dimensions = "3D"
    cu.extrude = 7 * MM
    sp = cu.splines.new("NURBS")
    sp.points.add(len(pts) - 1)
    for i, p in enumerate(pts):
        sp.points[i].co = (p[0] * MM, p[1] * MM, p[2] * MM, 1.0)
        sp.points[i].tilt = math.pi / 2  # dải phẳng nằm trên mặt bàn
    sp.use_endpoint_u = True
    sp.order_u = 3
    o = bpy.data.objects.new(name + "_strip", cu)
    _collection().objects.link(o)
    cu.materials.append(M()["ribbon"])
    o.parent = root
    return root
