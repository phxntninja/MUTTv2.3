# MUTT v2.5 - Service Operations Guide

**Target Audience:** System Administrators, DevOps Engineers, Site Reliability Engineers
**Priority Level:** P1 (Critical)
**Last Updated:** 2025-11-10

---

## Table of Contents

1. [Overview](#overview)
2. [Service Architecture](#service-architecture)
3. [Service Dependencies](#service-dependencies)
4. [Starting and Stopping Services](#starting-and-stopping-services)
5. [Health Monitoring](#health-monitoring)
6. [Service-Specific Operations](#service-specific-operations)
7. [Performance Tuning](#performance-tuning)
8. [Scaling Procedures](#scaling-procedures)
9. [Graceful Shutdown and Maintenance](#graceful-shutdown-and-maintenance)
10. [Log Management](#log-management)
11. [Common Operational Tasks](#common-operational-tasks)
12. [Emergency Procedures](#emergency-procedures)

---

## Overview

MUTT (Multi-Use Telemetry Tool) v2.5 consists of five microservices that work together to ingest, process, and forward telemetry events. This guide provides comprehensive operational procedures for managing these services in production.

### Service Inventory

| Service | Type | Purpose | Critical Path |
|---------|------|---------|---------------|
| **Ingestor** | HTTP API | Event ingestion endpoint | Yes |
| **Alerter** | Worker | Core event processing (the "brain") | Yes |
| **Moog Forwarder** | Worker | Alert forwarding to Moogsoft | Yes |
| **Remediation** | Worker | Self-healing and DLQ replay | No |
| **Web UI** | HTTP API | Dashboard and management interface | No |

### Infrastructure Requirements

| Component | Purpose | High Availability |
|-----------|---------|-------------------|
| **Redis** | Message queuing, caching, rate limiting | Required |
| **PostgreSQL** | Rules storage, audit logs | Required |
| **HashiCorp Vault** | Secrets management | Recommended |
| **Prometheus** | Metrics collection | Recommended |

---

## Service Architecture

### Event Flow Diagram

```
┌─────────────┐
│  External   │
│   Systems   │ (syslog, SNMP traps, webhooks)
└──────┬──────┘
       │
       v
┌─────────────────────────────────────────────────┐
│           INGESTOR SERVICE (Port 8080)          │
│  - Rate limiting (1000 req/min)                 │
│  - API key authentication                       │
│  - Backpressure handling                        │
│  - Metrics: /metrics                            │
└──────────────────┬──────────────────────────────┘
                   │
                   v
           ┌───────────────┐
           │  Redis Queue  │ (mutt:ingest_queue)
           └───────┬───────┘
                   │
                   v
┌─────────────────────────────────────────────────┐
│          ALERTER SERVICE (No HTTP)              │
│  - Rule matching and processing                 │
│  - Deduplication                                │
│  - Enrichment                                   │
│  - Health: :8081, Metrics: :9091                │
└──────────────────┬──────────────────────────────┘
                   │
         ┌─────────┴─────────┐
         v                   v
┌────────────────┐   ┌──────────────┐
│  Alert Queue   │   │ Unhandled    │
│  (Handled)     │   │ Meta-Alerts  │
└────────┬───────┘   └──────────────┘
         │
         v
┌─────────────────────────────────────────────────┐
│      MOOG FORWARDER SERVICE (No HTTP)           │
│  - Moogsoft webhook forwarding                  │
│  - Circuit breaker                              │
│  - Retry with exponential backoff               │
│  - Health: :8082, Metrics: :9092                │
└──────────────────┬──────────────────────────────┘
                   │
         ┌─────────┴──────────┐
         v                    v
  ┌─────────────┐      ┌────────────┐
  │  Moogsoft   │      │  DLQ       │
  │  Instance   │      │  (Failed)  │
  └─────────────┘      └──────┬─────┘
                              │
                              v
                ┌──────────────────────────────────┐
                │   REMEDIATION SERVICE (No HTTP)  │
                │   - DLQ replay when healthy      │
                │   - Poison message detection     │
                │   - Health: :8087, Metrics: :8086│
                └──────────────────────────────────┘

                ┌──────────────────────────────────┐
                │     WEB UI SERVICE (Port 8090)   │
                │     - Dashboard                  │
                │     - Rule management            │
                │     - Audit log viewer           │
                │     - Metrics: /metrics          │
                └──────────────────────────────────┘
```

### Port Allocation

| Service | Health Check | Metrics | Application |
|---------|-------------|---------|-------------|
| Ingestor | N/A | 9090 | 8080 |
| Alerter | 8081 | 9091 | N/A |
| Moog Forwarder | 8082 | 9092 | N/A |
| Remediation | 8087 | 8086 | N/A |
| Web UI | N/A | 9090 | 8090 |

---

## Service Dependencies

### Dependency Matrix

| Service | Redis | PostgreSQL | Vault | Moogsoft | Other Services |
|---------|-------|------------|-------|----------|----------------|
| Ingestor | Required | No | Required | No | None |
| Alerter | Required | Required | Required | No | None |
| Moog Forwarder | Required | No | Required | Required | None |
| Remediation | Required | No | Optional | Required | None |
| Web UI | Required | Required | Required | No | None |

### Critical Startup Order

For a clean startup, follow this sequence:

1. **Infrastructure First**
   ```bash
   # Start Redis
   sudo systemctl start redis

   # Start PostgreSQL
   sudo systemctl start postgresql

   # Verify both are healthy
   redis-cli PING
   sudo -u postgres psql -c "SELECT 1;"
   ```

2. **Application Services**
   ```bash
   # Can start in any order, but recommended sequence:
   sudo systemctl start mutt-ingestor      # Accept traffic immediately
   sudo systemctl start mutt-alerter       # Process queued events
   sudo systemctl start mutt-moog-forwarder # Forward alerts
   sudo systemctl start mutt-remediation    # Start self-healing
   sudo systemctl start mutt-webui          # Management interface
   ```

3. **Verify All Services**
   ```bash
   sudo systemctl status mutt-*
   ```

### Dependency Failure Behavior

| Service | Redis Down | PostgreSQL Down | Vault Down | Moogsoft Down |
|---------|------------|-----------------|------------|---------------|
| Ingestor | Fails fast | N/A | Fails fast | N/A |
| Alerter | Reconnects with backoff | Reconnects with backoff | Fails fast | N/A |
| Moog Forwarder | Reconnects with backoff | N/A | Fails fast | Uses DLQ |
| Remediation | Reconnects with backoff | N/A | Continues | Pauses replay |
| Web UI | Returns 500 errors | Returns 500 errors | Fails fast | N/A |

---

## Starting and Stopping Services

### Starting Individual Services

```bash
# Start a single service
sudo systemctl start mutt-ingestor

# Verify it started successfully
sudo systemctl status mutt-ingestor

# Check service logs
sudo journalctl -u mutt-ingestor -n 50 -f

# Verify health (for services with health endpoints)
curl http://localhost:8081/health  # Alerter
curl http://localhost:8082/health  # Moog Forwarder
curl http://localhost:8087/health  # Remediation
curl http://localhost:8080/health  # Ingestor
curl http://localhost:8090/health  # Web UI
```

### Starting All Services

```bash
# Start all MUTT services
sudo systemctl start mutt-ingestor mutt-alerter mutt-moog-forwarder mutt-remediation mutt-webui

# Verify all are running
sudo systemctl status mutt-* | grep "Active:"

# Check for any failures
sudo systemctl --failed | grep mutt
```

### Stopping Services Gracefully

```bash
# Stop a single service (graceful shutdown)
sudo systemctl stop mutt-ingestor

# Stop all MUTT services (reverse order for clean shutdown)
sudo systemctl stop mutt-webui mutt-remediation mutt-moog-forwarder mutt-alerter mutt-ingestor
```

**Graceful Shutdown Behavior:**
- **Ingestor**: Finishes processing in-flight requests (up to 30s timeout)
- **Alerter**: Completes current event processing, moves processing list back to queue
- **Moog Forwarder**: Completes current forwarding, moves processing list back to queue
- **Remediation**: Completes current remediation cycle
- **Web UI**: Finishes in-flight requests (up to 30s timeout)

### Restarting Services

```bash
# Restart a single service
sudo systemctl restart mutt-ingestor

# Restart all services (maintains startup order)
sudo systemctl restart mutt-ingestor mutt-alerter mutt-moog-forwarder mutt-remediation mutt-webui

# Reload systemd configuration (after editing .service files)
sudo systemctl daemon-reload
sudo systemctl restart mutt-ingestor
```

### Enabling/Disabling Auto-Start

```bash
# Enable auto-start on boot
sudo systemctl enable mutt-ingestor

# Enable all MUTT services
sudo systemctl enable mutt-ingestor mutt-alerter mutt-moog-forwarder mutt-remediation mutt-webui

# Disable auto-start
sudo systemctl disable mutt-ingestor

# Check auto-start status
systemctl is-enabled mutt-ingestor
```

---

## Health Monitoring

### Health Check Endpoints

Each service provides health information:

| Service | Endpoint | Expected Response |
|---------|----------|-------------------|
| Ingestor | `http://localhost:8080/health` | `{"status": "healthy", "redis": "ok", "vault": "ok"}` |
| Alerter | `http://localhost:8081/health` | `{"status": "healthy"}` |
| Moog Forwarder | `http://localhost:8082/health` | `{"status": "healthy"}` |
| Remediation | `http://localhost:8087/health` | `{"status": "healthy"}` |
| Web UI | `http://localhost:8090/health` | `{"status": "healthy", "redis": "ok", "postgres": "ok"}` |

### Automated Health Checks

Create a monitoring script (`/usr/local/bin/mutt-health-check.sh`):

```bash
#!/bin/bash
# MUTT Health Check Script

SERVICES=(
    "mutt-ingestor:8080"
    "mutt-alerter:8081"
    "mutt-moog-forwarder:8082"
    "mutt-remediation:8087"
    "mutt-webui:8090"
)

for service_port in "${SERVICES[@]}"; do
    service="${service_port%%:*}"
    port="${service_port##*:}"

    # Check systemd status
    if ! systemctl is-active --quiet "$service"; then
        echo "ERROR: $service is not running"
        continue
    fi

    # Check HTTP health endpoint
    response=$(curl -s -o /dev/null -w "%{http_code}" http://localhost:$port/health 2>/dev/null)

    if [ "$response" == "200" ]; then
        echo "OK: $service is healthy (HTTP $response)"
    else
        echo "WARNING: $service returned HTTP $response"
    fi
done

# Check infrastructure
echo ""
echo "Infrastructure Health:"

# Redis
if redis-cli -h localhost PING &>/dev/null; then
    echo "OK: Redis is responding"
else
    echo "ERROR: Redis is not responding"
fi

# PostgreSQL
if sudo -u postgres psql -c "SELECT 1;" &>/dev/null; then
    echo "OK: PostgreSQL is responding"
else
    echo "ERROR: PostgreSQL is not responding"
fi
```

Make it executable:
```bash
sudo chmod +x /usr/local/bin/mutt-health-check.sh
```

Run periodically via cron (every 5 minutes):
```bash
# Add to /etc/crontab
*/5 * * * * root /usr/local/bin/mutt-health-check.sh >> /var/log/mutt/health-checks.log 2>&1
```

### Metrics Monitoring

All services expose Prometheus metrics at `/metrics` endpoints:

```bash
# Ingestor metrics
curl http://localhost:9090/metrics

# Alerter metrics
curl http://localhost:9091/metrics

# Moog Forwarder metrics
curl http://localhost:9092/metrics

# Remediation metrics
curl http://localhost:8086/metrics

# Web UI metrics
curl http://localhost:8090/metrics
```

**Key Metrics to Monitor:**

| Metric | Service | Alert Threshold | Description |
|--------|---------|-----------------|-------------|
| `mutt_ingest_queue_depth` | Ingestor | > 10,000 | Ingest queue backlog |
| `mutt_ingest_requests_total{status="fail"}` | Ingestor | Rate > 10/min | Failed ingestions |
| `mutt_alerter_events_processed_total{status="error"}` | Alerter | Rate > 5/min | Processing errors |
| `mutt_moog_requests_total{status="fail"}` | Moog Forwarder | Rate > 10/min | Failed forwards |
| `mutt_moog_dlq_depth` | Moog Forwarder | > 100 | Dead letter queue depth |
| `mutt_remediation_dlq_depth` | Remediation | > 500 | DLQ not draining |
| `mutt_moog_health` | Remediation | == 0 | Moogsoft unhealthy |

### Service Status Dashboard

Query all service statuses:

```bash
# Create status script (/usr/local/bin/mutt-status.sh)
#!/bin/bash
echo "MUTT Service Status Report - $(date)"
echo "========================================"
echo ""

for service in mutt-ingestor mutt-alerter mutt-moog-forwarder mutt-remediation mutt-webui; do
    status=$(systemctl is-active $service)
    uptime=$(systemctl show $service --property=ActiveEnterTimestamp --value)

    printf "%-20s : %s (since %s)\n" "$service" "$status" "$uptime"
done

echo ""
echo "Queue Depths:"
redis-cli LLEN mutt:ingest_queue | xargs echo "  Ingest Queue    :"
redis-cli LLEN mutt:alert_queue | xargs echo "  Alert Queue     :"
redis-cli LLEN mutt:dlq:moog | xargs echo "  Moog DLQ        :"
redis-cli LLEN mutt:dlq:alerter | xargs echo "  Alerter DLQ     :"
```

---

## Service-Specific Operations

### Ingestor Service Operations

**Purpose:** HTTP API gateway for event ingestion

**Critical Configuration:**
- Port: 8080
- Workers: 4 (Gunicorn)
- Rate Limit: 1000 requests/60 seconds
- Queue Cap: 1,000,000 events

**Common Operations:**

1. **Check Ingest Rate**
   ```bash
   # View recent ingest activity
   sudo journalctl -u mutt-ingestor -n 100 | grep "Ingested event"

   # Get rate from Prometheus
   curl -s http://localhost:9090/metrics | grep mutt_ingest_requests_total
   ```

2. **Adjust Worker Count**
   ```bash
   # Edit service file
   sudo vi /etc/systemd/system/mutt-ingestor.service

   # Change --workers value
   ExecStart=/opt/mutt/venv/bin/gunicorn \
       --workers 8 \                           # <-- Increase from 4
       --bind 0.0.0.0:${INGESTOR_PORT} \
       ...

   # Reload and restart
   sudo systemctl daemon-reload
   sudo systemctl restart mutt-ingestor
   ```

3. **Test Ingest Endpoint**
   ```bash
   # Simple health check
   curl http://localhost:8080/health

   # Send test event (requires API key)
   curl -X POST http://localhost:8080/ingest \
     -H "X-API-Key: YOUR_API_KEY" \
     -H "Content-Type: application/json" \
     -d '{
       "source": "test-system",
       "severity": "warning",
       "message": "Test event",
       "timestamp": "'$(date -u +%Y-%m-%dT%H:%M:%SZ)'"
     }'
   ```

4. **Monitor Backpressure**
   ```bash
   # Check queue depth
   redis-cli LLEN mutt:ingest_queue

   # Monitor rejection rate
   curl -s http://localhost:9090/metrics | \
     grep 'mutt_ingest_requests_total{status="fail",reason="queue_full"}'
   ```

**Performance Tuning:**
- Increase workers for higher throughput (recommend: 2× CPU cores)
- Adjust `INGEST_QUEUE_CAP` if backpressure is too aggressive
- Enable rate limiting if source systems are overwhelming ingestor

**Troubleshooting:**
- **503 responses**: Queue is full, check alerter processing rate
- **401 errors**: API key authentication failing, check Vault
- **Slow responses**: Check Redis latency, consider connection pooling

---

### Alerter Service Operations

**Purpose:** Core event processing engine (the "brain")

**Critical Configuration:**
- Health Port: 8081
- Metrics Port: 9091
- Queue: `mutt:ingest_queue`
- Processing List: `mutt:processing:alerter:<pod_name>`

**Architecture Notes:**
- Long-running worker service (no HTTP API)
- Uses `BRPOPLPUSH` for reliable queue processing
- Caches all rules/hosts in memory
- Reloads cache on SIGHUP or every 5 minutes

**Common Operations:**

1. **Monitor Processing Rate**
   ```bash
   # View processing logs
   sudo journalctl -u mutt-alerter -f | grep "Processing event"

   # Get metrics
   curl -s http://localhost:9091/metrics | grep mutt_alerter_events_processed_total
   ```

2. **Reload Rule Cache**
   ```bash
   # Send SIGHUP to reload cache without restart
   sudo systemctl kill -s HUP mutt-alerter

   # Verify reload in logs
   sudo journalctl -u mutt-alerter -n 20 | grep "Reloading"
   ```

3. **Check Queue Processing**
   ```bash
   # Check ingest queue depth
   redis-cli LLEN mutt:ingest_queue

   # Check processing list (in-flight events)
   POD_NAME=$(grep POD_NAME /etc/mutt/mutt.env | cut -d= -f2)
   redis-cli LLEN "mutt:processing:alerter:$POD_NAME"

   # Check alert output queue
   redis-cli LLEN mutt:alert_queue
   ```

4. **Handle Backpressure**
   ```bash
   # Check current backpressure settings
   redis-cli GET mutt:config:alerter_queue_warn_threshold
   redis-cli GET mutt:config:alerter_queue_shed_threshold
   redis-cli GET mutt:config:alerter_shed_mode

   # Adjust thresholds dynamically (if DYNAMIC_CONFIG_ENABLED=true)
   python scripts/muttdev.py config --set alerter_queue_shed_threshold 5000 --publish
   ```

5. **Monitor Rule Matching**
   ```bash
   # View handled events
   curl -s http://localhost:9091/metrics | grep 'mutt_alerter_events_processed_total{status="handled"}'

   # View unhandled events
   curl -s http://localhost:9091/metrics | grep 'mutt_alerter_events_processed_total{status="unhandled"}'

   # Check unhandled meta-alerts
   curl -s http://localhost:9091/metrics | grep mutt_alerter_unhandled_meta_alerts_total
   ```

**Performance Tuning:**
- Optimize PostgreSQL queries by ensuring indexes on `alert_rules` table
- Increase `RULE_CACHE_TTL` if rules change infrequently
- Consider sharding if single alerter cannot keep up
- Adjust `BRPOPLPUSH_TIMEOUT` for responsiveness vs CPU usage

**Scaling Strategy:**
- **Vertical**: Increase CPU/memory (alerter is CPU-bound)
- **Horizontal**: Run multiple alerter pods with unique `POD_NAME` values
  ```bash
  # On second server, change POD_NAME
  sudo sed -i 's/POD_NAME=alerter-001/POD_NAME=alerter-002/' /etc/mutt/mutt.env
  sudo systemctl restart mutt-alerter
  ```

**Troubleshooting:**
- **Events stuck in ingest queue**: Check alerter logs for errors
- **High processing latency**: Check PostgreSQL connection pool, rule cache
- **Memory growth**: Check for rule cache bloat, restart service if needed

---

### Moog Forwarder Service Operations

**Purpose:** Forward alerts to Moogsoft via webhook

**Critical Configuration:**
- Health Port: 8082
- Metrics Port: 9092
- Queue: `mutt:alert_queue`
- DLQ: `mutt:dlq:moog`
- Circuit Breaker: Enabled (10 failures / 5 min timeout)

**Common Operations:**

1. **Monitor Forwarding Success Rate**
   ```bash
   # View forwarding logs
   sudo journalctl -u mutt-moog-forwarder -f | grep "Forwarded alert"

   # Get success/failure metrics
   curl -s http://localhost:9092/metrics | grep mutt_moog_requests_total
   ```

2. **Check Circuit Breaker Status**
   ```bash
   # View circuit breaker logs
   sudo journalctl -u mutt-moog-forwarder -n 50 | grep -i circuit

   # Metrics showing circuit state
   curl -s http://localhost:9092/metrics | grep mutt_moog_circuit_breaker
   ```

3. **Monitor Dead Letter Queue**
   ```bash
   # Check DLQ depth
   redis-cli LLEN mutt:dlq:moog

   # Sample DLQ messages
   redis-cli LRANGE mutt:dlq:moog 0 5

   # Get DLQ metrics
   curl -s http://localhost:9092/metrics | grep mutt_moog_dlq_depth
   ```

4. **Manual Circuit Breaker Reset**
   ```bash
   # Circuit breaker resets automatically after timeout
   # To force immediate reset, restart service (if Moogsoft is healthy)
   sudo systemctl restart mutt-moog-forwarder
   ```

5. **Adjust Rate Limiting**
   ```bash
   # Check current rate limit
   grep RATE_LIMIT /etc/mutt/mutt.env | grep MOOG

   # Modify rate limit (requires restart)
   sudo vi /etc/mutt/mutt.env
   # Change RATE_LIMIT_MAX_REQUESTS=100 to desired value

   sudo systemctl restart mutt-moog-forwarder
   ```

6. **Test Moogsoft Connectivity**
   ```bash
   # Manual webhook test
   MOOG_URL=$(grep MOOG_WEBHOOK_URL /etc/mutt/mutt.env | cut -d= -f2)

   curl -X POST "$MOOG_URL" \
     -H "Content-Type: application/json" \
     -d '{
       "severity": "warning",
       "description": "Test alert from MUTT",
       "source": "mutt-ops-test"
     }'
   ```

**Performance Tuning:**
- Adjust `RETRY_MAX_ATTEMPTS` and backoff settings for Moogsoft latency
- Increase `RATE_LIMIT_MAX_REQUESTS` if Moogsoft can handle higher load
- Tune circuit breaker `CIRCUIT_BREAKER_THRESHOLD` based on Moogsoft reliability

**Scaling Strategy:**
- **Horizontal**: Run multiple forwarder instances (they coordinate via Redis rate limiter)
  ```bash
  # Safe to run multiple forwarders, they share:
  # - Same alert_queue (BRPOPLPUSH ensures no duplicates)
  # - Same rate limiter (Redis-coordinated)
  # - Separate processing lists per POD_NAME
  ```

**Troubleshooting:**
- **DLQ growing**: Check Moogsoft availability, circuit breaker state
- **Rate limiting**: Check metrics `mutt_moog_rate_limit_hits_total`, adjust limits
- **Timeout errors**: Increase `MOOG_TIMEOUT`, check network latency

---

### Remediation Service Operations

**Purpose:** Self-healing service that replays messages from DLQ

**Critical Configuration:**
- Health Port: 8087
- Metrics Port: 8086
- Interval: 300 seconds (5 minutes)
- Batch Size: 10 messages per cycle

**Common Operations:**

1. **Monitor Remediation Activity**
   ```bash
   # View remediation logs
   sudo journalctl -u mutt-remediation -f | grep -E "Remediation|Replaying"

   # Get remediation metrics
   curl -s http://localhost:8086/metrics | grep mutt_remediation
   ```

2. **Check DLQ Replay Rate**
   ```bash
   # View replay success/failure
   curl -s http://localhost:8086/metrics | grep mutt_remediation_replay

   # Check poison messages moved to dead letter
   curl -s http://localhost:8086/metrics | grep mutt_remediation_poison_messages_total
   ```

3. **Verify Moogsoft Health Checks**
   ```bash
   # Check if remediation is detecting Moogsoft health
   sudo journalctl -u mutt-remediation -n 50 | grep -i "moog.*health"

   # Metrics for Moogsoft health
   curl -s http://localhost:8086/metrics | grep mutt_remediation_moog_health
   # 1 = healthy, 0 = unhealthy
   ```

4. **Adjust Remediation Interval**
   ```bash
   # Edit environment config
   sudo vi /etc/mutt/mutt.env
   # Change REMEDIATION_INTERVAL=300 to desired seconds

   # Restart to apply
   sudo systemctl restart mutt-remediation
   ```

5. **Handle Poison Messages**
   ```bash
   # Poison messages go to mutt:dlq:dead after MAX_POISON_RETRIES
   # Check dead letter queue
   redis-cli LLEN mutt:dlq:dead

   # Sample poison messages
   redis-cli LRANGE mutt:dlq:dead 0 10

   # Manually inspect and fix, then re-queue
   # (Requires manual intervention - likely indicates bad data or bug)
   ```

**Performance Tuning:**
- Decrease `REMEDIATION_INTERVAL` for faster DLQ drain (increases load)
- Increase `REMEDIATION_BATCH_SIZE` for bulk replay (up to 100)
- Adjust `MAX_POISON_RETRIES` to balance retry vs poison detection

**Operational Notes:**
- Remediation pauses replay if Moogsoft health checks fail
- Service is non-critical; can be stopped during Moogsoft maintenance
- Poison messages require manual investigation (check logs for reason)

**Troubleshooting:**
- **DLQ not draining**: Check Moogsoft health, verify remediation is running
- **High poison message rate**: Indicates data quality issue or Moog API changes
- **Remediation too slow**: Decrease interval or increase batch size

---

### Web UI Service Operations

**Purpose:** Management dashboard and CRUD API for rules/teams/hosts

**Critical Configuration:**
- Port: 8090
- Workers: 2 (Gunicorn)
- Metrics Cache TTL: 5 seconds

**Common Operations:**

1. **Access Dashboard**
   ```bash
   # Web browser
   http://localhost:8090/

   # CLI health check
   curl http://localhost:8090/health
   ```

2. **Manage Alert Rules**
   ```bash
   # View rules via API
   curl -H "X-API-Key: YOUR_API_KEY" http://localhost:8090/api/v1/rules

   # Create new rule
   curl -X POST http://localhost:8090/api/v1/rules \
     -H "X-API-Key: YOUR_API_KEY" \
     -H "Content-Type: application/json" \
     -d '{
       "rule_name": "disk_full",
       "pattern": ".*disk.*full.*",
       "severity": "critical",
       "priority": 100,
       "enabled": true
     }'
   ```

3. **View Audit Logs**
   ```bash
   # Web browser
   http://localhost:8090/audit-logs

   # API query
   curl -H "X-API-Key: YOUR_API_KEY" \
     "http://localhost:8090/api/v1/audit-logs?limit=50&offset=0"
   ```

4. **Monitor API Performance**
   ```bash
   # View access logs
   sudo journalctl -u mutt-webui -f | grep "GET\|POST\|PUT\|DELETE"

   # Get API metrics
   curl http://localhost:8090/metrics
   ```

5. **Clear Metrics Cache**
   ```bash
   # Metrics are cached for 5 seconds by default
   # To force fresh metrics, wait 5 seconds or restart service
   sudo systemctl restart mutt-webui
   ```

**Performance Tuning:**
- Increase workers for more concurrent users
- Adjust `METRICS_CACHE_TTL` to balance freshness vs load
- Consider CDN/proxy for static assets if high traffic

**Security Notes:**
- API key required for all non-dashboard endpoints
- Store API keys in Vault, rotate regularly
- Use HTTPS in production (place behind nginx/Apache)

**Troubleshooting:**
- **500 errors**: Check PostgreSQL/Redis connectivity
- **Slow dashboard**: Check metrics cache TTL, database query performance
- **Auth failures**: Verify Vault connectivity, check API key validity

---

## Performance Tuning

### Ingestor Performance

**Bottleneck Indicators:**
- High request latency (> 100ms p95)
- Worker saturation (all workers busy)
- Queue depth growing rapidly

**Tuning Parameters:**

| Parameter | Default | Recommendation | Impact |
|-----------|---------|----------------|--------|
| `INGESTOR_WORKERS` | 4 | 2× CPU cores | Higher throughput |
| `INGEST_QUEUE_CAP` | 1,000,000 | 2,000,000 | More backpressure buffer |
| `RATE_LIMIT_MAX_REQUESTS` | 1000 | Adjust per source | Prevent overload |
| `REDIS_POOL_MAX` | 10 | 20 | More concurrent Redis ops |

**Optimization Steps:**

1. **CPU-bound** (workers at 100%):
   ```bash
   # Increase Gunicorn workers
   sudo vi /etc/systemd/system/mutt-ingestor.service
   # Change --workers 4 to --workers 8
   sudo systemctl daemon-reload && sudo systemctl restart mutt-ingestor
   ```

2. **Redis-bound** (high Redis latency):
   ```bash
   # Check Redis latency
   redis-cli --latency-history

   # Increase connection pool (in code, requires redeploy)
   # Or consider Redis cluster for horizontal scaling
   ```

3. **Network-bound** (high connection latency):
   ```bash
   # Use TCP keepalive and connection pooling
   # Already enabled in redis_connector.py
   # Verify with:
   grep SOCKET_KEEPALIVE /etc/mutt/mutt.env
   ```

---

### Alerter Performance

**Bottleneck Indicators:**
- Ingest queue growing faster than processing
- High CPU usage (> 80%)
- Database query latency (> 50ms)

**Tuning Parameters:**

| Parameter | Default | Recommendation | Impact |
|-----------|---------|----------------|--------|
| `RULE_CACHE_TTL` | 300 | 600 | Less DB queries |
| `POSTGRES_POOL_MAX` | 10 | 20 | More DB connections |
| `BRPOPLPUSH_TIMEOUT` | 5 | 10 | Less CPU churn |

**Optimization Steps:**

1. **Database-bound**:
   ```sql
   -- Ensure indexes exist
   CREATE INDEX IF NOT EXISTS idx_alert_rules_enabled ON alert_rules(enabled) WHERE enabled = true;
   CREATE INDEX IF NOT EXISTS idx_alert_rules_priority ON alert_rules(priority DESC);

   -- Analyze query performance
   EXPLAIN ANALYZE SELECT * FROM alert_rules WHERE enabled = true ORDER BY priority DESC;
   ```

2. **CPU-bound**:
   ```bash
   # Scale horizontally: add more alerter pods
   # On second server:
   export POD_NAME=alerter-002
   sudo systemctl start mutt-alerter
   ```

3. **Memory-bound** (large rule cache):
   ```bash
   # Monitor memory usage
   ps aux | grep alerter_service

   # If > 2GB, consider rule optimization:
   # - Remove unused rules
   # - Consolidate similar rules
   # - Archive historical rules
   ```

---

### Moog Forwarder Performance

**Bottleneck Indicators:**
- Alert queue growing
- High DLQ depth
- Circuit breaker frequently open

**Tuning Parameters:**

| Parameter | Default | Recommendation | Impact |
|-----------|---------|----------------|--------|
| `RATE_LIMIT_MAX_REQUESTS` | 100 | 200 | Higher throughput |
| `MOOG_TIMEOUT` | 10 | 30 | Tolerate slower Moogsoft |
| `RETRY_MAX_ATTEMPTS` | 5 | 3 | Faster DLQ routing |
| `CIRCUIT_BREAKER_THRESHOLD` | 10 | 15 | Less sensitive |

**Optimization Steps:**

1. **Moogsoft slow/unreliable**:
   ```bash
   # Increase timeout and adjust circuit breaker
   sudo vi /etc/mutt/mutt.env
   MOOG_TIMEOUT=30
   CIRCUIT_BREAKER_THRESHOLD=15
   CIRCUIT_BREAKER_TIMEOUT=600  # 10 minutes

   sudo systemctl restart mutt-moog-forwarder
   ```

2. **Rate limiting too aggressive**:
   ```bash
   # Increase rate limit
   sudo vi /etc/mutt/mutt.env
   RATE_LIMIT_MAX_REQUESTS=200

   sudo systemctl restart mutt-moog-forwarder
   ```

3. **Scale horizontally**:
   ```bash
   # Multiple forwarders share rate limiter
   # On second server:
   export POD_NAME=moog-forwarder-002
   sudo systemctl start mutt-moog-forwarder
   ```

---

## Scaling Procedures

### Vertical Scaling (Single Server)

**When to vertically scale:**
- CPU usage consistently > 70%
- Memory usage > 80%
- Disk I/O wait > 20%

**Steps:**

1. **Identify bottleneck:**
   ```bash
   # CPU
   top -b -n 1 | head -20

   # Memory
   free -h

   # Disk I/O
   iostat -x 1 5
   ```

2. **Increase server resources:**
   - Add CPU cores
   - Add RAM
   - Upgrade to SSD (for PostgreSQL)

3. **Adjust service workers:**
   ```bash
   # Ingestor: increase Gunicorn workers
   # Recommendation: 2× CPU cores
   sudo vi /etc/systemd/system/mutt-ingestor.service
   # Change --workers value

   # PostgreSQL: increase max_connections
   sudo vi /var/lib/pgsql/data/postgresql.conf
   max_connections = 200

   # Redis: increase maxmemory
   sudo vi /etc/redis/redis.conf
   maxmemory 8gb
   ```

4. **Restart services:**
   ```bash
   sudo systemctl daemon-reload
   sudo systemctl restart mutt-*
   sudo systemctl restart postgresql
   sudo systemctl restart redis
   ```

---

### Horizontal Scaling (Multi-Server)

**Supported scaling models:**

| Service | Scalability | Coordination | Notes |
|---------|-------------|--------------|-------|
| Ingestor | Horizontal | Load balancer | Stateless, scale freely |
| Alerter | Horizontal | Redis queue | Unique `POD_NAME` required |
| Moog Forwarder | Horizontal | Redis queue + rate limiter | Shared rate limit |
| Remediation | Vertical only | Single instance | Not designed for horizontal |
| Web UI | Horizontal | Load balancer | Stateless, scale freely |

**Horizontal Scaling Steps:**

### Scaling Ingestor (Load Balanced)

```
                    ┌───────────────┐
                    │ Load Balancer │
                    │  (HAProxy)    │
                    └───────┬───────┘
                            │
              ┌─────────────┼─────────────┐
              │             │             │
              v             v             v
      ┌────────────┐ ┌────────────┐ ┌────────────┐
      │ Ingestor 1 │ │ Ingestor 2 │ │ Ingestor 3 │
      │  Server A  │ │  Server B  │ │  Server C  │
      └────────────┘ └────────────┘ └────────────┘
              │             │             │
              └─────────────┼─────────────┘
                            │
                            v
                      ┌──────────┐
                      │  Redis   │
                      └──────────┘
```

1. **Install MUTT on additional servers** (follow [Installation Guide](INSTALLATION_GUIDE.md))

2. **Configure HAProxy** (on dedicated load balancer):
   ```
   # /etc/haproxy/haproxy.cfg
   frontend ingestor_frontend
       bind *:8080
       mode http
       default_backend ingestor_backend

   backend ingestor_backend
       mode http
       balance roundrobin
       option httpchk GET /health
       http-check expect status 200
       server ingestor1 10.0.1.10:8080 check
       server ingestor2 10.0.1.11:8080 check
       server ingestor3 10.0.1.12:8080 check
   ```

3. **Update source systems to point to load balancer IP**

---

### Scaling Alerter (Queue Workers)

```
      ┌────────────┐
      │   Redis    │
      │   Queue    │
      └──────┬─────┘
             │
   ┌─────────┼─────────┬─────────┐
   │         │         │         │
   v         v         v         v
┌─────────────────────────────────────┐
│ Alerter 1   Alerter 2   Alerter 3  │
│ Server A     Server B    Server C   │
│ POD_NAME=    POD_NAME=   POD_NAME=  │
│ alerter-001  alerter-002 alerter-003│
└─────────────────────────────────────┘
```

1. **On each additional server, set unique POD_NAME:**
   ```bash
   # Server B
   sudo vi /etc/mutt/mutt.env
   POD_NAME=alerter-002

   # Server C
   sudo vi /etc/mutt/mutt.env
   POD_NAME=alerter-003
   ```

2. **Start alerter service:**
   ```bash
   sudo systemctl start mutt-alerter
   ```

3. **Verify load distribution:**
   ```bash
   # Check processing lists on each server
   redis-cli LLEN mutt:processing:alerter:alerter-001
   redis-cli LLEN mutt:processing:alerter:alerter-002
   redis-cli LLEN mutt:processing:alerter:alerter-003

   # Monitor metrics on each server
   curl http://server-a:9091/metrics | grep mutt_alerter_events_processed_total
   curl http://server-b:9091/metrics | grep mutt_alerter_events_processed_total
   curl http://server-c:9091/metrics | grep mutt_alerter_events_processed_total
   ```

**Important:** All alerters share the same Redis queue (`mutt:ingest_queue`) and coordinate via `BRPOPLPUSH` (atomic, no duplicates).

---

### Scaling Moog Forwarder

**Same process as Alerter** (unique `POD_NAME`, shared queue):

```bash
# Server B
sudo vi /etc/mutt/mutt.env
POD_NAME=moog-forwarder-002

sudo systemctl start mutt-moog-forwarder
```

**Rate Limiter Behavior:**
- All forwarders share the same Redis-backed rate limiter
- Total throughput = `RATE_LIMIT_MAX_REQUESTS` (not per instance)
- If you need higher throughput, increase the rate limit value

---

### Scaling PostgreSQL (Database)

**Options:**

1. **Vertical Scaling** (Recommended for MUTT):
   - Increase CPU/RAM/disk on PostgreSQL server
   - Tune `shared_buffers`, `work_mem`, `max_connections`

2. **Read Replicas** (If read-heavy):
   - Configure PostgreSQL streaming replication
   - Point read-only queries (dashboard) to replica
   - Point write queries (alerter) to primary

3. **Connection Pooling** (PgBouncer):
   - Install PgBouncer in front of PostgreSQL
   - Configure services to connect via PgBouncer
   - Reduces connection overhead

**PgBouncer Setup Example:**
```bash
# Install PgBouncer
sudo yum install pgbouncer -y

# Configure
sudo vi /etc/pgbouncer/pgbouncer.ini
[databases]
mutt = host=localhost port=5432 dbname=mutt

[pgbouncer]
listen_addr = 0.0.0.0
listen_port = 6432
auth_type = md5
pool_mode = transaction
max_client_conn = 200
default_pool_size = 25

# Update MUTT services to connect to port 6432
sudo vi /etc/mutt/mutt.env
POSTGRES_PORT=6432

sudo systemctl restart mutt-*
```

---

### Scaling Redis (Message Queue)

**Options:**

1. **Vertical Scaling** (Simplest):
   - Increase RAM (Redis is in-memory)
   - Increase CPU for list operations
   - Use Redis persistence (AOF) for durability

2. **Redis Sentinel** (High Availability):
   - 3-node Redis cluster with automatic failover
   - MUTT services auto-reconnect on failover

3. **Redis Cluster** (Sharding - Not Recommended):
   - Redis Cluster doesn't support multi-key operations (BRPOPLPUSH)
   - MUTT architecture relies on single-instance Redis
   - Consider Kafka if you need distributed queuing (see ADR-001)

**Redis Sentinel Setup** (High Availability):
```bash
# Install Redis on 3 servers (redis-1, redis-2, redis-3)
# On each server:
sudo yum install redis -y

# redis-1: Primary
sudo vi /etc/redis/redis.conf
bind 0.0.0.0
port 6379

sudo systemctl start redis

# redis-2 and redis-3: Replicas
sudo vi /etc/redis/redis.conf
bind 0.0.0.0
port 6379
replicaof redis-1 6379

sudo systemctl start redis

# All servers: Configure Sentinel
sudo vi /etc/redis/sentinel.conf
sentinel monitor mutt-master redis-1 6379 2
sentinel down-after-milliseconds mutt-master 5000
sentinel failover-timeout mutt-master 10000

sudo systemctl start redis-sentinel

# Update MUTT services to use Sentinel
# (Requires code changes to use Redis Sentinel client)
```

---

## Graceful Shutdown and Maintenance

### Planned Maintenance Window

**Recommended Procedure:**

1. **Pre-maintenance** (15 minutes before):
   ```bash
   # Stop accepting new traffic
   # Option 1: Load balancer (if using one)
   # - Remove ingestor from load balancer pool

   # Option 2: Firewall (standalone)
   sudo firewall-cmd --zone=public --remove-port=8080/tcp

   # Allow queue to drain
   watch -n 5 'redis-cli LLEN mutt:ingest_queue'
   # Wait until < 100 events
   ```

2. **Stop services** (in order):
   ```bash
   # Stop ingestor first (no new events)
   sudo systemctl stop mutt-ingestor

   # Wait for alerter to drain ingest queue
   watch redis-cli LLEN mutt:ingest_queue
   # Wait until 0

   # Stop alerter (no new alerts)
   sudo systemctl stop mutt-alerter

   # Wait for moog-forwarder to drain alert queue
   watch redis-cli LLEN mutt:alert_queue
   # Wait until 0

   # Stop moog-forwarder
   sudo systemctl stop mutt-moog-forwarder

   # Stop remediation and webui (non-critical)
   sudo systemctl stop mutt-remediation mutt-webui
   ```

3. **Perform maintenance**:
   - Update software: `sudo yum update`
   - Patch OS: `sudo yum update --security`
   - Upgrade MUTT: Deploy new version
   - Database maintenance: `VACUUM ANALYZE;`

4. **Restart services** (in order):
   ```bash
   # Start infrastructure
   sudo systemctl start redis postgresql

   # Verify infrastructure
   redis-cli PING
   sudo -u postgres psql -c "SELECT 1;"

   # Start MUTT services
   sudo systemctl start mutt-ingestor mutt-alerter mutt-moog-forwarder mutt-remediation mutt-webui

   # Verify all healthy
   /usr/local/bin/mutt-health-check.sh
   ```

5. **Resume traffic**:
   ```bash
   # Firewall
   sudo firewall-cmd --zone=public --add-port=8080/tcp

   # Or add back to load balancer
   ```

---

### Emergency Shutdown

**Immediate stop (data loss possible):**

```bash
# Kill all services immediately
sudo systemctl kill -s SIGKILL mutt-*

# Potential data loss:
# - Events in processing lists (Redis) will be orphaned
# - In-flight HTTP requests will fail
# - Moogsoft forwards in-progress will be lost to DLQ
```

**Graceful emergency stop (< 60 seconds):**

```bash
# Send SIGTERM (graceful shutdown with timeout)
sudo systemctl stop mutt-* --no-block

# Wait up to 60 seconds for clean shutdown
sleep 60

# Force kill any remaining
sudo systemctl kill -s SIGKILL mutt-*
```

**Data Recovery After Emergency Shutdown:**

```bash
# Orphaned events in processing lists will be recovered by Janitor
# Janitor runs every 60 seconds and checks for stale processing lists

# On restart, janitor will:
# 1. Detect processing lists with expired heartbeats
# 2. Move events back to main queue
# 3. Clean up stale keys

# Verify janitor recovery:
sudo journalctl -u mutt-alerter -f | grep -i janitor
```

---

### Rolling Updates (Zero Downtime)

**For horizontally scaled deployments:**

1. **Update one server at a time**:
   ```bash
   # Server A
   sudo systemctl stop mutt-alerter
   # Deploy new version
   sudo rsync -av /tmp/mutt-new/ /opt/mutt/
   sudo systemctl start mutt-alerter

   # Wait 5 minutes, verify health
   curl http://server-a:8081/health

   # Repeat for Server B, C, etc.
   ```

2. **Database migrations**:
   ```bash
   # Run migrations BEFORE updating services
   cd /opt/mutt
   source venv/bin/activate
   python scripts/migrate_db.py

   # Verify migration success
   psql -U mutt_user -d mutt -c "SELECT version FROM schema_version ORDER BY applied_at DESC LIMIT 1;"
   ```

3. **Rollback procedure**:
   ```bash
   # If new version has issues, rollback
   sudo systemctl stop mutt-*
   sudo rsync -av /opt/mutt-backup/ /opt/mutt/
   sudo systemctl start mutt-*

   # Verify health
   /usr/local/bin/mutt-health-check.sh
   ```

---

## Log Management

### Log Locations

| Service | Log Location | Systemd Journal | Log Format |
|---------|--------------|-----------------|------------|
| Ingestor | `/var/log/mutt/ingestor.log` | Yes (`journalctl -u mutt-ingestor`) | JSON |
| Alerter | `/var/log/mutt/alerter.log` | Yes (`journalctl -u mutt-alerter`) | JSON |
| Moog Forwarder | `/var/log/mutt/moog-forwarder.log` | Yes (`journalctl -u mutt-moog-forwarder`) | JSON |
| Remediation | `/var/log/mutt/remediation.log` | Yes (`journalctl -u mutt-remediation`) | JSON |
| Web UI | `/var/log/mutt/webui.log` | Yes (`journalctl -u mutt-webui`) | JSON |

### Log Rotation

**Automatic rotation via logrotate** (`/etc/logrotate.d/mutt`):

```
/var/log/mutt/*.log {
    daily
    rotate 30
    compress
    delaycompress
    missingok
    notifempty
    create 0640 mutt mutt
    sharedscripts
    postrotate
        /bin/systemctl reload rsyslog > /dev/null 2>&1 || true
    endscript
}
```

**Manual log rotation:**
```bash
# Force log rotation
sudo logrotate -f /etc/logrotate.d/mutt

# Verify rotation
ls -lh /var/log/mutt/
```

### Log Analysis

**Search for errors:**
```bash
# Last 100 errors from all services
sudo journalctl -u mutt-* --priority=err -n 100

# Errors from specific service
sudo journalctl -u mutt-alerter --priority=err --since "1 hour ago"

# JSON log parsing (if LOG_FORMAT=json)
sudo journalctl -u mutt-ingestor -o json | jq -r 'select(.level == "ERROR") | .message'
```

**Trace a correlation ID:**
```bash
# Find all log entries for a specific event
CORRELATION_ID="abc123-def456-ghi789"

sudo journalctl -u mutt-ingestor | grep $CORRELATION_ID
sudo journalctl -u mutt-alerter | grep $CORRELATION_ID
sudo journalctl -u mutt-moog-forwarder | grep $CORRELATION_ID
```

**Monitor log volume:**
```bash
# Log entries per minute (all services)
sudo journalctl -u mutt-* --since "1 hour ago" | wc -l

# Log size on disk
du -sh /var/log/mutt/
```

### Centralized Logging (Optional)

**Forward logs to Elasticsearch/Splunk/Datadog:**

1. **Using Filebeat** (Elasticsearch):
   ```yaml
   # /etc/filebeat/filebeat.yml
   filebeat.inputs:
   - type: log
     enabled: true
     paths:
       - /var/log/mutt/*.log
     json.keys_under_root: true
     json.add_error_key: true
     fields:
       service: mutt
       environment: production

   output.elasticsearch:
     hosts: ["https://elasticsearch:9200"]
     username: "mutt"
     password: "${ELASTICSEARCH_PASSWORD}"
   ```

2. **Using rsyslog** (Splunk/Syslog):
   ```
   # /etc/rsyslog.d/mutt.conf
   $ModLoad imfile

   $InputFileName /var/log/mutt/ingestor.log
   $InputFileTag mutt-ingestor:
   $InputFileStateFile stat-mutt-ingestor
   $InputFileSeverity info
   $InputFileFacility local3
   $InputRunFileMonitor

   # Forward to Splunk
   local3.* @@splunk.example.com:514
   ```

3. **Using journald forwarding**:
   ```bash
   # Forward journald to remote syslog
   sudo vi /etc/systemd/journald.conf
   ForwardToSyslog=yes

   sudo systemctl restart systemd-journald
   ```

---

## Common Operational Tasks

### Task 1: Add a New Alert Rule

```bash
# Option 1: Via Web UI
# Navigate to http://localhost:8090/rules and create rule via UI

# Option 2: Via API
curl -X POST http://localhost:8090/api/v1/rules \
  -H "X-API-Key: YOUR_API_KEY" \
  -H "Content-Type: application/json" \
  -d '{
    "rule_name": "cpu_high",
    "pattern": ".*CPU.*threshold.*exceeded.*",
    "severity": "warning",
    "priority": 50,
    "enabled": true,
    "description": "CPU threshold exceeded alert",
    "device_team_id": 1
  }'

# Option 3: Direct PostgreSQL insert
sudo -u postgres psql mutt <<EOF
INSERT INTO alert_rules (rule_name, pattern, severity, priority, enabled, description)
VALUES ('cpu_high', '.*CPU.*threshold.*exceeded.*', 'warning', 50, true, 'CPU threshold exceeded alert');
EOF

# After adding rule, reload alerter cache
sudo systemctl kill -s HUP mutt-alerter
```

---

### Task 2: Drain a Queue for Maintenance

```bash
# Scenario: Need to perform Moogsoft maintenance, drain alert queue first

# 1. Stop new events from entering alert queue
sudo systemctl stop mutt-alerter

# 2. Let forwarder drain alert queue
watch -n 5 'redis-cli LLEN mutt:alert_queue'
# Wait until 0

# 3. Stop forwarder
sudo systemctl stop mutt-moog-forwarder

# 4. Perform Moogsoft maintenance
# ...

# 5. Restart services
sudo systemctl start mutt-moog-forwarder
sleep 30  # Verify health
sudo systemctl start mutt-alerter
```

---

### Task 3: Investigate High DLQ Depth

```bash
# 1. Check DLQ depth
redis-cli LLEN mutt:dlq:moog

# 2. Sample DLQ messages
redis-cli LRANGE mutt:dlq:moog 0 10 | jq .

# 3. Check Moog forwarder logs for failure reason
sudo journalctl -u mutt-moog-forwarder -n 200 | grep -i "error\|fail\|dlq"

# 4. Check circuit breaker state
curl http://localhost:9092/metrics | grep circuit_breaker

# 5. Verify Moogsoft connectivity
MOOG_URL=$(grep MOOG_WEBHOOK_URL /etc/mutt/mutt.env | cut -d= -f2)
curl -I "$MOOG_URL"

# 6. If Moogsoft is healthy, increase rate limit to drain faster
sudo vi /etc/mutt/mutt.env
RATE_LIMIT_MAX_REQUESTS=200  # Increase from 100

sudo systemctl restart mutt-moog-forwarder

# 7. Monitor DLQ drain rate
watch -n 10 'redis-cli LLEN mutt:dlq:moog'
```

---

### Task 4: Change Dynamic Configuration

```bash
# Requires DYNAMIC_CONFIG_ENABLED=true

# 1. List all current config
python scripts/muttdev.py config --list

# 2. Update a configuration value
python scripts/muttdev.py config --set alerter_queue_shed_threshold 5000 --publish

# 3. Verify change propagated to service
sudo journalctl -u mutt-alerter -n 20 | grep -i config

# 4. Confirm new value is active
redis-cli GET mutt:config:alerter_queue_shed_threshold
```

---

### Task 5: Manually Replay a DLQ Message

```bash
# Scenario: Poison message in DLQ needs manual fix and replay

# 1. Pop message from DLQ
MESSAGE=$(redis-cli RPOP mutt:dlq:moog)

# 2. Parse and inspect
echo "$MESSAGE" | jq .

# 3. Fix the message (example: fix malformed JSON)
FIXED_MESSAGE=$(echo "$MESSAGE" | jq '.field = "corrected_value"')

# 4. Re-queue to alert queue
redis-cli LPUSH mutt:alert_queue "$FIXED_MESSAGE"

# 5. Verify forwarder picks it up
sudo journalctl -u mutt-moog-forwarder -f | grep "correlation_id"
```

---

### Task 6: Rotate Vault Token

```bash
# 1. Generate new Vault token (via Vault UI or CLI)
vault token create -policy=mutt-policy -ttl=720h

# 2. Update Vault Secret ID file
sudo vi /etc/mutt/vault_secret_id
# Paste new token

# 3. Restart services to pick up new token
sudo systemctl restart mutt-*

# 4. Verify Vault connectivity
sudo journalctl -u mutt-ingestor -n 20 | grep -i vault
```

---

### Task 7: Clear Redis Queue (Emergency)

```bash
# WARNING: This deletes all events in the queue!

# Backup queue first (optional)
redis-cli LRANGE mutt:ingest_queue 0 -1 > /tmp/ingest_queue_backup.json

# Delete queue
redis-cli DEL mutt:ingest_queue

# Verify
redis-cli LLEN mutt:ingest_queue
# Should return 0
```

---

## Emergency Procedures

### Emergency 1: Ingestor Unresponsive

**Symptoms:**
- HTTP 503 errors
- No response from ingestor endpoint
- High load on ingestor server

**Diagnosis:**
```bash
# Check service status
sudo systemctl status mutt-ingestor

# Check logs
sudo journalctl -u mutt-ingestor -n 100 --no-pager

# Check CPU/memory
top -b -n 1 | grep gunicorn

# Check Redis connectivity
redis-cli PING

# Check queue depth
redis-cli LLEN mutt:ingest_queue
```

**Resolution:**

1. **If queue is full** (backpressure):
   ```bash
   # Temporary: increase queue cap
   sudo vi /etc/mutt/mutt.env
   INGEST_QUEUE_CAP=2000000

   sudo systemctl restart mutt-ingestor

   # Long-term: scale alerter to process faster
   ```

2. **If Redis is down**:
   ```bash
   sudo systemctl status redis
   sudo systemctl start redis
   sudo systemctl restart mutt-ingestor
   ```

3. **If ingestor is crashed**:
   ```bash
   sudo systemctl restart mutt-ingestor
   ```

---

### Emergency 2: Events Not Processing

**Symptoms:**
- Ingest queue depth growing
- No alerter processing logs
- Alerter service running but idle

**Diagnosis:**
```bash
# Check alerter status
sudo systemctl status mutt-alerter

# Check queue depth
redis-cli LLEN mutt:ingest_queue

# Check processing list
POD_NAME=$(grep POD_NAME /etc/mutt/mutt.env | cut -d= -f2)
redis-cli LLEN "mutt:processing:alerter:$POD_NAME"

# Check for errors
sudo journalctl -u mutt-alerter --priority=err -n 50
```

**Resolution:**

1. **If alerter is stuck**:
   ```bash
   # Graceful restart
   sudo systemctl restart mutt-alerter

   # Verify processing resumes
   watch -n 5 'redis-cli LLEN mutt:ingest_queue'
   ```

2. **If PostgreSQL is down**:
   ```bash
   sudo systemctl status postgresql
   sudo systemctl start postgresql
   sudo systemctl restart mutt-alerter
   ```

3. **If rule cache is corrupted**:
   ```bash
   # Force cache reload
   sudo systemctl kill -s HUP mutt-alerter
   ```

---

### Emergency 3: Moogsoft Unreachable

**Symptoms:**
- Circuit breaker open
- DLQ depth growing rapidly
- Moogsoft webhook returning errors

**Diagnosis:**
```bash
# Check circuit breaker state
curl http://localhost:9092/metrics | grep mutt_moog_circuit_breaker

# Check Moogsoft connectivity
MOOG_URL=$(grep MOOG_WEBHOOK_URL /etc/mutt/mutt.env | cut -d= -f2)
curl -I "$MOOG_URL"

# Check DLQ depth
redis-cli LLEN mutt:dlq:moog

# Check forwarder logs
sudo journalctl -u mutt-moog-forwarder -n 100 | grep -i error
```

**Resolution:**

1. **If Moogsoft is temporarily down**:
   ```bash
   # Let circuit breaker do its job
   # Messages will go to DLQ and be replayed by remediation service
   # Monitor DLQ depth
   watch -n 10 'redis-cli LLEN mutt:dlq:moog'

   # Verify remediation is running
   sudo systemctl status mutt-remediation
   ```

2. **If Moogsoft is permanently unreachable**:
   ```bash
   # Stop forwarder to prevent DLQ growth
   sudo systemctl stop mutt-moog-forwarder

   # Update Moogsoft webhook URL
   sudo vi /etc/mutt/mutt.env
   MOOG_WEBHOOK_URL=https://new-moog-instance.com/webhook

   # Restart forwarder
   sudo systemctl start mutt-moog-forwarder
   ```

3. **If DLQ is too large (> 10,000)**:
   ```bash
   # Increase remediation batch size and frequency
   sudo vi /etc/mutt/mutt.env
   REMEDIATION_BATCH_SIZE=50
   REMEDIATION_INTERVAL=60

   sudo systemctl restart mutt-remediation
   ```

---

### Emergency 4: Redis Out of Memory

**Symptoms:**
- Redis errors: `OOM command not allowed`
- Ingestor/Alerter failing to write to Redis
- High memory usage on Redis server

**Diagnosis:**
```bash
# Check Redis memory usage
redis-cli INFO memory

# Check queue depths
redis-cli LLEN mutt:ingest_queue
redis-cli LLEN mutt:alert_queue
redis-cli LLEN mutt:dlq:moog

# Check used vs available memory
free -h
```

**Resolution:**

1. **Immediate**: Flush old/unnecessary data
   ```bash
   # Delete old unhandled event keys (> 7 days)
   redis-cli --scan --pattern "mutt:unhandled:*" | while read key; do
       age=$(redis-cli TTL "$key")
       if [ $age -lt 0 ] || [ $age -gt 604800 ]; then
           redis-cli DEL "$key"
       fi
   done
   ```

2. **Short-term**: Increase Redis memory limit
   ```bash
   sudo vi /etc/redis/redis.conf
   maxmemory 8gb  # Increase from current value

   sudo systemctl restart redis
   ```

3. **Long-term**: Scale Redis vertically or implement queue caps
   ```bash
   # Implement queue caps to prevent unbounded growth
   sudo vi /etc/mutt/mutt.env
   INGEST_QUEUE_CAP=500000  # Lower if needed

   sudo systemctl restart mutt-ingestor
   ```

---

### Emergency 5: PostgreSQL Connection Exhaustion

**Symptoms:**
- `FATAL: sorry, too many clients already`
- Alerter/WebUI failing with connection errors
- Slow query performance

**Diagnosis:**
```bash
# Check current connections
sudo -u postgres psql -c "SELECT count(*) FROM pg_stat_activity;"

# Check max connections
sudo -u postgres psql -c "SHOW max_connections;"

# View active queries
sudo -u postgres psql -c "SELECT pid, usename, application_name, state, query FROM pg_stat_activity WHERE state != 'idle';"
```

**Resolution:**

1. **Immediate**: Kill idle connections
   ```bash
   sudo -u postgres psql <<EOF
   SELECT pg_terminate_backend(pid)
   FROM pg_stat_activity
   WHERE state = 'idle' AND state_change < NOW() - INTERVAL '10 minutes';
   EOF
   ```

2. **Short-term**: Increase max_connections
   ```bash
   sudo vi /var/lib/pgsql/data/postgresql.conf
   max_connections = 200  # Increase from 100

   sudo systemctl restart postgresql
   ```

3. **Long-term**: Implement connection pooling (PgBouncer)
   ```bash
   # See "Scaling PostgreSQL" section above
   ```

---

## Next Steps

After mastering service operations:

1. **Advanced Troubleshooting**: See [Comprehensive Troubleshooting Guide](TROUBLESHOOTING_GUIDE.md) (coming soon)
2. **Configuration Management**: See [Configuration Management Guide](CONFIG_MANAGEMENT.md) (coming soon)
3. **Monitoring & Alerting**: See [Monitoring & Alerting Setup Guide](MONITORING_ALERTING.md) (coming soon)
4. **Disaster Recovery**: See [Backup & Recovery Guide](BACKUP_RECOVERY.md) (coming soon)
5. **Incident Response**: See [Incident Response Runbook](INCIDENT_RESPONSE.md) (coming soon)

---

## Reference

- **Installation Guide**: [INSTALLATION_GUIDE.md](INSTALLATION_GUIDE.md)
- **Architecture Decisions**: [docs/adr/README.md](../adr/README.md)
- **Developer Documentation**: [docs/DEV_QUICKSTART.md](../DEV_QUICKSTART.md)
- **Dynamic Configuration**: [docs/DYNAMIC_CONFIG_USAGE.md](../DYNAMIC_CONFIG_USAGE.md)
- **Operator Validation**: [docs/OPERATOR_VALIDATION_GUIDE.md](../OPERATOR_VALIDATION_GUIDE.md)

---

**Document Metadata:**
- **Version**: 1.0
- **Last Updated**: 2025-11-10
- **Maintainer**: MUTT Operations Team
- **Feedback**: Report issues at your internal ticketing system
