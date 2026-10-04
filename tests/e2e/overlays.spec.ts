import { test, expect, type Page } from '@playwright/test';
import { gotoGame, LOCAL } from './helpers';

// Finding A3 of the comment review (04.10.2026): the games showed and hid their overlays by hand at
// single transitions, and every forgotten one left the patient behind an overlay or without one. Here a
// seeded random sequence of what a player, a carer and the device can do runs against each game, and
// after every step the overlays must match the game's state.

type Op = { name: string; run: (page: Page) => Promise<void> };

type Game = {
  name: string;
  ready: string;       // JS expression: the page has initialised
  violations: string;  // JS expression: string[] of overlays that disagree with the state
  settled: string;     // JS expression: no move or transition is pending
  phase: string;       // JS expression: the game's phase, for coverage
  phases: string[];    // every phase the sequence must reach
  ops: Op[];
};

const key = (k: string): Op => ({ name: `key ${k}`, run: page => page.keyboard.press(k) });
const js = (name: string, code: string): Op => ({ name, run: async page => { await page.evaluate(code); } });

const VISIBLE = `const vis = id => !document.getElementById(id).classList.contains('hidden');`;

const GAMES: Game[] = [
  {
    name: 'chess',
    ready: `typeof ui !== 'undefined' && ui.phase === 'menu'`,
    violations: `(() => { ${VISIBLE} const out = [];
      if (vis('diff-menu') !== (ui.phase === 'menu')) out.push('diff-menu, phase ' + ui.phase);
      if (vis('promo-overlay') !== (ui.phase === 'promoting')) out.push('promo-overlay, phase ' + ui.phase);
      if (vis('game-over') !== (ui.phase === 'gameover')) out.push('game-over, phase ' + ui.phase);
      return out; })()`,
    settled: `!aiTimer`,
    phase: `ui.phase`,
    phases: ['menu', 'playing', 'promoting', 'gameover'],
    ops: [
      key(' '), key(' '), key('n'), key('u'), key('ArrowUp'), key('ArrowDown'), key('ArrowLeft'), key('ArrowRight'),
      js('device: puff', `onDeviceMessage({ type: 'action', kind: 'puff' })`),
      js('device: new game', `onDeviceMessage({ type: 'action', kind: 'new_game' })`),
      js('device: undo', `onDeviceMessage({ type: 'action', kind: 'undo' })`),
      js('the game ends', `if (ui.phase === 'playing') showGameOver('Test', 'Ende')`),
      js('a pawn reaches the last rank', `(() => {
        if (ui.phase !== 'playing' || game.turn !== 'w') return;
        const c = [0, 1, 2, 3, 4, 5, 6, 7].find(c => game.board[0][c]?.type !== 'k' && game.board[1][c]?.type !== 'k');
        game.board[1][c] = { color: 'w', type: 'p' }; game.board[0][c] = null;
        ui.promoMove = { fr: 1, fc: c, tr: 0, tc: c, flag: 'promo' };
        showPromoDialog(); })()`),
      js('mouse: game-over NEW', `document.getElementById('go-new').click()`),
    ],
  },
];

function rng(seed: number) {
  return () => { seed = (seed * 16807) % 2147483647; return (seed - 1) / 2147483646; };
}

for (const g of GAMES) {
  test(`${g.name}: overlays match the game state after every step`, async ({ page }) => {
    test.skip(!LOCAL, 'drives the page through many transitions; no device needed');
    test.setTimeout(120_000);
    await gotoGame(page, g.name);
    await page.waitForFunction(g.ready, null, { timeout: 15_000 });

    const random = rng(4711);
    const done: string[] = [];
    const seen = new Set<string>();
    for (let step = 0; step < 80; step++) {
      const op = g.ops[Math.floor(random() * g.ops.length)];
      await op.run(page);
      done.push(op.name);
      const now: string[] = await page.evaluate(g.violations);
      expect(now, `right after: ${done.slice(-6).join(' → ')}`).toEqual([]);
      await page.waitForFunction(g.settled, null, { timeout: 15_000 });
      const later: string[] = await page.evaluate(g.violations);
      expect(later, `once settled after: ${done.slice(-6).join(' → ')}`).toEqual([]);
      seen.add(await page.evaluate(g.phase));
    }
    expect([...seen].sort(), 'the sequence visits every phase').toEqual([...g.phases].sort());
  });
}
