import { test, expect } from '@playwright/test';
import { gotoESP32, esp32Cooldown } from './helpers';

test.describe('Memo', () => {
  test.afterEach(async ({ page }) => { await esp32Cooldown(page); });

  test.beforeEach(async ({ page }) => {
    await gotoESP32(page, '/www/memo.html');
  });

  test('1. page loads, shows difficulty menu', async ({ page }) => {
    await expect(page).toHaveTitle(/Memo/i);
    // showMenu() is called at page init, removing .hidden from #difficulty-menu
    const menu = page.locator('#difficulty-menu');
    await expect(menu).toBeVisible({ timeout: 15_000 });
    // Should have difficulty options
    const options = page.locator('.diff-option');
    const count = await options.count();
    expect(count).toBeGreaterThanOrEqual(2);
  });

  test('2. can start a game (press Space to select difficulty)', async ({ page }) => {
    // Wait for difficulty menu
    const menu = page.locator('#difficulty-menu');
    await expect(menu).toBeVisible({ timeout: 15_000 });

    // Press Space/Enter to select the current difficulty (action() in menu phase)
    await page.keyboard.press('Space');

    // After selecting, the difficulty menu should be hidden
    await expect(menu).toBeHidden({ timeout: 10_000 });
    // And the board should have card elements
    const cards = page.locator('#board .card');
    await expect(cards.first()).toBeVisible({ timeout: 10_000 });
  });

  test('3. portal button visible after game starts', async ({ page }) => {
    // Start a game via Space
    const menu = page.locator('#difficulty-menu');
    await expect(menu).toBeVisible({ timeout: 15_000 });
    await page.keyboard.press('Space');
    await expect(menu).toBeHidden({ timeout: 10_000 });

    // Portal button in action column
    const portalBtn = page.locator('#btn-back');
    await expect(portalBtn).toBeVisible();
    await expect(portalBtn).toContainText('Portal');
  });

  test('4. P key navigates to portal', async ({ page }) => {
    await page.waitForTimeout(1000);
    await page.keyboard.press('p');
    await page.waitForURL('**/', { timeout: 15_000 });
    const url = page.url();
    expect(url.endsWith('/') || url.endsWith(':80') || url.endsWith(':80/')).toBeTruthy();
  });

  test('5. footer shows keyboard hints', async ({ page }) => {
    const footer = page.locator('#footer');
    await expect(footer).toBeVisible();

    for (const key of ['N', 'K', 'P']) {
      const kbd = footer.locator('kbd', { hasText: key });
      await expect(kbd.first()).toBeVisible();
    }

    const spaceHint = footer.locator('kbd', { hasText: 'Leertaste' });
    await expect(spaceHint).toBeVisible();
  });

  test('6. title says Memo not Memory', async ({ page }) => {
    const title = await page.title();
    expect(title).toContain('Memo');
    expect(title).not.toContain('Memory');
  });
});
