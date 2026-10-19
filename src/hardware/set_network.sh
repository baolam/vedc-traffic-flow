#!/usr/bin/env bash
# Point the ESP32 firmware at another Wi-Fi network (home Wi-Fi now, a phone hotspot at the venue):
# writes src/hardware/secrets.ini, builds J1 and J2, and prints what is left to do on the boards and the Pi.
#
#   bash src/hardware/set_network.sh "<SSID>" "<password>"              # broker = this laptop's current IP
#   bash src/hardware/set_network.sh "<SSID>" "<password>" 172.20.10.4  # explicit broker IP
#
# Run it while the laptop is already connected to that network: the broker IP is read from the interface
# that carries the default route. The ESP32 only sees 2.4 GHz: on an iPhone hotspot turn on
# "Maximize Compatibility"; on Android pick the 2.4 GHz band.
# The previous secrets.ini is kept at ~/.edgeflow/secrets.ini.prev (outside the repo, never synced to the Pi).
set -euo pipefail

HW_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
SSID="${1:-}"
PASS="${2:-}"
BROKER="${3:-}"

if [[ -z "$SSID" || -z "$PASS" ]]; then
  sed -n '2,12p' "$0" | sed 's/^# \{0,1\}//'
  exit 2
fi
# The values become C string literals inside a PlatformIO build flag: quotes and backslashes would break it
for value in "$SSID" "$PASS" "$BROKER"; do
  if [[ "$value" == *[\"\'\\]* ]]; then
    echo "SSID/password/broker must not contain quotes or backslashes (rename the hotspot, e.g. EdgeFlow)" >&2
    exit 2
  fi
done
if (( ${#PASS} < 8 )); then
  echo "WPA2 passwords are at least 8 characters" >&2
  exit 2
fi

laptop_ip() {
  local iface
  if [[ "$(uname)" == "Darwin" ]]; then
    iface="$(route -n get default 2>/dev/null | awk '/interface:/ {print $2}')"
    [[ -n "$iface" ]] && ipconfig getifaddr "$iface" 2>/dev/null
  else
    ip route get 1.1.1.1 2>/dev/null | awk '{for (i = 1; i <= NF; i++) if ($i == "src") print $(i + 1)}'
  fi
}
if [[ -z "$BROKER" ]]; then
  BROKER="$(laptop_ip || true)"
  if [[ -z "$BROKER" ]]; then
    echo "Cannot find this laptop's IP (no default route?). Connect to the network first or pass the broker IP." >&2
    exit 1
  fi
fi
if ! [[ "$BROKER" =~ ^[0-9]{1,3}(\.[0-9]{1,3}){3}$ ]]; then
  echo "Broker must be an IPv4 address (the ESP32 firmware does not resolve .local names): $BROKER" >&2
  exit 2
fi

if [[ -f "$HW_DIR/secrets.ini" ]]; then
  mkdir -p "$HOME/.edgeflow"
  cp "$HW_DIR/secrets.ini" "$HOME/.edgeflow/secrets.ini.prev"
fi
# Single quotes keep spaces in an SSID inside one flag (PlatformIO build_flags syntax)
cat > "$HW_DIR/secrets.ini" <<INI
; Written by set_network.sh on $(date '+%Y-%m-%d %H:%M'). Git-ignored.
[secrets]
build_flags =
    '-D WIFI_SSID="$SSID"'
    '-D WIFI_PASS="$PASS"'
    '-D MQTT_BROKER="$BROKER"'
INI
echo "== secrets.ini: SSID '$SSID', broker $BROKER (previous file: ~/.edgeflow/secrets.ini.prev)"

PIO=(pio)
command -v pio >/dev/null || PIO=(uvx --from platformio pio)
cd "$HW_DIR"
for node in J1 J2; do
  echo "== Building $node"
  "${PIO[@]}" run -e "$node" | tail -3
done

cat <<NEXT

== Next
1. Flash each board (one plugged at a time):
     cd src/hardware && ${PIO[*]} run -e J1 -t upload     # then J2
   USB keeps dropping? esptool at 115200 with retries (see flash_retry.sh notes in KE_HOACH_DEPLOY.md).
2. Pi: join the same network, then in ~/vedc-traffic-flow/.env.rpi set
     MQTT_HOST=$BROKER
   and restart:  sudo systemctl restart edgeflow-vision
3. Laptop: nothing to change (the Docker broker listens on every interface). Check the boards:
     MQTT_HOST=127.0.0.1 python src/hardware/demo/laptop_command_test.py status
NEXT
