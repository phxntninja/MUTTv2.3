# MUTT v2.5 - Backup & Recovery Guide

**Target Audience:** System Administrators, DevOps Engineers, Disaster Recovery Coordinators
**Priority Level:** P2 (High)
**Last Updated:** 2025-11-10

---

## Table of Contents

1. [Overview](#overview)
2. [Backup Strategy](#backup-strategy)
3. [What to Back Up](#what-to-back-up)
4. [Backup Procedures](#backup-procedures)
5. [Restoration Procedures](#restoration-procedures)
6. [Disaster Recovery Scenarios](#disaster-recovery-scenarios)
7. [Backup Testing and Validation](#backup-testing-and-validation)
8. [Retention Policies](#retention-policies)
9. [Troubleshooting](#troubleshooting)

---

## Overview

MUTT v2.5 backup and recovery procedures ensure business continuity and data protection. This guide covers backup strategies, procedures, and recovery scenarios for all MUTT components.

### Backup Objectives

- **Recovery Time Objective (RTO)**: < 1 hour for critical services
- **Recovery Point Objective (RPO)**: < 24 hours for configuration/database
- **Data Integrity**: 100% - all backups must be restorable and validated
- **Compliance**: Meet SOX/GDPR retention requirements (365 days for audit logs)

### Backup Scope

| Component | Backup Type | Frequency | Retention | Priority |
|-----------|-------------|-----------|-----------|----------|
| **PostgreSQL** | Full + Incremental | Daily + Hourly | 30 days | Critical |
| **Redis** | Snapshot (RDB) | Every 6 hours | 7 days | High |
| **Configuration Files** | File backup | Daily | 90 days | Critical |
| **Vault Secrets** | Encrypted backup | Weekly | 90 days | Critical |
| **Application Code** | Git repository | On commit | Indefinite | Medium |
| **Logs** | Archive | Daily | 90 days | Medium |
| **Prometheus Metrics** | Snapshot | Weekly | 30 days | Low |

---

## Backup Strategy

### 3-2-1 Backup Rule

MUTT follows the industry-standard 3-2-1 backup rule:

- **3 Copies**: Production data + 2 backup copies
- **2 Media Types**: Local disk + Remote storage (S3, NAS, tape)
- **1 Offsite**: At least one copy offsite for disaster recovery

### Backup Architecture

```
┌──────────────────────────────────────────────────┐
│         MUTT Production Environment              │
│                                                  │
│  PostgreSQL    Redis    Config Files    Vault   │
└─────────┬─────────┬────────┬─────────┬──────────┘
          │         │        │         │
          │         │        │         │
          v         v        v         v
┌──────────────────────────────────────────────────┐
│            Local Backup Storage                  │
│         /var/backups/mutt/                       │
│                                                  │
│  - postgres/       (daily full + hourly incr)   │
│  - redis/          (6-hourly RDB snapshots)     │
│  - config/         (daily config backups)       │
│  - vault/          (weekly encrypted backups)   │
│  - logs/           (daily log archives)         │
└──────────┬───────────────────────────────────────┘
           │
           │ (Rsync/S3 sync every 6 hours)
           │
           v
┌──────────────────────────────────────────────────┐
│       Remote Backup Storage (Offsite)            │
│                                                  │
│  - S3 Bucket: s3://mutt-backups-prod/           │
│  - NAS: //backup-nas.internal/mutt/             │
│  - Retention: Automated lifecycle policies      │
└──────────────────────────────────────────────────┘
```

---

## What to Back Up

### PostgreSQL Database

**Critical Tables:**
- `alert_rules` - Alert matching rules
- `dev_hosts` - Development host exemptions
- `device_teams` - Team ownership mappings
- `config_audit_log` - Configuration change audit trail
- `event_audit_log` - Event processing audit trail

**Why Critical:**
- Contains business logic for alert processing
- Required for compliance (audit logs)
- Cannot be regenerated if lost

**Backup Method:** `pg_dump` (full) + WAL archiving (incremental)

---

### Redis Data

**Critical Keys:**
- `mutt:config:*` - Dynamic configuration
- `mutt:ingest_queue` - In-flight events (transient, low priority)
- `mutt:alert_queue` - In-flight alerts (transient, low priority)
- `mutt:dlq:*` - Dead letter queues (high priority)
- `mutt:unhandled:*` - Unhandled event tracking

**Why Critical:**
- Dynamic configuration required for zero-downtime operations
- DLQs contain failed messages that need investigation/replay

**Backup Method:** RDB snapshots + AOF (append-only file)

---

### Configuration Files

**Critical Files:**
- `/etc/mutt/mutt.env` - Environment variables
- `/etc/mutt/vault_secret_id` - Vault authentication token
- `/etc/mutt/certs/` - TLS certificates
- `/etc/systemd/system/mutt-*.service` - systemd unit files
- `/etc/prometheus/prometheus.yml` - Prometheus configuration
- `/etc/prometheus/alerts-v25.yml` - Alert rules
- `/etc/alertmanager/alertmanager.yml` - Alertmanager configuration

**Why Critical:**
- Required to restore services to operational state
- Contains infrastructure connection details
- Certificates required for TLS communication

**Backup Method:** File-based tarball

---

### HashiCorp Vault Secrets

**Critical Secrets:**
- API keys (INGEST_API_KEY, WEBUI_API_KEY, MOOG_API_KEY)
- Passwords (REDIS_PASS, DB_PASS)
- TLS client certificates

**Why Critical:**
- Services cannot start without valid secrets
- Regenerating secrets requires coordination with external systems

**Backup Method:** Vault snapshot (encrypted)

---

### Application Code

**What to Back Up:**
- `/opt/mutt/` - Application code and Python virtual environment
- Git repository (primary backup)

**Why Medium Priority:**
- Can be redeployed from Git repository
- Virtual environment can be recreated from `requirements.txt`

**Backup Method:** Git repository + optional tarball

---

### Logs

**Logs to Archive:**
- `/var/log/mutt/*.log` - Service logs
- `/var/lib/prometheus/` - Prometheus metrics (optional)

**Why Medium Priority:**
- Useful for historical analysis and forensics
- Not required for service restoration

**Backup Method:** Compressed tarball

---

## Backup Procedures

### Automated Backup Script

**Script:** `/usr/local/bin/backup_mutt.sh`

```bash
#!/bin/bash
# MUTT v2.5 - Automated Backup Script
# Run via cron: 0 2 * * * /usr/local/bin/backup_mutt.sh

set -e

BACKUP_ROOT="/var/backups/mutt"
TIMESTAMP=$(date +%Y%m%d_%H%M%S)
DATE_DIR=$(date +%Y/%m/%d)
LOG_FILE="/var/log/mutt/backups.log"

# Logging function
log() {
    echo "[$(date +'%Y-%m-%d %H:%M:%S')] $1" | tee -a "$LOG_FILE"
}

log "Starting MUTT backup process"

# Create backup directories
mkdir -p "$BACKUP_ROOT/postgres/$DATE_DIR"
mkdir -p "$BACKUP_ROOT/redis/$DATE_DIR"
mkdir -p "$BACKUP_ROOT/config/$DATE_DIR"
mkdir -p "$BACKUP_ROOT/vault/$DATE_DIR"
mkdir -p "$BACKUP_ROOT/logs/$DATE_DIR"

# 1. Backup PostgreSQL
log "Backing up PostgreSQL..."
pg_dump -h localhost -U mutt_user -d mutt \
  -F c \
  -f "$BACKUP_ROOT/postgres/$DATE_DIR/mutt_postgres_$TIMESTAMP.dump"

if [ $? -eq 0 ]; then
    log "✅ PostgreSQL backup successful"
else
    log "❌ PostgreSQL backup failed"
    exit 1
fi

# 2. Backup Redis (RDB snapshot)
log "Backing up Redis..."
redis-cli BGSAVE
sleep 5  # Wait for background save to complete

# Copy RDB file
cp /var/lib/redis/dump.rdb "$BACKUP_ROOT/redis/$DATE_DIR/dump_$TIMESTAMP.rdb"

if [ $? -eq 0 ]; then
    log "✅ Redis backup successful"
else
    log "❌ Redis backup failed"
fi

# 3. Backup Configuration Files
log "Backing up configuration files..."
tar -czf "$BACKUP_ROOT/config/$DATE_DIR/mutt_config_$TIMESTAMP.tar.gz" \
  -C / \
  etc/mutt \
  etc/systemd/system/mutt-*.service \
  etc/prometheus/prometheus.yml \
  etc/prometheus/alerts-v25.yml \
  etc/prometheus/recording-rules-v25.yml \
  etc/alertmanager/alertmanager.yml

if [ $? -eq 0 ]; then
    log "✅ Configuration backup successful"
else
    log "❌ Configuration backup failed"
fi

# 4. Backup Vault Secrets (encrypted)
log "Backing up Vault secrets..."
export VAULT_ADDR=$(grep VAULT_ADDR /etc/mutt/mutt.env | cut -d= -f2)
export VAULT_TOKEN=$(cat /etc/mutt/vault_secret_id)

# Take Vault snapshot
vault operator raft snapshot save "$BACKUP_ROOT/vault/$DATE_DIR/vault_snapshot_$TIMESTAMP.snap" 2>/dev/null || \
  vault kv get -format=json secret/mutt/prod > "$BACKUP_ROOT/vault/$DATE_DIR/vault_secrets_$TIMESTAMP.json"

if [ $? -eq 0 ]; then
    # Encrypt with GPG
    gpg --symmetric --cipher-algo AES256 \
      --output "$BACKUP_ROOT/vault/$DATE_DIR/vault_secrets_$TIMESTAMP.json.gpg" \
      "$BACKUP_ROOT/vault/$DATE_DIR/vault_secrets_$TIMESTAMP.json"
    rm "$BACKUP_ROOT/vault/$DATE_DIR/vault_secrets_$TIMESTAMP.json"  # Remove unencrypted
    log "✅ Vault backup successful (encrypted)"
else
    log "⚠️  Vault backup skipped (optional)"
fi

# 5. Backup Logs
log "Archiving logs..."
tar -czf "$BACKUP_ROOT/logs/$DATE_DIR/mutt_logs_$TIMESTAMP.tar.gz" \
  -C /var/log/mutt \
  . 2>/dev/null || log "⚠️  Log archiving skipped (optional)"

# 6. Sync to Remote Storage (S3)
log "Syncing to remote storage..."
if command -v aws &> /dev/null; then
    aws s3 sync "$BACKUP_ROOT/" "s3://mutt-backups-prod/$(hostname)/" \
      --storage-class STANDARD_IA \
      --exclude "*.log"
    log "✅ Remote sync successful"
else
    log "⚠️  AWS CLI not found, skipping remote sync"
fi

# 7. Cleanup old backups (keep 30 days locally)
log "Cleaning up old backups..."
find "$BACKUP_ROOT/postgres/" -type f -mtime +30 -delete
find "$BACKUP_ROOT/redis/" -type f -mtime +7 -delete
find "$BACKUP_ROOT/config/" -type f -mtime +90 -delete
find "$BACKUP_ROOT/vault/" -type f -mtime +90 -delete
find "$BACKUP_ROOT/logs/" -type f -mtime +90 -delete

log "Backup process completed successfully"
log "Backup location: $BACKUP_ROOT/$DATE_DIR"

# Send notification (optional)
# curl -X POST https://hooks.slack.com/services/YOUR/SLACK/WEBHOOK \
#   -d "{\"text\":\"MUTT backup completed successfully on $(hostname)\"}"
```

**Make executable:**
```bash
sudo chmod +x /usr/local/bin/backup_mutt.sh
```

---

### Schedule Automated Backups

Add to `/etc/crontab`:

```bash
# MUTT Automated Backups

# Full backup daily at 2 AM
0 2 * * * root /usr/local/bin/backup_mutt.sh >> /var/log/mutt/backups.log 2>&1

# Redis snapshot every 6 hours
0 */6 * * * root redis-cli BGSAVE && cp /var/lib/redis/dump.rdb /var/backups/mutt/redis/dump_$(date +\%Y\%m\%d_\%H\%M\%S).rdb

# PostgreSQL incremental backup (WAL archiving) every hour
0 * * * * postgres /usr/local/bin/archive_postgres_wal.sh
```

---

### Manual Backup Procedures

**On-Demand Full Backup:**

```bash
# Run backup script manually
sudo /usr/local/bin/backup_mutt.sh

# Verify backup created
ls -lh /var/backups/mutt/*/$(date +%Y/%m/%d)/

# Test restoration (in separate environment)
# See Restoration Procedures section
```

**Pre-Upgrade Backup:**

```bash
# Before any major upgrade, take full backup
BACKUP_DIR="/var/backups/mutt/pre-upgrade-$(date +%Y%m%d)"
mkdir -p "$BACKUP_DIR"

# PostgreSQL
pg_dump -h localhost -U mutt_user -d mutt -F c -f "$BACKUP_DIR/postgres.dump"

# Redis
redis-cli SAVE
cp /var/lib/redis/dump.rdb "$BACKUP_DIR/redis_dump.rdb"

# Configuration
tar -czf "$BACKUP_DIR/config.tar.gz" /etc/mutt /etc/systemd/system/mutt-*.service

# Vault
vault kv get -format=json secret/mutt/prod > "$BACKUP_DIR/vault_secrets.json"
gpg --symmetric --cipher-algo AES256 "$BACKUP_DIR/vault_secrets.json"
rm "$BACKUP_DIR/vault_secrets.json"

echo "Pre-upgrade backup complete: $BACKUP_DIR"
```

---

## Restoration Procedures

### Restore PostgreSQL Database

**Scenario:** PostgreSQL database corrupted or deleted

**Procedure:**

```bash
# 1. Stop all MUTT services
sudo systemctl stop mutt-*

# 2. Drop and recreate database (if needed)
sudo -u postgres psql <<EOF
DROP DATABASE IF EXISTS mutt;
CREATE DATABASE mutt OWNER mutt_user;
EOF

# 3. Restore from backup
BACKUP_FILE="/var/backups/mutt/postgres/2025/11/10/mutt_postgres_20251110_020000.dump"

pg_restore -h localhost -U mutt_user -d mutt \
  --clean \
  --if-exists \
  --no-owner \
  --no-privileges \
  "$BACKUP_FILE"

# 4. Verify restoration
sudo -u postgres psql -U mutt_user -d mutt <<EOF
SELECT count(*) FROM alert_rules;
SELECT count(*) FROM dev_hosts;
SELECT count(*) FROM config_audit_log;
EOF

# 5. Restart services
sudo systemctl start mutt-*

# 6. Verify services healthy
/usr/local/bin/mutt-health-check.sh
```

**Expected Output:**
```
alert_rules: 50+ rows
dev_hosts: 10+ rows
config_audit_log: 100+ rows
All services: healthy
```

---

### Restore Redis Data

**Scenario:** Redis data lost or corrupted

**Procedure:**

```bash
# 1. Stop Redis
sudo systemctl stop redis

# 2. Locate backup file
BACKUP_FILE="/var/backups/mutt/redis/2025/11/10/dump_20251110_020000.rdb"

# 3. Replace Redis RDB file
sudo cp "$BACKUP_FILE" /var/lib/redis/dump.rdb
sudo chown redis:redis /var/lib/redis/dump.rdb

# 4. Start Redis
sudo systemctl start redis

# 5. Verify data restored
redis-cli DBSIZE
redis-cli KEYS "mutt:config:*"

# 6. Restart MUTT services to reload config
sudo systemctl restart mutt-*
```

**Expected Output:**
```
DBSIZE: 1000+ keys
mutt:config:* keys present
```

---

### Restore Configuration Files

**Scenario:** Configuration files deleted or misconfigured

**Procedure:**

```bash
# 1. Locate backup
BACKUP_FILE="/var/backups/mutt/config/2025/11/10/mutt_config_20251110_020000.tar.gz"

# 2. Extract to temporary location
mkdir -p /tmp/mutt_restore
tar -xzf "$BACKUP_FILE" -C /tmp/mutt_restore

# 3. Stop services
sudo systemctl stop mutt-*

# 4. Restore configuration files
sudo cp -r /tmp/mutt_restore/etc/mutt/* /etc/mutt/
sudo cp /tmp/mutt_restore/etc/systemd/system/mutt-*.service /etc/systemd/system/

# 5. Set proper ownership
sudo chown -R mutt:mutt /etc/mutt
sudo chmod 600 /etc/mutt/vault_secret_id

# 6. Reload systemd and restart services
sudo systemctl daemon-reload
sudo systemctl start mutt-*

# 7. Verify
/usr/local/bin/validate_mutt_config.sh
```

---

### Restore Vault Secrets

**Scenario:** Vault secrets lost or Vault cluster failure

**Procedure:**

```bash
# 1. Locate encrypted backup
BACKUP_FILE="/var/backups/mutt/vault/2025/11/10/vault_secrets_20251110_020000.json.gpg"

# 2. Decrypt backup
gpg --decrypt "$BACKUP_FILE" > /tmp/vault_secrets.json

# 3. Restore secrets to Vault
export VAULT_ADDR="https://vault.internal:8200"
export VAULT_TOKEN="root-token-or-admin-token"

# Parse JSON and restore each secret
jq -r '.data.data | to_entries[] | "\(.key)=\(.value)"' /tmp/vault_secrets.json | \
  while IFS='=' read -r key value; do
    vault kv patch secret/mutt/prod "$key=$value"
  done

# 4. Verify secrets restored
vault kv get secret/mutt/prod

# 5. Securely delete decrypted file
shred -u /tmp/vault_secrets.json

# 6. Restart MUTT services
sudo systemctl restart mutt-*
```

---

### Full System Restoration

**Scenario:** Complete server failure, restore to new server

**Procedure:**

**Step 1: Provision New Server**

```bash
# Install RHEL 8.x
# Set hostname
sudo hostnamectl set-hostname mutt-prod-new

# Install base dependencies
sudo yum update -y
sudo yum install -y python39 redis postgresql-server
```

**Step 2: Restore Application Code**

```bash
# Clone from Git
cd /opt
sudo git clone https://github.com/your-org/mutt.git
cd mutt

# Create virtual environment
python3.9 -m venv venv
source venv/bin/activate
pip install -r requirements.txt
```

**Step 3: Restore Configuration**

```bash
# Copy from backup server or S3
aws s3 cp s3://mutt-backups-prod/mutt-prod-old/config/latest.tar.gz /tmp/
tar -xzf /tmp/latest.tar.gz -C /

# Or rsync from backup server
rsync -avz backup-server:/var/backups/mutt/config/latest/ /etc/mutt/
```

**Step 4: Restore PostgreSQL**

```bash
# Initialize PostgreSQL
sudo postgresql-setup --initdb
sudo systemctl start postgresql

# Create database and user
sudo -u postgres psql <<EOF
CREATE DATABASE mutt;
CREATE USER mutt_user WITH PASSWORD 'password';
GRANT ALL PRIVILEGES ON DATABASE mutt TO mutt_user;
EOF

# Restore data
pg_restore -h localhost -U mutt_user -d mutt /var/backups/mutt/postgres/latest.dump
```

**Step 5: Restore Redis**

```bash
# Copy RDB file
sudo cp /var/backups/mutt/redis/latest.rdb /var/lib/redis/dump.rdb
sudo chown redis:redis /var/lib/redis/dump.rdb

# Start Redis
sudo systemctl start redis
```

**Step 6: Restore Vault Secrets**

```bash
# Decrypt and restore (see Restore Vault Secrets procedure above)
```

**Step 7: Install systemd Services**

```bash
# Copy service files
sudo cp /etc/mutt/mutt-*.service /etc/systemd/system/

# Reload systemd
sudo systemctl daemon-reload

# Enable services
sudo systemctl enable mutt-ingestor mutt-alerter mutt-moog-forwarder mutt-remediation mutt-webui
```

**Step 8: Start Services**

```bash
# Start all services
sudo systemctl start mutt-*

# Verify health
/usr/local/bin/mutt-health-check.sh
```

**Step 9: Update DNS/Load Balancer**

```bash
# Update DNS A record to point to new server IP
# OR update load balancer backend pool

# Verify external connectivity
curl http://mutt-prod.internal:8080/health
```

**Estimated Time:** 2-4 hours (depending on data size)

---

## Disaster Recovery Scenarios

### Scenario 1: PostgreSQL Corruption

**Symptoms:**
- Database errors in logs
- Services cannot read rules
- Data integrity violations

**Recovery Steps:**
1. Stop all MUTT services
2. Assess extent of corruption
3. Restore from most recent backup
4. Replay WAL logs if available (point-in-time recovery)
5. Restart services
6. Verify data integrity

**RTO:** 30 minutes
**RPO:** < 24 hours (last full backup)

---

### Scenario 2: Redis Data Loss

**Symptoms:**
- Dynamic configuration reset to defaults
- DLQ messages lost
- Services using fallback values

**Recovery Steps:**
1. Stop Redis
2. Restore RDB snapshot
3. Restart Redis
4. Verify key counts
5. Restart MUTT services

**RTO:** 15 minutes
**RPO:** < 6 hours (last Redis snapshot)

---

### Scenario 3: Complete Server Failure

**Symptoms:**
- Server unresponsive
- Hardware failure
- OS corruption

**Recovery Steps:**
1. Provision new server
2. Follow Full System Restoration procedure (see above)
3. Update DNS/load balancer
4. Verify all services healthy

**RTO:** 2-4 hours
**RPO:** < 24 hours

---

### Scenario 4: Vault Secrets Lost

**Symptoms:**
- Services cannot authenticate to Vault
- "403 Forbidden" errors
- Missing API keys

**Recovery Steps:**
1. Restore Vault snapshot or secrets from encrypted backup
2. Update Vault token in `/etc/mutt/vault_secret_id`
3. Restart MUTT services
4. Verify secret retrieval

**RTO:** 20 minutes
**RPO:** < 7 days (weekly Vault backup)

---

### Scenario 5: Accidental Configuration Change

**Symptoms:**
- Services behaving unexpectedly after configuration change
- Incorrect rule matching
- Performance degradation

**Recovery Steps:**
1. Identify what changed (check audit logs)
2. Restore configuration from backup
3. Restart affected services
4. Verify correct behavior

**RTO:** 10 minutes
**RPO:** < 24 hours

---

## Backup Testing and Validation

### Monthly Backup Test

**Procedure:**

```bash
#!/bin/bash
# Monthly Backup Validation Test
# Run on separate test environment

BACKUP_DATE="2025-11-10"
TEST_ENV="mutt-test"

echo "Testing MUTT backup restoration for $BACKUP_DATE"

# 1. Test PostgreSQL restore
echo "Testing PostgreSQL restore..."
pg_restore -h localhost -U mutt_user -d mutt_test \
  /var/backups/mutt/postgres/${BACKUP_DATE}/mutt_postgres_*.dump

if [ $? -eq 0 ]; then
    echo "✅ PostgreSQL restore successful"
    # Verify row counts
    psql -U mutt_user -d mutt_test -c "SELECT 'alert_rules', count(*) FROM alert_rules"
else
    echo "❌ PostgreSQL restore failed"
fi

# 2. Test Redis restore
echo "Testing Redis restore..."
redis-cli -h $TEST_ENV FLUSHALL
cp /var/backups/mutt/redis/${BACKUP_DATE}/dump_*.rdb /tmp/test_dump.rdb
redis-cli -h $TEST_ENV SHUTDOWN SAVE
cp /tmp/test_dump.rdb /var/lib/redis-test/dump.rdb
redis-server --dir /var/lib/redis-test &

sleep 5
if redis-cli -h $TEST_ENV PING | grep -q PONG; then
    echo "✅ Redis restore successful"
    redis-cli -h $TEST_ENV DBSIZE
else
    echo "❌ Redis restore failed"
fi

# 3. Test configuration restore
echo "Testing configuration restore..."
tar -tzf /var/backups/mutt/config/${BACKUP_DATE}/mutt_config_*.tar.gz | head -10

if [ $? -eq 0 ]; then
    echo "✅ Configuration backup is readable"
else
    echo "❌ Configuration backup is corrupted"
fi

# 4. Test Vault secrets restore
echo "Testing Vault secrets restore..."
gpg --decrypt /var/backups/mutt/vault/${BACKUP_DATE}/vault_secrets_*.json.gpg > /tmp/vault_test.json 2>/dev/null

if [ $? -eq 0 ]; then
    echo "✅ Vault backup decryption successful"
    jq . /tmp/vault_test.json > /dev/null
    if [ $? -eq 0 ]; then
        echo "✅ Vault backup JSON is valid"
    fi
    shred -u /tmp/vault_test.json
else
    echo "❌ Vault backup decryption failed"
fi

echo "Backup validation test complete"
```

**Schedule:** Run monthly on first Sunday at 3 AM

```bash
# Add to crontab
0 3 1 * 0 root /usr/local/bin/test_mutt_backups.sh >> /var/log/mutt/backup_tests.log 2>&1
```

---

### Backup Integrity Checklist

**Monthly Review:**
- [ ] All backup jobs completed successfully (check logs)
- [ ] Backup files are not corrupted (test restore)
- [ ] Remote backups synced to S3/NAS
- [ ] Retention policies applied correctly
- [ ] Backup sizes are reasonable (check for anomalies)
- [ ] Encryption is working (Vault backups)
- [ ] Sufficient disk space for backups (< 80% used)

**Quarterly Review:**
- [ ] Perform full disaster recovery test (restore to new server)
- [ ] Validate RTO/RPO met in test
- [ ] Update DR documentation if procedures changed
- [ ] Review and update retention policies
- [ ] Test alerting for backup failures

---

## Retention Policies

### Local Retention (On-Server)

| Backup Type | Retention Period | Storage Location |
|-------------|------------------|------------------|
| PostgreSQL Full | 30 days | `/var/backups/mutt/postgres/` |
| PostgreSQL Incremental (WAL) | 7 days | `/var/lib/pgsql/archive/` |
| Redis Snapshots | 7 days | `/var/backups/mutt/redis/` |
| Configuration | 90 days | `/var/backups/mutt/config/` |
| Vault Secrets | 90 days | `/var/backups/mutt/vault/` |
| Logs | 90 days | `/var/backups/mutt/logs/` |

### Remote Retention (S3)

Configure S3 lifecycle policies:

```json
{
  "Rules": [
    {
      "Id": "MoveToGlacierAfter90Days",
      "Status": "Enabled",
      "Prefix": "postgres/",
      "Transitions": [
        {
          "Days": 90,
          "StorageClass": "GLACIER"
        }
      ],
      "Expiration": {
        "Days": 365
      }
    },
    {
      "Id": "DeleteRedisAfter30Days",
      "Status": "Enabled",
      "Prefix": "redis/",
      "Expiration": {
        "Days": 30
      }
    },
    {
      "Id": "RetainConfigFor365Days",
      "Status": "Enabled",
      "Prefix": "config/",
      "Transitions": [
        {
          "Days": 90,
          "StorageClass": "STANDARD_IA"
        }
      ],
      "Expiration": {
        "Days": 365
      }
    }
  ]
}
```

Apply lifecycle policy:
```bash
aws s3api put-bucket-lifecycle-configuration \
  --bucket mutt-backups-prod \
  --lifecycle-configuration file://s3-lifecycle-policy.json
```

---

## Troubleshooting

### Issue: Backup Script Fails

**Symptoms:**
- Backup log shows errors
- Backup files not created

**Diagnosis:**
```bash
# Check backup log
tail -100 /var/log/mutt/backups.log

# Check disk space
df -h /var/backups

# Check permissions
ls -ld /var/backups/mutt
```

**Resolution:**
```bash
# Fix disk space
sudo find /var/backups/mutt -type f -mtime +90 -delete

# Fix permissions
sudo chown -R root:root /var/backups/mutt
sudo chmod 755 /var/backups/mutt

# Retry backup
sudo /usr/local/bin/backup_mutt.sh
```

---

### Issue: PostgreSQL Restore Fails

**Symptoms:**
- `pg_restore` returns errors
- Tables not created

**Diagnosis:**
```bash
# Check backup file integrity
pg_restore --list /var/backups/mutt/postgres/latest.dump

# Check PostgreSQL logs
sudo tail -100 /var/lib/pgsql/data/log/postgresql-*.log
```

**Resolution:**
```bash
# Try older backup
pg_restore -h localhost -U mutt_user -d mutt \
  --clean --if-exists \
  /var/backups/mutt/postgres/previous.dump

# If still failing, restore schema then data separately
pg_restore --schema-only ...
pg_restore --data-only ...
```

---

### Issue: Redis Backup Corrupted

**Symptoms:**
- Redis fails to load RDB file
- Checksum mismatch errors

**Diagnosis:**
```bash
# Verify RDB file
redis-check-rdb /var/backups/mutt/redis/dump_latest.rdb

# Check file size (should be > 0 bytes)
ls -lh /var/backups/mutt/redis/dump_latest.rdb
```

**Resolution:**
```bash
# Use older backup
cp /var/backups/mutt/redis/dump_previous.rdb /var/lib/redis/dump.rdb

# OR reinitialize Redis with empty database
rm /var/lib/redis/dump.rdb
sudo systemctl start redis
# Reinitialize dynamic config manually
python scripts/init_dynamic_config.py
```

---

## Summary

### Backup Checklist

**Daily Tasks:**
- [ ] Verify automated backup ran successfully
- [ ] Check backup log for errors
- [ ] Monitor disk space on backup storage

**Weekly Tasks:**
- [ ] Review backup sizes for anomalies
- [ ] Verify remote sync to S3/NAS completed
- [ ] Check Vault encrypted backups present

**Monthly Tasks:**
- [ ] Test restore of PostgreSQL backup
- [ ] Test restore of Redis backup
- [ ] Verify backup retention policies applied
- [ ] Document any backup failures and resolutions

**Quarterly Tasks:**
- [ ] Perform full disaster recovery test
- [ ] Measure actual RTO/RPO
- [ ] Review and update retention policies
- [ ] Update disaster recovery documentation

---

## Next Steps

For additional operational guidance:

1. **Service Operations**: [SERVICE_OPERATIONS.md](SERVICE_OPERATIONS.md) - Service management, scaling
2. **Troubleshooting**: [TROUBLESHOOTING_GUIDE.md](TROUBLESHOOTING_GUIDE.md) - Problem diagnosis
3. **Configuration Management**: [CONFIG_MANAGEMENT.md](CONFIG_MANAGEMENT.md) - Config, secrets
4. **Monitoring & Alerting**: [MONITORING_ALERTING.md](MONITORING_ALERTING.md) - Prometheus, alerts
5. **Incident Response**: [INCIDENT_RESPONSE.md](INCIDENT_RESPONSE.md) (coming soon) - Incident procedures

---

**Document Metadata:**
- **Version**: 1.0
- **Last Updated**: 2025-11-10
- **Maintainer**: MUTT Operations Team
- **Feedback**: Report issues via internal ticketing system
