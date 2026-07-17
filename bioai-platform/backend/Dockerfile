FROM python:3.11-slim

RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential gcc g++ wget ca-certificates bzip2 xz-utils curl \
    openbabel libgl1-mesa-glx libgomp1 libopenblas-dev \
    libxml2 libxslt1.1 && \
    rm -rf /var/lib/apt/lists/*

# Download pre-compiled PhyML binary from bioconda
RUN wget -qO /tmp/phyml.tar.bz2 \
      https://anaconda.org/bioconda/phyml/3.3.20220408/download/linux-64/phyml-3.3.20220408-h9bc3f66_3.tar.bz2 && \
    tar xjf /tmp/phyml.tar.bz2 -C /tmp && \
    cp /tmp/bin/phyml /usr/local/bin/phyml && \
    chmod +x /usr/local/bin/phyml && \
    rm -rf /tmp/phyml.tar.bz2 /tmp/bin

# Download pre-compiled AutoDock Vina binary from GitHub releases
RUN wget -q "https://github.com/ccsb-scripps/AutoDock-Vina/releases/download/v1.2.7/vina_1.2.7_linux_x86_64" -O /usr/local/bin/vina && \
    chmod +x /usr/local/bin/vina

# Install micromamba for OpenMM (OpenMM is only on conda-forge, not PyPI)
RUN curl -Ls https://micro.mamba.pm/api/micromamba/linux-64/latest | \
    tar -xvj -C /usr/local/bin --strip-components=1 bin/micromamba

WORKDIR /app
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Install OpenMM from conda-forge into a prefix, then link into system Python
ENV MAMBA_ROOT_PREFIX=/opt/conda
RUN micromamba create -y -p /opt/conda/envs/openmm -c conda-forge openmm python=3.11 && \
    SITE=$(/opt/conda/envs/openmm/bin/python -c "import site; print(site.getsitepackages()[0])") && \
    ln -s "$SITE/openmm" "/usr/local/lib/python3.11/site-packages/openmm" && \
    ln -s "$SITE/openmm-$(/opt/conda/envs/openmm/bin/python -c 'import openmm; print(openmm.__version__)')".dist-info \
         "/usr/local/lib/python3.11/site-packages/" 2>/dev/null; \
    python -c "import openmm; print('OpenMM', openmm.__version__, 'installed successfully')"

# primer3-py is optional — skip silently if it fails
RUN pip install --no-cache-dir primer3-py>=2.0.3 2>/dev/null || echo "primer3-py skipped (optional)"

COPY . .

EXPOSE 7860
CMD ["sh", "-c", "python -c 'import openmm; print(\"OpenMM\", openmm.__version__)' && uvicorn app.main:app --host 0.0.0.0 --port ${PORT:-7860}"]
