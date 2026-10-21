#!/usr/bin/env bash
# Xuất 4 trang của EdgeFlow_ban_ve_mach.drawio (Phụ lục A) ra PNG (2x, có nhúng sơ đồ) và SVG.
# PNG có nhúng sơ đồ (-e): mở thẳng file PNG bằng draw.io vẫn sửa được.
# Cần draw.io desktop: brew install --cask drawio
set -euo pipefail

DIR="$(cd "$(dirname "$0")/../3.3_kien_truc" && pwd)"
SRC="$DIR/EdgeFlow_ban_ve_mach.drawio"
NAMES=(HA.1_tong_the_bo_tri_dau_noi HA.2_nguyen_ly_nut_chap_hanh HA.3_dau_noi_khoi_AI_bien HA.4_di_day_len_tru)

for i in "${!NAMES[@]}"; do
  page=$((i + 1))
  name="${NAMES[$i]}"
  drawio -x -f png -s 2 -b 0 -e -p "$page" -o "$DIR/$name.png" "$SRC" >/dev/null 2>&1
  drawio -x -f svg -b 0 -p "$page" -o "$DIR/$name.svg" "$SRC" >/dev/null 2>&1
  echo "trang $page -> $name.png / .svg"
done
