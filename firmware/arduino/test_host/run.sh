#!/usr/bin/env bash
# Host tests for the firmware: compiles the REAL src/updater.cpp and src/config.cpp with g++
# against small stubs (NVS, LittleFS, HTTP, OTA, FreeRTOS) and runs them on this machine.
# No device. String handling uses the Arduino core's own WString.cpp, so String behaves as on
# the ESP32. Needs one prior `pio run -e esp32` in firmware/arduino (ArduinoJson in .pio/libdeps).
# Exit code 0 = all tests green.
set -euo pipefail

HERE="$(cd "$(dirname "$0")" && pwd)"
FW="$(dirname "$HERE")"
CORE="${PLATFORMIO_CORE_DIR:-$HOME/.platformio}/packages/framework-arduinoespressif32/cores/esp32"
AJ="$FW/.pio/libdeps/esp32/ArduinoJson/src"
for need in "$CORE/WString.cpp" "$CORE/stdlib_noniso.c" "$AJ/ArduinoJson.h"; do
    if [[ ! -e "$need" ]]; then
        echo "FEHLT: $need -- erst 'pio run -e esp32' in $FW ausfuehren"
        exit 2
    fi
done

OUT="$(mktemp -d)"
trap 'rm -rf "$OUT"' EXIT

# stubs/ comes first so its Arduino.h, Preferences.h ... win over the core's; the core dir only
# supplies WString.h, pgmspace.h and stdlib_noniso.h.
CXXFLAGS=(-std=gnu++17 -O0 -g -Wall -Wno-unused-parameter
    -I"$HERE/stubs" -I"$HERE" -I"$CORE" -I"$FW/include" -I"$AJ"
    -DARDUINO=10812 -DARDUINOJSON_ENABLE_ARDUINO_STREAM=0 -DARDUINOJSON_ENABLE_ARDUINO_PRINT=0
    -DARDUINOJSON_ENABLE_PROGMEM=0 '-DMUNDMAUS_VERSION="4.2.14"' -DMUNDMAUS_FW_VERSION=4214
    '-DOTA_AUTH_B64="dGVzdA=="')

# The core sources include "Arduino.h" with quotes, which looks next to the source file first and
# would find the core's real Arduino.h. Compiled from a copy in $OUT, they get the stub instead.
cp "$CORE/WString.cpp" "$CORE/stdlib_noniso.c" "$OUT/"
gcc -c -I"$HERE/stubs" -I"$CORE" -o "$OUT/stdlib_noniso.o" "$OUT/stdlib_noniso.c"
g++ "${CXXFLAGS[@]}" -w -c -o "$OUT/WString.o" "$OUT/WString.cpp"  # core source: its warnings are not ours
for src in "$HERE/fakes.cpp" "$FW/src/updater.cpp" "$FW/src/config.cpp"; do
    g++ "${CXXFLAGS[@]}" -c -o "$OUT/$(basename "${src%.*}").o" "$src"
done
COMMON=("$OUT/fakes.o" "$OUT/WString.o" "$OUT/stdlib_noniso.o")

# test name -> firmware objects it links against
declare -A UNDER_TEST=([test_updater]="updater.o config.o" [test_config]="config.o")
rc=0
for t in test_updater test_config; do
    echo "=== $t"
    objs=()
    for o in ${UNDER_TEST[$t]}; do objs+=("$OUT/$o"); done
    # A test that does not compile is red too (e.g. it calls an API the fix has yet to add).
    if ! g++ "${CXXFLAGS[@]}" -o "$OUT/$t" "$HERE/$t.cpp" "${objs[@]}" "${COMMON[@]}" 2> "$OUT/$t.err"; then
        echo "ROT: $t kompiliert nicht"
        grep -m3 "error" "$OUT/$t.err" || true
        rc=1
        continue
    fi
    "$OUT/$t" || rc=1
done
exit $rc
