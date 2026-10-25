#pragma once
// Public half of the OTA signing key (ECDSA P-256). The private half lives in
// ~/data/mundmaus/ota_signing_key.pem, outside the repo, used by tools/sign_ota.py.
// A certificate failure falls back to an unchecked connection and accepts a
// file only when its detached .sig matches this key.

inline constexpr char OTA_PUBKEY_PEM[] =
    "-----BEGIN PUBLIC KEY-----\n"
    "MFkwEwYHKoZIzj0CAQYIKoZIzj0DAQcDQgAEOQgbwKAn3UeogVDNglLF6yojjvO2\n"
    "cO4jcnV6Kn/zbVlujogtNQaUNsocAiUNwglxruUxKv59E2vdlxRrxlmegA==\n"
    "-----END PUBLIC KEY-----\n";
