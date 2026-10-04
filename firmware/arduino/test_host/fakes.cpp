// Backing stores for the host stubs: NVS, LittleFS, HTTP, OTA partitions and the reset reason.
// Nothing here touches a device or the network.
#include <Arduino.h>
#include <Preferences.h>
#include <LittleFS.h>
#include <HTTPClient.h>
#include <Update.h>
#include <esp_ota_ops.h>
#include <map>
#include <set>
#include <string>
#include "fakes.h"

std::map<std::string, std::map<std::string, std::string>> g_nvs;
bool g_nvsWritesFail = false;
std::set<std::string> g_files;
std::map<std::string, std::pair<int, std::string>> g_http;
FakeSerial Serial; FakeESP ESP; FakeFS LittleFS; UpdateClass Update;

static unsigned long g_ms = 0;
unsigned long millis() { return g_ms; }
void delay(unsigned long ms) { g_ms += ms; }

esp_partition_t g_ota0{0x10, "app0"}, g_ota1{0x11, "app1"};
const esp_partition_t* g_running = &g_ota1;
std::map<const esp_partition_t*, esp_ota_img_states_t> g_state;
const esp_partition_t* g_bootSet = nullptr;
esp_reset_reason_t g_resetReason = ESP_RST_POWERON;

const esp_partition_t* esp_ota_get_running_partition() { return g_running; }
const esp_partition_t* esp_ota_get_next_update_partition(const esp_partition_t*) { return g_running == &g_ota0 ? &g_ota1 : &g_ota0; }
esp_err_t esp_ota_get_state_partition(const esp_partition_t* p, esp_ota_img_states_t* s) { *s = g_state[p]; return ESP_OK; }
esp_err_t esp_ota_set_boot_partition(const esp_partition_t* p) { g_bootSet = p; return ESP_OK; }
esp_err_t esp_ota_mark_app_valid_cancel_rollback() { return ESP_OK; }
esp_reset_reason_t esp_reset_reason() { return g_resetReason; }
void esp_restart() { throw Restart{}; }

void resetFakes() {
  g_nvs.clear(); g_nvsWritesFail = false; g_files.clear(); g_http.clear();
  g_running = &g_ota1; g_state.clear(); g_bootSet = nullptr; g_resetReason = ESP_RST_POWERON;
}

// newlib provides itoa/utoa on the ESP32; glibc does not. Delegate to the core's stdlib_noniso.
extern "C" char* ltoa(long, char*, int);
extern "C" char* ultoa(unsigned long, char*, int);
extern "C" char* itoa(int v, char* s, int r) { return ltoa(v, s, r); }
extern "C" char* utoa(unsigned int v, char* s, int r) { return ultoa(v, s, r); }
