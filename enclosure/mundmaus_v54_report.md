# MundMaus v5.4 Enclosure
## Summary
v5.4 replaces the v5.3 USB-C panel-mount on the +Y wall with an asymmetric +X adapter bay.
The ESP32 remains on the v5.3 left-shifted X=28 layout and gains a protected adapter cradle,
while the 3/8"-16 gooseneck mount moves to the -X short wall opposite the adapter bay.
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
| Mount center on -X wall | Y=0.00 mm, Z=15.50 mm |
| Mount collar edge margin on 50 mm wall | 13.00 mm each side |
| Tube exit wall | -Y |
| Tube-to-collar clearance | 11.59 mm |
| Cable notch-to-collar clearance | 11.23 mm |
| Pressure ledge to collar clearance in X | 3.10 mm |
| Nearest -X screw boss clearance in Y | 0.50 mm |
Assumptions: typical direct adapter body 25x12x6 mm,
receptacle setback 1.2 mm, USB-C plug insertion depth 6.8 mm.
The old SCAD failure mode came from using the pre-v5.3 ESP32 position; keeping X=28 and extending the bay
to 32 mm leaves >10 mm of insertion/alignment reserve after wall thickness is accounted for.
The tube and lid notch move to the -Y wall near X=-48.0 mm so the new -X collar stays clear,
and the pressure sensor ledge shifts to X=-42.0 mm to restore internal service access to the nut pocket.
## Mount Checklist
- [x] Mount-collar centered on -X wall at Y=0.0, Z=15.5
- [x] 24 mm collar on 50 mm wall leaves 13.0 mm edge margin per side
- [x] Tube-feedthrough on -Y wall clears collar by 11.6 mm
- [x] Cable-notch on -Y wall clears collar by 11.2 mm
- [x] Pressure-sensor ledge shifted to X=-42.0 leaves 3.1 mm X-clearance to collar
- [x] Nearest -X screw boss remains outside the collar envelope by 0.5 mm in Y
- [x] Hex-nut pocket opens toward the cavity on the -X wall and remains insertable from the top during assembly
## Changes vs v5.3
| Feature | v5.3 | v5.4 |
|---|---|---|
| USB solution | +Y bulkhead panel mount | +X direct adapter bay |
| Internal cable | short USB-C to Micro-B | none |
| -X wall | plain short wall | gooseneck mount collar + hex pocket |
| -Y wall | vents only | vents + tube exit + tube notch |
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
- Tube exit and lid notch are both on the -Y wall, reducing hose bend radius toward the patient side
- The -X collar remains internal-only; the outer -X wall stays flat for the microphone stand interface
- Suggested slicer baseline: 0.2 mm layer height, 4 walls, 25% gyroid, 240 C nozzle, 75 C bed, 40% fan
