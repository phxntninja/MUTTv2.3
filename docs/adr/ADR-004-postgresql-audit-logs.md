# ADR-004: PostgreSQL for Audit Logs

**Status:** Accepted
**Date:** 2025-11-11
**Deciders:** MUTT Development Team
**Technical Story:** Audit log storage and compliance

## Context and Problem Statement

MUTT requires comprehensive audit logging for compliance (SOX, GDPR, HIPAA). Audit logs must be:
- Immutable and tamper-evident
- Queryable with complex filters (by user, time range, operation, table)
- Retained for 7 years (regulatory requirement)
- Performant for both writes and queries

Should we use PostgreSQL, Elasticsearch, MongoDB, or a specialized audit log system?

## Decision Drivers

* Compliance requirements (SOX, GDPR, HIPAA)
* Query performance for audit reports
* Long-term storage cost (7-year retention)
* Data integrity and immutability
* Operational complexity
* Team expertise

## Considered Options

* PostgreSQL with partitioned tables
* Elasticsearch for log aggregation
* MongoDB for document storage
* Specialized audit systems (e.g., Splunk, Sumo Logic)
* AWS CloudTrail / Azure Activity Log (cloud-native)

## Decision Outcome

Chosen option: **PostgreSQL with table partitioning**, because:

1. **ACID guarantees**: Full transactional integrity for audit entries
2. **Structured queries**: Complex filtering with SQL (JOIN, WHERE, GROUP BY)
3. **Existing expertise**: Team has strong PostgreSQL skills
4. **Cost effective**: No additional licensing or infrastructure
5. **Partitioning**: Efficient archival and purging with monthly partitions
6. **Proven at scale**: Handles billions of rows with proper indexing

### Positive Consequences

* Single database for operational data and audit logs (simpler architecture)
* Strong data integrity guarantees (audit logs cannot be modified)
* Powerful query capabilities for compliance reports
* Automatic partition management for retention policies
* Point-in-time recovery and backups included
* No additional operational overhead

### Negative Consequences

* Higher storage cost than object storage for long-term retention
* Requires careful partitioning strategy for performance
* Backup/restore time increases with data volume
* Not optimized for full-text search (mitigated by limited need)

## Pros and Cons of the Options

### PostgreSQL with Partitioning

* Good, because ACID transactions ensure audit integrity
* Good, because powerful SQL queries for compliance reports
* Good, because native partitioning for efficient archival
* Good, because team expertise reduces operational risk
* Good, because write-ahead logging (WAL) provides tamper-evidence
* Good, because existing backup/recovery procedures apply
* Bad, because higher storage cost than cold storage
* Bad, because requires partition management automation

### Elasticsearch

* Good, because optimized for log aggregation
* Good, because excellent full-text search
* Good, because scales horizontally easily
* Bad, because eventual consistency (not ACID)
* Bad, because additional infrastructure to maintain
* Bad, because query language less familiar to team
* Bad, because data integrity not as strong as PostgreSQL

### MongoDB

* Good, because flexible schema
* Good, because scales horizontally
* Bad, because weaker consistency guarantees
* Bad, because less mature compliance features
* Bad, because team lacks MongoDB expertise
* Bad, because SQL queries are more expressive for audit reports

### Specialized Audit Systems

* Good, because built specifically for audit/compliance
* Good, because often includes compliance reporting
* Bad, because significant licensing costs
* Bad, because vendor lock-in
* Bad, because integration complexity
* Bad, because overkill for our requirements

### Cloud-Native Solutions

* Good, because managed service (no infrastructure)
* Good, because built-in compliance features
* Bad, because vendor lock-in
* Bad, because cannot run on-premise (RHEL requirement)
* Bad, because less control over data retention
* Bad, because cost at scale

## Implementation Details

**Schema Design**:
```sql
CREATE TABLE config_audit_log (
    id BIGSERIAL PRIMARY KEY,
    changed_at TIMESTAMPTZ NOT NULL,
    changed_by VARCHAR(255) NOT NULL,
    operation VARCHAR(50) NOT NULL,  -- CREATE, UPDATE, DELETE
    table_name VARCHAR(255) NOT NULL,
    record_id INTEGER NOT NULL,
    old_values JSONB,
    new_values JSONB,
    reason TEXT,
    correlation_id VARCHAR(255)
) PARTITION BY RANGE (changed_at);
```

**Partitioning Strategy**:
* Monthly partitions for active data (90 days)
* Automatic partition creation via CronJob
* Archive partitions older than 90 days
* Retention policy: 7 years in archive

**Indexes**:
```sql
CREATE INDEX idx_audit_changed_at ON config_audit_log(changed_at);
CREATE INDEX idx_audit_changed_by ON config_audit_log(changed_by);
CREATE INDEX idx_audit_operation ON config_audit_log(operation);
CREATE INDEX idx_audit_table_name ON config_audit_log(table_name);
CREATE INDEX idx_audit_correlation ON config_audit_log(correlation_id);
```

**Performance**:
* Write throughput: ~1000 audit entries/second
* Query performance: <100ms for filtered queries on indexed columns
* Partition switching: <1 second for monthly rollover

**Archival**:
* Active storage: 90 days (fast queries)
* Archive storage: 7 years (compliance)
* Purge: Automated deletion after 7 years

## Links

* [Audit Schema](../../database/config_audit_schema.sql)
* [Audit Logger Implementation](../../services/audit_logger.py)
* [Partition Management](../../scripts/create_monthly_partitions.py)
* [Archive Script](../../scripts/archive_old_events.py)
* [Related: ADR-002 Vault vs K8s Secrets](ADR-002-vault-vs-k8s-secrets.md)

## Notes

**Immutability**: Audit tables have no UPDATE or DELETE privileges granted to application users. Only retention policy automation can delete old records.

**Compliance Reports**:
* Who changed what and when
* All changes by a specific user
* All changes to a specific resource
* Changes within a time range
* Failed operations and security events

**Monitoring**:
* Alert if audit writes fail (potential compliance violation)
* Track partition sizes for capacity planning
* Monitor query performance for reporting

## Change Log

* 2025-11-11: Initial draft and acceptance
