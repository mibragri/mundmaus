// updater.cpp -- OTA update: manifest check + game/firmware download

#include "updater.h"
#include "config.h"

#include <HTTPClient.h>
#include <WiFi.h>
#include <Preferences.h>
#include <LittleFS.h>
#include <ArduinoJson.h>
#include <esp_ota_ops.h>
#include <Update.h>

#include <map>

namespace Updater {

// ============================================================
// LOCAL VERSION TRACKING (NVS-backed)
// ============================================================

// filename -> version number, persisted in Preferences namespace "ota_ver"
static std::map<String, int> _versions;

static const char* OTA_MARKER = "/.ota_marker";

void loadVersions() {
    _versions.clear();

    // If marker is missing, LittleFS was overwritten by USB flash.
    // Clear NVS so fresh-flash seeding can re-detect installed versions.
    if (!LittleFS.exists(OTA_MARKER)) {
        Preferences prefs;
        prefs.begin("ota_ver", false);
        prefs.clear();
        prefs.end();
        Serial.println("  OTA: fresh flash detected, cleared version tracking");
        return;
    }

    Preferences prefs;
    prefs.begin("ota_ver", true);  // read-only

    // Preferences doesn't support iteration, so we store a JSON blob
    // under key "json" containing {"filename": version, ...}
    String json = prefs.getString("json", "{}");
    prefs.end();

    JsonDocument doc;
    DeserializationError err = deserializeJson(doc, json);
    if (err) return;

    for (JsonPair kv : doc.as<JsonObject>()) {
        _versions[String(kv.key().c_str())] = kv.value().as<int>();
    }
}

void saveVersions() {
    JsonDocument doc;
    for (const auto& kv : _versions) {
        doc[kv.first] = kv.second;
    }
    String json;
    serializeJson(doc, json);

    Preferences prefs;
    prefs.begin("ota_ver", false);  // read-write
    prefs.putString("json", json);
    prefs.end();

    // Write marker so next boot knows NVS versions are valid
    File f = LittleFS.open(OTA_MARKER, "w");
    if (f) { f.print("1"); f.close(); }
}

// ============================================================
// HTTPS HELPERS
// ============================================================

/// Get chip ID as hex string (last 3 bytes of MAC).
static String _chipId() {
    uint64_t mac = ESP.getEfuseMac();
    char buf[7];
    snprintf(buf, sizeof(buf), "%02X%02X%02X",
             (uint8_t)(mac >> 24), (uint8_t)(mac >> 32), (uint8_t)(mac >> 40));
    return String(buf);
}

/// Configure HTTPClient for OTA server with device identification.
static bool _beginHttps(HTTPClient& http, const String& url) {
    http.setConnectTimeout(8000);
    http.setTimeout(15000);
    http.setFollowRedirects(HTTPC_STRICT_FOLLOW_REDIRECTS);

    if (!http.begin(url)) {
        Serial.printf("  OTA: HTTP begin failed: %s\n", url.c_str());
        return false;
    }

    // Device identification via User-Agent
    http.setUserAgent("MundMaus/" MUNDMAUS_VERSION " (ESP32; " + _chipId() + ")");

    // Basic Auth (transition period — server accepts both auth and no-auth)
    if (strlen(Config::OTA_AUTH) > 0) {
        String auth = "Basic ";
        auth += Config::OTA_AUTH;
        http.addHeader("Authorization", auth);
    }

    return true;
}

// ============================================================
// MANIFEST CHECK
// ============================================================

CheckResult checkManifest() {
    CheckResult result;
    result.offline = true;

    // Build manifest URL
    String url = String(Config::OTA_BASE_URL) + "/manifest.json";

    HTTPClient http;
    if (!_beginHttps(http, url)) {
        return result;
    }

    int code = http.GET();
    if (code != 200) {
        Serial.printf("  OTA: manifest HTTP %d\n", code);
        http.end();
        return result;
    }

    // Parse manifest JSON
    String body = http.getString();
    http.end();

    JsonDocument manifest;
    DeserializationError err = deserializeJson(manifest, body);
    if (err) {
        Serial.printf("  OTA: manifest JSON error: %s\n", err.c_str());
        return result;
    }

    // Successfully fetched manifest
    result.offline = false;

    // Load current local versions
    loadVersions();

    // Compare remote files against local versions
    JsonObject files = manifest["files"].as<JsonObject>();
    for (JsonPair kv : files) {
        String fname = kv.key().c_str();
        int remoteVer = kv.value()["version"] | 0;
        bool isFirmware = kv.value()["firmware"] | false;
        int localVer = 0;

        auto it = _versions.find(fname);
        if (it != _versions.end()) {
            localVer = it->second;
        }

        // After fresh flash: file exists on LittleFS but NVS has no version.
        // Seed version from manifest instead of offering a redundant re-download.
        if (localVer == 0 && !isFirmware) {
            String path = "/" + fname;
            if (LittleFS.exists(path)) {
                _versions[fname] = remoteVer;
                localVer = remoteVer;
            }
        }

        if (remoteVer > localVer) {
            UpdateFile uf;
            uf.name      = fname;
            uf.localVer  = localVer;
            uf.remoteVer = remoteVer;
            uf.firmware  = isFirmware;
            uf.deleteFile = false;
            result.available.push_back(uf);
        }
    }

    // Check for deleted files (in local but not in manifest)
    // Only consider www/ files — ignore stale .py entries from old manifests
    std::vector<String> staleKeys;
    for (const auto& kv : _versions) {
        if (!files[kv.first].is<JsonObject>()) {
            if (kv.first.startsWith("www/")) {
                UpdateFile uf;
                uf.name       = kv.first;
                uf.localVer   = kv.second;
                uf.remoteVer  = 0;
                uf.firmware   = false;
                uf.deleteFile = true;
                result.available.push_back(uf);
            } else {
                staleKeys.push_back(kv.first);
            }
        }
    }
    // Clean stale non-www entries from NVS
    for (const auto& key : staleKeys) {
        _versions.erase(key);
    }

    // Persist any seeded versions from fresh-flash detection
    saveVersions();

    Serial.printf("  OTA: %d updates available\n", result.available.size());
    return result;
}

// ============================================================
// GAME FILE DOWNLOAD + INSTALL
// ============================================================

bool installGameUpdates(const std::vector<UpdateFile>& files,
                        std::function<void(const String&, int, int)> progressCb) {
    if (files.empty()) return true;

    // Filter to game files only (skip firmware)
    std::vector<const UpdateFile*> games;
    std::vector<const UpdateFile*> deletes;
    for (const auto& f : files) {
        if (f.firmware) continue;
        if (f.deleteFile) {
            deletes.push_back(&f);
        } else {
            games.push_back(&f);
        }
    }

    int total = games.size() + deletes.size();
    int current = 0;
    bool allOk = true;

    // Download game files
    for (const auto* uf : games) {
        current++;
        if (progressCb) {
            progressCb(uf->name, current, total);
        }

        String url = String(Config::OTA_BASE_URL) + "/" + uf->name;
        HTTPClient http;

        if (!_beginHttps(http, url)) {
            Serial.printf("  OTA: download begin failed: %s\n", uf->name.c_str());
            allOk = false;
            continue;
        }

        int code = http.GET();
        if (code != 200) {
            Serial.printf("  OTA: download %s HTTP %d\n", uf->name.c_str(), code);
            http.end();
            allOk = false;
            continue;
        }

        int contentLen = http.getSize();

        // Ensure parent directory exists on LittleFS
        String path = "/" + uf->name;
        int lastSlash = path.lastIndexOf('/');
        if (lastSlash > 0) {
            String dir = path.substring(0, lastSlash);
            if (!LittleFS.exists(dir)) {
                LittleFS.mkdir(dir);
            }
        }

        // Stream to temporary file
        String tmpPath = path + ".new";
        File outFile = LittleFS.open(tmpPath, "w");
        if (!outFile) {
            Serial.printf("  OTA: can't create %s\n", tmpPath.c_str());
            http.end();
            allOk = false;
            continue;
        }

        WiFiClient* tcpStream = http.getStreamPtr();
        if (!tcpStream) {
            Serial.printf("  OTA: no stream for %s\n", uf->name.c_str());
            outFile.close();
            LittleFS.remove(tmpPath);
            http.end();
            allOk = false;
            continue;
        }
        uint8_t buf[1024];
        int written = 0;
        unsigned long lastData = millis();
        while (http.connected() && (contentLen > 0 || contentLen < 0)) {
            int avail = tcpStream->available();
            if (avail <= 0) {
                if (millis() - lastData > 30000) {
                    Serial.printf("  OTA: download stalled: %s\n", uf->name.c_str());
                    break;
                }
                delay(1);
                continue;
            }
            lastData = millis();
            int toRead = (avail < (int)sizeof(buf)) ? avail : (int)sizeof(buf);
            int n = tcpStream->readBytes(buf, toRead);
            if (n <= 0) break;
            outFile.write(buf, n);
            written += n;
            if (contentLen > 0) {
                contentLen -= n;
                if (contentLen <= 0) break;
            }
        }
        outFile.close();
        http.end();

        // Verify non-empty
        if (written == 0) {
            Serial.printf("  OTA: %s empty download\n", uf->name.c_str());
            LittleFS.remove(tmpPath);
            allOk = false;
            continue;
        }

        // Atomic install: remove old, rename .new -> final
        LittleFS.remove(path);
        LittleFS.rename(tmpPath, path);

        // Update version tracking
        _versions[uf->name] = uf->remoteVer;
        Serial.printf("  OTA: installed %s v%d\n", uf->name.c_str(), uf->remoteVer);
    }

    // Delete removed files
    for (const auto* uf : deletes) {
        current++;
        if (progressCb) {
            progressCb(uf->name, current, total);
        }
        String path = "/" + uf->name;
        LittleFS.remove(path);
        _versions.erase(uf->name);
        Serial.printf("  OTA: deleted %s\n", uf->name.c_str());
    }

    // Persist version tracking
    saveVersions();

    return allOk;
}

// ============================================================
// FIRMWARE OTA (dual-partition)
// ============================================================

bool installFirmwareUpdate(const UpdateFile& fw,
                           std::function<void(int, int)> progressCb) {
    String url = String(Config::OTA_BASE_URL) + "/" + fw.name;
    Serial.printf("  OTA: downloading firmware %s\n", fw.name.c_str());

    HTTPClient http;
    if (!_beginHttps(http, url)) {
        Serial.println("  OTA: firmware HTTPS failed");
        return false;
    }

    int code = http.GET();
    if (code != 200) {
        Serial.printf("  OTA: firmware HTTP %d\n", code);
        http.end();
        return false;
    }

    int contentLen = http.getSize();
    if (contentLen <= 0) {
        Serial.println("  OTA: firmware size unknown");
        http.end();
        return false;
    }

    Serial.printf("  OTA: firmware size %d bytes\n", contentLen);

    if (!Update.begin(contentLen)) {
        Serial.printf("  OTA: Update.begin failed: %s\n", Update.errorString());
        http.end();
        return false;
    }

    WiFiClient* stream = http.getStreamPtr();
    uint8_t buf[4096];
    int written = 0;
    unsigned long lastData = millis();

    while (written < contentLen) {
        int avail = stream->available();
        if (avail <= 0) {
            if (millis() - lastData > 30000) {
                Serial.println("  OTA: firmware download stalled");
                Update.abort();
                http.end();
                return false;
            }
            delay(1);
            continue;
        }
        lastData = millis();
        int toRead = min(avail, (int)sizeof(buf));
        toRead = min(toRead, contentLen - written);
        int n = stream->readBytes(buf, toRead);
        if (n <= 0) break;

        if (Update.write(buf, n) != (size_t)n) {
            Serial.printf("  OTA: write error: %s\n", Update.errorString());
            Update.abort();
            http.end();
            return false;
        }

        written += n;
        if (progressCb) {
            progressCb(written, contentLen);
        }
    }

    http.end();

    if (!Update.end(true)) {
        Serial.printf("  OTA: end failed: %s\n", Update.errorString());
        return false;
    }

    // Update firmware version tracking
    _versions[fw.name] = fw.remoteVer;
    saveVersions();

    Serial.printf("  OTA: firmware installed (%d bytes)\n", written);
    return true;
}

// ============================================================
// REMOTE SETTINGS
// ============================================================

int fetchRemoteSettings() {
    String url = String(Config::OTA_BASE_URL) + "/settings.json";

    HTTPClient http;
    if (!_beginHttps(http, url)) return -1;

    int code = http.GET();
    if (code != 200) {
        // 404 = no remote settings file, not an error
        if (code != 404) {
            Serial.printf("  OTA: settings HTTP %d\n", code);
        }
        http.end();
        return -1;
    }

    String body = http.getString();
    http.end();

    JsonDocument doc;
    DeserializationError err = deserializeJson(doc, body);
    if (err) {
        Serial.printf("  OTA: settings JSON error: %s\n", err.c_str());
        return -1;
    }

    return Config::applyRemote(doc);
}

// ============================================================
// BOOT VALIDATION
// ============================================================

void markBootOk() {
    // Mark current OTA partition as valid, cancelling any pending rollback.
    // Safe to call even on factory partition (no-op).
    esp_ota_mark_app_valid_cancel_rollback();
}

}  // namespace Updater
