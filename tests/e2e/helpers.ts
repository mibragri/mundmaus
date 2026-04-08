import { Page } from '@playwright/test';

export const LOCAL = !process.env.ESP32_URL;

export function gamePath(name: string) {
  return LOCAL ? `/${name}.html` : `/www/${name}.html`;
}

export async function gotoGame(page: Page, name: string, retries = 4): Promise<void> {
  const path = gamePath(name);
  if (LOCAL) {
    await page.goto(path, { waitUntil: 'domcontentloaded' });
    return;
  }
  for (let attempt = 1; attempt <= retries; attempt++) {
    try {
      await page.goto(path, { waitUntil: 'domcontentloaded', timeout: 30_000 });
      return;
    } catch (err) {
      if (attempt === retries) throw err;
      await page.waitForTimeout(3000 * attempt);
    }
  }
}

/** Navigate to a raw path (e.g. '/') — used by portal/resilience tests */
export async function gotoESP32(page: Page, path: string, retries = 4): Promise<void> {
  if (LOCAL) {
    await page.goto(path, { waitUntil: 'domcontentloaded' });
    return;
  }
  for (let attempt = 1; attempt <= retries; attempt++) {
    try {
      await page.goto(path, { waitUntil: 'domcontentloaded', timeout: 30_000 });
      return;
    } catch (err) {
      if (attempt === retries) throw err;
      await page.waitForTimeout(3000 * attempt);
    }
  }
}

export async function esp32Cooldown(page: Page): Promise<void> {
  if (!LOCAL) await page.waitForTimeout(3000);
}

/** Press a key with enough delay to satisfy the 120ms direct-mode cooldown */
export async function navPress(page: Page, key: string): Promise<void> {
  await page.keyboard.press(key);
  await page.waitForTimeout(150);
}

export async function getState(page: Page): Promise<Record<string, any>> {
  return page.evaluate(`({
    navZone: typeof navZone !== 'undefined' ? navZone : undefined,
    navCol: typeof navCol !== 'undefined' ? navCol : undefined,
    navCardIdx: typeof navCardIdx !== 'undefined' ? navCardIdx : undefined,
    selectedCard: typeof selectedCard !== 'undefined' ? selectedCard : undefined,
    gameWon: typeof gameWon !== 'undefined' ? gameWon : undefined,
    chargeActive: typeof charge !== 'undefined' ? (charge.active ?? false) : false,
  })`);
}
