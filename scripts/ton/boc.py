"""
BOC (Bag of Cells) serializer/deserializer.
Exact port from Kotlin BOCSerializer.kt — byte-for-byte compatible.
"""

import base64
from collections import OrderedDict
from .cell import Cell

BOC_MAGIC = bytes([0xB5, 0xEE, 0x9C, 0x72])


# ═══════════════════════════════════════════════
# Helpers
# ═══════════════════════════════════════════════

def _bytes_for_int(value: int) -> int:
    if value <= 0xFF:
        return 1
    elif value <= 0xFFFF:
        return 2
    elif value <= 0xFFFFFF:
        return 3
    return 4


def _append_int(buf: bytearray, value: int, size: int):
    for i in range(size - 1, -1, -1):
        buf.append((value >> (i * 8)) & 0xFF)


def _read_int(data: bytes, offset: int, size: int) -> int:
    result = 0
    for i in range(size):
        result = (result << 8) | (data[offset + i] & 0xFF)
    return result


# ═══════════════════════════════════════════════
# Serialize
# ═══════════════════════════════════════════════

def _serialize_cell_data(cell: Cell, hash_to_index: dict, ref_size: int) -> bytes:
    """Serialize a single cell's data + ref indices. Exact Kotlin port."""
    ref_count = len(cell.refs)
    data_byte_count = (cell.bit_length + 7) // 8
    rest_bits = cell.bit_length % 8
    full_bytes = rest_bits == 0

    d1 = ref_count
    d2 = (data_byte_count * 2) if full_bytes else (data_byte_count * 2 - 1)

    result = bytearray()
    result.append(d1)
    result.append(d2)

    if full_bytes:
        result.extend(cell.data[:data_byte_count])
    else:
        result.extend(cell.data[:data_byte_count - 1])
        last_byte = cell.data[data_byte_count - 1] if len(cell.data) >= data_byte_count else 0
        tag_bit = 1 << (7 - rest_bits)
        mask = (0xFF << (8 - rest_bits)) & 0xFF
        result.append((last_byte & mask) | tag_bit)

    for ref in cell.refs:
        _append_int(result, hash_to_index[ref.hash.hex()], ref_size)

    return bytes(result)


def serialize(root: Cell) -> bytes:
    """Serialize cell tree to BOC format. Exact Kotlin port."""
    # Flatten (BFS, deduplicate by hash)
    all_cells = []
    hash_to_index = OrderedDict()
    queue = [root]

    while queue:
        cell = queue.pop(0)
        key = cell.hash.hex()
        if key in hash_to_index:
            continue
        hash_to_index[key] = len(all_cells)
        all_cells.append(cell)
        queue.extend(cell.refs)

    cell_count = len(all_cells)
    ref_size = _bytes_for_int(cell_count)

    # Serialize each cell
    cell_datas = [_serialize_cell_data(c, hash_to_index, ref_size) for c in all_cells]
    total_data_size = sum(len(d) for d in cell_datas)
    offset_size = _bytes_for_int(total_data_size)

    # Build BOC
    boc = bytearray()
    boc.extend(BOC_MAGIC)

    # Flags: has_idx=0, has_crc32=0, has_cache_bits=0, flags=0, ref_size
    boc.append(ref_size)
    boc.append(offset_size)

    _append_int(boc, cell_count, ref_size)
    _append_int(boc, 1, ref_size)  # root_count = 1
    _append_int(boc, 0, ref_size)  # absent = 0
    _append_int(boc, total_data_size, offset_size)

    # Root index
    _append_int(boc, hash_to_index[root.hash.hex()], ref_size)

    # Cell data
    for cd in cell_datas:
        boc.extend(cd)

    return bytes(boc)


def to_base64(root: Cell) -> str:
    """Serialize cell to BOC → base64."""
    return base64.b64encode(serialize(root)).decode()


# ═══════════════════════════════════════════════
# Deserialize
# ═══════════════════════════════════════════════

def deserialize(data: bytes) -> Cell:
    """Deserialize BOC → root Cell. Exact port from Kotlin BOCSerializer.deserializeAll()."""
    if len(data) < 6 or data[:4] != BOC_MAGIC:
        raise ValueError("Invalid BOC magic")

    pos = 4
    flag_byte = data[pos] & 0xFF; pos += 1
    has_idx = (flag_byte & 0x80) != 0
    ref_size = flag_byte & 0x07
    off_size = data[pos] & 0xFF; pos += 1

    cell_count = _read_int(data, pos, ref_size); pos += ref_size
    root_count = _read_int(data, pos, ref_size); pos += ref_size
    _absent = _read_int(data, pos, ref_size); pos += ref_size
    _total_data = _read_int(data, pos, off_size); pos += off_size

    # Root indices
    root_indices = []
    for _ in range(root_count):
        root_indices.append(_read_int(data, pos, ref_size))
        pos += ref_size

    # Skip index table if present
    if has_idx:
        pos += cell_count * off_size

    # Parse raw cells
    raw_cells = []  # (bits, bit_len, ref_indices)
    for _ in range(cell_count):
        d1 = data[pos] & 0xFF; pos += 1
        d2 = data[pos] & 0xFF; pos += 1

        ref_count = d1 & 0x07
        data_byte_len = (d2 + 1) // 2
        is_full_bytes = (d2 & 1) == 0

        # Compute bit length
        if is_full_bytes:
            bit_len = data_byte_len * 8
        elif data_byte_len > 0:
            last_byte = data[pos + data_byte_len - 1] & 0xFF
            if last_byte == 0:
                bit_len = (data_byte_len - 1) * 8
            else:
                trailing = 0
                b = last_byte
                while (b & 1) == 0 and trailing < 8:
                    trailing += 1
                    b >>= 1
                bit_len = data_byte_len * 8 - trailing - 1
        else:
            bit_len = 0

        # Copy cell data
        cell_bits = bytearray(data[pos:pos + data_byte_len])

        # Strip completion tag from last byte
        if not is_full_bytes and data_byte_len > 0:
            rest_bits = bit_len % 8
            if rest_bits > 0:
                mask = (0xFF << (8 - rest_bits)) & 0xFF
                cell_bits[-1] = cell_bits[-1] & mask
            else:
                cell_bits[-1] = 0

        pos += data_byte_len

        # Ref indices
        ref_indices = []
        for _ in range(ref_count):
            ref_indices.append(_read_int(data, pos, ref_size))
            pos += ref_size

        raw_cells.append((bytes(cell_bits), bit_len, ref_indices))

    # Build Cell objects bottom-up
    built = [None] * cell_count
    for i in range(cell_count - 1, -1, -1):
        bits, bit_len, ref_idxs = raw_cells[i]
        refs = [built[ri] for ri in ref_idxs]
        built[i] = Cell(data=bits, bit_length=bit_len, refs=refs)

    return built[root_indices[0]]


def from_base64(b64: str) -> Cell:
    """Deserialize base64 BOC → root Cell."""
    return deserialize(base64.b64decode(b64))
