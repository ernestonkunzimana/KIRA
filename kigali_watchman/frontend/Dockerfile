# KIRA - Service 3: Command Center Dashboard (Frontend)
# Security-hardened production Dockerfile
# Base image: pinned to specific version, non-root user, minimal attack surface

FROM python:3.10.14-slim-bookworm

# Metadata labels for security scanning and tracking
LABEL maintainer="KIRA Team"
LABEL version="2.4.0"
LABEL description="KIRA - Command Center Dashboard (Streamlit Frontend)"
LABEL security="production-hardened"

WORKDIR /app

# System security: install only runtime essentials
RUN apt-get update && apt-get install -y --no-install-recommends \
    ca-certificates \
    && rm -rf /var/lib/apt/lists/* \
    && apt-get clean

# Python dependencies
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Application code (immutable after build)
COPY . .

# Create non-root user with minimal privileges
RUN useradd -m -u 1002 -s /usr/sbin/nologin -d /home/streamlit streamlit \
    && chown -R streamlit:streamlit /app

# Switch to non-root user
USER streamlit

# Set Python environment variables for Streamlit
ENV PYTHONUNBUFFERED=1
ENV PYTHONDONTWRITEBYTECODE=1

# Streamlit configuration (security: disable telemetry, set secure defaults)
ENV STREAMLIT_SERVER_HEADLESS=true
ENV STREAMLIT_LOGGER_LEVEL=info
ENV STREAMLIT_CLIENT_SHOWERRORDETAILS=false

# Expose Streamlit port (documentation only; port binding happens at runtime)
EXPOSE 8501

# Entrypoint: Streamlit with hardened security flags
CMD ["streamlit", "run", "dashboard.py", \
     "--server.port=8501", \
     "--server.address=0.0.0.0", \
     "--logger.level=info", \
     "--client.showErrorDetails=false"]
