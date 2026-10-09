FROM python:3.12-slim

WORKDIR /app

# Install system dependencies
RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    curl \
    && rm -rf /var/lib/apt/lists/*

# Copy pyproject dependencies
COPY pyproject.toml .

# Install dependencies
RUN pip install --no-cache-dir \
    fastapi>=0.110.0 \
    uvicorn[standard]>=0.28.0 \
    pydantic>=2.6.0 \
    chromadb>=0.4.22 \
    google-genai>=1.0.0 \
    python-dotenv>=1.0.0 \
    docling>=2.0.0

# Copy application code and assets
COPY app/ ./app/
COPY chroma_db/ ./chroma_db/
COPY data/ ./data/
COPY evaluation/ ./evaluation/
COPY scripts/ ./scripts/

EXPOSE 8000

ENV PYTHONPATH=/app

CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
