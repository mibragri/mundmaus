import { test, expect } from '@playwright/test';
import * as fs from 'fs';
import * as path from 'path';
import * as zlib from 'zlib';

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

  // This is the only guard against shipping a stale game, and it used to run
  // ZERO assertions: it looked at games/*.html.gz, which is gitignored, so
  // existsSync() was false on any fresh clone and the loop body never executed.
  // Even where the files did exist it compared mtimes, and a checkout gives
  // every file the same mtime. It now compares the CONTENT of the artefact that
  // actually ships (firmware/arduino/data/www/, which is tracked) against the
  // source, which is decisive and works on a fresh clone.
  test('shipped .gz archives match their source HTML exactly', () => {
    const gameFiles = Object.keys(manifest.files).filter(f => f.startsWith('www/'));
    expect(gameFiles.length, 'manifest lists no games').toBeGreaterThan(0);

    for (const f of gameFiles) {
      const name = f.replace('www/', '').replace('.html.gz', '');
      const srcPath = path.join(PROJECT, 'games', `${name}.html`);
      const gzPath = path.join(PROJECT, 'firmware/arduino/data/www', `${name}.html.gz`);

      expect(fs.existsSync(srcPath), `${srcPath} missing`).toBe(true);
      expect(fs.existsSync(gzPath), `${gzPath} missing`).toBe(true);

      const shipped = zlib.gunzipSync(fs.readFileSync(gzPath)).toString('utf8');
      expect(shipped, `${name}.html.gz does not match games/${name}.html — regenerate it`)
        .toBe(fs.readFileSync(srcPath, 'utf8'));
    }
  });
});
