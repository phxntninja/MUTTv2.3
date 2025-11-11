MUTT v2.5 — Code Module Overview

Purpose
- Orient developers to key modules, responsibilities, and important functions/classes.

Top-Level Services
- ingestor_service.py
  - Flask app exposing /api/v2/ingest, /health, /metrics
  - Validates payloads, applies backpressure via Redis queue depth, enqueues to mutt:ingest_queue
  - Vault auth (AppRole), token renewal thread; Redis pool with TLS
  - Key: METRIC_INGEST_TOTAL, METRIC_QUEUE_DEPTH, METRIC_LATENCY

- services/alerter_service.py
  - Long-running worker; consumes from mutt:ingest_queue using BRPOPLPUSH into per-pod processing list
  - Caching: alert_rules, development_hosts, device_teams; reload via timer + SIGHUP
  - Lua script for atomic unhandled meta-alerts; writes to PostgreSQL event_audit_log
  - Heartbeat + janitor pattern to recover orphaned messages; health/metrics endpoints
  - Key functions:
    - handle_backpressure(config, redis): shed/defer logic
    - process_message(): rule match, audit logging, forward to alert queue

- moog_forwarder_service.py
  - Long-running worker; consumes from alert queue
  - Shared rate limiting (Redis sorted set + Lua); exponential backoff with jitter
  - Dead Letter Queue (DLQ); circuit breaker (Redis keys) with metrics
  - Health server checks Redis + webhook reachability; Prometheus metrics endpoint
  - Key functions:
    - check_rate_limit(redis, config)
    - send_to_moog(alert, config, secrets)
    - process_alert(alert_string, config, secrets, redis)

- web_ui_service.py
  - Flask app for dashboard and CRUD APIs (rules, dev-hosts, teams), metrics, and audit endpoints
  - PostgreSQL pool; Redis metrics cache; Vault auth; API key auth; version headers
  - Config-audit writes for rule CRUD; dashboard shows metrics + recent config changes
  - Important endpoints: /api/v2/metrics, /api/v2/rules, /api/v2/audit-logs, /api/v2/config-audit

Cross-Cutting Modules
- services/api_versioning.py
  - Response header helpers; versioned_endpoint decorator; version history/state
  - CURRENT_API_VERSION = '2.5'; SUPPORTED_VERSIONS = ['2.5','2.0','1.0']

- services/audit_logger.py
  - Helpers to log/read configuration changes in config_audit_log
  - Typical usage in Web UI: log CRUD changes with old/new values + reason + correlation_id

- services/dynamic_config.py
  - Optional Redis-backed dynamic configuration plumbing; publish/subscribe notifications

- services/redis_connector.py
  - Utilities to create Redis connection pools with TLS options

- services/postgres_connector.py
  - Utilities to create PostgreSQL connection pools (ThreadedConnectionPool) with TLS

- services/rate_limiter.py
  - Shared Redis/Lua rate-limit primitives (if used by multiple services)

- services/remediation_service.py
  - Auto-remediation examples and hooks (optional); metrics for remediation outcomes

- services/logging_utils.py, services/tracing_utils.py
  - JSON logging setup; OpenTelemetry trace setup, propagation helpers

- services/slo_checker.py, services/slo_definitions.py
  - SLO target definitions and helper functions for the /api/v1/slo endpoint

Scripts & Jobs
- scripts/retention_cleanup.py
  - Enforces retention for config_audit_log (Postgres), event_audit_log (Postgres), DLQ (Redis); dry-run support

- scripts/create_monthly_partitions.py
  - Pre-creates event_audit_log monthly partitions; default months ahead via RETENTION_PRECREATE_MONTHS

- scripts/muttdev.py
  - Developer CLI: setup, config (dynamic), logs, up/down, tests, retention, e2e, load

Testing Utilities
- tests/test_api_v2_parity.py
  - Ensures v1/v2 parity for key Web UI endpoints

- tests/integration/test_e2e_flow.py
  - Compose-based smoke E2E (opt-in via E2E_COMPOSE=true); mock Moog sink validates flow

