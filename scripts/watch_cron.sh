#!/bin/bash
# Exton Wallet — cron watchdog for incoming transactions
# Runs every 2 minutes via system crontab
# If new transactions found → sends notification via OpenClaw

SKILL_DIR="$(cd "$(dirname "$0")/.." && pwd)"
EXTON_DIR="$HOME/.exton"
CONFIG="$EXTON_DIR/config.json"

# Skip if not configured
[ -f "$CONFIG" ] || exit 0
[ -f "$SKILL_DIR/.venv/bin/python3" ] || exit 0

# Run watch
RESULT=$("$SKILL_DIR/.venv/bin/python3" "$SKILL_DIR/scripts/main.py" watch 2>/dev/null)

# Check if new transactions
HAS_NEW=$(echo "$RESULT" | python3 -c "import sys,json; print(json.load(sys.stdin).get('has_new', False))" 2>/dev/null)

[ "$HAS_NEW" = "True" ] || exit 0

# Format notification
NOTIFICATION=$(echo "$RESULT" | python3 -c "
import sys, json
d = json.load(sys.stdin)
lines = []
for tx in d.get('new_incoming', []):
    amt = tx.get('amount_ton', 0)
    frm = tx.get('from', '?')
    lines.append(f'Received {amt} TON from {frm}')
for tx in d.get('new_outgoing', []):
    amt = tx.get('amount_ton', 0)
    to = tx.get('to', '?')
    lines.append(f'Sent {amt} TON to {to}')
bal = d.get('balance_ton', '?')
lines.append(f'Balance: {bal} TON')
print(chr(10).join(lines))
" 2>/dev/null)

[ -z "$NOTIFICATION" ] && exit 0

# Send via OpenClaw
CHAT_ID=$(python3 -c "import json; print(json.load(open('$CONFIG')).get('telegram_chat_id',''))" 2>/dev/null)

if [ -n "$CHAT_ID" ] && command -v openclaw &>/dev/null; then
    openclaw message send --channel telegram --target "$CHAT_ID" --message "$NOTIFICATION" 2>/dev/null
fi
