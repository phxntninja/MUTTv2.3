#!/usr/bin/env python3
"""
MUTT v2.5 - API Versioning Unit Tests

Tests for the API versioning module.

Run with:
    pytest tests/test_api_versioning.py -v
    pytest tests/test_api_versioning.py -v --cov=services.api_versioning
"""

import pytest
from unittest.mock import Mock, MagicMock, patch
import sys
import os

# Add services directory to path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'services'))

from api_versioning import (
    get_requested_version,
    get_api_version,
    add_version_headers,
    versioned_endpoint,
    get_version_info,
    _is_version_gte,
    CURRENT_API_VERSION,
    SUPPORTED_VERSIONS,
    DEFAULT_API_VERSION
)


class TestGetRequestedVersion:
    """Test suite for version negotiation"""

    @patch('api_versioning.request')
    def test_version_from_accept_version_header(self, mock_request):
        """Test version from Accept-Version header"""
        mock_request.headers.get.return_value = '2.0'
        mock_request.args.get.return_value = None

        version = get_requested_version()
        assert version == '2.0'

    @patch('api_versioning.request')
    def test_version_from_x_api_version_header(self, mock_request):
        """Test version from X-API-Version header"""
        def header_get(key):
            if key == 'Accept-Version':
                return None
            if key == 'X-API-Version':
                return '1.0'
            return None

        mock_request.headers.get.side_effect = header_get
        mock_request.args.get.return_value = None

        version = get_requested_version()
        assert version == '1.0'

    @patch('api_versioning.request')
    def test_version_from_query_parameter(self, mock_request):
        """Test version from query parameter"""
        mock_request.headers.get.return_value = None
        mock_request.args.get.return_value = '2.0'

        version = get_requested_version()
        assert version == '2.0'

    @patch('api_versioning.request')
    def test_default_version_when_not_specified(self, mock_request):
        """Test default version is returned when not specified"""
        mock_request.headers.get.return_value = None
        mock_request.args.get.return_value = None

        version = get_requested_version()
        assert version == DEFAULT_API_VERSION

    @patch('api_versioning.request')
    def test_unsupported_version_falls_back_to_default(self, mock_request):
        """Test unsupported version falls back to default"""
        mock_request.headers.get.return_value = '99.0'  # Unsupported
        mock_request.args.get.return_value = None

        version = get_requested_version()
        assert version == DEFAULT_API_VERSION

    @patch('api_versioning.request')
    def test_accept_version_takes_precedence(self, mock_request):
        """Test Accept-Version header takes precedence over others"""
        def header_get(key):
            if key == 'Accept-Version':
                return '2.0'
            if key == 'X-API-Version':
                return '1.0'
            return None

        mock_request.headers.get.side_effect = header_get
        mock_request.args.get.return_value = '1.0'

        version = get_requested_version()
        assert version == '2.0'  # Accept-Version wins


class TestAddVersionHeaders:
    """Test suite for version header injection"""

    def test_adds_current_version_header(self):
        """Test that current version header is added"""
        mock_response = Mock()
        mock_response.headers = {}

        result = add_version_headers(mock_response)

        assert 'X-API-Version' in result.headers
        assert result.headers['X-API-Version'] == CURRENT_API_VERSION

    def test_adds_supported_versions_header(self):
        """Test that supported versions header is added"""
        mock_response = Mock()
        mock_response.headers = {}

        result = add_version_headers(mock_response)

        assert 'X-API-Supported-Versions' in result.headers
        assert '2.0' in result.headers['X-API-Supported-Versions']
        assert '1.0' in result.headers['X-API-Supported-Versions']

    def test_adds_deprecation_header_when_deprecated(self):
        """Test deprecation header is added for deprecated endpoints"""
        mock_response = Mock()
        mock_response.headers = {}

        endpoint_meta = {
            'deprecated_in': '2.0',
            'removed_in': '3.0'
        }

        result = add_version_headers(mock_response, endpoint_meta)

        assert 'X-API-Deprecated' in result.headers
        assert 'Deprecated in version 2.0' in result.headers['X-API-Deprecated']
        assert 'will be removed in 3.0' in result.headers['X-API-Deprecated']

    def test_adds_sunset_header_when_removal_date_specified(self):
        """Test sunset header is added when removal date is specified"""
        mock_response = Mock()
        mock_response.headers = {}

        endpoint_meta = {
            'removed_in': '3.0',
            'removal_date': '2026-01-01'
        }

        result = add_version_headers(mock_response, endpoint_meta)

        assert 'X-API-Sunset' in result.headers
        assert result.headers['X-API-Sunset'] == '2026-01-01'


class TestVersionedEndpointDecorator:
    """Test suite for versioned endpoint decorator"""

    @patch('api_versioning.request')
    @patch('api_versioning.add_version_headers')
    @patch('api_versioning.make_response')
    def test_decorator_stores_metadata(self, mock_make_response, mock_add_headers, mock_request):
        """Test decorator stores version metadata on function"""
        @versioned_endpoint(since='1.0', deprecated_in='2.0', removed_in='3.0')
        def test_func():
            return {'data': 'value'}

        assert hasattr(test_func, 'api_version_info')
        assert test_func.api_version_info['since'] == '1.0'
        assert test_func.api_version_info['deprecated_in'] == '2.0'
        assert test_func.api_version_info['removed_in'] == '3.0'

    @patch('api_versioning.request')
    @patch('api_versioning.get_requested_version')
    @patch('api_versioning.add_version_headers')
    @patch('api_versioning.make_response')
    def test_decorator_returns_410_for_removed_endpoint(
        self, mock_make_response, mock_add_headers, mock_get_version, mock_request
    ):
        """Test decorator returns 410 Gone for removed endpoints"""
        mock_get_version.return_value = '3.0'
        mock_request.endpoint = 'test_endpoint'

        # Mock response chain
        mock_response = Mock()
        mock_response.status_code = 410
        mock_add_headers.return_value = mock_response

        @versioned_endpoint(since='1.0', removed_in='3.0')
        def test_func():
            return {'data': 'value'}

        with patch('api_versioning.jsonify') as mock_jsonify:
            mock_jsonify.return_value = mock_response
            result = test_func()

            # Verify 410 response
            mock_jsonify.assert_called_once()
            call_args = mock_jsonify.call_args[0][0]
            assert call_args['error'] == 'Endpoint removed'
            assert call_args['removed_in'] == '3.0'

    @patch('api_versioning.request')
    @patch('api_versioning.get_requested_version')
    @patch('api_versioning.add_version_headers')
    @patch('api_versioning.make_response')
    def test_decorator_allows_access_to_non_removed_endpoint(
        self, mock_make_response, mock_add_headers, mock_get_version, mock_request
    ):
        """Test decorator allows access to non-removed endpoints"""
        mock_get_version.return_value = '2.0'
        mock_request.endpoint = 'test_endpoint'

        mock_response = Mock()
        mock_make_response.return_value = mock_response
        mock_add_headers.return_value = mock_response

        @versioned_endpoint(since='1.0', removed_in='3.0')
        def test_func():
            return {'data': 'value'}

        result = test_func()

        # Endpoint should execute normally
        mock_add_headers.assert_called_once()


class TestVersionComparison:
    """Test suite for version comparison"""

    def test_version_gte_with_equal_versions(self):
        """Test version comparison with equal versions"""
        assert _is_version_gte('2.0', '2.0') is True
        assert _is_version_gte('1.0', '1.0') is True

    def test_version_gte_with_greater_version(self):
        """Test version comparison with greater version"""
        assert _is_version_gte('2.0', '1.0') is True
        assert _is_version_gte('3.0', '2.0') is True

    def test_version_gte_with_lesser_version(self):
        """Test version comparison with lesser version"""
        assert _is_version_gte('1.0', '2.0') is False
        assert _is_version_gte('2.0', '3.0') is False

    def test_version_gte_with_multi_part_versions(self):
        """Test version comparison with multi-part versions"""
        assert _is_version_gte('2.1', '2.0') is True
        assert _is_version_gte('2.0.1', '2.0.0') is True
        assert _is_version_gte('2.0', '2.0.1') is False

    def test_version_gte_with_invalid_versions(self):
        """Test version comparison with invalid version strings"""
        assert _is_version_gte('invalid', '2.0') is False
        assert _is_version_gte('2.0', 'invalid') is False


class TestGetVersionInfo:
    """Test suite for version info retrieval"""

    def test_returns_current_version(self):
        """Test that version info includes current version"""
        info = get_version_info()

        assert 'current_version' in info
        assert info['current_version'] == CURRENT_API_VERSION

    def test_returns_supported_versions(self):
        """Test that version info includes supported versions"""
        info = get_version_info()

        assert 'supported_versions' in info
        assert isinstance(info['supported_versions'], list)
        assert len(info['supported_versions']) > 0

    def test_returns_version_history(self):
        """Test that version info includes version history"""
        info = get_version_info()

        assert 'version_history' in info
        assert isinstance(info['version_history'], dict)
        assert '2.0' in info['version_history']
        assert '1.0' in info['version_history']

    def test_version_history_includes_metadata(self):
        """Test that version history includes changelog and status"""
        info = get_version_info()

        v2_info = info['version_history']['2.0']
        assert 'released' in v2_info
        assert 'status' in v2_info
        assert 'changes' in v2_info
        assert isinstance(v2_info['changes'], list)


if __name__ == '__main__':
    pytest.main([__file__, '-v', '--cov=services.api_versioning'])
