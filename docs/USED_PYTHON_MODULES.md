# MUTT v2.5 — Python Modules Used

Purpose
- This document enumerates Python packages/modules used by the repository to assist with enterprise approval.
- Grouped by runtime (required), optional/observability, and test/dev.

Notes
- Package names (as in pip/requirements) and their typical import module names are shown.
- Some packages are optional (observability) and not required for core operation.

Runtime (Production) Dependencies
- Flask (import: `flask`)
- gunicorn (run-time process manager; not imported by app code)
- psycopg2-binary (import: `psycopg2`)
- redis (import: `redis`)
- hvac (import: `hvac`)
- requests (import: `requests`)
- prometheus-client (import: `prometheus_client`)
- prometheus-flask-exporter (import: `prometheus_flask_exporter`)

Optional / Observability (Feature-flagged)
- opentelemetry-api (import: `opentelemetry`)
- opentelemetry-sdk (import: `opentelemetry`)
- opentelemetry-exporter-otlp-proto-grpc (import: `opentelemetry.exporter.otlp`)
- opentelemetry-instrumentation-flask (import: `opentelemetry.instrumentation.flask`)
- opentelemetry-instrumentation-requests (import: `opentelemetry.instrumentation.requests`)
- opentelemetry-instrumentation-redis (import: `opentelemetry.instrumentation.redis`)
- opentelemetry-instrumentation-psycopg2 (import: `opentelemetry.instrumentation.psycopg2`)

Test / Dev Dependencies
- pytest (import: `pytest`)
- pytest-cov
- pytest-mock
- pytest-xdist
- coverage
- mock
- pytest-flake8
- pytest-pylint
- pytest-benchmark
- pytest-html
- pytest-json-report
- requests-mock (import: `requests_mock`)

Internal Modules (for completeness; not external packages)
- Top-level packages under this repo used by the code: `services`, `scripts` (e.g., `services.api_versioning`, `services.web_ui_service`, etc.)

Source Files Referenced
- Runtime requirements: `requirements.txt`
- Test/dev requirements: `tests/requirements-test.txt`

