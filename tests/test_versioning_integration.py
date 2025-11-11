#!/usr/bin/env python3
"""
MUTT v2.5 - API Versioning Integration Tests

Integration tests for API versioning functionality.

Run with:
    pytest tests/test_versioning_integration.py -v
"""

import pytest
import json
from unittest.mock import Mock, patch
import sys
import os

# Add services directory to path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'services'))


class TestVersionHeadersIntegration:
    """Integration tests for version headers on API responses"""

    @patch('services.web_ui_service.fetch_secrets')
    @patch('services.web_ui_service.create_redis_pool')
    @patch('services.web_ui_service.create_postgres_pool')
    def test_api_responses_include_version_headers(self, mock_pg, mock_redis, mock_secrets):
        """Test that all API responses include version headers"""
        from services.web_ui_service import create_app

        app = create_app()
        app.config['TESTING'] = True
        app.config['SECRETS'] = {'WEBUI_API_KEY': 'test-key'}

        client = app.test_client()

        # Call version endpoint (no auth required)
        response = client.get('/api/v1/version')

        # Verify response has version headers
        assert response.status_code == 200
        assert 'X-API-Version' in response.headers
        assert 'X-API-Supported-Versions' in response.headers

    @patch('services.web_ui_service.fetch_secrets')
    @patch('services.web_ui_service.create_redis_pool')
    @patch('services.web_ui_service.create_postgres_pool')
    def test_version_endpoint_returns_comprehensive_info(self, mock_pg, mock_redis, mock_secrets):
        """Test that version endpoint returns comprehensive version info"""
        from services.web_ui_service import create_app

        app = create_app()
        app.config['TESTING'] = True

        client = app.test_client()

        response = client.get('/api/v1/version')
        assert response.status_code == 200

        data = json.loads(response.data)

        # Verify structure
        assert 'current_version' in data
        assert 'supported_versions' in data
        assert 'version_history' in data

        # Verify content
        assert isinstance(data['supported_versions'], list)
        assert len(data['supported_versions']) > 0
        assert data['current_version'] in data['supported_versions']

        # Verify version history has details
        assert isinstance(data['version_history'], dict)
        for version, info in data['version_history'].items():
            assert 'released' in info
            assert 'status' in info
            assert 'changes' in info


class TestVersionNegotiation:
    """Integration tests for version negotiation"""

    @patch('services.web_ui_service.fetch_secrets')
    @patch('services.web_ui_service.create_redis_pool')
    @patch('services.web_ui_service.create_postgres_pool')
    def test_accept_version_header_negotiation(self, mock_pg, mock_redis, mock_secrets):
        """Test version negotiation via Accept-Version header"""
        from services.web_ui_service import create_app

        app = create_app()
        app.config['TESTING'] = True

        client = app.test_client()

        # Request with specific version
        response = client.get(
            '/api/v1/version',
            headers={'Accept-Version': '2.0'}
        )

        assert response.status_code == 200
        assert response.headers.get('X-API-Version') == '2.0'

    @patch('services.web_ui_service.fetch_secrets')
    @patch('services.web_ui_service.create_redis_pool')
    @patch('services.web_ui_service.create_postgres_pool')
    def test_x_api_version_header_negotiation(self, mock_pg, mock_redis, mock_secrets):
        """Test version negotiation via X-API-Version header"""
        from services.web_ui_service import create_app

        app = create_app()
        app.config['TESTING'] = True

        client = app.test_client()

        # Request with specific version
        response = client.get(
            '/api/v1/version',
            headers={'X-API-Version': '1.0'}
        )

        assert response.status_code == 200
        # Should still report current version in header
        assert 'X-API-Version' in response.headers

    @patch('services.web_ui_service.fetch_secrets')
    @patch('services.web_ui_service.create_redis_pool')
    @patch('services.web_ui_service.create_postgres_pool')
    def test_unsupported_version_falls_back_gracefully(self, mock_pg, mock_redis, mock_secrets):
        """Test that unsupported version requests still work"""
        from services.web_ui_service import create_app

        app = create_app()
        app.config['TESTING'] = True

        client = app.test_client()

        # Request with unsupported version
        response = client.get(
            '/api/v1/version',
            headers={'Accept-Version': '99.0'}
        )

        # Should still succeed (falls back to default)
        assert response.status_code == 200


class TestVersionedEndpoints:
    """Integration tests for versioned endpoints"""

    @patch('services.web_ui_service.fetch_secrets')
    @patch('services.web_ui_service.create_redis_pool')
    @patch('services.web_ui_service.create_postgres_pool')
    def test_new_endpoint_has_version_metadata(self, mock_pg, mock_redis, mock_secrets):
        """Test that new endpoints (since 2.0) indicate their version"""
        from services.web_ui_service import create_app

        app = create_app()
        app.config['TESTING'] = True
        app.config['SECRETS'] = {'WEBUI_API_KEY': 'test-key'}

        # Mock DB pool for audit endpoint
        mock_db_pool = Mock()
        mock_conn = Mock()
        mock_cursor = Mock()
        mock_cursor.fetchone.return_value = (0,)  # No results
        mock_cursor.fetchall.return_value = []
        mock_cursor.description = [
            ('id',), ('changed_at',), ('changed_by',), ('operation',),
            ('table_name',), ('record_id',), ('old_values',), ('new_values',),
            ('reason',), ('correlation_id',)
        ]
        mock_conn.cursor.return_value = mock_cursor
        mock_db_pool.getconn.return_value = mock_conn
        app.config['DB_POOL'] = mock_db_pool

        client = app.test_client()

        # Call audit endpoint (new in 2.0)
        response = client.get(
            '/api/v1/audit',
            headers={'X-API-KEY': 'test-key'}
        )

        # Should have version headers
        assert 'X-API-Version' in response.headers


class TestBackwardCompatibility:
    """Tests for backward compatibility support"""

    @patch('services.web_ui_service.fetch_secrets')
    @patch('services.web_ui_service.create_redis_pool')
    @patch('services.web_ui_service.create_postgres_pool')
    def test_v1_requests_still_work(self, mock_pg, mock_redis, mock_secrets):
        """Test that v1 API requests still work"""
        from services.web_ui_service import create_app

        app = create_app()
        app.config['TESTING'] = True

        client = app.test_client()

        # Request version info as v1 client
        response = client.get(
            '/api/v1/version',
            headers={'Accept-Version': '1.0'}
        )

        # Should work
        assert response.status_code == 200

        data = json.loads(response.data)
        assert 'current_version' in data


class TestDeprecationWarnings:
    """Tests for deprecation warning headers"""

    def test_deprecated_endpoint_includes_warning_header(self):
        """Test that deprecated endpoints include deprecation header"""
        # Note: This would require creating a deprecated test endpoint
        # For now, we verify the versioning module can handle it
        from api_versioning import add_version_headers

        mock_response = Mock()
        mock_response.headers = {}

        endpoint_meta = {
            'deprecated_in': '2.0',
            'removed_in': '3.0',
            'removal_date': '2026-01-01'
        }

        result = add_version_headers(mock_response, endpoint_meta)

        # Verify deprecation headers
        assert 'X-API-Deprecated' in result.headers
        assert 'X-API-Sunset' in result.headers
        assert result.headers['X-API-Sunset'] == '2026-01-01'


class TestVersionDocumentation:
    """Tests for version documentation accuracy"""

    @patch('services.web_ui_service.fetch_secrets')
    @patch('services.web_ui_service.create_redis_pool')
    @patch('services.web_ui_service.create_postgres_pool')
    def test_version_history_is_complete(self, mock_pg, mock_redis, mock_secrets):
        """Test that version history includes all supported versions"""
        from services.web_ui_service import create_app

        app = create_app()
        app.config['TESTING'] = True

        client = app.test_client()

        response = client.get('/api/v1/version')
        data = json.loads(response.data)

        # All supported versions should be in history
        supported = data['supported_versions']
        history = data['version_history']

        for version in supported:
            assert version in history, f"Version {version} missing from history"

    @patch('services.web_ui_service.fetch_secrets')
    @patch('services.web_ui_service.create_redis_pool')
    @patch('services.web_ui_service.create_postgres_pool')
    def test_version_changelog_is_present(self, mock_pg, mock_redis, mock_secrets):
        """Test that each version has a changelog"""
        from services.web_ui_service import create_app

        app = create_app()
        app.config['TESTING'] = True

        client = app.test_client()

        response = client.get('/api/v1/version')
        data = json.loads(response.data)

        for version, info in data['version_history'].items():
            assert 'changes' in info, f"Version {version} missing changelog"
            assert len(info['changes']) > 0, f"Version {version} has empty changelog"


if __name__ == '__main__':
    pytest.main([__file__, '-v'])
