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
#include <freertos/FreeRTOS.h>
#include <freertos/semphr.h>

#include <map>

namespace Updater {

// ============================================================
// LOCAL VERSION TRACKING (NVS-backed)
// ============================================================

// filename -> version number, persisted in Preferences namespace "ota_ver"
static std::map<String, int> _versions;

// Bug 2: replace LittleFS .ota_marker file with an NVS schema key so a
// transient LittleFS full condition (or any LittleFS corruption) cannot
// silently wipe all version tracking on the next boot.
static constexpr int SCHEMA_VERSION = 1;

// Bug 5: Serialize all access to the "ota_ver" NVS namespace and _versions.
// checkManifest() can be invoked from multiple contexts (boot task, periodic
// check task, post-install refresh, HTTP handler callback) and all paths
// mutate the same backing store. Without a mutex concurrent writers can
// observe half-written state and corrupt the JSON blob.
static SemaphoreHandle_t _versionsMutex = nullptr;

static void _ensureMutex() {
    if (_versionsMutex == nullptr) {
        _versionsMutex = xSemaphoreCreateMutex();
    }
}

// Internal: load versions into _versions. Caller must hold _versionsMutex.
static void _loadVersionsLocked() {
    _versions.clear();

    Preferences prefs;
    prefs.begin("ota_ver", true);  // read-only
    int schema = prefs.getInt("schema_version", 0);
    prefs.end();

    if (schema != SCHEMA_VERSION) {
        // Fresh flash or schema upgrade — wipe NVS and set schema version.
        // This is the ONLY place that can clear NVS, and it only fires when
        // the schema key is missing (brand new NVS partition) or differs
        // (future migration). A transiently-full LittleFS can no longer
        // trigger this path.
        Serial.println("  OTA: fresh flash detected, cleared version tracking");
        prefs.begin("ota_ver", false);
        prefs.clear();
        prefs.putInt("schema_version", SCHEMA_VERSION);
        prefs.end();
        return;
    }

    // Normal path: load versions blob
    prefs.begin("ota_ver", true);
    String json = prefs.getString("json", "");
    prefs.end();

    if (json.length() == 0) return;

    JsonDocument doc;
    DeserializationError err = deserializeJson(doc, json);
    if (err) return;

    for (JsonPairConst kv : doc.as<JsonObjectConst>()) {
        _versions[String(kv.key().c_str())] = kv.value().as<int>();
    }
}

// Internal: save _versions to NVS. Caller must hold _versionsMutex.
static void _saveVersionsLocked() {
    JsonDocument doc;
    for (const auto& kv : _versions) {
        doc[kv.first.c_str()] = kv.second;
    }
    String json;
    serializeJson(doc, json);

    Preferences prefs;
    prefs.begin("ota_ver", false);  // read-write
    prefs.putString("json", json);
    // Keep schema version up to date — a rolled-back firmware that
    // downgraded NVS would otherwise look like a fresh flash next boot.
    prefs.putInt("schema_version", SCHEMA_VERSION);
    prefs.end();
}

void loadVersions() {
    _ensureMutex();
    if (xSemaphoreTake(_versionsMutex, portMAX_DELAY) != pdTRUE) return;
    _loadVersionsLocked();
    xSemaphoreGive(_versionsMutex);
}

void saveVersions() {
    _ensureMutex();
    if (xSemaphoreTake(_versionsMutex, portMAX_DELAY) != pdTRUE) return;
    _saveVersionsLocked();
    xSemaphoreGive(_versionsMutex);
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

    // Bug 5: Hold the versions mutex for the ENTIRE load/compare/save cycle.
    // Otherwise two concurrent manifest checks can both read the same stale
    // state, seed overlapping entries, and race on saveVersions() — the
    // JSON blob write is not atomic and the loser corrupts the namespace.
    _ensureMutex();
    if (xSemaphoreTake(_versionsMutex, portMAX_DELAY) != pdTRUE) {
        return result;
    }

    // Load current local versions (under the same lock)
    _loadVersionsLocked();

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

        // After fresh flash: firmware.bin has no NVS entry. The running
        // firmware knows its own version (MUNDMAUS_FW_VERSION build flag),
        // so use that instead of offering a spurious "update to self".
        if (localVer == 0 && isFirmware) {
            localVer = MUNDMAUS_FW_VERSION;
            _versions[fname] = localVer;
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
    _saveVersionsLocked();

    xSemaphoreGive(_versionsMutex);

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
        // P1-1: Track the original Content-Length so we can verify the full
        // payload was received. The download loop decrements contentLen as
        // bytes arrive, so we need a separate copy to compare against.
        const int expectedLen = contentLen;  // <0 means chunked/unknown
        uint8_t buf[1024];
        int written = 0;
        bool writeFailed = false;
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
            // P1-1: Check write return value — LittleFS can fail when full.
            // A short write means the file is corrupt; we must abort so we
            // don't atomic-rename a truncated file over the good one.
            if (outFile.write(buf, n) != (size_t)n) {
                Serial.printf("  OTA: %s write failed (LittleFS full?)\n", uf->name.c_str());
                writeFailed = true;
                break;
            }
            written += n;
            if (contentLen > 0) {
                contentLen -= n;
                if (contentLen <= 0) break;
            }
        }
        outFile.close();
        http.end();

        // P1-1: Verify completeness before atomic rename.
        // A truncated file silently installed is catastrophic for the patient
        // (broken game, blank page, no recovery). Fail loud, keep the old file.
        bool downloadOk = true;
        if (writeFailed) {
            downloadOk = false;
        } else if (written == 0) {
            Serial.printf("  OTA: %s empty download\n", uf->name.c_str());
            downloadOk = false;
        } else if (expectedLen > 0 && written != expectedLen) {
            // Known Content-Length: must match exactly
            Serial.printf("  OTA: %s truncated: got %d/%d bytes\n",
                          uf->name.c_str(), written, expectedLen);
            downloadOk = false;
        }
        // expectedLen < 0 (chunked/unknown): accept any non-zero length

        if (!downloadOk) {
            LittleFS.remove(tmpPath);
            allOk = false;
            continue;
        }

        // Atomic install with rollback: back up old -> install new -> restore on failure.
        // Previous version did `remove(path); rename(tmpPath, path);` which could lose
        // BOTH files if the rename failed, orphaning the game permanently.
        String oldBackup = path + ".old";
        bool hadOld = LittleFS.exists(path);
        if (hadOld) {
            // Clean any stale .old from a previous interrupted install before reusing the slot
            LittleFS.remove(oldBackup);
            if (!LittleFS.rename(path, oldBackup)) {
                Serial.printf("  OTA: cannot backup %s, aborting install\n", path.c_str());
                LittleFS.remove(tmpPath);
                allOk = false;
                continue;
            }
        }
        if (!LittleFS.rename(tmpPath, path)) {
            Serial.printf("  OTA: rename FAILED for %s, rolling back\n", path.c_str());
            LittleFS.remove(tmpPath);
            if (hadOld) {
                LittleFS.rename(oldBackup, path);  // restore old on best-effort basis
            }
            allOk = false;
            continue;  // do NOT update _versions
        }
        if (hadOld) {
            LittleFS.remove(oldBackup);  // cleanup backup on success
        }

        // Update version tracking (Bug 5: lock around _versions mutation)
        _ensureMutex();
        if (xSemaphoreTake(_versionsMutex, portMAX_DELAY) == pdTRUE) {
            _versions[uf->name] = uf->remoteVer;
            xSemaphoreGive(_versionsMutex);
        }
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
        // Bug 5: lock around _versions mutation
        _ensureMutex();
        if (xSemaphoreTake(_versionsMutex, portMAX_DELAY) == pdTRUE) {
            _versions.erase(uf->name);
            xSemaphoreGive(_versionsMutex);
        }
        Serial.printf("  OTA: deleted %s\n", uf->name.c_str());
    }

    // Persist version tracking (saveVersions() takes the mutex internally)
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

    // P2-3: Explicit truncation check. The loop above can exit via `break`
    // on read error (n <= 0) with written < contentLen. Without this check,
    // Update.end() may succeed on a partial image and brick the device.
    if (written != contentLen) {
        Serial.printf("  OTA: firmware size mismatch: %d/%d\n", written, contentLen);
        Update.abort();
        return false;
    }

    // Bug 1: Write pending_fw BEFORE calling Update.end(true).
    // Update.end(true) commits the partition flag flip — from that point on
    // the next boot will run the new firmware. If power is lost between
    // end(true) and the putInt() that used to follow it, the new firmware
    // boots successfully, but markBootOk() finds no pending_fw entry and
    // cannot promote the version — the manifest check then re-offers the
    // same update forever, causing an infinite update loop.
    //
    // By writing pending_fw first we guarantee the NVS entry is durable
    // before the partition flip. If Update.end(true) then fails, we remove
    // the entry again so we don't claim a pending update that never shipped.
    //
    // Context: Firmware version is NOT committed to _versions here — the
    // bootloader might still roll back. markBootOk() promotes pending_fw
    // only after the new image successfully completes its first boot.
    {
        Preferences prefs;
        prefs.begin("ota_ver", false);
        prefs.putInt("pending_fw", fw.remoteVer);
        prefs.end();
    }

    if (!Update.end(true)) {
        Serial.printf("  OTA: end failed: %s\n", Update.errorString());
        // Commit failed — remove the pending marker we just wrote, otherwise
        // next boot would try to promote a version that never installed.
        Preferences prefs;
        prefs.begin("ota_ver", false);
        prefs.remove("pending_fw");
        prefs.end();
        return false;
    }

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
    // P1-5: Capture the OTA image state BEFORE marking the partition valid.
    // esp_ota_mark_app_valid_cancel_rollback() transitions the state from
    // PENDING_VERIFY to VALID, so we must snapshot it first to know whether
    // this boot is a "first boot of a freshly flashed image" (which means
    // the pending_fw version should be promoted to installed) or just a
    // regular reboot (which must NOT promote pending_fw — otherwise a
    // rollback-then-reboot cycle would falsely claim the new version is
    // running when the old firmware is actually active).
    bool isFirstBootAfterOta = false;
    const esp_partition_t* running = esp_ota_get_running_partition();
    if (running != nullptr) {
        esp_ota_img_states_t state;
        if (esp_ota_get_state_partition(running, &state) == ESP_OK) {
            isFirstBootAfterOta = (state == ESP_OTA_IMG_PENDING_VERIFY ||
                                   state == ESP_OTA_IMG_NEW);
        }
    }

    // Promote pending firmware version only after a confirmed first boot of
    // a new image. If bootloader rolled back, the OLD firmware is running
    // and its partition is already VALID, so isFirstBootAfterOta == false
    // and pending_fw stays untouched — the next manifest check correctly
    // re-offers the update.
    if (!isFirstBootAfterOta) {
        // Regular boot — mark partition valid (no-op on factory) and exit.
        esp_ota_mark_app_valid_cancel_rollback();
        return;
    }

    // First boot after OTA: promote pending_fw in _versions.
    // Bug 4: DO NOT unconditionally call loadVersions() here. The previous
    // version re-entered the fresh-flash-detection path, which with an
    // LittleFS-based marker could wipe all NVS version tracking. Even with
    // the schema_version fix (Bug 2), re-loading is unnecessary work and
    // stomps on any entries the boot sequence already populated. Instead,
    // load ONLY if _versions has not been loaded yet this boot.
    _ensureMutex();
    if (xSemaphoreTake(_versionsMutex, portMAX_DELAY) != pdTRUE) {
        // Shouldn't happen — fall back to cancelling rollback and return.
        esp_ota_mark_app_valid_cancel_rollback();
        return;
    }

    int pending = 0;
    {
        Preferences prefs;
        prefs.begin("ota_ver", true);  // read-only
        pending = prefs.getInt("pending_fw", 0);
        prefs.end();
    }

    if (pending > 0) {
        if (_versions.empty()) {
            // Only load when we haven't already — avoids re-entering the
            // fresh-flash path and avoids clobbering an in-memory state
            // that may already reflect the current manifest check.
            _loadVersionsLocked();
        }
        _versions["firmware.bin"] = pending;
        _saveVersionsLocked();

        // Clear the pending marker so we don't re-promote on the next boot.
        Preferences prefs;
        prefs.begin("ota_ver", false);
        prefs.remove("pending_fw");
        prefs.end();
        Serial.printf("  OTA: firmware v%d promoted to installed\n", pending);
    }

    xSemaphoreGive(_versionsMutex);

    // Cancel rollback timer — firmware is now validated.
    esp_ota_mark_app_valid_cancel_rollback();
    Serial.println("  OTA: boot validated, rollback cancelled");
}

}  // namespace Updater
