# MUTT Evolution Roadmap

**Version:** 1.0
**Last Updated:** 2025-11-10
**Status:** Draft
**Audience:** Architects, Product Managers, Engineering Leads
**Prerequisites:** `SYSTEM_ARCHITECTURE.md`, `DESIGN_RATIONALE.md`

---

## Table of Contents
1. [Current Limitations](#current-limitations)
2. [Near-Term Evolution (6-12 months)](#near-term-evolution-6-12-months)
3. [Medium-Term Evolution (1-2 years)](#medium-term-evolution-1-2-years)
4. [Long-Term Vision (2-5 years)](#long-term-vision-2-5-years)
5. [Migration Strategies](#migration-strategies)

---

## Current Limitations

While MUTT v2.5 is a robust and scalable system, it has several known limitations and areas of technical debt that inform our future roadmap.

*   **Known Technical Debt:**
    *   **No Automated Testing Suite:** The lack of a comprehensive unit and integration test suite is the most significant piece of technical debt. This increases the risk of regressions and slows down future development.
    *   **Manual Database Partition Management:** The process for creating new monthly partitions for the `event_audit_log` is manual. This is a potential operational pain point.
    *   **No Graceful Shutdown on Workers:** While the janitor process prevents data loss, the worker processes do not currently have a graceful shutdown procedure to finish in-flight work before exiting.

*   **Scalability Ceiling:**
    *   The primary scalability bottleneck is the write throughput of the single **PostgreSQL** primary.
    *   At very high event volumes, the single-threaded nature of **Redis** could become a bottleneck.

*   **Feature Gaps:**
    *   **No Real-Time Rule Updates:** Rule changes require a cache reload (either via Pub/Sub, SIGHUP, or periodic refresh), which is not instantaneous.
    *   **Basic Deduplication:** The system relies on downstream systems like Moogsoft for advanced event deduplication.
    *   **No Built-in Correlation:** The system processes events in isolation and does not have a mechanism for correlating related events over a time window (e.g., a "link down" followed by a "link up").

*   **Operational Pain Points:**
    *   Troubleshooting "poison pill" messages in the Dead Letter Queues is a manual process.
    *   Tuning rate limits and circuit breaker thresholds requires manual configuration changes and redeployment.

---

## Near-Term Evolution (6-12 months)

The focus for the near term is on improving robustness, maintainability, and observability.

*   **Implement Comprehensive Automated Testing:**
    *   **Goal:** Achieve >80% unit test coverage for all services. Implement a `docker-compose`-based integration test suite that validates the end-to-end data flow.
    *   **Why:** To enable developers to make changes with confidence, reduce the risk of regressions, and automate quality gates in the CI/CD pipeline.

*   **Automate Database Partition Management:**
    *   **Goal:** Create a cron job or a small, dedicated service that automatically creates new database partitions for the upcoming months and archives or drops old ones based on the defined retention policy.
    *   **Why:** To remove a manual, error-prone operational task.

*   **Enhance Observability with OpenTelemetry:**
    *   **Goal:** Instrument the services with OpenTelemetry to provide distributed traces in addition to the existing logs and metrics.
    *   **Why:** To provide deeper insight into the latency of each processing step and make it easier to diagnose performance bottlenecks. The existing Correlation ID is a good foundation for this.

*   **Implement Graceful Shutdown:**
    *   **Goal:** Implement signal handlers (`SIGTERM`) in the Alerter and Moog Forwarder that allow the service to finish processing its current message before shutting down.
    *   **Why:** To reduce the number of "orphaned" messages that need to be recovered by the janitor process, leading to smoother deployments and scaling events.

---

## Medium-Term Evolution (1-2 years)

The focus for the medium term is on improving intelligence, scalability, and integration capabilities.

*   **Consider Kafka Migration Path:**
    *   **Trigger:** If sustained EPS targets exceed 10,000, or if a business need arises for long-term, replayable event streams.
    *   **Goal:** Develop and test a migration path from Redis to Apache Kafka as the primary message bus. This would likely involve creating a "bridge" service that could consume from Redis and produce to Kafka, allowing for a gradual transition.
    *   **Why:** Kafka provides superior throughput at very high scale and a durable, replayable log that can enable new use cases.

*   **Introduce a GraphQL API:**
    *   **Goal:** Implement a GraphQL endpoint in the Web UI service that aggregates data from the various REST API endpoints.
    *   **Why:** To provide a more flexible and efficient way for clients to query for exactly the data they need, reducing the number of API calls and simplifying frontend development.

*   **ML/AI Integration for Anomaly Detection:**
    *   **Goal:** Create a new service that subscribes to the event stream and uses machine learning models to detect anomalies (e.g., a sudden spike in events of a certain type).
    *   **Why:** To move from reactive, rule-based alerting to proactive, intelligent anomaly detection.

*   **ServiceNow Integration:**
    *   **Goal:** Create a new "Forwarder" service, similar to the Moog Forwarder, that can create and update incidents in ServiceNow.
    *   **Why:** To integrate with another major enterprise IT Service Management platform, expanding the system's applicability.

---

## Long-Term Vision (2-5 years)

The long-term vision is to evolve MUTT from an event processing pipeline into a comprehensive, intelligent automation platform.

*   **Evolve to a True Event-Driven Architecture:**
    *   **Goal:** Move beyond simple point-to-point queues to a full event streaming platform (likely based on Kafka) where services publish events to topics and other services can subscribe to them without direct coupling.
    *   **Why:** To create a more flexible and extensible architecture that allows new services and capabilities to be added easily.

*   **Advanced Correlation and Stream Processing:**
    *   **Goal:** Implement a stream processing engine (e.g., using Kafka Streams, Flink, or Spark Streaming) to perform complex event correlation over time windows.
    *   **Why:** To enable the detection of complex patterns that are invisible when looking at events in isolation (e.g., flapping interfaces, slow-building resource exhaustion).

*   **Self-Healing and Automated Remediation:**
    *   **Goal:** Create a "Remediation Service" that can take action based on correlated events, such as running an Ansible playbook, calling a cloud provider API, or automatically clearing a transient alert condition.
    *   **Why:** To close the loop from detection to resolution, moving towards a self-healing infrastructure.

---

## Migration Strategies

All major architectural changes must be implemented in a way that minimizes downtime and risk.

*   **Backward Compatibility:** APIs and message formats should be versioned. New versions should be introduced alongside the old ones, and the old versions should be deprecated and eventually removed after a suitable migration period. The current API versioning strategy (ADR-006) is the model for this.
*   **Parallel Infrastructure:** For major changes like a migration from Redis to Kafka, the new infrastructure should be built in parallel with the old. A "bridge" service can be used to route data between the two systems, allowing for a gradual, controlled cutover.
*   **Feature Flags:** New features or significant changes to existing logic should be deployed behind feature flags. This allows the new code to be deployed to production in a disabled state and then enabled for a subset of users or traffic, reducing the risk of a full-scale outage.
*   **Rollback Strategies:** Every deployment should have a documented rollback plan. For stateless services, this is as simple as deploying the previous version of the container image. For database or message format changes, the rollback plan is more complex and must be tested thoroughly.
