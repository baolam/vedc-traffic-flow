"""Sinh 3.3_kien_truc/EdgeFlow_ban_ve_mach.drawio (3 trang) cho Phụ lục A của báo cáo.

  A.1  Sơ đồ nguyên lý nút chấp hành J1 (J2 giống hệt)
  A.2  Sơ đồ đấu nối khối AI biên (Pi 5 + 2 camera)
  A.3  Sơ đồ đi dây lên trụ (breadboard, mặt đứng trụ, cụm đèn, lõi cáp W1)

Spec: _ghi_chu/2026-10-11-ban-ve-mach-design.md. Chân GPIO bám
vedc-traffic-flow/src/hardware/firmware/esp32_signal_controller.ino: script dừng nếu bảng CHAN lệch firmware.
Kích thước trụ lấy từ 4.4_hinh_minh_hoa/blender/bo_tri.py (phương án đề xuất).

Không ghi đè file .drawio đã có (đội có thể đã sửa), trừ khi chạy với --ghi-de.
  python3 _scripts/tao_drawio_ban_ve_mach.py                 # tạo mới
  python3 _scripts/tao_drawio_ban_ve_mach.py --out /tmp/x.drawio
"""
from __future__ import annotations

import argparse
import sys
import xml.etree.ElementTree as ET
from pathlib import Path

from ban_ve_mach_chung import (CAP, CHAN, DAY, LED_FILL, MO, NGUON, NODEMCU_PHAI, NODEMCU_TRAI, TIN_HIEU, TY,
                               chu, chu_giai, doc_chan_firmware, dot, gnd, khung, khung_ten, kiem_chan,
                               sym, sym_ngang, wire)
from drawio_lib import FLOW, Page, box_style, container_style, edge_style, label, write_drawio

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "3.3_kien_truc" / "EdgeFlow_ban_ve_mach.drawio"
sys.path.insert(0, str(ROOT / "4.4_hinh_minh_hoa" / "blender"))
import bo_tri  # noqa: E402  (kích thước trụ, không phụ thuộc Blender)

PHA = {"NS": ("NS_RED", "NS_YELLOW", "NS_GREEN"), "EW": ("EW_RED", "EW_YELLOW", "EW_GREEN")}
MAU = ("R", "Y", "G")

# ---------------------------------------------------------------- A.1 nguyên lý nút chấp hành
UX, UY, UW = 600, 220, 250          # khung U1
ROW0, PITCH = 245, 26               # cao độ chân đầu tiên, bước chân
STUB = 40
XB = {"R": 960, "Y": 1000, "G": 1040}   # trục dây chung của 3 màu
MX, MW, MH = 1290, 210, 130         # module đèn
MOD_TOP = {"H1": 150, "H2": 300, "H3": 470, "H4": 620}
MOD_TEN = {"H1": "Bắc", "H2": "Nam", "H3": "Đông", "H4": "Tây"}
MOD_PHA = {"NS": ("H1", "H2"), "EW": ("H3", "H4")}
ROW_OFF = {"R": 40, "Y": 70, "G": 100}


def row_y(i: int) -> int:
    return ROW0 + i * PITCH


def u1_y_phai(gpio: int) -> int:
    return row_y(NODEMCU_PHAI.index(f"IO{gpio}"))


def ve_u1(p: Page) -> None:
    dung = {f"IO{g}" for g in CHAN.values()}
    p.vertex("u1", UX, UY, UW, row_y(18) - UY + 25, "",
             box_style("actuate", white=False, rounded=False, extra={"strokeWidth": 2}))
    chu(p, "u1_ten", UX, UY - 46, UW, 20, "<b>U1</b> · ESP32 NodeMCU-32S (Ai-Thinker)", size=13, align="center")
    chu(p, "u1_phu", UX, UY - 24, UW, 18, "nhìn từ mặt linh kiện, anten ở trên", size=10, color="#555555",
        align="center")
    chu(p, "u1_giua", UX + 78, row_y(6), UW - 156, 150,
        "ESP-WROOM-32<br>2 nhân 240 MHz<br>Wi-Fi 2.4 GHz<br><br>mức logic 3,3 V", size=10, color="#2F7D4F",
        align="center")
    for side, names in (("t", NODEMCU_TRAI), ("p", NODEMCU_PHAI)):
        for i, name in enumerate(names):
            y = row_y(i)
            so = i + 1 if side == "t" else 38 - i
            used = (name in dung) if side == "p" else name in ("5V", "GND") and (name == "5V" or i == 13)
            color = DAY if used else MO
            x0, x1 = (UX - STUB, UX) if side == "t" else (UX + UW, UX + UW + STUB)
            wire(p, f"u1_{side}{i}", [(x0, y), (x1, y)], color, width=1.6 if used else 1.0)
            chu(p, f"u1_{side}{i}_so", x0, y - 13, STUB, 11, str(so), size=8.5, color="#777777", align="center")
            shown = "IO2 · LED" if name == "IO2" else name
            nx, align = (UX + 6, "left") if side == "t" else (UX + UW - 86, "right")
            chu(p, f"u1_{side}{i}_ten", nx, y - 9, 80, 18, shown, size=10.5, color=color, align=align, bold=used)
    p.vertex("u1_usb", UX + 85, row_y(18) + 25, 80, 24, "micro-USB",
             box_style("shared", size=10, rounded=False))


def ve_module(p: Page, m: str) -> None:
    top = MOD_TOP[m]
    p.vertex(f"{m}_box", MX, top, MW, MH, "",
             box_style("actuate", white=False, dashed=True, rounded=True))
    chu(p, f"{m}_ten", MX + 8, top + 6, MW - 16, 20, f"<b>{m}</b> · Module đèn hướng {MOD_TEN[m]}", size=11)
    xc = MX + 150                                    # dây chung cathode
    for c in MAU:
        y = top + ROW_OFF[c]
        chu(p, f"{m}_{c}_pin", MX - 20, y - 14, 18, 12, c, size=9, color=TIN_HIEU[c], align="center", bold=True)
        wire(p, f"{m}_{c}_a", [(MX, y), (MX + 12, y)], TIN_HIEU[c])
        sym_ngang(p, f"{m}_{c}_r", "resistors.resistor_1", MX + 12, y, 36, 12)
        wire(p, f"{m}_{c}_b", [(MX + 48, y), (MX + 66, y)])
        sym_ngang(p, f"{m}_{c}_led", "opto_electronics.led_2", MX + 66, y, 40, 24, ty=TY["led"], fill=LED_FILL[c])
        wire(p, f"{m}_{c}_c", [(MX + 106, y), (xc, y)])
    y_r, y_y, y_g = (top + ROW_OFF[c] for c in MAU)
    wire(p, f"{m}_k", [(xc, y_r), (xc, y_g)])
    wire(p, f"{m}_gnd_out", [(xc, y_y), (MX + MW + 20, y_y)])
    dot(p, f"{m}_k_dot", xc, y_y)
    chu(p, f"{m}_gnd_pin", MX + MW + 6, y_y - 14, 40, 12, "GND", size=9, color="#555555")
    gnd(p, f"{m}_gnd", MX + MW + 20, y_y)
    chu(p, f"{m}_note", MX + 8, top + MH - 22, MW - 16, 16, "trở hạn dòng có sẵn trên module", size=9,
        color="#555555")


def ve_day_den(p: Page) -> None:
    """GPIO → trục dây chung → 2 module song song. Dây cắt nhau không có chấm tròn là không nối."""
    ngang = []
    for pha, keys in PHA.items():
        m1, m2 = MOD_PHA[pha]
        for c, key in zip(MAU, keys):
            y_pin, y1, y2 = u1_y_phai(CHAN[key]), MOD_TOP[m1] + ROW_OFF[c], MOD_TOP[m2] + ROW_OFF[c]
            lo, hi = min(y_pin, y1), max(y_pin, y2)
            x = XB[c]
            wire(p, f"bus_{pha}{c}", [(x, lo), (x, hi)], TIN_HIEU[c], width=1.8)
            for y in (y_pin, y1, y2):
                if lo < y < hi:
                    dot(p, f"dot_{pha}{c}_{y}", x, y, TIN_HIEU[c])
            ngang.append((f"{pha}{c}", [(UX + UW + STUB, y_pin), (x, y_pin)], c, f"{pha}_{c}", y_pin))
            ngang.append((f"{pha}{c}_m1", [(x, y1), (MX, y1)], c, None, y1))
            ngang.append((f"{pha}{c}_m2", [(x, y2), (MX, y2)], c, None, y2))
    for cid, pts, c, net, y in ngang:
        wire(p, f"h_{cid}", pts, TIN_HIEU[c], width=1.8)
        if net:
            chu(p, f"net_{cid}", UX + UW + STUB + 4, y - 15, 60, 13, net, size=9.5, color=TIN_HIEU[c], bold=True)


def ve_nguon(p: Page) -> None:
    y5, yg = row_y(NODEMCU_TRAI.index("5V")), row_y(13)
    p.vertex("adapter", 40, 668, 130, 104, label("Adapter", "5 V / 4 A<br>cắm ổ 220 V", title_size=12),
             box_style("power", white=False, size=11))
    wire(p, "ad_p", [(170, y5), (215, y5)], NGUON, width=2)
    wire(p, "ad_n", [(170, 750), (215, 750)])
    p.vertex("x1", 215, 695, 50, 72, "", box_style("power", rounded=False))
    chu(p, "x1_ten", 200, 652, 120, 34, "<b>X1</b> jack DC<br>5.5 × 2.1 mm", size=10, align="center")
    chu(p, "x1_p", 217, y5 - 9, 20, 16, "+", size=11, bold=True, align="center")
    chu(p, "x1_n", 217, 742, 20, 16, "−", size=11, bold=True, align="center")
    wire(p, "x1_f1", [(265, y5), (300, y5)], NGUON, width=2)
    sym_ngang(p, "f1", "miscellaneous.fuse_2", 300, y5, 50, 16)
    chu(p, "f1_ten", 282, 676, 90, 26, "<b>F1</b> PTC<br>0,5–1 A", size=10, align="center")
    wire(p, "f1_d1", [(350, y5), (380, y5)], NGUON, width=2)
    sym_ngang(p, "d1", "diodes.schottky_diode", 380, y5, 40, 24)
    chu(p, "d1_ten", 362, 670, 76, 26, "<b>D1</b><br>1N5819", size=10, align="center")
    wire(p, "d1_u1", [(420, y5), (UX - STUB, y5)], NGUON, width=2)
    dot(p, "x2", 455, y5, NGUON)
    chu(p, "x2_ten", 462, y5 + 5, 90, 16, "<b>X2</b> domino", size=10)
    chu(p, "net_5v", 492, y5 - 17, 60, 14, "+5V", size=10, color=NGUON, bold=True)
    wire(p, "nhanh_j2", [(455, y5), (455, 840)], NGUON, width=2, end="block")
    chu(p, "nhanh_j2_t", 360, 848, 200, 32, "+5V → chân 5V/VIN của nút J2<br>(đấu giống hệt nút J1)", size=10,
        color=NGUON, align="center")
    wire(p, "x1_gnd", [(265, 750), (290, 750)])
    gnd(p, "x1_g", 290, 750)
    wire(p, "u1_gnd", [(UX - STUB, yg), (535, yg)])
    gnd(p, "u1_g", 535, yg)


def ve_safe_stop(p: Page) -> None:
    y4 = u1_y_phai(CHAN["SAFE_STOP"])
    ys = 805
    wire(p, "s1_a", [(UX + UW + STUB, y4), (920, y4), (920, ys), (945, ys)])
    chu(p, "net_s1", UX + UW + STUB + 4, y4 - 15, 80, 13, "SAFE_STOP", size=9.5, color="#C0392B", bold=True)
    sym(p, "s1", "electro-mechanical.pushbutton_make", 945, ys - 28 * TY["nut_nhan"], 60, 28)
    wire(p, "s1_b", [(1005, ys), (1040, ys)])
    gnd(p, "s1_g", 1040, ys)
    chu(p, "s1_ten", 893, ys + 10, 130, 34, "<b>S1</b> safe-stop<br>nút tự giữ, thường mở", size=10,
        align="center")


def ve_logic_analyzer(p: Page) -> None:
    chu(p, "x3_ten", 1255, 778, 320, 18, "<b>X3</b> · header logic analyzer (tùy chọn), kẹp song song "
        "lên net cùng tên", size=10)
    rows = [["Kênh", "Net", "GPIO"]]
    for i, key in enumerate(PHA["NS"] + PHA["EW"]):
        rows.append([f"CH{i}", f"{key[:2]}_{key[3]}", str(CHAN[key])])
    rows += [["CH6", "SAFE_STOP", str(CHAN["SAFE_STOP"])], ["GND", "GND", "—"]]
    p.table("x3", 1255, 800, [70, 120, 70], rows, row_h=20, size=10)


GHI_CHU_A1 = (
    "<b>Ghi chú</b><br>"
    "• Bắc và Nam cùng pha nên mắc <b>song song</b> trên 3 chân IO23/22/21; Đông và Tây trên IO19/18/5.<br>"
    "• Module đèn có sẵn trở hạn dòng. Dòng ước tính ~6 mA mỗi LED ở 3,3 V, tức ~12 mA mỗi chân GPIO "
    "(2 module song song).<br>"
    "• S1: GPIO 4 dùng điện trở kéo lên nội (INPUT_PULLUP). Nhấn = LOW = dừng an toàn: vàng nhấp nháy, "
    "từ chối lệnh.<br>"
    "• IO2 là LED trạng thái có sẵn trên board.<br>"
    "• Nạp firmware qua micro-USB (CH340): rút nguồn 5 V ngoài trước khi cắm cáp.<br>"
    "• Mọi ký hiệu GND là GND chung của nút J1 và J2. Pi 5 dùng nguồn riêng, không chung GND (Hình A.2).<br>"
    "• W1: cáp 8 lõi từ breadboard lên cụm đèn trên trụ, chi tiết ở Hình A.3."
)


def page_a1() -> Page:
    p = Page("A.1 Nguyên lý nút chấp hành", 1820, 1110)
    khung(p, "vung_tru", 1250, 112, 315, 655, stroke=CAP, value="Trên trụ J1 · cụm đèn 4 mặt")
    khung(p, "w1", 1150, 160, 50, 580, stroke=CAP)
    chu(p, "w1_ten", 1112, 120, 126, 36, "<b>W1</b> · cáp 8 lõi<br>lên trụ (~1,2 m)", size=10, color=CAP,
        align="center")
    chu(p, "ghi_chu", 40, 140, 480, 330, GHI_CHU_A1, size=11)
    ve_u1(p)
    for m in MOD_TOP:
        ve_module(p, m)
    ve_day_den(p)
    ve_nguon(p)
    ve_safe_stop(p)
    ve_logic_analyzer(p)
    chu_giai(p, "cg", 40, 1040, [(NGUON, "+5V", False), (DAY, "GND, dây trong module", False),
                                 (TIN_HIEU["R"], "Tín hiệu đèn (màu theo đèn)", False),
                                 (MO, "Chân không dùng", False)], step=228)
    chu(p, "quy_uoc", 40 + 4 * 228, 1030, 300, 20, "Dây cắt nhau không có chấm tròn: không nối", size=11)
    khung_ten(p, "kt", 1240, 1012, "A.1", "Sơ đồ nguyên lý nút chấp hành J1 (nút J2 giống hệt)",
              "Chân GPIO bám firmware esp32_signal_controller.ino")
    return p


# ---------------------------------------------------------------- A.2 đấu nối khối AI biên
GHI_CHU_A2 = (
    "<b>Ghi chú</b><br>"
    "• Hai miền nguồn tách riêng: Pi 5 dùng nguồn USB-C 27 W; hai ESP32 và module đèn dùng adapter 5 V "
    "(Hình A.1).<br>"
    "• Pi và ESP32 <b>không nối dây</b>, kể cả GND. Hai bên chỉ trao đổi qua Wi-Fi / MQTT.<br>"
    "• Cáp kèm camera là loại 15–15 pin, không cắm được vào Pi 5; cần cáp FPC 22 → 15 pin.<br>"
    "• Đọc 2 camera trên 1 Pi: phần cứng có sẵn 2 cổng CSI, phần mềm đang phát triển."
)


def page_a2() -> Page:
    p = Page("A.2 Đấu nối khối AI biên", 1700, 920)
    hw = dict(white=False)
    p.vertex("ac", 40, 150, 220, 56, label("Ổ cắm 220 V AC"), box_style("world", **hw))
    p.vertex("psu", 40, 290, 220, 74, label("Nguồn USB-C PD 27 W", "5,1 V / 5 A · riêng cho Pi"),
             box_style("power", **hw))
    p.vertex("pi", 420, 120, 520, 560, "Raspberry Pi 5 (4 GB) · đặt trong tủ ven đường",
             container_style("edge_ai"))
    ports = {
        "p_usb": (432, 307, 150, 44, "USB-C (nguồn vào)"),
        "p_fan": (780, 140, 150, 44, "FAN (JST 4 chân)"),
        "p_cam0": (778, 230, 150, 50, "CAM/DISP 0<br>(FPC 22 chân)"),
        "p_cam1": (778, 430, 150, 50, "CAM/DISP 1<br>(FPC 22 chân)"),
        "p_sd": (432, 600, 150, 44, "khe microSD 64 GB"),
        "p_wifi": (778, 600, 150, 44, "Wi-Fi 2.4 GHz (onboard)"),
    }
    for cid, (x, y, w, h, text) in ports.items():
        p.vertex(cid, x, y, w, h, text, box_style("edge_ai", size=11, rounded=False))
    chu(p, "pi_giua", 585, 290, 210, 210,
        "BCM2712 · 4× Cortex-A76 2,4 GHz<br>Raspberry Pi OS Trixie<br><br>YOLO11n (ONNX, OpenCV DNN)<br>"
        "vision J1 ← CAM0<br>vision J2 ← CAM1<br><br><i>đọc 2 camera: đang phát triển</i>",
        size=11, color="#2563A8", align="center")
    p.vertex("fan", 765, 20, 180, 62, label("Tản nhiệt + quạt 5 V", "cổng FAN hoặc chân 5V/GND,<br>tùy loại tản nhiệt",
                                            sub_size=10), box_style("shared", **hw))
    p.vertex("cam1", 1160, 210, 270, 90, label("Camera Module 3 Wide", "SC0874 · IMX708 · 120° chéo<br>"
                                               "trên trụ J1, nhìn thẳng xuống"), box_style("edge_ai", **hw))
    p.vertex("cam2", 1160, 410, 270, 90, label("Camera Module 3 Wide", "SC0874 · IMX708 · 120° chéo<br>"
                                               "trên trụ J2, nhìn thẳng xuống"), box_style("edge_ai", **hw))
    p.vertex("router", 1160, 594, 270, 56, label("Router Wi-Fi 2.4 GHz", "LAN riêng"), box_style("network", **hw))
    p.vertex("server", 1160, 720, 270, 56, label("Máy chủ điều phối", "MQTT broker · Graph-Control"),
             box_style("control", **hw))
    p.vertex("esp", 1470, 594, 200, 56, label("ESP32 J1, J2", "Hình A.1"), box_style("actuate", **hw))
    sym(p, "ant", "radio.aerial_-_antenna_1", 958, 570, 24, 30)
    pw = edge_style("power", width=2.2)
    p.edge("e_ac", "ac", "psu", "220 V", pw)
    p.edge("e_psu", "psu", "p_usb", "USB-C", pw)
    p.edge("e_fan", "p_fan", "fan", "", edge_style("physical", end="none", both=False))
    fpc = edge_style("physical", width=3, end="none")
    p.edge("e_cam0", "p_cam0", "cam1", "FPC 22 → 15 chân, dài 1 m", fpc)
    p.edge("e_cam1", "p_cam1", "cam2", "FPC 22 → 15 chân, dài 1 m", fpc)
    net = edge_style("physical", dashed=True, both=True)
    p.edge("e_wifi", "p_wifi", "router", "Wi-Fi", net)
    p.edge("e_srv", "router", "server", "Wi-Fi / LAN", net)
    p.edge("e_esp", "router", "esp", "", net)
    chu(p, "ghi_chu", 40, 420, 350, 250, GHI_CHU_A2, size=11)
    chu_giai(p, "cg", 40, 860, [(FLOW["power"], "Nguồn điện", False), (FLOW["physical"], "Cáp FPC / dây", False),
                                (FLOW["physical"], "Không dây (Wi-Fi)", True)])
    khung_ten(p, "kt", 1110, 806, "A.2", "Sơ đồ đấu nối khối AI biên (Raspberry Pi 5 + 2 camera)",
              "Cổng theo Raspberry Pi 5; linh kiện theo bảng 3.4")
    return p


# ---------------------------------------------------------------- A.3 đi dây lên trụ
BB_X, BB_W = 40, 560
PIN_DX = 15
X_PIN1 = 455            # chân 1 (3V3) và chân 38 (GND) ở đầu có anten (bên phải)
Y_TREN, Y_DUOI = 192, 298   # hàng chân trái (tấm A) và hàng chân phải (tấm B) khi anten quay sang phải
CORE_X = 548            # lõi W1 cắm ở mép phải tấm B
LOI = [  # (lõi, màu T568B, (màu chính, có sọc trắng), tín hiệu, khóa CHAN, module)
    (1, "cam-trắng", ("#F57C00", True), "NS_R", "NS_RED", "H1 Bắc + H2 Nam (chân R)"),
    (2, "cam", ("#F57C00", False), "NS_Y", "NS_YELLOW", "H1 Bắc + H2 Nam (chân Y)"),
    (3, "xanh lá-trắng", ("#2E7D32", True), "NS_G", "NS_GREEN", "H1 Bắc + H2 Nam (chân G)"),
    (4, "xanh dương", ("#1565C0", False), "EW_R", "EW_RED", "H3 Đông + H4 Tây (chân R)"),
    (5, "xanh dương-trắng", ("#1565C0", True), "EW_Y", "EW_YELLOW", "H3 Đông + H4 Tây (chân Y)"),
    (6, "xanh lá", ("#2E7D32", False), "EW_G", "EW_GREEN", "H3 Đông + H4 Tây (chân G)"),
    (7, "nâu-trắng", ("#6D4C41", True), "GND", None, "GND của H1–H4"),
    (8, "nâu", ("#6D4C41", False), "—", None, "dự phòng"),
]


def x_chan(so: int) -> float:
    """Tọa độ x của chân vật lý `so` trên breadboard (anten quay sang phải, micro-USB bên trái)."""
    return X_PIN1 - (so - 1) * PIN_DX if so <= 19 else X_PIN1 - (38 - so) * PIN_DX


def so_chan_phai(gpio: int) -> int:
    return 38 - NODEMCU_PHAI.index(f"IO{gpio}")


def ve_breadboard(p: Page) -> None:
    chu(p, "bb_tieu_de", 40, 40, 560, 22, "<b>① Breadboard của nút J1</b> (nhìn từ trên, giản lược)", size=13)
    for cid, y, rails in (("bbA", 90, (102, 114)), ("bbB", 250, (376, 388))):
        p.vertex(cid, BB_X, y, BB_W, 150, "", box_style("shared", white=False, rounded=False))
        wire(p, f"{cid}_p", [(BB_X + 8, rails[0]), (BB_X + BB_W - 8, rails[0])], "#E53935", width=1.2)
        wire(p, f"{cid}_n", [(BB_X + 8, rails[1]), (BB_X + BB_W - 8, rails[1])], "#1E63C6", width=1.2)
    chu(p, "bbA_ten", BB_X + 8, 120, 140, 16, "tấm A · thanh +5V / GND", size=9, color="#777777")
    chu(p, "bbB_ten", BB_X + 8, 354, 140, 16, "tấm B · thanh +5V / GND", size=9, color="#777777")
    p.vertex("bb_u1", 168, 178, 302, 134, "<b>U1</b> ESP32 NodeMCU-32S<br><span style='font-size:10px'>"
             "cắm bắc cầu qua khe giữa 2 tấm</span>", box_style("actuate", white=False, size=12,
                                                               extra={"verticalAlign": "middle"}))
    p.vertex("bb_usb", 146, 230, 24, 30, "", box_style("shared", rounded=False))
    chu(p, "bb_usb_t", 100, 262, 80, 14, "micro-USB", size=9, color="#555555")
    chu(p, "bb_ant", 472, 236, 50, 14, "anten", size=9, color="#555555")
    for so in range(1, 39):
        y = Y_TREN if so <= 19 else Y_DUOI
        dot(p, f"bb_pin{so}", x_chan(so), y, "#555555", r=2.5)
    # +5V và GND vào U1 (hàng trên, tấm A)
    x5, xg = x_chan(19), x_chan(14)
    wire(p, "bb_5v", [(x5, Y_TREN), (x5, 102)], NGUON, width=2, jump=True)
    wire(p, "bb_gnd", [(xg, Y_TREN), (xg, 114)], DAY, width=2)
    chu(p, "bb_5v_t", x5 + 4, 140, 40, 14, "5V", size=9, color=NGUON, bold=True)
    chu(p, "bb_gnd_t", xg + 4, 140, 40, 14, "GND", size=9, bold=True)
    wire(p, "bb_domino_p", [(0, 102), (BB_X + 8, 102)], NGUON, width=2)
    wire(p, "bb_domino_n", [(0, 114), (BB_X + 8, 114)], DAY, width=2)
    chu(p, "bb_domino_t", 40, 64, 300, 18, "← từ X2 domino: +5V, GND (Hình A.1)", size=10, color=NGUON)
    wire(p, "bb_gnd_ab", [(52, 114), (52, 388)], DAY, width=1.6, jump=True)
    # Tín hiệu đèn: chân U1 (hàng dưới, tấm B) → lõi W1 ở mép phải
    for i, (loi, _ten, _mau, net, key, _mod) in enumerate(LOI[:6]):
        x, y = x_chan(so_chan_phai(CHAN[key])), 315 + i * 10
        c = net[-1]
        wire(p, f"bb_s{loi}", [(x, Y_DUOI), (x, y), (CORE_X, y)], TIN_HIEU[c], width=1.8)
        chu(p, f"bb_s{loi}_t", x - 10, Y_DUOI - 22, 20, 10, str(CHAN[key]), size=8, color=TIN_HIEU[c],
            align="center", bold=True)
    dot(p, "bb_s7", CORE_X, 388, DAY)
    wire(p, "bb_bo", [(CORE_X, 310), (CORE_X, 412)], CAP, width=4)
    for i in range(6):
        chu(p, f"bb_loi{i + 1}", CORE_X + 6, 309 + i * 10, 14, 10, str(i + 1), size=8, color=CAP, bold=True)
    chu(p, "bb_loi7", CORE_X + 6, 382, 14, 10, "7", size=8, color=CAP, bold=True)
    # S1: IO4 → GND (thanh dưới tấm B)
    x4 = x_chan(so_chan_phai(CHAN["SAFE_STOP"]))
    wire(p, "bb_sw1_a", [(x4, Y_DUOI), (x4, 330)], "#C0392B", width=1.8)
    p.vertex("bb_sw1", x4 - 14, 330, 28, 26, "S1", box_style("safety", white=False, size=10, rounded=False))
    wire(p, "bb_sw1_b", [(x4, 356), (x4, 388)], DAY, width=1.8, jump=True)
    chu(p, "bb_sw1_t", x4 - 14, Y_DUOI - 22, 28, 10, "4", size=8, color="#C0392B", align="center", bold=True)
    chu(p, "bb_ghi_chu", 40, 418, 560, 120,
        "• Lõi cáp W1 (nên dùng loại lõi đặc) cắm thẳng vào mép phải tấm B, mỗi lõi một hàng.<br>"
        "• Dây nhảy cùng màu đèn: đỏ / vàng / xanh. Số nhỏ cạnh chân là số GPIO.<br>"
        "• S1 nối IO4 xuống thanh GND của tấm B.<br>"
        "• Hai thanh GND của 2 tấm nối với nhau (dây đen bên trái).", size=11)


def ve_tru(p: Page) -> None:
    s = 1.2                                   # px / mm
    y0, xp = 820, 800
    yz = lambda mm: y0 - mm * s               # noqa: E731
    reach = bo_tri.arm_len() * s
    xe = xp + reach                           # đầu cần, trên tâm ngã tư
    chu(p, "tru_tieu_de", 660, 40, 520, 22, "<b>② Mặt đứng trụ J1</b> (kích thước đề xuất, mm)", size=13)
    p.vertex("mat_sa_ban", 660, y0, 520, 10, "", box_style("world", white=False, rounded=False))
    chu(p, "mat_sa_ban_t", 1010, y0 + 12, 170, 16, "mặt sa bàn", size=10, color="#6B6B66", align="right")
    al = box_style("shared", white=False, rounded=False, extra={"fillColor": "#CFD8DC", "strokeColor": "#78909C"})
    top = bo_tri.ARM_Z + 12
    p.vertex("tru", xp - 8, yz(top), 16, top * s, "", al)
    p.vertex("can_cam", xp - 8, yz(bo_tri.ARM_Z) - 11, reach + 16, 22, "", al)
    p.vertex("can_den", xp - 8, yz(bo_tri.SIGNAL_ARM_H) - 10, reach + 16, 20, "", al)
    # camera dưới đầu cần trên
    y_lens = yz(bo_tri.CAMERA_H)
    p.vertex("cam", xe - 14, yz(bo_tri.ARM_Z) + 11, 28, y_lens - yz(bo_tri.ARM_Z) - 11, "",
             box_style("edge_ai", white=False, rounded=False))
    wire(p, "fov_l", [(xe, y_lens), (xe - 70, y_lens + 110)], "#9A9A9A", width=1, dashed=True)
    wire(p, "fov_r", [(xe, y_lens), (xe + 70, y_lens + 110)], "#9A9A9A", width=1, dashed=True)
    chu(p, "cam_t", xe + 22, y_lens - 34, 160, 30, "Camera Module 3 Wide<br>nhìn thẳng xuống", size=10,
        color="#2563A8")
    # cụm đèn treo dưới đầu cần đèn
    yc = yz(bo_tri.SIGNAL_H)
    wire(p, "treo", [(xe, yz(bo_tri.SIGNAL_ARM_H) + 10), (xe, yc - 24)], "#78909C", width=2)
    p.vertex("cum_den", xe - 16, yc - 24, 32, 48, "", box_style("shared", white=False, rounded=True,
                                                                 extra={"fillColor": "#37474F"}))
    for i, c in enumerate(MAU):
        dot(p, f"cum_{c}", xe, yc - 13 + i * 13, LED_FILL[c], r=4.5)
    chu(p, "cum_t", xe + 22, yc - 20, 160, 30, "cụm đèn 4 mặt H1–H4<br>(xem ③)", size=10)
    wire(p, "tam", [(xe, y0), (xe, y0 - 30)], "#9A9A9A", width=1, dashed=True)
    chu(p, "tam_t", xe - 60, y0 + 12, 120, 16, "tâm ngã tư", size=10, color="#6B6B66", align="center")
    # kích thước theo chiều cao (bên trái trụ)
    for i, (mm, ten) in enumerate([(bo_tri.ARM_Z, "cần camera"), (bo_tri.CAMERA_H, "ống kính"),
                                   (bo_tri.SIGNAL_ARM_H, "cần đèn"), (bo_tri.SIGNAL_H, "tâm cụm đèn")]):
        y = yz(mm)
        wire(p, f"kt_{i}", [(774, y), (xp - 10 if i != 1 else xe - 16, y)], "#B0B0B0", width=1, dashed=True)
        chu(p, f"kt_{i}_t", 660, y - 9, 110, 18, f"<b>{mm:.0f}</b> {ten}", size=10, align="right")
    wire(p, "kt_reach", [(xp, yz(bo_tri.ARM_Z) - 34), (xe, yz(bo_tri.ARM_Z) - 34)], DAY, width=1,
         end="block")
    chu(p, "kt_reach_t", xp, yz(bo_tri.ARM_Z) - 60, 260, 18,
        f"<b>{bo_tri.arm_len():.0f}</b> cần vươn tới tâm ngã tư", size=10)
    # cáp W1: từ breadboard → dưới mặt sa bàn → trụ (bên trái) → cần đèn → cụm đèn
    w1 = [(CORE_X, 412), (630, 412), (630, y0 + 26), (xp - 14, y0 + 26), (xp - 14, yz(bo_tri.SIGNAL_ARM_H) + 14),
          (xe - 6, yz(bo_tri.SIGNAL_ARM_H) + 14), (xe - 6, yc - 24)]
    wire(p, "w1", w1, CAP, width=3.2)
    chu(p, "w1_t", 636, y0 - 110, 110, 46, "<b>W1</b> CAT5e<br>8 lõi, ~1,2 m", size=10, color=CAP)
    # cáp FPC camera: Pi → dưới mặt sa bàn → trụ (bên phải) → lưng cần trên → camera
    fpc = [(660, y0 + 42), (xp + 14, y0 + 42), (xp + 14, yz(bo_tri.ARM_Z) - 16), (xe + 8, yz(bo_tri.ARM_Z) - 16),
           (xe + 8, yz(bo_tri.ARM_Z) + 11)]
    wire(p, "fpc", fpc, "#6B6B66", width=2, dashed=True)
    chu(p, "fpc_t", 660, y0 + 46, 520, 30,
        f"← từ Pi 5 (tủ ven đường): cáp FPC 22 → 15 chân, dài 1 m (đường đi ~{bo_tri.polyline_len(bo_tri.csi_route('J1')) / 1000:.2f} m)".replace(".", ","),
        size=10, color="#6B6B66")
    chu(p, "tru_ghi_chu", 660, 900, 520, 40, "Trụ nhôm định hình 20 × 20. Số đo lấy từ bo_tri.py, là phương án "
        "đề xuất; đo lại khi có sa bàn thật.", size=10, color="#555555")


def ve_cum_den(p: Page) -> None:
    cx, cy = 1330, 190
    chu(p, "cum_tieu_de", 1200, 40, 600, 22, "<b>③ Cụm đèn 4 mặt nhìn từ trên</b>", size=13)
    p.vertex("cum_tam", cx - 20, cy - 20, 40, 40, "", box_style("shared", white=False, rounded=False,
                                                                extra={"fillColor": "#37474F"}))
    faces = {"H1": (cx - 25, cy - 38, 50, 16, "Bắc", (cx - 40, cy - 66)),
             "H2": (cx - 25, cy + 22, 50, 16, "Nam", (cx - 40, cy + 42)),
             "H3": (cx + 22, cy - 25, 16, 50, "Đông", (cx + 44, cy - 10)),
             "H4": (cx - 38, cy - 25, 16, 50, "Tây", (cx - 124, cy - 10))}
    for m, (x, y, w, h, ten, (tx, ty)) in faces.items():
        p.vertex(f"mat_{m}", x, y, w, h, "", box_style("shared", white=False, rounded=False,
                                                      extra={"fillColor": "#263238"}))
        for i, c in enumerate(MAU):
            px, py = (x + 10 + i * 15, y + h / 2) if w > h else (x + w / 2, y + 10 + i * 15)
            dot(p, f"mat_{m}_{c}", px, py, LED_FILL[c], r=3.5)
        chu(p, f"mat_{m}_t", tx, ty, 80, 18, f"<b>{m}</b> {ten}", size=11, align="center" if w > h else "left")
    wire(p, "bac", [(1466, 230), (1466, 160)], DAY, width=1.6, end="block")
    chu(p, "bac_t", 1446, 236, 40, 16, "Bắc", size=10, align="center")
    chu(p, "cum_mo_ta", 1500, 120, 300, 150,
        "Mỗi mặt quay về phía xe tới: mặt H1 quay lên Bắc cho xe đi từ phía Bắc vào ngã tư, các mặt khác "
        "tương tự.<br><b>H1 song song H2</b> (pha Bắc–Nam), <b>H3 song song H4</b> (pha Đông–Tây).", size=11)


def ve_bang_loi(p: Page) -> None:
    x0, y0, rh = 1200, 330, 26
    cols = [56, 170, 80, 60, 230]
    chu(p, "loi_tieu_de", x0, 296, 600, 22, "<b>④ Lõi cáp W1 (CAT5e, màu T568B): ĐỀ XUẤT</b>", size=13)
    p.table("loi", x0, y0, cols, [["Lõi", "Màu", "Tín hiệu", "GPIO", "Tới module"]], row_h=rh, size=11)
    for r, (loi, ten_mau, (mau, soc), net, key, mod) in enumerate(LOI, start=1):
        y = y0 + r * rh
        gpio = str(CHAN[key]) if key else ("GND" if net == "GND" else "—")
        cells = [str(loi), ten_mau, net, gpio, mod]
        x = x0
        for c, (txt, w) in enumerate(zip(cells, cols)):
            extra = {"spacingLeft": 40} if c == 1 else {}
            p.vertex(f"loi_r{r}c{c}", x, y, w, rh, txt,
                     box_style("shared", rounded=False, size=11, align="left", extra=extra))
            x += w
        swatch = {"fillColor": mau, "strokeColor": "#555555"}
        if soc:
            swatch.update(gradientColor="#FFFFFF", gradientDirection="east")
        p.vertex(f"loi_r{r}_sw", x0 + cols[0] + 8, y + 7, 26, 12, "",
                 box_style("shared", rounded=False, extra=swatch))


def ve_re_nhanh(p: Page) -> None:
    chu(p, "re_tieu_de", 1200, 580, 600, 22, "<b>⑤ Điểm rẽ nhánh ở đầu cần đèn: ĐỀ XUẤT</b>", size=13)
    y = 660
    wire(p, "re_loi", [(1210, y), (1330, y)], "#F57C00", width=3)
    chu(p, "re_loi_t", 1210, y - 24, 120, 16, "lõi 1 (NS_R)", size=10)
    p.vertex("re_han", 1330, y - 11, 46, 22, "hàn", box_style("shared", white=False, size=10, rounded=True))
    for i, (m, dy) in enumerate((("H1 Bắc", -32), ("H2 Nam", 32))):
        wire(p, f"re_dupont{i}", [(1376, y), (1420, y), (1420, y + dy), (1470, y + dy)], TIN_HIEU["R"], width=1.8)
        p.vertex(f"re_mod{i}", 1470, y + dy - 13, 140, 26, f"{m} · chân R",
                 box_style("actuate", white=False, size=10, rounded=False))
    dot(p, "re_dot", 1420, y, TIN_HIEU["R"])
    chu(p, "re_mo_ta", 1200, 712, 600, 70,
        "Mỗi lõi tín hiệu hàn ra 2 dây dupont cái, bọc co nhiệt, cắm vào 2 module đối diện. Làm tương tự cho "
        "lõi 2–6. Lõi 7 (GND) rẽ ra cả 4 module.", size=11)


def page_a3() -> Page:
    p = Page("A.3 Đi dây lên trụ", 1840, 1060)
    ve_breadboard(p)
    ve_tru(p)
    ve_cum_den(p)
    ve_bang_loi(p)
    ve_re_nhanh(p)
    chu_giai(p, "cg", 40, 1000, [(NGUON, "+5V", False), (DAY, "GND", False),
                                 (TIN_HIEU["R"], "Dây tín hiệu đèn", False), (CAP, "Cáp W1 lên trụ", False),
                                 ("#6B6B66", "Cáp FPC camera", True)], step=232)
    khung_ten(p, "kt", 1240, 960, "A.3", "Sơ đồ đi dây lên trụ J1 (trụ J2 giống hệt, đặt đối xứng)",
              "Màu lõi cáp, cách rẽ nhánh và kích thước trụ là đề xuất")
    return p


# ---------------------------------------------------------------- kiểm tra và ghi file
def kiem_xml(path: Path) -> list[str]:
    """Mỗi trang parse được; mọi source/target của edge trỏ tới id có thật trong trang."""
    loi = []
    for diagram in ET.parse(path).getroot().iter("diagram"):
        cells = list(diagram.iter("mxCell"))
        ids = {c.get("id") for c in cells}
        for c in cells:
            for attr in ("source", "target"):
                ref = c.get(attr)
                if ref and ref not in ids:
                    loi.append(f"{diagram.get('name')}: {c.get('id')}.{attr} → '{ref}' không tồn tại")
    return loi


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--out", type=Path, default=OUT)
    ap.add_argument("--ghi-de", action="store_true", help="cho phép ghi đè file .drawio đã có")
    args = ap.parse_args()

    loi = kiem_chan(CHAN, doc_chan_firmware())
    if loi:
        print("Bảng chân lệch firmware, không vẽ:\n  " + "\n  ".join(loi), file=sys.stderr)
        return 1
    if args.out.exists() and not args.ghi_de:
        print(f"{args.out} đã có (có thể đội đã sửa). Không ghi đè; thêm --ghi-de nếu chắc chắn.", file=sys.stderr)
        return 2

    write_drawio(str(args.out), [page_a1(), page_a2(), page_a3()])
    loi = kiem_xml(args.out)
    if loi:
        print("XML lỗi:\n  " + "\n  ".join(loi), file=sys.stderr)
        return 1
    print(f"đã ghi {args.out} (3 trang)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
