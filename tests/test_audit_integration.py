#!/usr/bin/env python3
"""
MUTT v2.5 - Audit Trail Integration Tests

Integration tests to verify that CRUD operations properly create audit log entries.

Run with:
    pytest tests/test_audit_integration.py -v
"""

import pytest
import json
from unittest.mock import Mock, MagicMock, patch
import sys
import os

# Add services directory to path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'services'))


class TestAuditTrailIntegration:
    """Integration tests for audit trail completeness"""

    @patch('audit_logger.log_config_change')
    def test_create_rule_generates_audit_log(self, mock_log_config):
        """Test that creating a rule generates an audit log entry"""
        from web_ui_service import create_app

        # Create app with mocked dependencies
        with patch('web_ui_service.fetch_secrets'), \
             patch('web_ui_service.create_redis_pool'), \
             patch('web_ui_service.create_postgres_pool'):

            app = create_app()
            app.config['TESTING'] = True

            # Mock DB pool
            mock_db_pool = Mock()
            mock_conn = Mock()
            mock_cursor = Mock()
            mock_cursor.fetchone.return_value = (123,)  # new rule ID
            mock_conn.cursor.return_value = mock_cursor
            mock_db_pool.getconn.return_value = mock_conn
            app.config['DB_POOL'] = mock_db_pool

            # Mock secrets for API key
            app.config['SECRETS'] = {'WEBUI_API_KEY': 'test-key'}

            client = app.test_client()

            # Create a rule
            response = client.post(
                '/api/v1/rules',
                headers={'X-API-KEY': 'test-key'},
                json={
                    'match_string': 'ERROR',
                    'match_type': 'contains',
                    'priority': 100,
                    'prod_handling': 'Page_and_ticket',
                    'dev_handling': 'Ticket_only',
                    'team_assignment': 'NETO',
                    'reason': 'Test rule creation'
                }
            )

            # Verify HTTP response
            assert response.status_code == 201

            # Verify audit log was called
            mock_log_config.assert_called_once()
            call_args = mock_log_config.call_args

            # Verify audit log parameters
            assert call_args[1]['operation'] == 'CREATE'
            assert call_args[1]['table_name'] == 'alert_rules'
            assert call_args[1]['record_id'] == 123
            assert call_args[1]['new_values']['match_string'] == 'ERROR'
            assert call_args[1]['new_values']['priority'] == 100
            assert call_args[1]['reason'] == 'Test rule creation'

    @patch('audit_logger.log_config_change')
    def test_update_rule_generates_audit_log(self, mock_log_config):
        """Test that updating a rule generates an audit log entry"""
        from web_ui_service import create_app

        with patch('web_ui_service.fetch_secrets'), \
             patch('web_ui_service.create_redis_pool'), \
             patch('web_ui_service.create_postgres_pool'):

            app = create_app()
            app.config['TESTING'] = True

            # Mock DB pool
            mock_db_pool = Mock()
            mock_conn = Mock()

            # Mock cursor factory for RealDictCursor
            mock_cursor = Mock()
            mock_cursor.fetchone.return_value = {
                'id': 42,
                'match_string': 'ERROR',
                'trap_oid': None,
                'syslog_severity': None,
                'match_type': 'contains',
                'priority': 100,
                'prod_handling': 'Page_and_ticket',
                'dev_handling': 'Ticket_only',
                'team_assignment': 'NETO',
                'is_active': True
            }
            mock_cursor.rowcount = 1

            mock_conn.cursor.return_value = mock_cursor
            mock_db_pool.getconn.return_value = mock_conn
            app.config['DB_POOL'] = mock_db_pool

            app.config['SECRETS'] = {'WEBUI_API_KEY': 'test-key'}

            client = app.test_client()

            # Update a rule
            response = client.put(
                '/api/v1/rules/42',
                headers={'X-API-KEY': 'test-key'},
                json={
                    'priority': 200,
                    'reason': 'Increased priority for critical alerts'
                }
            )

            # Verify HTTP response
            assert response.status_code == 200

            # Verify audit log was called
            mock_log_config.assert_called_once()
            call_args = mock_log_config.call_args

            # Verify audit log parameters
            assert call_args[1]['operation'] == 'UPDATE'
            assert call_args[1]['table_name'] == 'alert_rules'
            assert call_args[1]['record_id'] == 42
            assert call_args[1]['old_values']['priority'] == 100
            assert call_args[1]['new_values']['priority'] == 200
            assert call_args[1]['reason'] == 'Increased priority for critical alerts'

    @patch('audit_logger.log_config_change')
    def test_delete_rule_generates_audit_log(self, mock_log_config):
        """Test that deleting a rule generates an audit log entry"""
        from web_ui_service import create_app

        with patch('web_ui_service.fetch_secrets'), \
             patch('web_ui_service.create_redis_pool'), \
             patch('web_ui_service.create_postgres_pool'):

            app = create_app()
            app.config['TESTING'] = True

            # Mock DB pool
            mock_db_pool = Mock()
            mock_conn = Mock()

            # Mock cursor for SELECT then DELETE
            mock_cursor = Mock()
            mock_cursor.fetchone.return_value = {
                'id': 99,
                'match_string': 'DEPRECATED',
                'trap_oid': None,
                'syslog_severity': None,
                'match_type': 'contains',
                'priority': 50,
                'prod_handling': 'Ignore',
                'dev_handling': 'Ignore',
                'team_assignment': 'NONE',
                'is_active': False
            }
            mock_cursor.rowcount = 1

            mock_conn.cursor.return_value = mock_cursor
            mock_db_pool.getconn.return_value = mock_conn
            app.config['DB_POOL'] = mock_db_pool

            app.config['SECRETS'] = {'WEBUI_API_KEY': 'test-key'}

            client = app.test_client()

            # Delete a rule
            response = client.delete(
                '/api/v1/rules/99',
                headers={'X-API-KEY': 'test-key'},
                json={'reason': 'Removing deprecated rule'}
            )

            # Verify HTTP response
            assert response.status_code == 200

            # Verify audit log was called
            mock_log_config.assert_called_once()
            call_args = mock_log_config.call_args

            # Verify audit log parameters
            assert call_args[1]['operation'] == 'DELETE'
            assert call_args[1]['table_name'] == 'alert_rules'
            assert call_args[1]['record_id'] == 99
            assert call_args[1]['old_values']['match_string'] == 'DEPRECATED'
            assert call_args[1]['old_values']['priority'] == 50
            assert call_args[1]['reason'] == 'Removing deprecated rule'

    @patch('audit_logger.log_config_change')
    def test_audit_log_failure_does_not_block_operation(self, mock_log_config):
        """Test that audit log failures don't block CRUD operations"""
        from web_ui_service import create_app

        # Make audit logging raise an exception
        mock_log_config.side_effect = Exception("Audit logging failed")

        with patch('web_ui_service.fetch_secrets'), \
             patch('web_ui_service.create_redis_pool'), \
             patch('web_ui_service.create_postgres_pool'):

            app = create_app()
            app.config['TESTING'] = True

            # Mock DB pool
            mock_db_pool = Mock()
            mock_conn = Mock()
            mock_cursor = Mock()
            mock_cursor.fetchone.return_value = (456,)
            mock_conn.cursor.return_value = mock_cursor
            mock_db_pool.getconn.return_value = mock_conn
            app.config['DB_POOL'] = mock_db_pool

            app.config['SECRETS'] = {'WEBUI_API_KEY': 'test-key'}

            client = app.test_client()

            # Create a rule (should succeed despite audit log failure)
            response = client.post(
                '/api/v1/rules',
                headers={'X-API-KEY': 'test-key'},
                json={
                    'match_string': 'WARNING',
                    'priority': 50,
                    'prod_handling': 'Ticket_only',
                    'dev_handling': 'Ignore',
                    'team_assignment': 'DEV'
                }
            )

            # Operation should still succeed
            assert response.status_code == 201
            data = json.loads(response.data)
            assert data['id'] == 456

    @patch('audit_logger.query_audit_logs')
    def test_audit_api_endpoint_filtering(self, mock_query_audit):
        """Test that the /api/v1/audit endpoint properly passes filters"""
        from web_ui_service import create_app

        # Mock query_audit_logs return value
        mock_query_audit.return_value = {
            'logs': [
                {
                    'id': 1,
                    'changed_at': '2025-11-10T10:00:00',
                    'changed_by': 'webui_api:abc123',
                    'operation': 'CREATE',
                    'table_name': 'alert_rules',
                    'record_id': 1,
                    'old_values': None,
                    'new_values': {'priority': 100},
                    'reason': 'Test',
                    'correlation_id': 'xyz-789'
                }
            ],
            'pagination': {
                'page': 1,
                'limit': 50,
                'total': 1,
                'pages': 1
            }
        }

        with patch('web_ui_service.fetch_secrets'), \
             patch('web_ui_service.create_redis_pool'), \
             patch('web_ui_service.create_postgres_pool'):

            app = create_app()
            app.config['TESTING'] = True

            # Mock DB pool
            mock_db_pool = Mock()
            mock_conn = Mock()
            mock_db_pool.getconn.return_value = mock_conn
            app.config['DB_POOL'] = mock_db_pool

            app.config['SECRETS'] = {'WEBUI_API_KEY': 'test-key'}

            client = app.test_client()

            # Query audit logs with filters
            response = client.get(
                '/api/v1/audit?changed_by=webui_api&operation=CREATE&table_name=alert_rules',
                headers={'X-API-KEY': 'test-key'}
            )

            # Verify HTTP response
            assert response.status_code == 200
            data = json.loads(response.data)
            assert 'logs' in data
            assert 'pagination' in data
            assert len(data['logs']) == 1

            # Verify query function was called with correct filters
            mock_query_audit.assert_called_once()
            call_kwargs = mock_query_audit.call_args[1]
            assert call_kwargs['changed_by'] == 'webui_api'
            assert call_kwargs['operation'] == 'CREATE'
            assert call_kwargs['table_name'] == 'alert_rules'


class TestAuditTrailCompleteness:
    """Tests to verify audit trail captures all necessary information"""

    @patch('audit_logger.log_config_change')
    def test_audit_captures_correlation_id(self, mock_log_config):
        """Test that audit logs capture correlation IDs from requests"""
        from web_ui_service import create_app

        with patch('web_ui_service.fetch_secrets'), \
             patch('web_ui_service.create_redis_pool'), \
             patch('web_ui_service.create_postgres_pool'):

            app = create_app()
            app.config['TESTING'] = True

            mock_db_pool = Mock()
            mock_conn = Mock()
            mock_cursor = Mock()
            mock_cursor.fetchone.return_value = (789,)
            mock_conn.cursor.return_value = mock_cursor
            mock_db_pool.getconn.return_value = mock_conn
            app.config['DB_POOL'] = mock_db_pool

            app.config['SECRETS'] = {'WEBUI_API_KEY': 'test-key'}

            client = app.test_client()

            # Create rule with correlation ID
            response = client.post(
                '/api/v1/rules',
                headers={
                    'X-API-KEY': 'test-key',
                    'X-Correlation-ID': 'test-correlation-123'
                },
                json={
                    'match_string': 'INFO',
                    'priority': 10,
                    'prod_handling': 'Ignore',
                    'dev_handling': 'Ignore',
                    'team_assignment': 'NONE'
                }
            )

            assert response.status_code == 201

            # Verify correlation ID was passed to audit log
            call_args = mock_log_config.call_args
            assert call_args[1]['correlation_id'] == 'test-correlation-123'

    @patch('audit_logger.log_config_change')
    def test_audit_captures_api_key_info(self, mock_log_config):
        """Test that audit logs capture truncated API key for identification"""
        from web_ui_service import create_app

        with patch('web_ui_service.fetch_secrets'), \
             patch('web_ui_service.create_redis_pool'), \
             patch('web_ui_service.create_postgres_pool'):

            app = create_app()
            app.config['TESTING'] = True

            mock_db_pool = Mock()
            mock_conn = Mock()
            mock_cursor = Mock()
            mock_cursor.fetchone.return_value = (555,)
            mock_conn.cursor.return_value = mock_cursor
            mock_db_pool.getconn.return_value = mock_conn
            app.config['DB_POOL'] = mock_db_pool

            app.config['SECRETS'] = {'WEBUI_API_KEY': 'my-secret-api-key-12345'}

            client = app.test_client()

            # Create rule
            response = client.post(
                '/api/v1/rules',
                headers={'X-API-KEY': 'my-secret-api-key-12345'},
                json={
                    'match_string': 'DEBUG',
                    'priority': 1,
                    'prod_handling': 'Ignore',
                    'dev_handling': 'Ignore',
                    'team_assignment': 'NONE'
                }
            )

            assert response.status_code == 201

            # Verify API key was truncated in changed_by field
            call_args = mock_log_config.call_args
            changed_by = call_args[1]['changed_by']
            assert changed_by.startswith('webui_api:')
            # Should only include first 8 chars of API key
            assert 'my-secre' in changed_by
            assert 'api-key-12345' not in changed_by  # Rest should be truncated


if __name__ == '__main__':
    pytest.main([__file__, '-v'])
