#pragma once
// updater.h -- OTA update: manifest check + game/firmware download
// Two OTA paths:
//   1. Game files (HTML on LittleFS): HTTPS download to LittleFS
//   2. Firmware binary: HTTPS download to inactive OTA partition (dual-partition rollback)

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
/// Skips firmware entries.
/// progressCb(filename, current, total) called per file.
/// Returns true if all downloads succeeded.
bool installGameUpdates(const std::vector<UpdateFile>& files,
                        std::function<void(const String&, int, int)> progressCb = nullptr);

/// Download and install firmware update to inactive OTA partition.
/// Returns true if update was written. Caller should reboot after.
/// Automatic rollback if new firmware fails to boot.
bool installFirmwareUpdate(const UpdateFile& fw,
                           std::function<void(int, int)> progressCb = nullptr);

/// Mark current firmware partition as valid (cancel rollback).
/// Call after successful boot in setup().
void markBootOk();

/// Fetch remote settings from OTA server and apply (non-locally-overridden).
/// Returns number of settings applied, or -1 on fetch error.
int fetchRemoteSettings();

/// Load local version tracking from NVS (Preferences "ota_ver").
void loadVersions();

/// Save local version tracking to NVS.
void saveVersions();

}  // namespace Updater
