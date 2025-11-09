-- =====================================================================
-- MUTT v2.5 - Event Audit Log Partitioning & Archival Extensions
-- =====================================================================
-- Purpose: Extend v2.3 event_audit_log with archival and retention
-- Created: 2025-11-09
-- Version: v2.5
--
-- This extends the existing partitioned event_audit_log table from v2.3
-- with additional features:
-- - Archive table for long-term compliance storage (7 years)
-- - Pre-created partitions for next 3 months
-- - Data archival utilities
-- =====================================================================

-- =====================================================================
-- Archive Table for Long-Term Storage
-- =====================================================================
-- Purpose: Store events older than retention period for compliance
-- Retention: Typically 7 years for SOX/GDPR compliance
-- Storage: Can be moved to cheaper storage tier
-- =====================================================================

CREATE TABLE IF NOT EXISTS event_audit_log_archive (
    id BIGSERIAL PRIMARY KEY,

    -- Original event data (same structure as event_audit_log)
    event_timestamp TIMESTAMPTZ NOT NULL,
    hostname VARCHAR(255) NOT NULL,
    matched_rule_id INT NOT NULL,
    handling_decision VARCHAR(100) NOT NULL,
    forwarded_to_moog BOOLEAN NOT NULL DEFAULT false,
    raw_message TEXT,

    -- Archival metadata
    archived_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    archived_from_partition VARCHAR(50),  -- Original partition name

    -- Original ID from event_audit_log (for reference)
    original_id BIGINT,
    original_partition_timestamp TIMESTAMPTZ
);

-- Indexes for archive table
CREATE INDEX idx_audit_archive_timestamp ON event_audit_log_archive (event_timestamp);
CREATE INDEX idx_audit_archive_hostname ON event_audit_log_archive (hostname);
CREATE INDEX idx_audit_archive_archived_at ON event_audit_log_archive (archived_at);
CREATE INDEX idx_audit_archive_rule_id ON event_audit_log_archive (matched_rule_id);

COMMENT ON TABLE event_audit_log_archive IS
'Long-term archive storage for events older than retention period. Typically 7 years for compliance.';

COMMENT ON COLUMN event_audit_log_archive.archived_at IS
'Timestamp when the event was moved from active storage to archive';

COMMENT ON COLUMN event_audit_log_archive.archived_from_partition IS
'Name of the original partition (e.g., event_audit_log_2025_01)';

-- =====================================================================
-- Pre-Create Partitions for Next 3 Months
-- =====================================================================
-- Purpose: Prevent runtime partition creation issues
-- Note: Update these dates as needed for your deployment
-- =====================================================================

-- Get current date and create next 3 months
DO $$
DECLARE
    current_month DATE;
    i INTEGER;
BEGIN
    -- Start from current month
    current_month := DATE_TRUNC('month', CURRENT_DATE);

    -- Create partitions for next 3 months
    FOR i IN 0..2 LOOP
        PERFORM create_monthly_partition(current_month + (i || ' months')::INTERVAL);
    END LOOP;

    RAISE NOTICE 'Pre-created partitions for next 3 months starting from %', current_month;
END $$;

-- =====================================================================
-- Archive Function - Move Old Events to Archive Table
-- =====================================================================
-- Purpose: Move events older than retention period to archive
-- Parameters:
--   retention_days: Number of days to keep in active storage (default: 90)
--   batch_size: Number of rows to archive per batch (default: 10000)
-- Returns: Number of rows archived
-- =====================================================================

CREATE OR REPLACE FUNCTION archive_old_events(
    retention_days INTEGER DEFAULT 90,
    batch_size INTEGER DEFAULT 10000
) RETURNS BIGINT AS $$
DECLARE
    rows_archived BIGINT := 0;
    total_archived BIGINT := 0;
    cutoff_timestamp TIMESTAMPTZ;
    partition_record RECORD;
BEGIN
    -- Calculate cutoff timestamp
    cutoff_timestamp := NOW() - (retention_days || ' days')::INTERVAL;

    RAISE NOTICE 'Starting archival of events older than % (cutoff: %)',
                 retention_days || ' days', cutoff_timestamp;

    -- Find all partitions with data older than cutoff
    FOR partition_record IN
        SELECT
            child.relname AS partition_name,
            pg_get_expr(child.relpartbound, child.oid, true) AS partition_bound
        FROM pg_inherits
        JOIN pg_class parent ON pg_inherits.inhparent = parent.oid
        JOIN pg_class child ON pg_inherits.inhrelid = child.oid
        WHERE parent.relname = 'event_audit_log'
        ORDER BY child.relname
    LOOP
        -- Archive events from this partition in batches
        LOOP
            -- Insert into archive (batch)
            INSERT INTO event_audit_log_archive (
                event_timestamp,
                hostname,
                matched_rule_id,
                handling_decision,
                forwarded_to_moog,
                raw_message,
                archived_from_partition,
                original_id,
                original_partition_timestamp
            )
            SELECT
                event_timestamp,
                hostname,
                matched_rule_id,
                handling_decision,
                forwarded_to_moog,
                raw_message,
                partition_record.partition_name,
                id,
                event_timestamp
            FROM event_audit_log
            WHERE event_timestamp < cutoff_timestamp
            LIMIT batch_size;

            GET DIAGNOSTICS rows_archived = ROW_COUNT;

            EXIT WHEN rows_archived = 0;

            -- Delete archived rows
            DELETE FROM event_audit_log
            WHERE event_timestamp < cutoff_timestamp
            AND id IN (
                SELECT original_id
                FROM event_audit_log_archive
                WHERE archived_from_partition = partition_record.partition_name
                ORDER BY id DESC
                LIMIT batch_size
            );

            total_archived := total_archived + rows_archived;

            RAISE NOTICE 'Archived % rows from partition %',
                         rows_archived, partition_record.partition_name;

            -- Commit batch
            COMMIT;
        END LOOP;
    END LOOP;

    RAISE NOTICE 'Archival complete. Total rows archived: %', total_archived;
    RETURN total_archived;
END;
$$ LANGUAGE plpgsql;

COMMENT ON FUNCTION archive_old_events IS
'Archives events older than retention period to event_audit_log_archive. Runs in batches to avoid long locks.';

-- =====================================================================
-- Function: Get Archive Statistics
-- =====================================================================
-- Purpose: Show statistics about archived data
-- Returns: Statistics as a table
-- =====================================================================

CREATE OR REPLACE FUNCTION get_archive_statistics()
RETURNS TABLE (
    metric_name TEXT,
    metric_value TEXT
) AS $$
BEGIN
    RETURN QUERY
    SELECT 'Total Archived Events'::TEXT, COUNT(*)::TEXT
    FROM event_audit_log_archive

    UNION ALL

    SELECT 'Oldest Archived Event'::TEXT, MIN(event_timestamp)::TEXT
    FROM event_audit_log_archive

    UNION ALL

    SELECT 'Newest Archived Event'::TEXT, MAX(event_timestamp)::TEXT
    FROM event_audit_log_archive

    UNION ALL

    SELECT 'Archive Table Size'::TEXT, pg_size_pretty(pg_total_relation_size('event_audit_log_archive'))

    UNION ALL

    SELECT 'Active Events Count'::TEXT, COUNT(*)::TEXT
    FROM event_audit_log

    UNION ALL

    SELECT 'Active Table Size'::TEXT, pg_size_pretty(pg_total_relation_size('event_audit_log'));
END;
$$ LANGUAGE plpgsql;

COMMENT ON FUNCTION get_archive_statistics IS
'Returns statistics about archived and active event data';

-- =====================================================================
-- Function: Delete Old Archives (Compliance Cleanup)
-- =====================================================================
-- Purpose: Delete archives older than compliance retention period
-- Parameters:
--   retention_years: Number of years to keep in archive (default: 7)
-- Returns: Number of rows deleted
-- =====================================================================

CREATE OR REPLACE FUNCTION delete_old_archives(
    retention_years INTEGER DEFAULT 7
) RETURNS BIGINT AS $$
DECLARE
    rows_deleted BIGINT;
    cutoff_timestamp TIMESTAMPTZ;
BEGIN
    -- Calculate cutoff timestamp
    cutoff_timestamp := NOW() - (retention_years || ' years')::INTERVAL;

    RAISE NOTICE 'Deleting archived events older than % years (cutoff: %)',
                 retention_years, cutoff_timestamp;

    -- Delete old archives
    DELETE FROM event_audit_log_archive
    WHERE event_timestamp < cutoff_timestamp;

    GET DIAGNOSTICS rows_deleted = ROW_COUNT;

    RAISE NOTICE 'Deleted % archived events older than % years',
                 rows_deleted, retention_years;

    RETURN rows_deleted;
END;
$$ LANGUAGE plpgsql;

COMMENT ON FUNCTION delete_old_archives IS
'Deletes archived events older than compliance retention period (default: 7 years)';

-- =====================================================================
-- View: Partition Health Summary
-- =====================================================================
-- Purpose: Show status of all partitions and their sizes
-- =====================================================================

CREATE OR REPLACE VIEW partition_health_summary AS
SELECT
    child.relname AS partition_name,
    pg_get_expr(child.relpartbound, child.oid, true) AS partition_range,
    pg_size_pretty(pg_total_relation_size(child.oid)) AS partition_size,
    (SELECT COUNT(*)
     FROM pg_catalog.pg_class c
     WHERE c.relname = child.relname) AS row_count_estimate
FROM pg_inherits
JOIN pg_class parent ON pg_inherits.inhparent = parent.oid
JOIN pg_class child ON pg_inherits.inhrelid = child.oid
WHERE parent.relname = 'event_audit_log'
ORDER BY child.relname DESC;

COMMENT ON VIEW partition_health_summary IS
'Shows all event_audit_log partitions with their sizes and ranges';

-- =====================================================================
-- Migration Notes
-- =====================================================================
-- If upgrading from v2.3 with existing data:
--
-- 1. Existing event_audit_log partitions are preserved
-- 2. Archive table is created fresh
-- 3. Run archive_old_events() to move old data to archive:
--    SELECT archive_old_events(retention_days => 90);
--
-- 4. Set up automated archival (see scripts/archive_old_events.py)
--
-- =====================================================================

-- =====================================================================
-- Usage Examples
-- =====================================================================

-- Create partition for a specific month
-- SELECT create_monthly_partition('2026-01-01');

-- Archive events older than 90 days
-- SELECT archive_old_events(retention_days => 90, batch_size => 10000);

-- View archive statistics
-- SELECT * FROM get_archive_statistics();

-- Delete archives older than 7 years
-- SELECT delete_old_archives(retention_years => 7);

-- View partition health
-- SELECT * FROM partition_health_summary;

-- =====================================================================
-- Maintenance Schedule (Recommended)
-- =====================================================================
-- Daily:   Run archive_old_events() to move old data to archive
-- Weekly:  Check partition_health_summary for growth trends
-- Monthly: Create next month's partition (automated via cron)
-- Yearly:  Run delete_old_archives() for compliance cleanup
-- =====================================================================

-- =====================================================================
-- Performance Notes
-- =====================================================================
-- 1. Archival runs in batches to avoid long table locks
-- 2. Archive table has separate indexes for query performance
-- 3. Old partitions can be dropped after archival for space reclamation
-- 4. Consider moving archive table to cheaper storage tier
-- =====================================================================

\echo 'Event audit log partitioning & archival extensions loaded (v2.5)'
