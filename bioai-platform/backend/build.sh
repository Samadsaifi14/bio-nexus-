#!/usr/bin/env bash
set -uo pipefail

echo "==> Installing system tools and figure renderer libraries"
# bzip2 is required by the .tar.bz2 payloads below (minimap2, PhyML) and is not
# guaranteed on the native runtime.
apt-get update -qq && apt-get install -y -qq --no-install-recommends \
    samtools libcairo2 libpango-1.0-0 libpangocairo-1.0-0 bzip2 && \
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

# ── Phylogenetics toolchain ────────────────────────────────────────────────
# These were present only in the Dockerfiles, which Render never runs (it
# deploys with `runtime: python`). Consequence: MAFFT fell back to the remote EBI
# service, and ML tree building hard-failed outright with "No ML tree tool found"
# (app/routers/phylo.py). All three are small (16 MB / 2 MB / 4.5 MB) and their
# payload paths are verified against the actual archives.
echo "==> Installing MAFFT, PhyML and IQ-TREE"

MAFFT_URL="https://mafft.cbrc.jp/alignment/software/mafft-7.526-linux.tgz"
if [ -x /usr/local/bin/mafft ]; then
    echo "     mafft already present"
else
    # mafft.bat resolves its helper binaries from `dirname $0`, so a symlink at
    # /usr/local/bin/mafft would make it look for /usr/local/bin/mafftdir and fail
    # (silently falling back to the remote EBI service). Use a wrapper that execs
    # the real path instead.
    if curl -fSL "$MAFFT_URL" | tar xzf - -C /opt && \
       printf '#!/bin/sh\nexec /opt/mafft-linux64/mafft.bat "$@"\n' > /usr/local/bin/mafft && \
       chmod +x /usr/local/bin/mafft; then
        echo "     mafft installed"
    else
        echo "     ERROR: MAFFT installation failed"
        exit 1
    fi
fi

PHYML_URL="https://anaconda.org/bioconda/phyml/3.3.20220408/download/linux-64/phyml-3.3.20220408-h9bc3f66_3.tar.bz2"
if [ -x /usr/local/bin/phyml ]; then
    echo "     phyml already present"
else
    curl -fSL "$PHYML_URL" | tar xjf - -C /tmp && \
        cp /tmp/bin/phyml /usr/local/bin/phyml && \
        chmod +x /usr/local/bin/phyml && rm -rf /tmp/bin /tmp/info /tmp/share && \
        echo "     phyml installed" || \
        { echo "     ERROR: PhyML installation failed"; exit 1; }
fi

IQTREE_URL="https://github.com/iqtree/iqtree2/releases/download/v2.3.6/iqtree-2.3.6-Linux-intel.tar.gz"
if [ -x /usr/local/bin/iqtree2 ]; then
    echo "     iqtree2 already present"
else
    curl -fSL "$IQTREE_URL" | tar xzf - -C /opt && \
        ln -sf /opt/iqtree-2.3.6-Linux-intel/bin/iqtree2 /usr/local/bin/iqtree2 && \
        echo "     iqtree2 installed" || \
        { echo "     ERROR: IQ-TREE installation failed"; exit 1; }
fi

# Gnina is OFF BY DEFAULT, and the reason is not image size.
# Verified on this base image: the v1.3.2 asset "gnina.1.3.2" (1,426,790,536 bytes)
# downloads fine, but gnina's CPU build is still linked against cuDNN and aborts at
# load time with "libcudnn.so.9: cannot open shared object file". libcudnn9 is not
# in Debian bookworm — only in NVIDIA's CUDA repo, whose signing key currently
# fails to verify. Its OpenCL need is otherwise satisfiable (pocl provides a
# working CPU device), so the blocker is the cuDNN link, not OpenCL.
# Shipping a 1.4 GB binary that cannot execute would be worse than the fallback,
# so rescoring stays on the Vina/Python path unless a host provides cuDNN.
GNINA_URL="https://github.com/gnina/gnina/releases/download/v1.3.2/gnina.1.3.2"
if [ "${INSTALL_GNINA:-0}" = "0" ]; then
    echo "==> Skipping gnina (INSTALL_GNINA=0): CPU build requires cuDNN, see comment"
    echo "    CNN rescoring falls back to the Vina/Python path and reports it as such"
else
    echo "==> Installing gnina (~1.4 GB)"
    if [ -x /usr/local/bin/gnina ] && gnina --version >/dev/null 2>&1; then
        echo "     gnina already present"
    else
        apt-get install -y -qq --no-install-recommends \
            ocl-icd-libopencl1 pocl-opencl-icd clinfo 2>/dev/null || true
        curl -fSL -o /usr/local/bin/gnina "$GNINA_URL" && \
            chmod +x /usr/local/bin/gnina || \
            { echo "     ERROR: gnina download failed"; exit 1; }
        echo "     size $(stat -c %s /usr/local/bin/gnina) bytes"
        gnina --version 2>&1 | head -3 || true
        if ! gnina --version >/dev/null 2>&1; then
            echo "     ERROR: gnina cannot execute here. Its CPU build links libcudnn.so.9,"
            echo "            which a CPU-only image does not provide. Install cuDNN or set INSTALL_GNINA=0."
            exit 1
        fi
        if ! clinfo -l 2>/dev/null | grep -qi "pocl\|portable computing language"; then
            echo "     ERROR: no CPU OpenCL platform visible; gnina would fail at run time."
            exit 1
        fi
        echo "     gnina installed and a CPU OpenCL device is available"
    fi
fi

echo "==> Building fpocket (pocket detection)"
# The Dockerfiles build fpocket, but Render deploys with `runtime: python`, so the
# Dockerfiles never run and fpocket was silently absent in production — every
# structure-prep run degraded to the SASA fallback. Build and verify it here.
FPOCKET_DEST="/usr/local/bin/fpocket"
if [ -x "$FPOCKET_DEST" ]; then
    echo "     fpocket already present"
else
    # build-essential/git are only needed to compile fpocket, and Render's native
    # Python runtime ships neither, so they are installed here rather than on every
    # build. -j keeps the compile from dominating build time.
    apt-get install -y -qq --no-install-recommends build-essential git >/dev/null 2>&1
    if git clone --depth 1 --branch 4.2.3 https://github.com/Discngine/fpocket /tmp/fpocket-src >/dev/null 2>&1 && \
       make -C /tmp/fpocket-src -j"$(nproc 2>/dev/null || echo 2)" >/dev/null 2>&1 && \
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
echo "     fpocket:  $(command -v fpocket || echo 'not on PATH')"
echo "     mafft:    $(command -v mafft || echo 'not on PATH')"
echo "     phyml:    $(command -v phyml || echo 'not on PATH')"
echo "     iqtree2:  $(command -v iqtree2 || echo 'not on PATH')"
echo "     gnina:    $(command -v gnina || echo 'not installed (optional)')"

echo "==> Installing Python dependencies"
pip install -r requirements.txt
python -c "import cairosvg; from PIL import Image; print('figure export renderer ready')"

echo "==> Downloading AutoDock Vina binary …"
VINA_DEST="/usr/local/bin/vina"
VINA_URL="https://github.com/ccsb-scripps/AutoDock-Vina/releases/download/v1.2.7/vina_1.2.7_linux_x86_64"
curl -fSL -o "$VINA_DEST" "$VINA_URL" && chmod +x "$VINA_DEST" && echo "     vina installed at $VINA_DEST ($(stat -c%s "$VINA_DEST") bytes)" || echo "     WARNING: vina download failed — Python fallback will handle"

echo "==> Build complete"
