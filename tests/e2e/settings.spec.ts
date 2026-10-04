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

// Finding A2 of the comment review (04.10.2026): when GET /api/settings failed, the page filled in the
// factory defaults as if the device ran them. Every slider step previewed from that invented base, and
// Cancel wrote all seven factory values onto the device. The device is modelled with page.route.
test.describe('Settings page — values come from the device', () => {
  test.skip(!LOCAL, 'models the device with page.route; on a real one the slider would preview');

  // A personalised profile; the factory defaults are 150/450/400/1000/400/75000/20.
  const DEVICE = { DEADZONE: 220, NAV_THRESHOLD: 700, NAV_REPEAT_MS: 300, NAV_COOLDOWN_MS: 1500,
                   PUFF_COOLDOWN_MS: 400, PUFF_RAW_THRESHOLD: 40000, SENSOR_POLL_MS: 20 };
  const FACTORY = { DEADZONE: 150, NAV_THRESHOLD: 450, NAV_REPEAT_MS: 400, NAV_COOLDOWN_MS: 1000,
                    PUFF_COOLDOWN_MS: 400, PUFF_RAW_THRESHOLD: 75000, SENSOR_POLL_MS: 20 };
  const answer = { current: DEVICE, saved: DEVICE, defaults: FACTORY };

  test('while the device does not answer: no numbers, controls locked, then its own values', async ({ page }) => {
    let deviceUp = false;
    await page.route('**/api/settings', route =>
      deviceUp ? route.fulfill({ json: answer }) : route.abort('connectionrefused'));
    await gotoGame(page, 'settings');

    await expect(page.locator('#exp-PUFF_RAW_THRESHOLD')).toHaveValue('');
    await expect(page.locator('#slider-puff')).toBeDisabled();
    await expect(page.locator('#exp-PUFF_RAW_THRESHOLD')).toBeDisabled();
    await expect(page.locator('#btn-save')).toBeDisabled();
    await expect(page.locator('#settings-loading')).toBeVisible();

    deviceUp = true;  // the page asks again on its own
    await expect(page.locator('#exp-PUFF_RAW_THRESHOLD')).toHaveValue('40000', { timeout: 10_000 });
    await expect(page.locator('#slider-puff')).toBeEnabled();
    await expect(page.locator('#settings-loading')).toBeHidden();
  });

  test('Cancel takes back only what this visit changed, to the value it loaded', async ({ page }) => {
    const posted: unknown[] = [];
    await page.route('**/api/settings', route => route.fulfill({ json: answer }));
    await page.route('**/api/settings/preview', route => {
      posted.push(route.request().postDataJSON());
      return route.fulfill({ json: { ok: true, applied: 1 } });
    });
    await gotoGame(page, 'settings');
    await expect(page.locator('#exp-PUFF_RAW_THRESHOLD')).toHaveValue('40000');

    await page.locator('#slider-puff').press('ArrowLeft');  // the one change of this visit
    await page.locator('#btn-cancel').click();
    await page.waitForURL(url => url.pathname === '/');

    expect(posted).toEqual([{ values: { PUFF_RAW_THRESHOLD: 40000 } }]);
  });

  // The device raises NAV_THRESHOLD itself when DEADZONE comes within 50 of it, and it applies the
  // keys in the order they arrive, so both go back, DEADZONE first.
  test('Cancel after a DEADZONE edit takes back both coupled thresholds, DEADZONE first', async ({ page }) => {
    const posted: { values: Record<string, number> }[] = [];
    await page.route('**/api/settings', route => route.fulfill({ json: answer }));
    await page.route('**/api/settings/preview', route => {
      posted.push(route.request().postDataJSON());
      return route.fulfill({ json: { ok: true, applied: 2 } });
    });
    await gotoGame(page, 'settings');
    await expect(page.locator('#exp-DEADZONE')).toHaveValue('220');

    await page.locator('#expert-toggle').click();
    await page.locator('#exp-DEADZONE').fill('680');
    await page.locator('#btn-cancel').click();
    await page.waitForURL(url => url.pathname === '/');

    expect(posted).toHaveLength(1);
    expect(Object.entries(posted[0].values)).toEqual([['DEADZONE', 220], ['NAV_THRESHOLD', 700]]);
  });

  test('after Save, Cancel writes nothing back', async ({ page }) => {
    const posted: unknown[] = [];
    await page.route('**/api/settings', route => route.fulfill({ json: answer }));
    await page.route('**/api/settings/preview', route => {
      posted.push(route.request().postDataJSON());
      return route.fulfill({ json: { ok: true, applied: 1 } });
    });
    await page.routeWebSocket(/:81\/?$/, ws => {
      ws.onMessage(raw => {
        if (JSON.parse(String(raw)).type === 'config_save') ws.send(JSON.stringify({ type: 'config_saved', ok: true }));
      });
    });
    await gotoGame(page, 'settings');
    await expect(page.locator('#exp-PUFF_RAW_THRESHOLD')).toHaveValue('40000');
    await expect(page.locator('#ws-status')).toHaveClass(/connected/);

    await page.locator('#slider-puff').press('ArrowLeft');
    await page.locator('#btn-save').click();
    await expect(page.locator('#toast')).toContainText('Gespeichert');
    await page.locator('#btn-cancel').click();
    await page.waitForURL(url => url.pathname === '/');

    expect(posted).toEqual([]);
  });
});
