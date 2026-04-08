# Architecture

## Overview

```
OpenClaw Gateway
  |
  |--- SKILL.md (agent instructions)
  |--- scripts/run.sh → .venv/bin/python3 main.py <command>
  |
  |--- System crontab (every 1 min)
         |--- watch_cron.sh → main.py watch → openclaw message send
```

## Components

### main.py — CLI Entry Point

Single Python script, 11 commands. All output is JSON. Called by agent via `run.sh`.

| Command | Purpose | Keystone? |
|---------|---------|-----------|
| `setup` | Recovery Code → keys + config | No |
| `balance` | Account balance | No |
| `history` | Recent transactions | No |
| `jettons` | Token balances (USDT, etc.) | No |
| `seqno` | Current sequence number | No |
| `resolve` | .ton domain → address | No |
| `watch` | New transactions since last check | No |
| `check-tx` | Recent incoming/outgoing | No |
| `send` | Build TX → sign app_key → QR | No (generates QR) |
| `sign-submit` | Decode signature → broadcast | No (uses photo) |
| `plugins` | List/limits of installed plugins | No |

### Transaction Flow

```
1. Agent calls: run.sh send --to <addr> --amount <nano>
   |
   ├── Get seqno from TON API
   ├── Check recipient status (bounce=false if uninit)
   ├── Build internal message (exact V4R2 format)
   ├── Build signing payload (wallet_id + valid_until + seqno + op + mode + ref)
   ├── Sign with tweaked Ed25519 (exton_app_key + vanity tweak)
   ├── Encode payload → Keystone UR format → QR PNG
   ├── Upload QR to api.exton.app/qr/upload → CDN URL
   └── Send QR image to Telegram via openclaw message send

2. User scans QR with Keystone 3 Pro
   ├── Keystone shows TX details on its screen
   ├── User confirms with physical button
   └── Keystone displays signature QR

3. User photographs Keystone screen → sends to chat

4. Agent calls: run.sh sign-submit --photo <path>
   ├── Decode QR from photo (pyzbar)
   ├── Parse UR → extract Ed25519 signature
   ├── Assemble: app_sig + pro_sig + payload → signed BOC
   ├── Broadcast via api.exton.app proxy → TON network
   └── Poll seqno for confirmation (up to 60 seconds)
```

### Key Derivation

```
Recovery Code (71 chars Base58)
  → Base58 decode → 52 bytes
  → Split: app_secret(12) + tweak(8) + pro_pubkey(32)

app_seed = SHA-256(app_secret || "exton-multisig-v1")
app_keypair = Ed25519(app_seed)  // seed directly, NOT SLIP-0010
tweaked_pubkey = app_pubkey + tweak * G  // Ed25519 point addition
```

### Signing with Tweak

Standard Ed25519 modified for vanity addresses:

```
expanded = SHA-512(seed)
scalar = clamp(expanded[0:32])
nonce_prefix = expanded[32:64]
tweaked_scalar = (scalar + tweak) mod L

Sign(message):
  r = SHA-512(nonce_prefix || message) mod L
  R = r * G
  k = SHA-512(R || tweaked_pubkey || message) mod L
  S = (r + k * tweaked_scalar) mod L
  signature = R || S  // 64 bytes
```

### API Proxy

All TON blockchain requests go through `api.exton.app`:

```
Skill → api.exton.app/ton/v2/... → tonapi.io (with server-side API key)
```

Users never need a TONAPI_KEY. Rate limited: 60 req/min per IP.

### File Storage

```
~/.exton/
  config.json       — wallet address, public keys, tweak (no secrets)
  app_key.enc       — AES-256-GCM encrypted private key
  watch_state.json  — last seen transaction timestamp
  pending/          — temporary files during TX signing
```

### Watch/Notifications

System crontab runs `watch_cron.sh` every minute:

1. Calls `main.py watch` — checks new TXs via API
2. If new transactions found → formats notification text
3. Sends via `openclaw message send --channel telegram`

Zero AI tokens consumed. Only one HTTP request per minute to API proxy.
