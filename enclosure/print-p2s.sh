#!/usr/bin/env bash
# MundMaus enclosure print — wrapper around generic bambu-print.py
# Uses project-specific profiles (5 walls, 25% gyroid, PETG)
#
# Usage: print-p2s.sh [base|lid|both] [preview|print]

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
BAMBU_PRINT="/home/ai/claude/projects/bambu-p2s/bambu-print.py"
PROFILE_DIR="${SCRIPT_DIR}/bambu-profiles"
OUTPUT_DIR="${SCRIPT_DIR}/output"
AMS_SLOT=4  # Grau PETG

PART="${1:-base}"
ACTION="${2:-preview}"

BASE_STL="${OUTPUT_DIR}/mundmaus_v55_base.stl"
LID_STL="${OUTPUT_DIR}/mundmaus_v55_lid.stl"

case "$PART" in
    base) STL_FILES="$BASE_STL" ;;
    lid)  STL_FILES="$LID_STL" ;;
    both) STL_FILES="$BASE_STL $LID_STL" ;;
    *)    echo "Usage: print-p2s.sh [base|lid|both] [preview|print]"; exit 1 ;;
esac

case "$ACTION" in
    preview)
        echo "=== MundMaus v5.5 — ${PART} Preview ==="
        $BAMBU_PRINT $STL_FILES \
            --slot "$AMS_SLOT" --profile "$PROFILE_DIR" --no-start
        echo ""
        echo "Preview only. Zum Drucken: print-p2s.sh $PART print"
        ;;
    print)
        echo "=== MundMaus v5.5 — ${PART} Drucken ==="
        $BAMBU_PRINT $STL_FILES \
            --slot "$AMS_SLOT" --profile "$PROFILE_DIR"
        ;;
    *)
        echo "Usage: print-p2s.sh [base|lid|both] [preview|print]"; exit 1
        ;;
esac
