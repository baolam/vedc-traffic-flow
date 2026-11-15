"""NHAN_DECAL_A4: cờ nhãn cáp (mã như bản vẽ A.1) và nhãn thiết bị, in decal nhựa trắng, tự cắt theo viền xám."""
from __future__ import annotations

from html import escape

CAP, NGUON, NUT, PI, AN_TOAN, INK = "#AE3EC9", "#D9480F", "#2B8A3E", "#1C7ED6", "#C92A2A", "#1E2329"

# (mã, mô tả, màu); mỗi cáp dán 2 đầu
CABLES = [
    ("W1", "CAT5e · breadboard J1 ↔ cụm đèn J1", CAP),
    ("W2", "CAT5e · breadboard J2 ↔ cụm đèn J2", CAP),
    ("P1", "DC · adapter 5 V → X1", NGUON),
    ("P2", "5 V · X2 → ESP32 J1", NGUON),
    ("P3", "5 V · X2 (J1) → ESP32 J2", NGUON),
    ("P4", "USB-C · bộ nguồn → Pi 5", NGUON),
]

# (chữ lớn, chữ nhỏ, màu, rộng mm, cao mm, số lượng)
DEVICES = [
    ("ESP32 · NÚT J1", "NodeMCU-32S", NUT, 44, 13, 2),
    ("ESP32 · NÚT J2", "NodeMCU-32S", NUT, 44, 13, 2),
    ("Raspberry Pi 5", "AI biên · đọc video", PI, 44, 13, 2),
    ("S1 · DỪNG AN TOÀN", "nhấn: vàng nhấp nháy", AN_TOAN, 44, 13, 3),
    ("X1 · 5 V VÀO", "jack DC 5,5 × 2,1", NGUON, 36, 11, 2),
    ("X2 · CHIA 5 V", "domino → VIN", NGUON, 36, 11, 2),
]
POLE_TAGS = ["J1", "J1", "J2", "J2"]
POLARITY = ["+5 V"] * 6 + ["GND"] * 6
TRAY_TAGS = [("ĐẾ TRỤ J1", "MDF 200 × 200"), ("ĐẾ TRỤ J2", "MDF 200 × 200")]

CSS = """
@page { size: A4; margin: 0 }
html, body { margin: 0 }
body { font-family: 'Avenir Next', Arial, sans-serif; color: #1E2329 }
.page { width: 210mm; height: 297mm; padding: 11mm 12mm; box-sizing: border-box }
h1 { font-family: 'Avenir Next Condensed', sans-serif; font-weight: 700; font-size: 15pt; margin: 0 0 1mm }
.note { font-size: 8pt; color: #5B6470; margin-bottom: 3mm }
h2 { font-family: 'Avenir Next Condensed', sans-serif; font-weight: 700; font-size: 10pt; margin: 3.5mm 0 1.6mm;
     text-transform: uppercase; letter-spacing: .6pt; color: #5B6470 }
.wrap { display: flex; flex-wrap: wrap; gap: 2.4mm }
.cut { outline: .25mm dashed #B8BEC6; outline-offset: 0 }
.flag { width: 60mm; height: 13mm; display: flex }
.flag .half { width: 30mm; height: 13mm; display: flex; align-items: center; gap: 1.6mm; padding: 0 1.8mm;
              box-sizing: border-box }
.flag .half + .half { border-left: .25mm dashed #5B6470 }
.code { font-family: 'Avenir Next Condensed', sans-serif; font-weight: 700; font-size: 15pt; color: #fff;
        border-radius: 1mm; padding: 0 1.3mm; line-height: 1.25 }
.desc { font-size: 5.4pt; line-height: 1.2; color: #1E2329 }
.dev { display: flex; flex-direction: column; justify-content: center; padding: 0 2.2mm; box-sizing: border-box;
       border-left: 2.2mm solid }
.dev b { font-family: 'Avenir Next Condensed', sans-serif; font-weight: 700; font-size: 10.5pt; line-height: 1.1 }
.dev span { font-size: 6.4pt; color: #5B6470 }
.pole { width: 17mm; height: 17mm; display: flex; align-items: center; justify-content: center; background: #1E2329;
        color: #fff; font-family: 'Avenir Next Condensed', sans-serif; font-weight: 700; font-size: 17pt }
.pol { width: 15mm; height: 7mm; display: flex; align-items: center; justify-content: center;
       font-family: 'Avenir Next Condensed', sans-serif; font-weight: 700; font-size: 9pt; color: #fff }
.tray { width: 62mm; height: 12mm; display: flex; align-items: center; justify-content: space-between;
        padding: 0 3mm; box-sizing: border-box; background: #3E4044; color: #fff }
.tray b { font-family: 'Avenir Next Condensed', sans-serif; font-size: 12pt }
.tray span { font-size: 8pt }
"""


def _flag(code: str, desc: str, color: str) -> str:
    half = (f'<div class="half"><span class="code" style="background:{color}">{code}</span>'
            f'<span class="desc">{escape(desc)}</span></div>')
    return f'<div class="flag cut">{half}{half}</div>'


def html() -> str:
    flags = "".join(_flag(c, d, col) for c, d, col in CABLES for _ in range(2))
    flags += "".join(_flag(c, d, col) for c, d, col in CABLES[:3])          # dự phòng
    devs = "".join(f'<div class="dev cut" style="width:{w}mm;height:{h}mm;border-color:{col}"><b>{escape(big)}</b>'
                   f'<span>{escape(small)}</span></div>'
                   for big, small, col, w, h, k in DEVICES for _ in range(k))
    poles = "".join(f'<div class="pole cut">{t}</div>' for t in POLE_TAGS)
    pols = "".join(f'<div class="pol cut" style="background:{NGUON if p.startswith("+") else INK}">{p}</div>'
                   for p in POLARITY)
    trays = "".join(f'<div class="tray cut"><b>{a}</b><span>{escape(b)}</span></div>' for a, b in TRAY_TAGS)
    spare = "".join(_flag(c, d, col) for c, d, col in CABLES[3:])
    spare += "".join(f'<div class="dev cut" style="width:44mm;height:13mm;border-color:{col}"></div>'
                     for col in (NUT, NUT, NGUON, NGUON, CAP, CAP, INK, INK))
    return f"""<!doctype html><html lang="vi"><head><meta charset="utf-8"><title>Nhãn decal</title>
<style>{CSS}</style></head><body><section class="page">
<h1>Nhãn decal · sa bàn EdgeFlow AI</h1>
<div class="note">In decal nhựa trắng, đúng tỉ lệ 100 %. Cắt theo viền xám nét đứt. Mã cáp theo bản vẽ A.1.</div>
<h2>Cờ nhãn cáp · gấp đôi theo nét đứt giữa, kẹp dây vào nếp gấp · mỗi cáp dán 2 đầu</h2>
<div class="wrap">{flags}</div>
<h2>Nhãn thiết bị</h2>
<div class="wrap">{devs}</div>
<h2>Nhãn trụ (mặt trụ 20 mm) · cực nguồn · đế trụ</h2>
<div class="wrap">{poles}{pols}{trays}</div>
<h2>Dự phòng · cờ nhãn và nhãn trống để viết tay</h2>
<div class="wrap">{spare}</div>
</section></body></html>"""
