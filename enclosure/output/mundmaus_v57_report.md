# MundMaus v5.7 Enclosure — Lid-Only Fix
## Summary
v5.7 changes from v5.6 (LID ONLY, base unchanged):
- **LIP_H 3.0 mm** (was 4.0): fixes collision between lid inner lip and sensor PCB top at z=25.5.
  Lip zone now 27.0–30, giving 1.5mm clearance above the sensor.
- **RIDGE_H 0.6 mm** (was 0.5): 20% more detent retention force.
- **RIDGE_Z 1.0 mm** (was 2.0): realigned so ridges still meet existing base grooves at z=28.

Ridge/groove alignment (assembly coords):
- Base groove z = EXT_H_BASE - 4.0 + 2.0 = 28 mm (v5.6 base, UNCHANGED)
- Lid ridge z  = EXT_H_BASE - 3.0 + 1.0 = 28.0 mm ✓

Component positions along X axis:
- Mic mount collar: -X wall (internal, -58.1 inner edge)
- Joystick center: X=-19.0 (platform -37.5 to -0.5)
- ESP32 center: X=35.0 (PCB 7.8 to 62.2, USB at -X end)
- Sensor shelf: +X inner wall, shelf X=61.0 to 66.0, Z=5.5 to 25.5
## Clearance Analysis
| Item | Value |
|---|---:|
| Lip zone bottom (was 26.0) | 27.0 mm |
| Sensor PCB top to lip zone | 1.5 mm |
| Ridge height (was 0.5) | 0.6 mm |
| Ridge interference with groove (GROOVE_D=0.55) | +0.05 mm |
| Ridge Z in assembly coords | 28.0 mm (matches base groove) |
| Mic collar to joystick platform | 20.60 mm |
| ESP32 right edge to +X inner wall | 3.80 mm |
| Sensor shelf inner edge X | 61.0 mm |
| Sensor bottom Z to ESP32 PCB top Z | -0.7 mm |
| Hold-down wall gap (lid closed) | 1.0 mm |
| Barb hole diameter | 2.8 mm (press-fit) |
| Pressure barb wall | +X |
| Lid attachment | detent ridges (7 points, 0.6mm) |
## Changes vs v5.6
| Feature | v5.6 | v5.7 |
|---|---|---|
| LIP_H | 4.0 mm | 3.0 mm |
| RIDGE_H | 0.5 mm | 0.6 mm |
| RIDGE_Z | 2.0 mm | 1.0 mm |
| Base STL | — | unchanged (reuse v5.6 print) |
## External Dimensions
- Base footprint: 136.0 x 50.0 mm
- Closed enclosure height: 39.0 mm
- Joystick protrusion above lid: 2.6 mm
## Print Notes
- Material: PETG preferred, PLA acceptable for quick fit checks
- Base orientation: floor-down, no support intended
- Lid orientation: flip 180 deg, ceiling-down
- USB cable: plug Micro-USB with lid off, route cable to -Y wall notch, close lid
- External hose path: mouthpiece -> +X wall barb (straight run, minimal bending)
- Pressure sensor: place PCB flat against +X inner wall, nipple through barb hole, lid retains from above
- The -X collar remains internal-only; the outer -X wall stays flat for the mic stand
- Suggested slicer baseline: 0.2 mm layer height, 4 walls, 25% gyroid, 240 C nozzle, 75 C bed, 40% fan
