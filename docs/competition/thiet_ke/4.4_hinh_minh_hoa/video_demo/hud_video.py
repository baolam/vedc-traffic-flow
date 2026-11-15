"""Phủ lớp chú thích luồng hệ thống lên video demo: lúc hệ thống kích hoạt, hàng đợi trong ROI, chuỗi xử lý
video → AI → điều khiển → đèn, nhật ký sự kiện, và một khung DASHBOARD (màn hình đặt cạnh sa bàn) hiện trạng thái
đèn, số giây và số xe chờ của từng nút.

  uv run -q --with opencv-python-headless --with numpy --with pillow python hud_video.py \\
      video_demo_150s.mp4 kich_ban_train.json rois_video.json video_trinh_dien_150s.mp4

Sa bàn thật chỉ có đèn R/Y/G, KHÔNG có bảng đếm giây: số giây chỉ xuất hiện trên dashboard (theo plan 22/09: hiện
quyết định bên cạnh đèn LED thật). Cụm đèn 3D trong video tự đổi màu theo từng khung hình.
Video sạch (không chú thích) là nguồn vào cho service vision; file này chỉ để trình diễn. Đây là MÔ PHỎNG MINH HỌA:
số xe lấy từ mô phỏng, không phải kết quả YOLO thật, quy tắc chọn pha là bản rút gọn, khung dashboard là bố cục
minh họa chứ không phải ảnh chụp dashboard React thật.
"""
from __future__ import annotations

import json
import math
import sys
from pathlib import Path

import cv2
import numpy as np
from PIL import Image, ImageDraw, ImageFont

FONT = "/System/Library/Fonts/Supplemental/Arial.ttf"
FONT_B = "/System/Library/Fonts/Supplemental/Arial Bold.ttf"
COLORS = {"G": (47, 158, 68), "Y": (242, 193, 78), "R": (214, 59, 59)}
INK, WHITE, DIM = (30, 35, 41), (255, 255, 255), (150, 156, 164)
AXIS_VN = {"NS": "Bắc–Nam", "EW": "Đông–Tây"}
STATE_VN = {"G": "XANH", "Y": "VÀNG", "R": "ĐỎ"}
PIPELINE = ["Video", "AI đếm xe (YOLO)", "Telemetry MQTT", "Graph-Control", "Lệnh pha", "ESP32 → đèn"]
FLASH_S, LOG_AGE_S = 3.0, 14.0


def f(size: int, bold: bool = False) -> ImageFont.FreeTypeFont:
    return ImageFont.truetype(FONT_B if bold else FONT, size)


def pill(d: ImageDraw.ImageDraw, box, fill, text: str, size: int, fg=WHITE, bold: bool = True, alpha_bg=None) -> None:
    d.rounded_rectangle(box, radius=(box[3] - box[1]) // 2 if box[3] - box[1] < 40 else 8, fill=fill)
    d.text(((box[0] + box[2]) / 2, (box[1] + box[3]) / 2), text, font=f(size, bold), fill=fg, anchor="mm")


def secs_text(node: dict) -> str:
    s = node["secs"]
    if node["dir"] == "up":
        return f"{int(s)}"
    return f"{math.ceil(s)}" if s > 0 else "0"


DASH_X0, DASH_Y0, DASH_H, DASH_W = 590, 562, 122, 676
APPRS = ("N", "S", "E", "W")


def phase_summary(st: dict) -> tuple[str, str, tuple[int, int, int]]:
    """(dòng trạng thái, chú thích đồng hồ, màu) của một nút."""
    ns, ew = st["NS"], st["EW"]
    green = "NS" if ns == "G" else ("EW" if ew == "G" else None)
    if green:
        note = "đã xanh" if st["dir"] == "up" else "còn lại"
        return f"{AXIS_VN[green]} XANH", note, COLORS["G"]
    if "Y" in (ns, ew):
        return "VÀNG", "còn lại", COLORS["Y"]
    return "ALL-RED", "còn lại", COLORS["R"]


def draw_node_card(d: ImageDraw.ImageDraw, box, node: str, st: dict, queues: dict, on: bool) -> None:
    x0, y0, x1, y1 = box
    d.rounded_rectangle(box, radius=8, fill=(34, 40, 49, 255))
    title, note, col = phase_summary(st)
    d.text((x0 + 12, y0 + 16), node, font=f(20, True), fill=WHITE, anchor="lm")
    d.text((x0 + 48, y0 + 16), title, font=f(15, True), fill=col, anchor="lm")
    d.text((x1 - 12, y0 + 22), f"{secs_text(st)} s", font=f(32, True), fill=WHITE, anchor="rm")
    d.text((x1 - 12, y0 + 44), note, font=f(12), fill=DIM, anchor="rm")
    cell = (x1 - x0 - 24) / len(APPRS)
    for i, appr in enumerate(APPRS):
        axis = "NS" if appr in "NS" else "EW"
        cx, cy = x0 + 12 + i * cell + 11, y1 - 17
        d.ellipse((cx - 11, cy - 11, cx + 11, cy + 11), fill=COLORS[st[axis]])
        d.text((cx, cy), appr, font=f(12, True), fill=INK if st[axis] == "Y" else WHITE, anchor="mm")
        q = f"{queues.get(f'{node}_{appr}_IN', 0)} xe" if on else "—"
        d.text((cx + 17, cy), q, font=f(13), fill=(205, 211, 218), anchor="lm")


def draw_dashboard(d: ImageDraw.ImageDraw, hud: dict, on: bool, W: int, H: int) -> None:
    """Khung dashboard ở dải dưới tấm bạt: thanh tiêu đề kiểu cửa sổ, mỗi nút một thẻ."""
    x0, y0 = DASH_X0, DASH_Y0
    x1, y1 = x0 + DASH_W, y0 + DASH_H
    d.rounded_rectangle((x0, y0, x1, y1), radius=10, fill=(14, 17, 22, 245), outline=(90, 98, 110, 255), width=2)
    for k, c in enumerate(((236, 106, 94), (244, 191, 79), (97, 197, 84))):
        d.ellipse((x0 + 12 + k * 18, y0 + 9, x0 + 22 + k * 18, y0 + 19), fill=c)
    d.text((x0 + 80, y0 + 14), "Dashboard EdgeFlow AI · trạng thái đèn (minh họa)", font=f(13, True), fill=(205, 211, 218),
           anchor="lm")
    state = "Hệ thống điều khiển" if on else "Đèn chu kỳ cố định"
    d.text((x1 - 12, y0 + 14), state, font=f(12, True), fill=COLORS["G"] if on else DIM, anchor="rm")
    top, pad = y0 + 28, 10
    cw = (DASH_W - 3 * pad) / 2
    for k, (node, st) in enumerate(hud["nodes"].items()):
        cx0 = x0 + pad + k * (cw + pad)
        draw_node_card(d, (cx0, top, cx0 + cw, y1 - pad), node, st, hud["queues"], on)


def draw(frame: np.ndarray, fi: int, sc: dict, rois: dict) -> np.ndarray:
    fps = sc["fps"]
    t = fi / fps
    hud = sc["hud"][min(fi, len(sc["hud"]) - 1)]
    on = hud["on"]
    base = Image.fromarray(cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)).convert("RGBA")
    over = Image.new("RGBA", base.size, (0, 0, 0, 0))
    d = ImageDraw.Draw(over)
    W, H = base.size

    # ROI và số xe đếm được: chỉ khi hệ thống đã kích hoạt
    if on:
        for node, polys in rois["nodes"].items():
            for name, pts in polys.items():
                q = hud["queues"].get(name, 0)
                col = (120, 190, 255) if q == 0 else ((242, 170, 40) if q == 1 else (230, 70, 60))
                d.polygon([tuple(p) for p in pts], fill=(*col, 52 if q else 26), outline=(*col, 230))
                cx = sum(p[0] for p in pts) / len(pts)
                cy = sum(p[1] for p in pts) / len(pts)
                d.rounded_rectangle((cx - 12, cy - 11, cx + 12, cy + 11), radius=6, fill=(20, 24, 30, 205))
                d.text((cx, cy), str(q), font=f(15, True), fill=WHITE, anchor="mm")

    # thanh trên
    d.rectangle((0, 0, W, 50), fill=(18, 22, 28, 225))
    d.text((18, 25), "EdgeFlow AI · mô phỏng luồng hệ thống", font=f(21, True), fill=WHITE, anchor="lm")
    d.text((W - 18, 25), f"t = {t:5.1f} s", font=f(20, True), fill=(220, 226, 232), anchor="rm")
    mode_txt = "EDGEFLOW AI ĐANG ĐIỀU KHIỂN" if on else "CHƯA KÍCH HOẠT · ĐÈN CHU KỲ CỐ ĐỊNH"
    pill(d, (W - 500, 9, W - 150, 41), (47, 158, 68) if on else (95, 102, 112), mode_txt, 13)

    # chuỗi xử lý
    n = len(PIPELINE)
    bw, gap, y0 = 168, 22, 60
    x0 = (W - (n * bw + (n - 1) * gap)) / 2
    pulse = any(0 <= t - e["t"] < 1.6 for e in sc["events"] if e["t"] >= sc["t_on"] - 0.01)
    for i, name in enumerate(PIPELINE):
        lit = (i == 0) or on
        hot = on and pulse and i >= 3
        fill = (38, 44, 54, 225) if not lit else ((242, 170, 40, 235) if hot else (47, 110, 190, 235))
        bx = x0 + i * (bw + gap)
        d.rounded_rectangle((bx, y0, bx + bw, y0 + 32), radius=8, fill=fill)
        d.text((bx + bw / 2, y0 + 16), name, font=f(13, True), fill=WHITE if lit else DIM, anchor="mm")
        if i < n - 1:
            d.text((bx + bw + gap / 2, y0 + 16), "›", font=f(22, True), fill=WHITE if lit else DIM, anchor="mm")

    draw_dashboard(d, hud, on, W, H)

    # nhật ký sự kiện
    shown = [e for e in sc["events"] if 0 <= t - e["t"] <= LOG_AGE_S][-4:]
    if shown:
        d.rounded_rectangle((14, H - 36 - 25 * len(shown) - 8, 560, H - 40), radius=10, fill=(18, 22, 28, 205))
        for i, e in enumerate(shown):
            age = t - e["t"]
            a = int(255 * (1.0 if age < 8 else max(0.35, 1 - (age - 8) / 6)))
            d.text((26, H - 36 - 25 * len(shown) + 25 * i + 4), f"{e['t']:5.1f}s  {e['text']}",
                   font=f(14, bold=(age < 3)), fill=(255, 255, 255, a), anchor="lm")

    # băng kích hoạt
    if on and 0 <= t - sc["t_on"] <= FLASH_S:
        a = int(235 * min(1.0, (FLASH_S - (t - sc["t_on"])) / 1.2))
        d.rounded_rectangle((W / 2 - 330, 300, W / 2 + 330, 372), radius=14, fill=(47, 158, 68, a))
        d.text((W / 2, 336), "EDGEFLOW AI KÍCH HOẠT", font=f(34, True), fill=(255, 255, 255, a), anchor="mm")

    # chú thích cuối
    d.rectangle((0, H - 30, W, H), fill=(18, 22, 28, 230))
    d.text((14, H - 15), "Mô phỏng minh họa: số xe lấy từ mô phỏng (không phải YOLO thật). Sa bàn thật chỉ có đèn R/Y/G; "
           "số giây chỉ hiện trên dashboard.", font=f(12), fill=(205, 211, 218), anchor="lm")

    out = Image.alpha_composite(base, over).convert("RGB")
    return cv2.cvtColor(np.asarray(out), cv2.COLOR_RGB2BGR)


def main() -> int:
    video, scen, roi, out = sys.argv[1:5]
    sc = json.loads(Path(scen).read_text())
    rois = json.loads(Path(roi).read_text())
    cap = cv2.VideoCapture(video)
    fps = cap.get(cv2.CAP_PROP_FPS)
    w, h = int(cap.get(3)), int(cap.get(4))
    writer = cv2.VideoWriter(out, cv2.VideoWriter_fourcc(*"mp4v"), fps, (w, h))
    i = 0
    while True:
        ok, fr = cap.read()
        if not ok:
            break
        writer.write(draw(fr, i, sc, rois))
        i += 1
    writer.release()
    print(f"{i} khung -> {out}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
