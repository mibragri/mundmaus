# MundMaus Enclosure v5.1 — Correction Report

## Summary

v5.1 applies four targeted corrections to the v5 landscape enclosure. No layout or structural changes — same external dimensions (136 x 50 x 41 mm).

## Changes vs v5

### 1. ESP32 Board Type (FIXED)

| Parameter | v5 (wrong) | v5.1 (correct) |
|-----------|-----------|----------------|
| Board | ESP32-S3 DevKitC-1 | ESP32-WROOM-32 DevKitC V4 |
| PCB size | 54.4 x 27.9 mm | 51.5 x 28.0 mm |
| USB connector | USB-C (9.5 x 4.0 mm) | Micro-USB (8.0 x 3.0 mm) |

ESP32 cradle (corner posts, guide rails, end stop) updated for new dimensions. Cradle position unchanged (X=35, right side).

### 2. Hex Nut Pocket Tolerance (ADJUSTED)

| Parameter | v5 | v5.1 |
|-----------|-----|------|
| MIC_NUT_TOL | 0.2 mm/side | 0.205 mm/side |
| Pocket SW | 14.69 mm | **14.7 mm** |
| Total tolerance | 0.4 mm | 0.41 mm |

Matches v4.2 target of 14.7mm pocket for 3/8"-16 hex nut (SW 14.29mm).

### 3. Joystick Clearance (FIXED)

| Parameter | v5 | v5.1 |
|-----------|-----|------|
| JOY_PLATFORM_H | 15.0 mm | **22.5 mm** |
| Stick tip Z | 36.6 mm | **44.1 mm** |
| Lid top Z | 41.0 mm | 41.0 mm |
| Stick protrusion | -4.4 mm (BELOW lid!) | **+3.1 mm** (above lid) |

v5 had a critical bug: the stick didn't protrude above the lid at all. Platform raised by 7.5mm to ensure 3.1mm protrusion above lid surface.

### 4. Cable Exits (ADDED)

New feature: cable routing notches at the base-lid seam line.

- **+X wall**: 8 x 4 mm notch at base top edge, aligned with USB connector — allows Micro-USB cable to exit cleanly
- **-X wall**: 8 x 4 mm notch at base top edge, aligned with tube feedthrough — allows pressure sensor tubing to route without kinking
- **Lid lip**: Matching cutouts in the lid lip at both locations, so cables aren't pinched when lid closes

Both the Micro-USB wall cutout (8x3mm, unchanged Z position) and the tube feedthrough (round, -X wall) remain from v5. The notches provide additional routing clearance at the seam.

## Dimensions (unchanged from v5)

- External: 136.0 x 50.0 x 41.0 mm
- Cavity: 130.0 x 44.0 x 35.0 mm
- Wall: 3.0 mm
- Weight estimate: ~45g (PETG, 25% infill)

## Print Settings (PETG, Bambu Lab P1S)

- Base: floor-down, no supports, 25% Gyroid, 4 walls
- Lid: ceiling-down (flipped 180), no supports
- Nozzle: 240C, Bed: 75C, Fan: 40%
- Layer height: 0.2mm recommended

## Output Files

| File | Description |
|------|-------------|
| `mundmaus_v51_enclosure.py` | CadQuery source (parametric) |
| `mundmaus_v51_base.stl` | Base part (1185 kB) |
| `mundmaus_v51_lid.stl` | Lid part (1049 kB) |
| `mundmaus_v51_assembly_iso.png` | Assembly isometric render |
| `mundmaus_v51_base_iso.png` | Base interior isometric |
| `mundmaus_v51_top_view.png` | Top-down view |
| `mundmaus_v51_assembly_iso.svg` | Assembly SVG (vector) |
| `mundmaus_v51_base_interior.svg` | Base interior SVG |
| `mundmaus_v51_side_usb.svg` | Side view (USB wall) |
| `mundmaus_v51_top_view.svg` | Top view SVG |
| `mundmaus_v51_mount_detail.svg` | Mount detail SVG |
