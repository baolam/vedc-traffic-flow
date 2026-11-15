"""Kích thước và bố trí sa bàn EdgeFlow AI, đơn vị mm, gốc tọa độ ở tâm tấm A0.

Trục x: Tây → Đông (chiều dài tấm A0). Trục y: Nam → Bắc. Xe chạy bên phải.
Module này không phụ thuộc thư viện ngoài: cả Blender lẫn script PIL đều import được.

Đây là phương án bố trí ĐỀ XUẤT để minh họa, chưa phải số đo của sa bàn thật.
"""
from __future__ import annotations

import math

BOARD_W, BOARD_H = 1189.0, 841.0          # tấm A0, foam PVC 5 mm
BOARD_T = 5.0
ROAD_W = 120.0                             # 2 làn, mỗi làn 60 mm (xe 1:64 rộng ~30 mm)
LANE_W = ROAD_W / 2
SIDEWALK_W = 16.0
CROSSWALK_D = 30.0                         # chiều sâu vạch qua đường
STOP_GAP = 8.0                             # khoảng từ vạch qua đường tới vạch dừng
JUNCTIONS = {"J1": (-280.0, 0.0), "J2": (280.0, 0.0)}

# Hộp đế: tấm A0 đặt lùi về phía sau, chừa dải trước 200 mm cho mạch điện tử
BASE_MARGIN_X = 45.0
BASE_FRONT = 200.0
BASE_BACK = 25.0
BASE_H = 50.0
BOARD_Y0 = 0.0                             # tâm tấm A0 trùng gốc tọa độ

# Trụ giao thông: mỗi ngã tư 1 trụ nhôm 20 × 20 ở một góc. Cần trên vươn chéo tới tâm ngã tư,
# treo camera nhìn thẳng xuống; cần dưới treo cụm đèn 4 mặt (4 module R/Y/G) ở tâm ngã tư.
# Hai trụ đặt ở hai góc phía Bắc quay vào nhau để cáp CSI về Pi (đặt giữa hai trụ) ngắn nhất.
POLE_CORNER = {"J1": (1, 1), "J2": (-1, 1)}   # J1: góc Đông-Bắc, J2: góc Tây-Bắc
POLE_OFF = 100.0                           # chân trụ cách tâm ngã tư 100 mm theo mỗi trục
CAMERA_H = 400.0                           # ống kính cách mặt sa bàn (xem ghi chú ở camera_cover_h)
SIGNAL_ARM_H = 160.0                       # cần treo đèn
SIGNAL_H = 112.0                           # tâm cụm đèn 4 mặt (~7 m ở tỉ lệ 1:64)
CAM_HFOV_DEG = 102.0                       # Camera Module 3 Wide (thông số nhà sản xuất)
CAM_VFOV_DEG = 67.0
PI_XY = (0.0, 140.0)                       # Pi 5 trong tủ điều khiển ven đường, giữa hai trụ
ROI_LEN = 200.0                            # vùng đếm hàng đợi ~2 xe tính từ vạch dừng

CAR_L, CAR_W = 75.0, 32.0                  # xe 1:64
CAR_GAP = 13.0


def stop_dist() -> float:
    """Khoảng từ tâm ngã tư tới vạch dừng."""
    return ROAD_W / 2 + CROSSWALK_D + STOP_GAP


def pole_xy(node: str) -> tuple[float, float]:
    jx, jy = JUNCTIONS[node]
    sx, sy = POLE_CORNER[node]
    return jx + sx * POLE_OFF, jy + sy * POLE_OFF


def arm_yaw(node: str) -> float:
    """Hướng từ tâm ngã tư ra chân trụ (độ). Cạnh dài khung hình camera nằm dọc theo hướng này."""
    sx, sy = POLE_CORNER[node]
    return math.degrees(math.atan2(sy, sx))


def arm_len() -> float:
    """Chiều dài nằm ngang của cần, từ trục trụ tới tâm ngã tư."""
    return POLE_OFF * math.sqrt(2)


def camera_footprint(node: str, h: float = CAMERA_H) -> list[tuple[float, float]]:
    """4 góc vùng nhìn trên mặt sa bàn của camera nhìn thẳng xuống, cạnh dài dọc theo cần."""
    jx, jy = JUNCTIONS[node]
    a = h * math.tan(math.radians(CAM_HFOV_DEG / 2))
    b = h * math.tan(math.radians(CAM_VFOV_DEG / 2))
    c, s = math.cos(math.radians(arm_yaw(node))), math.sin(math.radians(arm_yaw(node)))
    return [(jx + u * c - v * s, jy + u * s + v * c) for u, v in ((-a, -b), (a, -b), (a, b), (-a, b))]


def camera_cover_h(node: str) -> float:
    """Độ cao ống kính nhỏ nhất để vùng nhìn chứa trọn 4 ROI của nút (không tính méo ống kính)."""
    jx, jy = JUNCTIONS[node]
    ta = math.tan(math.radians(CAM_HFOV_DEG / 2))
    tb = math.tan(math.radians(CAM_VFOV_DEG / 2))
    c, s = math.cos(math.radians(arm_yaw(node))), math.sin(math.radians(arm_yaw(node)))
    need = 0.0
    for appr in "NSEW":
        for x, y in roi_rect(node, appr):
            u = (x - jx) * c + (y - jy) * s
            v = -(x - jx) * s + (y - jy) * c
            need = max(need, abs(u) / ta, abs(v) / tb)
    return need


ARM_Z = CAMERA_H + 32                      # tâm thanh cần trên (nhôm 20 × 20), tính từ mặt sa bàn


def csi_route(node: str) -> list[tuple[float, float, float]]:
    """Đường cáp CSI (mm, z tính từ mặt sa bàn): Pi → dọc mặt sa bàn → mặt Bắc của trụ → trên lưng cần →
    vòng qua cạnh cần xuống đầu nối camera."""
    px, py = PI_XY
    tx, ty = pole_xy(node)
    jx, jy = JUNCTIONS[node]
    side = 1 if tx > px else -1
    yaw = math.radians(arm_yaw(node) + 180)                # trục cần: từ trụ tới tâm ngã tư
    ox, oy = math.sin(yaw), -math.cos(yaw)                 # phía −y cục bộ của cần, nơi có đầu nối camera
    return [(px + side * 32, py + 10, 20), (px + side * 50, py + 8, 3), (tx - side * 20, ty + 12, 2),
            (tx, ty + 11, 6), (tx, ty + 11, ARM_Z - 14), (tx, ty + 6, ARM_Z + 11),
            (jx + ox * 4, jy + oy * 4, ARM_Z + 11), (jx + ox * 13, jy + oy * 13, ARM_Z),
            (jx + ox * 13, jy + oy * 13, CAMERA_H + 16), (jx + ox * 11, jy + oy * 11, CAMERA_H + 11)]


def polyline_len(pts) -> float:
    return sum(math.dist(a, b) for a, b in zip(pts, pts[1:]))


# Hướng tiếp cận: (dx, dy) là hướng xe đang chạy; lane_off là độ lệch làn so với tim đường
APPROACHES = {
    # tên: (hướng chạy, trục làn, dấu lệch làn)
    "N": ((0, -1), "x", -1),   # xe từ phía Bắc đi xuống (Nam), làn phía Tây của đường
    "S": ((0, 1), "x", 1),
    "E": ((-1, 0), "y", 1),    # xe từ phía Đông đi sang Tây, làn phía Bắc
    "W": ((1, 0), "y", -1),
}


def lane_center(node: str, appr: str) -> tuple[float, float]:
    jx, jy = JUNCTIONS[node]
    (_, _), axis, sign = APPROACHES[appr]
    if axis == "x":
        return jx + sign * LANE_W / 2, jy
    return jx, jy + sign * LANE_W / 2


def roi_rect(node: str, appr: str) -> list[tuple[float, float]]:
    """ROI của một hướng: làn vào, từ vạch dừng ra xa ROI_LEN; trên đoạn nối thì dừng ở giữa đoạn."""
    jx, jy = JUNCTIONS[node]
    sd = stop_dist()
    other = [j for j in JUNCTIONS if j != node][0]
    mid_x = (JUNCTIONS[node][0] + JUNCTIONS[other][0]) / 2
    if appr == "N":
        x0, x1, y0, y1 = jx - LANE_W, jx, jy + sd, jy + sd + ROI_LEN
    elif appr == "S":
        x0, x1, y0, y1 = jx, jx + LANE_W, jy - sd - ROI_LEN, jy - sd
    elif appr == "E":
        far = min(mid_x, jx + sd + ROI_LEN) if mid_x > jx else jx + sd + ROI_LEN
        x0, x1, y0, y1 = jx + sd, far, jy, jy + LANE_W
    else:
        far = max(mid_x, jx - sd - ROI_LEN) if mid_x < jx else jx - sd - ROI_LEN
        x0, x1, y0, y1 = far, jx - sd, jy - LANE_W, jy
    return [(x0, y0), (x1, y0), (x1, y1), (x0, y1)]


# Kịch bản minh họa: J1 xanh Bắc–Nam, J2 xanh Đông–Tây (ưu tiên hàng đợi dài trên đoạn nối)
PHASE_GREEN = {"J1": "NS", "J2": "EW"}

# Xe: (nút, hướng, khoảng cách từ vạch dừng tới đầu xe, mm). Âm = đã vào trong ngã tư.
CARS = [
    ("J1", "N", -95), ("J1", "N", 190),
    ("J1", "S", 60),
    ("J1", "W", 6), ("J1", "W", 94),
    ("J1", "E", 6), ("J1", "E", 94), ("J1", "E", 182),
    ("J2", "W", -105), ("J2", "W", 20), ("J2", "W", 125), ("J2", "W", 230),
    ("J2", "N", 6), ("J2", "N", 94), ("J2", "N", 182),
    ("J2", "S", 6), ("J2", "S", 94),
    ("J2", "E", 100),
]


def car_pose(node: str, appr: str, dist: float) -> tuple[float, float, float]:
    """Tâm xe (x, y) và góc quay quanh z (độ) cho xe ở hướng appr, cách vạch dừng dist."""
    (dx, dy), _, _ = APPROACHES[appr]
    cx, cy = lane_center(node, appr)
    jx, jy = JUNCTIONS[node]
    sd = stop_dist()
    # vạch dừng nằm cách tâm ngã tư sd theo hướng ngược chiều chạy
    stop_x, stop_y = jx - dx * sd, jy - dy * sd
    if dx == 0:
        stop_x = cx
    else:
        stop_y = cy
    centre_back = dist + CAR_L / 2
    x = stop_x - dx * centre_back
    y = stop_y - dy * centre_back
    heading = math.degrees(math.atan2(dy, dx))
    return x, y, heading


# Mặt đèn của cụm 4 mặt quay về phía xe tới: hướng N (xe từ phía Bắc) nhìn mặt quay lên Bắc, v.v.
FACE_YAW = {"N": 90.0, "S": -90.0, "E": 0.0, "W": 180.0}


def light_state(node: str, appr: str) -> str:
    green = PHASE_GREEN[node]
    axis = "NS" if appr in "NS" else "EW"
    return "G" if axis == green else "R"
