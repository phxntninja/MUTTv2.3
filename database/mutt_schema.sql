│ -- =====================================================================                                             │
│ -- MUTT (Multi Use Telemetry Tool) PostgreSQL Schema (v2.1)                                                          │
│ -- =====================================================================                                             │
│ -- This script reflects the v2.1 architecture and includes:                                                          │
│ -- 1. `priority` and `match_type` in `alert_rules` for advanced matching.                                            │
│ -- 2. Partitioning for the `event_audit_log` table for performance.                                                  │
│ -- 3. Enhanced constraints for data integrity and security.                                                          │
│ -- =====================================================================                                             │
│                                                                                                                      │
│ -- Drop tables in reverse dependency order if they already exist                                                     │
│ DROP TABLE IF EXISTS event_audit_log;                                                                                │
│ DROP TABLE IF EXISTS alert_rules;                                                                                    │
│ DROP TABLE IF EXISTS development_hosts;                                                                              │
│ DROP TABLE IF EXISTS device_teams;                                                                                   │
│                                                                                                                      │
│ -- -----------------------------------------------------                                                             │
│ -- Table: alert_rules                                                                                                │
│ -- Purpose: Stores the core logic for matching Syslog and SNMP Traps.                                                │
│ -- This table will be cached in-memory by the Alerter Service.                                                       │
│ -- -----------------------------------------------------                                                             │
│ CREATE TABLE alert_rules (                                                                                           │
│     id SERIAL PRIMARY KEY,                                                                                           │
│                                                                                                                      │
│     -- Match Criteria (at least one must be non-NULL)                                                                │
│     match_string VARCHAR(255) NULL,                                                                                  │
│     trap_oid VARCHAR(255) NULL,                                                                                      │
│     syslog_severity INT NULL,                                                                                        │
│                                                                                                                      │
│     -- New columns for v2.1 advanced matching logic                                                                  │
│     match_type VARCHAR(20) NOT NULL DEFAULT 'contains'                                                               │
│         CHECK (match_type IN ('contains', 'regex', 'oid_prefix')),                                                   │
│     priority INT NOT NULL DEFAULT 100,                                                                               │
│                                                                                                                      │
│     -- Handling Decision                                                                                             │
│     prod_handling VARCHAR(100) NOT NULL,                                                                             │
│     dev_handling VARCHAR(100) NOT NULL,                                                                              │
│     team_assignment VARCHAR(100) NOT NULL,                                                                           │
│                                                                                                                      │
│     -- Rule State                                                                                                    │
│     is_active BOOLEAN NOT NULL DEFAULT true,                                                                         │
│                                                                                                                      │
│     -- Ensures that a rule has a valid match criteria                                                                │
│     CONSTRAINT chk_match_criteria CHECK (match_string IS NOT NULL OR trap_oid IS NOT NULL),                          │
│                                                                                                                      │
│     -- Ensures syslog_severity is in valid range (0-7)                                                               │
│     CONSTRAINT chk_syslog_severity CHECK (syslog_severity IS NULL OR (syslog_severity >= 0 AND syslog_severity <=    │
│ 7))                                                                                                                  │
│ );                                                                                                                   │
│                                                                                                                      │
│ -- Indexes for fast initial loading/querying                                                                         │
│ CREATE INDEX idx_alert_rules_match_type ON alert_rules (match_type);                                                 │
│ CREATE INDEX idx_alert_rules_is_active ON alert_rules (is_active);                                                   │
│                                                                                                                      │
│ COMMENT ON TABLE alert_rules IS 'Stores the core logic for matching Syslog/SNMP. Cached by the Alerter service.';    │
│ COMMENT ON COLUMN alert_rules.match_string IS 'Text string/regex to match in a syslog message.';                     │
│ COMMENT ON COLUMN alert_rules.trap_oid IS 'SNMP OID to match (e.g., .1.3.4.6.323.1 or .1.3.4.6.323.1.*).';           │
│ COMMENT ON COLUMN alert_rules.match_type IS 'How to interpret the match_string/trap_oid: contains, regex,            │
│ oid_prefix.';                                                                                                        │
│ COMMENT ON COLUMN alert_rules.priority IS 'Rule priority (lower number wins) if multiple rules match.';              │
│                                                                                                                      │
│ -- -----------------------------------------------------                                                             │
│ -- Table: development_hosts                                                                                          │
│ -- Purpose: A simple lookup table to identify hosts that should                                                      │
│ -- be treated as 'Development' environments.                                                                         │
│ -- -----------------------------------------------------                                                             │
│ CREATE TABLE development_hosts (                                                                                     │
│     hostname VARCHAR(255) PRIMARY KEY                                                                                │
│ );                                                                                                                   │
│                                                                                                                      │
│ COMMENT ON TABLE development_hosts IS 'A lookup set of hostnames (cached) to be treated as Development. If a host is │
│  not in this table, it is treated as Production.';                                                                   │
│                                                                                                                      │
│                                                                                                                      │
│ -- -----------------------------------------------------                                                             │
│ -- Table: device_teams                                                                                               │
│ -- Purpose: A lookup table to map specific hosts to their                                                            │
│ -- responsible teams. Used for routing "unhandled" alerts.                                                           │
│ -- -----------------------------------------------------                                                             │
│ CREATE TABLE device_teams (                                                                                          │
│     hostname VARCHAR(255) PRIMARY KEY,                                                                               │
│     team_assignment VARCHAR(100) NOT NULL                                                                            │
│ );                                                                                                                   │
│                                                                                                                      │
│ COMMENT ON TABLE device_teams IS 'Maps a device hostname to its default team (cached). Used for routing unhandled    │
│ alerts.';                                                                                                            │
│                                                                                                                      │
│                                                                                                                      │
│ -- -----------------------------------------------------                                                             │
│ -- Table: event_audit_log (Partitioned)                                                                              │
│ -- Purpose: Records every event that successfully matched a rule.                                                    │
│ -- This is the PARENT table for partitioning.                                                                        │
│ -- -----------------------------------------------------                                                             │
│ CREATE TABLE event_audit_log (                                                                                       │
│     id BIGSERIAL NOT NULL,                                                                                           │
│     event_timestamp TIMESTAMPTZ NOT NULL,                                                                            │
│     hostname VARCHAR(255) NOT NULL,                                                                                  │
│                                                                                                                      │
│     -- Foreign key to the rule that was matched                                                                      │
│     matched_rule_id INT NOT NULL,                                                                                    │
│                                                                                                                      │
│     handling_decision VARCHAR(100) NOT NULL,                                                                         │
│     forwarded_to_moog BOOLEAN NOT NULL DEFAULT false,                                                                │
│     raw_message TEXT,                                                                                                │
│                                                                                                                      │
│     -- Primary key must include partition column                                                                     │
│     PRIMARY KEY (id, event_timestamp)                                                                                │
│ ) PARTITION BY RANGE (event_timestamp);                                                                              │
│                                                                                                                      │
│ -- Foreign key constraint (requires PostgreSQL 11+)                                                                  │
│ ALTER TABLE event_audit_log                                                                                          │
│ ADD CONSTRAINT fk_event_audit_matched_rule                                                                           │
│ FOREIGN KEY (matched_rule_id) REFERENCES alert_rules(id) ON DELETE RESTRICT;                                         │
│                                                                                                                      │
│ -- Create indexes on the parent table; they will be inherited by all partitions.                                     │
│ CREATE INDEX idx_audit_log_timestamp ON event_audit_log (event_timestamp);                                           │
│ CREATE INDEX idx_audit_log_hostname ON event_audit_log (hostname);                                                   │
│ CREATE INDEX idx_audit_log_rule_id ON event_audit_log (matched_rule_id);                                             │
│                                                                                                                      │
│ COMMENT ON TABLE event_audit_log IS 'Partitioned parent table for the audit trail of all "handled" events.';         │
│ COMMENT ON COLUMN event_audit_log.id IS 'Note: This ID is only unique within its partition, not globally.';          │
│ COMMENT ON COLUMN event_audit_log.event_timestamp IS 'Timestamp with timezone from the original message.';           │
│                                                                                                                      │
│ -- -----------------------------------------------------                                                             │
│ -- Partition Creation (Example)                                                                                      │
│ -- -----------------------------------------------------                                                             │
│ -- Partitions must be created manually or by a cron job.                                                             │
│ -- This script creates the partition for the current month as an example.                                            │
│ -- In production, a script should run monthly to create N+1 partitions.                                              │
│ --                                                                                                                   │
│ -- Example for creating a partition for November 2025:                                                               │
│ /*                                                                                                                   │
│ CREATE TABLE IF NOT EXISTS event_audit_log_2025_11                                                                   │
│     PARTITION OF event_audit_log                                                                                     │
│     FOR VALUES FROM ('2025-11-01') TO ('2025-12-01');                                                                │
│ */                                                                                                                   │
│ -- Example for creating a partition for December 2025:                                                               │
│ /*                                                                                                                   │
│ CREATE TABLE IF NOT EXISTS event_audit_log_2025_12                                                                   │
│     PARTITION OF event_audit_log                                                                                     │
│     FOR VALUES FROM ('2025-12-01') TO ('2026-01-01');                                                                │
│ */                                                                                                                   │
│                                                                                                                      │
│ -- -----------------------------------------------------                                                             │
│ -- Partition Management Function (Optional)                                                                          │
│ -- Helper function to create future partitions                                                                       │
│ -- -----------------------------------------------------                                                             │
│ CREATE OR REPLACE FUNCTION create_monthly_partition(                                                                 │
│     start_date DATE                                                                                                  │
│ ) RETURNS void AS $$                                                                                                 │
│ DECLARE                                                                                                              │
│     partition_name TEXT;                                                                                             │
│     start_ts TEXT;                                                                                                   │
│     end_ts TEXT;                                                                                                     │
│ BEGIN                                                                                                                │
│     -- Generate partition name (e.g., event_audit_log_2025_11)                                                       │
│     partition_name := 'event_audit_log_' || TO_CHAR(start_date, 'YYYY_MM');                                          │
│                                                                                                                      │
│     -- Generate date ranges                                                                                          │
│     start_ts := TO_CHAR(start_date, 'YYYY-MM-DD');                                                                   │
│     end_ts := TO_CHAR(start_date + INTERVAL '1 month', 'YYYY-MM-DD');                                                │
│                                                                                                                      │
│     -- Create partition                                                                                              │
│     EXECUTE format(                                                                                                  │
│         'CREATE TABLE IF NOT EXISTS %I PARTITION OF event_audit_log FOR VALUES FROM (%L) TO (%L)',                   │
│         partition_name,                                                                                              │
│         start_ts,                                                                                                    │
│         end_ts                                                                                                       │
│     );                                                                                                               │
│                                                                                                                      │
│     RAISE NOTICE 'Created partition % for range % to %', partition_name, start_ts, end_ts;                           │
│ END;                                                                                                                 │
│ $$ LANGUAGE plpgsql;                                                                                                 │
│                                                                                                                      │
│ COMMENT ON FUNCTION create_monthly_partition IS 'Creates a new monthly partition for event_audit_log';               │
│                                                                                                                      │
│ -- Example usage:                                                                                                    │
│ -- SELECT create_monthly_partition('2025-11-01');                                                                    │
│ -- SELECT create_monthly_partition('2025-12-01');                                                                    │
│ -- SELECT create_monthly_partition('2026-01-01');                                                                    │
│                                                                                                                      │
│ -- -----------------------------------------------------                                                             │
│ -- Partition Cleanup Function (Optional)                                                                             │
│ -- Helper function to drop old partitions                                                                            │
│ -- -----------------------------------------------------                                                             │
│ CREATE OR REPLACE FUNCTION drop_old_partitions(                                                                      │
│     retention_months INTEGER                                                                                         │
│ ) RETURNS void AS $$                                                                                                 │
│ DECLARE                                                                                                              │
│     partition_record RECORD;                                                                                         │
│     cutoff_date DATE;                                                                                                │
│ BEGIN                                                                                                                │
│     cutoff_date := CURRENT_DATE - (retention_months || ' months')::INTERVAL;                                         │
│                                                                                                                      │
│     FOR partition_record IN                                                                                          │
│         SELECT tablename                                                                                             │
│         FROM pg_tables                                                                                               │
│         WHERE schemaname = 'public'                                                                                  │
│           AND tablename LIKE 'event_audit_log_%'                                                                     │
│           AND tablename != 'event_audit_log'                                                                         │
│     LOOP                                                                                                             │
│         -- Extract date from partition name (e.g., event_audit_log_2024_05)                                          │
│         DECLARE                                                                                                      │
│             partition_date DATE;                                                                                     │
│         BEGIN                                                                                                        │
│             partition_date := TO_DATE(                                                                               │
│                 SUBSTRING(partition_record.tablename FROM '\d{4}_\d{2}$'),                                           │
│                 'YYYY_MM'                                                                                            │
│             );                                                                                                       │
│                                                                                                                      │
│             IF partition_date < cutoff_date THEN                                                                     │
│                 EXECUTE format('DROP TABLE IF EXISTS %I', partition_record.tablename);                               │
│                 RAISE NOTICE 'Dropped old partition %', partition_record.tablename;                                  │
│             END IF;                                                                                                  │
│         EXCEPTION WHEN OTHERS THEN                                                                                   │
│             RAISE NOTICE 'Skipping partition % (could not parse date)', partition_record.tablename;                  │
│         END;                                                                                                         │
│     END LOOP;                                                                                                        │
│ END;                                                                                                                 │
│ $$ LANGUAGE plpgsql;                                                                                                 │
│                                                                                                                      │
│ COMMENT ON FUNCTION drop_old_partitions IS 'Drops event_audit_log partitions older than specified months';           │
│                                                                                                                      │
│ -- Example usage (drop partitions older than 6 months):                                                              │
│ -- SELECT drop_old_partitions(6);                                                                                    │
│                                                                                                                      │
│ -- =====================================================================                                             │
│ -- Sample Data (Optional - for testing)                                                                              │
│ -- =====================================================================                                             │
│                                                                                                                      │
│ -- Example alert rules                                                                                               │
│ INSERT INTO alert_rules (match_string, match_type, priority, prod_handling, dev_handling, team_assignment) VALUES    │
│     ('CRITICAL', 'contains', 10, 'Page_and_ticket', 'Ticket_only', 'NETO'),                                          │
│     ('ERROR', 'contains', 20, 'Ticket_only', 'Ignore', 'NETO'),                                                      │
│     ('LINK-DOWN', 'contains', 5, 'Page_and_ticket', 'Ticket_only', 'NetOps'),                                        │
│     ('DOT1X-FIRMWARE-RUNNING', 'contains', 50, 'Ticket_only', 'Ignore', 'Security');                                 │
│                                                                                                                      │
│ -- Example SNMP trap rule                                                                                            │
│ INSERT INTO alert_rules (trap_oid, match_type, priority, prod_handling, dev_handling, team_assignment) VALUES        │
│     ('.1.3.6.1.4.1.9.9.41.2', 'oid_prefix', 15, 'Page_and_ticket', 'Ignore', 'NetOps');                              │
│                                                                                                                      │
│ -- Example development hosts                                                                                         │
│ INSERT INTO development_hosts (hostname) VALUES                                                                      │
│     ('dev-router1'),                                                                                                 │
│     ('test-switch1'),                                                                                                │
│     ('qa-firewall1');                                                                                                │
│                                                                                                                      │
│ -- Example device teams                                                                                              │
│ INSERT INTO device_teams (hostname, team_assignment) VALUES                                                          │
│     ('router1.prod.example.com', 'NetOps'),                                                                          │
│     ('switch1.prod.example.com', 'NetOps'),                                                                          │
│     ('firewall1.prod.example.com', 'Security'),                                                                      │
│     ('server1.prod.example.com', 'SysAdmin');                                                                        │
│                                                                                                                      │
│ -- =====================================================================                                             │
│ -- End of Schema                                                                                                     │
│ -- =====================================================================     