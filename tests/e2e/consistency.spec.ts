import { test, expect } from '@playwright/test';
import { gotoESP32, esp32Cooldown } from './helpers';

const GAMES = [
  { name: 'Chess', path: '/www/chess.html' },
  { name: 'Memo', path: '/www/memo.html' },
  { name: 'Solitaire', path: '/www/solitaire.html' },
];

test.describe('Cross-game consistency', () => {
  test.afterEach(async ({ page }) => { await esp32Cooldown(page); });

  test('1. all games have same background color (#1a1a2e)', async ({ page }) => {
    for (const game of GAMES) {
      await gotoESP32(page, game.path);
      const bgColor = await page.evaluate(() => {
        return getComputedStyle(document.body).backgroundColor;
      });
      // #1a1a2e = rgb(26, 26, 46)
      expect(bgColor, `${game.name} background`).toBe('rgb(26, 26, 46)');
      await page.waitForTimeout(1500);
    }
  });

  test('2. all games have favicon', async ({ page }) => {
    for (const game of GAMES) {
      await gotoESP32(page, game.path);
      const favicon = page.locator('link[rel="icon"]');
      await expect(favicon, `${game.name} favicon`).toHaveCount(1);
      const href = await favicon.getAttribute('href');
      expect(href, `${game.name} favicon href`).toContain('FFD700');
      await page.waitForTimeout(1500);
    }
  });

  test('3. all games have P for portal', async ({ page }) => {
    for (const game of GAMES) {
      await gotoESP32(page, game.path);
      const footer = page.locator('#footer');
      await expect(footer, `${game.name} footer`).toBeVisible();
      const pKey = footer.locator('kbd', { hasText: 'P' });
      await expect(pKey.first(), `${game.name} P key`).toBeVisible();
      await page.waitForTimeout(1500);
    }
  });

  test('4. all games have footer with keyboard hints', async ({ page }) => {
    for (const game of GAMES) {
      await gotoESP32(page, game.path);
      const footer = page.locator('#footer');
      await expect(footer, `${game.name} footer`).toBeVisible();

      const arrowHint = footer.locator('kbd', { hasText: /[←↑→↓]/ });
      await expect(arrowHint.first(), `${game.name} arrow keys`).toBeVisible();

      const spaceHint = footer.locator('kbd', { hasText: 'Leertaste' });
      await expect(spaceHint, `${game.name} Leertaste`).toBeVisible();
      await page.waitForTimeout(1500);
    }
  });
});
