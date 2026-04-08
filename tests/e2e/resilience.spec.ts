import { test, expect } from '@playwright/test';
import { gotoESP32, esp32Cooldown, fetchJSON } from './api-helpers';

test.describe('Error handling & resilience', () => {
  test.afterEach(async ({ page }) => { await esp32Cooldown(page); });

  test('1. portal loads even if WS fails to connect', async ({ page }) => {
    await gotoESP32(page, '/');
    await expect(page).toHaveTitle(/MundMaus/);
    const h1 = page.locator('h1');
    await expect(h1).toBeVisible();
    await expect(h1).toContainText('MundMaus');
    const gameLinks = page.locator('.g');
    await expect(gameLinks.first()).toBeVisible();
    const count = await gameLinks.count();
    expect(count).toBeGreaterThanOrEqual(1);
  });

  test('2. multiple rapid page loads don\'t crash ESP32', async ({ page }) => {
    for (let i = 0; i < 5; i++) {
      await gotoESP32(page, '/');
      await expect(page).toHaveTitle(/MundMaus/);
      await page.waitForTimeout(1500);
    }
    const { status, data } = await fetchJSON(page, '/api/info');
    expect(status).toBe(200);
    const info = data as Record<string, unknown>;
    expect(info.version).toBe('4.1');
  });

  test('3. games load after portal load (navigation flow)', async ({ page }) => {
    await gotoESP32(page, '/');
    await expect(page).toHaveTitle(/MundMaus/);
    await gotoESP32(page, '/www/chess.html');
    await expect(page).toHaveTitle(/Schach|Chess/i);
    await gotoESP32(page, '/www/memo.html');
    await expect(page).toHaveTitle(/Memo/i);
    await gotoESP32(page, '/www/solitaire.html');
    await expect(page).toHaveTitle(/Solit/i);
    await gotoESP32(page, '/');
    await expect(page).toHaveTitle(/MundMaus/);
  });

  test('4. back-to-portal from chess via P key', async ({ page }) => {
    await gotoESP32(page, '/www/chess.html');
    await page.waitForTimeout(1500);
    await page.keyboard.press('p');
    await page.waitForURL('**/', { timeout: 30_000 });
    await expect(page).toHaveTitle(/MundMaus/);
  });

  test('5. back-to-portal from memo via P key', async ({ page }) => {
    await gotoESP32(page, '/www/memo.html');
    await page.waitForTimeout(1500);
    await page.keyboard.press('p');
    await page.waitForURL('**/', { timeout: 30_000 });
    await expect(page).toHaveTitle(/MundMaus/);
  });

  test('6. back-to-portal from solitaire via P key', async ({ page }) => {
    await gotoESP32(page, '/www/solitaire.html');
    await page.waitForTimeout(1500);
    await page.keyboard.press('p');
    await page.waitForURL('**/', { timeout: 30_000 });
    await expect(page).toHaveTitle(/MundMaus/);
  });
});
