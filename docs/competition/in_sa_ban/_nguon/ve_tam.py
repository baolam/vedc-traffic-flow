"""Vẽ mặt in của tấm bạt 1200 × 600 (SVG, đơn vị mm, tỉ lệ 1:1, có tràn lề).

Màu giữ như decal của cảnh Blender (tao_texture.py) để sa bàn thật khớp ảnh trong báo cáo.
Dấu đặt đế trụ nằm dưới đế và trụ nên sau khi lắp không còn thấy.
"""
from __future__ import annotations

from html import escape

import hinh_hoc as G

GRASS = "#80A568"
SIDEWALK = "#D6D2C8"
ASPHALT = "#3E4044"
PAINT = "#F0F0EC"
PAD = "#C9C5BC"
PAD_EDGE = "#8F8B83"
MARK = "#1E2329"
FONT = "'Avenir Next Condensed', 'Avenir Next', Arial, sans-serif"


def _r(x0: float, y0: float, x1: float, y1: float, fill: str, extra: str = "") -> str:
    """Hình chữ nhật theo tọa độ y hướng Bắc."""
    return (f'<rect x="{min(x0, x1):.2f}" y="{-max(y0, y1):.2f}" width="{abs(x1 - x0):.2f}" '
            f'height="{abs(y1 - y0):.2f}" fill="{fill}" {extra}/>')


def _t(x: float, y: float, s: str, size: float, fill: str, weight: int = 600, anchor: str = "middle",
       extra: str = "") -> str:
    return (f'<text x="{x:.2f}" y="{-y:.2f}" font-family="{FONT}" font-size="{size}" font-weight="{weight}" '
            f'fill="{fill}" text-anchor="{anchor}" dominant-baseline="central" {extra}>{escape(s)}</text>')


def _road(lim: float) -> list[str]:
    e, r = G.EDGE, G.ROAD_HALF
    return [_r(-lim, -e, lim, e, SIDEWALK), _r(-e, -lim, e, lim, SIDEWALK),
            _r(-lim, -r, lim, r, ASPHALT), _r(-r, -lim, r, lim, ASPHALT)]


def _markings(node: str, lim: float) -> list[str]:
    r, cw, lw = G.ROAD_HALF, G.CROSSWALK_D, G.CENTER_LINE_W
    out = []
    off = G.WORLD_X[node]
    for a, b in G.ew_dashes_world():
        a, b = max(a - off, -lim), min(b - off, lim)
        if b > a:
            out.append(_r(a, -lw / 2, b, lw / 2, PAINT))
    for a, b in G.ns_dashes():
        out.append(_r(-lw / 2, a, lw / 2, b, PAINT))
    sw = G.ZEBRA_W
    for side in (-1, 1):
        yy = -r + 4
        while yy + sw <= r - 2:                           # nhánh Đông/Tây
            out.append(_r(side * r, yy, side * (r + cw), yy + sw, PAINT))
            yy += 2 * sw
        xx = -r + 4
        while xx + sw <= r - 2:                           # nhánh Bắc/Nam
            out.append(_r(xx, side * r, xx + sw, side * (r + cw), PAINT))
            xx += 2 * sw
    sd, t = G.STOP_DIST, G.STOP_LINE_W
    out += [_r(-r, sd - t / 2, 0, sd + t / 2, PAINT), _r(0, -sd - t / 2, r, -sd + t / 2, PAINT),
            _r(sd - t / 2, 0, sd + t / 2, r, PAINT), _r(-sd - t / 2, -r, -sd + t / 2, 0, PAINT)]
    return out


def _pads(node: str) -> list[str]:
    out = []
    for name, rect in G.pads(node):
        x0, y0, x1, y1 = G.rect_x(node, rect)
        out.append(_r(x0, y0, x1, y1, PAD, f'rx="4" stroke="{PAD_EDGE}" stroke-width="0.6"'))
        # chữ nằm trong dải lề phía Bắc của ô, thiết bị không che
        out.append(_t((x0 + x1) / 2, y1 - G.PAD_MARGIN / 2, name, 4.2, "#4A4741", 600,
                      extra='letter-spacing="0.4"'))
    return out


def _cross(x: float, y: float, d: float, label: str, dashed: bool = False) -> list[str]:
    dash = ' stroke-dasharray="1.2 0.8"' if dashed else ""
    k = d / 2 + 3
    return [f'<circle cx="{x:.2f}" cy="{-y:.2f}" r="{d / 2:.2f}" fill="none" stroke="{MARK}" '
            f'stroke-width="0.4"{dash}/>',
            f'<path d="M{x - k:.2f} {-y:.2f}H{x + k:.2f}M{x:.2f} {-y - k:.2f}V{-y + k:.2f}" '
            f'stroke="{MARK}" stroke-width="0.3"/>',
            _t(x, y - d / 2 - 3.4, label, 3.2, MARK, 500)]


def _pole_marks(node: str) -> list[str]:
    """Dấu đặt đế trụ: viền đế MDF và chân trụ (đế và trụ che hết khi lắp, chỉ để đội đặt cho đúng chỗ)."""
    out = []
    x0, y0, x1, y1 = G.rect_x(node, G.plate_rect())
    out.append(_r(x0, y0, x1, y1, "none", f'stroke="{MARK}" stroke-width="0.6" stroke-dasharray="3 2"'))
    out.append(_t((x0 + x1) / 2, y1 - 8, f"ĐẾ TRỤ MDF {G.PLATE:.0f} × {G.PLATE:.0f}", 4.4, MARK, 600,
                  extra='letter-spacing="0.4"'))
    px0, py0, px1, py1 = G.rect_x(node, G.pole_rect())
    out.append(_r(px0, py0, px1, py1, "none", f'stroke="{MARK}" stroke-width="0.5"'))
    out.append(_t((px0 + px1) / 2, (py0 + py1) / 2, "TRỤ", 3.4, MARK, 600))
    return out


def _label(node: str) -> list[str]:
    cx, cy = G.to_x(node, G.LABEL_U), G.LABEL_Y
    out = [_r(cx - 32, cy - 20, cx + 32, cy + 20, "#FAFAF8", 'rx="8" stroke="#282828" stroke-width="1.2"'),
           _t(cx, cy - 0.5, node, 27, "#1E1E1E", 700)]
    # mũi tên Bắc nhỏ cạnh nhãn, phía xa đường
    ax = cx + G.INWARD[node] * -48
    out.append(f'<path d="M{ax:.2f} {-(cy + 13):.2f}l5 11h-10z" fill="#F7F7F2"/>')
    out.append(_t(ax, cy - 6, "B", 8, "#F7F7F2", 700))
    return out


def _team(node: str) -> list[str]:
    if node != "J1":
        return []
    x, y = -G.HALF + 14, -G.HALF + 30
    out = [_t(x, y, "EdgeFlow AI · VEDC 2026 · đội 31µF", 9, "#F7F7F2", 700, "start")]
    # thước 100 mm để kiểm tỉ lệ in khi nhận hàng
    y0 = -G.HALF + 14
    out.append(_r(x, y0 - 1, x + 100, y0 + 1, "#F7F7F2"))
    for k in range(0, 101, 10):
        h = 3.5 if k in (0, 50, 100) else 2
        out.append(_r(x + k - 0.25, y0, x + k + 0.25, y0 + h, "#F7F7F2"))
    out.append(_t(x + 104, y0 + 0.5, "100 mm", 5.5, "#F7F7F2", 600, "start"))
    return out


def body(node: str, bleed: bool = True, marks: bool = True) -> str:
    """Các phần tử SVG của nửa bạt `node`, gốc ở tâm ngã tư, để nhúng vào hình khác."""
    lim = G.HALF + (G.BLEED if bleed else 0.0)
    parts = [_r(-lim, -lim, lim, lim, GRASS), *_road(lim), *_markings(node, lim), *_pads(node)]
    if marks:
        parts += _pole_marks(node)
    parts += _label(node) + _team(node)
    return "\n".join(parts)


def _bleed_strips(b: float) -> list[str]:
    """Phần tràn lề: đường và vỉa hè nối dài ra ngoài mép bạt ở 6 chỗ đường thoát ra."""
    e, r, h = G.EDGE, G.ROAD_HALF, G.HALF
    out = []
    for side in (-1, 1):                                  # đầu trái và phải của đường Đông-Tây
        edge = side * 2 * h
        out.append(_r(edge, -e, edge + side * b, e, SIDEWALK))
        out.append(_r(edge, -r, edge + side * b, r, ASPHALT))
    for n in G.NODES:                                     # đầu trên và dưới của 2 đường Bắc-Nam
        jx = G.WORLD_X[n]
        for side in (-1, 1):
            out.append(_r(jx - e, side * h, jx + e, side * (h + b), SIDEWALK))
            out.append(_r(jx - r, side * h, jx + r, side * (h + b), ASPHALT))
    return out


def sheet_svg(bleed: bool = True, marks: bool = True, extra: str = "", css_width: str | None = None) -> str:
    """Cả tấm bạt (hai ngã tư), gốc ở giữa bạt. bleed=True: file in 1240 × 640 mm; False: hình 1200 × 600 mm."""
    b = G.BLEED if bleed else 0.0
    w, h = G.SHEET_W + 2 * b, G.SHEET_H + 2 * b
    tiles = "".join(f'<g transform="translate({G.WORLD_X[n]},0)">{body(n, False, marks)}</g>' for n in G.NODES)
    ground = _r(-w / 2, -h / 2, w / 2, h / 2, GRASS)
    size = (f'style="width:{css_width};height:auto;display:block"' if css_width
            else f'width="{w:.0f}mm" height="{h:.0f}mm"')
    return (f'<svg xmlns="http://www.w3.org/2000/svg" {size} viewBox="{-w / 2} {-h / 2} {w} {h}">'
            f'{ground}{"".join(_bleed_strips(b)) if bleed else ""}{tiles}{extra}</svg>')


def pair_svg(marks: bool, extra: str = "", css_width: str = "100%") -> str:
    """Cả tấm bạt không tràn lề, dùng cho hình xem trước; `extra` vẽ đè theo tọa độ bạt (gốc ở giữa bạt)."""
    return sheet_svg(bleed=False, marks=marks, extra=extra, css_width=css_width)
