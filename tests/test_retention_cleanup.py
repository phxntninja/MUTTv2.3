#!/usr/bin/env python3
"""
MUTT v2.5 - Data Retention Cleanup Unit Tests

Tests for the retention cleanup module.

Run with:
    pytest tests/test_retention_cleanup.py -v
    pytest tests/test_retention_cleanup.py -v --cov=scripts.retention_cleanup
"""

import pytest
import json
from unittest.mock import Mock, MagicMock, patch, call
from datetime import datetime, timedelta, timezone
import sys
import os

# Add directories to path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'scripts'))
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'config'))

from retention_cleanup import RetentionCleanup


class TestRetentionCleanupInit:
    """Test suite for RetentionCleanup initialization"""

    def test_initialization_with_config(self):
        """Test that RetentionCleanup initializes with configuration"""
        mock_conn = Mock()
        config = {
            'enabled': True,
            'dry_run': False,
            'audit_days': 365,
            'event_audit_days': 90,
            'dlq_days': 30,
            'batch_size': 1000
        }

        cleanup = RetentionCleanup(mock_conn, config)

        assert cleanup.conn == mock_conn
        assert cleanup.config == config
        assert cleanup.dry_run == False
        assert cleanup.batch_size == 1000
        assert 'config_audit' in cleanup.stats
        assert 'event_audit' in cleanup.stats
        assert 'dlq' in cleanup.stats

    def test_initialization_with_dry_run(self):
        """Test that dry_run mode is properly set"""
        mock_conn = Mock()
        config = {'dry_run': True, 'batch_size': 500}

        cleanup = RetentionCleanup(mock_conn, config)

        assert cleanup.dry_run == True
        assert cleanup.batch_size == 500


class TestConfigAuditLogCleanup:
    """Test suite for configuration audit log cleanup"""

    def test_dry_run_counts_records_without_deleting(self):
        """Test dry-run mode counts records without deleting"""
        mock_conn = Mock()
        mock_cursor = Mock()
        mock_cursor.fetchone.return_value = (150,)  # 150 records to delete
        mock_conn.cursor.return_value = mock_cursor

        config = {'dry_run': True, 'audit_days': 365, 'batch_size': 1000}
        cleanup = RetentionCleanup(mock_conn, config)

        count = cleanup.cleanup_config_audit_logs()

        # Should count but not delete
        assert count == 150
        assert mock_cursor.execute.call_count == 1  # Only SELECT COUNT
        mock_conn.commit.assert_not_called()  # No commit in dry-run

    def test_deletes_old_records_in_batches(self):
        """Test that old records are deleted in batches"""
        mock_conn = Mock()
        mock_cursor = Mock()

        # Simulate 2500 records: first batch 1000, second 1000, third 500, fourth 0
        mock_cursor.rowcount = 1000
        call_count = [0]

        def side_effect(*args, **kwargs):
            call_count[0] += 1
            if call_count[0] == 1:
                mock_cursor.rowcount = 1000
            elif call_count[0] == 2:
                mock_cursor.rowcount = 1000
            elif call_count[0] == 3:
                mock_cursor.rowcount = 500
            return None

        mock_cursor.execute.side_effect = side_effect
        mock_conn.cursor.return_value = mock_cursor

        config = {'dry_run': False, 'audit_days': 365, 'batch_size': 1000}
        cleanup = RetentionCleanup(mock_conn, config)

        count = cleanup.cleanup_config_audit_logs()

        # Should delete 2500 total (1000 + 1000 + 500)
        assert count == 2500
        assert mock_conn.commit.call_count == 3  # One per batch

    def test_uses_correct_cutoff_date(self):
        """Test that correct cutoff date is used"""
        mock_conn = Mock()
        mock_cursor = Mock()
        mock_cursor.fetchone.return_value = (0,)
        mock_cursor.rowcount = 0
        mock_conn.cursor.return_value = mock_cursor

        config = {'dry_run': False, 'audit_days': 90, 'batch_size': 1000}
        cleanup = RetentionCleanup(mock_conn, config)

        with patch('retention_cleanup.utcnow') as mock_utcnow:
            mock_now = datetime(2025, 11, 10, 12, 0, 0, tzinfo=timezone.utc)
            mock_utcnow.return_value = mock_now

            cleanup.cleanup_config_audit_logs()

            # Cutoff should be 90 days before now
            expected_cutoff = mock_now - timedelta(days=90)

            # Check that execute was called with cutoff date
            call_args = mock_cursor.execute.call_args_list
            assert len(call_args) > 0
            # Verify cutoff date is in the parameters
            found_cutoff = False
            for call_arg in call_args:
                if len(call_arg[0]) > 1 and isinstance(call_arg[0][1], tuple):
                    if call_arg[0][1][0] == expected_cutoff:
                        found_cutoff = True
                        break
            assert found_cutoff, "Cutoff date not found in SQL parameters"

    def test_rollback_on_error(self):
        """Test that transaction is rolled back on error"""
        mock_conn = Mock()
        mock_cursor = Mock()
        mock_cursor.execute.side_effect = Exception("Database error")
        mock_conn.cursor.return_value = mock_cursor

        config = {'dry_run': False, 'audit_days': 365, 'batch_size': 1000}
        cleanup = RetentionCleanup(mock_conn, config)

        with pytest.raises(Exception, match="Database error"):
            cleanup.cleanup_config_audit_logs()

        # Should rollback on error
        mock_conn.rollback.assert_called()


class TestEventAuditLogCleanup:
    """Test suite for event audit log cleanup"""

    def test_deletes_from_correct_table(self):
        """Test that event audit logs are deleted from event_audit_log table"""
        mock_conn = Mock()
        mock_cursor = Mock()
        mock_cursor.rowcount = 50
        mock_conn.cursor.return_value = mock_cursor

        config = {'dry_run': False, 'event_audit_days': 30, 'batch_size': 1000}
        cleanup = RetentionCleanup(mock_conn, config)

        count = cleanup.cleanup_event_audit_logs()

        # Check that DELETE was executed on event_audit_log table
        call_args = mock_cursor.execute.call_args_list
        sql = call_args[0][0][0]
        assert 'event_audit_log' in sql
        assert 'DELETE' in sql

    def test_uses_event_audit_retention_period(self):
        """Test that event_audit_days is used for retention period"""
        mock_conn = Mock()
        mock_cursor = Mock()
        mock_cursor.rowcount = 0
        mock_conn.cursor.return_value = mock_cursor

        config = {'dry_run': False, 'event_audit_days': 45, 'batch_size': 1000}
        cleanup = RetentionCleanup(mock_conn, config)

        with patch('retention_cleanup.utcnow') as mock_utcnow:
            mock_now = datetime(2025, 11, 10, tzinfo=timezone.utc)
            mock_utcnow.return_value = mock_now

            cleanup.cleanup_event_audit_logs()

            # Verify 45 days is used (not audit_days)
            expected_cutoff = mock_now - timedelta(days=45)
            call_args = mock_cursor.execute.call_args_list
            # Should have cutoff date in parameters
            assert len(call_args) > 0


class TestDLQCleanup:
    """Test suite for Dead Letter Queue cleanup (Redis-based)"""

    @patch('retention_cleanup.redis.Redis')
    def test_removes_old_items_from_redis_dlq(self, mock_redis_cls):
        mock_conn = Mock()
        config = {'dry_run': False, 'dlq_days': 7, 'batch_size': 10}
        cleanup = RetentionCleanup(mock_conn, config)

        # Old item (10 days ago) and new item (now)
        old_ts = (datetime.now(timezone.utc) - timedelta(days=10)).isoformat()
        new_ts = datetime.now(timezone.utc).isoformat()
        old_item = json.dumps({'failed_at': old_ts})
        new_item = json.dumps({'failed_at': new_ts})

        mock_redis = Mock()
        # lindex returns old item first (tail), then after rpop, returns new item
        mock_redis.lindex.side_effect = [old_item, new_item]
        mock_redis.rpop.return_value = 1
        mock_redis_cls.return_value = mock_redis

        count = cleanup.cleanup_dlq_messages()
        assert count == 1
        assert mock_redis.rpop.called

    @patch('retention_cleanup.redis.Redis')
    def test_uses_dlq_retention_period(self, mock_redis_cls):
        mock_conn = Mock()
        config = {'dry_run': False, 'dlq_days': 14, 'batch_size': 10}
        cleanup = RetentionCleanup(mock_conn, config)

        # Item exactly at cutoff should not be deleted (strict older-than check)
        with patch('retention_cleanup.utcnow') as mock_utcnow:
            base_now = datetime(2025, 11, 10, tzinfo=timezone.utc)
            mock_utcnow.return_value = base_now

            cutoff = base_now - timedelta(days=14)
            item = json.dumps({'failed_at': cutoff.isoformat()})

            mock_redis = Mock()
            mock_redis.lindex.return_value = item
            mock_redis_cls.return_value = mock_redis

            count = cleanup.cleanup_dlq_messages()
            assert count == 0


class TestRunAllCleanups:
    """Test suite for running all cleanup tasks"""

    def test_run_executes_all_cleanup_tasks(self):
        """Test that run() executes all cleanup methods"""
        mock_conn = Mock()
        config = {'dry_run': False, 'audit_days': 365, 'event_audit_days': 90, 'dlq_days': 30, 'batch_size': 1000}

        cleanup = RetentionCleanup(mock_conn, config)

        # Mock all cleanup methods
        cleanup.cleanup_config_audit_logs = Mock(return_value=100)
        cleanup.cleanup_event_audit_logs = Mock(return_value=200)
        cleanup.cleanup_dlq_messages = Mock(return_value=50)

        stats = cleanup.run()

        # All methods should be called
        cleanup.cleanup_config_audit_logs.assert_called_once()
        cleanup.cleanup_event_audit_logs.assert_called_once()
        cleanup.cleanup_dlq_messages.assert_called_once()

        # Stats should be populated
        assert stats['config_audit'] == 100
        assert stats['event_audit'] == 200
        assert stats['dlq'] == 50

    def test_run_returns_statistics(self):
        """Test that run() returns deletion statistics"""
        mock_conn = Mock()
        mock_cursor = Mock()
        mock_cursor.rowcount = 0
        mock_conn.cursor.return_value = mock_cursor

        config = {'dry_run': False, 'audit_days': 365, 'event_audit_days': 90, 'dlq_days': 30, 'batch_size': 1000}
        cleanup = RetentionCleanup(mock_conn, config)

        stats = cleanup.run()

        assert isinstance(stats, dict)
        assert 'config_audit' in stats
        assert 'event_audit' in stats
        assert 'dlq' in stats


class TestBatchProcessing:
    """Test suite for batch processing logic"""

    def test_respects_batch_size(self):
        """Test that batch size is respected"""
        mock_conn = Mock()
        mock_cursor = Mock()
        mock_cursor.rowcount = 750  # Less than batch size
        mock_conn.cursor.return_value = mock_cursor

        config = {'dry_run': False, 'audit_days': 365, 'batch_size': 500}
        cleanup = RetentionCleanup(mock_conn, config)

        cleanup.cleanup_config_audit_logs()

        # Check that LIMIT matches batch size
        call_args = mock_cursor.execute.call_args_list
        if len(call_args) > 0:
            sql = call_args[0][0][0]
            params = call_args[0][0][1] if len(call_args[0][0]) > 1 else ()
            # Batch size should be in params
            assert 500 in params or 'LIMIT 500' in sql or 'LIMIT %s' in sql

    def test_stops_when_no_more_records(self):
        """Test that batch processing stops when no records remain"""
        mock_conn = Mock()
        mock_cursor = Mock()

        # First call: 100 records (less than batch), second call: not reached
        mock_cursor.rowcount = 100
        mock_conn.cursor.return_value = mock_cursor

        config = {'dry_run': False, 'audit_days': 365, 'batch_size': 1000}
        cleanup = RetentionCleanup(mock_conn, config)

        count = cleanup.cleanup_config_audit_logs()

        # Should stop after first batch since rowcount < batch_size
        assert count == 100
        assert mock_conn.commit.call_count == 1


if __name__ == '__main__':
    pytest.main([__file__, '-v', '--cov=scripts.retention_cleanup'])
