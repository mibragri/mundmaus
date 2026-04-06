# MundMaus v5.6 Enclosure
## Summary
v5.6 changes from v5.5:
- **Pressure sensor relocated** from +Y wall to +X wall (flat mount, barb through +X)
- **ESP32 hold-down wall** shortened by 1mm clearance so lid closes properly

Component positions along X axis:
- Mic mount collar: -X wall (internal, -58.1 inner edge)
- Joystick center: X=-19.0 (platform -37.5 to -0.5)
- ESP32 center: X=35.0 (PCB 7.8 to 62.2, USB at -X end)
- Sensor shelf: +X inner wall, shelf X=61.0 to 66.0, Z=5.5 to 25.5
## Clearance Analysis
| Item | Value |
|---|---:|
| Mic collar to joystick platform | 20.60 mm |
| ESP32 right edge to +X inner wall | 3.80 mm |
| Sensor shelf inner edge X | 61.0 mm |
| Sensor bottom Z to ESP32 PCB top Z | -0.7 mm |
| Hold-down wall gap (lid closed) | 1.0 mm |
| Barb hole diameter | 2.8 mm (press-fit) |
| Joystick center Y | -2.00 mm |
| Joystick PCB overrun past +Y inner wall | 0.00 mm |
| Remaining +Y wall behind PCB relief | 2.00 mm |
| Front joystick posts to +Y wall | 14.50 mm |
| Mount center on -X wall | Y=0.00 mm, Z=13.50 mm |
| Mount collar edge margin on 50 mm wall | 13.00 mm each side |
| USB cable notch X | 7.80 mm |
| USB cable notch wall | -Y |
| Vent slots wall | -Y |
| Pressure barb wall | +X |
| Lid attachment | detent ridges (7 points) |
## Changes vs v5.5
| Feature | v5.5 | v5.6 |
|---|---|---|
| Pressure sensor mount | +Y wall shelf at X=42 | +X wall flat mount, shelf at Z=6 |
| Barb hole | +Y wall, D3.0mm | +X wall, D2.8mm (press-fit) |
| Hose routing | mouthpiece -> +Y barb | mouthpiece -> +X barb |
| Hold-down wall | touches ESP32 PCB (0mm gap) | 1mm clearance |
| Sensor mount in pipeline | missing (not called) | added to make_base() |
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
