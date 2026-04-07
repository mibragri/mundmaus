#pragma once
// web_server.h -- HTTP server (port 80) + WebSocket server (port 81)
// Wraps ESPAsyncWebServer, mirrors MicroPython server.py API contract.

#include <ESPAsyncWebServer.h>
#include <ArduinoJson.h>
#include <freertos/queue.h>
#include <freertos/semphr.h>
#include <atomic>
#include "wifi_manager.h"
#include "updater.h"

// Forward declarations (avoid pulling in full sensor headers)
class CalibratedJoystick;
class PuffSensor;

// Thread-safe event for sensor->WS bridge (I1)
struct SensorEvent {
    enum Type { NAV, NAV_HOLD, NAV_RELEASE, ACTION, PUFF_LEVEL, CALIBRATE_DONE,
                UPDATE_PROGRESS, UPDATE_COMPLETE, UPDATE_ERROR, UPDATE_RESULT,
                DEBUG_JOYSTICK } type;
    char data[64];   // direction string, action kind, or filename/message
    float value;     // for puff_level
    int intVal;      // for progress current/total, calibrate centerX
    int intVal2;     // for progress total, calibrate centerY
    int intVal3;     // for calibrate_done: baseline
};

class MundMausServer {
public:
    explicit MundMausServer(WiFiManager& wifi);

    /// Start both HTTP (80) and WS (81) servers
    void start();

    /// Check pending reboot timer, call from loop()
    void checkReboot();

    // -- Sensors (set by main after sensor init) --
    void setSensors(CalibratedJoystick* joy, PuffSensor* puff);

    // -- OTA update result (set by main after check) --
    void setUpdateResult(const Updater::CheckResult& result);

    // -- Outbound (thread-safe: pushes to queue, safe from any core) --
    void sendNav(const char* direction);
    void sendNavHold(const char* direction, float intensity);
    void sendNavRelease();
    void sendAction(const char* kind);
    void sendPuffLevel(float value);

    /// Drain sensor queue and broadcast via WS (call from loop(), main core)
    void processSensorQueue();

    /// Queue handle accessor (for sensor task calibrate_done)
    QueueHandle_t sensorQueue() const { return _sensorQueue; }

    /// Set by WS handler, checked by sensor task (I3: non-blocking calibrate)
    volatile bool calibrateRequested = false;

    /// ADC debug stream — toggled via WS command "debug_joy", sends raw values at 5Hz.
    /// Data goes ONLY to the requesting client (tracked by ID) + Serial.
    volatile bool debugJoystick = false;
    volatile uint32_t debugJoystickClientId = 0;

    /// Hardware status (set by main before start)
    struct HwStatus {
        bool joystick = false;
        bool puff     = false;
        bool display  = false;
    } hwStatus;

private:
    AsyncWebServer _httpServer;
    AsyncWebServer _wsHttpServer;   // HTTP server on port 81 for WS upgrade
    AsyncWebSocket _ws;
    WiFiManager&   _wifi;
    volatile unsigned long _pendingReboot;  // 0 = none, else millis() when requested (M5: volatile)

    // Thread-safe sensor->WS queue (I1)
    QueueHandle_t _sensorQueue;

    // Sensor pointers (owned by main, nullable)
    CalibratedJoystick* _joystick = nullptr;
    PuffSensor*         _puffSensor = nullptr;

    // Cached OTA check result.
    // P1-2: Written by the periodic check task (Core 1) and the OTA install
    // task, read by AsyncTCP handlers on Core 0. Every access MUST hold
    // _updateResultMutex. External writers should use setUpdateResult().
    Updater::CheckResult _updateResult;
    SemaphoreHandle_t _updateResultMutex = nullptr;

    void _setupHttpRoutes();
    void _setupWsRoutes();
    void _onWsEvent(AsyncWebSocket* server, AsyncWebSocketClient* client,
                    AwsEventType type, void* arg, uint8_t* data, size_t len);
    void _handleWsMessage(AsyncWebSocketClient* client, JsonDocument& msg);
    void _sendJson(AsyncWebServerRequest* req, int status, JsonDocument& doc);
    void _sendJson200(AsyncWebServerRequest* req, JsonDocument& doc);
    int _applyConfigValues(JsonObjectConst values);

    // P1-3: Thread-safe broadcast via shared buffer. Uses makeBuffer() so
    // each client dequeues at its own pace via ref-counted buffer. Mitigates
    // the _clients list-iteration race (see processSensorQueue comment).
    void _broadcastText(const String& msg);

    // Build JSON for update status (shared by HTTP + WS)
    void _buildUpdateJson(JsonDocument& doc);

    // I5: One-shot FreeRTOS task for blocking OTA downloads
    static void _updateTaskWrapper(void* param);
    std::atomic<bool> _updateRunning{false};

    // P1-4: Async WiFi scan — scanNetworks() blocks 2-5s, so we run it in
    // a short-lived task and broadcast the result via WS when finished.
    void _startAsyncScan();
    static void _wifiScanTaskWrapper(void* param);
    std::atomic<bool> _wifiScanRunning{false};
    std::atomic<bool> _checkRunning{false};
};
