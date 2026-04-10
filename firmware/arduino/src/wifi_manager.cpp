// wifi_manager.cpp -- WiFi station/AP management with NVS credential persistence

#include "wifi_manager.h"
#include "config.h"
#include <WiFi.h>
#include <ESPmDNS.h>
#include <Preferences.h>
#include <esp_task_wdt.h>
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

bool WiFiManager::saveCredentials(const String& newSsid, const String& newPassword) {
    // BLOCKER 2: Verify every step of the NVS write. If the write fails (e.g.
    // flash wear, corrupted namespace), the in-RAM state must NOT be updated —
    // otherwise we'd try to connect with credentials that would be lost on the
    // next reboot, leaving the device unreachable after the scheduled restart.
    String trimmedSsid = newSsid;
    String trimmedPw = newPassword;
    trimmedSsid.trim();
    trimmedPw.trim();

    Preferences prefs;
    if (!prefs.begin("wifi", false)) {
        Serial.println("  ERROR: Failed to open NVS wifi namespace");
        return false;
    }
    size_t ssidWritten = prefs.putString("ssid", trimmedSsid);
    size_t pwWritten = prefs.putString("password", trimmedPw);
    prefs.end();

    if (ssidWritten != trimmedSsid.length() || pwWritten != trimmedPw.length()) {
        Serial.printf("  ERROR: NVS write incomplete (ssid: %u/%u, pw: %u/%u)\n",
                      (unsigned)ssidWritten, (unsigned)trimmedSsid.length(),
                      (unsigned)pwWritten, (unsigned)trimmedPw.length());
        return false;
    }

    // Only update in-RAM state AFTER successful NVS write.
    ssid = trimmedSsid;
    password = trimmedPw;
    Serial.printf("  Credentials gespeichert: '%s'\n", ssid.c_str());
    return true;
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

    // Retry up to 3 times with exponential-ish backoff.
    // After firmware updates, router may need a moment to accept the new connection.
    // Using disconnect(false) preserves internal WiFi storage — our NVS "wifi" namespace
    // keeps credentials persistent regardless, but we avoid wiping ESP32's internal cache.
    for (int attempt = 1; attempt <= 3; attempt++) {
        Serial.printf("  Verbinde mit '%s' (Versuch %d/3)...\n", ssid.c_str(), attempt);
        WiFi.begin(ssid.c_str(), password.c_str());

        unsigned long start = millis();
        while (!WiFi.isConnected()) {
            if (millis() - start > timeoutMs) {
                Serial.printf("  Timeout (%lums)\n", timeoutMs);
                WiFi.disconnect(false);
                break;
            }
            delay(250);
            esp_task_wdt_reset();  // keep WDT happy during long connect attempts
        }

        if (WiFi.isConnected()) break;

        if (attempt < 3) {
            Serial.printf("  Warte %ds vor naechstem Versuch...\n", attempt * 2);
            for (int w = 0; w < attempt * 8; w++) {
                delay(250);
                esp_task_wdt_reset();
            }
        }
    }

    if (!WiFi.isConnected()) {
        return "";
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
    // BLOCKER 3: Keep STA enabled permanently (WIFI_AP_STA) so network scans
    // work without toggling the radio on/off. Toggling caused dropped WS
    // connections and brief outages every time the settings page scanned.
    WiFi.mode(WIFI_AP_STA);

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
    // BLOCKER 3: STA interface is always enabled (WIFI_AP_STA from startAP,
    // or WIFI_STA from connectStation), so no toggling is required. The old
    // enableSTA(true)/enableSTA(false) toggle around the scan was the root
    // cause of brief radio outages during scans while in AP mode.
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

    return result;
}

// ============================================================
// RSSI
// ============================================================

std::pair<int, String> WiFiManager::getRSSI() {
    if (mode != "station" || !WiFi.isConnected()) {
        return {0, ""};
    }

    int rssi = static_cast<int>(WiFi.RSSI());  // NOLINT(bugprone-signed-char-misuse) RSSI is signed
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
