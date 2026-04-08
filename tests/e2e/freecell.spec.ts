import { test, expect } from '@playwright/test';
import { gotoGame, esp32Cooldown, getState, navPress } from './helpers';

test.describe('Freecell Gameplay', () => {
  test.afterEach(async ({ page }) => { await esp32Cooldown(page); });
  test.beforeEach(async ({ page }) => {
    await gotoGame(page, 'freecell');
    await page.waitForSelector('#game', { timeout: 15_000 });
  });

  test('loads with 52 cards across 8 columns', async ({ page }) => {
    const total = await page.evaluate(`
      tableau.reduce((sum, col) => sum + col.length, 0)
    `);
    expect(total).toBe(52);
  });

  test('navigation works across columns', async ({ page }) => {
    const start = await page.evaluate('navCol');
    expect(start).toBe(0);

    // Navigate right through 8 tableau columns + action col
    for (let i = 0; i < 8; i++) {
      await navPress(page, 'ArrowRight');
    }
    const afterRight = await page.evaluate('navCol');
    expect(afterRight).toBe(8); // action column

    // Navigate left back to col 0
    for (let i = 0; i < 8; i++) {
      await navPress(page, 'ArrowLeft');
    }
    const afterLeft = await page.evaluate('navCol');
    expect(afterLeft).toBe(0);
  });

  test('move card to free cell', async ({ page }) => {
    // Set up: single card in col 0, everything else empty
    await page.evaluate(`
      const card = {rank:'K', suit:'\u2660', faceUp:true};
      tableau = [[card], [], [], [], [], [], [], []];
      freeCells = [null, null, null, null];
      foundations = [[], [], [], []];
      selectedCard = null; gameWon = false;
      navZone = 'tableau'; navCol = 0; navCardIdx = -1;
      render();
    `);

    // Select the King
    await navPress(page, 'Space');
    expect((await getState(page)).selectedCard).not.toBeNull();

    // Navigate up to top row (free cells are cols 0-3)
    await navPress(page, 'ArrowUp');

    // Ensure we're at free cell col 0
    const topCol = await page.evaluate('navCol');
    // If not at 0, navigate left
    if (topCol > 0) {
      for (let i = 0; i < topCol; i++) await navPress(page, 'ArrowLeft');
    }

    // Place in free cell
    await navPress(page, 'Space');

    // Verify free cell has the card
    const fc0 = await page.evaluate('freeCells[0]');
    expect(fc0).not.toBeNull();
    expect(fc0.rank).toBe('K');
    // Tableau col 0 should be empty
    const col0Len = await page.evaluate('tableau[0].length');
    expect(col0Len).toBe(0);
  });

  test('move card between columns', async ({ page }) => {
    // Set up: red 6 on col 0, black 7 on col 1
    await page.evaluate(`
      tableau = [
        [{rank:'6', suit:'\u2665', faceUp:true}],
        [{rank:'7', suit:'\u2660', faceUp:true}],
        [], [], [], [], [], []
      ];
      freeCells = [null, null, null, null];
      foundations = [[], [], [], []];
      selectedCard = null; gameWon = false;
      navZone = 'tableau'; navCol = 0; navCardIdx = -1;
      render();
    `);

    // Select red 6
    await navPress(page, 'Space');
    expect((await getState(page)).selectedCard).not.toBeNull();

    // Navigate right to col 1
    await navPress(page, 'ArrowRight');

    // Place
    await navPress(page, 'Space');

    // Verify col 1 has 2 cards with red 6 on top
    const col1Len = await page.evaluate('tableau[1].length');
    expect(col1Len).toBe(2);
    const topRank = await page.evaluate('tableau[1][1].rank');
    expect(topRank).toBe('6');
    // Col 0 empty
    const col0Len = await page.evaluate('tableau[0].length');
    expect(col0Len).toBe(0);
  });

  test('undo reverses move', async ({ page }) => {
    // Set up: Ace on col 0
    await page.evaluate(`
      tableau = [
        [{rank:'A', suit:'\u2660', faceUp:true}],
        [{rank:'2', suit:'\u2665', faceUp:true}],
        [], [], [], [], [], []
      ];
      freeCells = [null, null, null, null];
      foundations = [[], [], [], []];
      selectedCard = null; gameWon = false;
      navZone = 'tableau'; navCol = 0; navCardIdx = -1;
      undoStack = [];
      render();
    `);

    // Move Ace to free cell
    await navPress(page, 'Space');
    await navPress(page, 'ArrowUp');
    // Navigate to free cell 0
    while (await page.evaluate('navCol') > 0) {
      await navPress(page, 'ArrowLeft');
    }
    await navPress(page, 'Space');

    // Verify move happened
    const fcBefore = await page.evaluate('freeCells[0]');
    expect(fcBefore).not.toBeNull();

    // Undo
    await page.keyboard.press('u');
    await page.waitForTimeout(150);

    // Verify undo worked
    const fcAfter = await page.evaluate('freeCells[0]');
    expect(fcAfter).toBeNull();
    const col0Len = await page.evaluate('tableau[0].length');
    expect(col0Len).toBe(1);
  });

  test('place Ace on foundation', async ({ page }) => {
    // Set up: Ace of spades in col 0
    await page.evaluate(`
      tableau = [
        [{rank:'A', suit:'\u2660', faceUp:true}],
        [], [], [], [], [], [], []
      ];
      freeCells = [null, null, null, null];
      foundations = [[], [], [], []];
      selectedCard = null; gameWon = false;
      navZone = 'tableau'; navCol = 0; navCardIdx = -1;
      render();
    `);

    // Select Ace
    await navPress(page, 'Space');
    expect((await getState(page)).selectedCard).not.toBeNull();

    // Navigate to top row, foundation col 4 (= foundation index 0, for spades)
    await navPress(page, 'ArrowUp');
    // Navigate to col 4 (foundation 0)
    while (await page.evaluate('navCol') < 4) {
      await navPress(page, 'ArrowRight');
    }

    // Place
    await navPress(page, 'Space');

    // Verify foundation has the Ace
    const fLen = await page.evaluate('foundations[0].length');
    expect(fLen).toBe(1);
  });

  test('N key starts new game', async ({ page }) => {
    // Make a move first to dirty the state
    await navPress(page, 'Space'); // select
    await page.keyboard.press('n');
    await page.waitForTimeout(200);

    const state = await getState(page);
    expect(state.navCol).toBe(0);
    expect(state.navZone).toBe('tableau');
    expect(state.selectedCard).toBeNull();
    expect(state.gameWon).toBe(false);

    // Should have 52 cards again
    const total = await page.evaluate('tableau.reduce((s,c) => s + c.length, 0)');
    expect(total).toBe(52);
  });

  test('rapid 10x new game does not crash', async ({ page }) => {
    for (let i = 0; i < 10; i++) await page.keyboard.press('n');
    await page.waitForTimeout(300);
    const total = await page.evaluate('tableau.reduce((s,c) => s + c.length, 0)');
    expect(total).toBe(52);
  });
});
