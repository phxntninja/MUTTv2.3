# MUTT v2.5 - Comprehensive Troubleshooting Guide

**Target Audience:** System Administrators, DevOps Engineers, Site Reliability Engineers, Support Engineers
**Priority Level:** P1 (Critical)
**Last Updated:** 2025-11-10

---

## Table of Contents

1. [Troubleshooting Methodology](#troubleshooting-methodology)
2. [Quick Diagnosis Decision Tree](#quick-diagnosis-decision-tree)
3. [Service-Specific Troubleshooting](#service-specific-troubleshooting)
4. [Infrastructure Troubleshooting](#infrastructure-troubleshooting)
5. [Network and Connectivity Issues](#network-and-connectivity-issues)
6. [Performance Troubleshooting](#performance-troubleshooting)
7. [Data Flow Troubleshooting](#data-flow-troubleshooting)
8. [Common Error Messages](#common-error-messages)
9. [Log Analysis Techniques](#log-analysis-techniques)
10. [Advanced Debugging Workflows](#advanced-debugging-workflows)
11. [Known Issues and Workarounds](#known-issues-and-workarounds)
12. [Escalation Procedures](#escalation-procedures)

---

## Troubleshooting Methodology

### The Five-Step Approach

Follow this systematic approach for all MUTT troubleshooting:

**Step 1: IDENTIFY**
- What is the symptom?
- When did it start?
- What changed recently?
- Is it affecting all users/events or specific ones?

**Step 2: ISOLATE**
- Which service(s) are affected?
- Is infrastructure (Redis/PostgreSQL/Vault) healthy?
- Can you reproduce the issue?

**Step 3: INVESTIGATE**
- Check service logs
- Review metrics
- Inspect queue depths
- Examine configuration

**Step 4: IMPLEMENT**
- Apply fix/workaround
- Document the change
- Monitor for resolution

**Step 5: ITERATE**
- Did the fix work?
- If no, return to Step 3
- If yes, perform root cause analysis

---

### Essential Diagnostic Commands

**Quick Health Check:**
```bash
# Service status
sudo systemctl status mutt-* | grep "Active:"

# Infrastructure status
redis-cli PING && echo "Redis: OK" || echo "Redis: FAIL"
sudo -u postgres psql -c "SELECT 1;" && echo "PostgreSQL: OK" || echo "PostgreSQL: FAIL"

# Queue depths
echo "Ingest Queue: $(redis-cli LLEN mutt:ingest_queue)"
echo "Alert Queue: $(redis-cli LLEN mutt:alert_queue)"
echo "Moog DLQ: $(redis-cli LLEN mutt:dlq:moog)"

# Health endpoints
for port in 8080 8081 8082 8087 8090; do
    echo -n "Port $port: "
    curl -s -o /dev/null -w "%{http_code}" http://localhost:$port/health
    echo ""
done
```

**Resource Usage:**
```bash
# CPU usage (top 10 processes)
ps aux --sort=-%cpu | head -11

# Memory usage
free -h

# Disk usage
df -h /var/log /opt/mutt /var/lib/pgsql

# Network connections
ss -tunap | grep -E ':(8080|8081|8082|8087|8090|6379|5432)'
```

**Log Tail (All Services):**
```bash
# Real-time logs from all MUTT services
sudo journalctl -u mutt-* -f --since "5 minutes ago"

# Errors only
sudo journalctl -u mutt-* --priority=err --since "1 hour ago"

# Specific service
sudo journalctl -u mutt-alerter -n 100 --no-pager
```

---

## Quick Diagnosis Decision Tree

```
┌─────────────────────────────────────┐
│   Is Ingestor receiving requests?   │
└──────────┬──────────────────────────┘
           │
    ┌──────┴───────┐
    NO             YES
    │              │
    v              v
┌─────────────┐  ┌────────────────────────┐
│Check:       │  │ Are events in Redis    │
│- Firewall   │  │ ingest queue growing?  │
│- Service    │  └──────────┬─────────────┘
│- Vault      │             │
│- Redis      │      ┌──────┴───────┐
└─────────────┘      NO             YES
                     │              │
                     v              v
              ┌─────────────┐  ┌──────────────┐
              │ Good! Check │  │ Alerter slow │
              │ if alerts   │  │ Check:       │
              │ forwarding  │  │ - Alerter    │
              │             │  │ - PostgreSQL │
              └─────────────┘  │ - CPU/Memory │
                               └──────────────┘

                 ┌──────────────────────────┐
                 │ Are alerts reaching Moog?│
                 └──────────┬───────────────┘
                            │
                     ┌──────┴───────┐
                     NO             YES
                     │              │
                     v              v
              ┌────────────────┐  ┌──────────────┐
              │ Moog Forwarder │  │ System       │
              │ Check:         │  │ Healthy!     │
              │ - Service      │  │              │
              │ - DLQ depth    │  └──────────────┘
              │ - Circuit      │
              │   breaker      │
              │ - Moog health  │
              └────────────────┘
```

---

## Service-Specific Troubleshooting

### Ingestor Service Troubleshooting

#### Symptom: Ingestor Returns 503 Service Unavailable

**Possible Causes:**
1. Ingest queue is full (backpressure)
2. Redis is unreachable
3. Rate limiting triggered

**Diagnosis:**
```bash
# Check queue depth vs cap
QUEUE_DEPTH=$(redis-cli LLEN mutt:ingest_queue)
QUEUE_CAP=$(grep INGEST_QUEUE_CAP /etc/mutt/mutt.env | cut -d= -f2)
echo "Queue Depth: $QUEUE_DEPTH / $QUEUE_CAP"

# Check rate limiting
curl -s http://localhost:9090/metrics | grep 'mutt_ingest_requests_total{status="fail",reason="rate_limit"}'

# Check Redis connectivity
redis-cli PING
```

**Resolution:**

**If backpressure (queue full):**
```bash
# Option 1: Scale alerter to process faster (permanent)
# See Service Operations Guide - Scaling section

# Option 2: Increase queue cap temporarily
sudo vi /etc/mutt/mutt.env
INGEST_QUEUE_CAP=2000000  # Double the cap

sudo systemctl restart mutt-ingestor

# Option 3: Enable shedding if queue is unrecoverable
# Drain old events to DLQ
redis-cli RPOPLPUSH mutt:ingest_queue mutt:dlq:old_events
# Repeat until queue depth is acceptable
```

**If rate limiting:**
```bash
# Check current rate limit
grep -E 'INGEST_MAX_RATE|INGEST_RATE_WINDOW' /etc/mutt/mutt.env

# Increase rate limit if legitimate traffic
sudo vi /etc/mutt/mutt.env
INGEST_MAX_RATE=2000  # Increase from 1000

sudo systemctl restart mutt-ingestor
```

**If Redis unreachable:**
```bash
# Check Redis status
sudo systemctl status redis

# Check Redis logs
sudo journalctl -u redis -n 50

# Restart Redis if needed
sudo systemctl restart redis
sudo systemctl restart mutt-ingestor
```

---

#### Symptom: Ingestor Returns 401 Unauthorized

**Possible Causes:**
1. API key missing or incorrect
2. Vault connectivity issue
3. API key not in Vault

**Diagnosis:**
```bash
# Test with known good API key
curl -X POST http://localhost:8080/ingest \
  -H "X-API-Key: YOUR_API_KEY" \
  -H "Content-Type: application/json" \
  -d '{"test": "event"}'

# Check Vault connectivity
vault_addr=$(grep VAULT_ADDR /etc/mutt/mutt.env | cut -d= -f2)
curl -s -k "$vault_addr/v1/sys/health" | jq .

# Check ingestor logs for auth errors
sudo journalctl -u mutt-ingestor -n 100 | grep -i "auth\|unauthorized\|api.key"
```

**Resolution:**

**If API key not in Vault:**
```bash
# Add API key to Vault (via Vault CLI)
vault kv put secret/mutt/prod INGEST_API_KEY="your-secure-api-key"

# Restart ingestor to reload from Vault
sudo systemctl restart mutt-ingestor

# Verify Vault secret
vault kv get secret/mutt/prod
```

**If Vault unreachable:**
```bash
# Check Vault status
systemctl status vault  # If Vault is local

# Check network connectivity to Vault
vault_addr=$(grep VAULT_ADDR /etc/mutt/mutt.env | cut -d= -f2 | sed 's|https://||' | cut -d: -f1)
ping -c 3 $vault_addr

# Check TLS certificate validity
vault_addr=$(grep VAULT_ADDR /etc/mutt/mutt.env | cut -d= -f2)
openssl s_client -connect $(echo $vault_addr | sed 's|https://||') -CAfile /etc/mutt/certs/vault-ca.crt

# Temporary: Use environment variable override (NOT recommended for production)
export VAULT_TOKEN="temporary-token"
sudo -E systemctl restart mutt-ingestor
```

---

#### Symptom: High Latency in Ingestor (> 100ms p95)

**Possible Causes:**
1. Gunicorn worker saturation
2. Redis latency
3. Slow Vault token renewal

**Diagnosis:**
```bash
# Check Gunicorn worker count
ps aux | grep "gunicorn.*ingestor" | wc -l

# Check CPU usage per worker
ps aux --sort=-%cpu | grep gunicorn | head -5

# Check Redis latency
redis-cli --latency-history

# Check ingestor metrics
curl -s http://localhost:9090/metrics | grep mutt_ingest_latency_seconds
```

**Resolution:**

**If worker saturation:**
```bash
# Increase Gunicorn workers (recommend 2× CPU cores)
sudo vi /etc/systemd/system/mutt-ingestor.service

# Change --workers value
ExecStart=/opt/mutt/venv/bin/gunicorn \
    --workers 8 \  # Increase from 4
    ...

sudo systemctl daemon-reload
sudo systemctl restart mutt-ingestor
```

**If Redis latency:**
```bash
# Check Redis memory usage
redis-cli INFO memory

# Check for slow commands
redis-cli SLOWLOG GET 10

# Tune Redis if needed
sudo vi /etc/redis/redis.conf
maxmemory 8gb
maxmemory-policy allkeys-lru

sudo systemctl restart redis
```

---

### Alerter Service Troubleshooting

#### Symptom: Events Stuck in Ingest Queue (Not Processing)

**Possible Causes:**
1. Alerter service down/crashed
2. PostgreSQL connection failure
3. Infinite loop in rule processing
4. Backpressure shedding enabled

**Diagnosis:**
```bash
# Check alerter status
sudo systemctl status mutt-alerter

# Check if alerter is consuming from queue
watch -n 5 'redis-cli LLEN mutt:ingest_queue'
# If decreasing = healthy, if constant = stuck

# Check alerter logs for errors
sudo journalctl -u mutt-alerter -n 100 --no-pager | grep -i error

# Check processing list depth
POD_NAME=$(grep POD_NAME /etc/mutt/mutt.env | cut -d= -f2)
redis-cli LLEN "mutt:processing:alerter:$POD_NAME"

# Check PostgreSQL connectivity
sudo -u postgres psql -U mutt_user -d mutt -c "SELECT count(*) FROM alert_rules WHERE enabled = true;"
```

**Resolution:**

**If alerter crashed:**
```bash
# Check crash logs
sudo journalctl -u mutt-alerter --since "1 hour ago" | tail -100

# Check for OOM (Out of Memory) kill
sudo dmesg | grep -i "mutt.*killed"

# Restart alerter
sudo systemctl restart mutt-alerter

# Monitor for stability
watch -n 5 'systemctl status mutt-alerter'
```

**If PostgreSQL connection failure:**
```bash
# Check PostgreSQL status
sudo systemctl status postgresql

# Check PostgreSQL logs
sudo tail -100 /var/lib/pgsql/data/log/postgresql-*.log

# Test connection
psql -h localhost -U mutt_user -d mutt -c "SELECT 1;"

# If password issue, update Vault secret
vault kv get secret/mutt/prod | grep DB_PASS

# Restart alerter after fixing database
sudo systemctl restart mutt-alerter
```

**If backpressure shedding:**
```bash
# Check backpressure config
redis-cli GET mutt:config:alerter_queue_shed_threshold
redis-cli GET mutt:config:alerter_shed_mode

# Check if queue exceeded threshold
QUEUE_DEPTH=$(redis-cli LLEN mutt:ingest_queue)
SHED_THRESHOLD=$(redis-cli GET mutt:config:alerter_queue_shed_threshold)
echo "Queue: $QUEUE_DEPTH, Threshold: $SHED_THRESHOLD"

# If shedding to DLQ, check DLQ depth
redis-cli LLEN mutt:dlq:alerter

# Adjust thresholds dynamically (if DYNAMIC_CONFIG_ENABLED=true)
python scripts/muttdev.py config --set alerter_queue_shed_threshold 5000 --publish

# Or disable shedding temporarily
python scripts/muttdev.py config --set alerter_shed_mode none --publish
```

---

#### Symptom: Alerter High CPU Usage (> 80%)

**Possible Causes:**
1. High event volume
2. Inefficient rule patterns (regex complexity)
3. Large rule cache
4. BRPOPLPUSH timeout too low (CPU churn)

**Diagnosis:**
```bash
# Check CPU per process
top -b -n 1 | grep alerter_service

# Check event processing rate
curl -s http://localhost:9091/metrics | grep mutt_alerter_events_processed_total

# Check rule count
sudo -u postgres psql -U mutt_user -d mutt -c "SELECT count(*) FROM alert_rules WHERE enabled = true;"

# Check for complex regex patterns
sudo -u postgres psql -U mutt_user -d mutt -c "SELECT rule_name, pattern FROM alert_rules WHERE enabled = true AND pattern ~ '.*\(.*\|.*\).*';"

# Check BRPOPLPUSH timeout
grep BRPOPLPUSH_TIMEOUT /etc/mutt/mutt.env
```

**Resolution:**

**If high event volume (legitimate):**
```bash
# Scale horizontally: add more alerter instances
# On second server:
export POD_NAME=alerter-002
sudo systemctl start mutt-alerter

# OR scale vertically: increase CPU cores
# (Requires infrastructure change)
```

**If inefficient regex:**
```sql
-- Connect to PostgreSQL
sudo -u postgres psql -U mutt_user -d mutt

-- Identify slow/complex rules
SELECT rule_name, pattern, priority
FROM alert_rules
WHERE enabled = true
ORDER BY LENGTH(pattern) DESC
LIMIT 10;

-- Optimize regex (example: avoid backtracking)
-- Bad: .* at start and end causes backtracking
-- Good: Use more specific patterns

-- Update rule to be more efficient
UPDATE alert_rules
SET pattern = '^CPU.*threshold exceeded$'
WHERE rule_name = 'cpu_high';

-- Reload alerter cache
\q
sudo systemctl kill -s HUP mutt-alerter
```

**If large rule cache:**
```bash
# Check memory usage
ps aux | grep alerter_service | awk '{print $6}'

# Increase rule cache TTL to reduce reload frequency
sudo vi /etc/mutt/mutt.env
RULE_CACHE_TTL=600  # Increase from 300

sudo systemctl restart mutt-alerter
```

---

#### Symptom: Unhandled Events Not Triggering Meta-Alerts

**Possible Causes:**
1. Unhandled detection logic disabled
2. Unhandled key TTL too short
3. Rules matching everything (no unhandled events)

**Diagnosis:**
```bash
# Check unhandled keys in Redis
redis-cli KEYS "mutt:unhandled:*" | wc -l

# Sample unhandled keys
redis-cli KEYS "mutt:unhandled:*" | head -5

# Check TTL on unhandled keys
redis-cli TTL "mutt:unhandled:$(redis-cli KEYS 'mutt:unhandled:*' | head -1 | cut -d: -f3-)"

# Check alerter logs for unhandled detection
sudo journalctl -u mutt-alerter -n 200 | grep -i unhandled

# Check metrics
curl -s http://localhost:9091/metrics | grep mutt_alerter_unhandled_meta_alerts_total
```

**Resolution:**

**If unhandled detection disabled:**
```bash
# Check alerter code for feature flag (requires code review)
# Verify unhandled detection is enabled in code

# Check janitor is running (janitor creates meta-alerts)
sudo journalctl -u mutt-alerter -n 200 | grep -i janitor
```

**If TTL too short:**
```bash
# Unhandled keys should persist long enough for janitor to detect
# Check janitor interval
grep JANITOR_INTERVAL /etc/mutt/mutt.env

# Recommended: Unhandled TTL > 3× JANITOR_INTERVAL
# (This is hardcoded in alerter_service.py, requires code change if wrong)
```

**If rules matching everything:**
```sql
-- Check for overly broad rules
sudo -u postgres psql -U mutt_user -d mutt

SELECT rule_name, pattern, priority
FROM alert_rules
WHERE enabled = true
AND pattern IN ('.*', '.+', '.*.*')
ORDER BY priority ASC;

-- Remove or make more specific
UPDATE alert_rules
SET enabled = false
WHERE pattern = '.*';
```

---

### Moog Forwarder Service Troubleshooting

#### Symptom: DLQ Depth Growing Rapidly

**Possible Causes:**
1. Moogsoft is down/unreachable
2. Circuit breaker is open
3. Moogsoft API rejecting requests (400/401)
4. Rate limiting too aggressive

**Diagnosis:**
```bash
# Check DLQ depth
redis-cli LLEN mutt:dlq:moog

# Check circuit breaker state
curl -s http://localhost:9092/metrics | grep circuit_breaker

# Check Moogsoft connectivity
MOOG_URL=$(grep MOOG_WEBHOOK_URL /etc/mutt/mutt.env | cut -d= -f2)
curl -I "$MOOG_URL"

# Check forwarder logs for error patterns
sudo journalctl -u mutt-moog-forwarder -n 200 | grep -E "error|fail|DLQ"

# Check failure reasons in metrics
curl -s http://localhost:9092/metrics | grep 'mutt_moog_requests_total{status="fail"}'
```

**Resolution:**

**If Moogsoft is down:**
```bash
# Verify Moogsoft status externally (ping operations team)

# Circuit breaker will automatically retry after timeout
grep CIRCUIT_BREAKER_TIMEOUT /etc/mutt/mutt.env

# DLQ messages will be replayed by remediation service
sudo systemctl status mutt-remediation

# Monitor remediation replay
curl -s http://localhost:8086/metrics | grep mutt_remediation_replay
```

**If circuit breaker open:**
```bash
# Circuit breaker opens after N failures (default: 10)
grep CIRCUIT_BREAKER_THRESHOLD /etc/mutt/mutt.env

# Wait for timeout (default: 300 seconds)
# Circuit will auto-reset and retry

# To force immediate retry, restart forwarder (only if Moogsoft is healthy)
curl -I "$MOOG_URL"  # Verify Moogsoft is up
sudo systemctl restart mutt-moog-forwarder
```

**If Moogsoft rejecting requests (400/401):**
```bash
# Check forwarder logs for HTTP error codes
sudo journalctl -u mutt-moog-forwarder -n 100 | grep "HTTP"

# Sample a DLQ message to inspect payload
redis-cli LRANGE mutt:dlq:moog 0 1 | jq .

# If 401 (auth error), check Moogsoft API key
vault kv get secret/mutt/prod | grep MOOG_API_KEY

# If 400 (bad request), check payload format
# Compare against Moogsoft API docs
```

**If rate limiting:**
```bash
# Check rate limit hits
curl -s http://localhost:9092/metrics | grep mutt_moog_rate_limit_hits_total

# Check current rate limit
grep -E 'RATE_LIMIT_MAX_REQUESTS|RATE_LIMIT_WINDOW_SECONDS' /etc/mutt/mutt.env

# Increase rate limit if Moogsoft can handle it
sudo vi /etc/mutt/mutt.env
RATE_LIMIT_MAX_REQUESTS=200  # Increase from 100

sudo systemctl restart mutt-moog-forwarder
```

---

#### Symptom: Alerts Forwarding Slowly (High Latency)

**Possible Causes:**
1. Moogsoft API slow
2. Rate limiting delaying requests
3. Retry backoff delaying requests
4. Network latency

**Diagnosis:**
```bash
# Check Moog request latency metrics
curl -s http://localhost:9092/metrics | grep mutt_moog_request_latency_seconds

# Manually test Moogsoft latency
time curl -X POST "$MOOG_URL" \
  -H "Content-Type: application/json" \
  -d '{"severity": "info", "description": "Test alert", "source": "mutt-test"}'

# Check retry backoff in logs
sudo journalctl -u mutt-moog-forwarder -n 100 | grep -i "retry\|backoff"

# Check network latency
MOOG_HOST=$(echo "$MOOG_URL" | sed 's|https://||' | cut -d/ -f1 | cut -d: -f1)
ping -c 10 "$MOOG_HOST"
```

**Resolution:**

**If Moogsoft API slow:**
```bash
# Increase timeout to tolerate slow Moogsoft
sudo vi /etc/mutt/mutt.env
MOOG_TIMEOUT=30  # Increase from 10

sudo systemctl restart mutt-moog-forwarder

# Consider scaling Moogsoft (contact Moogsoft ops team)
```

**If retry backoff:**
```bash
# Check retry configuration
grep -E 'RETRY_MAX_ATTEMPTS|RETRY_INITIAL_DELAY|RETRY_MAX_DELAY|RETRY_BACKOFF_MULTIPLIER' /etc/mutt/mutt.env

# Reduce retry attempts to fail faster to DLQ
sudo vi /etc/mutt/mutt.env
RETRY_MAX_ATTEMPTS=3  # Reduce from 5

sudo systemctl restart mutt-moog-forwarder
```

**If network latency:**
```bash
# Check MTU and packet loss
ping -M do -s 1472 -c 10 "$MOOG_HOST"

# Traceroute to identify bottleneck
traceroute "$MOOG_HOST"

# Check for firewall/proxy interference
# (Escalate to network team)
```

---

### Remediation Service Troubleshooting

#### Symptom: DLQ Not Draining

**Possible Causes:**
1. Remediation service not running
2. Moogsoft health check failing
3. Poison messages blocking replay
4. Remediation interval too long

**Diagnosis:**
```bash
# Check remediation service status
sudo systemctl status mutt-remediation

# Check Moogsoft health metric
curl -s http://localhost:8086/metrics | grep mutt_remediation_moog_health

# Check replay metrics
curl -s http://localhost:8086/metrics | grep mutt_remediation_replay

# Check for poison messages
curl -s http://localhost:8086/metrics | grep mutt_remediation_poison_messages_total

# Check remediation logs
sudo journalctl -u mutt-remediation -n 100
```

**Resolution:**

**If service not running:**
```bash
# Start remediation service
sudo systemctl start mutt-remediation

# Check for startup errors
sudo journalctl -u mutt-remediation -n 50
```

**If Moogsoft health check failing:**
```bash
# Manually test Moogsoft health
MOOG_URL=$(grep MOOG_WEBHOOK_URL /etc/mutt/mutt.env | cut -d= -f2)
curl -I "$MOOG_URL"

# If Moogsoft is healthy, check health check config
grep MOOG_HEALTH_CHECK_ENABLED /etc/mutt/mutt.env

# Temporarily disable health check (NOT recommended)
sudo vi /etc/mutt/mutt.env
MOOG_HEALTH_CHECK_ENABLED=false

sudo systemctl restart mutt-remediation
```

**If poison messages:**
```bash
# Check dead letter queue for poison messages
redis-cli LLEN mutt:dlq:dead

# Sample poison messages
redis-cli LRANGE mutt:dlq:dead 0 5 | jq .

# Investigate why messages are poison (check logs)
sudo journalctl -u mutt-remediation -n 500 | grep -i poison

# Manually fix and re-queue (see Common Tasks section)
```

**If interval too long:**
```bash
# Check current interval
grep REMEDIATION_INTERVAL /etc/mutt/mutt.env

# Decrease interval for faster drain
sudo vi /etc/mutt/mutt.env
REMEDIATION_INTERVAL=60  # Decrease from 300

sudo systemctl restart mutt-remediation
```

---

### Web UI Service Troubleshooting

#### Symptom: Dashboard Returns 500 Internal Server Error

**Possible Causes:**
1. Redis connection failure
2. PostgreSQL connection failure
3. Vault connection failure
4. API key authentication issue

**Diagnosis:**
```bash
# Check Web UI logs
sudo journalctl -u mutt-webui -n 100 --no-pager | grep -E "error|500"

# Check infrastructure connectivity
redis-cli PING
sudo -u postgres psql -U mutt_user -d mutt -c "SELECT 1;"

# Test dashboard directly
curl -I http://localhost:8090/

# Check Vault connectivity
vault_addr=$(grep VAULT_ADDR /etc/mutt/mutt.env | cut -d= -f2)
curl -s -k "$vault_addr/v1/sys/health"
```

**Resolution:**

**If Redis connection failure:**
```bash
# Check Redis status
sudo systemctl status redis

# Check Redis connectivity from Web UI perspective
redis-cli -h $(grep REDIS_HOST /etc/mutt/mutt.env | cut -d= -f2) PING

# Restart Web UI after fixing Redis
sudo systemctl restart redis
sudo systemctl restart mutt-webui
```

**If PostgreSQL connection failure:**
```bash
# Check PostgreSQL status
sudo systemctl status postgresql

# Check connection pool exhaustion
sudo -u postgres psql -c "SELECT count(*) FROM pg_stat_activity WHERE usename = 'mutt_user';"

# Check max connections
sudo -u postgres psql -c "SHOW max_connections;"

# Restart Web UI to reset connection pool
sudo systemctl restart mutt-webui
```

**If Vault connection failure:**
```bash
# Check Vault connectivity
vault_addr=$(grep VAULT_ADDR /etc/mutt/mutt.env | cut -d= -f2)
curl -s -k "$vault_addr/v1/sys/health" | jq .

# Check Vault token validity
cat /etc/mutt/vault_secret_id

# Renew Vault token if expired (via Vault admin)
vault token renew

# Restart Web UI
sudo systemctl restart mutt-webui
```

---

#### Symptom: API Endpoints Return Slow (> 5 seconds)

**Possible Causes:**
1. Database query performance
2. Metrics cache expired (re-fetching)
3. Connection pool exhaustion

**Diagnosis:**
```bash
# Check slow queries in PostgreSQL
sudo -u postgres psql -U mutt_user -d mutt -c "SELECT query, calls, mean_exec_time, max_exec_time FROM pg_stat_statements ORDER BY mean_exec_time DESC LIMIT 10;"

# Check metrics cache TTL
grep METRICS_CACHE_TTL /etc/mutt/mutt.env

# Check connection pool metrics
curl -s http://localhost:8090/metrics | grep -i pool

# Check Web UI logs for slow requests
sudo journalctl -u mutt-webui -n 200 | grep -E "GET|POST" | grep -E "[5-9][0-9]{3}ms|[0-9]{5}ms"
```

**Resolution:**

**If slow queries:**
```sql
-- Connect to PostgreSQL
sudo -u postgres psql -U mutt_user -d mutt

-- Analyze table statistics
ANALYZE alert_rules;
ANALYZE audit_logs;
ANALYZE dev_hosts;
ANALYZE device_teams;

-- Check for missing indexes
SELECT schemaname, tablename, indexname
FROM pg_indexes
WHERE schemaname = 'public';

-- Create missing indexes if needed
CREATE INDEX IF NOT EXISTS idx_alert_rules_enabled ON alert_rules(enabled);
CREATE INDEX IF NOT EXISTS idx_audit_logs_timestamp ON audit_logs(timestamp DESC);
```

**If metrics cache:**
```bash
# Increase cache TTL
sudo vi /etc/mutt/mutt.env
METRICS_CACHE_TTL=10  # Increase from 5

sudo systemctl restart mutt-webui
```

**If connection pool exhaustion:**
```bash
# Increase PostgreSQL pool size
sudo vi /etc/mutt/mutt.env
POSTGRES_POOL_MAX=20  # Increase from 10

sudo systemctl restart mutt-webui
```

---

## Infrastructure Troubleshooting

### Redis Troubleshooting

#### Symptom: Redis Out of Memory (OOM)

**Diagnosis:**
```bash
# Check Redis memory usage
redis-cli INFO memory | grep -E "used_memory_human|maxmemory_human|mem_fragmentation_ratio"

# Check queue depths
redis-cli LLEN mutt:ingest_queue
redis-cli LLEN mutt:alert_queue
redis-cli LLEN mutt:dlq:moog

# Check key count
redis-cli DBSIZE

# Check for large keys
redis-cli --bigkeys
```

**Resolution:**

**Immediate (free memory):**
```bash
# Delete old unhandled keys (> 7 days)
redis-cli --scan --pattern "mutt:unhandled:*" | while read key; do
    ttl=$(redis-cli TTL "$key")
    if [ "$ttl" -lt 0 ] || [ "$ttl" -gt 604800 ]; then
        redis-cli DEL "$key"
    fi
done

# Check for stuck keys without TTL
redis-cli --scan --pattern "mutt:*" | while read key; do
    ttl=$(redis-cli TTL "$key")
    if [ "$ttl" -eq -1 ]; then
        echo "$key has no TTL"
    fi
done
```

**Short-term (increase memory):**
```bash
# Increase Redis maxmemory
sudo vi /etc/redis/redis.conf
maxmemory 8gb  # Increase from current

sudo systemctl restart redis
```

**Long-term (scale):**
```bash
# Option 1: Implement queue caps
sudo vi /etc/mutt/mutt.env
INGEST_QUEUE_CAP=500000

sudo systemctl restart mutt-ingestor

# Option 2: Scale Redis vertically (add RAM)

# Option 3: Implement Redis Sentinel for HA
# (See Service Operations Guide - Scaling section)
```

---

#### Symptom: Redis High Latency (> 10ms)

**Diagnosis:**
```bash
# Check latency
redis-cli --latency-history

# Check slow log
redis-cli SLOWLOG GET 10

# Check CPU usage
top -b -n 1 | grep redis

# Check memory fragmentation
redis-cli INFO memory | grep mem_fragmentation_ratio
# Healthy: 1.0-1.5, High: > 2.0
```

**Resolution:**

**If memory fragmentation:**
```bash
# Restart Redis to defragment
sudo systemctl restart redis

# OR use active defragmentation (Redis 4.0+)
redis-cli CONFIG SET activedefrag yes
```

**If slow commands:**
```bash
# Identify slow commands
redis-cli SLOWLOG GET 10

# Common culprits: KEYS (use SCAN instead)
# If KEYS commands found, audit code for KEYS usage

# Increase slowlog threshold if needed
redis-cli CONFIG SET slowlog-log-slower-than 10000  # 10ms
```

**If CPU bound:**
```bash
# Check for blocking operations
redis-cli INFO stats | grep blocked_clients

# Scale Redis vertically (add CPU cores)
# OR distribute load across multiple Redis instances (if applicable)
```

---

### PostgreSQL Troubleshooting

#### Symptom: PostgreSQL Connection Exhaustion

**Diagnosis:**
```bash
# Check current connections
sudo -u postgres psql -c "SELECT count(*) AS current_connections, max_connections FROM (SELECT count(*) FROM pg_stat_activity) AS current, (SELECT setting::int AS max_connections FROM pg_settings WHERE name = 'max_connections') AS max;"

# Check connections by application
sudo -u postgres psql -c "SELECT application_name, count(*) FROM pg_stat_activity GROUP BY application_name ORDER BY count DESC;"

# Check for idle connections
sudo -u postgres psql -c "SELECT count(*) FROM pg_stat_activity WHERE state = 'idle' AND state_change < NOW() - INTERVAL '10 minutes';"
```

**Resolution:**

**Immediate (kill idle connections):**
```bash
sudo -u postgres psql <<EOF
SELECT pg_terminate_backend(pid)
FROM pg_stat_activity
WHERE state = 'idle'
AND state_change < NOW() - INTERVAL '10 minutes'
AND pid <> pg_backend_pid();
EOF
```

**Short-term (increase max_connections):**
```bash
sudo vi /var/lib/pgsql/data/postgresql.conf
max_connections = 200  # Increase from 100

sudo systemctl restart postgresql
```

**Long-term (connection pooling):**
```bash
# Install PgBouncer
sudo yum install pgbouncer -y

# Configure PgBouncer
sudo vi /etc/pgbouncer/pgbouncer.ini
[databases]
mutt = host=localhost port=5432 dbname=mutt

[pgbouncer]
listen_addr = 0.0.0.0
listen_port = 6432
pool_mode = transaction
max_client_conn = 200
default_pool_size = 25

sudo systemctl start pgbouncer
sudo systemctl enable pgbouncer

# Update MUTT services to use PgBouncer
sudo vi /etc/mutt/mutt.env
POSTGRES_PORT=6432

sudo systemctl restart mutt-alerter mutt-webui
```

---

#### Symptom: Slow PostgreSQL Queries

**Diagnosis:**
```bash
# Enable pg_stat_statements (if not already)
sudo -u postgres psql -c "CREATE EXTENSION IF NOT EXISTS pg_stat_statements;"

# Check slow queries
sudo -u postgres psql -U mutt_user -d mutt <<EOF
SELECT query, calls, mean_exec_time, max_exec_time, total_exec_time
FROM pg_stat_statements
WHERE query NOT LIKE '%pg_stat_statements%'
ORDER BY mean_exec_time DESC
LIMIT 10;
EOF

# Check for missing indexes
sudo -u postgres psql -U mutt_user -d mutt -c "SELECT schemaname, tablename, indexname FROM pg_indexes WHERE schemaname = 'public';"

# Check table bloat
sudo -u postgres psql -U mutt_user -d mutt -c "SELECT schemaname, tablename, pg_size_pretty(pg_total_relation_size(schemaname||'.'||tablename)) AS size FROM pg_tables WHERE schemaname = 'public' ORDER BY pg_total_relation_size(schemaname||'.'||tablename) DESC;"
```

**Resolution:**

**If missing indexes:**
```sql
-- Connect to PostgreSQL
sudo -u postgres psql -U mutt_user -d mutt

-- Create recommended indexes
CREATE INDEX IF NOT EXISTS idx_alert_rules_enabled ON alert_rules(enabled) WHERE enabled = true;
CREATE INDEX IF NOT EXISTS idx_alert_rules_priority ON alert_rules(priority DESC);
CREATE INDEX IF NOT EXISTS idx_audit_logs_timestamp ON audit_logs(timestamp DESC);
CREATE INDEX IF NOT EXISTS idx_audit_logs_user ON audit_logs(changed_by);

-- Analyze tables to update statistics
ANALYZE alert_rules;
ANALYZE audit_logs;
ANALYZE dev_hosts;
ANALYZE device_teams;
```

**If table bloat:**
```bash
# Vacuum tables to reclaim space
sudo -u postgres psql -U mutt_user -d mutt <<EOF
VACUUM FULL ANALYZE alert_rules;
VACUUM FULL ANALYZE audit_logs;
EOF
```

**If insufficient resources:**
```bash
# Tune PostgreSQL configuration
sudo vi /var/lib/pgsql/data/postgresql.conf

# Increase shared_buffers (25% of RAM)
shared_buffers = 2GB

# Increase work_mem (for sorts/joins)
work_mem = 16MB

# Increase effective_cache_size (50-75% of RAM)
effective_cache_size = 6GB

sudo systemctl restart postgresql
```

---

### Vault Troubleshooting

#### Symptom: Services Cannot Authenticate to Vault

**Diagnosis:**
```bash
# Check Vault status
vault_addr=$(grep VAULT_ADDR /etc/mutt/mutt.env | cut -d= -f2)
curl -s -k "$vault_addr/v1/sys/health" | jq .

# Check Vault token validity
cat /etc/mutt/vault_secret_id

# Test Vault authentication
export VAULT_ADDR="$vault_addr"
export VAULT_TOKEN=$(cat /etc/mutt/vault_secret_id)
vault kv get secret/mutt/prod

# Check service logs for Vault errors
sudo journalctl -u mutt-* -n 200 | grep -i vault
```

**Resolution:**

**If token expired:**
```bash
# Generate new token (via Vault admin)
vault token create -policy=mutt-policy -ttl=720h

# Update secret ID file
echo "NEW_TOKEN_HERE" | sudo tee /etc/mutt/vault_secret_id
sudo chmod 600 /etc/mutt/vault_secret_id
sudo chown mutt:mutt /etc/mutt/vault_secret_id

# Restart services
sudo systemctl restart mutt-*
```

**If Vault sealed:**
```bash
# Check seal status
vault status

# Unseal Vault (requires unseal keys from Vault admin)
vault operator unseal <unseal-key-1>
vault operator unseal <unseal-key-2>
vault operator unseal <unseal-key-3>

# Restart services after Vault is unsealed
sudo systemctl restart mutt-*
```

**If network/TLS issues:**
```bash
# Test connectivity
vault_host=$(echo "$vault_addr" | sed 's|https://||' | cut -d: -f1)
ping -c 3 "$vault_host"

# Test TLS
vault_host_port=$(echo "$vault_addr" | sed 's|https://||')
openssl s_client -connect "$vault_host_port" -CAfile /etc/mutt/certs/vault-ca.crt

# Verify CA certificate is valid
openssl x509 -in /etc/mutt/certs/vault-ca.crt -text -noout
```

---

## Network and Connectivity Issues

### Firewall Blocking Traffic

**Symptom:** Ingestor not receiving external traffic

**Diagnosis:**
```bash
# Check if port 8080 is open
sudo firewall-cmd --list-ports

# Check if service is listening
sudo ss -tunlp | grep 8080

# Test connectivity from external host
curl http://<mutt-server-ip>:8080/health
```

**Resolution:**
```bash
# Add firewall rule
sudo firewall-cmd --zone=public --add-port=8080/tcp --permanent
sudo firewall-cmd --reload

# Verify rule
sudo firewall-cmd --list-ports
```

---

### SELinux Blocking Service

**Symptom:** Service fails to start with "Permission denied" errors

**Diagnosis:**
```bash
# Check SELinux status
getenforce

# Check for SELinux denials
sudo ausearch -m avc -ts recent | grep mutt

# Check service logs for SELinux errors
sudo journalctl -u mutt-ingestor -n 100 | grep -i selinux
```

**Resolution:**

**Option 1: Create SELinux policy (recommended):**
```bash
# Generate policy from denials
sudo ausearch -m avc -ts recent | audit2allow -M mutt_policy

# Install policy
sudo semodule -i mutt_policy.pp

# Restart service
sudo systemctl restart mutt-ingestor
```

**Option 2: Set SELinux to permissive (temporary):**
```bash
# Permissive mode for troubleshooting only
sudo setenforce 0

# Check if service works
sudo systemctl start mutt-ingestor

# Re-enable enforcing and create proper policy
sudo setenforce 1
```

---

### DNS Resolution Issues

**Symptom:** Cannot connect to Vault/Moogsoft by hostname

**Diagnosis:**
```bash
# Test DNS resolution
nslookup vault.example.com
nslookup moogsoft.example.com

# Check /etc/resolv.conf
cat /etc/resolv.conf

# Test with IP address instead
vault_ip="10.0.1.50"
curl -k "https://$vault_ip:8200/v1/sys/health"
```

**Resolution:**
```bash
# Option 1: Add to /etc/hosts
echo "10.0.1.50 vault.example.com" | sudo tee -a /etc/hosts
echo "10.0.2.100 moogsoft.example.com" | sudo tee -a /etc/hosts

# Option 2: Fix DNS servers in /etc/resolv.conf
sudo vi /etc/resolv.conf
nameserver 8.8.8.8
nameserver 8.8.4.4

# Restart network
sudo systemctl restart network
```

---

## Performance Troubleshooting

### High Event Latency (End-to-End)

**Symptom:** Events take > 10 seconds from ingest to Moogsoft

**Diagnosis:**
```bash
# Measure latency at each stage

# 1. Ingest latency
curl -s http://localhost:9090/metrics | grep mutt_ingest_latency_seconds

# 2. Alerter processing latency
curl -s http://localhost:9091/metrics | grep mutt_alerter_processing_latency_seconds

# 3. Moog forwarding latency
curl -s http://localhost:9092/metrics | grep mutt_moog_request_latency_seconds

# 4. Queue depths (indicates bottlenecks)
echo "Ingest Queue: $(redis-cli LLEN mutt:ingest_queue)"
echo "Alert Queue: $(redis-cli LLEN mutt:alert_queue)"
```

**Resolution:**

**If ingest queue growing (alerter bottleneck):**
```bash
# Scale alerter horizontally
# Add more alerter instances (see Service Operations Guide)
```

**If alert queue growing (moog forwarder bottleneck):**
```bash
# Scale moog forwarder horizontally
# OR increase Moog rate limit
sudo vi /etc/mutt/mutt.env
RATE_LIMIT_MAX_REQUESTS=200

sudo systemctl restart mutt-moog-forwarder
```

**If all queues empty but still slow:**
```bash
# Check per-stage latency metrics
# Optimize the slow stage (see service-specific sections)
```

---

### Memory Leak Suspected

**Symptom:** Service memory usage grows over time

**Diagnosis:**
```bash
# Monitor memory usage over time
watch -n 60 'ps aux | grep alerter_service | awk "{print \$6}"'

# Check for memory growth in logs
sudo journalctl -u mutt-alerter --since "24 hours ago" | grep -i memory

# Use memory profiler (requires code instrumentation)
# Install memory_profiler: pip install memory-profiler
```

**Resolution:**

**Short-term (restart service):**
```bash
# Restart leaking service
sudo systemctl restart mutt-alerter

# Schedule periodic restarts via cron (workaround only)
echo "0 3 * * * root /usr/bin/systemctl restart mutt-alerter" | sudo tee -a /etc/crontab
```

**Long-term (fix code):**
```bash
# Identify leak source (requires profiling)
# Common causes:
# - Rule cache growing unbounded
# - Connection pool not releasing
# - Circular references in Python objects

# Report to development team for code fix
```

---

## Data Flow Troubleshooting

### Tracing an Event Through the System

**Objective:** Follow a single event from ingest to Moogsoft

**Step 1: Ingest Event with Correlation ID**
```bash
# Send test event
CORRELATION_ID=$(uuidgen)
curl -X POST http://localhost:8080/ingest \
  -H "X-API-Key: YOUR_API_KEY" \
  -H "Content-Type: application/json" \
  -d "{
    \"correlation_id\": \"$CORRELATION_ID\",
    \"source\": \"trace-test\",
    \"severity\": \"info\",
    \"message\": \"Tracing event through MUTT\",
    \"timestamp\": \"$(date -u +%Y-%m-%dT%H:%M:%SZ)\"
  }"

echo "Correlation ID: $CORRELATION_ID"
```

**Step 2: Verify in Ingest Queue**
```bash
# Check if event is in ingest queue
redis-cli LRANGE mutt:ingest_queue 0 -1 | jq ". | select(.correlation_id == \"$CORRELATION_ID\")"
```

**Step 3: Follow Through Alerter**
```bash
# Watch alerter logs for this correlation ID
sudo journalctl -u mutt-alerter -f | grep "$CORRELATION_ID"

# Expected output: "Processing event with correlation_id=$CORRELATION_ID"
```

**Step 4: Check if Handled or Unhandled**
```bash
# Check alert queue (handled events)
redis-cli LRANGE mutt:alert_queue 0 -1 | jq ". | select(.correlation_id == \"$CORRELATION_ID\")"

# Check unhandled keys (unhandled events)
redis-cli KEYS "mutt:unhandled:*" | xargs -I {} redis-cli GET {} | jq ". | select(.correlation_id == \"$CORRELATION_ID\")"
```

**Step 5: Follow Through Moog Forwarder**
```bash
# Watch moog forwarder logs
sudo journalctl -u mutt-moog-forwarder -f | grep "$CORRELATION_ID"

# Expected output: "Forwarded alert with correlation_id=$CORRELATION_ID"
```

**Step 6: Verify in Moogsoft**
```bash
# Check Moogsoft UI or API for the alert
# (Requires Moogsoft access)
```

**If Event Missing:**
```bash
# Check each queue/log systematically
# Missing from ingest queue? -> Check ingestor logs
# Missing from alert queue? -> Check alerter logs
# Missing from Moogsoft? -> Check moog forwarder logs and DLQ
```

---

## Common Error Messages

### Error: "redis.exceptions.ConnectionError: Error 111 connecting to localhost:6379. Connection refused."

**Cause:** Redis is not running or not listening on expected port

**Resolution:**
```bash
# Check Redis status
sudo systemctl status redis

# Start Redis
sudo systemctl start redis

# Verify listening
sudo ss -tunlp | grep 6379

# Restart affected service
sudo systemctl restart mutt-ingestor
```

---

### Error: "psycopg2.OperationalError: FATAL: sorry, too many clients already"

**Cause:** PostgreSQL connection pool exhausted

**Resolution:**
```bash
# Immediate: Kill idle connections (see PostgreSQL Troubleshooting section)

# Short-term: Increase max_connections (see PostgreSQL Troubleshooting section)

# Long-term: Implement PgBouncer (see PostgreSQL Troubleshooting section)
```

---

### Error: "hvac.exceptions.Forbidden: permission denied"

**Cause:** Vault token lacks required policy permissions

**Resolution:**
```bash
# Check current token policies
export VAULT_TOKEN=$(cat /etc/mutt/vault_secret_id)
vault token lookup

# Verify token has mutt-policy
vault token capabilities secret/mutt/prod

# If missing, create new token with correct policy
vault token create -policy=mutt-policy -ttl=720h

# Update secret ID file
echo "NEW_TOKEN" | sudo tee /etc/mutt/vault_secret_id
sudo systemctl restart mutt-*
```

---

### Error: "ValueError: Required secret INGEST_API_KEY not found in Vault"

**Cause:** API key not stored in Vault at expected path

**Resolution:**
```bash
# Add API key to Vault
vault kv put secret/mutt/prod INGEST_API_KEY="your-secure-api-key"

# Verify
vault kv get secret/mutt/prod

# Restart ingestor
sudo systemctl restart mutt-ingestor
```

---

### Error: "Circuit breaker is OPEN, skipping forward"

**Cause:** Circuit breaker opened due to repeated Moogsoft failures

**Reason:** This is expected behavior, not an error

**Resolution:**
```bash
# Wait for circuit breaker timeout (default: 300 seconds)
grep CIRCUIT_BREAKER_TIMEOUT /etc/mutt/mutt.env

# Circuit will auto-retry after timeout
# Messages are safely queued in DLQ for remediation

# If Moogsoft is healthy, restart forwarder to reset circuit immediately
curl -I "$MOOG_URL"  # Verify Moogsoft is up
sudo systemctl restart mutt-moog-forwarder
```

---

### Error: "Backpressure: Queue depth X exceeds shed threshold Y, shedding event"

**Cause:** Ingest queue exceeds configured shed threshold

**Reason:** This is expected backpressure behavior

**Resolution:**
```bash
# Check alerter processing rate
curl -s http://localhost:9091/metrics | grep mutt_alerter_events_processed_total

# Scale alerter to process faster (see Service Operations Guide)

# OR increase shed threshold temporarily
python scripts/muttdev.py config --set alerter_queue_shed_threshold 5000 --publish

# OR change shed mode to "defer" instead of "dlq"
python scripts/muttdev.py config --set alerter_shed_mode defer --publish
```

---

## Log Analysis Techniques

### Structured JSON Log Parsing

MUTT services log in JSON format (if `LOG_FORMAT=json`). Use `jq` for parsing:

**Extract errors from last hour:**
```bash
sudo journalctl -u mutt-ingestor --since "1 hour ago" -o json | \
  jq -r 'select(.MESSAGE) | .MESSAGE | fromjson? | select(.level == "ERROR") | .message'
```

**Count errors by service:**
```bash
for service in mutt-ingestor mutt-alerter mutt-moog-forwarder mutt-remediation mutt-webui; do
    count=$(sudo journalctl -u $service --since "1 hour ago" --priority=err | wc -l)
    echo "$service: $count errors"
done
```

**Extract correlation IDs from failed events:**
```bash
sudo journalctl -u mutt-ingestor --since "1 hour ago" -o json | \
  jq -r 'select(.MESSAGE) | .MESSAGE | fromjson? | select(.status == "fail") | .correlation_id'
```

---

### Log Correlation Across Services

**Find all log entries for a specific correlation ID:**
```bash
CORRELATION_ID="abc123-def456"

for service in mutt-ingestor mutt-alerter mutt-moog-forwarder; do
    echo "=== $service ==="
    sudo journalctl -u $service --since "24 hours ago" | grep "$CORRELATION_ID"
    echo ""
done
```

---

### Performance Metrics from Logs

**Calculate average processing time:**
```bash
# Extract processing times from alerter logs
sudo journalctl -u mutt-alerter --since "1 hour ago" | \
  grep "Processing event" | \
  awk -F'took ' '{print $2}' | \
  awk -F' ' '{sum+=$1; count++} END {print "Average: " sum/count " ms"}'
```

---

## Advanced Debugging Workflows

### Enabling Debug Logging

**Temporarily enable debug logging:**
```bash
# Edit environment file
sudo vi /etc/mutt/mutt.env
LOG_LEVEL=DEBUG

# Restart service
sudo systemctl restart mutt-alerter

# Tail debug logs
sudo journalctl -u mutt-alerter -f

# IMPORTANT: Revert to INFO after debugging (debug logs are verbose)
sudo vi /etc/mutt/mutt.env
LOG_LEVEL=INFO
sudo systemctl restart mutt-alerter
```

---

### Python Debugger (pdb) for Development

**For local development/testing only:**
```bash
# Insert breakpoint in code
# In alerter_service.py:
import pdb; pdb.set_trace()

# Run service in foreground
cd /opt/mutt
source venv/bin/activate
python services/alerter_service.py

# Debugger will pause at breakpoint
# Use pdb commands: n (next), s (step), c (continue), p (print), etc.
```

---

### Redis Command Monitoring

**Monitor all Redis commands in real-time:**
```bash
# In terminal 1: Start monitoring
redis-cli MONITOR

# In terminal 2: Trigger MUTT activity
curl -X POST http://localhost:8080/ingest \
  -H "X-API-Key: YOUR_API_KEY" \
  -H "Content-Type: application/json" \
  -d '{"test": "event"}'

# Terminal 1 will show all Redis commands executed
```

---

### PostgreSQL Query Logging

**Enable query logging:**
```bash
# Edit PostgreSQL config
sudo vi /var/lib/pgsql/data/postgresql.conf

# Enable logging
logging_collector = on
log_directory = 'log'
log_filename = 'postgresql-%Y-%m-%d_%H%M%S.log'
log_statement = 'all'  # Log all queries
log_duration = on      # Log query duration

# Restart PostgreSQL
sudo systemctl restart postgresql

# Tail query log
sudo tail -f /var/lib/pgsql/data/log/postgresql-*.log

# IMPORTANT: Disable after debugging (generates large logs)
log_statement = 'none'
sudo systemctl restart postgresql
```

---

## Known Issues and Workarounds

### Issue: Alerter Memory Growth Over Time

**Impact:** Alerter process memory usage grows over 24 hours

**Workaround:**
```bash
# Schedule nightly restart via cron
echo "0 3 * * * root /usr/bin/systemctl restart mutt-alerter" | sudo tee -a /etc/crontab

# Monitor memory usage
watch -n 300 'ps aux | grep alerter_service | awk "{print \$6}"'
```

**Permanent Fix:** Under investigation (likely rule cache optimization)

---

### Issue: Moogsoft Circuit Breaker Too Sensitive

**Impact:** Circuit breaker opens after brief Moogsoft hiccups

**Workaround:**
```bash
# Increase circuit breaker threshold
sudo vi /etc/mutt/mutt.env
CIRCUIT_BREAKER_THRESHOLD=20  # Increase from 10
CIRCUIT_BREAKER_TIMEOUT=600   # Increase timeout

sudo systemctl restart mutt-moog-forwarder
```

---

### Issue: PostgreSQL Connection Pool Exhaustion During Peak Load

**Impact:** Services return "too many clients" errors during traffic spikes

**Workaround:**
```bash
# Implement PgBouncer (see PostgreSQL Troubleshooting section)

# OR increase max_connections (short-term)
sudo vi /var/lib/pgsql/data/postgresql.conf
max_connections = 300

sudo systemctl restart postgresql
```

---

## Escalation Procedures

### When to Escalate

Escalate to **Development Team** if:
- Code bug suspected (crashes, exceptions, logic errors)
- Feature not working as documented
- Performance issue requires code optimization
- Data corruption detected

Escalate to **Infrastructure Team** if:
- Hardware failure (disk, network, memory)
- Hypervisor/VM issues
- Network routing/firewall issues
- DNS/load balancer issues

Escalate to **Database Team** if:
- PostgreSQL replication issues
- Database corruption
- Performance tuning beyond standard optimizations

Escalate to **Security Team** if:
- Unauthorized access suspected
- Security vulnerability discovered
- Compliance violation detected

---

### Escalation Template

```
Subject: MUTT v2.5 - [Severity] [Component] [Brief Description]

Severity: [P1-Critical | P2-High | P3-Medium | P4-Low]
Component: [Ingestor | Alerter | Moog Forwarder | Remediation | Web UI | Redis | PostgreSQL | Vault]
Environment: [Production | Staging | Development]

Issue Description:
[Detailed description of the issue]

Impact:
[Business impact, affected users/systems]

Steps to Reproduce:
1. [Step 1]
2. [Step 2]
3. [Step 3]

Observed Behavior:
[What actually happens]

Expected Behavior:
[What should happen]

Troubleshooting Performed:
1. [Action 1] - [Result]
2. [Action 2] - [Result]
3. [Action 3] - [Result]

Logs and Evidence:
[Attach relevant logs, metrics, screenshots]

Correlation IDs (if applicable):
[List correlation IDs for affected events]

Configuration:
- MUTT Version: 2.5
- Deployment: [Standalone | Kubernetes | Docker Compose]
- OS: [RHEL 8.x]
- Redis Version: [X.Y.Z]
- PostgreSQL Version: [X.Y.Z]

Suggested Next Steps:
[Your recommendations]
```

---

## Summary Checklist

Use this checklist for systematic troubleshooting:

**Initial Assessment:**
- [ ] Identify symptom and affected component(s)
- [ ] Check service status (`systemctl status mutt-*`)
- [ ] Check infrastructure status (Redis, PostgreSQL, Vault)
- [ ] Check recent changes (deployments, config changes)

**Data Collection:**
- [ ] Collect service logs (`journalctl -u mutt-*`)
- [ ] Collect metrics (Prometheus `/metrics` endpoints)
- [ ] Check queue depths (Redis LLEN)
- [ ] Check resource usage (CPU, memory, disk)

**Analysis:**
- [ ] Correlate symptoms with logs
- [ ] Identify error patterns
- [ ] Trace event flow (correlation IDs)
- [ ] Review recent configuration changes

**Resolution:**
- [ ] Apply fix/workaround
- [ ] Document action taken
- [ ] Monitor for resolution
- [ ] Verify end-to-end functionality

**Post-Mortem:**
- [ ] Document root cause
- [ ] Update runbooks/documentation
- [ ] Implement permanent fix (if workaround was used)
- [ ] Share lessons learned with team

---

## Next Steps

For additional operational guidance:

1. **Service Operations**: [SERVICE_OPERATIONS.md](SERVICE_OPERATIONS.md) - Starting/stopping, scaling, maintenance
2. **Configuration Management**: [CONFIG_MANAGEMENT.md](CONFIG_MANAGEMENT.md) (coming soon) - Dynamic config, secrets rotation
3. **Monitoring & Alerting**: [MONITORING_ALERTING.md](MONITORING_ALERTING.md) (coming soon) - Prometheus, alerting rules
4. **Incident Response**: [INCIDENT_RESPONSE.md](INCIDENT_RESPONSE.md) (coming soon) - Incident procedures, escalation

---

**Document Metadata:**
- **Version**: 1.0
- **Last Updated**: 2025-11-10
- **Maintainer**: MUTT Operations Team
- **Feedback**: Report issues via internal ticketing system
