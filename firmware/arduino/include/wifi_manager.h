#pragma once
// wifi_manager.h -- WiFi station/AP management with NVS credential persistence

#include <Arduino.h>
#include <ArduinoJson.h>
#include <vector>
#include <utility>

class WiFiManager {
public:
    WiFiManager() = default;

    /// Load SSID/password from NVS. Returns true if credentials found.
    bool loadCredentials();

    /// Save SSID/password to NVS.
    void saveCredentials(const String& ssid, const String& password);

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

    // Public state
    String ssid;
    String password;
    String mode;   // "station", "ap", or ""
    String ip;
};
