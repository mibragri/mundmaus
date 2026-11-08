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

# Die einzige Stelle, an der die Gehaeuse-Version steht. Pfade und Anzeige
# leiten sich davon ab.
#
# HIER STEHT, WAS AM GERAET VERBAUT IST — nicht, was der neueste Generator
# ist. Das sind zwei verschiedene Tatsachen, und sie zu verwechseln ist der
# Fehler aus 81e883e, nur andersherum. Ein Unterteil aus einem Stand und ein
# Deckel aus einem anderen passen nicht zwingend zusammen: zwischen v59 und
# v60 liegt die Joystick-Oeffnung im Deckel 2 mm daneben. Diese Zeile aendert
# sich deshalb erst, wenn ein neuer Stand wirklich gedruckt und eingebaut ist,
# und nicht schon, wenn er erzeugt wurde.
VERSION="v59"
OUTPUT_DIR="${SCRIPT_DIR}/output_${VERSION}"
GENERATOR="${SCRIPT_DIR}/mundmaus_${VERSION}_enclosure.py"

# Liegt ein neuerer Generator daneben, sagen statt schweigen. Kein Abbruch:
# einen aelteren Stand nachzudrucken ist der Normalfall, solange er verbaut
# ist. Aber wer hier ein Einzelteil nachdruckt, soll sehen, dass das eine Wahl
# war und keine Automatik.
#
# Verglichen wird mit plain sort, also zeichenweise — dieselbe Ordnung, die
# validate_enclosure.py mit max() benutzt. Absicht: zwei Waechter, die
# verschieden sortieren, widersprechen sich irgendwann, und dann glaubt man
# dem falschen. Beide teilen damit dieselbe Schwaeche: "v510" waere kleiner
# als "v59". Deshalb ging der Sprung nach v59 auf v60 und nicht auf v510.
NEUESTER=$(ls "${SCRIPT_DIR}"/mundmaus_v*_enclosure.py 2>/dev/null \
           | sed 's|.*/mundmaus_||; s|_enclosure\.py$||' | sort | tail -1)
if [ -n "$NEUESTER" ] && [ "$NEUESTER" != "$VERSION" ]; then
    echo "HINWEIS: gedruckt wird ${VERSION}, neuester Generator ist ${NEUESTER}." >&2
    echo "  Das ist Absicht, solange ${VERSION} am Geraet verbaut ist." >&2
    echo "  Teile aus verschiedenen Staenden bitte nicht mischen." >&2
    echo "" >&2
fi

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
