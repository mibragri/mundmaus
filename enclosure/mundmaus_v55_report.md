# MundMaus v5.5 Enclosure
## Summary
v5.5 is a compact symmetric redesign. Key changes from v5.4c:
- **Removed adapter bay** — enclosure shrinks from 168 to 136 mm
- **New component order**: Mount(-X) → ESP32 → Joystick → Sensor(+X)
- **USB cable notch** on -Y wall at seam height; lid provides strain relief
- No internal USB cable routing; plug with lid open, close for retention

Component positions along X axis:
- Mic mount collar: -X wall (internal, -57.1 inner edge)
- ESP32 center: X=-28.0 (PCB -53.8 to -2.2)
- Joystick center: X=18.0 (platform -0.5 to 36.5)
- Sensor bracket: X=50.0 (bracket 38.0 to 62.0)
## Clearance Analysis
| Item | Value |
|---|---:|
| ESP32 end stop to collar | 1.55 mm |
| ESP32 right edge to joystick platform | 1.75 mm |
| Joystick platform to sensor bracket | 1.50 mm |
| Sensor bracket to +X inner wall | 3.00 mm |
| Joystick center Y | 8.00 mm |
| Joystick PCB overrun past +Y inner wall | 0.00 mm |
| Remaining +Y wall behind PCB relief | 3.00 mm |
| Front joystick posts to +Y wall | 3.50 mm |
| Sensor barb X offset from joystick | 32.00 mm |
| Sensor holder top to lid rim | 1.50 mm |
| Mount center on -X wall | Y=0.00 mm, Z=15.50 mm |
| Mount collar edge margin on 50 mm wall | 13.00 mm each side |
| USB cable notch X | -2.25 mm |
| USB cable notch wall | -Y |
| Vent slots wall | -Y |
| Pressure barb wall | +Y |
| +X+Y screw boss Y (shifted) | 10.50 mm |
| Nearest -X screw boss clearance in Y | 0.50 mm |
## Changes vs v5.4c
| Feature | v5.4c | v5.5 |
|---|---|---|
| Shell width in X | 168 mm asymmetric | 136 mm symmetric |
| Adapter bay | +X, 32 mm | removed |
| Component order | Mount, Joystick, Sensor, ESP32+Adapter | Mount, ESP32, Joystick, Sensor |
| USB solution | +X adapter bay, direct plug | -Y cable notch + lid strain relief |
| ESP32 X position | 28.0 | -28.0 |
| Joystick X position | -15.0 | 18.0 |
| Sensor X position | 18.0 | 50.0 |
| +X+Y screw boss | standard corner | Y shifted to 10.5 (sensor clearance) |
| Vent slot wall | -Y (fixed) | -Y |
| Pressure sensor | +Y wall side-mount, external barb | +Y wall side-mount, external barb |
| Joystick Y position | upper edge (Y=8.0) | upper edge (Y=8.0) |
| Pneumatic path | external: mouthpiece → +Y barb | external: mouthpiece → +Y barb |
## External Dimensions
- Base footprint: 136.0 x 50.0 mm
- Closed enclosure height: 41.0 mm
- Joystick protrusion above lid: 3.1 mm
## Print Notes
- Material: PETG preferred, PLA acceptable for quick fit checks
- Base orientation: floor-down, no support intended
- Lid orientation: flip 180 deg, ceiling-down
- USB cable: plug Micro-USB with lid off, route cable to -Y wall notch, close lid
- External hose path: mouthpiece → leftward (+X) outside enclosure → +Y wall barb
- The pressure sensor holder is a U-bracket; install sensor against +Y wall, lid retains from above
- The -X collar remains internal-only; the outer -X wall stays flat for the mic stand
- Suggested slicer baseline: 0.2 mm layer height, 4 walls, 25% gyroid, 240 C nozzle, 75 C bed, 40% fan
