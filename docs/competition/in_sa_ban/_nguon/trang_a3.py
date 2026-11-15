"""BANG_GIOI_THIEU_A3: bảng dựng cạnh sa bàn lúc thi. Chỉ ghi điều có trong code/firmware, không có số kết quả."""
from __future__ import annotations

from html import escape

import hinh_hoc as G
import ve_tam

# (tiêu đề, mô tả, nhãn kỹ thuật, màu điểm dừng)
STOPS = [
    ("Video giao thông", "Render 3D mô phỏng, nhìn bao quát cả hai ngã tư J1 và J2", "VIDEO_SOURCE = file", "#1C7ED6"),
    ("Raspberry Pi 5 · YOLO11n", "Phát hiện xe và đếm hàng đợi theo từng làn (ROI) ngay trên thiết bị biên",
     "ONNX · OpenCV", "#1C7ED6"),
    ("MQTT · telemetry", "Gửi hàng đợi từng hướng của J1, J2 trong mạng LAN", "edgeflow/v1/telemetry/{nút}", "#B7791F"),
    ("Graph-Control", "Máy chủ điều phối chọn pha cho cả hai nút trên đồ thị mạng lưới (MaxPressure / EdgeFlow)",
     "edgeflow/v1/control/{nút}/command", "#6B46C1"),
    ("ESP32 J1, J2", "Kiểm giới hạn an toàn rồi mới đổi đèn, báo lại trạng thái lệnh",
     "…/ack · ACCEPTED → APPLIED", "#2B8A3E"),
    ("Đèn LED 4 hướng", "Cụm 4 mặt R/Y/G treo giữa mỗi ngã tư trên sa bàn", "GPIO 23 22 21 · 19 18 5", "#2B8A3E"),
]

HARDWARE = [
    ("Thiết bị biên", "Raspberry Pi 5 · YOLO11n ONNX"),
    ("Nút chấp hành", "2 × ESP32 NodeMCU-32S"),
    ("Đèn", "8 module R/Y/G, 4 mặt mỗi ngã tư"),
    ("Mạng", "MQTT qua Wi-Fi 2,4 GHz trong LAN"),
]

SAFETY = [
    ("3 s", "vàng", "#E09F00"),
    ("2 s", "đỏ toàn phần giữa hai pha", "#E03131"),
    ("5–60 s", "xanh tối thiểu – tối đa", "#2F9E44"),
    ("5 s", "mất lệnh: tự chạy dự phòng 15 s mỗi pha", "#3E4044"),
    ("S1", "nút dừng an toàn: vàng nhấp nháy", "#C92A2A"),
]

CSS = """
@page { size: A3; margin: 0 }
* { box-sizing: border-box }
html, body { margin: 0 }
body { font-family: 'Avenir Next', Arial, sans-serif; color: #1E2329; background: #F4F1EA }
.page { width: 297mm; height: 420mm; position: relative; overflow: hidden; background: #F4F1EA }
.hero { background: #2E3034; color: #F4F1EA; height: 124mm; padding: 14mm 18mm 0; position: relative }
.kicker { font-family: 'Avenir Next Condensed', sans-serif; font-weight: 600; font-size: 12pt; letter-spacing: 2.4pt;
          text-transform: uppercase; color: #FCC419 }
.title { font-family: 'Avenir Next Condensed', sans-serif; font-weight: 800; font-size: 104pt; line-height: .92;
         letter-spacing: -1pt; margin: 6mm 0 5mm }
.lead { font-size: 17pt; line-height: 1.3; max-width: 190mm; color: #E9E5DC; font-weight: 500 }
.road { position: absolute; left: 0; right: 0; bottom: 12mm; height: 2.2mm;
        background: repeating-linear-gradient(90deg, #F4F1EA 0 22mm, transparent 22mm 36mm) }
.head-signal { position: absolute; right: 22mm; top: 22mm; width: 26mm; height: 72mm; background: #17181B;
               border-radius: 6mm; display: flex; flex-direction: column; justify-content: space-around;
               align-items: center; padding: 3mm 0; box-shadow: 0 2mm 0 #0E0F11 }
.lamp { width: 17mm; height: 17mm; border-radius: 50% }
.body { display: grid; grid-template-columns: 124mm 1fr; gap: 10mm; padding: 13mm 18mm 0 }
.sec { font-family: 'Avenir Next Condensed', sans-serif; font-weight: 700; font-size: 11pt; letter-spacing: 1.6pt;
       text-transform: uppercase; color: #5B6470; margin: 0 0 5mm; display: flex; gap: 2.5mm; align-items: baseline }
.sec b { color: #1E2329; font-size: 19pt; letter-spacing: 0; text-transform: none }
.route { position: relative; padding-left: 11mm }
.route::before { content: ''; position: absolute; left: 3.6mm; top: 3mm; bottom: 12mm; width: 2.2mm;
                 background: #3E4044; border-radius: 1mm }
.stop { position: relative; margin-bottom: 7.4mm }
.dot { position: absolute; left: -11mm; top: .6mm; width: 9.4mm; height: 9.4mm; border-radius: 50%;
       background: #F4F1EA; border: 2.2mm solid; display: flex; align-items: center; justify-content: center;
       font-family: 'Avenir Next Condensed', sans-serif; font-weight: 700; font-size: 0 }
.stop h3 { font-family: 'Avenir Next Condensed', sans-serif; font-weight: 700; font-size: 18pt; margin: 0;
           line-height: 1.15 }
.stop p { margin: 1mm 0 1.6mm; font-size: 11.6pt; line-height: 1.35; color: #3B424B }
.hw { list-style: none; margin: 5mm 0 0; padding: 0; font-size: 10.4pt; line-height: 1.3 }
.hw li { display: flex; justify-content: space-between; gap: 4mm; border-bottom: .5pt solid #D8D2C4; padding: 1.6mm 0 }
.hw li span:last-child { color: #5B6470; text-align: right }
.wide { padding: 0 18mm }
.mono { font-family: Menlo, monospace; font-size: 8.2pt; background: #E6E1D6; padding: .5mm 1.6mm;
        border-radius: 1mm; color: #1E2329 }
.plan { background: #fff; border-radius: 3mm; padding: 4mm; box-shadow: 0 .8mm 0 #E0DBCF }
.legend { list-style: none; margin: 4mm 0 0; padding: 0; display: grid; grid-template-columns: 1fr 1fr; gap: 2.4mm 5mm;
          font-size: 10pt; line-height: 1.3 }
.legend li { display: flex; gap: 2mm }
.legend .k { flex: none; width: 6.2mm; height: 6.2mm; border-radius: 50%; background: #1E2329; color: #fff;
             font-family: 'Avenir Next Condensed', sans-serif; font-weight: 700; font-size: 10pt;
             display: flex; align-items: center; justify-content: center }
.modular { margin-top: 4mm; font-family: 'Avenir Next Condensed', sans-serif; font-weight: 600; font-size: 13pt;
           border-left: 1.6mm solid #FCC419; padding: 1mm 0 1mm 3mm }
.safe { display: grid; grid-template-columns: repeat(5, 1fr); gap: 2.4mm; margin-top: 3mm }
.tile { background: #fff; border-radius: 2.4mm; padding: 3.4mm 3.4mm; border-top: 2.4mm solid; min-height: 30mm }
.tile b { display: block; font-family: 'Avenir Next Condensed', sans-serif; font-weight: 800; font-size: 30pt;
          line-height: 1; white-space: nowrap }
.tile span { display: block; font-size: 10.4pt; line-height: 1.3; margin-top: 2mm; color: #3B424B }
.fine { font-size: 10.4pt; color: #3B424B; margin-top: 3mm; line-height: 1.4 }
.foot { position: absolute; left: 18mm; right: 18mm; bottom: 12mm; border-top: 1pt solid #1E2329; padding-top: 3.4mm;
        display: flex; justify-content: space-between; align-items: baseline }
.foot b { font-family: 'Avenir Next Condensed', sans-serif; font-size: 17pt }
.foot span { font-size: 10pt; color: #5B6470; max-width: 150mm; text-align: right; line-height: 1.35 }
"""


def _overlay() -> str:
    """Thiết bị vẽ đè lên tấm bạt (tọa độ ghép, y hướng Bắc) và số chú thích."""
    out = []

    def rect(r: tuple[float, float, float, float], node: str, fill: str, extra: str = "") -> str:
        x0, y0, x1, y1 = G.rect_x(node, r)
        off = G.WORLD_X[node]
        return (f'<rect x="{x0 + off:.1f}" y="{-y1:.1f}" width="{x1 - x0:.1f}" height="{y1 - y0:.1f}" '
                f'fill="{fill}" {extra}/>')

    for n in G.NODES:
        off = G.WORLD_X[n]
        px, py = off + G.to_x(n, G.POLE_U), G.POLE_Y
        out.append(f'<path d="M{px:.1f} {-py:.1f}L{off:.1f} 0" stroke="#17181B" stroke-width="14" '
                   f'stroke-linecap="square"/>')
        out.append(rect(G.pole_rect(), n, "#17181B"))
        out.append(f'<rect x="{off - 22}" y="-22" width="44" height="44" rx="5" fill="#17181B"/>')
        for k, (dx, dy, c) in enumerate([(0, -13, "#E03131"), (13, 0, "#2F9E44"), (0, 13, "#E03131"),
                                         (-13, 0, "#2F9E44")]):
            out.append(f'<circle cx="{off + dx}" cy="{dy}" r="5.5" fill="{c}"/>')
        out.append(rect(G.bb_rect(), n, "#FBFBF8", 'stroke="#B8BEC6" stroke-width="1.5" rx="3"'))
        out.append(rect(G.esp32_rect(), n, "#1E2329", 'rx="2"'))
    out.append(rect(G.pi_rect(), "J2", "#C8102E", 'rx="6"'))
    out.append(rect(G.x1_rect(), "J1", "#1E2329", 'rx="2"'))
    marks = [("1", -200 + 34, 132), ("2", -300 + 188 + 74, -172), ("3", G.WORLD_X["J2"] + G.to_x("J2", G.PI_U), G.PI_Y + 62), ("4", 0, 0)]
    for k, x, y in marks:
        out.append(f'<circle cx="{x}" cy="{-y}" r="19" fill="#1E2329" stroke="#fff" stroke-width="4"/>'
                   f'<text x="{x}" y="{-y}" fill="#fff" font-family="Avenir Next Condensed" font-weight="700" '
                   f'font-size="24" text-anchor="middle" dominant-baseline="central">{k}</text>')
    return "".join(out)


def html() -> str:
    stops = "".join(f'<div class="stop"><div class="dot" style="border-color:{c}"></div><h3>{escape(t)}</h3>'
                    f'<p>{escape(d)}</p><span class="mono">{escape(tag)}</span></div>' for t, d, tag, c in STOPS)
    safe = "".join(f'<div class="tile" style="border-color:{c}"><b>{escape(v)}</b><span>{escape(t)}</span></div>'
                   for v, t, c in SAFETY)
    plan = ve_tam.pair_svg(marks=False, extra=_overlay())
    legend = [("1", "Trụ đèn + cụm đèn 4 mặt treo giữa ngã tư"), ("2", "ESP32 trên breadboard, nút dừng S1"),
              ("3", "Raspberry Pi 5 chạy YOLO11n"), ("4", "Đoạn nối J1 – J2: xe rời nút này đi vào hàng đợi nút kia")]
    leg = "".join(f'<li><span class="k">{k}</span><span>{escape(t)}</span></li>' for k, t in legend)
    hw = "".join(f"<li><span>{escape(a)}</span><span>{escape(b)}</span></li>" for a, b in HARDWARE)
    return f"""<!doctype html><html lang="vi"><head><meta charset="utf-8"><title>Bảng giới thiệu</title>
<style>{CSS}</style></head><body><section class="page">
<header class="hero">
  <div class="kicker">VEDC 2026 · AI nhúng cho hệ thống IoT thông minh</div>
  <div class="title">EdgeFlow AI</div>
  <div class="lead">Điều khiển đèn giao thông thích ứng trên đồ thị mạng lưới đường: AI thị giác đếm xe ngay tại biên,
    máy chủ điều phối nhiều ngã tư cùng lúc, đèn tự giữ an toàn.</div>
  <div class="head-signal">
    <div class="lamp" style="background:#5C1F1F"></div>
    <div class="lamp" style="background:#5C4A12"></div>
    <div class="lamp" style="background:#51CF66;box-shadow:0 0 8mm 2mm rgba(81,207,102,.55)"></div>
  </div>
  <div class="road"></div>
</header>
<main class="body">
  <section>
    <div class="sec"><b>Luồng dữ liệu</b></div>
    <div class="route">{stops}</div>
  </section>
  <section>
    <div class="sec"><b>Trên sa bàn</b></div>
    <div class="plan">{plan}</div>
    <ul class="legend">{leg}</ul>
    <div class="modular">Thêm một ngã tư = nối dài bạt, thêm một ESP32 và khai báo nút trong topology.</div>
    <ul class="hw">{hw}</ul>
  </section>
</main>
<section class="wide" style="margin-top:4mm">
  <div class="sec" style="margin-bottom:1mm"><b>An toàn do đèn tự quyết</b>
    <span style="text-transform:none;letter-spacing:0;font-weight:500;font-family:'Avenir Next'">giới hạn nằm trong
    firmware ESP32, lệnh từ máy chủ không vượt qua được</span></div>
  <div class="safe">{safe}</div>
  <p class="fine">Trong phần trình diễn, đầu vào thị giác là video render 3D mô phỏng, không phải ảnh camera thật;
    xe trong video không dừng theo đèn trên sa bàn (vòng hở). Tốc độ, lưu lượng hiển thị là ước lượng.</p>
</section>
<footer class="foot"><b>Đội 31µF · Trường Đại học FPT TP.HCM</b>
  <span>Sa bàn {2 * G.TILE / 10:.0f} × {G.TILE / 10:.0f} cm · 2 nút J1, J2 · ESP32 NodeMCU-32S · Raspberry Pi 5</span>
</footer>
</section></body></html>"""
