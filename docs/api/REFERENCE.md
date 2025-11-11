MUTT v2.5 — API Reference (Code-Level)

This document describes the HTTP APIs exposed by MUTT services, including request/response formats, error codes, authentication, and versioning headers. Paths default to v2 where available; v1 remains for compatibility.

Authentication
- Header: X-API-KEY: <key>
- Required on all Web UI endpoints except /health and /metrics.
- Ingestor requires X-API-KEY on /api/v2/ingest.
- Errors: 401 Unauthorized for missing/invalid key

Versioning
- Headers on responses:
  - X-API-Version: v2.5
  - X-API-Deprecated: true|false (true on /api/v1/*)
  - X-API-Supported-Versions: v2.5, v2.0, v1.0

Ingestor Service
- Base: http://<host>:8080

POST /api/v2/ingest
- Ingest a single event (JSON object).
- Request body keys: timestamp, message, hostname, optional syslog_severity.
- Response 200: { "status": "queued", "correlation_id": "...", "queue_depth": N }
- Errors: 400 (invalid JSON / missing fields), 401 (auth), 503 (Redis)

Web UI Service
- Base: http://<host>:8090

Public (no auth)
- GET /health — returns Redis + DB status
- GET /metrics — Prometheus metrics

Metrics API
- GET /api/v2/metrics — real-time ingestion metrics (cached ~5s)

Rules API (CRUD)
- GET /api/v2/rules
- GET /api/v2/rules/{id}
- POST /api/v2/rules
- PUT /api/v2/rules/{id}
- DELETE /api/v2/rules/{id}
- Fields: match_string, trap_oid, syslog_severity, match_type (contains|regex|oid_prefix), priority, prod_handling, dev_handling, team_assignment, is_active

Audit Logs (Events)
- GET /api/v2/audit-logs
- Query: page, limit, hostname, rule_id, start_date, end_date

Config Audit (Changes)
- GET /api/v2/config-audit
- Query: page, limit, changed_by, table_name, record_id, operation, start_date, end_date

Dev Hosts
- GET /api/v2/dev-hosts
- POST /api/v2/dev-hosts — body: { "hostname": "dev-host-1" }
- DELETE /api/v2/dev-hosts/{hostname}

Teams
- GET /api/v2/teams
- POST /api/v2/teams — body: { "hostname": "host-a", "team_assignment": "NetOps" }
- PUT /api/v2/teams/{hostname} — body: { "team_assignment": "SRE" }
- DELETE /api/v2/teams/{hostname}

Alerter Service
- Health: http://<host>:8081/health
- Metrics: http://<host>:8082/metrics

Moog Forwarder
- Health: http://<host>:8084/health
- Metrics: http://<host>:8083/metrics
- Metrics include webhook latency, DLQ depth, circuit breaker state and trips

Common Error Codes
- 200 OK
- 201 Created
- 400 Bad Request (JSON/validation)
- 401 Unauthorized
- 404 Not Found
- 503 Service Unavailable (backend error)

Headers Summary
- X-API-Version: current service version (v2.5)
- X-API-Deprecated: true on v1 paths
- X-API-Supported-Versions: supported list
