#!/usr/bin/env python3
"""Write a detached ECDSA P-256 signature for an OTA file.

The signature is the base64 of the DER signature over the SHA-256 of the
file bytes, in <path>.sig. The firmware checks it only when the certificate
check failed. The private key is ota_signing_key.pem in the project root
and is not committed.
"""

import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
KEY = ROOT / "ota_signing_key.pem"


def sign(path: Path) -> None:
    if not KEY.is_file():
        sys.exit(f"missing {KEY}")
    if not path.is_file():
        sys.exit(f"missing {path}")
    der = subprocess.check_output(
        ["openssl", "dgst", "-sha256", "-sign", str(KEY), str(path)]
    )
    b64 = subprocess.check_output(["openssl", "base64", "-A"], input=der)
    path.with_name(path.name + ".sig").write_bytes(b64 + b"\n")


def main() -> None:
    if len(sys.argv) < 2:
        sys.exit("usage: sign_ota.py <file> [<file> ...]")
    for arg in sys.argv[1:]:
        sign(Path(arg))


if __name__ == "__main__":
    main()
