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
  {
    name: 'vier-gewinnt',
    ready: `typeof ui !== 'undefined' && ui.phase === 'menu'`,
    violations: `(() => { ${VISIBLE} const out = [];
      if (vis('diff-menu') !== (ui.phase === 'menu')) out.push('diff-menu, phase ' + ui.phase);
      if (vis('game-over') !== (ui.phase === 'gameover')) out.push('game-over, phase ' + ui.phase);
      return out; })()`,
    phase: `ui.phase`,
    phases: ['menu', 'playing', 'gameover'],
    ops: [
      key(' '), key(' '), key('n'), key('u'), key('ArrowUp'), key('ArrowDown'), key('ArrowLeft'), key('ArrowRight'),
      js('device: puff', `onDeviceMessage({ type: 'action', kind: 'puff' })`),
      js('device: new game', `onDeviceMessage({ type: 'action', kind: 'new_game' })`),
      js('device: undo', `onDeviceMessage({ type: 'action', kind: 'undo' })`),
      js('red drops the fourth in a row', `(() => {
        if (ui.phase !== 'playing' || !gameActive || ui.aiThinking || currentPlayer !== PLAYER) return;
        createBoard(); undoStack = [];
        for (const c of [0, 1, 2]) board[c][0] = PLAYER;
        ui.cursorCol = 3; ui.inBtnCol = false; renderBoard(); action(); })()`),
      js('mouse: game-over NEW', `document.getElementById('go-new').click()`),
    ],
  },
  {
    name: 'muehle',
    ready: `typeof ui !== 'undefined' && ui.phase === 'menu'`,
    violations: `(() => { ${VISIBLE} const out = [];
      if (vis('main-menu') !== (ui.phase === 'menu')) out.push('main-menu, phase ' + ui.phase);
      if (vis('game-over') !== (ui.phase === 'gameover')) out.push('game-over, phase ' + ui.phase);
      return out; })()`,
    phase: `ui.phase`,
    phases: ['menu', 'playing', 'gameover'],
    ops: [
      key(' '), key(' '), key('n'), key('u'), key('ArrowUp'), key('ArrowDown'), key('ArrowLeft'), key('ArrowRight'),
      js('device: puff', `onDeviceMessage({ type: 'action', kind: 'puff' })`),
      js('device: new game', `onDeviceMessage({ type: 'action', kind: 'new_game' })`),
      js('device: undo', `onDeviceMessage({ type: 'action', kind: 'undo' })`),
      js('black is down to two pieces', `(() => {
        if (ui.phase !== 'playing') return;
        game.board = Array(24).fill(null);
        for (const i of [0, 1, 2, 9]) game.board[i] = W;
        for (const i of [20, 21]) game.board[i] = B_;
        game.toPlace = { W: 0, B: 0 }; game.phase = 'zug'; game.turn = B_;
        renderBoard(); checkAndHandleWin(); })()`),
      js('mouse: game-over NEW', `document.getElementById('go-new').click()`),
    ],
  },
  {
    name: 'memo',
    ready: `typeof state !== 'undefined' && state.phase === 'menu'`,
    violations: `(() => { ${VISIBLE} const out = [];
      if (vis('difficulty-menu') !== (state.phase === 'menu')) out.push('difficulty-menu, phase ' + state.phase);
      if (vis('win-screen') !== (state.phase === 'win')) out.push('win-screen, phase ' + state.phase);
      return out; })()`,
    phase: `state.phase`,
    phases: ['menu', 'playing', 'win'],
    ops: [
      key(' '), key(' '), key('n'), key('ArrowUp'), key('ArrowDown'), key('ArrowLeft'), key('ArrowRight'),
      js('device: puff', `onDeviceMessage({ type: 'action', kind: 'puff' })`),
      js('device: new game', `onDeviceMessage({ type: 'action', kind: 'new_game' })`),
      js('all pairs found', `if (state.phase === 'playing') winGame()`),
      js('mouse: NEW button', `document.getElementById('btn-new').click()`),
      js('mouse: win NEW', `document.getElementById('btn-new-game').click()`),
    ],
  },
  ...['freecell', 'solitaire'].map((name): Game => ({
    name,
    ready: `typeof gameWon !== 'undefined' && typeof msgTimer !== 'undefined'`,
    violations: `(() => { const el = document.getElementById('message');
      const banner = el.classList.contains('show') && el.classList.contains('win');
      return banner === gameWon ? [] : ['win banner ' + banner + ', gameWon ' + gameWon]; })()`,
    phase: `gameWon ? 'won' : 'playing'`,
    phases: ['playing', 'won'],
    ops: [
      key(' '), key(' '), key('n'), key('u'), key('ArrowUp'), key('ArrowDown'), key('ArrowLeft'), key('ArrowRight'),
      js('device: puff', `onDeviceMessage({ type: 'action', kind: 'puff' })`),
      js('device: new game', `onDeviceMessage({ type: 'action', kind: 'new_game' })`),
      js('the last two kings go up by themselves', `(() => {
        if (gameWon) return;
        const card = (s, r) => ({ suit: SUITS[s], rank: RANKS[r], faceUp: true });
        foundations = SUITS.map((_, s) => RANKS.slice(0, s < 2 ? 12 : 13).map((_, r) => card(s, r)));
        tableau = tableau.map(() => []); tableau[0] = [card(0, 12)]; tableau[1] = [card(1, 12)];
        if (typeof freeCells !== 'undefined') freeCells = [null, null, null, null];
        if (typeof stock !== 'undefined') { stock = []; waste = []; }
        selectedCard = null; render(); updateStatus();
        showMessage('✨...'); autoCompleteTimer = setTimeout(autoComplete, 800); })()`),
    ],
  })),
];

function rng(seed: number) {
  return () => { seed = (seed * 16807) % 2147483647; return (seed - 1) / 2147483646; };
}

for (const g of GAMES) {
  test(`${g.name}: overlays match the game state after every step`, async ({ page }) => {
    test.skip(!LOCAL, 'drives the page through many transitions; no device needed');
    test.setTimeout(180_000);
    // Home and the portal buttons navigate to '/'; a 204 answer keeps the browser on the game.
    await page.route(url => new URL(url).pathname === '/', route => route.fulfill({ status: 204 }));
    await page.clock.install();
    await gotoGame(page, g.name);
    await page.clock.pauseAt(Date.now() + 1000);
    expect(await page.evaluate(g.ready), 'page initialised').toBe(true);

    const random = rng(4711);
    const done: string[] = [];
    const seen = new Set<string>();
    for (let step = 0; step < 80; step++) {
      const op = g.ops[Math.floor(random() * g.ops.length)];
      await op.run(page);
      done.push(op.name);
      // Three seconds in half-second steps: AI replies, the delayed game-over, memo's card checks,
      // the auto-complete and the 1.5 s message all fall inside, and each step is checked.
      for (let t = 0; t <= 3000; t += 500) {
        const v: string[] = await page.evaluate(g.violations);
        expect(v, `${t} ms after: ${done.slice(-6).join(' → ')}`).toEqual([]);
        if (t < 3000) await page.clock.runFor(500);
      }
      seen.add(await page.evaluate(g.phase));
    }
    expect([...seen].sort(), 'the sequence visits every phase').toEqual([...g.phases].sort());
  });
}
