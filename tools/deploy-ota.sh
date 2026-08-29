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

# --- Firmware provenance ---
# The check above proves firmware.bin EXISTS; it never proved it is the build the
# manifest advertises. manifest.json labels it with MUNDMAUS_FW_VERSION from
# platformio.ini, but nothing in the repo copies the built binary to the root, so
# the root sat on a 2026-05-01 v4.2.12 build while the manifest said 4214. A
# deploy would have published the patient's own current firmware under a new
# version number — and his device records that number after a successful update,
# so it would never fetch the real release again. Existence is not provenance.
if grep -q '"firmware.bin"' "$MANIFEST"; then
    echo -e "\n${YELLOW}--- Firmware provenance ---${NC}"
    FW_BIN="$PROJECT_DIR/firmware.bin"
    FW_BUILT="$PROJECT_DIR/firmware/arduino/.pio/build/esp32/firmware.bin"
    FW_EXPECT="$(sed -n 's/.*-DMUNDMAUS_VERSION=\\"\([0-9.]*\)\\".*/\1/p' \
                 "$PROJECT_DIR/firmware/arduino/platformio.ini")"

    if [[ -z "$FW_EXPECT" ]]; then
        echo -e "${RED}ERROR: cannot read MUNDMAUS_VERSION from platformio.ini${NC}"
        exit 1
    fi
    if [[ ! -f "$FW_BIN" ]]; then
        echo -e "${RED}ERROR: $FW_BIN is missing.${NC}"
        echo    "       Build it and copy it here:"
        echo    "         cd firmware/arduino && pio run -e esp32"
        echo    "         cp '$FW_BUILT' '$FW_BIN'"
        exit 1
    fi
    if ! strings "$FW_BIN" | grep -Fxq "$FW_EXPECT"; then
        FOUND="$(strings "$FW_BIN" | grep -oE '^[0-9]+\.[0-9]+\.[0-9]+$' | sort -u | tr '\n' ' ')"
        echo -e "${RED}ERROR: firmware.bin does not contain version $FW_EXPECT (found: ${FOUND:-none}).${NC}"
        echo    "       It would still be published as v$FW_EXPECT, and the patient's"
        echo    "       device would record that version and never fetch the real one."
        echo    "         cd firmware/arduino && pio run -e esp32"
        echo    "         cp '$FW_BUILT' '$FW_BIN'"
        exit 1
    fi
    echo -e "  ${GREEN}firmware.bin contains v$FW_EXPECT${NC}"
fi

# --- Game quality gates (skip with --skip-test) ---
if [[ "${1:-}" != "--skip-test" ]]; then
    echo -e "\n${YELLOW}--- Static game checks ---${NC}"
    python3 "$SCRIPT_DIR/test-game.py" --all || {
        echo -e "${RED}Static checks failed. Aborting deploy.${NC}"
        exit 1
    }

    # test-game.py reads source text; it opens no browser. CLAUDE.md defines the
    # gate as behavioural (start → play → win → new game → no state leak, undo to
    # empty does not crash), and that suite lives in tests/e2e. Running only the
    # static half meant a game that throws on first click, leaks state across
    # newGame() or strands the cursor deployed cleanly to the patient.
    E2E_DIR="$PROJECT_DIR/tests/e2e"
    if [[ -d "$E2E_DIR/node_modules" ]]; then
        echo -e "\n${YELLOW}--- Behavioural game tests (Playwright) ---${NC}"
        # test:local, not the whole suite: six specs (api, ota-files, portal,
        # resilience, updates, websocket) need a live ESP32 and would make every
        # deploy fail here. Run those separately with ESP32_URL set.
        (cd "$E2E_DIR" && npm run --silent test:local) || {
            echo -e "${RED}Behavioural tests failed. Aborting deploy.${NC}"
            exit 1
        }
    else
        # Fail loudly rather than skipping the behavioural gate in silence.
        echo -e "${RED}ERROR: $E2E_DIR/node_modules missing — the behavioural"
        echo -e "       game tests cannot run. Install them (cd tests/e2e && npm ci)"
        echo -e "       or deploy with --skip-test if you accept static checks only.${NC}"
        exit 1
    fi
fi

# --- Deploy ---
echo -e "\n${YELLOW}--- Deploying to $REMOTE_HOST:$REMOTE_DIR ---${NC}"

ssh "$REMOTE_HOST" "mkdir -p $REMOTE_DIR"

# Files first, manifest last. The manifest used to go up before the files it
# points at, leaving a window as long as a 1.3 MB firmware upload in which a
# device polling for updates saw the new version numbers but downloaded the
# PREVIOUS deploy's content — HTTP 200 with stale bytes, not a 404. updater.cpp
# only withholds the version bump on a failed transfer, so a successful download
# of stale content is recorded as the new version and that content is then
# pinned forever. Publishing the manifest last makes the window harmless: the
# device simply sees the old manifest and tries again later.

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

# Manifest last — it is what makes the new versions visible to devices.
rsync -avz "$MANIFEST" "$REMOTE_HOST:$REMOTE_DIR/manifest.json"

# --- Verify ---
echo -e "\n${YELLOW}--- Verifying ---${NC}"
if curl -sf "https://mundmaus.de/ota/manifest.json" | python3 -c 'import json,sys; m=json.load(sys.stdin); n=len(m["files"]); print(f"  Remote manifest: {n} files")'; then
    echo -e "  ${GREEN}Verify OK${NC}"
else
    echo -e "  ${YELLOW}WARNING: Could not verify HTTPS endpoint${NC}"
fi

echo -e "\n${GREEN}=== OTA Deploy complete ===${NC}"
echo "  URL: https://mundmaus.de/ota/manifest.json"
