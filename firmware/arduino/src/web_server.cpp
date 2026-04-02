// web_server.cpp -- HTTP + WebSocket server (mirrors MicroPython server.py)

#include "web_server.h"
#include "portal.h"
#include "config.h"
#include <LittleFS.h>
#include <WiFi.h>

// ============================================================
// CONSTRUCTOR
// ============================================================

MundMausServer::MundMausServer(WiFiManager& wifi)
    : _httpServer(Config::HTTP_PORT)
    , _wsHttpServer(Config::WS_PORT)
    , _ws("/")
    , _wifi(wifi)
    , _pendingReboot(0)
{
    hwStatus = {false, false, false};
}

// ============================================================
// START
// ============================================================

void MundMausServer::start() {
    // Initialize LittleFS for static file serving
    if (!LittleFS.begin(true)) {
        Serial.println("  LittleFS mount failed");
    }

    _setupHttpRoutes();
    _setupWsRoutes();

    _httpServer.begin();
    _wsHttpServer.begin();

    Serial.printf("  HTTP  :%d\n", Config::HTTP_PORT);
    Serial.printf("  WS    :%d\n", Config::WS_PORT);
}

// ============================================================
// HTTP ROUTES
// ============================================================

void MundMausServer::_setupHttpRoutes() {
    // --- GET / --- Portal HTML
    _httpServer.on("/", HTTP_GET, [this](AsyncWebServerRequest* req) {
        PortalHwStatus hw;
        hw.joystick = hwStatus.joystick;
        hw.puff     = hwStatus.puff;
        String html = generatePortal(_wifi, hw);
        req->send(200, "text/html; charset=utf-8", html);
    });

    // --- GET /api/info ---
    _httpServer.on("/api/info", HTTP_GET, [this](AsyncWebServerRequest* req) {
        JsonDocument doc;
        doc["version"]  = Config::VERSION;
        doc["board"]    = BOARD_NAME;
        doc["ip"]       = _wifi.ip;
        doc["mode"]     = _wifi.mode;
        doc["mem_free"] = ESP.getFreeHeap();
        _sendJson200(req, doc);
    });

    // --- GET /api/wifi ---
    _httpServer.on("/api/wifi", HTTP_GET, [this](AsyncWebServerRequest* req) {
        JsonDocument doc;
        _wifi.getStatus(doc);
        _sendJson200(req, doc);
    });

    // --- POST /api/wifi --- Save credentials + reboot
    _httpServer.on("/api/wifi", HTTP_POST,
        // Request handler (called after body is fully received)
        [this](AsyncWebServerRequest* req) {},
        // Upload handler (unused)
        nullptr,
        // Body handler
        [this](AsyncWebServerRequest* req, uint8_t* data, size_t len, size_t index, size_t total) {
            // Accumulate body (single chunk for small JSON)
            if (index == 0) {
                req->_tempObject = new String();
            }
            String* body = static_cast<String*>(req->_tempObject);
            body->concat(reinterpret_cast<const char*>(data), len);

            if (index + len >= total) {
                // Full body received, parse and respond
                JsonDocument input;
                DeserializationError err = deserializeJson(input, *body);
                delete body;
                req->_tempObject = nullptr;

                if (err) {
                    JsonDocument doc;
                    doc["ok"]    = false;
                    doc["error"] = "JSON parse error";
                    _sendJson(req, 400, doc);
                    return;
                }

                const char* ssid = input["ssid"] | "";
                const char* pw   = input["password"] | "";

                if (strlen(ssid) == 0) {
                    JsonDocument doc;
                    doc["ok"]    = false;
                    doc["error"] = "SSID leer";
                    _sendJson(req, 400, doc);
                    return;
                }

                _wifi.saveCredentials(String(ssid), String(pw));

                // Notify WS clients
                JsonDocument wsMsg;
                wsMsg["type"]    = "wifi_status";
                wsMsg["status"]  = "saved";
                wsMsg["ssid"]    = ssid;
                wsMsg["message"] = "Gespeichert. Neustart...";
                String wsBuf;
                serializeJson(wsMsg, wsBuf);
                _ws.textAll(wsBuf);

                // Send HTTP response
                JsonDocument doc;
                doc["ok"]      = true;
                doc["ssid"]    = ssid;
                String msg = String("'") + ssid + "' gespeichert. Neustart...";
                doc["message"] = msg;
                _sendJson200(req, doc);

                _pendingReboot = millis();
            }
        }
    );

    // --- GET /api/scan ---
    _httpServer.on("/api/scan", HTTP_GET, [this](AsyncWebServerRequest* req) {
        std::vector<String> networks = _wifi.scanNetworks();
        JsonDocument doc;
        JsonArray arr = doc["networks"].to<JsonArray>();
        for (const auto& n : networks) {
            arr.add(n);
        }
        _sendJson200(req, doc);
    });

    // --- GET /api/settings ---
    _httpServer.on("/api/settings", HTTP_GET, [this](AsyncWebServerRequest* req) {
        JsonDocument doc;
        JsonObject current  = doc["current"].to<JsonObject>();
        JsonObject defaults = doc["defaults"].to<JsonObject>();
        JsonObject saved    = doc["saved"].to<JsonObject>();

        // Use temporary docs to populate nested objects
        JsonDocument curDoc;
        Config::getAll(curDoc);
        for (JsonPair kv : curDoc.as<JsonObject>()) {
            current[kv.key()] = kv.value();
        }

        JsonDocument defDoc;
        Config::getDefaults(defDoc);
        for (JsonPair kv : defDoc.as<JsonObject>()) {
            defaults[kv.key()] = kv.value();
        }

        JsonDocument savDoc;
        Config::getSaved(savDoc);
        for (JsonPair kv : savDoc.as<JsonObject>()) {
            saved[kv.key()] = kv.value();
        }

        _sendJson200(req, doc);
    });

    // --- GET /api/reboot ---
    _httpServer.on("/api/reboot", HTTP_GET, [this](AsyncWebServerRequest* req) {
        JsonDocument doc;
        doc["ok"] = true;
        _sendJson200(req, doc);
        _pendingReboot = millis();
    });

    // --- GET /api/updates --- (stub, offline)
    _httpServer.on("/api/updates", HTTP_GET, [](AsyncWebServerRequest* req) {
        JsonDocument doc;
        doc["available"] = JsonArray();
        doc["offline"]   = true;
        String buf;
        serializeJson(doc, buf);
        req->send(200, "application/json", buf);
    });

    // --- POST /api/updates/check --- (reboot)
    _httpServer.on("/api/updates/check", HTTP_POST, [this](AsyncWebServerRequest* req) {
        JsonDocument doc;
        doc["ok"]      = true;
        doc["message"] = "Neustart...";
        _sendJson200(req, doc);
        _pendingReboot = millis();
    });

    // --- POST /api/update/start --- (stub)
    _httpServer.on("/api/update/start", HTTP_POST, [](AsyncWebServerRequest* req) {
        JsonDocument doc;
        doc["ok"]    = false;
        doc["error"] = "Keine Updates";
        String buf;
        serializeJson(doc, buf);
        req->send(200, "application/json", buf);
    });

    // --- Static files from LittleFS /www/ ---
    _httpServer.serveStatic("/www/", LittleFS, "/www/")
        .setCacheControl("no-cache");

    // --- GET /favicon.ico --- 204
    _httpServer.on("/favicon.ico", HTTP_GET, [](AsyncWebServerRequest* req) {
        req->send(204);
    });

    // --- Default handler --- 404
    _httpServer.onNotFound([](AsyncWebServerRequest* req) {
        req->send(404, "text/html",
                  "<html><body><h1>404</h1><p>" + req->url() + "</p></body></html>");
    });

    // CORS headers for all responses
    DefaultHeaders::Instance().addHeader("Access-Control-Allow-Origin", "*");
}

// ============================================================
// WEBSOCKET
// ============================================================

void MundMausServer::_setupWsRoutes() {
    _ws.onEvent([this](AsyncWebSocket* server, AsyncWebSocketClient* client,
                       AwsEventType type, void* arg, uint8_t* data, size_t len) {
        _onWsEvent(server, client, type, arg, data, len);
    });
    _wsHttpServer.addHandler(&_ws);
}

void MundMausServer::_onWsEvent(AsyncWebSocket* server, AsyncWebSocketClient* client,
                                 AwsEventType type, void* arg, uint8_t* data, size_t len) {
    if (type == WS_EVT_CONNECT) {
        Serial.printf("  WS client #%u connected\n", client->id());

        // Send wifi_status
        JsonDocument wsDoc;
        wsDoc["type"]   = "wifi_status";
        wsDoc["status"] = (_wifi.mode == "station") ? "connected" : "ap";
        wsDoc["ssid"]   = _wifi.ssid.length() > 0 ? _wifi.ssid : String(Config::AP_SSID);
        wsDoc["ip"]     = _wifi.ip;
        wsDoc["mode"]   = _wifi.mode;
        String buf;
        serializeJson(wsDoc, buf);
        client->text(buf);

        // Send update_status (offline stub)
        JsonDocument updDoc;
        updDoc["type"]      = "update_status";
        updDoc["available"] = JsonArray();
        updDoc["offline"]   = true;
        String updBuf;
        serializeJson(updDoc, updBuf);
        client->text(updBuf);

    } else if (type == WS_EVT_DISCONNECT) {
        Serial.printf("  WS client #%u disconnected\n", client->id());

    } else if (type == WS_EVT_DATA) {
        AwsFrameInfo* info = static_cast<AwsFrameInfo*>(arg);
        if (info->final && info->index == 0 && info->len == len && info->opcode == WS_TEXT) {
            // Complete text frame
            JsonDocument msg;
            DeserializationError err = deserializeJson(msg, data, len);
            if (!err) {
                _handleWsMessage(client, msg);
            }
        }
    }
    // WS_EVT_ERROR and WS_EVT_PONG ignored
}

void MundMausServer::_handleWsMessage(AsyncWebSocketClient* client, JsonDocument& msg) {
    const char* type = msg["type"] | "";

    if (strcmp(type, "wifi_config") == 0) {
        const char* ssid = msg["ssid"] | "";
        const char* pw   = msg["password"] | "";
        if (strlen(ssid) > 0) {
            _wifi.saveCredentials(String(ssid), String(pw));

            JsonDocument resp;
            resp["type"]    = "wifi_status";
            resp["status"]  = "saved";
            resp["ssid"]    = ssid;
            resp["message"] = "Gespeichert. Neustart...";
            String buf;
            serializeJson(resp, buf);
            _ws.textAll(buf);

            _pendingReboot = millis();
        }

    } else if (strcmp(type, "wifi_scan") == 0) {
        std::vector<String> networks = _wifi.scanNetworks();
        JsonDocument resp;
        resp["type"] = "wifi_networks";
        JsonArray arr = resp["networks"].to<JsonArray>();
        for (const auto& n : networks) {
            arr.add(n);
        }
        String buf;
        serializeJson(resp, buf);
        _ws.textAll(buf);

    } else if (strcmp(type, "config_preview") == 0) {
        const char* key = msg["key"] | "";
        if (strlen(key) > 0 && msg["value"].is<int>()) {
            Config::update(key, msg["value"].as<int>());
        }

    } else if (strcmp(type, "config_save") == 0) {
        Config::save();
        JsonDocument resp;
        resp["type"] = "config_saved";
        resp["ok"]   = true;
        String buf;
        serializeJson(resp, buf);
        _ws.textAll(buf);

    } else if (strcmp(type, "config_reset") == 0) {
        Config::reset();
        JsonDocument resp;
        resp["type"] = "config_values";

        JsonDocument curDoc;
        Config::getAll(curDoc);
        resp["current"] = curDoc;

        JsonDocument defDoc;
        Config::getDefaults(defDoc);
        resp["defaults"] = defDoc;

        resp["saved"] = JsonObject();

        String buf;
        serializeJson(resp, buf);
        _ws.textAll(buf);

    } else if (strcmp(type, "calibrate") == 0) {
        // Stub: sensors not yet implemented
        JsonDocument resp;
        resp["type"] = "calibrate_done";
        String buf;
        serializeJson(resp, buf);
        _ws.textAll(buf);
    }
}

// ============================================================
// OUTBOUND (sensor -> browser)
// ============================================================

void MundMausServer::sendNav(const char* direction) {
    JsonDocument doc;
    doc["type"] = "nav";
    doc["dir"]  = direction;
    String buf;
    serializeJson(doc, buf);
    _ws.textAll(buf);
}

void MundMausServer::sendAction(const char* kind) {
    JsonDocument doc;
    doc["type"] = "action";
    doc["kind"] = kind;
    String buf;
    serializeJson(doc, buf);
    _ws.textAll(buf);
}

void MundMausServer::sendPuffLevel(float value) {
    JsonDocument doc;
    doc["type"]  = "puff_level";
    doc["value"] = serialized(String(value, 3));
    String buf;
    serializeJson(doc, buf);
    _ws.textAll(buf);
}

// ============================================================
// REBOOT CHECK (call from loop)
// ============================================================

void MundMausServer::checkReboot() {
    if (_pendingReboot > 0 && (millis() - _pendingReboot) > 2000) {
        Serial.println("  Reboot...");
        ESP.restart();
    }
}

// ============================================================
// JSON HELPERS
// ============================================================

void MundMausServer::_sendJson(AsyncWebServerRequest* req, int status, JsonDocument& doc) {
    String buf;
    serializeJson(doc, buf);
    req->send(status, "application/json", buf);
}

void MundMausServer::_sendJson200(AsyncWebServerRequest* req, JsonDocument& doc) {
    _sendJson(req, 200, doc);
}
