#!/usr/bin/env python3
"""
MUTT v2.5 - Configuration Audit Logger

This module provides utilities for logging configuration changes to the
audit trail database. Required for SOX/GDPR compliance.

Usage:
    from audit_logger import log_config_change

    # Log a rule update
    audit_id = log_config_change(
        conn=db_connection,
        changed_by='admin_api_key',
        operation='UPDATE',
        table_name='alert_rules',
        record_id=42,
        old_values={'priority': 100, 'is_active': True},
        new_values={'priority': 200, 'is_active': True},
        reason='Increased priority due to production incidents',
        correlation_id='abc-123-def-456'
    )

Author: MUTT Development Team
License: MIT
Version: 2.5.0
"""

import json
import logging
from datetime import datetime
from typing import Dict, Any, Optional

logger = logging.getLogger(__name__)


class AuditLogError(Exception):
    """Raised when audit logging fails."""
    pass


def log_config_change(
    conn,
    changed_by: str,
    operation: str,
    table_name: str,
    record_id: int,
    old_values: Optional[Dict[str, Any]] = None,
    new_values: Optional[Dict[str, Any]] = None,
    reason: Optional[str] = None,
    correlation_id: Optional[str] = None
) -> int:
    """
    Log a configuration change to the audit trail.

    This function records all configuration changes to the config_audit_log
    table for compliance and auditing purposes. All changes are tracked with
    complete before/after snapshots.

    Args:
        conn: psycopg2 database connection object
        changed_by: Username, API key name, or system process identifier
                   (max 100 chars)
        operation: One of 'CREATE', 'UPDATE', or 'DELETE'
        table_name: Name of the table being modified (max 50 chars)
        record_id: Primary key ID of the record being modified
        old_values: Dictionary of values before the change (None for CREATE)
        new_values: Dictionary of values after the change (None for DELETE)
        reason: Optional human-readable reason for the change
        correlation_id: Optional correlation ID for distributed tracing

    Returns:
        int: The ID of the created audit log record

    Raises:
        AuditLogError: If the audit log insertion fails
        ValueError: If parameters are invalid

    Examples:
        # Creating a new rule
        >>> audit_id = log_config_change(
        ...     conn=db_conn,
        ...     changed_by='admin_user',
        ...     operation='CREATE',
        ...     table_name='alert_rules',
        ...     record_id=1,
        ...     new_values={'match_string': 'ERROR', 'priority': 100}
        ... )

        # Updating an existing rule
        >>> audit_id = log_config_change(
        ...     conn=db_conn,
        ...     changed_by='webui_session_alice',
        ...     operation='UPDATE',
        ...     table_name='alert_rules',
        ...     record_id=1,
        ...     old_values={'priority': 100},
        ...     new_values={'priority': 200},
        ...     reason='Increased priority for critical alerts'
        ... )

        # Deleting a rule
        >>> audit_id = log_config_change(
        ...     conn=db_conn,
        ...     changed_by='automation_service',
        ...     operation='DELETE',
        ...     table_name='alert_rules',
        ...     record_id=99,
        ...     old_values={'match_string': 'DEPRECATED', 'priority': 50}
        ... )
    """
    # Validate inputs
    if not changed_by or len(changed_by) > 100:
        raise ValueError("changed_by must be 1-100 characters")

    if operation not in ('CREATE', 'UPDATE', 'DELETE'):
        raise ValueError("operation must be one of: CREATE, UPDATE, DELETE")

    if not table_name or len(table_name) > 50:
        raise ValueError("table_name must be 1-50 characters")

    if not isinstance(record_id, int) or record_id < 1:
        raise ValueError("record_id must be a positive integer")

    # Validate operation-specific requirements
    if operation == 'CREATE' and old_values is not None:
        logger.warning(f"CREATE operation should not have old_values (record_id={record_id})")
        old_values = None

    if operation == 'DELETE' and new_values is not None:
        logger.warning(f"DELETE operation should not have new_values (record_id={record_id})")
        new_values = None

    if operation == 'UPDATE':
        if old_values is None or new_values is None:
            raise ValueError("UPDATE operation requires both old_values and new_values")

    # Convert dictionaries to JSON strings
    old_values_json = json.dumps(old_values) if old_values else None
    new_values_json = json.dumps(new_values) if new_values else None

    try:
        cursor = conn.cursor()

        # Insert audit record using parameterized query (SQL injection safe)
        cursor.execute("""
            INSERT INTO config_audit_log (
                changed_by,
                operation,
                table_name,
                record_id,
                old_values,
                new_values,
                reason,
                correlation_id
            ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s)
            RETURNING id
        """, (
            changed_by,
            operation,
            table_name,
            record_id,
            old_values_json,
            new_values_json,
            reason,
            correlation_id
        ))

        # Get the inserted audit log ID
        audit_id = cursor.fetchone()[0]

        # Commit the transaction
        conn.commit()

        logger.info(
            f"Audit log created: id={audit_id}, "
            f"operation={operation}, "
            f"table={table_name}, "
            f"record_id={record_id}, "
            f"changed_by={changed_by}"
        )

        return audit_id

    except Exception as e:
        # Rollback on error
        conn.rollback()
        logger.error(
            f"Failed to create audit log: {e}",
            exc_info=True,
            extra={
                'operation': operation,
                'table_name': table_name,
                'record_id': record_id,
                'changed_by': changed_by
            }
        )
        raise AuditLogError(f"Failed to log audit record: {e}") from e

    finally:
        cursor.close()


def get_audit_history(
    conn,
    table_name: str,
    record_id: int,
    limit: int = 100
) -> list:
    """
    Retrieve the audit history for a specific record.

    Args:
        conn: psycopg2 database connection
        table_name: Name of the table
        record_id: ID of the record
        limit: Maximum number of records to return (default: 100)

    Returns:
        list: List of audit log records (newest first), each as a dict

    Examples:
        >>> history = get_audit_history(conn, 'alert_rules', 42, limit=10)
        >>> for entry in history:
        ...     print(f"{entry['changed_at']}: {entry['operation']} by {entry['changed_by']}")
    """
    try:
        cursor = conn.cursor()

        cursor.execute("""
            SELECT
                id,
                changed_at,
                changed_by,
                operation,
                table_name,
                record_id,
                old_values,
                new_values,
                reason,
                correlation_id
            FROM config_audit_log
            WHERE table_name = %s AND record_id = %s
            ORDER BY changed_at DESC
            LIMIT %s
        """, (table_name, record_id, limit))

        columns = [desc[0] for desc in cursor.description]
        results = []

        for row in cursor.fetchall():
            record = dict(zip(columns, row))
            # Parse JSON fields
            if record['old_values']:
                record['old_values'] = json.loads(record['old_values'])
            if record['new_values']:
                record['new_values'] = json.loads(record['new_values'])
            results.append(record)

        return results

    except Exception as e:
        logger.error(f"Failed to retrieve audit history: {e}", exc_info=True)
        raise AuditLogError(f"Failed to retrieve audit history: {e}") from e

    finally:
        cursor.close()


def get_recent_changes(
    conn,
    hours: int = 24,
    limit: int = 100
) -> list:
    """
    Retrieve recent configuration changes.

    Args:
        conn: psycopg2 database connection
        hours: Number of hours to look back (default: 24)
        limit: Maximum number of records to return (default: 100)

    Returns:
        list: List of recent audit log records (newest first)

    Examples:
        >>> recent = get_recent_changes(conn, hours=1, limit=50)
        >>> print(f"Found {len(recent)} changes in the last hour")
    """
    try:
        cursor = conn.cursor()

        cursor.execute("""
            SELECT
                id,
                changed_at,
                changed_by,
                operation,
                table_name,
                record_id,
                old_values,
                new_values,
                reason,
                correlation_id
            FROM config_audit_log
            WHERE changed_at >= NOW() - INTERVAL '%s hours'
            ORDER BY changed_at DESC
            LIMIT %s
        """, (hours, limit))

        columns = [desc[0] for desc in cursor.description]
        results = []

        for row in cursor.fetchall():
            record = dict(zip(columns, row))
            # Parse JSON fields
            if record['old_values']:
                record['old_values'] = json.loads(record['old_values'])
            if record['new_values']:
                record['new_values'] = json.loads(record['new_values'])
            results.append(record)

        return results

    except Exception as e:
        logger.error(f"Failed to retrieve recent changes: {e}", exc_info=True)
        raise AuditLogError(f"Failed to retrieve recent changes: {e}") from e

    finally:
        cursor.close()


if __name__ == "__main__":
    # Example usage (requires database connection)
    print("MUTT v2.5 Audit Logger")
    print("=" * 60)
    print("\nThis module provides audit logging for configuration changes.")
    print("\nUsage:")
    print("  from audit_logger import log_config_change")
    print("\nSee module docstring for examples.")
