#!/usr/bin/env python3
"""
Exton Wallet CLI — entry point for OpenClaw skill.

Usage:
  python3 main.py setup --recovery-code "..."
  python3 main.py balance
  python3 main.py history [--limit 20]
  python3 main.py resolve <domain.ton>
  python3 main.py jettons
  python3 main.py seqno
  python3 main.py send --to <address> --amount <nanotons> [--comment "..."]
  python3 main.py plugins list
  python3 main.py plugins limits
"""

import json
import sys
import os

# Add scripts dir to path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))


def cmd_setup(args):
    """Setup wallet from Recovery Code."""
    from crypto.keys import recovery_code_to_keys
    from crypto.storage import save_encrypted_key, save_config, EXTON_DIR
    from ton.address import encode_address
    from ton.cell import begin_cell
    from ton.boc import from_base64

    code = args.get("recovery_code", "")
    if not code:
        print(json.dumps({"error": "Recovery code required"}))
        return

    keys = recovery_code_to_keys(code)

    password = args.get("password", "exton")
    save_encrypted_key(keys["app_privkey"], password)

    # Compute wallet address from StateInit
    wallet_address = ""
    for code_path in [
        os.path.expanduser("~/.exton/exton_multisig.code"),
    ]:
        if os.path.exists(code_path):
            code_cell = from_base64(open(code_path).read().strip())
            data_cell = (begin_cell()
                .store_bytes(keys["tweaked_app_pubkey"])
                .store_bytes(keys["pro_pubkey"])
                .store_uint(0, 32).store_uint(1, 32).store_uint(0, 1)
                .end_cell())
            state_init = (begin_cell()
                .store_uint(0, 1).store_uint(0, 1)
                .store_uint(1, 1).store_ref(code_cell)
                .store_uint(1, 1).store_ref(data_cell)
                .store_uint(0, 1)
                .end_cell())
            wallet_address = encode_address(0, state_init.hash, bounceable=False)
            break

    tonapi_key = args.get("tonapi_key", os.environ.get("TONAPI_KEY", ""))

    config = {
        "wallet_address": wallet_address,
        "app_pubkey": keys["app_pubkey"].hex(),
        "tweaked_app_pubkey": keys["tweaked_app_pubkey"].hex(),
        "pro_pubkey": keys["pro_pubkey"].hex(),
        "tweak": keys["tweak"].hex(),
        "tonapi_key": tonapi_key,
    }
    save_config(config)

    print(json.dumps({
        "status": "ok",
        "wallet_address": wallet_address,
        "app_pubkey": keys["app_pubkey"].hex(),
        "tweaked_app_pubkey": keys["tweaked_app_pubkey"].hex(),
        "config_dir": str(EXTON_DIR),
    }))


def cmd_balance(args):
    """Get wallet balance."""
    from crypto.storage import load_config
    from ton.api import get_balance

    config = load_config()
    address = config.get("wallet_address", "")
    if not address:
        # Use env variable as fallback
        address = os.environ.get("EXTON_WALLET_ADDRESS", "")
    if not address:
        print(json.dumps({"error": "Wallet address not configured"}))
        return

    result = get_balance(address)
    print(json.dumps(result))


def cmd_history(args):
    """Get transaction history."""
    from crypto.storage import load_config
    from ton.api import get_transactions

    config = load_config()
    address = config.get("wallet_address", os.environ.get("EXTON_WALLET_ADDRESS", ""))
    limit = int(args.get("limit", 20))

    result = get_transactions(address, limit)
    print(json.dumps(result, indent=2))


def cmd_resolve(args):
    """Resolve .ton domain."""
    from ton.api import resolve_domain

    domain = args.get("domain", "")
    if not domain:
        print(json.dumps({"error": "Domain required"}))
        return

    address = resolve_domain(domain)
    print(json.dumps({"domain": domain, "address": address}))


def cmd_jettons(args):
    """Get jetton balances."""
    from crypto.storage import load_config
    from ton.api import get_jettons

    config = load_config()
    address = config.get("wallet_address", os.environ.get("EXTON_WALLET_ADDRESS", ""))

    result = get_jettons(address)
    print(json.dumps(result, indent=2))


def cmd_seqno(args):
    """Get current seqno."""
    from crypto.storage import load_config
    from ton.api import get_seqno

    config = load_config()
    address = config.get("wallet_address", os.environ.get("EXTON_WALLET_ADDRESS", ""))

    seqno = get_seqno(address)
    print(json.dumps({"seqno": seqno}))


def cmd_plugins(args):
    """Plugin operations."""
    subcmd = args.get("subcmd", "list")
    if subcmd == "list":
        from crypto.storage import load_config
        config = load_config()
        plugins = config.get("plugins", {})
        print(json.dumps(plugins, indent=2))
    elif subcmd == "limits":
        from crypto.storage import load_config
        from ton.api import run_get_method
        config = load_config()
        plugins = config.get("plugins", {})
        result = {}
        for name, addr in plugins.items():
            try:
                if name == "daily_limit":
                    stack = run_get_method(addr, "dailyLimitInfo")
                    if len(stack) >= 3:
                        result[name] = {
                            "limit_nano": stack[0],
                            "spent_today_nano": stack[1],
                            "period_start": stack[2],
                            "remaining_nano": stack[0] - stack[1] if stack[0] > stack[1] else 0,
                        }
                elif name == "whitelist":
                    # Can't enumerate dict on-chain easily
                    result[name] = {"status": "active"}
            except Exception as e:
                result[name] = {"error": str(e)}
        print(json.dumps(result, indent=2))
    else:
        print(json.dumps({"error": f"Unknown plugin command: {subcmd}"}))


def cmd_send(args):
    """Build unsigned TX, sign app_key, generate QR for Keystone."""
    import base64 as b64lib
    from crypto.keys import recovery_code_to_keys
    from crypto.storage import load_config, load_encrypted_key, EXTON_DIR
    from ton.api import get_seqno, resolve_domain
    from ton.address import parse_friendly_address, parse_raw_address
    from ton.wallet import build_send_payload, sign_payload
    from ton.boc import serialize, from_base64
    from ton.cell import begin_cell
    from keystone.ur import encode_ton_sign_request
    from keystone.qr import generate_qr
    from pathlib import Path

    config = load_config()
    wallet_address = config.get("wallet_address", os.environ.get("EXTON_WALLET_ADDRESS", ""))
    to_raw = args.get("to", "")
    amount_nano = int(args.get("amount", 0))
    comment = args.get("comment", None)

    if not wallet_address or not to_raw or amount_nano <= 0:
        print(json.dumps({"error": "Required: --to <address> --amount <nanotons>"}))
        return

    # Resolve .ton domain if needed
    if to_raw.endswith(".ton") or to_raw.endswith(".t.me"):
        resolved = resolve_domain(to_raw)
        if not resolved:
            print(json.dumps({"error": f"Cannot resolve domain: {to_raw}"}))
            return
        to_raw = resolved

    # Parse addresses
    wc, wallet_hash = parse_friendly_address(wallet_address)
    if ":" in to_raw:
        to_wc, to_hash = parse_raw_address(to_raw)
    else:
        to_wc, to_hash = parse_friendly_address(to_raw)

    # Get seqno
    seqno = get_seqno(wallet_address)

    # Build payload
    payload = build_send_payload(
        seqno=seqno,
        to_workchain=to_wc,
        to_hash=to_hash,
        amount_nano=amount_nano,
        comment=comment,
    )

    # Load keys and sign
    tweak_hex = config.get("tweak", "")
    app_privkey = load_encrypted_key(os.environ.get("EXTON_KEY_PASSWORD", "exton"))
    app_sig = sign_payload(payload, app_privkey, tweak_hex if tweak_hex else None)

    # Save pending data for sign-submit
    pending_dir = EXTON_DIR / "pending"
    pending_dir.mkdir(parents=True, exist_ok=True)

    pending_data = {
        "payload_boc": b64lib.b64encode(serialize(payload)).decode(),
        "app_sig": b64lib.b64encode(app_sig).decode(),
        "wallet_address": wallet_address,
        "wallet_wc": wc,
        "wallet_hash": wallet_hash.hex(),
        "seqno": seqno,
        "needs_state_init": seqno == 0,
    }
    (pending_dir / "pending_tx.json").write_text(json.dumps(pending_data))

    # Generate Keystone QR
    payload_boc = serialize(payload)
    ur = encode_ton_sign_request(
        sign_data=payload_boc,
        address=wallet_address,
        path="m/44'/607'/0'",
    )
    qr_path = generate_qr(ur)

    print(json.dumps({
        "status": "pending_keystone",
        "qr_path": str(qr_path),
        "seqno": seqno,
        "amount_nano": amount_nano,
        "amount_ton": amount_nano / 1e9,
        "to": to_raw,
        "comment": comment,
    }))


def cmd_sign_submit(args):
    """Decode Keystone signature from photo/UR, assemble signed BOC, broadcast."""
    import base64 as b64lib
    from crypto.storage import load_config, EXTON_DIR
    from ton.boc import deserialize, serialize, to_base64, from_base64
    from ton.cell import begin_cell, Cell
    from ton.wallet import assemble_external_message
    from ton.api import broadcast
    from ton.address import parse_friendly_address
    from pathlib import Path

    # Load pending TX
    pending_file = EXTON_DIR / "pending" / "pending_tx.json"
    if not pending_file.exists():
        print(json.dumps({"error": "No pending transaction. Run 'send' first."}))
        return

    pending = json.loads(pending_file.read_text())
    payload = deserialize(b64lib.b64decode(pending["payload_boc"]))
    app_sig = b64lib.b64decode(pending["app_sig"])
    wallet_wc = pending["wallet_wc"]
    wallet_hash = bytes.fromhex(pending["wallet_hash"])
    needs_state_init = pending.get("needs_state_init", False)

    # Get pro signature
    photo_path = args.get("photo", "")
    ur_string = args.get("ur", "")

    if photo_path:
        from keystone.qr import decode_qr_from_image
        ur_string = decode_qr_from_image(photo_path)

    if not ur_string:
        print(json.dumps({"error": "Required: --photo <path> or --ur <string>"}))
        return

    from keystone.ur import decode_ton_signature
    _, pro_sig = decode_ton_signature(ur_string)

    # Build StateInit if first TX
    state_init = None
    if needs_state_init:
        config = load_config()
        code_b64 = open(os.path.join(os.path.dirname(__file__), '..', '..', 'resources', 'wallet', 'exton_multisig.code')).read().strip()
        # Try multiple paths for the code file
        for code_path in [
            '/Users/exme/exton/resources/wallet/exton_multisig.code',
            os.path.expanduser('~/.exton/exton_multisig.code'),
        ]:
            if os.path.exists(code_path):
                code_b64 = open(code_path).read().strip()
                break

        code_cell = from_base64(code_b64)
        tweaked_pub = bytes.fromhex(config.get("tweaked_app_pubkey", ""))
        pro_pub = bytes.fromhex(config.get("pro_pubkey", ""))

        data_cell = (begin_cell()
            .store_bytes(tweaked_pub)
            .store_bytes(pro_pub)
            .store_uint(0, 32).store_uint(1, 32).store_uint(0, 1)
            .end_cell())

        state_init = (begin_cell()
            .store_uint(0, 1).store_uint(0, 1)
            .store_uint(1, 1).store_ref(code_cell)
            .store_uint(1, 1).store_ref(data_cell)
            .store_uint(0, 1)
            .end_cell())

    # Assemble external message
    ext_msg = assemble_external_message(
        app_sig=app_sig,
        pro_sig=pro_sig,
        payload=payload,
        wallet_workchain=wallet_wc,
        wallet_hash=wallet_hash,
        state_init=state_init,
    )

    # Broadcast
    boc_b64 = to_base64(ext_msg)
    result = broadcast(boc_b64)

    # Cleanup
    pending_file.unlink(missing_ok=True)

    print(json.dumps({
        "status": "broadcast",
        "result": result,
        "boc_length": len(b64lib.b64decode(boc_b64)),
    }))


def main():
    if len(sys.argv) < 2:
        print(__doc__)
        return

    command = sys.argv[1]
    args = {}

    # Parse --key value pairs
    i = 2
    while i < len(sys.argv):
        if sys.argv[i].startswith("--"):
            key = sys.argv[i][2:].replace("-", "_")
            if i + 1 < len(sys.argv) and not sys.argv[i + 1].startswith("--"):
                args[key] = sys.argv[i + 1]
                i += 2
            else:
                args[key] = True
                i += 1
        else:
            # Positional argument
            if command == "resolve":
                args["domain"] = sys.argv[i]
            elif command == "plugins":
                args["subcmd"] = sys.argv[i]
            i += 1

    commands = {
        "setup": cmd_setup,
        "balance": cmd_balance,
        "history": cmd_history,
        "resolve": cmd_resolve,
        "jettons": cmd_jettons,
        "seqno": cmd_seqno,
        "plugins": cmd_plugins,
        "send": cmd_send,
        "sign-submit": cmd_sign_submit,
    }

    fn = commands.get(command)
    if fn:
        try:
            fn(args)
        except Exception as e:
            print(json.dumps({"error": str(e)}))
            sys.exit(1)
    else:
        print(json.dumps({"error": f"Unknown command: {command}"}))
        sys.exit(1)


if __name__ == "__main__":
    main()
