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
    AP_PASS,
    AP_SSID,
    BOARD,
    GC_INTERVAL,
    PIN_PUFF_CLK,
    PIN_PUFF_DATA,
    PIN_SW,
    PIN_VRX,
    PIN_VRY,
    PUFF_SEND_INTERVAL_MS,
    RECAL_IDLE_MS,
    SENSOR_POLL_MS,
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


async def _run_update_async(server):
    """Run update in background, yielding to event loop between files."""
    try:
        if not server._update_info:
            return
        from updater import run_update
        available = server._update_info.get('available', [])
        def on_progress(f, cur, tot):
            server.ws_send_all({'type': 'update_progress', 'file': f, 'current': cur, 'total': tot})
        def on_error(f, err):
            server.ws_send_all({'type': 'update_error', 'file': f, 'error': err})
        ok, msg = await run_update(available, progress_cb=on_progress, error_cb=on_error)
        server.ws_send_all({'type': 'update_complete',
                            'firmware_updated': any(u.get('firmware') for u in available),
                            'message': msg, 'ok': ok})
    except Exception as e:
        print(f"  Update-Fehler: {e}")
        server.ws_send_all({'type': 'update_complete', 'ok': False,
                            'message': f'Update-Fehler: {e}', 'firmware_updated': False})
    finally:
        server._updating = False
        server._update_info = None
        server._update_task_running = False


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

        if server._updating and not getattr(server, '_update_task_running', False):
            server._update_task_running = True
            asyncio.create_task(_run_update_async(server))

        if server._recheck_updates:
            server._recheck_updates = False
            asyncio.create_task(update_check(server, wifi))

        loop_count += 1
        if loop_count % GC_INTERVAL == 0:
            gc.collect()
            loop_count = 0

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
    """If update was pending, mark boot as successful and clean up .bak files."""
    import json as _json
    try:
        with open(UPDATE_STATE_FILE) as f:
            state = _json.load(f)
        needs_write = False
        if state.get('status') == 'pending':
            # Clean up .bak files from successful update
            for entry in os.listdir('/'):
                if entry.endswith('.bak'):
                    try:
                        os.remove(entry)
                    except:
                        pass
            print("  Update: Boot OK, Status gesetzt")
            needs_write = True
        if state.get('recovery'):
            print("  Recovery-Warnung zurueckgesetzt")
            needs_write = True
        if needs_write:
            with open(UPDATE_STATE_FILE, 'w') as f:
                _json.dump({'status': 'ok'}, f)
    except (OSError, ValueError):
        pass


async def update_check(server, wifi, initial=False):
    """Check for updates in background. Non-blocking."""
    if wifi.mode != 'station':
        server._update_info = {'available': [], 'offline': True}
        server.ws_send_all({'type': 'update_status', 'available': [], 'offline': True})
        return
    if initial:
        await asyncio.sleep_ms(2000)  # Let server settle on first boot
    from updater import check_manifest
    def on_result(result):
        server._update_info = result
        msg = {'type': 'update_status'}
        msg.update(result)
        server.ws_send_all(msg)
    check_manifest(notify_cb=on_result)


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
        except Exception:
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

    # Check for OTA updates in background
    asyncio.create_task(update_check(server, wifi, initial=True))

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
