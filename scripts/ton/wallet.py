"""
Exton MultiSig transaction builder — exact port from Kotlin ExtonMultiSigContract.kt.

Builds unsigned payloads, signs with exton_app_key, assembles with both signatures.
"""

import time
from .cell import Cell, CellBuilder, begin_cell
from . import boc

WALLET_ID = 0x29A9A317  # 698983191
DEFAULT_VALID_SECONDS = 300  # 5 minutes
# Standard TON V4R2 wallet contract code (from WalletV4R2.kt)
# Keystone stores keys indexed by V4R2 address — this code is needed to compute that address.
V4R2_CODE_BOC = "te6cckECFAEAAtQAART/APSkE/S88sgLAQIBIAIDAgFIBAUE+PKDCNcYINMf0x/THwL4I7vyZO1E0NMf0x/T//QE0VFDuvKhUVG68qIF+QFUEGT5EPKj+AAkpMjLH1JAyx9SMMv/UhD0AMntVPgPAdMHIcAAn2xRkyDXSpbTB9QC+wDoMOAhwAHjACHAAuMAAcADkTDjDQOkyMsfEssfy/8QERITAubQAdDTAyFxsJJfBOAi10nBIJJfBOAC0x8hghBwbHVnvSKCEGRzdHK9sJJfBeAD+kAwIPpEAcjKB8v/ydDtRNCBAUDXIfQEMFyBAQj0Cm+hMbOSXwfgBdM/yCWCEHBsdWe6kjgw4w0DghBkc3RyupJfBuMNBgcCASAICQB4AfoA9AQw+CdvIjBQCqEhvvLgUIIQcGx1Z4MesXCAGFAEywUmzxZY+gIZ9ADLaRfLH1Jgyz8gyYBA+wAGAIpQBIEBCPRZMO1E0IEBQNcgyAHPFvQAye1UAXKwjiOCEGRzdHKDHrFwgBhQBcsFUAPPFiP6AhPLassfyz/JgED7AJJfA+ICASAKCwBZvSQrb2omhAgKBrkPoCGEcNQICEekk30pkQzmkD6f+YN4EoAbeBAUiYcVnzGEAgFYDA0AEbjJftRNDXCx+AA9sp37UTQgQFA1yH0BDACyMoHy//J0AGBAQj0Cm+hMYAIBIA4PABmtznaiaEAga5Drhf/AABmvHfaiaEAQa5DrhY/AAG7SB/oA1NQi+QAFyMoHFcv/ydB3dIAYyMsFywIizxZQBfoCFMtrEszMyXP7AMhAFIEBCPRR8qcCAHCBAQjXGPoA0z/IVCBHgQEI9FHyp4IQbm90ZXB0gBjIywXLAlAGzxZQBPoCFMtqEssfyz/Jc/sAAgBsgQEI1xj6ANM/MFIkgQEI9Fnyp4IQZHN0cnB0gBjIywXLAlAFzxZQA/oCE8tqyx8Syz/Jc/sAAAr0AMntVGliJeU="


def compute_v4r2_address(pubkey: bytes) -> str:
    """Compute V4R2 wallet address for a pubkey.
    Keystone stores keys indexed by V4R2 address — this is how it finds the signing key.
    Uses standard V4R2 contract code (NOT Exton contract).
    """
    from . import address as addr_mod

    v4r2_code = boc.from_base64(V4R2_CODE_BOC)

    # V4R2 data cell: seqno(0,32) + wallet_id(32) + pubkey(256) + plugin_dict(0,1)
    data_cell = (begin_cell()
                 .store_uint(0, 32)
                 .store_uint(WALLET_ID, 32)
                 .store_bytes(pubkey)
                 .store_uint(0, 1)
                 .end_cell())

    state_init = (begin_cell()
                  .store_uint(0, 1)
                  .store_uint(0, 1)
                  .store_uint(1, 1).store_ref(v4r2_code)
                  .store_uint(1, 1).store_ref(data_cell)
                  .store_uint(0, 1)
                  .end_cell())

    return addr_mod.encode_address(0, state_init.hash, bounceable=False)


def build_state_init(app_pubkey: bytes, pro_pubkey: bytes, code_boc: bytes) -> Cell:
    """Build Exton MultiSig StateInit cell."""
    code_cell = Cell.from_boc(code_boc) if hasattr(Cell, "from_boc") else _parse_code(code_boc)

    data = (begin_cell()
            .store_bytes(app_pubkey)     # 256 bits
            .store_bytes(pro_pubkey)     # 256 bits
            .store_uint(0, 32)           # seqno = 0
            .store_uint(1, 32)           # code_version = 1
            .store_uint(0, 1)            # has_plugins = false
            .end_cell())

    state_init = (begin_cell()
                  .store_uint(0, 1)      # split_depth = false
                  .store_uint(0, 1)      # special = false
                  .store_uint(1, 1)      # code present = true
                  .store_ref(code_cell)
                  .store_uint(1, 1)      # data present = true
                  .store_ref(data)
                  .store_uint(0, 1)      # lib dict = false
                  .end_cell())

    return state_init


def _parse_code(code_boc: bytes) -> Cell:
    """Minimal BOC parser to extract code cell."""
    # Use the boc module for proper deserialization
    # For now, create a raw cell from BOC bytes
    from . import boc as boc_mod
    # Simple approach: the BOC IS the code cell
    # We need proper deserialization — for now, use a placeholder
    return Cell(data=code_boc, bit_length=len(code_boc) * 8)


def _build_internal_message(
    to_workchain: int,
    to_hash: bytes,
    amount_nano: int,
    bounce: bool = True,
    comment: str = None,
) -> Cell:
    """Build internal message cell. Exact port from Kotlin WalletV4R2.buildInternalMessage()."""
    b = begin_cell()
    b._store_bit(False)       # int_msg_info tag: 0
    b._store_bit(True)        # ihr_disabled
    b._store_bit(bounce)      # bounce
    b._store_bit(False)       # bounced
    b.store_address_none()    # src: addr_none
    b.store_address(to_workchain, to_hash)  # destination
    b.store_coins(amount_nano)
    b._store_bit(False)       # empty extra currencies
    b.store_coins(0)          # ihr_fee
    b.store_coins(0)          # fwd_fee
    b.store_uint(0, 64)       # created_lt
    b.store_uint(0, 32)       # created_at
    b._store_bit(False)       # init: Nothing

    if comment:
        b._store_bit(True)    # body as reference
        comment_cell = (begin_cell()
                        .store_uint(0, 32)
                        .store_bytes(comment.encode("utf-8"))
                        .end_cell())
        b.store_ref(comment_cell)
    else:
        b._store_bit(False)   # body inline empty

    return b.end_cell()


def build_send_payload(
    seqno: int,
    to_workchain: int,
    to_hash: bytes,
    amount_nano: int,
    comment: str = None,
    valid_until: int = None,
    bounce: bool = True,
    mode: int = 3,
) -> Cell:
    """Build signing payload for a single TON transfer (Op 0).
    Exact port from Kotlin ExtonMultiSigContract.buildUnsignedTransfer()."""
    if valid_until is None:
        valid_until = int(time.time()) + DEFAULT_VALID_SECONDS

    internal_msg = _build_internal_message(
        to_workchain=to_workchain,
        to_hash=to_hash,
        amount_nano=amount_nano,
        bounce=bounce,
        comment=comment,
    )

    # Signing payload: wallet_id + valid_until + seqno + op + mode + ref(msg)
    payload = (begin_cell()
               .store_uint(WALLET_ID, 32)
               .store_uint(valid_until, 32)
               .store_uint(seqno, 32)
               .store_uint(0, 8)         # op = 0 (send)
               .store_uint(mode, 8)      # mode
               .store_ref(internal_msg)
               .end_cell())

    return payload


def build_install_plugin_payload(
    seqno: int,
    plugin_workchain: int,
    plugin_hash: bytes,
    valid_until: int = None,
) -> Cell:
    """Build signing payload for InstallPlugin (Op 4)."""
    if valid_until is None:
        valid_until = int(time.time()) + DEFAULT_VALID_SECONDS

    payload = (begin_cell()
               .store_uint(WALLET_ID, 32)
               .store_uint(valid_until, 32)
               .store_uint(seqno, 32)
               .store_uint(4, 8)                   # op = 4 (install plugin)
               .store_int(plugin_workchain, 8)     # plugin wc (signed)
               .store_bytes(plugin_hash)            # plugin address hash (256 bits)
               .end_cell())

    return payload


def build_remove_plugin_payload(
    seqno: int,
    plugin_hash: bytes,
    valid_until: int = None,
) -> Cell:
    """Build signing payload for RemovePlugin (Op 5)."""
    if valid_until is None:
        valid_until = int(time.time()) + DEFAULT_VALID_SECONDS

    payload = (begin_cell()
               .store_uint(WALLET_ID, 32)
               .store_uint(valid_until, 32)
               .store_uint(seqno, 32)
               .store_uint(5, 8)         # op = 5 (remove plugin)
               .store_bytes(plugin_hash)  # plugin address hash (256 bits)
               .end_cell())

    return payload


def sign_payload(payload: Cell, app_privkey: bytes, tweak_hex: str = None) -> bytes:
    """Sign payload cell hash with exton_app_key → 64-byte signature.

    If tweak_hex is provided, uses tweaked Ed25519 signing (vanity wallet).
    Otherwise uses standard Ed25519.
    """
    msg = payload.hash
    if tweak_hex:
        from crypto.tweaked_signer import prepare_vanity_signing_key, sign_tweaked
        tweaked_scalar, nonce_prefix, pub = prepare_vanity_signing_key(app_privkey, tweak_hex)
        return sign_tweaked(tweaked_scalar, nonce_prefix, pub, msg)
    else:
        from crypto.ed25519 import sign
        return sign(msg, app_privkey)


def assemble_external_message(
    app_sig: bytes,
    pro_sig: bytes,
    payload: Cell,
    wallet_workchain: int,
    wallet_hash: bytes,
    state_init: Cell = None,
) -> Cell:
    """Assemble signed external message for Exton MultiSig.

    If state_init is provided (first TX, wallet uninit), includes it.
    """
    # Pro signature cell
    pro_sig_cell = begin_cell().store_bytes(pro_sig).end_cell()

    # External message body: app_sig(512) + ref(pro_sig) + ref(payload)
    body = (begin_cell()
            .store_bytes(app_sig)      # 512 bits (64 bytes)
            .store_ref(pro_sig_cell)   # ref[0]: cosigner sig
            .store_ref(payload)        # ref[1]: signing payload
            .end_cell())

    # External message wrapper
    msg = begin_cell()
    msg.store_uint(0b10, 2)          # ext_in_msg_info$10
    msg.store_address_none()          # src: none
    msg.store_address(wallet_workchain, wallet_hash)  # dest: wallet
    msg.store_uint(0, 4)              # import_fee = 0

    if state_init:
        msg.store_uint(1, 1)          # StateInit present
        msg.store_uint(1, 1)          # StateInit as ref
        msg.store_ref(state_init)
    else:
        msg.store_uint(0, 1)          # no StateInit

    msg.store_uint(1, 1)              # body as ref
    msg.store_ref(body)

    return msg.end_cell()


def external_message_to_boc(ext_msg: Cell) -> str:
    """Serialize external message to base64 BOC for broadcasting."""
    return boc.to_base64(ext_msg)
