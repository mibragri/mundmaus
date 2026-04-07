import { test, expect } from '@playwright/test';
import { gotoGame, esp32Cooldown } from './helpers';

const GAMES = ['chess', 'freecell', 'memo', 'muehle', 'solitaire', 'vier-gewinnt'];

test.describe('Cross-game consistency', () => {
  test.afterEach(async ({ page }) => { await esp32Cooldown(page); });

  for (const game of GAMES) {
    test(`${game}: background color is black`, async ({ page }) => {
      await gotoGame(page, game);
      const bg = await page.evaluate(() => getComputedStyle(document.body).backgroundColor);
      // All games use --bg: #000000
      expect(bg).toBe('rgb(0, 0, 0)');
    });

    test(`${game}: has favicon with M letter`, async ({ page }) => {
      await gotoGame(page, game);
      const favicon = page.locator('link[rel="icon"]');
      await expect(favicon).toHaveCount(1);
      const href = await favicon.getAttribute('href');
      // All favicons are SVG with an M letter (color varies: gold or green)
      expect(href).toContain('>M<');
    });

    test(`${game}: has footer with keyboard hints`, async ({ page }) => {
      await gotoGame(page, game);
      const footer = page.locator('#footer');
      await expect(footer).toBeVisible();
      const enterHint = footer.locator('kbd', { hasText: '⏎' });
      await expect(enterHint).toBeVisible();
    });

    test(`${game}: has action buttons`, async ({ page }) => {
      await gotoGame(page, game);
      const btns = page.locator('.action-btn');
      expect(await btns.count()).toBeGreaterThanOrEqual(3);
    });
  }
});
