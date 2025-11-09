#!/usr/bin/env python3
"""
MUTT v2.5 - Event Archival Script

This script archives old events from the active event_audit_log table to
the event_audit_log_archive table for long-term compliance storage.

This enables:
- 90-day active storage for fast queries
- 7-year archive storage for compliance (SOX/GDPR)
- Automated cleanup to control database growth

Usage:
    # Archive events older than 90 days (default)
    python archive_old_events.py

    # Archive events older than 30 days
    python archive_old_events.py --retention-days 30

    # Dry-run mode (no changes)
    python archive_old_events.py --dry-run

    # Custom batch size
    python archive_old_events.py --retention-days 90 --batch-size 5000

Author: MUTT Development Team
License: MIT
Version: 2.5.0
"""

import argparse
import logging
import os
import sys
import time
from datetime import datetime, timedelta

import psycopg2
from psycopg2 import sql


# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        logging.StreamHandler(sys.stdout),
        logging.FileHandler('/var/log/mutt/archive_manager.log', mode='a')
        if os.path.exists('/var/log/mutt')
        else logging.NullHandler()
    ]
)
logger = logging.getLogger(__name__)


class ArchiveManager:
    """Manages archival of old events from active storage to archive."""

    def __init__(
        self,
        db_host: str,
        db_port: int,
        db_name: str,
        db_user: str,
        db_password: str,
        retention_days: int,
        batch_size: int,
        dry_run: bool = False
    ):
        """
        Initialize archive manager.

        Args:
            db_host: PostgreSQL host
            db_port: PostgreSQL port
            db_name: Database name
            db_user: Database user
            db_password: Database password
            retention_days: Number of days to keep in active storage
            batch_size: Number of rows to archive per batch
            dry_run: If True, only log what would be done (no changes)
        """
        self.db_host = db_host
        self.db_port = db_port
        self.db_name = db_name
        self.db_user = db_user
        self.db_password = db_password
        self.retention_days = retention_days
        self.batch_size = batch_size
        self.dry_run = dry_run
        self.conn = None

        # Calculate cutoff timestamp
        self.cutoff_timestamp = datetime.now() - timedelta(days=retention_days)

    def connect(self) -> None:
        """Establish database connection with autocommit disabled."""
        try:
            self.conn = psycopg2.connect(
                host=self.db_host,
                port=self.db_port,
                database=self.db_name,
                user=self.db_user,
                password=self.db_password
            )
            self.conn.autocommit = False  # We want explicit transaction control
            logger.info(f"Connected to database: {self.db_name} on {self.db_host}")
        except Exception as e:
            logger.error(f"Failed to connect to database: {e}")
            raise

    def disconnect(self) -> None:
        """Close database connection."""
        if self.conn:
            self.conn.close()
            logger.info("Disconnected from database")

    def count_events_to_archive(self) -> int:
        """
        Count how many events are older than retention period.

        Returns:
            Number of events to archive
        """
        cursor = self.conn.cursor()
        cursor.execute("""
            SELECT COUNT(*)
            FROM event_audit_log
            WHERE event_timestamp < %s
        """, (self.cutoff_timestamp,))
        count = cursor.fetchone()[0]
        cursor.close()
        return count

    def archive_batch(self) -> int:
        """
        Archive one batch of old events.

        Returns:
            Number of rows archived in this batch

        Raises:
            Exception: If archival fails (will trigger rollback)
        """
        if self.dry_run:
            # In dry-run mode, just count how many would be archived
            cursor = self.conn.cursor()
            cursor.execute("""
                SELECT COUNT(*)
                FROM event_audit_log
                WHERE event_timestamp < %s
                LIMIT %s
            """, (self.cutoff_timestamp, self.batch_size))
            count = cursor.fetchone()[0]
            cursor.close()
            logger.info(f"[DRY-RUN] Would archive batch of {count} events")
            return count

        cursor = self.conn.cursor()

        try:
            # Step 1: Insert into archive (with RETURNING for verification)
            cursor.execute("""
                INSERT INTO event_audit_log_archive (
                    event_timestamp,
                    hostname,
                    matched_rule_id,
                    handling_decision,
                    forwarded_to_moog,
                    raw_message,
                    archived_from_partition,
                    original_id,
                    original_partition_timestamp
                )
                SELECT
                    event_timestamp,
                    hostname,
                    matched_rule_id,
                    handling_decision,
                    forwarded_to_moog,
                    raw_message,
                    'event_audit_log' AS archived_from_partition,
                    id AS original_id,
                    event_timestamp AS original_partition_timestamp
                FROM event_audit_log
                WHERE event_timestamp < %s
                LIMIT %s
                RETURNING id
            """, (self.cutoff_timestamp, self.batch_size))

            archived_ids = [row[0] for row in cursor.fetchall()]
            rows_inserted = len(archived_ids)

            if rows_inserted == 0:
                # No more rows to archive
                self.conn.rollback()
                return 0

            logger.info(f"Inserted {rows_inserted} rows into archive")

            # Step 2: Delete from main table (only rows that were archived)
            # We need to match by both id AND event_timestamp because id is not globally unique
            cursor.execute("""
                DELETE FROM event_audit_log
                WHERE event_timestamp < %s
                AND id IN (
                    SELECT original_id
                    FROM event_audit_log_archive
                    WHERE archived_at >= NOW() - INTERVAL '5 seconds'
                    LIMIT %s
                )
            """, (self.cutoff_timestamp, self.batch_size))

            rows_deleted = cursor.rowcount
            logger.info(f"Deleted {rows_deleted} rows from active storage")

            # Verify counts match
            if rows_inserted != rows_deleted:
                raise Exception(
                    f"Archival mismatch: inserted {rows_inserted} rows but deleted {rows_deleted} rows"
                )

            # Commit transaction
            self.conn.commit()
            logger.info(f"✅ Successfully archived {rows_inserted} events")

            return rows_inserted

        except Exception as e:
            # Rollback on any error
            self.conn.rollback()
            logger.error(f"❌ Archival batch failed (rolled back): {e}")
            raise

        finally:
            cursor.close()

    def archive_all(self) -> int:
        """
        Archive all events older than retention period.

        Returns:
            Total number of rows archived

        Raises:
            Exception: If archival fails
        """
        logger.info(f"Starting archival of events older than {self.retention_days} days")
        logger.info(f"Cutoff timestamp: {self.cutoff_timestamp}")
        logger.info(f"Batch size: {self.batch_size}")

        if self.dry_run:
            logger.info("🔍 DRY-RUN MODE - No changes will be made")

        # Count total events to archive
        total_to_archive = self.count_events_to_archive()
        logger.info(f"Found {total_to_archive} events to archive")

        if total_to_archive == 0:
            logger.info("No events to archive")
            return 0

        if self.dry_run:
            logger.info(f"[DRY-RUN] Would archive {total_to_archive} events")
            return total_to_archive

        # Archive in batches
        total_archived = 0
        batch_num = 0
        start_time = time.time()

        while True:
            batch_num += 1
            logger.info(f"Processing batch {batch_num}...")

            try:
                rows_archived = self.archive_batch()

                if rows_archived == 0:
                    logger.info("No more rows to archive")
                    break

                total_archived += rows_archived

                # Progress update
                percent_complete = (total_archived / total_to_archive) * 100
                logger.info(
                    f"Progress: {total_archived}/{total_to_archive} "
                    f"({percent_complete:.1f}%) archived"
                )

                # Small delay between batches to avoid overwhelming the database
                time.sleep(0.5)

            except Exception as e:
                logger.error(f"Batch {batch_num} failed: {e}")
                logger.error(f"Stopping archival. Total archived so far: {total_archived}")
                raise

        # Summary
        elapsed_time = time.time() - start_time
        logger.info("=" * 80)
        logger.info("Archival Summary:")
        logger.info(f"  Total archived: {total_archived} events")
        logger.info(f"  Batches processed: {batch_num}")
        logger.info(f"  Time elapsed: {elapsed_time:.2f} seconds")
        logger.info(f"  Events/second: {total_archived / elapsed_time:.2f}")
        logger.info("=" * 80)

        return total_archived

    def get_storage_statistics(self) -> dict:
        """
        Get storage statistics for active and archive tables.

        Returns:
            Dictionary with statistics
        """
        cursor = self.conn.cursor()

        # Active table stats
        cursor.execute("SELECT COUNT(*) FROM event_audit_log")
        active_count = cursor.fetchone()[0]

        cursor.execute("SELECT pg_size_pretty(pg_total_relation_size('event_audit_log'))")
        active_size = cursor.fetchone()[0]

        cursor.execute("SELECT MIN(event_timestamp), MAX(event_timestamp) FROM event_audit_log")
        active_min, active_max = cursor.fetchone()

        # Archive table stats
        cursor.execute("SELECT COUNT(*) FROM event_audit_log_archive")
        archive_count = cursor.fetchone()[0]

        cursor.execute("SELECT pg_size_pretty(pg_total_relation_size('event_audit_log_archive'))")
        archive_size = cursor.fetchone()[0]

        cursor.execute("SELECT MIN(event_timestamp), MAX(event_timestamp) FROM event_audit_log_archive")
        archive_min, archive_max = cursor.fetchone()

        cursor.close()

        return {
            'active_count': active_count,
            'active_size': active_size,
            'active_oldest': active_min,
            'active_newest': active_max,
            'archive_count': archive_count,
            'archive_size': archive_size,
            'archive_oldest': archive_min,
            'archive_newest': archive_max
        }


def main():
    """Main entry point."""
    parser = argparse.ArgumentParser(
        description='MUTT v2.5 - Event Archival Manager',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  # Archive events older than 90 days (default)
  python archive_old_events.py

  # Archive events older than 30 days
  python archive_old_events.py --retention-days 30

  # Dry-run (no changes)
  python archive_old_events.py --dry-run

  # Show storage statistics
  python archive_old_events.py --stats

  # Custom batch size for large datasets
  python archive_old_events.py --retention-days 90 --batch-size 5000
        """
    )

    parser.add_argument(
        '--retention-days',
        type=int,
        default=int(os.getenv('EVENT_RETENTION_DAYS', '90')),
        help='Number of days to keep in active storage (default: 90)'
    )
    parser.add_argument(
        '--batch-size',
        type=int,
        default=10000,
        help='Number of rows to archive per batch (default: 10000)'
    )
    parser.add_argument(
        '--dry-run',
        action='store_true',
        help='Dry-run mode (show what would be done, but make no changes)'
    )
    parser.add_argument(
        '--stats',
        action='store_true',
        help='Show storage statistics and exit'
    )

    # Database connection parameters (from environment or command line)
    parser.add_argument('--db-host', default=os.getenv('DB_HOST', 'localhost'))
    parser.add_argument('--db-port', type=int, default=int(os.getenv('DB_PORT', '5432')))
    parser.add_argument('--db-name', default=os.getenv('DB_NAME', 'mutt'))
    parser.add_argument('--db-user', default=os.getenv('DB_USER', 'mutt_user'))
    parser.add_argument('--db-password', default=os.getenv('DB_PASS', 'mutt_password'))

    args = parser.parse_args()

    # Initialize manager
    manager = ArchiveManager(
        db_host=args.db_host,
        db_port=args.db_port,
        db_name=args.db_name,
        db_user=args.db_user,
        db_password=args.db_password,
        retention_days=args.retention_days,
        batch_size=args.batch_size,
        dry_run=args.dry_run
    )

    try:
        # Connect to database
        manager.connect()

        if args.stats:
            # Show storage statistics
            logger.info("Storage Statistics:")
            logger.info("=" * 80)
            stats = manager.get_storage_statistics()
            logger.info(f"Active Storage:")
            logger.info(f"  Count: {stats['active_count']:,} events")
            logger.info(f"  Size: {stats['active_size']}")
            logger.info(f"  Date Range: {stats['active_oldest']} to {stats['active_newest']}")
            logger.info(f"")
            logger.info(f"Archive Storage:")
            logger.info(f"  Count: {stats['archive_count']:,} events")
            logger.info(f"  Size: {stats['archive_size']}")
            logger.info(f"  Date Range: {stats['archive_oldest']} to {stats['archive_newest']}")
            logger.info("=" * 80)
            return 0

        # Run archival
        total_archived = manager.archive_all()

        if total_archived > 0:
            logger.info(f"✅ Archival complete: {total_archived} events archived")
            return 0
        else:
            logger.info("ℹ️  No events to archive")
            return 0

    except Exception as e:
        logger.error(f"Archival failed: {e}", exc_info=True)
        return 1

    finally:
        manager.disconnect()


if __name__ == '__main__':
    sys.exit(main())
