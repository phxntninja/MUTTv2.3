# Phase 2 Handoff: Observability (Claude)

Role: Observability Lead

Objective: Implement Phase 2 observability with structured JSON logging and distributed tracing, fully opt‑in and backwards compatible.

Background
- Repo: MUTT v2.x — microservices under `services/` (ingestor, alerter, moog forwarder, web_ui).
- Phase 1 complete: standardized tooling (Black/isort/Ruff/MyPy), opt‑in DynamicConfig reads (`DYNAMIC_CONFIG_ENABLED`), incremental typing/docstrings, unit tests. CI enforces Ruff/MyPy.
- Current logging: ad‑hoc text logs with correlation IDs; no structured JSON; no tracing.

Scope
- Add JSON logging (opt‑in via `LOG_JSON_ENABLED`).
- Add OpenTelemetry tracing (opt‑in via `OTEL_ENABLED`) with context propagation and log/trace correlation.
- Keep behavior unchanged with flags off. No business logic changes.

Deliverables
1) `services/logging_utils.py`
   - `setup_json_logging(service_name: str, version: str, level: str = "INFO")`.
   - NDJSON formatter with fields: `timestamp`, `level`, `message`, `logger`, `module`, `function`, `line`, `thread`, `service`, `version`, `pod_name`, `correlation_id`, `trace_id`, `span_id`.
   - Safe fallback to plain logging if disabled.

2) `services/tracing_utils.py`
   - Safe imports; no‑op if OTEL not installed or flags off.
   - `setup_tracing(service_name: str, version: str)` sets `TracerProvider` + OTLP exporter (gRPC), resource attributes, and instruments Flask/Requests/Redis/Psycopg2.
   - Helpers: `get_current_trace_ids()`, `extract_tracecontext(flask_request)`, `inject_tracecontext(headers: dict)`.

3) Service wiring (minimal, guarded)
   - `services/ingestor_service.py`, `services/web_ui_service.py`: call `setup_json_logging` and `setup_tracing` at startup when flags set; extract `traceparent` in `before_request`.
   - `services/alerter_service.py`, `services/moog_forwarder_service.py`: call setup; wrap core processing (message/alert handling) in manual spans; include attributes (queue names, rule id, sizes, statuses).
   - Logs always include `correlation_id`; include `trace_id`/`span_id` when tracing enabled.

Configuration (env flags)
- `LOG_JSON_ENABLED` (default: false)
- `OTEL_ENABLED` (default: false)
- `OTEL_EXPORTER_OTLP_ENDPOINT` (e.g., `http://otel-collector:4317`)
- `OTEL_SERVICE_NAME` (defaults per service) and `OTEL_RESOURCE_ATTRIBUTES` (optional)
- Note: dynamic reads can be added later via existing `DynamicConfig` pattern if desired.

Requirements (Python 3.10/3.11 compatible; defaults OK)
- `opentelemetry-api>=1.24`
- `opentelemetry-sdk>=1.24`
- `opentelemetry-exporter-otlp-proto-grpc>=1.24`
- `opentelemetry-instrumentation-flask`
- `opentelemetry-instrumentation-requests`
- `opentelemetry-instrumentation-redis`
- `opentelemetry-instrumentation-psycopg2`

Acceptance Criteria
- Flags off (default): behavior/logs unchanged; full test suite passes.
- With `LOG_JSON_ENABLED=true`: logs are valid NDJSON lines with `correlation_id` present.
- With `OTEL_ENABLED=true` and OTLP endpoint reachable:
  - HTTP services emit spans with proper parent/child relationships.
  - Worker services emit spans around core processing; auto‑instrumentation active (Redis/DB/HTTP) where supported.
  - Logs include `trace_id`/`span_id` matching exported spans.

Implementation Plan
1. Add `logging_utils.py` + unit tests for JSON payload shape and correlation defaulting.
2. Add `tracing_utils.py` + unit tests guarded with `importorskip` or try/skip when OTEL missing; ensure no‑op behavior when disabled.
3. Wire Web UI as reference (guarded by flags), then Ingestor. Add minimal manual spans in Alerter/Forwarder around processing loops.
4. Pin OTEL deps in `requirements.txt`. CI unchanged (paths guarded when flags off and OTEL not installed).
5. Docs: `docs/OBSERVABILITY.md` (flags, schema, collector setup). Update README observability quick steps.

Validation
- Local: flags off → `pytest -v` green; logs unchanged.
- JSON logs: `LOG_JSON_ENABLED=true` → verify NDJSON with `correlation_id`.
- Tracing: `OTEL_ENABLED=true OTEL_EXPORTER_OTLP_ENDPOINT=http://localhost:4317` → verify spans in collector; logs include `trace_id`/`span_id`.

Stretch (later)
- OTLP Logs exporter to ship logs to collector with trace correlation once tracing is stable.

