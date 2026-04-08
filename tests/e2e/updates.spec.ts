import { test, expect } from '@playwright/test';
import { gotoESP32, esp32Cooldown, fetchJSON } from './api-helpers';

test.describe('OTA Update UI flow', () => {
  test.afterEach(async ({ page }) => { await esp32Cooldown(page); });

  test('1. portal has update button (hidden when no updates)', async ({ page }) => {
    await gotoESP32(page, '/');
    const updBtn = page.locator('#upd-btn');
    await expect(updBtn).toBeAttached();
    // Button exists but is hidden by default (shown by JS when updates available)
  });

  test('2. GET /api/updates returns JSON with available and offline fields', async ({ page }) => {
    const { status, data } = await fetchJSON(page, '/api/updates');
    expect(status).toBe(200);
    const updates = data as Record<string, unknown>;
    expect(updates).toHaveProperty('available');
    expect(Array.isArray(updates.available)).toBe(true);
    expect(typeof updates.offline === 'boolean' || updates.offline === undefined).toBe(true);
  });

  test('3. if no updates and online, update button stays hidden', async ({ page }) => {
    // Check API first (lightweight) before loading the full page
    const { data } = await fetchJSON(page, '/api/updates');
    const updates = data as { offline?: boolean; available: unknown[] };
    if (updates.offline || updates.available.length > 0) {
      // Skip if offline or updates available — button will be visible
      return;
    }
    await gotoESP32(page, '/');
    // Wait for WS to connect and update_status to arrive
    await page.waitForTimeout(5000);
    const updBtn = page.locator('#upd-btn');
    const display = await updBtn.evaluate(el => getComputedStyle(el).display);
    expect(display).toBe('none');
  });

  test('4. "Neustart zum Pruefen" button exists when offline', async ({ page }) => {
    // Check API first to determine if device is offline
    const { data } = await fetchJSON(page, '/api/updates');
    const updates = data as { offline?: boolean; available: unknown[] };
    if (!updates.offline) {
      // Not offline — button won't exist, skip page load
      return;
    }
    await gotoESP32(page, '/');
    const updBtn = page.locator('#upd-btn');
    await expect(updBtn).toBeVisible({ timeout: 15_000 });
    await expect(updBtn).toContainText('Neustart zum Pruefen');
  });

  test('5. GET /api/info returns valid JSON with version, board, mem_free, mode', async ({ page }) => {
    const { status, data } = await fetchJSON(page, '/api/info');
    expect(status).toBe(200);
    const info = data as Record<string, unknown>;
    expect(info).toHaveProperty('version');
    expect(info).toHaveProperty('board');
    expect(info).toHaveProperty('mem_free');
    expect(info).toHaveProperty('mode');
    expect(typeof info.version).toBe('string');
    expect(typeof info.board).toBe('string');
    expect(typeof info.mem_free).toBe('number');
    expect(info.mem_free as number).toBeGreaterThan(0);
  });

  test('6. POST /api/update/start returns error when no updates available', async ({ page }) => {
    const { data: updateStatus } = await fetchJSON(page, '/api/updates');
    const updates = updateStatus as { available: unknown[] };
    if (updates.available && updates.available.length > 0) {
      test.skip();
      return;
    }
    const { data } = await fetchJSON(page, '/api/update/start', { method: 'POST' });
    const result = data as { ok: boolean; error?: string };
    expect(result.ok).toBe(false);
    expect(result.error).toBe('Keine Updates verfuegbar');
  });

  // SKIPPED: triggers ESP32 reboot. Run manually: npx playwright test updates --grep "reboot"
  test.skip('7. POST /api/updates/check returns ok:true (triggers reboot)', async ({ page }) => {
    const { status, data } = await fetchJSON(page, '/api/updates/check', { method: 'POST' });
    expect(status).toBe(200);
    const result = data as { ok: boolean };
    expect(result.ok).toBe(true);
  });
});
