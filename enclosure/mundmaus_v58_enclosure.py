#!/usr/bin/env python3
# UNITS: mm
# SPEC: Lid auf Base verschrauben statt klipsen — 4 Spax 3.5x20 Senkkopf in den Ecken
"""MundMaus Enclosure v5.8 — Screw fastening instead of detent click.

v5.8 changes from v5.7:
  - Detent-Klick-Verschluss entfernt (RIDGE_*, GROOVE_*, _add_detent_groove).
  - 4 Schraubsäulen in den Eck-Innenbereichen (D=6mm, Bohrung 2.5mm in Base-Säule
    für selbstschneidende 3.5er Spanplattenschraube).
  - Lid: 4 hängende Säulen mit Durchgangsloch 4.0mm + Senkkopf-Senkung 7.5mm/2.1mm.
  - ESP-Side-Guide-Rails gekürzt (ESP_L*0.4 → 14mm fix), damit die Ecksäulen
    kollisionsfrei bei (±58, ±16.5) sitzen können.
  - Tiefenrechnung: Schraube 20mm = 9mm Lid-Korpus + 3mm Lip-Hänger + 8mm
    Eindringen in Base-Säule (Säulenoberkante Z=26.8, 0.2mm Spiel zum Lid-Hänger).

Was bleibt unverändert: Außenmaße, Wandstärke, ESP/Joystick/Sensor/Mic-Mount-Geometrie,
Lip-Zentrierung (LIP_H, LIP_GAP, LIP_T), USB-Notch, Vent-Slots.
"""
from __future__ import annotations

import argparse
import logging
import math
import re
import textwrap
import warnings
from dataclasses import dataclass
from itertools import pairwise
from pathlib import Path
from xml.etree import ElementTree as ET

import cadquery as cq  # type: ignore[import-not-found]
from PIL import Image, ImageDraw  # type: ignore[import-not-found]

warnings.filterwarnings("ignore")
logging.getLogger("OCC").setLevel(logging.ERROR)

# ── Core shell ──────────────────────────────────────────────────────
CAV_X, CAV_Y, WALL = 132.0, 46.0, 2.0  # thinner walls (5 perimeters @ 0.4mm)
FLOOR_T, CEIL_T, INNER_R = 2.0, 2.0, 10.0  # INNER_R = CORNER_R - WALL
BASE_INNER_H, LID_INNER_H = 28.0, 7.0
CORNER_R, LID_TOP_R, BASE_BOT_R = 12.0, 1.5, 2.0  # LID_TOP_R must be <= CEIL_T to avoid paper-thin walls when printed flipped
LIP_H, LIP_T, LIP_GAP = 3.0, 1.8, 0.15  # LIP_H 4.0→3.0 for sensor PCB clearance
TOL, TOL_LOOSE = 0.2, 0.2  # tighter guide rails — slight press-fit for ESP32

# ── ESP32-WROOM-32 DevKitC V4 ──────────────────────────────────────
ESP_L, ESP_W, ESP_H = 54.4, 28.0, 1.2  # Espressif DevKitC V4 spec (was 51.5)
ESP_MODULE_H = 3.1                      # WROOM-32 metal shield height
ESP_STANDOFF_H, ESP_GUIDE_H = 3.0, 3.0  # back to 3.0 — USB connector needs clearance below PCB
ESP_POS_X, ESP_POS_Y = 35.0, 0.0       # right side; USB faces -X (center). v5.8: Y=-2→0 für Eck-Säulen-Symmetrie
ESP_USB_PROTRUSION = 2.4
# ESP32 is mounted UPSIDE DOWN: WROOM module faces floor for cooling,
# buttons (EN/BOOT) face floor, pin headers face up.
# EN (reset) button position relative to USB end of PCB:
ESP_EN_BTN_FROM_USB = 7.5   # mm from USB end along long axis
ESP_EN_BTN_FROM_EDGE = 4.8  # mm from RIGHT edge (J2 side, when USB faces you)
ESP_EN_BTN_HOLE_D = 3.0     # access hole diameter in floor
HOLD_DOWN_CLEARANCE = 1.0   # mm gap between hold-down wall bottom and ESP32 PCB top

# ── KY-023 Joystick ────────────────────────────────────────────────
JOY_PCB_L, JOY_PCB_W, JOY_PCB_H = 34.0, 26.0, 1.6
JOY_HOUSING, JOY_STICK_H = 16.0, 17.0
JOY_PLATFORM_H = 21.0  # was 21.5 — 0.5mm lower per user feedback
JOY_PIN_D, JOY_PIN_H = 2.8, 3.0
JOY_HOLE_GRID_X, JOY_HOLE_GRID_Y = 26.67, 20.32  # 1.05" x 0.80" M4 holes
JOY_OPENING = 16.3  # was 17.0 — snug fit to center housing (0.15mm/side)
JOY_LID_HOLE_D = 14.0   # circular lid opening — rotation circle + 1mm clearance/side
JOY_LID_HOLE_OFFSET_X = 1.1   # calculated from measured housing center X=-17.9 vs JOY_POS=-19
JOY_LID_HOLE_OFFSET_Y = -0.8   # +0.3 was too far +Y, user says 1.1mm more toward -Y: 0.3 - 1.1 = -0.8
JOY_POS_X, JOY_POS_Y = -19.0, -2.0  # left side, Y=-2 = centered on USB plug Y for equal clearance
JOY_PLATFORM_MAIN_X, JOY_PLATFORM_MAIN_Y = JOY_PCB_L + 3.0, JOY_PCB_W - 6.0
JOY_PLATFORM_MAIN_SHIFT_Y = -2.0
JOY_PLATFORM_FRONT_X, JOY_PLATFORM_FRONT_Y = JOY_PCB_L, 6.0
JOY_PLATFORM_FRONT_SHIFT_Y = JOY_PCB_W / 2 - JOY_PLATFORM_FRONT_Y / 2 - 0.2

# ── Pressure Sensor (MPS20N0040D-S + HX710B) ───────────────────────
PRES_PCB_W = 20.0         # mm (Z direction when mounted flat against +X wall)
PRES_PCB_H = 15.0         # mm (Y direction when mounted flat against +X wall)
PRES_MOUNT_DEPTH = 5.0    # mm depth from +X inner wall into enclosure
PRES_POS_Y = 0.0          # centered on Y axis
PRES_POS_Z = 15.5         # center Z (lowered from 18.0 — PCB 20mm tall in Z, top must clear lip zone at Z=26)
PRES_BARB_HOLE_D = 2.8    # mm (was 3.0, tighter for press-fit)
PRES_BARB_CHAMFER_D = 5.0 # mm entry chamfer on exterior
PRES_SHELF_T = 1.5        # mm shelf thickness

# ── USB cable exit notch (+Y wall, at lid seam) ────────────────────
USB_NOTCH_W, USB_NOTCH_H = 8.0, 5.0
USB_NOTCH_X = ESP_POS_X - ESP_L / 2  # USB faces -X (center), cable routes left

# ── USB plug channel (cut into joystick platform base) ─────────────
USB_PLUG_W, USB_PLUG_H, USB_PLUG_DEPTH = 12.0, 9.0, 15.0

# ── Screw fastening (Spax 3.5x20 Senkkopf, selbstschneidend in PETG) ───
SCREW_THREAD_D = 3.5    # Gewinde-Außendurchmesser (Spax 3.5)
SCREW_LEN = 20.0        # Gesamtlänge
SCREW_HEAD_D = 7.0      # Senkkopf-Außendurchmesser (Standard für 3.5er Spax)
SCREW_HEAD_H = 2.1      # Senkkopf-Höhe = Senkungs-Tiefe
SCREW_PILOT_D = 2.5     # Vorbohr-Loch in Base-Säule (selbstschneidend, etwas unter Kerndurchmesser)
SCREW_CLEAR_D = 4.0     # Durchgangsloch im Lid (Schraube 3.5 + 0.5mm Spiel)
SCREW_CSK_D = 7.5       # Senkungs-Außendurchmesser (Kopf 7.0 + 0.5 für sauberen Sitz)
SCREW_PENETRATION = 8.0 # Soll-Eindringtiefe in die Base-Säule

# Eck-Säulen-Geometrie
PILLAR_OD = 6.0         # Säulen-Außendurchmesser (Wand 1.75mm um 2.5mm Bohrung — solide für PETG)
PILLAR_X = 58.0         # Säulen-X-Position (innen, in der Eckkurve mit INNER_R=10)
PILLAR_Y = 18.0         # Säulen-Y-Position (symmetrisch ±, mit ESP_POS_Y=0 → 1.0mm Abstand zu ESP32, 1.6mm zur Innenwand)
PILLAR_BASE_TOP_Z_OFFSET = 0.2  # Lücke zwischen Base-Säulen-Top und Lid-Hänger-Bottom

# ── 3/8"-16 UNC mic stand mount (-X wall) ──────────────────────────
MIC_CLEAR_D, MIC_NUT_SW, MIC_NUT_H = 10.5, 16.9, 5.56  # SW measured 16.8-16.9mm
MIC_NUT_TOL, MIC_NUT_POCKET_D, MIC_COLLAR_D = 0.205, 7.9, 24.0
MIC_POS_Y = 0.0
# MIC_POS_Z is derived below (collar sits on floor, top clears lip)

# ── Ventilation (-Y wall) ──────────────────────────────────────────
VENT_N, VENT_W, VENT_LEN, VENT_PITCH = 6, 1.6, 14.0, 6.0

# ── Derived geometry ───────────────────────────────────────────────
EXT_X, EXT_Y = CAV_X + 2 * WALL, CAV_Y + 2 * WALL  # 136 x 50
EXT_H_BASE, EXT_H_LID = FLOOR_T + BASE_INNER_H, CEIL_T + LID_INNER_H
OUTER_POS_X = EXT_X / 2    # +68
OUTER_POS_Y = EXT_Y / 2    # +25
INNER_POS_X = CAV_X / 2    # +65
INNER_POS_Y = EXT_Y / 2 - WALL  # +22

# Collar sits on floor: center = FLOOR_T + radius, top must clear lip (EXT_H_BASE - LIP_H)
MIC_POS_Z = FLOOR_T + MIC_COLLAR_D / 2 - 0.5  # 13.5mm, collar top = 25.5mm (0.5mm below lip at 26mm)
MIC_NUT_SW_TOL = MIC_NUT_SW + 2 * MIC_NUT_TOL
MIC_WALL_OUTER_X = -OUTER_POS_X
MIC_WALL_INNER_X = MIC_WALL_OUTER_X + WALL
MIC_COLLAR_INNER_X = MIC_WALL_INNER_X + MIC_NUT_POCKET_D
MIC_Y_EDGE_MARGIN = (EXT_Y - MIC_COLLAR_D) / 2

STICK_TIP_Z = FLOOR_T + JOY_PLATFORM_H + JOY_PCB_H + JOY_STICK_H
LID_TOP_Z = EXT_H_BASE + EXT_H_LID
STICK_PROTRUSION = STICK_TIP_Z - LID_TOP_Z

ESP_USB_FACE_X = ESP_POS_X - ESP_L / 2 - ESP_USB_PROTRUSION  # USB faces -X

# Joystick derived
JOY_PCB_TOP_Y = JOY_POS_Y + JOY_PCB_W / 2
JOY_WALL_RELIEF_DEPTH = max(0.0, JOY_PCB_TOP_Y - INNER_POS_Y)
JOY_REMAINING_TOP_WALL = WALL - JOY_WALL_RELIEF_DEPTH
JOY_FRONT_PIN_Y = JOY_POS_Y + (JOY_PCB_W / 2 - 2.5)
JOY_FRONT_PIN_TO_WALL_CLEAR = INNER_POS_Y - JOY_FRONT_PIN_Y
JOY_PLATFORM_MIN_X = JOY_POS_X - JOY_PLATFORM_MAIN_X / 2
JOY_PLATFORM_MAX_X = JOY_POS_X + JOY_PLATFORM_MAIN_X / 2

# Pressure sensor derived (v5.6: flat mount on +X inner wall)
PRES_INNER_X = CAV_X / 2          # = 66.0 (inner surface of +X wall)
PRES_SHELF_X_START = PRES_INNER_X - PRES_MOUNT_DEPTH  # = 61.0
PRES_Z_BOT = PRES_POS_Z - PRES_PCB_W / 2   # = 8.0 (bottom of PCB)
PRES_Z_TOP = PRES_POS_Z + PRES_PCB_W / 2    # = 28.0 (top of PCB)
# Nipple position (offset from PCB center, estimated from datasheet)
PRES_NIPPLE_Z = PRES_POS_Z + PRES_PCB_W / 2 - 5.0   # = 23.0
PRES_NIPPLE_Y = PRES_POS_Y + PRES_PCB_H / 2 - 4.0    # = 3.5

# Lip insertion zone: Z = EXT_H_BASE - LIP_H to EXT_H_BASE
# ALL internal features must have their top BELOW this zone
LIP_ZONE_BOTTOM = EXT_H_BASE - LIP_H
MIC_COLLAR_TOP_Z = MIC_POS_Z + MIC_COLLAR_D / 2
MIC_TO_LIP_CLEARANCE = LIP_ZONE_BOTTOM - MIC_COLLAR_TOP_Z

# Guard: all internal features must clear the lip insertion zone
_LIP_CLEARANCE_CHECKS = {
    "Mic collar top": (MIC_COLLAR_TOP_Z, LIP_ZONE_BOTTOM),
    "Sensor PCB top": (PRES_Z_TOP, LIP_ZONE_BOTTOM),
    "Joystick PCB top": (FLOOR_T + JOY_PLATFORM_H + JOY_PCB_H, LIP_ZONE_BOTTOM),
}
for _name, (_top, _limit) in _LIP_CLEARANCE_CHECKS.items():
    if _top > _limit:
        raise ValueError(
            f"COLLISION: {_name} at Z={_top:.1f}mm extends into lip zone "
            f"(Z={_limit:.1f}mm). Reduce height or move component down."
        )
    elif _top > _limit - 0.5:
        import warnings
        warnings.warn(f"{_name} at Z={_top:.1f}mm is only {_limit - _top:.1f}mm below lip zone")

# Clearances (layout: Collar → Joy → ESP32, Sensor on +X wall)
COLLAR_TO_JOY_CLEARANCE = JOY_PLATFORM_MIN_X - MIC_COLLAR_INNER_X
ESP_LEFT_EDGE_X = ESP_POS_X - ESP_L / 2
ESP_RIGHT_EDGE_X = ESP_POS_X + ESP_L / 2
ESP_TO_WALL_CLEARANCE = INNER_POS_X - ESP_RIGHT_EDGE_X
# Sensor vs ESP32 vertical clearance (different Z heights, same X region)
PRES_ESP_Z_GAP = PRES_Z_BOT - (FLOOR_T + ESP_STANDOFF_H + ESP_H)  # = 1.8mm

# Schraub-Säulen-Geometrie (Base- und Lid-Hänger-Positionen identisch)
PILLAR_BASE_TOP_Z = EXT_H_BASE - LIP_H - PILLAR_BASE_TOP_Z_OFFSET  # 26.8mm in base coords
PILLAR_POSITIONS = [(PILLAR_X, PILLAR_Y), (PILLAR_X, -PILLAR_Y),
                    (-PILLAR_X, PILLAR_Y), (-PILLAR_X, -PILLAR_Y)]
# Sanity: Säule darf die Innenwand-Eckkurve (INNER_R=10) nicht durchstechen
_PILLAR_CORNER_DIST = math.hypot(PILLAR_X - (CAV_X / 2 - INNER_R), PILLAR_Y - (CAV_Y / 2 - INNER_R))
if _PILLAR_CORNER_DIST + PILLAR_OD / 2 + 0.3 > INNER_R:
    raise ValueError(
        f"Eck-Säule bei (±{PILLAR_X}, ±{PILLAR_Y}) kollidiert mit Innenwand-Eckkurve: "
        f"Distanz zur Eckmitte = {_PILLAR_CORNER_DIST:.2f}mm, "
        f"erlaubt = {INNER_R - PILLAR_OD/2 - 0.3:.2f}mm."
    )

# ── Helper functions ───────────────────────────────────────────────


@dataclass(frozen=True)
class RenderView:
    filename: str
    projection_dir: tuple[float, float, float]
    assembled: bool
    target: str = "default"  # "default" → assembly/base, "lid" → lid only


def organic_box(
    length: float, width: float, height: float, corner_r: float,
    top_r: float = 0.0, bot_r: float = 0.0,
) -> cq.Workplane:
    r_v = min(corner_r, length / 2 - 0.5, width / 2 - 0.5)
    shape = cq.Workplane("XY").rect(length, width).extrude(height).edges("|Z").fillet(r_v)
    for sel, radius in [("<Z", bot_r), (">Z", top_r)]:
        if radius > 0.01:
            try:
                shape = shape.edges(sel).fillet(min(radius, r_v - 0.5, height / 2 - 0.5))
            except Exception:
                pass
    return shape


def rounded_cavity(length: float, width: float, height: float, radius: float) -> cq.Workplane:
    return cq.Workplane("XY").rect(length, width).extrude(height).edges("|Z").fillet(
        min(radius, length / 2 - 0.1, width / 2 - 0.1)
    )


# ── Base features ──────────────────────────────────────────────────


def _add_screw_pillars_base(base: cq.Workplane) -> cq.Workplane:
    """4 Schraubsäulen in den Eck-Innenbereichen mit Vorbohr-Loch von oben.

    Säule steht vom Floor (Z=FLOOR_T) bis PILLAR_BASE_TOP_Z (= 26.8mm in base coords).
    Bohrung von oben SCREW_PENETRATION+0.5mm tief mit SCREW_PILOT_D — selbstschneidend
    für 3.5er Spanplattenschraube. Säulenoberkante hat 0.2mm Lücke zum Lid-Hänger
    (PILLAR_BASE_TOP_Z_OFFSET) damit Lid auf Wandkante aufsitzt, nicht auf Säule.
    """
    pillar_h = PILLAR_BASE_TOP_Z - FLOOR_T
    pilot_depth = SCREW_PENETRATION + 0.5  # 0.5mm Sackloch-Reserve unter Schraubenspitze
    for cx, cy in PILLAR_POSITIONS:
        pillar = (cq.Workplane("XY")
                  .workplane(offset=FLOOR_T)
                  .center(cx, cy)
                  .circle(PILLAR_OD / 2)
                  .extrude(pillar_h))
        base = base.union(pillar)
        pilot = (cq.Workplane("XY")
                 .workplane(offset=PILLAR_BASE_TOP_Z + 0.01)
                 .center(cx, cy)
                 .circle(SCREW_PILOT_D / 2)
                 .extrude(-(pilot_depth + 0.02)))
        base = base.cut(pilot)
    return base


def _add_esp_cradle(base: cq.Workplane) -> cq.Workplane:
    """ESP32 cradle — board mounted UPSIDE DOWN (WROOM module faces floor).

    WROOM module (18×25.5×3.1mm) protrudes through a floor cutout for cooling.
    PCB edges rest on standoffs. Guide rails hold PCB. EN button through floor.
    """
    post_sz, rail_t = 3.5, 1.5
    # Standoff lifts PCB so module can protrude through floor
    guide_total = ESP_STANDOFF_H + ESP_H + ESP_GUIDE_H
    # Corner posts
    for dx, dy in [(-1, -1), (-1, 1), (1, -1), (1, 1)]:
        cx = ESP_POS_X + dx * (ESP_L / 2 - post_sz / 2)
        cy = ESP_POS_Y + dy * (ESP_W / 2 - post_sz / 2)
        post = cq.Workplane("XY").workplane(offset=FLOOR_T).center(cx, cy).rect(
            post_sz, post_sz
        ).extrude(ESP_STANDOFF_H)
        base = base.union(post)
    # Side guide rails (Y axis) — gekürzt auf 14mm in v5.8 für Eck-Säulen-Clearance.
    # 14mm ist mehr als ausreichend für Y-Führung des PCB; die Eck-Säulen bei
    # X=±58 dürfen nicht von den Rails (PCB-Rand bei Y=±15.95) überlappt werden.
    rail_len = 14.0
    for side in [-1, 1]:
        gy = ESP_POS_Y + side * (ESP_W / 2 + TOL_LOOSE + rail_t / 2)
        rail = cq.Workplane("XY").workplane(offset=FLOOR_T).center(ESP_POS_X, gy).rect(
            rail_len, rail_t
        ).extrude(guide_total)
        base = base.union(rail)
    # WROOM module pocket: hole in floor (16×18mm) with raised collar to guide module
    # Standoff=3.0mm, module=3.1mm → module bottom is 0.1mm below floor inner surface
    # Collar extends up from floor to meet the module and hold it aligned
    wroom_hole_w = 16.0 + 0.5   # 16mm across + clearance
    wroom_hole_l = 18.0 + 0.5   # 18mm along + clearance
    collar_wall = 1.5            # collar wall thickness
    collar_h = ESP_STANDOFF_H - (ESP_MODULE_H - FLOOR_T) + 1.0  # guide height above floor
    # Shield center: at non-antenna end of WROOM module
    antenna_end_x = ESP_POS_X + ESP_L / 2
    shield_start_x = antenna_end_x - 25.5  # module start
    wroom_x = shield_start_x + 18.0 / 2   # shield center
    wroom_y = ESP_POS_Y
    # Collar: raised ring around the hole
    collar_outer_w = wroom_hole_w + 2 * collar_wall
    collar_outer_l = wroom_hole_l + 2 * collar_wall
    collar = cq.Workplane("XY").workplane(offset=FLOOR_T).center(
        wroom_x, wroom_y
    ).rect(collar_outer_l, collar_outer_w).extrude(collar_h)
    collar_inner = cq.Workplane("XY").workplane(offset=FLOOR_T - 0.01).center(
        wroom_x, wroom_y
    ).rect(wroom_hole_l, wroom_hole_w).extrude(collar_h + 0.02)
    base = base.union(collar).cut(collar_inner)
    # Cut hole through floor
    wroom_cut = cq.Workplane("XY").workplane(offset=-0.01).center(
        wroom_x, wroom_y
    ).rect(wroom_hole_l, wroom_hole_w).extrude(FLOOR_T + 0.02)
    base = base.cut(wroom_cut)
    # EN reset button access hole through floor
    # Board upside down: USB at -X, EN is 6.1mm from USB end, 4.8mm from left edge (+Y)
    en_x = ESP_POS_X - ESP_L / 2 + ESP_EN_BTN_FROM_USB
    en_y = ESP_POS_Y - ESP_W / 2 + ESP_EN_BTN_FROM_EDGE  # -Y side (J2/EN side)
    btn_hole = cq.Workplane("XY").workplane(offset=-0.01).center(en_x, en_y).circle(
        ESP_EN_BTN_HOLE_D / 2
    ).extrude(FLOOR_T + 0.02)
    base = base.cut(btn_hole)
    return base


def _add_joystick_pillars(base: cq.Workplane) -> cq.Workplane:
    """4 pillar feet — USB cable routes between pillars (plug first, then seat joystick)."""
    _floor_overlap = 0.5
    pillar_d = 6.0       # thinner for USB plug clearance (1.7mm/side)
    base_flare_d = 9.0   # wider base for stability
    base_flare_h = 3.0   # flare height

    for dx in [-1, 1]:
        for dy in [-1, 1]:
            px = JOY_POS_X + dx * (JOY_HOLE_GRID_X / 2)
            py = JOY_POS_Y + dy * (JOY_HOLE_GRID_Y / 2)
            if py > INNER_POS_Y - 0.5:
                continue
            # Flared base for stability
            flare = cq.Workplane("XY").workplane(offset=FLOOR_T - _floor_overlap).center(
                px, py
            ).circle(base_flare_d / 2).workplane(offset=base_flare_h + _floor_overlap).circle(
                pillar_d / 2
            ).loft()
            # Main pillar shaft
            shaft = cq.Workplane("XY").workplane(offset=FLOOR_T + base_flare_h).center(
                px, py
            ).circle(pillar_d / 2).extrude(JOY_PLATFORM_H - base_flare_h)
            # Alignment pin on top (tapered for easy PCB insertion)
            pin = cq.Workplane("XY").workplane(offset=FLOOR_T + JOY_PLATFORM_H).center(
                px, py
            ).circle(JOY_PIN_D / 2).workplane(offset=JOY_PIN_H).circle(
                JOY_PIN_D / 2 - 0.2
            ).loft()
            base = base.union(flare).union(shaft).union(pin)
    return base


def _relieve_joystick_wall(base: cq.Workplane) -> cq.Workplane:
    if JOY_WALL_RELIEF_DEPTH <= 0.0:
        return base
    relief = cq.Workplane("XZ").workplane(offset=INNER_POS_Y).center(
        JOY_POS_X, FLOOR_T + JOY_PLATFORM_H + JOY_PCB_H / 2
    ).rect(JOY_PCB_L + 2.0, JOY_PCB_H + 2.4).extrude(JOY_WALL_RELIEF_DEPTH + 0.02)
    return base.cut(relief)


def _add_pressure_sensor_mount(base: cq.Workplane) -> cq.Workplane:
    """Bottom shelf on +X inner wall to support pressure sensor breakout board.

    PCB lies FLAT against +X inner wall. Shelf supports from below, lid retains above.
    """
    # Absolute positions (CadQuery coordinate rule)
    inner_x = PRES_INNER_X                          # = 66.0 (inner surface of +X wall)
    shelf_x_start = inner_x - PRES_MOUNT_DEPTH      # = 61.0
    shelf_z_bot = PRES_Z_BOT                         # = 8.0 (bottom of PCB)
    shelf_center_x = shelf_x_start + PRES_MOUNT_DEPTH / 2  # = 63.5
    # Create shelf as a box on the +X inner wall
    shelf = (
        cq.Workplane("XY")
        .workplane(offset=shelf_z_bot)  # Z = 8.0
        .center(shelf_center_x, PRES_POS_Y)  # X=63.5, Y=0.0
        .box(PRES_MOUNT_DEPTH, PRES_PCB_H, PRES_SHELF_T, centered=[True, True, False])
    )
    return base.union(shelf)


def _cut_pressure_barb_port(base: cq.Workplane) -> cq.Workplane:
    """Barb hole through +X wall for pressure sensor nipple (press-fit).

    Nipple estimated at ~5mm from PCB top edge, ~4mm from right edge.
    """
    # Absolute positions (CadQuery coordinate rule)
    nipple_z = PRES_NIPPLE_Z   # = 23.0
    nipple_y = PRES_NIPPLE_Y   # = 3.5
    wall_x = OUTER_POS_X       # = 68.0 (outer surface of +X wall)

    # YZ workplane normal is +X: offset=wall_x places plane at X=+68
    # Extrude negative goes into the wall (-X direction)
    hole = (
        cq.Workplane("YZ")
        .workplane(offset=wall_x + 0.01)  # at outer +X surface
        .center(nipple_y, nipple_z)
        .circle(PRES_BARB_HOLE_D / 2)
        .extrude(-(WALL + 0.02))  # through the wall into the enclosure
    )
    base = base.cut(hole)

    # Exterior chamfer — conical entry on outside of +X wall
    try:
        chamfer = (
            cq.Workplane("YZ")
            .workplane(offset=wall_x + 0.01)  # at outer +X surface
            .center(nipple_y, nipple_z)
            .circle(PRES_BARB_CHAMFER_D / 2)
            .workplane(offset=-1.0)  # 1mm into the wall
            .circle(PRES_BARB_HOLE_D / 2)
            .loft()
        )
        base = base.cut(chamfer)
    except Exception:
        pass
    return base


def _cut_usb_cable_notch(base: cq.Workplane) -> cq.Workplane:
    """Cut a notch in the +Y wall at seam height for USB cable exit."""
    # +Y wall: offset=-OUTER_POS_Y places plane at Y=+25 (outer +Y surface)
    # Extrude positive to cut through wall toward -Y (into cavity)
    notch = cq.Workplane("XZ").workplane(offset=-OUTER_POS_Y - 0.01).center(
        USB_NOTCH_X, EXT_H_BASE - USB_NOTCH_H / 2
    ).rect(USB_NOTCH_W, USB_NOTCH_H).extrude(WALL + 0.02)
    return base.cut(notch)


def _cut_usb_plug_channel(base: cq.Workplane) -> cq.Workplane:
    """Cut a channel in the joystick platform for USB Micro-B plug access."""
    plug_z = FLOOR_T + ESP_STANDOFF_H + ESP_H / 2 + 1.5
    ch_x0 = JOY_PLATFORM_MIN_X - 0.5  # 0.5mm overlap past platform face
    ch_x1 = JOY_PLATFORM_MIN_X + USB_PLUG_DEPTH
    channel = cq.Workplane("XY").workplane(offset=plug_z - USB_PLUG_H / 2).center(
        (ch_x0 + ch_x1) / 2, ESP_POS_Y
    ).rect(ch_x1 - ch_x0, USB_PLUG_W).extrude(USB_PLUG_H)
    return base.cut(channel)


def _add_mic_mount(base: cq.Workplane) -> cq.Workplane:
    nut_ac_tol = MIC_NUT_SW_TOL / math.cos(math.radians(30))
    # Overlap collar 0.5mm into wall to avoid OCCT coplanar-face boolean failure
    _collar_overlap = 0.5
    collar = cq.Workplane("YZ").workplane(offset=MIC_WALL_INNER_X - _collar_overlap).center(
        MIC_POS_Y, MIC_POS_Z
    ).circle(MIC_COLLAR_D / 2).extrude(MIC_NUT_POCKET_D + _collar_overlap)
    try:
        collar = collar.faces(">X").chamfer(1.0)
    except Exception:
        pass
    base = base.union(collar)
    bolt_hole = cq.Workplane("YZ").workplane(offset=MIC_WALL_OUTER_X - 0.01).center(
        MIC_POS_Y, MIC_POS_Z
    ).circle(MIC_CLEAR_D / 2).extrude(WALL + 0.02)
    pocket = cq.Workplane("YZ").workplane(offset=MIC_COLLAR_INNER_X + 0.01).center(
        MIC_POS_Y, MIC_POS_Z
    ).polygon(6, nut_ac_tol).extrude(-(MIC_NUT_POCKET_D + 0.02))
    return base.cut(bolt_hole).cut(pocket)


def _cut_vent_slots(base: cq.Workplane) -> cq.Workplane:
    """Cut vent slots through -Y wall (offset positive, extrude negative)."""
    for idx in range(VENT_N):
        slot_x = (idx - (VENT_N - 1) / 2.0) * VENT_PITCH
        vent = cq.Workplane("XZ").workplane(offset=OUTER_POS_Y + 0.01).center(
            slot_x, EXT_H_BASE * 0.55
        ).rect(VENT_W, VENT_LEN).extrude(-(WALL + 0.02))
        base = base.cut(vent)
    return base


# ── Assembly ───────────────────────────────────────────────────────


def make_base() -> cq.Workplane:
    base = organic_box(EXT_X, EXT_Y, EXT_H_BASE, CORNER_R, bot_r=BASE_BOT_R)
    cavity = rounded_cavity(CAV_X, CAV_Y, BASE_INNER_H + 1.0, INNER_R).translate((0, 0, FLOOR_T))
    base = base.cut(cavity)
    for fn in [
        _add_screw_pillars_base,
        _add_esp_cradle,
        _add_joystick_pillars,
        _add_pressure_sensor_mount,
        _cut_pressure_barb_port,
        _cut_usb_cable_notch,
        _add_mic_mount,
    ]:
        base = fn(base)
    return base


def make_lid() -> cq.Workplane:
    lip_x, lip_y = CAV_X - 2 * LIP_GAP, CAV_Y - 2 * LIP_GAP
    lip_r = max(0.5, INNER_R - LIP_GAP)
    lid = organic_box(EXT_X, EXT_Y, EXT_H_LID, CORNER_R, top_r=LID_TOP_R)
    lid = lid.cut(rounded_cavity(CAV_X, CAV_Y, LID_INNER_H + 0.01, INNER_R))
    # Two-zone inner wall for overhang-free printing (flipped, ceiling-down):
    # 1. LIP zone (Z=-LIP_H to Z=0): at lip_x dimensions, inserts into base
    #    with LIP_GAP clearance. This is the functional retention lip.
    # 2. SUPPORT zone (Z=0 to Z=LID_INNER_H): at CAV_X dimensions, flush with
    #    cavity inner wall. Stays inside the lid body, never enters the base.
    #    Provides continuous wall from ceiling to lip — no overhang at Z=9 in print.
    # Lip (lower zone — inserts into base)
    lip_outer = cq.Workplane("XY").workplane(offset=-LIP_H).rect(
        lip_x, lip_y
    ).extrude(LIP_H).edges("|Z").fillet(lip_r)
    lip_inner = cq.Workplane("XY").workplane(offset=-LIP_H - 0.01).rect(
        lip_x - 2 * LIP_T, lip_y - 2 * LIP_T
    ).extrude(LIP_H + 0.02).edges("|Z").fillet(max(0.3, lip_r - LIP_T))
    lid = lid.union(lip_outer.cut(lip_inner))
    # Support wall (upper zone — flush with cavity, stays in lid)
    support_outer = cq.Workplane("XY").rect(
        CAV_X, CAV_Y
    ).extrude(LID_INNER_H).edges("|Z").fillet(INNER_R)
    support_inner = cq.Workplane("XY").workplane(offset=-0.01).rect(
        CAV_X - 2 * LIP_T, CAV_Y - 2 * LIP_T
    ).extrude(LID_INNER_H + 0.02).edges("|Z").fillet(max(0.3, INNER_R - LIP_T))
    lid = lid.union(support_outer.cut(support_inner))
    # Joystick opening — circular, only rotation circle of stick
    # Offset compensates for observed housing position vs lid hole
    joy_hole_x = JOY_POS_X + JOY_LID_HOLE_OFFSET_X
    joy_hole_y = JOY_POS_Y + JOY_LID_HOLE_OFFSET_Y
    joy_cut = (cq.Workplane("XY").workplane(offset=-LIP_H - 0.01)
               .center(joy_hole_x, joy_hole_y)
               .circle(JOY_LID_HOLE_D / 2)
               .extrude(EXT_H_LID + LIP_H + 0.02))
    lid = lid.cut(joy_cut)
    try:
        # Chamfer on exterior edge — 2mm wide bevel for clean look
        joy_chamfer_outer = (cq.Workplane("XY").workplane(offset=EXT_H_LID - 0.01)
                             .center(joy_hole_x, joy_hole_y)
                             .circle(JOY_LID_HOLE_D / 2 + 2.0)
                             .workplane(offset=-2.0)
                             .circle(JOY_LID_HOLE_D / 2)
                             .loft())
        lid = lid.cut(joy_chamfer_outer)
    except Exception:
        pass
    # Schraubsäulen-Hänger: 4 hängende Säulen von Lid-Decke bis Lip-Boden.
    # Lid-Koord: hanger Z=-LIP_H bis Z=LID_INNER_H (= -3..7), also 10mm Hängerlänge.
    # Bohrung durchgehend von Z=EXT_H_LID (Lid-Außen oben) bis Z=-LIP_H (Lip-Boden).
    # Senkkopf-Senkung an der Außenseite (Z=EXT_H_LID nach unten SCREW_HEAD_H tief).
    hanger_z_bot = -LIP_H
    hanger_z_top = LID_INNER_H
    hanger_h = hanger_z_top - hanger_z_bot
    csk_z_top = EXT_H_LID
    bore_total = csk_z_top - hanger_z_bot  # 12.0mm Bohrungslänge durch Lid+Hänger
    for cx, cy in PILLAR_POSITIONS:
        hanger = (cq.Workplane("XY")
                  .workplane(offset=hanger_z_bot)
                  .center(cx, cy)
                  .circle(PILLAR_OD / 2)
                  .extrude(hanger_h))
        lid = lid.union(hanger)
        clear_hole = (cq.Workplane("XY")
                      .workplane(offset=csk_z_top + 0.01)
                      .center(cx, cy)
                      .circle(SCREW_CLEAR_D / 2)
                      .extrude(-(bore_total + 0.02)))
        lid = lid.cut(clear_hole)
        try:
            csk = (cq.Workplane("XY")
                   .workplane(offset=csk_z_top + 0.01)
                   .center(cx, cy)
                   .circle(SCREW_CSK_D / 2)
                   .workplane(offset=-(SCREW_HEAD_H + 0.01))
                   .circle(SCREW_CLEAR_D / 2)
                   .loft())
            lid = lid.cut(csk)
        except Exception:
            pass
    # ESP32 hold-down: continuous wall hangs from lid ceiling, presses PCB onto standoffs.
    # Runs along X axis between pin header rows (3mm Y width).
    # A wall is much stronger than isolated pillars — FDM layers run unbroken.
    # Wires route on both sides (+Y and -Y of wall).
    esp_pcb_top_z = FLOOR_T + ESP_STANDOFF_H + ESP_H  # 6.2mm in base coords
    rib_bot_z = -(EXT_H_BASE - esp_pcb_top_z - HOLD_DOWN_CLEARANCE)  # -22.8mm in lid coords (1mm shorter)
    rib_height = LID_INNER_H - rib_bot_z  # 29.8mm total
    wall_len, wall_t = 24.0, 3.0
    wall = (cq.Workplane("XY")
            .workplane(offset=rib_bot_z)
            .center(ESP_POS_X, ESP_POS_Y)
            .rect(wall_len, wall_t)
            .extrude(rib_height))
    lid = lid.union(wall)
    # Triangular gussets on both sides of wall where it meets the ceiling.
    # Each gusset: 5mm along Y (out from wall), 5mm along Z (down from ceiling).
    gusset_h, gusset_d = 5.0, 5.0  # height (Z) and depth (Y)
    wall_top_z = LID_INNER_H  # ceiling in lid coords
    wall_x_start = ESP_POS_X - wall_len / 2  # = 23.0 (ESP32 area, must be +X)
    assert wall_x_start > 0, f"wall_x_start={wall_x_start} must be positive (+X = ESP32 side)"
    for side in [-1, 1]:
        gy = ESP_POS_Y + side * wall_t / 2  # wall surface Y
        gusset = (cq.Workplane("YZ")
                  .workplane(offset=wall_x_start)
                  .moveTo(gy, wall_top_z)
                  .lineTo(gy + side * gusset_d, wall_top_z)
                  .lineTo(gy, wall_top_z - gusset_h)
                  .close()
                  .extrude(wall_len))
        lid = lid.union(gusset)
    # USB cable relief — notch in lid lip on +Y side matching base notch
    cable_relief = cq.Workplane("XZ").workplane(offset=-OUTER_POS_Y - 0.01).center(
        USB_NOTCH_X, -LIP_H / 2
    ).rect(USB_NOTCH_W, LIP_H + 0.02).extrude(WALL + LIP_GAP + LIP_T + 0.02)
    lid = lid.cut(cable_relief)
    # No lid vents — WROOM floor cutout provides ventilation
    return lid


# ── Export ─────────────────────────────────────────────────────────


def export_stl(shape: cq.Workplane, filepath: Path) -> None:
    cq.exporters.export(shape, str(filepath), exportType="STL", tolerance=0.01, angularTolerance=0.1)


def _parse_svg_path(path_data: str) -> list[tuple[float, float]]:
    tokens = re.findall(r"[ML]|-?\d+(?:\.\d+)?", path_data)
    points: list[tuple[float, float]] = []
    idx = 0
    while idx < len(tokens):
        if tokens[idx] in {"M", "L"}:
            points.append((float(tokens[idx + 1]), float(tokens[idx + 2])))
            idx += 3
        else:
            idx += 1
    return points


def _rgb(stroke: str) -> tuple[int, int, int]:
    match = re.match(r"rgb\((\d+),(\d+),(\d+)\)", stroke.replace(" ", ""))
    return (int(match.group(1)), int(match.group(2)), int(match.group(3))) if match else (0, 0, 0)


def _collect_svg_lines(
    node: ET.Element,
    stroke: str,
    hidden: bool,
    lines: list[tuple[tuple[float, float], tuple[float, float], tuple[int, int, int], bool]],
) -> None:
    tag = node.tag.rsplit("}", 1)[-1]
    stroke = node.attrib.get("stroke", stroke)
    hidden = hidden or "stroke-dasharray" in node.attrib
    if tag == "path":
        points = _parse_svg_path(node.attrib.get("d", ""))
        for start, end in pairwise(points):
            lines.append((start, end, _rgb(stroke), hidden))
    for child in list(node):
        _collect_svg_lines(child, stroke, hidden, lines)


def _svg_to_png(svg_path: Path, png_path: Path, width: int = 1400, height: int = 1000) -> None:
    root = ET.fromstring(svg_path.read_text())
    lines: list[tuple[tuple[float, float], tuple[float, float], tuple[int, int, int], bool]] = []
    _collect_svg_lines(root, "rgb(0,0,0)", False, lines)
    xs = [point[0] for line in lines for point in line[:2]]
    ys = [point[1] for line in lines for point in line[:2]]
    min_x, max_x = min(xs), max(xs)
    min_y, max_y = min(ys), max(ys)
    pad = 60
    scale = min(
        (width - 2 * pad) / max(max_x - min_x, 1.0),
        (height - 2 * pad) / max(max_y - min_y, 1.0),
    )

    def map_point(point: tuple[float, float]) -> tuple[float, float]:
        return (pad + (point[0] - min_x) * scale, height - (pad + (point[1] - min_y) * scale))

    image = Image.new("RGB", (width, height), "white")
    draw = ImageDraw.Draw(image)
    for hidden_pass in [True, False]:
        for start, end, color, is_hidden in lines:
            if is_hidden == hidden_pass:
                draw.line(
                    [map_point(start), map_point(end)],
                    fill=color,
                    width=1 if hidden_pass else 3,
                )
    image.save(png_path)
    svg_path.unlink(missing_ok=True)


def _assembly_shape(base: cq.Workplane, lid: cq.Workplane) -> cq.Shape:
    return cq.Compound.makeCompound([base.val(), lid.translate((0, 0, EXT_H_BASE)).val()])


def render_pngs(base: cq.Workplane, lid: cq.Workplane, outdir: Path) -> None:
    views = [
        RenderView("mundmaus_v58_assembly.png", (1.0, -1.0, 0.8), True),
        RenderView("mundmaus_v58_top.png", (0.0, 0.0, 1.0), True),
        RenderView("mundmaus_v58_side.png", (0.0, 1.0, 0.0), False),
        RenderView("mundmaus_v58_back.png", (-1.0, 0.0, 0.0), False),
        RenderView("mundmaus_v58_lid_underside.png", (0.0, 0.0, -1.0), False, target="lid"),
    ]
    assembly = _assembly_shape(base, lid)
    for view in views:
        svg_path = outdir / view.filename.replace(".png", ".svg")
        if view.target == "lid":
            shape = lid
        elif view.assembled:
            shape = assembly
        else:
            shape = base
        cq.exporters.export(
            shape,
            str(svg_path),
            opt={
                "width": 1400,
                "height": 1000,
                "projectionDir": view.projection_dir,
                "showHidden": True,
            },
        )
        _svg_to_png(svg_path, outdir / view.filename)


# ── Report ─────────────────────────────────────────────────────────


def write_report(report_path: Path) -> None:
    pillar_corner_clearance = INNER_R - _PILLAR_CORNER_DIST - PILLAR_OD / 2
    base_pillar_height = PILLAR_BASE_TOP_Z - FLOOR_T
    screw_total_engagement = (EXT_H_BASE + EXT_H_LID) - (PILLAR_BASE_TOP_Z - SCREW_PENETRATION)
    report = textwrap.dedent(
        f"""\
        # MundMaus v5.8 Enclosure — Schraub-Verschluss (Spax 3.5x20)
        ## Summary
        v5.8 ersetzt den Detent-Klick-Verschluss aus v5.7 durch eine echte Schraub-
        verbindung mit 4 Spax 3.5x20 Senkkopf-Spanplattenschrauben in den Eck-
        Innenbereichen. Detent-Ridges/Grooves vollständig entfernt.

        Geometrie:
        - 4 Schraubsäulen im Base bei (±{PILLAR_X:.0f}, ±{PILLAR_Y:.1f}), D={PILLAR_OD:.1f}mm,
          Vorbohr-Loch {SCREW_PILOT_D:.1f}mm.
        - 4 hängende Säulen im Lid (gleiche XY-Position) mit Durchgangsloch {SCREW_CLEAR_D:.1f}mm
          und Senkung {SCREW_CSK_D:.1f}mm × {SCREW_HEAD_H:.1f}mm tief an der Lid-Außenseite.
        - ESP-Side-Guide-Rails von ESP_L*0.4 (21.8mm) auf 14.0mm gekürzt — Rails standen
          sonst im Weg der +X- und +Y-Eck-Säulen.
        - Lip ({LIP_H:.1f}mm) bleibt zur Zentrierung beim Zusammenbau und für Staubdichtigkeit.

        ## Schrauben-Tiefenrechnung
        | Strecke | Wert |
        |---|---:|
        | Schraubenlänge gesamt | {SCREW_LEN:.1f} mm |
        | Senkung im Lid (Kopf bündig) | {SCREW_HEAD_H:.1f} mm |
        | Lid-Korpus durchquert (Decke + Lip-Hänger) | {EXT_H_LID + LIP_H:.1f} mm |
        | Eindringtiefe in Base-Säule | {SCREW_PENETRATION:.1f} mm |
        | Summe | {SCREW_HEAD_H + EXT_H_LID + LIP_H + SCREW_PENETRATION:.1f} mm |
        | Säulenoberkante Z (base coords) | {PILLAR_BASE_TOP_Z:.1f} mm |
        | Spiel Säulen-Top zu Lid-Hänger-Boden | {PILLAR_BASE_TOP_Z_OFFSET:.1f} mm |
        | Boden-Reserve unter Bohrung | {(PILLAR_BASE_TOP_Z - SCREW_PENETRATION) - FLOOR_T:.1f} mm |
        | Säulen-Kollisions-Abstand zur Eckkurve | {pillar_corner_clearance:.2f} mm |

        ## Komponenten-Layout (unverändert von v5.7)
        - Mic mount collar: -X wall (internal, {MIC_COLLAR_INNER_X:.1f} inner edge)
        - Joystick center: X={JOY_POS_X:.1f} (platform {JOY_PLATFORM_MIN_X:.1f} to {JOY_PLATFORM_MAX_X:.1f})
        - ESP32 center: X={ESP_POS_X:.1f} (PCB {ESP_LEFT_EDGE_X:.1f} to {ESP_RIGHT_EDGE_X:.1f}, USB at -X end)
        - Sensor shelf: +X inner wall, shelf X={PRES_SHELF_X_START:.1f} to {PRES_INNER_X:.1f}, Z={PRES_Z_BOT:.1f} to {PRES_Z_TOP:.1f}

        ## Clearance Analysis
        | Item | Value |
        |---|---:|
        | Lip zone bottom | {LIP_ZONE_BOTTOM:.1f} mm |
        | Sensor PCB top to lip zone | {LIP_ZONE_BOTTOM - PRES_Z_TOP:.1f} mm |
        | Mic collar to joystick platform | {COLLAR_TO_JOY_CLEARANCE:.2f} mm |
        | ESP32 right edge to +X inner wall | {ESP_TO_WALL_CLEARANCE:.2f} mm |
        | Sensor bottom Z to ESP32 PCB top Z | {PRES_ESP_Z_GAP:.1f} mm |
        | Hold-down wall gap (lid closed) | {HOLD_DOWN_CLEARANCE:.1f} mm |
        | Barb hole diameter | {PRES_BARB_HOLE_D:.1f} mm (press-fit) |
        | Pressure barb wall | +X |
        | Lid attachment | 4 Schrauben Spax 3.5x{SCREW_LEN:.0f} Senkkopf |

        ## Changes vs v5.7
        | Feature | v5.7 | v5.8 |
        |---|---|---|
        | Verschluss | Detent-Klick (7 Ridges/Grooves) | 4× Schraube Spax 3.5x20 |
        | RIDGE_H/GROOVE_D | 0.6 / 0.55 mm | entfallen |
        | Base-Säulen | — | 4× D={PILLAR_OD:.0f}mm, h={base_pillar_height:.1f}mm, Bohrung {SCREW_PILOT_D:.1f}mm |
        | Lid-Säulen-Hänger | — | 4× D={PILLAR_OD:.0f}mm, h={LID_INNER_H + LIP_H:.1f}mm, Senkung {SCREW_CSK_D:.1f}/{SCREW_HEAD_H:.1f} |
        | ESP-Side-Rails | 21.8 mm | 14.0 mm |
        | Base STL | v5.6 unchanged | NEU (Säulen + kürzere Rails) |
        | Lid STL | v5.7 | NEU (Hänger + Senkungen, ohne Detents) |

        ## External Dimensions
        - Base footprint: {EXT_X:.1f} x {EXT_Y:.1f} mm
        - Closed enclosure height: {EXT_H_BASE + EXT_H_LID:.1f} mm
        - Joystick protrusion above lid: {STICK_PROTRUSION:.1f} mm

        ## Print Notes
        - Material: PETG preferred, PLA acceptable for quick fit checks
        - Base orientation: floor-down, no support intended
        - Lid orientation: flip 180 deg, ceiling-down. Senkungen liegen damit an der Druckplatte;
          die 40°-Konuswand druckt support-frei (Material drumherum, nicht darüber).
        - Schrauben: 4× Spax/Spanplattenschraube 3.5×20 mm Senkkopf, Torx oder Kreuzschlitz.
          In PETG selbstschneidend — kein Brass-Insert nötig.
        - Anzugsmoment: handfest, nicht überdrehen (PETG-Säulenwand 1.75mm).
        - USB cable: plug Micro-USB with lid off, route cable to -Y wall notch, close lid.
        - External hose path: mouthpiece -> +X wall barb (straight run, minimal bending).
        - Pressure sensor: place PCB flat against +X inner wall, nipple through barb hole, lid retains from above.
        - The -X collar remains internal-only; the outer -X wall stays flat for the mic stand.
        - Suggested slicer baseline: 0.2 mm layer height, 4 walls, 25% gyroid, 240 C nozzle, 75 C bed, 40% fan.
        """
    )
    report_path.write_text(report)


# ── Main ───────────────────────────────────────────────────────────


def main() -> None:
    parser = argparse.ArgumentParser(description="MundMaus v5.8 enclosure (Schrauben statt Detent)")
    parser.add_argument("--outdir", default=".", type=str)
    parser.add_argument("--skip-renders", action="store_true")
    args = parser.parse_args()
    outdir = Path(args.outdir)
    outdir.mkdir(parents=True, exist_ok=True)

    base_path = outdir / "mundmaus_v58_base.stl"
    lid_path = outdir / "mundmaus_v58_lid.stl"
    base_step_path = outdir / "mundmaus_v58_base.step"
    lid_step_path = outdir / "mundmaus_v58_lid.step"
    report_path = outdir / "mundmaus_v58_report.md"

    print(f"MundMaus v5.8 — CadQuery {cq.__version__}")
    print(f"  External: {EXT_X:.1f} x {EXT_Y:.1f} x {EXT_H_BASE + EXT_H_LID:.1f} mm")
    print(f"  Schrauben: 4x Spax {SCREW_THREAD_D}x{SCREW_LEN:.0f} Senkkopf in den 4 Ecken")
    print(f"  Säulen: D={PILLAR_OD}mm bei (±{PILLAR_X}, ±{PILLAR_Y}), Vorbohr-Loch {SCREW_PILOT_D}mm")

    base = make_base()
    lid = make_lid()

    # STEP first (R9 — STEP ist Quelle der Wahrheit)
    cq.exporters.export(base, str(base_step_path), exportType="STEP")
    cq.exporters.export(lid, str(lid_step_path), exportType="STEP")

    export_stl(base, base_path)
    # Flip lid for printing — explicit rotation to avoid rotateAboutCenter Y-offset bug
    lid_flipped = lid.rotate((0, 0, 0), (1, 0, 0), 180)
    bb = lid_flipped.val().BoundingBox()
    lid_flipped = lid_flipped.translate((0, 0, -bb.zmin))
    export_stl(lid_flipped, lid_path)

    write_report(report_path)
    if not args.skip_renders:
        render_pngs(base, lid, outdir)
    print("Done.")


if __name__ == "__main__":
    main()
