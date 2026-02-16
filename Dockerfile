FROM python:3.11-slim

WORKDIR /app

# System dependencies
RUN apt-get update && apt-get install -y --no-install-recommends \
    curl && \
    rm -rf /var/lib/apt/lists/*

# Python dependencies
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Application code
COPY hvac_main.py hvac_impl.py hvac_routing.py hvac_inventory.py hvac_auth.py ./
COPY hvac_voice.py hvac_telnyx.py ./
COPY static/ ./static/

# Create log directory
RUN mkdir -p /app/logs

# Environment defaults
ENV MOCK_MODE=1
ENV LOG_DIR=/app/logs
ENV PYTHONUNBUFFERED=1

EXPOSE 8000

HEALTHCHECK --interval=30s --timeout=10s --retries=3 \
    CMD curl -f http://localhost:8000/health || exit 1

CMD ["uvicorn", "hvac_main:app", "--host", "0.0.0.0", "--port", "8000", "--workers", "1"]
