// main.cpp -- MundMaus ESP32 Firmware v3.2 (Arduino)
// Phase 2+3: Boot + WiFi + HTTP Server + WebSocket

#include <Arduino.h>
#include <esp_task_wdt.h>

#include "config.h"
#include "wifi_manager.h"
#include "web_server.h"

// Globals (must outlive setup)
static WiFiManager wifi;
static MundMausServer* server = nullptr;

// ============================================================
// SETUP
// ============================================================

void setup() {
    Serial.begin(115200);
    while (!Serial && millis() < 2000) { delay(10); }

    // Hardware watchdog (30s timeout)
    const esp_task_wdt_config_t wdtCfg = {
        .timeout_ms       = 30000,
        .idle_core_mask   = 0,       // don't watch idle tasks
        .trigger_panic    = true,
    };
    esp_task_wdt_reconfigure(&wdtCfg);
    esp_task_wdt_add(nullptr);

    // Load saved settings from NVS
    Config::load();

    // Banner
    Serial.println();
    Serial.println("==========================================");
    Serial.printf( "  MUNDMAUS v%s\n", Config::VERSION);
    Serial.printf( "  Board: %s\n", BOARD_NAME);
    Serial.println("==========================================");

    // WiFi
    Serial.println("\n[Netzwerk]");
    auto [ip, wifiMode] = wifi.startup();

    Serial.println();
    Serial.println("  ======================================");
    if (wifiMode == "ap") {
        Serial.printf("  HOTSPOT: %s / %s\n", Config::AP_SSID, Config::AP_PASS);
    } else {
        Serial.printf("  WLAN: %s\n", wifi.ssid.c_str());
    }
    Serial.printf("  IP: %s\n", ip.c_str());
    Serial.printf("  http://%s\n", ip.c_str());
    Serial.println("  ======================================");

    // Feed WDT after WiFi (may have taken a few seconds)
    esp_task_wdt_reset();

    // HTTP + WebSocket server
    Serial.println("\n[Server]");
    server = new MundMausServer(wifi);
    // TODO: set hwStatus.joystick / .puff when sensors are initialized
    server->start();

    Serial.printf("\n[Start] Heap frei: %u bytes\n", ESP.getFreeHeap());
    Serial.println("Bereit.\n");
}

// ============================================================
// LOOP
// ============================================================

void loop() {
    esp_task_wdt_reset();

    // Check pending reboot
    if (server) {
        server->checkReboot();
    }

    delay(10);
}
