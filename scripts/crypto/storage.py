"""
Encrypted key storage — AES-256-GCM.
Stores exme_app_privkey encrypted with user password.
"""

import hashlib
import json
import os
from pathlib import Path

EXME_DIR = Path.home() / ".exme"
CONFIG_FILE = EXME_DIR / "config.json"
KEY_FILE = EXME_DIR / "app_key.enc"


def _derive_aes_key(password: str, salt: bytes) -> bytes:
    """PBKDF2-SHA256, 100K iterations -> 32 bytes AES key."""
    return hashlib.pbkdf2_hmac("sha256", password.encode(), salt, 100_000, dklen=32)


def save_encrypted_key(private_key: bytes, password: str):
    """Encrypt and save private key."""
    EXME_DIR.mkdir(parents=True, exist_ok=True)
    salt = os.urandom(16)
    aes_key = _derive_aes_key(password, salt)

    # AES-256-GCM via cryptography or fallback to XOR+HMAC
    try:
        from cryptography.hazmat.primitives.ciphers.aead import AESGCM
        nonce = os.urandom(12)
        cipher = AESGCM(aes_key)
        encrypted = cipher.encrypt(nonce, private_key, None)
        data = salt + nonce + encrypted
    except ImportError:
        # Fallback: XOR with key + HMAC for integrity
        xored = bytes(a ^ b for a, b in zip(private_key, aes_key))
        mac = hashlib.sha256(aes_key + xored).digest()
        data = salt + xored + mac

    KEY_FILE.write_bytes(data)


def load_encrypted_key(password: str) -> bytes:
    """Decrypt and return private key."""
    data = KEY_FILE.read_bytes()
    salt = data[:16]
    aes_key = _derive_aes_key(password, salt)

    try:
        from cryptography.hazmat.primitives.ciphers.aead import AESGCM
        nonce = data[16:28]
        encrypted = data[28:]
        cipher = AESGCM(aes_key)
        return cipher.decrypt(nonce, encrypted, None)
    except ImportError:
        xored = data[16:48]
        mac = data[48:80]
        expected_mac = hashlib.sha256(aes_key + xored).digest()
        if mac != expected_mac:
            raise ValueError("Wrong password or corrupted key")
        return bytes(a ^ b for a, b in zip(xored, aes_key))


def save_config(config: dict):
    """Save wallet config (public info only)."""
    EXME_DIR.mkdir(parents=True, exist_ok=True)
    CONFIG_FILE.write_text(json.dumps(config, indent=2))


def load_config() -> dict:
    """Load wallet config."""
    if not CONFIG_FILE.exists():
        return {}
    return json.loads(CONFIG_FILE.read_text())


def is_configured() -> bool:
    """Check if wallet is set up."""
    return CONFIG_FILE.exists() and KEY_FILE.exists()
