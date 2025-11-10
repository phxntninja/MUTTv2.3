#!/usr/bin/env python3
"""
PostgreSQL connector with dual-password fallback for zero-downtime rotation.

Provides a helper to construct and validate a ThreadedConnectionPool, first
trying the CURRENT password, then falling back to the NEXT password if needed.

Backwards-compatible: if only a single password is provided, it will be used.
"""

from typing import Optional
import logging
import psycopg2
import psycopg2.pool


def get_postgres_pool(
    *,
    host: str,
    port: int,
    dbname: str,
    user: str,
    password_current: Optional[str] = None,
    password_next: Optional[str] = None,
    minconn: int = 1,
    maxconn: int = 5,
    sslmode: Optional[str] = None,
    sslrootcert: Optional[str] = None,
    logger: Optional[logging.Logger] = None,
) -> psycopg2.pool.ThreadedConnectionPool:
    log = logger or logging.getLogger(__name__)

    def _build_pool(password: str) -> psycopg2.pool.ThreadedConnectionPool:
        kwargs = {
            'host': host,
            'port': port,
            'dbname': dbname,
            'user': user,
            'password': password,
        }
        if sslmode:
            kwargs['sslmode'] = sslmode
        if sslrootcert:
            kwargs['sslrootcert'] = sslrootcert

        pool = psycopg2.pool.ThreadedConnectionPool(
            minconn=minconn,
            maxconn=maxconn,
            **kwargs,
        )
        # Validate a connection
        conn = pool.getconn()
        try:
            with conn.cursor() as cur:
                cur.execute('SELECT 1')
        finally:
            pool.putconn(conn)
        return pool

    last_error: Optional[Exception] = None

    # Try CURRENT first (or single password if NEXT not provided)
    if password_current:
        try:
            log.info("Attempting PostgreSQL pool with CURRENT password...")
            return _build_pool(password_current)
        except Exception as e:
            last_error = e
            log.warning(f"PostgreSQL connection with CURRENT password failed: {e}")

    # Try NEXT if provided
    if password_next:
        try:
            log.info("Attempting PostgreSQL pool with NEXT password...")
            return _build_pool(password_next)
        except Exception as e:
            last_error = e
            log.error(f"PostgreSQL connection with NEXT password failed: {e}")

    # If neither worked and a single legacy password was supplied via password_current
    if not password_next and password_current and last_error:
        raise last_error

    raise RuntimeError("Failed to create PostgreSQL pool with provided passwords")

