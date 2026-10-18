#!/usr/bin/env bash
# EdgeFlow AI - closed-loop rehearsal on one laptop, no hardware:
#   telemetry source -> REAL graph-control -> 2 virtual ESP32 (esp32_simulator.py) -> ACK/health -> back.
# Uses a private Mosquitto on 127.0.0.1 (default port 18830), records every message, then runs flow_report.py.
# The virtual ESP32 follows the firmware rules but is not evidence about the real boards.
#
#   bash src/hardware/demo/closed_loop_rehearsal.sh                                  # 60 s, fake Pi ns_heavy, max_pressure
#   bash src/hardware/demo/closed_loop_rehearsal.sh --controller edgeflow --source fake:camera_lost
#   bash src/hardware/demo/closed_loop_rehearsal.sh --source vision --model models/yolo11n.onnx   # real vision service, synthetic video
#
# Needs: mosquitto + mosquitto_sub in PATH, a Python with paho-mqtt, jsonschema, pydantic-settings, networkx
# (CI package list). PY=/path/to/python overrides the interpreter.
set -euo pipefail

REPO="$(cd "$(dirname "${BASH_SOURCE[0]}")/../../.." && pwd)"
DEMO="$REPO/src/hardware/demo"
PY="${PY:-python3}"
CONTROLLER=max_pressure
DURATION=60
SOURCE=fake:ns_heavy
TOPOLOGY=tabletop_j1_j2_v1
PORT=18830
MODEL=""
OUT=""

usage() { sed -n '2,13p' "$0" | sed 's/^# \{0,1\}//'; exit "${1:-0}"; }
while [ $# -gt 0 ]; do
  case "$1" in
    --controller) CONTROLLER=$2; shift 2 ;;
    --duration) DURATION=$2; shift 2 ;;
    --source) SOURCE=$2; shift 2 ;;
    --topology) TOPOLOGY=$2; shift 2 ;;
    --port) PORT=$2; shift 2 ;;
    --model) MODEL=$2; shift 2 ;;
    --out) OUT=$2; shift 2 ;;
    -h|--help) usage 0 ;;
    *) echo "Unknown option: $1" >&2; usage 2 ;;
  esac
done
case "$SOURCE" in fake:*|vision) ;; *) echo "--source must be fake:<scenario> or vision" >&2; exit 2 ;; esac
for tool in mosquitto mosquitto_sub; do
  command -v "$tool" >/dev/null || { echo "$tool not found (brew install mosquitto / apt install mosquitto mosquitto-clients)" >&2; exit 2; }
done
OUT="${OUT:-$HOME/edgeflow_runs/rehearsal_$(date +%Y%m%d_%H%M%S)_${CONTROLLER}_${SOURCE//:/_}}"
mkdir -p "$OUT"
export MQTT_HOST=127.0.0.1 MQTT_PORT="$PORT" EDGEFLOW_TOPOLOGY="$TOPOLOGY" EDGEFLOW_CONTROLLER="$CONTROLLER"

pids=()
cleanup() {
  for p in ${pids[@]+"${pids[@]}"}; do kill -TERM "$p" 2>/dev/null || true; done
  sleep 1
  for p in ${pids[@]+"${pids[@]}"}; do kill -KILL "$p" 2>/dev/null || true; done
}
trap cleanup EXIT INT TERM

printf 'listener %s 127.0.0.1\nallow_anonymous true\npersistence false\n' "$PORT" > "$OUT/mosquitto.conf"
mosquitto -c "$OUT/mosquitto.conf" > "$OUT/mosquitto.log" 2>&1 & pids+=("$!")
sleep 0.5
mosquitto_sub -h 127.0.0.1 -p "$PORT" -v -F '%U %t %p' -t 'edgeflow/v1/#' > "$OUT/mqtt.log" 2>&1 & pids+=("$!")
for node in J1 J2; do
  "$PY" -u "$DEMO/esp32_simulator.py" --node "$node" --mqtt-host 127.0.0.1 --mqtt-port "$PORT" \
    > "$OUT/esp32_$node.log" 2>&1 & pids+=("$!")
done
(cd "$REPO/services/graph-control" && exec "$PY" -u main.py) > "$OUT/graph_control.log" 2>&1 & pids+=("$!")
sleep 3
echo "Rehearsal: controller=$CONTROLLER source=$SOURCE topology=$TOPOLOGY ${DURATION}s -> $OUT"

if [ "${SOURCE%%:*}" = fake ]; then
  "$PY" -u "$DEMO/pi_fake_telemetry.py" --mqtt-host 127.0.0.1 --mqtt-port "$PORT" --topology "$TOPOLOGY" \
    --scenario "${SOURCE#fake:}" --seed 7 --duration "$DURATION" > "$OUT/source.log" 2>&1 || echo "telemetry source exited with an error: see $OUT/source.log" >&2
else
  (cd "$REPO" && VIDEO_SOURCE="${VIDEO_SOURCE:-synthetic}" VISION_NODE_IDS=J1,J2 \
     ROI_CONFIG_PATH="${ROI_CONFIG_PATH:-services/vision/rois/example_two_nodes_1280x720.json}" \
     DETECTION_MODEL_PATH="$MODEL" VISION_FPS="${VISION_FPS:-5}" exec "$PY" -u services/vision/main.py) \
     > "$OUT/source.log" 2>&1 &
  vision_pid=$!; pids+=("$vision_pid")
  sleep "$DURATION"
  kill -TERM "$vision_pid" 2>/dev/null || true
fi
# Silence after the source stops: each ESP32 must enter its fallback cycle about 5 s later.
sleep 8
cleanup
trap - EXIT INT TERM

status=0
"$PY" "$DEMO/flow_report.py" "$OUT/mqtt.log" --nodes J1,J2 --json "$OUT/flow_report.json" | tee "$OUT/flow_report.txt" || status=$?
if grep -qiE 'Traceback|ERROR' "$OUT/graph_control.log"; then
  echo "graph-control logged errors: see $OUT/graph_control.log" >&2
fi
exit "$status"
