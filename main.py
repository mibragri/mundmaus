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

import config
from config import (
    AP_PASS,
    AP_SSID,
    BOARD,

    PIN_PUFF_CLK,
    PIN_PUFF_DATA,
    PIN_SW,
    PIN_VRX,
    PIN_VRY,
    PUFF_SEND_INTERVAL_MS,
    RECAL_IDLE_MS,

    UPDATE_STATE_FILE,
    VERSION,
    WWW_DIR,
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
        try:
            now = time.ticks_ms()

            nav = joystick.poll_navigation()
            if nav:
                server.send_nav(nav)
                idle_start = now

            if joystick.poll_button():
                server.send_action('press')
                idle_start = now

            if puff:
                puff.poll()
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
        except Exception as e:
            print(f"  sensor_loop: {e}")

        _heartbeat['sensor'] = time.ticks_ms()
        await asyncio.sleep_ms(config.SENSOR_POLL_MS)




async def server_loop(server, wifi, joystick=None, puff=None):
    while True:
        try:
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

            server.check_reboot()

        except Exception as e:
            print(f"  server_loop: {e}")

        _heartbeat['server'] = time.ticks_ms()
        await asyncio.sleep_ms(10)


async def wifi_monitor(wifi):
    """Reconnect WiFi if connection drops. Essential for remote deployment."""
    while True:
        await asyncio.sleep_ms(30000)
        if wifi.mode == 'station' and not wifi.sta.isconnected():
            print("  WiFi verloren, reconnect...")
            ip = wifi.connect_station()
            if ip:
                print(f"  WiFi reconnected: {ip}")
            else:
                print("  WiFi reconnect fehlgeschlagen, retry in 30s")


_heartbeat = {'sensor': 0, 'server': 0}

async def watchdog_feed(wdt):
    """Feed hardware watchdog only if both sensor_loop and server_loop are alive."""
    while True:
        now = time.ticks_ms()
        sensor_age = time.ticks_diff(now, _heartbeat['sensor'])
        server_age = time.ticks_diff(now, _heartbeat['server'])
        if sensor_age < 30000 and server_age < 30000:
            wdt.feed()
        else:
            print(f"  WDT: NOT feeding (sensor={sensor_age}ms, server={server_age}ms)")
        await asyncio.sleep_ms(10000)


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
    """If update was pending, mark boot as successful and clean up .bak files."""
    import json as _json
    try:
        with open(UPDATE_STATE_FILE) as f:
            state = _json.load(f)
        if state.get('status') == 'pending' or state.get('recovery'):
            # Write state FIRST — if this fails, .bak files remain as safety net
            with open(UPDATE_STATE_FILE, 'w') as f:
                _json.dump({'status': 'ok'}, f)
            if state.get('status') == 'pending':
                print("  Update: Boot OK, Status gesetzt")
            if state.get('recovery'):
                print("  Recovery-Warnung zurueckgesetzt")
            # Clean up .bak files AFTER state is safe
            try:
                for entry in os.listdir('/'):
                    if entry.endswith('.bak'):
                        try:
                            os.remove(entry)
                        except:
                            pass
            except:
                pass
    except (OSError, ValueError):
        pass


async def async_main(wdt):
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
        except Exception:
            pass

    # Hardware
    print("\n[Hardware]")
    joystick = CalibratedJoystick(PIN_VRX, PIN_VRY, PIN_SW)

    # Plausibility: center ~2048 means ADC connected, near 0 or 4095 = floating pin
    joy_ok = 200 < joystick.center_x < 3900 and 200 < joystick.center_y < 3900
    if joy_ok:
        print("  Joystick: OK")
    else:
        print(f"  Joystick: nicht angeschlossen (center={joystick.center_x},{joystick.center_y})")

    puff = None
    puff_ok = False
    try:
        puff = PuffSensor(PIN_PUFF_DATA, PIN_PUFF_CLK)
        # Baseline 0 = no sensor (real sensor has baseline in thousands)
        puff_ok = puff.baseline != 0
        if puff_ok:
            print("  Drucksensor: OK")
        else:
            print("  Drucksensor: nicht angeschlossen (Baseline=0)")
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
    server.hw_status = {
        'joystick': joy_ok,
        'puff': puff_ok,
        'display': tft is not None,
    }
    server.start()

    # Apply pre-asyncio update check result
    if _update_result:
        server._update_info = _update_result

    display_status(tft, ip, mode,
                   (joystick.center_x, joystick.center_y),
                   puff.baseline if puff else 0, 0)

    # Mark boot successful (rollback protection)
    _mark_boot_ok()

    gc.collect()
    gc.threshold(gc.mem_free() // 4 + gc.mem_alloc())
    print(f"\n[Start] RAM frei: {gc.mem_free()} bytes")
    print("Bereit.\n")

    # Launch tasks
    asyncio.create_task(watchdog_feed(wdt))
    asyncio.create_task(sensor_loop(joystick, puff, server))
    asyncio.create_task(server_loop(server, wifi, joystick, puff))
    asyncio.create_task(wifi_monitor(wifi))
    if tft:
        asyncio.create_task(display_loop(tft, ip, mode, joystick, puff, server))

    while True:
        await asyncio.sleep_ms(60000)


_update_result = None  # Shared between main() and async_main()


def _check_and_install_updates_sync():
    """Run OTA check + install synchronously BEFORE asyncio starts.
    SSL and asyncio conflict on ESP32 — SSL handshake fails inside asyncio loop.
    ALL network operations must happen here, before asyncio.run().
    """
    global _update_result
    from wifi_manager import WiFiManager
    wifi = WiFiManager()
    if not wifi.load_credentials():
        return
    ip = wifi.connect_station(timeout_ms=8000)
    if not ip:
        return

    # Check if install was requested (flag set by /api/update/start)
    install_requested = False
    try:
        with open('_do_update'):
            install_requested = True
        os.remove('_do_update')
    except:
        pass

    print("\n[Updates]")
    from updater import check_manifest
    gc.collect()
    print(f"  Update-Check (RAM={gc.mem_free()})")
    try:
        result = check_manifest()
    except Exception as e:
        print(f"  Fehler: {e}")
        result = {'available': [], 'offline': True}
    if not result.get('offline'):
        n = len(result.get('available', []))
        print(f"  {'%d Update(s) verfuegbar' % n if n else 'Alles aktuell'}")

        # Install if requested
        if install_requested and n > 0:
            print("\n[Installation]")
            available = result.get('available', [])
            def on_progress(f, cur, tot):
                print(f"  {cur}/{tot}: {f}")
            gc.collect()
            from updater import run_update_sync
            ok, msg = run_update_sync(available, progress_cb=on_progress)
            print(f"  {msg}")
            if ok:
                result = {'available': [], 'offline': False}
    _update_result = result


def main():
    # WDT before OTA check — protects against hangs during SSL
    wdt = machine.WDT(timeout=30000)
    _check_and_install_updates_sync()
    wdt.feed()
    try:
        asyncio.run(async_main(wdt))
    except KeyboardInterrupt:
        print("\nBeendet.")
    except Exception as e:
        sys.print_exception(e)
        print("\nNeustart in 5s...")
        time.sleep(5)
        machine.reset()


if __name__ == '__main__':
    main()
