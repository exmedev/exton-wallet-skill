#!/bin/bash
# Exton Wallet Skill — install dependencies
# Idempotent: safe to run multiple times
set -e

SKILL_DIR="$(cd "$(dirname "$0")/.." && pwd)"

echo "Installing Exton Wallet Skill..."

# Check Python3
if ! command -v python3 &>/dev/null; then
    echo "python3 not found. Install Python 3.9+"
    exit 1
fi

# Install system dependency: zbar (for QR decoding)
OS="$(uname -s)"
if [ "$OS" = "Darwin" ]; then
    command -v brew &>/dev/null && brew install zbar 2>/dev/null || true
elif [ "$OS" = "Linux" ]; then
    if command -v apt-get &>/dev/null; then
        sudo apt-get install -y -qq libzbar0 python3-venv 2>/dev/null || true
    elif command -v dnf &>/dev/null; then
        sudo dnf install -y -q zbar python3-virtualenv 2>/dev/null || true
    fi
fi

# Create or repair venv
if [ ! -f "$SKILL_DIR/.venv/bin/python3" ]; then
    rm -rf "$SKILL_DIR/.venv"
    python3 -m venv "$SKILL_DIR/.venv"
fi

# Install Python packages
"$SKILL_DIR/.venv/bin/pip" install --quiet -r "$SKILL_DIR/scripts/requirements.txt"

# Verify
"$SKILL_DIR/.venv/bin/python3" -c "
import nacl.signing; import base58; import qrcode
print('  All dependencies OK')
try:
    from pyzbar import pyzbar
    print('  QR decoding OK')
except:
    print('  pyzbar not available (install zbar: brew install zbar / apt install libzbar0)')
"

# Enable cron in OpenClaw config if not already
OPENCLAW_CONFIG="$HOME/.openclaw/openclaw.json"
if [ -f "$OPENCLAW_CONFIG" ]; then
    python3 -c "
import json
config = json.load(open('$OPENCLAW_CONFIG'))
if 'cron' not in config:
    config['cron'] = {'enabled': True}
elif not config['cron'].get('enabled'):
    config['cron']['enabled'] = True
json.dump(config, open('$OPENCLAW_CONFIG', 'w'), indent=2)
print('  Cron enabled in openclaw.json')
" 2>/dev/null
fi

# Setup cron for transaction monitoring
# Write directly to jobs.json (safe during install, Gateway not yet running with new config)
CRON_DIR="$HOME/.openclaw/cron"
CRON_FILE="$CRON_DIR/jobs.json"
mkdir -p "$CRON_DIR"

python3 -c "
import json, os, uuid

jobs_file = '$CRON_FILE'
jobs = []
if os.path.exists(jobs_file):
    try:
        jobs = json.load(open(jobs_file))
        if not isinstance(jobs, list):
            jobs = []
    except:
        jobs = []

# Remove old exton-watch if exists
jobs = [j for j in jobs if j.get('name') != 'exton-watch']

# Add fresh cron job
jobs.append({
    'id': str(uuid.uuid4()),
    'name': 'exton-watch',
    'enabled': True,
    'schedule': {
        'kind': 'cron',
        'expr': '*/2 * * * *'
    },
    'message': 'Run exton-wallet watch command: bash {baseDir}/scripts/run.sh watch — if has_new is true, notify user about each transaction with amount and address. If has_new is false, silently finish.',
    'createdAt': int(__import__('time').time() * 1000)
})

json.dump(jobs, open(jobs_file, 'w'), indent=2)
print('  Cron job exton-watch configured (every 2 min)')
"

# Restart Gateway to pick up skill + cron
if command -v openclaw &>/dev/null; then
    openclaw gateway restart 2>/dev/null || true
fi

echo ""
echo "Exton Wallet Skill installed!"
echo "Start a new session (/new) and say: Connect my Exton wallet"
