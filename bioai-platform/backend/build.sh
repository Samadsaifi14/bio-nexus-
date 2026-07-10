#!/usr/bin/env bash
set -uo pipefail

echo "==> Installing Python dependencies (includes openbabel-wheel for obabel CLI)"
pip install -r requirements.txt

# Vina and PhyML are downloaded at runtime by the application
# (self-healing in app/tools/docking.py)

echo "==> Build complete"
