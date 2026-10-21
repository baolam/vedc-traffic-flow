"""Sinh texture cho cảnh Blender bằng PIL (chạy bằng Python hệ thống, không phải Python của Blender).

  decal_sa_ban.png   mặt in decal tấm A0 (4 px/mm): đường, vỉa hè, vạch, nhãn J1/J2
  breadboard.png     mặt trên breadboard 830 lỗ (8 px/mm)
  dashboard.png      màn hình laptop: bảng giám sát MINH HỌA (số xe lấy từ kịch bản trong bo_tri.py)
"""
from __future__ import annotations

import random
import sys
from pathlib import Path

from PIL import Image, ImageDraw, ImageFilter, ImageFont

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import bo_tri_a0 as L  # noqa: E402

OUT = HERE / "textures"
FONT = "/System/Library/Fonts/Supplemental/Arial.ttf"
FONT_B = "/System/Library/Fonts/Supplemental/Arial Bold.ttf"

GRASS = (128, 165, 104)
SIDEWALK = (214, 210, 200)
ASPHALT = (62, 64, 68)
PAINT = (240, 240, 236)
FRAME = (70, 72, 76)


def font(size: int, bold: bool = False) -> ImageFont.FreeTypeFont:
    return ImageFont.truetype(FONT_B if bold else FONT, size)


def decal(scale: float = 4.0) -> Image.Image:
    W, H = int(L.BOARD_W * scale), int(L.BOARD_H * scale)
    im = Image.new("RGB", (W, H), GRASS)
    d = ImageDraw.Draw(im)

    def P(x: float, y: float) -> tuple[float, float]:
        return (x + L.BOARD_W / 2) * scale, (L.BOARD_H / 2 - y) * scale

    def rect(x0, y0, x1, y1, fill):
        (a, b), (c, e) = P(min(x0, x1), max(y0, y1)), P(max(x0, x1), min(y0, y1))
        d.rectangle([a, b, c, e], fill=fill)

    # cỏ có hạt nhẹ
    rnd = random.Random(7)
    for _ in range(W * H // 60):
        x, y = rnd.randrange(W), rnd.randrange(H)
        k = rnd.randint(-14, 14)
        d.point((x, y), fill=(GRASS[0] + k, GRASS[1] + k, GRASS[2] + k // 2))
    im = im.filter(ImageFilter.GaussianBlur(0.6))
    d = ImageDraw.Draw(im)

    hw, hh = L.BOARD_W / 2, L.BOARD_H / 2
    r, s = L.ROAD_W / 2, L.SIDEWALK_W
    # vỉa hè rồi mặt đường
    rect(-hw, -r - s, hw, r + s, SIDEWALK)
    for jx, _ in L.JUNCTIONS.values():
        rect(jx - r - s, -hh, jx + r + s, hh, SIDEWALK)
    rect(-hw, -r, hw, r, ASPHALT)
    for jx, _ in L.JUNCTIONS.values():
        rect(jx - r, -hh, jx + r, hh, ASPHALT)

    # hạt nhựa đường
    rnd = random.Random(11)
    px = im.load()
    for _ in range(W * H // 25):
        x, y = rnd.randrange(W), rnd.randrange(H)
        c = px[x, y]
        if c == ASPHALT:
            k = rnd.randint(-9, 9)
            px[x, y] = (c[0] + k, c[1] + k, c[2] + k)

    cw, sg = L.CROSSWALK_D, L.STOP_GAP
    jxs = [j[0] for j in L.JUNCTIONS.values()]

    def in_junction_zone(x: float, y: float) -> bool:
        return any(abs(x - jx) < r + cw + 4 and abs(y) < r + cw + 4 for jx in jxs)

    # vạch tim đường nét đứt
    dash, gap, lw = 30.0, 20.0, 3.0
    x = -hw + 10
    while x < hw - 10:
        if not in_junction_zone(x, 0) and not in_junction_zone(x + dash, 0):
            rect(x, -lw / 2, x + dash, lw / 2, PAINT)
        x += dash + gap
    for jx in jxs:
        y = -hh + 10
        while y < hh - 10:
            if not in_junction_zone(jx, y) and not in_junction_zone(jx, y + dash):
                rect(jx - lw / 2, y, jx + lw / 2, y + dash, PAINT)
            y += dash + gap

    # vạch qua đường (zebra) và vạch dừng
    sw = 7.0
    for jx in jxs:
        for side in (-1, 1):
            # nhánh Đông/Tây: sọc chạy dọc theo x
            x0 = jx + side * r
            x1 = jx + side * (r + cw)
            yy = -r + 4
            while yy + sw <= r - 2:
                rect(x0, yy, x1, yy + sw, PAINT)
                yy += 2 * sw
            # nhánh Bắc/Nam
            y0 = side * r
            y1 = side * (r + cw)
            xx = jx - r + 4
            while xx + sw <= jx + r - 2:
                rect(xx, y0, xx + sw, y1, PAINT)
                xx += 2 * sw
        sd = L.stop_dist()
        t = 4.0
        rect(jx - r, sd - t / 2, jx, sd + t / 2, PAINT)          # N
        rect(jx, -sd - t / 2, jx + r, -sd + t / 2, PAINT)        # S
        rect(jx + sd - t / 2, 0, jx + sd + t / 2, r, PAINT)      # E
        rect(jx - sd - t / 2, -r, jx - sd + t / 2, 0, PAINT)     # W

    # nhãn nút trên bãi cỏ, ở góc phía Bắc không có trụ giao thông
    for name, (jx, jy) in L.JUNCTIONS.items():
        cx, cy = jx - L.POLE_CORNER[name][0] * (r + s + 52), jy + r + s + 40
        a, b = P(cx - 32, cy + 20)
        c, e = P(cx + 32, cy - 20)
        d.rounded_rectangle([a, b, c, e], radius=8 * scale, fill=(250, 250, 248), outline=(40, 40, 40),
                            width=int(1.2 * scale))
        f = font(int(26 * scale), True)
        tx, ty = P(cx, cy)
        d.text((tx, ty), name, font=f, fill=(30, 30, 30), anchor="mm")

    # chữ nhỏ góc trước-trái
    tx, ty = P(-hw + 14, -hh + 16)
    d.text((tx, ty), "EdgeFlow AI · VEDC 2026 · đội 31µF", font=font(int(10 * scale), True),
           fill=(245, 245, 240), anchor="ls")

    # viền tấm
    d.rectangle([0, 0, W - 1, H - 1], outline=FRAME, width=int(3 * scale))
    return im


def breadboard(scale: float = 8.0) -> Image.Image:
    Wmm, Hmm = 165.1, 54.6
    W, H = int(Wmm * scale), int(Hmm * scale)
    im = Image.new("RGB", (W, H), (246, 246, 242))
    d = ImageDraw.Draw(im)
    pitch = 2.54
    hole = 1.0

    def hole_at(xmm: float, ymm: float):
        x, y = xmm * scale, ymm * scale
        h = hole * scale / 2
        d.rectangle([x - h, y - h, x + h, y + h], fill=(70, 70, 70))

    x0 = (Wmm - 62 * pitch) / 2
    # vùng chính: 2 khối 5 hàng, khe giữa
    for i in range(63):
        for row in range(5):
            hole_at(x0 + i * pitch, 13.0 + row * pitch)
            hole_at(x0 + i * pitch, 31.0 + row * pitch)
    d.rectangle([0, 26.3 * scale, W, 28.3 * scale], fill=(225, 225, 220))
    # ray nguồn
    for base, color_top in ((2.6, True), (47.0, False)):
        for k in range(50):
            xg = x0 + 2 * pitch + k * pitch + (k // 5) * pitch * 0.2
            if xg > Wmm - 4:
                break
            hole_at(xg, base)
            hole_at(xg, base + pitch)
        red_y = base - 1.5 if color_top else base + pitch + 1.5
        blue_y = base + pitch + 1.5 if color_top else base - 1.5
        d.line([(4 * scale, red_y * scale), (W - 4 * scale, red_y * scale)], fill=(205, 40, 40),
               width=int(0.5 * scale))
        d.line([(4 * scale, blue_y * scale), (W - 4 * scale, blue_y * scale)], fill=(40, 80, 200),
               width=int(0.5 * scale))
    return im


def dashboard() -> Image.Image:
    W, H = 1600, 1000
    bg, panel, text, muted = (13, 19, 33), (22, 31, 50), (230, 236, 245), (140, 152, 172)
    green, red, amber, blue = (46, 204, 113), (231, 76, 60), (241, 196, 15), (66, 153, 225)
    im = Image.new("RGB", (W, H), bg)
    d = ImageDraw.Draw(im)
    d.rectangle([0, 0, W, 80], fill=(17, 26, 44))
    d.text((32, 40), "EdgeFlow AI", font=font(34, True), fill=text, anchor="lm")
    d.text((262, 42), "Bảng giám sát hành lang J1 – J2", font=font(26), fill=muted, anchor="lm")
    d.rounded_rectangle([1250, 22, 1568, 58], radius=18, fill=(40, 52, 76))
    d.text((1409, 40), "MINH HỌA · RENDER 3D", font=font(18, True), fill=amber, anchor="mm")

    # bản đồ hành lang
    d.rounded_rectangle([32, 108, 900, 960], radius=18, fill=panel)
    d.text((60, 140), "Mạng lưới (đồ thị có hướng)", font=font(24, True), fill=text, anchor="lm")
    cy = 540
    nodes = {"J1": 270, "J2": 660}
    d.line([(90, cy), (850, cy)], fill=(70, 84, 110), width=26)
    for jx in nodes.values():
        d.line([(jx, 220), (jx, 880)], fill=(70, 84, 110), width=26)
    d.line([(300, cy - 28), (630, cy - 28)], fill=red, width=10)       # đoạn nối có hàng đợi dài
    d.polygon([(630, cy - 40), (654, cy - 28), (630, cy - 16)], fill=red)
    for name, jx in nodes.items():
        d.ellipse([jx - 46, cy - 46, jx + 46, cy + 46], fill=(30, 41, 64), outline=text, width=4)
        d.text((jx, cy), name, font=font(30, True), fill=text, anchor="mm")
        g = L.PHASE_GREEN[name]
        d.text((jx, cy + 92), f"Pha xanh: {'Bắc–Nam' if g == 'NS' else 'Đông–Tây'}", font=font(22),
               fill=green, anchor="mm")
    d.text((465, cy - 70), "hàng đợi hạ lưu", font=font(20), fill=red, anchor="mm")

    # biểu đồ hàng đợi
    d.rounded_rectangle([930, 108, 1568, 700], radius=18, fill=panel)
    d.text((958, 140), "Hàng đợi theo hướng (xe)", font=font(24, True), fill=text, anchor="lm")
    counts: dict[str, int] = {}
    for node, appr, dist in L.CARS:
        if dist >= 0:
            counts[f"{node}_{appr}"] = counts.get(f"{node}_{appr}", 0) + 1
    keys = [f"{n}_{a}" for n in ("J1", "J2") for a in ("N", "S", "E", "W")]
    bx, by, bw = 980, 640, 58
    for i, k in enumerate(keys):
        v = counts.get(k, 0)
        x = bx + i * 72
        hpx = v * 100
        node, appr = k.split("_")
        col = green if L.light_state(node, appr) == "G" else red
        d.rectangle([x, by - hpx, x + bw, by], fill=col)
        d.text((x + bw / 2, by - hpx - 18), str(v), font=font(20, True), fill=text, anchor="mm")
        d.text((x + bw / 2, by + 22), k.replace("_", "·"), font=font(16), fill=muted, anchor="mm")

    # trạng thái thiết bị
    d.rounded_rectangle([930, 730, 1568, 960], radius=18, fill=panel)
    d.text((958, 765), "Thiết bị", font=font(24, True), fill=text, anchor="lm")
    rows = [("ESP32 J1", "HEALTHY"), ("ESP32 J2", "HEALTHY"), ("Vision (Pi 5)", "ONLINE")]
    for i, (n, st) in enumerate(rows):
        y = 815 + i * 48
        d.ellipse([960, y - 9, 978, y + 9], fill=green)
        d.text((995, y), n, font=font(22), fill=text, anchor="lm")
        d.text((1540, y), st, font=font(20, True), fill=green, anchor="rm")
    return im


def main() -> int:
    OUT.mkdir(exist_ok=True)
    decal().save(OUT / "decal_sa_ban.png", optimize=True)
    breadboard().save(OUT / "breadboard.png")
    dashboard().save(OUT / "dashboard.png")
    print("textures ->", OUT)
    return 0


if __name__ == "__main__":
    sys.exit(main())
