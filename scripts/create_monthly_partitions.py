#!/usr/bin/env python3
"""
MUTT v2.5 - Monthly Partition Manager

This script automatically creates monthly partitions for the event_audit_log
table. It should be run monthly via cron/Kubernetes CronJob to ensure
partitions exist before they're needed.

Usage:
    # Create partitions for next 3 months
    python create_monthly_partitions.py --months 3

    # Dry-run mode (no changes)
    python create_monthly_partitions.py --months 3 --dry-run

    # Custom database connection
    python create_monthly_partitions.py --months 6 --db-host localhost --db-name mutt

Author: MUTT Development Team
License: MIT
Version: 2.5.0
"""

import argparse
import logging
import os
import sys
from datetime import datetime, timedelta
from typing import List, Tuple

import psycopg2
from psycopg2 import sql


# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        logging.StreamHandler(sys.stdout),
        logging.FileHandler('/var/log/mutt/partition_manager.log', mode='a')
        if os.path.exists('/var/log/mutt')
        else logging.NullHandler()
    ]
)
logger = logging.getLogger(__name__)


class PartitionManager:
    """Manages monthly partitions for event_audit_log table."""

    def __init__(
        self,
        db_host: str,
        db_port: int,
        db_name: str,
        db_user: str,
        db_password: str,
        dry_run: bool = False
    ):
        """
        Initialize partition manager.

        Args:
            db_host: PostgreSQL host
            db_port: PostgreSQL port
            db_name: Database name
            db_user: Database user
            db_password: Database password
            dry_run: If True, only log what would be done (no changes)
        """
        self.db_host = db_host
        self.db_port = db_port
        self.db_name = db_name
        self.db_user = db_user
        self.db_password = db_password
        self.dry_run = dry_run
        self.conn = None

    def connect(self) -> None:
        """Establish database connection."""
        try:
            self.conn = psycopg2.connect(
                host=self.db_host,
                port=self.db_port,
                database=self.db_name,
                user=self.db_user,
                password=self.db_password
            )
            logger.info(f"Connected to database: {self.db_name} on {self.db_host}")
        except Exception as e:
            logger.error(f"Failed to connect to database: {e}")
            raise

    def disconnect(self) -> None:
        """Close database connection."""
        if self.conn:
            self.conn.close()
            logger.info("Disconnected from database")

    def get_existing_partitions(self) -> List[str]:
        """
        Get list of existing partition names.

        Returns:
            List of partition names (e.g., ['event_audit_log_2025_01', ...])
        """
        cursor = self.conn.cursor()
        cursor.execute("""
            SELECT child.relname
            FROM pg_inherits
            JOIN pg_class parent ON pg_inherits.inhparent = parent.oid
            JOIN pg_class child ON pg_inherits.inhrelid = child.oid
            WHERE parent.relname = 'event_audit_log'
            ORDER BY child.relname
        """)
        partitions = [row[0] for row in cursor.fetchall()]
        cursor.close()
        return partitions

    def generate_partition_dates(self, months_ahead: int) -> List[Tuple[datetime, str, str]]:
        """
        Generate partition start dates for next N months.

        Args:
            months_ahead: Number of months ahead to create partitions

        Returns:
            List of tuples: (date_obj, partition_name, date_range)
        """
        partitions = []
        current_date = datetime.now().replace(day=1, hour=0, minute=0, second=0, microsecond=0)

        for i in range(months_ahead):
            partition_date = current_date + timedelta(days=32 * i)
            partition_date = partition_date.replace(day=1)  # First day of month

            partition_name = f"event_audit_log_{partition_date.strftime('%Y_%m')}"

            # Calculate range: first day of month to first day of next month
            start_date = partition_date.strftime('%Y-%m-%d')
            end_date = (partition_date + timedelta(days=32)).replace(day=1).strftime('%Y-%m-%d')
            date_range = f"FROM ('{start_date}') TO ('{end_date}')"

            partitions.append((partition_date, partition_name, date_range))

        return partitions

    def partition_exists(self, partition_name: str, existing_partitions: List[str]) -> bool:
        """
        Check if partition already exists.

        Args:
            partition_name: Name of partition to check
            existing_partitions: List of existing partition names

        Returns:
            True if partition exists, False otherwise
        """
        return partition_name in existing_partitions

    def create_partition(self, partition_name: str, date_range: str) -> bool:
        """
        Create a monthly partition.

        Args:
            partition_name: Name of partition to create
            date_range: Date range for partition (e.g., "FROM ('2025-11-01') TO ('2025-12-01')")

        Returns:
            True if successful, False otherwise
        """
        if self.dry_run:
            logger.info(f"[DRY-RUN] Would create partition: {partition_name} {date_range}")
            return True

        try:
            cursor = self.conn.cursor()

            # Create partition using SQL
            create_sql = f"""
                CREATE TABLE IF NOT EXISTS {partition_name}
                PARTITION OF event_audit_log
                FOR VALUES {date_range}
            """

            cursor.execute(create_sql)
            self.conn.commit()

            logger.info(f"✅ Created partition: {partition_name} {date_range}")
            return True

        except Exception as e:
            self.conn.rollback()
            logger.error(f"❌ Failed to create partition {partition_name}: {e}")
            return False

        finally:
            cursor.close()

    def create_partitions(self, months_ahead: int) -> Tuple[int, int]:
        """
        Create partitions for next N months.

        Args:
            months_ahead: Number of months ahead to create partitions

        Returns:
            Tuple of (created_count, skipped_count)
        """
        logger.info(f"Creating partitions for next {months_ahead} months...")

        # Get existing partitions
        existing_partitions = self.get_existing_partitions()
        logger.info(f"Found {len(existing_partitions)} existing partitions")

        # Generate partition dates
        partition_dates = self.generate_partition_dates(months_ahead)

        created_count = 0
        skipped_count = 0

        # Create each partition
        for partition_date, partition_name, date_range in partition_dates:
            if self.partition_exists(partition_name, existing_partitions):
                logger.info(f"⏭️  Skipped (already exists): {partition_name}")
                skipped_count += 1
                continue

            if self.create_partition(partition_name, date_range):
                created_count += 1
            else:
                logger.warning(f"⚠️  Failed to create: {partition_name}")

        return created_count, skipped_count

    def get_partition_statistics(self) -> List[Tuple[str, str, str]]:
        """
        Get statistics about existing partitions.

        Returns:
            List of tuples: (partition_name, partition_range, size)
        """
        cursor = self.conn.cursor()
        cursor.execute("""
            SELECT
                child.relname AS partition_name,
                pg_get_expr(child.relpartbound, child.oid, true) AS partition_range,
                pg_size_pretty(pg_total_relation_size(child.oid)) AS partition_size
            FROM pg_inherits
            JOIN pg_class parent ON pg_inherits.inhparent = parent.oid
            JOIN pg_class child ON pg_inherits.inhrelid = child.oid
            WHERE parent.relname = 'event_audit_log'
            ORDER BY child.relname DESC
        """)
        stats = cursor.fetchall()
        cursor.close()
        return stats


def main():
    """Main entry point."""
    parser = argparse.ArgumentParser(
        description='MUTT v2.5 - Monthly Partition Manager',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  # Create partitions for next 3 months
  python create_monthly_partitions.py --months 3

  # Dry-run (no changes)
  python create_monthly_partitions.py --months 3 --dry-run

  # Show partition statistics
  python create_monthly_partitions.py --stats

  # Custom database connection
  python create_monthly_partitions.py --months 6 \\
      --db-host localhost --db-port 5432 \\
      --db-name mutt --db-user mutt_user
        """
    )

    parser.add_argument(
        '--months',
        type=int,
        default=int(os.getenv('RETENTION_PRECREATE_MONTHS', '3')),
        help='Number of months ahead to create partitions (default env RETENTION_PRECREATE_MONTHS or 3)'
    )
    parser.add_argument(
        '--dry-run',
        action='store_true',
        help='Dry-run mode (show what would be done, but make no changes)'
    )
    parser.add_argument(
        '--stats',
        action='store_true',
        help='Show partition statistics and exit'
    )

    # Database connection parameters (from environment or command line)
    parser.add_argument('--db-host', default=os.getenv('DB_HOST', 'localhost'))
    parser.add_argument('--db-port', type=int, default=int(os.getenv('DB_PORT', '5432')))
    parser.add_argument('--db-name', default=os.getenv('DB_NAME', 'mutt'))
    parser.add_argument('--db-user', default=os.getenv('DB_USER', 'mutt_user'))
    parser.add_argument('--db-password', default=os.getenv('DB_PASS', 'mutt_password'))

    args = parser.parse_args()

    # Initialize manager
    manager = PartitionManager(
        db_host=args.db_host,
        db_port=args.db_port,
        db_name=args.db_name,
        db_user=args.db_user,
        db_password=args.db_password,
        dry_run=args.dry_run
    )

    try:
        # Connect to database
        manager.connect()

        if args.stats:
            # Show partition statistics
            logger.info("Partition Statistics:")
            logger.info("-" * 80)
            stats = manager.get_partition_statistics()
            for partition_name, partition_range, size in stats:
                logger.info(f"{partition_name:30} {partition_range:50} {size}")
            logger.info("-" * 80)
            logger.info(f"Total partitions: {len(stats)}")
            return 0

        # Create partitions
        if args.dry_run:
            logger.info("🔍 DRY-RUN MODE - No changes will be made")

        created_count, skipped_count = manager.create_partitions(args.months)

        # Summary
        logger.info("=" * 80)
        logger.info("Partition Manager Summary:")
        logger.info(f"  ✅ Created: {created_count} partitions")
        logger.info(f"  ⏭️  Skipped: {skipped_count} partitions (already exist)")
        logger.info(f"  📅 Months ahead: {args.months}")
        if args.dry_run:
            logger.info("  🔍 Mode: DRY-RUN (no changes made)")
        logger.info("=" * 80)

        return 0

    except Exception as e:
        logger.error(f"Partition manager failed: {e}", exc_info=True)
        return 1

    finally:
        manager.disconnect()


if __name__ == '__main__':
    sys.exit(main())
