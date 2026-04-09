"""
Keystone UR protocol: CBOR encoding + Bytewords for ton-sign-request / ton-signature.
Exact port from Kotlin KeystoneUR.kt.
"""

import struct
import uuid
import zlib


# ═══════════════════════════════════════════════
# CBOR Encoder (RFC 8949, minimal subset)
# ═══════════════════════════════════════════════

class CBOREncoder:
    def __init__(self):
        self._buf = bytearray()

    def _write_header(self, major: int, value: int):
        mt = major << 5
        if value <= 23:
            self._buf.append(mt | value)
        elif value <= 0xFF:
            self._buf.append(mt | 24)
            self._buf.append(value)
        elif value <= 0xFFFF:
            self._buf.append(mt | 25)
            self._buf.extend(struct.pack(">H", value))
        elif value <= 0xFFFFFFFF:
            self._buf.append(mt | 26)
            self._buf.extend(struct.pack(">I", value))
        else:
            self._buf.append(mt | 27)
            self._buf.extend(struct.pack(">Q", value))

    def write_uint(self, value: int):
        self._write_header(0, value)

    def write_bytes(self, data: bytes):
        self._write_header(2, len(data))
        self._buf.extend(data)

    def write_text(self, text: str):
        utf8 = text.encode("utf-8")
        self._write_header(3, len(utf8))
        self._buf.extend(utf8)

    def write_array_header(self, count: int):
        self._write_header(4, count)

    def write_map_header(self, count: int):
        self._write_header(5, count)

    def write_tag(self, tag: int):
        self._write_header(6, tag)

    def write_bool(self, value: bool):
        self._buf.append(0xF5 if value else 0xF4)

    def to_bytes(self) -> bytes:
        return bytes(self._buf)


# ═══════════════════════════════════════════════
# CBOR Decoder (minimal subset)
# ═══════════════════════════════════════════════

class CBORDecoder:
    def __init__(self, data: bytes):
        self.data = data
        self.pos = 0

    def _read_uint_value(self) -> int:
        b = self.data[self.pos] & 0xFF
        additional = b & 0x1F
        self.pos += 1
        if additional <= 23:
            return additional
        elif additional == 24:
            v = self.data[self.pos] & 0xFF
            self.pos += 1
            return v
        elif additional == 25:
            v = struct.unpack_from(">H", self.data, self.pos)[0]
            self.pos += 2
            return v
        elif additional == 26:
            v = struct.unpack_from(">I", self.data, self.pos)[0]
            self.pos += 4
            return v
        elif additional == 27:
            v = struct.unpack_from(">Q", self.data, self.pos)[0]
            self.pos += 8
            return v
        raise ValueError(f"Invalid CBOR additional: {additional}")

    def read_item(self):
        if self.pos >= len(self.data):
            raise ValueError("Unexpected end of CBOR")
        b = self.data[self.pos] & 0xFF
        major = b >> 5

        if major == 0:  # unsigned int
            return self._read_uint_value()
        elif major == 1:  # negative int
            return -(self._read_uint_value() + 1)
        elif major == 2:  # bytes
            length = self._read_uint_value()
            result = self.data[self.pos:self.pos + length]
            self.pos += length
            return bytes(result)
        elif major == 3:  # text
            length = self._read_uint_value()
            result = self.data[self.pos:self.pos + length].decode("utf-8")
            self.pos += length
            return result
        elif major == 4:  # array
            count = self._read_uint_value()
            return [self.read_item() for _ in range(count)]
        elif major == 5:  # map
            count = self._read_uint_value()
            m = {}
            for _ in range(count):
                key = self.read_item()
                val = self.read_item()
                m[key] = val
            return m
        elif major == 6:  # tag
            self._read_uint_value()  # tag value (skip)
            return self.read_item()  # unwrap
        elif major == 7:  # simple
            additional = b & 0x1F
            self.pos += 1
            if additional == 20:
                return False
            elif additional == 21:
                return True
            return None
        raise ValueError(f"Unknown CBOR major: {major}")

    def read_top_level_map(self) -> dict:
        # Skip outer tags
        while self.pos < len(self.data):
            major = (self.data[self.pos] & 0xFF) >> 5
            if major == 6:
                self._read_uint_value()  # skip tag
            else:
                break
        return self.read_item()


# ═══════════════════════════════════════════════
# Bytewords (BCR-2020-012, minimal style)
# ═══════════════════════════════════════════════

WORDS = [
    "able", "acid", "also", "apex", "aqua", "arch", "atom", "aunt",
    "away", "axis", "back", "bald", "barn", "belt", "beta", "bias",
    "blue", "body", "brag", "brew", "bulb", "buzz", "calm", "cash",
    "cats", "chef", "city", "claw", "code", "cola", "cook", "cost",
    "crux", "curl", "cusp", "cyan", "dark", "data", "days", "deli",
    "dice", "diet", "door", "down", "draw", "drop", "drum", "dull",
    "duty", "each", "easy", "echo", "edge", "epic", "even", "exam",
    "exit", "eyes", "fact", "fair", "fern", "figs", "film", "fish",
    "fizz", "flap", "flew", "flux", "foxy", "free", "frog", "fuel",
    "fund", "gala", "game", "gear", "gems", "gift", "girl", "glow",
    "good", "gray", "grim", "guru", "gush", "gyro", "half", "hang",
    "hard", "hawk", "heat", "help", "high", "hill", "holy", "hope",
    "horn", "huts", "iced", "idea", "idle", "inch", "inky", "into",
    "iris", "iron", "item", "jade", "jazz", "join", "jolt", "jowl",
    "judo", "jugs", "jump", "junk", "jury", "keep", "keno", "kept",
    "keys", "kick", "kiln", "king", "kite", "kiwi", "knob", "lamb",
    "lava", "lazy", "leaf", "legs", "liar", "limp", "lion", "list",
    "logo", "loud", "love", "luau", "luck", "lung", "main", "many",
    "math", "maze", "memo", "menu", "meow", "mild", "mint", "miss",
    "monk", "nail", "navy", "need", "news", "next", "noon", "note",
    "numb", "obey", "oboe", "omit", "onyx", "open", "oval", "owls",
    "paid", "part", "peck", "play", "plus", "poem", "pool", "pose",
    "puff", "puma", "purr", "quad", "quiz", "race", "ramp", "real",
    "redo", "rich", "road", "rock", "roof", "ruby", "ruin", "runs",
    "rust", "safe", "saga", "scar", "sets", "silk", "skew", "slot",
    "soap", "solo", "song", "stub", "surf", "swan", "taco", "task",
    "taxi", "tent", "tied", "time", "tiny", "toil", "tomb", "toys",
    "trip", "tuna", "twin", "ugly", "undo", "unit", "urge", "user",
    "vast", "very", "veto", "vial", "vibe", "view", "visa", "void",
    "vows", "wall", "wand", "warm", "wasp", "wave", "waxy", "webs",
    "what", "when", "whiz", "wolf", "work", "yank", "yawn", "yell",
    "yoga", "yurt", "zaps", "zero", "zest", "zinc", "zone", "zoom",
]

MINIMAL = [w[0] + w[-1] for w in WORDS]
MINIMAL_REVERSE = {pair: idx for idx, pair in enumerate(MINIMAL)}


def _crc32_bytes(data: bytes) -> bytes:
    crc = zlib.crc32(data) & 0xFFFFFFFF
    return struct.pack(">I", crc)


def bytewords_encode(data: bytes) -> str:
    checksum = _crc32_bytes(data)
    combined = data + checksum
    return "".join(MINIMAL[b] for b in combined)


def bytewords_decode(encoded: str) -> bytes:
    lower = encoded.lower()
    if len(lower) % 2 != 0:
        raise ValueError("Invalid bytewords length")
    raw = bytearray()
    for i in range(0, len(lower), 2):
        pair = lower[i:i + 2]
        idx = MINIMAL_REVERSE.get(pair)
        if idx is None:
            raise ValueError(f"Invalid bytewords pair: '{pair}'")
        raw.append(idx)
    if len(raw) < 4:
        raise ValueError("Bytewords data too short")
    payload = bytes(raw[:-4])
    checksum = bytes(raw[-4:])
    expected = _crc32_bytes(payload)
    if checksum != expected:
        raise ValueError("Bytewords CRC32 mismatch")
    return payload


# ═══════════════════════════════════════════════
# ton-sign-request encoding (Exton → Keystone)
# ═══════════════════════════════════════════════

def parse_crypto_hdkey(ur_string: str) -> dict:
    """Parse crypto-hdkey UR from Keystone → public key + path + xfp.

    Returns dict with:
      pubkey: bytes (32 bytes Ed25519)
      path: str or None ("m/44'/607'/0'")
      xfp: str or None ("73C5DA0A")
      name: str or None
    """
    lower = ur_string.lower()
    prefix = "ur:crypto-hdkey/"
    if not lower.startswith(prefix):
        raise ValueError(f"Expected ur:crypto-hdkey, got: {ur_string[:30]}")
    body = ur_string[len(prefix):]
    cbor_data = bytewords_decode(body)

    decoder = CBORDecoder(cbor_data)
    m = decoder.read_top_level_map()

    # Key 3: public key (32 bytes, required)
    pubkey = m.get(3)
    if not isinstance(pubkey, bytes) or len(pubkey) != 32:
        raise ValueError(f"Missing or invalid public key (CBOR key 3)")

    # Key 6: origin (keypath + XFP)
    path = None
    xfp = None
    origin = m.get(6)
    if isinstance(origin, dict):
        # Key 6.1: derivation path components array
        components = origin.get(1)
        if isinstance(components, list):
            parts = ["m"]
            i = 0
            while i + 1 < len(components):
                index = components[i]
                hardened = components[i + 1]
                if isinstance(index, int):
                    parts.append(f"{index}'" if hardened else str(index))
                i += 2
            path = "/".join(parts)
        # Key 6.2: XFP (uint32)
        fp = origin.get(2)
        if isinstance(fp, int):
            xfp = f"{fp:08X}"

    # Key 9: account name
    name = m.get(9)

    return {
        "pubkey": pubkey,
        "path": path,
        "xfp": xfp,
        "name": name if isinstance(name, str) else None,
    }


def encode_ton_sign_request(
    sign_data: bytes,
    address: str,
    request_id: bytes = None,
    data_type: int = 1,  # 1=Transaction, 2=SignProof
    path: str = None,
    xfp: str = None,
) -> str:
    """Encode a TON sign request as UR string for Keystone QR."""
    if request_id is None:
        request_id = uuid.uuid4().bytes

    cbor = CBOREncoder()
    has_path = path is not None
    cbor.write_map_header(6 if has_path else 5)

    # 1: request_id = tagged(37, bytes(16))
    cbor.write_uint(1)
    cbor.write_tag(37)
    cbor.write_bytes(request_id)

    # 2: sign_data
    cbor.write_uint(2)
    cbor.write_bytes(sign_data)

    # 3: data_type
    cbor.write_uint(3)
    cbor.write_uint(data_type)

    # 4: derivation_path [optional]
    if path:
        cbor.write_uint(4)
        cbor.write_tag(304)
        parts = path.split("/")[1:]  # skip "m"
        has_xfp = xfp is not None
        cbor.write_map_header(2 if has_xfp else 1)
        cbor.write_uint(1)
        cbor.write_array_header(len(parts) * 2)
        for part in parts:
            hardened = part.endswith("'")
            index = int(part.rstrip("'"))
            cbor.write_uint(index)
            cbor.write_bool(hardened)
        if has_xfp:
            cbor.write_uint(2)
            cbor.write_uint(int(xfp, 16))

    # 5: address
    cbor.write_uint(5)
    cbor.write_text(address)

    # 6: origin
    cbor.write_uint(6)
    cbor.write_text("Tonkeeper")  # Keystone recognizes this

    body = bytewords_encode(cbor.to_bytes())
    return f"ur:ton-sign-request/{body}"


# ═══════════════════════════════════════════════
# ton-signature decoding (Keystone → Exton)
# ═══════════════════════════════════════════════

def decode_ton_signature(ur_string: str) -> tuple:
    """Decode a ton-signature UR string → (request_id_bytes, signature_64bytes)."""
    lower = ur_string.lower()
    prefix = "ur:ton-signature/"
    if not lower.startswith(prefix):
        raise ValueError(f"Expected ur:ton-signature, got: {ur_string[:30]}")
    body = ur_string[len(prefix):]
    cbor_data = bytewords_decode(body)

    decoder = CBORDecoder(cbor_data)
    m = decoder.read_top_level_map()

    request_id = m.get(1, b"\x00" * 16)
    signature = m.get(2)
    if signature is None or len(signature) != 64:
        raise ValueError(f"Expected 64-byte signature, got {len(signature) if signature else 'None'}")

    return request_id, signature
