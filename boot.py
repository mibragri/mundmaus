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

# Intentionally hardcoded — boot.py must not import config.py
# (if config.py is broken, boot.py is the safety net)
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


def _recovery_ap():
    """Minimal AP with file upload page. Blocks forever."""
    import network
    import socket

    ap = network.WLAN(network.AP_IF)
    ap.active(True)
    ap.config(essid='MundMaus-Recovery', password='mundmaus1', authmode=3)
    print("  Recovery-AP: MundMaus-Recovery / 192.168.4.1")

    srv = socket.socket()
    srv.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
    srv.bind(('0.0.0.0', 80))
    srv.listen(1)

    _upload_page = b"""<!DOCTYPE html><html><head><meta charset="utf-8">
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
            req = cl.recv(256)
            fl = req.split(b'\r\n')[0].decode('utf-8', 'ignore') if req else ''

            if 'POST /upload/' in fl:
                fname = fl.split('/upload/')[1].split(' ')[0]
                fname = fname.replace('%20', ' ')
                if '/' in fname or '\\' in fname:
                    fname = fname.split('/')[-1].split('\\')[-1]
                if fname.startswith('.'):
                    fname = '_' + fname
                # Read past headers (as bytes)
                while b'\r\n\r\n' not in req:
                    req += cl.recv(256)
                # Extract Content-Length from headers
                header_part = req[:req.index(b'\r\n\r\n')].decode('utf-8', 'ignore')
                cl_match = [line for line in header_part.split('\r\n') if 'Content-Length:' in line]
                cl_len = int(cl_match[0].split(':')[1].strip()) if cl_match else 0
                # Extract body as raw bytes
                body_start = req.index(b'\r\n\r\n') + 4
                body = req[body_start:]
                while len(body) < cl_len:
                    body += cl.recv(2048)
                dest = f'www/{fname}' if fname.endswith('.html') and not fname.endswith('.py') else fname
                with open(dest, 'wb') as f:
                    f.write(body)
                cl.send(b'HTTP/1.1 200 OK\r\nContent-Length: 2\r\n\r\nOK')
                print(f"  Upload: {dest} ({len(body)} bytes)")
            else:
                cl.send(b'HTTP/1.1 200 OK\r\nContent-Type: text/html\r\n')
                cl.send(f'Content-Length: {len(_upload_page)}\r\nConnection: close\r\n\r\n'.encode())
                cl.send(_upload_page)

            cl.close()
        except Exception as e:
            print(f"  Recovery: {e}")
            try:
                cl.close()
            except:
                pass


# ============================================================
# BOOT LOGIC
# ============================================================

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
