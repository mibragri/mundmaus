# server.py — HTTP + WebSocket server, portal, file serving

import gc
import json
import os
import socket
import time

import machine

from config import (
    AP_SSID,
    BOARD,
    HTTP_PORT,
    VERSION,
    WS_PORT,
    WWW_DIR,
)

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
                if not n: break
                client.send(buf[:n])
    except OSError:
        _send_404(client, filepath)

def _send_404(client, path):
    body = f'<html><body><h1>404</h1><p>{path}</p></body></html>'.encode()
    client.send(b'HTTP/1.1 404 Not Found\r\nContent-Type: text/html\r\n')
    client.send(f'Content-Length: {len(body)}\r\nConnection: close\r\n\r\n'.encode())
    client.send(body)

def _generate_portal(wifi, wifi_ip, hw_status=None):
    recovery = False
    try:
        with open('update_state.json') as _f:
            _us = json.load(_f)
            recovery = _us.get('recovery', False)
    except:
        pass

    recovery_banner = '<div style="background:#8b0000;padding:12px;border-radius:8px;margin-bottom:1em;max-width:800px;width:100%;text-align:center;margin-top:1em">Update fehlgeschlagen - alte Version wiederhergestellt</div>' if recovery else ''

    games = []
    try:
        for entry in os.listdir(WWW_DIR):
            if entry.endswith('.html') and entry != 'index.html':
                name = entry[:-5].replace('-', ' ').replace('_', ' ')
                name = name[0].upper() + name[1:] if name else name
                games.append((entry, name))
    except OSError:
        pass

    btns = ''
    for fn, name in sorted(games, key=lambda x: x[1]):
        btns += f'<a href="/{WWW_DIR}/{fn}" class="g">{name}</a>'
    if not btns:
        btns = '<p style="color:#78909c">Noch keine Spiele. Lade HTML in <code>www/</code></p>'

    wm = wifi
    mode = wm.mode if wm else '?'
    ssid = (wm.ssid or AP_SSID) if wm else '?'
    connected = wm.sta.isconnected() if wm and mode == 'station' else False
    mode_label = 'WLAN' if mode == 'station' else 'Hotspot'
    dot_color = '#4caf50' if connected else '#f0a030' if mode == 'ap' else '#d42a2a'
    rssi, rssi_label = wm.get_rssi() if wm else (0, '')
    rssi_text = f' ({rssi_label}, {rssi}dBm)' if rssi_label else ''

    return f"""<!DOCTYPE html><html lang="de"><head><meta charset="UTF-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>MundMaus</title><style>
*{{margin:0;padding:0;box-sizing:border-box}}
body{{font-family:system-ui,sans-serif;background:#0a1628;color:#e0e0e0;
min-height:100vh;display:flex;flex-direction:column;align-items:center;padding:2em}}
h1{{font-size:clamp(2em,5vw,3.5em);color:#FFD700;margin-bottom:.2em}}
.sub{{color:#78909c;margin-bottom:1.5em}}
.gs{{display:flex;flex-wrap:wrap;gap:1.5em;justify-content:center;max-width:800px}}
.g{{display:flex;align-items:center;justify-content:center;width:220px;height:120px;
background:linear-gradient(135deg,#1a3a5c,#0d2240);border:2px solid rgba(255,215,0,.3);border-radius:16px;
color:#FFD700;font-size:1.3em;font-weight:600;text-decoration:none;transition:all .2s}}
.g:hover{{border-color:#FFD700;transform:scale(1.05);box-shadow:0 0 20px rgba(255,215,0,.3)}}
.wf{{background:rgba(255,255,255,.04);border:1px solid #333;border-radius:12px;padding:1.2em;
margin-top:2em;max-width:500px;width:100%}}
.wf h2{{font-size:1.1em;color:#FFD700;margin-bottom:.8em;display:flex;align-items:center;gap:.5em}}
.wd{{width:10px;height:10px;border-radius:50%;background:{dot_color};flex-shrink:0}}
.wf label{{font-size:.85em;color:#aaa;display:block;margin-bottom:.3em}}
.wf select,.wf input{{width:100%;padding:8px;margin-bottom:.8em;background:#1a2a3a;
border:1px solid #444;border-radius:6px;color:#fff;font-size:15px}}
.wf select:focus,.wf input:focus{{border-color:#FFD700;outline:none}}
.wf button{{padding:10px 16px;border:none;border-radius:6px;font-size:15px;font-weight:600;cursor:pointer}}
.wb{{background:#FFD700;color:#000;width:100%}}
.wb:hover{{background:#ffe44d}}
.wsc{{background:#333;color:#ccc;margin-bottom:.8em;width:100%}}
.wsc:hover{{background:#444}}
.wm{{font-size:.85em;color:#FFD700;margin-top:.5em;min-height:1.2em}}
.rb{{background:#8b0000;color:#fff;padding:8px 20px;border:none;border-radius:6px;
font-size:.9em;cursor:pointer;margin-top:1.5em}}
.rb:hover{{background:#a00}}
.i{{margin-top:1.5em;color:#546e7a;font-size:.85em;text-align:center}}
code{{background:#1a2a3a;padding:2px 6px;border-radius:4px;color:#80cbc4}}
</style></head><body>
<h1>MundMaus</h1>
<p class="sub">Assistive Gaming Controller v{VERSION}</p>
<div class="gs">{btns}</div>
{recovery_banner}
<div class="wf" id="upd" style="display:none">
<h2>Software</h2>
<div id="upd-info"></div>
<button class="wb" id="upd-btn" onclick="startUpdate()" style="display:none">Jetzt installieren</button>
<div id="upd-progress" style="display:none">
<div style="background:#333;border-radius:4px;height:24px;margin:8px 0">
<div id="upd-bar" style="background:#FFD700;height:100%;border-radius:4px;width:0%;transition:width .3s"></div>
</div>
<div id="upd-file" style="font-size:.85em;color:#aaa"></div>
</div>
</div>
<div class="wf">
<h2><span class="wd"></span> {mode_label}: {ssid} - {wifi_ip}{rssi_text}</h2>
<button class="wsc" onclick="sc()">Netzwerke suchen</button>
<label>SSID</label>
<select id="sl" onchange="document.getElementById('si').value=this.value" style="display:none"></select>
<input id="si" placeholder="WLAN Name (SSID)">
<label>Passwort</label>
<input id="pw" type="password" placeholder="Passwort">
<button class="wb" onclick="sv()">Verbinden</button>
<div class="wm" id="wm"></div>
</div>
<button class="rb" onclick="rb()">Neustart</button>
<div class="i" style="display:flex;flex-wrap:wrap;gap:8px;align-items:center;justify-content:center">{wifi_ip} | {BOARD} | v{VERSION} | RAM: {gc.mem_free()//1024}KB
<span title="Joystick: {'verbunden' if hw_status and hw_status.get('joystick') else 'nicht angeschlossen'}" style="display:inline-flex;align-items:center;gap:4px;background:{'rgba(76,175,80,.15)' if hw_status and hw_status.get('joystick') else 'rgba(212,42,42,.15)'};border:1px solid {'#4caf50' if hw_status and hw_status.get('joystick') else '#d42a2a'};border-radius:12px;padding:2px 10px;font-size:.8em"><span style="width:6px;height:6px;border-radius:50%;background:{'#4caf50' if hw_status and hw_status.get('joystick') else '#d42a2a'}"></span>Joystick</span>
<span title="Drucksensor: {'verbunden' if hw_status and hw_status.get('puff') else 'nicht angeschlossen'}" style="display:inline-flex;align-items:center;gap:4px;background:{'rgba(76,175,80,.15)' if hw_status and hw_status.get('puff') else 'rgba(212,42,42,.15)'};border:1px solid {'#4caf50' if hw_status and hw_status.get('puff') else '#d42a2a'};border-radius:12px;padding:2px 10px;font-size:.8em"><span style="width:6px;height:6px;border-radius:50%;background:{'#4caf50' if hw_status and hw_status.get('puff') else '#d42a2a'}"></span>Puff</span>
<span id="ws-chip" title="Verbindung zum Geraet" style="display:inline-flex;align-items:center;gap:4px;background:rgba(212,42,42,.15);border:1px solid #d42a2a;border-radius:12px;padding:2px 10px;font-size:.8em"><span id="ws-dot" style="width:6px;height:6px;border-radius:50%;background:#d42a2a"></span>Verbunden</span></div>
<script>
async function sc(){{try{{const r=await fetch('/api/scan'),d=await r.json(),s=document.getElementById('sl');
s.innerHTML='<option>-- waehlen --</option>';
d.networks.forEach(n=>{{const o=document.createElement('option');o.value=n;o.textContent=n;s.appendChild(o)}});
s.style.display='block';document.getElementById('wm').textContent=d.networks.length+' Netzwerke'}}
catch(e){{document.getElementById('wm').textContent='Scan fehlgeschlagen'}}}}
async function sv(){{const s=document.getElementById('si').value,p=document.getElementById('pw').value;
if(!s)return(document.getElementById('wm').textContent='SSID eingeben!');
document.getElementById('wm').textContent='Speichere...';
try{{const r=await fetch('/api/wifi',{{method:'POST',headers:{{'Content-Type':'application/json'}},
body:JSON.stringify({{ssid:s,password:p}})}}),d=await r.json();
document.getElementById('wm').textContent=d.message||'OK'}}
catch(e){{document.getElementById('wm').textContent='Fehler: '+e}}}}
async function rb(){{if(confirm('ESP32 neu starten?')){{try{{await fetch('/api/reboot')}}catch(e){{}}
document.getElementById('wm').textContent='Neustart...'}}}}
function connectWS(){{const ws=new WebSocket('ws://'+location.hostname+':81');ws.onopen=function(){{const d=document.getElementById('ws-dot'),c=document.getElementById('ws-chip');if(d)d.style.background='#4caf50';if(c){{c.style.background='rgba(76,175,80,.15)';c.style.borderColor='#4caf50'}};fetch('/api/updates').then(r=>r.json()).then(d=>{{const el=document.getElementById('upd'),info=document.getElementById('upd-info'),btn=document.getElementById('upd-btn');el.style.display='block';if(d.offline){{info.innerHTML='Keine Internetverbindung';btn.textContent='Nochmal pruefen';btn.style.display='block';btn.onclick=function(){{fetch('/api/updates/check',{{method:'POST'}});info.textContent='Wird geprueft...';btn.style.display='none'}}}}else if(d.available&&d.available.length>0){{info.innerHTML=d.available.length+' Verbesserung'+(d.available.length>1?'en':'')+' verfuegbar';btn.textContent='Jetzt installieren';btn.onclick=startUpdate;btn.style.display='block'}}else{{info.innerHTML='Alles auf dem neuesten Stand';btn.style.display='none'}}}}).catch(()=>{{}})}};ws.onclose=function(){{const d=document.getElementById('ws-dot'),c=document.getElementById('ws-chip');if(d)d.style.background='#d42a2a';if(c){{c.style.background='rgba(212,42,42,.15)';c.style.borderColor='#d42a2a'}};setTimeout(connectWS,3000)}};ws.onmessage=function(e){{const d=JSON.parse(e.data);
if(d.type==='update_status'){{const el=document.getElementById('upd'),info=document.getElementById('upd-info'),btn=document.getElementById('upd-btn');el.style.display='block';if(d.offline){{info.innerHTML='Keine Internetverbindung';btn.textContent='Nochmal pruefen';btn.style.display='block';btn.onclick=function(){{fetch('/api/updates/check',{{method:'POST'}});info.textContent='Wird geprueft...';btn.style.display='none'}}}}else if(d.available&&d.available.length>0){{info.innerHTML=d.available.length+' Verbesserung'+(d.available.length>1?'en':'')+' verfuegbar';btn.textContent='Jetzt installieren';btn.onclick=startUpdate;btn.style.display='block'}}else{{info.innerHTML='Alles auf dem neuesten Stand';btn.style.display='none'}}}}
else if(d.type==='update_progress'){{document.getElementById('upd-btn').style.display='none';document.getElementById('upd-progress').style.display='block';document.getElementById('upd-bar').style.width=(d.current/d.total*100)+'%';document.getElementById('upd-file').textContent='Datei '+d.current+'/'+d.total+': '+d.file}}
else if(d.type==='update_complete'){{document.getElementById('upd-progress').style.display='none';document.getElementById('upd-info').textContent=d.message;document.getElementById('upd-btn').textContent='Nochmal pruefen';document.getElementById('upd-btn').style.display='block';document.getElementById('upd-btn').onclick=function(){{fetch('/api/updates/check',{{method:'POST'}});document.getElementById('upd-info').textContent='Wird geprueft...';document.getElementById('upd-btn').style.display='none'}}}}
else if(d.type==='update_error'){{document.getElementById('upd-file').textContent='Fehler: '+d.file+' - '+d.error}}}};}}connectWS();
fetch('/api/updates').then(r=>r.json()).then(d=>{{const el=document.getElementById('upd'),info=document.getElementById('upd-info'),btn=document.getElementById('upd-btn');el.style.display='block';if(d.offline){{info.innerHTML='Keine Internetverbindung';btn.textContent='Nochmal pruefen';btn.style.display='block';btn.onclick=function(){{fetch('/api/updates/check',{{method:'POST'}});info.textContent='Wird geprueft...';btn.style.display='none'}}}}else if(d.available&&d.available.length>0){{info.innerHTML=d.available.length+' Verbesserung'+(d.available.length>1?'en':'')+' verfuegbar';btn.textContent='Jetzt installieren';btn.onclick=startUpdate;btn.style.display='block'}}else{{info.innerHTML='Alles auf dem neuesten Stand';btn.style.display='none'}}}}).catch(()=>{{}});
async function startUpdate(){{document.getElementById('upd-info').textContent='Wird installiert...';document.getElementById('upd-btn').style.display='none';try{{await fetch('/api/update/start',{{method:'POST'}})}}catch(e){{document.getElementById('upd-info').textContent='Fehler: '+e}}}}
</script>
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
        self._update_info = None  # Set by updater after manifest check
        self._updating = False
        self._recheck_updates = False

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
            client, _addr = self.http_server.accept()
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
        elif 'GET /api/updates' in fl:
            if self._update_info:
                self._send_json(client, self._update_info)
            else:
                self._send_json(client, {'available': [], 'offline': True})
        elif 'POST /api/updates/check' in fl:
            if self._updating:
                self._send_json(client, {'ok': False, 'error': 'Update laeuft bereits'})
            else:
                self._send_json(client, {'ok': True})
                self._recheck_updates = True
        elif 'POST /api/update/start' in fl:
            if self._updating:
                self._send_json(client, {'ok': False, 'error': 'Update laeuft bereits'})
            elif not self._update_info or not self._update_info.get('available'):
                self._send_json(client, {'ok': False, 'error': 'Keine Updates'})
            else:
                self._updating = True
                self._send_json(client, {'ok': True})
        elif f'GET /{WWW_DIR}/' in fl:
            path = fl.split(' ')[1].lstrip('/')
            if '..' not in path and _file_exists(path):
                _serve_file(client, path)
            else:
                _send_404(client, path)
        elif 'GET / ' in fl or 'GET /index' in fl:
            p = _generate_portal(self.wifi, self.wifi.ip, getattr(self, 'hw_status', None))
            p_bytes = p.encode('utf-8') if isinstance(p, str) else p
            client.send(b'HTTP/1.1 200 OK\r\nContent-Type: text/html; charset=utf-8\r\n')
            client.send(f'Content-Length: {len(p_bytes)}\r\nConnection: close\r\n\r\n'.encode())
            for i in range(0, len(p_bytes), 2048):
                client.send(p_bytes[i:i+2048])
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
        _reasons = {200: 'OK', 400: 'Bad Request', 500: 'Internal Server Error'}
        body = json.dumps(data).encode()
        client.send(f'HTTP/1.1 {status} {_reasons.get(status, "OK")}\r\n'.encode())
        client.send(b'Content-Type: application/json\r\nAccess-Control-Allow-Origin: *\r\n')
        client.send(f'Content-Length: {len(body)}\r\nConnection: close\r\n\r\n'.encode())
        client.send(body)

    def _serve_setup(self, client):
        html = f"""<!DOCTYPE html><html><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>MundMaus Setup</title><style>
body{{font-family:sans-serif;background:#0a1628;color:#fff;display:flex;align-items:center;
justify-content:center;min-height:100vh;text-align:center}}
.b{{background:rgba(255,255,255,.04);padding:2em;border-radius:12px;max-width:400px;border:1px solid #333}}
h1{{color:#FFD700}}input,select{{width:100%;padding:10px;margin:8px 0;border-radius:6px;border:1px solid #444;
font-size:16px;background:#1a2a3a;color:#fff}}
button{{width:100%;padding:12px;margin-top:12px;background:#FFD700;color:#000;border:none;
border-radius:6px;font-size:18px;font-weight:bold;cursor:pointer}}
.s{{margin-top:15px;font-size:14px;color:#aaa}}
#sb{{background:#333;color:#ccc;font-size:14px;padding:8px}}
</style></head><body><div class="b">
<h1>MundMaus</h1>
<p>{BOARD} - v{VERSION}</p>
<button id="sb" onclick="sc()">Netzwerke suchen</button>
<select id="sl" onchange="document.getElementById('si').value=this.value" style="display:none"></select>
<input id="si" placeholder="WLAN Name (SSID)">
<input id="pw" type="password" placeholder="Passwort">
<button onclick="sv()">Verbinden</button>
<div class="s" id="st">IP: {self.wifi.ip}</div></div>
<script>
async function sc(){{document.getElementById('sb').textContent='...';
try{{const r=await fetch('/api/scan'),d=await r.json(),s=document.getElementById('sl');
s.innerHTML='<option>-- waehlen --</option>';
d.networks.forEach(n=>{{const o=document.createElement('option');o.value=n;o.textContent=n;s.appendChild(o)}});
s.style.display='block'}}catch(e){{document.getElementById('st').textContent='Fehler'}}
document.getElementById('sb').textContent='Suchen'}}
async function sv(){{const s=document.getElementById('si').value,p=document.getElementById('pw').value;
if(!s)return alert('SSID!');document.getElementById('st').textContent='Speichere...';
try{{const r=await fetch('/api/wifi',{{method:'POST',headers:{{'Content-Type':'application/json'}},
body:JSON.stringify({{ssid:s,password:p}})}}),d=await r.json();
document.getElementById('st').textContent=d.message||'OK'}}catch(e){{document.getElementById('st').textContent=''+e}}}}
</script></body></html>"""
        html_bytes = html.encode('utf-8')
        client.send(b'HTTP/1.1 200 OK\r\nContent-Type: text/html; charset=utf-8\r\n')
        client.send(f'Content-Length: {len(html_bytes)}\r\nConnection: close\r\n\r\n'.encode())
        client.send(html_bytes)

    # --- WebSocket ---

    def poll_ws(self):
        try:
            client, _addr = self.ws_server.accept()
            if self._ws_handshake(client):
                client.setblocking(False)
                self.ws_clients.append(client)
                self.ws_send_one(client, {
                    'type': 'wifi_status',
                    'status': 'connected' if self.wifi.mode == 'station' else 'ap',
                    'ssid': self.wifi.ssid or AP_SSID,
                    'ip': self.wifi.ip, 'mode': self.wifi.mode
                })
                if self._update_info:
                    msg = {'type': 'update_status'}
                    msg.update(self._update_info)
                    self.ws_send_one(client, msg)
                if self._updating:
                    self.ws_send_one(client, {'type': 'update_status', 'updating': True})
            else:
                client.close()
        except OSError:
            pass

    def _ws_handshake(self, client):
        try:
            import binascii
            import hashlib
            client.settimeout(2)
            data = client.recv(1024).decode()
            if 'Upgrade: websocket' not in data: return False
            key = None
            for line in data.split('\r\n'):
                if 'Sec-WebSocket-Key:' in line:
                    key = line.split(': ')[1].strip(); break
            if not key: return False
            magic = '258EAFA5-E914-47DA-95CA-C5AB0DC85B11'
            accept = binascii.b2a_base64(
                hashlib.sha1((key + magic).encode()).digest()
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
                if not data:
                    # Connection closed
                    dead.append(i)
                    continue
                if len(data) > 2:
                    # Check for close frame (opcode 0x8)
                    if (data[0] & 0x0f) == 0x8:
                        dead.append(i)
                        continue
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
