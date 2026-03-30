import { test, expect } from '@playwright/test';
import { gotoESP32, esp32Cooldown } from './helpers';

test.describe('Solitaire', () => {
  test.afterEach(async ({ page }) => { await esp32Cooldown(page); });

  test.beforeEach(async ({ page }) => {
    await gotoESP32(page, '/www/solitaire.html');
  });

  test('1. page loads, shows card tableau', async ({ page }) => {
    await expect(page).toHaveTitle(/Solit/i);
    const game = page.locator('#game');
    await expect(game).toBeVisible({ timeout: 15_000 });
    const cards = page.locator('.card, [class*="card"]');
    const count = await cards.count();
    expect(count).toBeGreaterThan(0);
  });

  test('2. four action buttons visible (💡, NEW, 🏠, kiosk)', async ({ page }) => {
    const actionCol = page.locator('.action-col');
    await expect(actionCol).toBeVisible({ timeout: 15_000 });

    // 4 action buttons: hints, new game, portal, kiosk
    const actionBtns = actionCol.locator('.action-btn');
    await expect(actionBtns).toHaveCount(4);

    // Home/portal button contains 🏠
    const homeBtn = actionCol.locator('.action-btn', { hasText: '🏠' });
    await expect(homeBtn).toBeVisible();
  });

  test('3. P key navigates to portal', async ({ page }) => {
    await page.waitForTimeout(1000);
    await page.keyboard.press('p');
    await page.waitForURL('**/', { timeout: 15_000 });
    const url = page.url();
    expect(url.endsWith('/') || url.endsWith(':80') || url.endsWith(':80/')).toBeTruthy();
  });

  test('4. U key exists for undo', async ({ page }) => {
    const footer = page.locator('#footer');
    await expect(footer).toBeVisible();
    const undoHint = footer.locator('kbd', { hasText: 'U' });
    await expect(undoHint.first()).toBeVisible();

    // Footer shows ↩ icon for undo (icon-based UI, no German text)
    const footerText = await footer.textContent();
    expect(footerText).toContain('↩');
  });

  test('5. mouse cursor visible (not hidden)', async ({ page }) => {
    const cursor = await page.locator('body').evaluate(
      (el) => getComputedStyle(el).cursor
    );
    expect(cursor).not.toBe('none');
  });

  test('6. nav cursor color is gold (#FFD700), not white', async ({ page }) => {
    const navColor = await page.evaluate(() => {
      return getComputedStyle(document.documentElement).getPropertyValue('--nav-color').trim();
    });
    expect(navColor).toBe('#FFD700');

    const highlight = await page.evaluate(() => {
      return getComputedStyle(document.documentElement).getPropertyValue('--highlight').trim();
    });
    expect(highlight).toBe('#FFD700');
  });

  test('7. footer shows keyboard hints including U', async ({ page }) => {
    const footer = page.locator('#footer');
    await expect(footer).toBeVisible();

    for (const key of ['U', 'N', 'K', 'P']) {
      const kbd = footer.locator('kbd', { hasText: key });
      await expect(kbd.first()).toBeVisible();
    }

    const enterHint = footer.locator('kbd', { hasText: '⏎' });
    await expect(enterHint).toBeVisible();
  });
});
