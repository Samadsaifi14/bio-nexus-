#!/usr/bin/env bash
set -uo pipefail

echo "==> Installing Python dependencies"
pip install -r requirements.txt

echo "==> Downloading AutoDock Vina binary …"
VINA_DEST="/usr/local/bin/vina"
VINA_URL="https://github.com/ccsb-scripps/AutoDock-Vina/releases/download/v1.2.7/vina_1.2.7_linux_x86_64"
curl -fSL -o "$VINA_DEST" "$VINA_URL" && chmod +x "$VINA_DEST" && echo "     vina installed at $VINA_DEST ($(stat -c%s "$VINA_DEST") bytes)" || echo "     WARNING: vina download failed — Python fallback will handle"

echo "==> Build complete"
