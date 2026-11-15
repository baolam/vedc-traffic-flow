"""Hình học sa bàn in: 1 tấm bạt 1200 × 600 mm (cuộn lại được), hai ngã tư J1 (trái) và J2 (phải). Đơn vị mm.

Từ 18/10 (chiều): đội in một tấm bạt liền thay cho 2 tấm fomex 600 × 600 + 2 khay. Bạt trải lên mặt bàn cứng,
không có khay, không khoan lỗ; trụ đứng trên đế MDF riêng, thiết bị đặt thẳng lên bạt (dán băng keo hai mặt).

Tọa độ cục bộ của mỗi ngã tư: gốc ở tâm ngã tư, x hướng Đông, y hướng Bắc. Mép trước (phía khán giả) là phía Nam.
J1 là nửa trái, J2 là nửa phải; hai nửa gặp nhau ở x = 0 của tọa độ bạt.
Vị trí được khai báo theo trục u = x × INWARD[nút], u dương là hướng về giữa bạt, nên J2 là ảnh gương của J1.

Mặt đường, vạch và trụ lấy từ bo_tri.py (cùng số đo với bản A0 cũ ở bo_tri_a0.py), nên trụ, cụm đèn và firmware
không đổi; chỉ khổ bạt và chỗ đặt mạch là đổi.
"""
from __future__ import annotations

import math
import sys
from dataclasses import dataclass
from pathlib import Path

VEDC = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(VEDC / "thiet_ke_bao_cao" / "4.4_hinh_minh_hoa" / "blender"))
import bo_tri as L  # noqa: E402

# ------------------------------------------------------------------ khổ bạt
TILE = 600.0                    # cạnh phần bạt của mỗi ngã tư
HALF = TILE / 2
SHEET_W, SHEET_H = 2 * TILE, TILE
BLEED = 20.0                    # tràn lề mỗi cạnh trong file in; tiệm gấp viền 20 mm, đội có thể bấm khoen góc
FOAM_T = L.BOARD_T              # độ dày bạt (mm), dùng cho cảnh Blender
MDF_DENSITY = 0.75e-3           # g/mm³

NODES = ("J1", "J2")
INWARD = {"J1": 1, "J2": -1}             # dấu x hướng về giữa bạt
WORLD_X = {"J1": -HALF, "J2": HALF}      # tâm ngã tư trên tấm bạt

# ------------------------------------------------------------------ mặt đường (giữ như bo_tri.py)
ROAD_HALF = L.ROAD_W / 2                 # 60
LANE_W = L.LANE_W
WALK = L.SIDEWALK_W                      # 16
EDGE = ROAD_HALF + WALK                  # 76: mép ngoài vỉa hè
CROSSWALK_D = L.CROSSWALK_D
STOP_DIST = L.stop_dist()                # 98: tâm ngã tư tới vạch dừng
ZONE = ROAD_HALF + CROSSWALK_D + 4       # 94: vùng ngã tư không vẽ vạch tim
DASH, GAP = 30.0, 20.0
CENTER_LINE_W, STOP_LINE_W, ZEBRA_W = 3.0, 4.0, 7.0

# ------------------------------------------------------------------ thiết bị (ngang x, dọc y, cao), mm


@dataclass(frozen=True)
class Device:
    name: str
    w: float
    d: float
    h: float
    source: str


BREADBOARD = Device("2 breadboard MB-102 830 lỗ ghép cạnh dài", 2 * 54.6, 165.1, 10.0,
                    "MB-102: 165,1 × 54,6 mm mỗi tấm; ESP32 bắc cầu qua khe giữa 2 tấm (A.4)")
ESP32 = Device("ESP32 NodeMCU-32S", 25.4, 51.4, 13.0, "Waveshare: 51,4 × 25,4 mm")
USB_PLUG = 35.0                          # đầu micro-USB + đoạn cáp uốn, nhô khỏi mép ESP32
PI_CASE = Device("Raspberry Pi 5 trong vỏ ABS có quạt", 95.0, 65.0, 32.0,
                 "board 85 × 56 mm (RP-008347-DS-1); vỏ ABS là ước tính, đo vỏ thật")
X1_JACK = Device("Jack DC 5,5 × 2,1 ra domino (X1)", 16.0, 32.0, 13.0, "ước tính, đo hàng thật")
POLE = Device("Trụ nhôm định hình 20 × 20", 20.0, 20.0, 200.0, "icdayroi: thanh 20 cm")
BRACKET = Device("Ke góc 20 × 20 (gang)", 17.0, 20.0, 20.0,
                 "thường gặp 20 × 20 × 17 mm; icdayroi không ghi, đặt ke thật để lấy dấu lỗ")
SIGNAL = Device("Mạch LED giao thông 5 V", 21.0, 11.0, 56.0, "icdayroi: 56 × 21 × 11 mm, LED 8 mm, 25 g")
CORE = 20.0                              # lõi cụm đèn: nhôm 20 × 20 dài 100 mm
TAPE_T = 1.0                             # băng keo 2 mặt
PAD_MARGIN = 6.0                         # ô in trên decal rộng hơn thiết bị mỗi bên

# ------------------------------------------------------------------ vị trí theo (u, y)
POLE_U, POLE_Y = L.POLE_OFF, L.POLE_OFF                  # 100, 100 như bo_tri.py
BOLT_FROM_FACE = 12.0                                    # tâm lỗ ke cách mặt trụ (lấy dấu theo ke thật)
PLATE = 200.0                                            # đế trụ MDF vuông, nằm trên ô cỏ sau-trong
PLATE_T = 6.0
PLATE_U0 = ROAD_HALF + 4.0                               # mép gần đường: lấn lên vỉa hè, không lên lòng đường
BB_U = (EDGE + HALF) / 2                                 # tâm ô cỏ trước-trong
BB_FRONT_GAP = 45.0                                      # mép trước breadboard tới mép tấm
BB_Y0 = -HALF + BB_FRONT_GAP
CABLE_U, CABLE_Y = HALF - 30.0, -100.0                   # chỗ cáp W (lên trụ) và dây P3 (sang nút kia) rời breadboard
# khối lượng ước tính (g) để kiểm chống lật của trụ trên đế
POLE_G, ARM_G, BRACKET_G = 86.0, 190.0, 35.0             # thanh 20 cm (~0,43 kg/m); cần + cụm đèn + cáp; mỗi ke
PI_U, PI_Y = -(EDGE + HALF) / 2, -(EDGE + HALF) / 2      # J2: ô cỏ trước-ngoài
LABEL_U, LABEL_Y = -(EDGE + 52.0), EDGE + 40.0           # nhãn J1/J2 ở ô cỏ sau-ngoài, như decal cũ
ARM_LEN = L.arm_len()                                    # 141: trục trụ tới tâm ngã tư
ARM_BAR = 200.0                                          # cần đèn là thanh 20 cm, phần thừa nằm sau trụ
CLUSTER_H = L.SIGNAL_H                                   # tâm cụm đèn 112 mm
ARM_H = L.SIGNAL_ARM_H                                   # tâm cần 160 mm


Rect = tuple[float, float, float, float]                 # u0, y0, u1, y1


def vn(v: float, nd: int | None = None) -> str:
    """Số kiểu Việt: dấu phẩy thập phân; nd=None thì bỏ số 0 thừa."""
    s = f"{v:.{nd}f}" if nd is not None else f"{v:g}"
    return s.replace(".", ",")


def bb_rect() -> Rect:
    return BB_U - BREADBOARD.w / 2, BB_Y0, BB_U + BREADBOARD.w / 2, BB_Y0 + BREADBOARD.d


def esp32_rect() -> Rect:
    """ESP32 nằm dọc ở đầu Nam breadboard, cổng USB quay ra mép trước."""
    return BB_U - ESP32.w / 2, BB_Y0 + 2.0, BB_U + ESP32.w / 2, BB_Y0 + 2.0 + ESP32.d


def x1_rect() -> Rect:
    """J1: jack X1 dán giữa vỉa hè và breadboard, miệng jack quay ra mép trước."""
    u1 = bb_rect()[0] - 2 * PAD_MARGIN - 2.0
    return u1 - X1_JACK.w, BB_Y0, u1, BB_Y0 + X1_JACK.d


def pi_rect() -> Rect:
    return PI_U - PI_CASE.w / 2, PI_Y - PI_CASE.d / 2, PI_U + PI_CASE.w / 2, PI_Y + PI_CASE.d / 2


def pole_rect() -> Rect:
    return POLE_U - POLE.w / 2, POLE_Y - POLE.d / 2, POLE_U + POLE.w / 2, POLE_Y + POLE.d / 2


def bracket_rects() -> list[Rect]:
    """2 ke chân trụ ở mặt Bắc và mặt hướng cạnh ghép: phía đối diện với cần đèn, chịu kéo khi trụ nghiêng."""
    pu0, py0, pu1, py1 = pole_rect()
    return [(POLE_U - BRACKET.w / 2, py1, POLE_U + BRACKET.w / 2, py1 + BRACKET.d),
            (pu1, POLE_Y - BRACKET.w / 2, pu1 + BRACKET.d, POLE_Y + BRACKET.w / 2)]


def bolt_points() -> list[tuple[float, float]]:
    _, _, pu1, py1 = pole_rect()
    return [(POLE_U, py1 + BOLT_FROM_FACE), (pu1 + BOLT_FROM_FACE, POLE_Y)]


def plate_rect() -> Rect:
    return PLATE_U0, PLATE_U0, PLATE_U0 + PLATE, PLATE_U0 + PLATE


def pads(node: str) -> list[tuple[str, Rect]]:
    """Ô in trên decal: thiết bị + PAD_MARGIN mỗi bên."""
    def grow(r: Rect) -> Rect:
        return r[0] - PAD_MARGIN, r[1] - PAD_MARGIN, r[2] + PAD_MARGIN, r[3] + PAD_MARGIN
    out = [(f"ESP32 · {node}", grow(bb_rect()))]
    if node == "J1":
        out.append(("X1", grow(x1_rect())))
    else:
        out.append(("AI BIÊN · PI 5", grow(pi_rect())))
    return out


def to_x(node: str, u: float) -> float:
    return u * INWARD[node]


def rect_x(node: str, r: Rect) -> Rect:
    u0, y0, u1, y1 = r
    a, b = to_x(node, u0), to_x(node, u1)
    return min(a, b), y0, max(a, b), y1


# ------------------------------------------------------------------ vạch tim


def ew_dashes_world() -> list[tuple[float, float]]:
    """Vạch tim đường Đông–Tây theo tọa độ khi ghép 2 tấm; đối xứng qua cạnh ghép x = 0 và cạnh ghép rơi vào khe."""
    out, x = [], -TILE + 10.0
    while x + DASH <= TILE - 10.0:
        if all(abs(x - jx) >= ZONE and abs(x + DASH - jx) >= ZONE and not (x < jx < x + DASH)
               for jx in WORLD_X.values()):
            out.append((x, x + DASH))
        x += DASH + GAP
    return out


def ns_dashes() -> list[tuple[float, float]]:
    out, y = [], -HALF + 10.0
    while y + DASH <= HALF - 10.0:
        if abs(y) >= ZONE and abs(y + DASH) >= ZONE and not (y < 0 < y + DASH):
            out.append((y, y + DASH))
        y += DASH + GAP
    return out


# ------------------------------------------------------------------ kiểm khớp


@dataclass(frozen=True)
class Check:
    item: str
    rule: str
    value: str
    ok: bool


def _inside(r: Rect, outer: Rect, margin: float) -> float:
    """Khoảng hở nhỏ nhất từ r tới mép trong của outer (âm là lấn ra ngoài)."""
    return min(r[0] - outer[0], r[1] - outer[1], outer[2] - r[2], outer[3] - r[3]) - margin


def _gap(a: Rect, b: Rect) -> float:
    dx = max(b[0] - a[2], a[0] - b[2], 0.0)
    dy = max(b[1] - a[3], a[1] - b[3], 0.0)
    if dx == 0 and dy == 0:
        return -1.0
    return math.hypot(dx, dy) if dx and dy else max(dx, dy)


def _circle_rect(u: float, y: float, d: float) -> Rect:
    return u - d / 2, y - d / 2, u + d / 2, y + d / 2


BLOCK_FRONT_IN: Rect = (EDGE, -HALF, HALF, -EDGE)       # ô cỏ trước-trong (u, y)
BLOCK_BACK_IN: Rect = (EDGE, EDGE, HALF, HALF)
BLOCK_FRONT_OUT: Rect = (-HALF, -HALF, -EDGE, -EDGE)


def cable_lengths() -> dict[str, float]:
    """Chiều dài cáp ước tính (mm). Cả hai cáp nằm trên mặt bạt (dán băng keo), đoạn dọc mặt bạt cộng 30 % độ chùng."""
    ground = math.dist((POLE_U, POLE_Y), (CABLE_U, CABLE_Y)) * 1.3
    core_top = ARM_H - CORE / 2                               # đáy cần, nơi lõi cụm đèn treo
    w = (core_top - (CLUSTER_H + SIGNAL.h / 2) + 20.0)        # từ đầu module lên cần
    w += ARM_LEN + ARM_H + PLATE_T + 20.0 + ground + 20.0 + 100.0
    p3 = 60.0 + 25.0 + 2 * (HALF - CABLE_U) * 1.3 + 25.0 + 100.0
    return {"W": w, "P3": p3}


def tip_ratio() -> float:
    """Mô men giữ / mô men lật của trụ trên đế, quanh góc đế gần ngã tư nhất (ước tính khối lượng).
    Cần đèn và cụm đèn kéo trọng tâm về phía tâm ngã tư theo đường chéo."""
    k = math.sqrt(2.0)
    pivot = PLATE_U0 * k                                     # khoảng từ gốc ngã tư tới góc đế, dọc đường chéo
    pole = POLE_U * k - pivot                                # trục trụ cách góc đế
    plate_c = (PLATE_U0 + PLATE / 2) * k - pivot             # tâm đế cách góc đế
    arm_c = POLE_U * k - ARM_LEN * 0.8 - pivot               # trọng tâm cần + cụm đèn (âm: vượt góc đế)
    plate_g = MDF_DENSITY * PLATE * PLATE * PLATE_T
    hold = POLE_G * pole + plate_g * plate_c + 2 * BRACKET_G * pole
    tip = ARM_G * max(-arm_c, 0.0)
    return hold / tip if tip else math.inf


def plate_weight_g() -> float:
    return MDF_DENSITY * PLATE * PLATE * PLATE_T


def checks() -> list[Check]:
    out: list[Check] = []

    def add(item: str, rule: str, value: float, need: float, unit: str = "mm") -> None:
        out.append(Check(item, rule, f"{vn(value, 1 if abs(value) < 10 else 0)} {unit}", value >= need))

    add("Breadboard + ESP32 (ô trước-trong)", "cách vỉa hè, mép bạt ≥ 10 mm",
        _inside(bb_rect(), BLOCK_FRONT_IN, 0), 10)
    add("Đầu cáp micro-USB của ESP32", f"nhô {USB_PLUG:.0f} mm, còn trong mép bạt",
        esp32_rect()[1] - (-HALF) - USB_PLUG, 0)
    add("Jack X1 (J1)", "không chạm vỉa hè, cách breadboard ≥ 10 mm",
        min(_inside(x1_rect(), BLOCK_FRONT_IN, 0), _gap(x1_rect(), bb_rect())), 10)
    add("Pi 5 trong vỏ (J2, ô trước-ngoài)", "cách vỉa hè, mép bạt ≥ 10 mm", _inside(pi_rect(), BLOCK_FRONT_OUT, 0), 10)
    pr = plate_rect()
    add("Đế trụ MDF 200 × 200", "không lấn lòng đường, còn trong mép bạt, cách ≥ 2 mm",
        min(pr[0] - ROAD_HALF, pr[1] - ROAD_HALF, HALF - pr[2], HALF - pr[3]), 2)
    foot = [pole_rect(), *bracket_rects()]
    add("Chân trụ + 2 ke trên đế", "cách mép đế ≥ 10 mm", min(_inside(r, pr, 0) for r in foot), 10)
    add("Cáp W rời breadboard", "cách ô breadboard ≥ 10 mm, còn trong mép bạt",
        min(_gap(_circle_rect(CABLE_U, CABLE_Y, 12.0), pads("J1")[0][1]), HALF - CABLE_U - 6.0), 10)
    arm_tail = (ARM_BAR - ARM_LEN) / math.sqrt(2)
    add("Đuôi cần đèn thừa sau trụ", f"thanh {ARM_BAR:.0f} mm, dài {ARM_LEN:.0f} mm tới tâm; còn trong bạt",
        HALF - (POLE_U + arm_tail), 0)
    cluster = CORE + 2 * (TAPE_T + SIGNAL.d)
    add("Cụm đèn 4 mặt treo giữa ngã tư", f"rộng {cluster:.0f} mm ≤ lòng ngã tư {L.ROAD_W:.0f} mm",
        L.ROAD_W - cluster, 0)
    add("4 module 21 mm quanh lõi 20 mm", "dán băng keo 1 mm thì không chạm góc",
        (CORE / 2 + TAPE_T) - SIGNAL.w / 2, 0)
    core_bottom = ARM_H - CORE / 2 - 100.0
    add("Đáy lõi cụm đèn (thanh 10 cm)", "cao hơn mặt đường", core_bottom, 20)
    ratio = tip_ratio()
    out.append(Check("Trụ chống lật trên đế (ước tính khối lượng)",
                     f"mô men giữ ≥ 1,5 × mô men lật; đế MDF 6 ly nặng ~{plate_weight_g():.0f} g",
                     f"{vn(ratio, 1)} lần", ratio >= 1.5))
    cab = cable_lengths()
    add("Cáp W1/W2 (cắt 1,0 m mỗi sợi)", f"ước tính {cab['W']:.0f} mm, 2 sợi ≤ 3 m đã mua", 1000 - cab["W"], 50)
    add("Dây P3 J1 → J2 (lõi CAT5e còn dư)", f"ước tính {cab['P3']:.0f} mm", 3000 - 2000 - cab["P3"], 0)
    return out


if __name__ == "__main__":
    for c in checks():
        print(("ĐẠT " if c.ok else "LỖI ") + f"{c.item}: {c.rule} → {c.value}")
    print("dashes EW:", ew_dashes_world())
    print("cáp:", {k: round(v) for k, v in cable_lengths().items()}, "đế MDF ~", round(plate_weight_g()), "g",
          "tỉ số chống lật", round(tip_ratio(), 2))
