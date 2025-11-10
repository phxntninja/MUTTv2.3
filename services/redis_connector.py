#!/usr/bin/env python3
"""
Redis connector with dual-password fallback for zero-downtime rotation.

Provides a helper to construct and validate a ConnectionPool, first trying the
CURRENT password, then falling back to the NEXT password if needed.

Backwards-compatible: if only a single password is provided, it will be used.
"""

from typing import Optional
import logging
import redis


def get_redis_pool(
    *,
    host: str,
    port: int,
    tls_enabled: bool = True,
    ca_cert_path: Optional[str] = None,
    password_current: Optional[str] = None,
    password_next: Optional[str] = None,
    max_connections: int = 10,
    logger: Optional[logging.Logger] = None,
) -> redis.ConnectionPool:
    log = logger or logging.getLogger(__name__)

    def _build_pool(password: str) -> redis.ConnectionPool:
        kwargs = {
            'host': host,
            'port': port,
            'password': password,
            'decode_responses': True,
            'socket_connect_timeout': 5,
            'socket_keepalive': True,
            'max_connections': max_connections,
        }
        if tls_enabled:
            kwargs['ssl'] = True
            kwargs['ssl_cert_reqs'] = 'required'
            if ca_cert_path:
                kwargs['ssl_ca_certs'] = ca_cert_path
        pool = redis.ConnectionPool(**kwargs)
        client = redis.Redis(connection_pool=pool)
        client.ping()
        return pool

    last_error: Optional[Exception] = None

    if password_current:
        try:
            log.info("Attempting Redis pool with CURRENT password...")
            return _build_pool(password_current)
        except Exception as e:
            last_error = e
            log.warning(f"Redis connection with CURRENT password failed: {e}")

    if password_next:
        try:
            log.info("Attempting Redis pool with NEXT password...")
            return _build_pool(password_next)
        except Exception as e:
            last_error = e
            log.error(f"Redis connection with NEXT password failed: {e}")

    if not password_next and password_current and last_error:
        raise last_error

    raise RuntimeError("Failed to create Redis pool with provided passwords")

