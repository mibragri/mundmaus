// wifi_manager.cpp -- WiFi station/AP management with NVS credential persistence

#include "wifi_manager.h"
#include "config.h"
#include <WiFi.h>
#include <ESPmDNS.h>
#include <Preferences.h>
#include <algorithm>

// ============================================================
// CREDENTIALS (NVS namespace "wifi")
// ============================================================

bool WiFiManager::loadCredentials() {
    Preferences prefs;
    prefs.begin("wifi", true);  // read-only

    ssid     = prefs.getString("ssid", "");
    password = prefs.getString("password", "");
    prefs.end();

    ssid.trim();
    password.trim();

    if (ssid.length() > 0) {
        Serial.printf("  Gespeicherte SSID: '%s'\n", ssid.c_str());
        return true;
    }
    Serial.println("  Keine WLAN-Daten gespeichert");
    return false;
}

void WiFiManager::saveCredentials(const String& newSsid, const String& newPassword) {
    ssid     = newSsid;
    password = newPassword;
    ssid.trim();
    password.trim();

    Preferences prefs;
    prefs.begin("wifi", false);  // read-write
    prefs.putString("ssid", ssid);
    prefs.putString("password", password);
    prefs.end();

    Serial.printf("  Credentials gespeichert: '%s'\n", ssid.c_str());
}

void WiFiManager::deleteCredentials() {
    Preferences prefs;
    prefs.begin("wifi", false);
    prefs.clear();
    prefs.end();

    ssid     = "";
    password = "";
}

// ============================================================
// STATION MODE
// ============================================================

String WiFiManager::connectStation(unsigned long timeoutMs) {
    if (ssid.length() == 0) return "";

    WiFi.mode(WIFI_STA);

    if (WiFi.isConnected()) {
        ip   = WiFi.localIP().toString();
        mode = "station";
        return ip;
    }

    Serial.printf("  Verbinde mit '%s'...\n", ssid.c_str());
    WiFi.begin(ssid.c_str(), password.c_str());

    unsigned long start = millis();
    while (!WiFi.isConnected()) {
        if (millis() - start > timeoutMs) {
            Serial.printf("  Timeout (%lums)\n", timeoutMs);
            WiFi.disconnect(true);
            return "";
        }
        delay(250);
    }

    ip   = WiFi.localIP().toString();
    mode = "station";
    Serial.printf("  Verbunden: %s\n", ip.c_str());

    // mDNS: mundmaus.local
    if (MDNS.begin("mundmaus")) {
        MDNS.addService("http", "tcp", Config::HTTP_PORT);
        Serial.println("  mDNS: mundmaus.local");
    }

    return ip;
}

// ============================================================
// AP MODE
// ============================================================

String WiFiManager::startAP() {
    WiFi.disconnect(true);
    WiFi.mode(WIFI_AP);

    WiFi.softAP(Config::AP_SSID, Config::AP_PASS);

    // Wait for AP to become active
    unsigned long start = millis();
    while (WiFi.softAPIP().toString() == "0.0.0.0") {
        if (millis() - start > 3000) break;
        delay(100);
    }

    ip   = WiFi.softAPIP().toString();
    mode = "ap";

    // mDNS: mundmaus.local (also in AP mode)
    if (MDNS.begin("mundmaus")) {
        MDNS.addService("http", "tcp", Config::HTTP_PORT);
        Serial.println("  mDNS: mundmaus.local");
    }
    return ip;
}

// ============================================================
// NETWORK SCAN
// ============================================================

std::vector<String> WiFiManager::scanNetworks() {
    // Ensure STA interface is active for scanning
    bool wasAP = (mode == "ap");
    if (wasAP) {
        WiFi.enableSTA(true);
        delay(100);
    }

    int n = WiFi.scanNetworks();

    // Build (rssi, ssid) pairs for sorting
    struct Entry {
        int    rssi;
        String ssid;
    };
    std::vector<Entry> entries;

    for (int i = 0; i < n; i++) {
        String name = WiFi.SSID(i);
        name.trim();
        if (name.length() == 0) continue;
        entries.push_back({WiFi.RSSI(i), name});
    }

    // Sort by RSSI descending (strongest first)
    std::sort(entries.begin(), entries.end(),
              [](const Entry& a, const Entry& b) { return a.rssi > b.rssi; });

    // Deduplicate
    std::vector<String> result;
    for (const auto& e : entries) {
        bool seen = false;
        for (const auto& r : result) {
            if (r == e.ssid) { seen = true; break; }
        }
        if (!seen) {
            result.push_back(e.ssid);
            if (result.size() >= 15) break;
        }
    }

    WiFi.scanDelete();

    if (wasAP) {
        WiFi.enableSTA(false);
    }

    return result;
}

// ============================================================
// RSSI
// ============================================================

std::pair<int, String> WiFiManager::getRSSI() {
    if (mode != "station" || !WiFi.isConnected()) {
        return {0, ""};
    }

    int rssi = WiFi.RSSI();
    String label;
    if      (rssi >= -50) label = "Perfekt";
    else if (rssi >= -60) label = "Gut";
    else if (rssi >= -70) label = "Schwach";
    else                  label = "Sehr schwach";

    return {rssi, label};
}

// ============================================================
// STATUS
// ============================================================

void WiFiManager::getStatus(JsonDocument& doc) {
    auto [rssi, rssiLabel] = getRSSI();

    doc["mode"]       = mode.length() > 0 ? mode : "disconnected";
    doc["ssid"]       = ssid;
    doc["ip"]         = ip;
    doc["ap_ssid"]    = Config::AP_SSID;
    doc["connected"]  = (mode == "station" && WiFi.isConnected());
    doc["rssi"]       = rssi;
    doc["rssi_label"] = rssiLabel;
}

// ============================================================
// STARTUP SEQUENCE
// ============================================================

std::pair<String, String> WiFiManager::startup() {
    bool hasCreds = loadCredentials();

    if (hasCreds) {
        String stationIP = connectStation();
        if (stationIP.length() > 0) {
            return {stationIP, "station"};
        }
        Serial.println("  WLAN fehlgeschlagen -> Hotspot");
    } else {
        Serial.println("  Keine Daten -> Hotspot");
    }

    String apIP = startAP();
    return {apIP, "ap"};
}
