// wifi_manager.cpp -- WiFi station/AP management with NVS credential persistence

#include "wifi_manager.h"
#include "config.h"
#include "wifi_log.h"
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
    bool willKeepAp = (currentMode == WIFI_MODE_AP || currentMode == WIFI_MODE_APSTA);
    WifiLog::log(String("event=connect_start mode=") + (willKeepAp ? "ap_sta" : "station"));

    if (WiFi.isConnected()) {
        ip   = WiFi.localIP().toString();
        mode = "station";
        return ip;
    }

    // Clear any stale WiFi state before begin(). A cold boot can leave the
    // radio partially initialized from the bootloader; WiFi.begin() then
    // latches onto that state and the association silently fails.
    WiFi.disconnect(true, true);
    WiFi.mode(WIFI_OFF);
    delay(100);
    esp_task_wdt_reset();

    if (willKeepAp) {
        WiFi.mode(WIFI_AP_STA);
    } else {
        WiFi.mode(WIFI_STA);
    }

    WiFi.setHostname("mundmaus");
    WiFi.setAutoReconnect(true);
    WiFi.persistent(true);

    // Scan first so the strongest matching BSSID can be pinned on each
    // attempt. Plain WiFi.begin(ssid, pw) in a Fritz-Repeater mesh lets
    // ESP32 heuristics pick an AP — sometimes a weaker one that refuses
    // the association.
    struct BssMatch {
        uint8_t bssid[6];
        int32_t channel;
        int     rssi;
    };
    std::vector<BssMatch> matches;
    int scanCount = WiFi.scanNetworks();
    if (scanCount > 0) {
        for (int i = 0; i < scanCount; i++) {
            if (WiFi.SSID(i) == localSsid) {
                BssMatch m;
                memcpy(m.bssid, WiFi.BSSID(i), 6);
                m.channel = WiFi.channel(i);
                m.rssi    = WiFi.RSSI(i);
                matches.push_back(m);
            }
        }
        std::sort(matches.begin(), matches.end(),
                  [](const BssMatch& a, const BssMatch& b) { return a.rssi > b.rssi; });
        // Cap at 5 — that is one match per retry attempt below.
        if (matches.size() > 5) matches.resize(5);
    }
    WiFi.scanDelete();

    int totalNets = (scanCount > 0) ? scanCount : 0;
    WifiLog::log(String("event=scan_result count=") + totalNets +
                 " matches_ssid=" + (int)matches.size());
    for (size_t i = 0; i < matches.size(); i++) {
        const BssMatch& m = matches[i];
        char bssidBuf[20];
        snprintf(bssidBuf, sizeof(bssidBuf), "%02x:%02x:%02x:%02x:%02x:%02x",
                 m.bssid[0], m.bssid[1], m.bssid[2],
                 m.bssid[3], m.bssid[4], m.bssid[5]);
        WifiLog::log(String("event=scan_match rssi=") + m.rssi +
                     " ch=" + (int)m.channel +
                     " bssid=" + bssidBuf);
    }

    // Retry up to 5 times with exponential-ish backoff. Bumped from 3 to 5
    // because the patient's router occasionally rejects the first 2-3 attempts
    // after a cold boot; falling to AP mode at 3 was triggering the caregiver
    // panic-recovery flow we are trying to avoid.
    // Using disconnect(false) preserves internal WiFi storage — our NVS "wifi" namespace
    // keeps credentials persistent regardless, but we avoid wiping ESP32's internal cache.
    constexpr int MAX_ATTEMPTS = 5;
    unsigned long beginMs = 0;
    for (int attempt = 1; attempt <= MAX_ATTEMPTS; attempt++) {
        int idx = attempt - 1;
        bool pinned = (idx < static_cast<int>(matches.size()));
        char bssidBuf[20] = "-";
        int  attemptCh    = 0;
        if (pinned) {
            const BssMatch& m = matches[idx];
            snprintf(bssidBuf, sizeof(bssidBuf), "%02x:%02x:%02x:%02x:%02x:%02x",
                     m.bssid[0], m.bssid[1], m.bssid[2],
                     m.bssid[3], m.bssid[4], m.bssid[5]);
            attemptCh = static_cast<int>(m.channel);
            Serial.printf("  Verbinde mit '%s' (Versuch %d/%d: BSSID %s Ch %d RSSI %d)...\n",
                          localSsid.c_str(), attempt, MAX_ATTEMPTS,
                          bssidBuf, attemptCh, m.rssi);
            WifiLog::log(String("event=begin_attempt n=") + attempt +
                         " mode=pinned bssid=" + bssidBuf +
                         " ch=" + attemptCh);
            beginMs = millis();
            WiFi.begin(localSsid.c_str(), localPw.c_str(), m.channel, m.bssid);
        } else {
            Serial.printf("  Verbinde mit '%s' (Versuch %d/%d: kein BSSID, plain)...\n",
                          localSsid.c_str(), attempt, MAX_ATTEMPTS);
            WifiLog::log(String("event=begin_attempt n=") + attempt + " mode=plain");
            beginMs = millis();
            WiFi.begin(localSsid.c_str(), localPw.c_str());
        }

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

        // Decode the failure reason from WiFi.status() so the log distinguishes
        // password mistakes (auth_fail) from missing AP (no_ssid) from
        // generic timeouts. Helps narrow down patient-site issues quickly.
        const char* reason = "timeout";
        wl_status_t st = WiFi.status();
        if (st == WL_NO_SSID_AVAIL)        reason = "no_ssid";
        else if (st == WL_CONNECT_FAILED)  reason = "auth_fail";
        WifiLog::log(String("event=attempt_failed n=") + attempt + " reason=" + reason);

        if (attempt < MAX_ATTEMPTS) {
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
    WiFi.setSleep(WIFI_PS_NONE);
    Serial.printf("  Verbunden: %s\n", ip.c_str());

    // Trigger SNTP as soon as we have an IP. Non-blocking — subsequent
    // log lines may still print boot/ms until the first sync arrives.
    WifiLog::startNtp();
    WifiLog::log(String("event=connected ip=") + ip +
                 " rssi=" + (int)WiFi.RSSI() +
                 " ms=" + (unsigned long)(millis() - beginMs));

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
    // Credentials are already populated in RAM by main() (via loadCredentials
    // on boot, or saveCredentials during serial provisioning). Re-reading NVS
    // here would mask a just-saved set if saveCredentials had a partial NVS
    // write failure, producing a misleading "no_credentials" ap_fallback log.
    String currentSsid;
    xSemaphoreTake(_credMutex, portMAX_DELAY);
    currentSsid = ssid;
    xSemaphoreGive(_credMutex);
    bool hasCreds = (currentSsid.length() > 0);

    if (hasCreds) {
        String stationIP = connectStation();
        if (stationIP.length() > 0) {
            return {stationIP, "station"};
        }
        Serial.println("  WLAN fehlgeschlagen -> Hotspot");
        WifiLog::log("event=ap_fallback attempts_failed=5");
    } else {
        Serial.println("  Keine Daten -> Hotspot");
        WifiLog::log("event=ap_fallback attempts_failed=0 reason=no_credentials");
    }

    String apIP = startAP();
    return {apIP, "ap"};
}
