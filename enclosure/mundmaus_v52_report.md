# MundMaus Enclosure v5.2 — Mount on Right Short Side

## Summary

Mount collar relocated from +Y wall (top long side) to +X wall (right short side).
Patient lies below at -Y; gooseneck enters from the right side.

## Changes vs v5.1

| Feature | v5.1 | v5.2 |
|---------|------|------|
| Gooseneck mount | +Y wall (top long side) | **+X wall (right short side)** |
| USB cutout | +X wall (direct connector) | **+Y wall (cable exit)** |
| ESP32 position X | 35.0 mm | **28.0 mm** (shifted left for collar clearance) |
| USB height | 3.0 mm | **3.5 mm** (cable routing clearance) |
| Cable notch (USB) | +X wall | **+Y wall** |

## Layout (top view)

```
+Y wall (TOP — USB cable exit)
+------------------------------------------------------+
| [Sensor(-48)]  [Joystick(-15)]     [ESP32(28)]       |mount(+X)
+------------------------------------------------------+
-Y wall (BOTTOM — vents, closest to patient)
```

## Dimensions

- External: 136 x 50 x 41 mm (unchanged)
- Cavity: 130 x 44 x 35 mm (unchanged)
- Mount collar: 24mm diameter on 50mm wall face, centered at Y=0, Z=15.5
- Joystick protrusion: 3.1 mm above lid (target >= 3mm)
- Hex nut pocket: 14.7mm across-flats (3/8"-16 UNC)

## Clearance Analysis

- ESP32 right edge (X=53.75) to collar inner face (X=57.1): **3.35mm** clearance
- Collar (24mm dia) on 50mm wall: **13mm** margin each side in Y
- Collar Z range (3.5–27.5) within 31mm base height: **3.5mm** margin top/bottom
- No conflict between collar and screw bosses (nearest boss at Y=16, collar R=12)

## USB Cable Routing

USB connector on ESP32 faces +X (toward mount). Cable must route internally
to +Y wall exit at X=45. Cable plugged in from inside; case must be opened
for programming. Cable exit on +Y wall (away from patient) prevents cable
dangling toward patient's face.

## Print Settings (PETG, Bambu Lab P2S)

- Base: floor-down, no supports needed
- Lid: ceiling-down (flipped 180deg), no supports
- Infill: 25% Gyroid, 4 walls
- Temperature: 240C nozzle, 75C bed, 40% fan
- Layer height: 0.2mm recommended

## Files

- `mundmaus_v52_enclosure.py` — CadQuery source (357 lines)
- `mundmaus_v52_base.stl` — Base part (1172 kB)
- `mundmaus_v52_lid.stl` — Lid part (1083 kB)
- `mundmaus_v52_assembly_iso.svg` — ISO assembly view
- `mundmaus_v52_mount_side.svg` — Right side (+X mount) view
- `mundmaus_v52_top_view.svg` — Top view
- `mundmaus_v52_base_interior.svg` — Base interior view
