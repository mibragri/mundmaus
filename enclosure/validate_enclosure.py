#!/usr/bin/env python3
"""MundMaus v5.8 Enclosure Validator — checks dimensions, clearances, printability.

Complements the generator instead of repeating it: mundmaus_v58_enclosure.py
raises at import on a lip-zone collision, a sensor/ESP32 overlap and a screw
pillar cutting the corner curve, so importing it already runs those checks.
"""

import math
import sys
from pathlib import Path

# ═══════════════════════════════════════════════════════════════════
# REFERENCE DIMENSIONS (from datasheets / research)
# ═══════════════════════════════════════════════════════════════════

SPEC = {
    "ESP32 DevKitC V4 (Espressif)": {
        "pcb_l": (54.4, "mm — Espressif official"),
        "pcb_w": (27.9, "mm — Espressif official (28.0 in code, OK within tolerance)"),
        "pcb_h": (1.2, "mm — standard FR4"),
        "module_h": (3.1, "mm — WROOM-32 module above PCB"),
        "pin_row_spacing": (25.4, "mm — 1.0 inch center-to-center"),
    },
    "KY-023 Joystick (AZDelivery)": {
        "pcb_l": (34.0, "mm"),
        "pcb_w": (26.0, "mm"),
        "hole_grid_x": (26.67, "mm — 1.05 inch"),
        "hole_grid_y": (20.32, "mm — 0.80 inch"),
        "hole_d": (4.2, "mm — M4 clearance"),
        "housing_size": (16.0, "mm — analog stick housing"),
        "stick_h": (17.0, "mm — stick above PCB"),
    },
    "MPS20N0040D-S + HX710B": {
        "board_l": (20.0, "mm — approximate"),
        "board_w": (15.0, "mm — approximate"),
        "board_h": (5.0, "mm — with sensor element"),
        "barb_od": (3.0, "mm — silicone tube barb"),
    },
    "3/8\"-16 UNC (Mic Stand)": {
        "clear_d": (10.5, "mm — through-hole"),
        "nut_sw": (14.29, "mm — across flats"),
        "nut_h": (5.56, "mm"),
    },
}

# ═══════════════════════════════════════════════════════════════════
# IMPORT ENCLOSURE CONSTANTS
# ═══════════════════════════════════════════════════════════════════

# Resolve from this file, not from the CWD: sys.path.insert(0, ".") meant the
# import only worked when run from inside enclosure/.
sys.path.insert(0, str(Path(__file__).resolve().parent))

# The model this validator actually knows how to check.
VALIDATED_MODEL = "mundmaus_v58_enclosure"

# The generator's own guards raise ValueError at import: a finding, not a crash.
try:
    from mundmaus_v58_enclosure import *  # noqa: E402, F403
except ValueError as _e:
    print(f"\n🔴 ERROR: the generator rejects its own geometry: {_e}\n")
    sys.exit(1)

# Validator-only constants go AFTER the import: `import *` silently overwrites any
# same-named value defined before it (it replaced a USB plug width of 11 with the
# model's 12). Model dimensions, the USB plug included, come from the model.
LINE_W, LAYER_H, NOZZLE = 0.42, 0.20, 0.4  # Bambu Lab, 0.4 mm nozzle

# Refuse to pass silently on a superseded model: once a newer generator exists,
# a pass here says nothing about the enclosure that would be printed.
_CURRENT_MODEL = max(
    (p.stem for p in Path(__file__).resolve().parent.glob("mundmaus_v*_enclosure.py")),
    default=VALIDATED_MODEL,
)
_MODEL_IS_CURRENT = (_CURRENT_MODEL == VALIDATED_MODEL)

# ═══════════════════════════════════════════════════════════════════
# VALIDATION
# ═══════════════════════════════════════════════════════════════════

errors = []
warnings = []
info = []


def err(msg):
    errors.append(f"  ✗ {msg}")


def warn(msg):
    warnings.append(f"  ⚠ {msg}")


def ok(msg):
    info.append(f"  ✓ {msg}")


print("=" * 65)
print("  MundMaus v5.8 Enclosure Validation")
print("=" * 65)

# ── 1. Component dimensions vs specs ─────────────────────────────

print("\n── 1. Component Dimensions vs Datasheets ──")

if abs(ESP_L - 54.4) > 0.1:
    err(f"ESP32 length {ESP_L}mm ≠ spec 54.4mm")
else:
    ok(f"ESP32 length: {ESP_L}mm ✓")

if abs(ESP_W - 27.9) > 0.5:
    err(f"ESP32 width {ESP_W}mm too far from spec 27.9mm")
else:
    ok(f"ESP32 width: {ESP_W}mm (spec 27.9, delta {ESP_W-27.9:+.1f}, OK)")

if abs(JOY_PCB_L - 34.0) > 0.5:
    err(f"Joystick PCB length {JOY_PCB_L}mm ≠ spec 34mm")
else:
    ok(f"Joystick PCB: {JOY_PCB_L}×{JOY_PCB_W}mm ✓")

if abs(JOY_HOLE_GRID_X - 26.67) > 0.1 or abs(JOY_HOLE_GRID_Y - 20.32) > 0.1:
    err(f"Joystick hole grid {JOY_HOLE_GRID_X}×{JOY_HOLE_GRID_Y} ≠ spec 26.67×20.32")
else:
    ok(f"Joystick hole grid: {JOY_HOLE_GRID_X}×{JOY_HOLE_GRID_Y}mm (1.05\"×0.80\") ✓")

pin_inset_x = (JOY_PCB_L - JOY_HOLE_GRID_X) / 2
pin_inset_y = (JOY_PCB_W - JOY_HOLE_GRID_Y) / 2
ok(f"Joystick pin inset from edge: X={pin_inset_x:.2f}mm, Y={pin_inset_y:.2f}mm")

if JOY_PIN_D >= 4.2:
    err(f"Joystick pin Ø{JOY_PIN_D}mm ≥ hole Ø4.2mm — won't fit!")
elif JOY_PIN_D > 3.8:
    warn(f"Joystick pin Ø{JOY_PIN_D}mm tight in Ø4.2mm hole (clearance {4.2-JOY_PIN_D:.1f}mm)")
else:
    ok(f"Joystick pin Ø{JOY_PIN_D}mm in Ø4.2mm hole — clearance {4.2-JOY_PIN_D:.1f}mm ✓")

_spec_pres = SPEC["MPS20N0040D-S + HX710B"]
if abs(PRES_PCB_W - _spec_pres["board_l"][0]) > 1.0 or abs(PRES_PCB_H - _spec_pres["board_w"][0]) > 1.0:
    warn(f"Pressure sensor PCB {PRES_PCB_W}×{PRES_PCB_H}mm differs from the approximate spec "
         f"{_spec_pres['board_l'][0]}×{_spec_pres['board_w'][0]}mm by more than 1mm")
else:
    ok(f"Pressure sensor PCB: {PRES_PCB_W}×{PRES_PCB_H}mm "
       f"(spec ≈{_spec_pres['board_l'][0]}×{_spec_pres['board_w'][0]}) ✓")
ok(f"Mic mount: Ø{MIC_CLEAR_D}mm clear, nut SW{MIC_NUT_SW}mm")

# ── 2. Cavity bounds check ───────────────────────────────────────

print("\n── 2. Components Inside Cavity ──")
print(f"     Cavity: ±{INNER_POS_X:.1f}mm (X), ±{INNER_POS_Y:.1f}mm (Y), "
      f"Z={FLOOR_T:.1f}..{EXT_H_BASE:.1f}mm")

# ESP32
esp_min_x = ESP_POS_X - ESP_L / 2
esp_max_x = ESP_POS_X + ESP_L / 2
esp_min_y = ESP_POS_Y - ESP_W / 2
esp_max_y = ESP_POS_Y + ESP_W / 2

if esp_max_x > INNER_POS_X:
    err(f"ESP32 +X edge ({esp_max_x:.1f}) exceeds cavity ({INNER_POS_X:.1f}) by {esp_max_x-INNER_POS_X:.1f}mm")
elif esp_max_x > INNER_POS_X - 1.0:
    warn(f"ESP32 +X edge ({esp_max_x:.1f}) very close to wall ({INNER_POS_X:.1f}), only {INNER_POS_X-esp_max_x:.1f}mm")
else:
    ok(f"ESP32 X: {esp_min_x:.1f} to {esp_max_x:.1f} — wall clearance {INNER_POS_X-esp_max_x:.1f}mm ✓")

if esp_min_x < -INNER_POS_X:
    err(f"ESP32 -X edge ({esp_min_x:.1f}) exceeds cavity ({-INNER_POS_X:.1f})")
if abs(esp_max_y) > INNER_POS_Y:
    err(f"ESP32 +Y edge ({esp_max_y:.1f}) exceeds cavity ({INNER_POS_Y:.1f})")
else:
    ok(f"ESP32 Y: {esp_min_y:.1f} to {esp_max_y:.1f} — wall clearance {INNER_POS_Y-esp_max_y:.1f}mm ✓")

# Joystick pillars (4 feet at hole grid positions)
_pillar_positions = []
for _dx in [-1, 1]:
    for _dy in [-1, 1]:
        _px = JOY_POS_X + _dx * (JOY_HOLE_GRID_X / 2)
        _py = JOY_POS_Y + _dy * (JOY_HOLE_GRID_Y / 2)
        if _py <= INNER_POS_Y - 0.5:
            _pillar_positions.append((_px, _py))

_pillar_base_r = JOY_PILLAR_FLARE_D / 2  # the foot is the widest part
_errors_before = len(errors)
if len(_pillar_positions) != 4:
    warn(f"Joystick stands on {len(_pillar_positions)} pillar feet, not one per M4 hole (4)")
for _px, _py in _pillar_positions:
    if abs(_px) + _pillar_base_r > INNER_POS_X:
        err(f"Joystick pillar at ({_px:.1f},{_py:.1f}) exceeds X cavity")
    if abs(_py) + _pillar_base_r > INNER_POS_Y:
        err(f"Joystick pillar at ({_px:.1f},{_py:.1f}) exceeds Y cavity")
if len(errors) == _errors_before:
    ok(f"Joystick pillars: {len(_pillar_positions)} feet, Ø{JOY_PILLAR_D}mm shaft on "
       f"Ø{JOY_PILLAR_FLARE_D}mm foot, inside cavity ✓")

# The USB cable runs between the feet (plug first, then seat the joystick)
_pillar_gap_x = (min(p[0] for p in _pillar_positions if p[0] > JOY_POS_X)
                 - max(p[0] for p in _pillar_positions if p[0] < JOY_POS_X) - JOY_PILLAR_D)
if _pillar_gap_x < USB_PLUG_W:
    warn(f"Gap between pillar shafts {_pillar_gap_x:.1f}mm < USB plug width {USB_PLUG_W}mm")
else:
    ok(f"Gap between pillar shafts (X): {_pillar_gap_x:.1f}mm — cable routes through ✓")

# The stick must reach through the lid, or there is nothing to put the mouthpiece on.
# (JOY_HOUSING is the housing's footprint, not its height; adding it to Z gave a
# warning on every run.)
if STICK_PROTRUSION <= 0:
    err(f"Stick tip Z={STICK_TIP_Z:.1f} does not reach above the lid top Z={LID_TOP_Z:.1f}")
else:
    ok(f"Stick protrudes {STICK_PROTRUSION:.1f}mm above the lid ✓")

# Joystick +Y wall relief
if JOY_WALL_RELIEF_DEPTH > 0:
    if JOY_REMAINING_TOP_WALL < 0.8:
        err(f"Joystick wall relief leaves only {JOY_REMAINING_TOP_WALL:.1f}mm — too thin!")
    elif JOY_REMAINING_TOP_WALL < 1.2:
        warn(f"Joystick wall relief leaves {JOY_REMAINING_TOP_WALL:.1f}mm — thin but printable")
    else:
        ok(f"Joystick wall relief: {JOY_WALL_RELIEF_DEPTH:.1f}mm deep, {JOY_REMAINING_TOP_WALL:.1f}mm remaining ✓")
else:
    ok(f"Joystick PCB fits inside cavity, no wall relief needed ✓")

# Pressure sensor: PCB flat against the +X inner wall, carried by a shelf
_pres_problems = []
if PRES_INNER_X > INNER_POS_X or PRES_SHELF_X_START <= 0:
    _pres_problems.append(f"shelf X {PRES_SHELF_X_START:.1f}..{PRES_INNER_X:.1f} is not against "
                          f"the +X inner wall ({INNER_POS_X:.1f})")
if abs(PRES_POS_Y) + PRES_PCB_H / 2 > INNER_POS_Y:
    _pres_problems.append(f"PCB reaches Y ±{abs(PRES_POS_Y) + PRES_PCB_H / 2:.1f}, cavity is ±{INNER_POS_Y:.1f}")
if PRES_SHELF_Z_BOT < FLOOR_T:
    _pres_problems.append(f"shelf underside Z={PRES_SHELF_Z_BOT:.1f} is below the floor top ({FLOOR_T:.1f})")
for _p in _pres_problems:
    err(f"Pressure sensor: {_p}")
if not _pres_problems:
    ok(f"Pressure sensor on +X wall: shelf X {PRES_SHELF_X_START:.1f}..{PRES_INNER_X:.1f}, "
       f"PCB Z {PRES_Z_BOT:.1f}..{PRES_Z_TOP:.1f} ✓")

# Barb port: the hole and its outer chamfer must sit inside the wall band below the lip
_barb_lo = PRES_NIPPLE_Z - PRES_BARB_CHAMFER_D / 2
_barb_hi = PRES_NIPPLE_Z + PRES_BARB_CHAMFER_D / 2
if _barb_lo < FLOOR_T or _barb_hi > LIP_ZONE_BOTTOM:
    err(f"Barb port Z {_barb_lo:.1f}..{_barb_hi:.1f} leaves the wall band {FLOOR_T:.1f}..{LIP_ZONE_BOTTOM:.1f}")
else:
    ok(f"Barb port Z {_barb_lo:.1f}..{_barb_hi:.1f} inside the wall band {FLOOR_T:.1f}..{LIP_ZONE_BOTTOM:.1f} ✓")

# Mic nut insertion clearance — nut must slide in from +X side
_nut_ac = MIC_NUT_SW_TOL / math.cos(math.radians(30))
_nearest_pillar_x = min(p[0] for p in _pillar_positions) - _pillar_base_r
_nut_insertion_gap = _nearest_pillar_x - MIC_COLLAR_INNER_X
_nut_min_gap = _nut_ac + 3.0  # nut across-corners + 3mm finger room
if _nut_insertion_gap < _nut_ac:
    err(f"Mic nut CANNOT be inserted! Gap {_nut_insertion_gap:.1f}mm < nut {_nut_ac:.1f}mm across-corners")
elif _nut_insertion_gap < _nut_min_gap:
    warn(f"Mic nut insertion tight: {_nut_insertion_gap:.1f}mm gap, nut {_nut_ac:.1f}mm + 3mm finger = {_nut_min_gap:.1f}mm needed")
else:
    ok(f"Mic nut insertion: {_nut_insertion_gap:.1f}mm gap for {_nut_ac:.1f}mm nut + finger room ✓")

# Mic collar
if MIC_Y_EDGE_MARGIN < 2.0:
    err(f"Mic collar margin only {MIC_Y_EDGE_MARGIN:.1f}mm from Y edge — too close")
else:
    ok(f"Mic collar margin: {MIC_Y_EDGE_MARGIN:.1f}mm from each Y edge ✓")

# ── 3. Inter-component clearances ────────────────────────────────

print("\n── 3. Inter-Component Clearances ──")

# (label, clearance, below this it is "tight"). Side-by-side parts want 2 mm; the
# sensor top vs the descending lid lip uses the generator's own warning margin.
checks = [
    ("Mic collar → Joystick platform", COLLAR_TO_JOY_CLEARANCE, 2.0),
    ("Joystick platform → Sensor shelf", PRES_SHELF_X_START - JOY_PLATFORM_MAX_X, 2.0),
    ("ESP32 right edge → +X wall", ESP_TO_WALL_CLEARANCE, 2.0),
    ("Joystick front pins → +Y wall", JOY_FRONT_PIN_TO_WALL_CLEAR, 2.0),
    ("Sensor PCB top → lid lip zone (Z)", LIP_ZONE_BOTTOM - PRES_Z_TOP, 0.5),
]

for label, val, tight in checks:
    if val < 0:
        err(f"{label}: {val:.1f}mm — COLLISION!")
    elif val < tight:
        warn(f"{label}: {val:.1f}mm — tight (< {tight}mm)")
    else:
        ok(f"{label}: {val:.1f}mm ✓")

# ESP32 vs sensor. The sensor PCB bottom sits below the ESP32 PCB top
# (PRES_ESP_Z_GAP < 0), so only the X gap keeps the boards apart. The generator
# raises at import when both gaps are negative; this also flags a thin X gap.
if PRES_ESP_Z_GAP >= 0:
    ok(f"Sensor above the ESP32 PCB: Z gap {PRES_ESP_Z_GAP:.1f}mm ✓")
elif PRES_ESP_X_GAP < 0:
    err(f"Sensor and ESP32 overlap in X ({PRES_ESP_X_GAP:.1f}mm) and Z ({PRES_ESP_Z_GAP:.1f}mm)")
elif PRES_ESP_X_GAP < 1.0:
    warn(f"Sensor and ESP32 share a Z band; X gap only {PRES_ESP_X_GAP:.1f}mm")
else:
    ok(f"Sensor/ESP32: X gap {PRES_ESP_X_GAP:.1f}mm (they share a Z band, Z gap {PRES_ESP_Z_GAP:.1f}) ✓")

# USB plug clearance
usb_plug_tip_x = ESP_USB_FACE_X - USB_PLUG_DEPTH
if usb_plug_tip_x < -INNER_POS_X:
    err(f"USB plug tip ({usb_plug_tip_x:.1f}mm) would hit -X wall ({-INNER_POS_X:.1f}mm)")
else:
    ok(f"USB plug access: port face at X={ESP_USB_FACE_X:.1f}, plug tip at {usb_plug_tip_x:.1f} — "
       f"{usb_plug_tip_x+INNER_POS_X:.1f}mm to wall ✓")

# ── 4. Screw closure ─────────────────────────────────────────────

print("\n── 4. Screw Closure (4× countersunk wood screw) ──")

# The generator refuses too little engagement only when it writes the report.
if SCREW_ACTUAL_PENETRATION < MIN_THREAD_ENGAGEMENT:
    err(f"Thread engagement {SCREW_ACTUAL_PENETRATION:.1f}mm < {MIN_THREAD_ENGAGEMENT:.0f}mm — screw too short")
else:
    ok(f"Thread engagement in base pillar: {SCREW_ACTUAL_PENETRATION:.1f}mm (min {MIN_THREAD_ENGAGEMENT:.0f}) ✓")

# Self-tapping: pilot below the thread, lid hole above it, countersink wider than the head
_screw_problems = []
if SCREW_PILOT_D >= SCREW_THREAD_D:
    _screw_problems.append(f"pilot Ø{SCREW_PILOT_D} ≥ thread Ø{SCREW_THREAD_D} — the screw cannot cut a thread")
if SCREW_CLEAR_D <= SCREW_THREAD_D:
    _screw_problems.append(f"lid hole Ø{SCREW_CLEAR_D} ≤ thread Ø{SCREW_THREAD_D} — the screw binds in the lid")
if SCREW_CSK_D <= SCREW_HEAD_D:
    _screw_problems.append(f"countersink Ø{SCREW_CSK_D} ≤ head Ø{SCREW_HEAD_D} — the head stands proud")
for _p in _screw_problems:
    err(f"Screw fit: {_p}")
if not _screw_problems:
    ok(f"Screw fit: pilot Ø{SCREW_PILOT_D} < thread Ø{SCREW_THREAD_D} < lid hole Ø{SCREW_CLEAR_D}, "
       f"countersink Ø{SCREW_CSK_D} > head Ø{SCREW_HEAD_D} ✓")

_pillar_wall = (PILLAR_OD - SCREW_PILOT_D) / 2
if _pillar_wall < 2 * LINE_W:
    err(f"Screw pillar wall {_pillar_wall:.2f}mm < 2 lines — splits when the screw cuts")
elif _pillar_wall < 3 * LINE_W:
    warn(f"Screw pillar wall {_pillar_wall:.2f}mm = {_pillar_wall / LINE_W:.1f} lines — thin")
else:
    ok(f"Screw pillar wall: {_pillar_wall:.2f}mm = {_pillar_wall / LINE_W:.1f} lines ✓")


def _circle_to_rect_gap(cx, cy, r, x0, x1, y0, y1):
    """XY distance from a circle (a pillar) to an axis-aligned rectangle (a board)."""
    return math.hypot(max(x0 - cx, 0.0, cx - x1), max(y0 - cy, 0.0, cy - y1)) - r


# Screw pillars in the corners vs the boards beside them. Both span the full
# cavity height, so the XY gap decides.
_boards = [
    ("ESP32 PCB", (ESP_LEFT_EDGE_X, ESP_RIGHT_EDGE_X, ESP_POS_Y - ESP_W / 2, ESP_POS_Y + ESP_W / 2)),
    ("sensor PCB", (PRES_SHELF_X_START, PRES_INNER_X, PRES_POS_Y - PRES_PCB_H / 2, PRES_POS_Y + PRES_PCB_H / 2)),
]
for _name, _rect in _boards:
    _gap = min(_circle_to_rect_gap(_px, _py, PILLAR_OD / 2, *_rect) for _px, _py in PILLAR_POSITIONS)
    if _gap < 0:
        err(f"Screw pillar cuts into the {_name} by {-_gap:.1f}mm")
    elif _gap < 0.5:
        warn(f"Screw pillar ↔ {_name}: only {_gap:.1f}mm")
    else:
        ok(f"Screw pillar ↔ {_name}: {_gap:.1f}mm ✓")

# ── 5. Printability (Bambu Lab P1S/P2S, 0.4mm nozzle) ───────────

print("\n── 5. Printability (Bambu Lab, 0.4mm nozzle) ──")

wall_lines = WALL / LINE_W
floor_layers = FLOOR_T / LAYER_H
ceil_layers = CEIL_T / LAYER_H
lip_lines = LIP_T / LINE_W

ok(f"Wall: {WALL}mm = {wall_lines:.1f} lines @ {LINE_W}mm (Arachne handles fractional)")
if wall_lines < 2.5:
    err(f"Wall too thin: {wall_lines:.1f} lines — minimum 3 for structural integrity")
elif wall_lines < 3.5:
    warn(f"Wall: {wall_lines:.1f} lines — functional but thin for handling")
else:
    ok(f"Wall perimeters: {wall_lines:.1f} — good for structural enclosure ✓")

ok(f"Floor: {FLOOR_T}mm = {floor_layers:.0f} layers @ {LAYER_H}mm")
ok(f"Ceiling: {CEIL_T}mm = {ceil_layers:.0f} layers @ {LAYER_H}mm")

if floor_layers < 4:
    warn(f"Floor only {floor_layers:.0f} layers — recommend ≥4 for bottom strength")
if ceil_layers < 4:
    warn(f"Ceiling only {ceil_layers:.0f} layers — recommend ≥4 for top strength")

if lip_lines < 2.0:
    warn(f"Lip only {lip_lines:.1f} lines — fragile when the lid is set on")
else:
    ok(f"Lip: {LIP_T}mm = {lip_lines:.1f} lines ✓")

# Corner radius vs nozzle
if CORNER_R < 2 * NOZZLE:
    warn(f"Corner radius {CORNER_R}mm < 2× nozzle ({2*NOZZLE}mm) — may print as sharp corner")
else:
    ok(f"Corner radius {CORNER_R}mm ✓")

# Overhang check — joystick platform
platform_overhang = JOY_PLATFORM_H  # vertical wall, no overhang
ok(f"Joystick platform: {JOY_PLATFORM_H}mm vertical wall — no overhang, no support needed ✓")

# Lid orientation check
ok(f"Lid prints upside-down (ceiling-down), no support needed")
ok(f"Base prints floor-down, no support needed")

# Vent slot printability
vent_lines = VENT_W / LINE_W
if vent_lines < 1.5:
    warn(f"Vent slots {VENT_W}mm wide = {vent_lines:.1f} lines — may not resolve cleanly")
else:
    ok(f"Vent slots: {VENT_W}mm = {vent_lines:.1f} lines ✓")

# Slicer settings are not validated here: they live in bambu-profiles/ and in the
# generator's report, and a list of recommendations cannot fail.

# ── 6. USB plug vs joystick pillars ──────────────────────────────

print("\n── 6. USB Plug vs Pillar Clearance ──")
_usb_port_x2 = ESP_USB_FACE_X
_usb_plug_x1 = _usb_port_x2 - USB_PLUG_DEPTH
_usb_plug_y1 = ESP_POS_Y - USB_PLUG_W / 2
_usb_plug_y2 = ESP_POS_Y + USB_PLUG_W / 2
_pillar_sr = JOY_PILLAR_D / 2

for _px, _py in _pillar_positions:
    _ox = min(_usb_port_x2, _px + _pillar_sr) - max(_usb_plug_x1, _px - _pillar_sr)
    if _ox <= 0:
        continue
    if _py > ESP_POS_Y:
        _gap = (_py - _pillar_sr) - _usb_plug_y2
    else:
        _gap = _usb_plug_y1 - (_py + _pillar_sr)
    if _gap < 0:
        err(f"USB plug COLLIDES with pillar ({_px:+.0f},{_py:+.0f}) by {-_gap:.1f}mm!")
    elif _gap < 1.5:
        warn(f"USB plug ↔ pillar ({_px:+.0f},{_py:+.0f}): {_gap:.1f}mm")
    else:
        ok(f"USB plug ↔ pillar ({_px:+.0f},{_py:+.0f}): {_gap:.1f}mm ✓")

# ── 7. Feature Position Sanity Checks ──────────────────────────────
print("\n── 7. Feature Position Sanity Checks ──")

# Every feature must be in its expected quadrant/region.
# Catches sign errors, wrong offsets, copy-paste bugs.

# USB notch: must be near ESP32 X range (not in joystick area)
if USB_NOTCH_X < 0:
    err(f"USB notch at X={USB_NOTCH_X:.1f} — expected X>0 (ESP32 area, not joystick area)")
else:
    ok(f"USB notch X={USB_NOTCH_X:.1f} in ESP32 region ✓")

# Mic mount: must be on -X wall (leftmost)
if MIC_WALL_OUTER_X > 0:
    err(f"Mic mount at X={MIC_WALL_OUTER_X:.1f} — expected X<0 (-X wall)")
else:
    ok(f"Mic mount on -X wall (X={MIC_WALL_OUTER_X:.1f}) ✓")

# Joystick: must be in -X half
if JOY_POS_X > 0:
    err(f"Joystick at X={JOY_POS_X:.1f} — expected X<0 (left side)")
else:
    ok(f"Joystick at X={JOY_POS_X:.1f} (left side) ✓")

# Pressure sensor: must be in +X half
if PRES_SHELF_X_START < 0:
    err(f"Pressure sensor shelf at X={PRES_SHELF_X_START:.1f} — expected X>0 (right side)")
else:
    ok(f"Pressure sensor shelf at X={PRES_SHELF_X_START:.1f} (right side) ✓")

# Geometry: both parts must build — a part that does not build cannot be printed,
# and the generator raises on a failed countersink loft instead of skipping it.
try:
    import cadquery as cq
    _base = make_base()
    make_lid()
except Exception as _e:
    err(f"Enclosure geometry does not build: {_e}")
else:
    ok("Base and lid build ✓")
    # Vent slots, probed in the built base: air at each slot centre in the middle
    # of the -Y wall means the slot was cut. 97fb175: the cut was defined but never
    # called, and the printed base had no ventilation at all. The control point
    # between two slots must hit material, or the probe is looking in the wrong place.
    _solid = _base.val()
    _wall_mid_y = -(OUTER_POS_Y - WALL / 2)
    _uncut = [x for x in VENT_CENTER_XS if _solid.isInside(cq.Vector(x, _wall_mid_y, VENT_CENTER_Z))]
    _control = cq.Vector(VENT_CENTER_XS[0] + VENT_PITCH / 2, _wall_mid_y, VENT_CENTER_Z)
    if not _solid.isInside(_control):
        err("Vent probe misses the -Y wall (control point between two slots is not material)")
    elif _uncut:
        err(f"Vent slots NOT cut at X={', '.join(f'{x:+.0f}' for x in _uncut)} — "
            f"the base would print without ventilation")
    else:
        ok(f"Vent slots: all {len(VENT_CENTER_XS)} cut through the -Y wall (probed; control hits material) ✓")

# ── Summary ──────────────────────────────────────────────────────

print("\n" + "=" * 65)
print(f"  ERRORS: {len(errors)}   WARNINGS: {len(warnings)}   OK: {len(info)}")
print("=" * 65)

if errors:
    print("\n🔴 ERRORS:")
    for e in errors:
        print(e)

if warnings:
    print("\n🟡 WARNINGS:")
    for w in warnings:
        print(w)

if not _MODEL_IS_CURRENT:
    print(f"\n🔴 STALE: this validator checks {VALIDATED_MODEL}, but the current "
          f"model is {_CURRENT_MODEL}.")
    print("   Its checks read that model's constants, so a pass here says nothing")
    print("   about the enclosure you would print. Port it before trusting it.")
elif not errors:
    print("\n🟢 No errors — design is valid")

print()

# Exit code, so this can actually gate anything. There was no sys.exit at all:
# the script printed a red ERRORS block and still returned 0, which meant any
# `validate_enclosure.py && …` or hook keyed on the exit status passed
# unconditionally — a check that could not fail.
sys.exit(1 if (errors or not _MODEL_IS_CURRENT) else 0)
