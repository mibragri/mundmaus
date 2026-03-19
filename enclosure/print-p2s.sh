#!/usr/bin/env bash
# MundMaus enclosure print — wrapper around generic bambu-print.sh
# Uses project-specific profiles (5 walls, 25% gyroid, PETG)
#
# Usage: print-p2s.sh [base|lid|both]

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
BAMBU_PRINT="/home/ai/claude/tools/bambu-print.sh"
PROFILE_DIR="${SCRIPT_DIR}/bambu-profiles"
OUTPUT_DIR="${SCRIPT_DIR}/output"
AMS_SLOT=4  # Grau PETG

PART="${1:-base}"

case "$PART" in
    base)
        echo "=== MundMaus v5.5 — Base drucken ==="
        "$BAMBU_PRINT" "${OUTPUT_DIR}/mundmaus_v55_base.stl" \
            --slot "$AMS_SLOT" --profile "$PROFILE_DIR"
        ;;
    lid)
        echo "=== MundMaus v5.5 — Lid drucken ==="
        "$BAMBU_PRINT" "${OUTPUT_DIR}/mundmaus_v55_lid.stl" \
            --slot "$AMS_SLOT" --profile "$PROFILE_DIR"
        ;;
    both)
        echo "=== MundMaus v5.5 — Base drucken ==="
        "$BAMBU_PRINT" "${OUTPUT_DIR}/mundmaus_v55_base.stl" \
            --slot "$AMS_SLOT" --profile "$PROFILE_DIR"
        echo ""
        echo "Base-Druck gestartet. Lid wird nach Fertigstellung gedruckt."
        echo "Starte 'print-p2s.sh lid' wenn die Base fertig ist."
        ;;
    *)
        echo "Usage: print-p2s.sh [base|lid|both]"
        exit 1
        ;;
esac
