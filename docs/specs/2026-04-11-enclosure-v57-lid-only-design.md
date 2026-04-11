# MundMaus Enclosure v5.7 — Lid-Only Fix

## Summary

Two changes to the v5.6 lid. **Base unchanged — only the lid needs to be reprinted.**

1. **Lip reduction** (LIP_H 4.0 → 3.0 mm): fixes collision between lid inner lip and pressure sensor PCB top
2. **Ridge strengthening** (RIDGE_H 0.5 → 0.6 mm) + alignment shift (RIDGE_Z 2.0 → 1.0 mm): 20% more detent retention, aligned with existing grooves in the base

## Problem Statement (v5.6 observed)

Two issues prevented the lid from latching properly:

1. **Lid won't close fully near the pressure sensor.** The lid's inner lip enters the base cavity from z=26 to z=30 (LIP_H=4). The sensor PCB top sits at z=25.5 (PRES_POS_Z=15.5 center + 10 half-height). The theoretical margin is 0.5mm but in practice the lip collides with the sensor assembly, preventing full lid seating.

2. **Detent ridges don't engage.** Because the lid sits ~0.5-1mm too high (due to #1), the ridges on the lid lip never align with the grooves in the base cavity wall. The lid sits on top of the collision with no retention at all.

Root cause of #2 is #1. Fix #1 and the ridges may engage correctly. But we also slightly strengthen the ridges for extra margin, since reprinting is cheap.

## Design

### Change 1: Lip reduction (LIP_H 4.0 → 3.0 mm)

- **Parameter:** `LIP_H = 3.0` (was 4.0)
- **Effect in base coords:** lip zone moves from z=26-30 to z=27-30. Sensor top at z=25.5 now has 1.5mm clearance (was 0.5mm theoretical, negative in practice).
- **Structural impact:** lid lip is 1mm shorter → slightly weaker engagement with base cavity. Compensated by detent strengthening below.
- **LIP_T (lip wall thickness)** stays at 1.8mm — flex characteristics unchanged.
- **LIP_GAP** stays at 0.15mm.

### Change 2: Ridge strengthening + alignment (RIDGE_H 0.5 → 0.6, RIDGE_Z 2.0 → 1.0)

The detent ridges on the lid lip need to (a) be stronger and (b) still align with the existing grooves in the base (which are at fixed z=28 in assembly coords).

**Alignment math:**
```
Ridge Z in assembly coords = EXT_H_BASE - LIP_H + RIDGE_Z
```

Existing base grooves:
```
groove_z = 30 - 4 + 2 = 28 mm  (v5.6 base, unchanged)
```

New lid ridges must match:
```
ridge_z = 30 - 3 + 1 = 28 mm  ✓ (with LIP_H=3, RIDGE_Z=1)
```

**Parameters:**
- **`RIDGE_H = 0.6`** (was 0.5): 20% taller, 20% more retention force
- **`RIDGE_Z = 1.0`** (was 2.0): ridge position within the lip, measured from lip bottom edge. Required to maintain alignment with existing grooves after LIP_H reduction.
- **`RIDGE_W = 0.8`** unchanged (ridge width along Z axis of lip, fits in 1mm-wide GROOVE_W)
- **`RIDGE_LEN = 10.0`** unchanged (ridge pad length along wall)

**Interference with existing grooves:** new `RIDGE_H=0.6` > existing `GROOVE_D=0.55`. 0.05mm interference at rest. PETG lip flex absorbs this easily; creates small preload on the latch, slightly improving hold.

### What does NOT change

- Base (`make_base()`) — zero code changes, existing prints work
- `GROOVE_D = 0.55`, `GROOVE_W = 1.0` — base grooves unchanged
- Groove positions in base (7 pads at same locations)
- Ridge positions in XY (same 7 ridge pads matching the groove locations)
- `HOLD_DOWN_CLEARANCE` (ESP32 hold-down wall)
- Pressure sensor mount, barb hole, all other base features

## Code Changes

File: copy `enclosure/mundmaus_v56_enclosure.py` → new file `enclosure/mundmaus_v57_enclosure.py` (keep v56 alongside, consistent with how v55 and v56 coexist in the repo).

Three constant changes:

```python
LIP_H, LIP_T, LIP_GAP = 3.0, 1.8, 0.15   # was 4.0
```

```python
RIDGE_H = 0.6        # was 0.5, 20% more retention
RIDGE_Z = 1.0        # was 2.0, realigned with existing grooves after LIP_H reduction
```

Plus:
- Update docstrings/comments in `make_lid()` referencing LIP_H values
- Update report text in the report-generation section (reference LIP_H, RIDGE_H, RIDGE_Z)
- Verify the `_LIP_CLEARANCE_CHECKS` guard still passes with `LIP_ZONE_BOTTOM = 27` (was 26)

**Expected guard re-check:**
- Sensor PCB top: 25.5mm vs new limit 27.0mm → margin 1.5mm ✓
- Mic collar top: 25.5mm vs 27.0mm → margin 1.5mm ✓
- Joystick PCB top: computed vs 27.0mm → likely still fine, verify on build

## Testing

No unit tests — this is pure CAD parameter change. Validation is geometric:

1. Script runs without errors
2. `_LIP_CLEARANCE_CHECKS` guard passes (sensor/mic/joystick all below new z=27 limit)
3. Rendered lid STL shows: 3mm lip, 0.6mm ridges at the correct Z, matching groove positions
4. Physical test: new lid closes on existing base without collision, ridges engage with audible/tactile click, lid cannot be lifted without deliberate prying

## Assembly Order (unchanged)

1. ESP32 in guide rails
2. Sensor PCB flat against +X wall, nipple through barb hole
3. Joystick on pillars
4. Lid closes — ridges snap into grooves

## Risks

- **0.05mm interference** (RIDGE_H=0.6, GROOVE_D=0.55): if PETG batch is unusually stiff or print tolerances stack unfavorably, the lid may be hard to close. Mitigation: if too tight, reduce RIDGE_H to 0.58 or 0.55 (matching groove exactly, zero interference but still 10% stronger than v5.6).
- **Guard check must pass:** the new LIP_ZONE_BOTTOM=27 is still above all internal features. If the build fails the guard (e.g. joystick at 27.0 exactly), we need to adjust position or accept the warning.
- **20% more retention may still not be enough:** if the lid still pops off after this change, next escalation is cantilever snap-fit clips (separate spec, base would need redesign).

## Files Changed

- `enclosure/mundmaus_v56_enclosure.py` → `mundmaus_v57_enclosure.py` (copy, edit 3 constants, update report text)
- No base STL regeneration needed
- New lid STL to be printed and tested on existing base

## Non-Goals

- Cantilever snap-fit clips (deferred — only if this fix is insufficient)
- Base redesign
- Pressure sensor or ESP32 hold-down changes
- Screws/heat-set inserts
