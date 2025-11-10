#!/usr/bin/env python3
"""
MUTT v2.5 - Data Retention Integration Tests

Integration tests for retention enforcement with actual database operations.

Run with:
    pytest tests/test_retention_integration.py -v
    pytest tests/test_retention_integration.py -v --integration
"""

import pytest
from unittest.mock import Mock, patch
from datetime import datetime, timedelta
import sys
import os

# Add directories to path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'scripts'))
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'config'))


# Skip integration tests by default (require --integration flag)
pytestmark = pytest.mark.skipif(
    '--integration' not in sys.argv,
    reason="Integration tests require --integration flag"
)


class TestRetentionConfiguration:
    """Integration tests for retention configuration"""

    def test_environment_variables_loaded_correctly(self):
        """Test that environment variables are loaded into config"""
        from environment import get_retention_config

        config = get_retention_config()

        assert 'enabled' in config
        assert 'audit_days' in config
        assert 'event_audit_days' in config
        assert 'dlq_days' in config
        assert 'batch_size' in config

        # Check types
        assert isinstance(config['enabled'], bool)
        assert isinstance(config['audit_days'], int)
        assert isinstance(config['batch_size'], int)

    def test_validation_catches_configuration_issues(self):
        """Test that validation identifies problematic configurations"""
        from environment import validate_retention_config

        with patch('environment.RETENTION_AUDIT_DAYS', 30):  # Too short
            warnings = validate_retention_config()
            assert len(warnings) > 0
            assert any('365' in w or 'year' in w for w in warnings)

    def test_database_config_returns_valid_structure(self):
        """Test that database configuration is properly structured"""
        from environment import get_database_config

        config = get_database_config()

        assert 'host' in config
        assert 'port' in config
        assert 'database' in config
        assert 'user' in config
        assert 'password' in config

        # Check types
        assert isinstance(config['port'], int)


class TestRetentionCleanupIntegration:
    """Integration tests for retention cleanup with mocked database"""

    @patch('psycopg2.connect')
    def test_main_function_connects_to_database(self, mock_connect):
        """Test that main() establishes database connection"""
        from retention_cleanup import main

        # Mock database connection
        mock_conn = Mock()
        mock_cursor = Mock()
        mock_cursor.rowcount = 0
        mock_conn.cursor.return_value = mock_cursor
        mock_connect.return_value = mock_conn

        # Mock environment to enable retention
        with patch('retention_cleanup.get_retention_config') as mock_config:
            mock_config.return_value = {
                'enabled': True,
                'dry_run': True,  # Use dry-run to avoid actual deletion
                'audit_days': 365,
                'event_audit_days': 90,
                'dlq_days': 30,
                'batch_size': 1000
            }

            with patch('retention_cleanup.get_database_config') as mock_db_config:
                mock_db_config.return_value = {
                    'host': 'localhost',
                    'port': 5432,
                    'database': 'mutt',
                    'user': 'mutt',
                    'password': 'mutt'
                }

                # Run main
                exit_code = main()

                # Should succeed
                assert exit_code == 0

                # Database connection should be established
                mock_connect.assert_called_once()

                # Connection should be closed
                mock_conn.close.assert_called_once()

    @patch('psycopg2.connect')
    def test_main_function_skips_when_disabled(self, mock_connect):
        """Test that main() skips cleanup when retention is disabled"""
        from retention_cleanup import main

        with patch('retention_cleanup.get_retention_config') as mock_config:
            mock_config.return_value = {
                'enabled': False,  # Disabled
                'dry_run': False,
                'audit_days': 365,
                'event_audit_days': 90,
                'dlq_days': 30,
                'batch_size': 1000
            }

            exit_code = main()

            # Should exit successfully without connecting to database
            assert exit_code == 0
            mock_connect.assert_not_called()

    @patch('psycopg2.connect')
    def test_main_function_handles_database_connection_error(self, mock_connect):
        """Test that main() handles database connection errors gracefully"""
        from retention_cleanup import main

        # Mock connection error
        mock_connect.side_effect = Exception("Connection refused")

        with patch('retention_cleanup.get_retention_config') as mock_config:
            mock_config.return_value = {
                'enabled': True,
                'dry_run': False,
                'audit_days': 365,
                'event_audit_days': 90,
                'dlq_days': 30,
                'batch_size': 1000
            }

            with patch('retention_cleanup.get_database_config') as mock_db_config:
                mock_db_config.return_value = {
                    'host': 'localhost',
                    'port': 5432,
                    'database': 'mutt',
                    'user': 'mutt',
                    'password': 'mutt'
                }

                # Run main - should fail gracefully
                exit_code = main()

                # Should return error code
                assert exit_code == 1


class TestRetentionMetrics:
    """Integration tests for retention metrics"""

    def test_write_metrics_creates_prometheus_file(self):
        """Test that metrics are written to Prometheus textfile"""
        from retention_cleanup import write_metrics
        import tempfile
        import os

        stats = {
            'config_audit': 100,
            'event_audit': 200,
            'dlq': 50
        }

        config = {
            'audit_days': 365,
            'event_audit_days': 90,
            'dlq_days': 30
        }

        # Use temporary directory
        with tempfile.TemporaryDirectory() as tmpdir:
            metrics_file = os.path.join(tmpdir, 'retention.prom')

            with patch.dict(os.environ, {'RETENTION_METRICS_FILE': metrics_file}):
                write_metrics(stats, config)

                # Verify file was created
                assert os.path.exists(metrics_file)

                # Verify content
                with open(metrics_file, 'r') as f:
                    content = f.read()

                # Check for expected metrics
                assert 'mutt_retention_cleanup_records_deleted_total' in content
                assert 'mutt_retention_policy_days' in content
                assert 'mutt_retention_cleanup_last_run_timestamp_seconds' in content

                # Check values
                assert 'type="config_audit"} 100' in content
                assert 'type="event_audit"} 200' in content
                assert 'type="dlq"} 50' in content

    def test_write_metrics_handles_missing_directory(self):
        """Test that write_metrics handles missing metrics directory gracefully"""
        from retention_cleanup import write_metrics

        stats = {'config_audit': 0, 'event_audit': 0, 'dlq': 0}
        config = {'audit_days': 365, 'event_audit_days': 90, 'dlq_days': 30}

        # Use non-existent directory
        with patch.dict(os.environ, {'RETENTION_METRICS_FILE': '/nonexistent/dir/metrics.prom'}):
            # Should not raise exception
            try:
                write_metrics(stats, config)
            except Exception as e:
                # If it raises, it should be a permission error, not a crash
                assert 'Permission' in str(e) or 'directory' in str(e).lower()


class TestRetentionEndToEnd:
    """End-to-end integration tests"""

    @patch('psycopg2.connect')
    def test_complete_retention_workflow(self, mock_connect):
        """Test complete retention cleanup workflow"""
        from retention_cleanup import RetentionCleanup

        # Mock database with realistic data
        mock_conn = Mock()
        mock_cursor = Mock()

        # Simulate data: 1500 old records across 2 batches
        call_count = [0]

        def execute_side_effect(*args, **kwargs):
            call_count[0] += 1
            # First call: COUNT query returns 1500
            if 'COUNT' in args[0]:
                mock_cursor.fetchone.return_value = (1500,)
            # Subsequent DELETE queries
            else:
                if call_count[0] == 2:
                    mock_cursor.rowcount = 1000  # First batch
                elif call_count[0] == 3:
                    mock_cursor.rowcount = 500   # Second batch (last)

        mock_cursor.execute.side_effect = execute_side_effect
        mock_cursor.fetchone.return_value = (1500,)
        mock_conn.cursor.return_value = mock_cursor
        mock_connect.return_value = mock_conn

        config = {
            'dry_run': False,
            'audit_days': 365,
            'event_audit_days': 90,
            'dlq_days': 30,
            'batch_size': 1000
        }

        cleanup = RetentionCleanup(mock_conn, config)

        # Run only config audit cleanup for this test
        deleted = cleanup.cleanup_config_audit_logs()

        # Should delete 1500 records in 2 batches
        assert deleted == 1500

        # Should commit twice (once per batch)
        assert mock_conn.commit.call_count >= 2


class TestRetentionCompliance:
    """Integration tests for compliance requirements"""

    def test_audit_logs_retained_for_minimum_period(self):
        """Test that audit logs are retained for at least minimum period"""
        from environment import get_retention_config

        config = get_retention_config()

        # Configuration audit logs should be retained for at least 30 days
        assert config['audit_days'] >= 30, "Audit retention period too short for compliance"

    def test_retention_can_be_disabled_for_legal_hold(self):
        """Test that retention can be disabled for legal hold scenarios"""
        with patch.dict(os.environ, {'RETENTION_ENABLED': 'false'}):
            from environment import get_retention_config

            config = get_retention_config()
            assert config['enabled'] == False

    def test_dry_run_mode_available_for_testing(self):
        """Test that dry-run mode is available for compliance testing"""
        with patch.dict(os.environ, {'RETENTION_DRY_RUN': 'true'}):
            from environment import get_retention_config

            config = get_retention_config()
            assert config['dry_run'] == True


if __name__ == '__main__':
    pytest.main([__file__, '-v', '--integration'])
