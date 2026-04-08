#!/bin/bash
# Exton Wallet Skill — automatic dependency installer
set -e

SKILL_DIR="$(cd "$(dirname "$0")/.." && pwd)"
VENV_DIR="$SKILL_DIR/.venv"

echo "Installing Exton Wallet Skill..."

# Check Python3
if ! command -v python3 &>/dev/null; then
    echo "python3 not found. Install Python 3.9+"
    exit 1
fi

# Install zbar (system library for QR decoding)
OS="$(uname -s)"
if [ "$OS" = "Darwin" ]; then
    command -v brew &>/dev/null && brew install zbar 2>/dev/null || true
elif [ "$OS" = "Linux" ]; then
    if command -v apt-get &>/dev/null; then
        sudo apt-get install -y libzbar0 python3-venv 2>/dev/null || true
    elif command -v dnf &>/dev/null; then
        sudo dnf install -y zbar python3-virtualenv 2>/dev/null || true
    fi
fi

# Create venv and install Python packages
echo "Creating virtual environment..."
python3 -m venv "$VENV_DIR"
"$VENV_DIR/bin/pip" install --quiet PyNaCl>=1.5.0 base58>=2.1 qrcode>=7.4 Pillow>=10.0 pyzbar>=0.1.9

# Create wrapper script that uses venv python
cat > "$SKILL_DIR/scripts/run.sh" << 'WRAPPER'
#!/bin/bash
SKILL_DIR="$(cd "$(dirname "$0")/.." && pwd)"
exec "$SKILL_DIR/.venv/bin/python3" "$SKILL_DIR/scripts/main.py" "$@"
WRAPPER
chmod +x "$SKILL_DIR/scripts/run.sh"

# Verify
"$VENV_DIR/bin/python3" -c "
import nacl.signing; import base58; import qrcode
print('  PyNaCl OK')
print('  base58 OK')
print('  qrcode OK')
try:
    from pyzbar import pyzbar; print('  pyzbar OK')
except:
    print('  pyzbar: not available (QR decode disabled)')
"

echo ""
echo "Exton Wallet Skill installed!"
echo "Say: 'Connect my Exton wallet' to get started."
