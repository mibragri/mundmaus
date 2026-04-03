#!/usr/bin/env bash
# check-games.sh — Verify every game has screenshot, README entry, and website card
# Run before committing new games. Exit 1 on missing items.
set -euo pipefail

PROJECT_DIR="$(cd "$(dirname "$0")/.." && pwd)"
ERRORS=0

# Name mapping: filename -> display name (for README table + website <h3>)
# Also: filename -> website image name (when different from filename)
declare -A DISPLAY_NAMES=(
    [chess]="Schach"
    [memo]="Memo|Memory"
    [solitaire]="Solitaire"
    [freecell]="Freecell"
    [vier-gewinnt]="Vier Gewinnt"
)
declare -A IMG_NAMES=(
    [memo]="memory"
)

# Games = all .html files in games/ except settings.html
GAMES=()
for f in "$PROJECT_DIR"/games/*.html; do
    base="$(basename "$f" .html)"
    [[ "$base" == "settings" ]] && continue
    GAMES+=("$base")
done

echo "Found ${#GAMES[@]} games: ${GAMES[*]}"
echo ""

for game in "${GAMES[@]}"; do
    display="${DISPLAY_NAMES[$game]:-$game}"
    img="${IMG_NAMES[$game]:-$game}"
    echo "--- $game ($display) ---"

    # 1. Screenshot exists
    if [[ -f "$PROJECT_DIR/screenshots/$game.png" ]]; then
        echo "  screenshot: OK"
    else
        echo "  screenshot: MISSING (screenshots/$game.png)"
        ERRORS=$((ERRORS + 1))
    fi

    # 2. README mentions screenshot
    if grep -q "screenshots/$game.png" "$PROJECT_DIR/README.md"; then
        echo "  README screenshot: OK"
    else
        echo "  README screenshot: MISSING (no screenshots/$game.png reference)"
        ERRORS=$((ERRORS + 1))
    fi

    # 3. README games table has entry (match any alias in display name)
    readme_ok=false
    IFS='|' read -ra aliases <<< "$display"
    for alias in "${aliases[@]}"; do
        grep -qi "| \*\*${alias}\*\*" "$PROJECT_DIR/README.md" && readme_ok=true
    done
    if $readme_ok; then
        echo "  README table: OK"
    else
        echo "  README table: MISSING (no '| **${display}**' row)"
        ERRORS=$((ERRORS + 1))
    fi

    # 4. Website has game card (match any alias in <h3>)
    website_ok=false
    for alias in "${aliases[@]}"; do
        grep -qi "<h3>${alias}</h3>" "$PROJECT_DIR/website/index.html" && website_ok=true
    done
    if $website_ok; then
        echo "  website card: OK"
    else
        echo "  website card: MISSING (no <h3>${display}</h3>)"
        ERRORS=$((ERRORS + 1))
    fi

    # 5. Website has image reference
    if grep -q "img/${img}.jpg" "$PROJECT_DIR/website/index.html"; then
        echo "  website image ref: OK"
    else
        echo "  website image ref: MISSING (no img/${img}.jpg in index.html)"
        ERRORS=$((ERRORS + 1))
    fi

    # 6. Website image file exists
    if [[ -f "$PROJECT_DIR/website/img/${img}.jpg" ]]; then
        echo "  website img file: OK"
    else
        echo "  website img file: MISSING (website/img/${img}.jpg)"
        ERRORS=$((ERRORS + 1))
    fi

    # 7. Manifest has game entry
    if grep -q "www/${game}.html.gz" "$PROJECT_DIR/manifest.json"; then
        echo "  manifest: OK"
    else
        echo "  manifest: MISSING (no www/${game}.html.gz in manifest.json)"
        ERRORS=$((ERRORS + 1))
    fi

    # 8. Arduino LittleFS has .gz file
    if [[ -f "$PROJECT_DIR/firmware/arduino/data/www/${game}.html.gz" ]]; then
        echo "  arduino data: OK"
    else
        echo "  arduino data: MISSING (firmware/arduino/data/www/${game}.html.gz)"
        ERRORS=$((ERRORS + 1))
    fi
done

echo ""
if [[ $ERRORS -gt 0 ]]; then
    echo "FAILED: $ERRORS missing items"
    exit 1
else
    echo "ALL OK: every game fully integrated"
fi
