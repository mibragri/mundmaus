import { defineConfig } from '@playwright/test';

const ESP32_URL = process.env.ESP32_URL ?? 'http://192.168.178.86';

export default defineConfig({
  testDir: '.',
  testMatch: '*.spec.ts',
  timeout: 60_000,
  expect: {
    timeout: 10_000,
  },
  fullyParallel: false,       // ESP32 is single-threaded, serialize tests
  workers: 1,
  retries: 0,
  reporter: 'list',
  use: {
    baseURL: ESP32_URL,
    navigationTimeout: 30_000,
    actionTimeout: 15_000,
    trace: 'off',
    screenshot: 'off',
    video: 'off',
    extraHTTPHeaders: { 'Connection': 'close' },  // ESP32 can't handle keep-alive well
  },
  projects: [
    {
      name: 'chromium',
      use: { browserName: 'chromium' },
    },
  ],
});
