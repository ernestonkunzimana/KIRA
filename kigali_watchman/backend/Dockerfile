# KIRA - Service 2: Core API (Backend)
# Security-hardened production Dockerfile
# Base image: pinned to specific version (NOT 'latest' or 'slim')
# Non-root user enforced, multi-stage optimization, minimal attack surface

# Stage 1: Builder (compiles dependencies)
FROM python:3.11.9-slim-bookworm AS builder

WORKDIR /build

# Install build dependencies (needed for pip compile)
RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    libssl-dev \
    libffi-dev \
    && rm -rf /var/lib/apt/lists/*

# Copy and pre-compile requirements
COPY requirements.txt .
RUN pip install --no-cache-dir --user -r requirements.txt


# Stage 2: Runtime (minimal, production image)
FROM python:3.11.9-slim-bookworm AS runtime

# Metadata labels for security scanning and tracking
LABEL maintainer="KIRA Team"
LABEL version="2.4.0"
LABEL description="KIRA - Kigali Intelligent Resilience Agent Core API"
LABEL security="production-hardened"

WORKDIR /app

# System security: install only runtime essentials, drop unnecessary packages
RUN apt-get update && apt-get install -y --no-install-recommends \
    ca-certificates \
    curl \
    && rm -rf /var/lib/apt/lists/* \
    && apt-get clean

# Copy pre-compiled Python packages from builder
COPY --from=builder /root/.local /home/kira/.local

# Copy application code (immutable after build)
COPY . .

# Create non-root user with minimal privileges (UID > 1000 for better security)
RUN useradd -m -u 1001 -s /usr/sbin/nologin -d /home/kira kira \
    && chown -R kira:kira /app \
    && chmod -R 755 /app

# Ensure runtime-writable directories exist and are owned by the non-root user.
# Avoid declaring VOLUME for these paths in the Dockerfile because Docker will
# initialize anonymous volumes at runtime with root ownership which causes
# permission errors for a non-root runtime user. Manage mounts from compose
# or runtime instead.
RUN mkdir -p /app/logs /app/audit \
    && chown -R 1001:1001 /app/logs /app/audit

# Note: We intentionally keep the final image user as root so the entrypoint
# can run privileged initialization (chown of bind mounts). The entrypoint
# script will drop privileges to `kira` (UID 1001) before executing the app.

# Set Python environment variables
ENV PATH="/home/kira/.local/bin:$PATH"
ENV PYTHONUNBUFFERED=1
ENV PYTHONDONTWRITEBYTECODE=1

# Security: mark filesystem as read-only (enforced by docker-compose or k8s)
# Applications using temporary storage should mount volumes explicitly

# Health check (SRE / orchestration probes)
HEALTHCHECK --interval=30s --timeout=10s --start-period=60s --retries=3 \
  CMD curl -f http://localhost:5000/api/v1/health || exit 1

# Expose port (documentation only; port binding happens at runtime)
EXPOSE 5000

# Copy and install the privileged entrypoint that will fix ownership of
# mounted host directories then drop to the non-root runtime user.
COPY entrypoint.py /usr/local/bin/entrypoint.py
RUN chmod +x /usr/local/bin/entrypoint.py

# Entrypoint runs as PID 1 (initialization + privilege drop)
ENTRYPOINT ["python3", "/usr/local/bin/entrypoint.py"]

# Production entrypoint: gunicorn with 4 workers
# Workers auto-scale based on CPU cores if run with --worker-class gthread
CMD ["gunicorn", \
     "--bind", "0.0.0.0:5000", \
     "--workers", "4", \
     "--worker-class", "sync", \
     "--timeout", "120", \
     "--log-level", "info", \
     "--access-logfile", "-", \
     "--error-logfile", "-", \
     "main:create_app()"]
