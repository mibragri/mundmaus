import { test, expect } from '@playwright/test';
import { gotoGame, esp32Cooldown, navPress } from './helpers';

test.describe('Memo Gameplay', () => {
  test.afterEach(async ({ page }) => { await esp32Cooldown(page); });
  test.beforeEach(async ({ page }) => {
    await gotoGame(page, 'memo');
    // Start with difficulty menu; select easiest (4x3 = 6 pairs)
    await page.waitForSelector('#difficulty-menu:not(.hidden)', { timeout: 15_000 });
    // menuCursor defaults to 1 (Mittel), move up for Leicht (0)
    await navPress(page, 'ArrowUp');
    await page.keyboard.press('Space');
    await page.waitForTimeout(300);
  });

  test('loads with correct card count', async ({ page }) => {
    // 4x3 = 12 cards (6 pairs)
    const cardCount = await page.evaluate('state.cards.length');
    expect(cardCount).toBe(12);

    const totalPairs = await page.evaluate('state.totalPairs');
    expect(totalPairs).toBe(6);
  });

  test('flip a card with Space', async ({ page }) => {
    // Ensure we're in playing phase
    const phase = await page.evaluate('state.phase');
    expect(phase).toBe('playing');

    // Flip card at cursor position (0)
    const beforeFlip = await page.evaluate('state.cards[0].flipped');
    expect(beforeFlip).toBe(false);

    await navPress(page, 'Space');

    const afterFlip = await page.evaluate('state.cards[0].flipped');
    expect(afterFlip).toBe(true);

    // first should be set
    const first = await page.evaluate('state.first');
    expect(first).toBe(0);
  });

  test('matching pair stays face up', async ({ page }) => {
    // Set up known state: put matching symbols at positions 0 and 1
    await page.evaluate(`
      const sym = state.cards[0].symbol;
      state.cards[1] = {
        id: state.cards[1].id,
        symbol: sym,
        flipped: false,
        matched: false,
      };
      state.first = null;
      state.second = null;
      state.cursor = 0;
      state.inBtnCol = false;
      state.phase = 'playing';
      updateCursor();
    `);

    // Flip first card (position 0)
    await navPress(page, 'Space');
    expect(await page.evaluate('state.first')).toBe(0);

    // Navigate right to position 1
    await navPress(page, 'ArrowRight');

    // Flip second card
    await navPress(page, 'Space');

    // Wait for match to be processed (400ms delay in game code)
    await page.waitForTimeout(600);

    // Both cards should be matched
    const card0 = await page.evaluate('state.cards[0].matched');
    const card1 = await page.evaluate('state.cards[1].matched');
    expect(card0).toBe(true);
    expect(card1).toBe(true);

    const matched = await page.evaluate('state.matched');
    expect(matched).toBeGreaterThanOrEqual(1);
  });

  test('mismatched pair flips back', async ({ page }) => {
    // Ensure cards 0 and 1 have different symbols
    await page.evaluate(`
      if (state.cards[0].symbol.label === state.cards[1].symbol.label) {
        // Swap card 1 with card 2 (which should be different)
        const tmp = state.cards[1];
        state.cards[1] = state.cards[2];
        state.cards[2] = tmp;
      }
      state.first = null;
      state.second = null;
      state.cursor = 0;
      state.inBtnCol = false;
      state.phase = 'playing';
      updateCursor();
    `);

    // Verify they're different
    const diff = await page.evaluate(
      'state.cards[0].symbol.label !== state.cards[1].symbol.label'
    );
    expect(diff).toBe(true);

    // Flip first card
    await navPress(page, 'Space');

    // Navigate right and flip second card
    await navPress(page, 'ArrowRight');
    await navPress(page, 'Space');

    // Wait for the mismatch animation (400ms visual + 800ms flip back)
    await page.waitForTimeout(1400);

    // Both cards should be flipped back
    const card0 = await page.evaluate('state.cards[0].flipped');
    const card1 = await page.evaluate('state.cards[1].flipped');
    expect(card0).toBe(false);
    expect(card1).toBe(false);
  });

  test('navigation works across grid', async ({ page }) => {
    // 4x3 grid: 4 cols, 3 rows
    const cursor0 = await page.evaluate('state.cursor');
    expect(cursor0).toBe(0);

    // Right moves through columns
    await navPress(page, 'ArrowRight');
    expect(await page.evaluate('state.cursor')).toBe(1);

    await navPress(page, 'ArrowRight');
    expect(await page.evaluate('state.cursor')).toBe(2);

    await navPress(page, 'ArrowRight');
    expect(await page.evaluate('state.cursor')).toBe(3);

    // Down moves to next row
    await navPress(page, 'ArrowDown');
    expect(await page.evaluate('state.cursor')).toBe(7); // row 1, col 3
  });

  test('N key returns to difficulty menu', async ({ page }) => {
    await page.keyboard.press('n');
    await page.waitForTimeout(300);

    const phase = await page.evaluate('state.phase');
    expect(phase).toBe('menu');

    const menuVisible = await page.evaluate(`
      !document.getElementById('difficulty-menu').classList.contains('hidden')
    `);
    expect(menuVisible).toBe(true);
  });

  test('win game shows win screen', async ({ page }) => {
    // Set up: mark all but 2 cards as matched, place matching pair at positions 0 and 1
    await page.evaluate(`
      const sym = state.cards[0].symbol;
      for (let i = 2; i < state.cards.length; i++) {
        state.cards[i].matched = true;
        state.cards[i].flipped = true;
      }
      state.cards[0].flipped = false;
      state.cards[0].matched = false;
      state.cards[1] = {
        id: state.cards[1].id,
        symbol: sym,
        flipped: false,
        matched: false,
      };
      state.matched = state.totalPairs - 1;
      state.first = null;
      state.second = null;
      state.cursor = 0;
      state.inBtnCol = false;
      state.phase = 'playing';
      updateCursor();
    `);

    // Flip both matching cards
    await navPress(page, 'Space');
    await navPress(page, 'ArrowRight');
    await navPress(page, 'Space');

    // Wait for match + win detection
    await page.waitForTimeout(800);

    const phase = await page.evaluate('state.phase');
    expect(phase).toBe('win');

    const winVisible = await page.evaluate(`
      !document.getElementById('win-screen').classList.contains('hidden')
    `);
    expect(winVisible).toBe(true);
  });

  test('footer shows keyboard hints', async ({ page }) => {
    const footer = page.locator('#footer');
    await expect(footer).toBeVisible();
    for (const key of ['N', 'K', 'P']) {
      await expect(footer.locator('kbd', { hasText: key }).first()).toBeVisible();
    }
  });
});
