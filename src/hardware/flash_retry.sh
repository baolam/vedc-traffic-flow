#!/bin/bash
# usage: flash_retry.sh J1|J2|J3|J4|J5 [max_tries]     (build first: pio run -e <node>)
# Nạp trực tiếp bằng esptool ở 115200, tự chờ cổng và thử lại khi USB rớt.
# Cổng: CP210x hoặc CH340 tuỳ lô DevKitC-32U (cả CH340 của board NodeMCU cũ). Cắm 1 board mỗi lần,
# hoặc chỉ định cổng: PORT=/dev/cu.usbserial-0001 bash flash_retry.sh J3
ENVN=${1:?J1|J2|J3|J4|J5}; MAX=${2:-15}
HW=$(cd "$(dirname "$0")" && pwd)
B=$HW/.pio/build/$ENVN
[ -f "$B/firmware.bin" ] || { echo "Chưa build $ENVN: cd $HW && uvx --from platformio pio run -e $ENVN"; exit 2; }
BA=$HOME/.platformio/packages/framework-arduinoespressif32/tools/partitions/boot_app0.bin
ET=$HOME/.platformio/packages/tool-esptoolpy/esptool.py
for i in $(seq 1 "$MAX"); do
  P=${PORT:-$(ls /dev/cu.wchusbserial* /dev/cu.SLAB_USBtoUART* /dev/cu.usbserial-* /dev/ttyUSB* 2>/dev/null | head -1)}
  if [ -z "$P" ] || [ ! -e "$P" ]; then sleep 0.3; continue; fi
  echo "[try $i] $P"
  OUT=$(uvx --from platformio python "$ET" --chip esp32 --port "$P" --baud 115200 \
    --before default_reset --after hard_reset write_flash -z --flash_mode dio --flash_freq 40m --flash_size 4MB \
    0x1000 $B/bootloader.bin 0x8000 $B/partitions.bin 0xe000 $BA 0x10000 $B/firmware.bin 2>&1)
  if echo "$OUT" | grep -q "Hash of data verified"; then echo "OK: $ENVN flashed on try $i"; exit 0; fi
  echo "$OUT" | grep -iE "error|fatal|failed" | head -2
  sleep 1
done
echo "FAILED after $MAX tries"; exit 1
