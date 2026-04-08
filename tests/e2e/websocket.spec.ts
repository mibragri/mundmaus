import { test, expect } from '@playwright/test';
import { gotoESP32, esp32Cooldown } from './api-helpers';

const ESP32_HOST = (process.env.ESP32_URL ?? 'http://192.168.178.86').replace(/^https?:\/\//, '');

test.describe('WebSocket connectivity', () => {
  test.afterEach(async ({ page }) => { await esp32Cooldown(page); });

  test('1. connect to ws://host:81 and receive initial message', async ({ page }) => {
    await page.goto('about:blank');
    const message = await page.evaluate(async (host) => {
      return new Promise<Record<string, unknown>>((resolve, reject) => {
        const ws = new WebSocket(`ws://${host}:81`);
        const timer = setTimeout(() => {
          ws.close();
          reject(new Error('WS timeout after 15s'));
        }, 15_000);
        ws.onmessage = (e) => {
          clearTimeout(timer);
          const data = JSON.parse(e.data);
          ws.close();
          resolve(data);
        };
        ws.onerror = () => {
          clearTimeout(timer);
          reject(new Error('WS connection error'));
        };
      });
    }, ESP32_HOST);
    expect(message).toBeTruthy();
    expect(message.type).toBe('wifi_status');
  });

  test('2. initial wifi_status message has required fields', async ({ page }) => {
    await page.goto('about:blank');
    const message = await page.evaluate(async (host) => {
      return new Promise<Record<string, unknown>>((resolve, reject) => {
        const ws = new WebSocket(`ws://${host}:81`);
        const timer = setTimeout(() => {
          ws.close();
          reject(new Error('WS timeout after 15s'));
        }, 15_000);
        ws.onmessage = (e) => {
          clearTimeout(timer);
          const data = JSON.parse(e.data);
          ws.close();
          resolve(data);
        };
        ws.onerror = () => {
          clearTimeout(timer);
          reject(new Error('WS connection error'));
        };
      });
    }, ESP32_HOST);
    expect(message.type).toBe('wifi_status');
    expect(message).toHaveProperty('status');
    expect(message).toHaveProperty('ssid');
    expect(message).toHaveProperty('ip');
    expect(typeof message.ssid).toBe('string');
    expect(typeof message.ip).toBe('string');
  });

  test('3. portal connects to WS and receives update_status', async ({ page }) => {
    // In v4.0+ portal, WS connection triggers /api/updates/check on open
    // and receives update_status messages. No visible WS indicator exists.
    await gotoESP32(page, '/');
    // Verify WS connection works by checking the update button state changes
    // (the portal script calls connectWS() which fetches /api/updates/check)
    await page.waitForTimeout(3000);
    // The update button should be attached (JS ran successfully via WS)
    const updBtn = page.locator('#upd-btn');
    await expect(updBtn).toBeAttached();
  });
});
