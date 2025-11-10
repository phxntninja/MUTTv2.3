#!/usr/bin/env python3
"""
MUTT v2.5 - Data Retention Cleanup Script

Enforces data retention policies by removing old records from the database.
Designed to run as a Kubernetes CronJob or scheduled task.

Features:
- Batch deletion to avoid long-running transactions
- Dry-run mode for testing
- Detailed logging and metrics
- Safe deletion with transaction rollback on errors

Usage:
    # Normal mode (actually deletes data)
    python retention_cleanup.py

    # Dry-run mode (only logs what would be deleted)
    RETENTION_DRY_RUN=true python retention_cleanup.py

    # Custom retention periods
    RETENTION_AUDIT_DAYS=180 python retention_cleanup.py

Author: MUTT Development Team
License: MIT
Version: 2.5.0
"""

import sys
import os
import logging
import psycopg2
import psycopg2.extras
from datetime import datetime, timedelta
from typing import Tuple, Dict

# Add parent directories to path for imports
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'config'))
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'services'))

from environment import (
    get_database_config,
    get_retention_config,
    validate_retention_config
)

# Set up logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


class RetentionCleanup:
    """
    Handles data retention cleanup operations.

    Attributes:
        conn: PostgreSQL database connection
        config: Retention configuration dict
        dry_run: If True, only log what would be deleted
        stats: Statistics about deleted records
    """

    def __init__(self, conn, config: dict):
        """
        Initialize retention cleanup handler.

        Args:
            conn: psycopg2 database connection
            config: Retention configuration dictionary
        """
        self.conn = conn
        self.config = config
        self.dry_run = config.get('dry_run', False)
        self.batch_size = config.get('batch_size', 1000)
        self.stats = {
            'config_audit': 0,
            'event_audit': 0,
            'dlq': 0
        }

    def cleanup_config_audit_logs(self) -> int:
        """
        Clean up old configuration audit logs.

        Returns:
            int: Number of records deleted

        Raises:
            Exception: If database operation fails
        """
        retention_days = self.config.get('audit_days', 365)
        cutoff_date = datetime.utcnow() - timedelta(days=retention_days)

        logger.info(
            f"Starting config audit log cleanup "
            f"(retention: {retention_days} days, cutoff: {cutoff_date})"
        )

        if self.dry_run:
            # Just count records that would be deleted
            cursor = self.conn.cursor()
            cursor.execute(
                "SELECT COUNT(*) FROM config_audit_log WHERE changed_at < %s",
                (cutoff_date,)
            )
            count = cursor.fetchone()[0]
            cursor.close()
            logger.info(f"[DRY RUN] Would delete {count} config audit log records")
            return count

        # Delete in batches
        total_deleted = 0
        while True:
            cursor = self.conn.cursor()
            try:
                cursor.execute(
                    """
                    DELETE FROM config_audit_log
                    WHERE id IN (
                        SELECT id FROM config_audit_log
                        WHERE changed_at < %s
                        ORDER BY changed_at
                        LIMIT %s
                    )
                    """,
                    (cutoff_date, self.batch_size)
                )
                deleted = cursor.rowcount
                self.conn.commit()
                total_deleted += deleted

                if deleted > 0:
                    logger.info(f"Deleted {deleted} config audit log records (total: {total_deleted})")

                if deleted < self.batch_size:
                    # No more records to delete
                    break

            except Exception as e:
                self.conn.rollback()
                logger.error(f"Error deleting config audit logs: {e}", exc_info=True)
                raise
            finally:
                cursor.close()

        logger.info(f"Config audit log cleanup complete: {total_deleted} records deleted")
        return total_deleted

    def cleanup_event_audit_logs(self) -> int:
        """
        Clean up old event audit logs.

        Returns:
            int: Number of records deleted

        Raises:
            Exception: If database operation fails
        """
        retention_days = self.config.get('event_audit_days', 90)
        cutoff_date = datetime.utcnow() - timedelta(days=retention_days)

        logger.info(
            f"Starting event audit log cleanup "
            f"(retention: {retention_days} days, cutoff: {cutoff_date})"
        )

        if self.dry_run:
            cursor = self.conn.cursor()
            cursor.execute(
                "SELECT COUNT(*) FROM audit_logs WHERE timestamp < %s",
                (cutoff_date,)
            )
            count = cursor.fetchone()[0]
            cursor.close()
            logger.info(f"[DRY RUN] Would delete {count} event audit log records")
            return count

        # Delete in batches
        total_deleted = 0
        while True:
            cursor = self.conn.cursor()
            try:
                cursor.execute(
                    """
                    DELETE FROM audit_logs
                    WHERE id IN (
                        SELECT id FROM audit_logs
                        WHERE timestamp < %s
                        ORDER BY timestamp
                        LIMIT %s
                    )
                    """,
                    (cutoff_date, self.batch_size)
                )
                deleted = cursor.rowcount
                self.conn.commit()
                total_deleted += deleted

                if deleted > 0:
                    logger.info(f"Deleted {deleted} event audit log records (total: {total_deleted})")

                if deleted < self.batch_size:
                    break

            except Exception as e:
                self.conn.rollback()
                logger.error(f"Error deleting event audit logs: {e}", exc_info=True)
                raise
            finally:
                cursor.close()

        logger.info(f"Event audit log cleanup complete: {total_deleted} records deleted")
        return total_deleted

    def cleanup_dlq_messages(self) -> int:
        """
        Clean up old Dead Letter Queue messages.

        Returns:
            int: Number of records deleted

        Raises:
            Exception: If database operation fails
        """
        retention_days = self.config.get('dlq_days', 30)
        cutoff_date = datetime.utcnow() - timedelta(days=retention_days)

        logger.info(
            f"Starting DLQ cleanup "
            f"(retention: {retention_days} days, cutoff: {cutoff_date})"
        )

        if self.dry_run:
            cursor = self.conn.cursor()
            cursor.execute(
                "SELECT COUNT(*) FROM dead_letter_queue WHERE failed_at < %s",
                (cutoff_date,)
            )
            count = cursor.fetchone()[0]
            cursor.close()
            logger.info(f"[DRY RUN] Would delete {count} DLQ records")
            return count

        # Delete in batches
        total_deleted = 0
        while True:
            cursor = self.conn.cursor()
            try:
                cursor.execute(
                    """
                    DELETE FROM dead_letter_queue
                    WHERE id IN (
                        SELECT id FROM dead_letter_queue
                        WHERE failed_at < %s
                        ORDER BY failed_at
                        LIMIT %s
                    )
                    """,
                    (cutoff_date, self.batch_size)
                )
                deleted = cursor.rowcount
                self.conn.commit()
                total_deleted += deleted

                if deleted > 0:
                    logger.info(f"Deleted {deleted} DLQ records (total: {total_deleted})")

                if deleted < self.batch_size:
                    break

            except Exception as e:
                self.conn.rollback()
                logger.error(f"Error deleting DLQ records: {e}", exc_info=True)
                raise
            finally:
                cursor.close()

        logger.info(f"DLQ cleanup complete: {total_deleted} records deleted")
        return total_deleted

    def run(self) -> Dict[str, int]:
        """
        Run all retention cleanup tasks.

        Returns:
            dict: Statistics about deleted records

        Examples:
            >>> cleanup = RetentionCleanup(conn, config)
            >>> stats = cleanup.run()
            >>> print(f"Deleted {stats['config_audit']} audit logs")
        """
        logger.info("=" * 60)
        logger.info("MUTT Data Retention Cleanup")
        logger.info("=" * 60)
        logger.info(f"Mode: {'DRY RUN' if self.dry_run else 'LIVE'}")
        logger.info(f"Configuration: {self.config}")

        start_time = datetime.utcnow()

        try:
            # Clean up configuration audit logs
            self.stats['config_audit'] = self.cleanup_config_audit_logs()

            # Clean up event audit logs
            self.stats['event_audit'] = self.cleanup_event_audit_logs()

            # Clean up DLQ messages
            self.stats['dlq'] = self.cleanup_dlq_messages()

            # Summary
            duration = (datetime.utcnow() - start_time).total_seconds()
            logger.info("=" * 60)
            logger.info("Retention Cleanup Summary")
            logger.info("=" * 60)
            logger.info(f"Duration: {duration:.2f}s")
            logger.info(f"Config audit logs: {self.stats['config_audit']} records")
            logger.info(f"Event audit logs: {self.stats['event_audit']} records")
            logger.info(f"DLQ messages: {self.stats['dlq']} records")
            logger.info(f"Total: {sum(self.stats.values())} records")

            if self.dry_run:
                logger.info("\nNOTE: This was a DRY RUN. No data was actually deleted.")

            return self.stats

        except Exception as e:
            logger.error(f"Retention cleanup failed: {e}", exc_info=True)
            raise


def main():
    """
    Main entry point for retention cleanup script.

    Returns:
        int: Exit code (0 for success, 1 for failure)
    """
    try:
        # Load configuration
        retention_config = get_retention_config()
        db_config = get_database_config()

        # Validate configuration
        warnings = validate_retention_config()
        if warnings:
            logger.warning("Configuration warnings:")
            for warning in warnings:
                logger.warning(f"  - {warning}")

        # Check if retention is enabled
        if not retention_config['enabled']:
            logger.info("Retention enforcement is DISABLED. Exiting.")
            return 0

        # Connect to database
        logger.info(f"Connecting to database: {db_config['host']}:{db_config['port']}/{db_config['database']}")
        conn = psycopg2.connect(
            host=db_config['host'],
            port=db_config['port'],
            database=db_config['database'],
            user=db_config['user'],
            password=db_config['password']
        )

        try:
            # Run cleanup
            cleanup = RetentionCleanup(conn, retention_config)
            stats = cleanup.run()

            # Write metrics for Prometheus (if metrics endpoint exists)
            try:
                write_metrics(stats, retention_config)
            except Exception as e:
                logger.warning(f"Failed to write metrics: {e}")

            return 0

        finally:
            conn.close()
            logger.info("Database connection closed")

    except Exception as e:
        logger.error(f"Retention cleanup failed: {e}", exc_info=True)
        return 1


def write_metrics(stats: Dict[str, int], config: dict):
    """
    Write cleanup metrics to a file for Prometheus node_exporter textfile collector.

    Args:
        stats: Statistics dictionary from cleanup
        config: Retention configuration

    Note:
        This writes metrics to /var/lib/node_exporter/textfile_collector/retention.prom
        which is read by node_exporter for Prometheus scraping.
    """
    metrics_file = os.getenv(
        'RETENTION_METRICS_FILE',
        '/var/lib/node_exporter/textfile_collector/retention.prom'
    )

    # Skip if directory doesn't exist (not in K8s environment)
    metrics_dir = os.path.dirname(metrics_file)
    if not os.path.exists(metrics_dir):
        logger.debug(f"Metrics directory {metrics_dir} doesn't exist, skipping metrics write")
        return

    try:
        timestamp = int(datetime.utcnow().timestamp() * 1000)

        with open(metrics_file, 'w') as f:
            # Write metrics
            f.write("# HELP mutt_retention_cleanup_records_deleted_total Total records deleted by retention cleanup\n")
            f.write("# TYPE mutt_retention_cleanup_records_deleted_total counter\n")

            for data_type, count in stats.items():
                f.write(f'mutt_retention_cleanup_records_deleted_total{{type="{data_type}"}} {count} {timestamp}\n')

            # Write retention configuration
            f.write("# HELP mutt_retention_policy_days Configured retention period in days\n")
            f.write("# TYPE mutt_retention_policy_days gauge\n")
            f.write(f'mutt_retention_policy_days{{type="config_audit"}} {config["audit_days"]} {timestamp}\n')
            f.write(f'mutt_retention_policy_days{{type="event_audit"}} {config["event_audit_days"]} {timestamp}\n')
            f.write(f'mutt_retention_policy_days{{type="dlq"}} {config["dlq_days"]} {timestamp}\n')

            # Write last run timestamp
            f.write("# HELP mutt_retention_cleanup_last_run_timestamp_seconds Timestamp of last retention cleanup run\n")
            f.write("# TYPE mutt_retention_cleanup_last_run_timestamp_seconds gauge\n")
            f.write(f'mutt_retention_cleanup_last_run_timestamp_seconds {timestamp // 1000} {timestamp}\n')

        logger.info(f"Metrics written to {metrics_file}")

    except Exception as e:
        logger.error(f"Failed to write metrics file: {e}", exc_info=True)
        raise


if __name__ == "__main__":
    sys.exit(main())
