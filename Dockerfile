FROM python:3.11-slim

WORKDIR /app

# System dependencies (curl for healthcheck, build-essential for vroom C extensions)
RUN apt-get update && apt-get install -y --no-install-recommends \
    curl build-essential && \
    rm -rf /var/lib/apt/lists/*

# Python dependencies
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Application code — copy ALL Python modules
COPY hvac_main.py hvac_impl.py hvac_routing.py hvac_inventory.py hvac_auth.py ./
COPY hvac_voice.py hvac_telnyx.py hvac_payment.py hvac_crm.py hvac_livekit.py ./
COPY hvac_schema.sql ./
COPY static/ ./static/
COPY landing.html web_demo.html ./

# Create log and data directories
RUN mkdir -p /app/logs /app/data /app/recordings

# Environment defaults
ENV MOCK_MODE=0
ENV LOG_DIR=/app/logs
ENV PYTHONUNBUFFERED=1
ENV PORT=8000

EXPOSE ${PORT}

HEALTHCHECK --interval=30s --timeout=10s --retries=3 \
    CMD curl -f http://localhost:${PORT}/health || exit 1

# Railway uses $PORT env var
CMD uvicorn hvac_main:app --host 0.0.0.0 --port ${PORT} --workers 1
