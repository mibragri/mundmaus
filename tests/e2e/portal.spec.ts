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

  test('2. three game buttons visible: Chess, Memo, Solitaer', async ({ page }) => {
    const gameLinks = page.locator('.g');
    await expect(gameLinks).toHaveCount(3);
    await expect(gameLinks.nth(0)).toContainText('Chess');
    await expect(gameLinks.nth(1)).toContainText('Memo');
    await expect(gameLinks.nth(2)).toContainText('Solitaer');
  });

  test('3. WiFi panel shows connected status (green dot)', async ({ page }) => {
    const wifiDot = page.locator('.wd').first();
    await expect(wifiDot).toBeVisible();
    await expect(wifiDot).toHaveCSS('background-color', 'rgb(76, 175, 80)');
  });

  test('4. software/update section visible', async ({ page }) => {
    // The update section (#upd) becomes visible after WS connects
    const updSection = page.locator('#upd');
    await expect(updSection).toBeVisible({ timeout: 15_000 });
  });

  test('5. footer shows sensor chips (Joystick, Puff - both red)', async ({ page }) => {
    const joystickChip = page.locator('span[title*="Joystick"]');
    await expect(joystickChip).toBeVisible();
    await expect(joystickChip).toContainText('Joystick');

    const puffChip = page.locator('span[title*="Drucksensor"]');
    await expect(puffChip).toBeVisible();
    await expect(puffChip).toContainText('Puff');

    // Both should have red dots (hardware not connected)
    const joystickDot = joystickChip.locator('span').first();
    await expect(joystickDot).toHaveCSS('background-color', 'rgb(212, 42, 42)');
    const puffDot = puffChip.locator('span').first();
    await expect(puffDot).toHaveCSS('background-color', 'rgb(212, 42, 42)');
  });

  test('6. WS chip exists and turns green (Erreichbar)', async ({ page }) => {
    const wsChip = page.locator('#ws-chip');
    await expect(wsChip).toBeVisible();

    // Wait for WebSocket to connect
    const wsDot = page.locator('#ws-dot');
    await expect(wsDot).toHaveCSS('background-color', 'rgb(76, 175, 80)', { timeout: 15_000 });

    const wsText = page.locator('#ws-text');
    await expect(wsText).toContainText('Erreichbar');
  });

  test('7. keyboard nav: arrow keys move highlight between game buttons', async ({ page }) => {
    const gameLinks = page.locator('.g');

    // Helper: check which button has the glow box-shadow (highlight indicator)
    async function getHighlightedIndex(): Promise<number> {
      return page.evaluate(() => {
        const items = document.querySelectorAll('.g');
        for (let i = 0; i < items.length; i++) {
          if (getComputedStyle(items[i]).boxShadow !== 'none') return i;
        }
        return -1;
      });
    }

    // First button starts highlighted (index 0)
    expect(await getHighlightedIndex()).toBe(0);

    // Move to second button
    await page.keyboard.press('ArrowRight');
    expect(await getHighlightedIndex()).toBe(1);

    // Move to third button
    await page.keyboard.press('ArrowRight');
    expect(await getHighlightedIndex()).toBe(2);

    // ArrowLeft goes back
    await page.keyboard.press('ArrowLeft');
    expect(await getHighlightedIndex()).toBe(1);
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

  test('10. footer keyboard hints visible', async ({ page }) => {
    const kbdElements = page.locator('kbd');
    const count = await kbdElements.count();
    expect(count).toBeGreaterThanOrEqual(2);

    // Arrow keys hint
    const arrowHint = page.locator('kbd', { hasText: /[←↑→↓]/ });
    await expect(arrowHint.first()).toBeVisible();

    // Leertaste hint
    const spaceHint = page.locator('kbd', { hasText: 'Leertaste' });
    await expect(spaceHint).toBeVisible();
  });
});
