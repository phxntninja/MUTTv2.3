# ADR-001: Redis Lists vs. Kafka for Queues

- Status: Accepted
- Date: 2025-11-10

Context
- MUTT processes moderate EPS with strict operational simplicity on RHEL/OpenShift.
- Requires atomic operations, DLQ semantics, and simple HA.

Decision
- Use Redis lists (with BRPOPLPUSH pattern) and per-worker processing lists; Sentinel/Cluster for HA.

Consequences
- Pros: Simple ops, low latency, atomic primitives, easy DLQ patterns.
- Cons: Not a durable log; limited replay; cluster complexity at large scale.

Alternatives Considered
- Kafka: +Strong durability and replay; -Operational overhead, higher latency, complexity not justified by EPS.

References
- services/alerter_service.py: BRPOPLPUSH processing lists
- docs/PHASE_3_HANDOFF_TO_ARCHITECT.md: Backpressure + DLQ patterns

