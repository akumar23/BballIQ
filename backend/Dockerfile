# Backend Dockerfile - production-ready with security hardening
FROM python:3.11-slim-bookworm

WORKDIR /app

# Install system dependencies
RUN apt-get update && apt-get install -y \
    gcc \
    libpq-dev \
    && rm -rf /var/lib/apt/lists/*

# Create non-root user and group
RUN groupadd --system app && useradd --system --gid app --home /app --shell /usr/sbin/nologin app

# Copy dependency metadata first (before application code) for better Docker layer caching
# This way code changes don't invalidate the pip install layer
COPY pyproject.toml ./

# Install Python dependencies as root (required for pip)
RUN pip install --no-cache-dir -e .

# Create data directory and set ownership
RUN mkdir -p /app/data/nba_api_cache && chown -R app:app /app/data

# Copy application code (after deps are installed)
COPY --chown=app:app . .

# Copy and configure entrypoint script
COPY entrypoint.sh /entrypoint.sh
RUN chmod +x /entrypoint.sh && chown app:app /entrypoint.sh

# Switch to non-root user for runtime
USER app

# Expose port
EXPOSE 8000

# Health check - the FastAPI app exposes /health endpoint
HEALTHCHECK --interval=30s --timeout=5s --start-period=10s --retries=3 \
    CMD python -c "import httpx; httpx.get('http://localhost:8000/health').raise_for_status()" || exit 1

# Entrypoint runs migrations before the main command
ENTRYPOINT ["/entrypoint.sh"]

# Run the application
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
