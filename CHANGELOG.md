# Changelog

All notable changes to this project will be documented in this file.

## [2.5.0] - 2025-11-12

### Highlights
- **Enterprise-Grade Reliability**: Implemented a full suite of reliability features including a global rate limiter, queue-depth backpressure, a circuit breaker for the Moogsoft forwarder, and a self-healing remediation service to replay from the DLQ.
- **Zero-Downtime Operations**: Enabled dynamic configuration hot-reloading from Redis and zero-downtime secret rotation for both PostgreSQL and Redis through a dual-password mechanism.
- **Compliance & Auditing**: Added a complete configuration audit trail for SOX/GDPR compliance and automated data retention/archiving policies.
- **Enhanced Developer Experience**: Introduced `muttdev`, a powerful CLI for managing local development, running tests, and interacting with the system.
- **Comprehensive Testing**: The test suite has grown to **335 passing tests**, including new integration tests for rate limiting, SLO compliance, and DLQ replay.

### Added

#### Phase 1: Infrastructure & Database
- **Config Audit**: Added `config_audit_log` table to PostgreSQL for tracking all configuration changes.
- **Data Retention**: Implemented partitioned `event_audit_log` tables and scripts for automated data archiving and cleanup.
- **Dynamic Configuration**: Created `DynamicConfig` service backed by Redis for zero-downtime configuration changes.

#### Phase 2: Hot Reload & Secrets
- **Hot-Reload**: Integrated `DynamicConfig` into all core services (Ingestor, Alerter, Moog Forwarder).
- **Secret Rotation**: Implemented dual-password connection helpers for PostgreSQL and Redis to allow zero-downtime secret rotation.
- **Config API**: Added API endpoints (`/api/v1/config/*`) to manage dynamic configuration at runtime.

#### Phase 3: Reliability & Observability
- **Rate Limiter**: Added a global, Redis-based sliding-window rate limiter to the Ingestor service.
- **Circuit Breaker**: Implemented a circuit breaker in the Moog Forwarder to prevent cascading failures.
- **Backpressure**: Added queue-depth monitoring to the Alerter to shed load when queues are too deep.
- **Auto-Remediation**: Created a new `remediation_service` to automatically check external dependency health (Moogsoft) and replay dead-lettered messages.
- **SLO Tracking**: Implemented an SLO compliance checker and a dashboard endpoint (`/api/v1/slo`) to monitor service level objectives against Prometheus metrics.
- **Integration Tests**: Added new integration tests for rate limiting, DLQ replay, and SLO compliance.

#### Phase 4: API & Compliance
- **Audit Trail**: Integrated audit logging into all rule and configuration changes via the API and UI.
- **API Versioning**: Implemented API versioning with a decorator, adding `X-API-Version` headers and deprecation warnings for v1 endpoints.
- **Retention Enforcement**: Created a `retention_policy_enforcer.py` script and a corresponding Kubernetes CronJob to automate data retention.

#### Phase 5: Developer Experience & Docs
- **Developer CLI**: Created the `muttdev` CLI tool with commands for setup, config management, log tailing, status checks, and database access.
- **Architecture Decision Records (ADRs)**: Added comprehensive ADRs explaining key architectural choices (Redis vs. Kafka, Vault usage, etc.).

#### Phase 6: Final Testing & Documentation
- **Documentation**: Created a comprehensive v2.5 Migration Guide, Feature Comparison Matrix, and Load Testing Guide.
- **Testing**: Expanded the test suite to 335 passing tests, including new integration and end-to-end tests.

### Changed
- **API Responses**: All API endpoints now return `X-API-Version` and `X-API-Deprecated` headers where applicable.
- **Vault Secret Structure**: Updated to support `_CURRENT` and `_NEXT` passwords for zero-downtime rotation (remains backward compatible).
- **Dependencies**: Added `opentelemetry` packages to `requirements.txt` for optional distributed tracing.

### Fixed
- Fixed a syntax error (unterminated f-string) in `services/ingestor_service.py`.
- Fixed an `ImportError` in `services/slo_checker.py` by adding the correct module prefix.
- Resolved multiple test failures to bring the test suite to 100% passing.

### Deprecated
- All `/api/v1/*` endpoints are now considered deprecated in favor of `/api/v2/*` endpoints. They remain functional but will be removed in a future release.

## [2.3.0] - 2025-06-01

- Initial production-ready release of the v2 architecture
- Core services (Ingestor, Alerter, Web UI) with Vault/Redis/Postgres integrations
- Basic metrics and dashboards; initial ADRs
