# EXME Wallet — OpenClaw Skill

Manage your [EXME](https://exme.org) TON crypto wallet through an AI agent. Sign transactions with Keystone 3 Pro hardware wallet — your private key never leaves the device.

## Quick Start

```bash
git clone https://github.com/exmedev/exme-wallet-skill.git \
  ~/.openclaw/skills/exme-wallet

bash ~/.openclaw/skills/exme-wallet/scripts/install.sh
```

Start a new session (`/new`) and say: **"Connect my EXME wallet"**

The agent will ask for your Recovery Code (from EXME Android app: Settings > Cortex > Recovery Code). That's it.

## Features

| Feature | Keystone Required? |
|---------|--------------------|
| Balance, history, jettons | No |
| Resolve .ton domains | No |
| Transaction notifications | No (automatic) |
| Send TON | Yes (QR in chat) |

## How Signing Works

```
You: "Send 100 TON to wallet.ton"

Agent: [QR image in chat]
       "Scan with Keystone 3 Pro"

You: [photo of Keystone signature screen]

Agent: "Sent 100 TON. Hash: abc123..."
```

Three messages. Everything in chat. Private key never leaves Keystone.

## Transaction Notifications

Incoming and outgoing transactions are monitored every minute after install. Notifications arrive in Telegram with zero AI token cost.

## Updating

```bash
bash ~/.openclaw/skills/exme-wallet/scripts/update.sh
```

## Security

- Private key stays in Keystone Secure Element
- Recovery Code encrypted with AES-256-GCM on disk
- All API calls through EXME proxy (no user API keys needed)
- Keystone shows transaction details on its own screen

## Requirements

- Python 3.9+
- [OpenClaw](https://github.com/openclaw/openclaw) with Telegram channel
- [Keystone 3 Pro](https://keyst.one) hardware wallet
- [EXME Wallet](https://download.exme.org) Android app

## Architecture

See [ARCHITECTURE.md](ARCHITECTURE.md) for technical details.

## License

MIT License. See [LICENSE](LICENSE).
