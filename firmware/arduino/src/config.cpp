// config.cpp -- MundMaus runtime configuration (NVS-backed)

#include "config.h"
#include <Preferences.h>

namespace Config {

// ============================================================
// GLOBALS (runtime-adjustable, initialized to defaults)
// ============================================================

volatile int DEADZONE         = DEFAULT_DEADZONE;
volatile int NAV_THRESHOLD    = DEFAULT_NAV_THRESHOLD;
volatile int NAV_REPEAT_MS    = DEFAULT_NAV_REPEAT_MS;
volatile int NAV_COOLDOWN_MS  = DEFAULT_NAV_COOLDOWN_MS;
volatile int PUFF_COOLDOWN_MS  = DEFAULT_PUFF_COOLDOWN_MS;
volatile int PUFF_RAW_THRESHOLD = DEFAULT_PUFF_RAW_THRESHOLD;
volatile int SENSOR_POLL_MS    = DEFAULT_SENSOR_POLL_MS;

// ============================================================
// KEY TABLES
// ============================================================

const char* CONFIGURABLE_KEYS[NUM_CONFIGURABLE] = {
    "DEADZONE",
    "NAV_THRESHOLD",
    "NAV_REPEAT_MS",
    "NAV_COOLDOWN_MS",
    "PUFF_COOLDOWN_MS",
    "PUFF_RAW_THRESHOLD",
    "SENSOR_POLL_MS",
};

const Range RANGES[NUM_CONFIGURABLE] = {
    {  10,   1000 },   // DEADZONE
    { 100,   2000 },   // NAV_THRESHOLD
    {  50,   2000 },   // NAV_REPEAT_MS
    {  50,   3000 },   // NAV_COOLDOWN_MS
    {  50,   5000 },   // PUFF_COOLDOWN_MS
    { 10000, 200000 }, // PUFF_RAW_THRESHOLD
    {   5,    500 },   // SENSOR_POLL_MS
};

// ============================================================
// HELPERS
// ============================================================

/// Map key index to the corresponding global variable pointer
static volatile int* _globalPtr(int idx) {
    switch (idx) {
        case 0: return &DEADZONE;
        case 1: return &NAV_THRESHOLD;
        case 2: return &NAV_REPEAT_MS;
        case 3: return &NAV_COOLDOWN_MS;
        case 4: return &PUFF_COOLDOWN_MS;
        case 5: return &PUFF_RAW_THRESHOLD;
        case 6: return &SENSOR_POLL_MS;
        default: return nullptr;
    }
}

static int _defaultVal(int idx) {
    switch (idx) {
        case 0: return DEFAULT_DEADZONE;
        case 1: return DEFAULT_NAV_THRESHOLD;
        case 2: return DEFAULT_NAV_REPEAT_MS;
        case 3: return DEFAULT_NAV_COOLDOWN_MS;
        case 4: return DEFAULT_PUFF_COOLDOWN_MS;
        case 5: return DEFAULT_PUFF_RAW_THRESHOLD;
        case 6: return DEFAULT_SENSOR_POLL_MS;
        default: return 0;
    }
}

/// Find index of key, or -1 if not found
static int _findKey(const char* key) {
    for (int i = 0; i < NUM_CONFIGURABLE; i++) {
        if (strcmp(key, CONFIGURABLE_KEYS[i]) == 0) return i;
    }
    return -1;
}

// ============================================================
// PUBLIC API
// ============================================================

void load() {
    Preferences prefs;
    prefs.begin("settings", true);  // read-only

    for (int i = 0; i < NUM_CONFIGURABLE; i++) {
        volatile int* ptr = _globalPtr(i);
        if (ptr) {
            // P2-1: Clamp to the valid range. Corrupt or legacy NVS values
            // (e.g. a PUFF_RAW_THRESHOLD of 0 from an older firmware schema)
            // could leave the device in a broken state that the patient
            // cannot recover from without keyboard access.
            int val = prefs.getInt(CONFIGURABLE_KEYS[i], _defaultVal(i));
            *ptr = constrain(val, RANGES[i].min, RANGES[i].max);
        }
    }

    prefs.end();
}

void save() {
    Preferences prefs;
    prefs.begin("settings", false);  // read-write

    for (int i = 0; i < NUM_CONFIGURABLE; i++) {
        volatile int* ptr = _globalPtr(i);
        if (!ptr) continue;

        if (*ptr != _defaultVal(i)) {
            prefs.putInt(CONFIGURABLE_KEYS[i], *ptr);
        } else {
            // Remove key if value equals default (keep NVS clean)
            prefs.remove(CONFIGURABLE_KEYS[i]);
        }
    }

    prefs.end();
}

void reset() {
    // Restore defaults in RAM
    for (int i = 0; i < NUM_CONFIGURABLE; i++) {
        volatile int* ptr = _globalPtr(i);
        if (ptr) *ptr = _defaultVal(i);
    }

    // Clear NVS namespace
    Preferences prefs;
    prefs.begin("settings", false);
    prefs.clear();
    prefs.end();
}

bool update(const char* key, int value) {
    int idx = _findKey(key);
    if (idx < 0) return false;

    volatile int* ptr = _globalPtr(idx);
    if (!ptr) return false;

    // Clamp to valid range
    int clamped = constrain(value, RANGES[idx].min, RANGES[idx].max);
    *ptr = clamped;

    // Cross-validate: NAV_THRESHOLD must exceed DEADZONE by at least 50
    if (NAV_THRESHOLD <= DEADZONE + 50) {
        NAV_THRESHOLD = DEADZONE + 100;
    }

    return true;
}

void getAll(JsonDocument& doc) {
    for (int i = 0; i < NUM_CONFIGURABLE; i++) {
        volatile int* ptr = _globalPtr(i);
        if (ptr) doc[CONFIGURABLE_KEYS[i]] = *ptr;
    }
}

void getDefaults(JsonDocument& doc) {
    for (int i = 0; i < NUM_CONFIGURABLE; i++) {
        doc[CONFIGURABLE_KEYS[i]] = _defaultVal(i);
    }
}

void getSaved(JsonDocument& doc) {
    Preferences prefs;
    prefs.begin("settings", true);

    for (int i = 0; i < NUM_CONFIGURABLE; i++) {
        // Check if key exists in NVS (isKey returns true only if stored)
        if (prefs.isKey(CONFIGURABLE_KEYS[i])) {
            doc[CONFIGURABLE_KEYS[i]] = prefs.getInt(CONFIGURABLE_KEYS[i], _defaultVal(i));
        }
    }

    prefs.end();
}

int applyRemote(const JsonDocument& remote) {
    // Only apply keys that are NOT locally customized (not in NVS)
    Preferences prefs;
    prefs.begin("settings", true);  // read-only

    int applied = 0;
    for (JsonPairConst kv : remote.as<JsonObjectConst>()) {
        const char* key = kv.key().c_str();
        int idx = _findKey(key);
        if (idx < 0) continue;

        // Skip if locally customized
        if (prefs.isKey(key)) continue;

        int value = kv.value().as<int>();
        if (update(key, value)) {
            applied++;
            Serial.printf("  Remote setting: %s=%d\n", key, value);
        }
    }

    prefs.end();
    return applied;
}

}  // namespace Config
