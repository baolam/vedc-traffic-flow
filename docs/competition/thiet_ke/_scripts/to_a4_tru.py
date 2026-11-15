"""Tờ A.4: sơ đồ đi dây từ breadboard lên trụ J1 (trụ J2 đối xứng).

① breadboard nhìn từ trên (giản lược: bước lỗ 10 px, ESP32 anten quay trái để hàng chân tín hiệu nằm phía
cáp W1 đi lên), ② mặt đứng trụ theo tỷ lệ 1,5 px/mm với số đo từ bo_tri.py, ③ cụm đèn nhìn từ trên,
④ bảng lõi W1, ⑤ chi tiết rẽ nhánh ở đầu cần đèn.
"""
from __future__ import annotations

import bo_tri as L
from ban_ve_mach_chung import (AN_TOAN, CAP, CHAN, CSI, INK, INK2, INK3, LED_FILL, LOI, MAU, NGUON, NODEMCU_PHAI,
                               NUT, NUT_NEN, TIN_HIEU, W, H, bang, chu, chu_giai, dot, duong,
                               ghi_chu, hop, khung_ten, khung_to, nhan, the)
from drawio_lib import Page

# ---------------------------------------------------------------- ① breadboard
OX, OY = 76, 214                    # góc trên trái tấm A
PT = 10                             # bước lỗ (giản lược)
BW, BHT = 480, 188                  # một tấm breadboard
RAIL = {"tren": (12, 22), "duoi": (166, 176)}      # (+, −) theo cao độ trong tấm
HANG = {c: 42 + i * PT for i, c in enumerate("abcde")} | {c: 106 + i * PT for i, c in enumerate("fghij")}
CL = 14                             # cột của chân 38 (hàng trên) và chân 1 (hàng dưới), anten quay trái
Y_CHAN_TREN = OY + HANG["h"]        # hàng chân 20–38 cắm ở hàng h tấm A
Y_CHAN_DUOI = OY + BHT + HANG["a"]  # hàng chân 1–19 cắm ở hàng a tấm B
Y_F = OY + HANG["f"]
ALU, ALU_VIEN = "#DEE2E6", "#868E96"


def cx(cot: int) -> float:
    return OX + 15 + (cot - 1) * PT


def cot_tren(chan: int) -> int:
    """Hàng trên: chân 38 ở cột CL (đầu anten, bên trái) … chân 20 ở cột CL + 18."""
    return CL + 38 - chan


def cot_duoi(chan: int) -> int:
    return CL + chan - 1


def chan_gpio(gpio: int) -> int:
    return 38 - NODEMCU_PHAI.index(f"IO{gpio}")


def ve_tam(p: Page, cid: str, y0: float) -> None:
    hop(p, cid, OX, y0, BW, BHT, fill="#FAFAF8", stroke="#CED4DA", sw=1.4, r=4)
    hop(p, f"{cid}_ranh", OX + 4, y0 + 88, BW - 8, 12, fill="#ECEEF0", stroke="none", sw=0)
    for k, (yp, yn) in RAIL.items():
        duong(p, f"{cid}_{k}_do", [(OX + 10, y0 + yp - 6), (OX + BW - 10, y0 + yp - 6)], "#F03E3E", width=1)
        duong(p, f"{cid}_{k}_xanh", [(OX + 10, y0 + yn + 6), (OX + BW - 10, y0 + yn + 6)], "#1C7ED6", width=1)
        for i, y in enumerate((yp, yn)):
            duong(p, f"{cid}_{k}_lo{i}", [(OX + 25, y0 + y), (OX + BW - 25, y0 + y)], "#ADB5BD", width=2.4,
                  dashed=True, dash="1 3.17")
    for c, y in HANG.items():
        duong(p, f"{cid}_h{c}", [(cx(1), y0 + y), (cx(46) + 1, y0 + y)], "#ADB5BD", width=2.4, dashed=True,
              dash="1 3.17")


def loi_day(p: Page, cid: str, pts: list[tuple[float, float]], mau: str, soc: bool, width: float = 2.6) -> None:
    """Lõi cáp màu T568B; lõi có sọc trắng vẽ thêm nét đứt trắng chồng lên."""
    duong(p, cid, pts, mau, width=width)
    if soc:
        duong(p, f"{cid}_soc", pts, "#FFFFFF", width=width * 0.5, dashed=True, dash="2 2")


def ve_esp32(p: Page) -> None:
    x0, x1 = cx(CL) - 38, cx(CL + 18) + 22
    y0, y1 = Y_CHAN_TREN - 8, Y_CHAN_DUOI + 8
    hop(p, "esp", x0, y0, x1 - x0, y1 - y0, fill="#22303F", stroke=INK, sw=1.4, r=4)
    hop(p, "esp_mod", x0 + 14, y0 + 20, 92, y1 - y0 - 40, '<span style="letter-spacing:0.04em">ESP-WROOM-32</span>',
        fill="#CED4DA", stroke="#ADB5BD", sw=1, r=2, size=8, color=INK2)
    duong(p, "esp_anten", [(x0 + 7, y0 + 24), (x0 + 11, y0 + 24), (x0 + 11, y0 + 40), (x0 + 5, y0 + 40),
                           (x0 + 5, y0 + 56), (x0 + 11, y0 + 56), (x0 + 11, y0 + 72), (x0 + 5, y0 + 72),
                           (x0 + 5, y0 + 88), (x0 + 11, y0 + 88)], "#E9C46A", width=1.6)
    hop(p, "esp_usb", x1 - 6, (y0 + y1) / 2 - 13, 16, 26, fill="#ADB5BD", stroke=INK2, sw=1)
    chu(p, "esp_t", x0 + 112, (y0 + y1) / 2 - 18, x1 - x0 - 124, 36,
        '<b>U1</b> NodeMCU-32S<br><span style="font-size:8.5px">anten quay trái</span>', size=10,
        color="#FFFFFF", align="center")
    for so in range(1, 39):
        x = cx(cot_tren(so)) if so >= 20 else cx(cot_duoi(so))
        y = Y_CHAN_TREN if so >= 20 else Y_CHAN_DUOI
        hop(p, f"esp_pin{so}", x - 2.5, y - 2.5, 5, 5, fill="#E9C46A", stroke="#B08900", sw=0.6)
    dung_tren = {chan_gpio(g): f"IO{g}" for g in CHAN.values() if g != CHAN["STATUS_LED"]} | {38: "GND", 32: "GND"}
    for so, ten in dung_tren.items():
        chu(p, f"esp_ten{so}", cx(cot_tren(so)) - 14, Y_CHAN_TREN + 6, 28, 9, ten, size=7, color="#FFFFFF",
            align="center", rot=-90)
    for so, ten in ((14, "GND"), (19, "5V")):
        chu(p, f"esp_tenb{so}", cx(cot_duoi(so)) - 14, Y_CHAN_DUOI - 16, 28, 9, ten, size=7, color="#FFFFFF",
            align="center", rot=-90)


def ve_breadboard(p: Page) -> None:
    nhan(p, "n1", 50, 50, 560, "1", "BREADBOARD NÚT J1", "nhìn từ trên, giản lược")
    ve_tam(p, "bbA", OY)
    ve_tam(p, "bbB", OY + BHT)
    chu(p, "bbA_t", OX + BW - 120, OY + 92, 116, 10, "tấm A", size=8.5, color=INK2, align="right")
    chu(p, "bbB_t", OX + BW - 120, OY + BHT + 92, 116, 10, "tấm B", size=8.5, color=INK2, align="right")
    ve_esp32(p)
    # W1 từ phía Bắc (khe luồn ở mép trước sa bàn) xuống, các lõi cắm thẳng vào hàng f cùng cột với chân GPIO
    jx = cx(cot_tren(33)) + 4
    hop(p, "w1_vo", jx - 12, 96, 24, 50, fill="#E5DBFF", stroke=CAP, sw=1.6, r=4)
    chu(p, "bb_w1_t", jx - 222, 100, 204, 30, "<b>W1</b> · CAT5e lên trụ J1<br>"
        f'<span style="color:{INK2}">lên khe luồn rồi tới trụ (②)</span>', size=10, color=CAP,
        align="right")
    y_ra = OY + RAIL["tren"][1]
    dich_loi = {1: -9, 2: -6, 3: -3, 7: 0, 4: 3, 5: 6, 6: 9}
    for loi, _ten, (mau, soc), net, key, _mod in LOI[:7]:
        if key:
            lx, ly = cx(cot_tren(chan_gpio(CHAN[key]))), Y_F
        else:
            lx, ly = cx(cot_tren(32)) + PT, y_ra
        ox = jx + dich_loi[loi]
        loi_day(p, f"bb_loi{loi}", [(ox, 146), (ox, 156), (lx, 186), (lx, ly)], mau, soc)
        dot(p, f"bb_loi{loi}_dau", lx, ly, mau, r=3)
    # GND: chân 38 lên thanh − tấm A; thanh − tấm A nối thanh − tấm B ở mép trái
    xg = cx(cot_tren(38))
    duong(p, "bb_gnd38", [(xg, Y_F), (xg, y_ra)], INK, width=2.2)
    yb_p, yb_n = OY + BHT + RAIL["duoi"][0], OY + BHT + RAIL["duoi"][1]
    duong(p, "bb_gnd_ab", [(OX + 14, y_ra), (OX - 12, y_ra), (OX - 12, yb_n), (OX + 14, yb_n)], INK, width=2.2)
    # nguồn từ X2 domino vào thanh dưới tấm B; ESP32 lấy 5 V và GND từ đó
    duong(p, "bb_p2_p", [(OX - 30, yb_p), (OX + 14, yb_p)], NGUON, width=2.4)
    duong(p, "bb_p2_n", [(OX - 30, yb_n + 14), (OX - 20, yb_n + 14), (OX - 20, yb_n)], INK, width=2.4)
    chu(p, "bb_p2_t", OX - 26, yb_n + 18, 330, 16, "← P2 từ X2 domino: +5V, GND (A.2)", size=10, color=NGUON)
    y_b = OY + BHT + HANG["c"]
    for so, (mau, y_rail) in ((19, (NGUON, yb_p)), (14, (INK, yb_n))):
        x = cx(cot_duoi(so))
        duong(p, f"bb_esp{so}", [(x, y_b), (x, y_rail)], mau, width=2.2)
        dot(p, f"bb_esp{so}_d", x, y_b, mau, r=3)
    # S1 safe-stop: IO4 → thanh − tấm A
    x4, xn = cx(cot_tren(chan_gpio(CHAN["SAFE_STOP"]))), cx(cot_tren(chan_gpio(CHAN["SAFE_STOP"])) + 2)
    dot(p, "s1", (x4 + xn) / 2, 120, AN_TOAN, r=13, fill="#FA5252", sw=1.6)
    dot(p, "s1_nap", (x4 + xn) / 2, 120, "#C92A2A", r=7, fill="#FF8787", sw=1)
    duong(p, "s1_a", [(x4, 132), (x4, Y_F)], AN_TOAN, width=2)
    duong(p, "s1_b", [(xn, 132), (xn, y_ra)], INK, width=2)
    dot(p, "s1_a_d", x4, Y_F, AN_TOAN, r=3)
    chu(p, "s1_t", (x4 + xn) / 2 + 18, 106, 150, 30, "<b>S1</b> safe-stop<br>IO4 → GND", size=10, color=AN_TOAN)


# ---------------------------------------------------------------- ② mặt đứng trụ
SZ = 1.5                            # px / mm
Y0 = 812                            # mặt sa bàn
XP = 812                            # trục trụ
XE = XP + L.arm_len() * SZ          # đầu cần, trên tâm ngã tư


def z(mm: float) -> float:
    return Y0 - mm * SZ


def ve_tru(p: Page) -> None:
    nhan(p, "n2", 640, 50, 420, "2", "MẶT ĐỨNG TRỤ J1", "theo tỷ lệ, mm")
    # mặt sa bàn và hộp đế (cắt)
    hop(p, "a0", 650, Y0, 400, 5 * SZ, fill="#CED4DA", stroke=INK2, sw=1)
    hop(p, "de", 650, Y0 + 5 * SZ, 400, L.BASE_H * SZ, fill="#F8F9FA", stroke=INK3, sw=1, dashed=True)
    chu(p, "a0_t", 850, Y0 + 12, 120, 14, "mặt sa bàn · z = 0", size=9.5, color=INK2)
    chu(p, "de_t", 900, Y0 + 62, 146, 14, "hộp đế (cắt)", size=9.5, color=INK2, align="right")
    top = L.ARM_Z + 12
    reach = L.arm_len() * SZ
    hop(p, "tru", XP - 15, z(top), 30, top * SZ, fill=ALU, stroke=ALU_VIEN, sw=1.4)
    hop(p, "can_tren", XP - 15, z(L.ARM_Z) - 15, reach + 36, 30, fill=ALU, stroke=ALU_VIEN, sw=1.4)
    hop(p, "can_tren_nap", XE + 18, z(L.ARM_Z) - 15, 3, 30, fill=INK, stroke=INK, sw=1)
    duong(p, "giang", [(XP + 15, z(L.ARM_Z - 78)), (XP + 72, z(L.ARM_Z - 15))], ALU_VIEN, width=3.2)
    hop(p, "kep_den", XP - 19, z(L.SIGNAL_ARM_H) - 12, 38, 24, fill="#ADB5BD", stroke=ALU_VIEN, sw=1.2, r=3)
    hop(p, "can_den", XP + 19, z(L.SIGNAL_ARM_H) - 7.5, reach - 4, 15, fill=ALU, stroke=ALU_VIEN, sw=1.2, r=7)
    # camera dưới đầu cần trên
    hop(p, "cam_de", XE - 12, z(L.ARM_Z) + 15, 24, 18, fill=INK, stroke=INK, sw=1, r=2)
    hop(p, "cam_pcb", XE - 19, z(L.CAMERA_H + 9), 38, 7, fill="#2B8A3E", stroke=NUT, sw=1)
    hop(p, "cam_kinh", XE - 9, z(L.CAMERA_H + 2), 18, 3 * SZ, fill="#343A40", stroke=INK, sw=1, r=2)
    for s in (-1, 1):
        duong(p, f"fov{s}", [(XE, z(L.CAMERA_H)), (XE + s * 36, z(L.CAMERA_H) + 45)], INK3, width=1, dashed=True)
    chu(p, "cam_t", XE - 168, z(L.CAMERA_H) + 22, 150, 30, "Camera Module 3 Wide<br>nhìn thẳng xuống",
        size=10, color=CSI, align="right")
    # cụm đèn treo dưới đầu cần đèn
    yc = z(L.SIGNAL_H)
    duong(p, "thanh_treo", [(XE, z(L.SIGNAL_ARM_H) + 7), (XE, z(L.SIGNAL_H + 34))], ALU_VIEN, width=3)
    hop(p, "cum", XE - 21, z(L.SIGNAL_H + 34), 42, 68 * SZ, fill="#343A40", stroke=INK, sw=1.2, r=4)
    for i, c in enumerate(MAU):
        dot(p, f"cum_{c}", XE, yc - 30 + i * 30, "#212529", r=10, fill=LED_FILL[c], sw=1)
    chu(p, "cum_t", XE - 170, yc - 15, 140, 30, "cụm đèn 4 mặt H1–H4<br>(xem ③)", size=10, align="right")
    # đường tâm ngã tư (gạch chấm)
    duong(p, "tam", [(XE, Y0 + 8), (XE, z(L.ARM_Z) - 30)], INK3, width=1, dashed=True, dash="12 3 2 3")
    chu(p, "tam_t", XE - 40, Y0 + 10, 80, 14, "tâm ngã tư", size=9.5, color=INK2, align="center")
    ve_cap_tru(p, reach)
    ve_kich_thuoc(p, reach)
    dai = L.polyline_len(L.csi_route("J1")) / 1000
    chu(p, "tru_ghi", 650, Y0 + 92, 400, 44,
        f"C1: FPC 22 → 15 chân từ Pi 5, dài 1 m (đường đi ~{dai:.2f} m). W1: CAT5e ~1,2 m tới breadboard ①. "
        "Trụ, cần: nhôm định hình 20 × 20. Số đo lấy từ bo_tri.py (đề xuất).".replace("~0.", "~0,"),
        size=9.5, color=INK2)


def ve_cap_tru(p: Page, reach: float) -> None:
    # W1: cụm đèn → dọc mặt dưới cần đèn → mặt phải trụ → lỗ chân trụ → trong hộp đế → breadboard
    xw = XP + 19
    y_duoi_can = z(L.SIGNAL_ARM_H) + 11
    duong(p, "w1", [(XE - 6, z(L.SIGNAL_H + 34)), (XE - 6, y_duoi_can), (xw, y_duoi_can), (xw, Y0)], CAP,
          width=3)
    duong(p, "w1_ngam", [(xw, Y0), (xw, Y0 + 40), (650, Y0 + 40)], CAP, width=3, dashed=True, dash="4 2")
    the(p, "tru_w1_t", 672, Y0 + 40, "W1 → ①", CAP)
    # FPC camera: từ Pi dọc mặt sa bàn → mặt trái trụ → lưng cần trên → camera
    xf = XP - 19
    y_lung = z(L.ARM_Z) - 19
    duong(p, "c1", [(650, Y0 - 3), (xf, Y0 - 3), (xf, y_lung), (XE + 4, y_lung), (XE + 4, z(L.CAMERA_H + 9))],
          "#74C0FC", width=6, opacity=90)
    duong(p, "c1_tim", [(650, Y0 - 3), (xf, Y0 - 3), (xf, y_lung), (XE + 4, y_lung), (XE + 4, z(L.CAMERA_H + 9))],
          CSI, width=1)
    the(p, "c1_t", 670, Y0 - 3, "C1", CSI)


def ve_kich_thuoc(p: Page, reach: float) -> None:
    muc = [(L.SIGNAL_H, "112", "tâm cụm đèn", XE - 21), (L.SIGNAL_ARM_H, "160", "cần đèn", XP - 19),
           (L.CAMERA_H, "400", "ống kính", XE - 19), (L.ARM_Z, "432", "tâm cần camera", XP - 15)]
    for i, (mm, so, ten, x_vat) in enumerate(muc):
        xd = 774 - i * 26
        y = z(mm)
        duong(p, f"kt{i}_dong", [(x_vat - 2, y), (xd - 6, y)], INK3, width=0.8)
        duong(p, f"kt{i}", [(xd, Y0), (xd, y)], INK, width=1, start="block", end="block", size=5)
        rong = 5.2 * len(f"{so} · {ten}") + 8
        hop(p, f"kt{i}_t", xd - rong / 2, (Y0 + y) / 2 - 8, rong, 16, f"<b>{so}</b> · {ten}", fill="#FFFFFF",
            stroke="none", sw=0, size=9.5, pad=0, extra={"rotation": -90})
    duong(p, "kt_dong0", [(XP - 15, Y0), (xd - 6, Y0)], INK3, width=0.8)
    yr = z(L.ARM_Z) - 48
    duong(p, "kt_vuon", [(XP, yr), (XE, yr)], INK, width=1, start="block", end="block", size=5)
    duong(p, "kt_vuon_d1", [(XP, z(top_tru())), (XP, yr - 6)], INK3, width=0.8)
    duong(p, "kt_vuon_d2", [(XE, z(L.ARM_Z) - 30), (XE, yr - 6)], INK3, width=0.8)
    chu(p, "kt_vuon_t", XP, yr - 20, XE - XP, 16, f"<b>{L.arm_len():.0f}</b> cần vươn (ngang)", size=10,
        align="center")


def top_tru() -> float:
    return L.ARM_Z + 12


# ---------------------------------------------------------------- ③ cụm đèn nhìn từ trên
def ve_cum_den(p: Page) -> None:
    nhan(p, "n3", 1090, 50, 460, "3", "CỤM ĐÈN 4 MẶT", "nhìn từ trên")
    cx0, cy0 = 1250, 210
    hop(p, "cum_tam", cx0 - 24, cy0 - 24, 48, 48, fill="#343A40", stroke=INK, sw=1.2, r=4)
    mat = {"H1": (cx0 - 30, cy0 - 46, 60, 18, "Bắc"), "H2": (cx0 - 30, cy0 + 28, 60, 18, "Nam"),
           "H3": (cx0 + 28, cy0 - 30, 18, 60, "Đông"), "H4": (cx0 - 46, cy0 - 30, 18, 60, "Tây")}
    for m, (x, y, w, h, ten) in mat.items():
        hop(p, f"mat_{m}", x, y, w, h, fill="#212529", stroke=INK, sw=1, r=3)
        for i, c in enumerate(MAU):
            px, py = (x + 12 + i * 18, y + h / 2) if w > h else (x + w / 2, y + 12 + i * 18)
            dot(p, f"mat_{m}_{c}", px, py, "#000000", r=4.5, fill=LED_FILL[c], sw=0.6)
    nhan_mat = {"H1": (cx0 - 50, cy0 - 74, 100, "center"), "H2": (cx0 - 50, cy0 + 52, 100, "center"),
                "H3": (cx0 + 52, cy0 - 8, 70, "left"), "H4": (cx0 - 122, cy0 - 8, 70, "right")}
    for m, (x, y, w, al) in nhan_mat.items():
        chu(p, f"mat_{m}_t", x, y, w, 16, f"<b>{m}</b> {mat[m][4]}", size=10.5, align=al)
    # xe tới: mũi tên chỉ vào mặt đèn mà xe nhìn thấy
    for i, (x1, y1, x2, y2) in enumerate(((cx0, cy0 - 124, cx0, cy0 - 96), (cx0, cy0 + 122, cx0, cy0 + 94),
                                          (cx0 + 140, cy0 + 22, cx0 + 112, cy0 + 22),
                                          (cx0 - 140, cy0 - 22, cx0 - 112, cy0 - 22))):
        duong(p, f"xe{i}", [(x1, y1), (x2, y2)], INK2, width=1.6, dashed=True, end="block", size=6)
    duong(p, "bac", [(1112, 158), (1112, 112)], INK, width=1.8, end="block", size=7)
    chu(p, "bac_t", 1098, 162, 28, 14, "B", size=11, bold=True, align="center")
    chu(p, "cum_mo_ta", 1404, 104, 146, 200,
        "Mỗi mặt quay về phía xe tới (mũi tên đứt): xe từ phía Bắc nhìn mặt H1, các hướng khác tương tự."
        "<br><br><b>H1 song song H2</b> (pha Bắc–Nam)<br><b>H3 song song H4</b> (pha Đông–Tây)", size=10.5)


# ---------------------------------------------------------------- ④ bảng lõi W1
def ve_bang_loi(p: Page) -> float:
    nhan(p, "n4", 1090, 340, 460, "4", "LÕI CÁP W1", "CAT5e, màu T568B · đề xuất")
    rows = [["LÕI", "MÀU", "NET", "GPIO", "TỚI MODULE"]]
    for loi, ten, _mau, net, key, mod in LOI:
        gpio = str(CHAN[key]) if key else ("GND" if net == "GND" else "—")
        rows.append([str(loi), ten, net, gpio, mod])
    mau = {(r, 2): TIN_HIEU[row[2][-1]] for r, row in enumerate(rows) if r and row[2][:2] in ("NS", "EW")}
    x0, y0, rh = 1090, 384, 24
    y = bang(p, "loi", x0, y0, [40, 142, 60, 48, 170], rows, row_h=rh, size=10.5, mau=mau,
             dam={(r, 2) for r in range(1, 9)}, le={1: 46})
    for r, (loi, _ten, (m, soc), *_rest) in enumerate(LOI, start=1):
        yy = y0 + 24 + (r - 1) * rh + 6
        hop(p, f"loi_sw{r}", x0 + 48, yy, 30, 12, fill=m, stroke="#495057", sw=0.8)
        if soc:
            hop(p, f"loi_soc{r}", x0 + 48, yy + 4, 30, 4, fill="#FFFFFF", stroke="none", sw=0)
    return y


# ---------------------------------------------------------------- ⑤ rẽ nhánh ở đầu cần
def ve_re_nhanh(p: Page, y_top: float) -> None:
    nhan(p, "n5", 1090, y_top, 460, "5", "RẼ NHÁNH Ở ĐẦU CẦN ĐÈN", "đề xuất")
    chu(p, "re_mo_ta", 1090, y_top + 40, 460, 30,
        "Lõi tín hiệu 1–6: hàn ra 2 dây dupont cái, bọc co nhiệt, cắm vào 2 module đối diện. Lõi 7 (GND) rẽ ra "
        "cả 4 module.", size=10, color=INK2)

    def nhanh(cid: str, y: float, loi: int, dich: list[tuple[str, float]], mau_day: str) -> None:
        _l, ten, (m, soc), net, *_ = LOI[loi - 1]
        loi_day(p, f"{cid}_loi", [(1096, y), (1238, y)], m, soc, width=3.2)
        chu(p, f"{cid}_loi_t", 1096, y - 20, 150, 14, f"lõi {loi} · {net}", size=10, bold=True)
        hop(p, f"{cid}_han", 1238, y - 8, 40, 16, "co nhiệt", fill="#E7F5FF", stroke=INK2, sw=1, r=8, size=7.5,
            color=INK2, pad=1)
        for i, (ten_mod, yy) in enumerate(dich):
            duong(p, f"{cid}_d{i}", [(1278, y), (1300, y), (1300, yy), (1412, yy)], mau_day, width=1.8)
            hop(p, f"{cid}_m{i}", 1412, yy - 11, 128, 22, ten_mod, fill=NUT_NEN, stroke=NUT, sw=1.2, r=3,
                size=10, align="left")
        dot(p, f"{cid}_dot", 1300, y, mau_day, r=3.2)

    y1 = y_top + 104
    nhanh("re1", y1, 1, [("H1 Bắc · chân R", y1 - 16), ("H2 Nam · chân R", y1 + 16)], TIN_HIEU["R"])
    y7 = y1 + 100
    nhanh("re7", y7, 7, [(f"{m} · chân GND", y7 - 42 + i * 28) for i, m in enumerate(("H1 Bắc", "H2 Nam",
                                                                                       "H3 Đông", "H4 Tây"))], INK)


GHI_CHU = [
    "Lõi W1 (nên dùng loại lõi đặc) cắm thẳng vào hàng f, cùng cột với chân GPIO. Lõi 7 (GND) cắm vào thanh − "
    "trên cùng của tấm A.",
    "Chân GND (chân 38) nối lên thanh − tấm A; thanh − của 2 tấm nối với nhau bằng dây đen ở mép trái.",
    "ESP32 nhận 5 V và GND (chân 19, 14) từ thanh nguồn dưới tấm B. S1 nối IO4 xuống thanh − tấm A.",
    "Bước lỗ breadboard vẽ giản lược, không đúng tỷ lệ với ESP32.",
]


def page() -> Page:
    p = Page("A.4 Đi dây lên trụ", W, H)
    khung_to(p)
    ve_breadboard(p)
    y = ghi_chu(p, "gc", 50, 632, 560, GHI_CHU, size=10.5)
    chu_giai(p, "cg", 50, y + 10, 560, [
        ("thick", NGUON, "+5V"), ("thick", INK, "GND"), ("thick", CAP, "Cáp W1 (CAT5e)"),
        ("ribbon", CSI, "Cáp FPC camera C1"), ("dash", CAP, "W1 trong hộp đế (khuất)"),
        ("dash", INK3, "Đường tâm, đường dóng")], cols=2)
    ve_tru(p)
    ve_cum_den(p)
    y = ve_bang_loi(p)
    ve_re_nhanh(p, y + 22)
    khung_ten(p, 4, "Sơ đồ đi dây từ breadboard lên trụ J1 (trụ J2 đối xứng)",
              "Màu lõi cáp, cách rẽ nhánh và kích thước trụ là đề xuất", ty_le="② theo tỷ lệ")
    return p
