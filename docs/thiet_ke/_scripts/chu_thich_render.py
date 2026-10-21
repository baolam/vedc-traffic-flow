"""Thêm chú thích (callout), ROI và kích thước lên ảnh render Blender.

Đầu vào : 4.4_hinh_minh_hoa/renders/raw/*.png + renders/anchors.json (do dung_canh.py xuất)
Đầu ra  : 4.4_hinh_minh_hoa/renders/H4.x_*.png và 3.4_linh_kien/H3.5_linh_kien_chinh.png
          (H4.1 tổng quan · H4.2 trụ J1 · H4.3 nút J1 · H4.4 hai camera + ROI · H4.5 nhìn từ trên · H4.6 mặt đứng)
Chạy    : python3 _scripts/chu_thich_render.py
"""
from __future__ import annotations

import json
import math
import sys
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont

ROOT = Path(__file__).resolve().parents[1]
REN = ROOT / "4.4_hinh_minh_hoa" / "renders"
RAW = REN / "raw"
sys.path.insert(0, str(ROOT / "4.4_hinh_minh_hoa" / "blender"))
import bo_tri as L  # noqa: E402

F_REG = "/System/Library/Fonts/Supplemental/Arial.ttf"
F_BOLD = "/System/Library/Fonts/Supplemental/Arial Bold.ttf"
INK = (28, 30, 34)
MUTED = (88, 92, 100)
BLUE = (37, 99, 168)
ORANGE = (214, 106, 32)
TAG = "Render 3D minh họa · bố trí đề xuất, không phải ảnh chụp"


def font(px: int, bold: bool = False) -> ImageFont.FreeTypeFont:
    return ImageFont.truetype(F_BOLD if bold else F_REG, px)


def load(view: str) -> tuple[Image.Image, dict]:
    data = json.loads((REN / "anchors.json").read_text())
    im = Image.open(RAW / f"{view}.png").convert("RGBA")
    entry = data[view]
    sx = im.width / entry["res"][0]
    sy = im.height / entry["res"][1]
    anchors = {k: (v[0] * sx, v[1] * sy) for k, v in entry["anchors"].items()}
    entry["scaled"] = anchors
    entry["sx"] = sx
    return im, entry


def tag(im: Image.Image, text: str = TAG) -> None:
    d = ImageDraw.Draw(im)
    s = im.width / 2400
    f = font(int(22 * s))
    w = d.textlength(text, font=f)
    pad = 10 * s
    x1, y1 = im.width - 24 * s, im.height - 22 * s
    d.rounded_rectangle([x1 - w - 2 * pad, y1 - 34 * s, x1, y1], radius=8 * s, fill=(255, 255, 255, 215))
    d.text((x1 - pad, y1 - 17 * s), text, font=f, fill=MUTED, anchor="rm")


def callout(im: Image.Image, anchor: tuple[float, float], offset: tuple[float, float], title: str,
            sub: str | None = None, color=INK) -> None:
    """Chấm tại điểm neo, đường dẫn và nhãn bo góc (offset tính theo ảnh rộng 2400 px)."""
    d = ImageDraw.Draw(im)
    s = im.width / 2400
    ax, ay = anchor
    cx, cy = ax + offset[0] * s, ay + offset[1] * s
    ft, fs = font(int(30 * s), True), font(int(23 * s))
    tw = d.textlength(title, font=ft)
    sw = d.textlength(sub, font=fs) if sub else 0
    w = max(tw, sw) + 34 * s
    h = (44 if not sub else 76) * s
    box = [cx - w / 2, cy - h / 2, cx + w / 2, cy + h / 2]
    # đường dẫn tới cạnh gần nhất của nhãn
    ex = min(max(ax, box[0]), box[2])
    ey = min(max(ay, box[1]), box[3])
    d.line([(ax, ay), (ex, ey)], fill=(255, 255, 255, 235), width=max(1, int(6 * s)))
    d.line([(ax, ay), (ex, ey)], fill=color, width=max(1, int(2.6 * s)))
    r = 7 * s
    d.ellipse([ax - r - 2 * s, ay - r - 2 * s, ax + r + 2 * s, ay + r + 2 * s], fill=(255, 255, 255, 240))
    d.ellipse([ax - r, ay - r, ax + r, ay + r], fill=color)
    d.rounded_rectangle(box, radius=12 * s, fill=(255, 255, 255, 238), outline=color, width=max(1, int(2.2 * s)))
    if sub:
        d.text((cx, cy - 15 * s), title, font=ft, fill=INK, anchor="mm")
        d.text((cx, cy + 19 * s), sub, font=fs, fill=MUTED, anchor="mm")
    else:
        d.text((cx, cy), title, font=ft, fill=INK, anchor="mm")


def save(im: Image.Image, path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    im.convert("RGB").save(path, optimize=True)
    print("->", path.relative_to(ROOT))


def _affine(a: dict, k1: str, k2: str, w1, w2):
    """Ánh xạ tuyến tính world (mm) → pixel từ 2 điểm neo của ảnh trực giao."""
    (p1x, p1y), (p2x, p2y) = a[k1], a[k2]
    sx = (p2x - p1x) / (w2[0] - w1[0]) if w2[0] != w1[0] else None
    sy = (p2y - p1y) / (w2[1] - w1[1]) if w2[1] != w1[1] else None
    return lambda x, y: (p1x + (x - w1[0]) * sx, p1y + (y - w1[1]) * sy)


def dim(d: ImageDraw.ImageDraw, p1, p2, text: str, s: float, color=INK, text_side: int = -1) -> None:
    """Đường kích thước có mũi tên hai đầu và chữ ở giữa."""
    d.line([p1, p2], fill=color, width=max(1, int(2.4 * s)))
    ang = math.atan2(p2[1] - p1[1], p2[0] - p1[0])
    for (x, y), a0 in ((p1, ang), (p2, ang + math.pi)):
        L_ = 16 * s
        for da in (0.4, -0.4):
            d.line([(x, y), (x + L_ * math.cos(a0 + da), y + L_ * math.sin(a0 + da))], fill=color,
                   width=max(1, int(2.4 * s)))
    f = font(int(27 * s), True)
    mx, my = (p1[0] + p2[0]) / 2, (p1[1] + p2[1]) / 2
    w = d.textlength(text, font=f)
    vertical = abs(p2[0] - p1[0]) < abs(p2[1] - p1[1])
    if vertical:
        tx, ty = mx + text_side * (w / 2 + 14 * s), my
    else:
        tx, ty = mx, my + text_side * 24 * s
    d.rounded_rectangle([tx - w / 2 - 8 * s, ty - 18 * s, tx + w / 2 + 8 * s, ty + 18 * s], radius=6 * s,
                        fill=(255, 255, 255, 235))
    d.text((tx, ty), text, font=f, fill=color, anchor="mm")


def ext(d, p1, p2, s, color=MUTED):
    d.line([p1, p2], fill=color, width=max(1, int(1.4 * s)))


# ------------------------------------------------------------------ số liệu dẫn ra từ bo_tri.py
NODE_COL = {"J1": BLUE, "J2": ORANGE}
CSI_MM = max(L.polyline_len(L.csi_route(n)) for n in L.JUNCTIONS)
CSI_TXT = f"{CSI_MM / 1000:.2f}".replace(".", ",")          # số thập phân kiểu Việt
POLE_TOP = L.ARM_Z + 10
CAM_NOTE = ("Render 3D: góc nhìn mô phỏng của Camera Module 3 Wide trên trụ {n} "
            "(chưa tính méo ống kính)")


def half_cover_x(h: float = L.CAMERA_H) -> float:
    """Nửa bề rộng vùng nhìn trên mặt sa bàn, đo dọc trục Đông–Tây qua tâm ngã tư (khung hình xoay 45°)."""
    a = h * math.tan(math.radians(L.CAM_HFOV_DEG / 2))
    b = h * math.tan(math.radians(L.CAM_VFOV_DEG / 2))
    t = math.radians(abs(L.arm_yaw("J1")))
    return min(a / abs(math.cos(t)) if math.cos(t) else 1e9, b / abs(math.sin(t)) if math.sin(t) else 1e9)


def dashed(d: ImageDraw.ImageDraw, pts, color, width: int, dash: float, gap: float) -> None:
    """Đường gấp khúc kín, nét đứt."""
    for (x0, y0), (x1, y1) in zip(pts, pts[1:] + pts[:1]):
        n = math.hypot(x1 - x0, y1 - y0)
        k = 0.0
        while k < n:
            e = min(k + dash, n)
            d.line([(x0 + (x1 - x0) * k / n, y0 + (y1 - y0) * k / n),
                    (x0 + (x1 - x0) * e / n, y0 + (y1 - y0) * e / n)], fill=color, width=width)
            k += dash + gap


def roi_overlay(im: Image.Image, rois: dict, s: float, fs: int) -> Image.Image:
    over = Image.new("RGBA", im.size, (0, 0, 0, 0))
    d = ImageDraw.Draw(over)
    for name, poly in rois.items():
        col = NODE_COL[name[:2]]
        d.polygon(poly, fill=(*col, 70), outline=(*col, 255), width=max(2, int(3 * s)))
    im = Image.alpha_composite(im, over)
    d = ImageDraw.Draw(im)
    f = font(fs, True)
    for name, poly in rois.items():
        col = NODE_COL[name[:2]]
        cx = sum(p[0] for p in poly) / len(poly)
        cy = sum(p[1] for p in poly) / len(poly)
        w = d.textlength(name, font=f) + 16 * s
        d.rounded_rectangle([cx - w / 2, cy - fs * 0.8, cx + w / 2, cy + fs * 0.8], radius=8 * s, fill=(*col, 235))
        d.text((cx, cy), name, font=f, fill=(255, 255, 255), anchor="mm")
    return im


# ------------------------------------------------------------------ từng hình
def hero() -> None:
    im, e = load("hero")
    a = e["scaled"]
    items = [
        ("cam_J1", (-295, -183), "Camera Module 3 Wide", f"đầu cần trụ J1, nhìn thẳng xuống, cao {int(L.CAMERA_H)} mm"),
        ("pole_J1", (-470, -40), "Trụ giao thông J1", "nhôm định hình 20 × 20 · camera + đèn"),
        ("pole_J2", (-19, -267), "Trụ giao thông J2", "mỗi ngã tư một trụ, một camera"),
        ("signal_J2", (179, -353), "Cụm đèn 4 mặt", "4 module R/Y/G · Bắc–Nam và Đông–Tây mắc song song"),
        ("pi", (307, 160), "Raspberry Pi 5 (AI thị giác)", "tủ giữa hai trụ · 2 cáp CSI dài 1 m"),
        ("router", (-20, 186), "Router Wi-Fi 2.4 GHz", "LAN riêng, không cần Internet"),
        ("laptop", (91, 233), "Laptop điều phối", "Mosquitto · Graph-Control · dashboard"),
        ("J1", (-250, 53), "Ngã tư J1", None),
        ("J2", (191, 18), "Ngã tư J2", None),
        ("esp_J1", (-400, 153), "ESP32 J1 trên breadboard", "dây đèn đi dưới mặt sa bàn, lên trụ"),
        ("esp_J2", (338, -26), "ESP32 J2", None),
        ("stop_J1", (-24, 205), "Nút safe-stop", "mỗi nút đèn một nút riêng"),
        ("power", (223, 180), "Nguồn 5 V + bảo vệ", "jack DC · PTC · Schottky"),
        ("adapter", (156, -126), "Adapter 5 V / 4 A", None),
    ]
    clean = im.copy()
    tag(clean)
    save(clean, REN / "H4.1_tong_quan_sa_ban_khong_chu_thich.png")
    for key, off, t, sub in items:
        if key in a:
            callout(im, a[key], off, t, sub)
    tag(im)
    save(im, REN / "H4.1_tong_quan_sa_ban.png")


def pole() -> None:
    im, e = load("pole")
    a = e["scaled"]
    items = [
        ("cam_J1", (-425, -163), "Camera Module 3 Wide",
         f"ống kính cao {int(L.CAMERA_H)} mm, nhìn thẳng xuống tâm ngã tư"),
        ("arm_J1", (459, -102), "Cần camera nhôm 20 × 20", f"vươn chéo {int(round(L.arm_len()))} mm, có thanh giằng"),
        ("signal_J1", (-521, -99), "Cụm đèn 4 mặt (4 module R/Y/G)",
         f"tâm cao {int(L.SIGNAL_H)} mm · mỗi mặt quay về một hướng xe tới"),
        ("pole_J1", (415, -43), "Trụ nhôm 20 × 20", f"cao {int(POLE_TOP)} mm, đế bắt vít vào sa bàn"),
        ("sigcable_J1", (-470, 120), "Cáp 8 lõi xuống ESP32", "7 lõi: R/Y/G × 2 pha + GND, đi dưới sa bàn"),
        ("pi", (158, -332), "Raspberry Pi 5 trong vỏ ABS", "CAM0 → camera J1 · CAM1 → camera J2"),
        ("csi_J1", (-153, 179), "Cáp CSI 22 → 15 pin",
         f"đi trong rãnh trụ và trên lưng cần, ~{CSI_TXT} m → dùng cáp 1 m"),
    ]
    for key, off, t, sub in items:
        if key in a and 0 < a[key][0] < im.width and 0 < a[key][1] < im.height:
            callout(im, a[key], off, t, sub)
    tag(im)
    save(im, REN / "H4.2_can_canh_tru_giao_thong_J1.png")


def closeup() -> None:
    im, e = load("closeup")
    a = e["scaled"]
    items = [
        ("esp_J1", (330, 290), "ESP32 NodeMCU-32S (nút J1)", "ESP-WROOM-32 · CH340 · micro-USB"),
        ("bb_J1", (-380, 200), "2 breadboard 830 lỗ ghép đôi", None),
        ("slot_J1", (-420, -170), "7 dây: GPIO 23/22/21 · 19/18/5 · GND",
         "đi dưới sa bàn, lên trụ J1 tới cụm đèn 4 mặt"),
        ("stop_J1", (240, 230), "Nút safe-stop tự giữ", "GPIO 4 ↔ GND, active-LOW"),
        ("power", (-170, -250), "Nguồn 5 V chung", "jack DC · domino · PTC"),
    ]
    for key, off, t, sub in items:
        if key in a and 0 < a[key][0] < im.width and 0 < a[key][1] < im.height:
            callout(im, a[key], off, t, sub)
    tag(im)
    save(im, REN / "H4.3_can_canh_nut_J1.png")


def camera_one(node: str) -> tuple[Image.Image, Image.Image]:
    im, e = load(f"cam_{node}")
    s = im.width / 1920
    note = CAM_NOTE.format(n=node)
    clean = im.copy()
    tag(clean, note)
    rois = {k: [(x * e["sx"], y * e["sx"]) for x, y in pts] for k, pts in e["rois"].items()}
    im = roi_overlay(im, rois, s, int(19 * s))
    d = ImageDraw.Draw(im)
    fb = font(int(30 * s), True)
    head = f"Camera trụ {node} · VISION_NODE_IDS={node}"
    w = d.textlength(head, font=fb)
    d.rounded_rectangle([20 * s, 18 * s, 48 * s + w, 66 * s], radius=10 * s, fill=(*NODE_COL[node], 235))
    d.text((34 * s, 42 * s), head, font=fb, fill=(255, 255, 255), anchor="lm")
    tag(im, note)
    return clean, im


def camera_views() -> None:
    panels = []
    for node in L.JUNCTIONS:
        clean, roi = camera_one(node)
        save(clean, REN / f"H4.4{'ab'[len(panels)]}_goc_nhin_camera_{node}.png")
        save(roi, REN / f"H4.4{'ab'[len(panels)]}_goc_nhin_camera_{node}_ROI.png")
        panels.append(roi)
    gap = int(24 * panels[0].width / 1920)
    w, h = panels[0].width, panels[0].height
    sheet = Image.new("RGBA", (w, 2 * h + gap + 70), (255, 255, 255, 255))
    for i, pnl in enumerate(panels):
        sheet.alpha_composite(pnl, (0, i * (h + gap)))
    d = ImageDraw.Draw(sheet)
    note = ("ROI minh họa theo topology, mỗi camera chỉ báo cho nút của mình. "
            "Trên sa bàn thật phải vẽ lại bằng services/vision/roi_calibrate.py")
    d.text((w / 2, 2 * h + gap + 35), note, font=font(int(24 * w / 1920)), fill=INK, anchor="mm")
    save(sheet, REN / "H4.4_goc_nhin_hai_camera_ROI.png")


def top_view() -> None:
    im, e = load("top")
    a = e["scaled"]
    hw, hh = L.BOARD_W / 2, L.BOARD_H / 2
    P = _affine(a, "board_WN", "board_ES", (-hw, hh), (hw, -hh))
    s = im.width / 2400
    over = Image.new("RGBA", im.size, (0, 0, 0, 0))
    d = ImageDraw.Draw(over)
    # ROI và vùng nhìn của từng camera
    for node in L.JUNCTIONS:
        col = NODE_COL[node]
        for appr in "NSEW":
            d.polygon([P(x, y) for x, y in L.roi_rect(node, appr)], fill=(*col, 80), outline=(*col, 230))
        dashed(d, [P(x, y) for x, y in L.camera_footprint(node)], (*col, 255), max(2, int(3.4 * s)),
               16 * s, 10 * s)
    top_y = P(0, hh)[1] - 60 * s
    # 1189 mm
    ext(d, P(-hw, hh), (P(-hw, hh)[0], top_y - 10 * s), s)
    ext(d, P(hw, hh), (P(hw, hh)[0], top_y - 10 * s), s)
    dim(d, (P(-hw, hh)[0], top_y), (P(hw, hh)[0], top_y), "1189 mm (tấm A0)", s)
    # 560 mm giữa hai ngã tư
    (j1x, _), (j2x, _) = L.JUNCTIONS["J1"], L.JUNCTIONS["J2"]
    y2 = top_y - 70 * s
    for jx in (j1x, j2x):
        ext(d, P(jx, hh), (P(jx, 0)[0], y2 - 10 * s), s, color=(*BLUE, 200))
    dim(d, (P(j1x, 0)[0], y2), (P(j2x, 0)[0], y2), f"{int(j2x - j1x)} mm giữa tâm J1 và J2", s, BLUE)
    # 841 mm
    rx = P(hw, 0)[0] + 70 * s
    ext(d, P(hw, hh), (rx + 10 * s, P(hw, hh)[1]), s)
    ext(d, P(hw, -hh), (rx + 10 * s, P(hw, -hh)[1]), s)
    dim(d, (rx, P(hw, hh)[1]), (rx, P(hw, -hh)[1]), "841 mm", s, text_side=1)
    # bề rộng đường
    lx = P(-hw, 0)[0] - 60 * s
    r = L.ROAD_W / 2
    ext(d, P(-hw, r), (lx - 10 * s, P(-hw, r)[1]), s)
    ext(d, P(-hw, -r), (lx - 10 * s, P(-hw, -r)[1]), s)
    dim(d, (lx, P(-hw, r)[1]), (lx, P(-hw, -r)[1]), f"đường {int(L.ROAD_W)} mm", s)
    # dải mạch điện phía trước
    fy0, fy1 = P(0, -hh)[1], P(0, -hh - L.BASE_FRONT)[1]
    dim(d, (lx, fy0), (lx, fy1), f"dải mạch {int(L.BASE_FRONT)} mm", s)
    im = Image.alpha_composite(im, over)
    d = ImageDraw.Draw(im)
    for node, (jx, jy) in L.JUNCTIONS.items():  # trục camera = tâm ngã tư
        cx, cy = P(jx, jy)
        R = 13 * s
        d.ellipse([cx - R, cy - R, cx + R, cy + R], outline=(200, 30, 30), width=max(1, int(3 * s)))
        d.line([(cx - 2 * R, cy), (cx + 2 * R, cy)], fill=(200, 30, 30), width=max(1, int(2 * s)))
        d.line([(cx, cy - 2 * R), (cx, cy + 2 * R)], fill=(200, 30, 30), width=max(1, int(2 * s)))
    side = {"J1": -1, "J2": 1}
    callout(im, P(*L.JUNCTIONS["J1"]), (-260, 330), "Trục camera J1 = tâm ngã tư",
            "nét đứt: vùng nhìn trên mặt sa bàn", color=BLUE)
    callout(im, P(*L.JUNCTIONS["J2"]), (330, 330), "Trục camera J2 = tâm ngã tư",
            "ô màu: 4 ROI của nút", color=ORANGE)
    for node in L.JUNCTIONS:
        callout(im, P(*L.pole_xy(node)), (side[node] * 150, -290), f"Chân trụ {node}",
                f"cách tâm {int(L.POLE_OFF)} mm mỗi trục", color=NODE_COL[node])
    callout(im, P(*L.PI_XY), (0, -330), "Raspberry Pi 5",
            f"cáp CSI mỗi bên ~{CSI_TXT} m (dùng cáp 1 m)")
    tag(im)
    save(im, REN / "H4.5_ban_ve_bo_tri_nhin_tu_tren.png")


def front_view() -> None:
    im, e = load("front")
    pad = int(260 * im.width / 2400)
    bg = Image.new("RGBA", (im.width, im.height + pad), (255, 255, 255, 255))
    bg.alpha_composite(im)
    im = bg
    a = e["scaled"]
    s = im.width / 2400
    z_top = L.BASE_H + L.BOARD_T
    (j1x, _), (j2x, _) = L.JUNCTIONS["J1"], L.JUNCTIONS["J2"]
    # ảnh nhìn từ phía Nam: trục ngang ảnh = x thế giới, trục đứng = −z
    P = _affine(a, "lens_J1", "board_under_J2", (j1x, z_top + L.CAMERA_H), (j2x, z_top))
    over = Image.new("RGBA", im.size, (0, 0, 0, 0))
    d = ImageDraw.Draw(over)
    hx = half_cover_x()
    hw = L.BOARD_W / 2
    for node, (jx, _) in L.JUNCTIONS.items():
        col = NODE_COL[node]
        d.polygon([P(jx, z_top + L.CAMERA_H), P(jx - hx, z_top), P(jx + hx, z_top)], fill=(*col, 34))
    for node, (jx, _) in L.JUNCTIONS.items():  # vẽ nét sau phần tô để hai vùng chồng nhau vẫn thấy biên
        lens = P(jx, z_top + L.CAMERA_H)
        for g in (P(jx - hx, z_top), P(jx + hx, z_top)):
            d.line([lens, g], fill=(*NODE_COL[node], 255), width=max(1, int(2.6 * s)))
    # chiều cao ống kính và cụm đèn (trụ J1)
    xl = P(-hw, 0)[0] - 40 * s
    lens1 = P(j1x, z_top + L.CAMERA_H)
    sig1 = P(j1x, z_top + L.SIGNAL_H)
    base = P(j1x, z_top)
    ext(d, lens1, (xl - 10 * s, lens1[1]), s)
    ext(d, sig1, (xl + 110 * s, sig1[1]), s)
    ext(d, (P(-hw, z_top)[0], base[1]), (xl - 10 * s, base[1]), s)
    dim(d, (xl, lens1[1]), (xl, base[1]), f"{int(L.CAMERA_H)} mm", s, text_side=-1)
    dim(d, (xl + 100 * s, sig1[1]), (xl + 100 * s, base[1]), f"{int(L.SIGNAL_H)} mm", s, text_side=1)
    # vùng nhìn dọc trục Đông–Tây và phần chồng lấn
    yb = P(0, 0)[1] + 50 * s
    for node, (jx, _) in L.JUNCTIONS.items():
        x0, x1 = max(jx - hx, -hw), min(jx + hx, hw)
        y = yb + (0 if node == "J1" else 70 * s)
        dim(d, (P(x0, 0)[0], y), (P(x1, 0)[0], y), f"camera {node}: {int(x1 - x0)} mm của tấm A0", s,
            NODE_COL[node], text_side=1)
    ov = 2 * hx - (j2x - j1x)
    yb2 = yb + 160 * s
    dim(d, (P(-ov / 2, 0)[0], yb2), (P(ov / 2, 0)[0], yb2), f"chồng lấn {int(ov)} mm", s, text_side=1)
    im = Image.alpha_composite(im, over)
    callout(im, a["cam_J2"], (300, -40), "Camera J2", f"cao {int(L.CAMERA_H)} mm như J1")
    callout(im, a["signal_J2"], (330, -60), "Cụm đèn 4 mặt J2", None)
    callout(im, a["pi"], (0, -230), "Raspberry Pi 5", "2 cổng CSI: CAM0 → J1, CAM1 → J2")
    tag(im, "Render 3D minh họa · mặt đứng nhìn từ phía Nam · vùng nhìn tính theo góc 102° × 67°, khung xoay 45°")
    save(im, REN / "H4.6_mat_dung_do_cao_tru.png")


def parts() -> None:
    im, e = load("parts")
    a = e["scaled"]
    s = im.width / 2400
    d = ImageDraw.Draw(im)
    names = {
        "router": ("Router Wi-Fi 2.4 GHz", "LAN riêng cho MQTT"),
        "pi5": ("Raspberry Pi 5 (4 GB)", "kèm tản nhiệt + quạt 5 V"),
        "adapter": ("Adapter 5 V / 4 A", "jack DC 5.5 × 2.1 mm"),
        "breadboard": ("Breadboard 830 lỗ", "2 tấm ghép cho mỗi nút"),
        "esp32": ("ESP32 NodeMCU-32S", "CH340 · micro-USB"),
        "camera": ("Camera Module 3 Wide × 2", "mỗi trụ một camera · cáp FPC 22 → 15 pin 1 m"),
        "light": ("Module đèn LED R/Y/G", "4 module ghép thành cụm 4 mặt"),
        "button": ("Nút nhấn tự giữ", "safe-stop, GPIO 4"),
        "power": ("Jack DC · domino · PTC · 1N5819", "bảo vệ đường 5 V"),
    }
    ft, fs = font(int(31 * s), True), font(int(24 * s))
    for k, (t, sub) in names.items():
        x, y = a[k]
        d.text((x, y + 6 * s), t, font=ft, fill=INK, anchor="mt")
        d.text((x, y + 46 * s), sub, font=fs, fill=MUTED, anchor="mt")
    tag(im, "Render 3D minh họa · đúng tỉ lệ kích thước thật")
    save(im, ROOT / "3.4_linh_kien" / "H3.5_linh_kien_chinh.png")


def main() -> int:
    views = sys.argv[1:] or ["hero", "pole", "closeup", "cams", "top", "front", "parts"]
    fns = {"hero": hero, "pole": pole, "closeup": closeup, "cams": camera_views, "top": top_view,
           "front": front_view, "parts": parts}
    for v in views:
        fns[v]()
    return 0


if __name__ == "__main__":
    sys.exit(main())
