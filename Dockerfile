# ================================
# Ciicerone API - Production Dockerfile
# ================================
# Multi-stage build for optimized container size

# Stage 1: Builder
FROM python:3.11-slim as builder

# Set working directory
WORKDIR /build

# Install build dependencies
RUN apt-get update && apt-get install -y --no-install-recommends \
    gcc \
    g++ \
    make \
    libpq-dev \
    && rm -rf /var/lib/apt/lists/*

# Copy requirements
COPY requirements.txt requirements-dev.txt ./

# Create virtual environment and install dependencies
RUN python -m venv /opt/venv
ENV PATH="/opt/venv/bin:$PATH"

# Install Python packages
RUN pip install --no-cache-dir --upgrade pip setuptools wheel && \
    pip install --no-cache-dir -r requirements.txt

# Stage 2: Runtime
FROM python:3.11-slim

# Set labels
LABEL maintainer="Ciicerone Team"
LABEL description="Ciicerone - AI-Powered Threat Simulation Platform"
LABEL version="0.1.0"

# Set environment variables
ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    PATH="/opt/venv/bin:$PATH" \
    PYTHONPATH="/app:$PYTHONPATH"

# Create app user
RUN groupadd -r ciicerone && useradd -r -g ciicerone ciicerone

# Install runtime dependencies
RUN apt-get update && apt-get install -y --no-install-recommends \
    libpq5 \
    curl \
    && rm -rf /var/lib/apt/lists/*

# Set working directory
WORKDIR /app

# Copy virtual environment from builder
COPY --from=builder /opt/venv /opt/venv

# Copy application code
COPY --chown=ciicerone:ciicerone ciicerone/ /app/ciicerone/
COPY --chown=ciicerone:ciicerone templates/ /app/templates/
COPY --chown=ciicerone:ciicerone config.yaml /app/
COPY --chown=ciicerone:ciicerone pyproject.toml /app/

# Create necessary directories
RUN mkdir -p /app/data /app/logs /app/generated_content /app/reports /app/output && \
    chown -R ciicerone:ciicerone /app

# Switch to app user
USER ciicerone

# Expose port
EXPOSE 8000

# Health check
HEALTHCHECK --interval=30s --timeout=10s --start-period=40s --retries=3 \
    CMD curl -f http://localhost:8000/health || exit 1

# Default command - run API server
CMD ["python", "-m", "uvicorn", "ciicerone.api.main:app", "--host", "0.0.0.0", "--port", "8000", "--workers", "4"]
