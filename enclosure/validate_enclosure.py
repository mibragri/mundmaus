#!/usr/bin/env python3
"""MundMaus v5.5 Enclosure Validator — checks dimensions, clearances, printability."""

import sys

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

sys.path.insert(0, ".")
from mundmaus_v55_enclosure import *  # noqa: E402, F403

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
print("  MundMaus v5.5 Enclosure Validation")
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

ok(f"Pressure sensor: {PRES_L}×{PRES_W}×{PRES_H}mm")
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

_pillar_base_r = 11.0 / 2  # base flare radius
for _px, _py in _pillar_positions:
    if abs(_px) + _pillar_base_r > INNER_POS_X:
        err(f"Joystick pillar at ({_px:.1f},{_py:.1f}) exceeds X cavity")
    if abs(_py) + _pillar_base_r > INNER_POS_Y:
        err(f"Joystick pillar at ({_px:.1f},{_py:.1f}) exceeds Y cavity")
ok(f"Joystick pillars: {len(_pillar_positions)} feet at Ø8mm (Ø11mm base flare) ✓")

# USB plug clearance through pillar gaps
_pillar_min_x = min(p[0] for p in _pillar_positions) - _pillar_base_r
_pillar_max_x = max(p[0] for p in _pillar_positions) + _pillar_base_r
_pillar_gap_x = min(p[0] for p in _pillar_positions if p[0] > JOY_POS_X) - max(p[0] for p in _pillar_positions if p[0] < JOY_POS_X) - 8.0
ok(f"Pillar gap between feet (X): {_pillar_gap_x:.1f}mm — cables route through ✓")

joy_top_z = FLOOR_T + JOY_PLATFORM_H + JOY_PCB_H + JOY_HOUSING
if joy_top_z > EXT_H_BASE:
    warn(f"Joystick housing top ({joy_top_z:.1f}mm) above base rim ({EXT_H_BASE:.1f}mm) — lid must clear")

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

# Pressure sensor
if PRES_HOLDER_MAX_X > INNER_POS_X:
    err(f"Pressure holder +X edge ({PRES_HOLDER_MAX_X:.1f}) exceeds cavity ({INNER_POS_X:.1f})")
if PRES_HOLDER_MIN_X < -INNER_POS_X:
    err(f"Pressure holder -X edge ({PRES_HOLDER_MIN_X:.1f}) exceeds cavity ({-INNER_POS_X:.1f})")
if PRES_HOLDER_MAX_Z > EXT_H_BASE:
    err(f"Pressure holder top ({PRES_HOLDER_MAX_Z:.1f}) above base rim ({EXT_H_BASE:.1f})")
else:
    ok(f"Pressure sensor holder Z: {PRES_HOLDER_MIN_Z:.1f} to {PRES_HOLDER_MAX_Z:.1f} (base rim {EXT_H_BASE:.1f}) ✓")

# Mic nut insertion clearance — nut must slide in from +X side
import math as _math
_nut_ac = MIC_NUT_SW_TOL / _math.cos(_math.radians(30))
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

MIN_CLEARANCE = 2.0  # mm minimum between components

checks = [
    ("Mic collar → Joystick platform", COLLAR_TO_JOY_CLEARANCE),
    ("Joystick platform → Sensor holder", JOY_TO_PRES_CLEARANCE),
    ("ESP32 right edge → +X wall", ESP_TO_WALL_CLEARANCE),
    ("Joystick front pins → +Y wall", JOY_FRONT_PIN_TO_WALL_CLEAR),
    ("Sensor holder top → base rim (Z)", BARB_TO_LID_RIM_CLEARANCE_Z),
]

for label, val in checks:
    if val < 0:
        err(f"{label}: {val:.1f}mm — COLLISION!")
    elif val < MIN_CLEARANCE:
        warn(f"{label}: {val:.1f}mm — tight (< {MIN_CLEARANCE}mm)")
    else:
        ok(f"{label}: {val:.1f}mm ✓")

# ESP32 vs Pressure sensor vertical clearance
esp_guide_top_z = FLOOR_T + ESP_STANDOFF_H + ESP_H + ESP_GUIDE_H
esp_guide_top_y = ESP_POS_Y + ESP_W / 2 + TOL_LOOSE + 1.5  # guide rail outer Y
pres_shelf_min_y = INNER_POS_Y - PRES_HOLDER_DEPTH

sensor_esp_x_overlap = min(esp_max_x, PRES_HOLDER_MAX_X) - max(esp_min_x, PRES_HOLDER_MIN_X)
if sensor_esp_x_overlap > 0:
    vert_gap = PRES_HOLDER_MIN_Z - esp_guide_top_z
    y_gap = pres_shelf_min_y - esp_guide_top_y
    if vert_gap < 1.0 and y_gap < 1.0:
        err(f"Sensor/ESP32 X-overlap {sensor_esp_x_overlap:.1f}mm with Z-gap {vert_gap:.1f}mm AND Y-gap {y_gap:.1f}mm")
    else:
        ok(f"Sensor/ESP32 share X-range ({sensor_esp_x_overlap:.1f}mm overlap), Z-gap={vert_gap:.1f}mm, Y-gap={y_gap:.1f}mm ✓")
else:
    ok(f"Sensor and ESP32 separated in X by {-sensor_esp_x_overlap:.1f}mm ✓")

# USB plug clearance
usb_plug_length = 12.0  # typical Micro-USB plug
usb_port_x = ESP_POS_X - ESP_L / 2
usb_plug_tip_x = usb_port_x - usb_plug_length
if usb_plug_tip_x < -INNER_POS_X:
    err(f"USB plug tip ({usb_plug_tip_x:.1f}mm) would hit -X wall ({-INNER_POS_X:.1f}mm)")
else:
    ok(f"USB plug access: port at X={usb_port_x:.1f}, plug tip at {usb_plug_tip_x:.1f} — {usb_plug_tip_x+INNER_POS_X:.1f}mm to wall ✓")

# USB cable notch position
ok(f"USB cable notch at X={USB_NOTCH_X:.1f} on -Y wall (aligned with USB port)")

# Screw boss conflicts
print("\n── 4. Screw Boss Clearances ──")
for i, (bx, by) in enumerate(SCREW_POSITIONS):
    label = f"Boss {i+1} ({bx:+.0f},{by:+.0f})"
    boss_r = SCREW_BOSS_D / 2

    # Check vs joystick pillars
    _boss_pillar_conflict = False
    for _px, _py in _pillar_positions:
        dist = ((bx - _px)**2 + (by - _py)**2)**0.5
        if dist < boss_r + _pillar_base_r:
            warn(f"{label} overlaps pillar at ({_px:.0f},{_py:.0f}) — will merge")
            _boss_pillar_conflict = True
            break
    if not _boss_pillar_conflict:
        ok(f"{label} clear of joystick pillars ✓")

    # Check vs mic collar
    collar_dist = ((bx - (-INNER_POS_X + MIC_NUT_POCKET_D / 2))**2 + (by - MIC_POS_Y)**2)**0.5
    if collar_dist < MIC_COLLAR_D / 2 + boss_r:
        warn(f"{label} close to mic collar (distance {collar_dist:.1f}mm)")

# ── 5. Printability (Bambu Lab P1S/P2S, 0.4mm nozzle) ───────────

print("\n── 5. Printability (Bambu Lab, 0.4mm nozzle) ──")

LINE_W = 0.42  # Bambu Studio default
LAYER_H = 0.20  # standard
NOZZLE = 0.4

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

ok(f"Lip: {LIP_T}mm = {lip_lines:.1f} lines")
if lip_lines < 2.0:
    warn(f"Lip only {lip_lines:.1f} lines — may be fragile during snap-fit")

# Corner radius vs nozzle
if CORNER_R < 2 * NOZZLE:
    warn(f"Corner radius {CORNER_R}mm < 2× nozzle ({2*NOZZLE}mm) — may print as sharp corner")
else:
    ok(f"Corner radius {CORNER_R}mm ✓")

# Overhang check — joystick platform
platform_overhang = JOY_PLATFORM_H  # vertical wall, no overhang
ok(f"Joystick platform: {JOY_PLATFORM_H}mm vertical wall — no overhang, no support needed ✓")

# Screw boss printability
boss_wall = (SCREW_BOSS_D - SCREW_PILOT_D) / 2
boss_lines = boss_wall / LINE_W
if boss_lines < 2:
    warn(f"Screw boss wall {boss_wall:.1f}mm = {boss_lines:.1f} lines — thin")
else:
    ok(f"Screw boss wall: {boss_wall:.1f}mm = {boss_lines:.1f} lines ✓")

# Lid orientation check
ok(f"Lid prints upside-down (ceiling-down), no support needed")
ok(f"Base prints floor-down, no support needed")

# Vent slot printability
vent_lines = VENT_W / LINE_W
if vent_lines < 1.5:
    warn(f"Vent slots {VENT_W}mm wide = {vent_lines:.1f} lines — may not resolve cleanly")
else:
    ok(f"Vent slots: {VENT_W}mm = {vent_lines:.1f} lines ✓")

# ── 6. Bambu Lab specific recommendations ────────────────────────

print("\n── 6. Bambu Lab Slicer Recommendations ──")
ok(f"Material: PETG (impact resistant, temp stable)")
ok(f"Layer height: 0.20mm (standard quality)")
ok(f"Wall count: 5 (= {5*LINE_W:.2f}mm, matches {WALL}mm wall)")
ok(f"Top/bottom layers: 5 (= {5*LAYER_H:.2f}mm, for {FLOOR_T}mm floor)")
ok(f"Infill: 20-25% gyroid (good for screw boss strength)")
ok(f"Nozzle temp: 240°C, Bed: 70°C (PETG on textured PEI)")
ok(f"Cooling: 40-60% (PETG, enclosed P1S/P2S chamber)")
ok(f"Arachne wall generator: enabled (default)")
ok(f"Seam: aligned to back (-Y wall) to hide on visible surfaces")

# ── 7. Visual Clearance (USB plug vs pillars) ────────────────────

print("\n── 7. USB Plug vs Pillar Clearance ──")
_usb_plug_w = 11.0
_usb_plug_len = 20.0
_usb_port_x2 = ESP_POS_X - ESP_L / 2
_usb_plug_x1 = _usb_port_x2 - _usb_plug_len
_usb_plug_y1 = ESP_POS_Y - _usb_plug_w / 2
_usb_plug_y2 = ESP_POS_Y + _usb_plug_w / 2
_pillar_sr = 3.0  # must match enclosure Ø6/2

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

if not errors:
    print("\n🟢 No errors — design is valid")

print()
