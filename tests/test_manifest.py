"""Tests for tools/update-manifest.py manifest generation."""
import json
import sys
from pathlib import Path

import pytest

# Import the module under test
sys.path.insert(0, str(Path(__file__).parent.parent / 'tools'))
from update_manifest import scan_files, compute_hash, update_manifest


@pytest.fixture
def project_dir(tmp_path):
    """Create a mock project directory."""
    (tmp_path / 'main.py').write_text('# main')
    (tmp_path / 'boot.py').write_text('# boot')
    (tmp_path / 'config.py').write_text('# config')
    (tmp_path / 'games').mkdir()
    (tmp_path / 'games' / 'chess.html').write_text('<html>chess</html>')
    (tmp_path / 'games' / 'memory.html').write_text('<html>memory</html>')
    # Files that should NOT be in manifest
    (tmp_path / 'wifi.json').write_text('{}')
    (tmp_path / 'versions.json').write_text('{}')
    (tmp_path / 'deploy.sh').write_text('#!/bin/bash')
    return tmp_path


def test_scan_files_finds_py_and_games(project_dir):
    files = scan_files(project_dir)
    names = {f['name'] for f in files}
    assert 'main.py' in names
    assert 'boot.py' not in names  # boot.py excluded — never OTA-update the safety net
    assert 'config.py' in names
    assert 'www/chess.html' in names
    assert 'www/memory.html' in names


def test_scan_files_excludes_non_firmware(project_dir):
    files = scan_files(project_dir)
    names = {f['name'] for f in files}
    assert 'wifi.json' not in names
    assert 'versions.json' not in names
    assert 'deploy.sh' not in names


def test_scan_files_marks_firmware(project_dir):
    files = scan_files(project_dir)
    by_name = {f['name']: f for f in files}
    assert by_name['main.py']['firmware'] is True
    assert by_name['www/chess.html']['firmware'] is False


def test_compute_hash_deterministic(project_dir):
    h1 = compute_hash(project_dir / 'main.py')
    h2 = compute_hash(project_dir / 'main.py')
    assert h1 == h2


def test_compute_hash_changes_on_content(project_dir):
    h1 = compute_hash(project_dir / 'main.py')
    (project_dir / 'main.py').write_text('# changed')
    h2 = compute_hash(project_dir / 'main.py')
    assert h1 != h2


def test_update_manifest_creates_new(project_dir):
    manifest_path = project_dir / 'manifest.json'
    state_path = project_dir / '.manifest-state.json'
    update_manifest(project_dir, manifest_path, state_path)

    manifest = json.loads(manifest_path.read_text())
    assert manifest['manifest_version'] == 1
    assert 'main.py' in manifest['files']
    assert manifest['files']['main.py']['version'] == 1
    assert manifest['files']['main.py']['firmware'] is True


def test_update_manifest_bumps_on_change(project_dir):
    manifest_path = project_dir / 'manifest.json'
    state_path = project_dir / '.manifest-state.json'

    # First run
    update_manifest(project_dir, manifest_path, state_path)
    m1 = json.loads(manifest_path.read_text())
    assert m1['files']['main.py']['version'] == 1

    # Change file
    (project_dir / 'main.py').write_text('# changed content')
    update_manifest(project_dir, manifest_path, state_path)
    m2 = json.loads(manifest_path.read_text())
    assert m2['files']['main.py']['version'] == 2


def test_update_manifest_no_bump_if_unchanged(project_dir):
    manifest_path = project_dir / 'manifest.json'
    state_path = project_dir / '.manifest-state.json'

    update_manifest(project_dir, manifest_path, state_path)
    update_manifest(project_dir, manifest_path, state_path)
    m = json.loads(manifest_path.read_text())
    assert m['files']['main.py']['version'] == 1


def test_update_manifest_removes_deleted_file(project_dir):
    manifest_path = project_dir / 'manifest.json'
    state_path = project_dir / '.manifest-state.json'

    update_manifest(project_dir, manifest_path, state_path)
    assert 'www/chess.html' in json.loads(manifest_path.read_text())['files']

    (project_dir / 'games' / 'chess.html').unlink()
    update_manifest(project_dir, manifest_path, state_path)
    assert 'www/chess.html' not in json.loads(manifest_path.read_text())['files']
