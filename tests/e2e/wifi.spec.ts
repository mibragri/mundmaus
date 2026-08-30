import { test, expect } from '@playwright/test';
import { fetchJSON, esp32Cooldown } from './api-helpers';

// WiFi provisioning had no dedicated spec — a stub in a stale nested tree
// claimed it had "moved to parent directory", but no such file existed.
//
// These tests cover the READ shape and the ORIGIN GUARDS added to the
// credential-changing paths. They deliberately do NOT send a valid wifi_config
// or hit /api/wifi/reset with a matching origin: either would actually
// re-provision or wipe the device's WiFi and knock it off the network
// mid-suite. Only the negative (foreign-origin → rejected) paths are exercised,
// which change no state.

const ESP32_HOST = (process.env.ESP32_URL ?? 'http://192.168.178.86').replace(/^https?:\/\//, '');

test.describe('WiFi provisioning', () => {
  test.skip(!process.env.ESP32_URL && ESP32_HOST !== '192.168.178.86',
            'needs a reachable device');
  test.afterEach(async ({ page }) => { await esp32Cooldown(page); });

  test('GET /api/wifi returns the expected shape', async ({ page }) => {
    const { status, data } = await fetchJSON(page, '/api/wifi');
    expect(status).toBe(200);
    const d = data as Record<string, unknown>;
    // mode is always present; the rest depends on station vs AP.
    expect(typeof d.mode === 'string' || typeof d.connected === 'boolean').toBe(true);
  });

  test('the WebSocket on :81 opens from the device\'s own page', async ({ page }) => {
    // Positive control for the origin guard: a page served BY the device must
    // still be able to open the socket (this is how the caretaker portal and
    // the games work). Regressing the guard so it rejects the device's own
    // origin would strand every game — this catches that.
    await page.goto(`http://${ESP32_HOST}/`, { waitUntil: 'domcontentloaded' });
    const result = await page.evaluate((host) => new Promise<string>((resolve) => {
      const ws = new WebSocket(`ws://${host}:81/`);
      const t = setTimeout(() => { try { ws.close(); } catch { /* noop */ } resolve('TIMEOUT'); }, 8000);
      ws.onopen = () => { clearTimeout(t); ws.close(); resolve('OPEN'); };
      ws.onerror = () => { clearTimeout(t); resolve('ERROR'); };
    }), ESP32_HOST);
    expect(result).toBe('OPEN');
  });

  test('a foreign-origin POST to /api/wifi/reset is rejected (credentials safe)', async ({ request }) => {
    // Does NOT change state: a foreign Origin must get 403, so credentials are
    // never wiped. A same-origin call is intentionally not made — it would
    // actually reset the device.
    const res = await request.post(`http://${ESP32_HOST}/api/wifi/reset`, {
      headers: { Origin: 'http://attacker.example' },
      failOnStatusCode: false,
    });
    expect(res.status()).toBe(403);
  });
});
