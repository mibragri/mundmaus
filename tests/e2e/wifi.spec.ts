import { test, expect } from '@playwright/test';
import { gotoESP32, esp32Cooldown, fetchJSON } from './api-helpers';

test.describe('WiFi panel flow', () => {
  test.afterEach(async ({ page }) => { await esp32Cooldown(page); });

  test('1. WiFi panel visible with SSID and IP', async ({ page }) => {
    await gotoESP32(page, '/');
    // The WiFi panel is a .wf div that is NOT #upd (update section is also .wf)
    const wifiPanel = page.locator('.wf:not(#upd)').first();
    await expect(wifiPanel).toBeVisible();
    const heading = wifiPanel.locator('h2');
    await expect(heading).toBeVisible();
    const headingText = await heading.textContent();
    // Should contain an IP address pattern (e.g. "WLAN: mot - 192.168.178.86")
    expect(headingText).toMatch(/\d+\.\d+\.\d+\.\d+/);
  });

  test('2. GET /api/wifi returns JSON with expected fields', async ({ page }) => {
    const { status, data } = await fetchJSON(page, '/api/wifi');
    expect(status).toBe(200);
    const wifi = data as Record<string, unknown>;
    expect(wifi).toHaveProperty('mode');
    expect(wifi).toHaveProperty('ssid');
    expect(wifi).toHaveProperty('ip');
    expect(wifi).toHaveProperty('connected');
    expect(wifi).toHaveProperty('rssi');
    expect(typeof wifi.mode).toBe('string');
    expect(typeof wifi.ssid).toBe('string');
    expect(typeof wifi.ip).toBe('string');
    expect(typeof wifi.connected).toBe('boolean');
    expect(typeof wifi.rssi).toBe('number');
  });

  test('3. Scan button exists', async ({ page }) => {
    await gotoESP32(page, '/');
    const scanBtn = page.locator('button.wsc');
    await expect(scanBtn).toBeVisible();
    await expect(scanBtn).toContainText('Scan');
  });

  test('4. GET /api/scan returns JSON with networks array', async ({ page }) => {
    const { status, data } = await fetchJSON(page, '/api/scan');
    expect(status).toBe(200);
    const scan = data as Record<string, unknown>;
    expect(scan).toHaveProperty('networks');
    expect(Array.isArray(scan.networks)).toBe(true);
    // Extra cooldown after scan — ESP32 WiFi radio needs recovery time
    await page.waitForTimeout(5000);
  });

  test('5. WiFi signal strength, inputs, and connect button', async ({ page }) => {
    // Combined test to reduce ESP32 page loads
    await gotoESP32(page, '/');

    // WiFi signal strength in heading (contains dBm in station mode)
    const wifiPanel = page.locator('.wf:not(#upd)').first();
    const heading = wifiPanel.locator('h2');
    const text = await heading.textContent();
    if (text && text.includes('WLAN')) {
      expect(text).toContain('dBm');
    }

    // SSID input
    const ssidInput = page.locator('#si');
    await expect(ssidInput).toBeVisible();
    await expect(ssidInput).toHaveAttribute('placeholder', /SSID/);

    // Password input
    const pwInput = page.locator('#pw');
    await expect(pwInput).toBeVisible();
    await expect(pwInput).toHaveAttribute('type', 'password');
    await expect(pwInput).toHaveAttribute('placeholder', /Passwort/);

    // "Connect" button in the WiFi panel
    const verbindenBtn = wifiPanel.locator('button.wb');
    await expect(verbindenBtn).toBeVisible();
    await expect(verbindenBtn).toContainText('Connect');

    // Select is hidden initially (shown only after scan)
    const selectEl = page.locator('#sl');
    await expect(selectEl).toBeHidden();

    // Message div exists
    const msgDiv = page.locator('#wm');
    await expect(msgDiv).toBeAttached();
  });
});
