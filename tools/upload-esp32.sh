#!/usr/bin/env bash
# upload-esp32.sh — Compile, minify, gzip, upload to ESP32 + auto-reboot
# Usage: tools/upload-esp32.sh [files...]
# Without args: uploads all firmware + games
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
PROJECT_DIR="$(dirname "$SCRIPT_DIR")"
PORT="${ESP32_PORT:-/dev/ttyUSB0}"

# Files that MUST stay as .py on ESP32 (not compiled to .mpy)
PY_ONLY=(boot.py main.py config.py)

# Modules compiled to .mpy before upload
MPY_MODULES=(sensors.py server.py updater.py wifi_manager.py display.py)

cd "$PROJECT_DIR"

# ── Helpers ──────────────────────────────────────────────────

reset_esp32() {
    python3 -c "
import serial, time
s = serial.Serial('$PORT', 115200, timeout=1)
s.dtr = False; time.sleep(0.1); s.dtr = True; time.sleep(2)
s.close()
" 2>/dev/null
}

compile_mpy() {
    local f="$1"
    local out="${f%.py}.mpy"
    mpy-cross "$f" -o "$out" 2>&1
    echo "  compiled: $f → $out"
}

minify_gzip() {
    python3 "$SCRIPT_DIR/minify_gzip.py" "$@"
}

upload() {
    local src="$1" dest="$2"
    mpremote connect "$PORT" cp "$src" ":$dest" 2>&1 | grep -v "^$" || true
    echo "  uploaded: $dest ($(wc -c < "$src" | tr -d ' ')B)"
}

# ── Reset ESP32 ──────────────────────────────────────────────

echo "Resetting ESP32..."
reset_esp32

if [[ $# -gt 0 ]]; then
    # Upload specific files
    for f in "$@"; do
        if [[ "$f" == *.py ]]; then
            base="$(basename "$f")"
            # Check if this should be compiled to .mpy
            is_py_only=false
            for po in "${PY_ONLY[@]}"; do
                [[ "$base" == "$po" ]] && is_py_only=true && break
            done
            if $is_py_only; then
                upload "$f" "$base"
            else
                compile_mpy "$f"
                upload "${f%.py}.mpy" "${base%.py}.mpy"
            fi
        elif [[ "$f" == games/*.html ]]; then
            fname="$(basename "$f")"
            minify_gzip "$f"
            upload "${f}.gz" "www/${fname}.gz"
        else
            upload "$f" "$(basename "$f")"
        fi
    done
else
    # ── Full upload ──────────────────────────────────────────

    echo ""
    echo "=== Compile .mpy ==="
    for f in "${MPY_MODULES[@]}"; do
        [[ -f "$f" ]] && compile_mpy "$f"
    done

    echo ""
    echo "=== Minify + gzip games ==="
    minify_gzip

    echo ""
    echo "=== Upload firmware ==="
    for f in "${PY_ONLY[@]}"; do
        [[ -f "$f" ]] && upload "$f" "$f"
    done
    for f in "${MPY_MODULES[@]}"; do
        local_mpy="${f%.py}.mpy"
        [[ -f "$local_mpy" ]] && upload "$local_mpy" "$local_mpy"
    done

    echo ""
    echo "=== Upload games (.gz) ==="
    for f in games/*.html.gz; do
        [[ -f "$f" ]] && upload "$f" "www/$(basename "$f")"
    done
fi

# ── Reboot + wait for "Bereit." ──────────────────────────────

echo ""
echo "Rebooting..."
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
