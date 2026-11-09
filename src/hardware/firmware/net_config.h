// EdgeFlow AI - Wi-Fi networks and MQTT brokers the actuator may use (from secrets.ini build flags).
//
// Up to 3 networks, each with its own broker IP (the broker is the laptop on that network):
//   WIFI_SSID   / WIFI_PASS   / MQTT_BROKER     required (set_network.sh writes them)
//   WIFI_SSID_2 / WIFI_PASS_2 / MQTT_BROKER_2   optional fallback network
//   WIFI_SSID_3 / WIFI_PASS_3 / MQTT_BROKER_3   optional
// There are deliberately no defaults: credentials must never live in the source (git history).
#pragma once

#if !defined(WIFI_SSID) || !defined(WIFI_PASS) || !defined(MQTT_BROKER)
#error "Wi-Fi/broker not configured: run  bash src/hardware/set_network.sh \"<SSID>\" \"<password>\"  (writes the git-ignored secrets.ini)"
#endif

struct NetworkSlot
{
  const char *ssid;
  const char *pass;
  const char *broker;
};

static const NetworkSlot NETWORKS[] = {
    {WIFI_SSID, WIFI_PASS, MQTT_BROKER},
#if defined(WIFI_SSID_2) && defined(WIFI_PASS_2) && defined(MQTT_BROKER_2)
    {WIFI_SSID_2, WIFI_PASS_2, MQTT_BROKER_2},
#endif
#if defined(WIFI_SSID_3) && defined(WIFI_PASS_3) && defined(MQTT_BROKER_3)
    {WIFI_SSID_3, WIFI_PASS_3, MQTT_BROKER_3},
#endif
};
static const size_t NETWORK_COUNT = sizeof(NETWORKS) / sizeof(NETWORKS[0]);

// SNTP: the broker machine first (the Pi runs chrony), then public servers for a phone hotspot with
// Internet access (macOS does not serve NTP by default, so "NTP = laptop broker" alone may never sync).
#ifndef NTP_FALLBACK_1
#define NTP_FALLBACK_1 "pool.ntp.org"
#endif
#ifndef NTP_FALLBACK_2
#define NTP_FALLBACK_2 "time.google.com"
#endif
