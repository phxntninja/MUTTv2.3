API Versioning

Overview
- Current service API version: v2.5.
- Backward‑compatible v2 aliases exist alongside all `/api/v1/*` Web UI endpoints.
- Responses include version headers to aid clients during migration.

Response Headers
- `X-API-Version`: current service API version (v2.5)
- `X-API-Deprecated`: `true` on `/api/v1/*` routes, `false` on `/api/v2/*`

Version Aliases
- Ingestor
  - `POST /ingest` (stable)
  - `POST /api/v1/ingest` (deprecated)
  - `POST /api/v2/ingest` (preferred)

- Web UI (all require `X-API-KEY` unless noted)
  - Metrics: `GET /api/v1/metrics` and `GET /api/v2/metrics`
  - Rules: `GET|POST /api/v1/rules` and `/api/v2/rules`
    - `PUT|DELETE /api/v1/rules/{id}` and `/api/v2/rules/{id}`
  - Audit Logs: `GET /api/v1/audit-logs` and `/api/v2/audit-logs`
  - Dev Hosts: `GET|POST /api/v1/dev-hosts` and `/api/v2/dev-hosts`
    - `DELETE /api/v1/dev-hosts/{hostname}` and `/api/v2/dev-hosts/{hostname}`
  - Teams: `GET|POST /api/v1/teams` and `/api/v2/teams`
    - `PUT|DELETE /api/v1/teams/{hostname}` and `/api/v2/teams/{hostname}`

Service Health
- Health endpoints include `X-API-Version: v2.5`.
  - Alerter: `GET /health` (port 8082), metrics on 8081
  - Moog Forwarder: `GET /health` (port 8084), metrics on 8083
  - Web UI: `GET /health` (port 8090)
  - Ingestor: `GET /health` (port 8080)

Client Guidance
- Prefer `/api/v2/*` routes; `/api/v1/*` remain for compatibility and return `X-API-Deprecated: true`.
- Check `X-API-Version` and `X-API-Deprecated` during integration testing to detect outdated paths.

Notes
- v2 routes currently return the same payloads as v1 (see tests in `tests/test_api_v2_parity.py`).
- If/when payloads diverge, negotiation via headers or query (e.g., `Accept-Version`, `X-API-Version`, `?api_version=`) can be introduced incrementally.
