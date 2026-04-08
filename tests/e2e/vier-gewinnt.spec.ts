import { test, expect } from '@playwright/test';
import { gotoGame, esp32Cooldown, navPress } from './helpers';

test.describe('Vier Gewinnt Gameplay', () => {
  test.afterEach(async ({ page }) => { await esp32Cooldown(page); });
  test.beforeEach(async ({ page }) => {
    await gotoGame(page, 'vier-gewinnt');
    // Vier Gewinnt starts with a difficulty menu
    await page.waitForSelector('#diff-menu:not(.hidden)', { timeout: 15_000 });
    await page.keyboard.press('Space'); // select difficulty (easiest)
    await page.waitForTimeout(300);
  });

  test('loads with empty 7x6 grid', async ({ page }) => {
    const phase = await page.evaluate('ui.phase');
    expect(phase).toBe('playing');

    const active = await page.evaluate('gameActive');
    expect(active).toBe(true);

    // All cells should be empty (EMPTY = 0)
    const emptyCount = await page.evaluate(`
      let count = 0;
      for (let c = 0; c < 7; c++)
        for (let r = 0; r < 6; r++)
          if (board[c][r] === 0) count++;
      count;
    `);
    expect(emptyCount).toBe(42); // 7x6
  });

  test('drop piece in column', async ({ page }) => {
    // Cursor starts at column 3 (center)
    const cursorCol = await page.evaluate('ui.cursorCol');
    expect(cursorCol).toBe(3);

    // Drop piece
    await navPress(page, 'Space');

    // Wait for AI response
    await page.waitForFunction(
      `currentPlayer === 1 && !ui.aiThinking`,
      { timeout: 5000 }
    );

    // Verify player piece landed at bottom of column 3
    const piece = await page.evaluate('board[3][0]');
    expect(piece).toBe(1); // PLAYER = 1
  });

  test('AI responds after player drop', async ({ page }) => {
    // Drop piece
    await navPress(page, 'Space');

    // Wait for AI
    await page.waitForFunction(
      `currentPlayer === 1 && !ui.aiThinking`,
      { timeout: 5000 }
    );

    // AI should have dropped a piece somewhere
    const aiPieces = await page.evaluate(`
      let count = 0;
      for (let c = 0; c < 7; c++)
        for (let r = 0; r < 6; r++)
          if (board[c][r] === 2) count++;
      count;
    `);
    expect(aiPieces).toBe(1);
  });

  test('navigation moves cursor between columns', async ({ page }) => {
    // Start at col 3
    expect(await page.evaluate('ui.cursorCol')).toBe(3);

    // Move left
    await navPress(page, 'ArrowLeft');
    expect(await page.evaluate('ui.cursorCol')).toBe(2);

    // Move right twice
    await navPress(page, 'ArrowRight');
    await navPress(page, 'ArrowRight');
    expect(await page.evaluate('ui.cursorCol')).toBe(4);

    // Move left to col 0
    for (let i = 0; i < 4; i++) await navPress(page, 'ArrowLeft');
    expect(await page.evaluate('ui.cursorCol')).toBe(0);

    // Can't go further left
    await navPress(page, 'ArrowLeft');
    expect(await page.evaluate('ui.cursorCol')).toBe(0);
  });

  test('detect horizontal win', async ({ page }) => {
    // Set up: 3 player pieces in a row at bottom of cols 0,1,2
    // AI pieces elsewhere to not interfere
    await page.evaluate(`
      // Reset board
      for (let c = 0; c < 7; c++)
        for (let r = 0; r < 6; r++)
          board[c][r] = 0;

      // Player pieces in cols 0,1,2 at row 0
      board[0][0] = 1;
      board[1][0] = 1;
      board[2][0] = 1;
      // AI pieces somewhere else (needed so game state is valid)
      board[5][0] = 2;
      board[5][1] = 2;
      board[5][2] = 2;

      currentPlayer = 1; // PLAYER
      gameActive = true;
      ui.phase = 'playing';
      ui.aiThinking = false;
      ui.cursorCol = 3;
      moveCount = 6;
      undoStack = [];
      winLine = null;
      renderBoard();
    `);

    // Drop in column 3 to complete the 4-in-a-row
    await navPress(page, 'Space');

    // Wait for win detection
    await page.waitForTimeout(600);

    // Game should be over
    const active = await page.evaluate('gameActive');
    expect(active).toBe(false);

    // Win line should be set
    const hasWinLine = await page.evaluate('winLine !== null');
    expect(hasWinLine).toBe(true);
  });

  test('undo reverses player + AI moves', async ({ page }) => {
    // Drop a piece
    await navPress(page, 'Space');

    // Wait for AI
    await page.waitForFunction(
      `currentPlayer === 1 && !ui.aiThinking`,
      { timeout: 5000 }
    );

    const movesBefore = await page.evaluate('moveCount');
    expect(movesBefore).toBe(2); // player + AI

    // Undo
    await page.keyboard.press('u');
    await page.waitForTimeout(200);

    // Move count should decrease
    const movesAfter = await page.evaluate('moveCount');
    expect(movesAfter).toBeLessThan(movesBefore);
  });

  test('N key returns to menu', async ({ page }) => {
    await page.keyboard.press('n');
    await page.waitForTimeout(300);

    const phase = await page.evaluate('ui.phase');
    expect(phase).toBe('menu');
  });

  test('rapid 10x new game does not crash', async ({ page }) => {
    for (let i = 0; i < 10; i++) {
      await page.keyboard.press('n');
      await page.waitForTimeout(50);
    }
    // Select difficulty to start again
    await page.keyboard.press('Space');
    await page.waitForTimeout(300);

    const phase = await page.evaluate('ui.phase');
    expect(phase).toBe('playing');
    const active = await page.evaluate('gameActive');
    expect(active).toBe(true);
  });

  test('footer has keyboard hints', async ({ page }) => {
    const footer = page.locator('#footer');
    await expect(footer).toBeVisible();
    for (const key of ['N', 'U', 'K']) {
      await expect(footer.locator('kbd', { hasText: key }).first()).toBeVisible();
    }
  });
});
