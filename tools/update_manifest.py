#!/usr/bin/env python3
"""Generate/update manifest.json by detecting file changes via SHA256."""

import hashlib
import json
from pathlib import Path

# Files that should be in the manifest
FIRMWARE_EXCLUDES = {'boot.py',  # NEVER OTA-update boot.py — it's the safety net
                     'wifi.json', 'versions.json', 'update_state.json',
                     'deploy.sh', 'pyproject.toml', 'uv.lock'}
GAME_DIR = 'games'  # Source dir in repo (mapped to www/ on ESP32)


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


def update_manifest(project_dir, manifest_path=None, state_path=None):
    """Scan files, compare hashes, bump versions, write manifest."""
    project_dir = Path(project_dir)
    if manifest_path is None:
        manifest_path = project_dir / 'manifest.json'
    if state_path is None:
        state_path = project_dir / '.manifest-state.json'

    manifest_path = Path(manifest_path)
    state_path = Path(state_path)

    # Load existing state (hashes from last run)
    old_state = {}
    if state_path.exists():
        old_state = json.loads(state_path.read_text())

    # Load existing manifest (for current versions)
    old_manifest = {'manifest_version': 1, 'files': {}}
    if manifest_path.exists():
        old_manifest = json.loads(manifest_path.read_text())

    # Scan current files
    current_files = scan_files(project_dir)
    new_state = {}
    new_files = {}

    for f in current_files:
        name = f['name']
        h = compute_hash(f['path'])
        new_state[name] = h

        old_hash = old_state.get(name)
        old_ver = old_manifest.get('files', {}).get(name, {}).get('version', 0)

        if old_hash is None or old_hash != h:
            version = old_ver + 1
        else:
            version = old_ver if old_ver > 0 else 1

        entry = {'version': version}
        if f['firmware']:
            entry['firmware'] = True
        new_files[name] = entry

    # Write manifest
    manifest = {
        'manifest_version': 1,
        'files': dict(sorted(new_files.items())),
    }
    manifest_path.write_text(json.dumps(manifest, indent=2) + '\n')

    # Write state
    state_path.write_text(json.dumps(new_state, indent=2) + '\n')

    return manifest


def main():
    project_dir = Path(__file__).parent.parent
    manifest_path = project_dir / 'manifest.json'
    state_path = project_dir / '.manifest-state.json'

    manifest = update_manifest(project_dir, manifest_path, state_path)

    print(f"manifest.json updated ({len(manifest['files'])} files):")
    for name, info in manifest['files'].items():
        flag = ' [firmware]' if info.get('firmware') else ''
        print(f"  {name}: v{info['version']}{flag}")


if __name__ == '__main__':
    main()
