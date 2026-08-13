#!/usr/bin/env bash
# Daily routine (macOS/Linux): fetch the new bar, step the paper account,
# refresh the cockpit. Paper mode only -- no real orders.
set -euo pipefail
cd "$(dirname "$0")"

echo "[1/2] Fetching latest data..."
python3 scripts/fetch_data.py --config h1b

echo "[2/2] Updating cockpit and paper account..."
python3 scripts/cockpit.py --config h1b

echo
echo "Done. Open out/cockpit.html"
