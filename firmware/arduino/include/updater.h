#pragma once
// updater.h -- OTA update: manifest check + game file download
// Port of MicroPython updater.py to Arduino/ESP32.
// Two OTA paths:
//   1. Game files (HTML on LittleFS): HTTPS download to LittleFS
//   2. Firmware binary: detection only (full OTA via Update.h is future work)

#include <Arduino.h>
#include <vector>
#include <functional>

namespace Updater {

// ============================================================
// TYPES
// ============================================================

struct UpdateFile {
    String name;
    int localVer  = 0;
    int remoteVer = 0;
    bool firmware   = false;   // true = firmware binary, false = game file
    bool deleteFile = false;   // true = file removed from manifest
};

struct CheckResult {
    std::vector<UpdateFile> available;
    bool offline = true;       // true until a successful manifest fetch
};

// ============================================================
// PUBLIC API
// ============================================================

/// Check manifest against local version tracking.
/// Fetches https://mundmaus.de/ota/manifest.json with Basic Auth.
/// Returns list of files needing update + offline flag.
CheckResult checkManifest();

/// Download and install game file updates to LittleFS.
/// Skips firmware entries (detection only).
/// progressCb(filename, current, total) called per file.
/// Returns true if all downloads succeeded.
bool installGameUpdates(const std::vector<UpdateFile>& files,
                        std::function<void(const String&, int, int)> progressCb = nullptr);

/// Mark current firmware partition as valid (cancel rollback).
/// Call after successful boot in setup().
void markBootOk();

/// Load local version tracking from NVS (Preferences "ota_ver").
void loadVersions();

/// Save local version tracking to NVS.
void saveVersions();

}  // namespace Updater
