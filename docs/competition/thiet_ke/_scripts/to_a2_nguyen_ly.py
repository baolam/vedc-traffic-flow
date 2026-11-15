"""Tờ A.2: sơ đồ nguyên lý nút chấp hành J1 (nút J2 đấu giống hệt).

Trái: bảng tín hiệu, ghi chú, chuỗi nguồn vào. Giữa: U1 đủ 38 chân. Cáp W1 vẽ thành dải dọc; bên phải dải là
phần nằm trên trụ: 6 trục dây rẽ nhánh và 4 module đèn H1–H4.

Thứ tự trục dây (xanh, vàng, đỏ từ trái sang; nhóm Đông–Tây bên trái nhóm Bắc–Nam) chọn để dây từ U1 không
cắt trục nào; chỉ còn 6 chỗ giao nhau trong từng nhóm, vẽ bằng cung vượt.
"""
from __future__ import annotations

from ban_ve_mach_chung import (CAP, CAP_NEN, CHAN, DAY, INK, INK2, LED_FILL, LOI, MAU, MO, NGUON, NGUON_NEN,
                               NODEMCU_PHAI, NODEMCU_TRAI, NUT, NUT_NEN, PHA, RULE, TIN_HIEU, TY, W, H,
                               bang, chu, chu_giai, dot, duong, ghi_chu, gnd, hop, khung_ten, khung_to,
                               net_ngan, nut_nhan_doc, sym_ngang, the, wire)
from drawio_lib import Page

UX, UW = 520, 250                   # khung U1
ROW0, PITCH = 190, 31               # cao độ chân đầu tiên, bước chân
STUB = 44
X_NET = UX + UW + STUB              # đầu dây tín hiệu sau chân U1
BAND_X, BAND_W = 950, 34            # dải cáp W1
BAND_Y0, BAND_Y1 = 160, 884
XBUS = {"EW": {"G": 1010, "Y": 1040, "R": 1070}, "NS": {"G": 1100, "Y": 1130, "R": 1160}}
MX, MW, MH = 1200, 250, 150         # module đèn
MOD_TOP = {"H1": 140, "H2": 312, "H3": 484, "H4": 656}
MOD_TEN = {"H1": "Bắc", "H2": "Nam", "H3": "Đông", "H4": "Tây"}
MOD_PHA = {"NS": ("H1", "H2"), "EW": ("H3", "H4")}
ROW_OFF = {"R": 58, "Y": 90, "G": 122}
X_GND_BUS = MX + MW + 40
Y_GND_VE = 856                      # đường GND quay về breadboard (lõi 7)
LOI_CUA = {key: loi for loi, _t, _m, _n, key, _mod in LOI if key}


def row_y(i: int) -> int:
    return ROW0 + i * PITCH


def y_gpio(gpio: int) -> int:
    return row_y(NODEMCU_PHAI.index(f"IO{gpio}"))


def so_chan(gpio: int) -> int:
    return 38 - NODEMCU_PHAI.index(f"IO{gpio}")


def ve_u1(p: Page) -> None:
    dung = {f"IO{g}" for g in CHAN.values()}
    top, bot = row_y(0) - 34, row_y(18) + 34
    chu(p, "u1_ten", UX - 30, 112, UW + 60, 20, "<b>U1</b> · ESP32 NodeMCU-32S", size=14, align="center")
    chu(p, "u1_phu", UX - 40, 132, UW + 80, 16, "Ai-Thinker · 38 chân · nhìn từ mặt linh kiện", size=10.5,
        color=INK2, align="center")
    hop(p, "u1", UX, top, UW, bot - top, fill="#FAFBFC", stroke=INK, sw=1.8, r=3)
    hop(p, "u1_anten", UX + 50, top + 4, UW - 100, 16, '<span style="letter-spacing:0.12em">ANTEN</span>',
        fill="none", stroke=RULE, sw=1, dashed=True, size=8, color=INK2)
    chu(p, "u1_giua", UX + 66, row_y(7) - 6, UW - 132, 110,
        "ESP-WROOM-32<br>Xtensa 2 nhân · 240 MHz<br>Wi-Fi 2.4 GHz<br>mức logic 3,3 V", size=10.5, color=INK2,
        align="center")
    for side, names in (("t", NODEMCU_TRAI), ("p", NODEMCU_PHAI)):
        for i, name in enumerate(names):
            y = row_y(i)
            so = i + 1 if side == "t" else 38 - i
            used = name in dung if side == "p" else name == "5V" or i == 13
            color = DAY if used else MO
            x0, x1 = (UX - STUB, UX) if side == "t" else (UX + UW, UX + UW + STUB)
            wire(p, f"u1_{side}{i}", [(x0, y), (x1, y)], color, width=1.6 if used else 1.1)
            chu(p, f"u1_{side}{i}_so", x0, y - 14, STUB, 12, str(so), size=9.5, color=INK2 if used else MO,
                align="center")
            shown = "IO2 · LED" if name == "IO2" else name
            nx, align = (UX + 8, "left") if side == "t" else (UX + UW - 98, "right")
            chu(p, f"u1_{side}{i}_ten", nx, y - 9, 90, 18, shown, size=11, color=color, align=align, bold=used)
    hop(p, "u1_usb", UX + UW / 2 - 52, bot, 104, 22, "micro-USB · CH340", fill="#FFFFFF", stroke=INK2, sw=1.2,
        size=9.5, color=INK2)
    chu(p, "u1_led", X_NET + 6, y_gpio(CHAN["STATUS_LED"]) - 8, 110, 16, "LED trên board", size=10, color=INK2)


def ve_bang_cap(p: Page) -> None:
    hop(p, "w1", BAND_X, BAND_Y0, BAND_W, BAND_Y1 - BAND_Y0, fill=CAP_NEN, stroke=CAP, sw=1.6, r=6)
    chu(p, "w1_ten", BAND_X - 110, BAND_Y0 - 44, 144, 40,
        '<b style="font-size:13px">W1</b> · CAT5e<br>8 lõi · ~1,2 m', size=10.5, color=CAP, align="right")


def ve_module(p: Page, m: str) -> None:
    top = MOD_TOP[m]
    hop(p, f"{m}_box", MX, top, MW, MH, fill="#FFFFFF", stroke=NUT, sw=1.5, r=5)
    hop(p, f"{m}_hdr", MX + 1.5, top + 1.5, MW - 3, 28, f"<b>{m}</b> · Module đèn hướng {MOD_TEN[m]}",
        fill=NUT_NEN, stroke="none", sw=0, r=4, size=11, align="left", pad=10)
    wire(p, f"{m}_hdr_vach", [(MX, top + 30), (MX + MW, top + 30)], NUT, width=1)
    xc = MX + 176                                    # dây chung cathode
    for c in MAU:
        y = top + ROW_OFF[c]
        chu(p, f"{m}_{c}_pin", MX + 4, y - 16, 16, 12, c, size=9.5, color=TIN_HIEU[c], align="center", bold=True)
        wire(p, f"{m}_{c}_a", [(MX, y), (MX + 22, y)], TIN_HIEU[c], width=1.8)
        sym_ngang(p, f"{m}_{c}_r", "resistors.resistor_1", MX + 22, y, 40, 12)
        wire(p, f"{m}_{c}_b", [(MX + 62, y), (MX + 84, y)])
        sym_ngang(p, f"{m}_{c}_led", "opto_electronics.led_2", MX + 84, y, 40, 24, ty=TY["led"],
                  fill=LED_FILL[c])
        wire(p, f"{m}_{c}_c", [(MX + 124, y), (xc, y)])
    y_r, y_y, y_g = (top + ROW_OFF[c] for c in MAU)
    wire(p, f"{m}_k", [(xc, y_r), (xc, y_g)])
    dot(p, f"{m}_k_dot", xc, y_y)
    wire(p, f"{m}_gnd", [(xc, y_y), (X_GND_BUS, y_y)])
    chu(p, f"{m}_gnd_pin", MX + MW - 44, y_y - 16, 40, 12, "GND", size=9.5, color=INK2, align="right", bold=True)
    if m != "H1":
        dot(p, f"{m}_gnd_dot", X_GND_BUS, y_y)


def ve_day_den(p: Page) -> None:
    """GPIO → qua W1 → trục rẽ nhánh → 2 module song song."""
    for pha, keys in PHA.items():
        m1, m2 = MOD_PHA[pha]
        for c, key in zip(MAU, keys):
            y_pin = y_gpio(CHAN[key])
            y1, y2 = MOD_TOP[m1] + ROW_OFF[c], MOD_TOP[m2] + ROW_OFF[c]
            lo, hi = min(y_pin, y1), max(y_pin, y2)
            x = XBUS[pha][c]
            wire(p, f"bus_{pha}{c}", [(x, lo), (x, hi)], TIN_HIEU[c], width=1.8)
            wire(p, f"h_{pha}{c}", [(X_NET, y_pin), (x, y_pin)], TIN_HIEU[c], width=1.8)
            chu(p, f"net_{pha}{c}", X_NET + 6, y_pin - 16, 70, 13, net_ngan(key), size=10.5, color=TIN_HIEU[c],
                bold=True)
            chu(p, f"loi_{pha}{c}", BAND_X, y_pin - 16, BAND_W, 13, str(LOI_CUA[key]), size=9.5, color=CAP,
                bold=True, align="center")
            for y in (y_pin, y1, y2):
                if lo < y < hi:
                    dot(p, f"dot_{pha}{c}_{y}", x, y, TIN_HIEU[c])
    for pha, keys in PHA.items():                    # vẽ sau trục để cung vượt nằm trên dây module
        m1, m2 = MOD_PHA[pha]
        for c in MAU:
            x = XBUS[pha][c]
            for m in (m1, m2):
                y = MOD_TOP[m] + ROW_OFF[c]
                duong(p, f"h_{m}{c}", [(x, y), (MX, y)], TIN_HIEU[c], width=1.8, jump=True)


def ve_gnd_ve(p: Page) -> None:
    y_top = MOD_TOP["H1"] + ROW_OFF["Y"]
    wire(p, "gnd_bus", [(X_GND_BUS, y_top), (X_GND_BUS, Y_GND_VE), (880, Y_GND_VE)], DAY, width=1.8)
    chu(p, "gnd_loi", BAND_X, Y_GND_VE - 16, BAND_W, 13, "7", size=9.5, color=CAP, bold=True, align="center")
    gnd(p, "gnd_ve_g", 880, Y_GND_VE)
    chu(p, "gnd_ve_t", 620, Y_GND_VE - 8, 250, 16, "về GND chung (thanh GND breadboard)", size=10, color=INK2,
        align="right")


def ve_nguon(p: Page) -> None:
    y5, yn = row_y(NODEMCU_TRAI.index("5V")), row_y(NODEMCU_TRAI.index("5V")) + 36
    hop(p, "adapter", 56, y5 - 40, 110, 92,
        '<b style="font-size:12px">Adapter</b><br>5 V / 4 A<br><span style="color:#5B6470">cắm ổ 220 V</span>',
        fill=NGUON_NEN, stroke=NGUON, sw=1.5, r=6, size=10.5)
    wire(p, "ad_p", [(166, y5), (196, y5)], NGUON, width=2.2)
    wire(p, "ad_n", [(166, yn), (196, yn)])
    hop(p, "x1", 196, y5 - 24, 40, 76, fill="#FFFFFF", stroke=NGUON, sw=1.5)
    chu(p, "x1_p", 198, y5 - 9, 18, 16, "+", size=12, bold=True, align="center")
    chu(p, "x1_n", 198, yn - 9, 18, 16, "−", size=12, bold=True, align="center")
    chu(p, "x1_ten", 160, y5 + 58, 112, 30, "<b>X1</b> jack DC<br>5.5 × 2.1 mm", size=10, align="center")
    wire(p, "x1_f1", [(236, y5), (262, y5)], NGUON, width=2.2)
    sym_ngang(p, "f1", "miscellaneous.fuse_2", 262, y5, 48, 16)
    chu(p, "f1_ten", 240, y5 - 46, 92, 30, "<b>F1</b> PTC<br>0,5–1 A", size=10, align="center")
    wire(p, "f1_d1", [(310, y5), (336, y5)], NGUON, width=2.2)
    sym_ngang(p, "d1", "diodes.schottky_diode", 336, y5, 40, 24)
    chu(p, "d1_ten", 318, y5 - 46, 76, 30, "<b>D1</b><br>1N5819", size=10, align="center")
    wire(p, "d1_u1", [(376, y5), (UX - STUB, y5)], NGUON, width=2.2)
    dot(p, "x2", 410, y5, NGUON)
    chu(p, "x2_ten", 418, y5 + 6, 70, 16, "<b>X2</b> domino", size=10)
    chu(p, "net_5v", 432, y5 - 18, 44, 14, "+5V", size=10.5, color=NGUON, bold=True)
    wire(p, "nhanh_j2", [(410, y5), (410, 846)], NGUON, width=2.2, end="block")
    the(p, "nhanh_j2_t", 410, 864, "P3 → nút J2 (5 V, GND)", NGUON)
    wire(p, "x1_gnd", [(236, yn), (280, yn)])
    gnd(p, "x1_g", 280, yn)
    yg = row_y(13)
    wire(p, "u1_gnd", [(UX - STUB, yg), (450, yg)])
    gnd(p, "u1_g", 450, yg)


def ve_safe_stop(p: Page) -> None:
    y4, x = y_gpio(CHAN["SAFE_STOP"]), 900
    wire(p, "s1_a", [(X_NET, y4), (x, y4), (x, 643)], "#C92A2A", width=1.8)
    chu(p, "net_s1", X_NET + 6, y4 - 16, 86, 13, "SAFE_STOP", size=10.5, color="#C92A2A", bold=True)
    nut_nhan_doc(p, "s1", x, 646, 700)
    wire(p, "s1_b", [(x, 703), (x, 716)])
    gnd(p, "s1_g", x, 716)
    chu(p, "s1_ten", 818, 640, 74, 62, "<b>S1</b><br>safe-stop<br>tự giữ,<br>thường mở", size=10, align="right")


def ve_bang_tin_hieu(p: Page) -> None:
    chu(p, "bth_td", 50, 62, 400, 16, '<span style="letter-spacing:0.08em">BẢNG TÍN HIỆU</span>', size=10.5,
        bold=True, color=INK2)
    rows = [["NET", "GPIO", "CHÂN U1", "LÕI W1", "KÊNH X3", "TỚI"]]
    mau = {}
    for i, key in enumerate(PHA["NS"] + PHA["EW"]):
        g = CHAN[key]
        rows.append([net_ngan(key), str(g), str(so_chan(g)), str(LOI_CUA[key]), f"CH{i}",
                     f"{'H1 + H2' if key[:2] == 'NS' else 'H3 + H4'} · {key[3]}"])
        mau[(i + 1, 0)] = TIN_HIEU[key[3]]
    g4 = CHAN["SAFE_STOP"]
    rows += [["SAFE_STOP", str(g4), str(so_chan(g4)), "—", "CH6", "S1 → GND"],
             ["GND", "—", "14, 32, 38", "7", "GND", "thanh GND, H1–H4"]]
    mau[(7, 0)] = "#C92A2A"
    bang(p, "bth", 50, 86, [74, 42, 62, 50, 60, 112], rows, row_h=23, mau=mau,
         dam={(r, 0) for r in range(1, 9)})


GHI_CHU = [
    "Bắc và Nam cùng pha nên mắc <b>song song</b> trên IO23/22/21; Đông và Tây trên IO19/18/5. "
    "Điểm rẽ nhánh nằm ở đầu cần đèn (A.4).",
    "Module đèn có sẵn điện trở hạn dòng. Dòng ước tính ~6 mA mỗi LED ở 3,3 V, tức ~12 mA mỗi chân GPIO.",
    "S1 dùng điện trở kéo lên nội (INPUT_PULLUP). Nhấn = LOW = dừng an toàn: vàng nhấp nháy, từ chối lệnh.",
    "IO2 là LED trạng thái có sẵn trên board.",
    "Nạp firmware qua micro-USB (CH340): rút nguồn 5 V ngoài trước khi cắm cáp.",
    "Mọi ký hiệu GND là GND chung của nút J1 và J2. Pi 5 dùng nguồn riêng, không chung GND (A.3).",
    "X3 (tùy chọn): header để kẹp logic analyzer song song lên các net trong bảng.",
]


def page() -> Page:
    p = Page("A.2 Nguyên lý nút chấp hành", W, H)
    khung_to(p)
    chu(p, "vung_bb", UX - 60, 62, 470, 16,
        '<span style="letter-spacing:0.08em">PHÍA BREADBOARD</span> · dải mạch trước sa bàn', size=10.5,
        bold=True, color=INK2)
    hop(p, "vung_tru", 996, 96, 554, 794, fill="#FAFBFC", stroke=RULE, sw=1.2, r=8, dashed=True)
    chu(p, "vung_tru_t", 1006, 62, 540, 16,
        '<span style="letter-spacing:0.08em">PHÍA TRỤ J1</span> · cụm đèn 4 mặt ở đầu cần (A.4)', size=10.5,
        bold=True, color=INK2)
    ve_bang_tin_hieu(p)
    ghi_chu(p, "gc", 50, 320, 400, GHI_CHU)
    ve_bang_cap(p)
    ve_u1(p)
    for m in MOD_TOP:
        ve_module(p, m)
    ve_day_den(p)
    ve_gnd_ve(p)
    ve_nguon(p)
    ve_safe_stop(p)
    chu_giai(p, "cg", 50, 912, 850, [
        ("line", NGUON, "+5V"), ("line", INK, "GND, dây trong module"),
        ("line", TIN_HIEU["R"], "Tín hiệu đèn (màu theo đèn)"), ("line", MO, "Chân không dùng"),
        ("band", CAP, "Cáp W1 lên trụ, số = lõi"), ("dot", INK, "Chấm tròn: điểm nối"),
        ("jump", INK, "Cung vượt: không nối")], cols=3)
    khung_ten(p, 2, "Sơ đồ nguyên lý nút chấp hành J1 (nút J2 giống hệt)",
              "Chân GPIO bám firmware esp32_signal_controller.ino")
    return p
