# Build stage
FROM registry-1.docker.io/python:3.10-slim AS builder

# Build arguments for proxy (optional)
ARG HTTP_PROXY
ARG HTTPS_PROXY
ARG NO_PROXY

# Build argument for pip index URL (default: Tsinghua mirror)
ARG PIP_INDEX_URL=https://pypi.tuna.tsinghua.edu.cn/simple

# Set proxy environment variables if provided
ENV HTTP_PROXY=${HTTP_PROXY}
ENV HTTPS_PROXY=${HTTPS_PROXY}
ENV NO_PROXY=${NO_PROXY}

WORKDIR /app

# Create virtual environment and install dependencies
COPY pyproject.toml ./
RUN python -m venv /opt/venv
ENV PATH="/opt/venv/bin:$PATH"

RUN pip config set global.index-url ${PIP_INDEX_URL} && \
    pip config set global.timeout 120 && \
    pip install --no-cache-dir .

# Runtime stage
FROM registry-1.docker.io/python:3.10-slim

# Build arguments for proxy (optional)
ARG HTTP_PROXY
ARG HTTPS_PROXY
ARG NO_PROXY

# Set proxy environment variables if provided
ENV HTTP_PROXY=${HTTP_PROXY}
ENV HTTPS_PROXY=${HTTPS_PROXY}
ENV NO_PROXY=${NO_PROXY}

WORKDIR /app

# Install gosu for proper user switching
RUN apt-get update && apt-get install -y --no-install-recommends gosu && rm -rf /var/lib/apt/lists/*

# Create non-root user
RUN groupadd -r ollama && useradd -r ollama -g ollama

# Copy virtual environment from builder
COPY --from=builder /opt/venv /opt/venv
ENV PATH="/opt/venv/bin:$PATH"

# Copy source code
COPY ollama_router ./ollama_router
COPY config.yaml.example ./config.yaml.example
COPY templates ./templates

# Create directories with proper permissions
RUN mkdir -p /app/logs /app/state && chown -R ollama:ollama /app

# Copy scripts
COPY scripts/docker-entrypoint.sh scripts/healthcheck.py /app/
RUN chmod +x /app/docker-entrypoint.sh /app/healthcheck.py

# Don't switch user here - let entrypoint handle it after fixing permissions

# Environment
ENV PYTHONUNBUFFERED=1
ENV LOG_LEVEL=INFO
ENV LOG_FILE=logs/ollama_router.log

# Expose port
EXPOSE 11435

# Graceful shutdown signal
STOPSIGNAL SIGTERM

# Health check using Python (curl not available in slim image)
HEALTHCHECK --interval=30s --timeout=10s --start-period=5s --retries=3 \
  CMD ["python", "/app/healthcheck.py"]

# Entrypoint
ENTRYPOINT ["/app/docker-entrypoint.sh"]
CMD ["python", "-m", "ollama_router"]
