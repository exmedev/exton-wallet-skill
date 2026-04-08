#!/bin/bash
# Exton Wallet Skill — automatic dependency installer
# Runs once on skill installation. Detects OS, installs minimal deps.

set -e

echo "🔧 Installing Exton Wallet Skill dependencies..."

# Detect OS
OS="$(uname -s)"

# Check Python3
if ! command -v python3 &>/dev/null; then
    echo "❌ python3 not found. Please install Python 3.9+"
    exit 1
fi

# Install system dependency: zbar (for QR decoding from photos)
if ! python3 -c "import pyzbar" 2>/dev/null; then
    if [ "$OS" = "Darwin" ]; then
        if command -v brew &>/dev/null; then
            echo "📦 Installing zbar (macOS)..."
            brew install zbar 2>/dev/null || true
        fi
    elif [ "$OS" = "Linux" ]; then
        if command -v apt-get &>/dev/null; then
            echo "📦 Installing zbar (Linux)..."
            sudo apt-get install -y libzbar0 2>/dev/null || true
        elif command -v dnf &>/dev/null; then
            sudo dnf install -y zbar 2>/dev/null || true
        fi
    fi
fi

# Install Python packages
echo "📦 Installing Python packages..."
python3 -m pip install --quiet --user PyNaCl>=1.5.0 base58>=2.1 qrcode>=7.4 Pillow>=10.0 pyzbar>=0.1.9

# Verify
echo "✅ Verifying..."
python3 -c "
import nacl.signing
import nacl.bindings
import base58
import qrcode
print('  ✓ PyNaCl (Ed25519)')
print('  ✓ base58 (Recovery Code)')
print('  ✓ qrcode (QR generation)')
try:
    from pyzbar import pyzbar
    print('  ✓ pyzbar (QR decoding)')
except:
    print('  ⚠ pyzbar not available (QR decoding from photos disabled)')
    print('    Install zbar: brew install zbar (macOS) or apt install libzbar0 (Linux)')
"

echo ""
echo "💎 Exton Wallet Skill installed!"
echo "   Say: 'Подключи мой Exton кошелёк' to get started."
