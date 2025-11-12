#!/usr/bin/env python3
"""
MUTT v2.5 - Initialize Default Configurations in Redis

This script initializes default configuration values in Redis for the
DynamicConfig system. It should be run once during initial deployment
or after Redis is wiped.

Features:
- Sets sensible defaults for all dynamically configurable values
- Idempotent: safe to run multiple times
- Reports what was set/updated
- Can be used for config reset

Usage:
    python scripts/init_default_configs.py

Author: MUTT Development Team
License: MIT
Version: 2.5.0
"""

import os
import sys
import redis
import logging
from typing import Dict, Any

# Add parent directory to path for imports
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from services.dynamic_config import DynamicConfig

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# =====================================================================
# DEFAULT CONFIGURATION VALUES
# =====================================================================

DEFAULT_CONFIGS: Dict[str, Dict[str, Any]] = {
    # ================================================================
    # Ingestor Service Configuration
    # ================================================================
    "ingestor": {
        "max_ingest_queue_size": {
            "value": "1000000",
            "description": "Maximum size of the ingestion queue before backpressure"
        },
        "ingest_max_rate": {
            "value": "1000",
            "description": "Maximum requests per window for rate limiting"
        },
        "ingest_rate_window": {
            "value": "60",
            "description": "Rate limit window in seconds"
        }
    },

    # ================================================================
    # Alerter Service Configuration
    # ================================================================
    "alerter": {
        "cache_reload_interval": {
            "value": "300",
            "description": "Cache reload interval in seconds (5 minutes)"
        },
        "unhandled_threshold": {
            "value": "100",
            "description": "Number of unhandled events before meta-alert"
        },
        "unhandled_expiry_seconds": {
            "value": "86400",
            "description": "Expiry for unhandled event counters (24 hours)"
        },
        "alerter_queue_warn_threshold": {
            "value": "1000",
            "description": "Queue depth to trigger warning logs"
        },
        "alerter_queue_shed_threshold": {
            "value": "2000",
            "description": "Queue depth to start load shedding"
        },
        "alerter_shed_mode": {
            "value": "dlq",
            "description": "Load shedding mode: dlq (dead letter queue) or defer"
        },
        "alerter_defer_sleep_ms": {
            "value": "250",
            "description": "Sleep duration in ms when using defer mode"
        }
    },

    # ================================================================
    # Moog Forwarder Service Configuration
    # ================================================================
    "moog_forwarder": {
        "moog_rate_limit": {
            "value": "100",
            "description": "Maximum requests to Moogsoft API per period"
        },
        "moog_rate_period": {
            "value": "60",
            "description": "Rate limit period in seconds"
        },
        "circuit_breaker_threshold": {
            "value": "10",
            "description": "Consecutive failures before circuit opens"
        },
        "circuit_breaker_timeout": {
            "value": "300",
            "description": "Seconds to wait before attempting recovery"
        }
    },

    # ================================================================
    # SLO Configuration
    # ================================================================
    "slo": {
        # Ingestor Availability SLO
        "slo_ingestor_availability_window_hours": {
            "value": "24",
            "description": "Time window for ingestor availability SLO"
        },
        "slo_ingestor_availability_burn_rate_warning": {
            "value": "5.0",
            "description": "Burn rate multiplier for warning alerts"
        },
        "slo_ingestor_availability_burn_rate_critical": {
            "value": "10.0",
            "description": "Burn rate multiplier for critical alerts"
        },

        # Ingestor Latency SLO
        "slo_ingestor_latency_p99_window_hours": {
            "value": "24",
            "description": "Time window for ingestor latency SLO"
        },
        "slo_ingestor_latency_p99_upper_bound_warning": {
            "value": "0.75",
            "description": "P99 latency warning threshold in seconds"
        },
        "slo_ingestor_latency_p99_upper_bound_critical": {
            "value": "1.0",
            "description": "P99 latency critical threshold in seconds"
        },

        # Forwarder Availability SLO
        "slo_forwarder_availability_window_hours": {
            "value": "24",
            "description": "Time window for forwarder availability SLO"
        },
        "slo_forwarder_availability_burn_rate_warning": {
            "value": "5.0",
            "description": "Burn rate multiplier for warning alerts"
        },
        "slo_forwarder_availability_burn_rate_critical": {
            "value": "10.0",
            "description": "Burn rate multiplier for critical alerts"
        },

        # Forwarder Latency SLO
        "slo_forwarder_latency_p99_window_hours": {
            "value": "24",
            "description": "Time window for forwarder latency SLO"
        },
        "slo_forwarder_latency_p99_upper_bound_warning": {
            "value": "3.0",
            "description": "P99 latency warning threshold in seconds"
        },
        "slo_forwarder_latency_p99_upper_bound_critical": {
            "value": "5.0",
            "description": "P99 latency critical threshold in seconds"
        },

        # Alerter Processing SLO
        "slo_alerter_processing_success_window_hours": {
            "value": "24",
            "description": "Time window for alerter processing SLO"
        },
        "slo_alerter_processing_success_burn_rate_warning": {
            "value": "5.0",
            "description": "Burn rate multiplier for warning alerts"
        },
        "slo_alerter_processing_success_burn_rate_critical": {
            "value": "10.0",
            "description": "Burn rate multiplier for critical alerts"
        },

        # Alerter Cache Reload SLO
        "slo_alerter_cache_reload_success_window_hours": {
            "value": "24",
            "description": "Time window for cache reload SLO"
        },
        "slo_alerter_cache_reload_success_burn_rate_warning": {
            "value": "5.0",
            "description": "Burn rate multiplier for warning alerts"
        },
        "slo_alerter_cache_reload_success_burn_rate_critical": {
            "value": "10.0",
            "description": "Burn rate multiplier for critical alerts"
        }
    },

    # ================================================================
    # Data Retention & Compliance Configuration (Phase 4.3)
    # ================================================================
    "retention": {
        "event_retention_days": {
            "value": "90",
            "description": "Days to retain events in active storage before archival"
        },
        "event_archive_retention_years": {
            "value": "7",
            "description": "Years to retain archived events for compliance (SOX/GDPR)"
        },
        "config_audit_retention_days": {
            "value": "365",
            "description": "Days to retain configuration audit logs (1 year)"
        },
        "metrics_retention_days": {
            "value": "30",
            "description": "Days to retain detailed Prometheus metrics"
        },
        "log_retention_days": {
            "value": "30",
            "description": "Days to retain application logs"
        },
        "retention_enforcement_enabled": {
            "value": "true",
            "description": "Enable automatic retention policy enforcement"
        },
        "retention_check_interval_hours": {
            "value": "24",
            "description": "Hours between retention policy enforcement runs"
        }
    }
}


def get_redis_connection() -> redis.Redis:
    """
    Create Redis connection using environment variables.

    Returns:
        Redis client instance

    Raises:
        ConnectionError: If unable to connect to Redis
    """
    redis_host = os.environ.get('REDIS_HOST', 'localhost')
    redis_port = int(os.environ.get('REDIS_PORT', 6379))
    redis_tls = os.environ.get('REDIS_TLS_ENABLED', 'false').lower() == 'true'

    logger.info(f"Connecting to Redis at {redis_host}:{redis_port} (TLS: {redis_tls})")

    try:
        if redis_tls:
            # For TLS, we'd need password from Vault, so for now just warn
            logger.warning(
                "TLS is enabled but this script doesn't integrate with Vault. "
                "Either disable TLS temporarily or provide REDIS_PASSWORD env var."
            )
            redis_password = os.environ.get('REDIS_PASSWORD')
            r = redis.Redis(
                host=redis_host,
                port=redis_port,
                ssl=True,
                password=redis_password,
                decode_responses=False
            )
        else:
            r = redis.Redis(
                host=redis_host,
                port=redis_port,
                decode_responses=False
            )

        # Test connection
        r.ping()
        logger.info("Successfully connected to Redis")
        return r

    except Exception as e:
        logger.error(f"Failed to connect to Redis: {e}")
        raise ConnectionError(f"Redis connection failed: {e}") from e


def initialize_configs(redis_client: redis.Redis, force: bool = False) -> Dict[str, int]:
    """
    Initialize default configurations in Redis.

    Args:
        redis_client: Redis client instance
        force: If True, overwrite existing values. If False, only set missing keys.

    Returns:
        Dictionary with counts: {set: int, skipped: int, total: int}
    """
    config = DynamicConfig(redis_client, prefix="mutt:config")
    stats = {"set": 0, "skipped": 0, "total": 0}

    logger.info("=" * 70)
    logger.info("Initializing MUTT Default Configurations")
    logger.info("=" * 70)
    logger.info(f"Mode: {'FORCE (overwrite existing)' if force else 'SAFE (skip existing)'}")
    logger.info("")

    # Iterate through all categories and configs
    for category, configs in DEFAULT_CONFIGS.items():
        logger.info(f"\n[{category.upper()}]")

        for key, meta in configs.items():
            stats["total"] += 1
            value = meta["value"]
            description = meta["description"]

            # Check if key already exists
            try:
                existing_value = config.get(key, default=None)
            except KeyError:
                existing_value = None

            if existing_value is not None and not force:
                logger.info(
                    f"  ✓ {key} = {existing_value} (already set, skipping)"
                )
                stats["skipped"] += 1
            else:
                # Set the value
                config.set(key, value, notify=False)  # Don't notify on init
                action = "OVERWRITTEN" if existing_value else "SET"
                logger.info(
                    f"  ✓ {key} = {value} ({action})"
                )
                logger.info(f"    └─ {description}")
                stats["set"] += 1

    logger.info("")
    logger.info("=" * 70)
    logger.info("Initialization Complete")
    logger.info("=" * 70)
    logger.info(f"Total configs: {stats['total']}")
    logger.info(f"Set/Updated:   {stats['set']}")
    logger.info(f"Skipped:       {stats['skipped']}")
    logger.info("")

    return stats


def main():
    """Main entry point."""
    import argparse

    parser = argparse.ArgumentParser(
        description="Initialize MUTT default configurations in Redis"
    )
    parser.add_argument(
        '--force',
        action='store_true',
        help='Overwrite existing configuration values'
    )
    parser.add_argument(
        '--dry-run',
        action='store_true',
        help='Show what would be set without actually setting'
    )

    args = parser.parse_args()

    if args.dry_run:
        logger.info("DRY RUN MODE - No changes will be made")
        logger.info("")
        for category, configs in DEFAULT_CONFIGS.items():
            logger.info(f"\n[{category.upper()}]")
            for key, meta in configs.items():
                logger.info(f"  {key} = {meta['value']}")
                logger.info(f"    └─ {meta['description']}")
        return 0

    try:
        # Connect to Redis
        redis_client = get_redis_connection()

        # Initialize configs
        stats = initialize_configs(redis_client, force=args.force)

        if stats["set"] > 0:
            logger.info("✅ Configuration initialization successful!")
        else:
            logger.info("✅ All configurations already set (use --force to overwrite)")

        return 0

    except Exception as e:
        logger.error(f"❌ Configuration initialization failed: {e}", exc_info=True)
        return 1


if __name__ == "__main__":
    sys.exit(main())
