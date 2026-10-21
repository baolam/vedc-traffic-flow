"""Ký hiệu điện, dây và khung tên dùng chung cho các trang bản vẽ mạch (Phụ lục A).

Dây là đường tự do, không gắn vào ký hiệu: kéo ký hiệu trong draw.io thì phải kéo dây theo.
Vị trí chân của stencil draw.io đo bằng render thử ngày 11/10/2026 (bảng TY bên dưới).
"""
from __future__ import annotations

import re
from pathlib import Path
from xml.sax.saxutils import quoteattr

from drawio_lib import FONT, Page, style

E = "mxgraph.electrical."
DAY = "#333333"
MO = "#A0A0A0"            # chân không dùng
NGUON = "#C05621"         # +5V
CAP = "#6B46C1"           # cáp W1 lên trụ
TIN_HIEU = {"R": "#D32F2F", "Y": "#C98A00", "G": "#2E7D32"}
LED_FILL = {"R": "#EF5350", "Y": "#FFC107", "G": "#66BB6A"}

# Tỉ lệ chiều cao (tính từ mép trên khung) của đường nối chân trong stencil draw.io.
TY = {"giua": 0.5, "led": 0.6, "nut_nhan": 1.0}

FIRMWARE = (Path(__file__).resolve().parents[2]
            / "vedc-traffic-flow" / "src" / "hardware" / "firmware" / "esp32_signal_controller.ino")

# Bảng chân dùng để vẽ. Phải khớp các hằng PIN_* trong firmware (kiem_chan).
CHAN = {"NS_RED": 23, "NS_YELLOW": 22, "NS_GREEN": 21,
        "EW_RED": 19, "EW_YELLOW": 18, "EW_GREEN": 5,
        "STATUS_LED": 2, "SAFE_STOP": 4}

# NodeMCU-32S (Ai-Thinker), nhìn từ mặt linh kiện, anten ở trên. Chân 1–19 ở hàng trái từ trên xuống;
# chân 38 → 20 ở hàng phải từ trên xuống (theo trang linh kiện LCSC/Flux "NodeMCU-32S").
NODEMCU_TRAI = ["3V3", "EN", "SVP", "SVN", "IO34", "IO35", "IO32", "IO33", "IO25", "IO26", "IO27",
                "IO14", "IO12", "GND", "IO13", "SD2", "SD3", "CMD", "5V"]
NODEMCU_PHAI = ["GND", "IO23", "IO22", "TX", "RX", "IO21", "GND", "IO19", "IO18", "IO5", "IO17",
                "IO16", "IO4", "IO0", "IO2", "IO15", "SD1", "SD0", "CLK"]


def doc_chan_firmware(path: Path = FIRMWARE) -> dict[str, int]:
    text = path.read_text(encoding="utf-8")
    return {m[1]: int(m[2]) for m in re.finditer(r"const\s+int\s+PIN_(\w+)\s*=\s*(\d+)\s*;", text)}


def kiem_chan(chan: dict[str, int], fw: dict[str, int]) -> list[str]:
    """Trả về danh sách chỗ lệch giữa hình vẽ và firmware (rỗng = khớp)."""
    loi = []
    for ten, so in chan.items():
        if ten not in fw:
            loi.append(f"firmware không có PIN_{ten}")
        elif fw[ten] != so:
            loi.append(f"PIN_{ten}: hình vẽ GPIO {so}, firmware GPIO {fw[ten]}")
    loi += [f"firmware có PIN_{ten} mà hình chưa vẽ" for ten in sorted(fw.keys() - chan.keys())]
    return loi


def wire(p: Page, cid: str, pts: list[tuple[float, float]], color: str = DAY, *, width: float = 1.6,
         dashed: bool = False, jump: bool = False, end: str = "none") -> str:
    """Dây gấp khúc qua các điểm pts (không gắn ký hiệu)."""
    kw = dict(endArrow=end, endFill=1, endSize=7, html=1, rounded=0, strokeColor=color, strokeWidth=width)
    if jump:
        kw.update(jumpStyle="arc", jumpSize=9)
    if dashed:
        kw.update(dashed=1, dashPattern="6 4")
    (x1, y1), (x2, y2) = pts[0], pts[-1]
    mids = "".join(f'<mxPoint x="{x}" y="{y}"/>' for x, y in pts[1:-1])
    arr = f'<Array as="points">{mids}</Array>' if mids else ""
    cid = p._new_id(cid)
    p.cells.append(
        f'<mxCell id={quoteattr(cid)} value="" style={quoteattr(style(**kw))} edge="1" parent="1">'
        f'<mxGeometry relative="1" as="geometry"><mxPoint x="{x1}" y="{y1}" as="sourcePoint"/>'
        f'<mxPoint x="{x2}" y="{y2}" as="targetPoint"/>{arr}</mxGeometry></mxCell>')
    return cid


def dot(p: Page, cid: str, x: float, y: float, color: str = DAY, r: float = 3.5) -> str:
    return p.vertex(cid, x - r, y - r, 2 * r, 2 * r, "",
                    style(shape="ellipse", perimeter="ellipsePerimeter", aspect="fixed", fillColor=color,
                          strokeColor=color))


def sym(p: Page, cid: str, shape: str, x: float, y: float, w: float, h: float, *,
        fill: str = "#FFFFFF", stroke: str = DAY, rot: int = 0) -> str:
    kw = dict(shape=E + shape, html=1, pointerEvents=1, strokeColor=stroke, strokeWidth=1.6, fillColor=fill)
    if rot:
        kw["rotation"] = rot
    return p.vertex(cid, x, y, w, h, "", style(**kw))


def sym_ngang(p: Page, cid: str, shape: str, x: float, y_day: float, w: float, h: float, *,
              ty: float = TY["giua"], fill: str = "#FFFFFF") -> str:
    """Ký hiệu 2 chân nằm ngang, đặt sao cho đường nối chân trùng dây ở cao độ y_day."""
    return sym(p, cid, shape, x, y_day - ty * h, w, h, fill=fill)


def gnd(p: Page, cid: str, x: float, y: float, *, chan: float = 12) -> None:
    """Ký hiệu GND: dây từ (x, y) đi xuống một đoạn rồi tới tam giác GND."""
    wire(p, f"{cid}_w", [(x, y), (x, y + chan)])
    sym(p, f"{cid}_s", "signal_sources.signal_ground", x - 10, y + chan, 20, 11)


def chu(p: Page, cid: str, x: float, y: float, w: float, h: float, value: str, *, size: float = 11,
        color: str = "#1F1F1F", align: str = "left", bold: bool = False, mono: bool = False) -> str:
    sty = style(text=1, html=1, whiteSpace="wrap", fontFamily="Menlo" if mono else FONT, fontSize=size,
                fontColor=color, align=align, verticalAlign="middle", fontStyle=1 if bold else 0,
                strokeColor="none", fillColor="none", spacing=0)
    return p.vertex(cid, x, y, w, h, value, sty)


def khung(p: Page, cid: str, x: float, y: float, w: float, h: float, *, stroke: str = "#8A8A8A",
          fill: str = "none", dashed: bool = True, value: str = "", size: int = 12) -> str:
    """Khung chữ nhật (nhóm, vùng lắp đặt). Chữ nằm góc trên trái."""
    kw = dict(rounded=1, arcSize=4, html=1, whiteSpace="wrap", fillColor=fill, strokeColor=stroke,
              strokeWidth=1.3, fontFamily=FONT, fontSize=size, fontStyle=1, fontColor=stroke,
              align="left", verticalAlign="top", spacingLeft=10, spacingTop=4)
    if dashed:
        kw.update(dashed=1, dashPattern="7 5")
    return p.vertex(cid, x, y, w, h, value, style(**kw))


def khung_ten(p: Page, cid: str, x: float, y: float, so_to: str, ten: str, nguon: str) -> None:
    """Khung tên kiểu bản vẽ kỹ thuật ở góc dưới phải."""
    p.table(cid, x, y, [410, 150], [
        ["EdgeFlow AI · Đội 31µF · VEDC 2026", f"Tờ {so_to} / A.3"],
        [ten, "11/10/2026"],
        [nguon, "Bản vẽ thể hiện"],
    ], row_h=26, size=11)


def chu_giai(p: Page, cid: str, x: float, y: float, items: list[tuple[str, str, bool]], *,
             step: float = 250) -> None:
    """Chú giải màu dây: (màu, chữ, nét đứt)."""
    cx = x
    for i, (color, text, dashed) in enumerate(items):
        wire(p, f"{cid}_{i}_w", [(cx, y), (cx + 34, y)], color, width=2.4 if color == CAP else 1.8,
             dashed=dashed)
        chu(p, f"{cid}_{i}_t", cx + 42, y - 10, 210, 20, text, size=11)
        cx += step
