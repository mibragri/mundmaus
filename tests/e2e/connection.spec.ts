import { test, expect, type Page } from '@playwright/test';
import { LOCAL, gamePath } from './helpers';

// Finding A1 of the comment review (04.10.2026): the WebSocket logic, seven copies of it, and conn-guard.js
// on top. The device is modelled with page.route and routeWebSocket, time with page.clock, so a two-minute
// outage takes a few seconds.

const PAGES = ['chess', 'freecell', 'memo', 'muehle', 'solitaire', 'vier-gewinnt', 'settings'];

const VALUES = { DEADZONE: 150, NAV_THRESHOLD: 450, NAV_REPEAT_MS: 400, NAV_COOLDOWN_MS: 1000,
                 PUFF_COOLDOWN_MS: 400, PUFF_RAW_THRESHOLD: 75000, SENSOR_POLL_MS: 20 };

type Device = {
  up: boolean;         // false: HTTP fails, open sockets go silent, new ones are refused (router off)
  silent: boolean;     // true: HTTP answers and sockets open, but nothing comes over them (21.09.2026)
  hangClose: boolean;  // true: a close from the page is never answered, so the socket hangs in CLOSING
};

async function mockDevice(page: Page, dev: Device) {
  await page.addInitScript(() => { (window as any).__mmConnGuardConfig = { force: true }; });
  await page.route('**/api/info', route =>
    dev.up ? route.fulfill({ json: { version: 'test' } }) : route.abort('connectionrefused'));
  await page.route('**/api/settings', route =>
    dev.up ? route.fulfill({ json: { current: VALUES, saved: VALUES, defaults: VALUES } }) : route.abort('connectionrefused'));
  await page.routeWebSocket(/:81\/?$/, ws => {
    if (!dev.up) { ws.close(); return; }
    if (dev.hangClose) ws.onClose(() => { /* never answers the closing handshake */ });
    if (!dev.silent) ws.send(JSON.stringify({ type: 'wifi_status', connected: true }));
    ws.onMessage(() => { if (dev.up && !dev.silent) ws.send('{"type":"hb"}'); });  // the firmware answers hb
  });
}

// Moves the page's clock in half-second steps so every timer fires and the mocked device can answer between them.
async function advance(page: Page, ms: number) {
  for (let t = 0; t < ms; t += 500) {
    await page.clock.runFor(500);
    await page.waitForTimeout(15);
  }
}

async function open(page: Page, name: string, dev: Device): Promise<{ loads: () => number }> {
  await mockDevice(page, dev);
  let loads = 0;
  page.on('load', () => { loads++; });
  await page.clock.install();
  await page.goto(gamePath(name));
  await page.clock.pauseAt(Date.now() + 1000);
  await advance(page, 3000);
  return { loads: () => loads };
}

const dot = (page: Page) => page.locator('#ws-status.connected');

for (const name of PAGES) {
  test.describe(`${name}: connection to the device`, () => {
    test.skip(!LOCAL, 'models the device with page.route and routeWebSocket');

    test('after a 40 s outage the page reconnects within 10 s, without a reload', async ({ page }) => {
      const dev = { up: true, silent: false, hangClose: false };
      const { loads } = await open(page, name, dev);
      await expect(dot(page)).toHaveCount(1);

      dev.up = false;
      await advance(page, 40_000);  // its own retries fall at about 13, 19, 31 and 55 s
      dev.up = true;
      await advance(page, 10_000);  // conn-guard polls every 5 s, the backoff by then is up to 30 s

      expect(loads(), 'the page was reloaded, and with it the running game').toBe(1);
      await expect(dot(page)).toHaveCount(1);
    });

    test('the status dot turns red when the device goes silent, even while the socket hangs in CLOSING', async ({ page }) => {
      const dev = { up: true, silent: false, hangClose: true };
      await open(page, name, dev);
      await expect(dot(page)).toHaveCount(1);

      dev.silent = true;
      await advance(page, 11_000);  // a socket gets 10 s without a message

      await expect(dot(page)).toHaveCount(0);
    });

    test('sockets that open but never receive anything get the page reloaded', async ({ page }) => {
      const dev = { up: true, silent: false, hangClose: false };
      const { loads } = await open(page, name, dev);
      await expect(dot(page)).toHaveCount(1);

      dev.silent = true;
      await advance(page, 120_000);

      expect(loads(), 'the page was not reloaded').toBeGreaterThan(1);
    });
  });
}

test('a page whose device-link.js did not arrive reloads until it is there', async ({ page }) => {
  test.skip(!LOCAL, 'models the device with page.route and routeWebSocket');
  await page.route('**/device-link.js', route => route.fulfill({ status: 404, body: '' }));
  const { loads } = await open(page, 'chess', { up: true, silent: false, hangClose: false });
  await expect(dot(page)).toHaveCount(0);

  await advance(page, 31_000);

  expect(loads()).toBeGreaterThan(1);
});
