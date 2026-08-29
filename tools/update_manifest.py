#!/usr/bin/env python3
"""Generate/update manifest.json by detecting file changes via SHA256."""

import hashlib
import json
import os
import re
from pathlib import Path

# FIRMWARE_EXCLUDES used to live here, listing boot.py and friends as "never
# OTA-update". It was dead code — nothing read it — and the test that guarded it
# could not fail, because scan_files() builds every name as 'www/<x>.html.gz' so
# no excluded name could ever appear. What actually restricts the manifest is
# the glob below: games/*.html only.
GAME_DIR = 'games'  # Source dir in repo (mapped to www/ on ESP32)
FIRMWARE_NAME = 'firmware.bin'
PLATFORMIO_INI = Path('firmware/arduino/platformio.ini')


def compute_hash(filepath):
    """SHA256 of file content."""
    h = hashlib.sha256()
    with open(filepath, 'rb') as f:
        while chunk := f.read(8192):
            h.update(chunk)
    return h.hexdigest()


def scan_files(project_dir):
    """Find game .html files for manifest.

    Manifest keys use .html.gz suffix (matching what the ESP32 stores
    on LittleFS and what deploy-ota.sh uploads). The hash is computed
    from the source .html file to detect content changes.

    MicroPython .py files are NOT included — the active firmware is
    Arduino C++ which does not use them.
    """
    project_dir = Path(project_dir)
    files = []

    # Game files (games/*.html → www/*.html.gz on ESP32)
    games_dir = project_dir / GAME_DIR
    if games_dir.exists():
        for p in games_dir.glob('*.html'):
            files.append({
                'name': f'www/{p.name}.gz',
                'path': p,
                'firmware': False,
            })

    return files


def read_firmware_version(project_dir):
    """Read MUNDMAUS_FW_VERSION from firmware/arduino/platformio.ini."""
    ini_path = Path(project_dir) / PLATFORMIO_INI
    if not ini_path.exists():
        return None

    text = ini_path.read_text(encoding='utf-8')
    match = re.search(r'-DMUNDMAUS_FW_VERSION=(\d+)', text)
    if not match:
        return None
    return int(match.group(1))


def update_manifest(project_dir, manifest_path=None):
    """Scan files, compare hashes, bump versions, write manifest.

    The previous hash of every file is kept IN the manifest, not in a side file.
    It used to live in .manifest-state.json, which is gitignored: the first run
    in any fresh clone or agent worktree therefore saw no prior hashes and bumped
    every game version despite byte-identical content, pushing seven "updates"
    that made each device rewrite its whole LittleFS game set. Versions were also
    not reproducible — two machines produced different manifests from the same
    source. Keeping the hash in the committed manifest makes the file
    self-contained, and the firmware ignores unknown keys (updater.cpp reads only
    "version" and "firmware" via ArduinoJson's default operator).
    """
    project_dir = Path(project_dir)
    if manifest_path is None:
        manifest_path = project_dir / 'manifest.json'
    manifest_path = Path(manifest_path)

    # Load existing manifest (current versions AND the hashes they belong to)
    old_manifest = {'manifest_version': 1, 'files': {}}
    if manifest_path.exists():
        old_manifest = json.loads(manifest_path.read_text())
    old_files = old_manifest.get('files', {})

    new_files = {}

    for f in scan_files(project_dir):
        name = f['name']
        h = compute_hash(f['path'])

        old_entry = old_files.get(name, {})
        old_hash = old_entry.get('sha256')
        old_ver = old_entry.get('version', 0)

        if old_ver == 0:
            version = 1                      # new file
        elif old_hash is None or old_hash != h:
            version = old_ver + 1            # content changed (or first hashed run)
        else:
            version = old_ver                # unchanged

        entry = {'version': version, 'sha256': h}
        if f['firmware']:
            entry['firmware'] = True
        new_files[name] = entry

    firmware_path = project_dir / FIRMWARE_NAME
    old_fw = old_files.get(FIRMWARE_NAME)
    fw_version = read_firmware_version(project_dir)
    if firmware_path.exists() or old_fw:
        # Fall back to the previous number only if there IS one. The old ternary
        # dereferenced old_fw unconditionally and raised AttributeError when a
        # firmware.bin existed with no prior entry and an unreadable version.
        if fw_version is None:
            fw_version = (old_fw or {}).get('version')
        if fw_version is None:
            raise SystemExit(
                f"ERROR: cannot determine firmware version — {PLATFORMIO_INI} is "
                f"missing or has no -DMUNDMAUS_FW_VERSION, and {FIRMWARE_NAME} has "
                f"no previous manifest entry to fall back to.")
        entry = {'version': fw_version, 'firmware': True}
        if firmware_path.exists():
            # Hash and size let a deploy prove it is shipping the binary the
            # manifest advertises; the manifest carried neither before.
            entry['sha256'] = compute_hash(firmware_path)
            entry['size'] = firmware_path.stat().st_size
        new_files[FIRMWARE_NAME] = entry

    manifest = {
        'manifest_version': 1,
        'files': dict(sorted(new_files.items())),
    }

    # Atomic: a reader (deploy-ota.sh parses this file) must never observe a
    # half-written manifest, and an interrupted run must not leave one behind.
    tmp = manifest_path.with_suffix(manifest_path.suffix + '.tmp')
    tmp.write_text(json.dumps(manifest, indent=2) + '\n')
    os.replace(tmp, manifest_path)

    return manifest


def main():
    project_dir = Path(__file__).parent.parent
    manifest_path = project_dir / 'manifest.json'

    manifest = update_manifest(project_dir, manifest_path)

    print(f"manifest.json updated ({len(manifest['files'])} files):")
    for name, info in manifest['files'].items():
        flag = ' [firmware]' if info.get('firmware') else ''
        print(f"  {name}: v{info['version']}{flag}")


if __name__ == '__main__':
    main()
