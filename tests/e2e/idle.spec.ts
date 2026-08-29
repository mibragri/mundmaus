import { test, expect } from '@playwright/test';
import { gotoGame, esp32Cooldown } from './helpers';

// Guard for the idle overlay.
//
// In kiosk mode (the patient's mode) solitaire and freecell arm a 120s idle
// timer that fades in #idle-overlay. doPuff() contains a dismiss branch that
// calls initGame() — which would throw away the running game, in solitaire even
// re-dealing a new random one. Today that branch is unreachable: doPuff() calls
// resetIdleTimer() first, and in kiosk mode that already runs hideIdle(), so the
// 'visible' check below it never matches. Outside kiosk mode the overlay cannot
// appear at all.
//
// The safety therefore rests entirely on the call order inside doPuff(). Moving
// resetIdleTimer() after the check, or hiding the overlay from somewhere else,
// silently turns it into real data loss for a patient who pauses longer than two
// minutes — and he navigates by mouth, so he often does. These tests pin the
// observable behaviour so that reordering fails here instead of at his bedside.
//
// The assertion spies on initGame() rather than on board state: it states the
// hazard directly and stays valid for both games regardless of their layout.

const GAMES = ['solitaire', 'freecell'] as const;

for (const game of GAMES) {
  test.describe(`${game} — idle overlay`, () => {
    test.afterEach(async ({ page }) => { await esp32Cooldown(page); });
    test.beforeEach(async ({ page }) => {
      await gotoGame(page, game);
      await page.waitForSelector('#game', { timeout: 15_000 });
    });

    test('dismissing the idle overlay does not start a new game', async ({ page }) => {
      // Kiosk mode is what arms the idle timer for the patient.
      await page.keyboard.press('k');
      await page.waitForTimeout(100);

      // Count initGame() calls from here on.
      await page.evaluate(`
        window.__initCalls = 0;
        const __origInit = initGame;
        initGame = function (...args) { window.__initCalls++; return __origInit.apply(this, args); };
      `);

      // Fire what the 120s timer would fire, without waiting two minutes.
      await page.evaluate('showIdle()');
      await expect(page.locator('#idle-overlay')).toHaveClass(/visible/);

      // The patient puffs to carry on playing.
      await page.keyboard.press('Space');
      await page.waitForTimeout(100);

      // The overlay must go away...
      await expect(page.locator('#idle-overlay')).not.toHaveClass(/visible/);
      // ...and the running game must survive.
      expect(await page.evaluate('window.__initCalls')).toBe(0);
    });

    test('idle overlay stays dismissed and the game remains playable', async ({ page }) => {
      await page.keyboard.press('k');
      await page.waitForTimeout(100);

      await page.evaluate('showIdle()');
      await page.keyboard.press('Space');
      await page.waitForTimeout(100);
      await expect(page.locator('#idle-overlay')).not.toHaveClass(/visible/);

      // Input still works afterwards — the cursor must not be stranded.
      await page.keyboard.press('ArrowRight');
      await page.waitForTimeout(150);
      const alive = await page.evaluate('typeof navCol !== "undefined" && navCol !== null');
      expect(alive).toBe(true);
    });
  });
}
