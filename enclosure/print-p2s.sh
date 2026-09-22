#!/usr/bin/env bash
# MundMaus enclosure print — wrapper around generic bambu-print.py
# Uses project-specific profiles (5 walls, 25% gyroid, PETG)
#
# Usage: print-p2s.sh [base|lid|both] [preview|print]

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
BAMBU_PRINT="/home/ai/claude/projects/bambu-p2s/bambu-print.py"
PROFILE_DIR="${SCRIPT_DIR}/bambu-profiles"
AMS_SLOT=4  # Grau PETG

# Die einzige Stelle, an der die Gehaeuse-Version steht. Pfade und Anzeige leiten
# sich davon ab; beim naechsten Versionssprung nur hier aendern.
VERSION="v58"
OUTPUT_DIR="${SCRIPT_DIR}/output_${VERSION}"
GENERATOR="${SCRIPT_DIR}/mundmaus_${VERSION}_enclosure.py"

PART="${1:-base}"
ACTION="${2:-preview}"

BASE_STL="${OUTPUT_DIR}/mundmaus_${VERSION}_base.stl"
LID_STL="${OUTPUT_DIR}/mundmaus_${VERSION}_lid.stl"

case "$PART" in
    base) STL_FILES="$BASE_STL" ;;
    lid)  STL_FILES="$LID_STL" ;;
    both) STL_FILES="$BASE_STL $LID_STL" ;;
    *)    echo "Usage: print-p2s.sh [base|lid|both] [preview|print]"; exit 1 ;;
esac

# Fehlt eine Datei, abbrechen statt auf irgendeine andere auszuweichen.
for f in $STL_FILES; do
    if [ ! -f "$f" ]; then
        echo "FEHLER: ${f} fehlt." >&2
        echo "Erst generieren: /home/ai/.local/share/mamba/envs/cadquery/bin/python ${GENERATOR} --outdir ${OUTPUT_DIR}" >&2
        exit 1
    fi
done
SHOWN="${STL_FILES//"${SCRIPT_DIR}/"/}"

case "$ACTION" in
    preview)
        echo "=== MundMaus ${VERSION} — ${PART} Preview: ${SHOWN} ==="
        $BAMBU_PRINT $STL_FILES \
            --slot "$AMS_SLOT" --profile "$PROFILE_DIR" --no-start
        echo ""
        echo "Preview only. Zum Drucken: print-p2s.sh $PART print"
        ;;
    print)
        echo "=== MundMaus ${VERSION} — ${PART} Drucken: ${SHOWN} ==="
        $BAMBU_PRINT $STL_FILES \
            --slot "$AMS_SLOT" --profile "$PROFILE_DIR"
        ;;
    *)
        echo "Usage: print-p2s.sh [base|lid|both] [preview|print]"; exit 1
        ;;
esac
