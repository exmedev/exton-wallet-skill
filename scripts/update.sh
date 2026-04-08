#!/bin/bash
# Exton Wallet Skill — update to latest version
# Handles ANY state: dirty working tree, untracked files, conflicts
set -e

SKILL_DIR="$(cd "$(dirname "$0")/.." && pwd)"
cd "$SKILL_DIR"

echo "Updating Exton Wallet Skill..."

# Reset local changes (skill code is managed by git, not user)
git fetch origin main 2>/dev/null
git reset --hard origin/main 2>/dev/null
git clean -fd --exclude=.venv 2>/dev/null

# Rebuild venv if missing or broken
if [ ! -f "$SKILL_DIR/.venv/bin/python3" ]; then
    echo "Rebuilding virtual environment..."
    rm -rf "$SKILL_DIR/.venv"
    python3 -m venv "$SKILL_DIR/.venv"
fi

# Install/update dependencies
"$SKILL_DIR/.venv/bin/pip" install --quiet -r "$SKILL_DIR/scripts/requirements.txt" 2>/dev/null

# Restart Gateway to pick up changes
if command -v openclaw &>/dev/null; then
    openclaw gateway restart 2>/dev/null || true
fi

echo "✅ Updated to: $(git log --oneline -1)"
