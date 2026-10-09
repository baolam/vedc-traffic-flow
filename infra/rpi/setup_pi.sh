#!/usr/bin/env bash
# One-time setup of the EdgeFlow vision node on Raspberry Pi 5 + Camera Module 3
# (Raspberry Pi OS Trixie 64-bit: its apt OpenCV 4.10 runs YOLOv8/11 ONNX, Bookworm's 4.6 cannot).
# Run from anywhere inside the repo:
#   bash infra/rpi/setup_pi.sh            # install deps, venv, .env.rpi, chrony
#   bash infra/rpi/setup_pi.sh --service  # ...and install + enable the systemd unit
set -euo pipefail

REPO_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
VENV_DIR="${VENV_DIR:-$REPO_DIR/.venv-pi}"
INSTALL_SERVICE=false
[[ "${1:-}" == "--service" ]] && INSTALL_SERVICE=true

echo "== Free space on / (needs a few hundred MB)"
df -h /

echo "== System packages (Picamera2/libcamera come from apt, not pip)"
sudo apt-get update
sudo apt-get install -y python3-picamera2 python3-opencv python3-venv rpicam-apps mosquitto-clients chrony

echo "== Camera check"
rpicam-hello --list-cameras || echo "WARNING: no camera listed; check the 22-pin cable orientation and reseat it."

echo "== Python venv with system site-packages (reuses apt numpy/opencv/picamera2)"
python3 -m venv --system-site-packages "$VENV_DIR"
"$VENV_DIR/bin/pip" install --upgrade pip
# Do NOT pip install services/vision/requirements.txt here: a pip numpy/opencv would shadow
# the apt builds that picamera2 is compiled against and break it with an ABI error.
"$VENV_DIR/bin/pip" install "paho-mqtt>=1.6.1" "pydantic>=2.0" "pydantic-settings>=2.0" "jsonschema>=4.0"
"$VENV_DIR/bin/python" -c "import picamera2, cv2, numpy, paho.mqtt.client; print('imports OK, cv2', cv2.__version__, 'numpy', numpy.__version__)"

echo "== OpenCV DNN version (raw YOLOv8/11 ONNX fails forward() on OpenCV 4.6/4.7)"
if ! "$VENV_DIR/bin/python" -c "import sys, cv2; sys.exit(tuple(map(int, cv2.__version__.split('.')[:2])) < (4, 8))"; then
  echo "ERROR: OpenCV $("$VENV_DIR/bin/python" -c 'import cv2; print(cv2.__version__)') cannot run the YOLO model (needs >= 4.8)." >&2
  echo "  Fix: reflash with Raspberry Pi OS Trixie 64-bit (apt python3-opencv 4.10)." >&2
  echo "  Bookworm fallback, keeps the apt numpy picamera2 is built against:" >&2
  echo "    $VENV_DIR/bin/pip install --no-deps opencv-python-headless==4.10.0.84" >&2
  exit 1
fi

echo "== Runtime config"
if [[ ! -f "$REPO_DIR/.env.rpi" ]]; then
  cp "$REPO_DIR/.env.rpi.example" "$REPO_DIR/.env.rpi"
  echo "Created .env.rpi from the example: set MQTT_HOST, VIDEO_SOURCE=picamera, model path."
fi

echo "== chrony: serve LAN time so ESP32/laptop clocks match the Pi (works without internet)"
sudo tee /etc/chrony/conf.d/edgeflow.conf >/dev/null <<'CONF'
allow 192.168.0.0/16
allow 10.0.0.0/8
local stratum 10
CONF
sudo systemctl restart chrony

if $INSTALL_SERVICE; then
  echo "== systemd unit"
  sed -e "s#@USER@#$USER#g" -e "s#@REPO_DIR@#$REPO_DIR#g" -e "s#@VENV_DIR@#$VENV_DIR#g" \
    "$REPO_DIR/infra/rpi/edgeflow-vision.service" | sudo tee /etc/systemd/system/edgeflow-vision.service >/dev/null
  sudo systemctl daemon-reload
  sudo systemctl enable --now edgeflow-vision
  echo "Logs: journalctl -u edgeflow-vision -f"
fi

echo "== Done. Manual run: $VENV_DIR/bin/python services/vision/main.py --video picamera --mqtt-host <BROKER_IP> --node-id J1"
