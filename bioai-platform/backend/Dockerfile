FROM python:3.11-slim

RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential gcc && \
    rm -rf /var/lib/apt/lists/*

WORKDIR /app
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt
# primer3-py is optional (requires C compiler) — skip silently if it fails
RUN pip install --no-cache-dir primer3-py>=2.0.3 2>/dev/null || echo "primer3-py skipped (optional)"
COPY . .

EXPOSE 7860
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "7860"]
