# MundMaus v5.5 Enclosure
## Summary
v5.5 is a compact symmetric redesign. Key changes from v5.4c:
- **Removed adapter bay** — enclosure shrinks from 168 to 136 mm
- **New component order**: Mount(-X) → Joystick → Sensor → ESP32(+X)
- **ESP32 USB faces -X** (center) for plug access; cable routes to -Y wall notch
- 4 screw bosses (restored +X+Y, sensor moved to center)

Component positions along X axis:
- Mic mount collar: -X wall (internal, -58.1 inner edge)
- Joystick center: X=-19.0 (platform -37.5 to -0.5)
- Sensor bracket: X=42.0 (bracket 30.0 to 54.0)
- ESP32 center: X=35.0 (PCB 7.8 to 62.2, USB at -X end)
## Clearance Analysis
| Item | Value |
|---|---:|
| Mic collar to joystick platform | 20.60 mm |
| Joystick platform to sensor bracket | 30.50 mm |
| ESP32 right edge to +X inner wall | 3.80 mm |
| Joystick center Y | -2.00 mm |
| Joystick PCB overrun past +Y inner wall | 0.00 mm |
| Remaining +Y wall behind PCB relief | 2.00 mm |
| Front joystick posts to +Y wall | 14.50 mm |
| Sensor barb X offset from joystick | 61.00 mm |
| Sensor holder top to lid rim | 2.50 mm |
| Mount center on -X wall | Y=0.00 mm, Z=15.00 mm |
| Mount collar edge margin on 50 mm wall | 13.00 mm each side |
| USB cable notch X | 7.80 mm |
| USB cable notch wall | -Y |
| Vent slots wall | -Y |
| Pressure barb wall | +Y |
| Screw bosses | 4 (all corners restored) |
| Nearest -X screw boss clearance in Y | 1.50 mm |
## Changes vs v5.4c
| Feature | v5.4c | v5.5 |
|---|---|---|
| Shell width in X | 168 mm asymmetric | 136 mm symmetric |
| Adapter bay | +X, 32 mm | removed |
| Component order | Mount, Joystick, Sensor, ESP32+Adapter | Mount, Joystick, Sensor, ESP32 |
| USB solution | +X adapter bay, direct plug | USB faces -X, -Y cable notch + lid strain relief |
| ESP32 X position | 28.0 | 35.0 |
| Joystick X position | -15.0 | -19.0 |
| Sensor X position | 18.0 | 42.0 |
| +X+Y screw boss | standard corner | restored (sensor moved to center) |
| Vent slot wall | -Y (fixed) | -Y |
| Pressure sensor | +Y wall side-mount, external barb | +Y wall side-mount, external barb |
| Joystick Y position | upper edge (Y=8.0) | upper edge (Y=-2.0) |
| Pneumatic path | external: mouthpiece → +Y barb | external: mouthpiece → +Y barb |
## External Dimensions
- Base footprint: 136.0 x 50.0 mm
- Closed enclosure height: 39.0 mm
- Joystick protrusion above lid: 4.1 mm
## Print Notes
- Material: PETG preferred, PLA acceptable for quick fit checks
- Base orientation: floor-down, no support intended
- Lid orientation: flip 180 deg, ceiling-down
- USB cable: plug Micro-USB with lid off, route cable to -Y wall notch, close lid
- External hose path: mouthpiece → leftward (+X) outside enclosure → +Y wall barb
- The pressure sensor holder is a U-bracket; install sensor against +Y wall, lid retains from above
- The -X collar remains internal-only; the outer -X wall stays flat for the mic stand
- Suggested slicer baseline: 0.2 mm layer height, 4 walls, 25% gyroid, 240 C nozzle, 75 C bed, 40% fan
