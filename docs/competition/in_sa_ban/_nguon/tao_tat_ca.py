"""Sinh toàn bộ file mang đi in vào VEDC/in_sa_ban/ rồi tự kiểm kích thước trang, font và khớp thiết bị.

Chạy:  python3 in_sa_ban/_nguon/tao_tat_ca.py      (Python hệ thống, không cần thư viện ngoài;
       cần Google Chrome, pdftoppm, pdfinfo, pdffonts của poppler)
"""
from __future__ import annotations

import sys
from pathlib import Path

import hinh_hoc as G
import trang_a3
import trang_nhan
import trang_phieu
import ve_tam
from xuat_pdf import fonts_embedded, html_to_pdf, page_size_mm, pdf_to_jpg

OUT = Path(__file__).resolve().parents[1]
HTML_DIR = OUT / "_nguon" / "html"
PREVIEW_DPI = 60
SIZE_TOL = 0.5                                  # mm; Chrome làm tròn khổ trang theo điểm ảnh


def _write_html(name: str, text: str) -> Path:
    HTML_DIR.mkdir(exist_ok=True)
    p = HTML_DIR / f"{name}.html"
    p.write_text(text, encoding="utf-8")
    return p


def _sheet_html() -> str:
    w, h = G.SHEET_W + 2 * G.BLEED, G.SHEET_H + 2 * G.BLEED
    return (f'<!doctype html><html lang="vi"><head><meta charset="utf-8"><title>Sa bàn bạt</title>'
            f"<style>@page{{size:{w:.0f}mm {h:.0f}mm;margin:0}}html,body{{margin:0}}svg{{display:block}}"
            f"</style></head><body>{ve_tam.sheet_svg()}</body></html>")


def build() -> list[tuple[Path, tuple[float, float], int]]:
    """(pdf, khổ mong đợi mm, số trang mong đợi)."""
    side = (G.SHEET_W + 2 * G.BLEED, G.SHEET_H + 2 * G.BLEED)
    jobs: list[tuple[str, str, tuple[float, float], int]] = [
        ("SA_BAN_BAT_1200x600", _sheet_html(), side, 1),
        ("PHIEU_DAT_IN", trang_phieu.html(), (210, 297), 3),
        ("NHAN_DECAL_A4", trang_nhan.html(), (210, 297), 1),
        ("BANG_GIOI_THIEU_A3", trang_a3.html(), (297, 420), 1)]
    out = []
    for name, text, size, pages in jobs:
        pdf = OUT / f"{name}.pdf"
        html_to_pdf(_write_html(name, text), pdf)
        out.append((pdf, size, pages))
    pdf_to_jpg(OUT / "SA_BAN_BAT_1200x600.pdf", OUT / "SA_BAN_BAT_1200x600_60dpi.jpg", PREVIEW_DPI)
    return out


def verify(results: list[tuple[Path, tuple[float, float], int]]) -> bool:
    ok = True
    for c in G.checks():
        if not c.ok:
            print(f"LỖI khớp thiết bị: {c.item} ({c.rule}) → {c.value}")
            ok = False
    for pdf, (w, h), pages in results:
        sizes = page_size_mm(pdf)
        good_size = all(abs(a - w) <= SIZE_TOL and abs(b - h) <= SIZE_TOL for a, b in sizes)
        good = good_size and len(sizes) == pages and fonts_embedded(pdf)
        ok &= good
        got = ", ".join(f"{a:.1f}×{b:.1f}" for a, b in sizes[:1])
        print(f"{'ĐẠT' if good else 'LỖI'}  {pdf.name}: {len(sizes)} trang (cần {pages}), {got} mm "
              f"(cần {w:.0f}×{h:.0f}), font nhúng: {fonts_embedded(pdf)}")
    return ok


if __name__ == "__main__":
    sys.exit(0 if verify(build()) else 1)
