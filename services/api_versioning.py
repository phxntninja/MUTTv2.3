#!/usr/bin/env python3
"""
MUTT v2.5 - API Versioning Module

This module provides API versioning capabilities for the MUTT Web UI service,
enabling backward compatibility and graceful deprecation of endpoints.

Features:
- Version negotiation via Accept-Version header
- Versioned endpoint decorator
- Deprecation warnings
- Automatic version headers in responses

Usage:
    from api_versioning import versioned_endpoint, get_api_version

    @versioned_endpoint(since='1.0', deprecated_in='2.0', removed_in='3.0')
    def my_endpoint():
        version = get_api_version()
        if version == '1.0':
            return legacy_response()
        return current_response()

Author: MUTT Development Team
License: MIT
Version: 2.5.0
"""

import logging
from functools import wraps
from typing import Optional, Callable, Dict, Any
from flask import jsonify, Response, make_response, request as flask_request
from datetime import datetime

logger = logging.getLogger(__name__)

# Note on request access in tests:
# We avoid binding Flask's LocalProxy `request` at import time to prevent
# evaluation outside an active request context when unit tests patch it.
# Tests may patch `api_versioning.request` directly. If present, we will use
# that object; otherwise we fall back to Flask's `flask_request`.
request = None  # type: ignore

# Current API version
CURRENT_API_VERSION = '2.5'

# Supported API versions (newest to oldest)
SUPPORTED_VERSIONS = ['2.5', '2.0', '1.0']

# Default version if client doesn't specify
DEFAULT_API_VERSION = '2.5'

# API version history and changelog
VERSION_HISTORY = {
    '2.5': {
        'released': '2025-11-10',
        'status': 'current',
        'changes': [
            'Added v2 route aliases across Web UI and Ingestor',
            'Response headers include X-API-Version and X-API-Deprecated',
            'Config change audit logging and endpoints',
            'Circuit breaker for Moog forwarder with metrics',
            'Prometheus alert rules consolidated for v2.5'
        ]
    },
    '2.0': {
        'released': '2025-11-10',
        'status': 'supported',
        'changes': [
            'Added configuration audit logging',
            'Enhanced filtering for audit logs',
            'Added /api/v1/audit endpoint',
            'Added /audit web UI viewer',
            'Normalized metric labels to status={success|fail}',
            'Added SLO monitoring endpoint',
            'Added alerter backpressure controls'
        ]
    },
    '1.0': {
        'released': '2024-01-01',
        'status': 'supported',
        'changes': [
            'Initial stable API release',
            'Basic CRUD operations for rules',
            'Event audit logs',
            'Metrics dashboard',
            'Dynamic configuration API'
        ],
        'deprecated_in': '3.0',
        'removal_date': '2026-01-01'
    }
}


def get_requested_version() -> str:
    """
    Extract the requested API version from the request.

    Checks the following sources in order:
    1. Accept-Version header
    2. X-API-Version header
    3. Query parameter 'api_version'
    4. Falls back to DEFAULT_API_VERSION

    Returns:
        str: The requested API version (e.g., '2.0')

    Examples:
        >>> # In a Flask request context
        >>> version = get_requested_version()
        >>> print(version)  # '2.0'
    """
    req = request if request is not None else flask_request  # type: ignore
    # Try Accept-Version header (preferred)
    version = req.headers.get('Accept-Version')
    if version and version in SUPPORTED_VERSIONS:
        return version

    # Try X-API-Version header (alternative)
    version = req.headers.get('X-API-Version')
    if version and version in SUPPORTED_VERSIONS:
        return version

    # Try query parameter
    version = req.args.get('api_version')
    if version and version in SUPPORTED_VERSIONS:
        return version

    # Default version
    return DEFAULT_API_VERSION


def get_api_version() -> str:
    """
    Get the negotiated API version for the current request.

    This is an alias for get_requested_version() for convenience.

    Returns:
        str: The API version for this request
    """
    return get_requested_version()


def add_version_headers(response: Response, endpoint_meta: Optional[Dict[str, Any]] = None) -> Response:
    """
    Add API version headers to a response.

    Args:
        response: Flask Response object
        endpoint_meta: Optional metadata about the endpoint (deprecation info, etc.)

    Returns:
        Response: Modified response with version headers

    Headers added:
        - X-API-Version: The current API version
        - X-API-Supported-Versions: Comma-separated list of supported versions
        - X-API-Deprecated: Warning if endpoint is deprecated (if applicable)
        - X-API-Sunset: ISO 8601 date when endpoint will be removed (if applicable)

    Examples:
        >>> response = jsonify({"data": "value"})
        >>> response = add_version_headers(response)
    """
    response.headers['X-API-Version'] = CURRENT_API_VERSION
    response.headers['X-API-Supported-Versions'] = ', '.join(SUPPORTED_VERSIONS)

    # Add deprecation warnings if applicable
    if endpoint_meta:
        if endpoint_meta.get('deprecated_in'):
            deprecation_msg = f"Deprecated in version {endpoint_meta['deprecated_in']}"
            if endpoint_meta.get('removed_in'):
                deprecation_msg += f", will be removed in {endpoint_meta['removed_in']}"
            if endpoint_meta.get('removal_date'):
                deprecation_msg += f" (removal date: {endpoint_meta['removal_date']})"
            response.headers['X-API-Deprecated'] = deprecation_msg

        if endpoint_meta.get('removal_date'):
            response.headers['X-API-Sunset'] = endpoint_meta['removal_date']

    return response


def versioned_endpoint(
    since: str = '1.0',
    deprecated_in: Optional[str] = None,
    removed_in: Optional[str] = None,
    removal_date: Optional[str] = None
) -> Callable:
    """
    Decorator to mark an endpoint with version information.

    Args:
        since: Version when this endpoint was introduced
        deprecated_in: Version when this endpoint was deprecated (optional)
        removed_in: Version when this endpoint will be removed (optional)
        removal_date: ISO 8601 date when endpoint will be removed (optional)

    Returns:
        Callable: Decorated function

    Examples:
        >>> @versioned_endpoint(since='1.0', deprecated_in='2.0', removed_in='3.0')
        >>> def old_endpoint():
        ...     return jsonify({"message": "Legacy endpoint"})

        >>> @versioned_endpoint(since='2.0')
        >>> def new_endpoint():
        ...     return jsonify({"message": "Current endpoint"})
    """
    def decorator(f: Callable) -> Callable:
        @wraps(f)
        def decorated_function(*args, **kwargs):
            requested_version = get_requested_version()

            # Store version metadata on the request for logging
            req = request if request is not None else flask_request  # type: ignore
            req.api_version = requested_version
            req.endpoint_metadata = {
                'since': since,
                'deprecated_in': deprecated_in,
                'removed_in': removed_in,
                'removal_date': removal_date
            }

            # Check if endpoint is removed in the requested version
            if removed_in and _is_version_gte(requested_version, removed_in):
                logger.warning(
                    f"Attempt to access removed endpoint: {getattr(req, 'endpoint', '<unknown>')} "
                    f"(removed in {removed_in}, requested version: {requested_version})"
                )
                response = jsonify({
                    "error": "Endpoint removed",
                    "message": f"This endpoint was removed in version {removed_in}",
                    "removed_in": removed_in,
                    "removal_date": removal_date,
                    "current_version": CURRENT_API_VERSION
                })
                response.status_code = 410  # Gone
                return add_version_headers(response, getattr(req, 'endpoint_metadata', None))

            # Log deprecation warnings
            if deprecated_in and _is_version_gte(requested_version, deprecated_in):
                logger.warning(
                    f"Deprecated endpoint accessed: {getattr(req, 'endpoint', '<unknown>')} "
                    f"(deprecated in {deprecated_in}, requested version: {requested_version})"
                )

            # Call the actual endpoint
            result = f(*args, **kwargs)

            # Add version headers to response
            if isinstance(result, Response):
                return add_version_headers(result, getattr(req, 'endpoint_metadata', None))
            elif isinstance(result, tuple):
                # Handle (response, status_code) tuples
                response = make_response(result)
                return add_version_headers(response, getattr(req, 'endpoint_metadata', None))
            else:
                response = make_response(result)
                return add_version_headers(response, getattr(req, 'endpoint_metadata', None))

        # Store metadata on the function for introspection
        decorated_function.api_version_info = {
            'since': since,
            'deprecated_in': deprecated_in,
            'removed_in': removed_in,
            'removal_date': removal_date
        }

        return decorated_function
    return decorator


def _is_version_gte(version1: str, version2: str) -> bool:
    """
    Check if version1 is greater than or equal to version2.

    Args:
        version1: First version string (e.g., '2.0')
        version2: Second version string (e.g., '1.0')

    Returns:
        bool: True if version1 >= version2

    Examples:
        >>> _is_version_gte('2.0', '1.0')
        True
        >>> _is_version_gte('1.0', '2.0')
        False
    """
    try:
        v1_parts = [int(x) for x in version1.split('.')]
        v2_parts = [int(x) for x in version2.split('.')]

        # Pad shorter version with zeros
        while len(v1_parts) < len(v2_parts):
            v1_parts.append(0)
        while len(v2_parts) < len(v1_parts):
            v2_parts.append(0)

        return v1_parts >= v2_parts
    except (ValueError, AttributeError):
        return False


def get_version_info() -> Dict[str, Any]:
    """
    Get comprehensive API version information.

    Returns:
        dict: Version information including current version, supported versions,
              and version history

    Examples:
        >>> info = get_version_info()
        >>> print(info['current_version'])  # '2.0'
        >>> print(info['supported_versions'])  # ['2.0', '1.0']
    """
    return {
        'current_version': CURRENT_API_VERSION,
        'default_version': DEFAULT_API_VERSION,
        'supported_versions': SUPPORTED_VERSIONS,
        'version_history': VERSION_HISTORY
    }


if __name__ == "__main__":
    # Example usage
    print("MUTT v2.5 API Versioning")
    print("=" * 60)
    print(f"Current API Version: {CURRENT_API_VERSION}")
    print(f"Supported Versions: {', '.join(SUPPORTED_VERSIONS)}")
    print("\nVersion History:")
    for version, info in VERSION_HISTORY.items():
        print(f"\n  Version {version} ({info['status']}):")
        print(f"    Released: {info['released']}")
        if info.get('deprecated_in'):
            print(f"    Deprecated in: {info['deprecated_in']}")
        if info.get('removal_date'):
            print(f"    Removal date: {info['removal_date']}")
