# ADR-004: PostgreSQL for Audit Logs

- Status: Accepted
- Date: 2025-11-10

Context
- Need reliable, queryable configuration change audits with compliance retention.

Decision
- Store config audits in PostgreSQL `config_audit_log` with JSONB for old/new values; partition event audits in `event_audit_log` and optionally archive.

Consequences
- Pros: ACID, indexing, JSONB queries, fewer moving parts; easy retention via jobs.
- Cons: Heavier DB storage; limited full-text analytics.

Alternatives Considered
- Elasticsearch/Splunk: Powerful search but adds infra and cost; not needed for compliance baseline.

References
- database/config_audit_schema.sql
- database/partitioned_event_audit_log.sql
- scripts/retention_cleanup.py

