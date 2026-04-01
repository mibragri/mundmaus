# Settings UI Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Browser-based config UI for joystick/puff thresholds — caregiver sliders + developer raw values, live preview, persistent save.

**Architecture:** New `settings.html` page served from ESP32 `www/`. Config module gets runtime `update()` + boot-time `settings.json` loading. `sensors.py` switches from copied imports to `config.X` module references so live preview works. Server gets `/api/settings` endpoint + WS handlers for preview/save/reset/calibrate.

**Tech Stack:** MicroPython on ESP32, single-file HTML+CSS+JS, WebSocket for live preview, JSON for persistence.

---

### Task 1: Make config values runtime-updatable

**Files:**
- Modify: `config.py`

- [ ] **Step 1: Add CONFIGURABLE_KEYS, DEFAULTS, update(), get_all() to config.py**

Add this block at the end of `config.py`, after all the constant definitions:

```python
# ============================================================
# RUNTIME CONFIG (live-adjustable via Settings UI)
# ============================================================

CONFIGURABLE_KEYS = [
    'DEADZONE', 'NAV_THRESHOLD', 'NAV_REPEAT_MS',
    'PUFF_THRESHOLD', 'PUFF_COOLDOWN_MS', 'PUFF_SAMPLES',
    'SENSOR_POLL_MS',
]

DEFAULTS = {k: globals()[k] for k in CONFIGURABLE_KEYS}

def update(key, value):
    """Update a config value at runtime (RAM only, not persisted)."""
    if key in CONFIGURABLE_KEYS:
        globals()[key] = value

def get_all():
    """Return dict of all configurable values."""
    return {k: globals()[k] for k in CONFIGURABLE_KEYS}

def get_saved():
    """Return only non-default values from settings.json."""
    import json
    try:
        with open('settings.json') as f:
            return json.load(f)
    except:
        return {}

def save(values):
    """Write non-default values to settings.json."""
    import json
    diff = {}
    for k, v in values.items():
        if k in CONFIGURABLE_KEYS and v != DEFAULTS[k]:
            diff[k] = v
    with open('settings.json', 'w') as f:
        json.dump(diff, f)

def reset():
    """Delete settings.json and restore all defaults in RAM."""
    import os
    for k in CONFIGURABLE_KEYS:
        globals()[k] = DEFAULTS[k]
    try:
        os.remove('settings.json')
    except OSError:
        pass

# Load saved settings at import time
try:
    import json as _json
    with open('settings.json') as _f:
        for _k, _v in _json.load(_f).items():
            if _k in CONFIGURABLE_KEYS:
                globals()[_k] = _v
except:
    pass
```

- [ ] **Step 2: Verify syntax**

Run: `python3 -c "import py_compile; py_compile.compile('config.py', doraise=True); print('OK')"`
Expected: `OK`

- [ ] **Step 3: Commit**

```bash
git add config.py
git commit -m "feat(config): runtime-updatable settings with persistence"
```

---

### Task 2: Switch sensors.py to config module references

**Files:**
- Modify: `sensors.py`

- [ ] **Step 1: Replace copied imports with module reference**

Change the imports at the top of `sensors.py` from:

```python
from config import (
    CALIBRATION_SAMPLES,
    DEADZONE,
    NAV_REPEAT_MS,
    NAV_THRESHOLD,
    PUFF_COOLDOWN_MS,
    PUFF_SAMPLES,
    PUFF_THRESHOLD,
)
```

To:

```python
import config
```

- [ ] **Step 2: Update CalibratedJoystick to use config.X references**

Replace the class. Key changes: `DEADZONE` → `config.DEADZONE`, `NAV_THRESHOLD` → `config.NAV_THRESHOLD`, `NAV_REPEAT_MS` → `config.NAV_REPEAT_MS`, `CALIBRATION_SAMPLES` → `config.CALIBRATION_SAMPLES`. The `deadzone` parameter in `__init__` is removed — always read from config live:

```python
class CalibratedJoystick:
    def __init__(self, pin_x, pin_y, pin_sw):
        self.adc_x = machine.ADC(machine.Pin(pin_x))
        self.adc_y = machine.ADC(machine.Pin(pin_y))
        self.adc_x.atten(machine.ADC.ATTN_11DB)
        self.adc_y.atten(machine.ADC.ATTN_11DB)
        try:
            self.adc_x.width(machine.ADC.WIDTH_12BIT)
            self.adc_y.width(machine.ADC.WIDTH_12BIT)
        except:
            pass

        self.sw = machine.Pin(pin_sw, machine.Pin.IN, machine.Pin.PULL_UP)
        self.center_x = 2048
        self.center_y = 2048
        self.last_dir = None
        self.last_nav_time = 0
        self.sw_last = 1
        self.sw_debounce_time = 0
        self.calibrate()

    def calibrate(self, samples=None):
        if samples is None:
            samples = config.CALIBRATION_SAMPLES
        print("  Joystick Kalibrierung...")
        for _ in range(10):
            self.adc_x.read(); self.adc_y.read()
            time.sleep_ms(5)
        sx, sy = 0, 0
        for _ in range(samples):
            sx += self.adc_x.read(); sy += self.adc_y.read()
            time.sleep_ms(10)
        self.center_x = sx // samples
        self.center_y = sy // samples
        print(f"  Center=({self.center_x},{self.center_y}) dz=\u00b1{config.DEADZONE}")

    def read_centered(self):
        dx = self.adc_x.read() - self.center_x
        dy = self.adc_y.read() - self.center_y
        if abs(dx) < config.DEADZONE: dx = 0
        if abs(dy) < config.DEADZONE: dy = 0
        return dx, dy

    def get_direction(self):
        dx, dy = self.read_centered()
        if abs(dx) > abs(dy):
            if dx < -config.NAV_THRESHOLD: return 'left'
            elif dx > config.NAV_THRESHOLD: return 'right'
        else:
            if dy < -config.NAV_THRESHOLD: return 'up'
            elif dy > config.NAV_THRESHOLD: return 'down'
        return None

    def poll_navigation(self):
        now = time.ticks_ms()
        d = self.get_direction()
        if d is None:
            self.last_dir = None
            return None
        if d != self.last_dir or time.ticks_diff(now, self.last_nav_time) > config.NAV_REPEAT_MS:
            self.last_dir = d
            self.last_nav_time = now
            return d
        return None

    def poll_button(self):
        now = time.ticks_ms()
        val = self.sw.value()
        if val == 0 and self.sw_last == 1:
            if time.ticks_diff(now, self.sw_debounce_time) > 200:
                self.sw_debounce_time = now
                self.sw_last = val
                return True
        self.sw_last = val
        return False

    def is_idle(self):
        dx, dy = self.read_centered()
        return abs(dx) < config.DEADZONE * 2 and abs(dy) < config.DEADZONE * 2
```

- [ ] **Step 3: Update PuffSensor to use config.X references**

Replace the class. Key changes: `PUFF_THRESHOLD` → `config.PUFF_THRESHOLD`, `PUFF_SAMPLES` → `config.PUFF_SAMPLES`, `PUFF_COOLDOWN_MS` → `config.PUFF_COOLDOWN_MS`. Remove `threshold` init param — read live from config:

```python
class PuffSensor:
    def __init__(self, data_pin, clk_pin):
        self.data = machine.Pin(data_pin, machine.Pin.IN)
        self.clk = machine.Pin(clk_pin, machine.Pin.OUT)
        self.clk.value(0)
        self.baseline = 0
        self.max_range = 1
        self.last_puff_time = 0
        self.samples_buf = [0] * config.PUFF_SAMPLES
        self.sample_idx = 0
        time.sleep_ms(100)
        self.calibrate_baseline()

    def _read_raw(self):
        timeout = 0
        while self.data.value() == 1:
            timeout += 1
            if timeout > 100000: return 0
        value = 0
        for i in range(24):
            self.clk.value(1); time.sleep_us(1)
            value = (value << 1) | self.data.value()
            self.clk.value(0); time.sleep_us(1)
        self.clk.value(1); time.sleep_us(1)
        self.clk.value(0); time.sleep_us(1)
        if value & 0x800000: value -= 0x1000000
        return value

    def calibrate_baseline(self, samples=30):
        print("  Drucksensor Kalibrierung...")
        readings = []
        for _ in range(samples):
            r = self._read_raw()
            if r != 0: readings.append(r)
            time.sleep_ms(20)
        if readings:
            self.baseline = sum(readings) // len(readings)
            self.max_range = abs(self.baseline) * 0.5 if self.baseline != 0 else 100000
        print(f"  Baseline={self.baseline} range={self.max_range}")

    def read_normalized(self):
        raw = self._read_raw()
        if raw == 0: return 0.0
        delta = abs(raw - self.baseline)
        n = min(1.0, delta / self.max_range)
        buf = self.samples_buf
        buf[self.sample_idx] = n
        self.sample_idx = (self.sample_idx + 1) % config.PUFF_SAMPLES
        return sum(buf) / config.PUFF_SAMPLES

    def detect_puff(self):
        now = time.ticks_ms()
        if time.ticks_diff(now, self.last_puff_time) < config.PUFF_COOLDOWN_MS: return False
        if self.read_normalized() >= config.PUFF_THRESHOLD:
            self.last_puff_time = now
            return True
        return False

    def get_level(self):
        return self.read_normalized()
```

- [ ] **Step 4: Update main.py — remove deadzone kwarg from CalibratedJoystick init**

In `main.py`, the constructor call `CalibratedJoystick(PIN_VRX, PIN_VRY, PIN_SW)` already matches the new signature (no `deadzone=` param). No change needed.

Verify the `PuffSensor` call: `PuffSensor(PIN_PUFF_DATA, PIN_PUFF_CLK)` — also matches (no `threshold=` param). No change needed.

- [ ] **Step 5: Verify syntax**

Run: `python3 -c "import py_compile; py_compile.compile('sensors.py', doraise=True); print('OK')"`
Expected: `OK`

- [ ] **Step 6: Commit**

```bash
git add sensors.py
git commit -m "refactor(sensors): use config module refs for live-updatable thresholds"
```

---

### Task 3: Add /api/settings endpoint + WS handlers to server.py

**Files:**
- Modify: `server.py`

- [ ] **Step 1: Add import for config module**

At the top of `server.py`, add after the existing imports:

```python
import config
```

- [ ] **Step 2: Add /api/settings HTTP endpoint**

In `_handle_http()` method, add this case before the `GET /api/info` handler:

```python
        elif 'GET /api/settings' in fl:
            self._send_json(client, {
                'current': config.get_all(),
                'defaults': config.DEFAULTS,
                'saved': config.get_saved(),
            })
```

- [ ] **Step 3: Add WS message handlers for config**

In `server_loop()` in `main.py`, the WS message handling block currently handles `wifi_config` and `wifi_scan`. Add new handlers. In `main.py`, after the `wifi_scan` elif block (around line 105):

```python
                elif msg.get('type') == 'config_preview':
                    key = msg.get('key', '')
                    val = msg.get('value')
                    if key and val is not None:
                        config.update(key, val)
                elif msg.get('type') == 'config_save':
                    try:
                        config.save(config.get_all())
                        server.ws_send_all({'type': 'config_saved', 'ok': True})
                    except Exception as e:
                        server.ws_send_all({'type': 'config_saved', 'ok': False, 'error': str(e)})
                elif msg.get('type') == 'config_reset':
                    config.reset()
                    server.ws_send_all({'type': 'config_values',
                                        'current': config.get_all(),
                                        'defaults': config.DEFAULTS,
                                        'saved': {}})
                elif msg.get('type') == 'calibrate':
                    result = {'type': 'calibrate_done'}
                    if joystick:
                        joystick.calibrate()
                        result['joy_center'] = [joystick.center_x, joystick.center_y]
                    if puff:
                        puff.calibrate_baseline()
                        result['puff_baseline'] = puff.baseline
                    server.ws_send_all(result)
```

Note: `joystick` and `puff` need to be accessible in `server_loop`. They're already defined in `async_main()` scope. Change `server_loop` signature to accept them:

In `main.py`, change the function signature:
```python
async def server_loop(server, wifi, joystick, puff):
```

And the launch call:
```python
    asyncio.create_task(server_loop(server, wifi, joystick, puff))
```

- [ ] **Step 4: Add config import to main.py**

At the top of `main.py`, add to imports:

```python
import config
```

- [ ] **Step 5: Verify syntax**

Run:
```bash
python3 -c "import py_compile; py_compile.compile('server.py', doraise=True); print('OK: server.py')"
python3 -c "import py_compile; py_compile.compile('main.py', doraise=True); print('OK: main.py')"
```
Expected: Both `OK`

- [ ] **Step 6: Commit**

```bash
git add server.py main.py
git commit -m "feat(server): /api/settings endpoint + WS config/calibrate handlers"
```

---

### Task 4: Add gear icon to portal

**Files:**
- Modify: `server.py` (portal HTML generation in `_generate_portal()`)

- [ ] **Step 1: Add settings link in portal game grid**

In `_generate_portal()`, after the games button loop (line ~96 `btns += ...`), add a settings gear button. Find the line:

```python
    if not btns:
        btns = '<p style="color:#78909c">Noch keine Spiele. Lade HTML in <code>www/</code></p>'
```

Add before it:

```python
    btns += f'<a href="/{WWW_DIR}/settings.html" class="g" style="border-color:rgba(255,255,255,.2);color:#aaa;font-size:2em">\u2699</a>'
```

This adds a gear icon (⚙) as the last item in the game grid, slightly dimmer than games to signal it's not a game.

- [ ] **Step 2: Verify syntax**

Run: `python3 -c "import py_compile; py_compile.compile('server.py', doraise=True); print('OK')"`
Expected: `OK`

- [ ] **Step 3: Commit**

```bash
git add server.py
git commit -m "feat(portal): add gear icon linking to settings page"
```

---

### Task 5: Create settings.html

**Files:**
- Create: `games/settings.html` (deployed to `www/settings.html` on ESP32)

- [ ] **Step 1: Create the settings page**

Create `games/settings.html` with the full implementation. Single-file HTML+CSS+JS following game standards (dark theme, `--vw` cap, favicon):

```html
<!DOCTYPE html>
<html lang="de">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>MundMaus Einstellungen</title>
<link rel="icon" href="data:image/svg+xml,<svg xmlns='http://www.w3.org/2000/svg' viewBox='0 0 32 32'><rect width='32' height='32' rx='6' fill='%231a1a2e'/><text x='16' y='24' text-anchor='middle' font-size='22' font-weight='bold' fill='%23FFD700'>M</text></svg>">
<style>
  :root {
    --bg: #1a1a2e;
    --text: #e8e8e8;
    --text-dim: #aaa;
    --gold: #FFD700;
    --header-bg: rgba(15, 52, 96, 0.6);
    --vw: min(1vw, 19.2px);
  }
  * { margin: 0; padding: 0; box-sizing: border-box; }
  body {
    background: var(--bg);
    color: var(--text);
    font-family: system-ui, sans-serif;
    max-width: 1920px;
    margin: 0 auto;
    width: 100%;
    min-height: 100vh;
  }
  #header {
    display: flex;
    justify-content: space-between;
    align-items: center;
    padding: 0.8vh calc(2 * var(--vw));
    background: var(--header-bg);
    backdrop-filter: blur(10px);
    height: 6vh;
  }
  #header h1 { font-size: 2.6vh; font-weight: 700; }
  #header h1 span { color: var(--gold); }
  .home-btn {
    font-size: 2.4vh;
    text-decoration: none;
    color: var(--text-dim);
    padding: 0.4vh 1vh;
    border-radius: 6px;
    transition: color 0.2s;
  }
  .home-btn:hover { color: var(--gold); }
  #content {
    max-width: 600px;
    margin: 3vh auto;
    padding: 0 2vh;
  }
  .section {
    background: rgba(255,255,255,0.04);
    border: 1px solid #333;
    border-radius: 12px;
    padding: 1.5em;
    margin-bottom: 1.5em;
  }
  .section h2 {
    font-size: 1.1em;
    color: var(--gold);
    margin-bottom: 1em;
  }
  .slider-group { margin-bottom: 1.5em; }
  .slider-label {
    display: flex;
    justify-content: space-between;
    align-items: baseline;
    margin-bottom: 0.4em;
  }
  .slider-label .name { font-size: 0.95em; }
  .slider-label .val { font-size: 0.85em; color: var(--gold); font-weight: 700; }
  .slider-label .sub { font-size: 0.75em; color: var(--text-dim); }
  input[type=range] {
    -webkit-appearance: none;
    width: 100%;
    height: 6px;
    background: #333;
    border-radius: 3px;
    outline: none;
  }
  input[type=range]::-webkit-slider-thumb {
    -webkit-appearance: none;
    width: 20px;
    height: 20px;
    border-radius: 50%;
    background: var(--gold);
    cursor: pointer;
  }
  .btn-row {
    display: flex;
    gap: 0.8em;
    margin-top: 1.5em;
    flex-wrap: wrap;
  }
  .btn {
    flex: 1;
    min-width: 120px;
    padding: 10px 16px;
    border: none;
    border-radius: 6px;
    font-size: 15px;
    font-weight: 600;
    cursor: pointer;
    transition: all 0.15s;
  }
  .btn-save { background: var(--gold); color: #000; }
  .btn-save:hover { background: #ffe44d; }
  .btn-reset { background: #333; color: #ccc; }
  .btn-reset:hover { background: #444; }
  .btn-cal { background: #1a3a5c; color: var(--gold); border: 1px solid rgba(255,215,0,0.3); }
  .btn-cal:hover { border-color: var(--gold); }
  .btn-save:disabled { opacity: 0.4; cursor: default; }
  #status {
    font-size: 0.85em;
    color: var(--gold);
    min-height: 1.2em;
    margin-top: 0.8em;
  }
  #unsaved {
    display: none;
    font-size: 0.8em;
    color: #f0a030;
    margin-top: 0.5em;
  }
  .toggle {
    background: none;
    border: none;
    color: var(--text-dim);
    font-size: 0.9em;
    cursor: pointer;
    padding: 0.5em 0;
    margin-bottom: 1em;
  }
  .toggle:hover { color: var(--gold); }
  #expert { display: none; }
  #expert.open { display: block; }
  .field-row {
    display: flex;
    justify-content: space-between;
    align-items: center;
    margin-bottom: 0.8em;
  }
  .field-row label { font-size: 0.85em; color: var(--text-dim); }
  .field-row input[type=number] {
    width: 100px;
    padding: 6px 8px;
    background: #1a2a3a;
    border: 1px solid #444;
    border-radius: 6px;
    color: #fff;
    font-size: 14px;
    text-align: right;
  }
  .field-row input[type=number]:focus { border-color: var(--gold); outline: none; }
  .field-row .unit { font-size: 0.75em; color: var(--text-dim); width: 30px; }
  #ws-status {
    position: fixed;
    top: 1vh;
    right: calc(1 * var(--vw));
    width: 10px;
    height: 10px;
    border-radius: 50%;
    background: #666;
    z-index: 200;
  }
  #ws-status.connected { background: #76ff03; box-shadow: 0 0 6px #76ff03; }
</style>
</head>
<body>
<div id="ws-status"></div>
<div id="header">
  <h1>Mund<span>Maus</span> Einstellungen</h1>
  <a href="/" class="home-btn">&#x1F3E0;</a>
</div>
<div id="content">
  <div class="section">
    <h2>&#x1F3AE; Steuerung / Controls</h2>

    <div class="slider-group">
      <div class="slider-label">
        <span class="name">Empfindlichkeit / Sensitivity</span>
        <span class="val" id="joy-val">5</span>
      </div>
      <div class="slider-label"><span class="sub">Joystick</span></div>
      <input type="range" id="joy-sens" min="1" max="10" value="5" oninput="onSlider()">
    </div>

    <div class="slider-group">
      <div class="slider-label">
        <span class="name">Puste-St&auml;rke / Puff strength</span>
        <span class="val" id="puff-val">5</span>
      </div>
      <div class="slider-label"><span class="sub">Drucksensor</span></div>
      <input type="range" id="puff-sens" min="1" max="10" value="5" oninput="onSlider()">
    </div>

    <div class="slider-group">
      <div class="slider-label">
        <span class="name">Geschwindigkeit / Speed</span>
        <span class="val" id="speed-val">5</span>
      </div>
      <div class="slider-label"><span class="sub">Navigation repeat</span></div>
      <input type="range" id="speed" min="1" max="10" value="5" oninput="onSlider()">
    </div>

    <div id="unsaved">&#9888; Nicht gespeichert / Unsaved changes</div>

    <div class="btn-row">
      <button class="btn btn-save" id="btn-save" onclick="doSave()">&#x1F4BE; Speichern / Save</button>
      <button class="btn btn-reset" onclick="doReset()">&#x21BA; Reset</button>
      <button class="btn btn-cal" id="btn-cal" onclick="doCal()">&#x1F3AF; Kalibrieren / Calibrate</button>
    </div>
    <div id="status"></div>
  </div>

  <button class="toggle" onclick="toggleExpert()">&#x2699; Erweitert / Advanced &#x25BC;</button>
  <div id="expert" class="section">
    <h2>&#x1F527; Raw Parameters</h2>
    <div class="field-row"><label>DEADZONE</label><input type="number" id="f-DEADZONE" min="50" max="500" step="10" onchange="onField()"><span class="unit"></span></div>
    <div class="field-row"><label>NAV_THRESHOLD</label><input type="number" id="f-NAV_THRESHOLD" min="200" max="1500" step="50" onchange="onField()"><span class="unit"></span></div>
    <div class="field-row"><label>NAV_REPEAT_MS</label><input type="number" id="f-NAV_REPEAT_MS" min="50" max="800" step="10" onchange="onField()"><span class="unit">ms</span></div>
    <div class="field-row"><label>PUFF_THRESHOLD</label><input type="number" id="f-PUFF_THRESHOLD" min="0.05" max="0.80" step="0.05" onchange="onField()"><span class="unit"></span></div>
    <div class="field-row"><label>PUFF_COOLDOWN_MS</label><input type="number" id="f-PUFF_COOLDOWN_MS" min="100" max="1000" step="50" onchange="onField()"><span class="unit">ms</span></div>
    <div class="field-row"><label>PUFF_SAMPLES</label><input type="number" id="f-PUFF_SAMPLES" min="1" max="20" step="1" onchange="onField()"><span class="unit"></span></div>
    <div class="field-row"><label>SENSOR_POLL_MS</label><input type="number" id="f-SENSOR_POLL_MS" min="10" max="100" step="5" onchange="onField()"><span class="unit">ms</span></div>
  </div>
</div>

<script>
// ── State ──────────────────────────────────────────────────
let current = {};
let saved = {};
let defaults = {};
let ws = null;
let dirty = false;

// ── Slider ↔ Raw mapping ──────────────────────────────────
// Joy sensitivity: slider 1-10 → DEADZONE 300→50, NAV_THRESHOLD 1200→400
function joyFromSlider(v) {
  const t = (v - 1) / 9; // 0..1
  return {
    DEADZONE: Math.round(300 - t * 250),
    NAV_THRESHOLD: Math.round(1200 - t * 800)
  };
}
function joyToSlider(dz, thresh) {
  const t = (300 - dz) / 250;
  return Math.round(t * 9 + 1);
}

// Puff: slider 1-10 → PUFF_THRESHOLD 0.5→0.1
function puffFromSlider(v) {
  const t = (v - 1) / 9;
  return { PUFF_THRESHOLD: Math.round((0.5 - t * 0.4) * 100) / 100 };
}
function puffToSlider(thresh) {
  const t = (0.5 - thresh) / 0.4;
  return Math.round(t * 9 + 1);
}

// Speed: slider 1-10 → NAV_REPEAT_MS 500→100
function speedFromSlider(v) {
  const t = (v - 1) / 9;
  return { NAV_REPEAT_MS: Math.round(500 - t * 400) };
}
function speedToSlider(ms) {
  const t = (500 - ms) / 400;
  return Math.round(t * 9 + 1);
}

// ── UI sync ───────────────────────────────────────────────
function updateUI() {
  // Sliders from current
  const jv = joyToSlider(current.DEADZONE, current.NAV_THRESHOLD);
  const pv = puffToSlider(current.PUFF_THRESHOLD);
  const sv = speedToSlider(current.NAV_REPEAT_MS);
  document.getElementById('joy-sens').value = jv;
  document.getElementById('joy-val').textContent = jv;
  document.getElementById('puff-sens').value = pv;
  document.getElementById('puff-val').textContent = pv;
  document.getElementById('speed').value = sv;
  document.getElementById('speed-val').textContent = sv;
  // Expert fields
  for (const k of ['DEADZONE','NAV_THRESHOLD','NAV_REPEAT_MS','PUFF_THRESHOLD','PUFF_COOLDOWN_MS','PUFF_SAMPLES','SENSOR_POLL_MS']) {
    const el = document.getElementById('f-' + k);
    if (el) el.value = current[k];
  }
  updateDirty();
}

function updateDirty() {
  // Compare current to what would be loaded from saved+defaults
  const effective = Object.assign({}, defaults, saved);
  dirty = false;
  for (const k in current) {
    if (current[k] !== effective[k]) { dirty = true; break; }
  }
  document.getElementById('unsaved').style.display = dirty ? 'block' : 'none';
}

// ── Event handlers ────────────────────────────────────────
function onSlider() {
  const jv = parseInt(document.getElementById('joy-sens').value);
  const pv = parseInt(document.getElementById('puff-sens').value);
  const sv = parseInt(document.getElementById('speed').value);
  document.getElementById('joy-val').textContent = jv;
  document.getElementById('puff-val').textContent = pv;
  document.getElementById('speed-val').textContent = sv;

  const j = joyFromSlider(jv);
  const p = puffFromSlider(pv);
  const s = speedFromSlider(sv);
  Object.assign(current, j, p, s);

  // Update expert fields
  for (const [k, v] of Object.entries(Object.assign({}, j, p, s))) {
    const el = document.getElementById('f-' + k);
    if (el) el.value = v;
    sendPreview(k, v);
  }
  updateDirty();
}

function onField() {
  for (const k of ['DEADZONE','NAV_THRESHOLD','NAV_REPEAT_MS','PUFF_THRESHOLD','PUFF_COOLDOWN_MS','PUFF_SAMPLES','SENSOR_POLL_MS']) {
    const el = document.getElementById('f-' + k);
    if (el) {
      const v = k === 'PUFF_THRESHOLD' ? parseFloat(el.value) : parseInt(el.value);
      if (v !== current[k]) {
        current[k] = v;
        sendPreview(k, v);
      }
    }
  }
  // Sync sliders
  document.getElementById('joy-sens').value = joyToSlider(current.DEADZONE, current.NAV_THRESHOLD);
  document.getElementById('joy-val').textContent = document.getElementById('joy-sens').value;
  document.getElementById('puff-sens').value = puffToSlider(current.PUFF_THRESHOLD);
  document.getElementById('puff-val').textContent = document.getElementById('puff-sens').value;
  document.getElementById('speed').value = speedToSlider(current.NAV_REPEAT_MS);
  document.getElementById('speed-val').textContent = document.getElementById('speed').value;
  updateDirty();
}

function toggleExpert() {
  const el = document.getElementById('expert');
  el.classList.toggle('open');
}

// ── WebSocket ─────────────────────────────────────────────
function sendPreview(key, value) {
  if (ws && ws.readyState === 1) {
    ws.send(JSON.stringify({type: 'config_preview', key: key, value: value}));
  }
}

function doSave() {
  if (ws && ws.readyState === 1) {
    ws.send(JSON.stringify({type: 'config_save'}));
    document.getElementById('status').textContent = 'Speichern...';
  }
}

function doReset() {
  if (ws && ws.readyState === 1) {
    ws.send(JSON.stringify({type: 'config_reset'}));
    document.getElementById('status').textContent = 'Reset...';
  }
}

function doCal() {
  if (ws && ws.readyState === 1) {
    ws.send(JSON.stringify({type: 'calibrate'}));
    document.getElementById('btn-cal').textContent = '...';
    document.getElementById('status').textContent = 'Kalibriere...';
  }
}

let wsBackoff = 3000;
function connectWS() {
  const host = location.hostname || '192.168.4.1';
  ws = new WebSocket('ws://' + host + ':81');
  ws.onopen = function() {
    document.getElementById('ws-status').className = 'connected';
    wsBackoff = 3000;
  };
  ws.onmessage = function(ev) {
    try {
      const m = JSON.parse(ev.data);
      if (m.type === 'config_saved') {
        if (m.ok) {
          saved = Object.assign({}, current);
          // Recompute saved as diff from defaults
          const diff = {};
          for (const k in saved) { if (saved[k] !== defaults[k]) diff[k] = saved[k]; }
          saved = diff;
          document.getElementById('status').textContent = '\u2713 Gespeichert / Saved';
          updateDirty();
        } else {
          document.getElementById('status').textContent = '\u2717 Fehler: ' + (m.error || '?');
        }
      } else if (m.type === 'config_values') {
        current = m.current;
        saved = m.saved || {};
        if (m.defaults) defaults = m.defaults;
        updateUI();
        document.getElementById('status').textContent = '\u2713 Defaults wiederhergestellt / Reset done';
      } else if (m.type === 'calibrate_done') {
        let msg = '\u2713 Kalibriert';
        if (m.joy_center) msg += ' | Joy: ' + m.joy_center[0] + ',' + m.joy_center[1];
        if (m.puff_baseline) msg += ' | Puff: ' + m.puff_baseline;
        document.getElementById('status').textContent = msg;
        document.getElementById('btn-cal').textContent = '\uD83C\uDFAF Kalibrieren / Calibrate';
      }
    } catch(e) {}
  };
  ws.onclose = function() {
    document.getElementById('ws-status').className = '';
    setTimeout(connectWS, wsBackoff);
    wsBackoff = Math.min(wsBackoff * 2, 30000);
  };
  ws.onerror = function() { ws.close(); };
}

// ── Init ──────────────────────────────────────────────────
fetch('/api/settings')
  .then(r => r.json())
  .then(d => {
    current = d.current;
    defaults = d.defaults;
    saved = d.saved || {};
    updateUI();
  })
  .catch(e => {
    document.getElementById('status').textContent = 'Fehler: ' + e;
  });
connectWS();
</script>
</body>
</html>
```

- [ ] **Step 2: Verify HTML is well-formed**

Open in a browser locally or check that there are no unclosed tags by visual inspection. The file is self-contained HTML+CSS+JS.

- [ ] **Step 3: Commit**

```bash
git add games/settings.html
git commit -m "feat: settings page — caregiver sliders + expert raw values"
```

---

### Task 6: Upload to ESP32 and test

**Files:**
- Upload: `config.py`, `sensors.py`, `main.py`, `server.py`, `games/settings.html`

- [ ] **Step 1: Upload all changed firmware files**

```bash
fuser -k /dev/ttyUSB0 2>/dev/null
sleep 1
mpremote connect /dev/ttyUSB0 reset
sleep 3
for f in config.py sensors.py main.py server.py; do
  mpremote connect /dev/ttyUSB0 cp $f :/$f && echo "OK: $f"
done
mpremote connect /dev/ttyUSB0 cp games/settings.html :/www/settings.html && echo "OK: settings.html"
```

- [ ] **Step 2: Reboot and verify boot**

```bash
mpremote connect /dev/ttyUSB0 exec "import machine; machine.reset()"
```

Wait 20s, then: `curl -s http://192.168.178.86/api/settings | python3 -m json.tool`

Expected: JSON with `current`, `defaults`, `saved` keys.

- [ ] **Step 3: Test in browser**

Open `http://192.168.178.86/www/settings.html`:
1. Sliders should show current values
2. Moving a slider should change behavior immediately (live preview)
3. "Save" should persist — verify by rebooting and checking values are retained
4. "Reset" should restore defaults
5. "Calibrate" should recalibrate sensors
6. Expert section should expand/collapse
7. Expert fields and sliders should stay in sync

- [ ] **Step 4: Test portal gear icon**

Open `http://192.168.178.86/` — gear icon should appear in the game grid, linking to settings page.

- [ ] **Step 5: Commit any fixes if needed, then final commit**

```bash
git add -A
git commit -m "feat: settings UI — live config for joystick/puff thresholds"
git push
```
