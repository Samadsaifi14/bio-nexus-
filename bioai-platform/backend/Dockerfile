FROM python:3.11-slim

RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential gcc autoconf automake pkg-config wget && \
    rm -rf /var/lib/apt/lists/*

# Build PhyML from source (~2 min)
RUN wget -qO /tmp/phyml.tar.gz \
      https://github.com/stephaneguindon/phyml/archive/refs/tags/v3.3.20250515.tar.gz && \
    tar xzf /tmp/phyml.tar.gz -C /tmp && \
    cd /tmp/phyml-3.3.20250515 && \
    ./autogen.sh && \
    ./configure --enable-phyml && \
    make -j$(nproc) && \
    make install && \
    cd / && \
    rm -rf /tmp/phyml-3.3.20250515 /tmp/phyml.tar.gz

WORKDIR /app
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt
# primer3-py is optional (requires C compiler) — skip silently if it fails
RUN pip install --no-cache-dir primer3-py>=2.0.3 2>/dev/null || echo "primer3-py skipped (optional)"
COPY . .

EXPOSE 7860
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "7860"]
