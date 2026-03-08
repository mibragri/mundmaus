#!/usr/bin/env python3
"""MundMaus Enclosure v5.4 - Adapter bay redesign in CadQuery."""
from __future__ import annotations
import argparse
import logging
import math
import re
import textwrap
import warnings
from dataclasses import dataclass
from pathlib import Path
from xml.etree import ElementTree as ET
import cadquery as cq  # type: ignore[import-not-found]
from PIL import Image, ImageDraw  # type: ignore[import-not-found]
warnings.filterwarnings("ignore")
logging.getLogger("OCC").setLevel(logging.ERROR)
# Core shell
CAV_X, CAV_Y, WALL = 130.0, 44.0, 3.0
FLOOR_T, CEIL_T, INNER_R = 3.0, 3.0, 2.5
BASE_INNER_H, LID_INNER_H = 28.0, 7.0
CORNER_R, LID_TOP_R, BASE_BOT_R = 12.0, 3.5, 2.0
LIP_H, LIP_T, LIP_GAP = 4.0, 1.8, 0.15
TOL, TOL_LOOSE = 0.2, 0.3
# Asymmetric +X adapter bay
ADAPTER_BAY_L = 32.0
ADAPTER_L, ADAPTER_W, ADAPTER_H = 25.0, 12.0, 6.0
ADAPTER_RECEPTACLE_SETBACK = 1.2
ESP_USB_PROTRUSION = 2.4
USB_OPEN_W, USB_OPEN_H, USB_OPEN_CHAMFER = 12.6, 8.0, 1.2
USB_CABLE_INSERT_D = 6.8
USB_CENTER_Z = FLOOR_T + 5.5
ADAPTER_GUIDE_CLEAR_W = ADAPTER_W + 0.6
ADAPTER_RAIL_T = 1.4
ADAPTER_SHELF_H = 2.4
ADAPTER_SHELF_X0, ADAPTER_SHELF_X1 = 58.0, 94.0
ADAPTER_HOOD_X0, ADAPTER_HOOD_X1 = 73.5, 82.7
ADAPTER_HOOD_H = ADAPTER_H + 1.8
ADAPTER_WEB_T = 1.4
USB_GUIDE_W, USB_GUIDE_H = 9.6, 4.6
# ESP32-WROOM-32 DevKitC V4
ESP_L, ESP_W, ESP_H = 51.5, 28.0, 1.2
ESP_STANDOFF_H, ESP_GUIDE_H = 3.0, 3.0
ESP_POS_X, ESP_POS_Y = 28.0, -2.0
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
# Tube feedthrough (-X wall)
TUBE_HOLE_D, TUBE_POS_Y, TUBE_POS_Z = 6.5, PRES_POS_Y, 13.0
CABLE_NOTCH_W, CABLE_NOTCH_H = 8.0, 4.0
# M3 screw bosses
SCREW_D, SCREW_BOSS_D, SCREW_BOSS_H = 3.4, 7.0, 10.0
SCREW_PILOT_D, SCREW_INSET = 2.5, 6.0
# 3/8"-16 UNC mic stand mount (+Y wall)
MIC_CLEAR_D, MIC_NUT_SW, MIC_NUT_H = 10.5, 14.29, 5.56
MIC_NUT_TOL, MIC_NUT_POCKET_D, MIC_COLLAR_D = 0.205, 7.9, 24.0
MIC_POS_X = 0.0
# Ventilation
VENT_N, VENT_W, VENT_LEN, VENT_PITCH = 6, 1.6, 14.0, 6.0
# Derived geometry
BASE_EXT_X, EXT_Y = CAV_X + 2 * WALL, CAV_Y + 2 * WALL
TOTAL_CAV_X, TOTAL_EXT_X = CAV_X + ADAPTER_BAY_L, BASE_EXT_X + ADAPTER_BAY_L
SHELL_SHIFT_X = ADAPTER_BAY_L / 2
EXT_H_BASE, EXT_H_LID = FLOOR_T + BASE_INNER_H, CEIL_T + LID_INNER_H
OUTER_NEG_X, OUTER_POS_X = -BASE_EXT_X / 2, BASE_EXT_X / 2 + ADAPTER_BAY_L
INNER_POS_X = CAV_X / 2 + ADAPTER_BAY_L
OUTER_POS_Y, INNER_POS_Y = EXT_Y / 2, EXT_Y / 2 - WALL
MIC_POS_Z = EXT_H_BASE / 2
MIC_NUT_SW_TOL = MIC_NUT_SW + 2 * MIC_NUT_TOL
STICK_TIP_Z = FLOOR_T + JOY_PLATFORM_H + JOY_PCB_H + JOY_STICK_H
LID_TOP_Z = EXT_H_BASE + EXT_H_LID
STICK_PROTRUSION = STICK_TIP_Z - LID_TOP_Z
ESP_PCB_RIGHT_X = ESP_POS_X + ESP_L / 2
ESP_USB_FACE_X = ESP_PCB_RIGHT_X + ESP_USB_PROTRUSION
ADAPTER_BODY_END_X = ESP_USB_FACE_X + ADAPTER_L
ADAPTER_RECEPTACLE_X = ADAPTER_BODY_END_X - ADAPTER_RECEPTACLE_SETBACK
USB_ALIGN_MARGIN = INNER_POS_X - (ADAPTER_RECEPTACLE_X + USB_CABLE_INSERT_D)
USB_OUTER_MARGIN = OUTER_POS_X - ADAPTER_BODY_END_X
SCREW_POSITIONS = [
    (CAV_X / 2 + ADAPTER_BAY_L - SCREW_INSET, CAV_Y / 2 - SCREW_INSET),
    (CAV_X / 2 + ADAPTER_BAY_L - SCREW_INSET, -CAV_Y / 2 + SCREW_INSET),
    (-CAV_X / 2 + SCREW_INSET, CAV_Y / 2 - SCREW_INSET),
    (-CAV_X / 2 + SCREW_INSET, -CAV_Y / 2 + SCREW_INSET),
]
@dataclass(frozen=True)
class RenderView:
    filename: str
    projection_dir: tuple[float, float, float]
    assembled: bool
def organic_box(length: float, width: float, height: float, corner_r: float,
                top_r: float = 0.0, bot_r: float = 0.0) -> cq.Workplane:
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
def _solid_along_y(profile: cq.Workplane, length: float, x: float, y_start: float,
                   z: float) -> cq.Workplane:
    return profile.extrude(length).rotate((0, 0, 0), (1, 0, 0), -90).translate((x, y_start, z))
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
    for dx, dy in [(-1, -1), (-1, 1), (1, -1), (1, 1)]:
        cx = ESP_POS_X + dx * (ESP_L / 2 - post_sz / 2)
        cy = ESP_POS_Y + dy * (ESP_W / 2 - post_sz / 2)
        post = cq.Workplane("XY").workplane(offset=FLOOR_T).center(cx, cy).rect(
            post_sz, post_sz
        ).extrude(ESP_STANDOFF_H)
        base = base.union(post)
    for side in [-1, 1]:
        gy = ESP_POS_Y + side * (ESP_W / 2 + TOL_LOOSE + rail_t / 2)
        rail = cq.Workplane("XY").workplane(offset=FLOOR_T).center(ESP_POS_X, gy).rect(
            ESP_L * 0.55, rail_t
        ).extrude(guide_total)
        base = base.union(rail)
    stop_x = ESP_POS_X - ESP_L / 2 - TOL_LOOSE - rail_t / 2
    stop = cq.Workplane("XY").workplane(offset=FLOOR_T).center(stop_x, ESP_POS_Y).rect(
        rail_t, ESP_W * 0.55
    ).extrude(guide_total)
    return base.union(stop)
def _add_joystick_platform(base: cq.Workplane) -> cq.Workplane:
    plat_x, plat_y = JOY_PCB_L + 5.0, JOY_PCB_W + 5.0
    platform = cq.Workplane("XY").workplane(offset=FLOOR_T).center(JOY_POS_X, JOY_POS_Y).rect(
        plat_x, plat_y
    ).extrude(JOY_PLATFORM_H).edges("|Z").fillet(2.5)
    base = base.union(platform)
    for dx in [-1, 1]:
        for dy in [-1, 1]:
            px = JOY_POS_X + dx * (JOY_PCB_L / 2 - 2.5)
            py = JOY_POS_Y + dy * (JOY_PCB_W / 2 - 2.5)
            pin = cq.Workplane("XY").workplane(offset=FLOOR_T + JOY_PLATFORM_H).center(
                px, py
            ).circle(JOY_PIN_D / 2).workplane(offset=JOY_PIN_H).circle(JOY_PIN_D / 2 - 0.2).loft()
            base = base.union(pin)
    return base
def _add_pressure_sensor_ledge(base: cq.Workplane) -> cq.Workplane:
    lx, ly, lh, lip_h = PRES_L + 4.0, PRES_W + 4.0, 3.0, 1.5
    platform = cq.Workplane("XY").workplane(offset=FLOOR_T).center(PRES_POS_X, PRES_POS_Y).rect(
        lx, ly
    ).extrude(lh).edges("|Z").fillet(1.5)
    base = base.union(platform)
    for cx, cy, sx, sy in [
        (PRES_POS_X, PRES_POS_Y + ly / 2 - 0.75, lx, 1.5),
        (PRES_POS_X, PRES_POS_Y - ly / 2 + 0.75, lx, 1.5),
        (PRES_POS_X + lx / 2 - 0.75, PRES_POS_Y, 1.5, ly),
    ]:
        base = base.union(
            cq.Workplane("XY").workplane(offset=FLOOR_T + lh).center(cx, cy).rect(sx, sy).extrude(
                PRES_H + lip_h
            )
        )
    return base
def _cut_usb_opening(base: cq.Workplane) -> cq.Workplane:
    opening = cq.Workplane("YZ").workplane(offset=OUTER_POS_X + 0.01).center(
        ESP_POS_Y, USB_CENTER_Z
    ).rect(USB_OPEN_W, USB_OPEN_H).extrude(-(WALL + 0.02))
    base = base.cut(opening)
    chamfer = cq.Workplane("YZ").workplane(offset=OUTER_POS_X - USB_OPEN_CHAMFER).center(
        ESP_POS_Y, USB_CENTER_Z
    ).rect(USB_OPEN_W + 2 * USB_OPEN_CHAMFER, USB_OPEN_H + 2 * USB_OPEN_CHAMFER).extrude(
        -(USB_OPEN_CHAMFER + 0.12)
    )
    return base.cut(chamfer)
def _add_adapter_retainer(base: cq.Workplane) -> cq.Workplane:
    guide_outer_w = ADAPTER_GUIDE_CLEAR_W + 2 * ADAPTER_RAIL_T
    shelf_len = ADAPTER_SHELF_X1 - ADAPTER_SHELF_X0
    shelf = cq.Workplane("XY").workplane(offset=FLOOR_T).center(
        (ADAPTER_SHELF_X0 + ADAPTER_SHELF_X1) / 2, ESP_POS_Y
    ).rect(shelf_len, guide_outer_w).extrude(ADAPTER_SHELF_H)
    try:
        shelf = shelf.edges("|Z").fillet(0.8)
    except Exception:
        pass
    base = base.union(shelf)
    rail_len = ADAPTER_SHELF_X1 - (ESP_USB_FACE_X + 2.0)
    rail_z0 = FLOOR_T + ADAPTER_SHELF_H
    rail_h = ADAPTER_H + 1.0
    rail_x = (ESP_USB_FACE_X + 2.0 + ADAPTER_SHELF_X1) / 2
    for side in [-1, 1]:
        rail_y = ESP_POS_Y + side * (ADAPTER_GUIDE_CLEAR_W / 2 + ADAPTER_RAIL_T / 2)
        rail = cq.Workplane("XY").workplane(offset=rail_z0).center(rail_x, rail_y).rect(
            rail_len, ADAPTER_RAIL_T
        ).extrude(rail_h)
        base = base.union(rail)
    hood_len = ADAPTER_HOOD_X1 - ADAPTER_HOOD_X0
    hood = cq.Workplane("XY").workplane(offset=rail_z0).center(
        (ADAPTER_HOOD_X0 + ADAPTER_HOOD_X1) / 2, ESP_POS_Y
    ).rect(hood_len, guide_outer_w).extrude(ADAPTER_HOOD_H)
    tunnel = cq.Workplane("XY").workplane(offset=rail_z0 - 0.01).center(
        (ADAPTER_HOOD_X0 + ADAPTER_HOOD_X1 - ADAPTER_WEB_T) / 2, ESP_POS_Y
    ).rect(hood_len - ADAPTER_WEB_T + 0.02, ADAPTER_GUIDE_CLEAR_W).extrude(ADAPTER_H + 0.8)
    hood = hood.cut(tunnel)
    aperture = cq.Workplane("YZ").workplane(offset=ADAPTER_HOOD_X1 + 0.01).center(
        ESP_POS_Y, USB_CENTER_Z
    ).rect(USB_GUIDE_W, USB_GUIDE_H).extrude(-(ADAPTER_WEB_T + 0.02))
    return base.union(hood).cut(aperture)
def _cut_tube_feedthrough(base: cq.Workplane) -> cq.Workplane:
    tube_cut = cq.Workplane("YZ").workplane(offset=OUTER_NEG_X + WALL * 1.5).center(
        TUBE_POS_Y, FLOOR_T + TUBE_POS_Z
    ).circle(TUBE_HOLE_D / 2).extrude(-WALL * 3)
    base = base.cut(tube_cut)
    try:
        funnel = cq.Workplane("YZ").workplane(offset=OUTER_NEG_X + 0.5).center(
            TUBE_POS_Y, FLOOR_T + TUBE_POS_Z
        ).circle(TUBE_HOLE_D / 2 + 1.5).workplane(offset=-1.5).circle(TUBE_HOLE_D / 2).loft()
        base = base.cut(funnel)
    except Exception:
        pass
    return base
def _cut_cable_notches(base: cq.Workplane) -> cq.Workplane:
    tube_notch = cq.Workplane("YZ").workplane(offset=OUTER_NEG_X + WALL * 1.5).center(
        TUBE_POS_Y, EXT_H_BASE - CABLE_NOTCH_H / 2
    ).rect(CABLE_NOTCH_W, CABLE_NOTCH_H).extrude(-WALL * 3)
    return base.cut(tube_notch)
def _add_mic_mount(base: cq.Workplane) -> cq.Workplane:
    nut_ac_tol = MIC_NUT_SW_TOL / math.cos(math.radians(30))
    collar = _solid_along_y(
        cq.Workplane("XY").circle(MIC_COLLAR_D / 2), MIC_NUT_POCKET_D, MIC_POS_X,
        INNER_POS_Y - MIC_NUT_POCKET_D, MIC_POS_Z
    )
    try:
        collar = collar.faces("<Y").chamfer(1.0)
    except Exception:
        pass
    base = base.union(collar)
    bolt_hole = _solid_along_y(
        cq.Workplane("XY").circle(MIC_CLEAR_D / 2), WALL + 0.02, MIC_POS_X,
        OUTER_POS_Y - WALL - 0.02, MIC_POS_Z
    )
    pocket = _solid_along_y(
        cq.Workplane("XY").polygon(6, nut_ac_tol), MIC_NUT_POCKET_D + 0.02, MIC_POS_X,
        INNER_POS_Y - MIC_NUT_POCKET_D - 0.01, MIC_POS_Z
    )
    return base.cut(bolt_hole).cut(pocket)
def _cut_vent_slots(base: cq.Workplane) -> cq.Workplane:
    for idx in range(VENT_N):
        slot_x = (idx - (VENT_N - 1) / 2.0) * VENT_PITCH
        vent = cq.Workplane("XZ").workplane(offset=CAV_Y / 2 - WALL * 0.5).center(
            slot_x, EXT_H_BASE * 0.55
        ).rect(VENT_W, VENT_LEN).extrude(WALL * 3)
        base = base.cut(vent)
    return base
def make_base() -> cq.Workplane:
    base = organic_box(TOTAL_EXT_X, EXT_Y, EXT_H_BASE, CORNER_R, bot_r=BASE_BOT_R).translate(
        (SHELL_SHIFT_X, 0, 0)
    )
    cavity = rounded_cavity(TOTAL_CAV_X, CAV_Y, BASE_INNER_H + 1.0, INNER_R).translate(
        (SHELL_SHIFT_X, 0, FLOOR_T)
    )
    base = base.cut(cavity)
    for fn in [
        _add_screw_bosses,
        _add_esp_cradle,
        _add_joystick_platform,
        _add_pressure_sensor_ledge,
        _cut_usb_opening,
        _add_adapter_retainer,
        _cut_tube_feedthrough,
        _cut_cable_notches,
        _add_mic_mount,
        _cut_vent_slots,
    ]:
        base = fn(base)
    return base
def make_lid() -> cq.Workplane:
    lip_x, lip_y = TOTAL_CAV_X - 2 * LIP_GAP, CAV_Y - 2 * LIP_GAP
    lip_r = max(0.5, INNER_R - LIP_GAP)
    lid = organic_box(TOTAL_EXT_X, EXT_Y, EXT_H_LID, CORNER_R, top_r=LID_TOP_R).translate(
        (SHELL_SHIFT_X, 0, 0)
    )
    lid = lid.cut(
        rounded_cavity(TOTAL_CAV_X, CAV_Y, LID_INNER_H + 0.01, INNER_R).translate((SHELL_SHIFT_X, 0, 0))
    )
    lip_outer = cq.Workplane("XY").workplane(offset=-LIP_H).center(SHELL_SHIFT_X, 0).rect(
        lip_x, lip_y
    ).extrude(LIP_H).edges("|Z").fillet(lip_r)
    lip_inner = cq.Workplane("XY").workplane(offset=-LIP_H - 0.01).center(SHELL_SHIFT_X, 0).rect(
        lip_x - 2 * LIP_T, lip_y - 2 * LIP_T
    ).extrude(LIP_H + 0.02).edges("|Z").fillet(max(0.3, lip_r - LIP_T))
    lid = lid.union(lip_outer.cut(lip_inner))
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
    tube_lip = cq.Workplane("YZ").workplane(offset=OUTER_NEG_X + WALL * 1.5).center(
        TUBE_POS_Y, -LIP_H / 2
    ).rect(CABLE_NOTCH_W, LIP_H + 0.02).extrude(-WALL * 3)
    lid = lid.cut(tube_lip)
    for px, py in SCREW_POSITIONS:
        lid = lid.cut(
            cq.Workplane("XY").workplane(offset=-LIP_H - 0.01).center(px, py).circle(
                SCREW_D / 2
            ).extrude(EXT_H_LID + LIP_H + 0.02)
        )
    for side in [-1, 0, 1]:
        for idx in range(3):
            slot_x = side * 35.0 + (idx - 1) * (VENT_PITCH - 0.5)
            lid = lid.cut(
                cq.Workplane("XY").workplane(offset=-0.01).center(slot_x, 0).rect(
                    VENT_W, VENT_LEN + 2
                ).extrude(EXT_H_LID + 0.02)
            )
    try:
        lid = lid.union(
            cq.Workplane("XY").workplane(offset=EXT_H_LID).center(SHELL_SHIFT_X, 14).text(
                "MundMaus v5.4", 7, 0.6, font="Liberation Sans:Bold"
            )
        )
    except Exception:
        pass
    return lid
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
def _collect_svg_lines(node: ET.Element, stroke: str, hidden: bool,
                       lines: list[tuple[tuple[float, float], tuple[float, float], tuple[int, int, int], bool]]) -> None:
    tag = node.tag.rsplit("}", 1)[-1]
    stroke = node.attrib.get("stroke", stroke)
    hidden = hidden or "stroke-dasharray" in node.attrib
    if tag == "path":
        points = _parse_svg_path(node.attrib.get("d", ""))
        for start, end in zip(points, points[1:]):
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
    scale = min((width - 2 * pad) / max(max_x - min_x, 1.0), (height - 2 * pad) / max(max_y - min_y, 1.0))
    def map_point(point: tuple[float, float]) -> tuple[float, float]:
        return (pad + (point[0] - min_x) * scale, height - (pad + (point[1] - min_y) * scale))
    image = Image.new("RGB", (width, height), "white")
    draw = ImageDraw.Draw(image)
    for hidden_pass in [True, False]:
        for start, end, color, is_hidden in lines:
            if is_hidden == hidden_pass:
                draw.line([map_point(start), map_point(end)], fill=color, width=1 if hidden_pass else 3)
    image.save(png_path)
    svg_path.unlink(missing_ok=True)
def _assembly_shape(base: cq.Workplane, lid: cq.Workplane) -> cq.Shape:
    return cq.Compound.makeCompound([base.val(), lid.translate((0, 0, EXT_H_BASE)).val()])
def render_pngs(base: cq.Workplane, lid: cq.Workplane, outdir: Path) -> None:
    views = [
        RenderView("mundmaus_v54_assembly.png", (1.0, -1.0, 0.8), True),
        RenderView("mundmaus_v54_top.png", (0.0, 0.0, 1.0), True),
        RenderView("mundmaus_v54_side.png", (1.0, -0.2, 0.15), False),
        RenderView("mundmaus_v54_back.png", (0.0, -1.0, 0.0), False),
    ]
    assembly = _assembly_shape(base, lid)
    for view in views:
        svg_path = outdir / view.filename.replace(".png", ".svg")
        cq.exporters.export(assembly if view.assembled else base, str(svg_path), opt={
            "width": 1400,
            "height": 1000,
            "projectionDir": view.projection_dir,
            "showHidden": True,
        })
        _svg_to_png(svg_path, outdir / view.filename)
def write_report(report_path: Path) -> None:
    report = textwrap.dedent(
        f"""\
        # MundMaus v5.4 Enclosure
        ## Summary
        v5.4 replaces the v5.3 USB-C panel-mount on the +Y wall with an asymmetric +X adapter bay.
        The ESP32 remains on the v5.3 left-shifted X=28 layout and gains a protected adapter cradle,
        while the 3/8"-16 gooseneck mount moves back to the +Y wall.
        ## Clearance Analysis
        | Item | Value |
        |---|---:|
        | ESP32 PCB right edge | {ESP_PCB_RIGHT_X:.2f} mm |
        | ESP32 Micro-USB nose | {ESP_USB_FACE_X:.2f} mm |
        | Adapter body end (+X) | {ADAPTER_BODY_END_X:.2f} mm |
        | Adapter receptacle plane | {ADAPTER_RECEPTACLE_X:.2f} mm |
        | +X inner wall | {INNER_POS_X:.2f} mm |
        | +X outer wall | {OUTER_POS_X:.2f} mm |
        | Receptacle to inner wall | {INNER_POS_X - ADAPTER_RECEPTACLE_X:.2f} mm |
        | USB-C insertion depth target | {USB_CABLE_INSERT_D:.2f} mm |
        | Remaining alignment margin | {USB_ALIGN_MARGIN:.2f} mm |
        | Adapter body to outer wall | {USB_OUTER_MARGIN:.2f} mm |
        Assumptions: typical direct adapter body {ADAPTER_L:.0f}x{ADAPTER_W:.0f}x{ADAPTER_H:.0f} mm,
        receptacle setback {ADAPTER_RECEPTACLE_SETBACK:.1f} mm, USB-C plug insertion depth {USB_CABLE_INSERT_D:.1f} mm.
        The old SCAD failure mode came from using the pre-v5.3 ESP32 position; keeping X=28 and extending the bay
        to {ADAPTER_BAY_L:.0f} mm leaves >10 mm of insertion/alignment reserve after wall thickness is accounted for.
        ## Changes vs v5.3
        | Feature | v5.3 | v5.4 |
        |---|---|---|
        | USB solution | +Y bulkhead panel mount | +X direct adapter bay |
        | Internal cable | short USB-C to Micro-B | none |
        | +Y wall | panel hole + nut recess | gooseneck mount collar + hex pocket |
        | Shell width in X | {BASE_EXT_X:.0f} mm symmetric | {TOTAL_EXT_X:.0f} mm asymmetric |
        | Adapter retention | cable clips for loose lead | shelf, side rails, capture hood |
        ## External Dimensions
        - Base footprint: {TOTAL_EXT_X:.1f} x {EXT_Y:.1f} mm
        - Closed enclosure height: {EXT_H_BASE + EXT_H_LID:.1f} mm
        - Adapter bay extension on +X: {ADAPTER_BAY_L:.1f} mm
        - Joystick protrusion above lid: {STICK_PROTRUSION:.1f} mm
        ## Print Notes
        - Material: PETG preferred, PLA acceptable for quick fit checks
        - Base orientation: floor-down, no support intended
        - Lid orientation: flip 180 deg, ceiling-down
        - Adapter retainer hood bridges {ADAPTER_GUIDE_CLEAR_W:.1f} mm; this stays inside the PETG 10-15 mm bridge guideline
        - Suggested slicer baseline: 0.2 mm layer height, 4 walls, 25% gyroid, 240 C nozzle, 75 C bed, 40% fan
        """
    )
    report_path.write_text(report)
def main() -> None:
    parser = argparse.ArgumentParser(description="MundMaus v5.4 enclosure")
    parser.add_argument("--outdir", default=".", type=str)
    parser.add_argument("--skip-renders", action="store_true")
    args = parser.parse_args()
    outdir = Path(args.outdir)
    outdir.mkdir(parents=True, exist_ok=True)
    base_path = outdir / "mundmaus_v54_base.stl"
    lid_path = outdir / "mundmaus_v54_lid.stl"
    report_path = outdir / "mundmaus_v54_report.md"
    print(f"MundMaus v5.4 - CadQuery {cq.__version__}")
    print(f"  External: {TOTAL_EXT_X:.1f} x {EXT_Y:.1f} x {EXT_H_BASE + EXT_H_LID:.1f} mm")
    print(f"  Adapter bay: +X {ADAPTER_BAY_L:.1f} mm, USB margin {USB_ALIGN_MARGIN:.1f} mm")
    print(f"  Mount: +Y wall, collar {MIC_COLLAR_D:.1f} mm, nut SW {MIC_NUT_SW_TOL:.1f} mm")
    base = make_base()
    lid = make_lid()
    export_stl(base, base_path)
    export_stl(lid.rotateAboutCenter((1, 0, 0), 180).translate((0, 0, EXT_H_LID)), lid_path)
    write_report(report_path)
    if not args.skip_renders:
        render_pngs(base, lid, outdir)
    print("Done.")
if __name__ == "__main__":
    main()
