#!/bin/bash
SKILL_DIR="$(cd "$(dirname "$0")/.." && pwd)"
exec "$SKILL_DIR/.venv/bin/python3" "$SKILL_DIR/scripts/main.py" "$@"
