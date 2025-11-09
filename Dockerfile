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
# =====================================================================
FROM python:3.9-slim as base

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
COPY services/ ./

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
     "ingestor_service:create_app()"]

# =====================================================================
# Alerter Service
# =====================================================================
FROM base as alerter

EXPOSE 8081 9091

# Health check
HEALTHCHECK --interval=30s --timeout=10s --start-period=5s --retries=3 \
    CMD curl -f http://localhost:8081/health || exit 1

# Run alerter (long-running worker)
CMD ["python3", "alerter_service.py"]

# =====================================================================
# Moog Forwarder Service
# =====================================================================
FROM base as moog-forwarder

EXPOSE 8082 9092

# Health check
HEALTHCHECK --interval=30s --timeout=10s --start-period=5s --retries=3 \
    CMD curl -f http://localhost:8082/health || exit 1

# Run moog forwarder (long-running worker)
CMD ["python3", "moog_forwarder_service.py"]

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
     "web_ui_service:create_app()"]
