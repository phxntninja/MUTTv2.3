# Feature Matrix: v2.3 → v2.5

This matrix summarizes key improvements delivered in v2.5 over v2.3 and the value they provide.

## Summary
- Config hot‑reload at runtime across services (no restarts)
- Zero‑downtime DB/Redis secret rotation (CURRENT/NEXT)
- Config change audit trail with API and history browsing
- Observability improvements (structured logs, optional OTEL traces)
- Hardening across Redis/Postgres connections and health checks

## Details
- Dynamic Configuration
  - v2.3: Static env vars; restart required for changes
  - v2.5: Redis‑backed DynamicConfig with cache + PubSub invalidation; WebUI APIs to view/update
- Secrets Management
  - v2.3: Single credential; rotations disruptive
  - v2.5: Dual‑password connectors (CURRENT/NEXT) for zero‑downtime rotation
- Auditability
  - v2.3: Limited event audit focus
  - v2.5: `config_audit_log` with WebUI history endpoint and best‑effort audit on updates
- Observability
  - v2.3: Prometheus metrics; basic logging
  - v2.5: Structured JSON logging helpers; optional OpenTelemetry (docs + toggles)
- Reliability
  - v2.3: Direct client construction
  - v2.5: Connection helpers, better error handling and fallbacks

