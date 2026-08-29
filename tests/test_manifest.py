"""Tests for tools/update_manifest.py manifest generation.

These used to assert MicroPython behaviour — that main.py and config.py appear
in the manifest and are flagged as firmware. scan_files() deliberately stopped
including .py files when the project moved to the Arduino firmware, so six of
the nine tests had been failing continuously and the gate was dead. Read
literally, "fixing" them meant putting .py back into the OTA manifest, i.e. the
opposite of what the code must do. They are inverted here instead, and the paths
that had no coverage at all — the firmware version and the hash-driven bump —
are covered.
"""
import json
import sys
from pathlib import Path

import pytest

# Import the module under test
sys.path.insert(0, str(Path(__file__).parent.parent / 'tools'))
from update_manifest import scan_files, compute_hash, update_manifest  # noqa: E402


@pytest.fixture
def project_dir(tmp_path):
    """A mock project: two games, plus files that must never be shipped."""
    (tmp_path / 'games').mkdir()
    (tmp_path / 'games' / 'chess.html').write_text('<html>chess</html>')
    (tmp_path / 'games' / 'memo.html').write_text('<html>memo</html>')
    # None of these may reach the manifest.
    (tmp_path / 'main.py').write_text('# main')
    (tmp_path / 'boot.py').write_text('# boot')
    (tmp_path / 'wifi.json').write_text('{}')
    (tmp_path / 'deploy.sh').write_text('#!/bin/bash')
    return tmp_path


def _with_platformio(project_dir, fw_version=4214):
    ini = project_dir / 'firmware' / 'arduino'
    ini.mkdir(parents=True, exist_ok=True)
    (ini / 'platformio.ini').write_text(
        f'[env:esp32]\nbuild_flags =\n    -DMUNDMAUS_FW_VERSION={fw_version}\n')
    return ini / 'platformio.ini'


# ── scanning ──────────────────────────────────────────────────────────────

def test_scan_files_finds_only_games(project_dir):
    names = {f['name'] for f in scan_files(project_dir)}
    assert names == {'www/chess.html.gz', 'www/memo.html.gz'}


def test_scan_files_never_returns_python(project_dir):
    """The Arduino firmware does not run the .py files; shipping them over OTA
    would waste the patient's flash and could overwrite the recovery path."""
    names = {f['name'] for f in scan_files(project_dir)}
    assert not any(n.endswith('.py') for n in names)


def test_scan_files_names_use_gz_suffix(project_dir):
    """Manifest keys must match what the device stores on LittleFS."""
    for f in scan_files(project_dir):
        assert f['name'].startswith('www/')
        assert f['name'].endswith('.html.gz')


def test_scan_files_hashes_the_source_html(project_dir):
    """The key is the .gz name but the hash comes from the .html source."""
    by_name = {f['name']: f for f in scan_files(project_dir)}
    assert by_name['www/chess.html.gz']['path'].name == 'chess.html'
    assert by_name['www/chess.html.gz']['firmware'] is False


# ── hashing ───────────────────────────────────────────────────────────────

def test_compute_hash_deterministic(project_dir):
    p = project_dir / 'games' / 'chess.html'
    assert compute_hash(p) == compute_hash(p)


def test_compute_hash_changes_on_content(project_dir):
    p = project_dir / 'games' / 'chess.html'
    h1 = compute_hash(p)
    p.write_text('<html>changed</html>')
    assert compute_hash(p) != h1


# ── manifest generation ───────────────────────────────────────────────────

def test_creates_new_manifest(project_dir):
    manifest_path = project_dir / 'manifest.json'
    update_manifest(project_dir, manifest_path)

    m = json.loads(manifest_path.read_text())
    assert m['manifest_version'] == 1
    assert m['files']['www/chess.html.gz']['version'] == 1
    assert not any(n.endswith('.py') for n in m['files'])


def test_stores_hash_in_manifest(project_dir):
    """The hash must live in the manifest itself — see the regression below."""
    manifest_path = project_dir / 'manifest.json'
    update_manifest(project_dir, manifest_path)
    m = json.loads(manifest_path.read_text())
    assert m['files']['www/chess.html.gz']['sha256'] == compute_hash(
        project_dir / 'games' / 'chess.html')


def test_bumps_on_change(project_dir):
    manifest_path = project_dir / 'manifest.json'
    update_manifest(project_dir, manifest_path)
    (project_dir / 'games' / 'chess.html').write_text('<html>changed</html>')
    update_manifest(project_dir, manifest_path)

    m = json.loads(manifest_path.read_text())
    assert m['files']['www/chess.html.gz']['version'] == 2
    assert m['files']['www/memo.html.gz']['version'] == 1  # untouched


def test_no_bump_if_unchanged(project_dir):
    manifest_path = project_dir / 'manifest.json'
    update_manifest(project_dir, manifest_path)
    update_manifest(project_dir, manifest_path)
    m = json.loads(manifest_path.read_text())
    assert m['files']['www/chess.html.gz']['version'] == 1


def test_no_bump_without_side_state_file(project_dir):
    """Regression: versions must not depend on untracked local state.

    The previous hash lived in .manifest-state.json, which is gitignored. A
    fresh clone or an agent worktree therefore saw no prior hashes and bumped
    EVERY game with byte-identical content, so each device re-downloaded its
    whole game set and two machines produced different manifests. Deleting any
    such side file between runs must change nothing.
    """
    manifest_path = project_dir / 'manifest.json'
    update_manifest(project_dir, manifest_path)
    first = json.loads(manifest_path.read_text())

    for stray in project_dir.glob('.manifest-state*'):
        stray.unlink()

    update_manifest(project_dir, manifest_path)
    assert json.loads(manifest_path.read_text()) == first


def test_removes_deleted_file(project_dir):
    manifest_path = project_dir / 'manifest.json'
    update_manifest(project_dir, manifest_path)
    assert 'www/chess.html.gz' in json.loads(manifest_path.read_text())['files']

    (project_dir / 'games' / 'chess.html').unlink()
    update_manifest(project_dir, manifest_path)
    assert 'www/chess.html.gz' not in json.loads(manifest_path.read_text())['files']


def test_no_temp_file_left_behind(project_dir):
    """The manifest is written atomically; nothing may linger."""
    manifest_path = project_dir / 'manifest.json'
    update_manifest(project_dir, manifest_path)
    assert list(project_dir.glob('manifest.json.tmp')) == []


# ── firmware entry (previously untested entirely) ─────────────────────────

def test_firmware_version_comes_from_platformio_ini(project_dir):
    _with_platformio(project_dir, 4214)
    (project_dir / 'firmware.bin').write_bytes(b'\x00' * 64)
    manifest_path = project_dir / 'manifest.json'
    update_manifest(project_dir, manifest_path)

    entry = json.loads(manifest_path.read_text())['files']['firmware.bin']
    assert entry['version'] == 4214
    assert entry['firmware'] is True


def test_firmware_entry_carries_hash_and_size(project_dir):
    """Without these a deploy cannot prove it ships the advertised binary."""
    _with_platformio(project_dir, 4214)
    (project_dir / 'firmware.bin').write_bytes(b'\x01' * 128)
    manifest_path = project_dir / 'manifest.json'
    update_manifest(project_dir, manifest_path)

    entry = json.loads(manifest_path.read_text())['files']['firmware.bin']
    assert entry['size'] == 128
    assert entry['sha256'] == compute_hash(project_dir / 'firmware.bin')


def test_firmware_version_bump_is_reflected(project_dir):
    _with_platformio(project_dir, 4214)
    (project_dir / 'firmware.bin').write_bytes(b'\x00' * 64)
    manifest_path = project_dir / 'manifest.json'
    update_manifest(project_dir, manifest_path)

    _with_platformio(project_dir, 4215)
    update_manifest(project_dir, manifest_path)
    assert json.loads(manifest_path.read_text())['files']['firmware.bin']['version'] == 4215


def test_unreadable_firmware_version_fails_loudly(project_dir):
    """It used to raise AttributeError on None, or silently keep the old number —
    which ships a new binary advertised at the previous version, so no device
    ever fetches it."""
    (project_dir / 'firmware.bin').write_bytes(b'\x00' * 64)   # no platformio.ini
    with pytest.raises(SystemExit):
        update_manifest(project_dir, project_dir / 'manifest.json')
