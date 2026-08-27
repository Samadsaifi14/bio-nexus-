# bookworm pin = gcc 12; trixie's gcc 14 turns fpocket's legacy C warnings into hard errors
FROM python:3.11-slim-bookworm

RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential gcc g++ wget ca-certificates git libnetcdf-dev \
    openbabel libgl1 libgomp1 libopenblas-dev \
    libxml2 libxslt1.1 samtools && \
    rm -rf /var/lib/apt/lists/*

# Gnina (CNN-based rescoring) — pre-built binary; --no_gpu for CPU-only environments
RUN wget -q "https://github.com/gnina/gnina/releases/download/v1.3.2/gnina" -O /usr/local/bin/gnina && \
    chmod +x /usr/local/bin/gnina || echo "gnina download skipped (optional)"

# MAFFT (local MSA) — portable Linux package, faster and more reliable than remote EBI endpoints
RUN wget -q "https://mafft.cbrc.jp/alignment/software/mafft-7.526-linux.tgz" -O /tmp/mafft.tgz && \
    tar xzf /tmp/mafft.tgz -C /opt && \
    ln -sf /opt/mafft-linux64/mafft.bat /usr/local/bin/mafft && \
    rm /tmp/mafft.tgz || echo "mafft download skipped (optional)"

# fpocket (pocket detection) — not packaged in Debian repos; build from source
# NOTE: tags carry no "v" prefix (4.2.3, not v4.2.3) — a wrong prefix kills the build
RUN git clone --depth 1 --branch 4.2.3 https://github.com/Discngine/fpocket /tmp/fpocket && \
    make -C /tmp/fpocket && make -C /tmp/fpocket install && \
    rm -rf /tmp/fpocket
# minimap2 (for NGS read alignment)
RUN wget -q https://github.com/lh3/minimap2/releases/download/v2.28/minimap2-2.28_x64-linux.tar.bz2 -O /tmp/minimap2.tar.bz2 && \
    tar xjf /tmp/minimap2.tar.bz2 -C /tmp --no-same-owner && \
    cp /tmp/minimap2-2.28_x64-linux/minimap2 /usr/local/bin/minimap2 && \
    chmod +x /usr/local/bin/minimap2 && \
    rm -rf /tmp/minimap2*

# Download pre-compiled PhyML binary from bioconda
RUN wget -qO /tmp/phyml.tar.bz2 \
      https://anaconda.org/bioconda/phyml/3.3.20220408/download/linux-64/phyml-3.3.20220408-h9bc3f66_3.tar.bz2 && \
    tar xjf /tmp/phyml.tar.bz2 -C /tmp --no-same-owner && \
    cp /tmp/bin/phyml /usr/local/bin/phyml && \
    chmod +x /usr/local/bin/phyml && \
    rm -rf /tmp/phyml.tar.bz2 /tmp/bin

# IQ-TREE2 (ultrafast bootstrap — 10-100x faster than PhyML for bootstrap)
RUN wget -q https://github.com/iqtree/iqtree2/releases/download/v2.3.6/iqtree-2.3.6-Linux-intel.tar.gz -O /tmp/iqtree.tar.gz && \
    tar xzf /tmp/iqtree.tar.gz -C /opt && \
    cp /opt/iqtree-2.3.6-Linux-intel/bin/iqtree2 /usr/local/bin/iqtree2 && \
    chmod +x /usr/local/bin/iqtree2 && \
    rm -rf /tmp/iqtree.tar.gz /opt/iqtree-2.3.6-Linux-intel

# Download pre-compiled AutoDock Vina binary from GitHub releases
RUN wget -q "https://github.com/ccsb-scripps/AutoDock-Vina/releases/download/v1.2.7/vina_1.2.7_linux_x86_64" -O /usr/local/bin/vina && \
    chmod +x /usr/local/bin/vina

WORKDIR /app
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# primer3-py is optional — skip silently if it fails
RUN pip install --no-cache-dir "primer3-py>=2.0.3" 2>/dev/null || echo "primer3-py skipped (optional)"

COPY . .

# Run as non-root (HF Spaces convention: uid 1000). Runtime writes go to
# /tmp (tool downloads) and $HOME (caches), both writable for this user.
RUN useradd -m -u 1000 appuser && chown -R appuser:appuser /app
USER appuser

EXPOSE 7860
CMD ["sh", "-c", "python -c 'import openmm; print(\"OpenMM\", openmm.__version__)' && uvicorn app.main:app --host 0.0.0.0 --port ${PORT:-7860}"]
