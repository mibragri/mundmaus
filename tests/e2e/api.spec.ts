import { test, expect } from '@playwright/test';
import { esp32Cooldown, fetchJSON, fetchHTML, fetchStatus } from './api-helpers';

test.describe('API endpoints', () => {
  test.afterEach(async ({ page }) => { await esp32Cooldown(page); });

  test('1. GET / returns HTML with MundMaus title', async ({ page }) => {
    const { status, html } = await fetchHTML(page, '/');
    expect(status).toBe(200);
    expect(html).toContain('<title>MundMaus</title>');
  });

  test('2. GET /api/info — valid JSON, version=4.1', async ({ page }) => {
    const { status, data } = await fetchJSON(page, '/api/info');
    expect(status).toBe(200);
    const info = data as Record<string, unknown>;
    expect(info.version).toBe('4.1');
    expect(info.board).toBeTruthy();
    expect(typeof info.mem_free).toBe('number');
    expect(info.mode).toBeTruthy();
    expect(info.ip).toBeTruthy();
  });

  test('3. GET /api/wifi — valid JSON with expected fields', async ({ page }) => {
    const { status, data } = await fetchJSON(page, '/api/wifi');
    expect(status).toBe(200);
    const wifi = data as Record<string, unknown>;
    expect(wifi).toHaveProperty('mode');
    expect(wifi).toHaveProperty('ssid');
    expect(wifi).toHaveProperty('ip');
    expect(wifi).toHaveProperty('connected');
    expect(wifi).toHaveProperty('rssi');
  });

  test('4. GET /api/scan — returns scan_started (async scan)', async ({ page }) => {
    const { status, data } = await fetchJSON(page, '/api/scan');
    expect(status).toBe(200);
    const scan = data as Record<string, unknown>;
    expect(scan.ok).toBe(true);
    expect(scan.status).toBe('scan_started');
  });

  test('5. GET /api/updates — valid JSON', async ({ page }) => {
    const { status, data } = await fetchJSON(page, '/api/updates');
    expect(status).toBe(200);
    const updates = data as Record<string, unknown>;
    expect(updates).toHaveProperty('available');
    expect(Array.isArray(updates.available)).toBe(true);
  });

  test('6. GET /www/chess.html — loads, contains Schach', async ({ page }) => {
    const { status, html } = await fetchHTML(page, '/www/chess.html');
    expect(status).toBe(200);
    expect(html).toContain('Schach');
  });

  test('7. GET /www/memo.html — loads, contains Memo', async ({ page }) => {
    const { status, html } = await fetchHTML(page, '/www/memo.html');
    expect(status).toBe(200);
    expect(html).toContain('Memo');
  });

  test('8. GET /www/solitaire.html — loads, contains Solitaer', async ({ page }) => {
    const { status, html } = await fetchHTML(page, '/www/solitaire.html');
    expect(status).toBe(200);
    expect(html.includes('Solitaer') || html.includes('Solit\u00e4r')).toBe(true);
  });

  test('9. GET /favicon.ico — returns 204', async ({ page }) => {
    const status = await fetchStatus(page, '/favicon.ico');
    expect(status).toBe(204);
  });

  test('10. GET /nonexistent — returns 404 or setup page', async ({ page }) => {
    const { status, html } = await fetchHTML(page, '/nonexistent');
    expect([200, 404]).toContain(status);
    if (status === 404) {
      expect(html).toContain('404');
    } else {
      expect(html).toContain('MundMaus');
    }
  });
});
