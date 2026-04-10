// wifi_manager.cpp -- WiFi station/AP management with NVS credential persistence

#include "wifi_manager.h"
#include "config.h"
#include <WiFi.h>
#include <ESPmDNS.h>
#include <Preferences.h>
#include <esp_task_wdt.h>
#include <algorithm>

// ============================================================
// MUTEX (Bug 4: protect credential string lifetime)
// ============================================================

void WiFiManager::_ensureMutex() {
    if (_credMutex == nullptr) {
        _credMutex = xSemaphoreCreateMutex();
    }
}

// ============================================================
// CREDENTIALS (NVS namespace "wifi")
// ============================================================

bool WiFiManager::loadCredentials() {
    _ensureMutex();

    Preferences prefs;
    prefs.begin("wifi", true);  // read-only

    String loadedSsid = prefs.getString("ssid", "");
    String loadedPw   = prefs.getString("password", "");
    prefs.end();

    loadedSsid.trim();
    loadedPw.trim();

    // Publish under lock so any concurrent reader sees a consistent snapshot.
    xSemaphoreTake(_credMutex, portMAX_DELAY);
    ssid     = loadedSsid;
    password = loadedPw;
    xSemaphoreGive(_credMutex);

    // Log from the local copy — reading ssid.c_str() here without the lock
    // would re-introduce the use-after-free class of bug we just fixed.
    if (loadedSsid.length() > 0) {
        Serial.printf("  Gespeicherte SSID: '%s'\n", loadedSsid.c_str());
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
    _ensureMutex();

    String trimmedSsid = newSsid;
    String trimmedPw = newPassword;
    trimmedSsid.trim();
    trimmedPw.trim();

    // NVS I/O happens outside the credential mutex — Preferences has its own
    // synchronization and NVS writes are slow enough that blocking
    // connectStation() on them would be wasteful.
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

    // Bug 4: publish in-RAM state under the mutex so another task calling
    // connectStation() cannot observe a freed String buffer.
    xSemaphoreTake(_credMutex, portMAX_DELAY);
    ssid = trimmedSsid;
    password = trimmedPw;
    xSemaphoreGive(_credMutex);

    Serial.printf("  Credentials gespeichert: '%s'\n", trimmedSsid.c_str());
    return true;
}

void WiFiManager::deleteCredentials() {
    _ensureMutex();

    Preferences prefs;
    prefs.begin("wifi", false);
    prefs.clear();
    prefs.end();

    xSemaphoreTake(_credMutex, portMAX_DELAY);
    ssid     = "";
    password = "";
    xSemaphoreGive(_credMutex);
}

// ============================================================
// STATION MODE
// ============================================================

String WiFiManager::connectStation(unsigned long timeoutMs) {
    _ensureMutex();

    // Bug 4: Copy the credentials to locals under the mutex BEFORE starting
    // the WiFi.begin retry loop. WiFi.begin() only latches the char* at the
    // start of the attempt, so if saveCredentials() reassigns `ssid` mid-
    // connect, the underlying buffer can be freed out from under WiFi.begin
    // → use-after-free. By using locals we give the WiFi stack a buffer we
    // own for the duration of the connect attempt.
    String localSsid;
    String localPw;
    xSemaphoreTake(_credMutex, portMAX_DELAY);
    localSsid = ssid;
    localPw   = password;
    xSemaphoreGive(_credMutex);

    if (localSsid.length() == 0) return "";

    // Bug 3: Preserve AP mode if it is already up. Previously this forced
    // WIFI_STA unconditionally, which tears down the softAP for ~49 seconds
    // while the station connect attempt runs — caregivers lose the
    // "MundMaus" hotspot mid-setup and panic-power-cycle the device.
    wifi_mode_t currentMode = WiFi.getMode();
    if (currentMode == WIFI_MODE_AP || currentMode == WIFI_MODE_APSTA) {
        WiFi.mode(WIFI_AP_STA);
    } else {
        WiFi.mode(WIFI_STA);
    }

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
        Serial.printf("  Verbinde mit '%s' (Versuch %d/3)...\n", localSsid.c_str(), attempt);
        WiFi.begin(localSsid.c_str(), localPw.c_str());

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
    _ensureMutex();
    auto [rssi, rssiLabel] = getRSSI();

    // Bug 4: snapshot ssid under the mutex. JsonDocument copies the value
    // immediately, so we can release the lock before assigning.
    String ssidSnapshot;
    xSemaphoreTake(_credMutex, portMAX_DELAY);
    ssidSnapshot = ssid;
    xSemaphoreGive(_credMutex);

    doc["mode"]       = mode.length() > 0 ? mode : "disconnected";
    doc["ssid"]       = ssidSnapshot;
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
