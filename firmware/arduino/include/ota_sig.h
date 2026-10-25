#pragma once
// Detached ECDSA P-256 signature over the SHA-256 of a downloaded OTA body.
// One hash at a time: the OTA tasks do not download two files at once.

#include <stddef.h>
#include <stdint.h>

void otaHashReset();
void otaHashUpdate(const uint8_t* data, size_t len);
// Finishes the hash. sigB64 is the base64 DER signature from the .sig file.
bool otaHashMatches(const char* sigB64);
bool otaSignatureOk(const uint8_t* msg, size_t len, const char* sigB64);
