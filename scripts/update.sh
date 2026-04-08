#!/bin/bash
# Exton Wallet Skill — update to latest version
set -e

SKILL_DIR="$(cd "$(dirname "$0")/.." && pwd)"

echo "Updating Exton Wallet Skill..."

cd "$SKILL_DIR"
git pull origin main 2>&1

# Reinstall dependencies (in case new ones added)
if [ -d "$SKILL_DIR/.venv" ]; then
    "$SKILL_DIR/.venv/bin/pip" install --quiet -r "$SKILL_DIR/scripts/requirements.txt" 2>/dev/null
fi

# Restart Gateway to pick up changes
if command -v openclaw &>/dev/null; then
    openclaw gateway restart 2>/dev/null || true
fi

echo "Updated to $(git log --oneline -1)"
