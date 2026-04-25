// wifi_log.cpp -- Persistent WiFi diagnostic event log on LittleFS
//
// See wifi_log.h for rationale. Briefly: cold-boot WiFi failures at the
// patient site cannot be diagnosed via serial (no laptop attached) and
// in-RAM logs vanish on the first power cycle the caregiver tries.

#include "wifi_log.h"
#include <LittleFS.h>
#include <Preferences.h>
#include <freertos/FreeRTOS.h>
#include <freertos/semphr.h>
#include <time.h>

namespace WifiLog {

namespace {

constexpr const char* LOG_DIR     = "/logs";
constexpr const char* LOG_PATH    = "/logs/wifi.log";
constexpr const char* LOG_OLD     = "/logs/wifi.log.old";
constexpr size_t      MAX_BYTES   = 8 * 1024;     // per-file cap before rotation
constexpr time_t      MIN_VALID_T = 1700000000;   // 2023-11-14: any sync past this is real

// AsyncTCP (Core 0) reads via the HTTP endpoint; connectStation() and the
// reconnect task on Core 1 write. A single mutex serializes both. Created
// exactly once in init() — do not lazy-create from log()/read()/clear(), a
// concurrent first-call race there would leak one handle.
SemaphoreHandle_t _mutex = nullptr;

uint32_t      _bootCount   = 0;
bool          _ntpStarted  = false;
unsigned long _ntpStartMs  = 0;

}  // anonymous namespace

void init() {
    if (_mutex == nullptr) {
        _mutex = xSemaphoreCreateMutex();
    }

    // LittleFS may or may not have been mounted yet; begin(false) mounts an
    // existing FS but does NOT reformat on a transient mount failure. A
    // brownout during WiFi TX can produce such a transient failure, and
    // format=true would silently wipe the diagnostic log we are trying to
    // capture on exactly that boot. web_server.cpp's start() still mounts
    // with format=true for game assets (those are reinstallable via OTA).
    LittleFS.begin(false);

    Preferences prefs;
    if (prefs.begin("mundmaus", false)) {
        _bootCount = prefs.getUInt("boot_count", 0) + 1;
        prefs.putUInt("boot_count", _bootCount);
        prefs.end();
    }

    // Brownout counter is incremented HERE, very early in setup() — before any
    // WiFi activity runs. The previous location (deep inside connectStation
    // → _adaptiveTxPower) was missed during fast brownout-loops because the
    // device re-browned out before reaching that code path. Empirically the
    // counter under-reported by ~5x. Doing it here means: if a single boot
    // log line "event=boot reset_reason=9" gets written (which it does), the
    // counter is also persisted in the same NVS commit window.
    if (esp_reset_reason() == ESP_RST_BROWNOUT) {
        Preferences bp;
        if (bp.begin("wifi", false)) {
            uint32_t total = bp.getUInt("bo_total", 0) + 1;
            bp.putUInt("bo_total", total);
            bp.end();
        }
    }

    if (!LittleFS.exists(LOG_DIR)) {
        LittleFS.mkdir(LOG_DIR);
    }
}

void startNtp() {
    if (_ntpStarted) return;
    // UTC (offset 0, dst 0). pool.ntp.org as primary so any network with
    // working outbound DNS/53 gets time. 192.168.178.1 as fallback for the
    // stock-FritzBox home network at the patient site. Primary/fallback
    // order was reversed — the previous arrangement cost 1-2 s per retry on
    // any non-FritzBox deployment.
    configTime(0, 0, "pool.ntp.org", "192.168.178.1");
    _ntpStarted = true;
    _ntpStartMs = millis();
}

bool ntpSynced() {
    return time(nullptr) >= MIN_VALID_T;
}

uint32_t bootCount() {
    return _bootCount;
}

String timestamp() {
    char buf[48];
    time_t now = time(nullptr);
    if (now >= MIN_VALID_T) {
        struct tm utc;
        gmtime_r(&now, &utc);
        snprintf(buf, sizeof(buf),
                 "%04d-%02d-%02dT%02d:%02d:%02dZ boot=%u",
                 utc.tm_year + 1900, utc.tm_mon + 1, utc.tm_mday,
                 utc.tm_hour, utc.tm_min, utc.tm_sec,
                 (unsigned)_bootCount);
    } else {
        snprintf(buf, sizeof(buf), "boot=%u ms=%lu",
                 (unsigned)_bootCount, (unsigned long)millis());
    }
    return String(buf);
}

void log(const String& event) {
    if (_mutex == nullptr) return;
    if (xSemaphoreTake(_mutex, pdMS_TO_TICKS(500)) != pdTRUE) {
        return;
    }

    String line = timestamp();
    line += ' ';
    line += event;
    line += '\n';

    File f = LittleFS.open(LOG_PATH, "a");
    if (f) {
        f.print(line);
        size_t after = f.size();
        f.close();

        if (after >= MAX_BYTES) {
            // Rotate: delete prior .old, then promote current .log to .old.
            // A subsequent write reopens .log with mode "a" which creates a
            // fresh file. Done outside the file handle so we never rename a
            // file we still hold open.
            if (LittleFS.exists(LOG_OLD)) {
                LittleFS.remove(LOG_OLD);
            }
            LittleFS.rename(LOG_PATH, LOG_OLD);
        }
    }

    xSemaphoreGive(_mutex);
}

static void _appendFile(const char* path, String& out) {
    File f = LittleFS.open(path, "r");
    if (!f) return;
    // Reserve once so we don't reallocate per chunk; the rotation cap means
    // each file is at most ~8 KB which fits well within heap.
    out.reserve(out.length() + f.size());
    char chunk[256];
    while (f.available()) {
        int n = f.readBytes(chunk, sizeof(chunk));
        if (n <= 0) break;
        out.concat(chunk, n);
    }
    f.close();
}

String read() {
    String out;
    if (_mutex == nullptr) return out;
    if (xSemaphoreTake(_mutex, pdMS_TO_TICKS(500)) != pdTRUE) {
        return out;
    }

    if (LittleFS.exists(LOG_OLD))  _appendFile(LOG_OLD,  out);
    if (LittleFS.exists(LOG_PATH)) _appendFile(LOG_PATH, out);

    xSemaphoreGive(_mutex);
    return out;
}

static void _streamFile(const char* path, Print& out) {
    File f = LittleFS.open(path, "r");
    if (!f) return;
    uint8_t chunk[256];
    while (f.available()) {
        int n = f.readBytes(reinterpret_cast<char*>(chunk), sizeof(chunk));
        if (n <= 0) break;
        out.write(chunk, n);
    }
    f.close();
}

void stream(Print& out) {
    if (_mutex == nullptr) return;
    if (xSemaphoreTake(_mutex, pdMS_TO_TICKS(500)) != pdTRUE) {
        return;
    }
    if (LittleFS.exists(LOG_OLD))  _streamFile(LOG_OLD,  out);
    if (LittleFS.exists(LOG_PATH)) _streamFile(LOG_PATH, out);
    xSemaphoreGive(_mutex);
}

void clear() {
    if (_mutex == nullptr) return;
    if (xSemaphoreTake(_mutex, pdMS_TO_TICKS(500)) != pdTRUE) {
        return;
    }
    if (LittleFS.exists(LOG_PATH)) LittleFS.remove(LOG_PATH);
    if (LittleFS.exists(LOG_OLD))  LittleFS.remove(LOG_OLD);
    xSemaphoreGive(_mutex);
}

}  // namespace WifiLog
