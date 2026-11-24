/*
 * EdgeFlow AI - Real-time Embedded Traffic Signal Actuator Firmware
 * Target Microcontroller: ESP32-DevKitC-32U (FreeRTOS / Arduino Framework)
 * Competition: VEDC 2026 (Team 31µF)
 *
 * Implements the EdgeFlow AI actuator state machine:
 *  - Mandatory physical clearance: GREEN -> YELLOW (3.0s) -> ALL_RED (2.0s) -> GREEN
 *  - Consumes canonical ControlCommand JSON payloads over MQTT
 *  - Emits canonical ControlACK JSON payloads (ACCEPTED, APPLIED, REJECTED, EXPIRED, FAILED)
 *  - Autonomous fallback schedule (15 s per phase) upon loss of coordinator (> 5.0s)
 *  - Flashing-yellow mode (both heads) for startup, safe-stop and detected faults; leaving it always goes
 *    steady YELLOW (3s) -> ALL_RED (2s) -> GREEN (MUTCD 4D.31: no flashing yellow straight to red)
 *  - SignalFaultEvents queued while the broker is unreachable and sent on reconnect
 *  - Hardware task watchdog; reset reason + boot counter reported in health
 *  - Serial output trace (TRACE lines) of every signal change for timing evidence
 *
 * Fault handling per scenario: VEDC/NANG_CAP_FIRMWARE_KICH_BAN_LOI.md (outside git) and src/hardware/README.md.
 * Build with PlatformIO from src/hardware/: `pio run -e J1 -t upload` (see platformio.ini).
 * Network settings come only from build flags (secrets.ini, written by set_network.sh).
 */

#define ARDUINOJSON_USE_LONG_LONG 1

#include <WiFi.h>
#include <PubSubClient.h>
#include <ArduinoJson.h>
#include <Preferences.h>
#include <esp_system.h>
#include <esp_task_wdt.h>
#include <esp_arduino_version.h>
#include <sys/time.h>
#include <time.h>

#include "net_config.h"
#include "fault_queue.h"

// ====================================================================
// 1. HARDWARE CONFIGURATION & NODE IDENTIFIER
// ====================================================================
#ifndef NODE_ID
#define NODE_ID "J1"
#endif
#ifndef NTP_SERVER
#define NTP_SERVER nullptr // nullptr = the broker of the active network
#endif
const int MQTT_PORT = 1883;

// ====================================================================
// 2. PIN DEFINITIONS (See schematic_and_pinout.md)
// ====================================================================
const int PIN_NS_RED = 23;
const int PIN_NS_YELLOW = 22;
const int PIN_NS_GREEN = 21;
const int PIN_EW_RED = 19;
const int PIN_EW_YELLOW = 18;
const int PIN_EW_GREEN = 5;
const int HEAD_PINS[6] = {PIN_NS_RED, PIN_NS_YELLOW, PIN_NS_GREEN, PIN_EW_RED, PIN_EW_YELLOW, PIN_EW_GREEN};

#ifndef SAFE_STOP_GPIO
#define SAFE_STOP_GPIO 4
#endif
// Input level that means "pressed": LOW for a normally-open contact to GND (default),
// HIGH for a normally-closed contact (all J1..J5 buttons are wired on their NC contact, so a broken
// wire also reads as "pressed": fail-safe)
#ifndef SAFE_STOP_PRESSED_LEVEL
#define SAFE_STOP_PRESSED_LEVEL LOW
#endif
// 1 = read every head output back and flash on a mismatch (shorted pin / solder bridge). Set
// -D OUTPUT_READBACK=0 if a board reports false mismatches (LED modules loading the pins too hard).
#ifndef OUTPUT_READBACK
#define OUTPUT_READBACK 1
#endif
const int PIN_STATUS_LED = 2;
const int PIN_SAFE_STOP = SAFE_STOP_GPIO;

// ====================================================================
// 3. SAFETY TIMING INVARIANTS (Milliseconds)
// ====================================================================
const unsigned long DURATION_YELLOW_MS = 3000;    // 3.0 s clearance yellow
const unsigned long DURATION_ALL_RED_MS = 2000;   // 2.0 s all-red clearance
const unsigned long DEFAULT_MIN_GREEN_MS = 5000;  // 5.0 s minimum green floor (device-owned)
const unsigned long DEFAULT_MAX_GREEN_MS = 60000; // 60.0 s maximum green cap (device-owned)
const unsigned long NETWORK_TIMEOUT_MS = 5000;    // 5.0 s without a command -> fallback
const unsigned long FALLBACK_GREEN_MS = 15000;    // 15.0 s green per phase in fallback
// A phase that only got green because the other one hit max green keeps it at least this long:
// otherwise a controller that always prefers the busy road takes it back after the 5 s minimum
// and the quiet road is served 5 s every ~70 s (soft starvation). Dashboard overrides are exempt.
const unsigned long FORCED_SERVICE_GREEN_MS = 15000;
const unsigned long STARTUP_FLASH_MS = 4000;      // flashing yellow after every boot/reset
const unsigned long FAULT_FLASH_HOLD_MS = 10000;  // flashing yellow after a conflict / readback fault
const unsigned long SAFE_STOP_DEBOUNCE_MS = 50;
const unsigned long FLASH_HALF_PERIOD_MS = 500; // 60 flashes/min, 1/2 on (MUTCD: 50-60/min)
const unsigned long HEALTH_PERIOD_MS = 5000;
const unsigned long MQTT_RETRY_MIN_MS = 2000; // reconnect spacing doubles up to MAX while failing
const unsigned long MQTT_RETRY_MAX_MS = 10000;
const uint32_t MQTT_CONNECT_TIMEOUT_S = 1; // TCP connect + CONNACK wait: worst-case block ~2 s
const unsigned long WIFI_SWITCH_MS = 10000;   // no Wi-Fi this long -> try the next configured network
const unsigned long WIFI_STAGGER_MS = 400;    // J1 starts Wi-Fi at 0 ms, J2 at 400 ms, ... (inrush)
const unsigned long READBACK_PERIOD_MS = 100;
const uint8_t READBACK_TRIP_COUNT = 3;             // 3 consecutive mismatches (~300 ms)
const unsigned long READBACK_FAULT_REPEAT_MS = 60000; // re-report a persisting mismatch at most every 60 s
const uint8_t EXPIRED_DISTRUST_COUNT = 3;          // this many EXPIRED in a row -> clock is wrong
const uint32_t HW_WATCHDOG_S = 10;                 // > worst-case blocking MQTT connect (~2 s)
const uint16_t MQTT_BUFFER_BYTES = 1024;           // PubSubClient default (256) truncates ACKs
const char *OVERRIDE_ID_PREFIX = "cmd-override-";  // dashboard override commands (API)

// ====================================================================
// 4. STATE MACHINE & DATA TYPES
// ====================================================================
enum PhaseId
{
  PHASE_NS = 0,
  PHASE_EW = 1
};

enum ClearanceState
{
  STATE_GREEN,
  STATE_YELLOW,
  STATE_ALL_RED,
  STATE_FLASH
};

enum FlashReason
{
  FLASH_NONE,
  FLASH_STARTUP,
  FLASH_SAFE_STOP,
  FLASH_FAULT,
  FLASH_EMERGENCY
};

PhaseId currentPhase = PHASE_NS;
PhaseId pendingPhase = PHASE_NS;
ClearanceState clearState = STATE_FLASH;
FlashReason flashReason = FLASH_STARTUP;
bool yellowOnBothHeads = false; // the steady yellow that leaves flashing mode

unsigned long currentMinGreenMs = DEFAULT_MIN_GREEN_MS;
unsigned long currentMaxGreenMs = DEFAULT_MAX_GREEN_MS;

unsigned long phaseStartTime = 0;
unsigned long stateStartTime = 0;
unsigned long flashStartTime = 0;
unsigned long lastCommandTime = 0;
unsigned long lastHealthTime = 0;

bool isLocalFallbackMode = false;
bool minGreenFaultSent = false; // ERR_MIN_GREEN_VIOLATION at most once per green interval
bool forcedServicePending = false; // the clearance in progress was forced by max green
bool forcedServiceActive = false;  // the current green was forced: FORCED_SERVICE_GREEN_MS applies
String pendingCommandId = "";
String pendingTargetPhaseStr = "";

bool safeStopActive = false;
bool safeStopRawLast = false;
unsigned long safeStopRawSince = 0;

bool conflictTripped = false; // set by writeHeads, handled in loop (no re-entry into the FSM)

// Last written head colours ('R', 'Y', 'G' or '-') and the pin levels they mean
char lastNs = '?';
char lastEw = '?';
const char *lastLabel = ""; // always a string literal
uint8_t wantedLevel[6] = {LOW, LOW, LOW, LOW, LOW, LOW};
uint8_t readbackMismatches = 0;
unsigned long lastReadbackTime = 0;
unsigned long lastReadbackFaultTime = 0;
bool readbackFaultReported = false;

// Clock trust
uint8_t consecutiveExpired = 0;
bool clockDistrusted = false;

// Boot info
uint32_t bootCount = 0;
esp_reset_reason_t resetReason = ESP_RST_UNKNOWN;

// Network
size_t netIndex = 0;
bool wifiStarted = false;
bool wifiWasConnected = false;
unsigned long wifiBeginTime = 0;
bool mqttUp = false;
bool mqttEverUp = false;
bool wifiLostDuringOutage = false;
unsigned long mqttDownSince = 0;
unsigned long lastMqttAttempt = 0;
unsigned long mqttRetryMs = MQTT_RETRY_MIN_MS;

WiFiClient espClient;
PubSubClient mqttClient(espClient);
FaultQueue<8> faultQueue;
uint32_t faultSeq = 0;

void publishHealth(unsigned long now);
void raiseFault(const char *category, const char *faultCode, const char *severity, const char *reason,
                const char *targetPhase = nullptr, const char *detailsJson = nullptr);
void enterFlash(FlashReason reason, unsigned long now);

// ====================================================================
// 5. CLOCK & BOOT HELPERS
// ====================================================================
bool isClockSynced()
{
  return time(nullptr) > 1700000000; // after Nov 2023 => SNTP has set the clock
}

uint64_t epochMs()
{
  struct timeval tv;
  gettimeofday(&tv, nullptr);
  return (uint64_t)tv.tv_sec * 1000ULL + (uint64_t)(tv.tv_usec / 1000);
}

const char *resetReasonName(esp_reset_reason_t r)
{
  switch (r)
  {
  case ESP_RST_POWERON:
    return "POWERON";
  case ESP_RST_EXT:
    return "EXTERNAL";
  case ESP_RST_SW:
    return "SOFTWARE";
  case ESP_RST_PANIC:
    return "PANIC";
  case ESP_RST_INT_WDT:
    return "INT_WDT";
  case ESP_RST_TASK_WDT:
    return "TASK_WDT";
  case ESP_RST_WDT:
    return "WDT";
  case ESP_RST_DEEPSLEEP:
    return "DEEPSLEEP";
  case ESP_RST_BROWNOUT:
    return "BROWNOUT";
  case ESP_RST_SDIO:
    return "SDIO";
  default:
    return "UNKNOWN";
  }
}

bool isAbnormalReset(esp_reset_reason_t r)
{
  return r == ESP_RST_PANIC || r == ESP_RST_INT_WDT || r == ESP_RST_TASK_WDT || r == ESP_RST_WDT ||
         r == ESP_RST_BROWNOUT;
}

// Boot counter in NVS: survives power loss; one write per boot, so flash wear is not a concern.
void loadBootInfo()
{
  resetReason = esp_reset_reason();
  Preferences prefs;
  if (prefs.begin("edgeflow", false))
  {
    bootCount = prefs.getUInt("boots", 0) + 1;
    prefs.putUInt("boots", bootCount);
    prefs.end();
  }
  Serial.printf("[BOOT] #%u reset reason %s\n", bootCount, resetReasonName(resetReason));
}

// ====================================================================
// 6. HARDWARE OUTPUT CONTROLLER
// ====================================================================
const char *clearanceName(ClearanceState state)
{
  switch (state)
  {
  case STATE_GREEN:
    return "GREEN";
  case STATE_YELLOW:
    return "YELLOW";
  case STATE_ALL_RED:
    return "ALL_RED";
  default:
    return "FLASHING_YELLOW";
  }
}

String canonicalPhaseString(PhaseId p)
{
  return String(NODE_ID) + (p == PHASE_NS ? "_PHASE_NS" : "_PHASE_EW");
}

// Writes both heads. Refuses a conflicting double green (forces ALL_RED now; the loop then enters fault
// flash) and logs every change as "TRACE,<millis>,<node>,<ns>,<ew>,<label>" for output-timing evidence.
void writeHeads(char ns, char ew, const char *label)
{
  if (ns == 'G' && ew == 'G')
  {
    Serial.println("ERROR,conflicting green requested -> forcing ALL_RED");
    ns = 'R';
    ew = 'R';
    label = "CONFLICT_GUARD";
    conflictTripped = true;
  }
  const char colours[6] = {'R', 'Y', 'G', 'R', 'Y', 'G'};
  for (int i = 0; i < 6; i++)
  {
    char head = (i < 3) ? ns : ew;
    wantedLevel[i] = (head == colours[i]) ? HIGH : LOW;
  }
  // All OFF first (no momentary overlap), then the requested colours
  for (int i = 0; i < 6; i++)
    digitalWrite(HEAD_PINS[i], LOW);
  for (int i = 0; i < 6; i++)
    if (wantedLevel[i] == HIGH)
      digitalWrite(HEAD_PINS[i], HIGH);

  // Also on a label change with the same colours (flashing Y/Y -> steady flash-exit Y/Y), so
  // verify_trace.py can time the steady yellow that leaves flashing mode
  if (ns != lastNs || ew != lastEw || strcmp(label, lastLabel) != 0)
  {
    lastNs = ns;
    lastEw = ew;
    lastLabel = label;
    Serial.printf("TRACE,%lu,%s,%c,%c,%s\n", millis(), NODE_ID, ns, ew, label);
  }
}

void applySignalOutputs(PhaseId activePhase, ClearanceState state)
{
  if (state == STATE_GREEN)
  {
    if (activePhase == PHASE_NS)
      writeHeads('G', 'R', "GREEN");
    else
      writeHeads('R', 'G', "GREEN");
  }
  else if (state == STATE_YELLOW)
  {
    if (yellowOnBothHeads)
      writeHeads('Y', 'Y', "FLASH_EXIT_YELLOW"); // leaving flashing yellow: steady yellow on both heads
    else if (activePhase == PHASE_NS)
      writeHeads('Y', 'R', "YELLOW");
    else
      writeHeads('R', 'Y', "YELLOW");
  }
  else if (state == STATE_ALL_RED)
  {
    writeHeads('R', 'R', "ALL_RED");
  }
}

// ====================================================================
// 7. CONTROL ACK, HEALTH & FAULT EMITTERS
// ====================================================================
void publishControlAck(const char *cmdId, const char *targetPhaseStr, const char *status, const char *reason)
{
  Serial.printf("[ACK] %s %s (%s)\n", status, cmdId ? cmdId : "", reason);
  if (!mqttClient.connected())
    return; // an ACK only matters to the coordinator now: not queued

  char topic[80];
  snprintf(topic, sizeof(topic), "edgeflow/v1/control/%s/ack", NODE_ID);

  StaticJsonDocument<512> doc;
  doc["command_id"] = (cmdId && strlen(cmdId) > 0) ? cmdId : "unknown";
  doc["node_id"] = NODE_ID;
  doc["target_phase_id"] = (targetPhaseStr && strlen(targetPhaseStr) > 0) ? targetPhaseStr : "UNKNOWN";
  doc["status"] = status;
  if (isClockSynced())
    doc["timestamp_ms"] = epochMs(); // UTC Unix ms (contract unit)
  doc["uptime_ms"] = millis();
  doc["reason"] = reason;

  char buffer[512];
  size_t len = serializeJson(doc, buffer, sizeof(buffer));
  if (!mqttClient.publish(topic, (const uint8_t *)buffer, len, false))
    Serial.println("ERROR,ACK publish failed (buffer/connection)");
}

const char *healthStatus()
{
  if (safeStopActive)
    return "SAFE_STOP";
  if (clearState == STATE_FLASH && flashReason == FLASH_FAULT)
    return "DEGRADED";
  if (clearState == STATE_FLASH && flashReason == FLASH_STARTUP)
    return "STARTING";
  if (clearState == STATE_FLASH && flashReason == FLASH_EMERGENCY)
    return "EMERGENCY_FLASH";
  return isLocalFallbackMode ? "FALLBACK_AUTONOMOUS" : "HEALTHY";
}

void publishHealth(unsigned long now)
{
  if (!mqttClient.connected())
    return;
  char healthTopic[80];
  snprintf(healthTopic, sizeof(healthTopic), "edgeflow/v1/health/%s", NODE_ID);

  StaticJsonDocument<640> hDoc;
  hDoc["node_id"] = NODE_ID;
  hDoc["service"] = "esp32_actuator";
  hDoc["status"] = healthStatus();
  hDoc["current_phase"] = canonicalPhaseString(currentPhase);
  hDoc["clearance"] = clearanceName(clearState);
  hDoc["safe_stop"] = safeStopActive;
  hDoc["uptime_s"] = now / 1000;
  hDoc["wifi_rssi_dbm"] = WiFi.RSSI();
  hDoc["wifi_network"] = (int)netIndex + 1; // 1 = WIFI_SSID, 2 = WIFI_SSID_2, ...
  hDoc["reset_reason"] = resetReasonName(resetReason);
  hDoc["boot_count"] = bootCount;
  hDoc["clock_synced"] = isClockSynced() && !clockDistrusted;
  hDoc["faults_queued"] = (int)faultQueue.size();
  hDoc["free_heap_b"] = ESP.getFreeHeap();
  if (isClockSynced())
    hDoc["timestamp_ms"] = epochMs();

  char hBuffer[640];
  size_t len = serializeJson(hDoc, hBuffer, sizeof(hBuffer));
  mqttClient.publish(healthTopic, (const uint8_t *)hBuffer, len, false);
}

// Queues a SignalFaultEvent (contracts/schemas/signal_fault_event.json); flushFaults() sends it on
// edgeflow/v1/signal_fault/<node>/<category> as soon as the broker is reachable.
void raiseFault(const char *category, const char *faultCode, const char *severity, const char *reason,
                const char *targetPhase, const char *detailsJson)
{
  Serial.printf("[FAULT] %s/%s %s: %s\n", category, faultCode, severity, reason ? reason : "");
  QueuedFault f;
  copyField(f.category, sizeof(f.category), category);
  copyField(f.code, sizeof(f.code), faultCode);
  copyField(f.severity, sizeof(f.severity), severity);
  copyField(f.reason, sizeof(f.reason), reason);
  copyField(f.target, sizeof(f.target), targetPhase);
  copyField(f.phase, sizeof(f.phase), canonicalPhaseString(currentPhase).c_str());
  copyField(f.clearance, sizeof(f.clearance), clearanceName(clearState));
  copyField(f.details, sizeof(f.details), detailsJson);
  f.occurredMs = millis();
  f.seq = ++faultSeq;
  faultQueue.push(f);
}

bool sendFault(const QueuedFault &f, unsigned long now, uint32_t droppedBefore)
{
  char topic[96];
  snprintf(topic, sizeof(topic), "edgeflow/v1/signal_fault/%s/%s", NODE_ID, f.category);

  StaticJsonDocument<768> doc;
  char eventId[48];
  // Unique across reboots: the API stores event_id as UNIQUE (INSERT OR REPLACE)
  snprintf(eventId, sizeof(eventId), "evt-%s-b%u-%u", NODE_ID, bootCount, f.seq);
  doc["event_id"] = eventId;
  doc["node_id"] = NODE_ID;
  doc["category"] = f.category;
  doc["fault_code"] = f.code;
  doc["severity"] = f.severity;
  doc["current_phase"] = f.phase;
  if (strlen(f.target) > 0)
    doc["target_phase"] = f.target;
  doc["clearance_state"] = f.clearance;
  doc["reason"] = f.reason;

  JsonObject details = doc.createNestedObject("details");
  // Lives until serializeJson(): ArduinoJson 6 may keep pointers to its keys instead of copying them
  StaticJsonDocument<256> extra;
  if (strlen(f.details) > 0)
  {
    if (!deserializeJson(extra, f.details))
      for (JsonPair kv : extra.as<JsonObject>())
        details[kv.key()] = kv.value();
  }
  unsigned long queuedMs = now - f.occurredMs;
  details["uptime_ms"] = now;
  details["occurred_uptime_ms"] = f.occurredMs;
  details["queued_ms"] = queuedMs;
  details["boot_count"] = bootCount;
  if (droppedBefore > 0)
    details["dropped_before"] = droppedBefore;
  // Time of the fault itself (not of the send), once SNTP is trusted
  if (isClockSynced() && !clockDistrusted)
    doc["timestamp_ms"] = epochMs() - (uint64_t)queuedMs;

  char buffer[768];
  size_t len = serializeJson(doc, buffer, sizeof(buffer));
  return mqttClient.publish(topic, (const uint8_t *)buffer, len, false);
}

void flushFaults(unsigned long now)
{
  while (!faultQueue.empty() && mqttClient.connected())
  {
    uint32_t dropped = faultQueue.takeDropped();
    if (!sendFault(faultQueue.front(), now, dropped))
    {
      Serial.println("ERROR,FAULT publish failed: kept in queue");
      return;
    }
    faultQueue.pop();
  }
}

// ====================================================================
// 8. FLASHING MODE (startup, safe-stop, fault)
// ====================================================================
const char *flashReasonName(FlashReason r)
{
  return r == FLASH_STARTUP ? "startup" : (r == FLASH_SAFE_STOP ? "safe-stop" : (r == FLASH_EMERGENCY ? "emergency" : "fault"));
}

void enterFlash(FlashReason reason, unsigned long now)
{
  clearState = STATE_FLASH;
  flashReason = reason;
  flashStartTime = now;
  yellowOnBothHeads = false;
  if (pendingCommandId.length() > 0)
  {
    char why[96];
    snprintf(why, sizeof(why), "Signal entered flashing mode (%s) before the transition was applied",
             flashReasonName(reason));
    publishControlAck(pendingCommandId.c_str(), pendingTargetPhaseStr.c_str(), "FAILED", why);
    pendingCommandId = "";
    pendingTargetPhaseStr = "";
  }
  Serial.printf("[FLASH] Enter flashing yellow (%s)\n", flashReasonName(reason));
  publishHealth(now);
}

// Flashing yellow -> steady yellow on both heads (3 s) -> ALL_RED (2 s) -> GREEN on the last served phase
void exitFlash(unsigned long now)
{
  Serial.printf("[FLASH] Leave flashing (%s) -> YELLOW -> ALL_RED -> GREEN\n", flashReasonName(flashReason));
  flashReason = FLASH_NONE;
  pendingPhase = currentPhase;
  forcedServicePending = false; // a max-green switch interrupted by flashing no longer applies
  yellowOnBothHeads = true;
  clearState = STATE_YELLOW;
  stateStartTime = now;
  applySignalOutputs(currentPhase, STATE_YELLOW);
  publishHealth(now);
}

void serviceFlash(unsigned long now)
{
  bool on = (now / FLASH_HALF_PERIOD_MS) % 2;
  writeHeads(on ? 'Y' : '-', on ? 'Y' : '-', "FLASH");
  if (flashReason == FLASH_STARTUP && now - flashStartTime >= STARTUP_FLASH_MS)
    exitFlash(now);
  else if (flashReason == FLASH_FAULT && now - flashStartTime >= FAULT_FLASH_HOLD_MS)
    exitFlash(now);
}

// ====================================================================
// 9. INCOMING CONTROL COMMAND HANDLER (MQTT CALLBACK)
// ====================================================================
bool isFlashPhaseString(const char *phaseStr)
{
  if (!phaseStr)
    return false;
  String s = String(phaseStr);
  return (s == String(NODE_ID) + "_PHASE_FLASH" ||
          s == String(NODE_ID) + "_FLASH" ||
          s == "FLASH" ||
          s == "FLASHING_YELLOW");
}

// Strict mapping of canonical target_phase_id ("<NODE>_PHASE_NS" / "<NODE>_PHASE_EW").
bool parsePhaseString(const char *phaseStr, PhaseId &out)
{
  if (!phaseStr)
    return false;
  String s = String(phaseStr);
  if (s == String(NODE_ID) + "_PHASE_NS")
  {
    out = PHASE_NS;
    return true;
  }
  if (s == String(NODE_ID) + "_PHASE_EW")
  {
    out = PHASE_EW;
    return true;
  }
  return false;
}

// GREEN -> YELLOW (3s) -> ALL_RED (2s) -> target GREEN. An empty cmdId means no APPLIED ACK.
void startClearance(PhaseId target, const String &cmdId, const String &targetStr, unsigned long now)
{
  pendingPhase = target;
  pendingCommandId = cmdId;
  pendingTargetPhaseStr = targetStr;
  forcedServicePending = false; // the max-green path sets it again right after this call
  yellowOnBothHeads = false;
  clearState = STATE_YELLOW;
  stateStartTime = now;
  applySignalOutputs(currentPhase, STATE_YELLOW);
}

bool isOverrideCommand(const char *cmdId)
{
  return cmdId && strncmp(cmdId, OVERRIDE_ID_PREFIX, strlen(OVERRIDE_ID_PREFIX)) == 0;
}

void reportOverrideApplied(const char *cmdId, const char *targetPhaseStr)
{
  if (isOverrideCommand(cmdId))
    raiseFault("emergency", "ERR_EMERGENCY_OVERRIDE", "INFO", "Operator phase override applied", targetPhaseStr);
}

// Returns true when the command must be dropped as expired. Several EXPIRED in a row mean the device
// clock (not the coordinator) is wrong: report it once and stop trusting the clock for expiry.
bool commandExpired(JsonDocument &doc)
{
  uint64_t expiresAtMs = doc["expires_at_ms"] | (uint64_t)0;
  if (expiresAtMs == 0 || !isClockSynced() || clockDistrusted || epochMs() <= expiresAtMs)
  {
    consecutiveExpired = 0;
    return false;
  }
  if (++consecutiveExpired >= EXPIRED_DISTRUST_COUNT)
  {
    clockDistrusted = true;
    raiseFault("hardware", "ERR_HARDWARE_DEFECT", "WARNING",
               "Repeated EXPIRED commands: device clock distrusted, expiry no longer checked", nullptr,
               "{\"kind\":\"clock\"}");
  }
  return true;
}

void onMqttCommand(char *topic, byte *payload, unsigned int length)
{
  unsigned long now = millis();

  StaticJsonDocument<768> doc;
  DeserializationError err = deserializeJson(doc, payload, length);
  if (err)
  {
    publishControlAck("unknown", "unknown", "REJECTED", "Invalid JSON payload format");
    return;
  }

  const char *cmdNodeId = doc["node_id"] | "";
  if (strcmp(cmdNodeId, NODE_ID) != 0)
    return; // commands for other nodes are ignored

  // A well-formed command for this node proves the coordinator is alive.
  lastCommandTime = now;
  if (isLocalFallbackMode)
  {
    isLocalFallbackMode = false;
    Serial.println("[WATCHDOG] Coordinator command received -> leaving autonomous fallback");
  }

  const char *cmdId = doc["command_id"] | "unknown";
  const char *targetPhaseStr = doc["target_phase_id"] | "";
  const char *controller = doc["controller"] | "";

  if (safeStopActive)
  {
    publishControlAck(cmdId, targetPhaseStr, "REJECTED", "Safe-stop is engaged");
    return;
  }

  bool reqFlash = isFlashPhaseString(targetPhaseStr) || strcmp(controller, "emergency_flash") == 0;
  if (reqFlash)
  {
    if (clearState == STATE_FLASH)
    {
      if (flashReason == FLASH_EMERGENCY)
        publishControlAck(cmdId, targetPhaseStr, "APPLIED", "Signal is already in emergency flashing mode");
      else
      {
        char why[64];
        snprintf(why, sizeof(why), "Signal is in flashing mode (%s)", flashReasonName(flashReason));
        publishControlAck(cmdId, targetPhaseStr, "REJECTED", why);
      }
      return;
    }
    enterFlash(FLASH_EMERGENCY, now);
    publishControlAck(cmdId, targetPhaseStr, "APPLIED", "Emergency all-yellow flash activated by operator command");
    raiseFault("emergency", "ERR_EMERGENCY_OVERRIDE", "WARNING", "Emergency all-yellow flashing mode commanded by dashboard", targetPhaseStr);
    return;
  }

  if (clearState == STATE_FLASH)
  {
    if (flashReason == FLASH_EMERGENCY)
    {
      PhaseId targetPhase;
      if (parsePhaseString(targetPhaseStr, targetPhase))
      {
        currentPhase = targetPhase;
      }
      if (cmdId && strlen(cmdId) > 0)
      {
        pendingCommandId = cmdId;
        pendingTargetPhaseStr = targetPhaseStr;
      }
      exitFlash(now);
      publishControlAck(cmdId, targetPhaseStr, "ACCEPTED", "Leaving emergency flashing mode -> YELLOW (3s) -> ALL_RED (2s) -> TARGET");
      raiseFault("emergency", "ERR_EMERGENCY_OVERRIDE", "INFO", "Emergency flashing mode cancelled by operator command", targetPhaseStr);
      return;
    }
    char why[64];
    snprintf(why, sizeof(why), "Signal is in flashing mode (%s)", flashReasonName(flashReason));
    publishControlAck(cmdId, targetPhaseStr, "REJECTED", why);
    return;
  }

  if (commandExpired(doc))
  {
    publishControlAck(cmdId, targetPhaseStr, "EXPIRED", "Command expired before processing");
    return;
  }

  PhaseId targetPhase;
  if (!parsePhaseString(targetPhaseStr, targetPhase))
  {
    publishControlAck(cmdId, targetPhaseStr, "REJECTED", "Unknown target_phase_id for this node");
    raiseFault("feedback_error", "ERR_FEEDBACK_MISMATCH", "WARNING", "Unknown target_phase_id for this node", targetPhaseStr);
    return;
  }

  // Requested timings may lengthen but never shorten the device limits.
  float minGreenS = doc["min_green_s"] | 5.0f;
  float maxGreenS = doc["max_green_s"] | 60.0f;
  unsigned long reqMinMs = (unsigned long)(max(minGreenS, 0.0f) * 1000.0f);
  unsigned long reqMaxMs = (unsigned long)(max(maxGreenS, 0.0f) * 1000.0f);
  currentMinGreenMs = max(reqMinMs, DEFAULT_MIN_GREEN_MS);
  currentMaxGreenMs = min(max(reqMaxMs, currentMinGreenMs), DEFAULT_MAX_GREEN_MS);

  if (targetPhase == currentPhase)
  {
    if (clearState == STATE_GREEN)
    {
      publishControlAck(cmdId, targetPhaseStr, "APPLIED", "Phase is already active. Green time extended.");
      reportOverrideApplied(cmdId, targetPhaseStr);
    }
    else
    {
      publishControlAck(cmdId, targetPhaseStr, "ACCEPTED", "Transition currently clearing through Yellow/All-Red.");
    }
    return;
  }

  if (targetPhase == pendingPhase && clearState != STATE_GREEN)
  {
    if (cmdId && strlen(cmdId) > 0)
    {
      pendingCommandId = cmdId;
      pendingTargetPhaseStr = targetPhaseStr;
    }
    publishControlAck(cmdId, targetPhaseStr, "ACCEPTED", "Phase transition is already pending and clearing.");
    return;
  }

  if (clearState != STATE_GREEN)
  {
    publishControlAck(cmdId, targetPhaseStr, "REJECTED", "Clearance interval currently in progress.");
    return;
  }

  unsigned long elapsedGreen = now - phaseStartTime;
  unsigned long requiredGreenMs = currentMinGreenMs;
  if (forcedServiceActive && !isOverrideCommand(cmdId))
    requiredGreenMs = max(requiredGreenMs, FORCED_SERVICE_GREEN_MS);
  if (elapsedGreen < requiredGreenMs)
  {
    char reason[80];
    snprintf(reason, sizeof(reason), "%s not met (%.1fs < %.1fs)",
             requiredGreenMs > currentMinGreenMs ? "Forced-service green" : "Min green time",
             elapsedGreen / 1000.0, requiredGreenMs / 1000.0);
    publishControlAck(cmdId, targetPhaseStr, "REJECTED", reason);
    if (!minGreenFaultSent)
    {
      minGreenFaultSent = true;
      raiseFault("feedback_error", "ERR_MIN_GREEN_VIOLATION", "INFO", reason, targetPhaseStr);
    }
    return;
  }

  startClearance(targetPhase, String(cmdId), String(targetPhaseStr), now);
  publishControlAck(cmdId, targetPhaseStr, "ACCEPTED", "Clearance initiated: GREEN -> YELLOW (3s) -> ALL_RED (2s) -> TARGET");
}

// ====================================================================
// 10. WI-FI & MQTT
// ====================================================================
void beginNetwork(size_t index, unsigned long now)
{
  const NetworkSlot &net = NETWORKS[index];
  netIndex = index;
  wifiBeginTime = now;
  Serial.printf("[WiFi] Connecting to network %u/%u '%s' (broker %s)\n", (unsigned)index + 1,
                (unsigned)NETWORK_COUNT, net.ssid, net.broker);
  WiFi.disconnect();
  WiFi.begin(net.ssid, net.pass);
  mqttClient.setServer(net.broker, MQTT_PORT);
  const char *ntp = NTP_SERVER ? NTP_SERVER : net.broker;
  configTime(0, 0, ntp, NTP_FALLBACK_1, NTP_FALLBACK_2); // UTC; non-blocking SNTP
}

void noteMqttDown(unsigned long now)
{
  if (!mqttUp)
    return;
  mqttUp = false;
  mqttDownSince = now;
  wifiLostDuringOutage = WiFi.status() != WL_CONNECTED;
  digitalWrite(PIN_STATUS_LED, LOW);
  Serial.println("[MQTT] Link lost");
}

void onMqttConnected(unsigned long now)
{
  mqttUp = true;
  mqttRetryMs = MQTT_RETRY_MIN_MS;
  char cmdTopic[80];
  snprintf(cmdTopic, sizeof(cmdTopic), "edgeflow/v1/control/%s/command", NODE_ID);
  mqttClient.subscribe(cmdTopic);
  digitalWrite(PIN_STATUS_LED, HIGH);
  Serial.printf("[MQTT] Connected, subscribed to %s\n", cmdTopic);

  if (mqttEverUp)
  {
    char reason[96], details[96];
    unsigned long downMs = now - mqttDownSince;
    snprintf(reason, sizeof(reason), "Broker link was down %.1fs (%s)", downMs / 1000.0,
             wifiLostDuringOutage ? "Wi-Fi lost" : "Wi-Fi up");
    snprintf(details, sizeof(details), "{\"down_ms\":%lu,\"wifi_lost\":%s,\"wifi_network\":%u}", downMs,
             wifiLostDuringOutage ? "true" : "false", (unsigned)netIndex + 1);
    raiseFault("disconnect", "ERR_BROKER_DISCONNECT", "WARNING", reason, nullptr, details);
  }
  mqttEverUp = true;
  publishHealth(now);
  flushFaults(now);
}

void maintainMqttConnection(unsigned long now)
{
  if (mqttClient.connected())
    return;
  noteMqttDown(now);
  // A connect attempt blocks up to ~2 s; never let it stretch YELLOW/ALL_RED timing. Flashing modes
  // have no interval to stretch, so reconnecting there (to report health) is fine.
  if (clearState == STATE_YELLOW || clearState == STATE_ALL_RED)
    return;
  if (now - lastMqttAttempt < mqttRetryMs)
    return;
  lastMqttAttempt = now;

  char clientId[48];
  snprintf(clientId, sizeof(clientId), "ESP32_Actuator_%s_%04X", NODE_ID, (uint16_t)ESP.getEfuseMac());
  char willTopic[80];
  snprintf(willTopic, sizeof(willTopic), "edgeflow/v1/health/%s", NODE_ID);
  char willPayload[96];
  snprintf(willPayload, sizeof(willPayload), "{\"node_id\":\"%s\",\"service\":\"esp32_actuator\",\"status\":\"OFFLINE\"}", NODE_ID);

  Serial.printf("[MQTT] Connecting to %s:%d as '%s'...\n", NETWORKS[netIndex].broker, MQTT_PORT, clientId);
  if (mqttClient.connect(clientId, willTopic, 0, false, willPayload))
  {
    onMqttConnected(millis());
  }
  else
  {
    mqttRetryMs = min(mqttRetryMs * 2, MQTT_RETRY_MAX_MS);
    Serial.printf("[MQTT] Connect failed, rc=%d. Retrying in %lums\n", mqttClient.state(), mqttRetryMs);
  }
}

void serviceNetwork(unsigned long now)
{
  if (!wifiStarted)
  {
    int index = atoi(NODE_ID + 1); // "J3" -> 3: stagger Wi-Fi start-up current peaks between boards
    unsigned long startAt = (index > 1 ? (unsigned long)(index - 1) : 0UL) * WIFI_STAGGER_MS;
    if (now < startAt)
      return;
    wifiStarted = true;
    beginNetwork(0, now);
    return;
  }

  if (WiFi.status() == WL_CONNECTED)
  {
    if (!wifiWasConnected)
    {
      wifiWasConnected = true;
      Serial.printf("[WiFi] Connected! IP=%s RSSI=%ddBm\n", WiFi.localIP().toString().c_str(), WiFi.RSSI());
    }
    maintainMqttConnection(now);
    mqttClient.loop();
    flushFaults(millis());
    return;
  }

  if (wifiWasConnected)
  {
    wifiWasConnected = false;
    wifiBeginTime = now; // give the driver's auto-reconnect a full WIFI_SWITCH_MS first
    Serial.println("[WiFi] Connection lost");
  }
  if (!mqttClient.connected())
    noteMqttDown(now);
  if (now - wifiBeginTime >= WIFI_SWITCH_MS)
    beginNetwork((netIndex + 1) % NETWORK_COUNT, now); // same network again when only one is set
}

// ====================================================================
// 11. SAFE-STOP INPUT & OUTPUT READBACK
// ====================================================================
bool readSafeStop(unsigned long now)
{
  bool raw = (digitalRead(PIN_SAFE_STOP) == SAFE_STOP_PRESSED_LEVEL);
  if (raw != safeStopRawLast)
  {
    safeStopRawLast = raw;
    safeStopRawSince = now;
  }
  if (raw != safeStopActive && now - safeStopRawSince >= SAFE_STOP_DEBOUNCE_MS)
    return raw;
  return safeStopActive;
}

void serviceSafeStop(unsigned long now)
{
  bool pressed = readSafeStop(now);
  if (pressed && !safeStopActive)
  {
    safeStopActive = true;
    Serial.println("[SAFE-STOP] Engaged -> flashing yellow, commands rejected");
    raiseFault("emergency", "ERR_SAFE_STOP_ENGAGED", "CRITICAL", "Safe-stop emergency switch engaged by user");
    enterFlash(FLASH_SAFE_STOP, now);
  }
  else if (!pressed && safeStopActive)
  {
    safeStopActive = false;
    Serial.println("[SAFE-STOP] Released -> YELLOW -> ALL_RED before resuming");
    raiseFault("emergency", "ERR_SAFE_STOP_RELEASED", "INFO", "Safe-stop emergency switch released");
    // graph-control halts commands on purpose during SAFE_STOP: give it a full watchdog period to resume
    lastCommandTime = now;
    exitFlash(now);
  }
}

// Every head pin is an OUTPUT with its input buffer on (Arduino-ESP32 OUTPUT = 0x03), so digitalRead()
// returns the real pad level. A pin that disagrees with what was written for ~300 ms is shorted or
// bridged: flash. An open (burnt) LED is NOT detectable this way (no current sensing).
void serviceReadback(unsigned long now)
{
#if OUTPUT_READBACK
  if (now - lastReadbackTime < READBACK_PERIOD_MS)
    return;
  lastReadbackTime = now;
  int badPin = -1;
  for (int i = 0; i < 6; i++)
    if (digitalRead(HEAD_PINS[i]) != wantedLevel[i])
      badPin = HEAD_PINS[i];
  if (badPin < 0)
  {
    readbackMismatches = 0;
    return;
  }
  if (++readbackMismatches < READBACK_TRIP_COUNT)
    return;
  readbackMismatches = 0;
  if (!readbackFaultReported || now - lastReadbackFaultTime >= READBACK_FAULT_REPEAT_MS)
  {
    readbackFaultReported = true;
    lastReadbackFaultTime = now;
    char reason[96], details[64];
    snprintf(reason, sizeof(reason), "Output readback mismatch on GPIO %d (shorted/bridged pin?)", badPin);
    snprintf(details, sizeof(details), "{\"kind\":\"output_readback\",\"gpio\":%d}", badPin);
    raiseFault("hardware", "ERR_HARDWARE_DEFECT", "CRITICAL", reason, nullptr, details);
  }
  if (!safeStopActive)
    enterFlash(FLASH_FAULT, now);
  else
    flashStartTime = now;
#endif
}

// ====================================================================
// 12. SETUP
// ====================================================================
void setupHardwareWatchdog()
{
#if ESP_ARDUINO_VERSION_MAJOR >= 3
  esp_task_wdt_config_t wdtConfig = {
      .timeout_ms = HW_WATCHDOG_S * 1000,
      .idle_core_mask = 0,
      .trigger_panic = true,
  };
  esp_task_wdt_reconfigure(&wdtConfig);
#else
  esp_task_wdt_init(HW_WATCHDOG_S, true);
#endif
  esp_task_wdt_add(NULL); // watch the Arduino loop task
}

void setup()
{
  Serial.begin(115200);
  delay(500);

  Serial.println("\n=========================================================");
  Serial.printf("  EdgeFlow AI - ESP32 Signal Actuator Node [%s]\n", NODE_ID);
  Serial.println("=========================================================");

  for (int i = 0; i < 6; i++)
    pinMode(HEAD_PINS[i], OUTPUT);
  pinMode(PIN_STATUS_LED, OUTPUT);
  pinMode(PIN_SAFE_STOP, INPUT_PULLUP);

  Serial.println("TRACE,millis,node,ns,ew,label");
  loadBootInfo();

  // Defined boot state: flashing yellow (startup), then YELLOW -> ALL_RED -> North-South GREEN
  unsigned long now = millis();
  currentPhase = PHASE_NS;
  pendingPhase = PHASE_NS;
  phaseStartTime = now;
  stateStartTime = now;
  lastCommandTime = now;
  enterFlash(FLASH_STARTUP, now);
  if (isAbnormalReset(resetReason))
  {
    char reason[80], details[96];
    snprintf(reason, sizeof(reason), "Abnormal reset: %s (boot #%u)", resetReasonName(resetReason), bootCount);
    snprintf(details, sizeof(details), "{\"kind\":\"reset\",\"reset_reason\":\"%s\"}", resetReasonName(resetReason));
    raiseFault("hardware", "ERR_HARDWARE_DEFECT", "CRITICAL", reason, nullptr, details); // queued until MQTT is up
  }

  WiFi.mode(WIFI_STA);
  WiFi.setSleep(false); // no modem sleep: lower command latency
  WiFi.setAutoReconnect(true);
#ifdef WIFI_TX_POWER
  WiFi.setTxPower(WIFI_TX_POWER); // e.g. -D WIFI_TX_POWER=WIFI_POWER_11dBm (lower current peaks; untested)
#endif

  mqttClient.setCallback(onMqttCommand);
  mqttClient.setBufferSize(MQTT_BUFFER_BYTES);
  mqttClient.setSocketTimeout(MQTT_CONNECT_TIMEOUT_S); // CONNACK wait
  espClient.setTimeout(MQTT_CONNECT_TIMEOUT_S);        // TCP connect (core default 3 s)

  setupHardwareWatchdog();
}

// ====================================================================
// 13. MAIN EVENT LOOP
// ====================================================================
void runSignalStateMachine(unsigned long now)
{
  if (clearState == STATE_YELLOW)
  {
    if (now - stateStartTime >= DURATION_YELLOW_MS)
    {
      yellowOnBothHeads = false;
      clearState = STATE_ALL_RED;
      stateStartTime = now;
      applySignalOutputs(currentPhase, STATE_ALL_RED);
      Serial.println("[FSM] Yellow finished -> Entered ALL_RED clearance (2.0s)");
    }
  }
  else if (clearState == STATE_ALL_RED)
  {
    if (now - stateStartTime >= DURATION_ALL_RED_MS)
    {
      currentPhase = pendingPhase;
      clearState = STATE_GREEN;
      stateStartTime = now;
      phaseStartTime = now;
      minGreenFaultSent = false;
      forcedServiceActive = forcedServicePending;
      forcedServicePending = false;
      applySignalOutputs(currentPhase, STATE_GREEN);
      Serial.printf("[FSM] ALL_RED finished -> GREEN active on [%s]\n", canonicalPhaseString(currentPhase).c_str());

      // APPLIED only after the output state has physically changed
      if (pendingCommandId.length() > 0)
      {
        publishControlAck(pendingCommandId.c_str(), pendingTargetPhaseStr.c_str(), "APPLIED",
                          "Physical clearance completed. Target phase is now active GREEN.");
        reportOverrideApplied(pendingCommandId.c_str(), pendingTargetPhaseStr.c_str());
        pendingCommandId = "";
        pendingTargetPhaseStr = "";
      }
      // Every switch to GREEN announces the new phase at once (vision copies it into telemetry)
      publishHealth(now);
    }
  }

  // Local fallback watchdog (loss of coordinator > 5 s)
  if (now - lastCommandTime > NETWORK_TIMEOUT_MS)
  {
    if (!isLocalFallbackMode)
    {
      isLocalFallbackMode = true;
      Serial.println("[WATCHDOG] Coordinator timeout > 5.0s -> Switched to Autonomous Fallback Schedule");
      raiseFault("disconnect", "ERR_COORDINATOR_TIMEOUT", "WARNING", "Coordinator timeout > 5.0s -> Switched to Autonomous Fallback Schedule");
      publishHealth(now);
    }
    if (clearState == STATE_GREEN && (now - phaseStartTime >= FALLBACK_GREEN_MS))
    {
      PhaseId next = (currentPhase == PHASE_NS) ? PHASE_EW : PHASE_NS;
      startClearance(next, "", canonicalPhaseString(next), now); // local cycle: no ACK
    }
  }
  else if (clearState == STATE_GREEN && (now - phaseStartTime >= currentMaxGreenMs))
  {
    // Maximum green is enforced by the device even if the controller keeps requesting it
    PhaseId next = (currentPhase == PHASE_NS) ? PHASE_EW : PHASE_NS;
    Serial.println("[FSM] Max green reached -> forced clearance to the opposing phase");
    startClearance(next, "", canonicalPhaseString(next), now);
    forcedServicePending = true; // the opposing phase then keeps green >= FORCED_SERVICE_GREEN_MS
  }
}

void loop()
{
  unsigned long now = millis();
  esp_task_wdt_reset();

  serviceSafeStop(now);
  serviceNetwork(now); // may block up to ~2 s while connecting to the broker
  // Commands handled inside mqttClient.loop() stamp times with a newer millis(): refresh `now` so the
  // unsigned `now - stateStartTime` below cannot wrap and skip the 3 s YELLOW.
  now = millis();
  serviceSafeStop(now); // the button is read again right after any blocking network call

  if (conflictTripped)
  {
    conflictTripped = false;
    raiseFault("feedback_error", "ERR_CONFLICT_GUARD_TRIGGERED", "CRITICAL", "Conflicting green requested -> forced ALL_RED, flashing");
    if (!safeStopActive)
      enterFlash(FLASH_FAULT, now);
  }

  if (clearState == STATE_FLASH)
    serviceFlash(now);
  else
    runSignalStateMachine(now);

  serviceReadback(now);

  if (now - lastHealthTime >= HEALTH_PERIOD_MS)
  {
    lastHealthTime = now;
    publishHealth(now);
  }
}
