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

  test('all manifest www assets exist as source files', () => {
    const wwwFiles = Object.keys(manifest.files).filter(f => f.startsWith('www/'));
    for (const f of wwwFiles) {
      // Map a manifest name to its repo source by stripping only the trailing
      // .gz: www/solitaire.html.gz -> games/solitaire.html, and
      // www/conn-guard.js.gz -> games/conn-guard.js (shared JS assets ship the
      // same way as the games).
      const src = f.replace(/^www\//, '').replace(/\.gz$/, '');
      const srcPath = path.join(PROJECT, 'games', src);
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
  test('shipped .gz archives match their source exactly', () => {
    const wwwFiles = Object.keys(manifest.files).filter(f => f.startsWith('www/'));
    expect(wwwFiles.length, 'manifest lists no www assets').toBeGreaterThan(0);

    for (const f of wwwFiles) {
      const src = f.replace(/^www\//, '').replace(/\.gz$/, '');   // solitaire.html | conn-guard.js
      const srcPath = path.join(PROJECT, 'games', src);
      const gzPath = path.join(PROJECT, 'firmware/arduino/data/www', `${src}.gz`);

      expect(fs.existsSync(srcPath), `${srcPath} missing`).toBe(true);
      expect(fs.existsSync(gzPath), `${gzPath} missing`).toBe(true);

      const shipped = zlib.gunzipSync(fs.readFileSync(gzPath)).toString('utf8');
      expect(shipped, `${src}.gz does not match games/${src} — regenerate it`)
        .toBe(fs.readFileSync(srcPath, 'utf8'));
    }
  });
});
