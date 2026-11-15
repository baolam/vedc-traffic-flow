"""Sinh 3.3_kien_truc/EdgeFlow_ban_ve_mach.drawio (4 trang) cho Phụ lục A của báo cáo.

  A.1  Sơ đồ bố trí và đấu nối tổng thể (mặt bằng sa bàn + bảng cáp)      to_a1_tong_the.py
  A.2  Sơ đồ nguyên lý nút chấp hành J1 (J2 giống hệt)                      to_a2_nguyen_ly.py
  A.3  Sơ đồ đấu nối khối AI biên (Pi 5 + 2 camera)                         to_a3_khoi_ai.py
  A.4  Sơ đồ đi dây lên trụ (breadboard, mặt đứng trụ, cụm đèn, lõi W1)     to_a4_tru.py

Thành phần dùng chung (khung tờ, khung tên, ký hiệu, bảng màu): ban_ve_mach_chung.py.
Spec: _ghi_chu/2026-10-11-ban-ve-mach-design.md. Chân GPIO bám
vedc-traffic-flow/src/hardware/firmware/esp32_signal_controller.ino: script dừng nếu bảng CHAN lệch firmware.
Bố trí và kích thước trụ lấy từ 4.4_hinh_minh_hoa/blender/bo_tri.py (phương án đề xuất).

Không ghi đè file .drawio đã có (đội có thể đã sửa), trừ khi chạy với --ghi-de.
  python3 _scripts/tao_drawio_ban_ve_mach.py                 # tạo mới
  python3 _scripts/tao_drawio_ban_ve_mach.py --out /tmp/x.drawio
"""
from __future__ import annotations

import argparse
import sys
import xml.etree.ElementTree as ET
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "3.3_kien_truc" / "EdgeFlow_ban_ve_mach.drawio"
sys.path.insert(0, str(ROOT / "4.4_hinh_minh_hoa" / "blender"))   # bo_tri.py, không phụ thuộc Blender

import to_a1_tong_the  # noqa: E402
import to_a2_nguyen_ly  # noqa: E402
import to_a3_khoi_ai  # noqa: E402
import to_a4_tru  # noqa: E402
from ban_ve_mach_chung import CHAN, doc_chan_firmware, kiem_chan  # noqa: E402
from drawio_lib import write_drawio  # noqa: E402

CAC_TO = (to_a1_tong_the, to_a2_nguyen_ly, to_a3_khoi_ai, to_a4_tru)


def kiem_xml(path: Path) -> list[str]:
    """Mỗi trang parse được; mọi source/target của edge trỏ tới id có thật trong trang."""
    loi = []
    for diagram in ET.parse(path).getroot().iter("diagram"):
        cells = list(diagram.iter("mxCell"))
        ids = {c.get("id") for c in cells}
        for c in cells:
            for attr in ("source", "target"):
                ref = c.get(attr)
                if ref and ref not in ids:
                    loi.append(f"{diagram.get('name')}: {c.get('id')}.{attr} → '{ref}' không tồn tại")
    return loi


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--out", type=Path, default=OUT)
    ap.add_argument("--ghi-de", action="store_true", help="cho phép ghi đè file .drawio đã có")
    args = ap.parse_args()

    loi = kiem_chan(CHAN, doc_chan_firmware())
    if loi:
        print("Bảng chân lệch firmware, không vẽ:\n  " + "\n  ".join(loi), file=sys.stderr)
        return 1
    if args.out.exists() and not args.ghi_de:
        print(f"{args.out} đã có (có thể đội đã sửa). Không ghi đè; thêm --ghi-de nếu chắc chắn.", file=sys.stderr)
        return 2

    write_drawio(str(args.out), [to.page() for to in CAC_TO])
    loi = kiem_xml(args.out)
    if loi:
        print("XML lỗi:\n  " + "\n  ".join(loi), file=sys.stderr)
        return 1
    print(f"đã ghi {args.out} ({len(CAC_TO)} trang)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
