import { test, expect } from '@playwright/test';
import { gotoGame, esp32Cooldown, navPress } from './helpers';

// Regressions found in the 2026-08-29 bug hunt. Each test failed before its fix.

test.describe('memo — win screen', () => {
  test.afterEach(async ({ page }) => { await esp32Cooldown(page); });
  test.beforeEach(async ({ page }) => {
    await gotoGame(page, 'memo');
    await page.waitForSelector('#difficulty-menu:not(.hidden)', { timeout: 15_000 });
    await navPress(page, 'ArrowUp');      // easiest level
    await page.keyboard.press('Space');
    await page.waitForTimeout(300);
  });

  // The win screen is a full-screen opaque overlay at z-index 200. Only
  // showMenu() ever removed it, but the win screen's second button (⟳, replay
  // the same level) calls createBoard() directly. The patient then drove a
  // freshly dealt board he could not see, and only a keypress could recover —
  // he has no keyboard. This is the "stuck, needs another person" case.
  test('replaying the same level clears the win overlay', async ({ page }) => {
    await page.evaluate('winGame()');
    await expect(page.locator('#win-screen')).toBeVisible();

    await navPress(page, 'ArrowDown');    // NEW -> ⟳ (replay same level)
    expect(await page.evaluate('state.winCursor')).toBe(1);

    await page.keyboard.press('Space');
    await page.waitForTimeout(250);

    expect(await page.evaluate('state.phase')).toBe('playing');
    await expect(page.locator('#win-screen')).toBeHidden();
  });

  // Whatever is on screen must be what receives the input.
  test('nothing covers the board after replaying', async ({ page }) => {
    await page.evaluate('winGame()');
    await navPress(page, 'ArrowDown');
    await page.keyboard.press('Space');
    await page.waitForTimeout(250);

    const covered = await page.evaluate(
      `!!document.elementFromPoint(innerWidth / 2, innerHeight / 2)?.closest('#win-screen')`
    );
    expect(covered).toBe(false);
  });
});

// Rotating carers get no training and operate the games by mouse. memo wired
// only 2 of its 7 buttons, and the difficulty menu — the very first screen —
// ignored every click, with nothing on screen saying a keyboard was required.
test.describe('memo — mouse operation', () => {
  test.afterEach(async ({ page }) => { await esp32Cooldown(page); });
  test.beforeEach(async ({ page }) => {
    await gotoGame(page, 'memo');
    await page.waitForSelector('#difficulty-menu:not(.hidden)', { timeout: 15_000 });
  });

  test('clicking a difficulty starts that level', async ({ page }) => {
    await page.locator('.diff-option').nth(2).click();
    await page.waitForTimeout(250);
    expect(await page.evaluate('state.phase')).toBe('playing');
    expect(await page.evaluate('state.level')).toBe(2);
  });

  test('clicking NEW returns to the difficulty menu', async ({ page }) => {
    await page.locator('.diff-option').nth(0).click();
    await page.waitForTimeout(250);
    await page.locator('#btn-new').click();
    await page.waitForTimeout(250);
    expect(await page.evaluate('state.phase')).toBe('menu');
    await expect(page.locator('#difficulty-menu')).toBeVisible();
  });

  test('clicking the win-screen replay button deals a new board', async ({ page }) => {
    await page.locator('.diff-option').nth(0).click();
    await page.waitForTimeout(250);
    await page.evaluate('winGame()');
    await expect(page.locator('#win-screen')).toBeVisible();

    await page.locator('#btn-same').click();
    await page.waitForTimeout(250);
    expect(await page.evaluate('state.phase')).toBe('playing');
    await expect(page.locator('#win-screen')).toBeHidden();
  });
});

// showMessage() scheduled an unmanaged 1.5 s clear. The auto-complete hint set
// one, the win banner arrived before it fired and set no timer of its own, and
// the stale clear then wiped the 🎉 while gameWon stayed true — navigation dead,
// board looking perfectly normal. The patient is deaf, so the win sound told him
// nothing and his joystick had simply stopped responding.
for (const game of ['solitaire', 'freecell'] as const) {
  test.describe(`${game} — win banner`, () => {
    test.afterEach(async ({ page }) => { await esp32Cooldown(page); });
    test.beforeEach(async ({ page }) => {
      await gotoGame(page, game);
      await page.waitForSelector('#game', { timeout: 15_000 });
    });

    test('survives a pending auto-complete message clear', async ({ page }) => {
      await page.evaluate(`showMessage('✨...', '')`);   // schedules a clear at +1.5 s
      await page.waitForTimeout(200);
      await page.evaluate(`showMessage('🎉', 'win')`);
      await expect(page.locator('#message')).toHaveClass(/win/);

      await page.waitForTimeout(1700);                   // past the stale clear
      await expect(page.locator('#message')).toHaveClass(/win/);
    });

    test('a plain message still clears itself', async ({ page }) => {
      await page.evaluate(`showMessage('✨...', '')`);
      await expect(page.locator('#message')).toHaveClass(/show/);
      await page.waitForTimeout(1700);
      await expect(page.locator('#message')).not.toHaveClass(/show/);
    });

    // The footer advertises N for a new game, but only the lowercase key was
    // matched — with Caps Lock on, a carer sees a game that ignores them.
    test('Shift+N starts a new game', async ({ page }) => {
      await page.evaluate('moves = 42');
      await page.keyboard.press('Shift+KeyN');
      await page.waitForTimeout(250);
      expect(await page.evaluate('moves')).toBe(0);
    });
  });
}

test.describe('freecell — NEW button', () => {
  test.afterEach(async ({ page }) => { await esp32Cooldown(page); });
  test.beforeEach(async ({ page }) => {
    await gotoGame(page, 'freecell');
    await page.waitForSelector('#game', { timeout: 15_000 });
  });

  // The action buttons were wired as `btn.onclick = actFns[i]`, so clicking NEW
  // called initGame(PointerEvent). initGame treats any non-undefined argument as
  // the deal seed, and mulberry32 does `seed |= 0` — an object becomes 0. Every
  // mouse click therefore dealt the identical board, so a caretaker restarting
  // the game for the patient handed him the same deal forever.
  test('clicking NEW deals a fresh, randomly seeded game', async ({ page }) => {
    const newBtn = page.locator('.action-btn').nth(1);

    await newBtn.click();
    await page.waitForTimeout(200);
    const first = await page.evaluate('dealNumber');
    expect(typeof first).toBe('number');
    expect(Number.isFinite(first as number)).toBe(true);

    await newBtn.click();
    await page.waitForTimeout(200);
    const second = await page.evaluate('dealNumber');
    expect(typeof second).toBe('number');
    expect(second).not.toBe(first);
  });
});
