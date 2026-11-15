"""Thành phần dùng chung cho các tờ bản vẽ mạch (Phụ lục A).

Gồm bảng màu, khung tờ có ô lưới tham chiếu, khung tên, nhãn hình, ghi chú, chú giải, bảng, thẻ tên cáp,
đường kích thước, ký hiệu điện và dây.

Dây là đường tự do, không gắn vào ký hiệu: kéo ký hiệu trong draw.io thì phải kéo dây theo.
Vị trí chân của stencil draw.io đo bằng render thử ngày 11/10/2026 (bảng TY bên dưới).
"""
from __future__ import annotations

import math
import re
from pathlib import Path
from xml.sax.saxutils import quoteattr

from drawio_lib import FONT, Page, style

# ---------------------------------------------------------------- khổ tờ
W, H = 1600, 1131           # mọi tờ cùng khổ, tỉ lệ A3 ngang
LE = 30                     # mép khung trong
TONG_SO_TO = 4
NGAY = "11/10/2026"
TB_W, TB_H = 640, 108       # khung tên ở góc dưới phải
TB_X, TB_Y = W - LE - TB_W, H - LE - TB_H

# ---------------------------------------------------------------- bảng màu
INK = "#1E2329"             # nét chính, chữ
INK2 = "#5B6470"            # chữ phụ
INK3 = "#A3ABB5"            # nét phụ, đường dóng
RULE = "#D5DAE0"            # đường kẻ bảng, vạch chia
NEN = "#F5F6F8"             # nền vùng
DAY = INK
MO = "#B8BEC6"              # chân không dùng
NGUON, NGUON_NEN = "#D9480F", "#FFF4E6"
CAP, CAP_NEN = "#AE3EC9", "#F8F0FC"     # cáp CAT5e W1/W2 lên trụ
CSI, CSI_NEN = "#1C7ED6", "#E7F5FF"     # cáp FPC camera
NUT, NUT_NEN = "#2B8A3E", "#EBFBEE"     # nút chấp hành (ESP32, module đèn)
MANG, MANG_NEN = "#B7791F", "#FFF5E1"   # router, Wi-Fi
DIEU_PHOI, DIEU_PHOI_NEN = "#6B46C1", "#F2EEFA"
AN_TOAN = "#C92A2A"
TIN_HIEU = {"R": "#E03131", "Y": "#E09F00", "G": "#2F9E44"}
LED_FILL = {"R": "#FF6B6B", "Y": "#FCC419", "G": "#51CF66"}
E = "mxgraph.electrical."

# Tỉ lệ chiều cao (tính từ mép trên khung) của đường nối chân trong stencil draw.io.
TY = {"giua": 0.5, "led": 0.6}

# ---------------------------------------------------------------- firmware
FIRMWARE = (Path(__file__).resolve().parents[2]
            / "vedc-traffic-flow" / "src" / "hardware" / "firmware" / "esp32_signal_controller.ino")

# Bảng chân dùng để vẽ. Phải khớp các hằng PIN_* trong firmware (kiem_chan).
CHAN = {"NS_RED": 23, "NS_YELLOW": 22, "NS_GREEN": 21,
        "EW_RED": 19, "EW_YELLOW": 18, "EW_GREEN": 5,
        "STATUS_LED": 2, "SAFE_STOP": 4}
PHA = {"NS": ("NS_RED", "NS_YELLOW", "NS_GREEN"), "EW": ("EW_RED", "EW_YELLOW", "EW_GREEN")}
MAU = ("R", "Y", "G")

# NodeMCU-32S (Ai-Thinker), nhìn từ mặt linh kiện, anten ở trên. Chân 1–19 ở hàng trái từ trên xuống;
# chân 38 → 20 ở hàng phải từ trên xuống (theo trang linh kiện LCSC/Flux "NodeMCU-32S").
NODEMCU_TRAI = ["3V3", "EN", "SVP", "SVN", "IO34", "IO35", "IO32", "IO33", "IO25", "IO26", "IO27",
                "IO14", "IO12", "GND", "IO13", "SD2", "SD3", "CMD", "5V"]
NODEMCU_PHAI = ["GND", "IO23", "IO22", "TX", "RX", "IO21", "GND", "IO19", "IO18", "IO5", "IO17",
                "IO16", "IO4", "IO0", "IO2", "IO15", "SD1", "SD0", "CLK"]

# Lõi cáp W1/W2 (CAT5e, màu T568B, ĐỀ XUẤT): (lõi, tên màu, (màu chính, có sọc trắng), net, khóa CHAN, module)
LOI = [
    (1, "cam-trắng", ("#F76707", True), "NS_R", "NS_RED", "H1 Bắc + H2 Nam · R"),
    (2, "cam", ("#F76707", False), "NS_Y", "NS_YELLOW", "H1 Bắc + H2 Nam · Y"),
    (3, "xanh lá-trắng", ("#2F9E44", True), "NS_G", "NS_GREEN", "H1 Bắc + H2 Nam · G"),
    (4, "xanh dương", ("#1971C2", False), "EW_R", "EW_RED", "H3 Đông + H4 Tây · R"),
    (5, "xanh dương-trắng", ("#1971C2", True), "EW_Y", "EW_YELLOW", "H3 Đông + H4 Tây · Y"),
    (6, "xanh lá", ("#2F9E44", False), "EW_G", "EW_GREEN", "H3 Đông + H4 Tây · G"),
    (7, "nâu-trắng", ("#8B5E3C", True), "GND", None, "GND của H1–H4"),
    (8, "nâu", ("#8B5E3C", False), "—", None, "dự phòng"),
]


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


def net_ngan(key: str) -> str:
    """NS_RED → NS_R."""
    return f"{key[:2]}_{key[3]}"


# ---------------------------------------------------------------- hình cơ bản
def duong(p: Page, cid: str, pts: list[tuple[float, float]], color: str = DAY, *, width: float = 1.6,
          dashed: bool = False, dash: str = "6 4", jump: bool = False, start: str = "none", end: str = "none",
          size: float = 7, value: str = "", font: float = 10, opacity: int | None = None,
          rounded: bool = False) -> str:
    """Đường gấp khúc qua các điểm pts (không gắn ký hiệu). value là chữ đặt giữa đường, nền trắng."""
    kw = dict(endArrow=end, endFill=1, endSize=size, startArrow=start, startFill=1, startSize=size, html=1,
              rounded=1 if rounded else 0, strokeColor=color, strokeWidth=width, fontFamily=FONT,
              fontSize=font, fontColor=color, labelBackgroundColor="#FFFFFF")
    if jump:
        kw.update(jumpStyle="arc", jumpSize=8)
    if dashed:
        kw.update(dashed=1, dashPattern=dash)
    if opacity is not None:
        kw["opacity"] = opacity
    (x1, y1), (x2, y2) = pts[0], pts[-1]
    mids = "".join(f'<mxPoint x="{x}" y="{y}"/>' for x, y in pts[1:-1])
    arr = f'<Array as="points">{mids}</Array>' if mids else ""
    cid = p._new_id(cid)
    p.cells.append(
        f'<mxCell id={quoteattr(cid)} value={quoteattr(value)} style={quoteattr(style(**kw))} edge="1" '
        f'parent="1"><mxGeometry relative="1" as="geometry"><mxPoint x="{x1}" y="{y1}" as="sourcePoint"/>'
        f'<mxPoint x="{x2}" y="{y2}" as="targetPoint"/>{arr}</mxGeometry></mxCell>')
    return cid


def wire(p: Page, cid: str, pts: list[tuple[float, float]], color: str = DAY, *, width: float = 1.6,
         dashed: bool = False, jump: bool = False, end: str = "none") -> str:
    """Dây điện gấp khúc (không gắn ký hiệu)."""
    return duong(p, cid, pts, color, width=width, dashed=dashed, jump=jump, end=end)


def dot(p: Page, cid: str, x: float, y: float, color: str = DAY, r: float = 3.6, *,
        fill: str | None = None, sw: float = 1.0) -> str:
    return p.vertex(cid, x - r, y - r, 2 * r, 2 * r, "",
                    style(shape="ellipse", perimeter="ellipsePerimeter", aspect="fixed",
                          fillColor=fill or color, strokeColor=color, strokeWidth=sw))


def hop(p: Page, cid: str, x: float, y: float, w: float, h: float, value: str = "", *,
        fill: str = "#FFFFFF", stroke: str = INK, sw: float = 1.4, r: float = 0, dashed: bool = False,
        size: float = 11, align: str = "center", valign: str = "middle", color: str = INK,
        bold: bool = False, opacity: int | None = None, pad: float = 6, extra: dict | None = None) -> str:
    """Hình chữ nhật đa dụng (r = bán kính bo góc tính bằng px, 0 = góc vuông)."""
    kw = dict(rounded=1 if r else 0, absoluteArcSize=1, arcSize=r * 2 or 1, whiteSpace="wrap", html=1, fillColor=fill,
              strokeColor=stroke, strokeWidth=sw, fontFamily=FONT, fontSize=size, fontColor=color,
              align=align, verticalAlign=valign, spacingLeft=pad, spacingRight=pad, spacingTop=2,
              spacingBottom=2, fontStyle=1 if bold else 0)
    if dashed:
        kw.update(dashed=1, dashPattern="6 4")
    if opacity is not None:
        kw.update(opacity=opacity)
    if extra:
        kw.update(extra)
    return p.vertex(cid, x, y, w, h, value, style(**kw))


def chu(p: Page, cid: str, x: float, y: float, w: float, h: float, value: str, *, size: float = 11,
        color: str = INK, align: str = "left", valign: str = "middle", bold: bool = False,
        mono: bool = False, rot: int = 0) -> str:
    kw = dict(text=1, html=1, whiteSpace="wrap", fontFamily="Menlo" if mono else FONT, fontSize=size,
              fontColor=color, align=align, verticalAlign=valign, fontStyle=1 if bold else 0,
              strokeColor="none", fillColor="none", spacing=0)
    if rot:
        kw["rotation"] = rot
    return p.vertex(cid, x, y, w, h, value, style(**kw))


def sym(p: Page, cid: str, shape: str, x: float, y: float, w: float, h: float, *,
        fill: str = "#FFFFFF", stroke: str = DAY, rot: int = 0, sw: float = 1.5) -> str:
    kw = dict(shape=E + shape, html=1, pointerEvents=1, strokeColor=stroke, strokeWidth=sw, fillColor=fill)
    if rot:
        kw["rotation"] = rot
    return p.vertex(cid, x, y, w, h, "", style(**kw))


def sym_ngang(p: Page, cid: str, shape: str, x: float, y_day: float, w: float, h: float, *,
              ty: float = TY["giua"], fill: str = "#FFFFFF") -> str:
    """Ký hiệu 2 chân nằm ngang, đặt sao cho đường nối chân trùng dây ở cao độ y_day."""
    return sym(p, cid, shape, x, y_day - ty * h, w, h, fill=fill)


def gnd(p: Page, cid: str, x: float, y: float, *, chan: float = 14) -> None:
    """Ký hiệu GND: dây từ (x, y) đi xuống một đoạn rồi tới 3 vạch ngang ngắn dần."""
    wire(p, f"{cid}_w", [(x, y), (x, y + chan)])
    for i, half in enumerate((9, 5.5, 2)):
        yy = y + chan + i * 3.6
        wire(p, f"{cid}_v{i}", [(x - half, yy), (x + half, yy)], width=1.6)


def nut_nhan_doc(p: Page, cid: str, x: float, y1: float, y2: float) -> None:
    """Nút nhấn thường mở, đặt dọc: hai cực tại (x, y1) và (x, y2), thanh tiếp điểm lệch sang phải."""
    for i, y in enumerate((y1, y2)):
        dot(p, f"{cid}_c{i}", x, y, DAY, r=3.2, fill="#FFFFFF", sw=1.4)
    xb = x + 12
    wire(p, f"{cid}_bar", [(xb, y1 - 4), (xb, y2 + 4)], width=2)
    ym = (y1 + y2) / 2
    wire(p, f"{cid}_can", [(xb, ym), (xb + 14, ym)], width=1.4, dashed=True)
    wire(p, f"{cid}_nap", [(xb + 14, ym - 8), (xb + 14, ym + 8)], width=2)


# ---------------------------------------------------------------- khung tờ, khung tên
def khung_to(p: Page) -> None:
    """Viền ngoài, viền trong và dải ô lưới tham chiếu 1–8 × A–F như bản vẽ kỹ thuật."""
    hop(p, "fr_ngoai", 10, 10, W - 20, H - 20, fill="none", stroke=INK3, sw=1)
    hop(p, "fr_trong", LE, LE, W - 2 * LE, H - 2 * LE, fill="none", stroke=INK, sw=2.2)
    cw, rh = (W - 2 * LE) / 8, (H - 2 * LE) / 6
    for i in range(8):
        x = LE + i * cw
        if i:
            wire(p, f"fr_ct{i}", [(x, 10), (x, LE)], INK3, width=1)
            wire(p, f"fr_cb{i}", [(x, H - LE), (x, H - 10)], INK3, width=1)
        for side, y in (("t", 11), ("b", H - LE + 1)):
            chu(p, f"fr_n{side}{i}", x, y, cw, LE - 12, str(i + 1), size=9, color=INK2, align="center")
    for j, letter in enumerate("ABCDEF"):
        y = LE + j * rh
        if j:
            wire(p, f"fr_rl{j}", [(10, y), (LE, y)], INK3, width=1)
            wire(p, f"fr_rr{j}", [(W - LE, y), (W - 10, y)], INK3, width=1)
        for side, x in (("l", 11), ("r", W - LE + 1)):
            chu(p, f"fr_l{side}{j}", x, y, LE - 12, rh, letter, size=9, color=INK2, align="center")


def _o(caption: str, value: str, *, vsize: float = 11.5, bold: bool = True) -> str:
    weight = "bold" if bold else "normal"
    return (f'<div style="font-size:8px;letter-spacing:0.08em;color:#868E96">{caption}</div>'
            f'<div style="font-size:{vsize}px;font-weight:{weight};color:{INK};margin-top:3px;'
            f'line-height:1.25">{value}</div>')


def khung_ten(p: Page, so_to: int, ten: str, nguon: str, ty_le: str = "không theo tỷ lệ") -> None:
    """Khung tên ở góc dưới phải, chạm viền trong."""
    x, y = TB_X, TB_Y
    o = dict(fill="#FFFFFF", stroke=INK, sw=1, align="left", valign="top", pad=8)
    hop(p, "tb_a", x, y, 180, 56,
        f'<div style="font-size:17px;font-weight:bold;letter-spacing:-0.01em">EdgeFlow AI</div>'
        f'<div style="font-size:10px;color:{INK2};margin-top:2px">Đội 31µF · VEDC 2026</div>',
        **{**o, "valign": "middle"})
    hop(p, "tb_b", x + 180, y, 320, 56, _o("TÊN BẢN VẼ", ten, vsize=12.5), **o)
    hop(p, "tb_c", x + 500, y, 140, 56,
        f'<div style="font-size:8px;letter-spacing:0.08em;color:#868E96">TỜ</div>'
        f'<div style="margin-top:1px"><span style="font-size:22px;font-weight:bold">A.{so_to}</span>'
        f'<span style="font-size:11px;color:#868E96">&nbsp;&nbsp;{so_to} / {TONG_SO_TO}</span></div>', **o)
    cx = x
    for i, (w, cap, val) in enumerate([(110, "NGÀY", NGAY), (130, "TỶ LỆ", ty_le), (260, "NGUỒN SỐ LIỆU", nguon),
                                        (140, "TRẠNG THÁI", "Bản vẽ thể hiện")]):
        hop(p, f"tb_r2_{i}", cx, y + 56, w, TB_H - 56, _o(cap, val, vsize=10, bold=False), **o)
        cx += w
    hop(p, "tb_vien", x, y, TB_W, TB_H, fill="none", stroke=INK, sw=2.2)


# ---------------------------------------------------------------- chữ có cấu trúc
def nhan(p: Page, cid: str, x: float, y: float, w: float, so: str, ten: str, phu: str = "") -> None:
    """Nhãn hình: ô số nền đậm + tiêu đề in hoa + chú thích nhạt + vạch kẻ dưới."""
    hop(p, f"{cid}_so", x, y, 24, 24, so, fill=INK, stroke=INK, sw=1, r=4, size=12.5, color="#FFFFFF",
        bold=True, pad=0)
    extra = f'&nbsp;&nbsp;<span style="font-weight:normal;color:{INK2};font-size:11px">{phu}</span>' if phu else ""
    chu(p, f"{cid}_t", x + 34, y, w - 34, 24,
        f'<span style="letter-spacing:0.03em">{ten}</span>{extra}', size=13.5, bold=True)
    wire(p, f"{cid}_vach", [(x, y + 33), (x + w, y + 33)], RULE, width=1)


def uoc_cao(text: str, w: float, size: float, line: float = 1.38) -> float:
    """Ước chiều cao khối chữ (Helvetica, chữ trung bình ~0,53 em), để xếp các khối không đè nhau."""
    dong = 0
    for doan in re.split(r"<br\s*/?>", text):
        plain = re.sub(r"<[^>]+>", "", doan).replace("&nbsp;", " ")
        dong += max(1, math.ceil(len(plain) * 0.5 * size / w))
    return dong * size * line + 2


def ghi_chu(p: Page, cid: str, x: float, y: float, w: float, items: list[str], *, tieu_de: str = "GHI CHÚ",
            size: float = 11, gap: float = 5) -> float:
    """Khối ghi chú đánh số, thụt đầu dòng treo. Trả về cao độ đáy."""
    chu(p, f"{cid}_td", x, y, w, 16, f'<span style="letter-spacing:0.08em">{tieu_de}</span>', size=10.5,
        bold=True, color=INK2)
    wire(p, f"{cid}_vach", [(x, y + 21), (x + w, y + 21)], RULE, width=1)
    cy = y + 30
    for i, text in enumerate(items, start=1):
        h = uoc_cao(text, w - 22, size)
        chu(p, f"{cid}_{i}_so", x, cy, 20, size * 1.4, f"{i}.", size=size, bold=True, color=INK2,
            valign="top")
        chu(p, f"{cid}_{i}", x + 22, cy, w - 22, h, text, size=size, valign="top")
        cy += h + gap
    return cy


def the(p: Page, cid: str, cx: float, cy: float, text: str, color: str, *, fill: str = "#FFFFFF",
        size: float = 10) -> str:
    """Thẻ tên (cáp, liên kết): viên thuốc viền màu, chữ đậm cùng màu, căn giữa tại (cx, cy)."""
    w = 14 + 0.62 * size * len(re.sub(r"<[^>]+>", "", text))
    return hop(p, cid, cx - w / 2, cy - 9, w, 18, text, fill=fill, stroke=color, sw=1.4, r=9, size=size,
               color=color, bold=True, pad=2)


def bang(p: Page, cid: str, x: float, y: float, cols: list[float], rows: list[list[str]], *,
         row_h: float = 24, head_h: float = 24, size: float = 10.5,
         mau: dict[tuple[int, int], str] | None = None, dam: set[tuple[int, int]] | None = None,
         le: dict[int, float] | None = None) -> float:
    """Bảng: hàng đầu chữ in nhỏ nền xám, các hàng dưới nền trắng xen kẽ xám rất nhạt. Trả về đáy."""
    mau, dam, le = mau or {}, dam or set(), le or {}
    cy = y
    for r, row in enumerate(rows):
        h = head_h if r == 0 else row_h
        cx = x
        for c, (txt, w) in enumerate(zip(row, cols)):
            if r == 0:
                val = f'<span style="letter-spacing:0.06em">{txt}</span>'
                hop(p, f"{cid}_r{r}c{c}", cx, cy, w, h, val, fill="#E9ECEF", stroke=RULE, sw=1, size=8.5,
                    align="left", color=INK2, bold=True)
            else:
                hop(p, f"{cid}_r{r}c{c}", cx, cy, w, h, txt, fill="#FFFFFF" if r % 2 else "#FAFBFC", stroke=RULE,
                    sw=1, size=size, align="left", color=mau.get((r, c), INK), bold=(r, c) in dam,
                    extra={"spacingLeft": le[c]} if c in le else None)
            cx += w
        cy += h
    hop(p, f"{cid}_vien", x, y, sum(cols), cy - y, fill="none", stroke=INK3, sw=1.2)
    return cy


def chu_giai(p: Page, cid: str, x: float, y: float, w: float, items: list[tuple[str, str, str]], *,
             cols: int = 2, row_h: float = 22) -> float:
    """Ô chú giải ký hiệu. items: (kiểu, màu, chữ); kiểu = line | dash | thick | band | dot | jump."""
    rows = math.ceil(len(items) / cols)
    h = 30 + rows * row_h + 6
    hop(p, f"{cid}_khung", x, y, w, h, fill="#FFFFFF", stroke=INK3, sw=1)
    chu(p, f"{cid}_td", x + 10, y + 6, w - 20, 16, '<span style="letter-spacing:0.08em">KÝ HIỆU</span>',
        size=10, bold=True, color=INK2)
    cw = (w - 20) / cols
    for i, (kieu, color, text) in enumerate(items):
        cx = x + 10 + (i % cols) * cw
        cy = y + 34 + (i // cols) * row_h + row_h / 2 - 4
        if kieu == "band":
            hop(p, f"{cid}_{i}_s", cx, cy - 6, 34, 12, fill=CAP_NEN, stroke=color, sw=1.4, r=3)
        elif kieu == "box":
            fill, stroke = color.split(",")
            hop(p, f"{cid}_{i}_s", cx + 4, cy - 7, 26, 14, fill=fill, stroke=stroke, sw=1.4)
        elif kieu == "ribbon":
            wire(p, f"{cid}_{i}_s", [(cx, cy), (cx + 34, cy)], "#74C0FC", width=9)
            wire(p, f"{cid}_{i}_s2", [(cx, cy), (cx + 34, cy)], color, width=1)
        elif kieu == "dot":
            wire(p, f"{cid}_{i}_s", [(cx, cy), (cx + 34, cy)], color)
            wire(p, f"{cid}_{i}_s2", [(cx + 17, cy), (cx + 17, cy + 9)], color)
            dot(p, f"{cid}_{i}_d", cx + 17, cy, color)
        elif kieu == "jump":
            wire(p, f"{cid}_{i}_s", [(cx + 17, cy - 9), (cx + 17, cy + 9)], color)
            duong(p, f"{cid}_{i}_s2", [(cx, cy), (cx + 34, cy)], color, width=1.6, jump=True)
        else:
            width = {"thick": 3.2}.get(kieu, 2)
            wire(p, f"{cid}_{i}_s", [(cx, cy), (cx + 34, cy)], color, width=width, dashed=kieu == "dash")
        chu(p, f"{cid}_{i}_t", cx + 42, cy - 9, cw - 46, 18, text, size=10.5)
    return y + h


def kt_doc(p: Page, cid: str, x: float, y1: float, y2: float, text: str, *, side: str = "left") -> None:
    """Đường kích thước dọc giữa y1 và y2, mũi tên hai đầu, chữ nằm ngang cạnh đường."""
    duong(p, cid, [(x, y1), (x, y2)], INK, width=1, start="block", end="block", size=5)
    tx = x - 56 if side == "left" else x + 6
    chu(p, f"{cid}_t", tx, (y1 + y2) / 2 - 8, 50, 16, text, size=10.5, bold=True,
        align="right" if side == "left" else "left")


def kt_ngang(p: Page, cid: str, y: float, x1: float, x2: float, text: str) -> None:
    """Đường kích thước ngang, chữ ở giữa phía trên."""
    duong(p, cid, [(x1, y), (x2, y)], INK, width=1, start="block", end="block", size=5)
    chu(p, f"{cid}_t", min(x1, x2), y - 19, abs(x2 - x1), 16, text, size=10.5, bold=True, align="center")
