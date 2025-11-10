# MUTT v2.5 - Phase 3 Remaining Work Plan

**Date**: 2025-11-10
**From**: Gemini (Project Architect)
**To**: Implementation AI
**Re**: Final Tasks for Phase 3 Completion

---

## 1. Executive Summary

This document outlines the final, remaining work required to complete Phase 3 of the MUTT v2.5 project.

- **COMPLETED**: Phase 2 (All), Phase 3A (Backpressure Foundations), and Phase 3.2 (Self-Healing/Remediation Service).
- **REMAINING**: Phase 3.1 (Alerter Backpressure) and Phase 3.3 (SLO Tracking).

The project is in a very healthy state. The last agent successfully implemented the entire remediation service. This plan will guide you through the final features needed to complete the project.

**Your task is to implement the work described in this plan, starting with Section 3: Alerter Backpressure.**

---

## 2. Current State

### Completed & Validated
- ✅ **Phase 2**: Dynamic Config, Secret Rotation, JSON Logging, and OpenTelemetry Tracing.
- ✅ **Phase 3A Foundations**: A reusable `services/rate_limiter.py` module containing both a `RedisSlidingWindowRateLimiter` and a `CircuitBreaker` has been created. The Ingestor and Moog Forwarder have been updated to use these components.
- ✅ **Phase 3.2 Self-Healing**: The `services/remediation_service.py` is fully implemented, tested, and documented. It correctly replays messages from the DLQ, handles poison pills, and has deployment manifests for Docker and Kubernetes.

### Test Status
- **Total Tests Passing**: ~272
- **CI Status**: Green

---

## 3. Task: Implement Phase 3.1 - Alerter Backpressure

**Goal**: Protect the Alerter service from being overwhelmed by implementing a queue depth monitor and a load-shedding mechanism.

### 3.1.1 Tasks
1.  **Implement Queue Depth Monitoring in `services/alerter_service.py`**:
    -   In the main processing loop, before fetching a message, check the current depth of the `alert_queue` (`LLEN mutt:ingest_queue`).
    -   Compare the depth against two new dynamic configuration values:
        -   `alerter_queue_warn_threshold` (integer, e.g., 1000)
        -   `alerter_queue_shed_threshold` (integer, e.g., 5000)
    -   If depth > `warn_threshold`, log a warning.
    -   If depth > `shed_threshold`, trigger the shedding logic (see next task).
    -   Expose the current queue depth as a Prometheus Gauge: `mutt_alerter_queue_depth`.

2.  **Implement Shedding Strategy**:
    -   When the `shed_threshold` is breached, the Alerter should stop processing new events from the `alert_queue`.
    -   Instead, it should pop an event, add a `shedding_reason` field to the event payload, and immediately push it to the Alerter's Dead Letter Queue (`mutt:dlq:alerter`).
    -   Increment a new Prometheus Counter: `mutt_alerter_shed_events_total`.
    -   This prevents the Alerter from falling further behind and ensures events are safely stored for the Remediation service to handle later.

3.  **Create Unit Tests in `tests/test_alerter_unit.py`**:
    -   Add tests to simulate different queue depths (by mocking the Redis `LLEN` response).
    -   Verify that a warning is logged when the warn threshold is crossed.
    -   Verify that events are correctly moved to the DLQ when the shed threshold is crossed.
    -   Verify that the `mutt_alerter_shed_events_total` metric is incremented.

### 3.1.2 Acceptance Criteria
- When the `alert_queue` depth exceeds `alerter_queue_warn_threshold`, a warning is logged.
- When the `alert_queue` depth exceeds `alerter_queue_shed_threshold`, events are moved to `mutt:dlq:alerter` without being processed.
- New Prometheus metrics (`mutt_alerter_queue_depth`, `mutt_alerter_shed_events_total`) are exposed and updated correctly.
- All new and existing unit tests pass.

### 3.1.3 Files to Modify
- `services/alerter_service.py`
- `tests/test_alerter_unit.py`

---

## 4. Task: Implement Phase 3.3 - SLO Tracking & Dashboard

**Goal**: Provide visibility into the service's reliability by calculating and exposing SLOs via an API.

### 4.3.1 Tasks
1.  **Create `services/slo_checker.py`**:
    -   This new module will contain the logic for querying Prometheus and calculating SLOs.
    -   It should query the Prometheus HTTP API (endpoint configured by `PROMETHEUS_URL` env var).
    -   Implement functions to calculate success ratios for:
        -   **Ingestor**: `sum(rate(mutt_ingest_requests_total{status="success"}[$window])) / sum(rate(mutt_ingest_requests_total[$window]))`
        -   **Moog Forwarder**: `sum(rate(mutt_moog_requests_total{status="success"}[$window])) / sum(rate(mutt_moog_requests_total[$window]))`
    -   The time window (`$window`) should be configurable via dynamic config (`slo_window_hours`).

2.  **Add `/api/v1/slo` Endpoint to `services/web_ui_service.py`**:
    -   Create a new GET endpoint.
    -   This endpoint should use the `slo_checker` module to get the current availability for each component (Ingestor, Moog Forwarder).
    -   The response should be a JSON object containing the SLO target, the current availability, and the error budget remaining for each component.

3.  **Create Prometheus Recording Rules Template**:
    -   Create a new file: `docs/prometheus/recording-rules-v25.yml`.
    -   Add example recording rules that pre-calculate the success and error rates over various time windows (e.g., 5m, 1h, 24h) to make querying faster and more efficient.

4.  **Create Unit Tests in `tests/test_slo_unit.py`**:
    -   Create a new test file.
    -   Use a library like `requests-mock` to mock the Prometheus API responses.
    -   Write tests to verify that the SLO availability and error budget calculations are correct based on the mock data.

### 4.3.2 Acceptance Criteria
- A new GET `/api/v1/slo` endpoint exists in the Web UI.
- The endpoint returns a JSON object with SLO status for the Ingestor and Moog Forwarder.
- The calculations correctly reflect the data returned from the (mocked) Prometheus API.
- An example recording rules file exists at `docs/prometheus/recording-rules-v25.yml`.
- All new unit tests pass.

### 4.3.3 Files to Create/Modify
- `services/slo_checker.py` (New)
- `services/web_ui_service.py` (Modify)
- `docs/prometheus/recording-rules-v25.yml` (New)
- `tests/test_slo_unit.py` (New)

---

## 5. Finalization

After the above features are implemented, a final pass on documentation and configuration is required.

1.  **Update `.env.template`**: Add all new environment variables and dynamic config keys introduced in Phase 3.1 and 3.3.
2.  **Create Documentation**:
    -   `docs/ALERTER_BACKPRESSURE.md`: Explain how the feature works, how to configure the thresholds, and what metrics to monitor.
    -   `docs/SLOs.md`: Explain the SLO methodology, how the calculations work, and how to use the API endpoint and Prometheus rules.

---
This concludes the plan. Please begin with **Section 3: Alerter Backpressure**.
