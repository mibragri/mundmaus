# Settings UI — Design Spec

## Goal

Browser-based configuration UI for joystick and puff sensor thresholds. Accessible from the MundMaus portal via a gear icon. Two-tier interface: simple sliders for caregivers, raw values for developer.

## Users

- **Caregiver** (primary): Adjusts sensitivity without technical knowledge. German + English labels.
- **Developer**: Fine-tunes raw config values. Accesses via expandable "Advanced" section.

## Page & Navigation

- New file: `www/settings.html` (single-file HTML+CSS+JS, same as games)
- Portal gets a gear icon button linking to `/www/settings.html`
- Settings page has a home button back to portal
- Same dark theme, `--vw: min(1vw, 19.2px)` cap for ultrawide
- No joystick/puff navigation needed (this is a caregiver-only page)

## Caregiver View (Default)

Three sliders with bilingual labels:

| Slider | Label | Range | Maps to | Mapping |
|--------|-------|-------|---------|---------|
| Joystick sensitivity | Empfindlichkeit / Sensitivity | 1–10 | DEADZONE + NAV_THRESHOLD | 1=DEADZONE:300,THRESH:1200 → 10=DEADZONE:50,THRESH:400 (inverse) |
| Puff strength | Puste-Stärke / Puff strength | 1–10 | PUFF_THRESHOLD | 1=0.5 → 10=0.1 (inverse: higher slider = less force needed) |
| Navigation speed | Geschwindigkeit / Speed | 1–10 | NAV_REPEAT_MS | 1=500ms → 10=100ms (inverse: higher slider = faster repeat) |

Buttons:
- **Kalibrieren / Calibrate** — Re-calibrates joystick center + puff baseline
- **Speichern / Save** — Persists current values to flash
- **Zurücksetzen / Reset** — Restores factory defaults

Visual feedback:
- Sliders change values live (preview mode)
- "Unsaved changes" indicator when preview differs from saved state
- Calibration button shows brief spinner/checkmark on completion

## Expert View (Expandable)

Toggle: "Advanced / Erweitert" below caregiver sliders. Collapsed by default.

Raw numeric input fields:

| Parameter | Range | Default | Unit |
|-----------|-------|---------|------|
| DEADZONE | 50–500 | 150 | - |
| NAV_THRESHOLD | 200–1500 | 800 | - |
| NAV_REPEAT_MS | 50–800 | 300 | ms |
| PUFF_THRESHOLD | 0.05–0.80 | 0.25 | - |
| PUFF_COOLDOWN_MS | 100–1000 | 400 | ms |
| PUFF_SAMPLES | 1–20 | 5 | - |
| SENSOR_POLL_MS | 10–100 | 20 | ms |

Expert changes update the caregiver sliders (snapped to nearest position). Caregiver slider changes update expert fields.

## Data Flow

### Live Preview

```
Browser slider change
  → WS: {"type": "config_preview", "key": "DEADZONE", "value": 100}
  → ESP32 applies to RAM (config module), does NOT write flash
  → Joystick/puff behavior changes immediately
```

### Save

```
Browser "Save" button
  → WS: {"type": "config_save"}
  → ESP32 writes settings.json to flash (only non-default values)
  → WS response: {"type": "config_saved", "ok": true}
```

### Reset

```
Browser "Reset" button
  → WS: {"type": "config_reset"}
  → ESP32 deletes settings.json, restores defaults in RAM
  → WS response: {"type": "config_values", ...all defaults...}
  → Browser updates all sliders/fields
```

### Calibrate

```
Browser "Calibrate" button
  → WS: {"type": "calibrate"}
  → ESP32 runs joystick.calibrate() + puff recalibration
  → WS response: {"type": "calibrate_done", "joy_center": [x,y], "puff_baseline": n}
  → Browser shows confirmation
```

### Page Load

```
Browser loads settings.html
  → GET /api/settings
  → Response: {
      "current": {"DEADZONE": 120, "NAV_THRESHOLD": 600, ...},
      "defaults": {"DEADZONE": 150, "NAV_THRESHOLD": 800, ...},
      "saved": {"DEADZONE": 120}  // only non-default values
    }
  → Browser initializes sliders from "current"
  → "Unsaved" indicator if current != saved+defaults
```

## ESP32 Changes

### config.py

Add `update(key, value)` function to change config values at runtime:

```python
_SETTINGS = {}  # Runtime overrides

def update(key, value):
    globals()[key] = value
    _SETTINGS[key] = value

def get_all():
    """Return dict of all configurable values."""
    return {k: globals()[k] for k in CONFIGURABLE_KEYS}

CONFIGURABLE_KEYS = [
    'DEADZONE', 'NAV_THRESHOLD', 'NAV_REPEAT_MS',
    'PUFF_THRESHOLD', 'PUFF_COOLDOWN_MS', 'PUFF_SAMPLES',
    'SENSOR_POLL_MS',
]

DEFAULTS = {k: globals()[k] for k in CONFIGURABLE_KEYS}
```

### config.py boot loading

At module load time, read `settings.json` and apply overrides:

```python
try:
    import json as _json
    with open('settings.json') as _f:
        for _k, _v in _json.load(_f).items():
            if _k in CONFIGURABLE_KEYS:
                globals()[_k] = _v
except:
    pass
```

### server.py

- New endpoint: `GET /api/settings` — returns current values, defaults, and saved overrides
- New WS message handlers: `config_preview`, `config_save`, `config_reset`, `calibrate`
- `config_save` writes `settings.json` with only non-default values
- `config_preview` calls `config.update(key, value)` — immediate effect

### sensors.py

**Must change.** Currently uses `from config import NAV_THRESHOLD` which copies the value at import time. After `config.update()`, the copy in `sensors.py` remains stale.

Fix: Change `sensors.py` to read config values via module reference instead of copy:

```python
# Before (broken for live preview):
from config import NAV_THRESHOLD
if dx > NAV_THRESHOLD: ...

# After (reads live value):
import config
if dx > config.NAV_THRESHOLD: ...
```

This change applies to: DEADZONE, NAV_THRESHOLD, NAV_REPEAT_MS, PUFF_THRESHOLD, PUFF_COOLDOWN_MS, PUFF_SAMPLES. All must use `config.X` instead of bare `X` in the hot path.

## Persistence

```json
// settings.json — only non-default values
{
  "DEADZONE": 120,
  "NAV_THRESHOLD": 600,
  "PUFF_THRESHOLD": 0.15
}
```

- Missing keys → default from `config.py`
- File missing or corrupt → all defaults
- File deleted by "Reset" button
- Survives OTA updates (not in manifest, not overwritten)

## Out of Scope

- Joystick/puff navigation of the settings page (caregiver uses keyboard/mouse)
- Display/TFT configuration
- WiFi settings (already in portal)
- OTA settings
