"""Tờ A.3: sơ đồ đấu nối khối AI biên (Raspberry Pi 5 + 2 camera).

Board Pi 5 vẽ theo tỷ lệ, vị trí cổng lấy từ bản vẽ cơ khí chính thức RP-008347-DS-1 (85 × 56 mm, gốc ở góc trên
trái, GPIO ở mép trên). Nhãn CAM/DISP đọc từ ảnh sản phẩm chính thức: đầu nối gần HDMI là CAM/DISP 1, đầu nối
gần Ethernet là CAM/DISP 0. Cổng không dùng vẽ màu xám.
"""
from __future__ import annotations

import bo_tri as L
from ban_ve_mach_chung import (CSI, CSI_NEN, DIEU_PHOI, DIEU_PHOI_NEN, INK, INK2, INK3, MANG, MANG_NEN, NGUON,
                               NGUON_NEN, NUT, NUT_NEN, W, H, bang, chu, chu_giai, dot, duong, ghi_chu, hop,
                               khung_ten, khung_to, nhan, the)
from drawio_lib import Page

K = 6.4                             # px / mm của board
BX, BY = 560, 300                   # góc trên trái board trên trang
XAM = dict(fill="#E9ECEF", stroke=INK3, sw=1.2, color=INK2)
RIBBON = "#74C0FC"
CAM_W, CAM_H = 110, 106             # Camera Module 3 (25 × 24 mm) ở 4,4 px/mm
CAMS = {"J1": 1225, "J2": 1395}     # x trái của 2 camera
CAM_Y = 560


def B(x: float, y: float) -> tuple[float, float]:
    return BX + x * K, BY + y * K


def BR(p: Page, cid: str, x: float, y: float, w: float, h: float, value: str = "", **kw) -> str:
    """Hình chữ nhật trên board, tọa độ mm."""
    return hop(p, cid, BX + x * K, BY + y * K, w * K, h * K, value, **kw)


def lo_bat_vit(p: Page, cid: str, x: float, y: float) -> None:
    cx, cy = B(x, y)
    dot(p, f"{cid}_vanh", cx, cy, "#C9B458", r=3 * K, fill="#F4E9B8", sw=1)
    dot(p, f"{cid}_lo", cx, cy, INK2, r=1.35 * K, fill="#FFFFFF", sw=1)


def ve_board(p: Page) -> None:
    BR(p, "pcb", 0, 0, 85, 56, fill="#E3F1E5", stroke=NUT, sw=1.8, r=3 * K)
    for i, (x, y) in enumerate(((3.5, 3.5), (61.5, 3.5), (3.5, 52.5), (61.5, 52.5))):
        lo_bat_vit(p, f"lo{i}", x, y)
    # GPIO 40 chân (không dùng)
    BR(p, "gpio", 7.1, 1.0, 50.8, 5.1, fill="#495057", stroke=INK, sw=1)
    for i, y in enumerate((2.27, 4.81)):
        duong(p, f"gpio_pin{i}", [B(8.0, y), B(57.3, y)], "#E9C46A", width=3.2, dashed=True, dash="1 4.08")
    chu(p, "gpio_t", *B(7.1, 6.6), 51 * K, 14, "GPIO 40 chân · không dùng", size=9, color=INK2, align="center")
    # linh kiện chính (chỉ để nhận diện)
    BR(p, "ram", 25.2, 11.8, 15.1, 10.2, "RAM 4 GB", fill="#495057", stroke=INK, sw=1, size=8.5, color="#FFFFFF")
    BR(p, "soc", 24.3, 24.5, 17.4, 17.4, "<b>BCM2712</b><br>4× A76", fill="#DEE2E6", stroke=INK2, sw=1.2, r=4,
       size=9, color=INK)
    BR(p, "rp1", 52.3, 14.6, 12.1, 12.0, "RP1", fill="#495057", stroke=INK, sw=1, size=8.5, color="#FFFFFF")
    BR(p, "wifi", 7.2, 6.9, 10.4, 13.0, "Wi-Fi", fill=MANG_NEN, stroke=MANG, sw=1.4, size=8.5, color=MANG,
       bold=True)
    # cổng không dùng
    BR(p, "usb2", 70.6, 1.4, 18.1, 14.3, "USB 2.0", **XAM, size=8.5)
    BR(p, "usb3", 70.6, 19.2, 18.1, 15.1, "USB 3.0", **XAM, size=8.5)
    BR(p, "eth", 66.7, 37.7, 21.5, 16.2, "Ethernet", **XAM, size=8.5)
    BR(p, "hdmi0", 22.0, 48.8, 7.6, 8.6, "HDMI0", **XAM, size=7.5)
    BR(p, "hdmi1", 35.4, 48.8, 7.6, 8.6, "HDMI1", **XAM, size=7.5)
    BR(p, "uart", 30.4, 50.5, 4.4, 3.5, **XAM)
    BR(p, "poe", 58.6, 44.0, 5.5, 5.3, fill="#495057", stroke=INK, sw=1)
    BR(p, "pcie", 1.2, 20.4, 4.6, 10.4, "PCIe", **XAM, size=7.5)
    BR(p, "nut_nguon", 0, 34.7, 2.5, 4.9, fill="#ADB5BD", stroke=INK2, sw=1)
    # cổng dùng
    BR(p, "usbc", 6.5, 49.5, 8.6, 7.2, "USB-C", fill=NGUON_NEN, stroke=NGUON, sw=1.6, size=8, color=NGUON,
       bold=True)
    BR(p, "fan", 64.8, 0.8, 3.4, 4.6, fill="#FFFFFF", stroke=INK, sw=1.4)
    chu(p, "fan_t", *B(64.0, 5.8), 40, 12, "FAN", size=8.5, color=INK, bold=True)
    for so, x in ((1, 47.2), (0, 53.0)):
        BR(p, f"cam{so}", x, 39.4, 3.0, 16.0, fill=CSI_NEN, stroke=CSI, sw=1.6)
        tx, ty = B(x - 3.0, 39.4)
        chu(p, f"cam{so}_t", tx - 40 + 1.5 * K, ty + 8 * K - 8, 80, 16, f"CAM/DISP {so}", size=9, color=CSI,
            bold=True, align="center", rot=-90)
    BR(p, "sd", -3.5, 21.5, 3.7, 10.5, fill="none", stroke=INK2, sw=1.2, dashed=True)
    sx, sy = B(-3.5, 26.75)
    duong(p, "sd_lead", [(sx, sy), (sx - 8, sy)], INK2, width=1, start="oval", size=4)
    chu(p, "sd_t", sx - 82, sy - 22, 72, 44, "microSD<br>64 GB<br>(mặt dưới)", size=9.5, color=INK2, align="right")


def ve_tu_va_quat(p: Page) -> None:
    hop(p, "tu", 452, 180, 718, 560, fill="none", stroke=INK2, sw=1.4, r=10, dashed=True)
    chu(p, "tu_t", 466, 188, 300, 16, '<span style="letter-spacing:0.08em">TỦ VEN ĐƯỜNG</span> · vỏ ABS',
        size=10.5, bold=True, color=INK2)
    hop(p, "quat", 870, 200, 220, 54, "<b>Tản nhiệt + quạt 5 V</b><br>"
        f'<span style="font-size:9.5px;color:{INK2}">cổng FAN hoặc chân 5V/GND, tùy loại</span>',
        fill="#F1F3F5", stroke=INK2, sw=1.4, r=6, size=10.5)
    fx, fy = B(66.5, 0.8)
    duong(p, "quat_day", [(fx, 254), (fx, fy)], INK, width=1.8)


def ve_camera(p: Page, n: str) -> tuple[float, float]:
    """Camera Module 3 Wide nhìn từ mặt có ống kính; trả về tâm đầu nối FPC (mép dưới)."""
    x, y = CAMS[n], CAM_Y
    hop(p, f"cam_{n}_pcb", x, y, CAM_W, CAM_H, fill="#E3F1E5", stroke=NUT, sw=1.6, r=6)
    for i, (dx, dy) in enumerate(((10, 10), (CAM_W - 10, 10), (10, CAM_H - 22), (CAM_W - 10, CAM_H - 22))):
        dot(p, f"cam_{n}_lo{i}", x + dx, y + dy, INK3, r=4, fill="#FFFFFF", sw=1)
    cx, cy = x + CAM_W / 2, y + 44
    dot(p, f"cam_{n}_vo", cx, cy, INK, r=27, fill="#343A40", sw=1)
    dot(p, f"cam_{n}_kinh", cx, cy, "#1C2A3A", r=16, fill="#22384F", sw=1)
    dot(p, f"cam_{n}_bong", cx - 6, cy - 6, "#FFFFFF", r=3.5, fill="#9FC3E6", sw=0)
    hop(p, f"cam_{n}_fpc", cx - 35, y + CAM_H - 14, 70, 14, fill=CSI_NEN, stroke=CSI, sw=1.4)
    chu(p, f"cam_{n}_t", x - 20, y - 40, CAM_W + 40, 34,
        f"<b>Camera trụ {n}</b><br>" f'<span style="color:{INK2}">nhìn thẳng xuống (A.4)</span>',
        size=10.5, align="center")
    return cx, y + CAM_H


def ve_cap_camera(p: Page) -> None:
    dai = L.polyline_len(L.csi_route("J1")) / 1000
    chu(p, "cam_chung", 1210, 470, 330, 34, "<b>2 × Camera Module 3 Wide</b> (SC0874)<br>"
        f'<span style="color:{INK2}">IMX708 · 12 MP · 120° chéo · cáp vào mép dưới</span>', size=10.5,
        align="center")
    tuyen = {"J1": (0, 53.0, 770), "J2": (1, 47.2, 800)}     # (cổng, x đầu nối mm, cao độ đi ngang)
    for n, (so, xmm, yy) in tuyen.items():
        ex, ey = ve_camera(p, n)
        sx, sy = B(xmm + 1.5, 55.4)
        duong(p, f"c_{n}", [(sx, sy), (sx, yy), (ex, yy), (ex, ey)], RIBBON, width=9, opacity=90)
        duong(p, f"c_{n}_tim", [(sx, sy), (sx, yy), (ex, yy), (ex, ey)], CSI, width=1)
        ma = "C1" if n == "J1" else "C2"
        the(p, f"c_{n}_tag", (sx + ex) / 2 + (40 if n == "J1" else 110), yy,
            f"{ma} · CAM/DISP {so} → {n}", CSI)
    chu(p, "c_dau22", 812, 676, 52, 14, "22 chân", size=9, color=CSI, align="right")
    chu(p, "c_dau15", 1290, 676, 60, 14, "15 chân", size=9, color=CSI)
    chu(p, "c_dai", 950, 812, 300, 30, f"FPC 22 → 15 chân, dài 1 m (đường đi ~{dai:.2f} m)".replace(".", ","),
        size=10, color=CSI)


def ve_mang(p: Page) -> None:
    hop(p, "esp", 80, 230, 270, 62, "<b>ESP32 J1, J2</b><br>"
        f'<span style="font-size:10px;color:{INK2}">nút chấp hành (A.2)</span>', fill=NUT_NEN, stroke=NUT,
        sw=1.5, r=6, size=11)
    hop(p, "r1", 80, 350, 270, 62, "<b>R1</b> · Router Wi-Fi 2.4 GHz<br>"
        f'<span style="font-size:10px;color:{INK2}">LAN riêng</span>', fill=MANG_NEN, stroke=MANG, sw=1.5, r=6,
        size=11)
    hop(p, "may_chu", 80, 470, 270, 62, "<b>Máy chủ điều phối</b><br>"
        f'<span style="font-size:10px;color:{INK2}">MQTT broker · Graph-Control</span>', fill=DIEU_PHOI_NEN,
        stroke=DIEU_PHOI, sw=1.5, r=6, size=11)
    nx = 215
    for cid, (y1, y2), ma in (("l2", (292, 350), "L2"), ("l3", (412, 470), "L3")):
        duong(p, cid, [(nx, y1), (nx, y2)], MANG, width=1.8, dashed=True, start="block", end="block", size=5)
        the(p, f"{cid}_tag", nx + 30, (y1 + y2) / 2, ma, MANG)
    wx, wy = B(7.2, 13.4)
    duong(p, "l1", [(350, 381), (wx - 40, 381), (wx - 40, wy), (wx, wy)], MANG, width=1.8, dashed=True,
          start="block", end="block", size=5)
    the(p, "l1_tag", 420, 381, "L1 · Wi-Fi 2.4 GHz", MANG)


def ve_nguon(p: Page) -> None:
    hop(p, "o_cam", 80, 760, 104, 50, "Ổ cắm<br>220 V", fill="#F1F3F5", stroke=INK2, sw=1.4, r=6, size=10.5)
    hop(p, "psu", 214, 752, 210, 66, "<b>Nguồn USB-C PD 27 W</b><br>"
        f'<span style="font-size:10px;color:{INK2}">5,1 V / 5 A · riêng cho Pi</span>', fill=NGUON_NEN,
        stroke=NGUON, sw=1.5, r=6, size=11)
    duong(p, "ac", [(184, 785), (214, 785)], NGUON, width=2, end="block", size=5)
    ux, uy = B(10.8, 56.7)
    duong(p, "p4", [(424, 785), (ux, 785), (ux, uy)], NGUON, width=2.4, end="block", size=6)
    the(p, "p4_tag", 500, 785, "P4 · USB-C", NGUON)


THONG_SO = [
    ["MỤC", "GIÁ TRỊ"],
    ["SoC", "BCM2712 · 4× Cortex-A76 · 2,4 GHz"],
    ["RAM", "4 GB"],
    ["Hệ điều hành", "Raspberry Pi OS Trixie"],
    ["Mô hình", "YOLO11n (ONNX, OpenCV DNN)"],
    ["Camera", "vision J1 ← CAM/DISP 0<br>vision J2 ← CAM/DISP 1"],
    ["Nguồn", "USB-C PD 5,1 V / 5 A (27 W)"],
    ["Mạng", "Wi-Fi 2.4 GHz onboard → R1"],
]

GHI_CHU = [
    "Hai miền nguồn tách riêng: Pi 5 dùng nguồn USB-C 27 W (P4); ESP32 và module đèn dùng adapter 5 V (A.2).",
    "Pi và ESP32 <b>không nối dây</b>, kể cả GND. Hai bên chỉ trao đổi qua Wi-Fi / MQTT (L1, L2).",
    "Cáp kèm camera là loại 15–15 chân, không cắm được vào Pi 5. Cần cáp FPC 22 → 15 chân (C1, C2).",
    "Không dùng khi vận hành: GPIO, USB, Ethernet, micro-HDMI, PCIe (vẽ màu xám).",
    "Đọc 2 camera trên 1 Pi: phần cứng có sẵn 2 cổng CSI, phần mềm <b>đang phát triển</b>.",
]


def page() -> Page:
    p = Page("A.3 Đấu nối khối AI biên", W, H)
    khung_to(p)
    nhan(p, "n1", 50, 50, 1120, "1", "RASPBERRY PI 5 VÀ HAI CAMERA",
         "board vẽ theo tỷ lệ, vị trí cổng theo bản vẽ cơ khí RP-008347-DS-1")
    ve_tu_va_quat(p)
    ve_board(p)
    ve_mang(p)
    ve_nguon(p)
    ve_cap_camera(p)
    nhan(p, "n2", 1210, 50, 340, "2", "THÔNG SỐ")
    bang(p, "ts", 1210, 96, [92, 248], THONG_SO, row_h=24, size=10.5, dam={(r, 0) for r in range(1, 8)})
    ghi_chu(p, "gc", 50, 856, 840, GHI_CHU, size=10.5)
    chu_giai(p, "cg", 930, 856, 620, [
        ("thick", NGUON, "Nguồn (P4)"), ("ribbon", CSI, "Cáp FPC camera (C1, C2)"),
        ("dash", MANG, "Liên kết Wi-Fi / LAN (L1–L3)"), ("line", INK, "Dây quạt"),
        ("box", f"{CSI_NEN},{CSI}", "Cổng đang dùng"), ("box", f"#E9ECEF,{INK3}", "Cổng không dùng")], cols=2)
    khung_ten(p, 3, "Sơ đồ đấu nối khối AI biên (Raspberry Pi 5 + 2 camera)",
              "Cổng theo bản vẽ cơ khí Raspberry Pi 5; linh kiện theo bảng 3.4", ty_le="board Pi theo tỷ lệ")
    return p
