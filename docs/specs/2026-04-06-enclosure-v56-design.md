# MundMaus Enclosure v5.6 — Design Spec

## Summary

Three changes to the v5.5 enclosure:

1. **Pressure sensor relocation** from +Y wall to +X wall (barb + holder + breakout board)
2. **ESP32 hold-down wall fix** in lid (1mm shorter, properly calculated)

~~3. ESP32 retention lip~~ — dropped: would need support printing, ESP32 is already held by guide rails + lid wall. Can add vertical clip later if needed.

## Sensor Hardware Reference

**MPS20N0040D-S + HX710B Breakout Board** (verified from datasheet + product photo):
- Red PCB: ~20mm x 15mm
- MPS20N0040D-S sensor in upper-right area of PCB, pressure nipple pointing UP (perpendicular to PCB surface)
- HX710B ADC in center of PCB
- 4-pin header at bottom edge: VCC, OUT, SCK, GND
- Nipple is NOT centered on the PCB — offset toward upper-right corner
- PCB thickness: ~1.6mm, sensor body ~5mm above PCB, nipple ~3mm above sensor
- Nipple outer diameter: ~3mm (barb hole Ø2.8mm for press-fit)

## Change 1: Pressure Sensor to +X Wall

### Current State (v5.5)
- Sensor mounted on +Y wall shelf at X=42
- Barb hole Ø3.0mm through +Y outer wall
- Holder function defined but NOT called in `make_base()`
- Barb port IS cut (`_cut_pressure_barb_port` is in the build pipeline)

### New Design (v5.6)
- **Mounting:** PCB lies FLAT against +X inner wall, component side (with sensor + nipple) facing the wall. Nipple pokes through the Ø2.8mm barb hole to the outside. Back side (solder pads, wiring) faces into the enclosure.
- **Depth into enclosure: only 5mm** (PCB 1.6mm + sensor body clearance + wiring space)
- **Sensor position on +X wall:**
  - Center Y = 0.0 (symmetric on wall)
  - Center Z = 18.0 (same as v5.5)
  - PCB footprint on wall: 20mm (Z) x 15mm (Y)
  - Z range: 8.0 to 28.0
  - Y range: -7.5 to +7.5
  - Inner edge at X = 66.0 - 5.0 = 61.0
- **ESP32 clearance:** sensor assembly bottom Z=8.0, ESP32 PCB top Z=6.2 -> 1.8mm vertical gap. Sensor inner edge X=61, ESP32 right edge X=62.2 -> 1.2mm overlap in X but at different Z heights, no physical conflict.
- **Barb hole:** Ø2.8mm through +X outer wall (was Ø3.0mm on +Y wall — tighter for press-fit). Chamfer on exterior side (Ø5.0mm entry). Barb hole position = sensor nipple center on the wall, offset from PCB center (needs measurement from actual board, estimated ~5mm from PCB top edge, ~4mm from right edge).
- **Holder:** L-bracket or shelf on +X inner wall. Bottom ledge supports PCB weight, optional side clips. Lid retains from above (same principle as v5.5).
- **Hose routing:** external, from mouthpiece to +X wall barb (was +Y wall).

### Code Changes
- `PRES_POS_X` removed (sensor is against +X wall, position derived from INNER_POS_X)
- `PRES_MOUNT_DEPTH = 5.0` (depth from +X inner wall into enclosure)
- `PRES_POS_Y = 0.0` (centered on wall)
- `PRES_POS_Z = 18.0` (kept from v5.5)
- `PRES_BARB_HOLE_D = 2.8` (was 3.0)
- Rewrite `_add_pressure_sensor_mount()`: flat mount against +X inner wall
- Rewrite `_cut_pressure_barb_port()`: hole through +X wall (YZ workplane at X=+OUTER_POS_X)
- Add `_add_pressure_sensor_mount` to `make_base()` pipeline (currently missing!)
- Remove old +Y barb cut
- Update report text

## Change 2: ESP32 Hold-Down Wall Height Fix

### Current State (v5.5)
```python
esp_pcb_top_z = FLOOR_T + ESP_STANDOFF_H + ESP_H  # = 6.2mm
rib_bot_z = -(EXT_H_BASE - esp_pcb_top_z)          # = -23.8mm (lid coords)
rib_height = LID_INNER_H - rib_bot_z               # = 30.8mm
```
Wall reaches EXACTLY to ESP32 PCB top when lid is fully closed. Zero tolerance.
Result: wall bottoms out on PCB before detent ridges can engage -> lid won't close.
User has filed down the wall by hand to make it work.

### New Design (v5.6)
```python
HOLD_DOWN_CLEARANCE = 1.0  # mm gap between wall bottom and ESP32 PCB top
rib_bot_z = -(EXT_H_BASE - esp_pcb_top_z - HOLD_DOWN_CLEARANCE)  # = -22.8mm
rib_height = LID_INNER_H - rib_bot_z  # = 29.8mm (1mm shorter)
```
Wall ends 1.0mm above ESP32 PCB top when lid is fully closed. Provides:
- Enough clearance for print tolerances, PETG shrinkage, elephant foot
- Space for detent ridges to fully engage before any PCB contact
- PCB can still only lift 1mm max (guide rails prevent lateral movement)

### Code Changes
- Add `HOLD_DOWN_CLEARANCE = 1.0` constant near ESP32 section
- Update `rib_bot_z` calculation in `make_lid()` to subtract clearance

## ~~Change 3: ESP32 Retention Lip~~ — DROPPED

Dropped: horizontal lip needs support printing, not worth the complexity. ESP32 already secured
by guide rails (lateral) + lid hold-down wall (vertical, now with 1mm clearance). If ESP32 lifts
without lid in practice, can add a vertical clip later (no support needed for vertical features).

## Assembly Order

1. ESP32 slides into guide rails
2. Pressure sensor breakout board placed flat against +X wall from inside, nipple through barb hole
3. Joystick seats on pillars (USB cable first if needed)
4. Lid closes — hold-down wall (1mm shorter) provides retention for ESP32, lid retains sensor

## Clearance Summary (v5.6)

| Item | Value |
|---|---:|
| ESP32 right edge to +X inner wall | 3.8 mm |
| Sensor assembly depth from +X wall | 5.0 mm |
| Sensor inner edge X | 61.0 mm |
| ESP32 right edge X | 62.2 mm |
| X overlap (different Z, no conflict) | 1.2 mm |
| Sensor bottom Z to ESP32 PCB top Z | 1.8 mm |
| Hold-down wall gap (lid closed) | 1.0 mm |
| Barb hole diameter | 2.8 mm (press-fit) |

## Files Changed

- `enclosure/mundmaus_v55_enclosure.py` -> rename to `mundmaus_v56_enclosure.py`
  - Constants: PRES_MOUNT_DEPTH, PRES_POS_Y/Z, PRES_BARB_HOLE_D, HOLD_DOWN_CLEARANCE
  - Functions: `_add_pressure_sensor_mount()`, `_cut_pressure_barb_port()`, lid hold-down calc
  - Pipeline: add sensor mount to `make_base()`, remove old +Y barb
  - Report text updates
