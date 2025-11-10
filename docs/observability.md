# MUTT v2 - Phase 2 Observability Guide

## Overview

MUTT v2 Phase 2 introduces production-grade observability through **structured JSON logging** and **distributed tracing** with OpenTelemetry. Both features are **opt-in** and fully backwards compatible.

### Key Features

- ✅ **Structured JSON Logging** (NDJSON format)
- ✅ **Distributed Tracing** with OpenTelemetry  
- ✅ **Log-Trace Correlation** (automatic trace_id/span_id injection)
- ✅ **Auto-instrumentation** (Flask, Redis, PostgreSQL, HTTP clients)
- ✅ **Manual Spans** for worker services
- ✅ **Zero Impact** when disabled (default behavior)
- ✅ **Backwards Compatible** with existing correlation IDs

---

## Quick Start

### Minimal Setup (JSON Logging Only)

\`\`\`bash
# Enable JSON logging
export LOG_JSON_ENABLED=true

# Run service
python services/web_ui_service.py
\`\`\`

Logs will now be output as NDJSON:

\`\`\`json
{"timestamp":"2025-11-09T12:00:00Z","level":"INFO","message":"Service started","service":"web_ui","correlation_id":"abc-123"}
\`\`\`

### Full Observability (Logging + Tracing)

\`\`\`bash
# Install dependencies
pip install -r requirements.txt

# Enable features
export LOG_JSON_ENABLED=true
export OTEL_ENABLED=true
export OTEL_EXPORTER_OTLP_ENDPOINT=http://localhost:4317

# Run service
python services/web_ui_service.py
\`\`\`

---

## Configuration Reference

### Environment Variables

| Variable | Default | Description |
|----------|---------|-------------|
| \`LOG_JSON_ENABLED\` | \`false\` | Enable JSON logging |
| \`LOG_LEVEL\` | \`INFO\` | Logging level |
| \`OTEL_ENABLED\` | \`false\` | Enable tracing |
| \`OTEL_EXPORTER_OTLP_ENDPOINT\` | \`http://localhost:4317\` | OTLP collector |
| \`POD_NAME\` | \`unknown\` | Pod identifier |

See full documentation in the repository.

