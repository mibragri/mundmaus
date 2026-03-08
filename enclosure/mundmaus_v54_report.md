# MundMaus v5.4 Enclosure
## Summary
v5.4 replaces the v5.3 USB-C panel-mount on the +Y wall with an asymmetric +X adapter bay.
The ESP32 remains on the v5.3 left-shifted X=28 layout and gains a protected adapter cradle,
while the 3/8"-16 gooseneck mount moves back to the +Y wall.
## Clearance Analysis
| Item | Value |
|---|---:|
| ESP32 PCB right edge | 53.75 mm |
| ESP32 Micro-USB nose | 56.15 mm |
| Adapter body end (+X) | 81.15 mm |
| Adapter receptacle plane | 79.95 mm |
| +X inner wall | 97.00 mm |
| +X outer wall | 100.00 mm |
| Receptacle to inner wall | 17.05 mm |
| USB-C insertion depth target | 6.80 mm |
| Remaining alignment margin | 10.25 mm |
| Adapter body to outer wall | 18.85 mm |
Assumptions: typical direct adapter body 25x12x6 mm,
receptacle setback 1.2 mm, USB-C plug insertion depth 6.8 mm.
The old SCAD failure mode came from using the pre-v5.3 ESP32 position; keeping X=28 and extending the bay
to 32 mm leaves >10 mm of insertion/alignment reserve after wall thickness is accounted for.
## Changes vs v5.3
| Feature | v5.3 | v5.4 |
|---|---|---|
| USB solution | +Y bulkhead panel mount | +X direct adapter bay |
| Internal cable | short USB-C to Micro-B | none |
| +Y wall | panel hole + nut recess | gooseneck mount collar + hex pocket |
| Shell width in X | 136 mm symmetric | 168 mm asymmetric |
| Adapter retention | cable clips for loose lead | shelf, side rails, capture hood |
## External Dimensions
- Base footprint: 168.0 x 50.0 mm
- Closed enclosure height: 41.0 mm
- Adapter bay extension on +X: 32.0 mm
- Joystick protrusion above lid: 3.1 mm
## Print Notes
- Material: PETG preferred, PLA acceptable for quick fit checks
- Base orientation: floor-down, no support intended
- Lid orientation: flip 180 deg, ceiling-down
- Adapter retainer hood bridges 12.6 mm; this stays inside the PETG 10-15 mm bridge guideline
- Suggested slicer baseline: 0.2 mm layer height, 4 walls, 25% gyroid, 240 C nozzle, 75 C bed, 40% fan
