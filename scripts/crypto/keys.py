"""
Key derivation from Recovery Code — exact port from Kotlin.

Recovery Code (52 bytes → Base58 ≈ 71 chars):
  exton_app_secret(12) + tweak(8) + exton_pro_pubkey(32)

Seed derivation:
  SHA-256(exton_app_secret || "exton-multisig-v1") → 32 bytes → SLIP-0010 → keypair
"""

import hashlib
import hmac
import struct

import base58
import nacl.signing

MULTISIG_SALT = b"exton-multisig-v1"
TON_PATH = [44, 607, 0]  # m/44'/607'/0' (all hardened)
HARDENED = 0x80000000


def apply_tweak(pubkey: bytes, tweak: bytes) -> bytes:
    """Apply vanity tweak to Ed25519 pubkey: P' = P + tweak_scalar * G.

    tweak is 8 bytes (u64 big-endian), converted to Ed25519 scalar (32 bytes LE).
    Uses libsodium's Ed25519 point arithmetic via PyNaCl bindings.
    """
    from nacl.bindings import (
        crypto_scalarmult_ed25519_base_noclamp,
        crypto_core_ed25519_add,
    )

    # Convert tweak (8 bytes BE) to u64, then to 32-byte LE scalar
    tweak_int = int.from_bytes(tweak, "big")
    tweak_scalar = tweak_int.to_bytes(32, "little")

    # tweak_point = tweak_scalar * G (base point multiplication)
    tweak_point = crypto_scalarmult_ed25519_base_noclamp(tweak_scalar)

    # result = pubkey + tweak_point (point addition)
    tweaked = crypto_core_ed25519_add(pubkey, tweak_point)
    return tweaked


def generate_app_secret() -> bytes:
    """Generate 12 random bytes for exton_app_secret."""
    import os
    return os.urandom(12)


def derive_seed(app_secret: bytes) -> bytes:
    """SHA-256(app_secret || salt) → 32-byte seed."""
    return hashlib.sha256(app_secret + MULTISIG_SALT).digest()


def seed_to_keypair(seed: bytes) -> tuple:
    """Seed → (private_key, public_key) directly, no SLIP-0010."""
    signing_key = nacl.signing.SigningKey(seed)
    return bytes(signing_key._signing_key[:32]), bytes(signing_key.verify_key)


def encode_recovery_code(app_secret: bytes, tweak: bytes, pro_pubkey: bytes) -> str:
    """Encode Recovery Code: app_secret(12) + tweak(8) + pro_pubkey(32) → Base58."""
    if len(app_secret) != 12:
        raise ValueError(f"app_secret must be 12 bytes, got {len(app_secret)}")
    if len(tweak) != 8:
        raise ValueError(f"tweak must be 8 bytes, got {len(tweak)}")
    if len(pro_pubkey) != 32:
        raise ValueError(f"pro_pubkey must be 32 bytes, got {len(pro_pubkey)}")
    combined = app_secret + tweak + pro_pubkey
    return base58.b58encode(combined).decode()


def format_recovery_code(code: str) -> str:
    """Format for display: 7-char groups separated by dashes."""
    return "-".join(code[i:i + 7] for i in range(0, len(code), 7))


def decode_recovery_code(code: str) -> tuple:
    """Decode Recovery Code → (app_secret, tweak, pro_pubkey) as bytes."""
    cleaned = code.replace("-", "").replace(" ", "").strip()
    raw = base58.b58decode(cleaned)
    if len(raw) != 52:
        raise ValueError(f"Recovery Code must be 52 bytes, got {len(raw)}")
    app_secret = raw[0:12]
    tweak = raw[12:20]
    pro_pubkey = raw[20:52]
    return app_secret, tweak, pro_pubkey


def _slip0010_master(seed: bytes) -> tuple:
    """HMAC-SHA512 master key derivation. Returns (private_key, chain_code)."""
    h = hmac.new(b"ed25519 seed", seed, hashlib.sha512).digest()
    return h[:32], h[32:]


def _slip0010_child(parent_key: bytes, parent_chain: bytes, index: int) -> tuple:
    """Derive hardened child key."""
    hardened_index = index | HARDENED
    data = bytearray(37)
    data[0] = 0x00
    data[1:33] = parent_key
    struct.pack_into(">I", data, 33, hardened_index)
    h = hmac.new(parent_chain, bytes(data), hashlib.sha512).digest()
    return h[:32], h[32:]


def derive_keypair(seed: bytes, path: list = None) -> tuple:
    """SLIP-0010 derivation: seed → (private_key, public_key) for given path."""
    if path is None:
        path = TON_PATH
    private_key, chain_code = _slip0010_master(seed)
    for index in path:
        private_key, chain_code = _slip0010_child(private_key, chain_code, index)
    signing_key = nacl.signing.SigningKey(private_key)
    public_key = bytes(signing_key.verify_key)
    return private_key, public_key


def recovery_code_to_keys(code: str) -> dict:
    """
    Full derivation: Recovery Code → all keys + address info.

    IMPORTANT: Exton MultiSig uses seed DIRECTLY as Ed25519 private key,
    NOT via SLIP-0010 derivation. This matches Kotlin:
      val appSeed = SHA-256(appSecret || salt)
      val keyPair = Ed25519KeyPair(appSeed)  // seed → Bouncy Castle directly

    Returns dict with:
      app_secret, tweak, pro_pubkey,
      app_privkey, app_pubkey (32 bytes each)
    """
    app_secret, tweak, pro_pubkey = decode_recovery_code(code)

    # Derive seed from app_secret + salt (this IS the private key for MultiSig)
    app_privkey = hashlib.sha256(app_secret + MULTISIG_SALT).digest()

    # Public key from seed directly (NOT SLIP-0010)
    signing_key = nacl.signing.SigningKey(app_privkey)
    app_pubkey = bytes(signing_key.verify_key)

    # Apply tweak: tweaked_pubkey = app_pubkey + tweak * G
    tweaked_app_pubkey = apply_tweak(app_pubkey, tweak)

    return {
        "app_secret": app_secret,
        "tweak": tweak,
        "pro_pubkey": pro_pubkey,
        "app_privkey": app_privkey,
        "app_pubkey": app_pubkey,           # original (for signing)
        "tweaked_app_pubkey": tweaked_app_pubkey,  # tweaked (for address)
    }
