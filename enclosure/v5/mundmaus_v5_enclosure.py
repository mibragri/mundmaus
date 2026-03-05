#!/usr/bin/env python3
"""
MundMaus Enclosure v5 — Landscape Layout for Lying Patient
CadQuery parametric design for FDM (Bambu Lab P1S, PETG)

v5 KEY CHANGE: Landscape (wide) orientation.
  Problem: v4.2 had 71mm vertical extent blocking patient's field of view.
  Solution: Components side-by-side along X axis. Mount at top (+Y wall).
  Result: EXT_Y reduced from 71mm to 50mm (30% reduction).

Layout (top view, patient lies below looking up):

  +Y wall (TOP — gooseneck mount attaches here)
  +------------------------------------------------------+
  | [Sensor]  [Joystick]  oMounto     [ESP32 -->USB]     |
  +------------------------------------------------------+
  -Y wall (BOTTOM — vent slots, closest to patient below)

  X axis = horizontal spread (136mm external)
  Y axis = vertical in patient's view (50mm external — minimized!)
  Z axis = toward/away from patient's face (41mm, unchanged)

Hardware (same as v4.2):
  - ESP32-S3 DevKitC-1 (54.4 x 27.9 mm, USB-C on short side)
  - KY-023 Joystick (34 x 26 mm PCB, stick 17mm above PCB)
  - MPS20N0040D-S + HX710B Pressure Sensor (20 x 15 x 5 mm)
  - 3/8"-16 UNC Mic Stand Mount (hex nut SW 14.29mm)

Usage:
  python3 mundmaus_v5_enclosure.py                    # export both
  python3 mundmaus_v5_enclosure.py --part base        # base only
  python3 mundmaus_v5_enclosure.py --part lid         # lid only
  python3 mundmaus_v5_enclosure.py --outdir /path/    # output directory
"""

import cadquery as cq
import math
import argparse
from pathlib import Path


# =====================================================================
# Parameters — all dimensions in mm
# =====================================================================

# --- Internal Cavity (LANDSCAPE: wide X, narrow Y) ---
CAV_X = 130.0         # internal cavity length (X axis) — wide
CAV_Y = 44.0          # internal cavity width  (Y axis) — narrow!
WALL  = 3.0           # wall thickness

# --- Wall Structure ---
FLOOR_T = 3.0         # base floor thickness
CEIL_T  = 3.0         # lid ceiling thickness
INNER_R = 2.5         # internal corner fillet radius

# --- Base / Lid Split ---
BASE_INNER_H = 28.0   # base internal depth
LID_INNER_H  = 7.0    # lid internal depth

# --- Organic Form ---
CORNER_R      = 12.0  # vertical edge fillet
LID_TOP_R     = 3.5   # lid top edge fillet
BASE_BOT_R    = 2.0   # base bottom edge fillet

# --- Lid Joint (lip insertion) ---
LIP_H   = 4.0         # lip insertion depth
LIP_T   = 1.8         # lip wall thickness
LIP_GAP = 0.15        # clearance per side (PETG)

# --- Tolerances (PETG) ---
TOL       = 0.2       # sliding fit per side
TOL_LOOSE = 0.3       # clearance fit per side

# --- ESP32-S3 DevKitC-1 ---
ESP_L          = 54.4   # PCB length (along X)
ESP_W          = 27.9   # PCB width  (along Y)
ESP_H          = 1.2    # PCB thickness
ESP_STANDOFF_H = 3.0    # standoff height below PCB
ESP_GUIDE_H    = 3.0    # guide wall height above PCB
ESP_POS_X = 35.0        # RIGHT side, USB-C faces +X wall
ESP_POS_Y = -2.0        # offset toward -Y to clear collar

# --- KY-023 Joystick ---
JOY_PCB_L      = 34.0
JOY_PCB_W      = 26.0
JOY_PCB_H      = 1.6
JOY_HOUSING    = 16.0
JOY_STICK_H    = 17.0
JOY_PLATFORM_H = 15.0
JOY_PIN_D      = 2.8
JOY_PIN_H      = 3.0
JOY_OPENING    = 17.0
JOY_POS_X = -15.0       # CENTER-LEFT
JOY_POS_Y = -4.0        # offset toward -Y to clear collar

# --- Pressure Sensor MPS20N0040D-S ---
PRES_L = 20.0
PRES_W = 15.0
PRES_H = 5.0
PRES_POS_X = -48.0      # FAR LEFT
PRES_POS_Y = -2.0

# --- Tube Feedthrough ---
TUBE_HOLE_D = 6.5
TUBE_POS_Y  = PRES_POS_Y
TUBE_POS_Z  = 13.0

# --- USB-C Cutout ---
USB_W       = 9.5
USB_H       = 4.0
USB_CHAMFER = 1.0
USB_POS_Z   = 5.5

# --- M3 Screw Bosses ---
SCREW_D       = 3.4
SCREW_BOSS_D  = 7.0
SCREW_BOSS_H  = 10.0
SCREW_PILOT_D = 2.5
SCREW_INSET   = 6.0

# --- 3/8"-16 UNC Mic Stand Mount — ON +Y WALL (TOP) ---
MIC_CLEAR_D      = 10.5
MIC_NUT_SW       = 14.29
MIC_NUT_H        = 5.56
MIC_NUT_TOL      = 0.2
MIC_NUT_POCKET_D = 7.9
MIC_COLLAR_D     = 24.0
MIC_POS_X        = 0.0

# --- Ventilation ---
VENT_N       = 6
VENT_W       = 1.6
VENT_LEN     = 14.0
VENT_PITCH   = 6.0


# =====================================================================
# Derived Dimensions
# =====================================================================

EXT_X      = CAV_X + 2 * WALL           # 136.0
EXT_Y      = CAV_Y + 2 * WALL           # 50.0  (was 71.0!)
EXT_H_BASE = FLOOR_T + BASE_INNER_H     # 31.0
EXT_H_LID  = CEIL_T + LID_INNER_H       # 10.0

MIC_POS_Z  = EXT_H_BASE / 2             # 15.5

SCREW_POSITIONS = [
    ( CAV_X / 2 - SCREW_INSET,  CAV_Y / 2 - SCREW_INSET),
    ( CAV_X / 2 - SCREW_INSET, -CAV_Y / 2 + SCREW_INSET),
    (-CAV_X / 2 + SCREW_INSET,  CAV_Y / 2 - SCREW_INSET),
    (-CAV_X / 2 + SCREW_INSET, -CAV_Y / 2 + SCREW_INSET),
]

MIC_NUT_AC = MIC_NUT_SW / math.cos(math.radians(30))
MIC_NUT_SW_TOL = MIC_NUT_SW + 2 * MIC_NUT_TOL
MIC_SHELF_W = (MIC_NUT_SW_TOL - MIC_CLEAR_D) / 2


# =====================================================================
# Helper Functions
# =====================================================================

def organic_box(
    length: float, width: float, height: float,
    corner_r: float, top_r: float = 0.0, bot_r: float = 0.0,
) -> cq.Workplane:
    """Organically rounded box — MundMaus design language."""
    r_v = min(corner_r, length / 2 - 0.5, width / 2 - 0.5)
    result = (
        cq.Workplane("XY").rect(length, width)
        .extrude(height).edges("|Z").fillet(r_v)
    )
    if bot_r > 0.01:
        r_b = min(bot_r, r_v - 0.5, height / 2 - 0.5)
        try:
            result = result.edges("<Z").fillet(r_b)
        except Exception:
            pass
    if top_r > 0.01:
        r_t = min(top_r, r_v - 0.5, height / 2 - 0.5)
        try:
            result = result.edges(">Z").fillet(r_t)
        except Exception:
            pass
    return result


def rounded_cavity(
    length: float, width: float, height: float, radius: float,
) -> cq.Workplane:
    """Rectangular cavity with vertical edge fillets."""
    r = min(radius, length / 2 - 0.1, width / 2 - 0.1)
    return (
        cq.Workplane("XY").rect(length, width)
        .extrude(height).edges("|Z").fillet(r)
    )


# =====================================================================
# BASE — individual feature functions
# =====================================================================

def _add_screw_bosses(base: cq.Workplane) -> cq.Workplane:
    for px, py in SCREW_POSITIONS:
        boss = (
            cq.Workplane("XY").workplane(offset=FLOOR_T)
            .center(px, py).circle(SCREW_BOSS_D / 2)
            .extrude(SCREW_BOSS_H)
        )
        pilot = (
            cq.Workplane("XY").workplane(offset=FLOOR_T - 0.01)
            .center(px, py).circle(SCREW_PILOT_D / 2)
            .extrude(SCREW_BOSS_H + 0.02)
        )
        base = base.union(boss).cut(pilot)
    return base


def _add_esp_cradle(base: cq.Workplane) -> cq.Workplane:
    """ESP32 rail-cradle: corner posts + side guide rails + end stop."""
    post_sz = 3.5
    rail_t = 1.5
    guide_total = ESP_STANDOFF_H + ESP_H + ESP_GUIDE_H

    corners = [
        (ESP_POS_X - ESP_L / 2 + post_sz / 2,
         ESP_POS_Y - ESP_W / 2 + post_sz / 2),
        (ESP_POS_X - ESP_L / 2 + post_sz / 2,
         ESP_POS_Y + ESP_W / 2 - post_sz / 2),
        (ESP_POS_X + ESP_L / 2 - post_sz / 2,
         ESP_POS_Y - ESP_W / 2 + post_sz / 2),
        (ESP_POS_X + ESP_L / 2 - post_sz / 2,
         ESP_POS_Y + ESP_W / 2 - post_sz / 2),
    ]
    for cx, cy in corners:
        post = (
            cq.Workplane("XY").workplane(offset=FLOOR_T)
            .center(cx, cy).rect(post_sz, post_sz)
            .extrude(ESP_STANDOFF_H)
        )
        base = base.union(post)

    for side in [-1, 1]:
        gy = ESP_POS_Y + side * (ESP_W / 2 + TOL_LOOSE + rail_t / 2)
        rail = (
            cq.Workplane("XY").workplane(offset=FLOOR_T)
            .center(ESP_POS_X, gy)
            .rect(ESP_L * 0.55, rail_t)
            .extrude(guide_total)
        )
        base = base.union(rail)

    stop_x = ESP_POS_X - ESP_L / 2 - TOL_LOOSE - rail_t / 2
    stop = (
        cq.Workplane("XY").workplane(offset=FLOOR_T)
        .center(stop_x, ESP_POS_Y)
        .rect(rail_t, ESP_W * 0.55)
        .extrude(guide_total)
    )
    base = base.union(stop)
    return base


def _add_joystick_platform(base: cq.Workplane) -> cq.Workplane:
    """Raised platform for KY-023 with snap-fit locating pins."""
    plat_x = JOY_PCB_L + 5.0
    plat_y = JOY_PCB_W + 5.0

    platform = (
        cq.Workplane("XY").workplane(offset=FLOOR_T)
        .center(JOY_POS_X, JOY_POS_Y)
        .rect(plat_x, plat_y).extrude(JOY_PLATFORM_H)
        .edges("|Z").fillet(2.5)
    )
    base = base.union(platform)

    pin_inset_x, pin_inset_y = 2.5, 2.5
    pin_positions = [
        (JOY_POS_X + dx * (JOY_PCB_L / 2 - pin_inset_x),
         JOY_POS_Y + dy * (JOY_PCB_W / 2 - pin_inset_y))
        for dx in [-1, 1] for dy in [-1, 1]
    ]
    for px, py in pin_positions:
        pin = (
            cq.Workplane("XY")
            .workplane(offset=FLOOR_T + JOY_PLATFORM_H)
            .center(px, py).circle(JOY_PIN_D / 2)
            .workplane(offset=JOY_PIN_H)
            .circle(JOY_PIN_D / 2 - 0.2).loft()
        )
        base = base.union(pin)
    return base


def _add_pressure_sensor_ledge(base: cq.Workplane) -> cq.Workplane:
    """Platform with retention walls for pressure sensor."""
    ledge_x = PRES_L + 4.0
    ledge_y = PRES_W + 4.0
    ledge_h = 3.0
    lip_h = 1.5

    platform = (
        cq.Workplane("XY").workplane(offset=FLOOR_T)
        .center(PRES_POS_X, PRES_POS_Y)
        .rect(ledge_x, ledge_y).extrude(ledge_h)
        .edges("|Z").fillet(1.5)
    )
    base = base.union(platform)

    walls_data = [
        (PRES_POS_X, PRES_POS_Y + ledge_y / 2 - 0.75, ledge_x, 1.5),
        (PRES_POS_X, PRES_POS_Y - ledge_y / 2 + 0.75, ledge_x, 1.5),
        (PRES_POS_X + ledge_x / 2 - 0.75, PRES_POS_Y, 1.5, ledge_y),
    ]
    for cx, cy, sx, sy in walls_data:
        wall = (
            cq.Workplane("XY").workplane(offset=FLOOR_T + ledge_h)
            .center(cx, cy).rect(sx, sy)
            .extrude(PRES_H + lip_h)
        )
        base = base.union(wall)
    return base


def _cut_usb_opening(base: cq.Workplane) -> cq.Workplane:
    """USB-C opening on +X wall."""
    usb_cut = (
        cq.Workplane("YZ")
        .workplane(offset=EXT_X / 2 - WALL * 1.5)
        .center(ESP_POS_Y, FLOOR_T + USB_POS_Z)
        .rect(USB_W, USB_H).extrude(WALL * 3)
    )
    base = base.cut(usb_cut)
    try:
        ch = (
            cq.Workplane("YZ")
            .workplane(offset=EXT_X / 2 - USB_CHAMFER)
            .center(ESP_POS_Y, FLOOR_T + USB_POS_Z)
            .rect(USB_W + USB_CHAMFER * 2, USB_H + USB_CHAMFER * 2)
            .extrude(USB_CHAMFER + 0.1)
        )
        base = base.cut(ch)
    except Exception:
        pass
    return base


def _cut_tube_feedthrough(base: cq.Workplane) -> cq.Workplane:
    """Tube hole on -X wall for pressure sensor silicone tube."""
    tube_cut = (
        cq.Workplane("YZ")
        .workplane(offset=-(EXT_X / 2 - WALL * 1.5))
        .center(TUBE_POS_Y, FLOOR_T + TUBE_POS_Z)
        .circle(TUBE_HOLE_D / 2).extrude(-WALL * 3)
    )
    base = base.cut(tube_cut)
    try:
        funnel = (
            cq.Workplane("YZ")
            .workplane(offset=-(EXT_X / 2 - 0.5))
            .center(TUBE_POS_Y, FLOOR_T + TUBE_POS_Z)
            .circle(TUBE_HOLE_D / 2 + 1.5)
            .workplane(offset=-1.5)
            .circle(TUBE_HOLE_D / 2).loft()
        )
        base = base.cut(funnel)
    except Exception:
        pass
    return base


def _add_mic_mount(base: cq.Workplane) -> cq.Workplane:
    """
    3/8"-16 UNC mic mount on +Y wall (TOP — gooseneck).
    Flat outer wall + internal collar with hex nut pocket.
    """
    nut_sw_tol = MIC_NUT_SW_TOL
    nut_ac_tol = nut_sw_tol / math.cos(math.radians(30))

    wall_outer_y = EXT_Y / 2
    wall_inner_y = wall_outer_y - WALL
    collar_face_y = wall_inner_y - MIC_NUT_POCKET_D

    collar = (
        cq.Workplane("XZ").workplane(offset=-wall_inner_y)
        .center(MIC_POS_X, MIC_POS_Z)
        .circle(MIC_COLLAR_D / 2)
        .extrude(MIC_NUT_POCKET_D)
    )
    try:
        collar = collar.edges(">Y").chamfer(1.0)
    except Exception:
        pass
    base = base.union(collar)

    bolt_hole = (
        cq.Workplane("XZ")
        .workplane(offset=-(wall_outer_y + 0.01))
        .center(MIC_POS_X, MIC_POS_Z)
        .circle(MIC_CLEAR_D / 2)
        .extrude(WALL + 0.02)
    )
    base = base.cut(bolt_hole)

    hex_pocket = (
        cq.Workplane("XZ")
        .workplane(offset=-(collar_face_y - 0.01))
        .center(MIC_POS_X, MIC_POS_Z)
        .polygon(6, nut_ac_tol)
        .extrude(-(MIC_NUT_POCKET_D + 0.01))
    )
    base = base.cut(hex_pocket)
    return base


def _cut_vent_slots(base: cq.Workplane) -> cq.Workplane:
    """Ventilation slots on -Y wall (BOTTOM, opposite mount)."""
    z_center = EXT_H_BASE * 0.55
    world_y_start = -(CAV_Y / 2 - WALL * 0.5)
    xz_offset = -world_y_start

    for i in range(VENT_N):
        slot_x = (i - (VENT_N - 1) / 2.0) * VENT_PITCH
        vent = (
            cq.Workplane("XZ").workplane(offset=xz_offset)
            .center(slot_x, z_center)
            .rect(VENT_W, VENT_LEN)
            .extrude(WALL * 3)
        )
        base = base.cut(vent)
    return base


# =====================================================================
# BASE — assembly
# =====================================================================

def make_base() -> cq.Workplane:
    """Build the base of the MundMaus v5 landscape enclosure."""
    base = organic_box(
        EXT_X, EXT_Y, EXT_H_BASE,
        corner_r=CORNER_R, bot_r=BASE_BOT_R, top_r=0.0,
    )
    cavity = (
        rounded_cavity(CAV_X, CAV_Y, BASE_INNER_H + 1.0, INNER_R)
        .translate((0, 0, FLOOR_T))
    )
    base = base.cut(cavity)
    base = _add_screw_bosses(base)
    base = _add_esp_cradle(base)
    base = _add_joystick_platform(base)
    base = _add_pressure_sensor_ledge(base)
    base = _cut_usb_opening(base)
    base = _cut_tube_feedthrough(base)
    base = _add_mic_mount(base)
    base = _cut_vent_slots(base)
    return base


# =====================================================================
# LID
# =====================================================================

def make_lid() -> cq.Workplane:
    """Build the lid of the MundMaus v5 landscape enclosure."""
    lip_x = CAV_X - 2 * LIP_GAP
    lip_y = CAV_Y - 2 * LIP_GAP
    lip_r = max(0.5, INNER_R - LIP_GAP)

    lid = organic_box(
        EXT_X, EXT_Y, EXT_H_LID,
        corner_r=CORNER_R, top_r=LID_TOP_R, bot_r=0.0,
    )
    lid_cavity = rounded_cavity(CAV_X, CAV_Y, LID_INNER_H + 0.01, INNER_R)
    lid = lid.cut(lid_cavity)

    # Inner lip
    lip_outer = (
        cq.Workplane("XY").workplane(offset=-LIP_H)
        .rect(lip_x, lip_y).extrude(LIP_H)
        .edges("|Z").fillet(lip_r)
    )
    lip_inner = (
        cq.Workplane("XY").workplane(offset=-LIP_H - 0.01)
        .rect(lip_x - 2 * LIP_T, lip_y - 2 * LIP_T)
        .extrude(LIP_H + 0.02)
        .edges("|Z").fillet(max(0.3, lip_r - LIP_T))
    )
    lid = lid.union(lip_outer.cut(lip_inner))

    # Joystick opening
    joy_cut = (
        cq.Workplane("XY").workplane(offset=-LIP_H - 0.01)
        .center(JOY_POS_X, JOY_POS_Y)
        .rect(JOY_OPENING, JOY_OPENING)
        .extrude(EXT_H_LID + LIP_H + 0.02)
    )
    lid = lid.cut(joy_cut)
    try:
        joy_ch = (
            cq.Workplane("XY").workplane(offset=EXT_H_LID - 0.01)
            .center(JOY_POS_X, JOY_POS_Y)
            .rect(JOY_OPENING, JOY_OPENING)
            .workplane(offset=-1.0)
            .rect(JOY_OPENING - 2.0, JOY_OPENING - 2.0).loft()
        )
        lid = lid.cut(joy_ch)
    except Exception:
        pass

    # Screw through-holes
    for px, py in SCREW_POSITIONS:
        hole = (
            cq.Workplane("XY").workplane(offset=-LIP_H - 0.01)
            .center(px, py).circle(SCREW_D / 2)
            .extrude(EXT_H_LID + LIP_H + 0.02)
        )
        lid = lid.cut(hole)

    # Lid top vent slots (3 groups for wider enclosure)
    for side in [-1, 0, 1]:
        x_off = side * 35.0
        for i in range(3):
            slot_x = x_off + (i - 1) * (VENT_PITCH - 0.5)
            vent = (
                cq.Workplane("XY").workplane(offset=-0.01)
                .center(slot_x, 0).rect(VENT_W, VENT_LEN + 2)
                .extrude(EXT_H_LID + 0.02)
            )
            lid = lid.cut(vent)

    # Label
    try:
        label = (
            cq.Workplane("XY").workplane(offset=EXT_H_LID)
            .center(0, 14)
            .text("MundMaus v5", 7, 0.6, font="Liberation Sans:Bold")
        )
        lid = lid.union(label)
    except Exception as e:
        print(f"  [label] Skipped: {e}")

    return lid


# =====================================================================
# Export
# =====================================================================

def export_stl(shape: cq.Workplane, filepath: str) -> None:
    cq.exporters.export(
        shape, filepath,
        exportType="STL", tolerance=0.01, angularTolerance=0.1,
    )
    size = Path(filepath).stat().st_size
    print(f"  Exported: {filepath}  ({size / 1024:.1f} kB)")


def main() -> None:
    parser = argparse.ArgumentParser(
        description="MundMaus Enclosure v5 — Landscape Layout"
    )
    parser.add_argument("--part", choices=["base", "lid", "both"], default="both")
    parser.add_argument("--outdir", type=str, default=".")
    args = parser.parse_args()

    outdir = Path(args.outdir)
    outdir.mkdir(parents=True, exist_ok=True)

    print(f"MundMaus v5 Enclosure — Landscape — CadQuery {cq.__version__}")
    print(f"  External: {EXT_X} x {EXT_Y} x {EXT_H_BASE + EXT_H_LID} mm")
    print(f"  v4.2 was: 96 x 71 x 41 mm  ->  Y reduced by {71 - EXT_Y:.0f} mm!")
    print(f"  Cavity: {CAV_X} x {CAV_Y} x {BASE_INNER_H + LID_INNER_H} mm")
    print(f"  Components: Sensor(X={PRES_POS_X}) | Joystick(X={JOY_POS_X})"
          f" | Mount(X={MIC_POS_X}) | ESP32(X={ESP_POS_X})")
    print(f"  Stick tip: Z={FLOOR_T+JOY_PLATFORM_H+JOY_PCB_H+JOY_STICK_H:.1f}")
    print()

    if args.part in ("base", "both"):
        print("Building base...")
        base = make_base()
        export_stl(base, str(outdir / "mundmaus_v5_base.stl"))

    if args.part in ("lid", "both"):
        print("Building lid...")
        lid = make_lid()
        lid_print = lid.rotateAboutCenter((1, 0, 0), 180).translate(
            (0, 0, EXT_H_LID))
        export_stl(lid_print, str(outdir / "mundmaus_v5_lid.stl"))

    print("\nDone.")
    print("  Base: floor-down, no supports, 25% Gyroid, 4 walls")
    print("  Lid:  ceiling-down (flipped), no supports")
    print("  Material: PETG, 240C nozzle, 75C bed, 40% fan")


if __name__ == "__main__":
    main()
