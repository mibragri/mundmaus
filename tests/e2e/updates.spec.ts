import { test, expect } from '@playwright/test';
import { gotoESP32, esp32Cooldown, fetchJSON } from './api-helpers';

test.describe('OTA Update UI flow', () => {
  test.afterEach(async ({ page }) => { await esp32Cooldown(page); });

  test('1. portal shows update status section (id=upd)', async ({ page }) => {
    await gotoESP32(page, '/');
    const updSection = page.locator('#upd');
    await expect(updSection).toBeAttached();
    await expect(updSection).toBeVisible({ timeout: 15_000 });
  });

  test('2. GET /api/updates returns JSON with available and offline fields', async ({ page }) => {
    const { status, data } = await fetchJSON(page, '/api/updates');
    expect(status).toBe(200);
    const updates = data as Record<string, unknown>;
    expect(updates).toHaveProperty('available');
    expect(Array.isArray(updates.available)).toBe(true);
    expect(typeof updates.offline === 'boolean' || updates.offline === undefined).toBe(true);
  });

  test('3. if no updates and online, shows "✓ Up to date"', async ({ page }) => {
    // Check API first (lightweight) before loading the full page
    const { data } = await fetchJSON(page, '/api/updates');
    const updates = data as { offline?: boolean; available: unknown[] };
    if (updates.offline || updates.available.length > 0) {
      // Skip page check if offline or updates available — text will differ
      return;
    }
    await gotoESP32(page, '/');
    const updInfo = page.locator('#upd-info');
    await expect(updInfo).toBeVisible({ timeout: 15_000 });
    await expect(updInfo).toContainText('✓ Up to date', { timeout: 15_000 });
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
    expect(result.error).toBe('Keine Updates');
  });

  // SKIPPED: triggers ESP32 reboot. Run manually: npx playwright test updates --grep "reboot"
  test.skip('7. POST /api/updates/check returns ok:true (triggers reboot)', async ({ page }) => {
    const { status, data } = await fetchJSON(page, '/api/updates/check', { method: 'POST' });
    expect(status).toBe(200);
    const result = data as { ok: boolean };
    expect(result.ok).toBe(true);
  });
});
