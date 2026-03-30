import { Page } from '@playwright/test';

export async function gotoESP32(page: Page, path: string, retries = 4): Promise<void> {
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
  await page.waitForTimeout(3000);
}

export async function fetchJSON(
  page: Page,
  path: string,
  options: { method?: string; retries?: number } = {},
): Promise<{ status: number; data: unknown }> {
  const method = options.method ?? 'GET';
  const retries = options.retries ?? 3;
  for (let attempt = 1; attempt <= retries; attempt++) {
    try {
      const res = method === 'POST'
        ? await page.request.post(path)
        : await page.request.get(path);
      return { status: res.status(), data: await res.json() };
    } catch (err) {
      if (attempt === retries) throw err;
      await page.waitForTimeout(3000 * attempt);
    }
  }
  throw new Error('unreachable');
}

export async function fetchHTML(
  page: Page,
  path: string,
  retries = 3,
): Promise<{ status: number; html: string }> {
  for (let attempt = 1; attempt <= retries; attempt++) {
    try {
      const res = await page.request.get(path);
      return { status: res.status(), html: await res.text() };
    } catch (err) {
      if (attempt === retries) throw err;
      await page.waitForTimeout(3000 * attempt);
    }
  }
  throw new Error('unreachable');
}

export async function fetchStatus(
  page: Page,
  path: string,
  retries = 3,
): Promise<number> {
  for (let attempt = 1; attempt <= retries; attempt++) {
    try {
      const res = await page.request.get(path);
      return res.status();
    } catch (err) {
      if (attempt === retries) throw err;
      await page.waitForTimeout(3000 * attempt);
    }
  }
  throw new Error('unreachable');
}
