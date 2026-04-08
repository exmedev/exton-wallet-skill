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

# Restart Gateway to pick up skill
if command -v openclaw &>/dev/null; then
    openclaw gateway restart 2>/dev/null || true
fi

echo ""
echo "Exton Wallet Skill installed!"
echo "Start a new session (/new) and say: Connect my Exton wallet"
