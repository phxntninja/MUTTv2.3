# MUTT v2.5 - Configuration Management Guide

**Target Audience:** System Administrators, DevOps Engineers, Security Engineers
**Priority Level:** P2 (High)
**Last Updated:** 2025-11-10

---

## Table of Contents

1. [Overview](#overview)
2. [Configuration Architecture](#configuration-architecture)
3. [Static Configuration Management](#static-configuration-management)
4. [Dynamic Configuration Management](#dynamic-configuration-management)
5. [Secrets Management](#secrets-management)
6. [Configuration Validation](#configuration-validation)
7. [Configuration Backup and Restore](#configuration-backup-and-restore)
8. [Configuration Audit Trails](#configuration-audit-trails)
9. [Secrets Rotation](#secrets-rotation)
10. [Configuration Migration](#configuration-migration)
11. [Best Practices](#best-practices)
12. [Troubleshooting](#troubleshooting)

---

## Overview

MUTT v2.5 uses a **hybrid configuration approach** that combines:

- **Static Configuration**: Environment variables and files (requires restart)
- **Dynamic Configuration**: Redis-backed runtime configuration (zero-downtime)
- **Secrets Management**: HashiCorp Vault integration (secure credentials)

### Configuration Hierarchy

Configuration precedence (highest to lowest):

1. **Runtime Configuration** (Dynamic Config in Redis) - if `DYNAMIC_CONFIG_ENABLED=true`
2. **Environment Variables** (Static Config from `/etc/mutt/mutt.env`)
3. **Default Values** (Hardcoded in service code)

### Quick Reference

| Configuration Type | Storage | Scope | Restart Required | Use Case |
|-------------------|---------|-------|------------------|----------|
| **Environment Variables** | `/etc/mutt/mutt.env` | All services | Yes | Infrastructure settings, initial config |
| **Dynamic Config** | Redis (`mutt:config:*`) | All services | No | Tunable parameters, thresholds |
| **Secrets** | HashiCorp Vault | Per-service | Yes | API keys, passwords, certificates |
| **Database** | PostgreSQL | Rules, teams, hosts | No (via UI) | Business logic, operational data |

---

## Configuration Architecture

### Configuration Flow Diagram

```
┌─────────────────────────────────────────────────────┐
│                 Configuration Sources               │
└─────────────────────────────────────────────────────┘
                         │
        ┌────────────────┼────────────────┐
        │                │                │
        v                v                v
┌──────────────┐  ┌─────────────┐  ┌────────────┐
│ Environment  │  │   Redis     │  │   Vault    │
│  Variables   │  │ (Dynamic)   │  │ (Secrets)  │
│              │  │             │  │            │
│ /etc/mutt/   │  │ mutt:config │  │ secret/    │
│ mutt.env     │  │ :*          │  │ mutt/prod  │
└──────┬───────┘  └──────┬──────┘  └─────┬──────┘
       │                 │                │
       │                 │                │
       v                 v                v
┌─────────────────────────────────────────────────────┐
│              MUTT Service Instance                  │
│                                                     │
│  1. Read static env vars (startup)                 │
│  2. Authenticate to Vault (startup)                │
│  3. Fetch secrets from Vault (startup)             │
│  4. Load dynamic config from Redis (runtime)       │
│  5. Watch Redis PubSub for updates (runtime)       │
└─────────────────────────────────────────────────────┘
```

### Configuration Lifecycle

**Startup:**
1. Service reads `/etc/mutt/mutt.env` for environment variables
2. Service authenticates to Vault using Secret ID
3. Service fetches secrets (passwords, API keys) from Vault
4. Service connects to Redis and PostgreSQL
5. If `DYNAMIC_CONFIG_ENABLED=true`, service loads dynamic config from Redis
6. Service starts background thread to watch Redis PubSub for config updates

**Runtime:**
1. Service checks dynamic config (cached for 5 seconds)
2. If config changes in Redis, PubSub notification triggers cache invalidation
3. Service reloads config value on next access (within 5 seconds)
4. Registered callbacks execute immediately on config change

**Shutdown:**
1. Service stops PubSub watcher thread
2. Service closes connections gracefully
3. Configuration is NOT persisted (already in Redis/Vault)

---

## Static Configuration Management

### Environment File Location

All static configuration is stored in `/etc/mutt/mutt.env`:

```bash
/etc/mutt/
├── mutt.env           # Main configuration file
├── vault_secret_id    # Vault authentication token
└── certs/             # TLS certificates
    ├── redis-ca.crt
    ├── postgres-ca.crt
    └── vault-ca.crt
```

### Viewing Current Configuration

```bash
# View entire configuration file
sudo cat /etc/mutt/mutt.env

# Search for specific setting
grep REDIS_HOST /etc/mutt/mutt.env

# View non-commented settings only
grep -v '^#' /etc/mutt/mutt.env | grep -v '^$'
```

---

### Modifying Static Configuration

**Procedure:**

1. **Backup current configuration:**
   ```bash
   sudo cp /etc/mutt/mutt.env /etc/mutt/mutt.env.backup.$(date +%Y%m%d_%H%M%S)
   ```

2. **Edit configuration file:**
   ```bash
   sudo vi /etc/mutt/mutt.env
   ```

3. **Validate syntax** (ensure no typos):
   ```bash
   # Check for invalid syntax (missing =, quotes, etc.)
   bash -n /etc/mutt/mutt.env || echo "Syntax error detected!"

   # Verify specific setting
   source /etc/mutt/mutt.env && echo $REDIS_HOST
   ```

4. **Restart affected services:**
   ```bash
   # Restart single service
   sudo systemctl restart mutt-ingestor

   # OR restart all services
   sudo systemctl restart mutt-*
   ```

5. **Verify changes took effect:**
   ```bash
   # Check logs for new configuration
   sudo journalctl -u mutt-ingestor -n 50 | grep -i "config\|redis_host"

   # Verify service health
   curl http://localhost:8080/health
   ```

---

### Critical Static Configuration Settings

**Infrastructure Settings** (require restart):

| Variable | Default | Description | Restart Required |
|----------|---------|-------------|------------------|
| `REDIS_HOST` | `localhost` | Redis server hostname | Yes |
| `REDIS_PORT` | `6379` | Redis server port | Yes |
| `REDIS_TLS_ENABLED` | `false` | Enable TLS for Redis | Yes |
| `POSTGRES_HOST` | `localhost` | PostgreSQL server hostname | Yes |
| `POSTGRES_PORT` | `5432` | PostgreSQL server port | Yes |
| `POSTGRES_DB` | `mutt` | PostgreSQL database name | Yes |
| `VAULT_ADDR` | (required) | Vault server URL | Yes |
| `VAULT_MOUNT_PATH` | `secret` | Vault secret mount path | Yes |

**Service Settings** (require restart):

| Variable | Default | Description | Restart Required |
|----------|---------|-------------|------------------|
| `INGESTOR_PORT` | `8080` | Ingestor HTTP port | Yes |
| `INGESTOR_WORKERS` | `4` | Gunicorn worker count | Yes |
| `ALERTER_HEALTH_PORT` | `8081` | Alerter health endpoint port | Yes |
| `MOOG_WEBHOOK_URL` | (required) | Moogsoft webhook URL | Yes |
| `WEBUI_PORT` | `8090` | Web UI HTTP port | Yes |
| `LOG_LEVEL` | `INFO` | Logging level (DEBUG/INFO/WARNING/ERROR) | Yes |

**Tunable Settings** (can be dynamic if `DYNAMIC_CONFIG_ENABLED=true`):

| Variable | Default | Description | Dynamic Alternative |
|----------|---------|-------------|---------------------|
| `INGEST_QUEUE_CAP` | `1000000` | Max ingest queue depth | N/A (static only) |
| `RULE_CACHE_TTL` | `300` | Rule cache TTL (seconds) | `mutt:config:rule_cache_ttl` |
| `ALERTER_QUEUE_WARN_THRESHOLD` | `1000` | Queue warning threshold | `mutt:config:alerter_queue_warn_threshold` |
| `ALERTER_QUEUE_SHED_THRESHOLD` | `2000` | Queue shedding threshold | `mutt:config:alerter_queue_shed_threshold` |
| `RATE_LIMIT_MAX_REQUESTS` | `1000` | Ingestor rate limit | `mutt:config:ingest_max_rate` |

---

### Configuration Templates

**Production Environment** (`/etc/mutt/mutt.env`):

```bash
# Production Configuration - MUTT v2.5
# Last Updated: 2025-11-10

# ===== INFRASTRUCTURE =====
REDIS_HOST=redis-prod.internal
REDIS_PORT=6379
REDIS_TLS_ENABLED=true
REDIS_TLS_CA_CERT=/etc/mutt/certs/redis-ca.crt

POSTGRES_HOST=postgres-prod.internal
POSTGRES_PORT=5432
POSTGRES_DB=mutt_prod
POSTGRES_USER=mutt_user
POSTGRES_TLS_ENABLED=true
POSTGRES_TLS_CA_CERT=/etc/mutt/certs/postgres-ca.crt

VAULT_ADDR=https://vault.internal:8200
VAULT_MOUNT_PATH=secret
VAULT_SECRET_PATH=mutt/prod
VAULT_TLS_CA_CERT=/etc/mutt/certs/vault-ca.crt

# ===== SERVICES =====
INGESTOR_HOST=0.0.0.0
INGESTOR_PORT=8080
INGESTOR_WORKERS=8

ALERTER_HEALTH_PORT=8081
ALERTER_METRICS_PORT=9091
POD_NAME=alerter-prod-001

MOOG_WEBHOOK_URL=https://moogsoft.internal/api/v1/webhook
MOOG_TIMEOUT=30

WEBUI_HOST=0.0.0.0
WEBUI_PORT=8090
WEBUI_WORKERS=4

# ===== DYNAMIC CONFIG =====
DYNAMIC_CONFIG_ENABLED=true

# ===== LOGGING =====
LOG_LEVEL=INFO
LOG_FORMAT=json

# ===== MONITORING =====
PROMETHEUS_ENABLED=true
METRICS_PORT=9090
```

**Development Environment:**

```bash
# Development Configuration - MUTT v2.5

# ===== INFRASTRUCTURE =====
REDIS_HOST=localhost
REDIS_PORT=6379
REDIS_TLS_ENABLED=false

POSTGRES_HOST=localhost
POSTGRES_PORT=5432
POSTGRES_DB=mutt_dev
POSTGRES_USER=mutt_dev
POSTGRES_TLS_ENABLED=false

VAULT_ADDR=http://localhost:8200
VAULT_MOUNT_PATH=secret
VAULT_SECRET_PATH=mutt/dev
VAULT_TLS_VERIFY=false

# ===== SERVICES =====
INGESTOR_PORT=8080
INGESTOR_WORKERS=2

MOOG_WEBHOOK_URL=http://localhost:9999/webhook  # Mock endpoint

WEBUI_PORT=8090
WEBUI_WORKERS=2

# ===== DYNAMIC CONFIG =====
DYNAMIC_CONFIG_ENABLED=true

# ===== LOGGING =====
LOG_LEVEL=DEBUG
LOG_FORMAT=text

# ===== MONITORING =====
PROMETHEUS_ENABLED=true
```

---

## Dynamic Configuration Management

### Overview

Dynamic configuration allows runtime changes without service restarts. Configuration is stored in Redis and synchronized across all service instances via PubSub.

**Enabling Dynamic Configuration:**

```bash
# Edit environment file
sudo vi /etc/mutt/mutt.env

# Add or update:
DYNAMIC_CONFIG_ENABLED=true

# Restart services to enable
sudo systemctl restart mutt-*
```

---

### Viewing Dynamic Configuration

**Method 1: Redis CLI**

```bash
# List all dynamic config keys
redis-cli KEYS "mutt:config:*"

# Get specific value
redis-cli GET mutt:config:alerter_queue_warn_threshold

# Get all config as JSON
redis-cli KEYS "mutt:config:*" | while read key; do
    value=$(redis-cli GET "$key")
    echo "$key = $value"
done
```

**Method 2: muttdev CLI Tool**

```bash
# List all configuration
python scripts/muttdev.py config --list

# Get specific value
python scripts/muttdev.py config --get alerter_queue_warn_threshold

# Get with JSON output
python scripts/muttdev.py config --list --format json
```

**Method 3: Web UI API**

```bash
# Get all config (requires API key)
curl -H "X-API-Key: YOUR_API_KEY" \
  http://localhost:8090/api/v1/config

# Get specific value
curl -H "X-API-Key: YOUR_API_KEY" \
  http://localhost:8090/api/v1/config/alerter_queue_warn_threshold
```

---

### Updating Dynamic Configuration

**Method 1: muttdev CLI (Recommended)**

```bash
# Update single value (with PubSub notification)
python scripts/muttdev.py config --set alerter_queue_warn_threshold 2000 --publish

# Update multiple values
python scripts/muttdev.py config \
  --set alerter_queue_warn_threshold 2000 --publish \
  --set alerter_queue_shed_threshold 5000 --publish

# Update without notification (local Redis only)
python scripts/muttdev.py config --set test_key test_value
```

**Method 2: Redis CLI**

```bash
# Set value
redis-cli SET mutt:config:alerter_queue_warn_threshold 2000

# Publish notification to all services
redis-cli PUBLISH mutt:config:updates alerter_queue_warn_threshold
```

**Method 3: Web UI API**

```bash
# Update via API
curl -X PUT http://localhost:8090/api/v1/config/alerter_queue_warn_threshold \
  -H "X-API-Key: YOUR_API_KEY" \
  -H "Content-Type: application/json" \
  -d '{
    "value": "2000",
    "reason": "Increased threshold due to high event volume"
  }'
```

---

### Verifying Configuration Changes

**Step 1: Confirm Redis update**

```bash
redis-cli GET mutt:config:alerter_queue_warn_threshold
# Expected output: 2000
```

**Step 2: Verify service received update**

```bash
# Check alerter logs for config update message
sudo journalctl -u mutt-alerter -n 50 | grep -i "config\|threshold"

# Expected log entry:
# "Config updated: alerter_queue_warn_threshold = 2000"
```

**Step 3: Verify behavior change**

```bash
# Check metrics for new threshold in use
curl -s http://localhost:9091/metrics | grep alerter_queue_warn_threshold

# Monitor queue warnings with new threshold
watch -n 5 'redis-cli LLEN mutt:ingest_queue'
```

---

### Dynamic Configuration Keys

**Alerter Backpressure:**

| Key | Type | Default | Description |
|-----|------|---------|-------------|
| `alerter_queue_warn_threshold` | int | 1000 | Queue depth warning threshold |
| `alerter_queue_shed_threshold` | int | 2000 | Queue depth shedding threshold |
| `alerter_shed_mode` | string | `dlq` | Shedding mode (`dlq` or `defer`) |
| `alerter_defer_sleep_ms` | int | 250 | Deferral sleep time (ms) |

**Remediation Service:**

| Key | Type | Default | Description |
|-----|------|---------|-------------|
| `remediation_enabled` | bool | true | Enable/disable remediation |
| `remediation_interval` | int | 300 | Remediation loop interval (seconds) |
| `remediation_batch_size` | int | 10 | Messages to replay per cycle |
| `max_poison_retries` | int | 3 | Max retries before dead letter |

**SLO Tracking:**

| Key | Type | Default | Description |
|-----|------|---------|-------------|
| `slo_ingest_success_target` | float | 0.995 | Ingestor success rate target |
| `slo_forward_success_target` | float | 0.99 | Forwarder success rate target |
| `slo_window_hours` | int | 24 | SLO evaluation window (hours) |
| `slo_burn_rate_critical` | float | 14.4 | Critical burn rate threshold |
| `slo_burn_rate_warning` | float | 6.0 | Warning burn rate threshold |

---

### Initializing Dynamic Configuration

On first deployment, load environment variables into Redis:

**Script: `scripts/init_dynamic_config.py`**

```bash
# Run initialization script
cd /opt/mutt
source venv/bin/activate
python scripts/init_dynamic_config.py

# Verify initialization
redis-cli KEYS "mutt:config:*"
```

**Manual Initialization:**

```bash
# Set baseline configuration
redis-cli SET mutt:config:alerter_queue_warn_threshold 1000
redis-cli SET mutt:config:alerter_queue_shed_threshold 2000
redis-cli SET mutt:config:alerter_shed_mode dlq
redis-cli SET mutt:config:alerter_defer_sleep_ms 250

redis-cli SET mutt:config:remediation_enabled true
redis-cli SET mutt:config:remediation_interval 300
redis-cli SET mutt:config:remediation_batch_size 10

redis-cli SET mutt:config:slo_ingest_success_target 0.995
redis-cli SET mutt:config:slo_forward_success_target 0.99
redis-cli SET mutt:config:slo_window_hours 24
```

---

## Secrets Management

### HashiCorp Vault Integration

MUTT uses Vault for secure secrets storage:

- **API Keys**: Ingestor, Web UI, Moogsoft authentication
- **Passwords**: Redis, PostgreSQL credentials
- **Certificates**: TLS client certificates (optional)

### Vault Structure

```
secret/mutt/prod/
├── INGEST_API_KEY        # Ingestor API key
├── WEBUI_API_KEY         # Web UI API key
├── MOOG_API_KEY          # Moogsoft API key
├── REDIS_PASS_CURRENT    # Current Redis password
├── REDIS_PASS_NEXT       # Next Redis password (rotation)
├── DB_PASS_CURRENT       # Current PostgreSQL password
└── DB_PASS_NEXT          # Next PostgreSQL password (rotation)
```

---

### Viewing Secrets

**Using Vault CLI:**

```bash
# Set Vault address and token
export VAULT_ADDR="https://vault.internal:8200"
export VAULT_TOKEN="s.YOUR_VAULT_TOKEN"

# View all MUTT secrets
vault kv get secret/mutt/prod

# View specific secret
vault kv get -field=INGEST_API_KEY secret/mutt/prod
```

**From MUTT Server:**

```bash
# Use service's Vault token
export VAULT_ADDR=$(grep VAULT_ADDR /etc/mutt/mutt.env | cut -d= -f2)
export VAULT_TOKEN=$(cat /etc/mutt/vault_secret_id)

# Get secrets
vault kv get secret/mutt/prod
```

---

### Adding/Updating Secrets

**Add New Secret:**

```bash
# Add INGEST_API_KEY
vault kv put secret/mutt/prod INGEST_API_KEY="mutt-ingest-$(uuidgen)"

# Verify
vault kv get -field=INGEST_API_KEY secret/mutt/prod
```

**Update Existing Secret:**

```bash
# Update Moogsoft API key
vault kv patch secret/mutt/prod MOOG_API_KEY="new-moog-api-key-here"

# Restart affected services
sudo systemctl restart mutt-moog-forwarder
```

**Update Multiple Secrets:**

```bash
# Update all API keys at once
vault kv put secret/mutt/prod \
  INGEST_API_KEY="new-ingest-key" \
  WEBUI_API_KEY="new-webui-key" \
  MOOG_API_KEY="new-moog-key" \
  REDIS_PASS_CURRENT="$(cat /dev/urandom | tr -dc 'a-zA-Z0-9' | head -c 32)" \
  DB_PASS_CURRENT="$(cat /dev/urandom | tr -dc 'a-zA-Z0-9' | head -c 32)"

# Restart all services
sudo systemctl restart mutt-*
```

---

### Vault Token Management

**Check Token Validity:**

```bash
# Check current token
export VAULT_TOKEN=$(cat /etc/mutt/vault_secret_id)
vault token lookup

# Output shows:
# - expire_time
# - policies
# - ttl (time to live)
```

**Renew Token:**

```bash
# Renew existing token (extends TTL)
vault token renew

# Renew with specific increment (720 hours = 30 days)
vault token renew -increment=720h
```

**Create New Token:**

```bash
# Create new token with mutt-policy
vault token create -policy=mutt-policy -ttl=720h

# Save token to secret ID file
echo "s.NEW_TOKEN_HERE" | sudo tee /etc/mutt/vault_secret_id
sudo chmod 600 /etc/mutt/vault_secret_id
sudo chown mutt:mutt /etc/mutt/vault_secret_id

# Restart services to use new token
sudo systemctl restart mutt-*
```

---

### Vault Policy for MUTT

**Policy: `mutt-policy`**

```hcl
# MUTT Service Policy
# Allows read access to MUTT secrets

path "secret/data/mutt/prod" {
  capabilities = ["read"]
}

path "secret/metadata/mutt/prod" {
  capabilities = ["read", "list"]
}

# Allow token renewal
path "auth/token/renew-self" {
  capabilities = ["update"]
}

# Allow token lookup
path "auth/token/lookup-self" {
  capabilities = ["read"]
}
```

**Apply Policy:**

```bash
# Write policy to Vault
vault policy write mutt-policy - <<EOF
path "secret/data/mutt/prod" {
  capabilities = ["read"]
}

path "secret/metadata/mutt/prod" {
  capabilities = ["read", "list"]
}

path "auth/token/renew-self" {
  capabilities = ["update"]
}

path "auth/token/lookup-self" {
  capabilities = ["read"]
}
EOF

# Create token with policy
vault token create -policy=mutt-policy -ttl=720h
```

---

## Configuration Validation

### Pre-Deployment Validation

Before deploying configuration changes, validate syntax and values:

**Script: `scripts/validate_config.sh`**

```bash
#!/bin/bash
# Configuration Validation Script

set -e

CONFIG_FILE="/etc/mutt/mutt.env"
ERRORS=0

echo "Validating MUTT Configuration..."

# Check file exists
if [ ! -f "$CONFIG_FILE" ]; then
    echo "❌ Error: Config file not found: $CONFIG_FILE"
    exit 1
fi

# Check syntax (source without executing)
if ! bash -n "$CONFIG_FILE" 2>/dev/null; then
    echo "❌ Error: Syntax error in $CONFIG_FILE"
    ERRORS=$((ERRORS + 1))
fi

# Source config
source "$CONFIG_FILE"

# Validate required variables
REQUIRED_VARS=(
    "REDIS_HOST"
    "REDIS_PORT"
    "POSTGRES_HOST"
    "POSTGRES_PORT"
    "POSTGRES_DB"
    "VAULT_ADDR"
    "INGESTOR_PORT"
    "MOOG_WEBHOOK_URL"
)

for var in "${REQUIRED_VARS[@]}"; do
    if [ -z "${!var}" ]; then
        echo "❌ Error: Required variable $var is not set"
        ERRORS=$((ERRORS + 1))
    else
        echo "✅ $var = ${!var}"
    fi
done

# Validate port ranges
validate_port() {
    local port_name=$1
    local port_value=$2

    if [ "$port_value" -lt 1 ] || [ "$port_value" -gt 65535 ]; then
        echo "❌ Error: $port_name ($port_value) must be between 1-65535"
        ERRORS=$((ERRORS + 1))
    else
        echo "✅ $port_name port is valid: $port_value"
    fi
}

validate_port "REDIS_PORT" "$REDIS_PORT"
validate_port "POSTGRES_PORT" "$POSTGRES_PORT"
validate_port "INGESTOR_PORT" "$INGESTOR_PORT"
validate_port "WEBUI_PORT" "$WEBUI_PORT"

# Validate connectivity
echo ""
echo "Testing Infrastructure Connectivity..."

# Test Redis
if redis-cli -h "$REDIS_HOST" -p "$REDIS_PORT" PING >/dev/null 2>&1; then
    echo "✅ Redis is reachable: $REDIS_HOST:$REDIS_PORT"
else
    echo "⚠️  Warning: Cannot reach Redis: $REDIS_HOST:$REDIS_PORT"
fi

# Test PostgreSQL
if psql -h "$POSTGRES_HOST" -p "$POSTGRES_PORT" -U "$POSTGRES_USER" -d "$POSTGRES_DB" -c "SELECT 1" >/dev/null 2>&1; then
    echo "✅ PostgreSQL is reachable: $POSTGRES_HOST:$POSTGRES_PORT"
else
    echo "⚠️  Warning: Cannot reach PostgreSQL: $POSTGRES_HOST:$POSTGRES_PORT"
fi

# Test Vault
if curl -s -k "$VAULT_ADDR/v1/sys/health" >/dev/null 2>&1; then
    echo "✅ Vault is reachable: $VAULT_ADDR"
else
    echo "⚠️  Warning: Cannot reach Vault: $VAULT_ADDR"
fi

# Summary
echo ""
if [ $ERRORS -eq 0 ]; then
    echo "✅ Configuration validation passed!"
    exit 0
else
    echo "❌ Configuration validation failed with $ERRORS error(s)"
    exit 1
fi
```

**Run Validation:**

```bash
# Make script executable
sudo chmod +x /usr/local/bin/validate_mutt_config.sh

# Run validation
sudo /usr/local/bin/validate_mutt_config.sh

# Validate before restart
sudo /usr/local/bin/validate_mutt_config.sh && sudo systemctl restart mutt-*
```

---

### Runtime Validation

Validate configuration while services are running:

```bash
# Check service health endpoints
for port in 8080 8081 8082 8087 8090; do
    echo -n "Port $port: "
    curl -s -o /dev/null -w "%{http_code}" http://localhost:$port/health
    echo ""
done

# Check service logs for errors
sudo journalctl -u mutt-* --since "5 minutes ago" --priority=err

# Verify dynamic config loaded
redis-cli KEYS "mutt:config:*" | wc -l
# Should return > 0 if dynamic config is initialized
```

---

## Configuration Backup and Restore

### Backing Up Configuration

**Script: `scripts/backup_config.sh`**

```bash
#!/bin/bash
# MUTT Configuration Backup Script

BACKUP_DIR="/var/backups/mutt"
TIMESTAMP=$(date +%Y%m%d_%H%M%S)
BACKUP_FILE="$BACKUP_DIR/mutt_config_$TIMESTAMP.tar.gz"

mkdir -p "$BACKUP_DIR"

echo "Backing up MUTT configuration..."

# Create temporary directory
TEMP_DIR=$(mktemp -d)

# Backup static configuration
cp /etc/mutt/mutt.env "$TEMP_DIR/"

# Backup dynamic configuration (from Redis)
redis-cli KEYS "mutt:config:*" | while read key; do
    value=$(redis-cli GET "$key")
    echo "$key=$value" >> "$TEMP_DIR/dynamic_config.txt"
done

# Backup database configuration (rules, teams, hosts)
pg_dump -h localhost -U mutt_user -d mutt \
  -t alert_rules -t dev_hosts -t device_teams \
  > "$TEMP_DIR/database_config.sql"

# Create tarball
tar -czf "$BACKUP_FILE" -C "$TEMP_DIR" .

# Cleanup
rm -rf "$TEMP_DIR"

echo "✅ Backup created: $BACKUP_FILE"

# Keep only last 30 backups
ls -t "$BACKUP_DIR"/mutt_config_*.tar.gz | tail -n +31 | xargs -r rm

echo "✅ Backup rotation completed"
```

**Schedule Automated Backups:**

```bash
# Add to crontab (daily at 2 AM)
echo "0 2 * * * root /usr/local/bin/backup_mutt_config.sh >> /var/log/mutt/config_backups.log 2>&1" | sudo tee -a /etc/crontab
```

---

### Restoring Configuration

**Script: `scripts/restore_config.sh`**

```bash
#!/bin/bash
# MUTT Configuration Restore Script

BACKUP_FILE="$1"

if [ -z "$BACKUP_FILE" ]; then
    echo "Usage: $0 <backup_file.tar.gz>"
    exit 1
fi

if [ ! -f "$BACKUP_FILE" ]; then
    echo "Error: Backup file not found: $BACKUP_FILE"
    exit 1
fi

echo "Restoring MUTT configuration from: $BACKUP_FILE"

# Create temporary directory
TEMP_DIR=$(mktemp -d)

# Extract backup
tar -xzf "$BACKUP_FILE" -C "$TEMP_DIR"

# Restore static configuration
echo "Restoring static configuration..."
sudo cp /etc/mutt/mutt.env /etc/mutt/mutt.env.pre-restore
sudo cp "$TEMP_DIR/mutt.env" /etc/mutt/mutt.env

# Restore dynamic configuration
echo "Restoring dynamic configuration..."
while IFS='=' read -r key value; do
    redis-cli SET "$key" "$value"
done < "$TEMP_DIR/dynamic_config.txt"

# Restore database configuration
echo "Restoring database configuration..."
psql -h localhost -U mutt_user -d mutt < "$TEMP_DIR/database_config.sql"

# Cleanup
rm -rf "$TEMP_DIR"

echo "✅ Configuration restored successfully"
echo "⚠️  Restart services to apply changes: sudo systemctl restart mutt-*"
```

**Restore Example:**

```bash
# List available backups
ls -lh /var/backups/mutt/

# Restore from specific backup
sudo /usr/local/bin/restore_mutt_config.sh /var/backups/mutt/mutt_config_20251110_020000.tar.gz

# Restart services
sudo systemctl restart mutt-*

# Verify restoration
/usr/local/bin/validate_mutt_config.sh
```

---

## Configuration Audit Trails

### Audit Log Structure

All configuration changes are logged to PostgreSQL for compliance:

**Table: `config_audit_log`**

```sql
CREATE TABLE config_audit_log (
    id SERIAL PRIMARY KEY,
    timestamp TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    changed_by VARCHAR(100) NOT NULL,      -- User, API key, or system
    operation VARCHAR(10) NOT NULL,         -- CREATE, UPDATE, DELETE
    table_name VARCHAR(50) NOT NULL,        -- Target table/config key
    record_id INTEGER,                      -- Primary key of changed record
    old_values JSONB,                       -- Values before change
    new_values JSONB,                       -- Values after change
    reason TEXT,                            -- Optional reason for change
    correlation_id VARCHAR(100)             -- Optional correlation ID
);

CREATE INDEX idx_audit_timestamp ON config_audit_log(timestamp DESC);
CREATE INDEX idx_audit_changed_by ON config_audit_log(changed_by);
CREATE INDEX idx_audit_table ON config_audit_log(table_name);
```

---

### Viewing Audit Logs

**Recent Configuration Changes:**

```sql
-- Connect to PostgreSQL
sudo -u postgres psql -U mutt_user -d mutt

-- View last 20 configuration changes
SELECT
    timestamp,
    changed_by,
    operation,
    table_name,
    record_id,
    old_values->>'priority' AS old_priority,
    new_values->>'priority' AS new_priority,
    reason
FROM config_audit_log
ORDER BY timestamp DESC
LIMIT 20;
```

**Changes by Specific User:**

```sql
SELECT
    timestamp,
    operation,
    table_name,
    record_id,
    reason
FROM config_audit_log
WHERE changed_by = 'admin_user'
ORDER BY timestamp DESC;
```

**Changes to Specific Table:**

```sql
SELECT
    timestamp,
    changed_by,
    operation,
    old_values,
    new_values,
    reason
FROM config_audit_log
WHERE table_name = 'alert_rules'
AND timestamp > NOW() - INTERVAL '7 days'
ORDER BY timestamp DESC;
```

---

### Generating Audit Reports

**Script: `scripts/generate_audit_report.sh`**

```bash
#!/bin/bash
# Generate configuration audit report

START_DATE="${1:-7 days ago}"
END_DATE="${2:-now}"

echo "Configuration Audit Report"
echo "=========================="
echo "Period: $START_DATE to $END_DATE"
echo ""

psql -h localhost -U mutt_user -d mutt <<EOF
\x off
\pset border 2

-- Summary statistics
SELECT
    'Total Changes' AS metric,
    COUNT(*) AS count
FROM config_audit_log
WHERE timestamp BETWEEN '$START_DATE' AND '$END_DATE'
UNION ALL
SELECT
    'Unique Users' AS metric,
    COUNT(DISTINCT changed_by) AS count
FROM config_audit_log
WHERE timestamp BETWEEN '$START_DATE' AND '$END_DATE';

-- Changes by operation type
SELECT
    operation,
    COUNT(*) AS count
FROM config_audit_log
WHERE timestamp BETWEEN '$START_DATE' AND '$END_DATE'
GROUP BY operation
ORDER BY count DESC;

-- Top 10 most active users
SELECT
    changed_by,
    COUNT(*) AS changes
FROM config_audit_log
WHERE timestamp BETWEEN '$START_DATE' AND '$END_DATE'
GROUP BY changed_by
ORDER BY changes DESC
LIMIT 10;

-- Changes by table
SELECT
    table_name,
    COUNT(*) AS changes
FROM config_audit_log
WHERE timestamp BETWEEN '$START_DATE' AND '$END_DATE'
GROUP BY table_name
ORDER BY changes DESC;
EOF
```

**Run Report:**

```bash
# Last 7 days (default)
/usr/local/bin/generate_mutt_audit_report.sh

# Specific date range
/usr/local/bin/generate_mutt_audit_report.sh "2025-11-01" "2025-11-10"

# Last 30 days
/usr/local/bin/generate_mutt_audit_report.sh "30 days ago" "now"
```

---

## Secrets Rotation

### Password Rotation Strategy

MUTT supports **zero-downtime password rotation** using dual-password authentication:

1. Add new password as `*_PASS_NEXT` in Vault
2. Services try `*_PASS_CURRENT` first, fall back to `*_PASS_NEXT`
3. Update infrastructure to use new password
4. Promote `*_PASS_NEXT` to `*_PASS_CURRENT`
5. Remove old password

---

### Redis Password Rotation

**Step 1: Add new password to Vault**

```bash
# Generate new password
NEW_REDIS_PASS=$(cat /dev/urandom | tr -dc 'a-zA-Z0-9' | head -c 32)

# Add as NEXT password
vault kv patch secret/mutt/prod REDIS_PASS_NEXT="$NEW_REDIS_PASS"

# Verify
vault kv get secret/mutt/prod | grep REDIS_PASS
```

**Step 2: Restart services** (they will now accept both passwords)

```bash
sudo systemctl restart mutt-*
```

**Step 3: Update Redis to use new password**

```bash
# Update Redis configuration
sudo vi /etc/redis/redis.conf
requirepass NEW_REDIS_PASSWORD_HERE

# Restart Redis
sudo systemctl restart redis
```

**Step 4: Promote new password to CURRENT**

```bash
# Get new password
NEW_PASS=$(vault kv get -field=REDIS_PASS_NEXT secret/mutt/prod)

# Update Vault
vault kv patch secret/mutt/prod \
  REDIS_PASS_CURRENT="$NEW_PASS" \
  REDIS_PASS_NEXT=""

# Restart services to use only CURRENT
sudo systemctl restart mutt-*
```

**Step 5: Verify**

```bash
# Test Redis connection with new password
REDIS_PASS=$(vault kv get -field=REDIS_PASS_CURRENT secret/mutt/prod)
redis-cli -a "$REDIS_PASS" PING
# Expected: PONG
```

---

### PostgreSQL Password Rotation

**Step 1: Add new password to Vault**

```bash
NEW_DB_PASS=$(cat /dev/urandom | tr -dc 'a-zA-Z0-9' | head -c 32)
vault kv patch secret/mutt/prod DB_PASS_NEXT="$NEW_DB_PASS"
```

**Step 2: Restart services**

```bash
sudo systemctl restart mutt-*
```

**Step 3: Update PostgreSQL user password**

```sql
-- Connect as postgres superuser
sudo -u postgres psql

-- Change password
ALTER USER mutt_user WITH PASSWORD 'NEW_DB_PASSWORD_HERE';
\q
```

**Step 4: Promote new password**

```bash
NEW_PASS=$(vault kv get -field=DB_PASS_NEXT secret/mutt/prod)
vault kv patch secret/mutt/prod \
  DB_PASS_CURRENT="$NEW_PASS" \
  DB_PASS_NEXT=""

sudo systemctl restart mutt-*
```

**Step 5: Verify**

```bash
DB_PASS=$(vault kv get -field=DB_PASS_CURRENT secret/mutt/prod)
PGPASSWORD="$DB_PASS" psql -h localhost -U mutt_user -d mutt -c "SELECT 1;"
```

---

### API Key Rotation

**Step 1: Generate new API key**

```bash
NEW_API_KEY="mutt-ingest-$(uuidgen)"
vault kv patch secret/mutt/prod INGEST_API_KEY="$NEW_API_KEY"
```

**Step 2: Restart ingestor**

```bash
sudo systemctl restart mutt-ingestor
```

**Step 3: Update client systems**

```bash
# Update all systems sending events to use new API key
# (Coordinate with application teams)
```

**Step 4: Verify**

```bash
# Test with new API key
API_KEY=$(vault kv get -field=INGEST_API_KEY secret/mutt/prod)
curl -X POST http://localhost:8080/ingest \
  -H "X-API-Key: $API_KEY" \
  -H "Content-Type: application/json" \
  -d '{"test": "event", "timestamp": "'$(date -u +%Y-%m-%dT%H:%M:%SZ)'"}'
```

---

## Configuration Migration

### Migrating from v2.3 to v2.5

**Major Changes:**
- Dynamic configuration support added
- Canonical config key names (breaking change)
- Audit logging for all configuration changes

**Migration Steps:**

**Step 1: Backup v2.3 configuration**

```bash
# Backup current config
sudo cp /etc/mutt/mutt.env /etc/mutt/mutt.env.v23.backup
```

**Step 2: Update environment file**

```bash
# Add new variables for v2.5
sudo vi /etc/mutt/mutt.env

# Add:
DYNAMIC_CONFIG_ENABLED=true  # Enable dynamic config
RETENTION_ENABLED=true       # Enable data retention (new in v2.5)
```

**Step 3: Update configuration keys**

```bash
# Legacy keys (v2.3) → Canonical keys (v2.5)

# OLD: alerter_queue_warn
# NEW: alerter_queue_warn_threshold

# OLD: alerter_queue_shed
# NEW: alerter_queue_shed_threshold

# Update in environment file if using static config
```

**Step 4: Initialize dynamic configuration**

```bash
cd /opt/mutt
source venv/bin/activate
python scripts/init_dynamic_config.py
```

**Step 5: Restart services**

```bash
sudo systemctl restart mutt-*
```

**Step 6: Verify migration**

```bash
# Check dynamic config loaded
redis-cli KEYS "mutt:config:*"

# Check services using new config
sudo journalctl -u mutt-* -n 100 | grep -i "config\|threshold"
```

---

## Best Practices

### DO:

✅ **Always backup before making changes**
```bash
sudo cp /etc/mutt/mutt.env /etc/mutt/mutt.env.backup.$(date +%Y%m%d_%H%M%S)
```

✅ **Validate configuration before restarting services**
```bash
/usr/local/bin/validate_mutt_config.sh && sudo systemctl restart mutt-*
```

✅ **Use dynamic config for tunable parameters** (thresholds, timeouts, batch sizes)

✅ **Use static config for infrastructure settings** (hostnames, ports, TLS)

✅ **Document the reason for configuration changes** (in audit logs)

✅ **Test configuration changes in staging first**

✅ **Rotate secrets regularly** (quarterly for passwords, annually for certificates)

✅ **Enable Redis persistence** (AOF or RDB) to retain dynamic config across restarts

✅ **Monitor audit logs for unauthorized changes**

---

### DON'T:

❌ **Don't store secrets in environment files** - use Vault instead

❌ **Don't change configuration during peak traffic** - schedule during maintenance windows

❌ **Don't skip validation** - always run validation scripts before restart

❌ **Don't modify dynamic config directly in Redis without publishing** - use muttdev CLI or API

❌ **Don't delete audit logs** - retain for compliance (365 days minimum)

❌ **Don't use weak passwords** - use strong random passwords (32+ characters)

❌ **Don't share Vault tokens** - each admin should have their own token

❌ **Don't restart all services simultaneously** - rolling restart preferred

---

## Troubleshooting

### Issue: Dynamic Config Not Loading

**Symptoms:**
- Configuration changes not reflected in services
- Services using default values instead of Redis values

**Diagnosis:**
```bash
# Check if feature is enabled
grep DYNAMIC_CONFIG_ENABLED /etc/mutt/mutt.env

# Check Redis connectivity
redis-cli PING

# Check if config keys exist
redis-cli KEYS "mutt:config:*"

# Check service logs
sudo journalctl -u mutt-alerter -n 100 | grep -i "dynamic.*config"
```

**Resolution:**
```bash
# Enable dynamic config
sudo vi /etc/mutt/mutt.env
DYNAMIC_CONFIG_ENABLED=true

# Initialize config in Redis
python scripts/init_dynamic_config.py

# Restart services
sudo systemctl restart mutt-*
```

---

### Issue: Vault Authentication Failure

**Symptoms:**
- Services fail to start with Vault errors
- "permission denied" or "403 Forbidden" errors

**Diagnosis:**
```bash
# Check Vault token validity
export VAULT_TOKEN=$(cat /etc/mutt/vault_secret_id)
export VAULT_ADDR=$(grep VAULT_ADDR /etc/mutt/mutt.env | cut -d= -f2)
vault token lookup

# Check Vault connectivity
curl -s -k "$VAULT_ADDR/v1/sys/health" | jq .
```

**Resolution:**
```bash
# Renew token if expiring soon
vault token renew -increment=720h

# OR create new token
vault token create -policy=mutt-policy -ttl=720h

# Update secret ID file
echo "NEW_TOKEN" | sudo tee /etc/mutt/vault_secret_id
sudo chmod 600 /etc/mutt/vault_secret_id
sudo chown mutt:mutt /etc/mutt/vault_secret_id

# Restart services
sudo systemctl restart mutt-*
```

---

### Issue: Configuration Changes Not Persisting

**Symptoms:**
- Dynamic config resets after Redis restart
- Configuration lost after system reboot

**Diagnosis:**
```bash
# Check Redis persistence configuration
redis-cli CONFIG GET save
redis-cli CONFIG GET appendonly

# Check if RDB/AOF files exist
ls -lh /var/lib/redis/
```

**Resolution:**
```bash
# Enable Redis persistence
sudo vi /etc/redis/redis.conf

# Enable RDB snapshots
save 900 1
save 300 10
save 60 10000

# OR enable AOF (recommended)
appendonly yes
appendfsync everysec

# Restart Redis
sudo systemctl restart redis

# Verify persistence
redis-cli CONFIG GET save
redis-cli CONFIG GET appendonly
```

---

## Summary

### Configuration Management Checklist

**Initial Setup:**
- [ ] Deploy static configuration to `/etc/mutt/mutt.env`
- [ ] Configure Vault authentication and secrets
- [ ] Initialize dynamic configuration in Redis
- [ ] Enable Redis persistence (AOF/RDB)
- [ ] Validate configuration with validation script
- [ ] Create initial configuration backup

**Ongoing Operations:**
- [ ] Use dynamic config for tunable parameters
- [ ] Use static config for infrastructure settings
- [ ] Document all configuration changes in audit logs
- [ ] Back up configuration daily (automated)
- [ ] Rotate secrets quarterly
- [ ] Review audit logs monthly
- [ ] Test configuration changes in staging first
- [ ] Validate before restarting services

**Incident Response:**
- [ ] Restore from backup if needed
- [ ] Review audit logs for unauthorized changes
- [ ] Rotate compromised secrets immediately
- [ ] Notify security team of breaches

---

## Next Steps

For additional operational guidance:

1. **Service Operations**: [SERVICE_OPERATIONS.md](SERVICE_OPERATIONS.md) - Service management, scaling, maintenance
2. **Troubleshooting**: [TROUBLESHOOTING_GUIDE.md](TROUBLESHOOTING_GUIDE.md) - Problem diagnosis and resolution
3. **Monitoring & Alerting**: [MONITORING_ALERTING.md](MONITORING_ALERTING.md) (coming soon) - Prometheus setup, alerting rules
4. **Backup & Recovery**: [BACKUP_RECOVERY.md](BACKUP_RECOVERY.md) (coming soon) - Disaster recovery procedures

---

**Document Metadata:**
- **Version**: 1.0
- **Last Updated**: 2025-11-10
- **Maintainer**: MUTT Operations Team
- **Feedback**: Report issues via internal ticketing system
