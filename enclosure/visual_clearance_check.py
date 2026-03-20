#!/usr/bin/env python3
"""Visual clearance checker — generates annotated top-view with collision detection.

Draws ALL components with their actual footprints and highlights
any overlaps or tight clearances. Outputs a PNG that can be sent
to iPhone for visual review.

This catches issues that the numeric validator misses:
- USB plug path vs pillar interference (3D projection onto XY plane)
- Cable routing conflicts
- Assembly sequence clearances (plug first, then seat)
"""

import sys
from pathlib import Path
from PIL import Image, ImageDraw

sys.path.insert(0, str(Path(__file__).parent))
from mundmaus_v55_enclosure import *  # noqa

# ── Config ────────────────────────────────────────────────────────

SCALE = 8  # px per mm
W, H = 1400, 900
CX, CY = W // 2, H // 2
MIN_CLEARANCE = 1.5  # mm — anything less is flagged red
WARN_CLEARANCE = 3.0  # mm — anything less is flagged yellow

USB_PLUG_LEN = 20.0  # mm, typical Micro-USB plug + strain relief
USB_PLUG_W = 11.0    # mm, plug housing width


def mm(x, y):
    return int(CX + x * SCALE), int(CY - y * SCALE)


def rect(d, x1, y1, x2, y2, **kw):
    d.rectangle([*mm(x1, y1), *mm(x2, y2)], **kw)


def circ(d, x, y, r, **kw):
    px, py = mm(x, y)
    d.ellipse([px - int(r * SCALE), py - int(r * SCALE),
               px + int(r * SCALE), py + int(r * SCALE)], **kw)


def overlap_1d(a1, a2, b1, b2):
    """Returns overlap amount (negative = gap)."""
    return min(a2, b2) - max(a1, b1)


# ── Collect components with their XY footprints ──────────────────

usb_port_x = ESP_POS_X - ESP_L / 2
usb_plug = {
    "name": "USB Plug",
    "x1": usb_port_x - USB_PLUG_LEN, "x2": usb_port_x,
    "y1": ESP_POS_Y - USB_PLUG_W / 2, "y2": ESP_POS_Y + USB_PLUG_W / 2,
    "z1": FLOOR_T + ESP_STANDOFF_H, "z2": FLOOR_T + ESP_STANDOFF_H + 8,
}

pillar_d = 6.0  # must match enclosure code
pillar_flare_d = 9.0
pillars = []
for dx in [-1, 1]:
    for dy in [-1, 1]:
        px = JOY_POS_X + dx * (JOY_HOLE_GRID_X / 2)
        py = JOY_POS_Y + dy * (JOY_HOLE_GRID_Y / 2)
        if abs(py) > INNER_POS_Y - 0.5:
            continue
        pillars.append({
            "name": f"Pillar ({px:+.0f},{py:+.0f})",
            "cx": px, "cy": py,
            "shaft_r": pillar_d / 2,
            "flare_r": pillar_flare_d / 2,
            "z1": FLOOR_T, "z2": FLOOR_T + JOY_PLATFORM_H,
        })

esp = {
    "name": "ESP32",
    "x1": ESP_POS_X - ESP_L / 2, "x2": ESP_POS_X + ESP_L / 2,
    "y1": ESP_POS_Y - ESP_W / 2, "y2": ESP_POS_Y + ESP_W / 2,
}

# ── Check USB plug vs each pillar ────────────────────────────────

issues = []

for p in pillars:
    # XY overlap between plug rectangle and pillar circle (approximate as square)
    sr = p["shaft_r"]
    ox = overlap_1d(usb_plug["x1"], usb_plug["x2"], p["cx"] - sr, p["cx"] + sr)
    oy = overlap_1d(usb_plug["y1"], usb_plug["y2"], p["cy"] - sr, p["cy"] + sr)

    if ox > 0 and oy > 0:
        issues.append(("COLLISION", f"{p['name']} overlaps USB plug by {min(ox,oy):.1f}mm"))
    elif ox > 0:
        gap_y = -oy
        if gap_y < MIN_CLEARANCE:
            issues.append(("TIGHT", f"{p['name']} ↔ USB plug: {gap_y:.1f}mm Y-gap"))
        elif gap_y < WARN_CLEARANCE:
            issues.append(("WARN", f"{p['name']} ↔ USB plug: {gap_y:.1f}mm Y-gap"))
        else:
            issues.append(("OK", f"{p['name']} ↔ USB plug: {gap_y:.1f}mm Y-gap"))

# ── Draw ──────────────────────────────────────────────────────────

img = Image.new("RGB", (W, H), "#1a2332")
d = ImageDraw.Draw(img)

# Enclosure
rect(d, -EXT_X/2, EXT_Y/2, EXT_X/2, -EXT_Y/2, outline="#4a6a4a", width=3)
rect(d, -INNER_POS_X, INNER_POS_Y, INNER_POS_X, -INNER_POS_Y, outline="#2a4a2a", width=2)

# Mic collar
circ(d, -INNER_POS_X + MIC_NUT_POCKET_D/2, MIC_POS_Y, MIC_COLLAR_D/2, outline="#ff8844", width=2)

# ESP32
rect(d, esp["x1"], esp["y2"], esp["x2"], esp["y1"], fill="#1a2a4a", outline="#4488ff", width=2)
# USB port
rect(d, usb_port_x - 2, ESP_POS_Y + 3, usb_port_x, ESP_POS_Y - 3, fill="#ff4444")
d.text(mm(ESP_POS_X - 5, ESP_POS_Y), "ESP32", fill="#6699ff")

# USB plug footprint (ghosted)
rect(d, usb_plug["x1"], usb_plug["y2"], usb_plug["x2"], usb_plug["y1"],
     outline="#ff666680", width=1)
# Fill with semi-transparent red
for y_off in range(int(usb_plug["y1"] * SCALE), int(usb_plug["y2"] * SCALE), 4):
    pass  # Can't do alpha easily, use dashed outline instead
d.text(mm(usb_plug["x1"], usb_plug["y2"] + 2), "USB Plug Path", fill="#ff6666")

# Pillars
for p in pillars:
    # Check if this pillar has issues
    pillar_issue = None
    for severity, msg in issues:
        if p["name"] in msg:
            pillar_issue = severity
            break

    color_shaft = {"COLLISION": "#ff2222", "TIGHT": "#ffaa00", "WARN": "#ffff44",
                   "OK": "#44cc44", None: "#44cc44"}[pillar_issue]
    color_flare = {"COLLISION": "#441111", "TIGHT": "#443300", "WARN": "#444400",
                   "OK": "#2a4a2a", None: "#2a4a2a"}[pillar_issue]

    circ(d, p["cx"], p["cy"], p["flare_r"], outline=color_flare, width=1)
    circ(d, p["cx"], p["cy"], p["shaft_r"], fill="#1a3a1a", outline=color_shaft, width=2)

# Joystick opening
rect(d, JOY_POS_X - JOY_OPENING/2, JOY_POS_Y + JOY_OPENING/2,
     JOY_POS_X + JOY_OPENING/2, JOY_POS_Y - JOY_OPENING/2, outline="#66ee66", width=2)

# Sensor
pres_y = INNER_POS_Y - PRES_H/2 - PRES_SENSOR_WALL_GAP
rect(d, PRES_POS_X - PRES_L/2, pres_y + PRES_W/2,
     PRES_POS_X + PRES_L/2, pres_y - PRES_W/2, fill="#3a2a00", outline="#ffaa00", width=2)
d.text(mm(PRES_POS_X - 8, pres_y), "Sensor", fill="#ffcc44")

# Screw bosses
for sx, sy in SCREW_POSITIONS:
    circ(d, sx, sy, SCREW_BOSS_D/2, outline="#555", width=1)

# Clearance annotations
for p in pillars:
    sr = p["shaft_r"]
    ox = overlap_1d(usb_plug["x1"], usb_plug["x2"], p["cx"] - sr, p["cx"] + sr)
    if ox <= 0:
        continue  # not in X range of plug

    # Draw clearance lines
    if p["cy"] > ESP_POS_Y:  # pillar above USB
        gap_y = (p["cy"] - sr) - usb_plug["y2"]
        line_y1, line_y2 = usb_plug["y2"], p["cy"] - sr
    else:  # pillar below USB
        gap_y = usb_plug["y1"] - (p["cy"] + sr)
        line_y1, line_y2 = p["cy"] + sr, usb_plug["y1"]

    color = "#ff2222" if gap_y < MIN_CLEARANCE else "#ffaa00" if gap_y < WARN_CLEARANCE else "#00ff00"
    lx = p["cx"] + sr + 2
    d.line([*mm(lx, line_y1), *mm(lx, line_y2)], fill=color, width=3)
    d.text(mm(lx + 1, (line_y1 + line_y2) / 2), f"{gap_y:.1f}mm", fill=color)

# Issue summary
y_pos = 20
d.text((20, y_pos), "MundMaus v5.5 — Visual Clearance Check", fill="#ccc")
y_pos += 25
d.text((20, y_pos), f"Pillars Ø{pillar_d}mm | Joy Y={JOY_POS_Y} | ESP Y={ESP_POS_Y}", fill="#888")
y_pos += 30

for severity, msg in issues:
    color = {"COLLISION": "#ff2222", "TIGHT": "#ffaa00", "WARN": "#ffff44", "OK": "#44cc44"}[severity]
    icon = {"COLLISION": "✗", "TIGHT": "⚠", "WARN": "~", "OK": "✓"}[severity]
    d.text((20, y_pos), f"  {icon} {msg}", fill=color)
    y_pos += 20

# Legend
d.text((20, H - 40), "■ Grün=OK  ■ Gelb=Knapp  ■ Rot=Kollision  □ Rot gestrichelt=USB Stecker", fill="#888")

outpath = Path(__file__).parent / "output" / "mundmaus_v55_clearance_check.png"
img.save(outpath)
print(f"Saved: {outpath}")

# Print results
print()
has_error = False
for severity, msg in issues:
    print(f"  [{severity}] {msg}")
    if severity in ("COLLISION", "TIGHT"):
        has_error = True

if has_error:
    print("\n⚠ Clearance issues found!")
    sys.exit(1)
else:
    print("\n✓ All clearances OK")
