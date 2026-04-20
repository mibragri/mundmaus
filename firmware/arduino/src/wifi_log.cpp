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
// reconnect task on Core 1 write. A single mutex serializes both.
SemaphoreHandle_t _mutex = nullptr;

uint32_t      _bootCount   = 0;
bool          _ntpStarted  = false;
unsigned long _ntpStartMs  = 0;

void _ensureMutex() {
    if (_mutex == nullptr) {
        _mutex = xSemaphoreCreateMutex();
    }
}

}  // anonymous namespace

void init() {
    _ensureMutex();

    // LittleFS may or may not have been mounted yet; begin() with format=true
    // is idempotent — returns immediately if the FS is already up. Without
    // this our first log() during connectStation() (well before
    // MundMausServer::start()) would silently no-op.
    LittleFS.begin(true);

    Preferences prefs;
    if (prefs.begin("mundmaus", false)) {
        _bootCount = prefs.getUInt("boot_count", 0) + 1;
        prefs.putUInt("boot_count", _bootCount);
        prefs.end();
    }

    if (!LittleFS.exists(LOG_DIR)) {
        LittleFS.mkdir(LOG_DIR);
    }
}

void startNtp() {
    if (_ntpStarted) return;
    // UTC (offset 0, dst 0). Fritzbox first so a stock home network without
    // outbound DNS still gets time. pool.ntp.org as fallback for any other
    // deployment.
    configTime(0, 0, "192.168.178.1", "pool.ntp.org");
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
    _ensureMutex();
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
    _ensureMutex();
    String out;
    if (xSemaphoreTake(_mutex, pdMS_TO_TICKS(500)) != pdTRUE) {
        return out;
    }

    if (LittleFS.exists(LOG_OLD))  _appendFile(LOG_OLD,  out);
    if (LittleFS.exists(LOG_PATH)) _appendFile(LOG_PATH, out);

    xSemaphoreGive(_mutex);
    return out;
}

void clear() {
    _ensureMutex();
    if (xSemaphoreTake(_mutex, pdMS_TO_TICKS(500)) != pdTRUE) {
        return;
    }
    if (LittleFS.exists(LOG_PATH)) LittleFS.remove(LOG_PATH);
    if (LittleFS.exists(LOG_OLD))  LittleFS.remove(LOG_OLD);
    xSemaphoreGive(_mutex);
}

}  // namespace WifiLog
