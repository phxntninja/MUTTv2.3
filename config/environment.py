#!/usr/bin/env python3
"""
MUTT v2.5 - Environment Configuration

Central configuration management for MUTT services using environment variables.
Includes data retention policies for compliance.

Author: MUTT Development Team
License: MIT
Version: 2.5.0
"""

import os
from typing import Optional


# =====================================================================
# DATABASE CONFIGURATION
# =====================================================================

DB_HOST = os.getenv('DB_HOST', 'localhost')
DB_PORT = int(os.getenv('DB_PORT', '5432'))
DB_NAME = os.getenv('DB_NAME', 'mutt')
DB_USER = os.getenv('DB_USER', 'mutt')
DB_PASSWORD = os.getenv('DB_PASSWORD', 'mutt')
DB_POOL_SIZE = int(os.getenv('DB_POOL_SIZE', '20'))

# =====================================================================
# REDIS CONFIGURATION
# =====================================================================

REDIS_HOST = os.getenv('REDIS_HOST', 'localhost')
REDIS_PORT = int(os.getenv('REDIS_PORT', '6379'))
REDIS_DB = int(os.getenv('REDIS_DB', '0'))
REDIS_PASSWORD = os.getenv('REDIS_PASSWORD', None)

# =====================================================================
# DATA RETENTION POLICIES (Phase 4.3)
# =====================================================================

# Audit log retention (days)
# How long to keep configuration change audit logs
RETENTION_AUDIT_DAYS = int(os.getenv('RETENTION_AUDIT_DAYS', '365'))  # 1 year default

# Event audit log retention (days)
# How long to keep event audit logs (alert processing, forwarding, etc.)
RETENTION_EVENT_AUDIT_DAYS = int(os.getenv('RETENTION_EVENT_AUDIT_DAYS', '90'))  # 90 days default

# Metrics retention (days)
# How long to keep detailed metrics in Prometheus/database
RETENTION_METRICS_DAYS = int(os.getenv('RETENTION_METRICS_DAYS', '90'))  # 90 days default

# Dead Letter Queue retention (days)
# How long to keep failed messages in DLQ before permanent deletion
RETENTION_DLQ_DAYS = int(os.getenv('RETENTION_DLQ_DAYS', '30'))  # 30 days default

# Cleanup batch size
# Number of records to delete in a single transaction (prevents long locks)
RETENTION_CLEANUP_BATCH_SIZE = int(os.getenv('RETENTION_CLEANUP_BATCH_SIZE', '1000'))

# Dry run mode
# If True, retention cleanup only logs what would be deleted without actually deleting
RETENTION_DRY_RUN = os.getenv('RETENTION_DRY_RUN', 'false').lower() == 'true'

# Enable/disable retention enforcement
RETENTION_ENABLED = os.getenv('RETENTION_ENABLED', 'true').lower() == 'true'

# =====================================================================
# SERVICE CONFIGURATION
# =====================================================================

WEBUI_PORT = int(os.getenv('WEBUI_PORT', '8090'))
WEBUI_HOST = os.getenv('WEBUI_HOST', '0.0.0.0')

ALERTER_PORT = int(os.getenv('ALERTER_PORT', '8091'))
ALERTER_HOST = os.getenv('ALERTER_HOST', '0.0.0.0')

FORWARDER_PORT = int(os.getenv('FORWARDER_PORT', '8092'))
FORWARDER_HOST = os.getenv('FORWARDER_HOST', '0.0.0.0')

# =====================================================================
# LOGGING CONFIGURATION
# =====================================================================

LOG_LEVEL = os.getenv('LOG_LEVEL', 'INFO')
LOG_FORMAT = os.getenv('LOG_FORMAT', 'json')  # json or text

# =====================================================================
# VAULT CONFIGURATION (Optional)
# =====================================================================

VAULT_ENABLED = os.getenv('VAULT_ENABLED', 'false').lower() == 'true'
VAULT_ADDR = os.getenv('VAULT_ADDR', 'http://localhost:8200')
VAULT_TOKEN = os.getenv('VAULT_TOKEN', None)
VAULT_SECRET_PATH = os.getenv('VAULT_SECRET_PATH', 'secret/data/mutt')

# =====================================================================
# HELPER FUNCTIONS
# =====================================================================

def get_retention_config() -> dict:
    """
    Get all retention policy configuration as a dictionary.

    Returns:
        dict: Retention configuration with days for each data type

    Examples:
        >>> config = get_retention_config()
        >>> print(config['audit_days'])  # 365
        >>> print(config['enabled'])  # True
    """
    return {
        'enabled': RETENTION_ENABLED,
        'dry_run': RETENTION_DRY_RUN,
        'audit_days': RETENTION_AUDIT_DAYS,
        'event_audit_days': RETENTION_EVENT_AUDIT_DAYS,
        'metrics_days': RETENTION_METRICS_DAYS,
        'dlq_days': RETENTION_DLQ_DAYS,
        'batch_size': RETENTION_CLEANUP_BATCH_SIZE
    }


def get_database_config() -> dict:
    """
    Get database configuration as a dictionary.

    Returns:
        dict: Database connection parameters

    Examples:
        >>> config = get_database_config()
        >>> print(config['host'])  # 'localhost'
    """
    return {
        'host': DB_HOST,
        'port': DB_PORT,
        'database': DB_NAME,
        'user': DB_USER,
        'password': DB_PASSWORD,
        'pool_size': DB_POOL_SIZE
    }


def get_redis_config() -> dict:
    """
    Get Redis configuration as a dictionary.

    Returns:
        dict: Redis connection parameters

    Examples:
        >>> config = get_redis_config()
        >>> print(config['host'])  # 'localhost'
    """
    config = {
        'host': REDIS_HOST,
        'port': REDIS_PORT,
        'db': REDIS_DB
    }
    if REDIS_PASSWORD:
        config['password'] = REDIS_PASSWORD
    return config


def validate_retention_config() -> list:
    """
    Validate retention configuration and return any warnings.

    Returns:
        list: List of warning messages (empty if all valid)

    Examples:
        >>> warnings = validate_retention_config()
        >>> if warnings:
        ...     for warning in warnings:
        ...         print(f"WARNING: {warning}")
    """
    warnings = []

    if RETENTION_AUDIT_DAYS < 365:
        warnings.append(
            f"Audit log retention ({RETENTION_AUDIT_DAYS} days) is less than "
            "recommended 1 year for compliance purposes"
        )

    if RETENTION_EVENT_AUDIT_DAYS < 30:
        warnings.append(
            f"Event audit retention ({RETENTION_EVENT_AUDIT_DAYS} days) is less than "
            "recommended 30 days minimum"
        )

    if RETENTION_DLQ_DAYS < 7:
        warnings.append(
            f"DLQ retention ({RETENTION_DLQ_DAYS} days) is very short. "
            "Consider at least 7 days for troubleshooting"
        )

    if RETENTION_CLEANUP_BATCH_SIZE > 10000:
        warnings.append(
            f"Cleanup batch size ({RETENTION_CLEANUP_BATCH_SIZE}) is very large. "
            "This may cause long-running transactions"
        )

    if not RETENTION_ENABLED:
        warnings.append(
            "Retention enforcement is DISABLED. Data will not be automatically cleaned up"
        )

    return warnings


if __name__ == "__main__":
    # Print current configuration
    print("MUTT v2.5 Configuration")
    print("=" * 60)

    print("\nDatabase:")
    for key, value in get_database_config().items():
        if key == 'password':
            value = '***' if value else None
        print(f"  {key}: {value}")

    print("\nRedis:")
    for key, value in get_redis_config().items():
        if key == 'password':
            value = '***' if value else None
        print(f"  {key}: {value}")

    print("\nRetention Policies:")
    for key, value in get_retention_config().items():
        print(f"  {key}: {value}")

    print("\nValidation:")
    warnings = validate_retention_config()
    if warnings:
        for warning in warnings:
            print(f"  WARNING: {warning}")
    else:
        print("  All retention policies are valid")
