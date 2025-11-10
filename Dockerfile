# =====================================================================
# MUTT v2.3 - Multi-Stage Dockerfile
# =====================================================================
# This Dockerfile builds all 4 MUTT services using a multi-stage pattern.
#
# Build all services:
#   docker build --target ingestor -t mutt-ingestor:2.3 .
#   docker build --target alerter -t mutt-alerter:2.3 .
#   docker build --target moog-forwarder -t mutt-moog-forwarder:2.3 .
#   docker build --target webui -t mutt-webui:2.3 .
#
# Or use docker-compose (recommended):
#   docker-compose build
# =====================================================================

# =====================================================================
# Base Stage - Common dependencies
#
# Multi-arch note:
# - This Dockerfile pins a linux/amd64 digest for reproducibility.
# - To build for other architectures, use buildx and override platform:
#     docker buildx build --platform linux/arm64 -t your/repo:mutt-2.5 --target webui .
# - Consider pinning the corresponding digest for your target arch.
# =====================================================================
# Pinned base image for reproducibility (linux/amd64)
FROM python:3.10-slim@sha256:2ade04f16d1e0bbde15b0a5a2586e180c060df230333e0d951660020557fcba4 as base

# Install system dependencies
RUN apt-get update && apt-get install -y \
    curl \
    gcc \
    libpq-dev \
    && rm -rf /var/lib/apt/lists/*

# Create app directory
WORKDIR /app

# Copy requirements and install Python dependencies
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy service files
COPY services/ ./services/

# Create non-root user
RUN useradd -m -u 1000 mutt && chown -R mutt:mutt /app
USER mutt

# =====================================================================
# Ingestor Service
# =====================================================================
FROM base as ingestor

EXPOSE 8080

# Health check
HEALTHCHECK --interval=30s --timeout=10s --start-period=5s --retries=3 \
    CMD curl -f http://localhost:8080/health || exit 1

# Run with gunicorn
CMD ["gunicorn", \
     "--bind", "0.0.0.0:8080", \
     "--workers", "4", \
     "--threads", "2", \
     "--worker-class", "gthread", \
     "--access-logfile", "-", \
     "--error-logfile", "-", \
     "--log-level", "info", \
     "services.ingestor_service:create_app()"]

# =====================================================================
# Alerter Service
# =====================================================================
FROM base as alerter

EXPOSE 8081 9091

# Health check
HEALTHCHECK --interval=30s --timeout=10s --start-period=5s --retries=3 \
    CMD curl -f http://localhost:8081/health || exit 1

# Run alerter (long-running worker)
CMD ["python3", "services/alerter_service.py"]

# =====================================================================
# Moog Forwarder Service
# =====================================================================
FROM base as moog-forwarder

EXPOSE 8082 9092

# Health check
HEALTHCHECK --interval=30s --timeout=10s --start-period=5s --retries=3 \
    CMD curl -f http://localhost:8082/health || exit 1

# Run moog forwarder (long-running worker)
CMD ["python3", "services/moog_forwarder_service.py"]

# =====================================================================
# Web UI Service
# =====================================================================
FROM base as webui

EXPOSE 8090

# Health check
HEALTHCHECK --interval=30s --timeout=10s --start-period=5s --retries=3 \
    CMD curl -f http://localhost:8090/health || exit 1

# Run with gunicorn
CMD ["gunicorn", \
     "--bind", "0.0.0.0:8090", \
     "--workers", "2", \
     "--threads", "2", \
     "--worker-class", "gthread", \
     "--access-logfile", "-", \
     "--error-logfile", "-", \
     "--log-level", "info", \
     "services.web_ui_service:create_app()"]
