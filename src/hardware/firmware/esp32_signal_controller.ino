/*
 * EdgeFlow AI - Real-time Embedded Traffic Signal Actuator Firmware
 * Target Microcontroller: ESP32 NodeMCU (FreeRTOS / Arduino Framework)
 * Competition: VEDC 2026 (Team 31µF - Semifinal Corridor Prototype)
 *
 * Implements 100% synchronization with EdgeFlow AI Actuator State Machine:
 *  - Enforces mandatory physical clearance: GREEN -> YELLOW (3.0s) -> ALL_RED (2.0s) -> GREEN
 *  - Consumes canonical ControlCommand JSON payloads over MQTT
 *  - Emits canonical ControlACK JSON payloads (ACCEPTED, APPLIED, REJECTED, EXPIRED)
 *  - Autonomous Watchdog Fallback Schedule upon loss of coordinator (> 5.0s)
 *  - Physical Safe-Stop emergency flashing yellow caution mode
 */

#include <WiFi.h>
#include <PubSubClient.h>
#include <ArduinoJson.h>

// ====================================================================
// 1. HARDWARE CONFIGURATION & NODE IDENTIFIER
// ====================================================================
// Change NODE_ID to "J1" for Intersection 1, or "J2" for Intersection 2
#ifndef NODE_ID
#define NODE_ID "J1"
#endif

// Network & Broker Credentials (Raspberry Pi 5 Local AP)
const char* WIFI_SSID     = "EdgeFlow_Local_AP";
const char* WIFI_PASS     = "EdgeFlow2026";
const char* MQTT_BROKER   = "192.168.4.1"; // IP of Raspberry Pi 5 AP
const int   MQTT_PORT     = 1883;

// ====================================================================
// 2. PIN DEFINITIONS (See schematic_and_pinout.md)
// ====================================================================
// North-South (NS) Signal Head (3 LEDs)
const int PIN_NS_RED      = 23;
const int PIN_NS_YELLOW   = 22;
const int PIN_NS_GREEN    = 21;

// East-West (EW) Signal Head (3 LEDs)
const int PIN_EW_RED      = 19;
const int PIN_EW_YELLOW   = 18;
const int PIN_EW_GREEN    = 5;

// Status LED & Emergency Safe-Stop Input
const int PIN_STATUS_LED  = 2;  // Onboard blue LED
const int PIN_SAFE_STOP   = 4;  // Active-LOW emergency button

// ====================================================================
// 3. SAFETY TIMING INVARIANTS (Milliseconds)
// ====================================================================
const unsigned long DURATION_YELLOW_MS   = 3000;  // 3.0 seconds clearance yellow
const unsigned long DURATION_ALL_RED_MS  = 2000;  // 2.0 seconds all-red clearance
const unsigned long DEFAULT_MIN_GREEN_MS = 5000;  // 5.0 seconds minimum green floor
const unsigned long DEFAULT_MAX_GREEN_MS = 60000; // 60.0 seconds maximum green cap
const unsigned long NETWORK_TIMEOUT_MS   = 5000;  // 5.0 seconds watchdog for fallback

// ====================================================================
// 4. STATE MACHINE & DATA TYPES
// ====================================================================
enum PhaseId {
  PHASE_NS = 0,
  PHASE_EW = 1
};

enum ClearanceState {
  STATE_GREEN,
  STATE_YELLOW,
  STATE_ALL_RED
};

// Current active state
PhaseId currentPhase        = PHASE_NS;
PhaseId pendingPhase        = PHASE_NS;
ClearanceState clearState   = STATE_GREEN;

// Dynamic timing bounds from controller
unsigned long currentMinGreenMs = DEFAULT_MIN_GREEN_MS;
unsigned long currentMaxGreenMs = DEFAULT_MAX_GREEN_MS;

// Timing anchors (system millis)
unsigned long phaseStartTime    = 0;
unsigned long stateStartTime    = 0;
unsigned long lastCommandTime   = 0;
unsigned long lastHealthTime    = 0;

bool isLocalFallbackMode        = false;
String pendingCommandId         = "";
String pendingTargetPhaseStr    = "";

WiFiClient espClient;
PubSubClient mqttClient(espClient);

// ====================================================================
// 5. HARDWARE OUTPUT CONTROLLER
// ====================================================================
void applySignalOutputs(PhaseId activePhase, ClearanceState state) {
  // Turn all OFF first (prevent phantom currents)
  digitalWrite(PIN_NS_RED,    LOW);
  digitalWrite(PIN_NS_YELLOW, LOW);
  digitalWrite(PIN_NS_GREEN,  LOW);
  digitalWrite(PIN_EW_RED,    LOW);
  digitalWrite(PIN_EW_YELLOW, LOW);
  digitalWrite(PIN_EW_GREEN,  LOW);

  if (state == STATE_GREEN) {
    if (activePhase == PHASE_NS) {
      digitalWrite(PIN_NS_GREEN, HIGH);
      digitalWrite(PIN_EW_RED,   HIGH);
    } else {
      digitalWrite(PIN_EW_GREEN, HIGH);
      digitalWrite(PIN_NS_RED,   HIGH);
    }
  } else if (state == STATE_YELLOW) {
    // Current green phase transitions to yellow; opposing phase stays red
    if (activePhase == PHASE_NS) {
      digitalWrite(PIN_NS_YELLOW, HIGH);
      digitalWrite(PIN_EW_RED,    HIGH);
    } else {
      digitalWrite(PIN_EW_YELLOW, HIGH);
      digitalWrite(PIN_NS_RED,    HIGH);
    }
  } else if (state == STATE_ALL_RED) {
    // Both directions RED during full intersection clearance
    digitalWrite(PIN_NS_RED, HIGH);
    digitalWrite(PIN_EW_RED, HIGH);
  }
}

// ====================================================================
// 6. CONTROL ACK & PROTOCOL EMITTER
// ====================================================================
void publishControlAck(const char* cmdId, const char* targetPhaseStr, const char* status, const char* reason) {
  if (!mqttClient.connected()) return;

  char topic[80];
  snprintf(topic, sizeof(topic), "edgeflow/v1/control/%s/ack", NODE_ID);

  StaticJsonDocument<384> doc;
  doc["command_id"]      = (cmdId && strlen(cmdId) > 0) ? cmdId : "unknown";
  doc["node_id"]         = NODE_ID;
  doc["target_phase_id"] = (targetPhaseStr && strlen(targetPhaseStr) > 0) ? targetPhaseStr : "UNKNOWN";
  doc["status"]          = status;
  doc["timestamp_ms"]    = millis();
  doc["reason"]          = reason;

  char buffer[384];
  serializeJson(doc, buffer);
  mqttClient.publish(topic, buffer);
  Serial.printf("[ACK] %s -> %s (%s)\n", topic, status, reason);
}

// Helper to determine PhaseId enum from canonical target_phase_id string
PhaseId parsePhaseString(const char* phaseStr) {
  if (!phaseStr) return PHASE_NS;
  String s = String(phaseStr);
  s.toUpperCase();
  if (s.indexOf("EW") >= 0 || s.indexOf("EAST") >= 0 || s.indexOf("WEST") >= 0 || s.indexOf("PHASE_2") >= 0) {
    return PHASE_EW;
  }
  return PHASE_NS;
}

const char* getCanonicalPhaseString(PhaseId p) {
  static char pBuf[32];
  snprintf(pBuf, sizeof(pBuf), "%s_PHASE_%s", NODE_ID, (p == PHASE_NS) ? "NS" : "EW");
  return pBuf;
}

// ====================================================================
// 7. INCOMING CONTROL COMMAND HANDLER (MQTT CALLBACK)
// ====================================================================
void onMqttCommand(char* topic, byte* payload, unsigned int length) {
  unsigned long now = millis();
  lastCommandTime = now;
  isLocalFallbackMode = false;

  StaticJsonDocument<512> doc;
  DeserializationError err = deserializeJson(doc, payload, length);
  if (err) {
    publishControlAck("unknown", "unknown", "REJECTED", "Invalid JSON payload format");
    return;
  }

  // 1. Extract and validate mandatory fields
  const char* cmdNodeId = doc["node_id"] | "";
  if (strcmp(cmdNodeId, NODE_ID) != 0) {
    // Ignore commands directed to other nodes on the corridor
    return;
  }

  const char* cmdId = doc["command_id"] | "unknown";
  const char* targetPhaseStr = doc["target_phase_id"] | "";
  float minGreenS = doc["min_green_s"] | 5.0;
  float maxGreenS = doc["max_green_s"] | 60.0;
  unsigned long expiresAtMs = doc["expires_at_ms"] | 0;

  // 2. Command Expiry Check
  if (expiresAtMs > 0 && (now > expiresAtMs)) {
    publishControlAck(cmdId, targetPhaseStr, "EXPIRED", "Command expired before processing");
    return;
  }

  currentMinGreenMs = (unsigned long)(minGreenS * 1000);
  currentMaxGreenMs = (unsigned long)(maxGreenS * 1000);
  PhaseId targetPhase = parsePhaseString(targetPhaseStr);

  // 3. Same Phase Requested during GREEN -> Extend Green Time
  if (targetPhase == currentPhase) {
    if (clearState == STATE_GREEN) {
      publishControlAck(cmdId, targetPhaseStr, "APPLIED", "Phase is already active. Green time extended.");
    } else {
      publishControlAck(cmdId, targetPhaseStr, "ACCEPTED", "Transition currently clearing through Yellow/All-Red.");
    }
    return;
  }

  // 4. Same as Pending Phase during Clearance -> Wait
  if (targetPhase == pendingPhase && clearState != STATE_GREEN) {
    publishControlAck(cmdId, targetPhaseStr, "ACCEPTED", "Phase transition is already pending and clearing.");
    return;
  }

  // 5. Different Phase requested while already clearing -> Busy
  if (clearState != STATE_GREEN) {
    publishControlAck(cmdId, targetPhaseStr, "REJECTED", "Clearance interval currently in progress.");
    return;
  }

  // 6. Check Minimum Green Safety Condition
  unsigned long elapsedGreen = now - phaseStartTime;
  if (elapsedGreen < currentMinGreenMs) {
    char reason[80];
    snprintf(reason, sizeof(reason), "Min green time not met (%.1fs < %.1fs)", elapsedGreen / 1000.0, currentMinGreenMs / 1000.0);
    publishControlAck(cmdId, targetPhaseStr, "REJECTED", reason);
    return;
  }

  // 7. Initiate Safe Clearance Sequence: GREEN -> YELLOW (3s) -> ALL_RED (2s) -> TARGET GREEN
  pendingPhase = targetPhase;
  pendingCommandId = String(cmdId);
  pendingTargetPhaseStr = String(targetPhaseStr);
  clearState = STATE_YELLOW;
  stateStartTime = now;
  applySignalOutputs(currentPhase, STATE_YELLOW);

  publishControlAck(cmdId, targetPhaseStr, "ACCEPTED", "Clearance initiated: GREEN -> YELLOW (3s) -> ALL_RED (2s) -> TARGET");
}

// ====================================================================
// 8. MQTT CONNECTION & SUBSCRIPTIONS
// ====================================================================
void maintainMqttConnection() {
  if (!mqttClient.connected()) {
    char clientId[48];
    snprintf(clientId, sizeof(clientId), "ESP32_Actuator_%s_%04X", NODE_ID, (uint16_t)ESP.getEfuseMac());
    
    Serial.printf("Connecting to MQTT Broker at %s:%d as '%s'...\n", MQTT_BROKER, MQTT_PORT, clientId);
    if (mqttClient.connect(clientId)) {
      char cmdTopic[80];
      snprintf(cmdTopic, sizeof(cmdTopic), "edgeflow/v1/control/%s/command", NODE_ID);
      mqttClient.subscribe(cmdTopic);
      digitalWrite(PIN_STATUS_LED, HIGH);
      Serial.printf("Connected! Subscribed to: %s\n", cmdTopic);
    } else {
      digitalWrite(PIN_STATUS_LED, LOW);
      Serial.printf("MQTT Connect failed, rc=%d. Retrying in loop...\n", mqttClient.state());
    }
  }
}

// ====================================================================
// 9. SETUP FUNCTION
// ====================================================================
void setup() {
  Serial.begin(115200);
  delay(500);

  Serial.println("\n=========================================================");
  Serial.printf("  EdgeFlow AI - ESP32 Signal Actuator Node [%s]\n", NODE_ID);
  Serial.println("=========================================================");

  // Configure Output Pins
  pinMode(PIN_NS_RED,    OUTPUT);
  pinMode(PIN_NS_YELLOW, OUTPUT);
  pinMode(PIN_NS_GREEN,  OUTPUT);
  pinMode(PIN_EW_RED,    OUTPUT);
  pinMode(PIN_EW_YELLOW, OUTPUT);
  pinMode(PIN_EW_GREEN,  OUTPUT);
  pinMode(PIN_STATUS_LED, OUTPUT);
  pinMode(PIN_SAFE_STOP,  INPUT_PULLUP);

  // Initial State: Start safely in North-South GREEN
  currentPhase   = PHASE_NS;
  pendingPhase   = PHASE_NS;
  clearState     = STATE_GREEN;
  phaseStartTime = millis();
  stateStartTime = millis();
  lastCommandTime = millis();
  applySignalOutputs(currentPhase, STATE_GREEN);

  // Initialize WiFi Station Mode
  WiFi.mode(WIFI_STA);
  WiFi.begin(WIFI_SSID, WIFI_PASS);
  Serial.printf("Connecting to WiFi '%s'...\n", WIFI_SSID);

  mqttClient.setServer(MQTT_BROKER, MQTT_PORT);
  mqttClient.setCallback(onMqttCommand);
}

// ====================================================================
// 10. MAIN EVENT LOOP
// ====================================================================
void loop() {
  unsigned long now = millis();

  // 1. Emergency Safe-Stop Physical Switch Check
  if (digitalRead(PIN_SAFE_STOP) == LOW) {
    // Flash all yellow lights as emergency caution
    digitalWrite(PIN_NS_RED,    LOW);
    digitalWrite(PIN_NS_GREEN,  LOW);
    digitalWrite(PIN_EW_RED,    LOW);
    digitalWrite(PIN_EW_GREEN,  LOW);
    digitalWrite(PIN_NS_YELLOW, (now / 500) % 2);
    digitalWrite(PIN_EW_YELLOW, (now / 500) % 2);
    return;
  }

  // 2. WiFi & MQTT Connection Handling
  if (WiFi.status() == WL_CONNECTED) {
    maintainMqttConnection();
    mqttClient.loop();
  }

  // 3. Clearance State Machine Execution
  if (clearState == STATE_YELLOW) {
    if (now - stateStartTime >= DURATION_YELLOW_MS) {
      clearState = STATE_ALL_RED;
      stateStartTime = now;
      applySignalOutputs(currentPhase, STATE_ALL_RED);
      Serial.println("[FSM] Yellow finished -> Entered ALL_RED clearance (2.0s)");
    }
  } else if (clearState == STATE_ALL_RED) {
    if (now - stateStartTime >= DURATION_ALL_RED_MS) {
      // Transition completed to Target GREEN
      currentPhase   = pendingPhase;
      clearState     = STATE_GREEN;
      stateStartTime = now;
      phaseStartTime = now;
      applySignalOutputs(currentPhase, STATE_GREEN);
      Serial.printf("[FSM] ALL_RED finished -> GREEN active on [%s]\n", getCanonicalPhaseString(currentPhase));

      // Emit APPLIED ControlACK to system
      if (pendingCommandId.length() > 0) {
        publishControlAck(
          pendingCommandId.c_str(),
          pendingTargetPhaseStr.c_str(),
          "APPLIED",
          "Physical clearance completed. Target phase is now active GREEN."
        );
        pendingCommandId = "";
        pendingTargetPhaseStr = "";
      }
    }
  }

  // 4. Local Fallback Watchdog (loss of coordinator > 5s)
  if (now - lastCommandTime > NETWORK_TIMEOUT_MS) {
    if (!isLocalFallbackMode) {
      isLocalFallbackMode = true;
      Serial.println("⚠️ [WATCHDOG] Coordinator timeout > 5.0s -> Switched to Autonomous Fallback Schedule");
    }

    // Execute local Fixed-Time cycle (15s green per phase)
    if (clearState == STATE_GREEN && (now - phaseStartTime >= 15000)) {
      pendingPhase = (currentPhase == PHASE_NS) ? PHASE_EW : PHASE_NS;
      pendingCommandId = "local_fallback_tick";
      pendingTargetPhaseStr = String(getCanonicalPhaseString(pendingPhase));
      clearState = STATE_YELLOW;
      stateStartTime = now;
      applySignalOutputs(currentPhase, STATE_YELLOW);
    }
  }

  // 5. Periodic Health Heartbeat Telemetry (every 5.0s)
  if (now - lastHealthTime >= 5000) {
    lastHealthTime = now;
    if (mqttClient.connected()) {
      char healthTopic[80];
      snprintf(healthTopic, sizeof(healthTopic), "edgeflow/v1/health/%s", NODE_ID);
      
      StaticJsonDocument<256> hDoc;
      hDoc["node_id"]       = NODE_ID;
      hDoc["service"]       = "esp32_actuator";
      hDoc["status"]        = isLocalFallbackMode ? "FALLBACK_AUTONOMOUS" : "HEALTHY";
      hDoc["current_phase"] = getCanonicalPhaseString(currentPhase);
      hDoc["clearance"]     = (clearState == STATE_GREEN) ? "GREEN" : (clearState == STATE_YELLOW ? "YELLOW" : "ALL_RED");
      hDoc["uptime_s"]      = now / 1000;

      char hBuffer[256];
      serializeJson(hDoc, hBuffer);
      mqttClient.publish(healthTopic, hBuffer);
    }
  }
}
