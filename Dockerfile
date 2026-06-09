# ── IoT Telemetry Simulator ───────────────────────────────────────────────────
FROM python:3.10-slim

WORKDIR /app

# Install dependencies first (layer-cached)
COPY requirements.txt .
RUN pip install --no-cache-dir requests==2.31.0

# Copy simulator source
COPY app.py .

# Default: push every 5 seconds. Override with: docker run ... --interval 10
ENTRYPOINT ["python", "app.py"]
CMD ["--interval", "5"]