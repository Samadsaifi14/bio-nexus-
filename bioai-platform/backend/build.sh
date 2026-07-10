#!/usr/bin/env bash
set -euo pipefail

echo "==> Installing Python dependencies (includes openbabel-wheel for obabel CLI)"
pip install -r requirements.txt

# Determine persistent binary directory (pip-managed, survives Render build→runtime)
BIN_DIR=$(python3 -c "import sys; print(sys.exec_prefix + '/bin')" 2>/dev/null) || BIN_DIR="/usr/local/bin"

echo "==> Installing AutoDock Vina → $BIN_DIR"
wget -q "https://github.com/ccsb-scripps/AutoDock-Vina/releases/download/v1.2.7/vina_1.2.7_linux_x86_64" -O "$BIN_DIR/vina"
chmod +x "$BIN_DIR/vina"

echo "==> Installing PhyML → $BIN_DIR"
wget -qO /tmp/phyml.tar.bz2 "https://anaconda.org/bioconda/phyml/3.3.20220408/download/linux-64/phyml-3.3.20220408-h9bc3f66_3.tar.bz2"
tar xjf /tmp/phyml.tar.bz2 -C /tmp
cp /tmp/bin/phyml "$BIN_DIR/phyml"
chmod +x "$BIN_DIR/phyml"
rm -rf /tmp/phyml.tar.bz2 /tmp/bin

echo "==> Build complete"
