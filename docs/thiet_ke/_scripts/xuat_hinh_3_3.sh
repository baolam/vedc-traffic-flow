#!/usr/bin/env bash
# Xuất 4 trang của EdgeFlow_3.3_kien_truc.drawio ra PNG (2x, có nhúng sơ đồ) và SVG.
# PNG có nhúng sơ đồ (-e): mở thẳng file PNG bằng draw.io vẫn sửa được.
# Cần draw.io desktop: brew install --cask drawio
set -euo pipefail

DIR="$(cd "$(dirname "$0")/../3.3_kien_truc" && pwd)"
SRC="$DIR/EdgeFlow_3.3_kien_truc.drawio"
NAMES=(H3.1_so_do_khoi H3.2_phan_cung_dau_noi H3.3_kien_truc_phan_mem H3.4_may_trang_thai_an_toan)

for i in "${!NAMES[@]}"; do
  page=$((i + 1))
  name="${NAMES[$i]}"
  drawio -x -f png -s 2 -b 24 -e -p "$page" -o "$DIR/$name.png" "$SRC" >/dev/null 2>&1
  drawio -x -f svg -b 24 -p "$page" -o "$DIR/$name.svg" "$SRC" >/dev/null 2>&1
  echo "trang $page -> $name.png / .svg"
done
