#!/usr/bin/env python3
"""Generate a small fit-test piece for critical MundMaus enclosure features.

Instead of printing the full base (~1.5h), this generates a ~15min print
that tests only the critical fits:
1. One joystick pillar with alignment pin (PCB hole fit)
2. ESP32 cradle corner (PCB + guide rail fit)
3. Mic nut pocket (nut insertion test)
4. USB plug clearance between two pillars (horizontal plug test)

Each test piece sits on a thin base plate for easy printing.
"""

import argparse
from pathlib import Path

import cadquery as cq

from mundmaus_v55_enclosure import (
    FLOOR_T, WALL,
    ESP_POS_X, ESP_POS_Y, ESP_L, ESP_W, ESP_H,
    ESP_STANDOFF_H, ESP_GUIDE_H,
    JOY_POS_X, JOY_POS_Y, JOY_HOLE_GRID_X, JOY_HOLE_GRID_Y,
    JOY_PLATFORM_H, JOY_PIN_D, JOY_PIN_H,
    MIC_NUT_SW, MIC_NUT_TOL, MIC_NUT_POCKET_D, MIC_COLLAR_D,
    MIC_POS_Y, MIC_POS_Z, MIC_CLEAR_D,
    TOL_LOOSE,
)
import math


def make_pillar_test():
    """Two pillars at correct grid spacing + pins — tests PCB hole fit."""
    pillar_d = 6.0
    flare_d = 9.0
    flare_h = 3.0
    base_t = 2.0
    pad = 5.0

    # Two right-side pillars (the ones near USB)
    grid_y = JOY_HOLE_GRID_Y
    total_y = grid_y + flare_d + 2 * pad
    total_x = flare_d + 2 * pad

    base = cq.Workplane("XY").rect(total_x, total_y).extrude(base_t)

    for dy in [-1, 1]:
        py = dy * grid_y / 2
        # Flare
        flare = cq.Workplane("XY").workplane(offset=base_t - 0.5).center(0, py).circle(
            flare_d / 2
        ).workplane(offset=flare_h + 0.5).circle(pillar_d / 2).loft()
        # Shaft
        shaft = cq.Workplane("XY").workplane(offset=base_t + flare_h).center(0, py).circle(
            pillar_d / 2
        ).extrude(JOY_PLATFORM_H - flare_h)
        # Pin
        pin = cq.Workplane("XY").workplane(offset=base_t + JOY_PLATFORM_H).center(0, py).circle(
            JOY_PIN_D / 2
        ).workplane(offset=JOY_PIN_H).circle(JOY_PIN_D / 2 - 0.2).loft()
        base = base.union(flare).union(shaft).union(pin)

    # Label
    try:
        base = base.union(
            cq.Workplane("XY").workplane(offset=base_t).center(0, 0).text(
                "PILLARx2", 4, 0.5, font="Liberation Sans:Bold"
            )
        )
    except Exception:
        pass

    return base


def make_esp_cradle_test():
    """One corner of ESP32 cradle — tests PCB + guide rail fit."""
    base_t = 2.0
    post_sz = 3.5
    rail_t = 1.5
    guide_total = ESP_STANDOFF_H + ESP_H + ESP_GUIDE_H
    pad = 3.0

    # Small section: 25mm x 20mm base
    section_x = 25.0
    section_y = ESP_W / 2 + TOL_LOOSE + rail_t + 2 * pad

    base = cq.Workplane("XY").rect(section_x, section_y * 2).extrude(base_t)

    # Two corner posts (one edge of ESP)
    for dy in [-1, 1]:
        cx = -section_x / 2 + pad + post_sz / 2
        cy = dy * (ESP_W / 2 - post_sz / 2)
        post = cq.Workplane("XY").workplane(offset=base_t).center(cx, cy).rect(
            post_sz, post_sz
        ).extrude(ESP_STANDOFF_H)
        base = base.union(post)

    # Guide rail (one side)
    for side in [-1, 1]:
        gy = side * (ESP_W / 2 + TOL_LOOSE + rail_t / 2)
        rail = cq.Workplane("XY").workplane(offset=base_t).center(0, gy).rect(
            section_x * 0.6, rail_t
        ).extrude(guide_total)
        base = base.union(rail)

    try:
        base = base.union(
            cq.Workplane("XY").workplane(offset=base_t).center(0, 0).text(
                "ESP32", 5, 0.5, font="Liberation Sans:Bold"
            )
        )
    except Exception:
        pass

    return base


def make_nut_pocket_test():
    """Mic mount nut pocket section — tests nut insertion fit."""
    base_t = 2.0
    nut_ac = (MIC_NUT_SW + 2 * MIC_NUT_TOL) / math.cos(math.radians(30))

    # Small wall section with nut pocket
    wall_section_x = WALL + MIC_NUT_POCKET_D + 5
    wall_section_y = MIC_COLLAR_D + 10
    wall_section_z = 20.0

    base = cq.Workplane("XY").rect(wall_section_x + 10, wall_section_y).extrude(base_t)

    # Wall
    wall = cq.Workplane("XY").workplane(offset=base_t).center(
        -wall_section_x / 2, 0
    ).rect(WALL, wall_section_y).extrude(wall_section_z)
    base = base.union(wall)

    # Collar
    collar = cq.Workplane("YZ").workplane(offset=-wall_section_x / 2 + WALL - 0.5).center(
        0, base_t + wall_section_z / 2
    ).circle(MIC_COLLAR_D / 2).extrude(MIC_NUT_POCKET_D + 0.5)
    base = base.union(collar)

    # Bolt hole
    bolt = cq.Workplane("YZ").workplane(offset=-wall_section_x / 2 - 0.01).center(
        0, base_t + wall_section_z / 2
    ).circle(MIC_CLEAR_D / 2).extrude(WALL + 0.02)
    base = base.cut(bolt)

    # Hex nut pocket
    pocket = cq.Workplane("YZ").workplane(
        offset=-wall_section_x / 2 + WALL + MIC_NUT_POCKET_D + 0.01
    ).center(0, base_t + wall_section_z / 2).polygon(
        6, (MIC_NUT_SW + 2 * MIC_NUT_TOL) / math.cos(math.radians(30))
    ).extrude(-(MIC_NUT_POCKET_D + 0.02))
    base = base.cut(pocket)

    try:
        base = base.union(
            cq.Workplane("XY").workplane(offset=base_t).center(5, 0).text(
                "NUT", 5, 0.5, font="Liberation Sans:Bold"
            )
        )
    except Exception:
        pass

    return base


def export_stl(shape, filepath):
    cq.exporters.export(shape, str(filepath), exportType="STL", tolerance=0.01, angularTolerance=0.1)


def main():
    parser = argparse.ArgumentParser(description="MundMaus fit-test generator")
    parser.add_argument("--outdir", default="output", type=str)
    parser.add_argument("--part", choices=["pillar", "esp", "nut", "all"], default="all")
    args = parser.parse_args()
    outdir = Path(args.outdir)
    outdir.mkdir(parents=True, exist_ok=True)

    tests = {
        "pillar": ("mundmaus_fit_test_pillar.stl", make_pillar_test,
                    "2 Säulen mit Pins — KY-023 PCB auflegen und Loch-Fit testen"),
        "esp": ("mundmaus_fit_test_esp.stl", make_esp_cradle_test,
                "ESP32 Cradle-Ecke — PCB einlegen und Passung testen"),
        "nut": ("mundmaus_fit_test_nut.stl", make_nut_pocket_test,
                "Mic-Mount Mutter-Tasche — 3/8-16 Mutter einsetzen testen"),
    }

    parts = [args.part] if args.part != "all" else list(tests.keys())

    for part in parts:
        filename, gen_fn, desc = tests[part]
        print(f"Generating {part}: {desc}")
        shape = gen_fn()
        filepath = outdir / filename
        export_stl(shape, filepath)
        size_kb = filepath.stat().st_size / 1024
        print(f"  → {filepath} ({size_kb:.0f} KB)")

    print(f"\nDrucken: ~5-10 min pro Teil, alle zusammen ~15-20 min")
    print(f"Danach: echte Bauteile probeweise einsetzen")


if __name__ == "__main__":
    main()
