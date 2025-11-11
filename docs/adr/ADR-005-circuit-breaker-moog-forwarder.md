# ADR-005: Circuit Breaker for Moog Forwarder

Date: 2025-11-10
Status: Accepted

## Context

The Moog Forwarder posts alerts to a Moogsoft webhook. When Moog is degraded or unreachable,
retries with exponential backoff help, but sustained failure still causes repeated attempts and
queue churn across replicas. We introduced a simple, global (cluster‑coordinated) circuit breaker
to fail fast and allow the system to recover gracefully.

## Decision

Implement a Redis‑backed circuit breaker in the forwarder that:
- Opens after N consecutive retryable failures
- Stays open for a configured duration
- Blocks sends (re‑queues messages) while open
- Resets on first success

## Implementation

File: `moog_forwarder_service.py`
- Keys:
  - `mutt:circuit:moog:open` (TTL when open)
  - `mutt:circuit:moog:failures` (counter of consecutive failures)
- Config (env):
  - `MOOG_CB_FAILURE_THRESHOLD` (default 5)
  - `MOOG_CB_OPEN_SECONDS` (default 60)
  - `MOOG_CB_KEY_PREFIX` (default `mutt:circuit:moog`)
- Metrics:
  - `mutt_moog_circuit_open` (0/1)
  - `mutt_moog_circuit_trips_total`
  - `mutt_moog_circuit_blocked_total`

## Rationale

This design is simple, observable, and requires no new infrastructure beyond Redis. It minimizes
additional latency when the downstream is known to be failing and protects the system from wasteful
retries during outages. Using Redis ensures all replicas share state.

## Alternatives Considered

1. Local in‑process breaker
   - Simpler but not shared across replicas; poor in horizontally scaled deployments.

2. Library‑based breakers (e.g., Hystrix‑like pattern)
   - Heavier dependencies and operational overhead; limited benefit beyond current needs.

3. Rely solely on backoff and rate limiting
   - Still attempts calls under persistent failure; slower recovery and higher load.

## Consequences

- When open, alerts are re‑queued; downstream pressure increases queue depth temporarily.
- Operators should monitor circuit metrics and DLQ depth; alerts may be delayed during outages.
- Tuning thresholds and open duration is environment‑specific; defaults are safe but may require adjustment.

## Follow‑ups

- Add operator runbook section (monitoring, tuning guidance).
- Optional: add half‑open state with trial requests after open period, if needed.

