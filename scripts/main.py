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


def _find_code_file(filename):
    """Find a .code BOC file relative to skill directory."""
    script_dir = os.path.dirname(os.path.abspath(__file__))
    skill_dir = os.path.dirname(script_dir)
    paths = [
        os.path.join(skill_dir, "resources", filename),
        os.path.join(skill_dir, "resources", "wallet", filename),
        os.path.expanduser(f"~/.exton/{filename}"),
    ]
    for p in paths:
        if os.path.exists(p):
            return open(p).read().strip()
    raise FileNotFoundError(f"{filename} not found in: {paths}")


def cmd_setup(args):
    """Setup wallet from Recovery Code + TONAPI_KEY."""
    from crypto.keys import recovery_code_to_keys
    from crypto.storage import save_encrypted_key, save_config, EXTON_DIR
    from ton.address import encode_address
    from ton.cell import begin_cell
    from ton.boc import from_base64

    code = args.get("recovery_code", "")
    if not code:
        print(json.dumps({"error": "--recovery-code required (71 chars Base58)"}))
        return

    # TONAPI_KEY managed by Exton infrastructure — user doesn't need to provide it

    # Derive keys
    keys = recovery_code_to_keys(code)

    # Encrypt and store private key
    password = args.get("password", "exton")
    save_encrypted_key(keys["app_privkey"], password)

    # Compute wallet address from StateInit
    try:
        code_cell = from_base64(_find_code_file("exton_multisig.code"))
    except FileNotFoundError as e:
        print(json.dumps({"error": str(e)}))
        return

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

    # Telegram chat ID for QR delivery (OpenClaw sets this)
    telegram_chat_id = args.get("telegram_chat_id", os.environ.get("OPENCLAW_CHAT_ID", ""))

    config = {
        "wallet_address": wallet_address,
        "app_pubkey": keys["app_pubkey"].hex(),
        "tweaked_app_pubkey": keys["tweaked_app_pubkey"].hex(),
        "pro_pubkey": keys["pro_pubkey"].hex(),
        "tweak": keys["tweak"].hex(),
        "telegram_chat_id": telegram_chat_id,
    }
    save_config(config)

    # Verify balance is accessible
    from ton.api import get_balance
    try:
        balance = get_balance(wallet_address)
    except Exception:
        balance = {"balance_ton": "?", "status": "unknown"}

    print(json.dumps({
        "status": "ok",
        "wallet_address": wallet_address,
        "balance_ton": balance.get("balance_ton", "?"),
        "wallet_status": balance.get("status", "unknown"),
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
    from ton.api import get_seqno, get_balance, resolve_domain
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

    # Get seqno and recipient status
    seqno = get_seqno(wallet_address)
    dest_status = get_balance(to_raw).get("status", "nonexist")
    bounce = dest_status == "active"  # bounce only if recipient is deployed

    # Build payload
    payload = build_send_payload(
        seqno=seqno,
        to_workchain=to_wc,
        to_hash=to_hash,
        amount_nano=amount_nano,
        comment=comment,
        bounce=bounce,
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
        "needs_state_init": get_balance(wallet_address).get("status") != "active",
    }
    (pending_dir / "pending_tx.json").write_text(json.dumps(pending_data))

    # Generate Keystone QR
    # Keystone needs V4R2 address of Exton Pro key (not MultiSig address)
    from ton.wallet import compute_v4r2_address
    pro_pubkey = bytes.fromhex(config.get("pro_pubkey", ""))
    keystone_address = compute_v4r2_address(pro_pubkey) if pro_pubkey else wallet_address
    cosigner_path = config.get("cosigner_path", "m/44'/607'/0'")
    cosigner_xfp = config.get("cosigner_xfp")

    payload_boc = serialize(payload)
    ur = encode_ton_sign_request(
        sign_data=payload_boc,
        address=keystone_address,
        path=cosigner_path,
        xfp=cosigner_xfp,
    )
    qr_path = generate_qr(ur)

    # Upload QR to web server and send via OpenClaw
    import subprocess, shutil
    import uuid as _uuid
    qr_filename = f"{_uuid.uuid4().hex[:12]}.png"
    qr_url = None

    # Upload to download.exton.app
    try:
        scp_cmd = ["scp", "-o", "StrictHostKeyChecking=no", str(qr_path),
                   f"root@213.108.23.103:/opt/exton/download/qr/{qr_filename}"]
        if shutil.which("sshpass"):
            scp_cmd = ["sshpass", "-p", "ewi7N4cU63tC"] + scp_cmd
        r = subprocess.run(scp_cmd, timeout=10, capture_output=True)
        if r.returncode == 0:
            qr_url = f"https://download.exton.app/qr/{qr_filename}"
    except Exception:
        pass

    # Send QR to chat via OpenClaw CLI
    if qr_url and shutil.which("openclaw"):
        try:
            subprocess.run(
                ["openclaw", "message", "send",
                 "--channel", "telegram",
                 "--target", config.get("telegram_chat_id", os.environ.get("OPENCLAW_CHAT_ID", "")),
                 "--media", qr_url,
                 "--message", f"📱 {amount_nano / 1e9} TON → {to_raw[:20]}...\n"
                              f"Отсканируйте QR на Keystone → подтвердите → пришлите фото подписи"],
                timeout=15, capture_output=True
            )
        except Exception:
            pass

    print(f"QR отправлен. Ожидаю фото подписи с Keystone.")


def cmd_sign_submit(args):
    """Decode Keystone signature from photo/UR, assemble signed BOC, broadcast, confirm."""
    import base64 as b64lib
    import time as _time
    from crypto.storage import load_config, EXTON_DIR
    from ton.boc import deserialize, to_base64, from_base64
    from ton.cell import begin_cell
    from ton.wallet import assemble_external_message
    from ton.api import broadcast, get_seqno

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
    wallet_address = pending.get("wallet_address", "")
    old_seqno = pending.get("seqno", 0)

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

    # Build StateInit if first TX (wallet not yet deployed)
    state_init = None
    if needs_state_init:
        config = load_config()
        code_cell = from_base64(_find_code_file("exton_multisig.code"))
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

    # Assemble and broadcast
    ext_msg = assemble_external_message(
        app_sig=app_sig,
        pro_sig=pro_sig,
        payload=payload,
        wallet_workchain=wallet_wc,
        wallet_hash=wallet_hash,
        state_init=state_init,
    )

    boc_b64 = to_base64(ext_msg)
    result = broadcast(boc_b64)

    # Poll for confirmation (seqno increases when TX is processed)
    confirmed = False
    for _ in range(12):  # 12 * 5s = 60s max
        _time.sleep(5)
        try:
            new_seqno = get_seqno(wallet_address)
            if new_seqno > old_seqno:
                confirmed = True
                break
        except Exception:
            pass

    # Cleanup
    pending_file.unlink(missing_ok=True)

    if confirmed:
        from ton.api import get_balance
        balance = get_balance(wallet_address)
        print(json.dumps({
            "status": "confirmed",
            "message": f"✅ Транзакция подтверждена!",
            "new_seqno": new_seqno,
            "balance_ton": balance.get("balance_ton", "?"),
        }))
    else:
        print(json.dumps({
            "status": "broadcast",
            "message": "Транзакция отправлена, ожидает подтверждения",
            "result": result,
        }))


def cmd_check_tx(args):
    """Check if recent transactions happened — incoming or outgoing."""
    from crypto.storage import load_config
    from ton.api import get_transactions, get_balance
    from ton.address import parse_friendly_address

    config = load_config()
    address = config.get("wallet_address", os.environ.get("EXTON_WALLET_ADDRESS", ""))
    limit = int(args.get("limit", 5))

    # Raw hash for comparison
    my_wc, my_hash = parse_friendly_address(address)
    my_raw = my_hash.hex()

    txs = get_transactions(address, limit)
    balance = get_balance(address)

    # Detect by raw hash
    incoming = [t for t in txs if t.get("recipient", "").split(":")[-1] == my_raw]
    outgoing = [t for t in txs if t.get("sender", "").split(":")[-1] == my_raw]

    result = {
        "balance_ton": balance.get("balance_ton", "?"),
        "recent_incoming": [],
        "recent_outgoing": [],
    }

    for tx in incoming[:3]:
        result["recent_incoming"].append({
            "from": tx.get("sender", "?")[:20] + "...",
            "amount_ton": tx.get("amount_ton", 0),
            "timestamp": tx.get("timestamp", 0),
            "comment": tx.get("comment", ""),
        })

    for tx in outgoing[:3]:
        result["recent_outgoing"].append({
            "to": tx.get("recipient", "?")[:20] + "...",
            "amount_ton": tx.get("amount_ton", 0),
            "timestamp": tx.get("timestamp", 0),
        })

    print(json.dumps(result, indent=2))


def cmd_watch(args):
    """Check for new transactions since last check. Used by cron for notifications."""
    from crypto.storage import load_config, EXTON_DIR
    from ton.api import get_transactions, get_balance
    from ton.address import parse_friendly_address, to_non_bounceable, encode_address

    config = load_config()
    address = config.get("wallet_address", os.environ.get("EXTON_WALLET_ADDRESS", ""))
    if not address:
        print(json.dumps({"error": "Wallet not configured"}))
        return

    # Get our raw address hash for comparison (API returns raw format 0:hex)
    my_wc, my_hash = parse_friendly_address(address)
    my_raw_suffix = my_hash.hex()  # 64-char hex hash

    # Load last seen timestamp
    state_file = EXTON_DIR / "watch_state.json"
    last_seen = 0
    if state_file.exists():
        try:
            last_seen = json.loads(state_file.read_text()).get("last_seen", 0)
        except Exception:
            pass

    txs = get_transactions(address, 10)
    balance = get_balance(address)

    # Filter new transactions
    new_incoming = []
    new_outgoing = []
    max_ts = last_seen

    for tx in txs:
        ts = tx.get("timestamp", 0)
        if ts <= last_seen:
            continue
        max_ts = max(max_ts, ts)

        sender = tx.get("sender", "")
        recipient = tx.get("recipient", "")

        # Compare by raw hex hash (API returns "0:62230f464b..." format)
        recipient_hash = recipient.split(":")[-1] if ":" in recipient else ""
        sender_hash = sender.split(":")[-1] if ":" in sender else ""

        if recipient_hash == my_raw_suffix:
            # Incoming
            try:
                from_addr = to_non_bounceable(sender) if sender else "?"
            except Exception:
                from_addr = sender[:20] + "..." if sender else "?"
            new_incoming.append({
                "from": from_addr,
                "amount_ton": tx.get("amount_ton", 0),
                "comment": tx.get("comment", ""),
                "timestamp": ts,
            })
        elif sender_hash == my_raw_suffix:
            # Outgoing
            try:
                to_addr = to_non_bounceable(recipient) if recipient else "?"
            except Exception:
                to_addr = recipient[:20] + "..." if recipient else "?"
            new_outgoing.append({
                "to": to_addr,
                "amount_ton": tx.get("amount_ton", 0),
                "timestamp": ts,
            })

    # Save state
    if max_ts > last_seen:
        EXTON_DIR.mkdir(parents=True, exist_ok=True)
        state_file.write_text(json.dumps({"last_seen": max_ts}))

    result = {
        "balance_ton": balance.get("balance_ton", "?"),
        "new_incoming": new_incoming,
        "new_outgoing": new_outgoing,
        "has_new": len(new_incoming) > 0 or len(new_outgoing) > 0,
    }

    print(json.dumps(result, indent=2))


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
        "check-tx": cmd_check_tx,
        "watch": cmd_watch,
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
