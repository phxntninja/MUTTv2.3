# MUTT v2.5 – Current Unified Plan (2025-11-10)

Status Summary
- Phase 1: Infrastructure & Database — COMPLETE
- Phase 2: Hot Reload & Secrets — COMPLETE
- Phase 3: Reliability & Observability — COMPLETE (Alerter backpressure, remediation service, SLO endpoint)
- Next Focus: Phase 4 (API & Compliance), Phase 5 (Developer Experience), plus follow-ups below

Guiding References
- Source of truth for Phase 3 delivery: docs/PHASE_3_HANDOFF_TO_ARCHITECT.md
- Operator guides: docs/ALERTER_BACKPRESSURE.md, docs/SLOs.md

Phase 4 — API & Compliance
- 4.1 Configuration Change Audit
  - Integrate audit logging into Web UI Rule CRUD
  - Add audit log API endpoints
  - Create audit log UI component
- 4.2 API Versioning & Deprecation
  - Add version headers to all responses
  - Create versioned endpoint decorator and implement v1 compatibility
  - Update API documentation
- 4.3 Data Retention Compliance
  - Add retention policy config to environment and dynamic config
  - Create retention policy enforcement (cron/K8s job)
  - Provide Prometheus recording rules for retention monitoring (if applicable)

Phase 5 — Developer Experience & Docs
- Developer CLI (muttdev)
  - CLI scaffold; `muttdev setup`, `muttdev config`, `muttdev logs`
  - Installation script and quickstart
- Architecture Decision Records
  - ADR template and ADRs for Redis vs Kafka, Vault vs K8s Secrets, Single-threaded workers, PostgreSQL audit logs

Cross-Cutting Follow-ups (from Architect Handoff)
- Dashboards & Alerts
  - Update Grafana/Prometheus dashboards to normalized labels
  - Add burn-rate SLO alerting (via /api/v1/slo or Prometheus recording rules)
- Integration & E2E Testing
  - End-to-end tests (ingest → alerter → forwarder → DLQ)
  - Load tests to validate backpressure behavior
- Capacity & Tuning
  - Validate warn/shed thresholds and defer parameters in staging
- Security & Compliance
  - Confirm API key rotation, Vault policies, optional mTLS for Prometheus
- Resilience Additions (Optional)
  - Consider circuit breaker on additional paths; add jitter to defer sleeps
- Documentation
  - Operator cheat-sheet for dynamic config commands; updated screenshots/examples

Environment & Config Notes
- Ensure `PROMETHEUS_URL` is set for Web UI
- Use canonical dynamic config keys for alerter backpressure:
  - `alerter_queue_warn_threshold`, `alerter_queue_shed_threshold`, `alerter_shed_mode` (dlq|defer), `alerter_defer_sleep_ms`
- Metrics label model normalized to `status={success|fail}` with low-cardinality `reason`

Verification Checklist (quick)
- Alerter warns/sheds per thresholds; metrics update
- `/api/v1/slo` returns targets, availability, burn rate, error budget
- Prometheus scrapes all services; recording rules loaded (docs/prometheus/recording-rules-v25.yml)

