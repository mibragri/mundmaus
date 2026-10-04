// Host tests for the REAL src/config.cpp, compiled unchanged by run.sh against stubs/ and fakes.cpp.
#include <Arduino.h>
#include "config.h"
#include "fakes.h"

// A9: a failed NVS write must reach the caller, so the settings page can show it.
int main() {
  std::printf("A9 Speichern der Einstellungen meldet Fehler\n");
  resetFakes();
  Config::PUFF_RAW_THRESHOLD = Config::PUFF_RAW_THRESHOLD + 1000;  // differs from the default -> gets written
  g_nvsWritesFail = true;
  const bool okWhenFull = Config::save();
  CHECK(!okWhenFull, "NVS-Schreibfehler wird gemeldet");

  g_nvsWritesFail = false;
  CHECK(Config::save(), "Kontrolle: gelungenes Speichern meldet Erfolg");
  CHECK(g_nvs["settings"].size() == 1, "Kontrolle: genau der geaenderte Wert steht im NVS");

  std::printf("%s: %d Fehler\n", failures() ? "ROT" : "GRUEN", failures());
  return failures() ? 1 : 0;
}
