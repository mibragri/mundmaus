import { test, expect } from '@playwright/test';
import { gotoGame, esp32Cooldown, navPress } from './helpers';

test.describe('Chess Gameplay', () => {
  test.afterEach(async ({ page }) => { await esp32Cooldown(page); });
  test.beforeEach(async ({ page }) => {
    await gotoGame(page, 'chess');
    // Chess starts with a difficulty menu; select easiest (random) and start
    await page.waitForSelector('#diff-menu', { timeout: 15_000 });
    await page.keyboard.press('Space'); // select difficulty
    // Wait for game to enter playing phase (ESP32 may be slow)
    await page.waitForFunction(`typeof ui !== 'undefined' && ui.phase === 'playing'`, { timeout: 10_000 });
  });

  test('loads with 32 pieces', async ({ page }) => {
    const pieceCount = await page.evaluate(`
      let count = 0;
      for (let r = 0; r < 8; r++)
        for (let c = 0; c < 8; c++)
          if (game.board[r][c]) count++;
      count;
    `);
    expect(pieceCount).toBe(32);
  });

  test('can select and move a pawn', async ({ page }) => {
    // cursor starts at [6, 4] — that's e2 pawn (white)
    // Verify there's a white pawn at cursor position
    const pawn = await page.evaluate(`
      const p = game.board[6][4];
      p ? {color: p.color, type: p.type} : null;
    `);
    expect(pawn).toEqual({ color: 'w', type: 'p' });

    // Select the pawn
    await navPress(page, 'Space');
    const selected = await page.evaluate('ui.selected');
    expect(selected).toEqual([6, 4]);

    // Navigate up twice to e4 (row 4)
    await navPress(page, 'ArrowUp');
    await navPress(page, 'ArrowUp');

    // Place the pawn
    await navPress(page, 'Space');

    // Verify pawn moved to e4 (row 4, col 4)
    const movedPiece = await page.evaluate(`
      const p = game.board[4][4];
      p ? {color: p.color, type: p.type} : null;
    `);
    expect(movedPiece).toEqual({ color: 'w', type: 'p' });

    // Original square should be empty
    const origSquare = await page.evaluate('game.board[6][4]');
    expect(origSquare).toBeNull();
  });

  test('AI responds after player move', async ({ page }) => {
    // Move e2-e4 (cursor is at [6,4])
    await navPress(page, 'Space'); // select e2
    await navPress(page, 'ArrowUp');
    await navPress(page, 'ArrowUp');
    await navPress(page, 'Space'); // place at e4

    // Wait for AI to respond (300ms delay for easy + thinking time)
    await page.waitForFunction(`game.turn === 'w'`, { timeout: 15_000 });

    // Verify a black piece moved: move count should be 2 (1 white + 1 black)
    const histLen = await page.evaluate('game.history.length');
    expect(histLen).toBe(2);
  });

  test('undo reverses player + AI move', async ({ page }) => {
    // Move e2-e4
    await navPress(page, 'Space');
    await navPress(page, 'ArrowUp');
    await navPress(page, 'ArrowUp');
    await navPress(page, 'Space');

    // Wait for AI
    await page.waitForFunction(`game.turn === 'w'`, { timeout: 15_000 });

    const histAfterMove = await page.evaluate('game.history.length');
    expect(histAfterMove).toBe(2);

    // Undo (undoes both player + AI move)
    await page.keyboard.press('u');
    await page.waitForTimeout(200);

    // History should be empty again
    const histAfterUndo = await page.evaluate('game.history.length');
    expect(histAfterUndo).toBe(0);

    // Board should be back to initial: e2 pawn present, e4 empty
    const e2 = await page.evaluate(`
      const p = game.board[6][4];
      p ? p.type : null;
    `);
    expect(e2).toBe('p');
    const e4 = await page.evaluate('game.board[4][4]');
    expect(e4).toBeNull();
  });

  test('navigation covers the full board', async ({ page }) => {
    // Start at [6,4], navigate to corner [0,0]
    // Up 6 times, left 4 times
    for (let i = 0; i < 6; i++) await navPress(page, 'ArrowUp');
    for (let i = 0; i < 4; i++) await navPress(page, 'ArrowLeft');

    const cursor = await page.evaluate('ui.cursor');
    expect(cursor).toEqual([0, 0]);
  });

  test('selecting empty square does nothing', async ({ page }) => {
    // Navigate to an empty square (row 4, col 4 = e4)
    await navPress(page, 'ArrowUp');
    await navPress(page, 'ArrowUp');

    // Try to select — should have no selection since it's empty
    await navPress(page, 'Space');
    const selected = await page.evaluate('ui.selected');
    expect(selected).toBeNull();
  });

  test('deselect piece by clicking same square', async ({ page }) => {
    // Select e2 pawn
    await navPress(page, 'Space');
    expect(await page.evaluate('ui.selected')).not.toBeNull();

    // Press Space again on same square → deselect
    await navPress(page, 'Space');
    expect(await page.evaluate('ui.selected')).toBeNull();
  });

  test('N during AI turn cancels and starts new game', async ({ page }) => {
    // Make a move to trigger AI
    await navPress(page, 'Space');
    await navPress(page, 'ArrowUp');
    await navPress(page, 'ArrowUp');
    await navPress(page, 'Space');

    // Immediately press N
    await page.keyboard.press('n');
    await page.waitForTimeout(500);

    // Should be back in difficulty menu
    const phase = await page.evaluate('ui.phase');
    expect(phase).toBe('menu');
  });

  test('footer has keyboard hints', async ({ page }) => {
    const footer = page.locator('#footer');
    await expect(footer).toBeVisible();
    for (const key of ['N', 'U', 'K']) {
      await expect(footer.locator('kbd', { hasText: key }).first()).toBeVisible();
    }
  });
});
