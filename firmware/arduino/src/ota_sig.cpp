#include "ota_sig.h"
#include "ota_pubkey.h"

#include <mbedtls/base64.h>
#include <mbedtls/md.h>
#include <mbedtls/pk.h>
#include <mbedtls/sha256.h>
#include <string.h>

static mbedtls_sha256_context g_sha;
static bool g_active = false;

static bool _verifyHash(const unsigned char hash[32], const char* sigB64) {
    if (sigB64 == nullptr || sigB64[0] == '\0') return false;
    unsigned char sig[96];
    size_t sigLen = 0;
    const int decoded = mbedtls_base64_decode(
        sig, sizeof(sig), &sigLen,
        reinterpret_cast<const unsigned char*>(sigB64), strlen(sigB64));
    if (decoded != 0 || sigLen == 0) return false;

    mbedtls_pk_context pk;
    mbedtls_pk_init(&pk);
    const int parsed = mbedtls_pk_parse_public_key(
        &pk, reinterpret_cast<const unsigned char*>(OTA_PUBKEY_PEM),
        strlen(OTA_PUBKEY_PEM) + 1);
    if (parsed != 0) {
        mbedtls_pk_free(&pk);
        return false;
    }
    const int ok = mbedtls_pk_verify(&pk, MBEDTLS_MD_SHA256, hash, 32, sig, sigLen);
    mbedtls_pk_free(&pk);
    return ok == 0;
}

void otaHashReset() {
    if (g_active) mbedtls_sha256_free(&g_sha);
    mbedtls_sha256_init(&g_sha);
    g_active = mbedtls_sha256_starts(&g_sha, 0) == 0;
}

void otaHashUpdate(const uint8_t* data, size_t len) {
    if (!g_active || data == nullptr || len == 0) return;
    if (mbedtls_sha256_update(&g_sha, data, len) != 0) g_active = false;
}

bool otaHashMatches(const char* sigB64) {
    unsigned char hash[32];
    if (!g_active || mbedtls_sha256_finish(&g_sha, hash) != 0) {
        if (g_active) mbedtls_sha256_free(&g_sha);
        g_active = false;
        return false;
    }
    mbedtls_sha256_free(&g_sha);
    g_active = false;
    return _verifyHash(hash, sigB64);
}

bool otaSignatureOk(const uint8_t* msg, size_t len, const char* sigB64) {
    otaHashReset();
    otaHashUpdate(msg, len);
    return otaHashMatches(sigB64);
}
