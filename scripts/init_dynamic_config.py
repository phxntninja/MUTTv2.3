#!/usr/bin/env python3
"""
MUTT v2.5 - Dynamic Config Initialization Script

This script initializes dynamic configuration in Redis from environment variables.
Should be run once during initial deployment or when adding new config keys.

Usage:
    # Initialize from environment variables
    python init_dynamic_config.py

    # Dry-run mode (show what would be set)
    python init_dynamic_config.py --dry-run

    # Force overwrite existing values
    python init_dynamic_config.py --force

Author: MUTT Development Team
License: MIT
Version: 2.5.0
"""

import argparse
import logging
import os
import sys
from typing import Dict

import redis

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


# Configuration mappings: Redis key -> (env_var, default_value)
CONFIG_MAPPINGS = {
    # Ingestor service
    'cache_reload_interval': ('CACHE_RELOAD_INTERVAL', '300'),
    'max_ingest_queue_size': ('MAX_INGEST_QUEUE_SIZE', '100000'),
    'ingest_max_rate': ('INGEST_MAX_RATE', '10000'),
    'ingest_queue_depth_limit': ('INGEST_QUEUE_DEPTH_LIMIT', '100000'),

    # Alerter service
    'alerter_cache_reload_interval': ('CACHE_RELOAD_INTERVAL', '300'),
    'max_queue_depth': ('MAX_QUEUE_DEPTH', '100000'),

    # Moog Forwarder service
    'moog_rate_limit': ('MOOG_RATE_LIMIT', '100'),
    'moog_batch_size': ('MOOG_BATCH_SIZE', '100'),
    'moog_circuit_breaker_timeout': ('MOOG_CIRCUIT_BREAKER_TIMEOUT', '300'),

    # Web UI service
    'webui_cache_ttl': ('WEBUI_CACHE_TTL', '5'),
    'api_rate_limit': ('API_RATE_LIMIT', '1000'),

    # Global settings
    'log_level': ('LOG_LEVEL', 'INFO'),
    'metrics_enabled': ('METRICS_ENABLED', 'true'),
}


def connect_to_redis(args) -> redis.Redis:
    """
    Connect to Redis.

    Args:
        args: Command-line arguments with connection parameters

    Returns:
        Redis client instance

    Raises:
        Exception: If connection fails
    """
    try:
        client = redis.Redis(
            host=args.redis_host,
            port=args.redis_port,
            db=args.redis_db,
            decode_responses=False,
            socket_timeout=5
        )

        # Test connection
        client.ping()
        logger.info(f"Connected to Redis: {args.redis_host}:{args.redis_port}")
        return client

    except Exception as e:
        logger.error(f"Failed to connect to Redis: {e}")
        raise


def get_config_value(env_var: str, default: str) -> str:
    """
    Get configuration value from environment or use default.

    Args:
        env_var: Environment variable name
        default: Default value if env var not set

    Returns:
        Configuration value
    """
    value = os.getenv(env_var, default)
    return value


def initialize_config(
    redis_client: redis.Redis,
    prefix: str,
    force: bool = False,
    dry_run: bool = False
) -> tuple:
    """
    Initialize dynamic configuration in Redis.

    Args:
        redis_client: Redis client instance
        prefix: Key prefix for config (e.g., "mutt:config")
        force: If True, overwrite existing values
        dry_run: If True, only show what would be done

    Returns:
        Tuple of (created_count, skipped_count, updated_count)
    """
    created_count = 0
    skipped_count = 0
    updated_count = 0

    logger.info("Initializing dynamic configuration...")
    logger.info(f"Prefix: {prefix}")
    logger.info(f"Force mode: {force}")
    logger.info(f"Dry-run mode: {dry_run}")
    logger.info("=" * 80)

    for config_key, (env_var, default_value) in CONFIG_MAPPINGS.items():
        redis_key = f"{prefix}:{config_key}"

        # Get value from environment or default
        value = get_config_value(env_var, default_value)

        # Check if key already exists
        existing_value = redis_client.get(redis_key)

        if existing_value:
            existing_value = existing_value.decode('utf-8') if isinstance(existing_value, bytes) else existing_value

            if not force:
                logger.info(f"⏭️  SKIP {config_key} = {existing_value} (already exists)")
                skipped_count += 1
                continue
            else:
                if dry_run:
                    logger.info(
                        f"[DRY-RUN] UPDATE {config_key}: "
                        f"{existing_value} → {value}"
                    )
                else:
                    redis_client.set(redis_key, value)
                    logger.info(
                        f"✏️  UPDATE {config_key}: "
                        f"{existing_value} → {value}"
                    )
                updated_count += 1
        else:
            if dry_run:
                logger.info(f"[DRY-RUN] CREATE {config_key} = {value}")
            else:
                redis_client.set(redis_key, value)
                logger.info(f"✅ CREATE {config_key} = {value}")
            created_count += 1

        # Show source
        if env_var in os.environ:
            logger.debug(f"    Source: environment variable {env_var}")
        else:
            logger.debug(f"    Source: default value")

    return created_count, skipped_count, updated_count


def verify_config(redis_client: redis.Redis, prefix: str) -> None:
    """
    Verify all config values are set correctly.

    Args:
        redis_client: Redis client instance
        prefix: Key prefix for config
    """
    logger.info("")
    logger.info("=" * 80)
    logger.info("Verification:")
    logger.info("=" * 80)

    all_correct = True

    for config_key, (env_var, default_value) in CONFIG_MAPPINGS.items():
        redis_key = f"{prefix}:{config_key}"
        expected_value = get_config_value(env_var, default_value)

        actual_value = redis_client.get(redis_key)
        if actual_value:
            actual_value = actual_value.decode('utf-8') if isinstance(actual_value, bytes) else actual_value

        if actual_value == expected_value:
            logger.info(f"✅ {config_key} = {actual_value}")
        else:
            logger.error(
                f"❌ {config_key}: expected={expected_value}, "
                f"actual={actual_value}"
            )
            all_correct = False

    logger.info("=" * 80)

    if all_correct:
        logger.info("✅ All config values verified successfully")
    else:
        logger.error("❌ Some config values are incorrect")
        sys.exit(1)


def main():
    """Main entry point."""
    parser = argparse.ArgumentParser(
        description='MUTT v2.5 - Initialize Dynamic Configuration',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  # Initialize from environment variables
  python init_dynamic_config.py

  # Dry-run (show what would be set)
  python init_dynamic_config.py --dry-run

  # Force overwrite existing values
  python init_dynamic_config.py --force

  # Custom Redis connection
  python init_dynamic_config.py --redis-host redis.example.com --redis-port 6380
        """
    )

    parser.add_argument(
        '--redis-host',
        default=os.getenv('REDIS_HOST', 'localhost'),
        help='Redis host (default: localhost)'
    )
    parser.add_argument(
        '--redis-port',
        type=int,
        default=int(os.getenv('REDIS_PORT', '6379')),
        help='Redis port (default: 6379)'
    )
    parser.add_argument(
        '--redis-db',
        type=int,
        default=int(os.getenv('REDIS_DB', '0')),
        help='Redis database number (default: 0)'
    )
    parser.add_argument(
        '--prefix',
        default='mutt:config',
        help='Config key prefix (default: mutt:config)'
    )
    parser.add_argument(
        '--force',
        action='store_true',
        help='Force overwrite existing config values'
    )
    parser.add_argument(
        '--dry-run',
        action='store_true',
        help='Show what would be done without making changes'
    )
    parser.add_argument(
        '--verify',
        action='store_true',
        help='Verify config after initialization'
    )

    args = parser.parse_args()

    try:
        # Connect to Redis
        redis_client = connect_to_redis(args)

        # Initialize config
        created, skipped, updated = initialize_config(
            redis_client,
            args.prefix,
            force=args.force,
            dry_run=args.dry_run
        )

        # Summary
        logger.info("")
        logger.info("=" * 80)
        logger.info("Summary:")
        logger.info(f"  ✅ Created: {created}")
        logger.info(f"  ✏️  Updated: {updated}")
        logger.info(f"  ⏭️  Skipped: {skipped}")
        logger.info(f"  📊 Total: {created + skipped + updated}")

        if args.dry_run:
            logger.info("")
            logger.info("🔍 DRY-RUN MODE - No changes were made")
            logger.info("   Run without --dry-run to apply changes")

        logger.info("=" * 80)

        # Verify if requested
        if args.verify and not args.dry_run:
            verify_config(redis_client, args.prefix)

        return 0

    except Exception as e:
        logger.error(f"Initialization failed: {e}", exc_info=True)
        return 1


if __name__ == '__main__':
    sys.exit(main())
