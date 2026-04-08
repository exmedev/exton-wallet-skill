"""
TON address encoding/decoding — CRC-16/XMODEM, Base64 URL-safe.
Port from Kotlin WalletV4R2.kt + TONAddressGenerator.kt.
"""

import base64
import hashlib
from .cell import Cell


def crc16_xmodem(data: bytes, length: int = None) -> int:
    """CRC-16/XMODEM (polynomial 0x1021, init 0x0000)."""
    if length is None:
        length = len(data)
    crc = 0x0000
    for i in range(length):
        crc ^= (data[i] & 0xFF) << 8
        for _ in range(8):
            if crc & 0x8000:
                crc = (crc << 1) ^ 0x1021
            else:
                crc <<= 1
            crc &= 0xFFFF
    return crc


def encode_address(workchain: int, hash_bytes: bytes, bounceable: bool = False) -> str:
    """Encode TON friendly address: base64url(tag + wc + hash + crc16)."""
    tag = 0x11 if bounceable else 0x51  # bounceable vs non-bounceable mainnet
    buf = bytearray(36)
    buf[0] = tag
    buf[1] = workchain & 0xFF
    buf[2:34] = hash_bytes
    crc = crc16_xmodem(buf, 34)
    buf[34] = (crc >> 8) & 0xFF
    buf[35] = crc & 0xFF
    return base64.urlsafe_b64encode(bytes(buf)).decode().rstrip("=")


def parse_friendly_address(address: str) -> tuple:
    """Parse friendly TON address → (workchain, hash_bytes)."""
    # Pad base64
    padded = address + "=" * (4 - len(address) % 4) if len(address) % 4 else address
    data = base64.urlsafe_b64decode(padded)
    if len(data) != 36:
        raise ValueError(f"Invalid TON address length: {len(data)}")
    workchain = data[1] if data[1] < 128 else data[1] - 256  # signed byte
    hash_bytes = bytes(data[2:34])
    # Verify CRC
    crc = (data[34] << 8) | data[35]
    computed = crc16_xmodem(data, 34)
    if crc != computed:
        raise ValueError("Invalid TON address CRC")
    return workchain, hash_bytes


def parse_raw_address(raw: str) -> tuple:
    """Parse raw address '0:hex' → (workchain, hash_bytes)."""
    parts = raw.split(":")
    if len(parts) != 2:
        raise ValueError(f"Invalid raw address: {raw}")
    workchain = int(parts[0])
    hash_bytes = bytes.fromhex(parts[1])
    return workchain, hash_bytes


def to_raw(workchain: int, hash_bytes: bytes) -> str:
    """Convert to raw format: 'wc:hex'."""
    return f"{workchain}:{hash_bytes.hex()}"


def to_non_bounceable(address: str) -> str:
    """Convert any TON address to non-bounceable friendly format."""
    if ":" in address:
        wc, h = parse_raw_address(address)
    else:
        wc, h = parse_friendly_address(address)
    return encode_address(wc, h, bounceable=False)


def compute_address(state_init: Cell, workchain: int = 0) -> tuple:
    """Compute contract address from StateInit cell → (workchain, hash, friendly)."""
    h = state_init.hash
    friendly = encode_address(workchain, h, bounceable=False)
    return workchain, h, friendly
