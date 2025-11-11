# MUTT Design Rationale

**Version:** 1.0
**Last Updated:** 2025-11-10
**Status:** Draft
**Audience:** Architects, Engineers
**Prerequisites:** `SYSTEM_ARCHITECTURE.md`

---

## Table of Contents
1. [Technology Selection Rationale](#technology-selection-rationale)
2. [Architectural Patterns Rationale](#architectural-patterns-rationale)
3. [Non-Functional Requirements](#non-functional-requirements)
4. [Trade-offs and Constraints](#trade-offs-and-constraints)

---

## Technology Selection Rationale

This section explains the reasoning behind the selection of key technologies in the MUTT stack.

### Redis vs. Kafka (ADR-001)

**Decision:** We chose Redis Lists with the `BRPOPLPUSH` pattern for our message queue over a more complex system like Apache Kafka.

**Rationale:**
*   **Operational Simplicity:** MUTT is designed to be operated by teams on standard RHEL environments. Redis is significantly easier to install, configure, and manage than a Zookeeper-dependent Kafka cluster. This aligns with our goal of minimizing operational complexity.
*   **Performance Characteristics:** For our target workload (moderate EPS, low-latency processing), Redis provides excellent performance. Its in-memory nature ensures that message queuing and retrieval are extremely fast.
*   **Atomic Primitives:** Redis provides powerful and simple atomic commands like `BRPOPLPUSH`, `INCR`, and Lua scripting. These primitives are the foundation of our reliability patterns (reliable queuing, atomic counters), and implementing them is straightforward.
*   **Good Enough Durability:** While Kafka offers superior durability through its distributed log, Redis with AOF (Append-Only File) persistence provides sufficient durability for our needs. In a crash, we might lose a few seconds of data that hasn't been flushed to disk, which is an acceptable trade-off for the operational simplicity.

**When to Reconsider:**
This decision should be revisited if the required Events Per Second (EPS) grows into the hundreds of thousands, or if a true "replayable log" of all events becomes a business requirement for long-term, queryable storage (beyond what the PostgreSQL audit log provides).

### Vault vs. Kubernetes Secrets (ADR-002)

**Decision:** We chose HashiCorp Vault as the primary secrets management solution, with support for Kubernetes Secrets as a potential read-only fallback.

**Rationale:**
*   **Cross-Platform Consistency:** MUTT must run on both bare-metal RHEL servers and in Kubernetes/OpenShift. Vault provides a single, consistent secrets management interface for both environments. Using only Kubernetes Secrets would require a separate, less secure solution for the RHEL deployment.
*   **Advanced Security Features:** Vault offers a rich set of features that are critical for a production-grade enterprise application:
    *   **Dynamic Secrets & Rotation:** Vault can dynamically generate and rotate credentials, which is essential for security compliance.
    *   **Fine-grained Access Control:** Vault's policy engine allows us to enforce strict, least-privilege access for each service.
    *   **Comprehensive Audit Trail:** Vault provides a detailed audit log of all secret access, which is a common requirement for security and compliance audits.
*   **AppRole Authentication:** Vault's AppRole authentication method is a perfect fit for our automated deployment model, allowing services to securely authenticate and retrieve their secrets without human intervention.

**When to Reconsider:**
If the project were to become Kubernetes-native *only*, and if the chosen Kubernetes environment had a mature, built-in secrets management solution with rotation and auditing capabilities (e.g., via a service mesh or a dedicated operator), we could consider simplifying the architecture by removing the Vault dependency.

### PostgreSQL for Audit Logs (ADR-004)

**Decision:** We chose PostgreSQL to store the `event_audit_log` and `config_audit_log`.

**Rationale:**
*   **Structured, Queryable Data:** The primary purpose of the audit log is for compliance and troubleshooting. PostgreSQL provides a robust, relational structure that allows for precise queries (e.g., "show me all events from `host-a` that matched `rule-123` in the last 24 hours"). This is much more difficult with a log aggregation platform.
*   **Partitioning for Manageability:** PostgreSQL's native table partitioning is a key feature. We partition the `event_audit_log` by month, which makes it easy to manage data retention (e.g., drop partitions older than 12 months) without performance degradation.
*   **Reduced Infrastructure Footprint:** Using a standard relational database that many organizations already have and support avoids the need to introduce and manage another complex system like Elasticsearch for what is a relatively simple requirement.
*   **ACID Compliance:** The transactional nature of PostgreSQL ensures that our audit records are written reliably.

**When to Reconsider:**
If the primary use case for the audit log were to shift from targeted queries to full-text search and complex data analytics, a system like Elasticsearch or Splunk would be more appropriate.

### Python as Implementation Language

**Decision:** We chose Python as the primary implementation language for all services.

**Rationale:**
*   **Rapid Development & Ecosystem:** Python's clean syntax and extensive library ecosystem (e.g., Flask, Requests, Psycopg2, HVAC) allow for rapid development and iteration. This was critical for delivering the project within the required timeframe.
*   **Team Expertise:** The development team has strong expertise in Python, which reduces development risk and improves code quality.
*   **Suitability for I/O-Bound Workloads:** Most of the work MUTT services do is I/O-bound (waiting for network requests, reading from Redis, writing to PostgreSQL). Python's concurrency models, while impacted by the GIL, are well-suited for this type of workload, especially when combined with a horizontal scaling strategy.
*   **Performance Trade-offs:** While a compiled language like Go or Rust might offer better raw performance, the performance of Python is more than sufficient for our current EPS targets, especially given our horizontally scalable architecture. The development velocity gained with Python outweighs the potential performance gains from other languages for this specific use case.

---

## Architectural Patterns Rationale

### Single-Threaded Workers (ADR-003)

**Decision:** We opted for single-threaded workers within each service container/pod, relying on horizontal scaling (running more pods) to increase throughput.

**Rationale:**
*   **Simplicity and Predictability:** A single-threaded model is vastly simpler to reason about, debug, and test. It eliminates a whole class of complex concurrency bugs (race conditions, deadlocks) within the application code itself.
*   **Clear Performance Model:** With a single thread, the resource utilization (CPU, memory) of a single worker is highly predictable. Scaling becomes a simple matter of running more copies of this predictable unit.
*   **Effective with Horizontal Scaling:** In modern containerized environments, scaling by adding more pods is the standard, idiomatic approach. Our architecture is designed to leverage this. The `BRPOPLPUSH` pattern naturally load-balances messages across all available workers.

**When to Reconsider:**
If the overhead of running many pods becomes a significant cost or operational burden, or if a particular service becomes heavily CPU-bound in a way that cannot be parallelized across multiple pods (a highly unlikely scenario for this application), we might consider introducing multi-threading or async processing (e.g., with `asyncio`) within a single worker.

### In-Memory Caching Strategy

**Decision:** The Alerter service maintains an in-memory cache of all alert rules, dev hosts, and team mappings, which is reloaded from PostgreSQL periodically and on-demand via a SIGHUP signal.

**Rationale:**
*   **Performance:** The Alerter may process thousands of events per second. Querying the database for every single event would create an unacceptable bottleneck. By caching all rules in memory, the matching process becomes extremely fast (O(n) in-memory scan vs. a database query per message).
*   **Database Decoupling:** The cache allows the Alerter to continue processing events even if the database is temporarily unavailable for reads.
*   **Hot-Reload with SIGHUP:** The use of a `SIGHUP` signal handler to trigger a cache reload is a standard, proven pattern in the Linux/Unix world. It allows for dynamic configuration updates without restarting the service, which is critical for a production system. The periodic refresh provides an additional layer of eventual consistency.

### Janitor Pattern for Recovery

**Decision:** We implemented a "janitor" process that runs on worker startup to recover orphaned messages from dead workers.

**Rationale:**
*   **Self-Healing and Resilience:** This pattern is the key to our crash-safe, at-least-once processing guarantee. It ensures that a worker crash is not a catastrophic event and that the system can automatically recover without losing data.
*   **No External Coordinator:** The janitor pattern achieves distributed system resilience without requiring a complex external coordinator like Zookeeper. Each worker is responsible for its own part in the recovery process, making the system simpler to operate.
*   **Heartbeat for Liveness:** The janitor process relies on a simple heartbeat key in Redis with a TTL to detect dead workers. This is a lightweight and effective liveness probe.

### Backpressure Design

**Decision:** The Ingestor service implements backpressure by monitoring the `ingest_queue` depth and returning an `HTTP 503` error if it exceeds a threshold.

**Rationale:**
*   **Preventing System Overload:** This is a critical stability pattern. It prevents a flood of incoming events from overwhelming the Redis server and causing a cascading failure.
*   **Pushing Back to the Source:** By returning a `503`, the Ingestor signals to the upstream system (`rsyslog`) that it needs to slow down. `rsyslog` is designed to handle this gracefully by queuing to disk and retrying, effectively using the host's local disk as an extended buffer. This prevents data loss at the source.
*   **Simplicity:** This queue-depth monitoring approach is simple to implement and effective for our architecture.

### Rate Limiting Approach

**Decision:** The Moog Forwarder uses a shared, Redis-based sliding window rate limiter implemented with a Lua script.

**Rationale:**
*   **Global Coordination:** The downstream Moog AIOps platform has a global rate limit. Any rate limiting solution must be shared across all horizontally scaled Moog Forwarder instances. A local, in-process rate limiter would be ineffective, as N workers would allow N times the desired rate.
*   **Atomicity:** A race condition exists where multiple workers could check the limit, see that it's okay, and then all send a request, collectively exceeding the limit. Using a Lua script in Redis ensures that the check-and-increment operation is atomic, preventing this race condition.
*   **Sliding Window Algorithm:** A sorted set in Redis provides an efficient way to implement a sliding window rate limiter, which is more accurate than a simpler fixed-window approach.

---

## Non-Functional Requirements

The architecture was designed to meet the following key non-functional requirements:

*   **Reliability:** The system must guarantee at-least-once processing of all events. No data should be lost due to a component crash. This drove the adoption of the `BRPOPLPUSH` and Janitor patterns.
*   **Scalability:** The system must be able to scale horizontally to handle increasing event volumes. This drove the stateless worker and shared-nothing architecture.
*   **Operational Simplicity:** The system must be deployable and manageable on standard enterprise infrastructure (RHEL, Docker, Kubernetes) without requiring exotic components. This drove the choice of Redis over Kafka and the simple, single-threaded worker model.
*   **Security:** All secrets must be managed securely, with rotation and auditing capabilities. All traffic between components must be encrypted. This drove the adoption of Vault and TLS-everywhere.
*   **Maintainability:** The codebase should be easy to understand, test, and modify. This drove the choice of Python and the separation of concerns between the different microservices.

---

## Trade-offs and Constraints

*   **Simplicity vs. Features:** We consistently chose simpler, proven patterns over more complex, feature-rich alternatives (e.g., Redis vs. Kafka). The trade-off is that we sacrifice some capabilities (like event stream replayability) for significant gains in operational simplicity and maintainability.
*   **At-Least-Once vs. Exactly-Once Processing:** Our reliability patterns guarantee at-least-once processing. In some rare crash scenarios (e.g., a crash after processing but before the message is removed from the processing list), a message could be processed twice. Given the nature of the data, this is an acceptable trade-off. Implementing exactly-once processing would add significant complexity.
*   **Known Limitation: Cache Invalidation:** The Alerter's rule cache is updated via a PubSub message and a periodic refresh. There is a small window (up to 5 minutes for the periodic refresh) where an Alerter might be operating with a slightly stale cache if it misses the PubSub message. This was deemed an acceptable trade-off for the performance gains of the in-memory cache.
*   **Constraint: RHEL Deployment:** The requirement to support a standalone RHEL deployment was a major constraint that influenced technology choices (e.g., Vault over K8s-native secrets) and deployment architecture.
