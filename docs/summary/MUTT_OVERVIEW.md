MUTT v2.5 — Program Overview (Executive + Technical)

Audience
- Product Owners and Executives: fast value/benefits read
- Technical Leadership and Engineers: high-level architecture and flow

Visual
- See the end-to-end flow diagram: ../images/mutt-overview.svg

Executive Summary (2–3 minutes)
- Purpose: MUTT turns raw infra/application signals into actionable, deduplicated alerts with auditability and guardrails.
- Key Outcomes
  - Faster incident response: normalized alerts and routing reduce noise and MTTR.
  - Operational resilience: backpressure, rate-limits, and circuit breaker prevent cascades.
  - Compliance by design: complete configuration audit trail and data retention controls.
  - Secure by default: API keys, least-privilege, Vault integration for secrets.
- What’s Included
  - Web UI for metrics, rules, config audit, dev-hosts, teams (API + dashboard).
  - Ingestor service for syslog/SNMP events (HTTP) with backpressure.
  - Alerter service for rule matching and audit logging (PostgreSQL).
  - Forwarder service for Moogsoft with shared rate limiting and circuit breaker.
  - Observability: Prometheus metrics and health endpoints across services.
- What’s New in v2.5
  - Versioned APIs (v2.5 current; v2 aliases for most endpoints) to ease migrations.
  - Hardened forwarder (circuit breaker) and smoke/E2E test coverage.
  - Consolidated Prometheus alerts and improved documentation.

Technical Summary
- Core Flow (see diagram for ports and arrows)
  1) Sources
     - rsyslog (514/tcp, 514/udp) and snmptrapd (162/udp) receive raw events.
     - rsyslog posts JSON to Ingestor HTTP:8080; snmptrapd may proxy via rsyslog or adapter.
  2) Ingestor (HTTP:8080)
     - Validates payloads, enforces queue caps; pushes to Redis ingest_queue.
  3) Alerter (metrics:8081, health:8082)
     - BRPOPLPUSH from ingest_queue → per-worker list; rule match; write event audit to PostgreSQL; push to alert_queue.
     - Janitor on startup reclaims orphaned lists; heartbeat for liveness.
  4) Moog Forwarder (metrics:8083, health:8084)
     - Rate limit via Redis + Lua; circuit breaker opens on failures; posts to Moogsoft webhook; DLQ fallback after retries.
  5) Web UI (HTTP/API:8090)
     - Metrics dashboard; CRUD for rules/dev-hosts/teams; configuration audit views.
     - Writes config-change audits to PostgreSQL; reads metrics from Redis caches.
  6) Observability & Ops
     - Prometheus scrapes all metrics; Alertmanager uses alerts-v25.yml; Grafana dashboards optional.
     - Vault (AppRole) for secrets; TLS support for Redis/PostgreSQL.
- Data Stores
  - Redis: queues, rate-limit/circuit state, metrics cache.
  - PostgreSQL: configuration and audit logs (event_audit_log, config_audit_log).
- Interfaces & Security
  - All APIs require X-API-KEY except public health/metrics.
  - Response headers include X-API-Version for rollout safety.
- Availability & Safety
  - Backpressure caps and 503s protect ingress; BRPOPLPUSH + janitor prevent message loss on crash.
  - Circuit breaker protects Moog/egress; DLQ ensures no alert is discarded silently.

Quick References
- Current API version: v2.5 with v2 aliases (see docs/API_VERSIONING.md)
- Prometheus rule file: docs/prometheus/alerts-v25.yml
- Ports at a glance: README.md: Service Ports

