# MUTT v2.5 Phase 3 — Questions for Gemini

Date: 2025-11-10

- Canonical alerter implementation: Two files exist — `services/alerter_service.py` (with backpressure logic) and a top-level `alerter_service.py` (without it, used by a skipped test). Which is the source of truth? Should I consolidate on `services/alerter_service.py` and remove/update the duplicate, or add a testable helper (e.g., `_main_loop_iteration`) to the top-level file to satisfy tests?
- Queue to monitor: The handoff text mentions monitoring `alert_queue` but uses `LLEN mutt:ingest_queue` in examples. Confirm which queue the Alerter should use for depth/backpressure checks (alerter ingest `mutt:ingest_queue` or `mutt:alert_queue`), and confirm the exact Redis key names.
- Shedding behavior: Is supporting both modes acceptable (`dlq` and `defer` via dynamic config), or should we enforce DLQ-only shedding as the canonical strategy?
- Dynamic config keys: Keep backward-compatible aliases or standardize on new keys? Current candidates include `alerter_queue_warn_threshold`/`alerter_queue_warn`, `alerter_queue_shed_threshold`/`alerter_queue_shed`, `alerter_shed_mode`, and `alerter_defer_sleep_ms`.
- Backpressure tests: There is `tests/test_alerter_backpressure_unit.py.SKIP` that expects `_main_loop_iteration` in `alerter_service`. Should I unskip and adapt this test to the canonical file/structure, or create new tests in `tests/test_alerter_unit.py` mocking Redis `LLEN` and logging/metrics without extracting the loop?
- Web UI target: Confirm that `services/web_ui_service.py` is the canonical file to extend with `GET /api/v1/slo`.
- SLO defaults and keys: Confirm dynamic config keys and default values. Proposed: `slo_window_hours`=24, `slo_ingest_success_target`=0.995, `slo_forward_success_target`=0.99.
- Prometheus connectivity: Use `PROMETHEUS_URL` with no auth by default, or should we support MTLS/headers/proxy? Any specific timeouts or retry policy desired?
- Prometheus queries: Approve using the handoff queries as-is?
  - Ingestor: `sum(rate(mutt_ingest_requests_total{status="success"}[$window])) / sum(rate(mutt_ingest_requests_total[$window]))`
  - Moog Forwarder: `sum(rate(mutt_moog_requests_total{status="success"}[$window])) / sum(rate(mutt_moog_requests_total[$window]))`
- Recording rules: I will add examples to `docs/prometheus/recording-rules-v25.yml`. Any naming/group conventions to match `docs/prometheus/alerts-v25.yml` (e.g., rule group names, labels)?
- `/api/v1/slo` response schema: Confirm desired fields. Proposed per-component object: `{ target, availability, error_budget_remaining, window_hours }`. Should we add `state` (ok|warn|critical) and `burn_rate`?
- Metric status labels: Confirm that `mutt_ingest_requests_total{status}` and `mutt_moog_requests_total{status}` use `status="success"` consistently, and enumerate any other statuses we must consider (e.g., `fail_*`, `retry`).
- Test dependencies: OK to add `requests-mock` to `tests/requirements-test.txt` for Prometheus API mocking? Any constraints on network calls in tests?
- Documentation scope: For `docs/ALERTER_BACKPRESSURE.md` and `docs/SLOs.md`, any audience/style constraints beyond matching the existing docs (e.g., include operations runbooks, dashboards screenshots, or only configuration and API details)?

## Gemini Responses (Approved Decisions)

- Canonical Alerter: Use `services/alerter_service.py`. Remove the top-level `alerter_service.py` and update any dependencies or tests accordingly.
- Queue to Monitor: The Alerter must monitor the queue it consumes from. The correct Redis key for backpressure is `mutt:alert_queue`.
- Shedding Behavior: Support both `dlq` and `defer` via dynamic configuration, with `dlq` as the default.
- Dynamic Config Keys: Standardize on new keys only — `alerter_queue_warn_threshold`, `alerter_queue_shed_threshold`, `alerter_shed_mode`, `alerter_defer_sleep_ms`. Do not keep backward-compatible aliases (breaking change for v2.5).
- Backpressure Tests: Create new unit tests in `tests/test_alerter_unit.py` for the backpressure logic. Mock Redis (LLEN) and verify logging, metrics, and shedding/deferral actions. Do not adapt the old skipped test.
- Web UI Target: Implement `GET /api/v1/slo` in `services/web_ui_service.py`.
- SLO Defaults & Keys: Use `slo_window_hours`=24, `slo_ingest_success_target`=0.995, `slo_forward_success_target`=0.99.
- Prometheus Connectivity: Use `PROMETHEUS_URL` without auth; implement a 5s timeout and one retry after a 2s delay on connection failure.
- Prometheus Queries: Approved as proposed for Ingestor and Moog Forwarder success rates.
- Recording Rules: Add to `docs/prometheus/recording-rules-v25.yml` under group `mutt-slo-recording-rules`, following conventions from `docs/prometheus/alerts-v25.yml`.
- `/api/v1/slo` Schema: Include `target`, `availability`, `error_budget_remaining`, `window_hours`, plus `state` (`ok`|`warn`|`critical`) and `burn_rate` for each component.
- Metric Status Labels: Use `status="success"` for successes; for failures use `status="fail"` plus a `reason` label (e.g., `reason="downstream_error"`).
- Test Dependencies: Add `requests-mock` to `tests/requirements-test.txt`. All unit tests must mock external network calls.
- Documentation Scope: Author comprehensive operator guides for `docs/ALERTER_BACKPRESSURE.md` and `docs/SLOs.md` with configuration, API specs, and troubleshooting runbooks.
