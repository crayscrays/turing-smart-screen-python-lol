#!/usr/bin/env bash
# lol-turing-dash installer (macOS / Linux).
# Run from the REPO ROOT (the folder containing this README and the `library/` dir):
#     bash lol_dash/scripts/install.sh

set -euo pipefail

# Resolve repo root = two levels up from this script
SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
ROOT="$(cd "$SCRIPT_DIR/../.." && pwd)"
cd "$ROOT"

echo "==> lol-turing-dash installer"
echo "    Repo root: $ROOT"

# ---------- 1. Python venv ----------
if [ ! -d ".venv" ]; then
    echo "==> Creating virtualenv .venv"
    python3 -m venv .venv
fi
# shellcheck disable=SC1091
source .venv/bin/activate

echo "==> Installing Python dependencies"
python -m pip install --upgrade pip wheel
# Upstream library deps
python -m pip install -r requirements.txt
# Our additional deps
python -m pip install -r lol_dash/requirements.txt

# ---------- 2. Riot TLS cert ----------
echo "==> Fetching Riot Live Client cert"
mkdir -p lol_dash/certs
python -m lol_dash.src.utils.cert || echo "   (cert fetch failed — will fall back to insecure TLS)"

# ---------- 3. ffmpeg check (conversion happens at runtime) ----------
if command -v ffmpeg >/dev/null 2>&1; then
    echo "==> ffmpeg found — idle videos will auto-convert at launch"
else
    echo "!! ffmpeg not found — install it (brew install ffmpeg / apt install ffmpeg) to enable idle video."
fi
echo "   Drop your .mp4 into lol_dash/videos/ and launch the app."

echo ""
echo "==> Done."
echo "    Activate venv:   source .venv/bin/activate"
echo "    Run dashboard:   python -m lol_dash.src.main --config lol_dash/config.yaml"
echo "    Preview only:    python -m lol_dash.src.main --config lol_dash/config.yaml --no-screen"
