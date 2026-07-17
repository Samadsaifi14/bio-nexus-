FROM python:3.11-slim

RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential gcc g++ wget ca-certificates openbabel \
    libgl1-mesa-glx libgomp1 libopenblas-dev && \
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

# Install micromamba
RUN wget -qO /tmp/micromamba.tar.bz2 "https://micro.mamba.pm/api/micromamba/linux-64/latest" && \
    tar -xjf /tmp/micromamba.tar.bz2 -C /usr/local/bin --strip-components=1 bin/micromamba && \
    rm /tmp/micromamba.tar.bz2

# Create conda env with OpenMM + Python — all pip deps install into this env
RUN micromamba create -n app -c conda-forge openmm python=3.11 -y --root-workdir /opt/conda

# All subsequent commands run inside the conda env
ENV PATH="/opt/conda/envs/app/bin:$PATH"
ENV PYTHONPATH="/opt/conda/envs/app/lib/python3.11/site-packages"

WORKDIR /app
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# primer3-py is optional (requires C compiler) — skip silently if it fails
RUN pip install --no-cache-dir primer3-py>=2.0.3 2>/dev/null || echo "primer3-py skipped (optional)"

COPY . .

EXPOSE 7860
CMD ["sh", "-c", "uvicorn app.main:app --host 0.0.0.0 --port ${PORT:-7860}"]
