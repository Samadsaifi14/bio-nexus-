FROM python:3.11-slim

RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential gcc wget ca-certificates && \
    rm -rf /var/lib/apt/lists/*

# Download pre-compiled PhyML binary from bioconda
RUN wget -qO /tmp/phyml.tar.bz2 \
      https://anaconda.org/bioconda/phyml/3.3.20220408/download/linux-64/phyml-3.3.20220408-h9bc3f66_3.tar.bz2 && \
    tar xjf /tmp/phyml.tar.bz2 -C /tmp && \
    cp /tmp/bin/phyml /usr/local/bin/phyml && \
    chmod +x /usr/local/bin/phyml && \
    rm -rf /tmp/phyml.tar.bz2 /tmp/bin

WORKDIR /app
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt
# primer3-py is optional (requires C compiler) — skip silently if it fails
RUN pip install --no-cache-dir primer3-py>=2.0.3 2>/dev/null || echo "primer3-py skipped (optional)"
COPY . .

EXPOSE 7860
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "7860"]
