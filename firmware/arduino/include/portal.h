#pragma once
// portal.h -- Generate portal HTML (dark theme, game buttons, WiFi status)
// Mirrors MicroPython server.py _generate_portal() output exactly.

#include <Arduino.h>
#include "wifi_manager.h"

struct PortalHwStatus {
    bool joystick = false;
    bool puff     = false;
};

/// Generate the full portal HTML page.
/// Scans LittleFS /www/ for game .html files, builds dark-themed portal
/// with WiFi status, game buttons, settings link, and embedded JS.
String generatePortal(WiFiManager& wifi, const PortalHwStatus& hw);
