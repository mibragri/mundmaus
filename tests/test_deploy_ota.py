"""Tests for tools/deploy-ota.sh: what reaches the OTA server must be readable by its web server,
whatever mode the local copy has. On 01.11.2026 a firmware.bin at mode 600 went up as 600 (rsync -a
keeps the mode), and Caddy answered 403 while the new manifest was already live."""
import re
from pathlib import Path

DEPLOY = Path(__file__).resolve().parent.parent / 'tools' / 'deploy-ota.sh'


def _uploads():
    return [line.strip() for line in DEPLOY.read_text().splitlines()
            if re.match(r'\s*rsync\b', line) and '$REMOTE_HOST:' in line]


def test_the_uploads_are_found():
    # Without this, moving the uploads to another tool would let the check below pass on nothing.
    assert len(_uploads()) >= 6


def test_every_upload_sets_a_world_readable_mode():
    for line in _uploads():
        assert '--chmod=F644' in line, line
