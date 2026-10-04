// Host tests for the REAL src/updater.cpp, compiled unchanged by run.sh against stubs/ and fakes.cpp.
// The build sets MUNDMAUS_FW_VERSION=4214, so in every test the running image is 4214.
#include <Arduino.h>
#include "config.h"
#include "updater.h"
#include "fakes.h"

static const std::string MANIFEST_URL = std::string(Config::OTA_BASE_URL) + "/manifest.json";

static void serveManifest(int fw) {
  g_http[MANIFEST_URL] = {200, R"({"files":{"www/chess.html.gz":{"version":3},"www/memo.html.gz":{"version":2},)"
                                R"("firmware.bin":{"version":)" + std::to_string(fw) + R"(,"firmware":true}}})"};
}
static void nvsKnowsVersions(int fw) {
  g_nvs["ota_ver"]["schema_version"] = "1";
  g_nvs["ota_ver"]["json"] = R"({"www/chess.html.gz":3,"www/memo.html.gz":2,"firmware.bin":)" + std::to_string(fw) + "}";
}
static const Updater::UpdateFile* offered(const Updater::CheckResult& r, const char* name) {
  for (const auto& f : r.available) if (f.name == name) return &f;
  return nullptr;
}

// Boots the device n times; before each boot the previous reset had reason `why`.
// Returns the boot number that rolled back to the other partition, or 0.
static int bootLoop(int n, esp_reset_reason_t why, bool ranPast60s = false) {
  for (int boot = 1; boot <= n; ++boot) {
    g_resetReason = (boot == 1) ? ESP_RST_POWERON : why;
    try {
      Updater::checkBootCrashLoop();
    } catch (const Restart&) {
      return boot;
    }
    if (ranPast60s) Updater::bootCrashCounterReset();
  }
  return 0;
}
static void twoValidImages() { g_running = &g_ota1; g_state[&g_ota0] = ESP_OTA_IMG_VALID; g_state[&g_ota1] = ESP_OTA_IMG_VALID; }

// --- A1: a reformatted LittleFS must get its game files back ------------------------------
static void a1() {
  std::printf("A1 LittleFS formatiert, NVS kennt die Versionen noch\n");
  resetFakes(); serveManifest(4214); nvsKnowsVersions(4214);  // LittleFS empty
  auto r = Updater::checkManifest("");
  const auto* chess = offered(r, "www/chess.html.gz");
  CHECK(chess && offered(r, "www/memo.html.gz"), "fehlende Spieldateien werden wieder angeboten");
  CHECK(chess && chess->localVer == 0, "eine fehlende Datei gilt als Version 0");

  resetFakes(); serveManifest(4214); nvsKnowsVersions(4214);
  g_files = {"/www/memo.html.gz"};
  r = Updater::checkManifest("");
  CHECK(offered(r, "www/chess.html.gz") && !offered(r, "www/memo.html.gz"), "eine einzeln verlorene Datei wird angeboten, die vorhandene nicht");

  resetFakes(); serveManifest(4214); nvsKnowsVersions(4214);
  g_files = {"/www/chess.html.gz", "/www/memo.html.gz"};
  CHECK(Updater::checkManifest("").available.empty(), "Kontrolle: Normalbetrieb bietet nichts an");

  resetFakes(); serveManifest(4214);  // fresh flash: NVS empty, files present
  g_files = {"/www/chess.html.gz", "/www/memo.html.gz"};
  CHECK(Updater::checkManifest("").available.empty(), "Kontrolle: frisch geflasht, Dateien da -> nichts angeboten");
}

// --- A2: only crashes may count toward the boot-loop rollback ------------------------------
static void a2BootLoop() {
  std::printf("A2 Boot-Crash-Waechter\n");
  resetFakes(); twoValidImages();
  CHECK(bootLoop(8, ESP_RST_BROWNOUT) == 0, "Brownout-Schleife fuehrt nicht zum Rueckfall");
  resetFakes(); twoValidImages();
  CHECK(bootLoop(8, ESP_RST_POWERON) == 0, "schnelles Aus- und Einschalten fuehrt nicht zum Rueckfall");
  resetFakes(); twoValidImages();
  CHECK(bootLoop(8, ESP_RST_SW) == 0, "gewollte Neustarts fuehren nicht zum Rueckfall");
  resetFakes(); twoValidImages();
  int rb = bootLoop(8, ESP_RST_PANIC);
  CHECK(rb > 0 && g_bootSet == &g_ota0, "Kontrolle: Absturz-Schleife faellt auf das gute Image zurueck");
  CHECK(rb == 6, "Kontrolle: Rueckfall beim Boot nach dem fuenften Absturz");
  resetFakes(); twoValidImages();
  CHECK(bootLoop(8, ESP_RST_TASK_WDT) == 6, "Kontrolle: Task-Watchdog-Schleife faellt ebenfalls zurueck");
  resetFakes(); twoValidImages();
  CHECK(bootLoop(8, ESP_RST_PANIC, /*ranPast60s=*/true) == 0, "Kontrolle: Abstuerze nach jeweils ueber 60 s sind keine Schleife");
  resetFakes(); twoValidImages();
  // Crash loop interrupted by brownouts: brownouts neither count nor clear the crash count.
  int boot = 0; bool rolled = false;
  esp_reset_reason_t seq[] = {ESP_RST_POWERON, ESP_RST_PANIC, ESP_RST_BROWNOUT, ESP_RST_PANIC, ESP_RST_PANIC,
                              ESP_RST_BROWNOUT, ESP_RST_PANIC, ESP_RST_PANIC};
  for (auto why : seq) {
    ++boot; g_resetReason = why;
    try { Updater::checkBootCrashLoop(); } catch (const Restart&) { rolled = true; break; }
  }
  CHECK(rolled && boot == 8, "Kontrolle: fuenf Abstuerze mit Brownouts dazwischen fallen trotzdem zurueck");
}

// --- A2: after a rollback the lost firmware must be offered again ---------------------------
static void a2Version() {
  std::printf("A2 Versionsabgleich nach einem Rueckfall (laufendes Image 4214)\n");
  resetFakes(); serveManifest(4215); nvsKnowsVersions(4215);  // NVS still claims the lost 4215
  g_files = {"/www/chess.html.gz", "/www/memo.html.gz"};
  const auto r = Updater::checkManifest("");
  const auto* fw = offered(r, "firmware.bin");
  CHECK(fw != nullptr, "die verlorene 4215 wird wieder angeboten");
  CHECK(fw && fw->localVer == 4214, "installiert gilt die tatsaechlich laufende 4214");

  resetFakes(); serveManifest(4214); nvsKnowsVersions(4213);
  g_files = {"/www/chess.html.gz", "/www/memo.html.gz"};
  CHECK(Updater::checkManifest("").available.empty(), "Kontrolle: veraltetes NVS nach USB-Flash -> kein Update auf sich selbst");

  resetFakes(); serveManifest(4213); nvsKnowsVersions(4214);
  g_files = {"/www/chess.html.gz", "/www/memo.html.gz"};
  CHECK(Updater::checkManifest("").available.empty(), "Kontrolle: aeltere Firmware auf dem Server wird nicht angeboten");
}

int main() {
  a1();
  a2BootLoop();
  a2Version();
  std::printf("%s: %d Fehler\n", failures() ? "ROT" : "GRUEN", failures());
  return failures() ? 1 : 0;
}
