## MUTT Data Retention Policy - Operator Guide

## Overview

MUTT v2.5 implements automated data retention policies to ensure compliance with data governance requirements while managing storage costs. This guide covers configuration, monitoring, and troubleshooting of the retention system.

## Table of Contents

- [Retention Policies](#retention-policies)
- [Configuration](#configuration)
- [Deployment](#deployment)
- [Monitoring](#monitoring)
- [Troubleshooting](#troubleshooting)
- [Compliance](#compliance)

---

## Retention Policies

### Default Retention Periods

| Data Type | Default Retention | Minimum Recommended | Purpose |
|-----------|------------------|---------------------|---------|
| **Configuration Audit Logs** | 365 days | 365 days | Compliance, change tracking |
| **Event Audit Logs** | 90 days | 30 days | Operational history, debugging |
| **Metrics Data** | 90 days | 30 days | Performance analysis |
| **DLQ Messages** | 30 days | 7 days | Failed message investigation |

### Data Types Explained

**Configuration Audit Logs** (`config_audit_log` table)
- Records all CRUD operations on alert rules, dynamic config, etc.
- Used for compliance audits and change tracking
- Required for SOX, GDPR, and other compliance frameworks
- **Recommendation:** Retain for at least 1 year

**Event Audit Logs** (`event_audit_log` table)
- Records alert processing events, forwarding attempts, enrichment
- Used for debugging and operational analysis
- Grows quickly with high alert volumes
- **Recommendation:** 30-90 days based on troubleshooting needs

**DLQ Messages** (Redis lists: `mutt:dlq:alerter`, `mutt:dlq:dead`)
- Failed alerts that couldn't be processed or forwarded (stored in Redis)
- Include error details and original message (JSON with `failed_at` timestamp)
- Can be replayed after fixing issues by the Remediation service
- **Recommendation:** 7-30 days for investigation window

---

## Configuration

### Environment Variables

Set these in your Kubernetes ConfigMap, Deployment, or CronJob:

```yaml
# Enable/disable retention enforcement
RETENTION_ENABLED=true

# Dry-run mode (log what would be deleted without deleting)
RETENTION_DRY_RUN=false

# Retention periods (days)
RETENTION_AUDIT_DAYS=365        # Configuration audit logs
RETENTION_EVENT_AUDIT_DAYS=90   # Event audit logs (PostgreSQL)
RETENTION_METRICS_DAYS=90       # Prometheus metrics
RETENTION_DLQ_DAYS=30           # Dead letter queue (Redis)

# Cleanup batch size (records per transaction)
RETENTION_CLEANUP_BATCH_SIZE=1000
```

### Configuration File

Alternatively, use the [config/environment.py](../config/environment.py) file:

```python
from config.environment import get_retention_config

config = get_retention_config()
print(config['audit_days'])  # 365
```

### Validation

Run validation to check for configuration issues:

```bash
python config/environment.py
```

**Output:**
```
MUTT v2.5 Configuration
============================================================

Retention Policies:
  enabled: True
  dry_run: False
  audit_days: 365
  event_audit_days: 90
  dlq_days: 30
  batch_size: 1000

Validation:
  WARNING: DLQ retention (7 days) is very short. Consider at least 7 days for troubleshooting
```

---

## Deployment

### Kubernetes CronJob

Deploy the retention cleanup as a Kubernetes CronJob:

```bash
# Apply the CronJob manifest
kubectl apply -f k8s/retention-cleanup-cronjob.yaml

# Verify deployment
kubectl get cronjobs -n mutt
```

**CronJob Schedule:**
- **Default:** Daily at 2 AM (`0 2 * * *`)
- **Every 6 hours:** `0 */6 * * *`
- **Weekly:** `0 0 * * 0` (Sunday at midnight)

### Manual Execution

Run cleanup manually for testing:

```bash
# Dry-run (no actual deletion)
kubectl create job --from=cronjob/retention-cleanup \
  retention-cleanup-manual-$(date +%s) -n mutt

# Watch logs
kubectl logs -f -n mutt -l job-name=retention-cleanup-manual-XXXXXXX
```

### Docker Container

Build and run the retention cleanup container:

```bash
# Build
docker build -t mutt/retention:v2.5 -f Dockerfile.retention .

# Run with environment variables
docker run --rm \
  -e DB_HOST=postgres \
  -e DB_PORT=5432 \
  -e DB_NAME=mutt \
  -e DB_USER=mutt \
  -e DB_PASSWORD=secret \
  -e RETENTION_DRY_RUN=true \
  mutt/retention:v2.5
```

### Standalone Script

Run the cleanup script directly:

```bash
# Set environment variables
export DB_HOST=localhost
export DB_PORT=5432
export DB_NAME=mutt
export DB_USER=mutt
export DB_PASSWORD=mutt
export RETENTION_DRY_RUN=false

# Run cleanup
python scripts/retention_cleanup.py
```

---

## Monitoring

### Prometheus Metrics

The retention cleanup exposes metrics via node_exporter textfile collector:

**Available Metrics:**

```promql
# Total records deleted by type
mutt_retention_cleanup_records_deleted_total{type="config_audit"}
mutt_retention_cleanup_records_deleted_total{type="event_audit"}
mutt_retention_cleanup_records_deleted_total{type="dlq"}

# Configured retention periods
mutt_retention_policy_days{type="config_audit"}
mutt_retention_policy_days{type="event_audit"}
mutt_retention_policy_days{type="dlq"}

# Last successful run timestamp
mutt_retention_cleanup_last_run_timestamp_seconds
```

### DLQ Retention (Redis)

DLQ items are stored in Redis lists:
- `ALERTER_DLQ_NAME` (default: `mutt:dlq:alerter`)
- `DEAD_LETTER_QUEUE` (default: `mutt:dlq:dead`)

The cleanup script inspects the oldest item in each list and removes items whose
timestamp (`failed_at` or `timestamp`) is older than the configured retention.
Items without a timestamp are skipped for safety.

Runbook:
- To flush DLQs manually: `redis-cli DEL mutt:dlq:alerter mutt:dlq:dead`
- To inspect tail message: `redis-cli LINDEX mutt:dlq:alerter -1`

**Example Queries:**

```promql
# Records deleted in last 24 hours
increase(mutt_retention_cleanup_records_deleted_total[24h])

# Time since last cleanup (minutes)
(time() - mutt_retention_cleanup_last_run_timestamp_seconds) / 60

# Deletion rate (records/sec)
rate(mutt_retention_cleanup_records_deleted_total[5m])
```

### Grafana Dashboard

Create a Grafana dashboard with these panels:

1. **Last Cleanup Time** (Stat panel)
   ```promql
   time() - mutt_retention_cleanup_last_run_timestamp_seconds
   ```

2. **Records Deleted (24h)** (Bar gauge)
   ```promql
   increase(mutt_retention_cleanup_records_deleted_total[24h])
   ```

3. **Deletion Rate** (Graph)
   ```promql
   rate(mutt_retention_cleanup_records_deleted_total[5m])
   ```

4. **Retention Policy Status** (Table)
   ```promql
   mutt_retention_policy_days
   ```

### Alerts

Deploy Prometheus alerts from [docs/prometheus/retention-rules.yml](../docs/prometheus/retention-rules.yml):

```bash
kubectl create configmap prometheus-retention-rules \
  --from-file=docs/prometheus/retention-rules.yml \
  -n monitoring
```

**Key Alerts:**
- `RetentionCleanupStale` - Cleanup hasn't run in 25+ hours
- `RetentionCleanupFailing` - Job is failing
- `RetentionDeletionRateHigh` - Abnormally high deletion rate
- `RetentionPolicyExpiring` - Data approaching retention limit

---

## Troubleshooting

### Cleanup Not Running

**Problem:** CronJob exists but jobs aren't being created.

**Check:**
```bash
# View CronJob status
kubectl get cronjob retention-cleanup -n mutt -o yaml

# Check events
kubectl describe cronjob retention-cleanup -n mutt

# View recent jobs
kubectl get jobs -n mutt -l app=retention-cleanup
```

**Common Causes:**
- CronJob suspended (`spec.suspend: true`)
- Schedule syntax error
- `startingDeadlineSeconds` too short
- Namespace or RBAC issues

**Fix:**
```bash
# Resume suspended CronJob
kubectl patch cronjob retention-cleanup -n mutt \
  -p '{"spec":{"suspend":false}}'

# Trigger manual job
kubectl create job --from=cronjob/retention-cleanup \
  retention-test -n mutt
```

### Job Failing

**Problem:** Job pods are failing or erroring.

**Check:**
```bash
# View job status
kubectl get jobs -n mutt -l app=retention-cleanup

# View pod logs
kubectl logs -n mutt -l app=retention-cleanup --tail=100

# Describe pod for events
kubectl describe pod -n mutt -l app=retention-cleanup
```

**Common Errors:**

**Database Connection Failed:**
```
psycopg2.OperationalError: could not connect to server
```
**Fix:** Check database credentials in secrets:
```bash
kubectl get secret mutt-db-secret -n mutt -o yaml
```

**Permission Denied:**
```
ERROR: permission denied for table config_audit_log
```
**Fix:** Grant DELETE permission to database user:
```sql
GRANT DELETE ON config_audit_log, event_audit_log TO mutt;
```

**Out of Memory:**
```
OOMKilled
```
**Fix:** Increase memory limits in CronJob manifest or reduce batch size:
```yaml
env:
- name: RETENTION_CLEANUP_BATCH_SIZE
  value: "500"  # Reduce from 1000
```

### No Data Being Deleted

**Problem:** Cleanup runs successfully but deletes 0 records.

**Check:**
```bash
# View cleanup logs
kubectl logs -n mutt -l app=retention-cleanup --tail=50 | grep "records deleted"

# Check oldest records in database
psql -h $DB_HOST -U mutt -d mutt -c \
  "SELECT MIN(changed_at) as oldest FROM config_audit_log;"
```

**Possible Reasons:**
1. **No old data:** All data is within retention period
2. **Dry-run enabled:** `RETENTION_DRY_RUN=true`
3. **Retention disabled:** `RETENTION_ENABLED=false`
4. **Wrong cutoff date:** Retention period too long

**Verify:**
```bash
# Check configuration
kubectl get cronjob retention-cleanup -n mutt \
  -o jsonpath='{.spec.jobTemplate.spec.template.spec.containers[0].env}'
```

### High Deletion Rate

**Problem:** Retention cleanup is deleting large volumes of data.

**Alert:** `RetentionDeletionRateHigh`

**Investigation:**
```bash
# Check deletion volume
kubectl logs -n mutt -l app=retention-cleanup | grep "Deleted"

# Query database for data volume
psql -h $DB_HOST -U mutt -d mutt <<EOF
SELECT
  COUNT(*) as total_records,
  MIN(changed_at) as oldest,
  MAX(changed_at) as newest
FROM config_audit_log;
EOF
```

**Causes:**
- Data accumulation due to missed cleanup runs
- Retention period recently shortened
- High alert volume generating lots of audit logs

**Resolution:**
1. Verify retention configuration is correct
2. Increase cleanup frequency if needed
3. Consider archiving data before deletion
4. Review alert volume and tuning

---

## Compliance

### Audit Requirements

**Configuration Audit Logs (365 days minimum):**
- Required for compliance frameworks (SOX, GDPR, HIPAA)
- Must capture: who, what, when, why
- Cannot be modified after creation
- Must be available for audits

**Event Audit Logs (30-90 days):**
- Operational troubleshooting and debugging
- Not typically required for compliance
- Can be shortened to reduce storage costs

### Data Retention Reports

Generate compliance reports:

```bash
# Records retained by type
kubectl exec -it -n mutt deployment/webui -- \
  psql -U mutt -d mutt <<EOF
SELECT
  'config_audit' as type,
  COUNT(*) as total_records,
  MIN(changed_at) as oldest_record,
  MAX(changed_at) as newest_record,
  EXTRACT(DAY FROM NOW() - MIN(changed_at)) as retention_days
FROM config_audit_log
UNION ALL
SELECT
  'event_audit' as type,
  COUNT(*),
  MIN(event_timestamp),
  MAX(event_timestamp),
  EXTRACT(DAY FROM NOW() - MIN(event_timestamp))
FROM event_audit_log;
EOF
```

### Archival Strategy

For long-term compliance (7+ years), consider archiving before deletion:

**Option 1: Database Archive Table**
```sql
CREATE TABLE config_audit_log_archive AS
SELECT * FROM config_audit_log
WHERE changed_at < NOW() - INTERVAL '365 days';
```

**Option 2: Export to Cold Storage**
```bash
# Export to JSON
pg_dump -h $DB_HOST -U mutt -d mutt \
  --table=config_audit_log \
  --data-only --column-inserts \
  > audit_archive_$(date +%Y-%m-%d).sql

# Compress and upload to S3
gzip audit_archive_*.sql
aws s3 cp audit_archive_*.sql.gz s3://mutt-archives/audit/
```

**Option 3: Automated Archival Script**
Add archival step to retention cleanup script before deletion.

### Legal Hold

To preserve data for legal/audit purposes:

**Temporarily Disable Retention:**
```bash
kubectl set env cronjob/retention-cleanup -n mutt \
  RETENTION_ENABLED=false
```

**Tag Specific Records:**
```sql
ALTER TABLE config_audit_log ADD COLUMN legal_hold BOOLEAN DEFAULT FALSE;
UPDATE config_audit_log SET legal_hold = TRUE
WHERE changed_at BETWEEN '2025-01-01' AND '2025-12-31';
```

**Modify Cleanup Query:**
Update retention script to skip legal hold records:
```sql
DELETE FROM config_audit_log
WHERE changed_at < %s AND legal_hold = FALSE
```

---

## Best Practices

### Configuration

1. **Start with defaults:** Use recommended retention periods
2. **Enable dry-run first:** Test with `RETENTION_DRY_RUN=true`
3. **Monitor closely:** Watch metrics after enabling
4. **Validate configuration:** Run validation before deploying

### Operational

1. **Schedule during off-hours:** Run cleanup at low-traffic times (2-4 AM)
2. **Use batch deletion:** Keep batch size at 1000 or less
3. **Monitor database load:** Watch for long-running transactions
4. **Set resource limits:** Prevent cleanup from impacting services

### Compliance

1. **Document retention policies:** Maintain written policies
2. **Regular audits:** Verify retention enforcement quarterly
3. **Archive before deletion:** For compliance > 1 year
4. **Test restore procedures:** Ensure archived data is recoverable

### Monitoring

1. **Alert on missed runs:** Set up `RetentionCleanupStale` alert
2. **Track deletion rates:** Monitor for anomalies
3. **Dashboard visibility:** Include retention status in main dashboard
4. **Regular reviews:** Check retention metrics weekly

---

## Reference

### Configuration Files
- [config/environment.py](../config/environment.py) - Environment configuration
- [scripts/retention_cleanup.py](../scripts/retention_cleanup.py) - Cleanup script
- [k8s/retention-cleanup-cronjob.yaml](../k8s/retention-cleanup-cronjob.yaml) - Kubernetes CronJob

### Monitoring
- [docs/prometheus/retention-rules.yml](../docs/prometheus/retention-rules.yml) - Prometheus rules
- [Grafana Dashboard](#grafana-dashboard) - Retention dashboard

### Database Schema
```sql
-- Configuration audit log
CREATE TABLE config_audit_log (
  id SERIAL PRIMARY KEY,
  changed_at TIMESTAMP NOT NULL,
  changed_by VARCHAR(100) NOT NULL,
  operation VARCHAR(10) NOT NULL,
  table_name VARCHAR(100) NOT NULL,
  record_id INTEGER NOT NULL,
  old_values JSONB,
  new_values JSONB,
  reason TEXT,
  correlation_id VARCHAR(100)
);

CREATE INDEX idx_config_audit_changed_at ON config_audit_log(changed_at);
```

### Support

For issues or questions:
- Check logs: `kubectl logs -n mutt -l app=retention-cleanup`
- Review alerts: Prometheus alerts dashboard
- Contact: MUTT Operations Team

---

**Last Updated:** 2025-11-10
**Version:** 2.5.0
