# Backend Dockerfile
FROM python:3.11-slim

WORKDIR /app

# Install system dependencies
RUN apt-get update && apt-get install -y \
    gcc \
    libpq-dev \
    && rm -rf /var/lib/apt/lists/*

# Copy application code first (needed for editable install)
COPY . .

# Install Python dependencies
RUN pip install --no-cache-dir -e .

# Create data directory for caching
RUN mkdir -p /app/data/nba_api_cache

# Expose port
EXPOSE 8000

# Run the application
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
