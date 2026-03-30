import { test, expect } from '@playwright/test';
import { gotoESP32, esp32Cooldown } from './helpers';

test.describe('Chess', () => {
  test.afterEach(async ({ page }) => { await esp32Cooldown(page); });

  test.beforeEach(async ({ page }) => {
    await gotoESP32(page, '/www/chess.html');
    // Dismiss the difficulty menu that shows on load (keyboard-only, no click handlers on .diff-opt)
    const diffMenu = page.locator('#diff-menu');
    await expect(diffMenu).toBeVisible({ timeout: 10_000 });
    await page.keyboard.press('Enter');
    // Wait for menu to hide and game to start
    await expect(diffMenu).toBeHidden({ timeout: 5_000 });
  });

  test('1. page loads, has chess board', async ({ page }) => {
    await expect(page).toHaveTitle(/Schach|Chess/i);
    const board = page.locator('#board, #chess-board, canvas, .board');
    await expect(board.first()).toBeVisible({ timeout: 15_000 });
  });

  test('2. portal button visible in action column', async ({ page }) => {
    const portalBtn = page.locator('#btn-back');
    await expect(portalBtn).toBeVisible();
    await expect(portalBtn).toContainText('Portal');
  });

  test('3. P key navigates to portal', async ({ page }) => {
    await page.waitForTimeout(1000);
    await page.keyboard.press('p');
    await page.waitForURL('**/', { timeout: 15_000 });
    const url = page.url();
    expect(url.endsWith('/') || url.endsWith(':80') || url.endsWith(':80/')).toBeTruthy();
  });

  test('4. ESC navigates to portal (when no piece selected)', async ({ page }) => {
    await page.waitForTimeout(1000);
    await page.keyboard.press('Escape');
    await page.waitForURL('**/', { timeout: 15_000 });
    const url = page.url();
    expect(url.endsWith('/') || url.endsWith(':80') || url.endsWith(':80/')).toBeTruthy();
  });

  test('5. keyboard shortcuts footer visible (N, K, P, U)', async ({ page }) => {
    const footer = page.locator('#footer');
    await expect(footer).toBeVisible();

    for (const key of ['N', 'U', 'K', 'P']) {
      const kbd = footer.locator('kbd', { hasText: key });
      await expect(kbd.first()).toBeVisible();
    }
  });

  test('6. favicon present', async ({ page }) => {
    const favicon = page.locator('link[rel="icon"]');
    await expect(favicon).toHaveCount(1);
    const href = await favicon.getAttribute('href');
    expect(href).toContain('svg');
    expect(href).toContain('FFD700');
  });
});
