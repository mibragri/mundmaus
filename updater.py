# updater.py — OTA update: manifest check, download, atomic install

import gc
import json
import os

try:
    import asyncio
except ImportError:
    import uasyncio as asyncio

from config import OTA_AUTH, OTA_BASE_URL, UPDATE_STATE_FILE, VERSIONS_FILE


def _load_versions():
    try:
        with open(VERSIONS_FILE) as f:
            return json.load(f)
    except (OSError, ValueError):
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


async def run_update(available, progress_cb=None, error_cb=None):
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
            if error_cb:
                error_cb(fname, "Download fehlgeschlagen")
        await asyncio.sleep_ms(0)

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
            if error_cb:
                error_cb(fname, "Download fehlgeschlagen")
            break
        await asyncio.sleep_ms(0)

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
        # Step 0: set pending state BEFORE any destructive operations
        with open(UPDATE_STATE_FILE, 'w') as f:
            json.dump({'status': 'pending', 'attempts': 0}, f)

        # Step a: create all backups
        for upd in firmware:
            fname = upd['file']
            if _file_exists(fname):
                _safe_remove(fname + '.bak')
                os.rename(fname, fname + '.bak')

        # Step b: rename all .new → final
        try:
            for upd in firmware:
                fname = upd['file']
                os.rename(fname + '.new', fname)
                local[fname] = upd['to_ver']
        except Exception as e:
            print(f"  Install-Fehler: {e}, Rollback...")
            for upd in firmware:
                fname = upd['file']
                if _file_exists(fname + '.bak'):
                    _safe_remove(fname)
                    os.rename(fname + '.bak', fname)
            # Do NOT delete state file — let boot.py handle rollback on next reboot
            # if immediate rollback was incomplete
            try:
                with open(UPDATE_STATE_FILE, 'w') as f:
                    json.dump({'status': 'ok'}, f)
            except:
                pass
            return False, f"Install fehlgeschlagen: {e}, Rollback durchgefuehrt"

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

    gc.collect()
    addr = socket.getaddrinfo(host, 443)[0][-1]
    raw_sock = socket.socket()
    raw_sock.settimeout(timeout)
    sock = raw_sock
    try:
        raw_sock.connect(addr)
        sock = ssl.wrap_socket(raw_sock, server_hostname=host)
        sock.write(f'GET {path} HTTP/1.0\r\nHost: {host}\r\nAuthorization: Basic {OTA_AUTH}\r\n\r\n'.encode())

        # Read header
        header = b''
        while b'\r\n\r\n' not in header:
            if len(header) > 4096:
                print(f"  Header zu gross ({host})")
                return None
            chunk = sock.read(256)
            if not chunk:
                return None
            header += chunk

        header_end = header.index(b'\r\n\r\n') + 4
        status_line = header.split(b'\r\n')[0]
        if b' 200 ' not in status_line:
            print(f"  HTTP {status_line} ({host})")
            return None
        body = header[header_end:]

        # Read rest
        while True:
            chunk = sock.read(1024)
            if not chunk:
                break
            body += chunk
            if len(body) > 16384:
                print(f"  Body zu gross ({host})")
                return None

        return body
    except Exception as e:
        print(f"  HTTP Fehler ({host}): {e}")
        return None
    finally:
        try:
            sock.close()
        except:
            pass
        if sock is not raw_sock:
            try:
                raw_sock.close()
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

    gc.collect()  # SSL handshake needs ~20KB free RAM
    addr = socket.getaddrinfo(host, 443)[0][-1]
    raw_sock = socket.socket()
    raw_sock.settimeout(10)
    sock = raw_sock
    try:
        raw_sock.connect(addr)
        sock = ssl.wrap_socket(raw_sock, server_hostname=host)
        sock.write(f'GET {path} HTTP/1.0\r\nHost: {host}\r\nAuthorization: Basic {OTA_AUTH}\r\n\r\n'.encode())

        # Skip header
        header = b''
        while b'\r\n\r\n' not in header:
            if len(header) > 4096:
                print(f"  Header zu gross ({host})")
                return False
            chunk = sock.read(256)
            if not chunk:
                return False
            header += chunk

        header_end = header.index(b'\r\n\r\n') + 4
        remainder = header[header_end:]

        # Check HTTP status
        status_line = header.split(b'\r\n')[0]
        if b' 200 ' not in status_line:
            print(f"  Download {fname}: {status_line}")
            return False

        # Extract Content-Length for verification
        expected_size = 0
        for hline in header.split(b'\r\n'):
            if hline.lower().startswith(b'content-length:'):
                expected_size = int(hline.split(b':')[1].strip())
                break

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

        # Verify download size against Content-Length
        actual_size = os.stat(dest)[6]
        if expected_size > 0 and actual_size != expected_size:
            print(f"  Download {fname}: {actual_size}/{expected_size} bytes (unvollstaendig)")
            _safe_remove(dest)
            return False

        # Verify non-empty download
        if actual_size == 0:
            print(f"  Download {fname}: leer")
            _safe_remove(dest)
            return False
        return True
    except Exception as e:
        print(f"  Download {fname}: {e}")
        return False
    finally:
        try:
            sock.close()
        except:
            pass
        if sock is not raw_sock:
            try:
                raw_sock.close()
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
