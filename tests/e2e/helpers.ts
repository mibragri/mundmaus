import { Page } from '@playwright/test';

/**
 * Navigate to a page on the ESP32 with retry logic.
 * The ESP32 HTTP server is single-threaded and resets connections
 * if requests come too fast. Retries with increasing backoff.
 */
export async function gotoESP32(page: Page, path: string, retries = 4): Promise<void> {
  for (let attempt = 1; attempt <= retries; attempt++) {
    try {
      await page.goto(path, { waitUntil: 'domcontentloaded', timeout: 30_000 });
      return;
    } catch (err) {
      if (attempt === retries) throw err;
      // Exponential backoff: 3s, 6s, 9s
      await page.waitForTimeout(3000 * attempt);
    }
  }
}

/**
 * Pause between tests so the ESP32 can recover.
 * ESP32 needs ~3s between connections to avoid ERR_CONNECTION_RESET.
 */
export async function esp32Cooldown(page: Page): Promise<void> {
  await page.waitForTimeout(3000);
}
