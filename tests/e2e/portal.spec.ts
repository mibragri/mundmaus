import { test, expect } from '@playwright/test';
import { gotoESP32, esp32Cooldown } from './helpers';

test.describe('Portal (ESP32 root)', () => {
  test.afterEach(async ({ page }) => { await esp32Cooldown(page); });

  test.beforeEach(async ({ page }) => {
    await gotoESP32(page, '/');
  });

  test('1. portal loads, title contains MundMaus', async ({ page }) => {
    await expect(page).toHaveTitle(/MundMaus/);
    const h1 = page.locator('h1');
    await expect(h1).toBeVisible();
    await expect(h1).toContainText('MundMaus');
  });

  test('2. six game buttons visible (sorted alphabetically)', async ({ page }) => {
    const gameLinks = page.locator('.g');
    await expect(gameLinks).toHaveCount(6);
    // Games are sorted alphabetically by label:
    // Chess, Freecell, Memo, Muehle, Solitaer, Vier gewinnt
    await expect(gameLinks.nth(0)).toContainText('Chess');
    await expect(gameLinks.nth(1)).toContainText('Freecell');
    await expect(gameLinks.nth(2)).toContainText('Memo');
    await expect(gameLinks.nth(3)).toContainText('Muehle');
    await expect(gameLinks.nth(4)).toContainText('Solitaer');
    await expect(gameLinks.nth(5)).toContainText('Vier gewinnt');
  });

  test('3. version number visible in bottom-right', async ({ page }) => {
    const gear = page.locator('.settings-gear');
    await expect(gear).toBeVisible();
    await expect(gear).toContainText(/v\d+\.\d+/);
  });

  test('4. settings gear link visible', async ({ page }) => {
    const settingsLink = page.locator('.settings-gear a[href*="settings"]');
    await expect(settingsLink).toBeVisible();
  });

  test('5. reload button visible', async ({ page }) => {
    // The reload button is a span with ↻ (&#8635;) inside .settings-gear
    const reloadSpan = page.locator('.settings-gear span[onclick*="reload"]');
    await expect(reloadSpan).toBeVisible();
  });

  test('6. update button exists (hidden by default)', async ({ page }) => {
    // The update button is hidden by default (display:none), shown by JS when updates available
    const updBtn = page.locator('#upd-btn');
    await expect(updBtn).toBeAttached();
    // Default state is hidden (no updates available)
    const display = await updBtn.evaluate(el => getComputedStyle(el).display);
    expect(display).toBe('none');
  });

  test('7. all 6 game links are clickable', async ({ page }) => {
    const gameLinks = page.locator('.g');
    const count = await gameLinks.count();
    expect(count).toBe(6);
    for (let i = 0; i < count; i++) {
      const href = await gameLinks.nth(i).getAttribute('href');
      expect(href).toContain('/www/');
      expect(href).toContain('.html');
    }
  });

  test('8. clicking a game button navigates to the game', async ({ page }) => {
    const chessLink = page.locator('.g', { hasText: 'Chess' });
    await chessLink.click();
    await page.waitForURL('**/www/chess.html', { timeout: 30_000 });
    expect(page.url()).toContain('/www/chess.html');
  });

  test('9. favicon exists (golden M in SVG)', async ({ page }) => {
    const favicon = page.locator('link[rel="icon"]');
    await expect(favicon).toHaveCount(1);
    const href = await favicon.getAttribute('href');
    expect(href).toContain('svg');
    expect(href).toContain('FFD700');
    expect(href).toContain('>M<');
  });

  test('10. game links point to /www/*.html paths', async ({ page }) => {
    const gameLinks = page.locator('.g');
    const count = await gameLinks.count();
    for (let i = 0; i < count; i++) {
      const href = await gameLinks.nth(i).getAttribute('href');
      expect(href).toMatch(/^\/www\/\w[\w-]*\.html$/);
    }
  });
});
