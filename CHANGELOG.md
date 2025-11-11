# Changelog

All notable changes to this project will be documented in this file.

## [2.5.0] - 2025-11-10

Highlights
- Added Redis-backed circuit breaker to Moog Forwarder with metrics
- Completed v2 API aliases across Web UI and Ingestor; version headers standardized
- Implemented config-change audit on rules CRUD; added read endpoints and UI panel
- Consolidated Prometheus alert rules (alerts-v25.yml) and added README link
- Added docker-compose test harness, mock Moog service, and E2E smoke test
- Expanded developer tooling (`muttdev`: retention, e2e, load) and onboarding docs
- Added code-level docs: API reference, module overview, DB schema, examples; master docs index

Fixes & Improvements
- Backpressure try/except guard in Alerter to avoid flow disruption on transient Redis errors
- Fixed forwarder health/metrics port references in docs; updated QUICKSTART to v2 ingest path
- Syntax and indentation cleanup in services (Web UI, Alerter, Forwarder)

Docs
- New: docs/INDEX.md, docs/api/REFERENCE.md, docs/code/MODULES.md, docs/db/SCHEMA.md, docs/code/EXAMPLES.md, docs/dev/ONBOARDING.md
- OpenAPI: docs/api/openapi.yaml with ReDoc viewer at docs/api/redoc.html

## [2.3.0] - 2025-06-01

- Initial production-ready release of the v2 architecture
- Core services (Ingestor, Alerter, Web UI) with Vault/Redis/Postgres integrations
- Basic metrics and dashboards; initial ADRs

