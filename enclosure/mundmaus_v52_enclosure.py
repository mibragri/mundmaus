#!/usr/bin/env python3
"""MundMaus Enclosure v5.2 — Mount on Right Short Side (+X Wall)
CadQuery parametric design for FDM (Bambu Lab P1S, PETG)

v5.2 Changes vs v5.1:
  1. Gooseneck mount (3/8"-16 UNC) moved from +Y wall to +X wall (right)
  2. ESP32 shifted left (X=28) for collar clearance
  3. USB cable exit moved from +X wall to +Y wall (top long side)
  4. Cable notches relocated accordingly

Layout (top view, patient lies below at -Y):
  +Y wall (TOP — USB cable exit)
  +------------------------------------------------------+
  | [Sensor]  [Joystick]       [ESP32]                   |mount(+X)
  +------------------------------------------------------+
  -Y wall (BOTTOM — vents, closest to patient)
"""
import cadquery as cq
import math
import argparse
import logging
from pathlib import Path

logging.getLogger("OCC").setLevel(logging.ERROR)

# --- Parameters ---
CAV_X, CAV_Y, WALL = 130.0, 44.0, 3.0
FLOOR_T, CEIL_T, INNER_R = 3.0, 3.0, 2.5
BASE_INNER_H, LID_INNER_H = 28.0, 7.0
CORNER_R, LID_TOP_R, BASE_BOT_R = 12.0, 3.5, 2.0
LIP_H, LIP_T, LIP_GAP = 4.0, 1.8, 0.15
TOL, TOL_LOOSE = 0.2, 0.3

# ESP32-WROOM-32 DevKitC V4
ESP_L, ESP_W, ESP_H = 51.5, 28.0, 1.2
ESP_STANDOFF_H, ESP_GUIDE_H = 3.0, 3.0
ESP_POS_X = 28.0  # v5.2: was 35 — shifted left for collar clearance
ESP_POS_Y = -2.0

# KY-023 Joystick
JOY_PCB_L, JOY_PCB_W, JOY_PCB_H = 34.0, 26.0, 1.6
JOY_HOUSING, JOY_STICK_H = 16.0, 17.0
JOY_PLATFORM_H = 22.5
JOY_PIN_D, JOY_PIN_H = 2.8, 3.0
JOY_OPENING = 17.0
JOY_POS_X, JOY_POS_Y = -15.0, -4.0

# Pressure Sensor
PRES_L, PRES_W, PRES_H = 20.0, 15.0, 5.0
PRES_POS_X, PRES_POS_Y = -48.0, -2.0

# Tube Feedthrough (-X wall)
TUBE_HOLE_D, TUBE_POS_Y, TUBE_POS_Z = 6.5, PRES_POS_Y, 13.0

# USB Cable Exit (+Y wall) — v5.2: was on +X wall
USB_W, USB_H, USB_CHAMFER, USB_POS_Z = 8.0, 3.5, 0.8, 5.5
USB_EXIT_X = 45.0  # X position on +Y wall near ESP32 USB end

# Cable Exit Notches
CABLE_NOTCH_W, CABLE_NOTCH_H = 8.0, 4.0

# M3 Screw Bosses
SCREW_D, SCREW_BOSS_D, SCREW_BOSS_H = 3.4, 7.0, 10.0
SCREW_PILOT_D, SCREW_INSET = 2.5, 6.0

# 3/8"-16 UNC Mic Mount (+X wall) — v5.2: was +Y wall
MIC_CLEAR_D, MIC_NUT_SW, MIC_NUT_H = 10.5, 14.29, 5.56
MIC_NUT_TOL, MIC_NUT_POCKET_D, MIC_COLLAR_D = 0.205, 7.9, 24.0
MIC_POS_Y = 0.0  # Y position on +X wall (centered)

# Ventilation
VENT_N, VENT_W, VENT_LEN, VENT_PITCH = 6, 1.6, 14.0, 6.0

# --- Derived ---
EXT_X, EXT_Y = CAV_X + 2 * WALL, CAV_Y + 2 * WALL  # 136, 50
EXT_H_BASE = FLOOR_T + BASE_INNER_H  # 31
EXT_H_LID = CEIL_T + LID_INNER_H     # 10
MIC_POS_Z = EXT_H_BASE / 2           # 15.5
SCREW_POSITIONS = [
    ( CAV_X/2 - SCREW_INSET,  CAV_Y/2 - SCREW_INSET),
    ( CAV_X/2 - SCREW_INSET, -CAV_Y/2 + SCREW_INSET),
    (-CAV_X/2 + SCREW_INSET,  CAV_Y/2 - SCREW_INSET),
    (-CAV_X/2 + SCREW_INSET, -CAV_Y/2 + SCREW_INSET),
]
MIC_NUT_SW_TOL = MIC_NUT_SW + 2 * MIC_NUT_TOL  # 14.7mm
STICK_TIP_Z = FLOOR_T + JOY_PLATFORM_H + JOY_PCB_H + JOY_STICK_H
LID_TOP_Z = EXT_H_BASE + EXT_H_LID
STICK_PROTRUSION = STICK_TIP_Z - LID_TOP_Z


# --- Helpers ---
def organic_box(length, width, height, corner_r, top_r=0.0, bot_r=0.0):
    r_v = min(corner_r, length/2 - 0.5, width/2 - 0.5)
    result = cq.Workplane("XY").rect(length, width).extrude(height).edges("|Z").fillet(r_v)
    for sel, r in [("<Z", bot_r), (">Z", top_r)]:
        if r > 0.01:
            try: result = result.edges(sel).fillet(min(r, r_v - 0.5, height/2 - 0.5))
            except Exception: pass
    return result


def rounded_cavity(length, width, height, radius):
    r = min(radius, length/2 - 0.1, width/2 - 0.1)
    return cq.Workplane("XY").rect(length, width).extrude(height).edges("|Z").fillet(r)


# --- BASE features ---
def _add_screw_bosses(base):
    for px, py in SCREW_POSITIONS:
        boss = cq.Workplane("XY").workplane(offset=FLOOR_T).center(px, py) \
            .circle(SCREW_BOSS_D/2).extrude(SCREW_BOSS_H)
        pilot = cq.Workplane("XY").workplane(offset=FLOOR_T - 0.01).center(px, py) \
            .circle(SCREW_PILOT_D/2).extrude(SCREW_BOSS_H + 0.02)
        base = base.union(boss).cut(pilot)
    return base


def _add_esp_cradle(base):
    post_sz, rail_t = 3.5, 1.5
    guide_total = ESP_STANDOFF_H + ESP_H + ESP_GUIDE_H
    for dx, dy in [(-1, -1), (-1, 1), (1, -1), (1, 1)]:
        cx = ESP_POS_X + dx * (ESP_L/2 - post_sz/2)
        cy = ESP_POS_Y + dy * (ESP_W/2 - post_sz/2)
        post = cq.Workplane("XY").workplane(offset=FLOOR_T).center(cx, cy) \
            .rect(post_sz, post_sz).extrude(ESP_STANDOFF_H)
        base = base.union(post)
    for side in [-1, 1]:
        gy = ESP_POS_Y + side * (ESP_W/2 + TOL_LOOSE + rail_t/2)
        rail = cq.Workplane("XY").workplane(offset=FLOOR_T).center(ESP_POS_X, gy) \
            .rect(ESP_L * 0.55, rail_t).extrude(guide_total)
        base = base.union(rail)
    stop_x = ESP_POS_X - ESP_L/2 - TOL_LOOSE - rail_t/2
    stop = cq.Workplane("XY").workplane(offset=FLOOR_T).center(stop_x, ESP_POS_Y) \
        .rect(rail_t, ESP_W * 0.55).extrude(guide_total)
    return base.union(stop)


def _add_joystick_platform(base):
    plat_x, plat_y = JOY_PCB_L + 5.0, JOY_PCB_W + 5.0
    platform = cq.Workplane("XY").workplane(offset=FLOOR_T) \
        .center(JOY_POS_X, JOY_POS_Y).rect(plat_x, plat_y) \
        .extrude(JOY_PLATFORM_H).edges("|Z").fillet(2.5)
    base = base.union(platform)
    for dx in [-1, 1]:
        for dy in [-1, 1]:
            px = JOY_POS_X + dx * (JOY_PCB_L/2 - 2.5)
            py = JOY_POS_Y + dy * (JOY_PCB_W/2 - 2.5)
            pin = cq.Workplane("XY").workplane(offset=FLOOR_T + JOY_PLATFORM_H) \
                .center(px, py).circle(JOY_PIN_D/2) \
                .workplane(offset=JOY_PIN_H).circle(JOY_PIN_D/2 - 0.2).loft()
            base = base.union(pin)
    return base


def _add_pressure_sensor_ledge(base):
    lx, ly, lh, lip_h = PRES_L + 4.0, PRES_W + 4.0, 3.0, 1.5
    platform = cq.Workplane("XY").workplane(offset=FLOOR_T) \
        .center(PRES_POS_X, PRES_POS_Y).rect(lx, ly).extrude(lh).edges("|Z").fillet(1.5)
    base = base.union(platform)
    for cx, cy, sx, sy in [
        (PRES_POS_X, PRES_POS_Y + ly/2 - 0.75, lx, 1.5),
        (PRES_POS_X, PRES_POS_Y - ly/2 + 0.75, lx, 1.5),
        (PRES_POS_X + lx/2 - 0.75, PRES_POS_Y, 1.5, ly),
    ]:
        wall = cq.Workplane("XY").workplane(offset=FLOOR_T + lh) \
            .center(cx, cy).rect(sx, sy).extrude(PRES_H + lip_h)
        base = base.union(wall)
    return base


def _cut_usb_opening(base):
    """USB cable exit on +Y wall. XZ normal=-Y, offset=-N => Y=N, extrude => -Y."""
    usb_cut = cq.Workplane("XZ").workplane(offset=-(EXT_Y/2 + 0.01)) \
        .center(USB_EXIT_X, FLOOR_T + USB_POS_Z).rect(USB_W, USB_H).extrude(WALL + 0.02)
    base = base.cut(usb_cut)
    try:
        ch = cq.Workplane("XZ").workplane(offset=-(EXT_Y/2 - USB_CHAMFER)) \
            .center(USB_EXIT_X, FLOOR_T + USB_POS_Z) \
            .rect(USB_W + USB_CHAMFER*2, USB_H + USB_CHAMFER*2) \
            .extrude(-(USB_CHAMFER + 0.1))
        base = base.cut(ch)
    except Exception: pass
    return base


def _cut_tube_feedthrough(base):
    """Tube hole on -X wall for pressure sensor silicone tube."""
    tube_cut = cq.Workplane("YZ").workplane(offset=-(EXT_X/2 - WALL*1.5)) \
        .center(TUBE_POS_Y, FLOOR_T + TUBE_POS_Z).circle(TUBE_HOLE_D/2).extrude(-WALL*3)
    base = base.cut(tube_cut)
    try:
        funnel = cq.Workplane("YZ").workplane(offset=-(EXT_X/2 - 0.5)) \
            .center(TUBE_POS_Y, FLOOR_T + TUBE_POS_Z).circle(TUBE_HOLE_D/2 + 1.5) \
            .workplane(offset=-1.5).circle(TUBE_HOLE_D/2).loft()
        base = base.cut(funnel)
    except Exception: pass
    return base


def _cut_cable_notches(base):
    """USB cable notch on +Y wall, tube notch on -X wall."""
    base_top = EXT_H_BASE
    usb_notch = cq.Workplane("XZ").workplane(offset=-(EXT_Y/2 + 0.01)) \
        .center(USB_EXIT_X, base_top - CABLE_NOTCH_H/2) \
        .rect(CABLE_NOTCH_W, CABLE_NOTCH_H).extrude(WALL + 0.02)
    base = base.cut(usb_notch)
    tube_notch = cq.Workplane("YZ").workplane(offset=-(EXT_X/2 - WALL*1.5)) \
        .center(TUBE_POS_Y, base_top - CABLE_NOTCH_H/2) \
        .rect(CABLE_NOTCH_W, CABLE_NOTCH_H).extrude(-WALL*3)
    return base.cut(tube_notch)


def _add_mic_mount(base):
    """3/8-16 UNC gooseneck mount on +X wall (right short side).
    YZ normal=+X, offset=N => X=N, extrude => +X."""
    nut_ac_tol = MIC_NUT_SW_TOL / math.cos(math.radians(30))
    wall_outer_x = EXT_X / 2          # 68
    wall_inner_x = wall_outer_x - WALL  # 65
    collar_face_x = wall_inner_x - MIC_NUT_POCKET_D  # 57.1

    collar = cq.Workplane("YZ").workplane(offset=wall_inner_x) \
        .center(MIC_POS_Y, MIC_POS_Z).circle(MIC_COLLAR_D/2) \
        .extrude(-MIC_NUT_POCKET_D)
    try: collar = collar.edges("<X").chamfer(1.0)
    except Exception: pass
    base = base.union(collar)

    bolt_hole = cq.Workplane("YZ").workplane(offset=wall_outer_x + 0.01) \
        .center(MIC_POS_Y, MIC_POS_Z).circle(MIC_CLEAR_D/2).extrude(-(WALL + 0.02))
    base = base.cut(bolt_hole)

    hex_pocket = cq.Workplane("YZ").workplane(offset=collar_face_x - 0.01) \
        .center(MIC_POS_Y, MIC_POS_Z).polygon(6, nut_ac_tol) \
        .extrude(MIC_NUT_POCKET_D + 0.01)
    return base.cut(hex_pocket)


def _cut_vent_slots(base):
    """Ventilation slots on -Y wall."""
    z_center = EXT_H_BASE * 0.55
    xz_offset = CAV_Y/2 - WALL*0.5
    for i in range(VENT_N):
        slot_x = (i - (VENT_N - 1) / 2.0) * VENT_PITCH
        vent = cq.Workplane("XZ").workplane(offset=xz_offset) \
            .center(slot_x, z_center).rect(VENT_W, VENT_LEN).extrude(WALL*3)
        base = base.cut(vent)
    return base


# --- BASE assembly ---
def make_base():
    base = organic_box(EXT_X, EXT_Y, EXT_H_BASE, corner_r=CORNER_R, bot_r=BASE_BOT_R)
    cavity = rounded_cavity(CAV_X, CAV_Y, BASE_INNER_H + 1.0, INNER_R).translate((0, 0, FLOOR_T))
    base = base.cut(cavity)
    for fn in [_add_screw_bosses, _add_esp_cradle, _add_joystick_platform,
               _add_pressure_sensor_ledge, _cut_usb_opening, _cut_tube_feedthrough,
               _cut_cable_notches, _add_mic_mount, _cut_vent_slots]:
        base = fn(base)
    return base


# --- LID ---
def make_lid():
    lip_x, lip_y = CAV_X - 2*LIP_GAP, CAV_Y - 2*LIP_GAP
    lip_r = max(0.5, INNER_R - LIP_GAP)

    lid = organic_box(EXT_X, EXT_Y, EXT_H_LID, corner_r=CORNER_R, top_r=LID_TOP_R)
    lid = lid.cut(rounded_cavity(CAV_X, CAV_Y, LID_INNER_H + 0.01, INNER_R))

    # Inner lip
    lip_outer = cq.Workplane("XY").workplane(offset=-LIP_H) \
        .rect(lip_x, lip_y).extrude(LIP_H).edges("|Z").fillet(lip_r)
    lip_inner = cq.Workplane("XY").workplane(offset=-LIP_H - 0.01) \
        .rect(lip_x - 2*LIP_T, lip_y - 2*LIP_T).extrude(LIP_H + 0.02) \
        .edges("|Z").fillet(max(0.3, lip_r - LIP_T))
    lid = lid.union(lip_outer.cut(lip_inner))

    # Joystick opening
    joy_cut = cq.Workplane("XY").workplane(offset=-LIP_H - 0.01) \
        .center(JOY_POS_X, JOY_POS_Y).rect(JOY_OPENING, JOY_OPENING) \
        .extrude(EXT_H_LID + LIP_H + 0.02)
    lid = lid.cut(joy_cut)
    try:
        joy_ch = cq.Workplane("XY").workplane(offset=EXT_H_LID - 0.01) \
            .center(JOY_POS_X, JOY_POS_Y).rect(JOY_OPENING, JOY_OPENING) \
            .workplane(offset=-1.0).rect(JOY_OPENING - 2.0, JOY_OPENING - 2.0).loft()
        lid = lid.cut(joy_ch)
    except Exception: pass

    # Cable notches: USB on +Y wall, tube on -X wall
    usb_lip_notch = cq.Workplane("XZ").workplane(offset=-(EXT_Y/2 + 0.01)) \
        .center(USB_EXIT_X, -LIP_H/2).rect(CABLE_NOTCH_W, LIP_H + 0.02).extrude(WALL + 0.02)
    lid = lid.cut(usb_lip_notch)
    tube_lip_notch = cq.Workplane("YZ").workplane(offset=-(EXT_X/2 - WALL*1.5)) \
        .center(TUBE_POS_Y, -LIP_H/2).rect(CABLE_NOTCH_W, LIP_H + 0.02).extrude(-WALL*3)
    lid = lid.cut(tube_lip_notch)

    # Screw through-holes
    for px, py in SCREW_POSITIONS:
        hole = cq.Workplane("XY").workplane(offset=-LIP_H - 0.01) \
            .center(px, py).circle(SCREW_D/2).extrude(EXT_H_LID + LIP_H + 0.02)
        lid = lid.cut(hole)

    # Lid top vent slots
    for side in [-1, 0, 1]:
        x_off = side * 35.0
        for i in range(3):
            slot_x = x_off + (i - 1) * (VENT_PITCH - 0.5)
            vent = cq.Workplane("XY").workplane(offset=-0.01) \
                .center(slot_x, 0).rect(VENT_W, VENT_LEN + 2).extrude(EXT_H_LID + 0.02)
            lid = lid.cut(vent)

    # Label
    try:
        label = cq.Workplane("XY").workplane(offset=EXT_H_LID).center(0, 14) \
            .text("MundMaus v5.2", 7, 0.6, font="Liberation Sans:Bold")
        lid = lid.union(label)
    except Exception as e:
        print(f"  [label] Skipped: {e}")
    return lid


# --- Export ---
def export_stl(shape, filepath):
    cq.exporters.export(shape, filepath, exportType="STL", tolerance=0.01, angularTolerance=0.1)
    print(f"  Exported: {filepath}  ({Path(filepath).stat().st_size / 1024:.1f} kB)")


def main():
    parser = argparse.ArgumentParser(description="MundMaus Enclosure v5.2")
    parser.add_argument("--part", choices=["base", "lid", "both"], default="both")
    parser.add_argument("--outdir", type=str, default=".")
    args = parser.parse_args()
    outdir = Path(args.outdir)
    outdir.mkdir(parents=True, exist_ok=True)

    print(f"MundMaus v5.2 Enclosure — CadQuery {cq.__version__}")
    print(f"  External: {EXT_X} x {EXT_Y} x {EXT_H_BASE + EXT_H_LID} mm")
    print(f"  Mount: +X wall (right), collar {MIC_COLLAR_D}mm, nut SW {MIC_NUT_SW_TOL:.1f}mm")
    print(f"  USB exit: +Y wall at X={USB_EXIT_X}")
    print(f"  Stick protrusion: {STICK_PROTRUSION:.1f} mm (target: >=3mm)\n")

    if args.part in ("base", "both"):
        print("Building base...")
        export_stl(make_base(), str(outdir / "mundmaus_v52_base.stl"))
    if args.part in ("lid", "both"):
        print("Building lid...")
        lid = make_lid()
        lid_print = lid.rotateAboutCenter((1, 0, 0), 180).translate((0, 0, EXT_H_LID))
        export_stl(lid_print, str(outdir / "mundmaus_v52_lid.stl"))

    print("\nDone. Base: floor-down, Lid: ceiling-down (flipped), no supports")
    print("Material: PETG, 240C nozzle, 75C bed, 40% fan, 25% Gyroid, 4 walls")


if __name__ == "__main__":
    main()
