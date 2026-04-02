#pragma once
// web_server.h -- HTTP server (port 80) + WebSocket server (port 81)
// Wraps ESPAsyncWebServer, mirrors MicroPython server.py API contract.

#include <ESPAsyncWebServer.h>
#include <ArduinoJson.h>
#include "wifi_manager.h"

class MundMausServer {
public:
    explicit MundMausServer(WiFiManager& wifi);

    /// Start both HTTP (80) and WS (81) servers
    void start();

    /// Check pending reboot timer, call from loop()
    void checkReboot();

    // -- Outbound (called by sensor task later) --
    void sendNav(const char* direction);
    void sendAction(const char* kind);
    void sendPuffLevel(float value);

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
    unsigned long  _pendingReboot;  // 0 = none, else millis() when requested

    void _setupHttpRoutes();
    void _setupWsRoutes();
    void _onWsEvent(AsyncWebSocket* server, AsyncWebSocketClient* client,
                    AwsEventType type, void* arg, uint8_t* data, size_t len);
    void _handleWsMessage(AsyncWebSocketClient* client, JsonDocument& msg);
    void _sendJson(AsyncWebServerRequest* req, int status, JsonDocument& doc);
    void _sendJson200(AsyncWebServerRequest* req, JsonDocument& doc);
};
