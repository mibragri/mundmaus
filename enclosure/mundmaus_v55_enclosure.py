#!/usr/bin/env python3
"""MundMaus Enclosure v5.5 — Compact symmetric layout in CadQuery.

v5.5 removes the asymmetric adapter bay and rearranges components:
  Mount(-X) → ESP32 → Joystick → Sensor(+X)
Enclosure shrinks from 168 x 50 to 136 x 50 mm (symmetric).
USB cable enters through a notch in the -Y wall; the lid provides strain relief.
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
CORNER_R, LID_TOP_R, BASE_BOT_R = 12.0, 3.5, 2.0
LIP_H, LIP_T, LIP_GAP = 4.0, 1.8, 0.15
TOL, TOL_LOOSE = 0.2, 0.5

# ── ESP32-WROOM-32 DevKitC V4 ──────────────────────────────────────
ESP_L, ESP_W, ESP_H = 54.4, 28.0, 1.2  # Espressif DevKitC V4 spec (was 51.5)
ESP_STANDOFF_H, ESP_GUIDE_H = 3.0, 3.0
ESP_POS_X, ESP_POS_Y = 35.0, -2.0  # right side; USB faces -X (center)
ESP_USB_PROTRUSION = 2.4

# ── KY-023 Joystick ────────────────────────────────────────────────
JOY_PCB_L, JOY_PCB_W, JOY_PCB_H = 34.0, 26.0, 1.6
JOY_HOUSING, JOY_STICK_H = 16.0, 17.0
JOY_PLATFORM_H = 22.5
JOY_PIN_D, JOY_PIN_H = 2.8, 3.0
JOY_HOLE_GRID_X, JOY_HOLE_GRID_Y = 26.67, 20.32  # 1.05" x 0.80" M4 holes
JOY_OPENING = 17.0
JOY_POS_X, JOY_POS_Y = -19.0, -2.0  # left side, Y=-2 = centered on USB plug Y for equal clearance
JOY_PLATFORM_MAIN_X, JOY_PLATFORM_MAIN_Y = JOY_PCB_L + 3.0, JOY_PCB_W - 6.0
JOY_PLATFORM_MAIN_SHIFT_Y = -2.0
JOY_PLATFORM_FRONT_X, JOY_PLATFORM_FRONT_Y = JOY_PCB_L, 6.0
JOY_PLATFORM_FRONT_SHIFT_Y = JOY_PCB_W / 2 - JOY_PLATFORM_FRONT_Y / 2 - 0.2

# ── Pressure Sensor (MPS20N0040D-S + HX710B) ───────────────────────
PRES_L, PRES_W, PRES_H = 20.0, 15.0, 5.0
PRES_POS_X, PRES_POS_Z = 42.0, 20.0  # right of ESP32, +Y wall shelf
PRES_SENSOR_WALL_GAP = 0.3
PRES_HOLDER_T, PRES_HOLDER_DEPTH = 2.0, 7.0
PRES_BARB_HOLE_D, PRES_BARB_CHAMFER_D = 3.0, 5.0
CABLE_NOTCH_W, CABLE_NOTCH_H = 8.0, 4.0

# ── USB cable exit notch (-Y wall, at lid seam) ────────────────────
USB_NOTCH_W, USB_NOTCH_H = 8.0, 5.0
USB_NOTCH_X = ESP_POS_X - ESP_L / 2  # USB faces -X (center), cable routes left

# ── USB plug channel (cut into joystick platform base) ─────────────
USB_PLUG_W, USB_PLUG_H, USB_PLUG_DEPTH = 12.0, 9.0, 15.0

# ── M3 screw bosses ────────────────────────────────────────────────
SCREW_D, SCREW_BOSS_D, SCREW_BOSS_H = 3.4, 7.0, 10.0
SCREW_PILOT_D, SCREW_INSET = 2.5, 6.0

# ── 3/8"-16 UNC mic stand mount (-X wall) ──────────────────────────
MIC_CLEAR_D, MIC_NUT_SW, MIC_NUT_H = 10.5, 14.29, 5.56
MIC_NUT_TOL, MIC_NUT_POCKET_D, MIC_COLLAR_D = 0.205, 7.9, 24.0
MIC_POS_Y = 0.0

# ── Ventilation (-Y wall) ──────────────────────────────────────────
VENT_N, VENT_W, VENT_LEN, VENT_PITCH = 6, 1.6, 14.0, 6.0

# ── Derived geometry ───────────────────────────────────────────────
EXT_X, EXT_Y = CAV_X + 2 * WALL, CAV_Y + 2 * WALL  # 136 x 50
EXT_H_BASE, EXT_H_LID = FLOOR_T + BASE_INNER_H, CEIL_T + LID_INNER_H
OUTER_POS_X = EXT_X / 2    # +68
OUTER_POS_Y = EXT_Y / 2    # +25
INNER_POS_X = CAV_X / 2    # +65
INNER_POS_Y = EXT_Y / 2 - WALL  # +22

MIC_POS_Z = EXT_H_BASE / 2
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

# Pressure sensor derived
PRES_POS_Y = INNER_POS_Y - PRES_H / 2 - PRES_SENSOR_WALL_GAP
PRES_HOLDER_OUTER_X = PRES_L + 2 * PRES_HOLDER_T
PRES_HOLDER_MIN_X = PRES_POS_X - PRES_HOLDER_OUTER_X / 2
PRES_HOLDER_MAX_X = PRES_POS_X + PRES_HOLDER_OUTER_X / 2
PRES_HOLDER_MIN_Z = PRES_POS_Z - PRES_W / 2 - PRES_HOLDER_T
PRES_HOLDER_MAX_Z = PRES_POS_Z + PRES_W / 2
PRES_TO_JOY_PLATFORM_CLEARANCE_X = PRES_HOLDER_MIN_X - JOY_PLATFORM_MAX_X
BARB_TO_JOYSTICK_OFFSET_X = PRES_POS_X - JOY_POS_X
BARB_TO_LID_RIM_CLEARANCE_Z = EXT_H_BASE - PRES_HOLDER_MAX_Z

# Clearances (new layout: Collar → Joy → Sensor → ESP32)
COLLAR_TO_JOY_CLEARANCE = JOY_PLATFORM_MIN_X - MIC_COLLAR_INNER_X
JOY_TO_PRES_CLEARANCE = PRES_HOLDER_MIN_X - JOY_PLATFORM_MAX_X
ESP_LEFT_EDGE_X = ESP_POS_X - ESP_L / 2
ESP_RIGHT_EDGE_X = ESP_POS_X + ESP_L / 2
ESP_TO_WALL_CLEARANCE = INNER_POS_X - ESP_RIGHT_EDGE_X

# Screw positions — 4 bosses (restored +X+Y, sensor moved to center)
_STD_X = CAV_X / 2 - SCREW_INSET
_STD_Y = CAV_Y / 2 - SCREW_INSET
SCREW_POSITIONS = [
    (_STD_X, -_STD_Y),          # +X -Y
    (_STD_X, _STD_Y),           # +X +Y (restored)
    (-_STD_X, _STD_Y),          # -X +Y
    (-_STD_X, -_STD_Y),         # -X -Y
]
NEAREST_BOSS_Y_CLEARANCE = _STD_Y - (MIC_COLLAR_D / 2 + SCREW_BOSS_D / 2)

# ── Helper functions ───────────────────────────────────────────────


@dataclass(frozen=True)
class RenderView:
    filename: str
    projection_dir: tuple[float, float, float]
    assembled: bool


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


def _add_screw_bosses(base: cq.Workplane) -> cq.Workplane:
    for px, py in SCREW_POSITIONS:
        boss = cq.Workplane("XY").workplane(offset=FLOOR_T).center(px, py).circle(
            SCREW_BOSS_D / 2
        ).extrude(SCREW_BOSS_H)
        pilot = cq.Workplane("XY").workplane(offset=FLOOR_T - 0.01).center(px, py).circle(
            SCREW_PILOT_D / 2
        ).extrude(SCREW_BOSS_H + 0.02)
        base = base.union(boss).cut(pilot)
    return base


def _add_esp_cradle(base: cq.Workplane) -> cq.Workplane:
    post_sz, rail_t = 3.5, 1.5
    guide_total = ESP_STANDOFF_H + ESP_H + ESP_GUIDE_H
    # Corner posts
    for dx, dy in [(-1, -1), (-1, 1), (1, -1), (1, 1)]:
        cx = ESP_POS_X + dx * (ESP_L / 2 - post_sz / 2)
        cy = ESP_POS_Y + dy * (ESP_W / 2 - post_sz / 2)
        post = cq.Workplane("XY").workplane(offset=FLOOR_T).center(cx, cy).rect(
            post_sz, post_sz
        ).extrude(ESP_STANDOFF_H)
        base = base.union(post)
    # Side guide rails (Y axis)
    for side in [-1, 1]:
        gy = ESP_POS_Y + side * (ESP_W / 2 + TOL_LOOSE + rail_t / 2)
        rail = cq.Workplane("XY").workplane(offset=FLOOR_T).center(ESP_POS_X, gy).rect(
            ESP_L * 0.4, rail_t
        ).extrude(guide_total)
        base = base.union(rail)
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
    """Simple shelf — sensor sits on ledge against +Y wall, lid retains from above."""
    shelf = cq.Workplane("XY").workplane(offset=PRES_HOLDER_MIN_Z).center(
        PRES_POS_X, INNER_POS_Y - PRES_HOLDER_DEPTH / 2
    ).rect(PRES_L + 2 * PRES_HOLDER_T, PRES_HOLDER_DEPTH).extrude(PRES_HOLDER_T)
    return base.union(shelf)


def _cut_pressure_barb_port(base: cq.Workplane) -> cq.Workplane:
    # XZ workplane normal is -Y: offset=-(V) places plane at Y=+V
    barb_cut = cq.Workplane("XZ").workplane(offset=-(OUTER_POS_Y + 0.01)).center(
        PRES_POS_X, PRES_POS_Z
    ).circle(PRES_BARB_HOLE_D / 2).extrude(WALL + 0.02)
    base = base.cut(barb_cut)
    try:
        chamfer = cq.Workplane("XZ").workplane(offset=-(OUTER_POS_Y + 0.01)).center(
            PRES_POS_X, PRES_POS_Z
        ).circle(PRES_BARB_CHAMFER_D / 2).workplane(offset=1.0).circle(
            PRES_BARB_HOLE_D / 2
        ).loft()
        base = base.cut(chamfer)
    except Exception:
        pass
    return base


def _cut_usb_cable_notch(base: cq.Workplane) -> cq.Workplane:
    """Cut a notch in the -Y wall at seam height for USB cable exit."""
    # XZ normal is -Y: offset=+V places plane at Y=-V
    # To reach -Y outer wall (Y=-25): offset = OUTER_POS_Y + eps
    # Extrude negative to go through wall toward +Y (into cavity)
    notch = cq.Workplane("XZ").workplane(offset=OUTER_POS_Y + 0.01).center(
        USB_NOTCH_X, EXT_H_BASE - USB_NOTCH_H / 2
    ).rect(USB_NOTCH_W, USB_NOTCH_H).extrude(-(WALL + 0.02))
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
        _add_screw_bosses,
        _add_esp_cradle,
        _add_joystick_pillars,
        _add_pressure_sensor_mount,
        _cut_pressure_barb_port,
        _cut_usb_cable_notch,
        _add_mic_mount,
        _cut_vent_slots,
    ]:
        base = fn(base)
    return base


def make_lid() -> cq.Workplane:
    lip_x, lip_y = CAV_X - 2 * LIP_GAP, CAV_Y - 2 * LIP_GAP
    lip_r = max(0.5, INNER_R - LIP_GAP)
    lid = organic_box(EXT_X, EXT_Y, EXT_H_LID, CORNER_R, top_r=LID_TOP_R)
    lid = lid.cut(rounded_cavity(CAV_X, CAV_Y, LID_INNER_H + 0.01, INNER_R))
    lip_outer = cq.Workplane("XY").workplane(offset=-LIP_H).rect(
        lip_x, lip_y
    ).extrude(LIP_H).edges("|Z").fillet(lip_r)
    lip_inner = cq.Workplane("XY").workplane(offset=-LIP_H - 0.01).rect(
        lip_x - 2 * LIP_T, lip_y - 2 * LIP_T
    ).extrude(LIP_H + 0.02).edges("|Z").fillet(max(0.3, lip_r - LIP_T))
    lid = lid.union(lip_outer.cut(lip_inner))
    # Joystick opening
    joy_cut = cq.Workplane("XY").workplane(offset=-LIP_H - 0.01).center(
        JOY_POS_X, JOY_POS_Y
    ).rect(JOY_OPENING, JOY_OPENING).extrude(EXT_H_LID + LIP_H + 0.02)
    lid = lid.cut(joy_cut)
    try:
        joy_chamfer = cq.Workplane("XY").workplane(offset=EXT_H_LID - 0.01).center(
            JOY_POS_X, JOY_POS_Y
        ).rect(JOY_OPENING, JOY_OPENING).workplane(offset=-1.0).rect(
            JOY_OPENING - 2.0, JOY_OPENING - 2.0
        ).loft()
        lid = lid.cut(joy_chamfer)
    except Exception:
        pass
    # Screw through-holes
    for px, py in SCREW_POSITIONS:
        lid = lid.cut(
            cq.Workplane("XY").workplane(offset=-LIP_H - 0.01).center(px, py).circle(
                SCREW_D / 2
            ).extrude(EXT_H_LID + LIP_H + 0.02)
        )
    # USB cable relief — notch in lid lip on -Y side matching base notch
    cable_relief = cq.Workplane("XZ").workplane(offset=OUTER_POS_Y + 0.01).center(
        USB_NOTCH_X, -LIP_H / 2
    ).rect(USB_NOTCH_W, LIP_H + 0.02).extrude(-(WALL + LIP_GAP + LIP_T + 0.02))
    lid = lid.cut(cable_relief)
    # Lid vents
    for side in [-1, 0, 1]:
        for idx in range(3):
            slot_x = side * 35.0 + (idx - 1) * (VENT_PITCH - 0.5)
            lid = lid.cut(
                cq.Workplane("XY").workplane(offset=-0.01).center(slot_x, 0).rect(
                    VENT_W, VENT_LEN + 2
                ).extrude(EXT_H_LID + 0.02)
            )
    # Label
    try:
        lid = lid.union(
            cq.Workplane("XY").workplane(offset=EXT_H_LID).center(0, 14).text(
                "MundMaus v5.5", 7, 0.6, font="Liberation Sans:Bold"
            )
        )
    except Exception:
        pass
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
        RenderView("mundmaus_v55_assembly.png", (1.0, -1.0, 0.8), True),
        RenderView("mundmaus_v55_top.png", (0.0, 0.0, 1.0), True),
        RenderView("mundmaus_v55_side.png", (0.0, 1.0, 0.0), False),
        RenderView("mundmaus_v55_back.png", (-1.0, 0.0, 0.0), False),
    ]
    assembly = _assembly_shape(base, lid)
    for view in views:
        svg_path = outdir / view.filename.replace(".png", ".svg")
        cq.exporters.export(
            assembly if view.assembled else base,
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
    report = textwrap.dedent(
        f"""\
        # MundMaus v5.5 Enclosure
        ## Summary
        v5.5 is a compact symmetric redesign. Key changes from v5.4c:
        - **Removed adapter bay** — enclosure shrinks from 168 to {EXT_X:.0f} mm
        - **New component order**: Mount(-X) → Joystick → Sensor → ESP32(+X)
        - **ESP32 USB faces -X** (center) for plug access; cable routes to -Y wall notch
        - 4 screw bosses (restored +X+Y, sensor moved to center)

        Component positions along X axis:
        - Mic mount collar: -X wall (internal, {MIC_COLLAR_INNER_X:.1f} inner edge)
        - Joystick center: X={JOY_POS_X:.1f} (platform {JOY_PLATFORM_MIN_X:.1f} to {JOY_PLATFORM_MAX_X:.1f})
        - Sensor bracket: X={PRES_POS_X:.1f} (bracket {PRES_HOLDER_MIN_X:.1f} to {PRES_HOLDER_MAX_X:.1f})
        - ESP32 center: X={ESP_POS_X:.1f} (PCB {ESP_LEFT_EDGE_X:.1f} to {ESP_RIGHT_EDGE_X:.1f}, USB at -X end)
        ## Clearance Analysis
        | Item | Value |
        |---|---:|
        | Mic collar to joystick platform | {COLLAR_TO_JOY_CLEARANCE:.2f} mm |
        | Joystick platform to sensor bracket | {JOY_TO_PRES_CLEARANCE:.2f} mm |
        | ESP32 right edge to +X inner wall | {ESP_TO_WALL_CLEARANCE:.2f} mm |
        | Joystick center Y | {JOY_POS_Y:.2f} mm |
        | Joystick PCB overrun past +Y inner wall | {JOY_WALL_RELIEF_DEPTH:.2f} mm |
        | Remaining +Y wall behind PCB relief | {JOY_REMAINING_TOP_WALL:.2f} mm |
        | Front joystick posts to +Y wall | {JOY_FRONT_PIN_TO_WALL_CLEAR:.2f} mm |
        | Sensor barb X offset from joystick | {BARB_TO_JOYSTICK_OFFSET_X:.2f} mm |
        | Sensor holder top to lid rim | {BARB_TO_LID_RIM_CLEARANCE_Z:.2f} mm |
        | Mount center on -X wall | Y={MIC_POS_Y:.2f} mm, Z={MIC_POS_Z:.2f} mm |
        | Mount collar edge margin on {EXT_Y:.0f} mm wall | {MIC_Y_EDGE_MARGIN:.2f} mm each side |
        | USB cable notch X | {USB_NOTCH_X:.2f} mm |
        | USB cable notch wall | -Y |
        | Vent slots wall | -Y |
        | Pressure barb wall | +Y |
        | Screw bosses | 4 (all corners restored) |
        | Nearest -X screw boss clearance in Y | {NEAREST_BOSS_Y_CLEARANCE:.2f} mm |
        ## Changes vs v5.4c
        | Feature | v5.4c | v5.5 |
        |---|---|---|
        | Shell width in X | 168 mm asymmetric | {EXT_X:.0f} mm symmetric |
        | Adapter bay | +X, 32 mm | removed |
        | Component order | Mount, Joystick, Sensor, ESP32+Adapter | Mount, Joystick, Sensor, ESP32 |
        | USB solution | +X adapter bay, direct plug | USB faces -X, -Y cable notch + lid strain relief |
        | ESP32 X position | 28.0 | {ESP_POS_X:.1f} |
        | Joystick X position | -15.0 | {JOY_POS_X:.1f} |
        | Sensor X position | 18.0 | {PRES_POS_X:.1f} |
        | +X+Y screw boss | standard corner | restored (sensor moved to center) |
        | Vent slot wall | -Y (fixed) | -Y |
        | Pressure sensor | +Y wall side-mount, external barb | +Y wall side-mount, external barb |
        | Joystick Y position | upper edge (Y=8.0) | upper edge (Y={JOY_POS_Y:.1f}) |
        | Pneumatic path | external: mouthpiece → +Y barb | external: mouthpiece → +Y barb |
        ## External Dimensions
        - Base footprint: {EXT_X:.1f} x {EXT_Y:.1f} mm
        - Closed enclosure height: {EXT_H_BASE + EXT_H_LID:.1f} mm
        - Joystick protrusion above lid: {STICK_PROTRUSION:.1f} mm
        ## Print Notes
        - Material: PETG preferred, PLA acceptable for quick fit checks
        - Base orientation: floor-down, no support intended
        - Lid orientation: flip 180 deg, ceiling-down
        - USB cable: plug Micro-USB with lid off, route cable to -Y wall notch, close lid
        - External hose path: mouthpiece → leftward (+X) outside enclosure → +Y wall barb
        - The pressure sensor holder is a U-bracket; install sensor against +Y wall, lid retains from above
        - The -X collar remains internal-only; the outer -X wall stays flat for the mic stand
        - Suggested slicer baseline: 0.2 mm layer height, 4 walls, 25% gyroid, 240 C nozzle, 75 C bed, 40% fan
        """
    )
    report_path.write_text(report)


# ── Main ───────────────────────────────────────────────────────────


def main() -> None:
    parser = argparse.ArgumentParser(description="MundMaus v5.5 enclosure")
    parser.add_argument("--outdir", default=".", type=str)
    parser.add_argument("--skip-renders", action="store_true")
    args = parser.parse_args()
    outdir = Path(args.outdir)
    outdir.mkdir(parents=True, exist_ok=True)

    base_path = outdir / "mundmaus_v55_base.stl"
    lid_path = outdir / "mundmaus_v55_lid.stl"
    report_path = outdir / "mundmaus_v55_report.md"

    print(f"MundMaus v5.5 — CadQuery {cq.__version__}")
    print(f"  External: {EXT_X:.1f} x {EXT_Y:.1f} x {EXT_H_BASE + EXT_H_LID:.1f} mm")
    print(f"  Layout: Mount(-X) → Joy(X={JOY_POS_X:.0f}) → Sensor(X={PRES_POS_X:.0f}) → ESP32(X={ESP_POS_X:.0f})")
    print(f"  Mount: -X wall, collar {MIC_COLLAR_D:.1f} mm")

    base = make_base()
    lid = make_lid()

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
