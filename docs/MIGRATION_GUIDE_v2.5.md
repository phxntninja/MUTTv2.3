# MUTT v2.5 Migration Guide

**Version:** 2.5.0
**Release Date:** 2025-11-11
**Migration Effort:** Medium (2-4 hours)

This guide walks you through migrating from MUTT v2.3/v2.4 to v2.5.

---

## Table of Contents

1. [Overview](#overview)
2. [Breaking Changes](#breaking-changes)
3. [New Features](#new-features)
4. [Migration Steps](#migration-steps)
5. [Post-Migration Validation](#post-migration-validation)
6. [Rollback Procedure](#rollback-procedure)

---

## Overview

MUTT v2.5 introduces significant improvements in reliability, compliance, and developer experience while maintaining backward compatibility for most configurations.

**Key Changes:**
- Enhanced API versioning with deprecation warnings
- Zero-downtime secret rotation (dual-password support)
- Comprehensive data retention and compliance features
- Circuit breaker state transition metrics
- Developer CLI tool (`muttdev`)
- Architecture Decision Records (ADRs)

**Compatibility:**
- ✅ All v2.3/v2.4 configurations continue to work
- ✅ Existing API endpoints remain functional
- ✅ Database schema is backward compatible
- ⚠️ Some environment variables have new names (old names still work)

---

## Breaking Changes

### 1. API Version Headers

**What Changed:**
All API responses now include version headers.

**Action Required:** None (backward compatible)

**Details:**
- `X-API-Version: 2.5` header added to all responses
- `/api/v1/*` endpoints remain functional but return `X-API-Deprecated: true`
- Recommended: Update clients to use `/api/v2/*` endpoints

**Migration:**
```bash
# Old (still works)
curl http://localhost:8090/api/v1/metrics

# New (recommended)
curl http://localhost:8090/api/v2/metrics
```

### 2. Vault Secret Structure

**What Changed:**
Secrets now support dual-password scheme for zero-downtime rotation.

**Action Required:** Update Vault secrets (optional, backward compatible)

**Old Structure:**
```json
{
  "REDIS_PASS": "current_password",
  "DB_PASS": "current_password"
}
```

**New Structure:**
```json
{
  "REDIS_PASS_CURRENT": "current_password",
  "REDIS_PASS_NEXT": "next_password",
  "DB_PASS_CURRENT": "current_password",
  "DB_PASS_NEXT": "next_password"
}
```

**Migration:**
```bash
# Run vault init script to update secrets
./scripts/vault-init.sh
```

**Note:** Old single-password secrets (`REDIS_PASS`, `DB_PASS`) continue to work.

### 3. Environment Variables

**What Changed:**
New environment variables for retention policies and features.

**Action Required:** Review and set (optional, has defaults)

**New Variables:**
```bash
# Retention Policies (Phase 4.3)
EVENT_RETENTION_DAYS=90                    # Default: 90
EVENT_ARCHIVE_RETENTION_YEARS=7           # Default: 7
CONFIG_AUDIT_RETENTION_DAYS=365           # Default: 365

# Feature Flags
DYNAMIC_CONFIG_ENABLED=true               # Default: true
RETENTION_ENFORCEMENT_ENABLED=true        # Default: true
```

---

## New Features

### 1. Dynamic Configuration (Phase 2.1)

**Feature:** Runtime configuration changes without service restart.

**Setup:**
```bash
# Initialize defaults in Redis
python scripts/init_default_configs.py

# Update config via CLI
muttdev config set cache_reload_interval 600

# Or via Web UI API
curl -X PUT http://localhost:8090/api/v1/config/cache_reload_interval \
  -H "X-API-KEY: your-key" \
  -d '{"value": "600"}'
```

**Benefits:**
- No service downtime for config changes
- Changes propagate across all instances within 5 seconds
- Full audit trail in `config_audit_log` table

### 2. Zero-Downtime Secret Rotation (Phase 2.2)

**Feature:** Rotate secrets without service interruption.

**Procedure:**
```bash
# 1. Add new password to Vault as NEXT
vault kv patch secret/mutt/prod \
  DB_PASS_NEXT="new_password"

# 2. Update database to accept both passwords
psql -c "ALTER USER mutt_app PASSWORD 'new_password';"

# 3. Promote NEXT to CURRENT in Vault
vault kv patch secret/mutt/prod \
  DB_PASS_CURRENT="new_password" \
  DB_PASS_NEXT="newer_password"

# 4. Services automatically reconnect with new password
```

See [Secret Rotation Procedure](SECRET_ROTATION_PROCEDURE.md) for details.

### 3. Data Retention Automation (Phase 4.3)

**Feature:** Automated data archival and deletion for compliance.

**Setup:**
```bash
# Deploy retention CronJob to Kubernetes
kubectl apply -f k8s/retention-cleanup-cronjob.yaml

# Or run manually
python scripts/retention_policy_enforcer.py

# Dry-run to preview
python scripts/retention_policy_enforcer.py --dry-run
```

**Policies:**
- Events: 90 days active, 7 years archive
- Config audits: 365 days
- Automatic enforcement: Daily at 2 AM

### 4. Circuit Breaker Metrics (Phase 3.1.3)

**Feature:** Enhanced circuit breaker observability.

**New Metrics:**
```promql
# Circuit breaker state (0=CLOSED, 1=HALF_OPEN, 2=OPEN)
mutt_circuit_breaker_state{name="moogsoft"}

# Failure count
mutt_circuit_breaker_failures{name="moogsoft"}

# State transitions
mutt_circuit_breaker_state_changes_total{name="moogsoft",from_state="CLOSED",to_state="OPEN"}
```

**Grafana Dashboard:** Import `dashboards/circuit-breaker.json`

### 5. Developer CLI (Phase 5.1)

**Feature:** `muttdev` command-line tool for developers.

**Installation:**
```bash
# Install muttdev CLI
./scripts/install_muttdev.sh

# Verify
muttdev --version
```

**Commands:**
```bash
muttdev setup              # Initialize dev environment
muttdev config list        # View all configs
muttdev logs alerter -f    # Tail service logs
muttdev status             # Check service health
muttdev test --coverage    # Run tests with coverage
muttdev db shell           # Open PostgreSQL shell
```

---

## Migration Steps

### Step 1: Backup Current System

```bash
# Backup database
pg_dump -h localhost -U postgres mutt > mutt_backup_$(date +%Y%m%d).sql

# Backup Redis
redis-cli --rdb /tmp/redis_backup_$(date +%Y%m%d).rdb

# Backup configuration
tar -czf mutt_config_backup_$(date +%Y%m%d).tar.gz \
  .env docker-compose.yml k8s/
```

### Step 2: Update Docker Images

```bash
# Pull new v2.5 images
docker-compose pull

# Or build from source
docker-compose build
```

### Step 3: Update Database Schema

```bash
# Apply v2.5 schema changes
psql -h localhost -U postgres -d mutt -f database/postgres-init.sql

# Verify partition management
python scripts/create_monthly_partitions.py --dry-run
```

### Step 4: Initialize Dynamic Configuration

```bash
# Load default configs into Redis
python scripts/init_default_configs.py

# Verify
redis-cli --scan --pattern "mutt:config:*"
```

### Step 5: Update Vault Secrets (Optional)

```bash
# Update to dual-password structure
./scripts/vault-init.sh

# Or manually update each secret
vault kv patch secret/mutt/prod \
  REDIS_PASS_CURRENT="$OLD_REDIS_PASS" \
  REDIS_PASS_NEXT="$NEW_REDIS_PASS"
```

### Step 6: Deploy v2.5 Services

**Option A: Docker Compose**
```bash
# Stop services
docker-compose down

# Start v2.5
docker-compose up -d

# Check logs
docker-compose logs -f
```

**Option B: Kubernetes**
```bash
# Update deployments
kubectl apply -f k8s/

# Watch rollout
kubectl rollout status deployment/alerter -n mutt
kubectl rollout status deployment/moog-forwarder -n mutt

# Check pod status
kubectl get pods -n mutt
```

### Step 7: Deploy Retention CronJob (Optional)

```bash
# Deploy retention automation
kubectl apply -f k8s/retention-cleanup-cronjob.yaml

# Verify CronJob
kubectl get cronjobs -n mutt
```

### Step 8: Install muttdev CLI (Optional)

```bash
# Install developer CLI
./scripts/install_muttdev.sh

# Test
muttdev status
```

---

## Post-Migration Validation

### 1. Service Health Checks

```bash
# Using muttdev
muttdev status

# Or manually
curl http://localhost:8080/health  # Ingestor
curl http://localhost:8082/health  # Alerter
curl http://localhost:8084/health  # Moog Forwarder
curl http://localhost:8090/health  # Web UI
```

**Expected:** All should return `200 OK` with `{"status": "healthy"}`

### 2. API Version Headers

```bash
# Check version headers
curl -I http://localhost:8090/api/v1/metrics \
  -H "X-API-KEY: your-key"

# Should see:
# X-API-Version: 2.5
# X-API-Deprecated: true
```

### 3. Dynamic Configuration

```bash
# Test config retrieval
muttdev config get cache_reload_interval

# Test config update
muttdev config set cache_reload_interval 300

# Verify propagation (check service logs)
muttdev logs alerter | grep "Config change detected"
```

### 4. Circuit Breaker Metrics

```bash
# Query Prometheus
curl 'http://localhost:9090/api/v1/query?query=mutt_circuit_breaker_state'

# Or check metrics endpoint
curl http://localhost:8083/metrics | grep circuit_breaker
```

### 5. Database Schema

```bash
# Verify new tables exist
psql -h localhost -U postgres -d mutt -c "\dt"

# Should include:
# - config_audit_log
# - event_audit_log (partitioned)
# - event_audit_log_archive
```

### 6. Run Test Suite

```bash
# Run all tests
muttdev test

# Or with pytest directly
pytest tests/ -v

# Expected: 327+ tests passing
```

### 7. Check Metrics

```bash
# Verify Prometheus scraping
curl http://localhost:9090/targets

# Check key metrics exist
curl http://localhost:8081/metrics | grep mutt_ingest_requests_total
curl http://localhost:8083/metrics | grep mutt_circuit_breaker_state
```

---

## Rollback Procedure

If you encounter issues with v2.5, follow these steps to rollback:

### Step 1: Stop v2.5 Services

```bash
# Docker Compose
docker-compose down

# Kubernetes
kubectl rollout undo deployment/alerter -n mutt
kubectl rollout undo deployment/moog-forwarder -n mutt
kubectl rollout undo deployment/ingestor -n mutt
kubectl rollout undo deployment/webui -n mutt
```

### Step 2: Restore Previous Version

```bash
# Update docker-compose.yml image tags to v2.4
sed -i 's/:v2.5/:v2.4/g' docker-compose.yml

# Restart services
docker-compose up -d
```

### Step 3: Restore Database (if needed)

```bash
# Drop current database
psql -h localhost -U postgres -c "DROP DATABASE mutt;"

# Restore from backup
psql -h localhost -U postgres -c "CREATE DATABASE mutt;"
psql -h localhost -U postgres -d mutt < mutt_backup_YYYYMMDD.sql
```

### Step 4: Restore Redis (if needed)

```bash
# Stop Redis
redis-cli shutdown

# Restore RDB backup
cp /tmp/redis_backup_YYYYMMDD.rdb /var/lib/redis/dump.rdb

# Restart Redis
redis-server
```

### Step 5: Verify Rollback

```bash
# Check service health
curl http://localhost:8080/health
curl http://localhost:8082/health
curl http://localhost:8084/health
curl http://localhost:8090/health

# Verify version
curl -I http://localhost:8090/api/v1/metrics \
  -H "X-API-KEY: your-key" | grep X-API-Version
```

---

## Troubleshooting

### Issue: Services fail to start after upgrade

**Symptoms:** Pods in CrashLoopBackOff, or docker containers exiting

**Solution:**
```bash
# Check logs
muttdev logs <service>

# Common causes:
# 1. Missing environment variables
# 2. Vault connection issues
# 3. Database schema not updated

# Verify environment
env | grep REDIS
env | grep DB_
env | grep VAULT
```

### Issue: DynamicConfig not working

**Symptoms:** Config changes not propagating

**Solution:**
```bash
# Check Redis connection
redis-cli ping

# Verify configs exist
redis-cli --scan --pattern "mutt:config:*"

# Check service logs for DynamicConfig init
muttdev logs alerter | grep "DynamicConfig"

# Re-initialize defaults
python scripts/init_default_configs.py --force
```

### Issue: Circuit breaker metrics missing

**Symptoms:** `mutt_circuit_breaker_state` not in Prometheus

**Solution:**
```bash
# Verify circuit breaker is enabled
env | grep CIRCUIT_BREAKER_ENABLED

# Check Moog Forwarder logs
muttdev logs moog_forwarder | grep "circuit breaker"

# Verify metrics endpoint
curl http://localhost:8083/metrics | grep circuit_breaker
```

### Issue: Retention CronJob not running

**Symptoms:** Old data not being archived

**Solution:**
```bash
# Check CronJob status
kubectl get cronjobs -n mutt
kubectl describe cronjob retention-cleanup -n mutt

# Check recent jobs
kubectl get jobs -n mutt

# View job logs
kubectl logs job/retention-cleanup-XXXXXXX -n mutt

# Run manually to test
python scripts/retention_policy_enforcer.py --dry-run
```

---

## Support & Resources

- **Documentation:** `docs/` directory
- **ADRs:** `docs/adr/` for architecture decisions
- **Runbooks:** `docs/operations/` for operational procedures
- **Issues:** Report bugs and issues on GitHub
- **CLI Help:** `muttdev --help` or `muttdev <command> --help`

---

## Change Log

- **2025-11-11:** Initial v2.5 migration guide created
