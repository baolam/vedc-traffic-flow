"""In HTML ra PDF bằng Chrome headless, và PDF ra JPG bằng pdftoppm."""
from __future__ import annotations

import subprocess
import tempfile
from pathlib import Path

CHROME = "/Applications/Google Chrome.app/Contents/MacOS/Google Chrome"


def html_to_pdf(html: Path, pdf: Path) -> None:
    """Khổ trang lấy từ @page trong HTML. Dùng profile tạm để không đụng Chrome đang mở."""
    with tempfile.TemporaryDirectory() as profile:
        subprocess.run([CHROME, "--headless=new", "--disable-gpu", "--no-pdf-header-footer",
                        f"--user-data-dir={profile}", "--virtual-time-budget=3000",
                        f"--print-to-pdf={pdf}", html.resolve().as_uri()],
                       check=True, capture_output=True, timeout=180)
    if not pdf.exists() or pdf.stat().st_size == 0:
        raise RuntimeError(f"Chrome không xuất được {pdf}")


def pdf_to_jpg(pdf: Path, jpg: Path, dpi: int) -> None:
    stem = jpg.with_suffix("")
    subprocess.run(["pdftoppm", "-r", str(dpi), "-jpeg", "-jpegopt", "quality=92", "-singlefile",
                    str(pdf), str(stem)], check=True, timeout=300)


def page_size_mm(pdf: Path) -> list[tuple[float, float]]:
    """Kích thước từng trang (mm) đọc bằng pdfinfo."""
    out = subprocess.run(["pdfinfo", "-f", "1", "-l", "99", str(pdf)], check=True, capture_output=True,
                         text=True).stdout
    sizes = []
    for line in out.splitlines():
        if line.startswith("Page") and "size:" in line:
            w, h = line.split("size:")[1].split("pts")[0].split("x")
            sizes.append((float(w) * 25.4 / 72, float(h) * 25.4 / 72))
    return sizes


def fonts_embedded(pdf: Path) -> bool:
    out = subprocess.run(["pdffonts", str(pdf)], check=True, capture_output=True, text=True).stdout
    rows = out.splitlines()[2:]
    return all(r.split()[-5] == "yes" for r in rows if r.strip())
