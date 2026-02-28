# ============================================================
# MUNDMAUS - MicroPython ESP32/ESP32-S3 Firmware
# main.py - Solitaire Edition v3.0
# ============================================================
# Hardware:
#   ESP32-S3-DevKitC-1 N16R8 (empfohlen) oder ESP32 DevKitC V4
#   KY-023 Joystick
#   MPS20N0040D-S + HX710B 24-bit Drucksensor
#     -> ebay.de/itm/284856729901 (~4,29 EUR)
#     -> Silikonschlauch + Mundstück an Sensorport
#   ST7735 1.8" TFT Display (optional)
#
# Neu in v3.0:
#   - Automatische Board-Erkennung (ESP32 vs ESP32-S3)
#   - asyncio-basierte Hauptschleife
#   - File-Server: serviert HTML-Spiele aus www/ Ordner
#   - Spiele-Portal (index.html) als Launcher
#   - Verbesserte Fehlerbehandlung
#
# Netzwerk-Logik:
#   1. Gespeicherte WLAN-Credentials laden (wifi.json)
#   2. Verbindungsversuch (10s Timeout)
#   3. Bei Fehler/keine Credentials -> AP-Hotspot starten
#      SSID: "MundMaus", Passwort: "mundmaus1"
#      IP: 192.168.4.1
#   4. Browser öffnet http://192.168.4.1 -> Spiele-Portal
#   5. Neue Credentials per WebSocket oder HTTP API
#   6. Beim nächsten Boot: erneuter Versuch
# ============================================================

import machine
import time
import json
import gc
import os
import sys
import network
import socket

try:
    import asyncio
except ImportError:
    import uasyncio as asyncio

# ============================================================
# BOARD DETECTION
# ============================================================

_machine_id = getattr(sys.implementation, '_machine', '')

if 'ESP32S3' in _machine_id:
    BOARD = 'ESP32-S3'
    # ESP32-S3: GPIO33-39 existieren NICHT
    # ADC1-Kanäle: GPIO1-10
    PIN_VRX       = 1     # ADC1_CH0
    PIN_VRY       = 2     # ADC1_CH1
    PIN_SW        = 42    # Digital
    PIN_PUFF_DATA = 4     # Digital (HX710B Data)
    PIN_PUFF_CLK  = 5     # Digital (HX710B Clock)
    PIN_DISP_A0   = 6     # Display Data/Command
    PIN_DISP_RST  = 14    # Display Reset
    PIN_DISP_CS   = 17    # Display CS
    PIN_DISP_SCK  = 18    # Display SCK (SPI)
    PIN_DISP_SDA  = 23    # Display MOSI (SPI)
else:
    BOARD = 'ESP32-WROOM'
    # Klassischer ESP32 DevKitC V4 (AZ-Delivery)
    # ADC1-Kanäle: GPIO32-39 (ADC2 blockiert bei WiFi!)
    PIN_VRX       = 33    # ADC1_CH5
    PIN_VRY       = 35    # ADC1_CH7
    PIN_SW        = 21    # Digital
    PIN_PUFF_DATA = 32    # ADC1_CH4 (Digital für HX710B)
    PIN_PUFF_CLK  = 25    # Digital
    PIN_DISP_A0   = 2     # Display Data/Command
    PIN_DISP_RST  = 14    # Display Reset
    PIN_DISP_CS   = 17    # Display CS
    PIN_DISP_SCK  = 18    # Display SCK (SPI)
    PIN_DISP_SDA  = 23    # Display MOSI (SPI)

# ============================================================
# CONFIGURATION
# ============================================================

VERSION = '3.0'

WS_PORT = 81
HTTP_PORT = 80

# AP Hotspot settings
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


# ============================================================
# WIFI MANAGER - Credentials persist across reboots
# ============================================================

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
            with open(WIFI_CONFIG_FILE, 'r') as f:
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
                       authmode=network.AUTH_WPA_WPA2_PSK)
        while not self.ap.active():
            time.sleep_ms(100)
        self.ip = self.ap.ifconfig()[0]
        self.mode = 'ap'
        return self.ip
    
    def scan_networks(self):
        try:
            was_active = self.sta.active()
            self.sta.active(True)
            time.sleep_ms(100)
            results = self.sta.scan()
            if not was_active and self.mode == 'ap':
                self.sta.active(False)
            seen = set()
            ssids = []
            for r in sorted(results, key=lambda x: x[3], reverse=True):
                name = r[0].decode('utf-8', 'ignore').strip()
                if name and name not in seen:
                    seen.add(name)
                    ssids.append(name)
            return ssids[:15]
        except Exception as e:
            print(f"  Scan Fehler: {e}")
            return []
    
    def get_status(self):
        return {
            'mode': self.mode or 'disconnected',
            'ssid': self.ssid or '',
            'ip': self.ip or '',
            'ap_ssid': AP_SSID,
            'connected': self.sta.isconnected() if self.mode == 'station' else False
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


# ============================================================
# JOYSTICK with AUTO-CALIBRATION
# ============================================================

class CalibratedJoystick:
    def __init__(self, pin_x, pin_y, pin_sw, deadzone=DEADZONE):
        self.adc_x = machine.ADC(machine.Pin(pin_x))
        self.adc_y = machine.ADC(machine.Pin(pin_y))
        self.adc_x.atten(machine.ADC.ATTN_11DB)
        self.adc_y.atten(machine.ADC.ATTN_11DB)
        try:
            self.adc_x.width(machine.ADC.WIDTH_12BIT)
            self.adc_y.width(machine.ADC.WIDTH_12BIT)
        except:
            pass  # Neuere MicroPython brauchen das evtl. nicht
        
        self.sw = machine.Pin(pin_sw, machine.Pin.IN, machine.Pin.PULL_UP)
        self.deadzone = deadzone
        self.center_x = 2048
        self.center_y = 2048
        self.last_dir = None
        self.last_nav_time = 0
        self.sw_last = 1
        self.sw_debounce_time = 0
        self.calibrate()
    
    def calibrate(self, samples=CALIBRATION_SAMPLES):
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
        print(f"  Center=({self.center_x},{self.center_y}) dz=±{self.deadzone}")
    
    def read_centered(self):
        dx = self.adc_x.read() - self.center_x
        dy = self.adc_y.read() - self.center_y
        if abs(dx) < self.deadzone: dx = 0
        if abs(dy) < self.deadzone: dy = 0
        return dx, dy
    
    def get_direction(self):
        dx, dy = self.read_centered()
        if abs(dx) > abs(dy):
            if dx < -NAV_THRESHOLD: return 'left'
            elif dx > NAV_THRESHOLD: return 'right'
        else:
            if dy < -NAV_THRESHOLD: return 'up'
            elif dy > NAV_THRESHOLD: return 'down'
        return None
    
    def poll_navigation(self):
        now = time.ticks_ms()
        d = self.get_direction()
        if d is None:
            self.last_dir = None
            return None
        if d != self.last_dir or time.ticks_diff(now, self.last_nav_time) > NAV_REPEAT_MS:
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
        return abs(dx) < self.deadzone * 2 and abs(dy) < self.deadzone * 2


# ============================================================
# PRESSURE SENSOR (HX710B / MPS20N0040D-S)
# ============================================================

class PuffSensor:
    def __init__(self, data_pin, clk_pin, threshold=PUFF_THRESHOLD):
        self.data = machine.Pin(data_pin, machine.Pin.IN)
        self.clk = machine.Pin(clk_pin, machine.Pin.OUT)
        self.clk.value(0)
        self.threshold = threshold
        self.baseline = 0
        self.max_range = 1
        self.last_puff_time = 0
        self.samples_buf = [0] * PUFF_SAMPLES
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
        self.samples_buf[self.sample_idx] = n
        self.sample_idx = (self.sample_idx + 1) % PUFF_SAMPLES
        return sum(self.samples_buf) / PUFF_SAMPLES
    
    def detect_puff(self):
        now = time.ticks_ms()
        if time.ticks_diff(now, self.last_puff_time) < PUFF_COOLDOWN_MS: return False
        if self.read_normalized() >= self.threshold:
            self.last_puff_time = now
            return True
        return False
    
    def get_level(self):
        return self.read_normalized()


# ============================================================
# FILE SERVER - serves HTML games from www/ folder
# ============================================================

_CONTENT_TYPES = {
    '.html': 'text/html; charset=utf-8',
    '.js': 'application/javascript',
    '.css': 'text/css',
    '.json': 'application/json',
    '.png': 'image/png',
    '.jpg': 'image/jpeg',
    '.ico': 'image/x-icon',
    '.svg': 'image/svg+xml',
}

def _file_exists(path):
    try:
        os.stat(path)
        return True
    except OSError:
        return False

def _serve_file(client, filepath):
    ext = filepath[filepath.rfind('.'):]
    ctype = _CONTENT_TYPES.get(ext, 'application/octet-stream')
    try:
        size = os.stat(filepath)[6]
        client.send(b'HTTP/1.1 200 OK\r\n')
        client.send(f'Content-Type: {ctype}\r\n'.encode())
        client.send(f'Content-Length: {size}\r\n'.encode())
        client.send(b'Cache-Control: max-age=3600\r\nConnection: close\r\n\r\n')
        buf = bytearray(2048)
        with open(filepath, 'rb') as f:
            while True:
                n = f.readinto(buf)
                if n == 0: break
                client.send(buf[:n])
    except OSError:
        _send_404(client, filepath)

def _send_404(client, path):
    body = f'<html><body><h1>404</h1><p>{path}</p></body></html>'
    client.send(b'HTTP/1.1 404 Not Found\r\nContent-Type: text/html\r\nConnection: close\r\n\r\n')
    client.send(body.encode())

def _generate_portal(wifi_ip):
    games = []
    try:
        for entry in os.listdir(WWW_DIR):
            if entry.endswith('.html') and entry != 'index.html':
                name = entry[:-5].replace('-', ' ').replace('_', ' ').title()
                games.append((entry, name))
    except OSError:
        pass
    
    btns = ''
    for fn, name in sorted(games, key=lambda x: x[1]):
        btns += f'<a href="/{WWW_DIR}/{fn}" class="g">{name}</a>'
    if not btns:
        btns = '<p style="color:#78909c">Noch keine Spiele. Lade HTML in <code>www/</code></p>'
    
    return f"""<!DOCTYPE html><html lang="de"><head><meta charset="UTF-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>MundMaus</title><style>
*{{margin:0;padding:0;box-sizing:border-box}}
body{{font-family:system-ui,sans-serif;background:#0a1628;color:#e0e0e0;
min-height:100vh;display:flex;flex-direction:column;align-items:center;justify-content:center;padding:2em}}
h1{{font-size:clamp(2em,5vw,3.5em);color:#00d4ff;margin-bottom:.2em}}
.sub{{color:#78909c;margin-bottom:2em}}
.gs{{display:flex;flex-wrap:wrap;gap:1.5em;justify-content:center;max-width:800px}}
.g{{display:flex;align-items:center;justify-content:center;width:220px;height:120px;
background:linear-gradient(135deg,#1a3a5c,#0d2240);border:2px solid #00d4ff44;border-radius:16px;
color:#00d4ff;font-size:1.3em;font-weight:600;text-decoration:none;transition:all .2s}}
.g:hover{{border-color:#00d4ff;transform:scale(1.05);box-shadow:0 0 20px #00d4ff33}}
.i{{margin-top:2em;color:#546e7a;font-size:.85em;text-align:center}}
code{{background:#1a2a3a;padding:2px 6px;border-radius:4px;color:#80cbc4}}
</style></head><body>
<h1>🎮 MundMaus</h1>
<p class="sub">Assistive Gaming Controller v{VERSION}</p>
<div class="gs">{btns}</div>
<div class="i">📶 {wifi_ip} &nbsp;|&nbsp; {BOARD} &nbsp;|&nbsp; v{VERSION} &nbsp;|&nbsp; RAM: {gc.mem_free()//1024}KB frei</div>
</body></html>"""


# ============================================================
# COMBINED HTTP + WEBSOCKET SERVER
# ============================================================

class MundMausServer:
    def __init__(self, wifi_manager, ws_port=WS_PORT, http_port=HTTP_PORT):
        self.wifi = wifi_manager
        self.ws_port = ws_port
        self.http_port = http_port
        self.ws_clients = []
        self.ws_server = None
        self.http_server = None
        self._pending_reboot = False
    
    def start(self):
        self.http_server = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        self.http_server.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        self.http_server.bind(('0.0.0.0', self.http_port))
        self.http_server.listen(3)
        self.http_server.setblocking(False)
        print(f"  HTTP  :{self.http_port}")
        
        self.ws_server = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        self.ws_server.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        self.ws_server.bind(('0.0.0.0', self.ws_port))
        self.ws_server.listen(2)
        self.ws_server.setblocking(False)
        print(f"  WS    :{self.ws_port}")
    
    def poll_http(self):
        try:
            client, addr = self.http_server.accept()
            client.settimeout(3)
            try:
                request = client.recv(2048).decode('utf-8', 'ignore')
                self._handle_http(client, request)
            except:
                pass
            finally:
                client.close()
        except OSError:
            pass
    
    def _handle_http(self, client, request):
        fl = request.split('\r\n')[0] if request else ''
        
        if 'POST /api/wifi' in fl:
            self._api_wifi_config(client, request)
        elif 'GET /api/wifi' in fl:
            self._send_json(client, self.wifi.get_status())
        elif 'GET /api/scan' in fl:
            self._send_json(client, {'networks': self.wifi.scan_networks()})
        elif 'GET /api/reboot' in fl:
            self._send_json(client, {'ok': True})
            self._pending_reboot = True
        elif 'GET /api/info' in fl:
            self._send_json(client, {
                'version': VERSION, 'board': BOARD,
                'ip': self.wifi.ip, 'mode': self.wifi.mode,
                'mem_free': gc.mem_free()
            })
        elif f'GET /{WWW_DIR}/' in fl:
            path = fl.split(' ')[1].lstrip('/')
            if '..' not in path and _file_exists(path):
                _serve_file(client, path)
            else:
                _send_404(client, path)
        elif 'GET / ' in fl or 'GET /index' in fl:
            p = _generate_portal(self.wifi.ip)
            client.send(b'HTTP/1.1 200 OK\r\nContent-Type: text/html; charset=utf-8\r\n')
            client.send(f'Content-Length: {len(p)}\r\nConnection: close\r\n\r\n'.encode())
            for i in range(0, len(p), 2048):
                client.send(p[i:i+2048].encode() if isinstance(p, str) else p[i:i+2048])
        elif 'GET /favicon' in fl:
            client.send(b'HTTP/1.1 204 No Content\r\n\r\n')
        else:
            self._serve_setup(client)
    
    def _api_wifi_config(self, client, request):
        try:
            body = request.split('\r\n\r\n', 1)
            if len(body) < 2:
                self._send_json(client, {'ok': False, 'error': 'No body'}, 400)
                return
            data = json.loads(body[1])
            ssid = data.get('ssid', '').strip()
            pw = data.get('password', '').strip()
            if not ssid:
                self._send_json(client, {'ok': False, 'error': 'SSID leer'}, 400)
                return
            self.wifi.save_credentials(ssid, pw)
            self.ws_send_all({'type': 'wifi_status', 'status': 'saved', 'ssid': ssid,
                              'message': 'Gespeichert. Neustart...'})
            self._send_json(client, {'ok': True, 'ssid': ssid,
                                     'message': f"'{ssid}' gespeichert. Neustart..."})
            self._pending_reboot = True
        except Exception as e:
            self._send_json(client, {'ok': False, 'error': str(e)}, 500)
    
    def _send_json(self, client, data, status=200):
        body = json.dumps(data)
        client.send(f'HTTP/1.1 {status} OK\r\n'.encode())
        client.send(b'Content-Type: application/json\r\nAccess-Control-Allow-Origin: *\r\n')
        client.send(f'Content-Length: {len(body)}\r\nConnection: close\r\n\r\n'.encode())
        client.send(body.encode())
    
    def _serve_setup(self, client):
        html = f"""<!DOCTYPE html><html><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>MundMaus Setup</title><style>
body{{font-family:sans-serif;background:#1e5631;color:#fff;display:flex;align-items:center;
justify-content:center;min-height:100vh;text-align:center}}
.b{{background:rgba(0,0,0,.4);padding:2em;border-radius:12px;max-width:400px}}
h1{{color:#00d4ff}}input,select{{width:100%;padding:10px;margin:8px 0;border-radius:6px;border:none;font-size:16px}}
button{{width:100%;padding:12px;margin-top:12px;background:#00d4ff;color:#000;border:none;
border-radius:6px;font-size:18px;font-weight:bold;cursor:pointer}}
.s{{margin-top:15px;font-size:14px;color:#aaa}}
#sb{{background:#444;color:#fff;font-size:14px;padding:8px}}
</style></head><body><div class="b">
<h1>🎮 MundMaus</h1>
<p>{BOARD} &mdash; v{VERSION}</p>
<button id="sb" onclick="sc()">🔍 Netzwerke suchen</button>
<select id="sl" onchange="document.getElementById('si').value=this.value" style="display:none"></select>
<input id="si" placeholder="WLAN Name (SSID)">
<input id="pw" type="password" placeholder="Passwort">
<button onclick="sv()">Verbinden</button>
<div class="s" id="st">IP: {self.wifi.ip}</div></div>
<script>
async function sc(){{document.getElementById('sb').textContent='...';
try{{const r=await fetch('/api/scan'),d=await r.json(),s=document.getElementById('sl');
s.innerHTML='<option>-- wählen --</option>';
d.networks.forEach(n=>{{const o=document.createElement('option');o.value=n;o.textContent=n;s.appendChild(o)}});
s.style.display='block'}}catch(e){{document.getElementById('st').textContent='Fehler'}}
document.getElementById('sb').textContent='🔍 Suchen'}}
async function sv(){{const s=document.getElementById('si').value,p=document.getElementById('pw').value;
if(!s)return alert('SSID!');document.getElementById('st').textContent='Speichere...';
try{{const r=await fetch('/api/wifi',{{method:'POST',headers:{{'Content-Type':'application/json'}},
body:JSON.stringify({{ssid:s,password:p}})}}),d=await r.json();
document.getElementById('st').textContent=d.message||'OK'}}catch(e){{document.getElementById('st').textContent=''+e}}}}
</script></body></html>"""
        client.send(b'HTTP/1.1 200 OK\r\nContent-Type: text/html; charset=utf-8\r\n')
        client.send(f'Content-Length: {len(html)}\r\nConnection: close\r\n\r\n'.encode())
        client.send(html.encode())
    
    # --- WebSocket ---
    
    def poll_ws(self):
        try:
            client, addr = self.ws_server.accept()
            if self._ws_handshake(client):
                client.setblocking(False)
                self.ws_clients.append(client)
                self.ws_send_one(client, {
                    'type': 'wifi_status',
                    'status': 'connected' if self.wifi.mode == 'station' else 'ap',
                    'ssid': self.wifi.ssid or AP_SSID,
                    'ip': self.wifi.ip, 'mode': self.wifi.mode
                })
            else:
                client.close()
        except OSError:
            pass
    
    def _ws_handshake(self, client):
        try:
            import hashlib, binascii
            client.settimeout(2)
            data = client.recv(1024).decode()
            if 'Upgrade: websocket' not in data: return False
            key = None
            for line in data.split('\r\n'):
                if 'Sec-WebSocket-Key:' in line:
                    key = line.split(': ')[1].strip(); break
            if not key: return False
            MAGIC = '258EAFA5-E914-47DA-95CA-C5AB0DC85B11'
            accept = binascii.b2a_base64(
                hashlib.sha1((key + MAGIC).encode()).digest()
            ).decode().strip()
            client.send(
                f'HTTP/1.1 101 Switching Protocols\r\n'
                f'Upgrade: websocket\r\nConnection: Upgrade\r\n'
                f'Sec-WebSocket-Accept: {accept}\r\n\r\n'.encode()
            )
            return True
        except:
            return False
    
    def _ws_frame(self, payload):
        length = len(payload)
        frame = bytearray([0x81])
        if length < 126:
            frame.append(length)
        elif length < 65536:
            frame.append(126)
            frame.extend(length.to_bytes(2, 'big'))
        frame.extend(payload)
        return bytes(frame)
    
    def ws_send_all(self, message):
        if not self.ws_clients: return
        frame = self._ws_frame(json.dumps(message).encode())
        dead = []
        for i, c in enumerate(self.ws_clients):
            try: c.send(frame)
            except: dead.append(i)
        for i in reversed(dead):
            try: self.ws_clients[i].close()
            except: pass
            self.ws_clients.pop(i)
    
    def ws_send_one(self, client, message):
        try:
            client.send(self._ws_frame(json.dumps(message).encode()))
        except:
            pass
    
    def ws_read_all(self):
        messages = []
        dead = []
        for i, c in enumerate(self.ws_clients):
            try:
                data = c.recv(512)
                if data and len(data) > 2:
                    payload = self._ws_decode(data)
                    if payload:
                        try: messages.append(json.loads(payload))
                        except: pass
            except OSError:
                pass
            except:
                dead.append(i)
        for i in reversed(dead):
            try: self.ws_clients[i].close()
            except: pass
            self.ws_clients.pop(i)
        return messages
    
    def _ws_decode(self, data):
        try:
            if len(data) < 6: return None
            if (data[0] & 0x0f) != 1: return None
            length = data[1] & 0x7f
            idx = 2
            if length == 126:
                length = int.from_bytes(data[2:4], 'big')
                idx = 4
            if data[1] & 0x80:
                mask = data[idx:idx+4]; idx += 4
                payload = bytearray(data[idx:idx+length])
                for j in range(len(payload)):
                    payload[j] ^= mask[j % 4]
                return payload.decode('utf-8', 'ignore')
            return data[idx:idx+length].decode('utf-8', 'ignore')
        except:
            return None
    
    def check_reboot(self):
        if self._pending_reboot:
            time.sleep(2)
            machine.reset()
    
    def send_nav(self, d): self.ws_send_all({"type": "nav", "dir": d})
    def send_action(self, k): self.ws_send_all({"type": "action", "kind": k})
    def send_puff_level(self, v): self.ws_send_all({"type": "puff_level", "value": round(v, 3)})


# ============================================================
# DISPLAY (optional ST7735)
# ============================================================

def init_display():
    if not USE_DISPLAY: return None
    try:
        from ST7735 import TFT
        from sysfont import sysfont
        spi = machine.SPI(1, baudrate=20000000, polarity=0, phase=0,
            sck=machine.Pin(PIN_DISP_SCK), mosi=machine.Pin(PIN_DISP_SDA))
        tft = TFT(spi, PIN_DISP_A0, PIN_DISP_RST, PIN_DISP_CS)
        tft.initr(); tft.rgb(True); tft.fill(TFT.BLACK)
        return tft
    except Exception as e:
        print(f"  Display: {e}")
        return None

def display_status(tft, ip, mode, joy_cal, puff_bl, clients):
    if not tft: return
    try:
        from sysfont import sysfont
        from ST7735 import TFT
        tft.fill(TFT.BLACK)
        tft.text((5, 5), f"MundMaus v{VERSION}", TFT.WHITE, sysfont)
        tft.text((5, 20), f"{'WLAN' if mode=='station' else 'HOTSPOT'}: {ip}", TFT.CYAN, sysfont)
        tft.text((5, 35), f"Joy: {joy_cal[0]},{joy_cal[1]}", TFT.GREEN, sysfont)
        tft.text((5, 50), f"Puff: {puff_bl}", TFT.YELLOW, sysfont)
        tft.text((5, 65), f"Clients: {clients}", TFT.WHITE, sysfont)
        tft.text((5, 80), f"{BOARD}", TFT.WHITE, sysfont)
    except:
        pass


# ============================================================
# ASYNC TASKS
# ============================================================

async def sensor_loop(joystick, puff, server):
    """Polls joystick + puff sensor at ~50 Hz."""
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
    """Handles HTTP, WS connections, and incoming messages."""
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
    """Updates display every 5 seconds."""
    while True:
        display_status(tft, ip, mode,
                       (joystick.center_x, joystick.center_y),
                       puff.baseline if puff else 0,
                       len(server.ws_clients))
        await asyncio.sleep_ms(5000)


# ============================================================
# MAIN
# ============================================================

async def async_main():
    print("=" * 42)
    print(f"  MUNDMAUS v{VERSION}")
    print(f"  Board: {BOARD}")
    print("=" * 42)
    
    # Ensure www/ exists
    try:
        os.stat(WWW_DIR)
    except OSError:
        try: os.mkdir(WWW_DIR)
        except: pass
    
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
    
    print(f"\n  {'='*38}")
    if mode == 'ap':
        print(f"  HOTSPOT: {AP_SSID} / {AP_PASS}")
    else:
        print(f"  WLAN: {wifi.ssid}")
    print(f"  IP: {ip}")
    print(f"  http://{ip}")
    print(f"  {'='*38}")
    
    # Server
    print("\n[Server]")
    server = MundMausServer(wifi)
    server.start()
    
    display_status(tft, ip, mode,
                   (joystick.center_x, joystick.center_y),
                   puff.baseline if puff else 0, 0)
    
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

