"""Sinh texture cho cảnh Blender bằng PIL (chạy bằng Python hệ thống, không phải Python của Blender).

  decal_bat.png      mặt in tấm bạt 1200 × 600 (4 px/mm), lấy từ cùng SVG với file in; cần rsvg-convert
  breadboard.png     mặt trên breadboard 830 lỗ (8 px/mm)
  dashboard.png      màn hình laptop: bảng giám sát MINH HỌA (số xe lấy từ kịch bản trong bo_tri.py)
"""
from __future__ import annotations

import sys
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
sys.path.insert(0, str(HERE.parents[2] / "in_sa_ban" / "_nguon"))
import bo_tri as L  # noqa: E402

OUT = HERE / "textures"
FONT = "/System/Library/Fonts/Supplemental/Arial.ttf"
FONT_B = "/System/Library/Fonts/Supplemental/Arial Bold.ttf"


def font(size: int, bold: bool = False) -> ImageFont.FreeTypeFont:
    return ImageFont.truetype(FONT_B if bold else FONT, size)


def decal_bat(px_per_mm: float = 4.0) -> None:
    """Decal tấm bạt 1200 × 600: rasterize đúng SVG của file in (in_sa_ban/_nguon/ve_tam.py), bỏ phần tràn lề và
    dấu đặt đế trụ (nằm dưới đế). Nhờ vậy ảnh render khớp bản in từng nét."""
    import subprocess
    import ve_tam

    svg = OUT / "_decal_bat.svg"
    svg.write_text(ve_tam.sheet_svg(bleed=False, marks=False), encoding="utf-8")
    subprocess.run(["rsvg-convert", "-w", str(int(round(L.BOARD_W * px_per_mm))),
                    "-h", str(int(round(L.BOARD_H * px_per_mm))), "-o", str(OUT / "decal_bat.png"), str(svg)],
                   check=True)
    svg.unlink()


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
    decal_bat()
    breadboard().save(OUT / "breadboard.png")
    dashboard().save(OUT / "dashboard.png")
    print("textures ->", OUT)
    return 0


if __name__ == "__main__":
    sys.exit(main())
