# =====================================================================
# Dockerfile — AGENT-OS Backend
# Python 3.11 slim — optimized for Railway deployment
# =====================================================================

FROM python:3.11-slim

# Set working directory
WORKDIR /app

# Install system dependencies
RUN apt-get update && apt-get install -y \
    gcc \
    && rm -rf /var/lib/apt/lists/*

# Copy requirements first (Docker cache optimization)
# If requirements.txt hasn't changed, this layer is cached
COPY requirements.txt .

# Install Python dependencies
RUN pip install --no-cache-dir --upgrade pip && \
    pip install --no-cache-dir -r requirements.txt

# Copy all project files
COPY . .

# Expose port (Railway sets PORT env var automatically)
EXPOSE 8000

# Start the FastAPI server
# Railway injects $PORT automatically — shell form (no brackets) lets it expand correctly
CMD uvicorn main_api:app --host 0.0.0.0 --port $PORT