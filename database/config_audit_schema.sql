-- =====================================================================
-- MUTT v2.5 - Configuration Audit Log Schema
-- =====================================================================
-- Purpose: Track all configuration changes for compliance (SOX/GDPR)
-- Created: 2025-11-09
-- Version: v2.5
-- =====================================================================

-- =====================================================================
-- Configuration Audit Log Table
-- =====================================================================
-- Captures complete audit trail of all configuration changes including:
-- - WHO made the change (changed_by)
-- - WHAT was changed (table_name, record_id, old/new values)
-- - WHEN it happened (changed_at)
-- - WHY it was changed (reason)
-- - HOW to track it (correlation_id for request tracing)
-- =====================================================================

CREATE TABLE IF NOT EXISTS config_audit_log (
    -- Primary key
    id BIGSERIAL PRIMARY KEY,

    -- Timestamp of the change (defaults to current time)
    changed_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),

    -- Who made the change (API key name, username, or system process)
    changed_by VARCHAR(100) NOT NULL,

    -- Type of operation performed
    operation VARCHAR(10) NOT NULL CHECK (operation IN ('CREATE', 'UPDATE', 'DELETE')),

    -- Which table was modified
    table_name VARCHAR(50) NOT NULL,

    -- ID of the record that was modified
    record_id INTEGER NOT NULL,

    -- JSONB snapshot of values before the change (NULL for CREATE)
    old_values JSONB,

    -- JSONB snapshot of values after the change (NULL for DELETE)
    new_values JSONB,

    -- Optional reason/justification for the change
    reason TEXT,

    -- Correlation ID for tracing this change through all services
    correlation_id VARCHAR(36)
);

-- =====================================================================
-- Indexes for Performance
-- =====================================================================

-- Index for finding all changes to a specific record
-- Usage: SELECT * FROM config_audit_log WHERE table_name='alert_rules' AND record_id=42;
CREATE INDEX idx_config_audit_log_table_record
    ON config_audit_log(table_name, record_id);

-- Index for finding recent changes (most common query)
-- Usage: SELECT * FROM config_audit_log ORDER BY changed_at DESC LIMIT 100;
CREATE INDEX idx_config_audit_log_changed_at
    ON config_audit_log(changed_at DESC);

-- Index for tracking changes by user
-- Usage: SELECT * FROM config_audit_log WHERE changed_by='admin_api_key';
CREATE INDEX idx_config_audit_log_changed_by
    ON config_audit_log(changed_by);

-- Index for correlation ID tracking (request tracing)
-- Usage: SELECT * FROM config_audit_log WHERE correlation_id='abc-123-def-456';
CREATE INDEX idx_config_audit_log_correlation_id
    ON config_audit_log(correlation_id) WHERE correlation_id IS NOT NULL;

-- =====================================================================
-- JSONB Indexes for Searching Within Values
-- =====================================================================

-- GIN index for searching within old_values JSONB
-- Usage: SELECT * FROM config_audit_log WHERE old_values @> '{"priority": 100}';
CREATE INDEX idx_config_audit_log_old_values_gin
    ON config_audit_log USING GIN(old_values);

-- GIN index for searching within new_values JSONB
-- Usage: SELECT * FROM config_audit_log WHERE new_values @> '{"is_active": false}';
CREATE INDEX idx_config_audit_log_new_values_gin
    ON config_audit_log USING GIN(new_values);

-- =====================================================================
-- Comments for Documentation
-- =====================================================================

COMMENT ON TABLE config_audit_log IS
'Complete audit trail of all configuration changes. Required for SOX/GDPR compliance. Tracks WHO, WHAT, WHEN, WHY for every config modification.';

COMMENT ON COLUMN config_audit_log.changed_by IS
'User identifier (API key name, username, or system process) who made the change';

COMMENT ON COLUMN config_audit_log.operation IS
'Type of operation: CREATE (new record), UPDATE (modified record), DELETE (removed record)';

COMMENT ON COLUMN config_audit_log.old_values IS
'JSONB snapshot of record before change. NULL for CREATE operations. Used for rollback and diff views.';

COMMENT ON COLUMN config_audit_log.new_values IS
'JSONB snapshot of record after change. NULL for DELETE operations. Used for audit trail.';

COMMENT ON COLUMN config_audit_log.reason IS
'Optional human-readable reason for the change. Helps with compliance audits.';

COMMENT ON COLUMN config_audit_log.correlation_id IS
'Request correlation ID for distributed tracing. Links this change to other service logs.';

-- =====================================================================
-- Sample Data for Testing
-- =====================================================================

-- Example 1: Creating a new alert rule
INSERT INTO config_audit_log (
    changed_by,
    operation,
    table_name,
    record_id,
    old_values,
    new_values,
    reason,
    correlation_id
) VALUES (
    'admin_api_key',
    'CREATE',
    'alert_rules',
    1,
    NULL,
    '{"match_string": "ERROR", "priority": 100, "team_assignment": "NETO", "is_active": true}'::JSONB,
    'New rule for critical errors',
    'a1b2c3d4-e5f6-7890-abcd-ef1234567890'
);

-- Example 2: Updating an existing rule (changing priority)
INSERT INTO config_audit_log (
    changed_by,
    operation,
    table_name,
    record_id,
    old_values,
    new_values,
    reason,
    correlation_id
) VALUES (
    'webui_session_user_alice',
    'UPDATE',
    'alert_rules',
    1,
    '{"match_string": "ERROR", "priority": 100, "team_assignment": "NETO", "is_active": true}'::JSONB,
    '{"match_string": "ERROR", "priority": 200, "team_assignment": "NETO", "is_active": true}'::JSONB,
    'Increased priority due to production incidents',
    'b2c3d4e5-f6a7-8901-bcde-f12345678901'
);

-- Example 3: Deactivating a rule (soft delete)
INSERT INTO config_audit_log (
    changed_by,
    operation,
    table_name,
    record_id,
    old_values,
    new_values,
    reason,
    correlation_id
) VALUES (
    'automation_service',
    'UPDATE',
    'alert_rules',
    1,
    '{"match_string": "ERROR", "priority": 200, "team_assignment": "NETO", "is_active": true}'::JSONB,
    '{"match_string": "ERROR", "priority": 200, "team_assignment": "NETO", "is_active": false}'::JSONB,
    'Rule no longer needed after infrastructure upgrade',
    'c3d4e5f6-a7b8-9012-cdef-123456789012'
);

-- Example 4: Hard deleting a rule
INSERT INTO config_audit_log (
    changed_by,
    operation,
    table_name,
    record_id,
    old_values,
    new_values,
    reason
) VALUES (
    'admin_api_key',
    'DELETE',
    'alert_rules',
    99,
    '{"match_string": "DEPRECATED", "priority": 50, "team_assignment": "LEGACY", "is_active": false}'::JSONB,
    NULL,
    'Cleanup of old deprecated rules'
);

-- =====================================================================
-- Verification Queries
-- =====================================================================

-- View all sample audit records
-- SELECT * FROM config_audit_log ORDER BY changed_at DESC;

-- View audit trail for a specific rule
-- SELECT * FROM config_audit_log WHERE table_name='alert_rules' AND record_id=1 ORDER BY changed_at;

-- Find who made changes in the last 24 hours
-- SELECT DISTINCT changed_by FROM config_audit_log WHERE changed_at >= NOW() - INTERVAL '24 hours';

-- Find all changes to active rules
-- SELECT * FROM config_audit_log WHERE new_values @> '{"is_active": true}';

-- =====================================================================
-- Maintenance Notes
-- =====================================================================

-- Consider partitioning by month if audit log grows very large:
-- CREATE TABLE config_audit_log_partitioned (...) PARTITION BY RANGE (changed_at);

-- For compliance, consider retention policy:
-- Typically: Keep 90 days online, 7 years in archive

-- =====================================================================
-- End of Schema
-- =====================================================================
