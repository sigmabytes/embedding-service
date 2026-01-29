# Embedding Service — Phase 1 foundation
# Python 3.10+ per §10.1
FROM python:3.11-slim

WORKDIR /app

# System deps only if needed later (e.g. for sentence-transformers)
RUN apt-get update && apt-get install -y --no-install-recommends \
    curl \
    && rm -rf /var/lib/apt/lists/*

COPY requirements.txt .

# Install CPU-only PyTorch first (~200MB instead of ~2GB+ of CUDA wheels).
# sentence-transformers will use this and not pull GPU deps.
RUN pip install --no-cache-dir torch --index-url https://download.pytorch.org/whl/cpu

RUN pip install --no-cache-dir -r requirements.txt

# Application code; build context is project root
COPY app/ ./app/

ENV PYTHONPATH=/app

EXPOSE 8000

CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
