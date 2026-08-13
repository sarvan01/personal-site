#!/usr/bin/env bash
# One-time setup (macOS/Linux): fetch the majors and build the cockpit.
# Run once; then use daily.sh for the recurring run. Non-destructive.
# (The H2 privacy research is closed/archived; see scripts/research/.)
set -euo pipefail
cd "$(dirname "$0")"

echo "[1/2] Fetching majors (BTC/ETH/BNB/XRP/SOL)..."
python3 scripts/fetch_data.py --config h1b

echo "[2/2] Building the cockpit..."
python3 scripts/cockpit.py --config h1b

echo
echo "Setup complete. Open out/cockpit.html"
echo "From now on, run ./daily.sh once a day (or schedule it)."
