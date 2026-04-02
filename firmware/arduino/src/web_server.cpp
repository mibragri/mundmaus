// web_server.cpp -- HTTP + WebSocket server (mirrors MicroPython server.py)

#include "web_server.h"
#include "portal.h"
#include "config.h"
#include "sensors.h"
#include "updater.h"
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
    , _sensorQueue(xQueueCreate(32, sizeof(SensorEvent)))  // M1: increased from 20 for OTA events
{
    if (!_sensorQueue) {
        Serial.println("  ERROR: Failed to create sensor queue!");
    }
    hwStatus = {false, false, false};
}

// ============================================================
// SENSOR + OTA SETTERS
// ============================================================

void MundMausServer::setSensors(CalibratedJoystick* joy, PuffSensor* puff) {
    _joystick = joy;
    _puffSensor = puff;
}

void MundMausServer::setUpdateResult(const Updater::CheckResult& result) {
    _updateResult = result;
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
            // M2: _tempObject leaks if client disconnects mid-upload.
            // ESPAsyncWebServer does not call body handler on disconnect,
            // so we cannot free it. Library limitation, not fixable here.
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

                _pendingReboot = millis() | 1;  // I3: ensure nonzero
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
        _pendingReboot = millis() | 1;  // I3: ensure nonzero
    });

    // --- GET /api/updates ---
    _httpServer.on("/api/updates", HTTP_GET, [this](AsyncWebServerRequest* req) {
        JsonDocument doc;
        _buildUpdateJson(doc);
        _sendJson200(req, doc);
    });

    // --- POST /api/updates/check --- I4: reboot to re-check (matches MicroPython)
    _httpServer.on("/api/updates/check", HTTP_POST, [this](AsyncWebServerRequest* req) {
        JsonDocument doc;
        doc["ok"]      = true;
        doc["message"] = "Neustart fuer Update-Pruefung...";
        _sendJson200(req, doc);
        _pendingReboot = millis() | 1;  // I3: ensure nonzero; OTA check runs automatically on boot
    });

    // --- POST /api/update/start --- I5: spawn FreeRTOS task (non-blocking)
    _httpServer.on("/api/update/start", HTTP_POST, [this](AsyncWebServerRequest* req) {
        if (_updateResult.available.empty() || _updateResult.offline) {
            JsonDocument doc;
            doc["ok"]    = false;
            doc["error"] = "Keine Updates verfuegbar";
            _sendJson200(req, doc);
            return;
        }

        // Send immediate response
        JsonDocument doc;
        doc["ok"]      = true;
        doc["message"] = "Update gestartet...";
        _sendJson200(req, doc);

        // Spawn one-shot task for blocking HTTPS downloads
        xTaskCreate(_updateTaskWrapper, "ota_install", 8192, this, 1, nullptr);
    });

    // --- OTA update task wrapper (I5: runs blocking downloads off async context) ---
    // (static method defined below, declared in header)

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

        // Send update_status
        JsonDocument updDoc;
        updDoc["type"] = "update_status";
        _buildUpdateJson(updDoc);
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

            _pendingReboot = millis() | 1;  // I3: ensure nonzero
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
        if (strlen(key) > 0) {
            // M3: Accept both int and float values (JS may send 1.0 for 1)
            if (msg["value"].is<int>()) {
                Config::update(key, msg["value"].as<int>());
            } else if (msg["value"].is<float>()) {
                Config::update(key, (int)msg["value"].as<float>());
            }
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
        // I3: Don't block async handler -- set flag, sensor task handles it
        calibrateRequested = true;
    }
}

// ============================================================
// OUTBOUND (sensor -> browser)
// ============================================================

void MundMausServer::sendNav(const char* direction) {
    // I1: Push to queue -- processed on main core in processSensorQueue()
    SensorEvent ev;
    ev.type = SensorEvent::NAV;
    strncpy(ev.data, direction, sizeof(ev.data) - 1);
    ev.data[sizeof(ev.data) - 1] = '\0';
    ev.value = 0;
    xQueueSend(_sensorQueue, &ev, 0);  // non-blocking
}

void MundMausServer::sendAction(const char* kind) {
    SensorEvent ev;
    ev.type = SensorEvent::ACTION;
    strncpy(ev.data, kind, sizeof(ev.data) - 1);
    ev.data[sizeof(ev.data) - 1] = '\0';
    ev.value = 0;
    xQueueSend(_sensorQueue, &ev, 0);
}

void MundMausServer::sendPuffLevel(float value) {
    // N1: NaN/Inf safety + clamp
    if (isnan(value) || isinf(value)) value = 0.0f;
    value = constrain(value, 0.0f, 1.0f);

    SensorEvent ev;
    ev.type = SensorEvent::PUFF_LEVEL;
    ev.data[0] = '\0';
    ev.value = value;
    xQueueSend(_sensorQueue, &ev, 0);
}

// I1: Drain queue and broadcast via WS (runs on main core, same as AsyncTCP)
void MundMausServer::processSensorQueue() {
    SensorEvent ev;
    while (xQueueReceive(_sensorQueue, &ev, 0) == pdTRUE) {
        JsonDocument doc;
        switch (ev.type) {
        case SensorEvent::NAV:
            doc["type"] = "nav";
            doc["dir"]  = ev.data;
            break;
        case SensorEvent::ACTION:
            doc["type"] = "action";
            doc["kind"] = ev.data;
            break;
        case SensorEvent::PUFF_LEVEL:
            doc["type"]  = "puff_level";
            doc["value"] = serialized(String(ev.value, 3));
            break;
        case SensorEvent::CALIBRATE_DONE: {
            // C1: Match MicroPython JSON keys exactly
            doc["type"] = "calibrate_done";
            if (ev.intVal != 0 || ev.intVal2 != 0) {
                JsonArray jc = doc["joy_center"].to<JsonArray>();
                jc.add(ev.intVal);
                jc.add(ev.intVal2);
            }
            if (ev.intVal3 != 0) {
                doc["puff_baseline"] = ev.intVal3;
            }
            break;
        }
        case SensorEvent::UPDATE_PROGRESS:
            doc["type"]    = "update_progress";
            doc["current"] = ev.intVal;
            doc["total"]   = ev.intVal2;
            doc["file"]    = ev.data;
            break;
        case SensorEvent::UPDATE_COMPLETE:
            doc["type"]    = "update_complete";
            doc["message"] = ev.data;
            break;
        case SensorEvent::UPDATE_ERROR:
            doc["type"]  = "update_error";
            doc["file"]  = ev.data;
            doc["error"] = ev.data;  // error detail in data field
            break;
        case SensorEvent::UPDATE_RESULT:
            // Safe assignment on main core (fixes I1 data race)
            _updateResult = Updater::checkManifest();
            break;
        }
        // UPDATE_RESULT is internal-only, no WS broadcast needed
        if (ev.type == SensorEvent::UPDATE_RESULT) continue;
        String buf;
        serializeJson(doc, buf);
        _ws.textAll(buf);
    }
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

// ============================================================
// OTA JSON BUILDER
// ============================================================

void MundMausServer::_buildUpdateJson(JsonDocument& doc) {
    doc["offline"] = _updateResult.offline;
    JsonArray arr = doc["available"].to<JsonArray>();
    for (const auto& uf : _updateResult.available) {
        if (uf.firmware) continue;  // Don't show firmware updates in portal (Arduino can't install .py)
        JsonObject obj = arr.add<JsonObject>();
        obj["file"]     = uf.name;
        obj["from_ver"] = uf.localVer;
        obj["to_ver"]   = uf.remoteVer;
        if (uf.deleteFile) {
            obj["delete"] = true;
        }
    }
}

// ============================================================
// OTA UPDATE TASK (I5: one-shot FreeRTOS task for blocking downloads)
// ============================================================

void MundMausServer::_updateTaskWrapper(void* param) {
    MundMausServer* self = static_cast<MundMausServer*>(param);
    QueueHandle_t q = self->_sensorQueue;

    // Install game files first
    bool ok = Updater::installGameUpdates(self->_updateResult.available,
        [q](const String& name, int cur, int total) {
            Serial.printf("  OTA: %s (%d/%d)\n", name.c_str(), cur, total);
            SensorEvent ev;
            ev.type = SensorEvent::UPDATE_PROGRESS;
            strncpy(ev.data, name.c_str(), sizeof(ev.data) - 1);
            ev.data[sizeof(ev.data) - 1] = '\0';
            ev.intVal  = cur;
            ev.intVal2 = total;
            xQueueSend(q, &ev, 0);
        });

    // Install firmware update if available
    bool needsReboot = false;
    for (const auto& uf : self->_updateResult.available) {
        if (uf.firmware && !uf.deleteFile && uf.name.endsWith(".bin")) {
            Serial.printf("  OTA: firmware update %s\n", uf.name.c_str());
            {
                SensorEvent ev;
                ev.type = SensorEvent::UPDATE_PROGRESS;
                strncpy(ev.data, "Firmware...", sizeof(ev.data) - 1);
                ev.data[sizeof(ev.data) - 1] = '\0';
                ev.intVal = 0; ev.intVal2 = 1;
                xQueueSend(q, &ev, 0);
            }
            bool fwOk = Updater::installFirmwareUpdate(uf,
                [q](int written, int total) {
                    SensorEvent ev;
                    ev.type = SensorEvent::UPDATE_PROGRESS;
                    strncpy(ev.data, "Firmware", sizeof(ev.data) - 1);
                    ev.data[sizeof(ev.data) - 1] = '\0';
                    ev.intVal = written / 1024;
                    ev.intVal2 = total / 1024;
                    xQueueSend(q, &ev, 0);
                });
            if (fwOk) needsReboot = true;
            else ok = false;
        }
    }

    Serial.printf("  OTA install %s\n", ok ? "OK" : "FAILED");

    // Push completion event
    {
        SensorEvent ev;
        if (ok) {
            ev.type = SensorEvent::UPDATE_COMPLETE;
            if (needsReboot) {
                strncpy(ev.data, "Update OK — Neustart...", sizeof(ev.data) - 1);
            } else {
                strncpy(ev.data, "Update abgeschlossen", sizeof(ev.data) - 1);
            }
        } else {
            ev.type = SensorEvent::UPDATE_ERROR;
            strncpy(ev.data, "Update fehlgeschlagen", sizeof(ev.data) - 1);
        }
        ev.data[sizeof(ev.data) - 1] = '\0';
        xQueueSend(q, &ev, 0);
    }

    // Reboot after firmware update
    if (needsReboot) {
        delay(3000);
        ESP.restart();
    }

    // I1: Push UPDATE_RESULT so main core re-checks manifest (no direct write)
    {
        SensorEvent ev;
        ev.type = SensorEvent::UPDATE_RESULT;
        ev.data[0] = '\0';
        xQueueSend(q, &ev, 0);
    }

    // Delete this one-shot task
    vTaskDelete(nullptr);
}
