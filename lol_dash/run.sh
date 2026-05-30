#!/usr/bin/env bash
# Double-click runner for lol-turing-dash (macOS / Linux).
# Activates the venv (creating it on first run) and launches the dashboard.

set -e

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
ROOT="$(cd "$SCRIPT_DIR/.." && pwd)"
cd "$ROOT"

if [ ! -d ".venv" ]; then
    echo "First run — installing dependencies (one-time, ~1 minute)…"
    bash lol_dash/scripts/install.sh
fi

# shellcheck disable=SC1091
source .venv/bin/activate
exec python -m lol_dash.src.main "$@"
