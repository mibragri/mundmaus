import { test, expect } from '@playwright/test';
import { gotoGame, esp32Cooldown } from './helpers';

const GAMES = ['solitaire', 'freecell', 'chess', 'memo', 'muehle', 'vier-gewinnt'];

test.describe('Charge system consistency', () => {
  test.afterEach(async ({ page }) => { await esp32Cooldown(page); });

  for (const game of GAMES) {
    test(`${game}: has charge functions`, async ({ page }) => {
      await gotoGame(page, game);
      await page.waitForTimeout(2000);
      const fns = await page.evaluate(`({
        startCharge: typeof startCharge === 'function',
        cancelCharge: typeof cancelCharge === 'function',
        completeCharge: typeof completeCharge === 'function',
        chargeLoop: typeof chargeLoop === 'function',
        renderChargePreview: typeof renderChargePreview === 'function',
        computeTarget: typeof computeTarget === 'function',
      })`);
      expect(fns.startCharge).toBe(true);
      expect(fns.cancelCharge).toBe(true);
      expect(fns.completeCharge).toBe(true);
      expect(fns.chargeLoop).toBe(true);
      expect(fns.renderChargePreview).toBe(true);
      expect(fns.computeTarget).toBe(true);
    });

    test(`${game}: charge state object has correct shape`, async ({ page }) => {
      await gotoGame(page, game);
      await page.waitForTimeout(2000);
      const result = await page.evaluate(`({
        hasActive: 'active' in charge,
        hasDir: 'dir' in charge,
        hasIntensity: 'intensity' in charge,
        hasProgress: 'progress' in charge,
        hasTarget: 'target' in charge,
        hasSource: 'source' in charge,
        hasWsSupported: 'wsSupported' in charge,
        active: charge.active,
      })`);
      expect(result.hasActive).toBe(true);
      expect(result.hasDir).toBe(true);
      expect(result.hasIntensity).toBe(true);
      expect(result.hasProgress).toBe(true);
      expect(result.hasTarget).toBe(true);
      expect(result.hasSource).toBe(true);
      expect(result.hasWsSupported).toBe(true);
      // charge.active may be true if ESP32 hardware sends nav_hold during load
      expect(typeof result.active).toBe('boolean');
    });

    test(`${game}: navCooldown is 1000 default`, async ({ page }) => {
      await gotoGame(page, game);
      await page.waitForTimeout(2000);
      const nc = await page.evaluate('navCooldown');
      expect(nc).toBe(1000);
    });

    test(`${game}: J key toggles sim mode`, async ({ page }) => {
      await gotoGame(page, game);
      await page.waitForTimeout(2000);
      const before = await page.evaluate('kbSimMode');
      await page.keyboard.press('j');
      await page.waitForTimeout(200);
      const after = await page.evaluate('kbSimMode');
      expect(after).toBe(!before);
    });
  }
});
