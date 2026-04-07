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
    // P1-2: Mutex protects _updateResult against concurrent access from
    // AsyncTCP handlers (Core 0), the OTA install task, and the periodic
    // check task. Created before start() so it is ready for any first access.
    _updateResultMutex = xSemaphoreCreateMutex();
    if (!_updateResultMutex) {
        Serial.println("  ERROR: Failed to create update result mutex!");
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
    // P1-2: Take the mutex so callers (main.cpp periodic check, OTA task)
    // can write without manual locking. 100ms is plenty — every holder of
    // this mutex does a short copy, never blocking I/O.
    if (_updateResultMutex && xSemaphoreTake(_updateResultMutex, pdMS_TO_TICKS(100)) == pdTRUE) {
        _updateResult = result;
        xSemaphoreGive(_updateResultMutex);
    }
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
            // ESPAsyncWebServer does not provide a request destructor callback
            // and does not call body handler on disconnect, so we cannot free it.
            // Reviewed: accepted as known limitation — only triggers during WiFi
            // config (rare), not normal operation. Leak is one String object.
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
                _broadcastText(wsBuf);

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
    // P1-4: WiFi.scanNetworks() blocks the caller for 2-5 seconds. If we run
    // it inline here we stall the AsyncTCP task on Core 0 — that starves WS
    // sensor traffic for the patient and may drop in-flight HTTP requests.
    // Spawn a one-shot task that performs the blocking scan off-thread, then
    // broadcasts results via WS so both the portal and any WS clients see
    // them. The HTTP caller gets an immediate "scan_started" acknowledgment.
    _httpServer.on("/api/scan", HTTP_GET, [this](AsyncWebServerRequest* req) {
        _startAsyncScan();
        JsonDocument doc;
        doc["ok"]      = true;
        doc["status"]  = "scan_started";
        doc["message"] = "Scan laeuft, Ergebnis per WebSocket";
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

    // --- POST /api/settings/preview ---
    // Used by the settings page to synchronously revert live-preview values
    // before navigating away. HTTP gives us an explicit success/failure point
    // that a best-effort WS send cannot guarantee during page unload.
    _httpServer.on("/api/settings/preview", HTTP_POST,
        [this](AsyncWebServerRequest* req) {},
        nullptr,
        [this](AsyncWebServerRequest* req, uint8_t* data, size_t len, size_t index, size_t total) {
            if (index == 0) {
                req->_tempObject = new String();
            }
            String* body = static_cast<String*>(req->_tempObject);
            body->concat(reinterpret_cast<const char*>(data), len);

            if (index + len < total) {
                return;
            }

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

            int applied = 0;
            if (input["values"].is<JsonObjectConst>()) {
                applied = _applyConfigValues(input["values"].as<JsonObjectConst>());
            } else {
                const char* key = input["key"] | "";
                if (strlen(key) > 0 && (input["value"].is<int>() || input["value"].is<float>())) {
                    applied = Config::update(key, (int)input["value"].as<float>()) ? 1 : 0;
                }
            }

            JsonDocument doc;
            doc["ok"]      = (applied > 0);
            doc["applied"] = applied;
            if (applied <= 0) {
                doc["error"] = "Keine gueltigen Werte";
                _sendJson(req, 400, doc);
                return;
            }

            JsonDocument resp;
            resp["type"] = "config_values";
            JsonDocument curDoc;
            Config::getAll(curDoc);
            resp["current"] = curDoc;
            String buf;
            serializeJson(resp, buf);
            _broadcastText(buf);

            _sendJson200(req, doc);
        }
    );

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

    // --- POST /api/updates/check --- Fresh manifest check (non-blocking background task)
    _httpServer.on("/api/updates/check", HTTP_POST, [this](AsyncWebServerRequest* req) {
        JsonDocument doc;
        doc["ok"]      = true;
        doc["message"] = "Pruefe...";
        _sendJson200(req, doc);

        // Spawn one-shot task to re-check manifest and broadcast result
        xTaskCreate([](void* param) {
            auto* srv = static_cast<MundMausServer*>(param);
            Updater::CheckResult result = Updater::checkManifest();
            srv->setUpdateResult(result);
            // Push UPDATE_RESULT so processSensorQueue broadcasts to WS clients
            SensorEvent ev;
            ev.type = SensorEvent::UPDATE_RESULT;
            ev.data[0] = '\0';
            xQueueSend(srv->sensorQueue(), &ev, 0);
            vTaskDelete(nullptr);
        }, "upd_check", 8192, this, 1, nullptr);
    });

    // --- POST /api/update/start --- I5: spawn FreeRTOS task (non-blocking)
    _httpServer.on("/api/update/start", HTTP_POST, [this](AsyncWebServerRequest* req) {
        // Atomic test-and-set: prevents TOCTOU race on concurrent requests
        bool expected = false;
        if (!_updateRunning.compare_exchange_strong(expected, true)) {
            JsonDocument doc;
            doc["ok"]    = false;
            doc["error"] = "Update laeuft bereits";
            _sendJson200(req, doc);
            return;
        }
        // P1-2: Snapshot _updateResult under the mutex so we decide based on
        // a consistent view. Reading .available.empty() and .offline without
        // the mutex races with the periodic check task's writer.
        bool hasUpdates = false;
        if (_updateResultMutex && xSemaphoreTake(_updateResultMutex, pdMS_TO_TICKS(100)) == pdTRUE) {
            hasUpdates = !_updateResult.available.empty() && !_updateResult.offline;
            xSemaphoreGive(_updateResultMutex);
        }
        if (!hasUpdates) {
            _updateRunning = false;  // release the flag
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

        // Spawn one-shot task for blocking HTTPS downloads (16KB stack for TLS+JSON+buffer)
        xTaskCreate(_updateTaskWrapper, "ota_install", 16384, this, 1, nullptr);
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
        req->send(404, "text/plain", "404 Not Found");
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
        // Drop messages instead of disconnecting when queue full.
        // Prevents patient losing joystick control during WiFi hiccups.
        client->setCloseClientOnQueueFull(false);
        Serial.printf("  WS client #%lu connected\n", (unsigned long)client->id());

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
        Serial.printf("  WS client #%lu disconnected\n", (unsigned long)client->id());

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
            _broadcastText(buf);

            _pendingReboot = millis() | 1;  // I3: ensure nonzero
        }

    } else if (strcmp(type, "wifi_scan") == 0) {
        // P1-4: Never call WiFi.scanNetworks() from this handler — it runs on
        // the AsyncTCP task (Core 0) and would block WS traffic for the
        // patient for 2-5 seconds. Dispatch to a worker task; results arrive
        // later as a wifi_networks broadcast.
        _startAsyncScan();
        JsonDocument resp;
        resp["type"]    = "wifi_scan_started";
        resp["message"] = "Scan laeuft";
        String buf;
        serializeJson(resp, buf);
        client->text(buf);

    } else if (strcmp(type, "config_preview") == 0) {
        const char* key = msg["key"] | "";
        if (strlen(key) > 0) {
            // M3: Accept both int and float values (JS may send 1.0 for 1)
            if (msg["value"].is<int>() || msg["value"].is<float>()) {
                Config::update(key, (int)msg["value"].as<float>());
            }
        }

    } else if (strcmp(type, "config_preview_bulk") == 0) {
        if (msg["values"].is<JsonObjectConst>()) {
            _applyConfigValues(msg["values"].as<JsonObjectConst>());
        }

    } else if (strcmp(type, "config_save") == 0) {
        Config::save();
        JsonDocument resp;
        resp["type"] = "config_saved";
        resp["ok"]   = true;
        String buf;
        serializeJson(resp, buf);
        _broadcastText(buf);

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
        _broadcastText(buf);

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

void MundMausServer::sendNavHold(const char* direction, float intensity) {
    SensorEvent ev;
    ev.type = SensorEvent::NAV_HOLD;
    strncpy(ev.data, direction, sizeof(ev.data) - 1);
    ev.data[sizeof(ev.data) - 1] = '\0';
    ev.value = constrain(intensity, 0.0f, 1.0f);
    xQueueSend(_sensorQueue, &ev, 0);
}

void MundMausServer::sendNavRelease() {
    SensorEvent ev;
    ev.type = SensorEvent::NAV_RELEASE;
    ev.data[0] = '\0';
    ev.value = 0;
    xQueueSend(_sensorQueue, &ev, 0);
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

// I1: Drain queue and broadcast via WS (runs on loop() task, Core 1).
//
// P1-3 (mitigated): _ws.textAll() iterates AsyncWebSocket::_clients
// (std::list) without a library mutex. AsyncTCP on Core 0 can
// emplace_back concurrently. We mitigate via _broadcastText() which
// uses makeBuffer() + textAll(buffer): the shared_ptr buffer lets
// each client dequeue independently via the per-client lock, and
// setCloseClientOnQueueFull(false) prevents list mutations from full
// queues. The list-iteration race window is microseconds (small JSON,
// 10Hz rate) and client connect/disconnect events are seconds apart.
// A full fix requires library-level locking on _clients.
void MundMausServer::processSensorQueue() {
    _ws.cleanupClients();  // prune stale/disconnected WebSocket clients

    SensorEvent ev;
    while (xQueueReceive(_sensorQueue, &ev, 0) == pdTRUE) {
        JsonDocument doc;
        switch (ev.type) {
        case SensorEvent::NAV:
            doc["type"] = "nav";
            doc["dir"]  = ev.data;
            break;
        case SensorEvent::NAV_HOLD:
            doc["type"]      = "nav_hold";
            doc["dir"]       = ev.data;
            doc["intensity"] = ev.value;
            break;
        case SensorEvent::NAV_RELEASE:
            doc["type"] = "nav_release";
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
            // Result was already set by the caller (OTA task or periodic check).
            // Broadcast update_status to all WS clients so portal refreshes.
            {
                JsonDocument updDoc;
                updDoc["type"] = "update_status";
                _buildUpdateJson(updDoc);
                String updBuf;
                serializeJson(updDoc, updBuf);
                _broadcastText(updBuf);
            }
            continue;  // already broadcast, skip generic broadcast below
        }
        String buf;
        serializeJson(doc, buf);
        _broadcastText(buf);
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

void MundMausServer::_broadcastText(const String& msg) {
    // P1-3: Use makeBuffer + textAll(buffer) instead of textAll(String).
    // The shared_ptr buffer lets each client dequeue independently, and the
    // per-client text(buf) path acquires the client's own lock. This mitigates
    // the _clients list-iteration race: while the iteration itself is not
    // library-locked, the window is microseconds (small message, 10Hz rate)
    // and _clients mutations (connect/disconnect) are seconds apart.
    auto buf = _ws.makeBuffer(msg.length());
    if (buf) {
        memcpy(buf->get(), msg.c_str(), msg.length());
        _ws.textAll(buf);
    }
}

int MundMausServer::_applyConfigValues(JsonObjectConst values) {
    int applied = 0;
    for (JsonPairConst kv : values) {
        const char* key = kv.key().c_str();
        if (key == nullptr || strlen(key) == 0) {
            continue;
        }
        if (!kv.value().is<int>() && !kv.value().is<float>()) {
            continue;
        }
        if (Config::update(key, (int)kv.value().as<float>())) {
            applied++;
        }
    }
    return applied;
}

// ============================================================
// OTA JSON BUILDER
// ============================================================

void MundMausServer::_buildUpdateJson(JsonDocument& doc) {
    // P1-2: Hold the mutex during the entire iteration. This runs on the
    // AsyncTCP task (Core 0) whenever a client queries /api/updates or we
    // broadcast an update_status message, and concurrently the periodic
    // check task (Core 1) may rewrite _updateResult via setUpdateResult().
    // Without this lock std::vector::iterator can observe moved-from state.
    if (_updateResultMutex && xSemaphoreTake(_updateResultMutex, pdMS_TO_TICKS(100)) == pdTRUE) {
        doc["offline"] = _updateResult.offline;
        JsonArray arr = doc["available"].to<JsonArray>();
        for (const auto& uf : _updateResult.available) {
            // Skip .py firmware entries (MicroPython-only), but show .bin firmware updates
            if (uf.firmware && !uf.name.endsWith(".bin")) continue;
            JsonObject obj = arr.add<JsonObject>();
            obj["file"]     = uf.name;
            obj["from_ver"] = uf.localVer;
            obj["to_ver"]   = uf.remoteVer;
            if (uf.deleteFile) {
                obj["delete"] = true;
            }
        }
        xSemaphoreGive(_updateResultMutex);
    } else {
        // Mutex timeout — report offline rather than exposing stale state
        doc["offline"] = true;
        doc["available"].to<JsonArray>();
    }
}

// ============================================================
// OTA UPDATE TASK (I5: one-shot FreeRTOS task for blocking downloads)
// ============================================================

void MundMausServer::_updateTaskWrapper(void* param) {
    MundMausServer* self = static_cast<MundMausServer*>(param);
    QueueHandle_t q = self->_sensorQueue;

    // P1-2: Copy the update list into a local vector under the mutex, then
    // release. Downloads take tens of seconds and must not hold the mutex —
    // AsyncTCP handlers would stall waiting for _buildUpdateJson otherwise.
    std::vector<Updater::UpdateFile> availableCopy;
    if (self->_updateResultMutex &&
        xSemaphoreTake(self->_updateResultMutex, pdMS_TO_TICKS(100)) == pdTRUE) {
        availableCopy = self->_updateResult.available;
        xSemaphoreGive(self->_updateResultMutex);
    }

    // Install game files first
    bool ok = Updater::installGameUpdates(availableCopy,
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
    for (const auto& uf : availableCopy) {
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

    if (!needsReboot) {
        Updater::CheckResult refreshed = Updater::checkManifest();
        if (!refreshed.offline) {
            self->setUpdateResult(refreshed);
        } else if (ok) {
            Updater::CheckResult resolved;
            resolved.offline = false;
            self->setUpdateResult(resolved);
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

    self->_updateRunning = false;

    // Delete this one-shot task
    vTaskDelete(nullptr);
}

// ============================================================
// WIFI SCAN TASK (P1-4: off-thread blocking scan)
// ============================================================

void MundMausServer::_startAsyncScan() {
    // Atomic test-and-set: prevents TOCTOU race where two rapid requests
    // could both pass the check and spawn duplicate scan tasks.
    bool expected = false;
    if (!_wifiScanRunning.compare_exchange_strong(expected, true)) {
        return; // scan already running
    }
    // 4KB stack is enough for scanNetworks + a small JSON serialize.
    xTaskCreate(_wifiScanTaskWrapper, "wifi_scan", 4096, this, 1, nullptr);
}

void MundMausServer::_wifiScanTaskWrapper(void* param) {
    MundMausServer* self = static_cast<MundMausServer*>(param);

    // Blocking call happens on this worker task, NOT on AsyncTCP.
    std::vector<String> networks = self->_wifi.scanNetworks();

    // Broadcast result as WS message so the portal updates regardless of
    // which transport (HTTP or WS) triggered the scan.
    JsonDocument resp;
    resp["type"] = "wifi_networks";
    JsonArray arr = resp["networks"].to<JsonArray>();
    for (const auto& n : networks) {
        arr.add(n);
    }
    String buf;
    serializeJson(resp, buf);
    self->_broadcastText(buf);

    self->_wifiScanRunning = false;
    vTaskDelete(nullptr);
}
