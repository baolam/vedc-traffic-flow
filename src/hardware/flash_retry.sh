#!/bin/bash
# usage: flash_retry.sh J1|J2 [max_tries]
# Nạp trực tiếp bằng esptool ở 115200, tự chờ cổng và thử lại khi USB rớt.
ENVN=${1:?J1|J2}; MAX=${2:-15}
HW=/Users/dominhhien/Documents/AI/VEDC/vedc-traffic-flow/src/hardware
B=$HW/.pio/build/$ENVN
BA=$HOME/.platformio/packages/framework-arduinoespressif32/tools/partitions/boot_app0.bin
ET=$HOME/.platformio/packages/tool-esptoolpy/esptool.py
for i in $(seq 1 "$MAX"); do
  PORT=$(ls /dev/cu.wchusbserial* 2>/dev/null | head -1)
  if [ -z "$PORT" ]; then sleep 0.3; continue; fi
  echo "[try $i] $PORT"
  OUT=$(uvx --from platformio python "$ET" --chip esp32 --port "$PORT" --baud 115200 \
    --before default_reset --after hard_reset write_flash -z --flash_mode dio --flash_freq 40m --flash_size 4MB \
    0x1000 $B/bootloader.bin 0x8000 $B/partitions.bin 0xe000 $BA 0x10000 $B/firmware.bin 2>&1)
  if echo "$OUT" | grep -q "Hash of data verified"; then echo "OK: $ENVN flashed on try $i"; exit 0; fi
  echo "$OUT" | grep -iE "error|fatal|failed" | head -2
  sleep 1
done
echo "FAILED after $MAX tries"; exit 1
