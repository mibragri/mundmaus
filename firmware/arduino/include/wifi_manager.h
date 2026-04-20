#pragma once
// wifi_manager.h -- WiFi station/AP management with NVS credential persistence

#include <Arduino.h>
#include <ArduinoJson.h>
#include <freertos/FreeRTOS.h>
#include <freertos/semphr.h>
#include <vector>
#include <utility>

class WiFiManager {
public:
    WiFiManager() = default;

    /// Load SSID/password from NVS. Returns true if credentials found.
    bool loadCredentials();

    /// Save SSID/password to NVS. Returns true on success, false if the NVS
    /// write failed or was incomplete (in which case in-RAM state is NOT
    /// updated — callers must surface the error and not assume success).
    bool saveCredentials(const String& ssid, const String& password);

    /// Delete stored credentials from NVS.
    void deleteCredentials();

    /// Try connecting to saved SSID. Returns IP or empty string on failure.
    String connectStation(unsigned long timeoutMs = 15000);

    /// Start AP mode. Returns AP IP address.
    String startAP();

    /// Scan for visible networks. Returns deduplicated list sorted by RSSI.
    std::vector<String> scanNetworks();

    /// Get current RSSI and quality label. Returns (dBm, label).
    std::pair<int, String> getRSSI();

    /// Populate JsonDocument with current WiFi status.
    void getStatus(JsonDocument& doc);

    /// Full startup sequence: try station, fallback to AP.
    /// Returns (ip, mode) where mode is "station" or "ap".
    std::pair<String, String> startup();

    /// Current persisted TX-power index (0 = 15 dBm default, 4 = 7 dBm floor).
    /// Read from NVS; cheap to call.
    uint8_t txLevel();

    /// Cumulative count of brownout-triggered boots since first flash. Drives
    /// the cable-health indicator on the portal.
    uint32_t brownoutTotal();

    /// Human-readable hint for the portal if the adaptive stepdown or the
    /// brownout counter suggests a hardware problem. Returns an empty string
    /// when the power supply looks healthy.
    String powerHealthHint();

    // Public state
    // NOTE: ssid and password are protected by _credMutex on all write paths
    // and on all read paths that outlive the lock scope (e.g. WiFi.begin
    // taking const char* that must not be freed mid-connect). Callers that
    // only need a snapshot for display should copy under _credMutex.
    String ssid;
    String password;
    String mode;   // "station", "ap", or ""
    String ip;

private:
    // Bug 4: Protects concurrent credential changes (saveCredentials) against
    // in-flight reads (connectStation, getStatus). Without this, reassigning
    // `ssid = trimmed` frees the String buffer while another task may still
    // hold a pointer from ssid.c_str(), causing use-after-free.
    SemaphoreHandle_t _credMutex = nullptr;

    /// Lazily create _credMutex on first use.
    void _ensureMutex();

    /// Load last-known-good BSSID/channel from NVS (namespace "wifi",
    /// keys "last_bssid"/"last_chan"). Returns true if both present and
    /// the BSSID is a valid 6-byte blob.
    bool _loadLastBssid(uint8_t bssid[6], uint8_t& channel);

    /// Persist BSSID/channel of a successful connect so the next cold-boot
    /// can skip the scan phase. Scan is a TX-burst producer and has been
    /// the root-cause window for USB-brownouts on long-cable setups.
    void _saveLastBssid(const uint8_t bssid[6], uint8_t channel);

    /// Clear the cached BSSID/channel. Called when credentials change so
    /// the next boot does not waste a 15s cached-attempt timeout on a
    /// BSSID that belongs to an unreachable network.
    void _clearLastBssid();

    /// First-call-per-boot hook: consume esp_reset_reason() and, if it was a
    /// brownout, step the persisted TX-power level down one notch. Returns
    /// the wifi_power_t to apply. Floor is 7 dBm — below that the radio
    /// reaches specified minimum and further cuts stop helping.
    int _adaptiveTxPower();
};
