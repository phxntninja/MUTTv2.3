#!/usr/bin/env python3
"""
MUTT v2.5 - Audit Logger Unit Tests

Tests for the audit logging module.

Run with:
    pytest tests/test_audit_logger.py -v
    pytest tests/test_audit_logger.py -v --cov=services.audit_logger
"""

import json
import pytest
from unittest.mock import Mock, MagicMock, patch
import sys
import os

# Add services directory to path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'services'))

from audit_logger import (
    log_config_change,
    get_audit_history,
    get_recent_changes,
    query_audit_logs,
    AuditLogError
)


class TestLogConfigChange:
    """Test suite for log_config_change function"""

    def test_log_create_operation_success(self):
        """Test logging a CREATE operation"""
        # Mock database connection and cursor
        mock_conn = Mock()
        mock_cursor = Mock()
        mock_cursor.fetchone.return_value = (123,)  # audit_id
        mock_conn.cursor.return_value = mock_cursor

        # Call the function
        audit_id = log_config_change(
            conn=mock_conn,
            changed_by='admin_user',
            operation='CREATE',
            table_name='alert_rules',
            record_id=1,
            new_values={'match_string': 'ERROR', 'priority': 100}
        )

        # Assertions
        assert audit_id == 123
        mock_cursor.execute.assert_called_once()
        mock_conn.commit.assert_called_once()
        mock_cursor.close.assert_called_once()

        # Verify SQL parameters
        call_args = mock_cursor.execute.call_args
        sql = call_args[0][0]
        params = call_args[0][1]

        assert 'INSERT INTO config_audit_log' in sql
        assert params[0] == 'admin_user'  # changed_by
        assert params[1] == 'CREATE'  # operation
        assert params[2] == 'alert_rules'  # table_name
        assert params[3] == 1  # record_id
        assert params[4] is None  # old_values (None for CREATE)
        assert json.loads(params[5]) == {'match_string': 'ERROR', 'priority': 100}  # new_values

    def test_log_update_operation_success(self):
        """Test logging an UPDATE operation"""
        mock_conn = Mock()
        mock_cursor = Mock()
        mock_cursor.fetchone.return_value = (456,)
        mock_conn.cursor.return_value = mock_cursor

        old_vals = {'priority': 100, 'is_active': True}
        new_vals = {'priority': 200, 'is_active': True}

        audit_id = log_config_change(
            conn=mock_conn,
            changed_by='webui_alice',
            operation='UPDATE',
            table_name='alert_rules',
            record_id=42,
            old_values=old_vals,
            new_values=new_vals,
            reason='Increased priority',
            correlation_id='abc-123'
        )

        assert audit_id == 456
        mock_conn.commit.assert_called_once()

        # Verify parameters
        params = mock_cursor.execute.call_args[0][1]
        assert params[0] == 'webui_alice'
        assert params[1] == 'UPDATE'
        assert params[3] == 42
        assert json.loads(params[4]) == old_vals
        assert json.loads(params[5]) == new_vals
        assert params[6] == 'Increased priority'
        assert params[7] == 'abc-123'

    def test_log_delete_operation_success(self):
        """Test logging a DELETE operation"""
        mock_conn = Mock()
        mock_cursor = Mock()
        mock_cursor.fetchone.return_value = (789,)
        mock_conn.cursor.return_value = mock_cursor

        audit_id = log_config_change(
            conn=mock_conn,
            changed_by='automation',
            operation='DELETE',
            table_name='alert_rules',
            record_id=99,
            old_values={'match_string': 'DEPRECATED', 'priority': 50}
        )

        assert audit_id == 789
        mock_conn.commit.assert_called_once()

        # Verify parameters
        params = mock_cursor.execute.call_args[0][1]
        assert params[1] == 'DELETE'
        assert params[4] is not None  # old_values should be present
        assert params[5] is None  # new_values should be None for DELETE

    def test_invalid_operation_raises_error(self):
        """Test that invalid operation raises ValueError"""
        mock_conn = Mock()

        with pytest.raises(ValueError, match="operation must be one of"):
            log_config_change(
                conn=mock_conn,
                changed_by='user',
                operation='INVALID',
                table_name='alert_rules',
                record_id=1
            )

    def test_invalid_changed_by_raises_error(self):
        """Test that invalid changed_by raises ValueError"""
        mock_conn = Mock()

        # Empty changed_by
        with pytest.raises(ValueError, match="changed_by must be"):
            log_config_change(
                conn=mock_conn,
                changed_by='',
                operation='CREATE',
                table_name='alert_rules',
                record_id=1
            )

        # Too long changed_by
        with pytest.raises(ValueError, match="changed_by must be"):
            log_config_change(
                conn=mock_conn,
                changed_by='x' * 101,  # 101 chars (max is 100)
                operation='CREATE',
                table_name='alert_rules',
                record_id=1
            )

    def test_invalid_table_name_raises_error(self):
        """Test that invalid table_name raises ValueError"""
        mock_conn = Mock()

        with pytest.raises(ValueError, match="table_name must be"):
            log_config_change(
                conn=mock_conn,
                changed_by='user',
                operation='CREATE',
                table_name='',  # Empty
                record_id=1
            )

    def test_invalid_record_id_raises_error(self):
        """Test that invalid record_id raises ValueError"""
        mock_conn = Mock()

        with pytest.raises(ValueError, match="record_id must be"):
            log_config_change(
                conn=mock_conn,
                changed_by='user',
                operation='CREATE',
                table_name='alert_rules',
                record_id=0  # Must be positive
            )

    def test_update_requires_both_old_and_new_values(self):
        """Test that UPDATE operation requires both old and new values"""
        mock_conn = Mock()

        # Missing old_values
        with pytest.raises(ValueError, match="UPDATE operation requires both"):
            log_config_change(
                conn=mock_conn,
                changed_by='user',
                operation='UPDATE',
                table_name='alert_rules',
                record_id=1,
                new_values={'priority': 100}
            )

        # Missing new_values
        with pytest.raises(ValueError, match="UPDATE operation requires both"):
            log_config_change(
                conn=mock_conn,
                changed_by='user',
                operation='UPDATE',
                table_name='alert_rules',
                record_id=1,
                old_values={'priority': 50}
            )

    def test_database_error_triggers_rollback(self):
        """Test that database errors trigger rollback"""
        mock_conn = Mock()
        mock_cursor = Mock()
        mock_cursor.execute.side_effect = Exception("Database error")
        mock_conn.cursor.return_value = mock_cursor

        with pytest.raises(AuditLogError, match="Failed to log audit record"):
            log_config_change(
                conn=mock_conn,
                changed_by='user',
                operation='CREATE',
                table_name='alert_rules',
                record_id=1,
                new_values={'priority': 100}
            )

        # Verify rollback was called
        mock_conn.rollback.assert_called_once()

    def test_correlation_id_is_optional(self):
        """Test that correlation_id is optional"""
        mock_conn = Mock()
        mock_cursor = Mock()
        mock_cursor.fetchone.return_value = (999,)
        mock_conn.cursor.return_value = mock_cursor

        # Without correlation_id
        audit_id = log_config_change(
            conn=mock_conn,
            changed_by='user',
            operation='CREATE',
            table_name='alert_rules',
            record_id=1,
            new_values={'priority': 100}
        )

        assert audit_id == 999

        # Verify correlation_id is None
        params = mock_cursor.execute.call_args[0][1]
        assert params[7] is None  # correlation_id

    def test_reason_is_optional(self):
        """Test that reason is optional"""
        mock_conn = Mock()
        mock_cursor = Mock()
        mock_cursor.fetchone.return_value = (888,)
        mock_conn.cursor.return_value = mock_cursor

        audit_id = log_config_change(
            conn=mock_conn,
            changed_by='user',
            operation='CREATE',
            table_name='alert_rules',
            record_id=1,
            new_values={'priority': 100}
        )

        assert audit_id == 888

        # Verify reason is None
        params = mock_cursor.execute.call_args[0][1]
        assert params[6] is None  # reason


class TestGetAuditHistory:
    """Test suite for get_audit_history function"""

    def test_get_audit_history_success(self):
        """Test retrieving audit history for a record"""
        mock_conn = Mock()
        mock_cursor = Mock()

        # Mock cursor description
        mock_cursor.description = [
            ('id',), ('changed_at',), ('changed_by',), ('operation',),
            ('table_name',), ('record_id',), ('old_values',), ('new_values',),
            ('reason',), ('correlation_id',)
        ]

        # Mock fetchall results
        mock_cursor.fetchall.return_value = [
            (1, '2025-11-09', 'user1', 'UPDATE', 'alert_rules', 42,
             '{"priority": 100}', '{"priority": 200}', 'test', 'abc-123'),
            (2, '2025-11-08', 'user2', 'CREATE', 'alert_rules', 42,
             None, '{"priority": 100}', 'initial', 'def-456')
        ]

        mock_conn.cursor.return_value = mock_cursor

        # Call function
        history = get_audit_history(mock_conn, 'alert_rules', 42, limit=10)

        # Assertions
        assert len(history) == 2
        assert history[0]['id'] == 1
        assert history[0]['operation'] == 'UPDATE'
        assert history[0]['old_values'] == {'priority': 100}
        assert history[0]['new_values'] == {'priority': 200}
        assert history[1]['id'] == 2
        assert history[1]['old_values'] is None

        mock_cursor.close.assert_called_once()


class TestGetRecentChanges:
    """Test suite for get_recent_changes function"""

    def test_get_recent_changes_success(self):
        """Test retrieving recent configuration changes"""
        mock_conn = Mock()
        mock_cursor = Mock()

        mock_cursor.description = [
            ('id',), ('changed_at',), ('changed_by',), ('operation',),
            ('table_name',), ('record_id',), ('old_values',), ('new_values',),
            ('reason',), ('correlation_id',)
        ]

        mock_cursor.fetchall.return_value = [
            (1, '2025-11-09', 'user1', 'UPDATE', 'alert_rules', 1,
             '{"priority": 100}', '{"priority": 200}', 'test', 'abc-123')
        ]

        mock_conn.cursor.return_value = mock_cursor

        # Call function
        recent = get_recent_changes(mock_conn, hours=24, limit=100)

        # Assertions
        assert len(recent) == 1
        assert recent[0]['operation'] == 'UPDATE'
        assert recent[0]['old_values'] == {'priority': 100}

        mock_cursor.close.assert_called_once()


class TestQueryAuditLogs:
    """Test suite for query_audit_logs function"""

    def test_query_all_logs_success(self):
        """Test querying all audit logs without filters"""
        mock_conn = Mock()
        mock_cursor = Mock()

        # Mock cursor description
        mock_cursor.description = [
            ('id',), ('changed_at',), ('changed_by',), ('operation',),
            ('table_name',), ('record_id',), ('old_values',), ('new_values',),
            ('reason',), ('correlation_id',)
        ]

        # Mock count and data queries
        mock_cursor.fetchone.return_value = (100,)  # total count
        mock_cursor.fetchall.return_value = [
            (1, '2025-11-10', 'user1', 'CREATE', 'alert_rules', 1,
             None, '{"priority": 100}', 'Created', 'abc-123'),
            (2, '2025-11-09', 'user2', 'UPDATE', 'alert_rules', 2,
             '{"priority": 100}', '{"priority": 200}', 'Updated', 'def-456')
        ]

        mock_conn.cursor.return_value = mock_cursor

        # Call function
        result = query_audit_logs(mock_conn, page=1, limit=50)

        # Assertions
        assert 'logs' in result
        assert 'pagination' in result
        assert len(result['logs']) == 2
        assert result['pagination']['total'] == 100
        assert result['pagination']['page'] == 1
        assert result['pagination']['limit'] == 50
        assert result['pagination']['pages'] == 2

        # Verify SQL was called twice (count + data)
        assert mock_cursor.execute.call_count == 2

        mock_cursor.close.assert_called_once()

    def test_query_with_changed_by_filter(self):
        """Test querying logs filtered by user"""
        mock_conn = Mock()
        mock_cursor = Mock()

        mock_cursor.description = [
            ('id',), ('changed_at',), ('changed_by',), ('operation',),
            ('table_name',), ('record_id',), ('old_values',), ('new_values',),
            ('reason',), ('correlation_id',)
        ]

        mock_cursor.fetchone.return_value = (5,)
        mock_cursor.fetchall.return_value = [
            (1, '2025-11-10', 'webui_api:abc123', 'CREATE', 'alert_rules', 1,
             None, '{"priority": 100}', None, 'xyz-789')
        ]

        mock_conn.cursor.return_value = mock_cursor

        # Call with filter
        result = query_audit_logs(mock_conn, changed_by='webui_api')

        # Assertions
        assert len(result['logs']) == 1
        assert result['pagination']['total'] == 5

        # Verify filter was applied in SQL (ILIKE pattern)
        call_args = mock_cursor.execute.call_args_list
        # Check that ILIKE was used for changed_by
        assert any('%webui_api%' in str(args) for args, _ in call_args)

    def test_query_with_operation_filter(self):
        """Test querying logs filtered by operation type"""
        mock_conn = Mock()
        mock_cursor = Mock()

        mock_cursor.description = [
            ('id',), ('changed_at',), ('changed_by',), ('operation',),
            ('table_name',), ('record_id',), ('old_values',), ('new_values',),
            ('reason',), ('correlation_id',)
        ]

        mock_cursor.fetchone.return_value = (10,)
        mock_cursor.fetchall.return_value = []

        mock_conn.cursor.return_value = mock_cursor

        # Call with operation filter
        result = query_audit_logs(mock_conn, operation='DELETE')

        # Verify operation filter in params
        call_args = mock_cursor.execute.call_args_list
        assert any('DELETE' in str(args) for args, _ in call_args)

    def test_query_with_table_and_record_id_filter(self):
        """Test querying logs for a specific table and record"""
        mock_conn = Mock()
        mock_cursor = Mock()

        mock_cursor.description = [
            ('id',), ('changed_at',), ('changed_by',), ('operation',),
            ('table_name',), ('record_id',), ('old_values',), ('new_values',),
            ('reason',), ('correlation_id',)
        ]

        mock_cursor.fetchone.return_value = (3,)
        mock_cursor.fetchall.return_value = []

        mock_conn.cursor.return_value = mock_cursor

        # Call with table and record_id filters
        result = query_audit_logs(
            mock_conn,
            table_name='alert_rules',
            record_id=42
        )

        # Verify filters
        call_args = mock_cursor.execute.call_args_list
        # Should have both filters in parameters
        params_found = False
        for args, _ in call_args:
            if len(args) > 1 and isinstance(args[1], (list, tuple)):
                if 'alert_rules' in args[1] and 42 in args[1]:
                    params_found = True
                    break
        assert params_found

    def test_query_with_date_range_filter(self):
        """Test querying logs with date range"""
        mock_conn = Mock()
        mock_cursor = Mock()

        mock_cursor.description = [
            ('id',), ('changed_at',), ('changed_by',), ('operation',),
            ('table_name',), ('record_id',), ('old_values',), ('new_values',),
            ('reason',), ('correlation_id',)
        ]

        mock_cursor.fetchone.return_value = (20,)
        mock_cursor.fetchall.return_value = []

        mock_conn.cursor.return_value = mock_cursor

        # Call with date range
        result = query_audit_logs(
            mock_conn,
            start_date='2025-11-01',
            end_date='2025-11-10'
        )

        # Verify date filters were applied
        call_args = mock_cursor.execute.call_args_list
        params_found = False
        for args, _ in call_args:
            if len(args) > 1 and isinstance(args[1], (list, tuple)):
                if '2025-11-01' in args[1] and '2025-11-10' in args[1]:
                    params_found = True
                    break
        assert params_found

    def test_query_with_pagination(self):
        """Test pagination parameters"""
        mock_conn = Mock()
        mock_cursor = Mock()

        mock_cursor.description = [
            ('id',), ('changed_at',), ('changed_by',), ('operation',),
            ('table_name',), ('record_id',), ('old_values',), ('new_values',),
            ('reason',), ('correlation_id',)
        ]

        mock_cursor.fetchone.return_value = (150,)
        mock_cursor.fetchall.return_value = []

        mock_conn.cursor.return_value = mock_cursor

        # Call with page 3, limit 25
        result = query_audit_logs(mock_conn, page=3, limit=25)

        # Verify pagination
        assert result['pagination']['page'] == 3
        assert result['pagination']['limit'] == 25
        assert result['pagination']['total'] == 150
        assert result['pagination']['pages'] == 6  # 150 / 25 = 6

        # Verify offset calculation (page 3 = offset 50)
        call_args = mock_cursor.execute.call_args_list
        # Data query should have LIMIT 25 OFFSET 50
        last_call_params = call_args[-1][0][1]
        assert 25 in last_call_params
        assert 50 in last_call_params

    def test_query_limit_validation(self):
        """Test that limit is capped at 200"""
        mock_conn = Mock()
        mock_cursor = Mock()

        mock_cursor.description = [
            ('id',), ('changed_at',), ('changed_by',), ('operation',),
            ('table_name',), ('record_id',), ('old_values',), ('new_values',),
            ('reason',), ('correlation_id',)
        ]

        mock_cursor.fetchone.return_value = (1000,)
        mock_cursor.fetchall.return_value = []

        mock_conn.cursor.return_value = mock_cursor

        # Try to request 500 items (should be capped at 200)
        result = query_audit_logs(mock_conn, limit=500)

        assert result['pagination']['limit'] == 200

    def test_query_invalid_operation_raises_error(self):
        """Test that invalid operation raises ValueError"""
        mock_conn = Mock()

        with pytest.raises(ValueError, match="operation must be one of"):
            query_audit_logs(mock_conn, operation='INVALID')

    def test_query_database_error(self):
        """Test handling of database errors"""
        mock_conn = Mock()
        mock_cursor = Mock()
        mock_cursor.execute.side_effect = Exception("Database error")
        mock_conn.cursor.return_value = mock_cursor

        with pytest.raises(AuditLogError, match="Failed to query audit logs"):
            query_audit_logs(mock_conn)

        mock_cursor.close.assert_called_once()

    def test_query_json_parsing(self):
        """Test that JSON fields are properly parsed"""
        mock_conn = Mock()
        mock_cursor = Mock()

        mock_cursor.description = [
            ('id',), ('changed_at',), ('changed_by',), ('operation',),
            ('table_name',), ('record_id',), ('old_values',), ('new_values',),
            ('reason',), ('correlation_id',)
        ]

        mock_cursor.fetchone.return_value = (1,)
        mock_cursor.fetchall.return_value = [
            (1, '2025-11-10', 'user1', 'UPDATE', 'alert_rules', 1,
             '{"priority": 100, "is_active": true}',
             '{"priority": 200, "is_active": false}',
             'test', 'abc-123')
        ]

        mock_conn.cursor.return_value = mock_cursor

        result = query_audit_logs(mock_conn)

        # Verify JSON was parsed
        assert isinstance(result['logs'][0]['old_values'], dict)
        assert isinstance(result['logs'][0]['new_values'], dict)
        assert result['logs'][0]['old_values']['priority'] == 100
        assert result['logs'][0]['new_values']['priority'] == 200


if __name__ == '__main__':
    pytest.main([__file__, '-v', '--cov=services.audit_logger'])
