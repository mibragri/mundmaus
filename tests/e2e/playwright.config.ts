import { defineConfig } from '@playwright/test';

const ESP32_URL = process.env.ESP32_URL;
const LOCAL = !ESP32_URL;
const BASE_URL = ESP32_URL ?? 'http://localhost:9990';

export default defineConfig({
  testDir: '.',
  testMatch: '*.spec.ts',
  timeout: LOCAL ? 30_000 : 60_000,
  expect: { timeout: LOCAL ? 5_000 : 10_000 },
  fullyParallel: LOCAL,
  workers: LOCAL ? undefined : 1,
  retries: 0,
  reporter: 'list',
  use: {
    baseURL: BASE_URL,
    navigationTimeout: LOCAL ? 10_000 : 30_000,
    actionTimeout: LOCAL ? 5_000 : 15_000,
    trace: 'off',
    screenshot: 'off',
    video: 'off',
    ...(ESP32_URL ? { extraHTTPHeaders: { 'Connection': 'close' } } : {}),
  },
  projects: [{ name: 'chromium', use: { browserName: 'chromium' } }],
  ...(LOCAL ? {
    webServer: {
      command: `python3 -m http.server 9990 -d ${process.cwd()}/../../games`,
      port: 9990,
      reuseExistingServer: true,
    },
  } : {}),
});
