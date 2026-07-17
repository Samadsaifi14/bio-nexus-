FROM python:3.11-slim

RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential gcc g++ wget ca-certificates openbabel \
    libgl1-mesa-glx libgomp1 libopenblas-dev \
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

WORKDIR /app
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Install OpenMM directly into system Python
RUN pip install --no-cache-dir openmm && \
    python -c "import openmm; print('OpenMM', openmm.__version__, 'installed successfully')" || \
    echo "FAILED: pip install openmm did not work"

# Verify OpenMM is importable
RUN python -c "from openmm.app import PDBFile, ForceField, OBC2, Modeller; print('OpenMM app modules OK')" || \
    echo "FAILED: OpenMM app modules not importable"

# primer3-py is optional — skip silently if it fails
RUN pip install --no-cache-dir primer3-py>=2.0.3 2>/dev/null || echo "primer3-py skipped (optional)"

COPY . .

EXPOSE 7860
CMD ["sh", "-c", "python -c 'import openmm; print(\"OpenMM\", openmm.__version__)' && uvicorn app.main:app --host 0.0.0.0 --port ${PORT:-7860}"]
