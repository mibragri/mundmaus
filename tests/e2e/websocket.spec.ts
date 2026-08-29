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

  test('3. portal opens a WebSocket and receives a frame from the device', async ({ page }) => {
    // This used to assert only that #upd-btn was attached. portal.cpp emits that
    // button unconditionally in the portal HTML, so the test passed with the
    // WebSocket server dead or never sending anything — it verified neither
    // half of its own name. Capture actual frames instead.
    const frames: string[] = [];
    page.on('websocket', ws => {
      ws.on('framereceived', f => {
        if (typeof f.payload === 'string') frames.push(f.payload);
      });
    });

    await gotoESP32(page, '/');

    await expect.poll(() => frames.length, {
      timeout: 15_000,
      message: 'portal opened no WebSocket, or the device sent no frame',
    }).toBeGreaterThan(0);

    // Whatever arrives must be a typed JSON message, not arbitrary bytes.
    const types = frames.map(f => {
      try { return JSON.parse(f).type; } catch { return null; }
    });
    expect(types.some(t => typeof t === 'string' && t.length > 0),
           `no typed JSON frame among: ${frames.slice(0, 3).join(' | ')}`).toBe(true);
  });
});
