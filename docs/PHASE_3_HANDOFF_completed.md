# MUTT v2.5 – Phase 3 Handoff (Backpressure, Self‑Healing, SLOs)

Status: Phase 3A foundations partially implemented and validated. This plan completes the remaining Phase 3 work with clear tasks, acceptance criteria, and test strategy so another tool/agent can continue hands‑off.

Owner intent: Complete Phase 3 while keeping test suite green and aligning with decisions in `ai/handoffs/PHASE_3_ANSWERS_GEMINI.md`.

## Current State (as of handoff)
- Implemented and green (243 passed, 15 skipped):
  - Circuit Breaker infrastructure (services/rate_limiter.py) and integration into Moog Forwarder (services/moog_forwarder_service.py):
    - State checks, success/failure recording, Prometheus metrics, DynamicConfig getters
  - Ingestor global rate limiter (Redis sliding window) integrated (services/ingestor_service.py)
  - CI matrix with lint/type/security; tracing tests hardened; docs and dashboards added
- Fixed indentation and compilation issues in `services/moog_forwarder_service.py` (including `send_to_moog`).

## Phase 3 Work Breakdown

### 3.1 Backpressure & Load Shedding (Alerter)
Goal: Protect the system under load by shedding work and avoiding persistent backlog.

Tasks
- 3.1.1 Queue depth monitors in Alerter
  - Implement Redis queue depth checks with thresholds (warn, shed).
  - DynamicConfig keys: `alerter_queue_warn_threshold`, `alerter_queue_shed_threshold`, `alerter_shed_mode`, `alerter_defer_sleep_ms`.
  - Prometheus metrics: `mutt_alerter_queue_depth`, `mutt_alerter_shed_events_total`.
- 3.1.2 Shedding strategy
  - When depth exceeds shed threshold: either short‑circuit to DLQ or temporary 429‑style deferral (configurable: `alerter_shed_mode = dlq|defer`).
  - Add poison‑message protection (respect retry counters attached by Alerter logic).
- 3.1.3 Janitor enhancements
  - Verify orphan recovery respects new thresholds; ensure safe behavior during shedding.
- 3.1.4 Tests
  - Unit tests: monitor thresholds, shed path to DLQ vs defer.
  - Integration test: simulate depth with Redis, assert metrics + behavior.

Acceptance Criteria
- Alerter logs warn at warn threshold and sheds per mode at shed threshold.
- Metrics expose queue depth and shed counters.
- Tests pass and demonstrate behavior transitions.

Files
- `services/alerter_service.py`
- `tests/test_alerter_unit.py` (new cases)
- `tests/test_integration_v25.py` (extend)

### 3.2 Self‑Healing & Auto‑Remediation
Goal: Build a remediation worker to reduce manual toil and recover from failure modes automatically.

Tasks
- 3.2.1 Remediation service scaffold
  - New `services/remediation_service.py`: long‑running loop with configurable interval.
  - Health check endpoint + Prometheus metrics server (similar pattern to Alerter).
- 3.2.2 DLQ replay with poison protection
  - Read `mutt:dlq:alerter` and replay to `alert_queue` if retry count < `max_retries`.
  - If over limit, move to `mutt:dlq:dead` (terminal).
  - Config via DynamicConfig: `remediation_enabled`, `remediation_interval`, `remediation_batch_size`, `max_poison_retries`.
  - Metrics: `mutt_remediation_replay_success_total`, `mutt_remediation_replay_fail_total`, `mutt_remediation_dlq_depth`.
- 3.2.3 Moog health checks (optional)
  - Attempt a lightweight POST to a Moog test endpoint (config), update metric `mutt_moog_health_last_ok_timestamp`.
- 3.2.4 Compose/K8s wiring
  - Add remediation service to docker‑compose (if used) and `k8s/remediation-deployment.yaml`.
- 3.2.5 Tests
  - Unit tests: batch replay logic, poison cut‑off, metrics increments.
  - Integration test: preload DLQ → run one loop → assert replays and terminal moves.

Acceptance Criteria
- Remediation loops without crashing; respects interval and batch size.
- DLQ messages replayed or terminally quarantined based on retry count.
- Metrics reflect actions; tests pass.

Files
- `services/remediation_service.py` (new)
- `tests/test_remediation_unit.py` (new)
- `tests/test_integration_v25.py` (extend)
- `k8s/remediation-deployment.yaml` (new)

### 3.3 SLO Tracking and SLO Dashboard
Goal: Track error budgets and SLO compliance using Prometheus, surface in Web UI.

Tasks
- 3.3.1 SLO definitions
  - Config keys (DynamicConfig/Config): `slo_ingest_success_target`, `slo_forward_success_target`, `slo_window_hours`, `slo_burn_rate_critical`, `slo_burn_rate_warning`.
- 3.3.2 SLO checker module
  - `services/slo_checker.py`: query Prometheus HTTP API (URL from env `PROMETHEUS_URL`).
  - Compute availability and burn rate for:
    - Ingestor success ratio (based on `mutt_ingest_requests_total{status="success"}` vs errors)
    - Moog forward success ratio (`mutt_moog_requests_total` status breakdown)
- 3.3.3 Web UI endpoint
  - `services/web_ui_service.py`: GET `/api/v1/slo` returning components’ SLO status and burn rates.
- 3.3.4 Recording rules template
  - `docs/prometheus/recording-rules-v25.yml` with convenient rates/counters for SLO computations.
- 3.3.5 Tests
  - Unit: mock Prometheus client responses; verify calculations and thresholds.
  - Integration: run with a mocked HTTP server to simulate Prometheus responses.

Acceptance Criteria
- `/api/v1/slo` returns JSON with current targets, calculated availability, and burn rates with state (`ok|warn|critical`).
- Recording rules documented; unit/integration tests pass.

Files
- `services/slo_checker.py` (new)
- `services/web_ui_service.py` (extend)
- `tests/test_slo_unit.py` (new), `tests/test_integration_v25.py` (extend)
- `docs/prometheus/recording-rules-v25.yml` (new)

### 3.4 Validation, Packaging, Docs
Tasks
- 3.4.1 .env.template updates
  - Add new envs: rate limiting, circuit breaker tuning, remediation knobs, SLO params, `PROMETHEUS_URL`.
- 3.4.2 Docker/K8s
  - Add remediation deployment YAML (see 3.2.4), ensure ports/probes present.
- 3.4.3 Docs
  - `docs/REMEDIATION.md`: how replay works, limits, runbook.
  - `docs/SLOs.md`: SLO math, supported indicators, examples.
  - Update `docs/PHASE_2_HANDOFF.md` references and `README.md` quick links.
- 3.4.4 CI
  - Add/mark integration tests; optionally split into fast(unit) vs full(integration) workflows.

Acceptance Criteria
- New env template committed; README/docs sections exist and link correctly.
- CI remains fully green; integration tests run on demand/matrix.

## Execution Order
1) 3.1 Alerter backpressure (low‑risk, contained);
2) 3.2 Remediation worker and DLQ replay;
3) 3.3 SLO checker + Web UI endpoint;
4) 3.4 Docs, env, K8s/compose, CI refinements.

## Test Plan Summary
- Unit first: pure logic and boundary tests for backpressure, remediation, SLO math.
- Integration: Redis‑backed flows for DLQ replay and rate limiting; HTTP‑mocked Prometheus for SLO.
- Non‑functional checks: perf sanity (no hot loops), graceful shutdown of new service, metrics visible.

## Risks & Mitigations
- Redis latency or script errors under load → fail‑open for rate limiting; log and alert.
- DLQ replay storm → cap batch size and add small inter‑batch sleep; expose metrics.
- Prometheus unavailability → SLO endpoint returns last known or `unknown` state with warn logs.

## Deliverables Checklist
- [ ] Alerter backpressure thresholds + shedding + metrics + tests
- [ ] Remediation service + DLQ replay + poison protection + tests + k8s yaml (and compose if used)
- [ ] SLO checker + `/api/v1/slo` + recording rules + tests
- [ ] Env template updates + docs (`REMEDIATION.md`, `SLOs.md`) + README links
- [ ] CI tweaks for integration tests (optional)

## Commands & References
- Run unit tests: `pytest -q -m unit`
- Run all tests: `pytest -q`
- Web UI SLO: `GET /api/v1/slo`
- DLQ keys: `mutt:dlq:alerter`, terminal `mutt:dlq:dead`
- Prometheus URL: `$PROMETHEUS_URL`

## Handoff Notes
- All changes should keep style and metrics conventions established in v2.3–v2.5.
- Prefer DynamicConfig for tuning; static envs for URLs and identities (per Gemini decisions).
- Keep patches focused; run the suite once per batch of related changes.
