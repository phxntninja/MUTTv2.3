# MUTT v2 - Phase 2 Observability Guide

## Overview

MUTT v2 Phase 2 introduces production-grade observability through structured JSON logging and distributed tracing with OpenTelemetry. Both features are opt-in and fully backwards compatible.

## Quick Start

### JSON Logging Only
### Full Observability  
\Defaulting to user installation because normal site-packages is not writeable
Collecting Flask==2.3.3 (from -r requirements.txt (line 8))
  Using cached flask-2.3.3-py3-none-any.whl.metadata (3.6 kB)
Collecting gunicorn==21.2.0 (from -r requirements.txt (line 9))
  Using cached gunicorn-21.2.0-py3-none-any.whl.metadata (4.1 kB)
Collecting psycopg2-binary==2.9.9 (from -r requirements.txt (line 12))
  Using cached psycopg2-binary-2.9.9.tar.gz (384 kB)
  Installing build dependencies: started
  Installing build dependencies: finished with status 'done'
  Getting requirements to build wheel: started
  Getting requirements to build wheel: finished with status 'error'
## Configuration

| Variable | Default | Description |
|----------|---------|-------------|
| LOG_JSON_ENABLED | false | Enable JSON logging |
| LOG_LEVEL | INFO | Logging level |
| OTEL_ENABLED | false | Enable OpenTelemetry tracing |
| OTEL_EXPORTER_OTLP_ENDPOINT | http://localhost:4317 | OTLP collector endpoint |
| POD_NAME | unknown | Kubernetes pod name |

## Features

### JSON Logging
- NDJSON format for easy parsing
- Includes correlation_id, trace_id, span_id
- Custom fields via extra parameter
- Backwards compatible

### Distributed Tracing  
- W3C Trace Context propagation
- Auto-instrumentation: Flask, Redis, PostgreSQL, HTTP
- Manual spans for worker services
- Log-trace correlation

## See Also
- services/logging_utils.py - JSON logging implementation
- services/tracing_utils.py - Tracing implementation
- tests/test_logging_utils.py - Test examples
