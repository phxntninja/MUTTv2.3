MUTT v2.5 — Alerter Backpressure Guide

Overview
- Purpose: Prevent downstream overload by monitoring queue depth and reacting via shedding or deferral.
- Scope: Affects Alerter service only (Component #2). Uses Redis and Dynamic Config.

Queues
- Monitored queue: `mutt:alert_queue` (Alerter backpressure check target)
- Alerter ingest queue: `mutt:ingest_queue` (messages shed from here in `dlq` mode)
- Alerter DLQ: `mutt:dlq:alerter`

Dynamic Config (breaking change in v2.5)
- `alerter_queue_warn_threshold` (int, default 1000): warn threshold
- `alerter_queue_shed_threshold` (int, default 2000): shedding threshold
- `alerter_shed_mode` (string, default `dlq`): `dlq` or `defer`
- `alerter_defer_sleep_ms` (int, default 250): sleep when deferring

Behavior
- Warn: When `LLEN mutt:alert_queue` > `alerter_queue_warn_threshold`, logs a warning and updates `mutt_alerter_queue_depth`.
- Shed (`dlq`): When depth > `alerter_queue_shed_threshold`, removes 1 event from `mutt:ingest_queue` and pushes to `mutt:dlq:alerter`. Increments `mutt_alerter_shed_events_total{mode="dlq"}`.
- Defer: When depth > `..._shed_threshold` and `alerter_shed_mode=defer`, sleeps `alerter_defer_sleep_ms` and increments `mutt_alerter_shed_events_total{mode="defer"}`.

Metrics
- `mutt_alerter_queue_depth` (gauge): Current depth of monitored queue.
- `mutt_alerter_shed_events_total{mode}` (counter): Total shed/defers.

Operations Runbook
- Symptom: Frequent shedding (dlq) or deferral.
  - Check current depth: `LLEN mutt:alert_queue`.
  - Inspect DLQ depth: `LLEN mutt:dlq:alerter`.
  - Verify forwarder health and rate limits.
  - If transient spike, consider `defer` mode temporarily: `SET mutt:config:alerter_shed_mode defer`.
  - If sustained, raise thresholds cautiously and plan capacity increase.
- Recovery: Reprocess DLQ via batch replay tooling or ad-hoc scripts (ensure idempotency).

Configuration Changes
- All keys above are new and canonical for v2.5. Legacy aliases are not honored.

Verification
- Unit tests live in `tests/test_alerter_unit.py` (backpressure section) and mock Redis `LLEN`, `RPOP`, and `LPUSH`.
