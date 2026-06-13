#!/usr/bin/env bash
# One-time setup (macOS/Linux): fetch majors + privacy basket, build cockpit.
# Run once; then use daily.sh for the recurring run. Non-destructive.
set -euo pipefail
cd "$(dirname "$0")"

echo "[1/3] Fetching majors (BTC/ETH/BNB/XRP/SOL)..."
python3 scripts/fetch_data.py --config h1b

echo "[2/3] Fetching privacy basket for the Railgun study..."
python3 scripts/fetch_privacy.py || echo "  (privacy fetch failed -- continuing; retry later)"

echo "[3/3] Building the cockpit..."
python3 scripts/cockpit.py --config h1b

echo
echo "Setup complete. Open out/cockpit.html"
echo "From now on, run ./daily.sh once a day (or schedule it)."
