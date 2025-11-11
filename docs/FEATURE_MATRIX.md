# Feature Matrix: v2.3 → v2.5

This matrix summarizes key improvements delivered in v2.5 over v2.3 and the value they provide.

| Feature | v2.3 Implementation | v2.5 Implementation | Business Value | Documentation |
|---|---|---|---|---|
| **Dynamic Configuration** | Static env vars; restart required for changes | Redis-backed DynamicConfig with cache + PubSub invalidation; WebUI APIs to view/update | Enables zero-downtime configuration changes, improving operational agility and reducing maintenance windows. | [DYNAMIC_CONFIG_USAGE.md](DYNAMIC_CONFIG_USAGE.md) |
| **Secrets Management** | Single credential; rotations disruptive | Dual-password connectors (CURRENT/NEXT) for zero-downtime rotation | Enhances security by allowing regular, non-disruptive rotation of database and service credentials. | [SECRET_ROTATION_PROCEDURE.md](SECRET_ROTATION_PROCEDURE.md) |
| **Auditability** | Limited event audit focus | `config_audit_log` with WebUI history endpoint and best-effort audit on updates | Provides a complete audit trail for all configuration changes, supporting compliance (SOX, GDPR) and improving accountability. | [API_CONFIG_AUDIT_ENDPOINTS.md](API_CONFIG_AUDIT_ENDPOINTS.md) |
| **Observability** | Prometheus metrics; basic logging | Structured JSON logging helpers; optional OpenTelemetry (docs + toggles) | Improves troubleshooting and monitoring with richer, more structured logs and distributed tracing capabilities. | [observability.md](observability.md) |
| **Reliability** | Direct client construction | Connection helpers, better error handling and fallbacks | Increases service resilience by improving connection management and error handling for external dependencies like Redis and PostgreSQL. | [DEVELOPMENT_STANDARDS.md](DEVELOPMENT_STANDARDS.md) |
| **Backpressure & Load Shedding** | None | Global rate limiting, queue depth monitoring, and circuit breakers | Protects downstream systems from overloads and ensures system stability during traffic spikes. | [ALERTER_BACKPRESSURE.md](ALERTER_BACKPRESSURE.md) |
| **Developer Experience** | Manual setup | `muttdev` CLI for one-command setup, config management, and log streaming | Reduces developer onboarding time and streamlines common development tasks. | `V2.5_QUICK_START.md` |
| **API Versioning** | Single API version | Versioned endpoints with a compatibility layer for v1 and a clear deprecation strategy | Allows for seamless API evolution without breaking existing client integrations. | [API_VERSIONING.md](API_VERSIONING.md) |
| **Data Retention** | Manual | Automated archival and deletion of old data based on configurable retention policies | Ensures compliance with data retention policies and manages storage costs. | [DATA_RETENTION_GUIDE.md](DATA_RETENTION_GUIDE.md) |
| **Architecture Decisions** | Informal | Formalized Architecture Decision Records (ADRs) | Preserves the rationale behind key technical decisions, improving long-term maintainability and knowledge sharing. | [adr](adr/) |
