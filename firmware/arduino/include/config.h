#pragma once
// config.h -- MundMaus shared configuration
// Board detection via -D build flags in platformio.ini
// Runtime-adjustable values stored in ESP32 NVS (Preferences)

#include <Arduino.h>
#include <ArduinoJson.h>

// ============================================================
// BOARD NAME (derived from build flags)
// ============================================================
#if defined(BOARD_ESP32_S3)
  #define BOARD_NAME "ESP32-S3"
#elif defined(BOARD_ESP32_WROOM)
  #define BOARD_NAME "ESP32-WROOM"
#else
  #define BOARD_NAME "UNKNOWN"
#endif

// Pin defines come from -D flags in platformio.ini:
//   PIN_VRX, PIN_VRY, PIN_SW, PIN_PUFF_DATA, PIN_PUFF_CLK

namespace Config {

// ============================================================
// COMPILE-TIME CONSTANTS
// ============================================================

constexpr const char* VERSION = MUNDMAUS_VERSION;

// Network
constexpr uint16_t WS_PORT   = 81;
constexpr uint16_t HTTP_PORT = 80;

// AP Hotspot
constexpr const char* AP_SSID = "MundMaus";
constexpr const char* AP_PASS = "mundmaus1";
constexpr const char* AP_IP   = "192.168.4.1";

// Display
constexpr bool USE_DISPLAY = false;

// File serving
constexpr const char* WWW_DIR = "/www";

// OTA
constexpr const char* OTA_BASE_URL = "https://mundmaus.de/ota";
#ifdef OTA_AUTH_B64
constexpr const char* OTA_AUTH     = OTA_AUTH_B64;
#else
constexpr const char* OTA_AUTH     = "";
#endif

// ============================================================
// RUNTIME-ADJUSTABLE VALUES (defaults + extern globals)
// ============================================================

// Joystick
constexpr int DEFAULT_DEADZONE          = 150;
constexpr int DEFAULT_NAV_THRESHOLD     = 450;
constexpr int DEFAULT_NAV_REPEAT_MS     = 400;
constexpr int DEFAULT_CALIBRATION_SAMPLES = 50;

// Puff
constexpr int DEFAULT_PUFF_COOLDOWN_MS  = 400;
constexpr int DEFAULT_PUFF_RAW_THRESHOLD = 75000;

// Timing
constexpr int DEFAULT_RECAL_IDLE_MS         = 10000;
constexpr int DEFAULT_PUFF_SEND_INTERVAL_MS = 100;
constexpr int DEFAULT_SENSOR_POLL_MS        = 20;

// Globals (defined in config.cpp)
extern int DEADZONE;
extern int NAV_THRESHOLD;
extern int NAV_REPEAT_MS;
extern int PUFF_COOLDOWN_MS;
extern int PUFF_RAW_THRESHOLD;
extern int SENSOR_POLL_MS;

// ============================================================
// CONFIGURABLE KEYS (for settings UI)
// ============================================================

constexpr int NUM_CONFIGURABLE = 6;

extern const char* CONFIGURABLE_KEYS[NUM_CONFIGURABLE];

// Range validation (min, max per key)
struct Range {
    int min;
    int max;
};

extern const Range RANGES[NUM_CONFIGURABLE];

// ============================================================
// FUNCTIONS
// ============================================================

/// Load saved settings from NVS into globals
void load();

/// Save non-default values to NVS
void save();

/// Clear NVS and restore all defaults
void reset();

/// Update a single key at runtime (range-clamped)
/// Returns true if key was valid and updated
bool update(const char* key, int value);

/// Populate JsonDocument with all current configurable values
void getAll(JsonDocument& doc);

/// Populate JsonDocument with compile-time defaults
void getDefaults(JsonDocument& doc);

/// Populate JsonDocument with only NVS-persisted (non-default) values
void getSaved(JsonDocument& doc);

/// Apply remote settings: only keys NOT locally saved in NVS are updated.
/// Returns number of keys applied.
int applyRemote(const JsonDocument& remote);

}  // namespace Config
