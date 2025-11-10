# MUTT v2.5 – Phase 3 Handoff (to Coordinator & Architect)

Date: 2025-11-10
Owner: Codex

## Executive Summary

Note for Architect
- Please conduct your review using the chunked protocol in `docs/ARCHITECT_STATUS_FOR_GEMINI.md`. It specifies the exact reading order, output limits, and micro-prompts to avoid context overflows.

Phase 3 objectives are complete: the alerter has canonicalized paths and backpressure controls, the Web UI exposes SLOs backed by Prometheus, deployments and documentation are aligned, and unit tests cover the new behaviors. This package is ready for coordinator/architect review and integration into the broader program plan.

---

## Scope Delivered (Phase 3)

1) Canonicalization & Deploy Path Hygiene
- Consolidated on `services/alerter_service.py` as the source of truth.
- Removed top-level duplicate and updated all references across Dockerfile, README, systemd deploy script, Kubernetes, and docs to `services/*` paths (ingestor, web UI, moog forwarder).

2) Alerter Backpressure (Queue Depth)
- Monitors `mutt:alert_queue` depth; sheds from `mutt:ingest_queue` when over threshold.
- Modes: `dlq` (default) or `defer`, controlled via dynamic config.
- Standardized keys (breaking change from legacy aliases):
  - `alerter_queue_warn_threshold` (default 1000)
  - `alerter_queue_shed_threshold` (default 2000)
  - `alerter_shed_mode` (`dlq` or `defer`)
  - `alerter_defer_sleep_ms` (default 250)
- Metrics exposed: `mutt_alerter_queue_depth`, `mutt_alerter_shed_events_total{mode}`
- Tests: new backpressure unit tests added.

3) SLOs (/api/v1/slo)
- Web UI endpoint returns component SLOs for Ingestor and Moog Forwarder:
  - Fields: `target`, `availability`, `error_budget_remaining`, `burn_rate`, `state`, `window_hours`.
  - States based on burn rate: `ok` (<=1.0), `warn` (<=2.0), `critical` (>2.0).
- Prometheus connectivity: `PROMETHEUS_URL` env var, 5s timeout, 1 retry after 2s.
- Queries approved and implemented:
  - Ingestor: `sum(rate(mutt_ingest_requests_total{status="success"}[$window])) / sum(rate(mutt_ingest_requests_total[$window]))`
  - Forwarder: `sum(rate(mutt_moog_requests_total{status="success"}[$window])) / sum(rate(mutt_moog_requests_total[$window]))`
- Recording rules file added: `docs/prometheus/recording-rules-v25.yml`.
- Tests: SLO endpoint unit tests including the retry path added.

4) Metrics Label Normalization
- Normalized high-level status to `success|fail` and moved error cause to a low-cardinality `reason` label.
  - Ingestor: `mutt_ingest_requests_total{status,reason}`
  - Forwarder: `mutt_moog_requests_total{status,reason}`
- SLO queries unchanged (still filter on `{status="success"}`).

5) Deployment & Configuration Updates
- Dockerfile CMD/gunicorn entrypoints updated to `services.*` paths.
- Systemd deploy script now installs into `/opt/mutt/services` and runs via module paths.
- docker-compose and k8s (`k8s/configmap.yaml`) define `PROMETHEUS_URL` for Web UI.
- `.env.template` switched to canonical backpressure keys; added `ALERTER_DEFER_SLEEP_MS`.

6) Documentation
- Alerter backpressure operator guide: `docs/ALERTER_BACKPRESSURE.md`.
- SLOs operator guide: `docs/SLOs.md` (API spec, queries, runbook).
- Upgrade guide updated with breaking changes (path + config keys): `docs/UPGRADE_GUIDE_v2_3_to_v2_5.md`.
- Dynamic config guide updated with canonical keys & SLO keys: `docs/DYNAMIC_CONFIG_USAGE.md`.
- README updated (API, Monitoring, configs, run commands, metrics, SLOs).

7) Tests
- Alerter backpressure unit tests added: `tests/test_alerter_unit.py`.
- SLO endpoint tests added: `tests/test_webui_unit.py`.
- Installed `requests-mock` in `tests/requirements-test.txt`.
- Removed legacy skipped test: `tests/test_alerter_backpressure_unit.py.SKIP`.

---

## Breaking Changes (Operator Impact)

- Canonical paths: run and deploy commands must use `services/alerter_service.py` (and `services/*` for others).
- Backpressure keys: legacy aliases `alerter_queue_warn`/`alerter_queue_shed` are no longer honored. Use canonical keys listed above.
- Metrics labeling: dashboards or alerts targeting specific `fail_*` statuses should migrate to `status="fail"` with optional `reason` filters.

---

## How to Verify (Quick Checklist)

1) Environment
- `PROMETHEUS_URL` set for Web UI (compose/k8s manifest included).
- Alerter dynamic config keys set (warn/shed thresholds, mode).

2) Functional
- Push load into `mutt:ingest_queue` and verify:
  - Alerter warns at warn threshold; sheds or defers at shed threshold per mode.
  - `mutt_alerter_queue_depth` and `mutt_alerter_shed_events_total{mode}` update.
- Hit `/api/v1/slo` with `X-API-KEY` and confirm schema + states; simulate Prometheus failure to observe retry.

3) Observability
- Prometheus targets scrape metrics from all services.
- Dashboards/alerts reflect new label model for ingestor/forwarder metrics where applicable.

---

## Recommended Next Steps

1) Dashboards & Alerts
- Update Grafana dashboards and Prometheus alerts to use:
  - Ingestor: `mutt_ingest_requests_total{status="fail",reason=~"auth|json|validation|queue_full|redis|rate_limit|unknown"}`
  - Forwarder: `mutt_moog_requests_total{status="fail",reason=~"http|rate_limit|retry_exhausted|circuit_open"}`
- Add burn-rate SLO alerting using `/api/v1/slo` outputs or recording rules.

2) Integration & E2E Testing
- Add integration tests that simulate end-to-end flow (ingest → alerter → forwarder → DLQ) with Redis/Postgres containers.
- Include load tests to validate backpressure behavior under sustained traffic.

3) Capacity & Tuning
- Validate thresholds in production-like environments and tune warn/shed values.
- Confirm defer mode operational guidance (when to switch and for how long).

4) Security & Compliance
- Confirm API key rotation and Vault policies across services.
- Optionally add MTLS to Prometheus queries if required by environment.

5) Resilience Additions (Optional)
- Consider circuit breaker on alerter outputs (if needed), mirroring forwarder patterns.
- Add jitter to defer sleeps to reduce thundering herd effects.

6) Documentation Follow-ups
- Provide an operator cheat-sheet of dynamic config commands (Redis CLI examples) for backpressure and SLO tuning.
- Include updated Grafana screenshots/examples using normalized labels.

---

## File & Change Index (Key Touchpoints)

- Alerter service: `services/alerter_service.py` (backpressure handler + canonicalized)
- Web UI service: `services/web_ui_service.py` (`/api/v1/slo` + Prometheus client)
- Forwarder service: `services/moog_forwarder_service.py` (metrics normalization)
- Ingestor service: `services/ingestor_service.py` (metrics normalization)
- Dockerfile CMD/gunicorn app paths updated
- Deploy script (RHEL): `scripts/deploy_mutt_v2.3.sh` (module paths; `/opt/mutt/services`)
- Compose & k8s: `docker-compose.yml`, `k8s/configmap.yaml` (PROMETHEUS_URL)
- Docs: `docs/ALERTER_BACKPRESSURE.md`, `docs/SLOs.md`, `docs/prometheus/recording-rules-v25.yml`, `docs/UPGRADE_GUIDE_v2_3_to_v2_5.md`, `docs/DYNAMIC_CONFIG_USAGE.md`
- Tests: `tests/test_alerter_unit.py`, `tests/test_webui_unit.py`, `tests/requirements-test.txt`

---

## Risks & Assumptions

- Metric label normalization may require coordinated dashboard/alert updates to avoid gaps.
- SLO computation assumes Prometheus has continuous data; sparse series yield `None` values (handled by endpoint).
- Backpressure shedding in `dlq` mode trades off data loss vs. system stability; operator runbook provided.

---

## Contacts

- Engineering (Codex): Phase 3 implementation, tests, docs.
- Coordinator/Architect: Please review breaking changes, SLO approach, and backpressure policies; advise on org-wide dashboard/alert migration plan.
