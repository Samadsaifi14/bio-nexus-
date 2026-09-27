#!/usr/bin/env bash
set -uo pipefail

echo "==> Installing system tools and figure renderer libraries"
# build-essential/git are needed to compile fpocket from source (not packaged in
# Debian repos) — Render's native Python runtime ships neither.
apt-get update -qq && apt-get install -y -qq --no-install-recommends \
    samtools libcairo2 libpango-1.0-0 libpangocairo-1.0-0 \
    build-essential git 2>/dev/null && \
    echo "     samtools installed: $(samtools --version | head -1)" || \
    { echo "     ERROR: system dependency installation failed"; exit 1; }

MINIMAP2_DEST="/usr/local/bin/minimap2"
MINIMAP2_URL="https://github.com/lh3/minimap2/releases/download/v2.28/minimap2-2.28_x64-linux.tar.bz2"
if [ -x "$MINIMAP2_DEST" ]; then
    echo "     minimap2 already present: $($MINIMAP2_DEST --version 2>&1 | head -1)"
else
    curl -fSL "$MINIMAP2_URL" | tar xjf - -C /tmp && \
        cp /tmp/minimap2-2.28_x64-linux/minimap2 "$MINIMAP2_DEST" && \
        chmod +x "$MINIMAP2_DEST" && rm -rf /tmp/minimap2* && \
        echo "     minimap2 installed: $($MINIMAP2_DEST --version 2>&1 | head -1)" || \
        { echo "     ERROR: minimap2 installation failed"; exit 1; }
fi

echo "==> Building fpocket (pocket detection)"
# The Dockerfiles build fpocket, but Render deploys with `runtime: python`, so the
# Dockerfiles never run and fpocket was silently absent in production — every
# structure-prep run degraded to the SASA fallback. Build and verify it here.
FPOCKET_DEST="/usr/local/bin/fpocket"
if [ -x "$FPOCKET_DEST" ]; then
    echo "     fpocket already present"
else
    if git clone --depth 1 --branch 4.2.3 https://github.com/Discngine/fpocket /tmp/fpocket-src >/dev/null 2>&1 && \
       make -C /tmp/fpocket-src >/dev/null 2>&1 && \
       make -C /tmp/fpocket-src install >/dev/null 2>&1; then
        rm -rf /tmp/fpocket-src
        echo "     fpocket installed: $FPOCKET_DEST"
    else
        rm -rf /tmp/fpocket-src
        echo "     ERROR: fpocket build failed — pocket detection would silently fall back to SASA"
        exit 1
    fi
fi
# Fail the build if the binary is unusable, so a broken toolchain cannot ship as a
# silent downgrade to fallback output.
fpocket --version >/dev/null 2>&1 || fpocket -h >/dev/null 2>&1 || {
    echo "     ERROR: fpocket present but not executable at $FPOCKET_DEST"; exit 1; }

echo "==> Verifying native tools"
samtools --version | head -1
minimap2 --version 2>&1 | head -1
echo "     fpocket: $(command -v fpocket || echo 'not on PATH')"

echo "==> Installing Python dependencies"
pip install -r requirements.txt
python -c "import cairosvg; from PIL import Image; print('figure export renderer ready')"

echo "==> Downloading AutoDock Vina binary …"
VINA_DEST="/usr/local/bin/vina"
VINA_URL="https://github.com/ccsb-scripps/AutoDock-Vina/releases/download/v1.2.7/vina_1.2.7_linux_x86_64"
curl -fSL -o "$VINA_DEST" "$VINA_URL" && chmod +x "$VINA_DEST" && echo "     vina installed at $VINA_DEST ($(stat -c%s "$VINA_DEST") bytes)" || echo "     WARNING: vina download failed — Python fallback will handle"

echo "==> Build complete"
