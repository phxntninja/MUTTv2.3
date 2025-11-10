# Phase 3.2 Self-Healing & Remediation - Completion Report

**Date:** 2025-11-10
**Completed By:** Claude (AI Assistant)
**Status:** ✅ **COMPLETE & VALIDATED**

---

## Executive Summary

Phase 3.2 (Self-Healing & Auto-Remediation) has been **successfully implemented and validated**. The remediation service provides automated recovery from common failure scenarios:

- ✅ **Remediation Service**: Long-running service with configurable interval
- ✅ **DLQ Replay**: Automatic replay of failed messages with poison protection
- ✅ **Moogsoft Health Checks**: Active health monitoring before replay
- ✅ **Poison Message Protection**: Prevents infinite retry loops
- ✅ **Comprehensive Metrics**: Full Prometheus instrumentation
- ✅ **Well-Tested**: 24 new unit tests, all passing
- ✅ **Production-Ready**: Docker Compose + Kubernetes manifests included

**Test Results:** 272 total tests passing (248 + 24 remediation), 13 skipped, 0 failures

---

## What Was Implemented

### 1. Remediation Service Core ([services/remediation_service.py](../../../services/remediation_service.py))

**Lines of Code:** 600+ lines
**Key Features:**
- Long-running service with configurable sleep interval
- Health check endpoint (port 8087)
- Prometheus metrics endpoint (port 8086)
- Graceful shutdown support (SIGINT/SIGTERM)
- Dynamic configuration support
- Phase 2 observability integration (JSON logging, OpenTelemetry)

**Architecture:**
```python
def main():
    # 1. Initialize configuration and connections
    # 2. Start metrics + health check servers
    # 3. Connect to Redis
    # 4. Run remediation loop:
    #    a. Check Moogsoft health
    #    b. Replay DLQ messages (if healthy)
    #    c. Sleep until next cycle
```

### 2. DLQ Replay Logic

**Function:** `replay_dlq_messages()`
**Features:**
- ✅ Pops messages from `mutt:dlq:alerter` (Right-to-Left)
- ✅ Checks `_moog_retry_count` field
- ✅ **If retry_count < MAX_POISON_RETRIES**: Replays to `alert_queue`
- ✅ **If retry_count >= MAX_POISON_RETRIES**: Moves to `mutt:dlq:dead` (terminal)
- ✅ Batch processing (configurable batch size)
- ✅ Error handling: Failures are pushed back to DLQ

**Poison Message Protection:**
```python
retry_count = get_retry_count(message)

if retry_count >= max_retries:
    # Terminal - move to dead letter
    redis_client.lpush(config.DEAD_LETTER_QUEUE, message)
    METRIC_POISON_MESSAGES.inc()
else:
    # Replay to alert queue
    redis_client.lpush(config.ALERTER_QUEUE_NAME, message)
    METRIC_REPLAY_SUCCESS.inc()
```

### 3. Moogsoft Health Checking

**Function:** `check_moogsoft_health()`
**Implementation:**
- Sends test event with special marker: `source=MUTT_HEALTH_CHECK`
- Accepts 200, 201, or 202 as healthy
- Timeouts and connection errors = unhealthy
- Configurable timeout (default: 5 seconds)
- Updates `mutt_remediation_moog_health` gauge metric

**Test Payload:**
```json
{
  "source": "MUTT_HEALTH_CHECK",
  "description": "Health check probe - auto-close",
  "severity": "clear",
  "check_id": "health_check_<timestamp>",
  "timestamp": "<iso8601>"
}
```

**Note for Operations:** Configure Moogsoft to auto-close alerts with `source=MUTT_HEALTH_CHECK`.

### 4. Prometheus Metrics

**New Metrics Added:**

| Metric | Type | Description |
|--------|------|-------------|
| `mutt_remediation_loops_total` | Counter | Total remediation loops executed |
| `mutt_remediation_dlq_depth` | Gauge | Current DLQ depth (by dlq_name) |
| `mutt_remediation_replay_success_total` | Counter | Successfully replayed messages |
| `mutt_remediation_replay_fail_total` | Counter | Failed replays (by reason) |
| `mutt_remediation_poison_messages_total` | Counter | Poison messages moved to dead letter |
| `mutt_remediation_moog_health` | Gauge | Moogsoft health (1=healthy, 0=unhealthy) |
| `mutt_remediation_loop_duration_seconds` | Histogram | Time per remediation loop |

### 5. Configuration Parameters

**New Environment Variables** (see [.env.template](../../../.env.template)):

```bash
# Remediation Service
REMEDIATION_ENABLED=true
REMEDIATION_INTERVAL=300          # 5 minutes
REMEDIATION_BATCH_SIZE=10
MAX_POISON_RETRIES=3
METRICS_PORT_REMEDIATION=8086
HEALTH_PORT_REMEDIATION=8087

# DLQ Names
ALERTER_DLQ_NAME=mutt:dlq:alerter
DEAD_LETTER_QUEUE=mutt:dlq:dead

# Moogsoft Health Check
MOOG_HEALTH_CHECK_ENABLED=true
MOOG_WEBHOOK_URL=http://moogsoft.example.com/webhook
MOOG_HEALTH_TIMEOUT=5

# Dynamic Config
DYNAMIC_CONFIG_ENABLED=false
```

**Dynamic Config Keys** (if enabled):
- `remediation_interval`: Override interval at runtime
- `remediation_batch_size`: Override batch size
- `max_poison_retries`: Override poison threshold

---

## Testing

### Unit Tests ([tests/test_remediation_unit.py](../../../tests/test_remediation_unit.py))

**Test Coverage:** 24 tests, all passing

**Test Classes:**
1. **TestRemediationConfig** (2 tests)
   - Config from environment variables
   - Config defaults

2. **TestMoogsoftHealthCheck** (6 tests)
   - Health check disabled/no URL
   - Success scenarios (200, 202)
   - Failure scenarios (500, timeout, connection error)

3. **TestRetryCountExtraction** (3 tests)
   - Extracting retry count from message
   - Handling missing retry count
   - Invalid JSON handling

4. **TestDLQReplay** (5 tests)
   - Empty DLQ
   - Normal message replay
   - Poison message handling
   - Batch size limit
   - Processing error handling

5. **TestDynamicConfigHelpers** (4 tests)
   - Getting interval/batch size/max retries
   - With and without dynamic config

6. **TestRemediationMetrics** (4 tests)
   - Replay success metric
   - Poison message metric
   - DLQ depth gauge

**Run Tests:**
```bash
pytest tests/test_remediation_unit.py -v
# Result: 24 passed in 0.81s
```

---

## Deployment

### 1. Docker Compose

**Added to:** [docker-compose.yml](../../../docker-compose.yml)

```yaml
remediation:
  build:
    context: .
    dockerfile: Dockerfile
    target: remediation
  container_name: mutt-remediation
  ports:
    - "8086:8086"  # Metrics
    - "8087:8087"  # Health
  environment:
    # ... (see docker-compose.yml for full config)
  depends_on:
    - redis
  healthcheck:
    test: ["CMD", "curl", "-f", "http://localhost:8087/health"]
  networks:
    - mutt-network
```

**Start Service:**
```bash
docker-compose up -d remediation
docker-compose logs -f remediation
```

### 2. Kubernetes

**Manifest:** [k8s/remediation-deployment.yaml](../../../k8s/remediation-deployment.yaml)

**Resources Created:**
- `Deployment`: mutt-remediation (1 replica, Recreate strategy)
- `Service`: mutt-remediation (ClusterIP)
- `ServiceAccount`: mutt-remediation
- `PodDisruptionBudget`: mutt-remediation-pdb

**Key Features:**
- Single replica (prevents race conditions on DLQ)
- Recreate strategy (ensures only one instance)
- Prometheus scraping annotations
- Liveness & readiness probes
- Security context (non-root, read-only filesystem)
- Resource limits (256Mi memory, 500m CPU)

**Deploy:**
```bash
kubectl apply -f k8s/remediation-deployment.yaml
kubectl get pods -n mutt -l component=remediation
kubectl logs -n mutt -l component=remediation -f
```

---

## Operation

### Monitoring

**Health Check:**
```bash
curl http://localhost:8087/health
# Returns: OK
```

**Metrics:**
```bash
curl http://localhost:8086/metrics | grep mutt_remediation
```

**Key Metrics to Watch:**
- `mutt_remediation_dlq_depth`: Should trend toward 0
- `mutt_remediation_poison_messages_total`: Should be low/zero
- `mutt_remediation_moog_health`: Should be 1
- `mutt_remediation_replay_success_total`: Increases when DLQ has messages

### Troubleshooting

**DLQ not draining?**
1. Check Moogsoft health: `mutt_remediation_moog_health` should be 1
2. Check logs for errors
3. Verify Redis connectivity
4. Check batch size vs DLQ depth

**Too many poison messages?**
1. Review `mutt:dlq:dead` contents
2. Check `_moog_retry_count` values
3. Consider increasing `MAX_POISON_RETRIES`
4. Investigate root cause of failures

**Service not starting?**
1. Check Redis connectivity
2. Verify Moogsoft URL is configured
3. Check logs: `docker-compose logs remediation`

---

## Integration with Existing System

### Message Flow

```
┌─────────────┐
│  Ingestor   │
└──────┬──────┘
       │
       v
┌─────────────┐
│alert_queue  │
└──────┬──────┘
       │
       v
┌─────────────┐
│   Alerter   │──────┐ Failure
└──────┬──────┘      │
       │             v
       │      ┌──────────────┐
       │      │dlq:alerter   │◄──┐
       │      └──────┬───────┘   │
       │             │           │
       v             │  ┌────────────────┐
┌─────────────┐     │  │  Remediation   │
│alert_queue  │     │  │   Service      │
└──────┬──────┘     │  └────────────────┘
       │            │         │
       v            │         │ Retry count
┌─────────────┐    │         │ >= max?
│Moog Forward │────┘         │
└──────┬──────┘              │
       │                     v
       v               ┌──────────┐
   [Moogsoft]          │dlq:dead  │ (Terminal)
                       └──────────┘
```

### Redis Keys Used

| Key | Type | Purpose |
|-----|------|---------|
| `mutt:dlq:alerter` | List | Primary DLQ (source for replay) |
| `mutt:ingest_queue` | List | Target for replayed messages |
| `mutt:dlq:dead` | List | Terminal storage for poison messages |

---

## Files Modified/Created

### New Files
- ✅ [services/remediation_service.py](../../../services/remediation_service.py) - Main service (600+ lines)
- ✅ [tests/test_remediation_unit.py](../../../tests/test_remediation_unit.py) - Unit tests (450+ lines)
- ✅ [k8s/remediation-deployment.yaml](../../../k8s/remediation-deployment.yaml) - K8s manifest

### Modified Files
- ✅ [docker-compose.yml](../../../docker-compose.yml) - Added remediation service
- ✅ [.env.template](../../../.env.template) - Added Phase 3.1 + 3.2 parameters

---

## Acceptance Criteria

**From [Phase 3 Handoff](../../docs/PHASE_3_HANDOFF.md):**

| Criteria | Status | Evidence |
|----------|--------|----------|
| Remediation service runs as long-running process | ✅ | `remediation_loop()` with configurable interval |
| DLQ messages replayed when conditions favorable | ✅ | `replay_dlq_messages()` function |
| Poison message protection implemented | ✅ | Checks `_moog_retry_count`, moves to dead letter |
| Moogsoft health checking before replay | ✅ | `check_moogsoft_health()` function |
| Comprehensive metrics exposed | ✅ | 7 new Prometheus metrics |
| Unit tests pass | ✅ | 24/24 tests passing |
| Docker Compose integration | ✅ | Service added to docker-compose.yml |
| Kubernetes deployment manifest | ✅ | remediation-deployment.yaml created |

---

## Next Steps

### Immediate
- [ ] Add remediation service to CI/CD pipeline
- [ ] Configure Moogsoft to auto-close health check events
- [ ] Set up Prometheus alerts for remediation metrics
- [ ] Document operational runbooks

### Phase 3.3 (SLO Tracking)
- [ ] Implement SLO checker module
- [ ] Create `/api/v1/slo` endpoint in Web UI
- [ ] Create Prometheus recording rules template
- [ ] Add SLO compliance tests

### Future Enhancements
- [ ] Add email/Slack notifications for poison messages
- [ ] Implement DLQ inspection API
- [ ] Add remediation service dashboard in Grafana
- [ ] Support multiple DLQ sources

---

## Metrics Baseline

**After Implementation:**
```
272 tests passing (248 core + 24 remediation)
13 tests skipped
0 failures

Test execution time: ~2 seconds
```

---

## Documentation

**User Documentation:**
- Configuration: See `.env.template` Phase 3.2 section
- Deployment: See this document, sections "Deployment" and "Operation"
- Troubleshooting: See "Troubleshooting" section above

**Developer Documentation:**
- Service architecture: See `services/remediation_service.py` docstrings
- Test coverage: See `tests/test_remediation_unit.py`
- API: Health check at `:8087/health`, metrics at `:8086/metrics`

---

## Summary

Phase 3.2 adds critical self-healing capabilities to MUTT v2.5:

1. **Automated Recovery**: DLQ messages automatically replayed when conditions improve
2. **Poison Protection**: Prevents infinite retry loops with retry count tracking
3. **Health-Aware**: Only replays when Moogsoft is healthy
4. **Observable**: Full Prometheus instrumentation
5. **Production-Ready**: Complete with Docker + K8s deployment

The remediation service significantly reduces operational toil by automatically recovering from transient failures while protecting against poison messages.

**Status: Phase 3.2 Complete ✅**

**Next: Phase 3.3 (SLO Tracking)** or **Finalization**
