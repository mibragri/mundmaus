import { test, expect } from '@playwright/test';
import * as fs from 'fs';
import * as path from 'path';

const PROJECT = path.resolve(__dirname, '../..');
const MANIFEST_PATH = path.join(PROJECT, 'manifest.json');

test.describe('OTA Manifest Validation', () => {
  const manifest = JSON.parse(fs.readFileSync(MANIFEST_PATH, 'utf-8'));

  test('manifest is valid JSON with correct structure', () => {
    expect(manifest).toHaveProperty('manifest_version', 1);
    expect(manifest).toHaveProperty('files');
    expect(typeof manifest.files).toBe('object');
  });

  test('firmware.bin entry exists and has firmware:true', () => {
    expect(manifest.files['firmware.bin']).toBeDefined();
    expect(manifest.files['firmware.bin'].firmware).toBe(true);
    expect(manifest.files['firmware.bin'].version).toBeGreaterThan(0);
  });

  test('all game files have version > 0', () => {
    const gameFiles = Object.keys(manifest.files).filter(f => f.startsWith('www/'));
    expect(gameFiles.length).toBeGreaterThanOrEqual(6);
    for (const f of gameFiles) {
      expect(manifest.files[f].version, f).toBeGreaterThan(0);
    }
  });

  test('all manifest game files exist as source HTML', () => {
    const gameFiles = Object.keys(manifest.files).filter(f => f.startsWith('www/'));
    for (const f of gameFiles) {
      const name = f.replace('www/', '').replace('.html.gz', '');
      const srcPath = path.join(PROJECT, 'games', `${name}.html`);
      expect(fs.existsSync(srcPath), `${srcPath} missing`).toBe(true);
    }
  });

  test('all manifest game files exist in LittleFS data dir', () => {
    const gameFiles = Object.keys(manifest.files).filter(f => f.startsWith('www/'));
    for (const f of gameFiles) {
      const dataPath = path.join(PROJECT, 'firmware/arduino/data', f);
      expect(fs.existsSync(dataPath), `${dataPath} missing`).toBe(true);
    }
  });

  test('gz files are newer than source HTML files', () => {
    const gameFiles = Object.keys(manifest.files).filter(f => f.startsWith('www/'));
    for (const f of gameFiles) {
      const name = f.replace('www/', '').replace('.html.gz', '');
      const srcPath = path.join(PROJECT, 'games', `${name}.html`);
      const gzPath = path.join(PROJECT, 'games', `${name}.html.gz`);
      if (fs.existsSync(gzPath)) {
        const srcTime = fs.statSync(srcPath).mtimeMs;
        const gzTime = fs.statSync(gzPath).mtimeMs;
        expect(gzTime, `${name}.html.gz older than source`).toBeGreaterThanOrEqual(srcTime);
      }
    }
  });
});
