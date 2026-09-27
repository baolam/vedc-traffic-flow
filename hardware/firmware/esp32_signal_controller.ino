/*
 * EdgeFlow AI - Real-time Embedded Traffic Signal Actuator Firmware
 * Target Microcontroller: ESP32 NodeMCU
 * Competition: VEDC 2026 (Team 31µF)
 *
 * Implements safe clearance state transitions (Green -> Yellow -> All-Red),
 * ControlACK responses, and automatic Local Fallback Schedule on network loss.
 */

#include <WiFi.h>
#include <PubSubClient.h>
#include <ArduinoJson.h>

// ==========================================
// 1. CONFIGURATION & NETWORK CREDENTIALS
// ==========================================
const char* WIFI_SSID = "EdgeFlow_Local_AP";
const char* WIFI_PASS = "EdgeFlow2026";
const char* MQTT_BROKER = "192.168.4.1"; // Default IP of Raspberry Pi AP
const int MQTT_PORT = 1883;

// Set Node ID: "J1" for Intersection 1, "J2" for Intersection 2
const char* NODE_ID = "J1";

// ==========================================
// 2. PIN DEFINITIONS (See schematic_and_pinout.md)
// ==========================================
const int PIN_NS_RED    = 23;
const int PIN_NS_YELLOW = 22;
const int PIN_NS_GREEN  = 21;

const int PIN_EW_RED    = 19;
const int PIN_EW_YELLOW = 18;
const int PIN_EW_GREEN  = 5;

const int PIN_STATUS_LED = 2;
const int PIN_SAFE_STOP  = 4;

// ==========================================
// 3. SAFETY TIMINGS (in milliseconds)
// ==========================================
const unsigned long DURATION_YELLOW_MS  = 3000;
const unsigned long DURATION_ALL_RED_MS = 2000;
const unsigned long MIN_GREEN_MS        = 10000;
const unsigned long NETWORK_TIMEOUT_MS  = 5000; // Watchdog TTL for local fallback

// ==========================================
// 4. STATE MACHINE DEFINITIONS
// ==========================================
enum Phase {
  PHASE_NS,
  PHASE_EW
};

enum ClearanceState {
  STATE_GREEN,
  STATE_YELLOW,
  STATE_ALL_RED
};

Phase currentPhase = PHASE_NS;
Phase pendingPhase = PHASE_NS;
ClearanceState clearanceState = STATE_GREEN;

unsigned long phaseStartTime = 0;
unsigned long stateStartTime = 0;
unsigned long lastCommandTime = 0;
unsigned long lastHealthTime = 0;

bool isLocalFallbackMode = false;
String lastCommandId = "";

WiFiClient espClient;
PubSubClient mqttClient(espClient);

// ==========================================
// 5. HARDWARE ACTUATION HELPER
// ==========================================
void setSignalHardware(Phase activePhase, ClearanceState state) {
  // Turn all OFF first
  digitalWrite(PIN_NS_RED, LOW);
  digitalWrite(PIN_NS_YELLOW, LOW);
  digitalWrite(PIN_NS_GREEN, LOW);
  digitalWrite(PIN_EW_RED, LOW);
  digitalWrite(PIN_EW_YELLOW, LOW);
  digitalWrite(PIN_EW_GREEN, LOW);

  if (state == STATE_GREEN) {
    if (activePhase == PHASE_NS) {
      digitalWrite(PIN_NS_GREEN, HIGH);
      digitalWrite(PIN_EW_RED, HIGH);
    } else {
      digitalWrite(PIN_EW_GREEN, HIGH);
      digitalWrite(PIN_NS_RED, HIGH);
    }
  } else if (state == STATE_YELLOW) {
    if (activePhase == PHASE_NS) {
      digitalWrite(PIN_NS_YELLOW, HIGH);
      digitalWrite(PIN_EW_RED, HIGH);
    } else {
      digitalWrite(PIN_EW_YELLOW, HIGH);
      digitalWrite(PIN_NS_RED, HIGH);
    }
  } else if (state == STATE_ALL_RED) {
    // Both directions RED during clearance interval
    digitalWrite(PIN_NS_RED, HIGH);
    digitalWrite(PIN_EW_RED, HIGH);
  }
}

// ==========================================
// 6. MQTT & JSON PROTOCOL HANDLERS
// ==========================================
void sendAck(const char* cmdId, const char* targetPhaseStr, const char* status, const char* reason) {
  char topic[64];
  snprintf(topic, sizeof(topic), "edgeflow/v1/control/%s/ack", NODE_ID);

  StaticJsonDocument<256> doc;
  doc["command_id"] = cmdId;
  doc["node_id"] = NODE_ID;
  doc["target_phase_id"] = targetPhaseStr;
  doc["status"] = status;
  doc["timestamp_ms"] = millis();
  doc["reason"] = reason;

  char buffer[256];
  serializeJson(doc, buffer);
  mqttClient.publish(topic, buffer);
}

void onMqttMessage(char* topic, byte* payload, unsigned int length) {
  lastCommandTime = millis();
  isLocalFallbackMode = false;

  StaticJsonDocument<512> doc;
  DeserializationError err = deserializeJson(doc, payload, length);
  if (err) {
    sendAck("unknown", "unknown", "REJECTED", "JSON deserialization failed");
    return;
  }

  const char* cmdId = doc["command_id"] | "unknown";
  const char* targetPhaseStr = doc["target_phase_id"] | "";
  float minGreenS = doc["min_green_s"] | 10.0;
  unsigned long reqMinGreenMs = (unsigned long)(minGreenS * 1000);

  Phase targetPhase = (strstr(targetPhaseStr, "EW") != NULL) ? PHASE_EW : PHASE_NS;

  // If already in target phase
  if (targetPhase == currentPhase && clearanceState == STATE_GREEN) {
    sendAck(cmdId, targetPhaseStr, "APPLIED", "Phase is already active. Green time extended.");
    return;
  }

  // If currently in yellow or all-red clearance
  if (clearanceState != STATE_GREEN) {
    sendAck(cmdId, targetPhaseStr, "REJECTED", "Transition clearance in progress.");
    return;
  }

  // Check minimum green safety condition
  unsigned long elapsedGreen = millis() - phaseStartTime;
  if (elapsedGreen < reqMinGreenMs) {
    sendAck(cmdId, targetPhaseStr, "REJECTED", "Minimum green time constraint not met.");
    return;
  }

  // Start safe transition sequence: GREEN -> YELLOW -> ALL_RED -> TARGET GREEN
  pendingPhase = targetPhase;
  lastCommandId = cmdId;
  clearanceState = STATE_YELLOW;
  stateStartTime = millis();
  setSignalHardware(currentPhase, STATE_YELLOW);

  sendAck(cmdId, targetPhaseStr, "ACCEPTED", "Clearance sequence initiated (Yellow -> All-Red).");
}

void connectMqtt() {
  if (!mqttClient.connected()) {
    char clientId[32];
    snprintf(clientId, sizeof(clientId), "ESP32_Actuator_%s", NODE_ID);
    if (mqttClient.connect(clientId)) {
      char cmdTopic[64];
      snprintf(cmdTopic, sizeof(cmdTopic), "edgeflow/v1/control/%s/command", NODE_ID);
      mqttClient.subscribe(cmdTopic);
      digitalWrite(PIN_STATUS_LED, HIGH);
    } else {
      digitalWrite(PIN_STATUS_LED, LOW);
    }
  }
}

// ==========================================
// 7. SETUP & MAIN LOOP
// ==========================================
void setup() {
  Serial.begin(115200);

  pinMode(PIN_NS_RED, OUTPUT);
  pinMode(PIN_NS_YELLOW, OUTPUT);
  pinMode(PIN_NS_GREEN, OUTPUT);
  pinMode(PIN_EW_RED, OUTPUT);
  pinMode(PIN_EW_YELLOW, OUTPUT);
  pinMode(PIN_EW_GREEN, OUTPUT);
  pinMode(PIN_STATUS_LED, OUTPUT);
  pinMode(PIN_SAFE_STOP, INPUT_PULLUP);

  // Initial state: Start in North-South Green
  currentPhase = PHASE_NS;
  clearanceState = STATE_GREEN;
  phaseStartTime = millis();
  stateStartTime = millis();
  lastCommandTime = millis();
  setSignalHardware(currentPhase, STATE_GREEN);

  // Connect WiFi
  WiFi.mode(WIFI_STA);
  WiFi.begin(WIFI_SSID, WIFI_PASS);

  mqttClient.setServer(MQTT_BROKER, MQTT_PORT);
  mqttClient.setCallback(onMqttMessage);
}

void loop() {
  unsigned long now = millis();

  // 1. Safe-Stop Emergency Button Check
  if (digitalRead(PIN_SAFE_STOP) == LOW) {
    // Flash Yellows as emergency hazard caution
    digitalWrite(PIN_NS_YELLOW, (now / 500) % 2);
    digitalWrite(PIN_EW_YELLOW, (now / 500) % 2);
    return;
  }

  // 2. WiFi & MQTT Connection Handling
  if (WiFi.status() == WL_CONNECTED) {
    connectMqtt();
    mqttClient.loop();
  }

  // 3. Clearance State Machine Execution
  if (clearanceState == STATE_YELLOW) {
    if (now - stateStartTime >= DURATION_YELLOW_MS) {
      clearanceState = STATE_ALL_RED;
      stateStartTime = now;
      setSignalHardware(currentPhase, STATE_ALL_RED);
    }
  } else if (clearanceState == STATE_ALL_RED) {
    if (now - stateStartTime >= DURATION_ALL_RED_MS) {
      currentPhase = pendingPhase;
      clearanceState = STATE_GREEN;
      stateStartTime = now;
      phaseStartTime = now;
      setSignalHardware(currentPhase, STATE_GREEN);

      if (lastCommandId.length() > 0) {
        char phaseStr[32];
        snprintf(phaseStr, sizeof(phaseStr), "%s_PHASE_%s", NODE_ID, (currentPhase == PHASE_NS) ? "NS" : "EW");
        sendAck(lastCommandId.c_str(), phaseStr, "APPLIED", "Phase transition completed successfully.");
        lastCommandId = "";
      }
    }
  }

  // 4. Local Fallback Watchdog (loss of network/coordinator)
  if (now - lastCommandTime > NETWORK_TIMEOUT_MS) {
    isLocalFallbackMode = true;
    // Execute local Fixed-Time cycle (15s green per phase)
    if (clearanceState == STATE_GREEN && (now - phaseStartTime >= 15000)) {
      pendingPhase = (currentPhase == PHASE_NS) ? PHASE_EW : PHASE_NS;
      clearanceState = STATE_YELLOW;
      stateStartTime = now;
      setSignalHardware(currentPhase, STATE_YELLOW);
    }
  }

  // 5. Periodic Heartbeat / Health Report (every 5s)
  if (now - lastHealthTime >= 5000) {
    lastHealthTime = now;
    if (mqttClient.connected()) {
      char healthTopic[64];
      snprintf(healthTopic, sizeof(healthTopic), "edgeflow/v1/health/%s", NODE_ID);
      StaticJsonDocument<128> hDoc;
      hDoc["node_id"] = NODE_ID;
      hDoc["status"] = isLocalFallbackMode ? "FALLBACK_AUTONOMOUS" : "HEALTHY";
      hDoc["current_phase"] = (currentPhase == PHASE_NS) ? "NS" : "EW";
      hDoc["uptime_ms"] = now;

      char hBuffer[128];
      serializeJson(hDoc, hBuffer);
      mqttClient.publish(healthTopic, hBuffer);
    }
  }
}
