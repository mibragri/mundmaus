#!/usr/bin/env bash
# test-esp32.sh — Upload to ESP32, verify boot, run Playwright browser tests
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
PROJECT_DIR="$(dirname "$SCRIPT_DIR")"
PORT="${ESP32_PORT:-/dev/ttyUSB0}"
BOOT_TIMEOUT=30

RED='\033[0;31m'; GREEN='\033[0;32m'; YELLOW='\033[1;33m'; NC='\033[0m'

echo -e "${YELLOW}=== MundMaus ESP32 Test ===${NC}"

# --- Pre-check: mpy-cross syntax validation ---
echo -e "\n${YELLOW}--- Syntax check (mpy-cross) ---${NC}"
FAIL=0
for f in "$PROJECT_DIR"/*.py; do
    fname="$(basename "$f")"
    if mpy-cross "$f" -o /dev/null 2>/dev/null; then
        echo -e "  ${GREEN}OK${NC}  $fname"
    else
        echo -e "  ${RED}FAIL${NC}  $fname"
        FAIL=1
    fi
done
if [[ $FAIL -eq 1 ]]; then
    echo -e "${RED}Syntax errors found. Aborting.${NC}"
    exit 1
fi

# --- Check ESP32 connected ---
if [[ ! -e "$PORT" ]]; then
    echo -e "${RED}ESP32 not found at $PORT. Set ESP32_PORT if different.${NC}"
    exit 1
fi
echo -e "  ESP32 at $PORT"

# --- Upload files ---
echo -e "\n${YELLOW}--- Uploading firmware ---${NC}"
for f in boot.py main.py config.py wifi_manager.py sensors.py server.py display.py updater.py; do
    if [[ -f "$PROJECT_DIR/$f" ]]; then
        mpremote connect "$PORT" cp "$PROJECT_DIR/$f" ":$f"
        echo "  $f"
    fi
done

echo -e "\n${YELLOW}--- Uploading games ---${NC}"
mpremote connect "$PORT" mkdir :www 2>/dev/null || true
for f in "$PROJECT_DIR"/games/*.html; do
    fname="$(basename "$f")"
    mpremote connect "$PORT" cp "$f" ":www/$fname"
    echo "  www/$fname"
done

# --- Reboot and monitor serial ---
echo -e "\n${YELLOW}--- Rebooting + monitoring serial ---${NC}"
SERIAL_LOG=$(mktemp)
trap 'rm -f '"$SERIAL_LOG" EXIT

mpremote connect "$PORT" exec "import machine; machine.reset()" 2>/dev/null || true
sleep 1

timeout "$BOOT_TIMEOUT" bash -c "
    stty -F '$PORT' 115200 raw -echo 2>/dev/null && cat '$PORT'
" > "$SERIAL_LOG" 2>&1 &
SERIAL_PID=$!

WAITED=0
while [[ $WAITED -lt $BOOT_TIMEOUT ]]; do
    if grep -q "Bereit." "$SERIAL_LOG" 2>/dev/null; then
        break
    fi
    sleep 1
    WAITED=$((WAITED + 1))
done

kill $SERIAL_PID 2>/dev/null || true

if grep -q "Bereit." "$SERIAL_LOG"; then
    echo -e "  ${GREEN}Boot OK${NC}"
else
    echo -e "  ${RED}Boot failed (timeout ${BOOT_TIMEOUT}s)${NC}"
    echo "  Serial output:"
    cat "$SERIAL_LOG"
    exit 1
fi

if grep -qi "Traceback\|Error\|Exception" "$SERIAL_LOG"; then
    echo -e "  ${YELLOW}WARNING: Errors in serial output:${NC}"
    grep -i "Traceback\|Error\|Exception" "$SERIAL_LOG"
fi

ESP_IP=$(grep -oP 'IP: \K[0-9.]+' "$SERIAL_LOG" | tail -1)
if [[ -z "$ESP_IP" ]]; then
    echo -e "  ${RED}Could not extract IP from serial${NC}"
    cat "$SERIAL_LOG"
    exit 1
fi
echo -e "  IP: $ESP_IP"

echo -e "\n${GREEN}=== All ESP32 tests passed ===${NC}"
