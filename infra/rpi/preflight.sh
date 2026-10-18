#!/usr/bin/env bash
# Pre-flight check of the EdgeFlow vision node on Raspberry Pi 5, before starting the service,
# a benchmark or a demo run. Read-only: it starts no camera stream and publishes nothing.
#   bash infra/rpi/preflight.sh                 # reads .env.rpi
#   ENV_FILE=/path/to/env bash infra/rpi/preflight.sh
# Prints PASS/WARN/FAIL per check; exit 1 if anything FAILs.
set -uo pipefail

REPO_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
VENV_DIR="${VENV_DIR:-$REPO_DIR/.venv-pi}"
ENV_FILE="${ENV_FILE:-$REPO_DIR/.env.rpi}"
[[ "$ENV_FILE" = /* ]] || ENV_FILE="$PWD/$ENV_FILE"  # some checks run from services/vision
PY="$VENV_DIR/bin/python"
FAILS=0
WARNS=0

pass() { printf '  [PASS] %s\n' "$*"; }
warn() { printf '  [WARN] %s\n' "$*"; WARNS=$((WARNS + 1)); }
fail() { printf '  [FAIL] %s\n' "$*"; FAILS=$((FAILS + 1)); }
have() { command -v "$1" >/dev/null 2>&1; }

# Last KEY=value in the env file, without sourcing (no shell execution of its content)
env_get() {
  local value
  value="$(grep -E "^[[:space:]]*$1=" "$ENV_FILE" 2>/dev/null | tail -n 1 | cut -d= -f2- | sed -e 's/[[:space:]]*#.*$//' -e 's/^"//' -e 's/"$//')"
  printf '%s' "${value:-${2:-}}"
}

echo "== Board and OS"
CODENAME="$(. /etc/os-release 2>/dev/null && echo "${VERSION_CODENAME:-unknown}")"
case "$CODENAME" in
  trixie) pass "Raspberry Pi OS / Debian $CODENAME" ;;
  bookworm) warn "Debian bookworm: apt OpenCV is 4.6 and cannot run the YOLO model (see the OpenCV check)" ;;
  *) warn "OS codename '${CODENAME:-unknown}' (expected trixie)" ;;
esac
MODEL="$({ tr -d '\0' </sys/firmware/devicetree/base/model; } 2>/dev/null || true)"
if [[ "$MODEL" == *"Raspberry Pi 5"* ]]; then pass "$MODEL"; else warn "board '${MODEL:-unknown}' is not a Raspberry Pi 5"; fi

echo "== Power, temperature, disk"
if have vcgencmd; then
  THROTTLED="$(vcgencmd get_throttled 2>/dev/null | cut -d= -f2)"
  if [[ ! "$THROTTLED" =~ ^0x[0-9a-fA-F]+$ ]]; then
    warn "could not read vcgencmd get_throttled"
  elif [[ "$THROTTLED" == "0x0" ]]; then
    pass "no under-voltage or throttling since boot (get_throttled=0x0)"
  elif (( THROTTLED & 0xF )); then
    fail "under-voltage/throttling NOW (get_throttled=$THROTTLED): use the 5V 5A USB-C supply, check the cable"
  else
    warn "under-voltage/throttling happened since boot (get_throttled=$THROTTLED); reboot clears it, then watch again"
  fi
  EXT5V="$(vcgencmd pmic_read_adc EXT5V_V 2>/dev/null | sed -n 's/.*=\([0-9.]*\)V.*/\1/p')"
  if [[ -n "$EXT5V" ]]; then
    if awk -v v="$EXT5V" 'BEGIN { exit !(v >= 4.9) }'; then pass "USB-C input ${EXT5V} V"; else warn "USB-C input only ${EXT5V} V (want >= 4.9 V under load)"; fi
  fi
  TEMP="$(vcgencmd measure_temp 2>/dev/null | sed -n 's/temp=\([0-9.]*\).*/\1/p')"
  if [[ -n "$TEMP" ]]; then
    if awk -v t="$TEMP" 'BEGIN { exit !(t < 75) }'; then pass "SoC ${TEMP} C"; else warn "SoC ${TEMP} C: check the fan/heatsink before a long run"; fi
  fi
else
  fail "vcgencmd not found (not Raspberry Pi OS?)"
fi
FREE_MB="$(df -Pm / | awk 'NR == 2 { print $4 }')"
if (( FREE_MB >= 1024 )); then pass "${FREE_MB} MB free on /"; else warn "only ${FREE_MB} MB free on / (logs, dataset frames)"; fi

echo "== Python environment ($VENV_DIR)"
if [[ ! -x "$PY" ]]; then
  fail "no venv at $VENV_DIR: run bash infra/rpi/setup_pi.sh"
else
  for module in picamera2 numpy paho.mqtt.client pydantic_settings jsonschema; do
    if "$PY" -c "import $module" 2>/dev/null; then pass "import $module"; else fail "import $module (re-run setup_pi.sh)"; fi
  done
  CV="$("$PY" -c 'import cv2; print(cv2.__version__)' 2>/dev/null || true)"
  if [[ -z "$CV" ]]; then
    fail "import cv2"
  elif "$PY" -c 'import sys, cv2; sys.exit(tuple(map(int, cv2.__version__.split(".")[:2])) < (4, 8))'; then
    pass "OpenCV $CV (>= 4.8 runs YOLOv8/11 ONNX)"
  else
    fail "OpenCV $CV < 4.8 cannot run the YOLO model: use Raspberry Pi OS Trixie"
  fi
fi

echo "== Camera"
if have rpicam-hello; then
  CAMERAS="$(rpicam-hello --list-cameras 2>&1 || true)"
  if grep -q "imx708_wide" <<<"$CAMERAS"; then
    pass "Camera Module 3 Wide detected (imx708_wide)"
  elif grep -q "imx708" <<<"$CAMERAS"; then
    warn "Camera Module 3 detected but NOT the Wide variant: it may not cover both intersections"
  elif grep -qE "^[[:space:]]*[0-9]+ :" <<<"$CAMERAS"; then
    warn "a camera is listed but it is not Camera Module 3: $(grep -E '^[[:space:]]*[0-9]+ :' <<<"$CAMERAS" | head -n 1)"
  else
    fail "no camera listed: reseat the 22-pin cable (contacts facing the board) in CAM/DISP 0"
  fi
else
  fail "rpicam-hello not found (sudo apt install rpicam-apps)"
fi
if have systemctl && systemctl is-active --quiet edgeflow-vision 2>/dev/null; then
  warn "edgeflow-vision is running and holds the camera: stop it before benchmark.py or capture_dataset.py"
fi

echo "== Runtime config ($ENV_FILE)"
if [[ ! -f "$ENV_FILE" ]]; then
  fail "missing $ENV_FILE: cp .env.rpi.example .env.rpi and edit it"
else
  pass "found $(basename "$ENV_FILE")"
  # systemd's EnvironmentFile keeps an inline "# comment" in the value and the service parses every
  # variable at import, so read the file the way systemd does and build the service's settings once
  if [[ -x "$PY" ]]; then
    if OUT="$(cd "$REPO_DIR/services/vision" && "$PY" - "$ENV_FILE" 2>&1 <<'PY'
import os, re, sys
for number, raw in enumerate(open(sys.argv[1], encoding="utf-8"), 1):
    line = raw.strip()
    if not line or line[0] in "#;" or "=" not in line:
        continue
    key, value = (part.strip() for part in line.split("=", 1))
    if len(value) >= 2 and value[0] == value[-1] and value[0] in "\"'":
        value = value[1:-1]
    elif re.search(r"\s#", value):
        sys.exit(f"line {number}: {key}={value!r}: systemd keeps an inline comment in the value, move it to its own line")
    os.environ[key] = value
try:
    from config import Settings
    s = Settings()
except Exception as error:
    details = error.errors() if hasattr(error, "errors") else []
    reason = "; ".join(f"{str(d['loc'][0]).upper()}={d.get('input')!r}: {d['msg']}" for d in details)
    sys.exit(f"the service would crash at start: {reason or error}")
print(f"service settings load as systemd passes them: video={s.video_source}, "
      f"nodes={s.vision_node_ids or s.vision_node_id}, broker={s.mqtt_host}:{s.mqtt_port}, "
      f"model={s.detection_model_path or 'none (motion baseline)'} @ {s.detector_input_size}")
PY
    )"; then
      pass "$(tail -n 1 <<<"$OUT")"
    else
      fail "$(tail -n 1 <<<"$OUT")"
    fi
  fi
  VIDEO="$(env_get VIDEO_SOURCE synthetic)"
  if [[ "$VIDEO" =~ ^(picamera|picamera2|csi)$ ]]; then pass "VIDEO_SOURCE=$VIDEO"; else warn "VIDEO_SOURCE=$VIDEO (the CSI camera needs picamera)"; fi
  if [[ -n "$(env_get CAMERA_LENS_POSITION)" ]]; then
    pass "focus locked (CAMERA_LENS_POSITION=$(env_get CAMERA_LENS_POSITION))"
  else
    warn "CAMERA_LENS_POSITION empty: autofocus breathing shifts vehicles relative to the ROIs"
  fi

  echo "== Model"
  MODEL_PATH="$(env_get DETECTION_MODEL_PATH)"
  INPUT_SIZE="$(env_get DETECTOR_INPUT_SIZE 640)"
  if [[ -z "$MODEL_PATH" ]]; then
    warn "DETECTION_MODEL_PATH empty: motion baseline only (development, not the learned detector the plan requires)"
  else
    [[ "$MODEL_PATH" = /* ]] || MODEL_PATH="$REPO_DIR/$MODEL_PATH"
    if [[ ! -f "$MODEL_PATH" ]]; then
      fail "model not found: $MODEL_PATH (scp it from the Mac, see KE_HOACH_DEPLOY.md)"
    else
      SUM="$(sha256sum "$MODEL_PATH" 2>/dev/null || shasum -a 256 "$MODEL_PATH")"
      SUM="${SUM%% *}"
      LISTED="$(awk -v name="$(basename "$MODEL_PATH")" '$2 == name { print $1 }' "$REPO_DIR/models/SHA256SUMS" 2>/dev/null)"
      if [[ -z "$LISTED" ]]; then
        warn "$(basename "$MODEL_PATH") is not in models/SHA256SUMS (sha256 ${SUM:0:12}...): record it once validated"
      elif [[ "$LISTED" == "$SUM" ]]; then
        pass "$(basename "$MODEL_PATH") matches models/SHA256SUMS (${SUM:0:12}...)"
      else
        fail "$(basename "$MODEL_PATH") sha256 ${SUM:0:12}... differs from models/SHA256SUMS ${LISTED:0:12}...: corrupt or wrong copy"
      fi
      if [[ -x "$PY" ]]; then
        # Same load path as the service: one blank forward catches OpenCV, imgsz and class-count mismatches
        if OUT="$(cd "$REPO_DIR/services/vision" && "$PY" - "$MODEL_PATH" "$INPUT_SIZE" \
            "$(env_get DETECTOR_OUTPUT_FORMAT yolov8)" "$(env_get DETECTOR_NUM_CLASSES 80)" \
            "$(env_get DETECTOR_VEHICLE_CLASSES 2,3,5,7)" 2>&1 <<'PY'
import sys, time
from detector import VehicleDetector
path, size, fmt, classes, vehicles = sys.argv[1:6]
started = time.perf_counter()
VehicleDetector(path, input_size=int(size), output_format=fmt, num_classes=int(classes),
                vehicle_classes=tuple(int(c) for c in vehicles.split(",")))
print(f"loads and runs at DETECTOR_INPUT_SIZE={size} ({(time.perf_counter() - started) * 1000:.0f} ms incl. self-test)")
PY
        )"; then
          pass "$(tail -n 1 <<<"$OUT")"
        else
          fail "detector self-test: $( (grep -E 'Error|error' <<<"$OUT" || echo "$OUT") | tail -n 1)"
        fi
      fi
    fi
  fi

  echo "== ROI calibration"
  NODES="$(env_get VISION_NODE_IDS)"
  ROI="$(env_get ROI_CONFIG_PATH)"
  if [[ -z "$NODES" ]]; then
    warn "VISION_NODE_IDS empty: only $(env_get VISION_NODE_ID J1) gets telemetry, the other node stays in fallback"
  elif [[ -z "$ROI" ]]; then
    fail "VISION_NODE_IDS=$NODES needs ROI_CONFIG_PATH"
  else
    if [[ "$ROI" == *example_two_nodes* ]]; then
      warn "ROI_CONFIG_PATH is the uncalibrated example: draw the real polygons with roi_calibrate.py"
    fi
    if [[ -x "$PY" ]] && OUT="$(cd "$REPO_DIR" && "$PY" services/vision/roi_calibrate.py check --config "$ROI" --nodes "$NODES" \
        --topology "$(env_get EDGEFLOW_TOPOLOGY four_intersection_v1)" 2>&1)"; then
      pass "$(tail -n 1 <<<"$OUT")"
    else
      fail "ROI check: $(tail -n 1 <<<"${OUT:-no python}")"
    fi
  fi

  echo "== Network and time"
  HOST="$(env_get MQTT_HOST localhost)"
  PORT="$(env_get MQTT_PORT 1883)"
  TIMEOUT=(); have timeout && TIMEOUT=(timeout 3)
  if ${TIMEOUT[@]+"${TIMEOUT[@]}"} bash -c "exec 3<>/dev/tcp/$HOST/$PORT" 2>/dev/null; then
    pass "MQTT broker reachable at $HOST:$PORT"
  else
    fail "cannot reach MQTT broker $HOST:$PORT (laptop on? same LAN? firewall port 1883?)"
  fi
fi
if have chronyc; then
  if chronyc tracking 2>/dev/null | grep -q "Leap status *: Normal"; then
    pass "chrony synchronised"
  else
    # 'local stratum 10' still serves time to the ESP32s offline, but a Pi without an RTC battery may boot with a wrong clock
    warn "chrony not synchronised, Pi clock reads $(date '+%F %T %Z'). If that is wrong (offline, no RTC battery), set it from the laptop: ssh -t ${USER:-pi}@$(hostname).local \"sudo date -s @\$(date +%s)\""
  fi
else
  warn "chronyc not found: ESP32 command expiry needs a LAN time source (setup_pi.sh installs chrony)"
fi

echo
echo "Preflight: $FAILS FAIL, $WARNS WARN"
(( FAILS == 0 ))
