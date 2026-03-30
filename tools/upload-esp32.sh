#!/usr/bin/env bash
# upload-esp32.sh — Upload files to ESP32 + auto-reboot
# Usage: tools/upload-esp32.sh [files...]
# Without args: uploads all firmware + games
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
PROJECT_DIR="$(dirname "$SCRIPT_DIR")"
PORT="${ESP32_PORT:-/dev/ttyUSB0}"

# Reset ESP32 first (stop running server so mpremote can connect)
python3 -c "
import serial, time
s = serial.Serial('$PORT', 115200, timeout=1)
s.dtr = False; time.sleep(0.1); s.dtr = True; time.sleep(2)
s.close()
" 2>/dev/null

if [[ $# -gt 0 ]]; then
    # Upload specific files
    for f in "$@"; do
        if [[ "$f" == *.mpy ]]; then
            mpremote connect "$PORT" cp "$f" ":$(basename "$f")"
        elif [[ "$f" == games/* || "$f" == www/* ]]; then
            fname="$(basename "$f")"
            mpremote connect "$PORT" cp "$f" ":www/$fname"
        else
            mpremote connect "$PORT" cp "$f" ":$(basename "$f")"
        fi
        echo "  $(basename "$f")"
    done
else
    # Upload all: firmware (.mpy + main.py + boot.py) + games
    for f in boot.py main.py; do
        [[ -f "$PROJECT_DIR/$f" ]] && mpremote connect "$PORT" cp "$PROJECT_DIR/$f" ":$f" && echo "  $f"
    done
    for f in "$PROJECT_DIR"/*.mpy; do
        [[ -f "$f" ]] && mpremote connect "$PORT" cp "$f" ":$(basename "$f")" && echo "  $(basename "$f")"
    done
    for f in "$PROJECT_DIR"/games/*.html; do
        fname="$(basename "$f")"
        mpremote connect "$PORT" cp "$f" ":www/$fname" && echo "  www/$fname"
    done
fi

# Auto-reboot
echo "  Rebooting..."
python3 -c "
import serial, time
s = serial.Serial('$PORT', 115200, timeout=1)
s.dtr = False; time.sleep(0.1); s.dtr = True
time.sleep(0.5); s.reset_input_buffer()
start = time.time()
while time.time() - start < 50:
    data = s.read(512).decode('utf-8', 'ignore')
    if data: print(data, end='', flush=True)
    if 'Bereit.' in data: break
s.close()
"
