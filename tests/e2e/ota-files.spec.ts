import { test, expect } from '@playwright/test';
import * as fs from 'fs';
import * as path from 'path';

const OTA_BASE = 'https://mundmaus.de/ota';
const PROJECT = path.resolve(__dirname, '../..');
const localManifest = JSON.parse(fs.readFileSync(path.join(PROJECT, 'manifest.json'), 'utf-8'));

// Read OTA auth from project
const authFile = path.join(PROJECT, '.ota_auth_b64');
const AUTH = fs.existsSync(authFile) ? `Basic ${fs.readFileSync(authFile, 'utf-8').trim()}` : '';

test.describe('OTA Remote File Integrity', () => {
  test('remote manifest is accessible and valid JSON', async () => {
    const headers: Record<string, string> = {};
    if (AUTH) headers['Authorization'] = AUTH;
    const resp = await fetch(`${OTA_BASE}/manifest.json`, { headers });
    expect(resp.status).toBe(200);
    const data = await resp.json();
    expect(data).toHaveProperty('manifest_version', 1);
    expect(data).toHaveProperty('files');
  });

  test('remote manifest matches local manifest versions', async () => {
    const headers: Record<string, string> = {};
    if (AUTH) headers['Authorization'] = AUTH;
    const resp = await fetch(`${OTA_BASE}/manifest.json`, { headers });
    const remote = await resp.json();
    for (const [file, info] of Object.entries(localManifest.files)) {
      const remoteInfo = remote.files[file] as any;
      expect(remoteInfo, `${file} missing on remote`).toBeDefined();
      expect(remoteInfo.version, `${file} version mismatch`).toBe((info as any).version);
    }
  });

  test('all manifest files are downloadable', async () => {
    const headers: Record<string, string> = {};
    if (AUTH) headers['Authorization'] = AUTH;
    for (const file of Object.keys(localManifest.files)) {
      const resp = await fetch(`${OTA_BASE}/${file}`, { method: 'HEAD', headers });
      expect(resp.status, `${file} not downloadable`).toBe(200);
    }
  });

  test('firmware.bin is reasonable size (500KB-2MB)', async () => {
    const headers: Record<string, string> = {};
    if (AUTH) headers['Authorization'] = AUTH;
    const resp = await fetch(`${OTA_BASE}/firmware.bin`, { method: 'HEAD', headers });
    const size = parseInt(resp.headers.get('content-length') ?? '0');
    expect(size).toBeGreaterThan(500_000);
    expect(size).toBeLessThan(2_000_000);
  });
});
