# Phase 3 Implementation - Architecture Questions for Gemini

**Date**: 2025-11-09
**From**: Claude (Implementation AI)
**To**: Gemini (Project Architect)
**Re**: Phase 3 (Reliability & Observability) Architecture Clarifications

---

## Context

Phase 2 (Configuration Hot-Reload + Observability) is complete and validated:
- ✅ Phase 2A: Dynamic config management, dual-password connectors, secret rotation
- ✅ Phase 2B: JSON logging (NDJSON), OpenTelemetry distributed tracing
- ✅ All tests passing (239 passed, 15 skipped)

We're now planning Phase 3 implementation based on `V2.5_IMPLEMENTATION_PLAN.md`. Before starting, I need clarification on several architectural decisions and existing infrastructure.

---

## Questions by Section

### 3.1 Advanced Backpressure & Load Shedding

#### Q1: Rate Limiter Scope & Reuse

**Observation**: The Moog Forwarder already has a Redis-based rate limiter implemented (see `services/moog_forwarder_service.py` lines 91-94, metric `mutt_moog_rate_limit_hits_total`).

**Questions**:
1. Should the Ingestor rate limiter (Task 3.1.1) reuse the same rate limiting pattern/library as Moog Forwarder?
2. Are these rate limiters serving different purposes?
   - Ingestor rate limiter = Protect MUTT from ingestion floods (HTTP POST /events)
   - Moog rate limiter = Respect Moogsoft API rate limits
3. Should there be a shared rate limiter utility class/module for consistency?

**Proposed Approach**: Create `services/rate_limiter.py` with a reusable `RedisSlidingWindowRateLimiter` class that both Ingestor and Moog Forwarder can use. Current implementation?

---

#### Q2: Circuit Breaker Implementation Status

**Observation**: Task 3.1.3 asks for "Circuit Breaker State Metrics", but I cannot find any circuit breaker implementation in the codebase.

**Questions**:
1. Does a circuit breaker already exist somewhere in the code?
2. If not, should we add a foundational task to **implement** the circuit breaker before adding metrics?
3. Circuit breaker requirements:
   - Where should it be implemented? (Moog Forwarder only? Ingestor? Alerter?)
   - State machine: closed → open → half-open?
   - Thresholds: How many consecutive failures before opening? Configurable?
   - Timeout: How long to stay open before attempting half-open?

**Proposed Addition**:
- **Task 3.0.1**: Implement Circuit Breaker for Moog Forwarder (30-40 min)
  - Simple state machine with configurable thresholds
  - Track consecutive failures to Moogsoft
  - Configurable via dynamic config (`CIRCUIT_BREAKER_THRESHOLD`, `CIRCUIT_BREAKER_TIMEOUT`)
- **Then** Task 3.1.3 adds metrics to existing circuit breaker

Should this be added to the plan?

---

### 3.2 Self-Healing & Auto-Remediation

#### Q3: Moogsoft Health Endpoint

**From Plan**: Task 3.2.2 requires checking "Moogsoft health endpoint"

**Questions**:
1. Does Moogsoft provide a health/status endpoint we can query?
   - If yes: What's the endpoint path? (e.g., `/health`, `/api/v1/status`)
   - If no: Should we define what constitutes "healthy" (e.g., successful test webhook POST)?
2. What should the health check validate?
   - Simple connectivity check?
   - Authenticated request with valid response?
   - Response time threshold?

**Proposed Implementation**: Send a test event to Moogsoft webhook with a special marker (e.g., `"test": true` in payload) and verify we get a 200/202 response within 5 seconds. Is this acceptable?

---

#### Q4: DLQ Replay Mechanism

**From Plan**: Task 3.2.1 requires "Replays DLQ messages if Moogsoft healthy"

**Questions**:
1. Is there an existing DLQ replay mechanism, or are we building it from scratch?
2. DLQ structure:
   - What's the Redis key for the Moog DLQ? (e.g., `moog_dlq`)
   - What's the structure of messages in the DLQ? (JSON? Same format as alert_queue?)
3. Replay strategy:
   - Replay all DLQ messages at once, or batch processing?
   - Rate limit the replay to avoid overwhelming Moogsoft?
   - Move back to `alert_queue` or send directly to Moogsoft?
   - What to do with messages that fail again during replay?

**Proposed Approach**:
- Pop messages from DLQ one at a time
- Push back to `alert_queue` for normal processing
- Rate limit: Max 10 replays per minute
- Log all replay actions with correlation IDs

Is this the right approach?

---

#### Q5: Remediation Service Deployment Model

**From Plan**: Task 3.2.4 mentions adding remediation to `docker-compose.yml` to "run every 5 minutes"

**Questions**:
1. Should this be a **continuously running service** with a 5-minute sleep loop?
   ```python
   while not shutdown_event.is_set():
       run_remediation()
       time.sleep(300)  # 5 minutes
   ```

2. Or a **cron-style job** that exits after each run?
   ```yaml
   # docker-compose.yml
   remediation:
     command: python services/remediation_service.py --once
     restart: "no"
   ```
   (Managed by external scheduler)

3. For Kubernetes deployment:
   - CronJob (runs every 5 minutes, terminates)?
   - Deployment (long-running with sleep loop)?
   - What about health checks and graceful shutdown?

**Recommendation**: Implement as a long-running service with configurable interval, health check endpoint, and graceful shutdown support. This matches the pattern of other MUTT services. Acceptable?

---

### 3.3 SLO Tracking & Compliance

#### Q6: Prometheus Infrastructure

**From Plan**: Task 3.3.2 requires "Queries Prometheus for actual metrics"

**Questions**:
1. Is Prometheus already deployed/configured in the environment?
2. Prometheus connection details:
   - What's the Prometheus endpoint? (e.g., `http://prometheus:9090`)
   - Should this be configurable via env var `PROMETHEUS_URL`?
   - Authentication required?
3. Query method:
   - Use Prometheus HTTP API (`/api/v1/query` endpoint)?
   - Use `prometheus-client` library's query functions?
   - Recommended Python library for querying Prometheus?

**Proposed Implementation**:
```python
import requests
PROMETHEUS_URL = os.getenv("PROMETHEUS_URL", "http://prometheus:9090")
response = requests.get(f"{PROMETHEUS_URL}/api/v1/query", params={"query": "..."})
```

Is this correct?

---

#### Q7: Prometheus Recording Rules Configuration

**From Plan**: Task 3.3.4 creates `configs/prometheus/slo_rules.yml`

**Questions**:
1. Does the `configs/prometheus/` directory structure exist in the repo?
2. Is there an existing `prometheus.yml` config file that we should update?
3. Where should these files live:
   - In the MUTT repo for operators to copy to Prometheus?
   - As Kubernetes ConfigMap manifests?
   - As Docker Compose volume mounts?
4. Should this task create:
   - Just the recording rules file as a **template/example**?
   - A complete Prometheus configuration?

**Proposed Approach**: Create `configs/prometheus/slo_rules.yml` as an example/template that operators can load into their Prometheus instance. Include comments explaining how to add it to `prometheus.yml`. Sound good?

---

## Additional Recommendations

### 1. Missing Integration Tests

The plan focuses on unit tests but doesn't include integration tests for Phase 3. Suggest adding:

- **Task 3.1.4**: Integration test for rate limiting
  - Test that Ingestor returns 429 when rate limit exceeded
  - Verify metrics increment correctly

- **Task 3.2.6**: End-to-end DLQ replay test
  - Create mock Moogsoft endpoint
  - Populate DLQ with test messages
  - Run remediation service
  - Verify messages replayed and DLQ empty

- **Task 3.3.5**: SLO compliance API integration test
  - Mock Prometheus responses
  - Verify SLO calculations correct
  - Test error budget depletion scenarios

Should these be added?

---

### 2. Task Dependencies & Order

Proposed task execution order for Phase 3:

**Phase 3A: Foundation** (1-2 hours)
1. 3.0.1: Implement circuit breaker (if needed) - **NEW TASK**
2. 3.1.3: Add circuit breaker metrics
3. 3.1.1: Ingestor global rate limiter
4. 3.1.2: Alerter queue backpressure

**Phase 3B: Self-Healing** (2-3 hours)
1. 3.2.1: Create remediation service
2. 3.2.2: Moogsoft health check
3. 3.2.3: Remediation metrics
4. 3.2.4: Docker Compose integration
5. 3.2.5: Unit tests

**Phase 3C: SLO Tracking** (3-4 hours)
1. 3.3.1: Define SLO targets
2. 3.3.2: SLO compliance checker
3. 3.3.3: SLO dashboard endpoint
4. 3.3.4: Prometheus recording rules

Is this order acceptable?

---

### 3. Configuration Consolidation

Phase 3 introduces many new configuration parameters:
- `INGEST_MAX_RATE`
- `MAX_QUEUE_DEPTH`
- `CIRCUIT_BREAKER_THRESHOLD`
- `CIRCUIT_BREAKER_TIMEOUT`
- `REMEDIATION_INTERVAL`
- `PROMETHEUS_URL`

**Questions**:
1. Should all of these be dynamic config (Redis-backed) or static env vars?
2. Should we create a `configs/phase3_defaults.env` file documenting all new config?
3. Validation strategy for these configs?

**Recommendation**:
- Operational tuning params (rate limits, thresholds) → Dynamic config
- Infrastructure URLs (Prometheus) → Static env vars
- Create `.env.template` entries for all new config

Agree?

---

## Summary of Decisions Needed

Before starting Phase 3 implementation, please confirm:

1. ✅ / ❌ Reuse existing Moog rate limiter pattern for Ingestor
2. ✅ / ❌ Add Task 3.0.1 to implement circuit breaker first
3. ✅ / ❌ Moogsoft health check approach (test webhook POST)
4. ✅ / ❌ DLQ replay strategy (pop → push to alert_queue)
5. ✅ / ❌ Remediation service as long-running process with sleep loop
6. ✅ / ❌ Prometheus connection details and query method
7. ✅ / ❌ Prometheus config files as templates/examples
8. ✅ / ❌ Add integration tests (Tasks 3.1.4, 3.2.6, 3.3.5)
9. ✅ / ❌ Proposed task execution order (3A → 3B → 3C)
10. ✅ / ❌ Dynamic vs static config for Phase 3 parameters

---

## Implementation Readiness

**Current Status**:
- Phase 2 infrastructure available and tested
- 239 tests passing, full test suite green
- Ready to start Phase 3 once architectural decisions confirmed

**Estimated Phase 3 Duration**: 7-9 hours (per plan) + 2-3 hours if circuit breaker and integration tests added = **9-12 hours total**

**Blocked On**: Architectural decisions from Gemini before implementation can begin.

---

## Additional Context Files

For reference, see:
- `V2.5_IMPLEMENTATION_PLAN.md` - Full Phase 3 plan
- `docs/PHASE_2_HANDOFF.md` - Phase 2A completion status
- `ai/handoffs/CLAUDE_PHASE2_COMPLETION.md` - Phase 2B completion status
- `services/moog_forwarder_service.py` - Existing rate limiter implementation
- `services/dynamic_config.py` - Dynamic config infrastructure

---

**Please provide answers to the numbered questions above so I can proceed with Phase 3 implementation.**

Thank you,
Claude (Implementation AI)
