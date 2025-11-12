#!/usr/bin/env python3
"""
MUTT v2.5 - Retention Policy Enforcement Service

This script enforces data retention policies across MUTT services to ensure
compliance with regulatory requirements (SOX, GDPR, HIPAA, etc.).

Features:
- Automated archival of old active events
- Deletion of expired archived data
- Cleanup of old configuration audit logs
- Configurable retention periods via DynamicConfig
- Dry-run mode for testing
- Metrics export for monitoring

Usage:
    # Run enforcement with default settings (from DynamicConfig/env vars)
    python retention_policy_enforcer.py

    # Dry-run mode (no changes)
    python retention_policy_enforcer.py --dry-run

    # Force run regardless of last run time
    python retention_policy_enforcer.py --force

    # Run as daemon (continuous mode)
    python retention_policy_enforcer.py --daemon

Author: MUTT Development Team
License: MIT
Version: 2.5.0
"""

import argparse
import logging
import os
import sys
import time
from datetime import datetime, timedelta, timezone
from typing import Optional, Dict, Any

import psycopg2
import redis
from prometheus_client import Counter, Gauge, start_http_server

# Add parent directory to path for imports
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

try:
    from services.dynamic_config import DynamicConfig
except ImportError:
    DynamicConfig = None  # type: ignore

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# =====================================================================
# PROMETHEUS METRICS
# =====================================================================

METRIC_EVENTS_ARCHIVED = Counter(
    'mutt_retention_events_archived_total',
    'Total number of events archived'
)

METRIC_EVENTS_DELETED = Counter(
    'mutt_retention_events_deleted_total',
    'Total number of expired events deleted from archive'
)

METRIC_CONFIG_AUDITS_DELETED = Counter(
    'mutt_retention_config_audits_deleted_total',
    'Total number of old config audit logs deleted'
)

METRIC_RETENTION_ERRORS = Counter(
    'mutt_retention_errors_total',
    'Total number of retention enforcement errors',
    ['task']
)

METRIC_LAST_RUN_TIMESTAMP = Gauge(
    'mutt_retention_last_run_timestamp',
    'Unix timestamp of last successful retention run'
)

METRIC_ENFORCEMENT_DURATION = Gauge(
    'mutt_retention_enforcement_duration_seconds',
    'Duration of last retention enforcement run in seconds'
)


# =====================================================================
# RETENTION POLICY ENFORCER
# =====================================================================

class RetentionPolicyEnforcer:
    """
    Enforces data retention policies across MUTT services.
    """

    def __init__(
        self,
        db_config: Dict[str, Any],
        redis_config: Optional[Dict[str, Any]] = None,
        dry_run: bool = False
    ):
        """
        Initialize retention policy enforcer.

        Args:
            db_config: PostgreSQL connection config
            redis_config: Redis connection config (optional, for DynamicConfig)
            dry_run: If True, log actions without making changes
        """
        self.db_config = db_config
        self.redis_config = redis_config
        self.dry_run = dry_run
        self.db_conn: Optional[psycopg2.extensions.connection] = None
        self.redis_client: Optional[redis.Redis] = None
        self.dyn_config: Optional[Any] = None

        # Retention policies (defaults, can be overridden by DynamicConfig)
        self.policies = {
            'event_retention_days': int(os.getenv('EVENT_RETENTION_DAYS', '90')),
            'event_archive_retention_years': int(os.getenv('EVENT_ARCHIVE_RETENTION_YEARS', '7')),
            'config_audit_retention_days': int(os.getenv('CONFIG_AUDIT_RETENTION_DAYS', '365')),
            'retention_enforcement_enabled': os.getenv('RETENTION_ENFORCEMENT_ENABLED', 'true').lower() == 'true'
        }

        logger.info(f"RetentionPolicyEnforcer initialized (dry_run={dry_run})")

    def connect(self) -> None:
        """Establish database and Redis connections."""
        # Connect to PostgreSQL
        try:
            self.db_conn = psycopg2.connect(**self.db_config)
            logger.info("Connected to PostgreSQL")
        except Exception as e:
            logger.error(f"Failed to connect to PostgreSQL: {e}")
            raise

        # Connect to Redis and load DynamicConfig
        if self.redis_config and DynamicConfig:
            try:
                self.redis_client = redis.Redis(**self.redis_config)
                self.redis_client.ping()
                logger.info("Connected to Redis")

                self.dyn_config = DynamicConfig(self.redis_client, prefix="mutt:config")
                self._load_policies_from_dynamic_config()
            except Exception as e:
                logger.warning(f"Failed to connect to Redis/DynamicConfig: {e}")
                logger.info("Using environment variable defaults")

    def _load_policies_from_dynamic_config(self) -> None:
        """Load retention policies from DynamicConfig."""
        if not self.dyn_config:
            return

        try:
            self.policies['event_retention_days'] = int(
                self.dyn_config.get('event_retention_days', default=str(self.policies['event_retention_days']))
            )
            self.policies['event_archive_retention_years'] = int(
                self.dyn_config.get('event_archive_retention_years', default=str(self.policies['event_archive_retention_years']))
            )
            self.policies['config_audit_retention_days'] = int(
                self.dyn_config.get('config_audit_retention_days', default=str(self.policies['config_audit_retention_days']))
            )
            enabled_str = self.dyn_config.get('retention_enforcement_enabled', default='true')
            self.policies['retention_enforcement_enabled'] = enabled_str.lower() == 'true'

            logger.info("Loaded retention policies from DynamicConfig")
            logger.info(f"  Event retention: {self.policies['event_retention_days']} days")
            logger.info(f"  Archive retention: {self.policies['event_archive_retention_years']} years")
            logger.info(f"  Config audit retention: {self.policies['config_audit_retention_days']} days")
            logger.info(f"  Enforcement enabled: {self.policies['retention_enforcement_enabled']}")
        except Exception as e:
            logger.error(f"Error loading policies from DynamicConfig: {e}")

    def disconnect(self) -> None:
        """Close database and Redis connections."""
        if self.db_conn:
            self.db_conn.close()
            logger.info("Disconnected from PostgreSQL")

        if self.redis_client:
            self.redis_client.close()
            logger.info("Disconnected from Redis")

    def enforce_all_policies(self) -> Dict[str, int]:
        """
        Enforce all retention policies.

        Returns:
            Dictionary with counts of actions taken
        """
        if not self.policies['retention_enforcement_enabled']:
            logger.warning("Retention enforcement is disabled - skipping")
            return {}

        logger.info("=" * 80)
        logger.info("Starting Retention Policy Enforcement")
        logger.info("=" * 80)

        start_time = time.time()
        results = {}

        try:
            # 1. Archive old events from active storage
            results['events_archived'] = self.archive_old_events()

            # 2. Delete expired events from archive
            results['archived_events_deleted'] = self.delete_expired_archived_events()

            # 3. Delete old config audit logs
            results['config_audits_deleted'] = self.delete_old_config_audits()

            # Update metrics
            duration = time.time() - start_time
            METRIC_LAST_RUN_TIMESTAMP.set(time.time())
            METRIC_ENFORCEMENT_DURATION.set(duration)

            logger.info("=" * 80)
            logger.info("Retention Policy Enforcement Complete")
            logger.info(f"  Duration: {duration:.2f} seconds")
            logger.info(f"  Events archived: {results.get('events_archived', 0)}")
            logger.info(f"  Archived events deleted: {results.get('archived_events_deleted', 0)}")
            logger.info(f"  Config audits deleted: {results.get('config_audits_deleted', 0)}")
            logger.info("=" * 80)

            return results

        except Exception as e:
            logger.error(f"Retention enforcement failed: {e}", exc_info=True)
            METRIC_RETENTION_ERRORS.labels(task='enforce_all').inc()
            raise

    def archive_old_events(self) -> int:
        """
        Archive events older than retention_days from active to archive storage.

        Returns:
            Number of events archived
        """
        logger.info(f"Archiving events older than {self.policies['event_retention_days']} days...")

        cutoff = datetime.now(timezone.utc) - timedelta(days=self.policies['event_retention_days'])

        try:
            cursor = self.db_conn.cursor()

            # Count events to archive
            cursor.execute(
                "SELECT COUNT(*) FROM event_audit_log WHERE event_timestamp < %s",
                (cutoff,)
            )
            count = cursor.fetchone()[0]

            if count == 0:
                logger.info("No events to archive")
                return 0

            if self.dry_run:
                logger.info(f"[DRY-RUN] Would archive {count} events")
                return count

            # Archive events (INSERT ... SELECT with DELETE)
            cursor.execute("""
                WITH archived AS (
                    DELETE FROM event_audit_log
                    WHERE event_timestamp < %s
                    RETURNING *
                )
                INSERT INTO event_audit_log_archive
                SELECT * FROM archived
            """, (cutoff,))

            self.db_conn.commit()
            METRIC_EVENTS_ARCHIVED.inc(count)

            logger.info(f"Archived {count} events")
            return count

        except Exception as e:
            self.db_conn.rollback()
            logger.error(f"Failed to archive events: {e}", exc_info=True)
            METRIC_RETENTION_ERRORS.labels(task='archive_events').inc()
            return 0

    def delete_expired_archived_events(self) -> int:
        """
        Delete archived events older than archive_retention_years.

        Returns:
            Number of archived events deleted
        """
        logger.info(f"Deleting archived events older than {self.policies['event_archive_retention_years']} years...")

        cutoff = datetime.now(timezone.utc) - timedelta(days=self.policies['event_archive_retention_years'] * 365)

        try:
            cursor = self.db_conn.cursor()

            # Count events to delete
            cursor.execute(
                "SELECT COUNT(*) FROM event_audit_log_archive WHERE event_timestamp < %s",
                (cutoff,)
            )
            count = cursor.fetchone()[0]

            if count == 0:
                logger.info("No archived events to delete")
                return 0

            if self.dry_run:
                logger.info(f"[DRY-RUN] Would delete {count} archived events")
                return count

            # Delete expired archived events
            cursor.execute(
                "DELETE FROM event_audit_log_archive WHERE event_timestamp < %s",
                (cutoff,)
            )

            self.db_conn.commit()
            METRIC_EVENTS_DELETED.inc(count)

            logger.info(f"Deleted {count} expired archived events")
            return count

        except Exception as e:
            self.db_conn.rollback()
            logger.error(f"Failed to delete archived events: {e}", exc_info=True)
            METRIC_RETENTION_ERRORS.labels(task='delete_archived_events').inc()
            return 0

    def delete_old_config_audits(self) -> int:
        """
        Delete config audit logs older than config_audit_retention_days.

        Returns:
            Number of config audit logs deleted
        """
        logger.info(f"Deleting config audits older than {self.policies['config_audit_retention_days']} days...")

        cutoff = datetime.now(timezone.utc) - timedelta(days=self.policies['config_audit_retention_days'])

        try:
            cursor = self.db_conn.cursor()

            # Count audits to delete
            cursor.execute(
                "SELECT COUNT(*) FROM config_audit_log WHERE changed_at < %s",
                (cutoff,)
            )
            count = cursor.fetchone()[0]

            if count == 0:
                logger.info("No config audits to delete")
                return 0

            if self.dry_run:
                logger.info(f"[DRY-RUN] Would delete {count} config audit logs")
                return count

            # Delete old config audits
            cursor.execute(
                "DELETE FROM config_audit_log WHERE changed_at < %s",
                (cutoff,)
            )

            self.db_conn.commit()
            METRIC_CONFIG_AUDITS_DELETED.inc(count)

            logger.info(f"Deleted {count} config audit logs")
            return count

        except Exception as e:
            self.db_conn.rollback()
            logger.error(f"Failed to delete config audits: {e}", exc_info=True)
            METRIC_RETENTION_ERRORS.labels(task='delete_config_audits').inc()
            return 0


def main():
    """Main entry point."""
    parser = argparse.ArgumentParser(
        description="MUTT v2.5 Retention Policy Enforcement Service"
    )
    parser.add_argument(
        '--dry-run',
        action='store_true',
        help='Log actions without making changes'
    )
    parser.add_argument(
        '--daemon',
        action='store_true',
        help='Run as daemon (continuous mode)'
    )
    parser.add_argument(
        '--interval',
        type=int,
        default=24,
        help='Hours between enforcement runs in daemon mode (default: 24)'
    )
    parser.add_argument(
        '--metrics-port',
        type=int,
        default=9100,
        help='Prometheus metrics port (default: 9100)'
    )

    args = parser.parse_args()

    # Database configuration
    db_config = {
        'host': os.getenv('DB_HOST', 'localhost'),
        'port': int(os.getenv('DB_PORT', '5432')),
        'dbname': os.getenv('DB_NAME', 'mutt'),
        'user': os.getenv('DB_USER', 'mutt_app'),
        'password': os.getenv('DB_PASS', '')
    }

    # Redis configuration (optional)
    redis_config = None
    if os.getenv('REDIS_HOST'):
        redis_config = {
            'host': os.getenv('REDIS_HOST', 'localhost'),
            'port': int(os.getenv('REDIS_PORT', '6379')),
            'decode_responses': False
        }

    # Start Prometheus metrics server
    if args.daemon:
        start_http_server(args.metrics_port)
        logger.info(f"Prometheus metrics server started on port {args.metrics_port}")

    # Create enforcer
    enforcer = RetentionPolicyEnforcer(
        db_config=db_config,
        redis_config=redis_config,
        dry_run=args.dry_run
    )

    try:
        enforcer.connect()

        if args.daemon:
            logger.info(f"Running in daemon mode (interval: {args.interval} hours)")
            while True:
                try:
                    enforcer.enforce_all_policies()
                except Exception as e:
                    logger.error(f"Enforcement run failed: {e}", exc_info=True)

                # Sleep until next run
                sleep_seconds = args.interval * 3600
                logger.info(f"Sleeping for {args.interval} hours until next run...")
                time.sleep(sleep_seconds)
        else:
            # Single run
            enforcer.enforce_all_policies()

    except KeyboardInterrupt:
        logger.info("Received interrupt signal, shutting down...")
    except Exception as e:
        logger.error(f"Fatal error: {e}", exc_info=True)
        return 1
    finally:
        enforcer.disconnect()

    return 0


if __name__ == "__main__":
    sys.exit(main())
