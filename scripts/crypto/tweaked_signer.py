"""
Ed25519 signing with vanity tweak — exact port from Kotlin Ed25519RawSigner.kt.

Standard Ed25519 uses seed → SHA-512 → (scalar, nonce_prefix) → sign.
Vanity tweak modifies scalar: tweaked_scalar = (clamped_scalar + tweak) mod L.
The nonce_prefix stays the same (from original seed SHA-512).

This produces valid Ed25519 signatures that verify against the tweaked public key
(P_tweaked = P_original + tweak * G).
"""

import hashlib
import struct

from nacl.bindings import (
    crypto_scalarmult_ed25519_base_noclamp,
    crypto_core_ed25519_scalar_reduce,
    crypto_core_ed25519_scalar_add,
)

# Ed25519 group order L
L = 2**252 + 27742317777372353535851937790883648493


def _sha512(data: bytes) -> bytes:
    return hashlib.sha512(data).digest()


def _le_bytes_to_int(b: bytes) -> int:
    return int.from_bytes(b, "little")


def _int_to_le32(n: int) -> bytes:
    return (n % (2**256)).to_bytes(32, "little")


def _reduce_mod_l(b64: bytes) -> bytes:
    """Reduce 64-byte LE value mod L → 32-byte LE scalar."""
    n = _le_bytes_to_int(b64)
    return _int_to_le32(n % L)


def _scalar_mul_add(r: bytes, k: bytes, s: bytes) -> bytes:
    """Compute (r + k * s) mod L, all 32-byte LE scalars."""
    r_int = _le_bytes_to_int(r)
    k_int = _le_bytes_to_int(k)
    s_int = _le_bytes_to_int(s)
    result = (r_int + k_int * s_int) % L
    return _int_to_le32(result)


def prepare_vanity_signing_key(seed: bytes, tweak_hex: str) -> tuple:
    """
    Prepare signing material from seed + tweak.

    Returns: (tweaked_scalar, nonce_prefix, public_key) — all 32 bytes.

    Exact port from Kotlin Ed25519RawSigner.prepareVanitySigningKey().
    """
    expanded = _sha512(seed)
    scalar = bytearray(expanded[:32])
    nonce_prefix = bytes(expanded[32:64])

    # Clamp scalar (Ed25519 standard)
    scalar[0] &= 248
    scalar[31] &= 127
    scalar[31] |= 64

    # Apply tweak: tweaked_scalar = (scalar + tweak) mod L
    scalar_int = _le_bytes_to_int(bytes(scalar))
    tweak_int = int(tweak_hex, 16)
    tweaked_int = (scalar_int + tweak_int) % L
    tweaked_scalar = _int_to_le32(tweaked_int)

    # Public key from tweaked scalar (point multiplication)
    public_key = crypto_scalarmult_ed25519_base_noclamp(tweaked_scalar)

    return tweaked_scalar, nonce_prefix, public_key


def sign_tweaked(
    tweaked_scalar: bytes,
    nonce_prefix: bytes,
    public_key: bytes,
    message: bytes,
) -> bytes:
    """
    Ed25519 signature with tweaked scalar.

    Returns: 64-byte signature (R || S).

    Exact port from Kotlin Ed25519RawSigner.sign():
    1. r = SHA-512(nonce_prefix || message) mod L
    2. R = r * G
    3. k = SHA-512(R || public_key || message) mod L
    4. S = (r + k * tweaked_scalar) mod L
    5. signature = R || S
    """
    # 1. r = SHA-512(nonce_prefix || message) mod L
    nonce_hash = _sha512(nonce_prefix + message)
    r = _reduce_mod_l(nonce_hash)

    # 2. R = r * G (base point multiplication)
    R = crypto_scalarmult_ed25519_base_noclamp(r)

    # 3. k = SHA-512(R || public_key || message) mod L
    k_hash = _sha512(R + public_key + message)
    k = _reduce_mod_l(k_hash)

    # 4. S = (r + k * tweaked_scalar) mod L
    S = _scalar_mul_add(r, k, tweaked_scalar)

    # 5. Signature = R || S
    return R + S
