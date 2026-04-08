"""
TON Cell and CellBuilder — exact port from Kotlin Cell.kt.

Cell = basic data unit in TON: up to 1023 bits + up to 4 refs.
Hash = SHA-256 of cell representation (descriptor + data + ref depths + ref hashes).
"""

import hashlib
from typing import List, Optional


class Cell:
    """Immutable TON cell."""

    def __init__(self, data: bytes, bit_length: int, refs: Optional[List["Cell"]] = None):
        self.data = data
        self.bit_length = bit_length
        self.refs = refs or []
        self._hash: Optional[bytes] = None
        self._depth: Optional[int] = None

    @property
    def hash(self) -> bytes:
        if self._hash is None:
            self._hash = self._compute_hash()
        return self._hash

    @property
    def depth(self) -> int:
        if self._depth is None:
            if not self.refs:
                self._depth = 0
            else:
                self._depth = max(r.depth for r in self.refs) + 1
        return self._depth

    def _compute_hash(self) -> bytes:
        ref_count = len(self.refs)
        data_byte_count = (self.bit_length + 7) // 8
        rest_bits = self.bit_length % 8
        full_bytes = rest_bits == 0

        d1 = ref_count & 0xFF
        d2 = (data_byte_count * 2) if full_bytes else (data_byte_count * 2 - 1)

        # Build representation
        buf_size = 2 + data_byte_count + ref_count * (2 + 32)
        buf = bytearray(buf_size)
        pos = 0

        buf[pos] = d1; pos += 1
        buf[pos] = d2 & 0xFF; pos += 1

        if full_bytes:
            buf[pos:pos + data_byte_count] = self.data[:data_byte_count]
            pos += data_byte_count
        else:
            if data_byte_count > 1:
                buf[pos:pos + data_byte_count - 1] = self.data[:data_byte_count - 1]
                pos += data_byte_count - 1
            # Last byte with completion tag
            last = self.data[data_byte_count - 1] if data_byte_count > 0 else 0
            buf[pos] = last | (1 << (7 - rest_bits))
            pos += 1

        # Ref depths (2 bytes each, big-endian)
        for ref in self.refs:
            d = ref.depth
            buf[pos] = (d >> 8) & 0xFF; pos += 1
            buf[pos] = d & 0xFF; pos += 1

        # Ref hashes (32 bytes each)
        for ref in self.refs:
            h = ref.hash
            buf[pos:pos + 32] = h
            pos += 32

        return hashlib.sha256(bytes(buf[:pos])).digest()

    def __repr__(self):
        return f"Cell(bits={self.bit_length}, refs={len(self.refs)}, hash={self.hash[:4].hex()}...)"


class CellBuilder:
    """Builds a Cell bit by bit. MSB-first within bytes."""

    MAX_BITS = 1023
    MAX_REFS = 4

    def __init__(self):
        self._buffer = bytearray(128)  # 1023 bits → max 128 bytes
        self._bit_length = 0
        self._refs: List[Cell] = []

    def _store_bit(self, value: bool) -> "CellBuilder":
        if self._bit_length >= self.MAX_BITS:
            raise ValueError("Cell overflow: max 1023 bits")
        byte_idx = self._bit_length // 8
        bit_idx = 7 - (self._bit_length % 8)
        if value:
            self._buffer[byte_idx] |= (1 << bit_idx)
        self._bit_length += 1
        return self

    def store_uint(self, value: int, bits: int) -> "CellBuilder":
        """Store unsigned integer, big-endian, MSB first."""
        for i in range(bits - 1, -1, -1):
            self._store_bit(bool((value >> i) & 1))
        return self

    def store_int(self, value: int, bits: int) -> "CellBuilder":
        """Store signed integer (two's complement)."""
        if value < 0:
            value = (1 << bits) + value
        return self.store_uint(value, bits)

    def store_bytes(self, data: bytes) -> "CellBuilder":
        """Store raw bytes (8 bits each)."""
        for b in data:
            self.store_uint(b, 8)
        return self

    def store_coins(self, nanotons: int) -> "CellBuilder":
        """Store VarUInteger 16 (TON amount)."""
        if nanotons == 0:
            self.store_uint(0, 4)
        else:
            byte_count = (nanotons.bit_length() + 7) // 8
            self.store_uint(byte_count, 4)
            self.store_uint(nanotons, byte_count * 8)
        return self

    def store_address(self, workchain: int, hash_bytes: bytes) -> "CellBuilder":
        """Store addr_std$10 format: tag(2) + anycast(1) + wc(8) + hash(256)."""
        self.store_uint(0b10, 2)  # addr_std tag
        self._store_bit(False)     # no anycast
        self.store_int(workchain, 8)
        self.store_bytes(hash_bytes)
        return self

    def store_address_none(self) -> "CellBuilder":
        """Store addr_none$00."""
        self.store_uint(0b00, 2)
        return self

    def store_ref(self, cell: Cell) -> "CellBuilder":
        """Add a cell reference."""
        if len(self._refs) >= self.MAX_REFS:
            raise ValueError("Cell overflow: max 4 refs")
        self._refs.append(cell)
        return self

    def end_cell(self) -> Cell:
        """Finalize and return a Cell."""
        data_bytes = (self._bit_length + 7) // 8
        return Cell(
            data=bytes(self._buffer[:data_bytes]),
            bit_length=self._bit_length,
            refs=list(self._refs)
        )


def begin_cell() -> CellBuilder:
    """Create a new CellBuilder."""
    return CellBuilder()
