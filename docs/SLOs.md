MUTT v2.5 — SLOs and /api/v1/slo

Overview
- Components: Ingestor and Moog Forwarder.
- Objective: Expose rolling-window availability and error-budget health via `/api/v1/slo`.

Defaults (Dynamic Config)
- `slo_window_hours` (int, default 24)
- `slo_ingest_success_target` (float, default 0.995)
- `slo_forward_success_target` (float, default 0.99)

Prometheus
- Configure `PROMETHEUS_URL` env var on Web UI (default `http://localhost:9090`).
- Timeout: 5s per request; single retry after 2s on failure.
- Queries:
  - Ingestor success: `sum(rate(mutt_ingest_requests_total{status="success"}[$window])) / sum(rate(mutt_ingest_requests_total[$window]))`
  - Forwarder success: `sum(rate(mutt_moog_requests_total{status="success"}[$window])) / sum(rate(mutt_moog_requests_total[$window]))`

Recording Rules
- File: `docs/prometheus/recording-rules-v25.yml`
- Group: `mutt-slo-recording-rules` (follows `docs/prometheus/alerts-v25.yml` conventions)

API: GET /api/v1/slo
- Auth: Requires `X-API-KEY` or `?api_key=`
- Response:
  - `window_hours`: integer
  - `components`: object
    - `ingestor|forwarder`:
      - `target`: float
      - `availability`: float
      - `error_budget_remaining`: float (proportion of budget left)
      - `burn_rate`: float ((1-availability)/(1-target))
      - `state`: `ok`|`warn`|`critical` (derived from burn rate: <=1 ok, <=2 warn, >2 critical)
      - `window_hours`: integer

Runbook
- `state=warn` or `critical`:
  - Check service health alerts (see `docs/prometheus/alerts-v25.yml`).
  - Investigate spikes in `fail` statuses with `reason` labels to locate sources.
  - For `forwarder`, confirm rate limits and downstream availability; throttle or buffer as needed.
  - For `ingestor`, inspect traffic surges and rate limiter configuration.

Testing
- Unit tests must mock Prometheus; use `requests-mock` and avoid real network calls.
