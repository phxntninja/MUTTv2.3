#!/bin/bash
# =====================================================================
# MUTT v2.3 - PostgreSQL Partition Manager
# =====================================================================
# This script automates creation and cleanup of monthly partitions for
# the event_audit_log table.
#
# Usage:
#   ./partition_manager.sh create              # Create next 3 months
#   ./partition_manager.sh cleanup             # Drop partitions older than 6 months
#   ./partition_manager.sh auto                # Both create and cleanup
#
# Cron Setup (run on 1st of each month):
#   0 2 1 * * /opt/mutt/scripts/partition_manager.sh auto >> /var/log/mutt/partition_manager.log 2>&1
#
# Environment Variables:
#   DB_HOST - PostgreSQL host (default: localhost)
#   DB_PORT - PostgreSQL port (default: 5432)
#   DB_NAME - Database name (default: mutt)
#   DB_USER - Database user (default: mutt_user)
#   DB_PASS - Database password (required)
# =====================================================================

set -euo pipefail

# =====================================================================
# Configuration
# =====================================================================
DB_HOST="${DB_HOST:-localhost}"
DB_PORT="${DB_PORT:-5432}"
DB_NAME="${DB_NAME:-mutt}"
DB_USER="${DB_USER:-mutt_user}"
DB_PASS="${DB_PASS:-}"

# Retention period in months
RETENTION_MONTHS=6

# Number of future months to pre-create
FUTURE_MONTHS=3

# =====================================================================
# Colors for output
# =====================================================================
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

# =====================================================================
# Logging Functions
# =====================================================================
log_info() {
    echo -e "${GREEN}[INFO]${NC} $(date '+%Y-%m-%d %H:%M:%S') - $1"
}

log_warn() {
    echo -e "${YELLOW}[WARN]${NC} $(date '+%Y-%m-%d %H:%M:%S') - $1"
}

log_error() {
    echo -e "${RED}[ERROR]${NC} $(date '+%Y-%m-%d %H:%M:%S') - $1"
}

# =====================================================================
# Database Connection
# =====================================================================
run_sql() {
    local sql="$1"
    PGPASSWORD="$DB_PASS" psql -h "$DB_HOST" -p "$DB_PORT" -U "$DB_USER" -d "$DB_NAME" -t -c "$sql"
}

# =====================================================================
# Validation
# =====================================================================
validate_config() {
    if [[ -z "$DB_PASS" ]]; then
        log_error "DB_PASS environment variable is required"
        echo "Usage: DB_PASS=your_password $0 <create|cleanup|auto>"
        exit 1
    fi

    # Test database connection
    if ! PGPASSWORD="$DB_PASS" psql -h "$DB_HOST" -p "$DB_PORT" -U "$DB_USER" -d "$DB_NAME" -c "SELECT 1" > /dev/null 2>&1; then
        log_error "Cannot connect to database"
        exit 1
    fi

    log_info "Database connection successful"
}

# =====================================================================
# Create Future Partitions
# =====================================================================
create_partitions() {
    log_info "Creating partitions for next $FUTURE_MONTHS months..."

    for i in $(seq 0 $FUTURE_MONTHS); do
        # Calculate month offset from today
        if [[ "$OSTYPE" == "darwin"* ]]; then
            # macOS date command
            partition_date=$(date -v+${i}m '+%Y-%m-01')
        else
            # Linux date command
            partition_date=$(date -d "$(date +%Y-%m-01) +${i} months" '+%Y-%m-01')
        fi

        log_info "Creating partition for $partition_date..."

        # Call PostgreSQL function to create partition
        result=$(run_sql "SELECT create_monthly_partition('$partition_date'::DATE);")

        if [[ -n "$result" ]]; then
            log_info "  ✓ $result"
        else
            log_warn "  Partition may already exist for $partition_date"
        fi
    done

    log_info "Partition creation complete"
}

# =====================================================================
# Cleanup Old Partitions
# =====================================================================
cleanup_partitions() {
    log_info "Cleaning up partitions older than $RETENTION_MONTHS months..."

    # Call PostgreSQL function to drop old partitions
    result=$(run_sql "SELECT drop_old_partitions($RETENTION_MONTHS);")

    if [[ -n "$result" ]]; then
        log_info "  ✓ Dropped partitions: $result"
    else
        log_info "  No partitions to drop"
    fi

    log_info "Partition cleanup complete"
}

# =====================================================================
# List Existing Partitions
# =====================================================================
list_partitions() {
    log_info "Existing partitions:"

    partitions=$(run_sql "
        SELECT schemaname || '.' || tablename AS partition_name
        FROM pg_tables
        WHERE tablename LIKE 'event_audit_log_%'
        AND schemaname = 'public'
        ORDER BY tablename;
    ")

    if [[ -n "$partitions" ]]; then
        echo "$partitions" | while read -r partition; do
            # Get partition size
            size=$(run_sql "SELECT pg_size_pretty(pg_total_relation_size('$partition'));")

            # Get row count
            rows=$(run_sql "SELECT COUNT(*) FROM $partition;")

            echo "  • $partition - $size - $rows rows"
        done
    else
        log_warn "  No partitions found"
    fi
}

# =====================================================================
# Main
# =====================================================================
main() {
    local action="${1:-}"

    if [[ -z "$action" ]]; then
        echo "Usage: $0 <create|cleanup|auto|list>"
        echo ""
        echo "Commands:"
        echo "  create  - Create partitions for next $FUTURE_MONTHS months"
        echo "  cleanup - Drop partitions older than $RETENTION_MONTHS months"
        echo "  auto    - Both create and cleanup (recommended for cron)"
        echo "  list    - List all existing partitions"
        echo ""
        echo "Environment Variables:"
        echo "  DB_HOST - PostgreSQL host (default: localhost)"
        echo "  DB_PORT - PostgreSQL port (default: 5432)"
        echo "  DB_NAME - Database name (default: mutt)"
        echo "  DB_USER - Database user (default: mutt_user)"
        echo "  DB_PASS - Database password (required)"
        echo ""
        echo "Example:"
        echo "  DB_PASS=secret $0 auto"
        exit 1
    fi

    log_info "MUTT Partition Manager v2.3"
    log_info "Action: $action"

    validate_config

    case "$action" in
        create)
            create_partitions
            ;;
        cleanup)
            cleanup_partitions
            ;;
        auto)
            create_partitions
            cleanup_partitions
            ;;
        list)
            list_partitions
            ;;
        *)
            log_error "Unknown action: $action"
            exit 1
            ;;
    esac

    log_info "Operation completed successfully"
}

main "$@"
