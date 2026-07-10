#!/usr/bin/env bash
set -euo pipefail

echo "==> Installing openbabel CLI via openbabel-wheel"
pip install openbabel-wheel

echo "==> Installing AutoDock Vina"
wget -q "https://github.com/ccsb-scripps/AutoDock-Vina/releases/download/v1.2.7/vina_1.2.7_linux_x86_64" -O /usr/local/bin/vina
chmod +x /usr/local/bin/vina

echo "==> Installing PhyML"
wget -qO /tmp/phyml.tar.bz2 "https://anaconda.org/bioconda/phyml/3.3.20220408/download/linux-64/phyml-3.3.20220408-h9bc3f66_3.tar.bz2"
tar xjf /tmp/phyml.tar.bz2 -C /tmp
cp /tmp/bin/phyml /usr/local/bin/phyml
chmod +x /usr/local/bin/phyml
rm -rf /tmp/phyml.tar.bz2 /tmp/bin

echo "==> Installing Python dependencies"
pip install -r requirements.txt

echo "==> Build complete"
