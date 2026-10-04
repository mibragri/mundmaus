import { test, expect, type APIRequestContext } from '@playwright/test';

// Bench-only checks against the ESP32 on the bench (ESP32_URL). They disturb the device or run for
// minutes, so each runs only when asked for explicitly:
//   MUNDMAUS_TEST_HOOKS=1      firmware from env:esp32_testhooks; wedges the device once
//   MUNDMAUS_STRESS_MINUTES=N  N minutes of WebSocket reconnect churn with broadcasts, any firmware
// Never point these at the patient's device.
const BASE = process.env.ESP32_URL;

// Last "event=boot" line of /api/wifi-log: boot counter and esp_reset_reason() of that boot.
async function lastBoot(api: APIRequestContext): Promise<{ boot: number; reason: number }> {
  const text = await (await api.get('/api/wifi-log', { timeout: 10_000 })).text();
  const boots = [...text.matchAll(/boot=(\d+)\b.*?event=boot\b.*?reset_reason=(\d+)/g)];
  expect(boots.length, 'wifi-log has boot entries').toBeGreaterThan(0);
  const last = boots[boots.length - 1];
  return { boot: Number(last[1]), reason: Number(last[2]) };
}

// Polls /api/info until it answers; returns the elapsed ms, or null at the deadline.
async function waitForInfo(api: APIRequestContext, deadlineMs: number): Promise<number | null> {
  const start = Date.now();
  while (Date.now() - start < deadlineMs) {
    try {
      if ((await api.get('/api/info', { timeout: 3_000 })).ok()) return Date.now() - start;
    } catch { /* not up yet */ }
    await new Promise(r => setTimeout(r, 3_000));
  }
  return null;
}

test.describe('Bench', () => {
  test.skip(!BASE, 'needs ESP32_URL');

  // Finding A3: with CONFIG_ASYNC_TCP_USE_WDT=0 nothing watched the AsyncTCP task. A blocked handler
  // left the CPU free, the Core-0 heartbeat kept ticking, and HTTP and WS stayed dead for good.
  test('A3: a wedged AsyncTCP task reboots the device', async ({ request }) => {
    test.skip(process.env.MUNDMAUS_TEST_HOOKS !== '1', 'needs env:esp32_testhooks and MUNDMAUS_TEST_HOOKS=1');
    test.setTimeout(240_000);
    const before = await lastBoot(request);
    await request.post('/api/test/wedge-asynctcp', { timeout: 3_000 }).catch(() => { /* never answers */ });
    // The task watchdog fires after 30 s; booting and rejoining WiFi take another 10-20 s.
    const back = await waitForInfo(request, 120_000);
    expect(back, 'HTTP comes back on its own within 2 minutes').not.toBeNull();
    const after = await lastBoot(request);
    expect(after.boot, 'the device rebooted').toBeGreaterThan(before.boot);
    console.log(`  back after ${back} ms, reset_reason of the new boot: ${after.reason}`);
  });

  // Finding C1: AsyncWebSocket 3.6.0 iterates and erases its client list without a lock while new
  // clients are appended (LoadProhibited panic under reconnect churn). Churn plus broadcasts.
  test('C1: reconnect churn with broadcasts does not crash the device', async ({ request }) => {
    const minutes = Number(process.env.MUNDMAUS_STRESS_MINUTES || 0);
    test.skip(!minutes, 'set MUNDMAUS_STRESS_MINUTES');
    test.setTimeout((minutes + 4) * 60_000);
    const before = await lastBoot(request);
    const current = (await (await request.get('/api/settings')).json()).current;
    const wsUrl = `ws://${new URL(BASE!).hostname}:81/`;
    const end = Date.now() + minutes * 60_000;
    let opened = 0, broadcasts = 0;

    // Open a socket, hold it 0-400 ms, close it, repeat.
    const churner = async () => {
      while (Date.now() < end) {
        await new Promise<void>(resolve => {
          const ws = new WebSocket(wsUrl);
          const done = () => { try { ws.close(); } catch { /* already closed */ } resolve(); };
          ws.onopen = () => { opened++; setTimeout(done, Math.random() * 400); };
          ws.onerror = () => setTimeout(done, 200);
        });
      }
    };
    // A preview with the current values changes nothing but makes the device broadcast to every client.
    const broadcaster = async () => {
      while (Date.now() < end) {
        try {
          const r = await request.post('/api/settings/preview', { data: { values: current }, timeout: 5_000 });
          if (r.ok()) broadcasts++;
        } catch { /* busy */ }
        await new Promise(r => setTimeout(r, 50));
      }
    };
    await Promise.all([churner(), churner(), churner(), churner(), churner(), churner(), broadcaster()]);

    const back = await waitForInfo(request, 60_000);
    expect(back, 'device still answers').not.toBeNull();
    const after = await lastBoot(request);
    console.log(`  ${opened} sockets opened, ${broadcasts} broadcasts, boot ${before.boot} -> ${after.boot}`);
    expect(after.boot, 'no reboot during the churn').toBe(before.boot);
  });
});
