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

  test('3. WS chip in portal turns green after connection (id=ws-dot)', async ({ page }) => {
    await gotoESP32(page, '/');
    const wsDot = page.locator('#ws-dot');
    await expect(wsDot).toHaveCSS('background-color', 'rgb(76, 175, 80)', { timeout: 15_000 });
  });

  test('4. "✓" text appears (id=ws-text)', async ({ page }) => {
    await gotoESP32(page, '/');
    const wsText = page.locator('#ws-text');
    await expect(wsText).toContainText('✓', { timeout: 15_000 });
  });

  test('5. WS chip border turns green after connection', async ({ page }) => {
    await gotoESP32(page, '/');
    const wsChip = page.locator('#ws-chip');
    await expect(wsChip).toBeVisible();
    await expect(wsChip).toHaveCSS('border-color', 'rgb(76, 175, 80)', { timeout: 15_000 });
  });
});
