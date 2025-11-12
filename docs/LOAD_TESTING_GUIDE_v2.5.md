# MUTT v2.5 Load Testing Guide

**Version:** 2.5.0
**Last Updated:** 2025-11-11
**Purpose:** Validate v2.5 features under production-like load conditions

This guide covers load testing strategies, tools, scenarios, and success criteria for MUTT v2.5.

---

## Table of Contents

1. [Overview](#overview)
2. [Testing Objectives](#testing-objectives)
3. [Test Environment](#test-environment)
4. [Testing Tools](#testing-tools)
5. [Test Scenarios](#test-scenarios)
6. [Baseline Performance Targets](#baseline-performance-targets)
7. [Execution Procedures](#execution-procedures)
8. [Monitoring & Metrics](#monitoring--metrics)
9. [Results Analysis](#results-analysis)
10. [Troubleshooting](#troubleshooting)

---

## Overview

MUTT v2.5 introduces several features that require validation under load:

- **Dynamic Configuration Hot-Reload** - Config changes propagating across services
- **Rate Limiting & Backpressure** - Handling traffic spikes gracefully
- **Circuit Breaker** - Failing fast when downstream services are unhealthy
- **Secret Rotation** - Zero-downtime password changes
- **SLO Tracking** - Maintaining service level objectives under stress
- **Data Retention** - Archival and purge performance with large datasets

Load testing validates that these features perform as expected under production-like conditions.

---

## Testing Objectives

### Primary Objectives

1. **Validate v2.5 Feature Performance**
   - Dynamic config propagates within 5 seconds under load
   - Rate limiter prevents system overload
   - Circuit breaker opens/closes correctly under failure conditions
   - Secret rotation completes without dropped events
   - SLO compliance maintained during normal and peak loads

2. **Establish Performance Baselines**
   - Maximum sustainable throughput (events/hour)
   - API latency percentiles (P50, P95, P99)
   - Queue depth under various load levels
   - Database query performance with partitioned tables
   - Redis memory usage under high config churn

3. **Identify Breaking Points**
   - Maximum event throughput before degradation
   - Queue depth limits before backpressure triggers
   - Database connection pool saturation
   - Redis connection limits
   - Memory/CPU resource constraints

### Secondary Objectives

4. **Validate Auto-Remediation**
   - Remediation service detects and restarts failed services
   - Circuit breaker prevents cascading failures

5. **Test Data Retention at Scale**
   - Partition creation performance
   - Archive operation performance with millions of rows
   - Purge performance for expired data

---

## Test Environment

### Infrastructure Requirements

**Recommended Setup:**
```yaml
Environment: Kubernetes cluster or Docker Compose
Resources:
  - Ingestor: 2 replicas, 512MB RAM, 0.5 CPU each
  - Alerter: 2 replicas, 512MB RAM, 0.5 CPU each
  - Moog Forwarder: 2 replicas, 512MB RAM, 0.5 CPU each
  - Web UI: 1 replica, 256MB RAM, 0.25 CPU
  - Remediation: 1 replica, 256MB RAM, 0.25 CPU
  - PostgreSQL: 2GB RAM, 2 CPU
  - Redis: 1GB RAM, 1 CPU
  - Prometheus: 1GB RAM, 1 CPU
  - Grafana: 512MB RAM, 0.5 CPU
```

**Network:**
- Low-latency network (<1ms between services)
- Sufficient bandwidth for 100K events/hour
- Load generator on separate host (avoid resource contention)

**Database:**
- PostgreSQL 13+ with partitioned tables enabled
- At least 50GB disk space for test data
- Connection pooling configured (20 connections per service)

**Monitoring:**
- Prometheus scraping all service metrics
- Grafana dashboards for real-time visualization
- Log aggregation (ELK or similar) for error tracking

---

## Testing Tools

### Recommended: k6 (Open Source)

**Why k6:**
- JavaScript-based scripting
- Excellent HTTP/REST API support
- Built-in metrics and thresholds
- Cloud and local execution
- Prometheus integration

**Installation:**
```bash
# macOS
brew install k6

# Linux
wget https://github.com/grafana/k6/releases/download/v0.47.0/k6-v0.47.0-linux-amd64.tar.gz
tar -xzf k6-v0.47.0-linux-amd64.tar.gz
sudo mv k6 /usr/local/bin/

# Verify
k6 version
```

### Alternative: Apache JMeter

**Why JMeter:**
- GUI for test plan creation
- Extensive protocol support
- Large plugin ecosystem
- Mature and battle-tested

**Installation:**
```bash
# Download from https://jmeter.apache.org/download_jmeter.cgi
wget https://dlcdn.apache.org//jmeter/binaries/apache-jmeter-5.6.2.tgz
tar -xzf apache-jmeter-5.6.2.tgz
cd apache-jmeter-5.6.2/bin
./jmeter
```

### Additional Tools

- **Prometheus** - Metrics collection and alerting
- **Grafana** - Real-time dashboard visualization
- **hey** - Simple HTTP load generator for quick tests
- **wrk** - High-performance HTTP benchmarking

---

## Test Scenarios

### Scenario 1: Baseline Event Throughput

**Objective:** Establish maximum sustainable event ingestion rate.

**Test Parameters:**
- Duration: 30 minutes
- Ramp-up: 5 minutes (0 → 50K events/hour)
- Sustain: 20 minutes (50K events/hour)
- Ramp-down: 5 minutes (50K → 0)

**k6 Script:**
```javascript
// tests/load/scenario1-baseline-throughput.js
import http from 'k6/http';
import { check, sleep } from 'k6';
import { Rate } from 'k6/metrics';

const errorRate = new Rate('errors');

export const options = {
  stages: [
    { duration: '5m', target: 700 },  // Ramp up to 700 VUs (50K events/hour)
    { duration: '20m', target: 700 }, // Sustain 700 VUs
    { duration: '5m', target: 0 },    // Ramp down
  ],
  thresholds: {
    http_req_duration: ['p(95)<600', 'p(99)<1000'],
    http_req_failed: ['rate<0.01'],  // <1% errors
    errors: ['rate<0.01'],
  },
};

export default function () {
  const url = 'http://localhost:8080/api/v1/ingest';
  const payload = JSON.stringify({
    source: 'load_test',
    severity: 'INFO',
    message: `Load test event ${__VU}-${__ITER}`,
    timestamp: new Date().toISOString(),
    metadata: {
      test_id: 'scenario1',
      vu: __VU,
      iteration: __ITER,
    },
  });

  const params = {
    headers: {
      'Content-Type': 'application/json',
      'X-API-KEY': 'test-api-key',
    },
  };

  const res = http.post(url, payload, params);

  check(res, {
    'status is 200': (r) => r.status === 200,
    'response time < 500ms': (r) => r.timings.duration < 500,
  }) || errorRate.add(1);

  sleep(1); // 1 request/second per VU
}
```

**Execution:**
```bash
k6 run tests/load/scenario1-baseline-throughput.js
```

**Success Criteria:**
- ✅ All events successfully ingested
- ✅ P95 latency < 600ms
- ✅ P99 latency < 1000ms
- ✅ Error rate < 1%
- ✅ Queue depth remains < 500
- ✅ CPU usage < 80% on all services
- ✅ Memory stable (no leaks)

---

### Scenario 2: Rate Limiting Under Spike

**Objective:** Validate rate limiter prevents system overload during traffic spikes.

**Test Parameters:**
- Duration: 15 minutes
- Pattern: Spike to 2x normal rate every 3 minutes

**k6 Script:**
```javascript
// tests/load/scenario2-rate-limiting.js
import http from 'k6/http';
import { check } from 'k6';

export const options = {
  stages: [
    { duration: '1m', target: 500 },   // Normal load
    { duration: '1m', target: 1000 },  // Spike 2x
    { duration: '1m', target: 500 },   // Back to normal
    { duration: '1m', target: 1000 },  // Spike 2x
    { duration: '1m', target: 500 },   // Back to normal
    { duration: '1m', target: 1000 },  // Spike 2x
    { duration: '1m', target: 500 },   // Back to normal
  ],
  thresholds: {
    'http_req_duration{rate_limited:false}': ['p(95)<600'],
    'checks{check:rate_limited}': ['rate>0.1'], // Expect some 429s during spikes
  },
};

export default function () {
  const url = 'http://localhost:8080/api/v1/ingest';
  const payload = JSON.stringify({
    source: 'rate_limit_test',
    severity: 'INFO',
    message: `Rate limit test ${__VU}-${__ITER}`,
  });

  const params = {
    headers: {
      'Content-Type': 'application/json',
      'X-API-KEY': 'test-api-key',
    },
    tags: { rate_limited: 'false' },
  };

  const res = http.post(url, payload, params);

  if (res.status === 429) {
    params.tags.rate_limited = 'true';
  }

  check(res, {
    'status is 200 or 429': (r) => r.status === 200 || r.status === 429,
    'rate_limited': (r) => r.status === 429,
  });
}
```

**Success Criteria:**
- ✅ Rate limiter returns 429 during spikes
- ✅ Accepted requests maintain low latency
- ✅ No service crashes or OOM errors
- ✅ Rate limit metric increments correctly
- ✅ System recovers to normal after spike

---

### Scenario 3: Dynamic Config Hot-Reload

**Objective:** Validate config changes propagate across all services within 5 seconds under load.

**Test Procedure:**
```bash
#!/bin/bash
# tests/load/scenario3-config-hotreload.sh

# Step 1: Start baseline load (30K events/hour)
k6 run --duration 10m tests/load/baseline.js &
K6_PID=$!

# Step 2: Monitor initial cache_reload_interval
echo "Initial config: cache_reload_interval=$(muttdev config get cache_reload_interval)"

# Step 3: Change config after 2 minutes
sleep 120
echo "Changing cache_reload_interval to 300..."
muttdev config set cache_reload_interval 300

# Step 4: Monitor service logs for config reload
timeout 10 bash -c 'until muttdev logs alerter | grep "Config change detected: cache_reload_interval"; do sleep 1; done'
if [ $? -eq 0 ]; then
    echo "✅ Config change detected within 10 seconds"
else
    echo "❌ Config change NOT detected within 10 seconds"
fi

# Step 5: Verify new value in all services
sleep 5
echo "Verifying config propagation..."
for service in alerter moog_forwarder; do
    if muttdev logs $service | grep "cache_reload_interval.*300" > /dev/null; then
        echo "✅ $service picked up new config"
    else
        echo "❌ $service did NOT pick up new config"
    fi
done

# Step 6: Wait for load test completion
wait $K6_PID
echo "Load test completed"
```

**Success Criteria:**
- ✅ Config change detected within 10 seconds (target: 5 sec)
- ✅ All service instances receive update
- ✅ No event loss during config reload
- ✅ Latency spike < 100ms during reload
- ✅ Audit log entry created for config change

---

### Scenario 4: Circuit Breaker Behavior

**Objective:** Validate circuit breaker opens when downstream fails, preventing cascading failures.

**Test Procedure:**
```bash
#!/bin/bash
# tests/load/scenario4-circuit-breaker.sh

# Step 1: Start baseline load
k6 run --duration 15m tests/load/baseline.js &
K6_PID=$!

# Step 2: Monitor circuit breaker state (should be CLOSED)
echo "Initial circuit breaker state:"
curl -s http://localhost:8083/metrics | grep 'mutt_circuit_breaker_state{name="moogsoft"}'

# Step 3: Simulate Moogsoft failure (after 3 minutes)
sleep 180
echo "Simulating Moogsoft failure (returning 500 errors)..."
# Use mock server or iptables to block Moogsoft endpoint
docker-compose stop moogsoft-mock  # Or similar

# Step 4: Wait for circuit breaker to open (15 failures)
timeout 60 bash -c 'until curl -s http://localhost:8083/metrics | grep "mutt_circuit_breaker_state.*2"; do sleep 2; done'
if [ $? -eq 0 ]; then
    echo "✅ Circuit breaker OPENED"
    curl -s http://localhost:8083/metrics | grep 'mutt_circuit_breaker_state{name="moogsoft"}'
else
    echo "❌ Circuit breaker did NOT open"
fi

# Step 5: Verify events go to DLQ
DLQ_COUNT=$(redis-cli llen mutt:queue:dlq)
echo "DLQ depth: $DLQ_COUNT"

# Step 6: Restore Moogsoft
sleep 60
echo "Restoring Moogsoft..."
docker-compose start moogsoft-mock

# Step 7: Wait for circuit breaker to close
timeout 120 bash -c 'until curl -s http://localhost:8083/metrics | grep "mutt_circuit_breaker_state.*0"; do sleep 5; done'
if [ $? -eq 0 ]; then
    echo "✅ Circuit breaker CLOSED"
else
    echo "❌ Circuit breaker did NOT close"
fi

# Step 8: Verify DLQ processing resumes
sleep 30
NEW_DLQ_COUNT=$(redis-cli llen mutt:queue:dlq)
if [ $NEW_DLQ_COUNT -lt $DLQ_COUNT ]; then
    echo "✅ DLQ processing resumed ($DLQ_COUNT → $NEW_DLQ_COUNT)"
else
    echo "⚠️  DLQ not processing ($DLQ_COUNT → $NEW_DLQ_COUNT)"
fi

wait $K6_PID
```

**Success Criteria:**
- ✅ Circuit breaker opens after threshold failures
- ✅ State metric transitions: CLOSED → OPEN → HALF_OPEN → CLOSED
- ✅ Transition counter increments for each state change
- ✅ Events routed to DLQ while circuit is open
- ✅ Circuit closes after downstream recovery
- ✅ DLQ processing resumes automatically

---

### Scenario 5: Zero-Downtime Secret Rotation

**Objective:** Rotate database and Redis passwords without dropping events or causing errors.

**Test Procedure:**
```bash
#!/bin/bash
# tests/load/scenario5-secret-rotation.sh

# Step 1: Start sustained load (40K events/hour)
echo "Starting load test..."
k6 run --duration 20m tests/load/baseline.js &
K6_PID=$!

# Step 2: Monitor error rate before rotation
sleep 60
ERRORS_BEFORE=$(curl -s http://localhost:8081/metrics | grep 'mutt_ingest_errors_total' | awk '{print $2}')
echo "Errors before rotation: $ERRORS_BEFORE"

# Step 3: Rotate Redis password (after 5 minutes)
sleep 240
echo "Starting Redis password rotation..."

# 3a. Set NEXT password in Vault
vault kv patch secret/mutt/prod REDIS_PASS_NEXT="new_redis_password_$(date +%s)"

# 3b. Update Redis to accept both passwords (requires Redis 6+ ACL)
# NOTE: This step depends on Redis configuration
redis-cli ACL SETUSER mutt_app >"new_redis_password_$(date +%s)"

# 3c. Wait for services to pick up NEXT password (Vault token refresh)
sleep 60

# 3d. Promote NEXT to CURRENT
vault kv patch secret/mutt/prod \
  REDIS_PASS_CURRENT="new_redis_password_$(date +%s)" \
  REDIS_PASS_NEXT="newer_redis_password_$(date +%s)"

echo "Redis password rotated"

# Step 4: Monitor for errors during rotation
sleep 60
ERRORS_AFTER=$(curl -s http://localhost:8081/metrics | grep 'mutt_ingest_errors_total' | awk '{print $2}')
echo "Errors after rotation: $ERRORS_AFTER"

if [ "$ERRORS_AFTER" -eq "$ERRORS_BEFORE" ]; then
    echo "✅ No errors during Redis rotation"
else
    echo "⚠️  Errors increased: $ERRORS_BEFORE → $ERRORS_AFTER"
fi

# Step 5: Repeat for PostgreSQL password (after 10 minutes)
sleep 300
echo "Starting PostgreSQL password rotation..."

# Similar steps for DB_PASS_CURRENT and DB_PASS_NEXT
# ...

wait $K6_PID
echo "Load test completed"

# Step 6: Verify total error count
TOTAL_ERRORS=$(curl -s http://localhost:8081/metrics | grep 'mutt_ingest_errors_total' | awk '{print $2}')
echo "Total errors during test: $TOTAL_ERRORS"
```

**Success Criteria:**
- ✅ Zero event loss during rotation
- ✅ No connection errors in service logs
- ✅ Error rate remains < 0.1%
- ✅ Latency does not spike during rotation
- ✅ All services reconnect successfully

---

### Scenario 6: SLO Compliance Under Load

**Objective:** Maintain all 6 SLOs during normal and peak load conditions.

**Test Parameters:**
- Duration: 60 minutes
- Load pattern: Baseline → Peak → Baseline

**SLOs to Validate:**
1. **Event Ingestion Availability**: >99.9%
2. **Event Processing Latency**: P95 < 600ms
3. **Alert Delivery Success Rate**: >99.5%
4. **API Availability**: >99.9%
5. **Queue Health**: Depth < 1000
6. **Circuit Breaker Uptime**: >95% in CLOSED state

**Monitoring Queries:**
```promql
# 1. Ingestion Availability
sum(rate(mutt_ingest_requests_total{status="success"}[5m]))
/
sum(rate(mutt_ingest_requests_total[5m]))
> 0.999

# 2. Processing Latency P95
histogram_quantile(0.95,
  rate(mutt_event_processing_duration_seconds_bucket[5m])
) < 0.600

# 3. Alert Delivery Success
sum(rate(mutt_alert_delivery_total{status="success"}[5m]))
/
sum(rate(mutt_alert_delivery_total[5m]))
> 0.995

# 4. API Availability
sum(rate(mutt_api_requests_total{status=~"2.."}[5m]))
/
sum(rate(mutt_api_requests_total[5m]))
> 0.999

# 5. Queue Health
mutt_queue_depth < 1000

# 6. Circuit Breaker Uptime
avg_over_time(mutt_circuit_breaker_state[5m]) == 0  # CLOSED
```

**Success Criteria:**
- ✅ All 6 SLOs maintained for >95% of test duration
- ✅ SLO dashboard shows green status
- ✅ Error budget not exceeded
- ✅ No SLO violations trigger alerts

---

### Scenario 7: Data Retention Performance

**Objective:** Validate archival and purge performance with large datasets.

**Prerequisites:**
- PostgreSQL with 1M+ events in event_audit_log
- At least 100K events older than 90 days
- Partitions created for past 12 months

**Test Procedure:**
```bash
#!/bin/bash
# tests/load/scenario7-retention.sh

# Step 1: Check current data volume
echo "=== Current Data Volume ==="
psql -h localhost -U postgres -d mutt -c "
SELECT
    schemaname, tablename,
    pg_size_pretty(pg_total_relation_size(schemaname||'.'||tablename)) AS size
FROM pg_tables
WHERE tablename LIKE 'event_audit_log%'
ORDER BY pg_total_relation_size(schemaname||'.'||tablename) DESC;
"

# Step 2: Run retention enforcer with dry-run
echo ""
echo "=== Dry-Run (Preview) ==="
python scripts/retention_policy_enforcer.py --dry-run

# Step 3: Run actual archival
echo ""
echo "=== Running Archival ==="
time python scripts/retention_policy_enforcer.py --archive

# Step 4: Check archive table size
echo ""
echo "=== Archive Table Size ==="
psql -h localhost -U postgres -d mutt -c "
SELECT
    COUNT(*) AS archived_events,
    pg_size_pretty(pg_total_relation_size('event_audit_log_archive')) AS size
FROM event_audit_log_archive;
"

# Step 5: Run purge (delete data >7 years old)
echo ""
echo "=== Running Purge ==="
time python scripts/retention_policy_enforcer.py --purge

# Step 6: Verify purge results
echo ""
echo "=== Purge Results ==="
psql -h localhost -U postgres -d mutt -c "
SELECT
    MIN(event_time) AS oldest_event,
    MAX(event_time) AS newest_event,
    COUNT(*) AS total_events
FROM event_audit_log_archive;
"

# Step 7: Check metrics
echo ""
echo "=== Retention Metrics ==="
curl -s http://localhost:9090/api/v1/query?query=mutt_retention_archived_events_total
curl -s http://localhost:9090/api/v1/query?query=mutt_retention_purged_events_total
```

**Performance Targets:**
- Archival: 10,000 rows/second
- Purge: 5,000 rows/second
- Partition creation: < 1 second
- Index creation: < 10 seconds for 1M rows

**Success Criteria:**
- ✅ Archive completes in < 10 minutes for 1M rows
- ✅ Purge completes in < 5 minutes for 500K rows
- ✅ No blocking of active writes during archival
- ✅ Prometheus metrics updated correctly
- ✅ Database size reduced after purge

---

## Baseline Performance Targets

### Event Ingestion

| Metric | Target | Stretch Goal |
|--------|--------|--------------|
| **Throughput** | 50,000 events/hour | 100,000 events/hour |
| **Latency P50** | < 200ms | < 100ms |
| **Latency P95** | < 600ms | < 400ms |
| **Latency P99** | < 1000ms | < 800ms |
| **Error Rate** | < 1% | < 0.1% |

### API Performance

| Metric | Target | Stretch Goal |
|--------|--------|--------------|
| **GET /api/v2/metrics** | < 200ms P95 | < 100ms P95 |
| **POST /api/v1/config** | < 500ms P95 | < 300ms P95 |
| **GET /api/v1/audit** | < 1000ms P95 | < 500ms P95 |

### Resource Utilization

| Resource | Normal Load | Peak Load | Max Limit |
|----------|-------------|-----------|-----------|
| **CPU (per service)** | < 50% | < 80% | 90% |
| **Memory (per service)** | < 300MB | < 450MB | 512MB |
| **PostgreSQL Connections** | < 50 | < 80 | 100 |
| **Redis Memory** | < 500MB | < 800MB | 1GB |

### Queue Health

| Metric | Normal | Warning | Critical |
|--------|--------|---------|----------|
| **Queue Depth** | < 100 | 100-500 | > 1000 |
| **Processing Lag** | < 5 sec | 5-30 sec | > 60 sec |
| **DLQ Depth** | < 10 | 10-100 | > 500 |

---

## Execution Procedures

### Pre-Test Checklist

```bash
# 1. Verify environment is ready
muttdev status

# 2. Check baseline metrics
curl http://localhost:8081/metrics | grep mutt_ingest_requests_total
curl http://localhost:8083/metrics | grep mutt_circuit_breaker_state

# 3. Clear queues
redis-cli DEL mutt:queue:events mutt:queue:processing mutt:queue:dlq

# 4. Reset Prometheus counters (optional - restart Prometheus)
docker-compose restart prometheus

# 5. Check disk space
df -h

# 6. Verify Grafana dashboards are accessible
curl http://localhost:3000/api/health

# 7. Tail logs for errors
muttdev logs alerter -f &
```

### Running Tests

**Single Scenario:**
```bash
k6 run tests/load/scenario1-baseline-throughput.js
```

**All Scenarios Sequentially:**
```bash
#!/bin/bash
# tests/load/run-all-scenarios.sh

for scenario in scenario{1..7}*.js; do
    echo "Running $scenario..."
    k6 run "$scenario"

    # Cool-down period between tests
    echo "Cooling down for 5 minutes..."
    sleep 300
done

echo "All scenarios complete!"
```

**Continuous Load Testing:**
```bash
# Run baseline load continuously for soak testing
k6 run --duration 24h tests/load/baseline.js
```

### Post-Test Analysis

```bash
# 1. Export Prometheus data
curl -G 'http://localhost:9090/api/v1/query_range' \
  --data-urlencode 'query=mutt_ingest_requests_total' \
  --data-urlencode 'start=2025-11-11T10:00:00Z' \
  --data-urlencode 'end=2025-11-11T11:00:00Z' \
  --data-urlencode 'step=15s' \
  > results/ingest_requests.json

# 2. Check for errors in logs
muttdev logs alerter | grep -i error > results/alerter_errors.log
muttdev logs moog_forwarder | grep -i error > results/forwarder_errors.log

# 3. Analyze queue metrics
redis-cli --csv llen mutt:queue:events > results/queue_depth.csv

# 4. Database query performance
psql -h localhost -U postgres -d mutt -c "
SELECT query, calls, mean_exec_time, max_exec_time
FROM pg_stat_statements
ORDER BY mean_exec_time DESC
LIMIT 20;
" > results/slow_queries.txt

# 5. Generate HTML report from k6 output
k6 run --out json=results/scenario1.json tests/load/scenario1-baseline-throughput.js
# Use k6-reporter or similar to generate HTML
```

---

## Monitoring & Metrics

### Key Metrics to Watch

**During Load Tests:**

1. **Ingestion Rate:**
   ```promql
   rate(mutt_ingest_requests_total[1m])
   ```

2. **Processing Latency:**
   ```promql
   histogram_quantile(0.95, rate(mutt_event_processing_duration_seconds_bucket[5m]))
   ```

3. **Error Rate:**
   ```promql
   rate(mutt_ingest_errors_total[1m]) / rate(mutt_ingest_requests_total[1m])
   ```

4. **Queue Depth:**
   ```promql
   mutt_queue_depth
   ```

5. **Circuit Breaker State:**
   ```promql
   mutt_circuit_breaker_state{name="moogsoft"}
   ```

6. **Resource Usage:**
   ```promql
   container_memory_usage_bytes{container=~"alerter|moog_forwarder|ingestor"}
   container_cpu_usage_seconds_total{container=~"alerter|moog_forwarder|ingestor"}
   ```

### Grafana Dashboards

**Import Pre-Built Dashboards:**
```bash
# Import MUTT v2.5 load testing dashboard
curl -X POST http://localhost:3000/api/dashboards/db \
  -H "Content-Type: application/json" \
  -d @dashboards/load-testing.json
```

**Key Panels:**
- Ingestion rate (events/sec)
- API latency percentiles (P50, P95, P99)
- Queue depth over time
- Error rate over time
- Circuit breaker state timeline
- Resource utilization (CPU, memory)
- SLO compliance indicators

### Alerting During Tests

**Prometheus Alert Rules:**
```yaml
groups:
  - name: load_testing
    interval: 30s
    rules:
      - alert: HighErrorRateDuringLoadTest
        expr: rate(mutt_ingest_errors_total[5m]) / rate(mutt_ingest_requests_total[5m]) > 0.05
        for: 2m
        annotations:
          summary: "Error rate >5% during load test"

      - alert: HighQueueDepthDuringLoadTest
        expr: mutt_queue_depth > 2000
        for: 5m
        annotations:
          summary: "Queue depth sustained >2000"

      - alert: HighLatencyDuringLoadTest
        expr: histogram_quantile(0.95, rate(mutt_event_processing_duration_seconds_bucket[5m])) > 1.0
        for: 3m
        annotations:
          summary: "P95 latency >1 second"
```

---

## Results Analysis

### Success Criteria Checklist

After each test scenario, verify:

**Performance:**
- [ ] Throughput meets or exceeds target
- [ ] Latency within acceptable bounds (P95, P99)
- [ ] Error rate < 1%

**Reliability:**
- [ ] No service crashes or restarts
- [ ] Circuit breaker operates correctly
- [ ] Auto-remediation functions as expected

**Scalability:**
- [ ] Resource usage remains within limits
- [ ] No memory leaks detected
- [ ] Database connections don't exhaust pool

**Feature Validation:**
- [ ] Dynamic config propagates within 5 seconds
- [ ] Secret rotation completes without errors
- [ ] SLOs maintained under load
- [ ] Data retention performs within targets

### Interpreting Results

**Good Test Results:**
```
Scenario 1: Baseline Throughput
✅ Throughput: 52,000 events/hour (target: 50K)
✅ P95 latency: 480ms (target: <600ms)
✅ P99 latency: 720ms (target: <1000ms)
✅ Error rate: 0.3% (target: <1%)
✅ CPU usage: 65% peak (limit: 80%)
✅ Memory: 380MB peak (limit: 512MB)
```

**Problematic Results:**
```
Scenario 2: Rate Limiting
❌ P95 latency: 1200ms (target: <600ms) - INVESTIGATION NEEDED
⚠️  Error rate: 2.1% (target: <1%) - MARGINAL
❌ CPU usage: 92% peak (limit: 80%) - RESOURCE CONSTRAINT
✅ Rate limiter active: 429 responses during spike
```

**Action Items from Problems:**
- Latency exceeds target → Investigate slow database queries, add indexes
- Error rate high → Check service logs for specific error types
- CPU constraint → Consider horizontal scaling or code optimization

### Comparative Analysis

**Compare v2.5 vs v2.4:**

| Metric | v2.4 | v2.5 | Change |
|--------|------|------|--------|
| Throughput | 30K/hr | 50K/hr | +67% ✅ |
| P95 Latency | 600ms | 500ms | -17% ✅ |
| Error Rate | 0.8% | 0.3% | -62% ✅ |
| Memory/Service | 450MB | 380MB | -16% ✅ |
| Features | 12 | 25 | +108% ✅ |

---

## Troubleshooting

### Common Issues

#### Issue 1: High Queue Depth

**Symptoms:**
- Queue depth >1000 sustained
- Processing lag increasing
- Backpressure activated

**Diagnosis:**
```bash
# Check queue depths
redis-cli llen mutt:queue:events
redis-cli llen mutt:queue:processing
redis-cli llen mutt:queue:dlq

# Check alerter processing rate
curl http://localhost:8082/metrics | grep mutt_events_processed_total

# Check for alerter errors
muttdev logs alerter | grep -i error
```

**Solutions:**
- Increase alerter replicas
- Check for slow database queries
- Verify network connectivity to downstream services
- Check circuit breaker state

#### Issue 2: Circuit Breaker Stuck Open

**Symptoms:**
- Circuit breaker state = 2 (OPEN) for extended period
- All events going to DLQ
- Moogsoft health check failing

**Diagnosis:**
```bash
# Check circuit breaker state
curl http://localhost:8083/metrics | grep mutt_circuit_breaker_state

# Check Moogsoft health
curl http://moogsoft:8080/health

# Check circuit breaker failure count
curl http://localhost:8083/metrics | grep mutt_circuit_breaker_failures
```

**Solutions:**
- Verify Moogsoft service is running and healthy
- Check Moogsoft logs for errors
- Manually test Moogsoft API endpoint
- Restart Moog Forwarder to reset circuit breaker

#### Issue 3: Memory Leak

**Symptoms:**
- Memory usage continuously increasing
- OOMKilled pods in Kubernetes
- Slow performance degradation

**Diagnosis:**
```bash
# Monitor memory over time
watch -n 5 'docker stats --no-stream'

# Check for memory leaks with Python profiler
python -m memory_profiler services/alerter_service.py

# Analyze heap dump
# (Requires py-spy or similar)
py-spy dump --pid $(pgrep -f alerter_service)
```

**Solutions:**
- Review code for unclosed connections
- Check for large in-memory caches
- Verify proper garbage collection
- Add memory limits and restart policies

#### Issue 4: Slow Database Queries

**Symptoms:**
- API latency high
- Database CPU at 100%
- Slow log queries appearing

**Diagnosis:**
```sql
-- Check slow queries
SELECT
    query,
    calls,
    mean_exec_time,
    max_exec_time
FROM pg_stat_statements
WHERE mean_exec_time > 100
ORDER BY mean_exec_time DESC
LIMIT 20;

-- Check missing indexes
SELECT
    schemaname,
    tablename,
    attname,
    n_distinct,
    correlation
FROM pg_stats
WHERE schemaname = 'public'
  AND n_distinct > 100
  AND correlation < 0.5;

-- Check table bloat
SELECT
    schemaname,
    tablename,
    pg_size_pretty(pg_total_relation_size(schemaname||'.'||tablename)) AS size
FROM pg_tables
WHERE schemaname = 'public'
ORDER BY pg_total_relation_size(schemaname||'.'||tablename) DESC;
```

**Solutions:**
- Add indexes for frequently filtered columns
- Run VACUUM ANALYZE on large tables
- Review query plans with EXPLAIN ANALYZE
- Consider partitioning large tables

#### Issue 5: Config Changes Not Propagating

**Symptoms:**
- Config update via API succeeds
- Services don't pick up new value
- Logs show no config change detection

**Diagnosis:**
```bash
# Check Redis for config value
redis-cli GET mutt:config:cache_reload_interval

# Check PubSub channel
redis-cli SUBSCRIBE mutt:config:invalidate

# Check service logs for DynamicConfig initialization
muttdev logs alerter | grep "DynamicConfig"
muttdev logs alerter | grep "Config change detected"

# Verify watcher thread is running
muttdev logs alerter | grep "Config watcher thread"
```

**Solutions:**
- Verify DYNAMIC_CONFIG_ENABLED=true
- Check Redis connection in service logs
- Restart services to reinitialize DynamicConfig
- Verify PubSub channel name matches

---

## Summary

Load testing is critical to validate MUTT v2.5 features perform under production-like conditions. Follow these scenarios systematically, monitor key metrics, and analyze results to ensure:

1. **Performance targets are met** (50K events/hour, <600ms P95 latency)
2. **New features work under load** (dynamic config, secret rotation, circuit breaker)
3. **SLOs are maintained** (>99.9% availability, <1% errors)
4. **System is resilient** (graceful degradation, auto-recovery)

Use the provided k6 scripts and bash procedures as a starting point, then customize based on your specific deployment environment and requirements.

---

## Additional Resources

- [k6 Documentation](https://k6.io/docs/)
- [Apache JMeter Documentation](https://jmeter.apache.org/usermanual/index.html)
- [Prometheus Query Examples](https://prometheus.io/docs/prometheus/latest/querying/examples/)
- [Grafana Dashboard Best Practices](https://grafana.com/docs/grafana/latest/dashboards/build-dashboards/best-practices/)

---

## Change Log

- **2025-11-11**: Initial v2.5 load testing guide created

