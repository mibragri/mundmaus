import { test, expect } from '@playwright/test';
import { gotoGame, esp32Cooldown, LOCAL } from './helpers';

test.describe('Settings page', () => {
  test.afterEach(async ({ page }) => { await esp32Cooldown(page); });

  test.beforeEach(async ({ page }) => {
    await gotoGame(page, 'settings');
    await page.waitForTimeout(1000);
  });

  // === LOADING ===
  test('loads with title', async ({ page }) => {
    await expect(page).toHaveTitle(/Einstellungen|Settings/i);
  });

  test('has back-to-portal link', async ({ page }) => {
    const btn = page.locator('#btn-home');
    await expect(btn).toBeVisible();
    const text = await btn.textContent();
    expect(text).toContain('Spiele');
  });

  // === SLIDERS ===
  test('has joystick sensitivity slider', async ({ page }) => {
    await expect(page.locator('#slider-joy')).toBeVisible();
  });

  test('has puff sensitivity slider', async ({ page }) => {
    await expect(page.locator('#slider-puff')).toBeVisible();
  });

  test('has speed slider', async ({ page }) => {
    await expect(page.locator('#slider-speed')).toBeVisible();
  });

  // === ACTION BUTTONS ===
  test('has save, cancel, calibrate, reset buttons', async ({ page }) => {
    await expect(page.locator('#btn-save')).toBeVisible();
    await expect(page.locator('#btn-cancel')).toBeVisible();
    await expect(page.locator('#btn-calibrate')).toBeVisible();
    await expect(page.locator('#btn-reset')).toBeVisible();
  });

  // === WIFI SECTION ===
  test('has WiFi config card', async ({ page }) => {
    const card = page.locator('#wifi-card');
    await expect(card).toBeVisible();
  });

  test('WiFi card has SSID dropdown', async ({ page }) => {
    const select = page.locator('#wifi-ssid');
    await expect(select).toBeVisible();
  });

  test('WiFi card has password input', async ({ page }) => {
    const input = page.locator('#wifi-pw');
    await expect(input).toBeVisible();
    const type = await input.getAttribute('type');
    expect(type).toBe('password');
  });

  test('WiFi card has scan button', async ({ page }) => {
    const btn = page.locator('#wifi-card button', { hasText: /Scan/i });
    await expect(btn).toBeVisible();
  });

  test('WiFi card has connect button', async ({ page }) => {
    const btn = page.locator('#wifi-card button', { hasText: /Verbinden/i });
    await expect(btn).toBeVisible();
  });

  test('WiFi status shows connection info', async ({ page }) => {
    if (LOCAL) {
      // Local mode: no API, skip status check
      return;
    }
    const status = page.locator('#wifi-status');
    await expect(status).not.toBeEmpty({ timeout: 5000 });
    const text = await status.textContent();
    // Should show either connected, AP mode, or disconnected
    expect(text).toMatch(/Verbunden|Hotspot|Nicht verbunden|Status/);
  });

  // === EXPERT PANEL ===
  test('expert panel toggle exists', async ({ page }) => {
    const toggle = page.locator('#expert-toggle');
    await expect(toggle).toBeVisible();
  });

  test('expert panel has NAV_COOLDOWN_MS field', async ({ page }) => {
    // Open expert panel
    await page.locator('#expert-toggle').click();
    await page.waitForTimeout(300);
    const field = page.locator('#exp-NAV_COOLDOWN_MS');
    await expect(field).toBeVisible();
  });
});
