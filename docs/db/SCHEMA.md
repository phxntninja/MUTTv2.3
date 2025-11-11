MUTT v2.5 — Database Schema

Overview
- Primary store: PostgreSQL
- Audit trail for events and configuration changes
- Partitioned tables for scalable event logging

Tables
1) alert_rules
   - id (serial, PK)
   - match_string (text, nullable if trap_oid is used)
   - trap_oid (text, nullable)
   - syslog_severity (int, nullable)
   - match_type (text: contains|regex|oid_prefix)
   - priority (int, default 100)
   - prod_handling (text)
   - dev_handling (text)
   - team_assignment (text)
   - is_active (bool, default true)
   - Indexes: by match_type, is_active; consider priority

2) development_hosts
   - hostname (text, PK)

3) device_teams
   - hostname (text, PK)
   - team_assignment (text)

4) event_audit_log (partitioned by month)
   - id (bigserial, PK)
   - event_timestamp (timestamptz, NOT NULL)
   - hostname (text)
   - matched_rule_id (int, FK -> alert_rules.id)
   - handling_decision (text)
   - forwarded_to_moog (bool)
   - raw_message (text or json)
   - Indexes: by event_timestamp, hostname, matched_rule_id
   - Partitions: monthly (YYYY_MM)

5) config_audit_log
   - id (bigserial, PK)
   - changed_at (timestamptz, default now())
   - changed_by (varchar)
   - operation (varchar: CREATE|UPDATE|DELETE)
   - table_name (varchar)
   - record_id (int)
   - old_values (jsonb, nullable)
   - new_values (jsonb, nullable)
   - reason (text, nullable)
   - correlation_id (varchar, nullable)
   - Indexes: (table_name, record_id), changed_at desc, changed_by, GIN on old_values/new_values

Helper Functions & Jobs
- Partition helpers: create_monthly_partition(date), drop_old_partitions(retention_months)
- Scripts:
  - scripts/create_monthly_partitions.py — pre-create partitions (default RETENTION_PRECREATE_MONTHS)
  - scripts/retention_cleanup.py — periodic cleanup

Relationships
- alert_rules referenced by event_audit_log.matched_rule_id
- device_teams/development_hosts used by Alerter for enrichment and matching

Query Patterns
- Fetch active rules ordered by priority on startup; refresh cache periodically
- Paginated reads from event_audit_log and config_audit_log for UI endpoints
- JSONB containment queries for audit diffs (requires GIN index)

Migrations
- Maintain SQL under database/*.sql
- Apply with psql during deployment
- For partition changes, roll forward by creating future partitions (never drop current/month)

