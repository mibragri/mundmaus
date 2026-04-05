#!/usr/bin/env bash
# deploy-ota.sh — Deploy OTA files to mundmaus.de after ESP32 test
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
PROJECT_DIR="$(dirname "$SCRIPT_DIR")"
REMOTE_HOST="mbs"
REMOTE_DIR="/srv/mundmaus/ota"
MANIFEST="$PROJECT_DIR/manifest.json"

RED='\033[0;31m'; GREEN='\033[0;32m'; YELLOW='\033[1;33m'; NC='\033[0m'

echo -e "${YELLOW}=== MundMaus OTA Deploy ===${NC}"

# --- Pre-flight: game completeness check ---
echo -e "\n${YELLOW}--- Game completeness check ---${NC}"
if ! bash "$SCRIPT_DIR/check-games.sh"; then
    echo -e "${RED}Game check failed. Fix missing items before deploying.${NC}"
    exit 1
fi

if [[ ! -f "$MANIFEST" ]]; then
    echo -e "${RED}ERROR: manifest.json not found. Run tools/update_manifest.py first.${NC}"
    exit 1
fi

MANIFEST="$MANIFEST" python3 -c "
import json, os, sys
m = json.load(open(os.environ['MANIFEST']))
assert 'files' in m, 'No files in manifest'
assert len(m['files']) > 0, 'Empty manifest'
print(f\"  Manifest OK: {len(m['files'])} files\")
for name, info in m['files'].items():
    print(f\"    {name}: v{info['version']}\")
"

MANIFEST="$MANIFEST" PROJECT_DIR="$PROJECT_DIR" python3 -c "
import json, os, sys
from pathlib import Path
m = json.load(open(os.environ['MANIFEST']))
project = Path(os.environ['PROJECT_DIR'])
missing = []
for name in m['files']:
    src = name.replace('www/', 'games/') if name.startswith('www/') else name
    if not (project / src).exists():
        missing.append(f'{name} (source: {src})')
if missing:
    print('Missing files:')
    for f in missing:
        print(f'  {f}')
    sys.exit(1)
print('  All source files present')
"

# --- ESP32 test gate (skip with --skip-test) ---
if [[ "${1:-}" != "--skip-test" ]]; then
    if [[ -f "$SCRIPT_DIR/test-esp32.sh" ]]; then
        echo -e "\n${YELLOW}--- Running ESP32 tests ---${NC}"
        bash "$SCRIPT_DIR/test-esp32.sh" || {
            echo -e "${RED}ESP32 tests failed. Aborting deploy.${NC}"
            exit 1
        }
    else
        echo -e "${YELLOW}  test-esp32.sh not found, skipping hardware test${NC}"
    fi
fi

# --- Deploy ---
echo -e "\n${YELLOW}--- Deploying to $REMOTE_HOST:$REMOTE_DIR ---${NC}"

ssh "$REMOTE_HOST" "mkdir -p $REMOTE_DIR"

rsync -avz "$MANIFEST" "$REMOTE_HOST:$REMOTE_DIR/manifest.json"

MANIFEST="$MANIFEST" python3 -c "
import json, os
m = json.load(open(os.environ['MANIFEST']))
for name in m['files']:
    if not name.startswith('www/'):
        print(name)
" | while read -r fname; do
    rsync -avz "$PROJECT_DIR/$fname" "$REMOTE_HOST:$REMOTE_DIR/$fname"
done

ssh "$REMOTE_HOST" "mkdir -p $REMOTE_DIR/www"
MANIFEST="$MANIFEST" python3 -c "
import json, os
m = json.load(open(os.environ['MANIFEST']))
for name in m['files']:
    if name.startswith('www/'):
        print(name)
" | while read -r fname; do
    src="$PROJECT_DIR/games/$(basename "$fname")"
    rsync -avz "$src" "$REMOTE_HOST:$REMOTE_DIR/$fname"
done

# --- Verify ---
echo -e "\n${YELLOW}--- Verifying ---${NC}"
if curl -sf "https://mundmaus.de/ota/manifest.json" | python3 -c 'import json,sys; m=json.load(sys.stdin); n=len(m["files"]); print(f"  Remote manifest: {n} files")'; then
    echo -e "  ${GREEN}Verify OK${NC}"
else
    echo -e "  ${YELLOW}WARNING: Could not verify HTTPS endpoint${NC}"
fi

echo -e "\n${GREEN}=== OTA Deploy complete ===${NC}"
echo "  URL: https://mundmaus.de/ota/manifest.json"
