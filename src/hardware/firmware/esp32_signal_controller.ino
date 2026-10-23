/*
 * EdgeFlow AI - Real-time Embedded Traffic Signal Actuator Firmware
 * Target Microcontroller: ESP32 NodeMCU-32S (FreeRTOS / Arduino Framework)
 * Competition: VEDC 2026 (Team 31µF - Semifinal Corridor Prototype)
 *
 * Implements 100% synchronization with EdgeFlow AI Actuator State Machine:
 *  - Enforces mandatory physical clearance: GREEN -> YELLOW (3.0s) -> ALL_RED (2.0s) -> GREEN
 *  - Consumes canonical ControlCommand JSON payloads over MQTT
 *  - Emits canonical ControlACK JSON payloads (ACCEPTED, APPLIED, REJECTED, EXPIRED, FAILED)
 *  - Autonomous Watchdog Fallback Schedule upon loss of coordinator (> 5.0s)
 *  - Hardware task watchdog: a hung loop resets the board into the defined boot state
 *  - Physical Safe-Stop emergency flashing yellow caution mode
 *  - Serial output trace (TRACE lines) of every signal change for timing evidence
 *
 * Build with PlatformIO from src/hardware/: `pio run -e J1 -t upload` (see platformio.ini).
 * Network settings come from build flags (secrets.ini); the defaults below are fallbacks.
 */

#define ARDUINOJSON_USE_LONG_LONG 1

#include <WiFi.h>
#include <PubSubClient.h>
#include <ArduinoJson.h>
#include <esp_task_wdt.h>
#include <esp_arduino_version.h>
#include <sys/time.h>
#include <time.h>

// ====================================================================
// 1. HARDWARE CONFIGURATION & NODE IDENTIFIER
// ====================================================================
// Change NODE_ID to "J1" for Intersection 1, or "J2" for Intersection 2
#ifndef NODE_ID
#define NODE_ID "J1"
#endif

// Network & Broker Credentials (override with -D flags in secrets.ini)
#ifndef WIFI_SSID
#define WIFI_SSID "Kinghouse B11-12"
#endif
#ifndef WIFI_PASS
#define WIFI_PASS "kingshouse2018"
#endif
#ifndef MQTT_BROKER
#define MQTT_BROKER "172.30.80.1" // IP of the host running Mosquitto
#endif
#ifndef NTP_SERVER
#define NTP_SERVER MQTT_BROKER // e.g. the Pi running chrony (infra/rpi/setup_pi.sh)
#endif
const int MQTT_PORT = 1883;

// ====================================================================
// 2. PIN DEFINITIONS (See schematic_and_pinout.md)
// ====================================================================
// North-South (NS) Signal Head (3 LEDs; N and S modules wired in parallel)
const int PIN_NS_RED = 23;
const int PIN_NS_YELLOW = 22;
const int PIN_NS_GREEN = 21;

// East-West (EW) Signal Head (3 LEDs; E and W modules wired in parallel)
const int PIN_EW_RED = 19;
const int PIN_EW_YELLOW = 18;
const int PIN_EW_GREEN = 5;

// Status LED & Emergency Safe-Stop Input
// SAFE_STOP_GPIO can be overridden per board in platformio.ini (J1 is soldered to GPIO 16)
#ifndef SAFE_STOP_GPIO
#define SAFE_STOP_GPIO 4
#endif
// Input level that means "pressed": LOW for a normally-open contact to GND (default),
// HIGH for a normally-closed contact (J1 and J2 buttons are wired on their NC contact)
#ifndef SAFE_STOP_PRESSED_LEVEL
#define SAFE_STOP_PRESSED_LEVEL LOW
#endif
const int PIN_STATUS_LED = 2;             // Onboard blue LED
const int PIN_SAFE_STOP = SAFE_STOP_GPIO; // Active-LOW emergency button (use a latching button)

// ====================================================================
// 3. SAFETY TIMING INVARIANTS (Milliseconds)
// ====================================================================
const unsigned long DURATION_YELLOW_MS = 3000;    // 3.0 seconds clearance yellow
const unsigned long DURATION_ALL_RED_MS = 2000;   // 2.0 seconds all-red clearance
const unsigned long DEFAULT_MIN_GREEN_MS = 5000;  // 5.0 seconds minimum green floor (device-owned)
const unsigned long DEFAULT_MAX_GREEN_MS = 60000; // 60.0 seconds maximum green cap (device-owned)
const unsigned long NETWORK_TIMEOUT_MS = 5000;    // 5.0 seconds watchdog for fallback
const unsigned long FALLBACK_GREEN_MS = 15000;    // 15.0 seconds green per phase in fallback
const unsigned long SAFE_STOP_DEBOUNCE_MS = 50;   // input must be stable this long
const unsigned long SAFE_STOP_FLASH_MS = 500;     // flashing yellow half-period
const unsigned long HEALTH_PERIOD_MS = 5000;
const unsigned long MQTT_RETRY_MS = 2000; // reconnect attempt spacing
const uint32_t HW_WATCHDOG_S = 10;        // > worst-case blocking MQTT connect (~5 s)
const uint16_t MQTT_BUFFER_BYTES = 1024;  // PubSubClient default (256) truncates ACKs

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
  STATE_ALL_RED
};

// Current active state
PhaseId currentPhase = PHASE_NS;
PhaseId pendingPhase = PHASE_NS;
ClearanceState clearState = STATE_GREEN;

// Dynamic timing bounds from controller (clamped to device limits)
unsigned long currentMinGreenMs = DEFAULT_MIN_GREEN_MS;
unsigned long currentMaxGreenMs = DEFAULT_MAX_GREEN_MS;

// Timing anchors (system millis)
unsigned long phaseStartTime = 0;
unsigned long stateStartTime = 0;
unsigned long lastCommandTime = 0;
unsigned long lastHealthTime = 0;
unsigned long lastMqttAttempt = 0;

bool isLocalFallbackMode = false;
String pendingCommandId = "";
String pendingTargetPhaseStr = "";

// Safe-stop debounce state
bool safeStopActive = false;
bool safeStopRawLast = false;
unsigned long safeStopRawSince = 0;

// Last written head colours ('R', 'Y', 'G' or '-') for change-only tracing
char lastNs = '?';
char lastEw = '?';

WiFiClient espClient;
PubSubClient mqttClient(espClient);

// ====================================================================
// 5. CLOCK HELPERS (UTC via SNTP when available)
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

// ====================================================================
// 6. HARDWARE OUTPUT CONTROLLER
// ====================================================================
const char *clearanceName(ClearanceState state)
{
  return (state == STATE_GREEN) ? "GREEN" : (state == STATE_YELLOW ? "YELLOW" : "ALL_RED");
}

// Writes both heads. Refuses a conflicting double green and logs every change as
// "TRACE,<millis>,<node>,<ns>,<ew>,<label>" for output-timing evidence.
void writeHeads(char ns, char ew, const char *label)
{
  if (ns == 'G' && ew == 'G')
  {
    Serial.println("ERROR,conflicting green requested -> forcing ALL_RED");
    ns = 'R';
    ew = 'R';
    label = "CONFLICT_GUARD";
  }
  // Turn all OFF first (prevent phantom currents), then light the requested colours
  digitalWrite(PIN_NS_RED, LOW);
  digitalWrite(PIN_NS_YELLOW, LOW);
  digitalWrite(PIN_NS_GREEN, LOW);
  digitalWrite(PIN_EW_RED, LOW);
  digitalWrite(PIN_EW_YELLOW, LOW);
  digitalWrite(PIN_EW_GREEN, LOW);
  if (ns == 'R')
    digitalWrite(PIN_NS_RED, HIGH);
  if (ns == 'Y')
    digitalWrite(PIN_NS_YELLOW, HIGH);
  if (ns == 'G')
    digitalWrite(PIN_NS_GREEN, HIGH);
  if (ew == 'R')
    digitalWrite(PIN_EW_RED, HIGH);
  if (ew == 'Y')
    digitalWrite(PIN_EW_YELLOW, HIGH);
  if (ew == 'G')
    digitalWrite(PIN_EW_GREEN, HIGH);

  if (ns != lastNs || ew != lastEw)
  {
    lastNs = ns;
    lastEw = ew;
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
    // Current green phase transitions to yellow; opposing phase stays red
    if (activePhase == PHASE_NS)
      writeHeads('Y', 'R', "YELLOW");
    else
      writeHeads('R', 'Y', "YELLOW");
  }
  else
  {
    // Both directions RED during full intersection clearance
    writeHeads('R', 'R', "ALL_RED");
  }
}

// ====================================================================
// 7. CONTROL ACK, HEALTH & PROTOCOL EMITTER
// ====================================================================
void publishControlAck(const char *cmdId, const char *targetPhaseStr, const char *status, const char *reason)
{
  Serial.printf("[ACK] %s %s (%s)\n", status, cmdId ? cmdId : "", reason);
  if (!mqttClient.connected())
    return;

  char topic[80];
  snprintf(topic, sizeof(topic), "edgeflow/v1/control/%s/ack", NODE_ID);

  StaticJsonDocument<512> doc;
  doc["command_id"] = (cmdId && strlen(cmdId) > 0) ? cmdId : "unknown";
  doc["node_id"] = NODE_ID;
  doc["target_phase_id"] = (targetPhaseStr && strlen(targetPhaseStr) > 0) ? targetPhaseStr : "UNKNOWN";
  doc["status"] = status;
  if (isClockSynced())
  {
    doc["timestamp_ms"] = epochMs(); // UTC Unix ms (contract unit)
  }
  doc["uptime_ms"] = millis();
  doc["reason"] = reason;

  char buffer[512];
  size_t len = serializeJson(doc, buffer, sizeof(buffer));
  if (!mqttClient.publish(topic, (const uint8_t *)buffer, len, false))
  {
    Serial.println("ERROR,ACK publish failed (buffer/connection)");
  }
}

void publishHealth(unsigned long now)
{
  if (!mqttClient.connected())
    return;
  char healthTopic[80];
  snprintf(healthTopic, sizeof(healthTopic), "edgeflow/v1/health/%s", NODE_ID);

  const char *status = safeStopActive ? "SAFE_STOP" : (isLocalFallbackMode ? "FALLBACK_AUTONOMOUS" : "HEALTHY");
  StaticJsonDocument<384> hDoc;
  hDoc["node_id"] = NODE_ID;
  hDoc["service"] = "esp32_actuator";
  hDoc["status"] = status;
  hDoc["current_phase"] = String(NODE_ID) + (currentPhase == PHASE_NS ? "_PHASE_NS" : "_PHASE_EW");
  hDoc["clearance"] = clearanceName(clearState);
  hDoc["safe_stop"] = safeStopActive;
  hDoc["uptime_s"] = now / 1000;
  hDoc["wifi_rssi_dbm"] = WiFi.RSSI();
  if (isClockSynced())
  {
    hDoc["timestamp_ms"] = epochMs();
  }

  char hBuffer[384];
  size_t len = serializeJson(hDoc, hBuffer, sizeof(hBuffer));
  mqttClient.publish(healthTopic, (const uint8_t *)hBuffer, len, false);
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

String canonicalPhaseString(PhaseId p)
{
  return String(NODE_ID) + (p == PHASE_NS ? "_PHASE_NS" : "_PHASE_EW");
}

// GREEN -> YELLOW (3s) -> ALL_RED (2s) -> target GREEN. An empty cmdId means no APPLIED ACK.
void startClearance(PhaseId target, const String &cmdId, const String &targetStr, unsigned long now)
{
  pendingPhase = target;
  pendingCommandId = cmdId;
  pendingTargetPhaseStr = targetStr;
  clearState = STATE_YELLOW;
  stateStartTime = now;
  applySignalOutputs(currentPhase, STATE_YELLOW);
}

// ====================================================================
// 8. INCOMING CONTROL COMMAND HANDLER (MQTT CALLBACK)
// ====================================================================
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

  // 1. Extract and validate mandatory fields
  const char *cmdNodeId = doc["node_id"] | "";
  if (strcmp(cmdNodeId, NODE_ID) != 0)
  {
    // Ignore commands directed to other nodes on the corridor
    return;
  }

  // A well-formed command for this node proves the coordinator is alive.
  lastCommandTime = now;
  if (isLocalFallbackMode)
  {
    isLocalFallbackMode = false;
    Serial.println("[WATCHDOG] Coordinator command received -> leaving autonomous fallback");
  }

  const char *cmdId = doc["command_id"] | "unknown";
  const char *targetPhaseStr = doc["target_phase_id"] | "";

  if (safeStopActive)
  {
    publishControlAck(cmdId, targetPhaseStr, "REJECTED", "Safe-stop is engaged");
    return;
  }

  // 2. Command Expiry Check (UTC ms; only meaningful once SNTP has synced the clock)
  uint64_t expiresAtMs = doc["expires_at_ms"] | (uint64_t)0;
  if (expiresAtMs > 0 && isClockSynced() && epochMs() > expiresAtMs)
  {
    publishControlAck(cmdId, targetPhaseStr, "EXPIRED", "Command expired before processing");
    return;
  }

  PhaseId targetPhase;
  if (!parsePhaseString(targetPhaseStr, targetPhase))
  {
    publishControlAck(cmdId, targetPhaseStr, "REJECTED", "Unknown target_phase_id for this node");
    return;
  }

  // Requested timings may lengthen but never shorten the device limits.
  float minGreenS = doc["min_green_s"] | 5.0f;
  float maxGreenS = doc["max_green_s"] | 60.0f;
  unsigned long reqMinMs = (unsigned long)(max(minGreenS, 0.0f) * 1000.0f);
  unsigned long reqMaxMs = (unsigned long)(max(maxGreenS, 0.0f) * 1000.0f);
  currentMinGreenMs = max(reqMinMs, DEFAULT_MIN_GREEN_MS);
  currentMaxGreenMs = min(max(reqMaxMs, currentMinGreenMs), DEFAULT_MAX_GREEN_MS);

  // 3. Same Phase Requested during GREEN -> Extend Green Time
  if (targetPhase == currentPhase)
  {
    if (clearState == STATE_GREEN)
    {
      publishControlAck(cmdId, targetPhaseStr, "APPLIED", "Phase is already active. Green time extended.");
    }
    else
    {
      publishControlAck(cmdId, targetPhaseStr, "ACCEPTED", "Transition currently clearing through Yellow/All-Red.");
    }
    return;
  }

  // 4. Same as Pending Phase during Clearance -> Wait
  if (targetPhase == pendingPhase && clearState != STATE_GREEN)
  {
    publishControlAck(cmdId, targetPhaseStr, "ACCEPTED", "Phase transition is already pending and clearing.");
    return;
  }

  // 5. Different Phase requested while already clearing -> Busy
  if (clearState != STATE_GREEN)
  {
    publishControlAck(cmdId, targetPhaseStr, "REJECTED", "Clearance interval currently in progress.");
    return;
  }

  // 6. Check Minimum Green Safety Condition
  unsigned long elapsedGreen = now - phaseStartTime;
  if (elapsedGreen < currentMinGreenMs)
  {
    char reason[80];
    snprintf(reason, sizeof(reason), "Min green time not met (%.1fs < %.1fs)", elapsedGreen / 1000.0, currentMinGreenMs / 1000.0);
    publishControlAck(cmdId, targetPhaseStr, "REJECTED", reason);
    return;
  }

  // 7. Initiate Safe Clearance Sequence: GREEN -> YELLOW (3s) -> ALL_RED (2s) -> TARGET GREEN
  startClearance(targetPhase, String(cmdId), String(targetPhaseStr), now);
  publishControlAck(cmdId, targetPhaseStr, "ACCEPTED", "Clearance initiated: GREEN -> YELLOW (3s) -> ALL_RED (2s) -> TARGET");
}

// ====================================================================
// 9. MQTT CONNECTION & SUBSCRIPTIONS
// ====================================================================
void maintainMqttConnection(unsigned long now)
{
  if (mqttClient.connected())
    return;
  // A connect attempt can block for seconds; never let it stretch YELLOW/ALL_RED timing.
  // During safe-stop the clearance timers are frozen, so reconnecting (for health reports) is fine.
  if (clearState != STATE_GREEN && !safeStopActive)
    return;
  if (now - lastMqttAttempt < MQTT_RETRY_MS)
    return;
  lastMqttAttempt = now;

  char clientId[48];
  snprintf(clientId, sizeof(clientId), "ESP32_Actuator_%s_%04X", NODE_ID, (uint16_t)ESP.getEfuseMac());
  char willTopic[80];
  snprintf(willTopic, sizeof(willTopic), "edgeflow/v1/health/%s", NODE_ID);
  char willPayload[96];
  snprintf(willPayload, sizeof(willPayload), "{\"node_id\":\"%s\",\"service\":\"esp32_actuator\",\"status\":\"OFFLINE\"}", NODE_ID);

  Serial.printf("Connecting to MQTT Broker at %s:%d as '%s'...\n", MQTT_BROKER, MQTT_PORT, clientId);
  if (mqttClient.connect(clientId, willTopic, 0, false, willPayload))
  {
    char cmdTopic[80];
    snprintf(cmdTopic, sizeof(cmdTopic), "edgeflow/v1/control/%s/command", NODE_ID);
    mqttClient.subscribe(cmdTopic);
    digitalWrite(PIN_STATUS_LED, HIGH);
    Serial.printf("Connected! Subscribed to: %s\n", cmdTopic);
    publishHealth(now);
  }
  else
  {
    digitalWrite(PIN_STATUS_LED, LOW);
    Serial.printf("MQTT Connect failed, rc=%d. Retrying in %lums...\n", mqttClient.state(), MQTT_RETRY_MS);
  }
}

// ====================================================================
// 10. SAFE-STOP INPUT
// ====================================================================
// Returns the debounced state of the safe-stop input (true = pressed).
bool readSafeStop(unsigned long now)
{
  bool raw = (digitalRead(PIN_SAFE_STOP) == SAFE_STOP_PRESSED_LEVEL);
  if (raw != safeStopRawLast)
  {
    safeStopRawLast = raw;
    safeStopRawSince = now;
  }
  if (raw != safeStopActive && now - safeStopRawSince >= SAFE_STOP_DEBOUNCE_MS)
  {
    return raw;
  }
  return safeStopActive;
}

void engageSafeStop(unsigned long now)
{
  safeStopActive = true;
  Serial.println("[SAFE-STOP] Engaged -> flashing yellow, commands rejected");
  if (pendingCommandId.length() > 0)
  {
    publishControlAck(pendingCommandId.c_str(), pendingTargetPhaseStr.c_str(), "FAILED",
                      "Safe-stop engaged before the transition was applied");
    pendingCommandId = "";
    pendingTargetPhaseStr = "";
  }
  publishHealth(now);
}

// Restart in a defined state: ALL_RED clearance, then GREEN on the last served phase.
void releaseSafeStop(unsigned long now)
{
  safeStopActive = false;
  pendingPhase = currentPhase;
  pendingCommandId = "";
  pendingTargetPhaseStr = "";
  clearState = STATE_ALL_RED;
  stateStartTime = now;
  applySignalOutputs(currentPhase, STATE_ALL_RED);
  Serial.println("[SAFE-STOP] Released -> ALL_RED clearance before resuming");
  publishHealth(now);
}

// ====================================================================
// 11. SETUP FUNCTION
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

  // Configure Output Pins
  pinMode(PIN_NS_RED, OUTPUT);
  pinMode(PIN_NS_YELLOW, OUTPUT);
  pinMode(PIN_NS_GREEN, OUTPUT);
  pinMode(PIN_EW_RED, OUTPUT);
  pinMode(PIN_EW_YELLOW, OUTPUT);
  pinMode(PIN_EW_GREEN, OUTPUT);
  pinMode(PIN_STATUS_LED, OUTPUT);
  pinMode(PIN_SAFE_STOP, INPUT_PULLUP);

  Serial.println("TRACE,millis,node,ns,ew,label");

  // Initial State: ALL_RED clearance first, then North-South GREEN (defined boot/restart state)
  unsigned long now = millis();
  currentPhase = PHASE_NS;
  pendingPhase = PHASE_NS;
  clearState = STATE_ALL_RED;
  phaseStartTime = now;
  stateStartTime = now;
  lastCommandTime = now;
  applySignalOutputs(currentPhase, STATE_ALL_RED);

  // Initialize WiFi Station Mode (no modem sleep: lower command latency)
  WiFi.mode(WIFI_STA);
  WiFi.setSleep(false);
  WiFi.setAutoReconnect(true);
  WiFi.begin(WIFI_SSID, WIFI_PASS);
  Serial.printf("Connecting to WiFi '%s'...\n", WIFI_SSID);

  configTime(0, 0, NTP_SERVER); // UTC; non-blocking SNTP

  mqttClient.setServer(MQTT_BROKER, MQTT_PORT);
  mqttClient.setCallback(onMqttCommand);
  mqttClient.setBufferSize(MQTT_BUFFER_BYTES);
  mqttClient.setSocketTimeout(2);

  setupHardwareWatchdog();
}

// ====================================================================
// 12. MAIN EVENT LOOP
// ====================================================================
void loop()
{
  unsigned long now = millis();
  esp_task_wdt_reset();

  // 1. Emergency Safe-Stop Physical Switch (debounced, level-based)
  bool pressed = readSafeStop(now);
  if (pressed && !safeStopActive)
    engageSafeStop(now);
  else if (!pressed && safeStopActive)
    releaseSafeStop(now);

  // 2. WiFi & MQTT Connection Handling (keeps running during safe-stop for health reports)
  if (WiFi.status() == WL_CONNECTED)
  {
    maintainMqttConnection(now);
    mqttClient.loop();
  }

  // onMqttCommand() runs inside mqttClient.loop() and stamps stateStartTime with a newer millis().
  // Refresh `now` so the unsigned `now - stateStartTime` below cannot wrap and skip the 3 s YELLOW.
  now = millis();

  if (safeStopActive)
  {
    // Flash all yellow lights as emergency caution
    bool on = (now / SAFE_STOP_FLASH_MS) % 2;
    writeHeads(on ? 'Y' : '-', on ? 'Y' : '-', "SAFE_STOP");
  }
  else
  {
    // 3. Clearance State Machine Execution
    if (clearState == STATE_YELLOW)
    {
      if (now - stateStartTime >= DURATION_YELLOW_MS)
      {
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
        // Transition completed to Target GREEN
        currentPhase = pendingPhase;
        clearState = STATE_GREEN;
        stateStartTime = now;
        phaseStartTime = now;
        applySignalOutputs(currentPhase, STATE_GREEN);
        Serial.printf("[FSM] ALL_RED finished -> GREEN active on [%s]\n", canonicalPhaseString(currentPhase).c_str());

        // Emit APPLIED ControlACK only after the output state has physically changed
        if (pendingCommandId.length() > 0)
        {
          publishControlAck(
              pendingCommandId.c_str(),
              pendingTargetPhaseStr.c_str(),
              "APPLIED",
              "Physical clearance completed. Target phase is now active GREEN.");
          pendingCommandId = "";
          pendingTargetPhaseStr = "";
        }
        // Every switch to GREEN (command, max green, fallback, safe-stop release, boot) announces the
        // new phase at once: vision copies it into telemetry current_phase_id instead of waiting 5 s
        publishHealth(now);
      }
    }

    // 4. Local Fallback Watchdog (loss of coordinator > 5s)
    if (now - lastCommandTime > NETWORK_TIMEOUT_MS)
    {
      if (!isLocalFallbackMode)
      {
        isLocalFallbackMode = true;
        Serial.println("[WATCHDOG] Coordinator timeout > 5.0s -> Switched to Autonomous Fallback Schedule");
        publishHealth(now);
      }

      // Execute local Fixed-Time cycle (15s green per phase); no ACK for local transitions
      if (clearState == STATE_GREEN && (now - phaseStartTime >= FALLBACK_GREEN_MS))
      {
        PhaseId next = (currentPhase == PHASE_NS) ? PHASE_EW : PHASE_NS;
        startClearance(next, "", canonicalPhaseString(next), now);
      }
    }
    else if (clearState == STATE_GREEN && (now - phaseStartTime >= currentMaxGreenMs))
    {
      // 5. Maximum green is enforced by the device even if the controller keeps requesting it
      PhaseId next = (currentPhase == PHASE_NS) ? PHASE_EW : PHASE_NS;
      Serial.println("[FSM] Max green reached -> forced clearance to the opposing phase");
      startClearance(next, "", canonicalPhaseString(next), now);
    }
  }

  // 6. Periodic Health Heartbeat Telemetry (every 5.0s)
  if (now - lastHealthTime >= HEALTH_PERIOD_MS)
  {
    lastHealthTime = now;
    publishHealth(now);
  }
}
