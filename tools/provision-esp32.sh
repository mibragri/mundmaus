#!/usr/bin/env bash
# provision-esp32.sh — Flash MicroPython + upload firmware for new ESP32 devices
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
PROJECT_DIR="$(dirname "$SCRIPT_DIR")"
PORT="${ESP32_PORT:-/dev/ttyUSB0}"
FIRMWARE_URL="https://micropython.org/resources/firmware/ESP32_GENERIC-20241129-v1.24.1.bin"
FIRMWARE_BIN="$SCRIPT_DIR/.micropython-firmware.bin"

RED='\033[0;31m'; GREEN='\033[0;32m'; YELLOW='\033[1;33m'; NC='\033[0m'

echo -e "${YELLOW}=== MundMaus ESP32 Provisioning ===${NC}"

for cmd in esptool.py mpremote; do
    if ! command -v "$cmd" &>/dev/null; then
        echo -e "${RED}$cmd not found. Install with: pip install $cmd${NC}"
        exit 1
    fi
done

if [[ ! -e "$PORT" ]]; then
    echo -e "${RED}ESP32 not found at $PORT. Set ESP32_PORT if different.${NC}"
    exit 1
fi

if [[ ! -f "$FIRMWARE_BIN" ]]; then
    echo -e "\n${YELLOW}--- Downloading MicroPython firmware ---${NC}"
    curl -L -o "$FIRMWARE_BIN" "$FIRMWARE_URL"
fi

echo -e "\n${YELLOW}--- Flashing MicroPython ---${NC}"
echo "  Erasing flash..."
esptool.py --chip esp32 --port "$PORT" erase_flash
echo "  Writing firmware..."
esptool.py --chip esp32 --port "$PORT" --baud 460800 \
    write_flash -z 0x1000 "$FIRMWARE_BIN"

echo "  Waiting for reboot..."
sleep 3

echo -e "\n${YELLOW}--- Uploading MundMaus firmware ---${NC}"
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

echo -e "\n${YELLOW}--- Creating versions.json ---${NC}"
python3 -c "
import json
m = json.load(open('$PROJECT_DIR/manifest.json'))
versions = {name: info['version'] for name, info in m['files'].items()}
with open('/tmp/mundmaus_versions.json', 'w') as f:
    json.dump(versions, f)
print(f'  {len(versions)} versions')
"
mpremote connect "$PORT" cp /tmp/mundmaus_versions.json :versions.json

echo -e "\n${GREEN}=== Provisioning complete ===${NC}"
echo "  1. Connect to WiFi 'MundMaus' (password: mundmaus1)"
echo "  2. Open http://192.168.4.1"
echo "  3. Configure home WiFi in the portal"
echo "  4. Device will auto-update from mundmaus.de after WiFi setup"
