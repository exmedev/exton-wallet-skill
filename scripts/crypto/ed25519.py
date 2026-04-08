"""
Ed25519 signing wrapper over PyNaCl.
"""

import nacl.signing


def sign(message: bytes, private_key: bytes) -> bytes:
    """Sign message with Ed25519 private key. Returns 64-byte signature."""
    signing_key = nacl.signing.SigningKey(private_key)
    signed = signing_key.sign(message)
    return signed.signature  # 64 bytes


def verify(message: bytes, signature: bytes, public_key: bytes) -> bool:
    """Verify Ed25519 signature."""
    try:
        verify_key = nacl.signing.VerifyKey(public_key)
        verify_key.verify(message, signature)
        return True
    except nacl.exceptions.BadSignatureError:
        return False


def public_key_from_private(private_key: bytes) -> bytes:
    """Derive public key from private key."""
    signing_key = nacl.signing.SigningKey(private_key)
    return bytes(signing_key.verify_key)
