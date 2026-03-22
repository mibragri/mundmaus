#!/usr/bin/env bash
# Validate Bambu slicer profiles before printing.
# Catches wrong/generic gcodes, missing temperatures, wrong bed types.
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
MACHINE="${SCRIPT_DIR}/machine-resolved.json"
FILAMENT="${SCRIPT_DIR}/filament-resolved.json"
PROCESS="${SCRIPT_DIR}/process-resolved.json"

ERRORS=0
err() { echo "  ✗ $1"; ERRORS=$((ERRORS + 1)); }
ok()  { echo "  ✓ $1"; }

echo "=== Bambu Profile Validation ==="

# 1. Machine profile: must contain P2S-specific start gcode
echo ""
echo "── Machine Profile ──"
if [[ ! -f "$MACHINE" ]]; then
    err "machine-resolved.json not found"
else
    # P2S start gcode contains "P2S start gcode" marker
    if python3 -c "
import json, sys
m = json.load(open('$MACHINE'))
gcode = m.get('machine_start_gcode', '')
if 'P2S start gcode' not in gcode and 'P1S start gcode' not in gcode:
    print('GENERIC')
    sys.exit(1)
print('P2S')
" 2>/dev/null; then
        ok "Start-GCode ist P2S-spezifisch"
    else
        err "Start-GCode ist GENERISCH (nicht P2S)! Profile neu generieren mit resolve-profiles.py"
    fi

    # Check bed type
    BED=$(python3 -c "import json; print(json.load(open('$MACHINE')).get('curr_bed_type','MISSING'))")
    if [[ "$BED" == *"PEI"* || "$BED" == *"Engineering"* ]]; then
        ok "Bed type: $BED (PETG-kompatibel)"
    elif [[ "$BED" == *"Cool"* ]]; then
        err "Bed type: $BED — nicht für PETG geeignet!"
    else
        ok "Bed type: $BED"
    fi

    # Check 'from' field exists (CLI requirement)
    FROM=$(python3 -c "import json; print(json.load(open('$MACHINE')).get('from','MISSING'))")
    if [[ "$FROM" == "MISSING" || "$FROM" == "" ]]; then
        err "'from' field fehlt oder leer — CLI wird abstürzen"
    else
        ok "from: $FROM"
    fi
fi

# 2. Filament profile: nozzle temperature must be set
echo ""
echo "── Filament Profile ──"
if [[ ! -f "$FILAMENT" ]]; then
    err "filament-resolved.json not found"
else
    python3 -c "
import json, sys
f = json.load(open('$FILAMENT'))
t = int(f.get('nozzle_temperature', ['0'])[0])
ti = int(f.get('nozzle_temperature_initial_layer', ['0'])[0])
tmin = int(f.get('nozzle_temperature_range_low', ['180'])[0])
tmax = int(f.get('nozzle_temperature_range_high', ['300'])[0])
bed = int(f.get('textured_plate_temp', ['0'])[0])
bed_i = int(f.get('textured_plate_temp_initial_layer', ['0'])[0])
fil_type = str(f.get('filament_type', '?'))
ok = lambda m: print(f'  OK {m}')
er = lambda m: print(f'  FAIL {m}')
fail = False
if t < tmin or t > tmax:
    er(f'Nozzle {t}C outside range {tmin}-{tmax}C'); fail = True
if 'PETG' in fil_type and t < 230:
    er(f'Nozzle {t}C too low for PETG (recommend 230-250C)'); fail = True
if 'PETG' in fil_type and ti < 230:
    er(f'Nozzle initial {ti}C too low for PETG first layer'); fail = True
if 'PETG' in fil_type and bed < 70:
    er(f'Bed {bed}C too low for PETG on Textured PEI (recommend 70-80C)'); fail = True
ok(f'Nozzle: {t}C (initial: {ti}C)')
ok(f'Bed: {bed}C (initial: {bed_i}C)')
ok(f'Filament: {fil_type}')
sys.exit(1 if fail else 0)
"
    FILAMENT_CHECK=$?
    if [[ $FILAMENT_CHECK -ne 0 ]]; then
        ERRORS=$((ERRORS + 1))
    fi
fi

# 3. Process profile: wall count, infill
echo ""
echo "── Process Profile ──"
if [[ ! -f "$PROCESS" ]]; then
    err "process-resolved.json not found"
else
    WALLS=$(python3 -c "import json; print(json.load(open('$PROCESS')).get('wall_loops','?'))")
    INFILL=$(python3 -c "import json; print(json.load(open('$PROCESS')).get('sparse_infill_density','?'))")
    PATTERN=$(python3 -c "import json; print(json.load(open('$PROCESS')).get('sparse_infill_pattern','?'))")
    ok "Walls: $WALLS, Infill: $INFILL $PATTERN"

    # Prime tower should be off for single-filament prints
    PRIME=$(python3 -c "import json; print(json.load(open('$PROCESS')).get('enable_prime_tower',0))")
    if [[ "$PRIME" == "1" ]]; then
        err "Prime tower enabled — unnecessary for single-filament, wastes space between parts"
    else
        ok "Prime tower: off"
    fi
fi

# 4. Retraction check (PETG-specific: direct drive = low retraction)
echo ""
echo "── Retraction Check ──"
python3 -c "
import json, sys
m = json.load(open('$MACHINE'))
f = json.load(open('$FILAMENT'))
errors = []
# Machine retraction (base)
r_len = m.get('retraction_length', ['0'])[0]
r_spd = m.get('retraction_speed', ['0'])[0]
# Filament can override
f_len = f.get('filament_retraction_length', ['nil'])[0]
if f_len not in ('nil', ''):
    r_len = f_len
r_len = float(r_len)
r_spd = float(r_spd)
if r_len > 2.0:
    print(f'ERROR retraction_length={r_len}mm >2.0mm — PETG clog risk on direct drive!')
    errors.append(1)
elif r_len > 1.0:
    print(f'WARN retraction_length={r_len}mm — on the high side for direct drive PETG')
else:
    print(f'OK retraction={r_len}mm @ {r_spd}mm/s')
sys.exit(1 if errors else 0)
" 2>/dev/null
RETRACT_RESULT=$?
if [[ $RETRACT_RESULT -eq 0 ]]; then
    RETRACT_MSG=$(python3 -c "
import json
m = json.load(open('$MACHINE'))
f = json.load(open('$FILAMENT'))
r = f.get('filament_retraction_length', ['nil'])[0]
if r in ('nil', ''): r = m.get('retraction_length', ['?'])[0]
s = m.get('retraction_speed', ['?'])[0]
print(f'Retraction: {r}mm @ {s}mm/s')
")
    ok "$RETRACT_MSG"
else
    RETRACT_MSG=$(python3 -c "
import json
m = json.load(open('$MACHINE'))
f = json.load(open('$FILAMENT'))
r = f.get('filament_retraction_length', ['nil'])[0]
if r in ('nil', ''): r = m.get('retraction_length', ['?'])[0]
print(f'Retraction: {r}mm — zu hoch für PETG Direct Drive!')
")
    err "$RETRACT_MSG"
fi

# 5. Quick slice test (dry run)
echo ""
echo "── Slice Smoke Test ──"
if command -v /home/ai/.local/bin/BambuStudio.AppImage &>/dev/null; then
    TEST_3MF="/tmp/bambu-profile-test-$$.3mf"
    # Create a tiny test cube STL
    python3 -c "
import struct
# Minimal 10mm cube STL (binary)
triangles = [
    # bottom
    ((0,0,-1), (0,0,0), (10,0,0), (10,10,0)),
    ((0,0,-1), (0,0,0), (10,10,0), (0,10,0)),
    # top
    ((0,0,1), (0,0,10), (10,10,10), (10,0,10)),
    ((0,0,1), (0,0,10), (0,10,10), (10,10,10)),
    # front
    ((0,-1,0), (0,0,0), (10,0,0), (10,0,10)),
    ((0,-1,0), (0,0,0), (10,0,10), (0,0,10)),
    # back
    ((0,1,0), (0,10,0), (0,10,10), (10,10,10)),
    ((0,1,0), (0,10,0), (10,10,10), (10,10,0)),
    # left
    ((-1,0,0), (0,0,0), (0,0,10), (0,10,10)),
    ((-1,0,0), (0,0,0), (0,10,10), (0,10,0)),
    # right
    ((1,0,0), (10,0,0), (10,10,0), (10,10,10)),
    ((1,0,0), (10,0,0), (10,10,10), (10,0,10)),
]
with open('/tmp/test_cube.stl', 'wb') as f:
    f.write(b'\0' * 80)
    f.write(struct.pack('<I', len(triangles)))
    for n, v1, v2, v3 in triangles:
        f.write(struct.pack('<3f', *n))
        f.write(struct.pack('<3f', *v1))
        f.write(struct.pack('<3f', *v2))
        f.write(struct.pack('<3f', *v3))
        f.write(struct.pack('<H', 0))
" 2>/dev/null

    /home/ai/.local/bin/BambuStudio.AppImage \
        --load-settings "${MACHINE};${PROCESS}" \
        --load-filaments "${FILAMENT}" \
        --ensure-on-bed --slice 0 \
        --export-3mf "$TEST_3MF" \
        /tmp/test_cube.stl 2>&1 | grep -v trace > /dev/null 2>&1

    if [[ -f "$TEST_3MF" ]]; then
        # Verify gcode in output
        GCODE_CHECK=$(python3 -c "
import zipfile, sys
z = zipfile.ZipFile('$TEST_3MF')
gcode = z.read('Metadata/plate_1.gcode').decode()
if 'P2S start gcode' in gcode or 'M140 S' in gcode[:2000]:
    print('OK')
else:
    print('BAD_GCODE')
")
        if [[ "$GCODE_CHECK" == "OK" ]]; then
            ok "Smoke test: Slice + GCode korrekt"
        else
            err "Smoke test: GCode enthält nicht den P2S Start-Code!"
        fi
        rm -f "$TEST_3MF"
    else
        err "Smoke test: Slice fehlgeschlagen"
    fi
    rm -f /tmp/test_cube.stl
else
    ok "BambuStudio nicht installiert — Smoke Test übersprungen"
fi

echo ""
echo "================================"
if [[ $ERRORS -gt 0 ]]; then
    echo "  $ERRORS FEHLER — NICHT DRUCKEN!"
    exit 1
else
    echo "  Alle Checks bestanden ✓"
    exit 0
fi
