import { test, expect } from '@playwright/test';
import { gotoGame, esp32Cooldown, navPress } from './helpers';

test.describe('Muehle Gameplay', () => {
  test.afterEach(async ({ page }) => { await esp32Cooldown(page); });
  test.beforeEach(async ({ page }) => {
    await gotoGame(page, 'muehle');
    // Muehle starts with a menu; select easiest difficulty
    await page.waitForSelector('#main-menu:not(.hidden)', { timeout: 15_000 });
    await page.keyboard.press('Space'); // select first option (easiest)
    await page.waitForTimeout(300);
  });

  test('loads with empty board', async ({ page }) => {
    const phase = await page.evaluate('ui.phase');
    expect(phase).toBe('playing');

    const gamePhase = await page.evaluate('game.phase');
    expect(gamePhase).toBe('setz'); // placement phase

    // Board should be all null (empty)
    const emptyCount = await page.evaluate(`
      game.board.filter(p => p === null).length
    `);
    expect(emptyCount).toBe(24);

    // Each player should have 9 pieces to place
    const toPlaceW = await page.evaluate("game.toPlace['W']");
    expect(toPlaceW).toBe(9);
  });

  test('place piece on intersection', async ({ page }) => {
    // In setz phase, pressing Space on empty intersection places a piece
    const cursorPos = await page.evaluate('ui.cursor');
    expect(typeof cursorPos).toBe('number');

    // Verify position is empty
    const before = await page.evaluate('game.board[ui.cursor]');
    expect(before).toBeNull();

    // Place piece
    await navPress(page, 'Space');

    // If AI didn't trigger a removal, the piece should be placed
    // Wait briefly for any AI response
    await page.waitForTimeout(500);

    // Check that at least one white piece is on the board
    const whiteCount = await page.evaluate(`
      game.board.filter(p => p === 'W').length
    `);
    expect(whiteCount).toBeGreaterThanOrEqual(1);
  });

  test('navigation works across board positions', async ({ page }) => {
    const startPos = await page.evaluate('ui.cursor');

    // Navigate in each direction and verify cursor changes
    await navPress(page, 'ArrowRight');
    const pos1 = await page.evaluate('ui.cursor');
    expect(pos1).not.toBe(startPos);

    await navPress(page, 'ArrowDown');
    const pos2 = await page.evaluate('ui.cursor');
    expect(pos2).not.toBe(pos1);

    await navPress(page, 'ArrowLeft');
    const pos3 = await page.evaluate('ui.cursor');
    expect(pos3).not.toBe(pos2);

    await navPress(page, 'ArrowUp');
    const pos4 = await page.evaluate('ui.cursor');
    expect(pos4).not.toBe(pos3);
  });

  test('can enter button column and return', async ({ page }) => {
    // Navigate right until we enter the button column
    for (let i = 0; i < 20; i++) {
      await navPress(page, 'ArrowRight');
      const inBtn = await page.evaluate('ui.inBtnCol');
      if (inBtn) break;
    }

    const inBtnCol = await page.evaluate('ui.inBtnCol');
    expect(inBtnCol).toBe(true);

    // Navigate left to return to board
    await navPress(page, 'ArrowLeft');
    const backOnBoard = await page.evaluate('ui.inBtnCol');
    expect(backOnBoard).toBe(false);
  });

  test('undo reverses placement', async ({ page }) => {
    // Place a piece
    await navPress(page, 'Space');
    await page.waitForTimeout(500); // wait for AI

    // Wait until it's player's turn again
    await page.waitForFunction(
      `game.turn === 'W' && !aiInProgress`,
      { timeout: 5000 }
    );

    const histLen = await page.evaluate('game.history.length');
    expect(histLen).toBeGreaterThan(0);

    // Undo
    await page.keyboard.press('u');
    await page.waitForTimeout(200);

    const histAfter = await page.evaluate('game.history.length');
    expect(histAfter).toBeLessThan(histLen);
  });

  test('N key returns to menu', async ({ page }) => {
    await page.keyboard.press('n');
    await page.waitForTimeout(300);

    const phase = await page.evaluate('ui.phase');
    expect(phase).toBe('menu');
  });

  test('multiple placements alternate turns', async ({ page }) => {
    // Place first piece (white)
    const pos1 = await page.evaluate('ui.cursor');
    await navPress(page, 'Space');

    // Wait for AI to respond
    await page.waitForFunction(
      `game.turn === 'W' && !aiInProgress`,
      { timeout: 5000 }
    );

    // Both players should have placed a piece
    const wCount = await page.evaluate("game.board.filter(p => p === 'W').length");
    const bCount = await page.evaluate("game.board.filter(p => p === 'B').length");
    expect(wCount).toBe(1);
    expect(bCount).toBe(1);
  });

  test('footer has keyboard hints', async ({ page }) => {
    const footer = page.locator('#footer');
    await expect(footer).toBeVisible();
    for (const key of ['N', 'U', 'K']) {
      await expect(footer.locator('kbd', { hasText: key }).first()).toBeVisible();
    }
  });
});
