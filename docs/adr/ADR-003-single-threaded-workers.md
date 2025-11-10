# ADR-003: Single-Threaded Workers per Pod

- Status: Accepted
- Date: 2025-11-10

Context
- Simplicity and predictability under load; Redis-backed queues; horizontal pod scaling available.

Decision
- Prefer single-threaded workers (one main loop) per pod/container, scale out horizontally.

Consequences
- Pros: Easier backpressure semantics; fewer concurrency bugs; predictable CPU/memory.
- Cons: Uses more pods for high throughput; may need careful CPU limits.

Alternatives Considered
- Multi-threading in-process: higher complexity, potential GIL contention for Python, harder metrics per worker.

References
- services/alerter_service.py and services/moog_forwarder_service.py main loops

