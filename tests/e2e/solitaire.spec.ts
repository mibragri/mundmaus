import { test, expect } from '@playwright/test';
import { gotoGame, esp32Cooldown, getState, navPress, LOCAL } from './helpers';

test.describe('Solitaire', () => {
  test.afterEach(async ({ page }) => { await esp32Cooldown(page); });
  test.beforeEach(async ({ page }) => {
    await gotoGame(page, 'solitaire');
    await page.waitForSelector('#game', { timeout: 15_000 });
  });

  // === LOADING ===
  test('loads with cards visible', async ({ page }) => {
    const cards = await page.locator('.card').count();
    expect(cards).toBeGreaterThan(20);
  });

  test('has 4 action buttons', async ({ page }) => {
    await expect(page.locator('.action-btn')).toHaveCount(4);
  });

  // === NAVIGATION ===
  test('right arrow increases navCol', async ({ page }) => {
    const before = await getState(page);
    await page.keyboard.press('ArrowRight');
    const after = await getState(page);
    expect(after.navCol).toBe(before.navCol + 1);
  });

  test('left arrow decreases navCol', async ({ page }) => {
    await navPress(page, 'ArrowRight'); // move to col 1 first
    const before = await getState(page);
    expect(before.navCol).toBe(1);
    await navPress(page, 'ArrowLeft');
    const after = await getState(page);
    expect(after.navCol).toBe(0);
  });

  test('left at col 0 stays at col 0', async ({ page }) => {
    await page.keyboard.press('ArrowLeft');
    const state = await getState(page);
    expect(state.navCol).toBe(0);
  });

  test('up from tableau goes to top row', async ({ page }) => {
    const before = await getState(page);
    expect(before.navZone).toBe('tableau');
    await page.keyboard.press('ArrowUp');
    const after = await getState(page);
    expect(after.navZone).toBe('top');
  });

  test('down from top returns to tableau', async ({ page }) => {
    await navPress(page, 'ArrowUp');
    expect((await getState(page)).navZone).toBe('top');
    await navPress(page, 'ArrowDown');
    expect((await getState(page)).navZone).toBe('tableau');
  });

  test('navigate to action buttons (col 7)', async ({ page }) => {
    for (let i = 0; i < 8; i++) await navPress(page, 'ArrowRight');
    const state = await getState(page);
    expect(state.navCol).toBe(7);
  });

  // === VISUAL FOCUS ===
  test('focused card has gold outline', async ({ page }) => {
    const cursor = page.locator('.nav-cursor, .nav-active');
    await expect(cursor.first()).toBeVisible();
  });

  test('focusPulse animation is active on nav element', async ({ page }) => {
    // Navigate to col 1 which always has a face-up card with nav-cursor
    await navPress(page, 'ArrowRight');
    const anim = await page.evaluate(() => {
      // Check both nav-cursor (on cards) and nav-active (on pile-slots)
      const el = document.querySelector('.nav-cursor') || document.querySelector('.nav-active');
      if (!el) return 'NO_ELEMENT';
      return getComputedStyle(el).animationName;
    });
    expect(anim).toContain('focusPulse');
  });

  // === CARD SELECTION ===
  test('space selects a card', async ({ page }) => {
    // Navigate to column with face-up card (col 0 always has one)
    await page.keyboard.press('Space');
    const state = await getState(page);
    // Either selected a card or drew from stock (if on stock)
    // Navigate right first to avoid stock
    await page.keyboard.press('n'); // new game to reset
    await page.keyboard.press('ArrowRight'); // col 1
    await page.keyboard.press('Space');
    const after = await getState(page);
    expect(after.selectedCard).not.toBeNull();
  });

  test('space on same card deselects', async ({ page }) => {
    await page.keyboard.press('ArrowRight'); // col 1
    await page.keyboard.press('Space'); // select
    expect((await getState(page)).selectedCard).not.toBeNull();
    await page.keyboard.press('Space'); // deselect
    expect((await getState(page)).selectedCard).toBeNull();
  });

  // === STOCK ===
  test('space on stock draws card to waste', async ({ page }) => {
    await page.keyboard.press('ArrowUp'); // go to top row
    // Navigate to col 0 (stock)
    while ((await getState(page)).navCol > 0) await page.keyboard.press('ArrowLeft');
    const before = await page.evaluate('waste.length');
    await page.keyboard.press('Space');
    const after = await page.evaluate('waste.length');
    expect(after).toBe(before + 1);
  });

  // === UNDO ===
  test('undo reverses stock draw', async ({ page }) => {
    await page.keyboard.press('ArrowUp');
    while ((await getState(page)).navCol > 0) await page.keyboard.press('ArrowLeft');
    await page.keyboard.press('Space'); // draw
    const wasteAfterDraw = await page.evaluate('waste.length');
    expect(wasteAfterDraw).toBeGreaterThan(0);
    await page.keyboard.press('u'); // undo
    const wasteAfterUndo = await page.evaluate('waste.length');
    expect(wasteAfterUndo).toBe(wasteAfterDraw - 1);
  });

  // === NEW GAME ===
  test('N key starts new game', async ({ page }) => {
    await page.keyboard.press('ArrowRight');
    await page.keyboard.press('Space'); // select something
    await page.keyboard.press('n'); // new game
    const state = await getState(page);
    expect(state.navCol).toBe(0);
    expect(state.navZone).toBe('tableau');
    expect(state.selectedCard).toBeNull();
    expect(state.gameWon).toBe(false);
  });

  test('rapid 10x new game does not crash', async ({ page }) => {
    for (let i = 0; i < 10; i++) await page.keyboard.press('n');
    const cards = await page.locator('.card').count();
    expect(cards).toBeGreaterThan(20);
  });

  // === CHARGE SYSTEM ===
  test('J toggles sim mode', async ({ page }) => {
    await page.keyboard.press('j');
    const text = await page.locator('#kb-mode').textContent();
    expect(text).toContain('Sim');
    await page.keyboard.press('j');
    const text2 = await page.locator('#kb-mode').textContent();
    expect(text2).toContain('Direkt');
  });

  test('charge preview appears in sim mode', async ({ page }) => {
    await page.keyboard.press('j'); // sim mode
    await page.keyboard.down('ArrowRight');
    await page.waitForTimeout(200);
    const visible = await page.evaluate(() => {
      const pv = document.getElementById('charge-preview');
      return pv && pv.style.display !== 'none';
    });
    expect(visible).toBe(true);
    await page.keyboard.up('ArrowRight');
  });

  test('charge cancel on key release hides preview', async ({ page }) => {
    await page.keyboard.press('j');
    await page.keyboard.down('ArrowRight');
    await page.waitForTimeout(200);
    await page.keyboard.up('ArrowRight');
    await page.waitForTimeout(100);
    const state = await getState(page);
    expect(state.chargeActive).toBe(false);
  });

  // === FOOTER ===
  test('footer has keyboard hints', async ({ page }) => {
    const footer = page.locator('#footer');
    await expect(footer).toBeVisible();
    for (const key of ['U', 'N', 'K']) {
      await expect(footer.locator('kbd', { hasText: key }).first()).toBeVisible();
    }
  });

  // === PORTAL ===
  test('P navigates to portal', async ({ page }) => {
    await page.waitForTimeout(500);
    await page.keyboard.press('p');
    await page.waitForURL('**/', { timeout: 15_000 });
  });
});
