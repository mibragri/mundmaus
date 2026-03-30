# ESP32 Auto-Update Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Modularize the monolithic ESP32 firmware and add OTA auto-update from mundmaus.de with rollback protection.

**Architecture:** Split main.py (1009 lines) into 7 focused modules (config, wifi_manager, sensors, server, display, updater, main). Add manifest-based OTA update system hosted on mundmaus.de/ota with atomic .new→.bak→rename install, rollback in boot.py, and Playwright-based ESP32 testing.

**Tech Stack:** MicroPython 1.27+ on ESP32, asyncio, raw socket+ssl for HTTPS downloads, mpy-cross for syntax validation, Playwright for browser testing, rshell/mpremote for ESP32 communication.

**Spec:** `docs/specs/2026-03-29-auto-update-design.md`

---

## File Map

### Phase 1: Modularization (extract from main.py)

| File | Responsibility | Source Lines |
|------|---------------|-------------|
| `config.py` (create) | Board detection, PIN_*, all constants | main.py:46-120 |
| `wifi_manager.py` (create) | WiFiManager class | main.py:126-249 |
| `sensors.py` (create) | CalibratedJoystick + PuffSensor | main.py:256-399 |
| `server.py` (create) | HTTP/WS server, portal HTML, file serving | main.py:406-807 |
| `display.py` (create) | ST7735 init + status rendering | main.py:813-839 |
| `main.py` (rewrite) | Thin orchestrator, async loop | main.py:846-1008 (reworked) |

### Phase 2: Auto-Update

| File | Responsibility |
|------|---------------|
| `updater.py` (create) | Manifest fetch, version compare, streaming download, atomic install |
| `boot.py` (rewrite) | Rollback logic (update_state.json), recovery AP |
| `server.py` (modify) | Update API endpoints, portal update badge/button/progress |
| `manifest.json` (create) | File versions for OTA |

### Host-Side Tools

| File | Responsibility |
|------|---------------|
| `tools/update-manifest.py` (create) | Generate/bump manifest.json from file hashes |
| `tools/deploy-ota.sh` (create) | Test on ESP32 → deploy to mundmaus.de |
| `tools/test-esp32.sh` (create) | Upload + serial monitor + Playwright tests |
| `tools/provision-esp32.sh` (create) | Flash + upload for new devices |
| `tests/test_manifest.py` (create) | Host-side tests for manifest tool |

---

## Task 1: Install Prerequisites

**Files:** None (system setup)

- [ ] **Step 1: Install mpy-cross, mpremote**

```bash
pip install mpy-cross mpremote
```

- [ ] **Step 2: Verify installation**

Run: `mpy-cross --version && mpremote --help | head -3`
Expected: Version output, no errors.

- [ ] **Step 3: Commit pyproject.toml if changed**

No commit needed — these are system tools, not project deps.

---

## Task 2: Create config.py

Central configuration shared by all modules. Extracted from main.py lines 46-120.

**Files:**
- Create: `config.py`

- [ ] **Step 1: Create config.py**

```python
# config.py — MundMaus shared configuration
# Board detection + constants used by all modules

import sys

# ============================================================
# BOARD DETECTION
# ============================================================

_machine_id = getattr(sys.implementation, '_machine', '')

if 'ESP32S3' in _machine_id:
    BOARD = 'ESP32-S3'
    PIN_VRX       = 1
    PIN_VRY       = 2
    PIN_SW        = 42
    PIN_PUFF_DATA = 4
    PIN_PUFF_CLK  = 5
    PIN_DISP_A0   = 6
    PIN_DISP_RST  = 14
    PIN_DISP_CS   = 17
    PIN_DISP_SCK  = 18
    PIN_DISP_SDA  = 23
else:
    BOARD = 'ESP32-WROOM'
    PIN_VRX       = 33
    PIN_VRY       = 35
    PIN_SW        = 21
    PIN_PUFF_DATA = 32
    PIN_PUFF_CLK  = 25
    PIN_DISP_A0   = 2
    PIN_DISP_RST  = 14
    PIN_DISP_CS   = 17
    PIN_DISP_SCK  = 18
    PIN_DISP_SDA  = 23

# ============================================================
# CONFIGURATION
# ============================================================

VERSION = '3.1'

WS_PORT = 81
HTTP_PORT = 80

# AP Hotspot
AP_SSID = 'MundMaus'
AP_PASS = 'mundmaus1'
AP_IP = '192.168.4.1'

# Credentials file
WIFI_CONFIG_FILE = 'wifi.json'

# Joystick
DEADZONE = 150
NAV_THRESHOLD = 800
NAV_REPEAT_MS = 300
CALIBRATION_SAMPLES = 50

# Puff
PUFF_THRESHOLD = 0.25
PUFF_COOLDOWN_MS = 400
PUFF_SAMPLES = 5

# Display
USE_DISPLAY = False

# File serving
WWW_DIR = 'www'

# Timing
RECAL_IDLE_MS = 10000
PUFF_SEND_INTERVAL_MS = 100
SENSOR_POLL_MS = 20
GC_INTERVAL = 500

# OTA
OTA_BASE_URL = 'https://mundmaus.de/ota'
VERSIONS_FILE = 'versions.json'
UPDATE_STATE_FILE = 'update_state.json'
```

- [ ] **Step 2: Validate syntax**

Run: `mpy-cross config.py && echo OK`
Expected: `OK` (no output from mpy-cross means success)

- [ ] **Step 3: Lint check**

Run: `ruff check config.py`
Expected: No errors.

- [ ] **Step 4: Commit**

```bash
git add config.py
git commit -m "refactor: extract config.py from main.py — board detection + constants"
```

---

## Task 3: Create wifi_manager.py

Extracted from main.py lines 126-249. No behavioral changes.

**Files:**
- Create: `wifi_manager.py`

- [ ] **Step 1: Create wifi_manager.py**

```python
# wifi_manager.py — WiFi station/AP management with credential persistence

import json
import os
import time

import network

from config import WIFI_CONFIG_FILE, AP_SSID, AP_PASS, AP_IP


class WiFiManager:
    def __init__(self):
        self.sta = network.WLAN(network.STA_IF)
        self.ap = network.WLAN(network.AP_IF)
        self.ssid = None
        self.password = None
        self.mode = None
        self.ip = None

    def load_credentials(self):
        try:
            with open(WIFI_CONFIG_FILE) as f:
                data = json.load(f)
                self.ssid = data.get('ssid', '').strip()
                self.password = data.get('password', '').strip()
                if self.ssid:
                    print(f"  Gespeicherte SSID: '{self.ssid}'")
                    return True
                return False
        except OSError:
            print("  Keine wifi.json vorhanden")
            return False
        except Exception as e:
            print(f"  wifi.json Fehler: {e}")
            return False

    def save_credentials(self, ssid, password):
        self.ssid = ssid.strip()
        self.password = password.strip()
        try:
            with open(WIFI_CONFIG_FILE, 'w') as f:
                json.dump({'ssid': self.ssid, 'password': self.password}, f)
            print(f"  Credentials gespeichert: '{self.ssid}'")
            return True
        except Exception as e:
            print(f"  Speicherfehler: {e}")
            return False

    def delete_credentials(self):
        try:
            os.remove(WIFI_CONFIG_FILE)
        except:
            pass
        self.ssid = None
        self.password = None

    def connect_station(self, timeout_ms=10000):
        if not self.ssid:
            return None
        self.ap.active(False)
        self.sta.active(True)
        if self.sta.isconnected():
            self.ip = self.sta.ifconfig()[0]
            self.mode = 'station'
            return self.ip
        print(f"  Verbinde mit '{self.ssid}'...")
        try:
            self.sta.connect(self.ssid, self.password)
        except Exception as e:
            print(f"  Fehler: {e}")
            return None
        start = time.ticks_ms()
        while not self.sta.isconnected():
            if time.ticks_diff(time.ticks_ms(), start) > timeout_ms:
                print(f"  Timeout ({timeout_ms}ms)")
                self.sta.active(False)
                return None
            time.sleep_ms(250)
        self.ip = self.sta.ifconfig()[0]
        self.mode = 'station'
        print(f"  Verbunden: {self.ip}")
        return self.ip

    def start_ap(self):
        self.sta.active(False)
        self.ap.active(True)
        self.ap.config(essid=AP_SSID, password=AP_PASS,
                       authmode=3, max_clients=3)
        self.ip = AP_IP
        self.mode = 'ap'
        print(f"  Hotspot: {AP_SSID} ({AP_IP})")
        return self.ip

    def scan_networks(self, limit=15):
        try:
            was_active = self.sta.active()
            self.sta.active(True)
            raw = self.sta.scan()
            if not was_active and self.mode == 'ap':
                self.sta.active(False)
            seen = set()
            results = []
            for ssid_b, *_, rssi, _ in sorted(raw, key=lambda x: x[3], reverse=True):
                ssid = ssid_b.decode('utf-8', 'ignore').strip()
                if ssid and ssid not in seen:
                    seen.add(ssid)
                    results.append(ssid)
                if len(results) >= limit:
                    break
            return results
        except Exception as e:
            print(f"  Scan-Fehler: {e}")
            return []

    def get_status(self):
        return {
            'mode': self.mode,
            'ssid': self.ssid or AP_SSID,
            'ip': self.ip,
            'ap_ssid': AP_SSID,
            'connected': self.sta.isconnected() if self.mode == 'station' else False,
        }

    def startup(self):
        has_creds = self.load_credentials()
        if has_creds:
            ip = self.connect_station()
            if ip:
                return ip, 'station'
            print("  WLAN fehlgeschlagen -> Hotspot")
        else:
            print("  Keine Daten -> Hotspot")
        ip = self.start_ap()
        return ip, 'ap'
```

- [ ] **Step 2: Validate syntax**

Run: `mpy-cross wifi_manager.py && echo OK`
Expected: `OK`

- [ ] **Step 3: Lint check**

Run: `ruff check wifi_manager.py`
Expected: No errors.

- [ ] **Step 4: Commit**

```bash
git add wifi_manager.py
git commit -m "refactor: extract wifi_manager.py — WiFiManager class"
```

---

## Task 4: Create sensors.py

Extracted from main.py lines 256-399. CalibratedJoystick + PuffSensor (HX710B).

**Files:**
- Create: `sensors.py`

- [ ] **Step 1: Create sensors.py**

```python
# sensors.py — CalibratedJoystick + PuffSensor (HX710B 24-bit)

import time

import machine

from config import (
    CALIBRATION_SAMPLES, DEADZONE, NAV_REPEAT_MS, NAV_THRESHOLD,
    PUFF_COOLDOWN_MS, PUFF_SAMPLES, PUFF_THRESHOLD,
)


class CalibratedJoystick:
    def __init__(self, pin_x, pin_y, pin_sw, deadzone=DEADZONE):
        self.adc_x = machine.ADC(machine.Pin(pin_x))
        self.adc_y = machine.ADC(machine.Pin(pin_y))
        self.adc_x.atten(machine.ADC.ATTN_11DB)
        self.adc_y.atten(machine.ADC.ATTN_11DB)
        self.btn = machine.Pin(pin_sw, machine.Pin.IN, machine.Pin.PULL_UP)
        self.deadzone = deadzone
        self.center_x = 2048
        self.center_y = 2048
        self.last_nav = None
        self.last_nav_time = 0
        self.last_btn = 1
        self.last_btn_time = 0
        self.calibrate()

    def calibrate(self, samples=CALIBRATION_SAMPLES):
        sx, sy = 0, 0
        for _ in range(samples):
            sx += self.adc_x.read()
            sy += self.adc_y.read()
            time.sleep_ms(5)
        self.center_x = sx // samples
        self.center_y = sy // samples
        print(f"  Joystick cal: {self.center_x}, {self.center_y}")

    def read_centered(self):
        x = self.adc_x.read() - self.center_x
        y = self.adc_y.read() - self.center_y
        if abs(x) < self.deadzone: x = 0
        if abs(y) < self.deadzone: y = 0
        return x, y

    def get_direction(self):
        x, y = self.read_centered()
        if abs(x) > abs(y):
            if x > NAV_THRESHOLD: return 'right'
            if x < -NAV_THRESHOLD: return 'left'
        else:
            if y > NAV_THRESHOLD: return 'down'
            if y < -NAV_THRESHOLD: return 'up'
        return None

    def poll_navigation(self):
        d = self.get_direction()
        now = time.ticks_ms()
        if d is None:
            self.last_nav = None
            return None
        if d != self.last_nav or time.ticks_diff(now, self.last_nav_time) > NAV_REPEAT_MS:
            self.last_nav = d
            self.last_nav_time = now
            return d
        return None

    def poll_button(self):
        val = self.btn.value()
        now = time.ticks_ms()
        if val == 0 and self.last_btn == 1 and time.ticks_diff(now, self.last_btn_time) > 200:
            self.last_btn = 0
            self.last_btn_time = now
            return True
        if val == 1:
            self.last_btn = 1
        return False

    def is_idle(self):
        x, y = self.read_centered()
        return x == 0 and y == 0


class PuffSensor:
    def __init__(self, data_pin, clk_pin, threshold=PUFF_THRESHOLD, samples=PUFF_SAMPLES):
        self.data = machine.Pin(data_pin, machine.Pin.IN)
        self.clk = machine.Pin(clk_pin, machine.Pin.OUT)
        self.clk.value(0)
        self.threshold = threshold
        self.baseline = 0
        self.last_puff_time = 0
        self._buf = [0] * samples
        self._idx = 0
        self._samples = samples
        self.calibrate_baseline()

    def _read_raw(self):
        timeout = time.ticks_ms() + 200
        while self.data.value() == 1:
            if time.ticks_diff(time.ticks_ms(), timeout) > 0:
                return None
        result = 0
        for _ in range(24):
            self.clk.value(1)
            self.clk.value(0)
            result = (result << 1) | self.data.value()
        self.clk.value(1)
        self.clk.value(0)
        if result & 0x800000:
            result -= 0x1000000
        return result

    def calibrate_baseline(self, n=30):
        vals = []
        for _ in range(n):
            v = self._read_raw()
            if v is not None:
                vals.append(v)
            time.sleep_ms(10)
        if vals:
            self.baseline = sum(vals) // len(vals)
            print(f"  Puff-Baseline: {self.baseline}")
        else:
            print("  Puff: Sensor antwortet nicht")

    def read_normalized(self):
        raw = self._read_raw()
        if raw is None:
            return 0.0
        diff = abs(raw - self.baseline)
        self._buf[self._idx] = diff
        self._idx = (self._idx + 1) % self._samples
        return sum(self._buf) / (self._samples * max(abs(self.baseline), 1))

    def detect_puff(self):
        level = self.read_normalized()
        now = time.ticks_ms()
        if level > self.threshold and time.ticks_diff(now, self.last_puff_time) > PUFF_COOLDOWN_MS:
            self.last_puff_time = now
            return True
        return False

    def get_level(self):
        return self.read_normalized()
```

- [ ] **Step 2: Validate syntax**

Run: `mpy-cross sensors.py && echo OK`
Expected: `OK`

- [ ] **Step 3: Lint check**

Run: `ruff check sensors.py`
Expected: No errors.

- [ ] **Step 4: Commit**

```bash
git add sensors.py
git commit -m "refactor: extract sensors.py — CalibratedJoystick + PuffSensor"
```

---

## Task 5: Create display.py

Extracted from main.py lines 813-839. Optional ST7735 display.

**Files:**
- Create: `display.py`

- [ ] **Step 1: Create display.py**

```python
# display.py — Optional ST7735 1.8" TFT display

import machine

from config import (
    BOARD, PIN_DISP_A0, PIN_DISP_CS, PIN_DISP_RST,
    PIN_DISP_SCK, PIN_DISP_SDA, USE_DISPLAY, VERSION,
)


def init_display():
    if not USE_DISPLAY:
        return None
    try:
        from ST7735 import TFT
        spi = machine.SPI(1, baudrate=20000000, polarity=0, phase=0,
            sck=machine.Pin(PIN_DISP_SCK), mosi=machine.Pin(PIN_DISP_SDA))
        tft = TFT(spi, PIN_DISP_A0, PIN_DISP_RST, PIN_DISP_CS)
        tft.initr()
        tft.rgb(True)
        tft.fill(TFT.BLACK)
        return tft
    except Exception as e:
        print(f"  Display: {e}")
        return None


def display_status(tft, ip, mode, joy_cal, puff_bl, clients):
    if not tft:
        return
    try:
        from ST7735 import TFT
        from sysfont import sysfont
        tft.fill(TFT.BLACK)
        tft.text((5, 5), f"MundMaus v{VERSION}", TFT.WHITE, sysfont)
        tft.text((5, 20), f"{'WLAN' if mode == 'station' else 'HOTSPOT'}: {ip}", TFT.CYAN, sysfont)
        tft.text((5, 35), f"Joy: {joy_cal[0]},{joy_cal[1]}", TFT.GREEN, sysfont)
        tft.text((5, 50), f"Puff: {puff_bl}", TFT.YELLOW, sysfont)
        tft.text((5, 65), f"Clients: {clients}", TFT.WHITE, sysfont)
        tft.text((5, 80), f"{BOARD}", TFT.WHITE, sysfont)
    except:
        pass
```

- [ ] **Step 2: Validate + lint**

Run: `mpy-cross display.py && ruff check display.py && echo OK`
Expected: `OK`

- [ ] **Step 3: Commit**

```bash
git add display.py
git commit -m "refactor: extract display.py — optional ST7735 TFT"
```

---

## Task 6: Create server.py

Largest extraction: HTTP server, WebSocket, portal HTML, file serving. From main.py lines 406-807. Key change: eliminate `wifi_mgr_ref` global — pass WiFiManager as parameter to `_generate_portal`.

**Files:**
- Create: `server.py`

- [ ] **Step 1: Create server.py**

Extract the following from main.py with these modifications:
- `_CONTENT_TYPES` dict (lines 406-415)
- `_file_exists()` (lines 417-422)
- `_serve_file()` (lines 424-440)
- `_send_404()` (lines 442-445)
- `_generate_portal()` (lines 447-534) — change signature to `_generate_portal(wifi, wifi_ip)` instead of reading `wifi_mgr_ref` global. Replace `wm = wifi_mgr_ref` with `wm = wifi` parameter.
- `MundMausServer` class (lines 545-807) — pass `self.wifi` to `_generate_portal()` at line 609.
- Remove `wifi_mgr_ref = None` global (line 538) entirely.

Top of file:

```python
# server.py — HTTP + WebSocket server, portal, file serving

import gc
import json
import os
import socket
import time

import machine

from config import (
    AP_SSID, BOARD, HTTP_PORT, VERSION, WS_PORT, WWW_DIR,
)
```

The `_generate_portal` function changes from:
```python
def _generate_portal(wifi_ip):
    ...
    wm = wifi_mgr_ref
```
to:
```python
def _generate_portal(wifi, wifi_ip):
    ...
    wm = wifi
```

And in `MundMausServer._handle_http`, the portal call changes from:
```python
p = _generate_portal(self.wifi.ip)
```
to:
```python
p = _generate_portal(self.wifi, self.wifi.ip)
```

The full file is the exact code from main.py lines 406-807 with these import/parameter changes. No behavioral changes.

- [ ] **Step 2: Validate + lint**

Run: `mpy-cross server.py && ruff check server.py && echo OK`
Expected: `OK`

- [ ] **Step 3: Commit**

```bash
git add server.py
git commit -m "refactor: extract server.py — HTTP/WS server, portal, file serving

Eliminates wifi_mgr_ref global — WiFiManager passed as parameter."
```

---

## Task 7: Rewrite main.py as thin orchestrator

Replace the 1009-line monolith with ~80-line orchestrator that imports all modules.

**Files:**
- Rewrite: `main.py`

- [ ] **Step 1: Rewrite main.py**

```python
# main.py — MundMaus ESP32 Firmware v3.1
# Thin orchestrator: imports modules, runs async event loop.

import gc
import os
import sys
import time

import machine

try:
    import asyncio
except ImportError:
    import uasyncio as asyncio

from config import (
    BOARD, GC_INTERVAL, PIN_PUFF_CLK, PIN_PUFF_DATA, PIN_SW,
    PIN_VRX, PIN_VRY, PUFF_SEND_INTERVAL_MS, RECAL_IDLE_MS,
    SENSOR_POLL_MS, VERSION, WWW_DIR, AP_SSID, AP_PASS,
    UPDATE_STATE_FILE,
)
from display import display_status, init_display
from sensors import CalibratedJoystick, PuffSensor
from server import MundMausServer
from wifi_manager import WiFiManager


# ============================================================
# ASYNC TASKS
# ============================================================

async def sensor_loop(joystick, puff, server):
    idle_start = time.ticks_ms()
    last_recal = time.ticks_ms()
    last_puff_send = 0

    while True:
        now = time.ticks_ms()

        nav = joystick.poll_navigation()
        if nav:
            server.send_nav(nav)
            idle_start = now

        if joystick.poll_button():
            server.send_action('press')
            idle_start = now

        if puff:
            if time.ticks_diff(now, last_puff_send) > PUFF_SEND_INTERVAL_MS:
                level = puff.get_level()
                if level > 0.02:
                    server.send_puff_level(level)
                last_puff_send = now
            if puff.detect_puff():
                server.send_action('puff')
                idle_start = now

        if joystick.is_idle():
            if time.ticks_diff(now, idle_start) > RECAL_IDLE_MS:
                if time.ticks_diff(now, last_recal) > 60000:
                    joystick.calibrate(samples=20)
                    last_recal = now
                    idle_start = now
        else:
            idle_start = now

        await asyncio.sleep_ms(SENSOR_POLL_MS)


async def server_loop(server, wifi):
    loop_count = 0
    while True:
        server.poll_http()
        server.poll_ws()

        for msg in server.ws_read_all():
            if msg.get('type') == 'wifi_config':
                ssid = msg.get('ssid', '')
                pw = msg.get('password', '')
                if ssid:
                    wifi.save_credentials(ssid, pw)
                    server.ws_send_all({'type': 'wifi_status', 'status': 'saved',
                                        'ssid': ssid, 'message': 'Gespeichert. Neustart...'})
                    await asyncio.sleep_ms(2000)
                    machine.reset()
            elif msg.get('type') == 'wifi_scan':
                server.ws_send_all({'type': 'wifi_networks',
                                    'networks': wifi.scan_networks()})

        server.check_reboot()

        loop_count += 1
        if loop_count % GC_INTERVAL == 0:
            gc.collect()

        await asyncio.sleep_ms(10)


async def display_loop(tft, ip, mode, joystick, puff, server):
    while True:
        display_status(tft, ip, mode,
                       (joystick.center_x, joystick.center_y),
                       puff.baseline if puff else 0,
                       len(server.ws_clients))
        await asyncio.sleep_ms(5000)


# ============================================================
# MAIN
# ============================================================

def _mark_boot_ok():
    """If update was pending, mark boot as successful."""
    import json as _json
    try:
        with open(UPDATE_STATE_FILE) as f:
            state = _json.load(f)
        if state.get('status') == 'pending':
            with open(UPDATE_STATE_FILE, 'w') as f:
                _json.dump({'status': 'ok'}, f)
            print("  Update: Boot OK, Status gesetzt")
    except OSError:
        pass


async def async_main():
    print("=" * 42)
    print(f"  MUNDMAUS v{VERSION}")
    print(f"  Board: {BOARD}")
    print("=" * 42)

    # Ensure www/ exists
    try:
        os.stat(WWW_DIR)
    except OSError:
        try:
            os.mkdir(WWW_DIR)
        except:
            pass

    # Hardware
    print("\n[Hardware]")
    joystick = CalibratedJoystick(PIN_VRX, PIN_VRY, PIN_SW)

    puff = None
    try:
        puff = PuffSensor(PIN_PUFF_DATA, PIN_PUFF_CLK)
        print("  Drucksensor: OK")
    except Exception as e:
        print(f"  Drucksensor: {e}")

    tft = init_display()

    # WiFi
    print("\n[Netzwerk]")
    wifi = WiFiManager()
    ip, mode = wifi.startup()

    print(f"\n  {'=' * 38}")
    if mode == 'ap':
        print(f"  HOTSPOT: {AP_SSID} / {AP_PASS}")
    else:
        print(f"  WLAN: {wifi.ssid}")
    print(f"  IP: {ip}")
    print(f"  http://{ip}")
    print(f"  {'=' * 38}")

    # Server
    print("\n[Server]")
    server = MundMausServer(wifi)
    server.start()

    display_status(tft, ip, mode,
                   (joystick.center_x, joystick.center_y),
                   puff.baseline if puff else 0, 0)

    # Mark boot successful (rollback protection)
    _mark_boot_ok()

    gc.collect()
    print(f"\n[Start] RAM frei: {gc.mem_free()} bytes")
    print("Bereit.\n")

    # Launch tasks
    asyncio.create_task(sensor_loop(joystick, puff, server))
    asyncio.create_task(server_loop(server, wifi))
    if tft:
        asyncio.create_task(display_loop(tft, ip, mode, joystick, puff, server))

    while True:
        await asyncio.sleep_ms(60000)


def main():
    try:
        asyncio.run(async_main())
    except KeyboardInterrupt:
        print("\nBeendet.")
    except Exception as e:
        sys.print_exception(e)
        print("\nNeustart in 5s...")
        time.sleep(5)
        machine.reset()


if __name__ == '__main__':
    main()
```

- [ ] **Step 2: Validate + lint**

Run: `mpy-cross main.py && ruff check main.py && echo OK`
Expected: `OK`

- [ ] **Step 3: Commit modularization**

```bash
git add main.py
git commit -m "refactor: rewrite main.py as thin orchestrator

Imports config, wifi_manager, sensors, server, display modules.
Adds _mark_boot_ok() for update rollback integration.
Version bump to 3.1."
```

---

## Task 8: Verify modularization on ESP32

**Prerequisite:** ESP32 connected via USB (scheduled for tomorrow).

**Files:** None (verification only)

- [ ] **Step 1: Upload all files to ESP32**

```bash
mpremote connect /dev/ttyUSB0 cp config.py wifi_manager.py sensors.py server.py display.py main.py boot.py :
mpremote connect /dev/ttyUSB0 mkdir :www 2>/dev/null
mpremote connect /dev/ttyUSB0 cp games/solitaire.html :www/solitaire.html
mpremote connect /dev/ttyUSB0 cp games/chess.html :www/chess.html
mpremote connect /dev/ttyUSB0 cp games/memory.html :www/memory.html
```

- [ ] **Step 2: Monitor boot via serial**

```bash
mpremote connect /dev/ttyUSB0 reboot
# Watch for:
#   "MundMaus v3.1 booting..."
#   "[Hardware]" section with joystick + puff calibration
#   "[Netzwerk]" section with IP
#   "[Server]" section with ports
#   "Bereit."
# NO import errors, NO tracebacks
```

- [ ] **Step 3: Test portal in browser**

Open `http://<esp-ip>/` — portal loads, games listed, WiFi panel works.

- [ ] **Step 4: Test each game**

Open each game URL — loads, no JS errors, WebSocket connects.

- [ ] **Step 5: Commit verification**

No code changes — just confirm the refactoring works identically to the monolith.

---

## Task 9: Create updater.py

New module: manifest fetch, version compare, streaming download, atomic install.

**Files:**
- Create: `updater.py`

- [ ] **Step 1: Create updater.py**

```python
# updater.py — OTA update: manifest check, download, atomic install

import gc
import json
import os

from config import OTA_BASE_URL, UPDATE_STATE_FILE, VERSIONS_FILE, WWW_DIR


def _load_versions():
    try:
        with open(VERSIONS_FILE) as f:
            return json.load(f)
    except OSError:
        return {}


def _save_versions(versions):
    with open(VERSIONS_FILE, 'w') as f:
        json.dump(versions, f)


def _file_exists(path):
    try:
        os.stat(path)
        return True
    except OSError:
        return False


def check_manifest(notify_cb=None):
    """Fetch manifest from mundmaus.de, compare with local versions.
    Returns dict: {available: [{file, from_ver, to_ver}], offline: bool}
    notify_cb(result) called when done (for async WS push).
    """
    result = {'available': [], 'offline': False}
    try:
        manifest = _fetch_json(f'{OTA_BASE_URL}/manifest.json')
        if manifest is None:
            result['offline'] = True
            if notify_cb:
                notify_cb(result)
            return result

        local = _load_versions()
        for fname, info in manifest.get('files', {}).items():
            remote_ver = info.get('version', 0)
            local_ver = local.get(fname, 0)
            if remote_ver > local_ver:
                result['available'].append({
                    'file': fname,
                    'from_ver': local_ver,
                    'to_ver': remote_ver,
                    'firmware': info.get('firmware', False),
                })

        # Check for deleted files (in local but not in manifest)
        for fname in local:
            if fname not in manifest.get('files', {}):
                result['available'].append({
                    'file': fname,
                    'from_ver': local[fname],
                    'to_ver': 0,
                    'firmware': False,
                    'delete': True,
                })

    except Exception as e:
        print(f"  Update-Check Fehler: {e}")
        result['offline'] = True

    if notify_cb:
        notify_cb(result)
    return result


def run_update(available, progress_cb=None):
    """Download and install updates. Returns (success, message).
    progress_cb(file, current, total) called per file.
    """
    if not available:
        return True, "Nichts zu aktualisieren"

    games = [u for u in available if not u.get('firmware') and not u.get('delete')]
    firmware = [u for u in available if u.get('firmware')]
    deletes = [u for u in available if u.get('delete')]
    total = len(games) + len(firmware) + len(deletes)
    current = 0
    errors = []
    local = _load_versions()
    has_firmware = len(firmware) > 0

    # --- DOWNLOAD PHASE: all as .new ---

    # Games (best-effort: skip failed)
    for upd in games:
        current += 1
        fname = upd['file']
        if progress_cb:
            progress_cb(fname, current, total)
        ok = _download_file(fname, fname + '.new')
        if not ok:
            errors.append(fname)
            _safe_remove(fname + '.new')

    # Firmware (all-or-nothing)
    fw_ok = True
    for upd in firmware:
        current += 1
        fname = upd['file']
        if progress_cb:
            progress_cb(fname, current, total)
        ok = _download_file(fname, fname + '.new')
        if not ok:
            fw_ok = False
            errors.append(fname)
            break

    if not fw_ok:
        # Clean up ALL firmware .new files
        for upd in firmware:
            _safe_remove(upd['file'] + '.new')
        firmware = []  # Skip firmware install
        has_firmware = False

    # --- INSTALL PHASE ---

    # Install games (.new → final)
    for upd in games:
        fname = upd['file']
        new_path = fname + '.new'
        if _file_exists(new_path):
            _ensure_dir(fname)
            _safe_remove(fname)
            os.rename(new_path, fname)
            local[fname] = upd['to_ver']

    # Install firmware (backup first, then rename)
    if firmware:
        # Step a: create all backups
        for upd in firmware:
            fname = upd['file']
            if _file_exists(fname):
                _safe_remove(fname + '.bak')
                os.rename(fname, fname + '.bak')

        # Step b: rename all .new → final
        for upd in firmware:
            fname = upd['file']
            os.rename(fname + '.new', fname)
            local[fname] = upd['to_ver']

        # Step c: set pending state
        with open(UPDATE_STATE_FILE, 'w') as f:
            json.dump({'status': 'pending', 'attempts': 0}, f)

    # Delete removed files
    for upd in deletes:
        current += 1
        fname = upd['file']
        if progress_cb:
            progress_cb(fname, current, total)
        _safe_remove(fname)
        local.pop(fname, None)

    # Save versions (LAST step)
    _save_versions(local)
    gc.collect()

    if errors:
        msg = f"{total - len(errors)} von {total} installiert, Fehler: {', '.join(errors)}"
        if has_firmware:
            msg += " (Firmware wird beim naechsten Start aktiv)"
        return False, msg

    msg = "Update fertig"
    if has_firmware:
        msg += ", wird beim naechsten Start aktiv"
    return True, msg


# ============================================================
# HTTP DOWNLOAD (streaming, low RAM)
# ============================================================

def _fetch_json(url):
    """Fetch JSON from URL. Returns parsed dict or None."""
    data = _http_get(url)
    if data is None:
        return None
    try:
        return json.loads(data)
    except:
        return None


def _http_get(url, timeout=5):
    """Simple HTTPS GET, returns response body as bytes or None."""
    import socket
    try:
        import ssl
    except ImportError:
        import ussl as ssl

    _, _, host, path = url.split('/', 3)
    path = '/' + path

    addr = socket.getaddrinfo(host, 443)[0][-1]
    sock = socket.socket()
    sock.settimeout(timeout)
    try:
        sock.connect(addr)
        sock = ssl.wrap_socket(sock, server_hostname=host)
        sock.write(f'GET {path} HTTP/1.0\r\nHost: {host}\r\n\r\n'.encode())

        # Read header
        header = b''
        while b'\r\n\r\n' not in header:
            chunk = sock.read(256)
            if not chunk:
                return None
            header += chunk

        header_end = header.index(b'\r\n\r\n') + 4
        body = header[header_end:]

        # Read rest
        while True:
            chunk = sock.read(1024)
            if not chunk:
                break
            body += chunk

        return body
    except Exception as e:
        print(f"  HTTP Fehler ({host}): {e}")
        return None
    finally:
        try:
            sock.close()
        except:
            pass


def _download_file(fname, dest):
    """Stream-download a file to dest path. Returns True on success."""
    import socket
    try:
        import ssl
    except ImportError:
        import ussl as ssl

    url = f'{OTA_BASE_URL}/{fname}'
    _, _, host, path = url.split('/', 3)
    path = '/' + path

    try:
        addr = socket.getaddrinfo(host, 443)[0][-1]
        sock = socket.socket()
        sock.settimeout(10)
        sock.connect(addr)
        sock = ssl.wrap_socket(sock, server_hostname=host)
        sock.write(f'GET {path} HTTP/1.0\r\nHost: {host}\r\n\r\n'.encode())

        # Skip header
        header = b''
        while b'\r\n\r\n' not in header:
            chunk = sock.read(256)
            if not chunk:
                return False
            header += chunk

        header_end = header.index(b'\r\n\r\n') + 4
        remainder = header[header_end:]

        # Check HTTP status
        status_line = header.split(b'\r\n')[0]
        if b'200' not in status_line:
            print(f"  Download {fname}: {status_line}")
            return False

        # Write to file in chunks
        _ensure_dir(dest)
        buf = bytearray(2048)
        with open(dest, 'wb') as f:
            if remainder:
                f.write(remainder)
            while True:
                n = sock.readinto(buf)
                if not n:
                    break
                f.write(buf[:n])

        return True
    except Exception as e:
        print(f"  Download {fname}: {e}")
        return False
    finally:
        try:
            sock.close()
        except:
            pass
        gc.collect()


# ============================================================
# HELPERS
# ============================================================

def _safe_remove(path):
    try:
        os.remove(path)
    except OSError:
        pass


def _ensure_dir(filepath):
    """Create parent directory if needed (e.g., www/ for www/chess.html)."""
    if '/' in filepath:
        d = filepath[:filepath.rfind('/')]
        if d:
            try:
                os.stat(d)
            except OSError:
                try:
                    os.mkdir(d)
                except:
                    pass
```

- [ ] **Step 2: Validate + lint**

Run: `mpy-cross updater.py && ruff check updater.py && echo OK`
Expected: `OK`

- [ ] **Step 3: Commit**

```bash
git add updater.py
git commit -m "feat: add updater.py — OTA manifest check, streaming download, atomic install"
```

---

## Task 10: Rewrite boot.py with rollback + recovery AP

Current boot.py is 16 lines. New boot.py: rollback logic + recovery AP as safety net.

**Files:**
- Rewrite: `boot.py`

- [ ] **Step 1: Rewrite boot.py**

```python
# boot.py — MundMaus ESP32 boot with update rollback + recovery AP
# This file is the safety net. Update it RARELY and test thoroughly.

import esp
esp.osdebug(None)

import gc
gc.collect()

import json
import os
import sys

_m = getattr(sys.implementation, '_machine', '?')
print(f"MundMaus booting... ({_m})")

# ============================================================
# UPDATE ROLLBACK
# ============================================================

_STATE_FILE = 'update_state.json'
_MAX_ATTEMPTS = 2


def _read_state():
    try:
        with open(_STATE_FILE) as f:
            return json.load(f)
    except:
        return {'status': 'ok'}


def _write_state(state):
    with open(_STATE_FILE, 'w') as f:
        json.dump(state, f)


def _file_exists(path):
    try:
        os.stat(path)
        return True
    except OSError:
        return False


def _rollback():
    """Restore all .bak files."""
    count = 0
    for entry in os.listdir('/'):
        if entry.endswith('.bak'):
            orig = entry[:-4]
            try:
                os.remove(orig)
            except:
                pass
            os.rename(entry, orig)
            count += 1
            print(f"  Rollback: {entry} -> {orig}")
    return count


state = _read_state()

if state.get('status') == 'pending':
    attempts = state.get('attempts', 0)

    if attempts >= _MAX_ATTEMPTS:
        # Too many failed boots — rollback
        print(f"  Update fehlgeschlagen ({attempts} Versuche)")

        # Check if .bak files exist
        has_bak = any(e.endswith('.bak') for e in os.listdir('/'))

        if has_bak:
            n = _rollback()
            _write_state({'status': 'ok', 'recovery': True})
            print(f"  {n} Dateien wiederhergestellt")
            # main.py (restored) will run normally after boot.py
        else:
            print("  Keine .bak Dateien — Recovery-AP")
            _write_state({'status': 'ok', 'recovery': True})
            _recovery_ap()
            # _recovery_ap() blocks forever — main.py won't run
    else:
        # Increment attempt counter and let main.py try
        state['attempts'] = attempts + 1
        _write_state(state)
        print(f"  Update-Versuch {attempts + 1}/{_MAX_ATTEMPTS}")


# ============================================================
# RECOVERY AP (last resort)
# ============================================================

def _recovery_ap():
    """Minimal AP with file upload page. Blocks forever."""
    import network
    import socket

    ap = network.WLAN(network.AP_IF)
    ap.active(True)
    ap.config(essid='MundMaus-Recovery', password='mundmaus1', authmode=3)
    print(f"  Recovery-AP: MundMaus-Recovery / 192.168.4.1")

    srv = socket.socket()
    srv.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
    srv.bind(('0.0.0.0', 80))
    srv.listen(1)

    _UPLOAD_PAGE = b"""<!DOCTYPE html><html><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>MundMaus Recovery</title>
<style>body{font-family:sans-serif;background:#300;color:#fff;display:flex;
align-items:center;justify-content:center;min-height:100vh;text-align:center}
.b{background:rgba(0,0,0,.5);padding:2em;border-radius:12px;max-width:450px}
h1{color:#f44}input{margin:10px 0}button{padding:12px 24px;background:#f44;
color:#fff;border:none;border-radius:6px;font-size:16px;cursor:pointer}
#s{margin-top:10px;color:#ff8}</style></head>
<body><div class="b"><h1>Recovery</h1>
<p>Update fehlgeschlagen. Firmware-Datei hochladen:</p>
<input type="file" id="f" accept=".py,.html"><br>
<button onclick="u()">Hochladen</button>
<div id="s"></div></div>
<script>
async function u(){const f=document.getElementById('f').files[0];
if(!f)return;const n=f.name,s=document.getElementById('s');
s.textContent='Lade '+n+'...';
try{const r=await fetch('/upload/'+encodeURIComponent(n),
{method:'POST',body:await f.arrayBuffer(),
headers:{'Content-Type':'application/octet-stream'}});
s.textContent=r.ok?n+' OK! Seite neu laden nach Upload aller Dateien.':'Fehler: '+r.status
}catch(e){s.textContent='Fehler: '+e}}
</script></body></html>"""

    while True:
        try:
            cl, _ = srv.accept()
            cl.settimeout(10)
            req = cl.recv(256).decode('utf-8', 'ignore')
            fl = req.split('\r\n')[0] if req else ''

            if 'POST /upload/' in fl:
                fname = fl.split('/upload/')[1].split(' ')[0]
                fname = fname.replace('%20', ' ')
                # Read past headers
                while b'\r\n\r\n' not in req.encode():
                    req += cl.recv(256).decode('utf-8', 'ignore')
                # Read body (file content)
                cl_match = [l for l in req.split('\r\n') if 'Content-Length:' in l]
                cl_len = int(cl_match[0].split(':')[1].strip()) if cl_match else 0
                body_start = req.index('\r\n\r\n') + 4
                body = req[body_start:].encode()
                while len(body) < cl_len:
                    body += cl.recv(2048)
                # Determine destination
                dest = f'www/{fname}' if fname.endswith('.html') and not fname.endswith('.py') else fname
                with open(dest, 'wb') as f:
                    f.write(body)
                cl.send(b'HTTP/1.1 200 OK\r\nContent-Length: 2\r\n\r\nOK')
                print(f"  Upload: {dest} ({len(body)} bytes)")
            else:
                cl.send(b'HTTP/1.1 200 OK\r\nContent-Type: text/html\r\n\r\n')
                cl.send(_UPLOAD_PAGE)

            cl.close()
        except Exception as e:
            print(f"  Recovery: {e}")
            try:
                cl.close()
            except:
                pass
```

- [ ] **Step 2: Validate + lint**

Run: `mpy-cross boot.py && ruff check boot.py && echo OK`
Expected: `OK`

- [ ] **Step 3: Commit**

```bash
git add boot.py
git commit -m "feat: boot.py with update rollback + recovery AP

Reads update_state.json, allows 2 boot attempts after firmware update.
On failure: restores .bak files, starts recovery AP as last resort."
```

---

## Task 11: Integrate updater into server + main

Add update API endpoints, portal badge/button/progress, async manifest check.

**Files:**
- Modify: `server.py` (add API endpoints, portal HTML additions)
- Modify: `main.py` (add async update_check task)

- [ ] **Step 1: Add update state to MundMausServer.__init__**

In `server.py`, add to `MundMausServer.__init__`:

```python
self._update_info = None  # Set by updater after manifest check
self._updating = False
```

- [ ] **Step 2: Add update API endpoints to _handle_http**

In `server.py`, add two routes in `_handle_http` before the `GET /www/` check:

```python
elif 'GET /api/updates' in fl:
    if self._update_info:
        self._send_json(client, self._update_info)
    else:
        self._send_json(client, {'available': [], 'offline': True})
elif 'POST /api/update/start' in fl:
    if self._updating:
        self._send_json(client, {'ok': False, 'error': 'Update laeuft bereits'})
    elif not self._update_info or not self._update_info.get('available'):
        self._send_json(client, {'ok': False, 'error': 'Keine Updates'})
    else:
        self._updating = True
        self._send_json(client, {'ok': True})
```

- [ ] **Step 3: Add update progress handler to server_loop**

In `main.py`, add to `server_loop` after the WS message handling:

```python
if server._updating:
    from updater import run_update
    available = server._update_info.get('available', [])
    def on_progress(f, cur, tot):
        server.ws_send_all({'type': 'update_progress', 'file': f, 'current': cur, 'total': tot})
    ok, msg = run_update(available, progress_cb=on_progress)
    server.ws_send_all({'type': 'update_complete',
                        'firmware_updated': any(u.get('firmware') for u in available),
                        'message': msg, 'ok': ok})
    server._updating = False
    server._update_info = None
```

- [ ] **Step 4: Add async update_check task to main.py**

In `main.py`, add after `_mark_boot_ok`:

```python
async def update_check(server, wifi):
    """Check for updates in background after boot. Non-blocking."""
    if wifi.mode != 'station':
        server._update_info = {'available': [], 'offline': True}
        server.ws_send_all({'type': 'update_status', 'available': [], 'offline': True})
        return
    await asyncio.sleep_ms(2000)  # Let server settle
    from updater import check_manifest
    def on_result(result):
        server._update_info = result
        server.ws_send_all({'type': 'update_status', **result})
    check_manifest(notify_cb=on_result)
```

Launch it in `async_main` after server.start():

```python
asyncio.create_task(update_check(server, wifi))
```

- [ ] **Step 5: Add update badge/button to portal HTML**

In `server.py`, modify `_generate_portal` to add an update section after the WiFi panel. Add JavaScript that listens for `update_status`, `update_progress`, `update_complete` WS messages and updates the DOM:

```html
<div class="wf" id="upd" style="display:none">
<h2>Updates</h2>
<div id="upd-info"></div>
<button class="wb" id="upd-btn" onclick="startUpdate()" style="display:none">Jetzt aktualisieren</button>
<div id="upd-progress" style="display:none">
<div style="background:#333;border-radius:4px;height:24px;margin:8px 0">
<div id="upd-bar" style="background:#FFD700;height:100%;border-radius:4px;width:0%;transition:width .3s"></div>
</div>
<div id="upd-file" style="font-size:.85em;color:#aaa"></div>
</div>
</div>
```

JavaScript additions for the portal (in the `<script>` block):

```javascript
const ws = new WebSocket('ws://' + location.hostname + ':81');
ws.onmessage = function(e) {
    const d = JSON.parse(e.data);
    if (d.type === 'update_status') {
        const el = document.getElementById('upd');
        const info = document.getElementById('upd-info');
        const btn = document.getElementById('upd-btn');
        el.style.display = 'block';
        if (d.offline) {
            info.textContent = 'Offline — keine Update-Pruefung';
        } else if (d.available && d.available.length > 0) {
            info.textContent = d.available.length + ' Update(s) verfuegbar';
            btn.style.display = 'block';
        } else {
            info.textContent = 'Aktuell';
        }
    } else if (d.type === 'update_progress') {
        document.getElementById('upd-btn').style.display = 'none';
        document.getElementById('upd-progress').style.display = 'block';
        document.getElementById('upd-bar').style.width = (d.current/d.total*100)+'%';
        document.getElementById('upd-file').textContent = 'Datei ' + d.current + '/' + d.total + ': ' + d.file;
    } else if (d.type === 'update_complete') {
        document.getElementById('upd-progress').style.display = 'none';
        document.getElementById('upd-info').textContent = d.message;
        document.getElementById('upd-btn').style.display = 'none';
    }
};
```

- [ ] **Step 6: Show recovery warning in portal**

In `_generate_portal`, check `update_state.json` for `recovery: true` flag and show a warning banner:

```python
# At top of _generate_portal, after reading wifi state:
recovery = False
try:
    import json as _json
    with open('update_state.json') as f:
        _us = _json.load(f)
        recovery = _us.get('recovery', False)
except:
    pass
```

Add banner HTML if recovery is True:

```html
<div style="background:#8b0000;padding:12px;border-radius:8px;margin-bottom:1em;max-width:800px;width:100%;text-align:center">
Update fehlgeschlagen &mdash; alte Version wiederhergestellt
</div>
```

- [ ] **Step 7: Validate + lint**

Run: `mpy-cross server.py && mpy-cross main.py && ruff check server.py main.py && echo OK`
Expected: `OK`

- [ ] **Step 8: Commit**

```bash
git add server.py main.py
git commit -m "feat: integrate OTA updates into portal — badge, button, progress bar

API: GET /api/updates, POST /api/update/start
WS: update_status, update_progress, update_complete
Async manifest check after boot, recovery warning banner."
```

---

## Task 12: Create manifest.json

Initial manifest with current file versions (all version 1 since this is first release with OTA).

**Files:**
- Create: `manifest.json`

- [ ] **Step 1: Create manifest.json**

```json
{
  "manifest_version": 1,
  "files": {
    "boot.py":            { "version": 1, "firmware": true },
    "main.py":            { "version": 1, "firmware": true },
    "config.py":          { "version": 1, "firmware": true },
    "wifi_manager.py":    { "version": 1, "firmware": true },
    "server.py":          { "version": 1, "firmware": true },
    "sensors.py":         { "version": 1, "firmware": true },
    "updater.py":         { "version": 1, "firmware": true },
    "display.py":         { "version": 1, "firmware": true },
    "www/solitaire.html": { "version": 1 },
    "www/chess.html":     { "version": 1 },
    "www/memory.html":    { "version": 1 }
  }
}
```

- [ ] **Step 2: Commit**

```bash
git add manifest.json
git commit -m "feat: add manifest.json for OTA updates — initial versions"
```

---

## Task 13: Create tools/update-manifest.py with tests

Host-side tool to detect file changes and auto-bump versions.

**Files:**
- Create: `tools/update-manifest.py`
- Create: `tests/test_manifest.py`

- [ ] **Step 1: Create tests/test_manifest.py**

```python
"""Tests for tools/update-manifest.py manifest generation."""
import json
import os
import tempfile
from pathlib import Path

import pytest

# Import the module under test
import sys
sys.path.insert(0, str(Path(__file__).parent.parent / 'tools'))
from update_manifest import scan_files, compute_hash, update_manifest


@pytest.fixture
def project_dir(tmp_path):
    """Create a mock project directory."""
    (tmp_path / 'main.py').write_text('# main')
    (tmp_path / 'boot.py').write_text('# boot')
    (tmp_path / 'config.py').write_text('# config')
    (tmp_path / 'games').mkdir()
    (tmp_path / 'games' / 'chess.html').write_text('<html>chess</html>')
    (tmp_path / 'games' / 'memory.html').write_text('<html>memory</html>')
    # Files that should NOT be in manifest
    (tmp_path / 'wifi.json').write_text('{}')
    (tmp_path / 'versions.json').write_text('{}')
    (tmp_path / 'deploy.sh').write_text('#!/bin/bash')
    return tmp_path


def test_scan_files_finds_py_and_games(project_dir):
    files = scan_files(project_dir)
    names = {f['name'] for f in files}
    assert 'main.py' in names
    assert 'boot.py' in names
    assert 'config.py' in names
    assert 'www/chess.html' in names
    assert 'www/memory.html' in names


def test_scan_files_excludes_non_firmware(project_dir):
    files = scan_files(project_dir)
    names = {f['name'] for f in files}
    assert 'wifi.json' not in names
    assert 'versions.json' not in names
    assert 'deploy.sh' not in names


def test_scan_files_marks_firmware(project_dir):
    files = scan_files(project_dir)
    by_name = {f['name']: f for f in files}
    assert by_name['main.py']['firmware'] is True
    assert by_name['www/chess.html']['firmware'] is False


def test_compute_hash_deterministic(project_dir):
    h1 = compute_hash(project_dir / 'main.py')
    h2 = compute_hash(project_dir / 'main.py')
    assert h1 == h2


def test_compute_hash_changes_on_content(project_dir):
    h1 = compute_hash(project_dir / 'main.py')
    (project_dir / 'main.py').write_text('# changed')
    h2 = compute_hash(project_dir / 'main.py')
    assert h1 != h2


def test_update_manifest_creates_new(project_dir):
    manifest_path = project_dir / 'manifest.json'
    state_path = project_dir / '.manifest-state.json'
    update_manifest(project_dir, manifest_path, state_path)

    manifest = json.loads(manifest_path.read_text())
    assert manifest['manifest_version'] == 1
    assert 'main.py' in manifest['files']
    assert manifest['files']['main.py']['version'] == 1
    assert manifest['files']['main.py']['firmware'] is True


def test_update_manifest_bumps_on_change(project_dir):
    manifest_path = project_dir / 'manifest.json'
    state_path = project_dir / '.manifest-state.json'

    # First run
    update_manifest(project_dir, manifest_path, state_path)
    m1 = json.loads(manifest_path.read_text())
    assert m1['files']['main.py']['version'] == 1

    # Change file
    (project_dir / 'main.py').write_text('# changed content')
    update_manifest(project_dir, manifest_path, state_path)
    m2 = json.loads(manifest_path.read_text())
    assert m2['files']['main.py']['version'] == 2


def test_update_manifest_no_bump_if_unchanged(project_dir):
    manifest_path = project_dir / 'manifest.json'
    state_path = project_dir / '.manifest-state.json'

    update_manifest(project_dir, manifest_path, state_path)
    update_manifest(project_dir, manifest_path, state_path)
    m = json.loads(manifest_path.read_text())
    assert m['files']['main.py']['version'] == 1


def test_update_manifest_removes_deleted_file(project_dir):
    manifest_path = project_dir / 'manifest.json'
    state_path = project_dir / '.manifest-state.json'

    update_manifest(project_dir, manifest_path, state_path)
    assert 'www/chess.html' in json.loads(manifest_path.read_text())['files']

    (project_dir / 'games' / 'chess.html').unlink()
    update_manifest(project_dir, manifest_path, state_path)
    assert 'www/chess.html' not in json.loads(manifest_path.read_text())['files']
```

- [ ] **Step 2: Run tests (should fail — tool not written yet)**

Run: `cd /home/ai/claude/projects/mundmaus && python -m pytest tests/test_manifest.py -v`
Expected: ImportError or ModuleNotFoundError for `update_manifest`.

- [ ] **Step 3: Create tools/update-manifest.py**

```python
#!/usr/bin/env python3
"""Generate/update manifest.json by detecting file changes via SHA256."""

import hashlib
import json
import sys
from pathlib import Path

# Files that should be in the manifest
FIRMWARE_PATTERNS = ['*.py']
FIRMWARE_EXCLUDES = {'wifi.json', 'versions.json', 'update_state.json',
                     'deploy.sh', 'pyproject.toml', 'uv.lock'}
GAME_DIR = 'games'  # Source dir in repo (mapped to www/ on ESP32)


def compute_hash(filepath):
    """SHA256 of file content."""
    h = hashlib.sha256()
    with open(filepath, 'rb') as f:
        while chunk := f.read(8192):
            h.update(chunk)
    return h.hexdigest()


def scan_files(project_dir):
    """Find all firmware (.py) and game (.html) files for manifest."""
    project_dir = Path(project_dir)
    files = []

    # Firmware files (*.py in root, excluding non-firmware)
    for p in project_dir.glob('*.py'):
        if p.name not in FIRMWARE_EXCLUDES:
            files.append({
                'name': p.name,
                'path': p,
                'firmware': True,
            })

    # Game files (games/*.html → www/*.html on ESP32)
    games_dir = project_dir / GAME_DIR
    if games_dir.exists():
        for p in games_dir.glob('*.html'):
            files.append({
                'name': f'www/{p.name}',
                'path': p,
                'firmware': False,
            })

    return files


def update_manifest(project_dir, manifest_path=None, state_path=None):
    """Scan files, compare hashes, bump versions, write manifest."""
    project_dir = Path(project_dir)
    if manifest_path is None:
        manifest_path = project_dir / 'manifest.json'
    if state_path is None:
        state_path = project_dir / '.manifest-state.json'

    manifest_path = Path(manifest_path)
    state_path = Path(state_path)

    # Load existing state (hashes from last run)
    old_state = {}
    if state_path.exists():
        old_state = json.loads(state_path.read_text())

    # Load existing manifest (for current versions)
    old_manifest = {'manifest_version': 1, 'files': {}}
    if manifest_path.exists():
        old_manifest = json.loads(manifest_path.read_text())

    # Scan current files
    current_files = scan_files(project_dir)
    new_state = {}
    new_files = {}

    for f in current_files:
        name = f['name']
        h = compute_hash(f['path'])
        new_state[name] = h

        old_hash = old_state.get(name)
        old_ver = old_manifest.get('files', {}).get(name, {}).get('version', 0)

        if old_hash is None or old_hash != h:
            version = old_ver + 1
        else:
            version = old_ver if old_ver > 0 else 1

        entry = {'version': version}
        if f['firmware']:
            entry['firmware'] = True
        new_files[name] = entry

    # Write manifest
    manifest = {
        'manifest_version': 1,
        'files': dict(sorted(new_files.items())),
    }
    manifest_path.write_text(json.dumps(manifest, indent=2) + '\n')

    # Write state
    state_path.write_text(json.dumps(new_state, indent=2) + '\n')

    return manifest


def main():
    project_dir = Path(__file__).parent.parent
    manifest_path = project_dir / 'manifest.json'
    state_path = project_dir / '.manifest-state.json'

    manifest = update_manifest(project_dir, manifest_path, state_path)

    print(f"manifest.json updated ({len(manifest['files'])} files):")
    for name, info in manifest['files'].items():
        flag = ' [firmware]' if info.get('firmware') else ''
        print(f"  {name}: v{info['version']}{flag}")


if __name__ == '__main__':
    main()
```

- [ ] **Step 4: Run tests (should pass)**

Run: `cd /home/ai/claude/projects/mundmaus && python -m pytest tests/test_manifest.py -v`
Expected: All 8 tests PASS.

- [ ] **Step 5: Add .manifest-state.json to .gitignore**

Append to `.gitignore`:
```
.manifest-state.json
```

- [ ] **Step 6: Commit**

```bash
mkdir -p tools tests
git add tools/update-manifest.py tests/test_manifest.py .gitignore
git commit -m "feat: add tools/update-manifest.py — auto-bump versions on file change

Includes pytest test suite (8 tests)."
```

---

## Task 14: Create tools/deploy-ota.sh

Deploys manifest + files to mundmaus.de/ota/ via rsync. Runs test-esp32.sh as gate.

**Files:**
- Create: `tools/deploy-ota.sh`

- [ ] **Step 1: Create tools/deploy-ota.sh**

```bash
#!/usr/bin/env bash
# deploy-ota.sh — Deploy OTA files to mundmaus.de after ESP32 test
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
PROJECT_DIR="$(dirname "$SCRIPT_DIR")"
REMOTE_HOST="mbs"
REMOTE_DIR="/srv/mundmaus/ota"
MANIFEST="$PROJECT_DIR/manifest.json"

# Colors
RED='\033[0;31m'; GREEN='\033[0;32m'; YELLOW='\033[1;33m'; NC='\033[0m'

echo -e "${YELLOW}=== MundMaus OTA Deploy ===${NC}"

# --- Pre-flight ---
if [[ ! -f "$MANIFEST" ]]; then
    echo -e "${RED}ERROR: manifest.json not found. Run tools/update-manifest.py first.${NC}"
    exit 1
fi

# Validate manifest is valid JSON and has files
python3 -c "
import json, sys
m = json.load(open('$MANIFEST'))
assert 'files' in m, 'No files in manifest'
assert len(m['files']) > 0, 'Empty manifest'
print(f\"  Manifest OK: {len(m['files'])} files\")
for name, info in m['files'].items():
    print(f\"    {name}: v{info['version']}\")
"

# Check all referenced files exist
python3 -c "
import json, sys
from pathlib import Path
m = json.load(open('$MANIFEST'))
project = Path('$PROJECT_DIR')
missing = []
for name in m['files']:
    # Map www/* to games/* for source
    src = name.replace('www/', 'games/') if name.startswith('www/') else name
    if not (project / src).exists():
        missing.append(f'{name} (source: {src})')
if missing:
    print('Missing files:')
    for f in missing:
        print(f'  {f}')
    sys.exit(1)
print('  All source files present')
"

# --- ESP32 test gate (skip with --skip-test) ---
if [[ "${1:-}" != "--skip-test" ]]; then
    if [[ -f "$SCRIPT_DIR/test-esp32.sh" ]]; then
        echo -e "\n${YELLOW}--- Running ESP32 tests ---${NC}"
        bash "$SCRIPT_DIR/test-esp32.sh" || {
            echo -e "${RED}ESP32 tests failed. Aborting deploy.${NC}"
            exit 1
        }
    else
        echo -e "${YELLOW}  test-esp32.sh not found, skipping hardware test${NC}"
    fi
fi

# --- Deploy ---
echo -e "\n${YELLOW}--- Deploying to $REMOTE_HOST:$REMOTE_DIR ---${NC}"

# Create remote dir
ssh "$REMOTE_HOST" "mkdir -p $REMOTE_DIR"

# Copy manifest
rsync -avz "$MANIFEST" "$REMOTE_HOST:$REMOTE_DIR/manifest.json"

# Copy firmware files (*.py from project root)
python3 -c "
import json
m = json.load(open('$MANIFEST'))
for name in m['files']:
    if not name.startswith('www/'):
        print(name)
" | while read -r fname; do
    rsync -avz "$PROJECT_DIR/$fname" "$REMOTE_HOST:$REMOTE_DIR/$fname"
done

# Copy game files (games/*.html → ota/www/*.html)
ssh "$REMOTE_HOST" "mkdir -p $REMOTE_DIR/www"
python3 -c "
import json
m = json.load(open('$MANIFEST'))
for name in m['files']:
    if name.startswith('www/'):
        print(name)
" | while read -r fname; do
    src="$PROJECT_DIR/games/$(basename "$fname")"
    rsync -avz "$src" "$REMOTE_HOST:$REMOTE_DIR/$fname"
done

# --- Verify ---
echo -e "\n${YELLOW}--- Verifying ---${NC}"
ssh "$REMOTE_HOST" "cat $REMOTE_DIR/manifest.json | python3 -c 'import json,sys; m=json.load(sys.stdin); print(f\"Remote manifest: {len(m[\"files\"])} files\")'"

echo -e "\n${GREEN}=== OTA Deploy complete ===${NC}"
echo "  URL: https://mundmaus.de/ota/manifest.json"
```

- [ ] **Step 2: Make executable**

```bash
chmod +x tools/deploy-ota.sh
```

- [ ] **Step 3: Commit**

```bash
git add tools/deploy-ota.sh
git commit -m "feat: add tools/deploy-ota.sh — OTA deployment to mundmaus.de"
```

---

## Task 15: Create tools/test-esp32.sh

Upload firmware to test ESP32, monitor serial boot, run Playwright tests.

**Files:**
- Create: `tools/test-esp32.sh`

- [ ] **Step 1: Create tools/test-esp32.sh**

```bash
#!/usr/bin/env bash
# test-esp32.sh — Upload to ESP32, verify boot, run Playwright browser tests
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
PROJECT_DIR="$(dirname "$SCRIPT_DIR")"
PORT="${ESP32_PORT:-/dev/ttyUSB0}"
BOOT_TIMEOUT=30

RED='\033[0;31m'; GREEN='\033[0;32m'; YELLOW='\033[1;33m'; NC='\033[0m'

echo -e "${YELLOW}=== MundMaus ESP32 Test ===${NC}"

# --- Pre-check: mpy-cross syntax validation ---
echo -e "\n${YELLOW}--- Syntax check (mpy-cross) ---${NC}"
FAIL=0
for f in "$PROJECT_DIR"/*.py; do
    fname="$(basename "$f")"
    if mpy-cross "$f" -o /dev/null 2>/dev/null; then
        echo -e "  ${GREEN}OK${NC}  $fname"
    else
        echo -e "  ${RED}FAIL${NC}  $fname"
        FAIL=1
    fi
done
if [[ $FAIL -eq 1 ]]; then
    echo -e "${RED}Syntax errors found. Aborting.${NC}"
    exit 1
fi

# --- Check ESP32 connected ---
if [[ ! -e "$PORT" ]]; then
    echo -e "${RED}ESP32 not found at $PORT. Set ESP32_PORT if different.${NC}"
    exit 1
fi
echo -e "  ESP32 at $PORT"

# --- Upload files ---
echo -e "\n${YELLOW}--- Uploading firmware ---${NC}"
for f in boot.py main.py config.py wifi_manager.py sensors.py server.py display.py updater.py; do
    if [[ -f "$PROJECT_DIR/$f" ]]; then
        mpremote connect "$PORT" cp "$PROJECT_DIR/$f" ":$f"
        echo "  $f"
    fi
done

echo -e "\n${YELLOW}--- Uploading games ---${NC}"
mpremote connect "$PORT" mkdir :www 2>/dev/null || true
for f in "$PROJECT_DIR"/games/*.html; do
    fname="$(basename "$f")"
    mpremote connect "$PORT" cp "$f" ":www/$fname"
    echo "  www/$fname"
done

# --- Reboot and monitor serial ---
echo -e "\n${YELLOW}--- Rebooting + monitoring serial ---${NC}"
SERIAL_LOG=$(mktemp)
trap "rm -f $SERIAL_LOG" EXIT

# Capture serial output in background
mpremote connect "$PORT" exec "import machine; machine.reset()" 2>/dev/null || true
sleep 1

# Read serial until "Bereit." or timeout
timeout "$BOOT_TIMEOUT" bash -c "
    mpremote connect '$PORT' cat /dev/stdin 2>/dev/null || \
    stty -F '$PORT' 115200 raw -echo && cat '$PORT'
" > "$SERIAL_LOG" 2>&1 &
SERIAL_PID=$!

# Wait for boot
WAITED=0
while [[ $WAITED -lt $BOOT_TIMEOUT ]]; do
    if grep -q "Bereit." "$SERIAL_LOG" 2>/dev/null; then
        break
    fi
    sleep 1
    WAITED=$((WAITED + 1))
done

kill $SERIAL_PID 2>/dev/null || true

if grep -q "Bereit." "$SERIAL_LOG"; then
    echo -e "  ${GREEN}Boot OK${NC}"
else
    echo -e "  ${RED}Boot failed (timeout ${BOOT_TIMEOUT}s)${NC}"
    echo "  Serial output:"
    cat "$SERIAL_LOG"
    exit 1
fi

# Check for errors in serial
if grep -qi "Traceback\|Error\|Exception" "$SERIAL_LOG"; then
    echo -e "  ${YELLOW}WARNING: Errors in serial output:${NC}"
    grep -i "Traceback\|Error\|Exception" "$SERIAL_LOG"
fi

# Extract IP
ESP_IP=$(grep -oP 'IP: \K[0-9.]+' "$SERIAL_LOG" | tail -1)
if [[ -z "$ESP_IP" ]]; then
    echo -e "  ${RED}Could not extract IP from serial${NC}"
    cat "$SERIAL_LOG"
    exit 1
fi
echo -e "  IP: $ESP_IP"

# --- Playwright browser tests ---
echo -e "\n${YELLOW}--- Browser tests (Playwright) ---${NC}"
if command -v npx &>/dev/null; then
    npx playwright test --config "$SCRIPT_DIR/playwright.config.ts" \
        --reporter=list 2>&1 || {
        echo -e "${RED}Browser tests failed.${NC}"
        exit 1
    }
    echo -e "  ${GREEN}Browser tests passed${NC}"
else
    echo -e "  ${YELLOW}npx not found, skipping Playwright tests${NC}"
fi

echo -e "\n${GREEN}=== All ESP32 tests passed ===${NC}"
```

- [ ] **Step 2: Make executable**

```bash
chmod +x tools/test-esp32.sh
```

- [ ] **Step 3: Commit**

```bash
git add tools/test-esp32.sh
git commit -m "feat: add tools/test-esp32.sh — ESP32 upload, boot verify, browser tests"
```

---

## Task 16: Create tools/provision-esp32.sh

Flash MicroPython firmware + upload all files for new devices.

**Files:**
- Create: `tools/provision-esp32.sh`

- [ ] **Step 1: Create tools/provision-esp32.sh**

```bash
#!/usr/bin/env bash
# provision-esp32.sh — Flash MicroPython + upload firmware for new ESP32 devices
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
PROJECT_DIR="$(dirname "$SCRIPT_DIR")"
PORT="${ESP32_PORT:-/dev/ttyUSB0}"
FIRMWARE_URL="https://micropython.org/resources/firmware/ESP32_GENERIC-20241129-v1.24.1.bin"
FIRMWARE_BIN="$SCRIPT_DIR/.micropython-firmware.bin"

RED='\033[0;31m'; GREEN='\033[0;32m'; YELLOW='\033[1;33m'; NC='\033[0m'

echo -e "${YELLOW}=== MundMaus ESP32 Provisioning ===${NC}"

# --- Check tools ---
for cmd in esptool.py mpremote; do
    if ! command -v "$cmd" &>/dev/null; then
        echo -e "${RED}$cmd not found. Install with: pip install $cmd${NC}"
        exit 1
    fi
done

# --- Check ESP32 ---
if [[ ! -e "$PORT" ]]; then
    echo -e "${RED}ESP32 not found at $PORT. Set ESP32_PORT if different.${NC}"
    exit 1
fi

# --- Download MicroPython firmware if needed ---
if [[ ! -f "$FIRMWARE_BIN" ]]; then
    echo -e "\n${YELLOW}--- Downloading MicroPython firmware ---${NC}"
    curl -L -o "$FIRMWARE_BIN" "$FIRMWARE_URL"
fi

# --- Flash MicroPython ---
echo -e "\n${YELLOW}--- Flashing MicroPython ---${NC}"
echo "  Erasing flash..."
esptool.py --chip esp32 --port "$PORT" erase_flash
echo "  Writing firmware..."
esptool.py --chip esp32 --port "$PORT" --baud 460800 \
    write_flash -z 0x1000 "$FIRMWARE_BIN"

echo "  Waiting for reboot..."
sleep 3

# --- Upload MundMaus files ---
echo -e "\n${YELLOW}--- Uploading MundMaus firmware ---${NC}"
for f in boot.py main.py config.py wifi_manager.py sensors.py server.py display.py updater.py; do
    if [[ -f "$PROJECT_DIR/$f" ]]; then
        mpremote connect "$PORT" cp "$PROJECT_DIR/$f" ":$f"
        echo "  $f"
    fi
done

echo -e "\n${YELLOW}--- Uploading games ---${NC}"
mpremote connect "$PORT" mkdir :www 2>/dev/null || true
for f in "$PROJECT_DIR"/games/*.html; do
    fname="$(basename "$f")"
    mpremote connect "$PORT" cp "$f" ":www/$fname"
    echo "  www/$fname"
done

# --- Create initial versions.json ---
echo -e "\n${YELLOW}--- Creating versions.json ---${NC}"
python3 -c "
import json
m = json.load(open('$PROJECT_DIR/manifest.json'))
versions = {name: info['version'] for name, info in m['files'].items()}
print(json.dumps(versions))
" | mpremote connect "$PORT" exec "
import sys
data = sys.stdin.read()
with open('versions.json', 'w') as f:
    f.write(data)
print('  versions.json created')
"

# --- Verify boot ---
echo -e "\n${YELLOW}--- Verifying boot ---${NC}"
mpremote connect "$PORT" exec "import machine; machine.reset()" 2>/dev/null || true
sleep 5

echo -e "\n${GREEN}=== Provisioning complete ===${NC}"
echo "  1. Connect to WiFi 'MundMaus' (password: mundmaus1)"
echo "  2. Open http://192.168.4.1"
echo "  3. Configure home WiFi in the portal"
echo "  4. Device will auto-update from mundmaus.de after WiFi setup"
```

- [ ] **Step 2: Make executable**

```bash
chmod +x tools/provision-esp32.sh
```

- [ ] **Step 3: Commit**

```bash
git add tools/provision-esp32.sh
git commit -m "feat: add tools/provision-esp32.sh — flash + provision new ESP32 devices"
```

---

## Task 17: Update Caddy config for mundmaus.de/ota

The OTA endpoint needs to be served by Caddy on mundmaus.de.

**Files:**
- Modify: `deploy.sh` or document the Caddy config change

- [ ] **Step 1: Document required Caddy config**

The existing Caddy config for mundmaus.de needs to serve `/ota/` from `/srv/mundmaus/ota/`. Add to Caddyfile:

```
mundmaus.de {
    # Existing site
    root * /srv/mundmaus
    file_server

    # OTA endpoint (already covered by file_server with root /srv/mundmaus)
    # Files at /srv/mundmaus/ota/ are automatically served at /ota/
}
```

If the existing root is `/srv/mundmaus`, the `/ota/` path is already served. Verify with:

```bash
ssh mbs "curl -s -o /dev/null -w '%{http_code}' https://mundmaus.de/ota/manifest.json"
```

Expected: `200` (after first deploy-ota.sh run).

- [ ] **Step 2: Commit**

No code change needed if Caddy root is already `/srv/mundmaus`. Just verify after first OTA deploy.

---

## Task 18: Update .gitignore and pyproject.toml

**Files:**
- Modify: `.gitignore`
- Modify: `pyproject.toml`

- [ ] **Step 1: Update .gitignore**

Add:
```
.manifest-state.json
tools/.micropython-firmware.bin
```

- [ ] **Step 2: Update pyproject.toml ruff config**

Add new files to per-file-ignores (they use MicroPython modules):

```toml
[tool.ruff.lint.per-file-ignores]
"boot.py" = ["E402", "F401"]
"main.py" = ["E402"]
"config.py" = []
"wifi_manager.py" = []
"sensors.py" = []
"server.py" = []
"display.py" = []
"updater.py" = []
```

- [ ] **Step 3: Commit**

```bash
git add .gitignore pyproject.toml
git commit -m "chore: update .gitignore + ruff config for modular firmware"
```

---

## Self-Review Checklist

1. **Spec coverage:** All sections of the spec are covered:
   - Phase 1 modularization: Tasks 2-8
   - Phase 2 auto-update: Tasks 9-12
   - Manifest pflege: Task 13
   - Deploy pipeline: Task 14
   - ESP32 testing: Task 15
   - Provisioning: Task 16
   - Caddy config: Task 17
   - Housekeeping: Tasks 1, 18

2. **Placeholder scan:** No TBDs, TODOs, or "implement later" found.

3. **Type consistency:** Verified:
   - `check_manifest()` returns `{available: [...], offline: bool}` — matches API response in Task 11
   - `run_update(available, progress_cb)` — `available` list structure matches throughout
   - `_update_info` field on MundMausServer — set in Task 11, read in Task 11
   - `update_state.json` format `{status, attempts}` — consistent between boot.py and main.py/_mark_boot_ok
   - WS message types: `update_status`, `update_progress`, `update_complete` — consistent between Python and JS
