"""PHIEU_DAT_IN: trang 1 phiếu đặt in cho tiệm, trang 2 bản vẽ đế trụ, trang 3 bảng kiểm khớp thiết bị cho đội."""
from __future__ import annotations

from html import escape

import hinh_hoc as G
import ve_tam

NGAY = "19/10/2026"
INK, INK2, INK3, RULE = "#1E2329", "#5B6470", "#A3ABB5", "#D5DAE0"

CSS = """
@page { size: A4; margin: 0 }
* { box-sizing: border-box }
html, body { margin: 0; background: #fff }
body { font-family: 'Avenir Next', Arial, sans-serif; color: #1E2329; font-size: 9.6pt; line-height: 1.38 }
.page { width: 210mm; height: 297mm; padding: 13mm 14mm 11mm; position: relative; page-break-after: always;
        overflow: hidden }
.page:last-child { page-break-after: auto }
.head { display: flex; justify-content: space-between; align-items: flex-end; border-bottom: 2.2pt solid #1E2329;
        padding-bottom: 2.4mm; margin-bottom: 4mm }
.head h1 { font-family: 'Avenir Next Condensed', sans-serif; font-weight: 700; font-size: 23pt; margin: 0;
           letter-spacing: .3pt; line-height: 1 }
.head .sub { font-size: 9pt; color: #5B6470; margin-top: 1.2mm }
.head .meta { text-align: right; font-size: 8.4pt; color: #5B6470 }
.tag { display: inline-block; font-family: 'Avenir Next Condensed', sans-serif; font-weight: 700; font-size: 8pt;
       letter-spacing: .6pt; text-transform: uppercase; color: #fff; background: #3E4044; padding: .5mm 2mm;
       border-radius: 1mm }
h2 { font-family: 'Avenir Next Condensed', sans-serif; font-weight: 700; font-size: 12.5pt; margin: 4mm 0 1.8mm;
     letter-spacing: .2pt }
h2 .n { display: inline-block; width: 6mm; height: 6mm; line-height: 6mm; text-align: center; border-radius: 50%;
        background: #1E2329; color: #fff; font-size: 9pt; margin-right: 2mm; vertical-align: 1px }
.fill { display: grid; grid-template-columns: 1.3fr 1fr 1fr; gap: 4mm; font-size: 9pt; margin-bottom: 1mm }
.fill div { border-bottom: .6pt solid #A3ABB5; padding-bottom: 4.5mm; color: #5B6470 }
table { width: 100%; border-collapse: collapse; font-size: 8.8pt }
th { text-align: left; font-weight: 600; font-size: 7.6pt; letter-spacing: .4pt; text-transform: uppercase;
     color: #5B6470; border-bottom: 1pt solid #1E2329; padding: 1.4mm 1.6mm }
td { border-bottom: .5pt solid #D5DAE0; padding: 1.8mm 1.6mm; vertical-align: top }
td.num { font-family: 'Avenir Next Condensed', sans-serif; font-weight: 700; font-size: 12pt; width: 7mm }
td b { font-weight: 600 }
.file { font-family: Menlo, monospace; font-size: 7.4pt; color: #1E2329; background: #F1F3F5; padding: .2mm 1mm;
        border-radius: .8mm; white-space: nowrap }
.blank { border-bottom: .6pt solid #A3ABB5; min-width: 22mm; height: 6mm }
ul { margin: 0; padding-left: 4.5mm }
li { margin: .6mm 0 }
.warn { border-left: 2.4pt solid #D9480F; background: #FFF4E6; padding: 2.2mm 3mm; margin-top: 3mm; font-size: 9pt }
.cols { display: grid; grid-template-columns: 1fr 1fr; gap: 6mm }
.check { row-gap: 0 }
.check li { list-style: none; position: relative; padding-left: 5mm }
.check li::before { content: ''; position: absolute; left: 0; top: 1mm; width: 2.8mm; height: 2.8mm;
                    border: .8pt solid #1E2329; border-radius: .6mm }
.fig { margin-top: 2mm }
.cap { font-size: 8pt; color: #5B6470; margin-top: 1.4mm }
.ok { color: #2B8A3E; font-weight: 600 } .bad { color: #C92A2A; font-weight: 600 }
.foot { position: absolute; left: 14mm; right: 14mm; bottom: 7mm; font-size: 7.4pt; color: #A3ABB5;
        display: flex; justify-content: space-between }
.dense td { padding: 1mm 1.6mm; font-size: 8.2pt } .dense th { padding: .9mm 1.6mm }
.dense h2 { margin: 3.2mm 0 1.4mm } .dense li { margin: .3mm 0; font-size: 8.7pt }
"""


def _fmt(v: float) -> str:
    return f"{v:.0f}"


def page_order() -> str:
    full_w, full_h = G.SHEET_W + 2 * G.BLEED, G.SHEET_H + 2 * G.BLEED
    items = [
        ("1", "Mặt sa bàn (1 tấm bạt)",
         f"In <b>bạt Hiflex</b> (bạt khổ in phun), mặt <b>mờ</b>, thành phẩm <b>{G.SHEET_W:.0f} × {G.SHEET_H:.0f} mm</b>. "
         f"<b>Gấp viền {G.BLEED:.0f} mm dán keo</b> (không may). Bấm khoen tròn 4 góc nếu tiệm có sẵn. "
         "<b>Không bồi cứng</b>: đội trải lên bàn và cuộn lại khi chở.",
         "1 tấm", '<span class="file">SA_BAN_BAT_1200x600.pdf</span>'),
        ("2", "Đế trụ",
         f"<b>MDF 6 ly</b> (hoặc tấm gỗ ép 6 ly), cắt vuông <b>{G.PLATE:.0f} × {G.PLATE:.0f} mm</b>, mài cạnh. "
         "Tiệm gỗ hoặc quảng cáo có máy CNC đều cắt được. Bản vẽ trang 2.",
         "2 tấm", "trang 2"),
        ("3", "Tờ nhãn",
         "In màu trên <b>decal nhựa trắng</b> A4, không cần bế (đội tự cắt theo viền xám).",
         "2 tờ", '<span class="file">NHAN_DECAL_A4.pdf</span>'),
        ("4", "Bảng giới thiệu",
         "In <b>decal cán mờ bồi fomex 3 ly</b>, khổ <b>A3 dọc</b> (297 × 420 mm), kèm 1 chân dựng.",
         "1 bảng", '<span class="file">BANG_GIOI_THIEU_A3.pdf</span>'),
    ]
    rows = "".join(f"<tr><td class='num'>{n}</td><td><b>{name}</b><br>{spec}</td><td>{qty}</td><td>{f}</td>"
                   f"<td><div class='blank'></div></td></tr>" for n, name, spec, qty, f in items)
    preview = ve_tam.pair_svg(marks=True)
    return f"""
<section class="page">
  <div class="head"><div><span class="tag">Phiếu đặt in</span>
    <h1 style="margin-top:2mm">Sa bàn EdgeFlow AI</h1>
    <div class="sub">Đội 31µF · VEDC 2026 · 1 tấm bạt {G.SHEET_W:.0f} × {G.SHEET_H:.0f} mm, hai ngã tư J1 – J2</div></div>
    <div class="meta">Ngày lập {NGAY}<br>3 trang · trang 1 và 2 đưa tiệm</div></div>
  <div class="fill"><div>Người đặt:</div><div>SĐT:</div><div>Ngày lấy hàng:</div></div>
  <h2><span class="n">1</span>Hạng mục</h2>
  <table><tr><th></th><th>Hạng mục và quy cách</th><th>Số lượng</th><th>File</th><th>Giá tiệm báo</th></tr>{rows}</table>
  <div class="warn"><b>Lưu ý cho tiệm.</b> In đúng tỉ lệ 100 %, không co giãn, không “fit to page”. File PDF khổ
    {full_w:.0f} × {full_h:.0f} mm, gồm {G.BLEED:.0f} mm tràn lề mỗi cạnh để gấp viền; thành phẩm
    {G.SHEET_W:.0f} × {G.SHEET_H:.0f} mm. Màu mặt đường và vỉa hè phải <b>đều, không sọc ngang</b> (bạt khổ rộng dễ
    ra sọc). Chọn bạt <b>mờ, dày ≥ 440 g/m²</b>, không chọn bạt bóng (đèn hội trường gây lóa).</div>
  <h2><span class="n">2</span>Hình xem trước (J1 trái, J2 phải, mép trước ở dưới)</h2>
  <div class="fig" style="width:128mm;margin:1mm auto 0">{preview}</div>
  <div class="cap">Ô xám là chỗ đặt mạch. Nét đứt là chỗ đặt đế trụ MDF; đế và trụ che hết nét này khi lắp.</div>
  <h2><span class="n">3</span>Đội kiểm khi nhận hàng</h2>
  <ul class="check cols" style="padding-left:0">
    <li>Thước in ở góc trước-trái đo đúng 100 mm ±1</li>
    <li>Bạt {G.SHEET_W:.0f} × {G.SHEET_H:.0f} mm (±3 mm), góc vuông</li>
    <li>Đường Đông–Tây và vạch tim liền, không đứt giữa bạt</li>
    <li>Mặt mờ, màu đều, viền gấp phẳng, không bong keo</li>
    <li>Trải trên bàn: bạt không gợn sóng, không cong mép</li>
    <li>Đế trụ MDF vuông, cạnh {G.PLATE:.0f} mm ±1</li>
  </ul>
  <div class="foot"><span>EdgeFlow AI · đội 31µF</span><span>Phiếu đặt in · 1/3</span></div>
</section>"""


def _plate_svg() -> str:
    """Bản vẽ đế trụ: vị trí trên bạt (tọa độ từ góc trước-trái bạt) và hình đế 1:2 có trụ, 2 ke."""
    s = 0.125                                        # mm giấy / mm thật cho hình bạt
    ox, oy = 6.0, 10.0
    out = []

    def P(x: float, y: float) -> tuple[float, float]:
        return ox + (x + G.TILE) * s, oy + (G.HALF - y) * s

    x0, y0 = P(-G.TILE, G.HALF)
    out.append(f'<rect x="{x0:.2f}" y="{y0:.2f}" width="{G.SHEET_W * s:.2f}" height="{G.SHEET_H * s:.2f}" '
               f'fill="#F6F7F4" stroke="{INK}" stroke-width=".35"/>')
    mid, _ = P(0, 0)
    out.append(f'<path d="M{mid:.2f} {y0:.2f}v{G.SHEET_H * s:.2f}" stroke="{INK3}" stroke-width=".25" '
               f'stroke-dasharray="1.2 .8"/>')
    for n in G.NODES:
        ux0, uy0, ux1, uy1 = G.rect_x(n, G.plate_rect())
        ax, ay = P(G.WORLD_X[n] + ux0, uy1)
        out.append(f'<rect x="{ax:.2f}" y="{ay:.2f}" width="{G.PLATE * s:.2f}" height="{G.PLATE * s:.2f}" '
                   f'fill="#E9ECEF" stroke="{INK}" stroke-width=".4"/>')
        px0, py0, px1, py1 = G.rect_x(n, G.pole_rect())
        bx, by = P(G.WORLD_X[n] + px0, py1)
        out.append(f'<rect x="{bx:.2f}" y="{by:.2f}" width="{(px1 - px0) * s:.2f}" height="{(py1 - py0) * s:.2f}" '
                   f'fill="{INK}"/>')
        cx, cy = P(G.WORLD_X[n], 0)
        out.append(f'<text x="{cx:.2f}" y="{cy:.2f}" class="big">{n}</text>')
        out.append(f'<text x="{ax + G.PLATE * s / 2:.2f}" y="{ay + G.PLATE * s / 2 + 1:.2f}" class="sm">ĐẾ {n}</text>')
        ex = P(G.WORLD_X[n] + (G.to_x(n, G.PLATE_U0) if n == "J2" else 0), 0)[0]
        # khoảng cách từ mép bạt gần nhất tới mép đế
        left = G.WORLD_X[n] + ux0 + G.TILE
        out.append(f'<text x="{ax + G.PLATE * s / 2:.2f}" y="{ay - 1.4:.2f}" class="dim">cách mép bạt trái {left:.0f}'
                   f'</text>' if n == "J1" else
                   f'<text x="{ax + G.PLATE * s / 2:.2f}" y="{ay - 1.4:.2f}" class="dim">cách mép bạt phải '
                   f'{G.TILE - (G.WORLD_X[n] + ux1):.0f}</text>')
    xl, yt = P(-G.TILE, G.HALF)
    xr, yb = P(G.TILE, -G.HALF)

    def dim_h(xa: float, xb: float, y: float, label: str) -> None:
        out.append(f'<path d="M{xa:.2f} {y:.2f}H{xb:.2f}M{xa:.2f} {y - 1.5:.2f}v3M{xb:.2f} {y - 1.5:.2f}v3" '
                   f'stroke="{INK2}" stroke-width=".25"/>')
        out.append(f'<text x="{(xa + xb) / 2:.2f}" y="{y - 1.2:.2f}" class="dim">{label}</text>')

    dim_h(xl, xr, yt - 5, f"{G.SHEET_W:.0f}")
    out.append(f'<path d="M{xr + 4:.2f} {yt:.2f}V{yb:.2f}M{xr + 2.5:.2f} {yt:.2f}h3M{xr + 2.5:.2f} {yb:.2f}h3" '
               f'stroke="{INK2}" stroke-width=".25"/>')
    out.append(f'<text x="{xr + 6:.2f}" y="{(yt + yb) / 2:.2f}" class="dim" style="text-anchor:start">{G.SHEET_H:.0f}</text>')
    out.append(f'<text x="{(xl + xr) / 2:.2f}" y="{yb + 6:.2f}" class="pcap">MÉP TRƯỚC · phía khán giả</text>')

    # hình đế 1:3 (J1; J2 là ảnh gương)
    k, bx0, by0 = 0.34, 12.0, 108.0
    u0, v0, u1, v1 = G.plate_rect()
    out.append(f'<text x="{bx0:.2f}" y="{by0 - 4:.2f}" class="ttl" style="text-anchor:start">Đế trụ J1 nhìn từ trên · 1:3 '
               f'(J2 là ảnh gương)</text>')
    def Q(u: float, v: float) -> tuple[float, float]:
        return bx0 + (u - u0) * k, by0 + (v1 - v) * k
    qx, qy = Q(u0, v1)
    out.append(f'<rect x="{qx:.2f}" y="{qy:.2f}" width="{G.PLATE * k:.2f}" height="{G.PLATE * k:.2f}" fill="#E9ECEF" '
               f'stroke="{INK}" stroke-width=".4"/>')
    pu0, pv0, pu1, pv1 = G.pole_rect()
    ax_, ay_ = Q(pu0, pv1)
    out.append(f'<rect x="{ax_:.2f}" y="{ay_:.2f}" width="{(pu1 - pu0) * k:.2f}" height="{(pv1 - pv0) * k:.2f}" '
               f'fill="{INK}"/>')
    for r in G.bracket_rects():
        rx, ry = Q(r[0], r[3])
        out.append(f'<rect x="{rx:.2f}" y="{ry:.2f}" width="{(r[2] - r[0]) * k:.2f}" height="{(r[3] - r[1]) * k:.2f}" '
                   f'fill="#8E949A" stroke="{INK}" stroke-width=".25"/>')
    ex1 = Q(G.bracket_rects()[1][2], 0)[0]                      # mép phải của ke mặt Đông
    out.append(f'<text x="{ex1 + 1.5:.2f}" y="{ay_ + (pv1 - pv0) * k / 2 + 1:.2f}" class="sm" '
               f'style="text-anchor:start">2 ke góc</text>')
    # gần đường: góc dưới-trái của đế (u nhỏ, y nhỏ); chữ đặt bên phải ke để không đè số 26
    out.append(f'<text x="{ex1 - 4:.2f}" y="{qy + G.PLATE * k - 1.5:.2f}" class="sm" style="text-anchor:start">'
               f'← góc gần tâm ngã tư</text>')
    dim_h(qx, qx + G.PLATE * k, qy + G.PLATE * k + 6, f"{G.PLATE:.0f}")
    out.append(f'<path d="M{qx + G.PLATE * k + 3:.2f} {qy:.2f}V{qy + G.PLATE * k:.2f}M{qx + G.PLATE * k + 1.5:.2f} '
               f'{qy:.2f}h3M{qx + G.PLATE * k + 1.5:.2f} {qy + G.PLATE * k:.2f}h3" stroke="{INK2}" stroke-width=".25"/>')
    out.append(f'<text x="{qx + G.PLATE * k + 5:.2f}" y="{qy + G.PLATE * k / 2:.2f}" class="dim" '
               f'style="text-anchor:start">{G.PLATE:.0f}</text>')
    # tâm trụ cách hai mép gần đường
    out.append(f'<text x="{(qx + ax_) / 2:.2f}" y="{ay_ + (pv1 - pv0) * k / 2 + 1:.2f}" class="sm">'
               f'{G.POLE_U - G.PLATE_U0 - G.POLE.w / 2:.0f}</text>')
    pole_bottom = ay_ + (pv1 - pv0) * k
    out.append(f'<text x="{ax_ + (pu1 - pu0) * k / 2:.2f}" y="{(pole_bottom + qy + G.PLATE * k) / 2 + 1:.2f}" class="sm">'
               f'{G.POLE_Y - G.PLATE_U0 - G.POLE.d / 2:.0f}</text>')
    out.append(f'<text x="{bx0 + G.PLATE * k + 22:.2f}" y="{by0 + 4:.2f}" class="ttl" style="text-anchor:start">Trụ đứng trên đế</text>')
    notes = [f"Đế MDF {G.PLATE_T:.0f} ly, {G.PLATE:.0f} × {G.PLATE:.0f} mm, nặng ~{plate_g():.0f} g.",
             f"Trụ 20 × 20 cách mép gần đường {G.POLE_U - G.PLATE_U0 - G.POLE.w / 2:.0f} mm mỗi phía.",
             "Cần đèn vươn chéo về phía tâm ngã tư;",
             "đế nằm lui về phía ô cỏ.",
             "Bắt 2 ke góc vào đế bằng bu lông đầu chìm,",
             "mặt dưới đế phải phẳng để đặt xuống bạt.",
             "Dán đế xuống bạt bằng băng keo hai mặt."]
    for i, t in enumerate(notes):
        out.append(f'<text x="{bx0 + G.PLATE * k + 22:.2f}" y="{by0 + 11 + i * 4.6:.2f}" class="sm" '
                   f'style="text-anchor:start">{escape(t)}</text>')
    style = (f"<style>.big{{font:700 6px 'Avenir Next Condensed';fill:{INK3};text-anchor:middle;"
             f"dominant-baseline:central;letter-spacing:.3px}}"
             f".dim{{font:600 3px 'Avenir Next';fill:{INK2};text-anchor:middle}}"
             f".sm{{font:500 3px 'Avenir Next';fill:{INK2};text-anchor:middle}}"
             # không đặt tên .cap: <style> trong SVG áp cho cả trang và sẽ đè .cap của chú thích trang 1
             f".pcap{{font:600 2.9px 'Avenir Next';fill:{INK2};text-anchor:middle;letter-spacing:.3px}}"
             f".ttl{{font:600 3.4px 'Avenir Next';fill:{INK}}}</style>")
    return (f'<svg xmlns="http://www.w3.org/2000/svg" style="width:182mm;height:182mm;display:block" '
            f'viewBox="0 0 182 182">{style}{"".join(out)}</svg>')


def plate_g() -> float:
    return G.plate_weight_g()


def page_plate() -> str:
    return f"""
<section class="page">
  <div class="head"><div><span class="tag">Bản vẽ đế trụ</span>
    <h1 style="margin-top:2mm">2 đế MDF {G.PLATE:.0f} × {G.PLATE:.0f} × {G.PLATE_T:.0f} mm</h1>
    <div class="sub">Đơn vị mm · vị trí đế in sẵn nét đứt trên bạt</div></div>
    <div class="meta">Ngày lập {NGAY}<br>Đưa tiệm cùng trang 1</div></div>
  {_plate_svg()}
  <div class="cols" style="margin-top:2mm">
    <div><h2 style="margin-top:0"><span class="n">1</span>Gia công đế</h2>
      <ul>
        <li>2 tấm MDF {G.PLATE_T:.0f} ly vuông {G.PLATE:.0f} mm, sai số ±1 mm, mài cạnh cho khỏi xước bạt.</li>
        <li>Không khoan sẵn: lỗ bắt ke đội khoan khi có ke thật (icdayroi không ghi kích thước ke).</li>
        <li>Mặt dưới đế phải phẳng. Bu lông đầu chìm hoặc khoét lõm đai ốc, để đế nằm sát bạt.</li>
      </ul></div>
    <div><h2 style="margin-top:0"><span class="n">2</span>Vì sao cần đế</h2>
      <ul>
        <li>Bạt mềm, không bắt ốc trực tiếp được. Đế vừa giữ trụ đứng vừa dằn bạt.</li>
        <li>Cần đèn và cụm đèn kéo trụ nghiêng về phía ngã tư. Đế MDF {G.PLATE_T:.0f} ly cho tỉ số chống lật
            ~{G.vn(G.tip_ratio(), 1)} (ước tính khối lượng, cần thử lắc khi lắp thật).</li>
        <li>Bàn đặt bạt phải <b>phẳng, cứng</b>; bạt dán băng keo giấy 4 góc.</li>
      </ul></div>
  </div>
  <div class="foot"><span>EdgeFlow AI · đội 31µF</span><span>Phiếu đặt in · 2/3</span></div>
</section>"""


def page_fit() -> str:
    rows = "".join(f"<tr><td>{escape(c.item)}</td><td>{escape(c.rule)}</td><td>{escape(c.value)}</td>"
                   f"<td class='{'ok' if c.ok else 'bad'}'>{'Đạt' if c.ok else 'Không đạt'}</td></tr>"
                   for c in G.checks())
    devs = [G.BREADBOARD, G.ESP32, G.PI_CASE, G.X1_JACK, G.POLE, G.BRACKET, G.SIGNAL]
    dev_rows = "".join(f"<tr><td>{escape(d.name)}</td><td>{G.vn(d.w)} × {G.vn(d.d)} × {G.vn(d.h)}</td>"
                       f"<td>{escape(d.source)}</td></tr>" for d in devs)
    cab = G.cable_lengths()
    return f"""
<section class="page dense">
  <div class="head"><div><span class="tag" style="background:#2B8A3E">Dành cho đội</span>
    <h1 style="margin-top:2mm">Kiểm khớp thiết bị và lắp đặt</h1>
    <div class="sub">Số tính bằng <span class="file">_nguon/hinh_hoc.py</span>; đổi số đo ở đó rồi chạy lại để sinh mọi file</div>
    </div><div class="meta">Ngày lập {NGAY}<br>Không cần đưa tiệm</div></div>
  <h2><span class="n">1</span>Kiểm khớp từng thiết bị</h2>
  <table><tr><th>Hạng mục</th><th>Điều kiện</th><th>Còn dư</th><th></th></tr>{rows}</table>
  <h2><span class="n">2</span>Kích thước thiết bị đã dùng để tính (ngang × dọc × cao, mm)</h2>
  <table><tr><th>Thiết bị</th><th>Kích thước</th><th>Nguồn số đo</th></tr>{dev_rows}</table>
  <div class="cols" style="margin-top:1mm">
    <div><h2><span class="n">3</span>Lắp đặt</h2><ul>
      <li>Trải bạt lên bàn phẳng, dán băng keo giấy 4 góc. Đặt đế trụ vào nét đứt ở góc sau-trong mỗi ngã tư
          (cách tâm ngã tư {G.POLE_U:.0f} mm mỗi trục), dán băng keo hai mặt.</li>
      <li>ESP32 nằm dọc ở đầu Nam breadboard, cổng micro-USB quay ra mép trước. Breadboard và ESP32 dán lên ô xám.</li>
      <li>Cáp W đi dọc rãnh nhôm ở mặt ngoài trụ, xuống đế, rồi <b>dán băng keo vải sát mặt bạt</b> tới breadboard
          (băng qua đường ở gần giữa bạt). Ước tính {G.vn(cab['W'] / 1000, 2)} m: cắt 1,0 m mỗi sợi.</li>
      <li>Nguồn: adapter 5 V → X1 (J1) → F1 → D1 → X2 trên breadboard J1. Dây P3 sang ESP32 J2 đi qua giữa bạt,
          ~{G.vn(cab['P3'] / 1000, 1)} m, dán băng keo sát mặt bạt.</li>
      <li>Pi 5 đặt ở ô trước-ngoài J2 (hoặc cạnh laptop); chỉ cần nguồn USB-C, không nối dây với ESP32.</li>
    </ul></div>
    <div><h2><span class="n">4</span>Mang đi bằng xe máy</h2><ul>
      <li>Cuộn bạt quanh ống PVC Ø ≥ 10 cm (mặt in hướng ra ngoài), buộc 2 đầu. Dài 60 cm, nặng chưa tới 1 kg.</li>
      <li>2 đế trụ MDF và trụ, cần đèn, mạch: bỏ vào 1 thùng nhỏ. Trụ tháo khỏi đế nếu cần, giữ nguyên dây W.</li>
      <li>Ở hội trường: trải bạt, dán góc, đặt đế trụ vào nét đứt, cắm lại P3, lắc thử trụ.</li>
      <li>Tránh gấp bạt: vết gấp làm đứt màu mặt đường. Cuộn lỏng, không siết dây.</li>
    </ul>
    <div class="warn" style="border-color:#1C7ED6;background:#E7F5FF">Kích thước vỏ Pi và jack X1 là ước tính; ô in
      trên bạt rộng hơn thiết bị {G.PAD_MARGIN:.0f} mm mỗi bên nên lệch vài mm vẫn vừa.</div></div>
  </div>
  <div class="foot"><span>EdgeFlow AI · đội 31µF</span><span>Phiếu đặt in · 3/3</span></div>
</section>"""


def html() -> str:
    return (f'<!doctype html><html lang="vi"><head><meta charset="utf-8"><title>Phiếu đặt in</title>'
            f"<style>{CSS}</style></head><body>{page_order()}{page_plate()}{page_fit()}</body></html>")
