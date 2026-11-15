"""Tờ A.1: sơ đồ bố trí và đấu nối tổng thể.

Trái: mặt bằng sa bàn vẽ theo tỷ lệ từ bo_tri.py (2 ngã tư, 2 trụ, tủ Pi, dải mạch phía trước) cùng đường đi
của mọi cáp, mỗi cáp một mã. Khối ngoài sa bàn (router, máy chủ, nguồn) không theo tỷ lệ.
Phải: bảng cáp và liên kết, danh mục tờ, ghi chú, ký hiệu.
"""
from __future__ import annotations

import bo_tri as L
from ban_ve_mach_chung import (AN_TOAN, CAP, CSI, CSI_NEN, DIEU_PHOI, DIEU_PHOI_NEN, INK, INK2, INK3, MANG,
                               MANG_NEN, NGUON, NGUON_NEN, RULE, W, H, bang, chu, chu_giai, dot,
                               duong, ghi_chu, hop, khung_ten, khung_to, nhan, the)
from drawio_lib import Page

S = 0.66                            # px / mm trên mặt bằng
X0, Y0 = 540, 519                   # tâm tấm A0 trên trang
APRON_Y = -L.BOARD_H / 2 - L.BASE_FRONT / 2 - 2      # tâm dải mạch phía trước (như dung_canh.py)
SLOT_Y = -L.BOARD_H / 2 - 9                          # khe luồn cáp W ở mép trước tấm A0
BB_W, BB_H = 165.0, 109.2                            # 2 breadboard 830 lỗ ghép dọc
HB_W, HB_H = L.BOARD_W / 2, L.BOARD_H / 2


def P(x: float, y: float) -> tuple[float, float]:
    """mm (gốc tâm tấm A0, y hướng Bắc) → px trên trang."""
    return X0 + x * S, Y0 - y * S


def R(p: Page, cid: str, x0: float, y0: float, x1: float, y1: float, value: str = "", **kw) -> str:
    """Hình chữ nhật theo tọa độ mm."""
    (a, b), (c, d) = P(x0, y1), P(x1, y0)
    return hop(p, cid, a, b, c - a, d - b, value, **kw)


def D(p: Page, cid: str, pts_mm: list[tuple[float, float]], color: str, **kw) -> str:
    return duong(p, cid, [P(x, y) for x, y in pts_mm], color, **kw)


def ve_nen(p: Page) -> None:
    R(p, "de", -HB_W - L.BASE_MARGIN_X, -HB_H - L.BASE_FRONT, HB_W + L.BASE_MARGIN_X, HB_H + L.BASE_BACK,
      fill="#F1F3F5", stroke=INK3, sw=1.2, r=4)
    R(p, "a0", -HB_W, -HB_H, HB_W, HB_H, fill="#EAF3E4", stroke=INK2, sw=1.3)
    rw = L.ROAD_W / 2
    R(p, "duong_ew", -HB_W, -rw, HB_W, rw, fill="#DEE2E6", stroke="none", sw=0)
    for n, (jx, _) in L.JUNCTIONS.items():
        R(p, f"duong_ns_{n}", jx - rw, -HB_H, jx + rw, HB_H, fill="#DEE2E6", stroke="none", sw=0)
    # mép đường và vạch tim, bỏ qua lòng ngã tư
    xs = sorted(jx for jx, _ in L.JUNCTIONS.values())
    cuts = [-HB_W] + [v for jx in xs for v in (jx - rw, jx + rw)] + [HB_W]
    for i in range(0, len(cuts), 2):
        a, b = cuts[i], cuts[i + 1]
        for s in (-1, 1):
            D(p, f"mep_ew_{i}_{s}", [(a, s * rw), (b, s * rw)], "#CED4DA", width=1)
        D(p, f"tim_ew_{i}", [(a + 30, 0), (b - 30, 0)], INK3, width=1, dashed=True, dash="8 6")
    for n, (jx, _) in L.JUNCTIONS.items():
        for s in (-1, 1):
            for k in (-1, 1):
                D(p, f"mep_ns_{n}_{s}_{k}", [(jx + k * rw, s * rw), (jx + k * rw, s * HB_H)], "#CED4DA", width=1)
            D(p, f"tim_ns_{n}_{s}", [(jx, s * (rw + 30)), (jx, s * HB_H)], INK3, width=1, dashed=True, dash="8 6")
        x, y = P(jx + (1 if jx > 0 else -1) * 205, -150)
        hop(p, f"nhan_{n}", x - 44, y - 12, 88, 24, f"NGÃ TƯ {n}", fill="#FFFFFF", stroke=INK2, sw=1, r=5,
            size=10.5, color=INK2, bold=True)
    chu(p, "a0_t", *P(-HB_W + 8, HB_H - 6), 220, 16, "Tấm A0 · 1189 × 841 mm", size=10, color=INK2)
    chu(p, "de_t", *P(-HB_W - 38, -HB_H - 6), 260, 16, "Dải mạch phía trước · 200 mm", size=10, color=INK2)


def ve_tru(p: Page, n: str) -> None:
    jx, jy = L.JUNCTIONS[n]
    tx, ty = L.pole_xy(n)
    D(p, f"can_{n}", [(tx, ty), (jx, jy)], "#868E96", width=4)
    x, y = P(tx, ty)
    hop(p, f"tru_{n}", x - 7, y - 7, 14, 14, fill=INK, stroke=INK, sw=1)
    cx, cy = P(jx, jy)
    hop(p, f"cum_{n}", cx - 9, cy - 9, 18, 18, fill="#343A40", stroke=INK, sw=1, r=2)
    hop(p, f"cam_{n}", cx - 5, cy - 5, 10, 10, fill=CSI, stroke="#FFFFFF", sw=1)
    out = -1 if jx < 0 else 1                      # nhãn ở ô cỏ phía ngoài, ngay góc Bắc của ngã tư
    w = 170
    lx, ly = P(jx + out * (L.ROAD_W / 2 + 8), 150)
    ax = lx - w if out < 0 else lx
    chu(p, f"tru_{n}_t", ax, ly - 26, w, 52,
        f"<b>Trụ {n}</b><br>camera + cụm đèn 4 mặt<br>"
        f'<span style="color:{INK2}">treo ở tâm ngã tư (A.4)</span>', size=10.5,
        align="right" if out < 0 else "left")
    ex, ey = P(jx + out * (L.ROAD_W / 2 + 4), 70)
    duong(p, f"tru_{n}_lead", [(ex, ey), (cx + out * 10, cy - 10)], INK2, width=1, end="oval", size=4)


def ve_tu_pi(p: Page) -> None:
    px, py = L.PI_XY
    R(p, "pi", px - 39, py - 53, px + 39, py + 53, '<b>Pi 5</b>', fill=CSI_NEN, stroke=CSI, sw=1.6, r=3, size=11,
      color=CSI)
    x, y = P(px - 39, py + 53)
    chu(p, "pi_t", x - 170, y - 66, 180, 48, "<b>Tủ ven đường</b><br>Raspberry Pi 5<br>"
        f'<span style="color:{INK2}">2 cổng CSI (A.3)</span>', size=10.5, align="right")
    the(p, "pi_wifi", *P(px + 92, py + 20), "Wi-Fi", MANG)


def ve_cap_csi(p: Page) -> None:
    for i, n in enumerate(L.JUNCTIONS, start=1):
        route = L.csi_route(n)
        pts = []
        for x, y, _z in route:
            if not pts or (abs(pts[-1][0] - x) > 0.5 or abs(pts[-1][1] - y) > 0.5):
                pts.append((x, y))
        D(p, f"c{i}", pts, CSI, width=2.4)
        mx, my = (pts[1][0] + pts[2][0]) / 2, (pts[1][1] + pts[2][1]) / 2
        the(p, f"c{i}_tag", *P(mx, my + 2), f"C{i}", CSI)


def ve_cap_w(p: Page) -> None:
    for i, n in enumerate(L.JUNCTIONS, start=1):
        jx, jy = L.JUNCTIONS[n]
        tx, ty = L.pole_xy(n)
        s = 1 if tx > jx else -1
        k = 12 / 2 ** 0.5                          # lệch sang mặt dưới cần, tránh cáp CSI
        D(p, f"w{i}_can", [(jx + s * k, jy - k), (tx + s * k, ty - k)], CAP, width=2.4)
        xs = jx + s * 30
        D(p, f"w{i}_ngam", [(tx, ty), (tx, -400), (xs, -400), (xs, SLOT_Y)], CAP, width=2.4, dashed=True,
          dash="7 4")
        D(p, f"w{i}_noi", [(xs, SLOT_Y), (xs, APRON_Y + BB_H / 2)], CAP, width=2.4)
        R(p, f"khe_{n}", jx - 43, SLOT_Y - 3.5, jx + 43, SLOT_Y + 3.5, fill="#495057", stroke="none", sw=0)
        the(p, f"w{i}_tag", *P((tx + xs) / 2, -400), f"W{i}", CAP)


def ve_dai_mach(p: Page) -> None:
    for i, (n, (jx, _)) in enumerate(L.JUNCTIONS.items(), start=1):
        R(p, f"bb_{n}", jx - BB_W / 2, APRON_Y - BB_H / 2, jx + BB_W / 2, APRON_Y + BB_H / 2, fill="#FFFFFF",
          stroke=INK3, sw=1.2, r=2)
        D(p, f"bb_{n}_khe", [(jx - BB_W / 2, APRON_Y), (jx + BB_W / 2, APRON_Y)], RULE, width=1)
        R(p, f"esp_{n}", jx - 32.5, APRON_Y - 13, jx + 16.5, APRON_Y + 13, fill="#2C3A4B", stroke=INK, sw=1, r=1)
        x, y = P(jx + 128, APRON_Y)
        dot(p, f"s1_{n}", x, y, AN_TOAN, r=7, fill="#FA5252", sw=1.4)
        chu(p, f"s1_{n}_t", x + 10, y - 8, 24, 14, "S1", size=9.5, color=AN_TOAN, bold=True)
        bx, by = P(jx, APRON_Y - BB_H / 2)
        chu(p, f"bb_{n}_t", bx - 110, by + 4, 220, 30,
            f"<b>ESP32 {n}</b> trên 2 breadboard (A.2)", size=10.5, align="center")
        the(p, f"wifi_{n}", *P(jx - 128, APRON_Y + 30), "Wi-Fi", MANG)
    R(p, "nguon", -40, APRON_Y - 30, 34, APRON_Y - 10, fill=NGUON_NEN, stroke=NGUON, sw=1.4, r=2)
    x, y = P(-3, APRON_Y - 10)
    chu(p, "nguon_t", x - 90, y - 40, 180, 30, "<b>Nguồn 5 V</b><br>X1 · F1 · D1 · X2 (A.2)", size=10,
        align="center")
    for i, (n, (jx, _)) in enumerate(L.JUNCTIONS.items(), start=2):
        s = 1 if jx > 0 else -1
        y = APRON_Y - 20
        D(p, f"p{i}", [(s * 37, y), (jx - s * BB_W / 2, y)], NGUON, width=2.2)
        the(p, f"p{i}_tag", *P((s * 37 + jx - s * BB_W / 2) / 2, y - 18), f"P{i}", NGUON)


def ve_ngoai_sa_ban(p: Page) -> None:
    """Khối ngoài sa bàn: không theo tỷ lệ."""
    hop(p, "r1", 120, 96, 200, 62, "<b>R1</b> · Router Wi-Fi 2.4 GHz<br>"
        f'<span style="font-size:10px;color:{INK2}">LAN riêng, không cần Internet</span>', fill=MANG_NEN,
        stroke=MANG, sw=1.5, r=6, size=11)
    hop(p, "may_chu", 356, 96, 200, 62, "<b>Máy chủ điều phối</b><br>"
        f'<span style="font-size:10px;color:{INK2}">MQTT broker · Graph-Control</span>', fill=DIEU_PHOI_NEN,
        stroke=DIEU_PHOI, sw=1.5, r=6, size=11)
    duong(p, "l3", [(320, 127), (356, 127)], MANG, width=1.8, dashed=True, start="block", end="block", size=5)
    the(p, "l3_tag", 338, 176, "L3", MANG)
    hop(p, "psu_pi", 640, 96, 190, 62, "<b>Nguồn USB-C PD 27 W</b><br>"
        f'<span style="font-size:10px;color:{INK2}">5,1 V / 5 A · riêng cho Pi</span>', fill=NGUON_NEN,
        stroke=NGUON, sw=1.5, r=6, size=11)
    hop(p, "o_cam", 866, 104, 96, 46, "Ổ cắm<br>220 V", fill="#F1F3F5", stroke=INK2, sw=1.4, r=6, size=10.5)
    duong(p, "ac_psu", [(866, 127), (830, 127)], NGUON, width=2, end="block", size=5)
    px, py = L.PI_XY
    x_pi, y_pi = P(px + 30, py + 53)
    duong(p, "p4", [(735, 158), (735, 200), (x_pi, 200), (x_pi, y_pi)], NGUON, width=2.2, end="block", size=6)
    the(p, "p4_tag", 680, 200, "P4", NGUON)
    chu(p, "r1_ghi", 120, 162, 200, 30, "Pi 5, ESP32 J1/J2 và máy chủ cùng vào LAN của R1 (L1–L3)", size=9.5,
        color=INK2)
    # adapter 5 V phía trước
    hop(p, "adapter", 600, 952, 130, 46, "<b>Adapter 5 V / 4 A</b><br>"
        f'<span style="font-size:10px;color:{INK2}">cắm ổ 220 V</span>', fill=NGUON_NEN, stroke=NGUON, sw=1.5,
        r=6, size=10.5)
    xj, yj = P(-3, APRON_Y - 30)
    duong(p, "p1", [(600, 975), (xj, 975), (xj, yj)], NGUON, width=2.2, end="block", size=6)
    the(p, "p1_tag", 568, 975, "P1", NGUON)


def ve_huong_ty_le(p: Page) -> None:
    duong(p, "bac", [(76, 1052), (76, 1000)], INK, width=2, end="block", size=8)
    chu(p, "bac_t", 62, 978, 28, 18, "B", size=12, bold=True, align="center")
    x0, y0 = 120, 1040
    seg = 100 * S
    for i in range(2):
        hop(p, f"tl_{i}", x0 + i * seg, y0, seg, 7, fill=INK if i == 0 else "#FFFFFF", stroke=INK, sw=1)
    for i, t in enumerate(("0", "100", "200 mm")):
        chu(p, f"tl_t{i}", x0 + i * seg - 20, y0 + 10, 40 if i < 2 else 60, 14, t, size=9.5, color=INK2,
            align="center" if i < 2 else "left")
    chu(p, "tl_ghi", x0, y0 - 46, 420, 32, "Mặt bằng theo tỷ lệ (bố trí đề xuất, bo_tri.py)<br>"
        "Khối ngoài sa bàn không theo tỷ lệ", size=9.5, color=INK2)


BANG_CAP = [
    ["MÃ", "LOẠI", "TỪ", "ĐẾN", "DÀI", "TỜ"],
    ["C1", "FPC 22→15 chân", "Pi 5 · CAM/DISP 0", "Camera trụ J1", "1 m", "A.3"],
    ["C2", "FPC 22→15 chân", "Pi 5 · CAM/DISP 1", "Camera trụ J2", "1 m", "A.3"],
    ["W1", "CAT5e 8 lõi", "Breadboard J1", "Cụm đèn trụ J1", "~1,2 m", "A.4"],
    ["W2", "CAT5e 8 lõi", "Breadboard J2", "Cụm đèn trụ J2", "~1,2 m", "A.4"],
    ["P1", "Dây DC", "Adapter 5 V", "X1 jack DC", "kèm adapter", "A.2"],
    ["P2", "Dây đôi 5 V, GND", "X2 domino", "Thanh nguồn J1", "~0,25 m", "A.2"],
    ["P3", "Dây đôi 5 V, GND", "X2 domino", "Thanh nguồn J2", "~0,25 m", "A.2"],
    ["P4", "USB-C", "Nguồn 27 W", "Pi 5 · USB-C", "kèm nguồn", "A.3"],
    ["L1", "Wi-Fi 2.4 GHz", "Pi 5", "R1 router", "—", "A.3"],
    ["L2", "Wi-Fi 2.4 GHz", "ESP32 J1, J2", "R1 router", "—", "A.2"],
    ["L3", "Wi-Fi / LAN", "Máy chủ điều phối", "R1 router", "—", "—"],
]
MAU_MA = {"C": CSI, "W": CAP, "P": NGUON, "L": MANG}

GHI_CHU = [
    "Hai miền nguồn tách riêng: Pi 5 dùng nguồn USB-C 27 W (P4); hai ESP32 và 8 module đèn dùng chung adapter "
    "5 V (P1–P3).",
    "Pi và ESP32 <b>không nối dây nào</b>, kể cả GND. Hai bên chỉ trao đổi qua Wi-Fi / MQTT trong LAN riêng của R1.",
    "Nét đứt: cáp W1, W2 đi dưới mặt sa bàn, chui lên qua lỗ ở chân trụ.",
    "Vị trí, kích thước và độ dài cáp là phương án đề xuất, chưa phải số đo trên sa bàn thật.",
    "Đọc 2 camera trên 1 Pi: phần cứng có sẵn 2 cổng CSI, phần mềm đang phát triển.",
]


def ve_cot_phai(p: Page) -> None:
    x, w = 1060, 490
    nhan(p, "n2", x, 50, w, "2", "BẢNG CÁP VÀ LIÊN KẾT")
    mau = {(r, 0): MAU_MA[row[0][0]] for r, row in enumerate(BANG_CAP) if r}
    y = bang(p, "cap", x, 94, [40, 104, 112, 106, 74, 54], BANG_CAP, row_h=23, size=10, mau=mau,
             dam={(r, 0) for r in range(1, len(BANG_CAP))})
    nhan(p, "n3", x, y + 22, w, "3", "DANH MỤC TỜ")
    y = bang(p, "to", x, y + 66, [54, 436], [
        ["TỜ", "NỘI DUNG"],
        ["<b>A.1</b>", "Sơ đồ bố trí và đấu nối tổng thể (tờ này)"],
        ["<b>A.2</b>", "Sơ đồ nguyên lý nút chấp hành J1 (nút J2 giống hệt)"],
        ["<b>A.3</b>", "Sơ đồ đấu nối khối AI biên: Raspberry Pi 5 + 2 camera"],
        ["<b>A.4</b>", "Sơ đồ đi dây từ breadboard lên trụ J1 (trụ J2 đối xứng)"],
    ], row_h=23, size=10.5)
    y = ghi_chu(p, "gc", x, y + 22, w, GHI_CHU, size=10.5)
    chu_giai(p, "cg", x, y + 8, w, [
        ("thick", CSI, "Cáp FPC camera (C1, C2)"), ("thick", CAP, "Cáp CAT5e lên trụ (W1, W2)"),
        ("dash", CAP, "Đoạn đi dưới mặt sa bàn"), ("thick", NGUON, "Dây nguồn (P1–P4)"),
        ("dash", MANG, "Liên kết Wi-Fi / LAN"), ("thick", "#868E96", "Cần nhôm của trụ")], cols=2)


def page() -> Page:
    p = Page("A.1 Tổng thể", W, H)
    khung_to(p)
    nhan(p, "n1", 50, 50, 960, "1", "MẶT BẰNG SA BÀN", "nhìn từ trên · mã cáp tra ở bảng 2")
    ve_nen(p)
    ve_dai_mach(p)
    ve_cap_w(p)
    ve_cap_csi(p)
    for n in L.JUNCTIONS:
        ve_tru(p, n)
    ve_tu_pi(p)
    ve_ngoai_sa_ban(p)
    ve_huong_ty_le(p)
    ve_cot_phai(p)
    khung_ten(p, 1, "Sơ đồ bố trí và đấu nối tổng thể hệ thống phần cứng",
              "Bố trí theo bo_tri.py (đề xuất); chân, cổng theo A.2–A.4", ty_le="mặt bằng: theo thước")
    return p
