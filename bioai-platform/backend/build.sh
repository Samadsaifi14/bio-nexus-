#!/usr/bin/env bash
set -uo pipefail

echo "==> Installing Python dependencies (openbabel-wheel for obabel CLI)"
pip install -r requirements.txt

echo "==> Downloading AutoDock Vina binary …"
VINA_DEST="/usr/local/bin/vina"
curl -sSL -o "$VINA_DEST" \
  "https://github.com/ccsb-scripps/AutoDock-Vina/releases/download/v1.2.7/vina_1.2.7_linux_x86_64"
chmod +x "$VINA_DEST"
echo "     vina installed at $VINA_DEST ($(stat -c%s "$VINA_DEST") bytes)"

echo "==> Build complete"
