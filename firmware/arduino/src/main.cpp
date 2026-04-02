// main.cpp -- MundMaus ESP32 Firmware v3.2 (Arduino)
// Phases 1-7: Boot + WiFi + HTTP/WS + Sensors + LittleFS + Config + OTA

#include <Arduino.h>
#include <esp_task_wdt.h>

#include "config.h"
#include "wifi_manager.h"
#include "web_server.h"
#include "sensors.h"
#include "updater.h"

// Globals (must outlive setup)
static WiFiManager wifi;
static MundMausServer* server = nullptr;
static CalibratedJoystick* joystick = nullptr;
static PuffSensor* puffSensor = nullptr;

// Heartbeat timestamp for WDT (written by sensor task, read by loop)
static volatile unsigned long sensorHeartbeat = 0;

// ============================================================
// SENSOR TASK (FreeRTOS, Core 1, 50Hz)
// ============================================================

static void sensorTask(void* param) {
    (void)param;

    unsigned long idleStart = millis();
    unsigned long lastRecal = millis();
    unsigned long lastPuffSend = 0;

    for (;;) {
        unsigned long now = millis();

        // -- Joystick navigation --
        const char* nav = joystick->pollNavigation();
        if (nav) {
            server->sendNav(nav);
            idleStart = now;
        }

        // -- Joystick button --
        if (joystick->pollButton()) {
            server->sendAction("press");
            idleStart = now;
        }

        // -- Puff sensor --
        if (puffSensor) {
            puffSensor->poll();

            // Broadcast puff level periodically
            if ((now - lastPuffSend) > (unsigned long)Config::DEFAULT_PUFF_SEND_INTERVAL_MS) {
                float level = puffSensor->getLevel();
                if (level > 0.02f) {
                    server->sendPuffLevel(level);
                }
                lastPuffSend = now;
            }

            // Detect puff event
            if (puffSensor->detectPuff()) {
                server->sendAction("puff");
                idleStart = now;
            }
        }

        // -- Auto-recalibrate joystick when idle > 10s (max once per 60s) --
        if (joystick->isIdle()) {
            if ((now - idleStart) > (unsigned long)Config::DEFAULT_RECAL_IDLE_MS) {
                if ((now - lastRecal) > 60000) {
                    joystick->calibrate(20);
                    lastRecal = now;
                    idleStart = now;
                }
            }
        } else {
            idleStart = now;
        }

        // Update heartbeat for WDT check in loop()
        sensorHeartbeat = now;

        vTaskDelay(pdMS_TO_TICKS(Config::SENSOR_POLL_MS));
    }
}

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

    // -- Sensors --
    Serial.println("\n[Sensoren]");

    // Joystick (always initialized)
    joystick = new CalibratedJoystick(PIN_VRX, PIN_VRY, PIN_SW);
    bool joystickOk = (joystick->centerX > 200 && joystick->centerX < 3900 &&
                       joystick->centerY > 200 && joystick->centerY < 3900);
    if (joystickOk) {
        Serial.println("  Joystick: OK");
    } else {
        Serial.printf("  Joystick: WARNUNG Center=(%d,%d) ausserhalb 200-3900\n",
                      joystick->centerX, joystick->centerY);
    }

    esp_task_wdt_reset();

    // Puff sensor (may fail if not connected)
    puffSensor = new PuffSensor(PIN_PUFF_DATA, PIN_PUFF_CLK);
    bool puffOk = (puffSensor->baseline != 0);
    if (puffOk) {
        Serial.println("  Drucksensor: OK");
    } else {
        Serial.println("  Drucksensor: nicht erkannt (Baseline=0)");
        delete puffSensor;
        puffSensor = nullptr;
    }

    esp_task_wdt_reset();

    // HTTP + WebSocket server
    Serial.println("\n[Server]");
    server = new MundMausServer(wifi);
    server->hwStatus.joystick = joystickOk;
    server->hwStatus.puff     = puffOk;
    server->setSensors(joystick, puffSensor);
    server->start();

    // Start sensor task on Core 1, priority 2, 4KB stack
    sensorHeartbeat = millis();
    xTaskCreatePinnedToCore(
        sensorTask,
        "sensors",
        4096,
        nullptr,
        2,              // priority (above loop's 1)
        nullptr,
        1               // Core 1 (WiFi/AsyncTCP on Core 0)
    );
    Serial.println("\n[Sensor-Task] gestartet (Core 1, 50Hz)");

    Serial.printf("\n[Start] Heap frei: %u bytes\n", ESP.getFreeHeap());
    Serial.println("Bereit.\n");

    // Mark firmware boot as valid (cancel OTA rollback)
    Updater::markBootOk();

    // OTA check (only in station mode with internet)
    if (wifiMode == "station") {
        Serial.println("[OTA] Pruefe Updates...");
        esp_task_wdt_reset();
        Updater::CheckResult otaResult = Updater::checkManifest();
        esp_task_wdt_reset();
        server->setUpdateResult(otaResult);
        if (!otaResult.offline) {
            Serial.printf("[OTA] %d Updates verfuegbar\n", otaResult.available.size());
        } else {
            Serial.println("[OTA] Offline (Server nicht erreichbar)");
        }
    }
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
