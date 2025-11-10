Next Step: Database Schema & Initialization
Priority: CRITICAL (Deploy Blocker)
The v2.3 services reference PostgreSQL tables that do not exist in any documentation. Without these, services will crash on startup with "relation does not exist" errors.
Database Schema Definition
File: matt_schema.sql
sql
Copy

-- =============================================
-- MUTT Project v2.3 Database Schema
-- PostgreSQL 14+ (with TLS support)
-- =============================================

-- Enable UUID extension for correlation IDs (optional but recommended)
CREATE EXTENSION IF NOT EXISTS "uuid-ossp";

-- =============================================
-- Table: alert_rules
-- Core matching rules for event processing
-- =============================================

CREATE TABLE IF NOT EXISTS alert_rules (
    id SERIAL PRIMARY KEY,
    
    -- Matching criteria
    match_string TEXT,  -- Text to match in message (contains/regex)
    trap_oid TEXT,      -- SNMP trap OID (exact or prefix)
    syslog_severity TEXT,  -- syslog severity level (if applicable)
    match_type VARCHAR(20) NOT NULL DEFAULT 'contains' 
        CHECK (match_type IN ('contains', 'regex', 'oid_prefix')),
    
    -- Priority: lower numbers = higher priority (1 = highest)
    priority INTEGER NOT NULL DEFAULT 100,
    
    -- Handling decisions (environment-aware)
    prod_handling VARCHAR(30) NOT NULL 
        CHECK (prod_handling IN ('Page_and_ticket', 'Page_only', 'Ticket_only', 'Ignore')),
    dev_handling VARCHAR(30) NOT NULL 
        CHECK (dev_handling IN ('Page_and_ticket', 'Page_only', 'Ticket_only', 'Ignore')),
    
    -- Team assignment for Moogsoft
    team_assignment VARCHAR(10) NOT NULL DEFAULT 'NETO',
    
    -- Rule state
    is_active BOOLEAN NOT NULL DEFAULT TRUE,
    
    -- Audit fields
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    created_by VARCHAR(100) DEFAULT 'system',
    
    -- Constraints
    CONSTRAINT at_least_one_match_criteria 
        CHECK (match_string IS NOT NULL OR trap_oid IS NOT NULL)
);

-- Indexes for fast rule lookup
CREATE INDEX idx_alert_rules_active_priority ON alert_rules(is_active, priority ASC);
CREATE INDEX idx_alert_rules_trap_oid ON alert_rules(trap_oid) WHERE trap_oid IS NOT NULL;
CREATE INDEX idx_alert_rules_match_string ON alert_rules(match_string) WHERE match_string IS NOT NULL;

-- =============================================
-- Table: development_hosts
-- Hosts classified as development environment
-- =============================================

CREATE TABLE IF NOT EXISTS development_hosts (
    hostname VARCHAR(255) PRIMARY KEY,
    description TEXT,
    added_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    added_by VARCHAR(100) DEFAULT 'system'
);

CREATE INDEX idx_dev_hosts_hostname ON development_hosts(hostname);

-- =============================================
-- Table: device_teams
-- Mapping of devices to teams for alert routing
-- =============================================

CREATE TABLE IF NOT EXISTS device_teams (
    hostname VARCHAR(255) PRIMARY KEY,
    team_assignment VARCHAR(10) NOT NULL DEFAULT 'NETO',
    assigned_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    assigned_by VARCHAR(100) DEFAULT 'system'
);

CREATE INDEX idx_device_teams_team ON device_teams(team_assignment);

-- =============================================
-- Table: event_audit_log
-- Complete audit trail of all processed events
-- =============================================

CREATE TABLE IF NOT EXISTS event_audit_log (
    id BIGSERIAL PRIMARY KEY,
    
    -- Event metadata
    event_timestamp TIMESTAMPTZ NOT NULL,
    correlation_id UUID,  -- From event payload
    hostname VARCHAR(255) NOT NULL,
    source_type VARCHAR(20) DEFAULT 'solarwinds',
    
    -- Rule matching result
    matched_rule_id INTEGER REFERENCES alert_rules(id) ON DELETE SET NULL,
    handling_decision VARCHAR(30) NOT NULL,
    forwarded_to_moog BOOLEAN NOT NULL DEFAULT FALSE,
    
    -- Original payload (for forensics)
    raw_message JSONB NOT NULL,
    
    -- Processing metadata
    processed_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    processor_pod VARCHAR(100)  -- Which alerter pod processed this
);

-- Partitioning strategy: Partition by month for performance
-- CREATE TABLE event_audit_log_2025_01 PARTITION OF event_audit_log
--     FOR VALUES FROM ('2025-01-01') TO ('2025-02-01');

-- Indexes for query performance
CREATE INDEX idx_audit_log_timestamp ON event_audit_log(event_timestamp DESC);
CREATE INDEX idx_audit_log_hostname ON event_audit_log(hostname);
CREATE INDEX idx_audit_log_correlation_id ON event_audit_log(correlation_id);
CREATE INDEX idx_audit_log_rule_id ON event_audit_log(matched_rule_id) WHERE matched_rule_id IS NOT NULL;
CREATE INDEX idx_audit_log_processed_at ON event_audit_log(processed_at DESC);

-- Composite index for common dashboard queries
CREATE INDEX idx_audit_log_hostname_timestamp ON event_audit_log(hostname, event_timestamp DESC);

-- =============================================
-- Optional: View for unhandled events summary
-- =============================================

CREATE OR REPLACE VIEW unhandled_events_summary AS
SELECT 
    DATE_TRUNC('hour', processed_at) AS hour,
    hostname,
    COUNT(*) as unhandled_count
FROM event_audit_log
WHERE matched_rule_id IS NULL
GROUP BY hour, hostname
ORDER BY hour DESC, unhandled_count DESC;

-- =============================================
-- Sample Data for Initial Setup
-- =============================================

-- Example: Add some development hosts
INSERT INTO development_hosts (hostname, description) VALUES
    ('dev-switch-01', 'Development lab switch'),
    ('test-router-02', 'QA environment router')
ON CONFLICT DO NOTHING;

-- Example: Add team mappings
INSERT INTO device_teams (hostname, team_assignment) VALUES
    ('core-router-01', 'NETCORE'),
    ('edge-firewall-01', 'SECURITY'),
    ('dc-switch-01', 'NETCORE')
ON CONFLICT (hostname) DO UPDATE SET team_assignment = EXCLUDED.team_assignment;

-- Example: Add basic alert rules
INSERT INTO alert_rules 
    (match_string, trap_oid, syslog_severity, match_type, priority, 
     prod_handling, dev_handling, team_assignment, is_active)
VALUES
    -- Critical interface events
    ('Interface down', NULL, NULL, 'contains', 10, 
     'Page_and_ticket', 'Ticket_only', 'NETCORE', TRUE),
    
    -- OSPF neighbor down (SNMP trap)
    (NULL, '1.3.6.1.4.1.9.1.1.1.1', NULL, 'oid_prefix', 5,
     'Page_and_ticket', 'Ticket_only', 'NETCORE', TRUE),
    
    -- High CPU (syslog)
    ('CPU utilization', NULL, 'Critical', 'contains', 20,
     'Ticket_only', 'Ignore', 'NETCORE', TRUE),
    
    -- Low severity events (catch-all)
    ('WARNING', NULL, NULL, 'contains', 100,
     'Ticket_only', 'Ignore', 'NETO', TRUE)
ON CONFLICT DO NOTHING;

-- =============================================
-- Migration Notes
-- =============================================

-- To add columns in future versions:
-- ALTER TABLE alert_rules ADD COLUMN IF NOT EXISTS new_field TEXT;

-- To backfill data:
-- UPDATE alert_rules SET team_assignment = 'NETO' WHERE team_assignment IS NULL;

-- To create a read-only user for Web UI:
-- CREATE USER mutt_webui WITH PASSWORD 'strong-password';
-- GRANT SELECT ON ALL TABLES IN SCHEMA public TO mutt_webui;
-- GRANT INSERT ON event_audit_log TO mutt_webui;

Database Connection Pooling Configuration
Environment Variables (All Services)
bash
Copy

# PostgreSQL Pool Settings
DB_POOL_MIN_CONN=2          # Minimum idle connections
DB_POOL_MAX_CONN=10         # Maximum connections per pod
DB_POOL_MAX_OVERFLOW=5      # Extra connections beyond pool size (SQLAlchemy-specific, but similar concept)

Performance Tuning Notes

    alert_rules table: Keep it small (<10k rows). Cache reloads are SELECT *.
    event_audit_log: Will be your largest table. Partition by time (monthly).
    PG Bouncer: Consider using PgBouncer for connection pooling at the database level in high-scale deployments.
    Index maintenance: Run VACUUM ANALYZE weekly, REINDEX monthly on event_audit_log.