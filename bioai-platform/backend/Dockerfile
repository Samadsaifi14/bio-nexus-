# bookworm pin = gcc 12; trixie's gcc 14 turns fpocket's legacy C warnings into hard errors
FROM python:3.11-slim-bookworm

RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential gcc g++ wget ca-certificates git libnetcdf-dev \
    openbabel libgl1 libgomp1 libopenblas-dev \
    libcairo2 libpango-1.0-0 libpangocairo-1.0-0 \
    libxml2 libxslt1.1 samtools \
    r-base-core r-bioc-org.hs.eg.db r-bioc-org.mm.eg.db r-bioc-go.db r-bioc-deseq2 r-bioc-complexheatmap r-cran-ggplot2 r-cran-jsonlite r-cran-circlize && \
    rm -rf /var/lib/apt/lists/*

# Verify the deterministic RNA-seq statistical runtime at image-build time.
RUN Rscript -e 'suppressPackageStartupMessages({library(DESeq2); library(ComplexHeatmap); library(ggplot2); library(jsonlite); library(circlize)}); cat("DESeq2", as.character(packageVersion("DESeq2")), "ComplexHeatmap", as.character(packageVersion("ComplexHeatmap")), "\n")'

# Gnina (CNN-based rescoring) — OFF BY DEFAULT, and the reason is not image size.
#
# Verified on this base image (python:3.11-slim-bookworm, CPU-only):
#   * The v1.3.2 release asset "gnina.1.3.2" (1,426,790,536 bytes) downloads
#     fine, but the official CPU build is still linked against cuDNN and aborts
#     at load time:
#         gnina: error while loading shared libraries:
#         libcudnn.so.9: cannot open shared object file: No such file or directory
#   * libcudnn9 is not in Debian bookworm. It lives only in NVIDIA's CUDA apt
#     repository, whose signing key the image cannot currently verify
#     (NO_PUBKEY A4B469963BF863CC), so enabling gnina fails the build.
#   * Its OpenCL requirement is otherwise satisfiable: pocl provides a working CPU
#     device (verified via clinfo), so the blocker is the cuDNN link, not OpenCL.
#
# Rather than ship a ~1.4 GB binary that cannot execute, or bake a third-party GPU
# repository with a rotating GPG key into a CPU image, rescoring uses the
# Vina/Python fallback and says so. To enable on a host that genuinely provides
# cuDNN, build with --build-arg INSTALL_GNINA=1.
ARG INSTALL_GNINA=0
RUN if [ "$INSTALL_GNINA" = "0" ]; then \
        echo "gnina skipped (INSTALL_GNINA=0): CPU build requires cuDNN, see comment above"; \
        echo "  CNN rescoring falls back to the Vina/Python path and reports it as such"; \
    else \
        apt-get update && apt-get install -y --no-install-recommends \
            ocl-icd-libopencl1 pocl-opencl-icd clinfo && \
        rm -rf /var/lib/apt/lists/*; \
        wget -q "https://github.com/gnina/gnina/releases/download/v1.3.2/gnina.1.3.2" -O /usr/local/bin/gnina && \
        chmod +x /usr/local/bin/gnina || { echo "ERROR: gnina download failed"; exit 1; }; \
        echo "gnina: size $(stat -c %s /usr/local/bin/gnina) bytes"; \
        gnina --version 2>&1 | head -3 || true; \
        if ! gnina --version >/dev/null 2>&1; then \
            echo "ERROR: gnina cannot execute here. Its CPU build links libcudnn.so.9,"; \
            echo "       which a CPU-only image does not provide. Install cuDNN or set INSTALL_GNINA=0."; \
            exit 1; \
        fi; \
        if ! clinfo -l 2>/dev/null | grep -qi "pocl\|portable computing language"; then \
            echo "ERROR: no CPU OpenCL platform visible; gnina would fail at run time."; \
            exit 1; \
        fi; \
        echo "gnina: installed and a CPU OpenCL device is available"; \
    fi

# MAFFT (local MSA) — portable Linux package, faster and more reliable than remote EBI endpoints.
# mafft.bat resolves its helpers from `dirname $0`, so a symlink makes it look for
# /usr/local/bin/mafftdir and fail (exit 127) — hence the exec wrapper, not a symlink.
RUN wget -q "https://mafft.cbrc.jp/alignment/software/mafft-7.526-linux.tgz" -O /tmp/mafft.tgz && \
    tar xzf /tmp/mafft.tgz -C /opt && \
    printf '#!/bin/sh\nexec /opt/mafft-linux64/mafft.bat "$@"\n' > /usr/local/bin/mafft && \
    chmod +x /usr/local/bin/mafft && \
    rm /tmp/mafft.tgz && mafft --version || echo "mafft download skipped (optional)"

# fpocket (pocket detection) — not packaged in Debian repos; build from source
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
RUN python -c "import cairosvg; from PIL import Image; print('figure export renderer ready')"

# primer3-py is optional — skip silently if it fails
RUN pip install --no-cache-dir "primer3-py>=2.0.3" 2>/dev/null || echo "primer3-py skipped (optional)"

COPY . .

RUN Rscript tests/test_go_enrichment.R

# Exercise the bundled R analysis and figure export during every backend build.
# The 221-gene SALS subset is a regression fixture, not a biological result.
RUN mkdir -p /tmp/rnaseq-smoke && \
    Rscript app/rnaseq/deseq2_analysis.R \
      app/data/rnaseq/Cer_SALS_every100_validation_subset.tsv \
      app/data/rnaseq/Cer_SALS_metadata.tsv \
      /tmp/rnaseq-smoke condition healthy SALS "" 0.05 1 10 8:40 human && \
    test -s /tmp/rnaseq-smoke/go_enrichment_all.tsv && \
    test -s /tmp/rnaseq-smoke/go_gene_mapping.tsv && \
    test -s /tmp/rnaseq-smoke/analysis_summary.json && \
    test -s /tmp/rnaseq-smoke/pca.svg && \
    test -s /tmp/rnaseq-smoke/dispersion_plot.svg && \
    test -s /tmp/rnaseq-smoke/volcano.svg && \
    test -s /tmp/rnaseq-smoke/deseq2_all_results.tsv && \
    rm -rf /tmp/rnaseq-smoke

RUN useradd -m -u 1000 appuser && chown -R appuser:appuser /app
USER appuser

EXPOSE 7860
CMD ["sh", "-c", "python -c 'import openmm; print(\"OpenMM\", openmm.__version__)' && uvicorn app.main:app --host 0.0.0.0 --port ${PORT:-7860}"]
