# MUTT System Architecture

**Version:** 1.0
**Last Updated:** 2025-11-10
**Status:** Draft
**Audience:** Architects, Engineers, Operators
**Prerequisites:** None

---

## Table of Contents
1. [System Overview](#system-overview)
2. [Architecture Diagram Description](#architecture-diagram-description)
3. [Component Architecture](#component-architecture)
4. [Data Flow Patterns](#data-flow-patterns)
5. [Reliability Patterns](#reliability-patterns)
6. [Scalability Architecture](#scalability-architecture)

---

## System Overview

MUTT (Multi-Use Telemetry Tool) is a production-grade, horizontally scalable event processing system designed for network operations teams and Site Reliability Engineers (SREs). At a business level, MUTT functions as an intelligent filter and forwarder for high-volume machine-generated data (syslog and SNMP traps). It ingests raw event streams, applies rule-based logic to determine their significance, and forwards actionable alerts to the Moogsoft AIOps platform. This process reduces alert noise, ensures critical events are handled correctly, and provides a comprehensive audit trail for all incoming data.

The key benefit of MUTT is its ability to decouple event sources from the AIOps platform, providing a layer of intelligent, resilient, and scalable processing. This allows operations teams to manage complex routing logic, test rules in a development context, and ensure that only high-value alerts reach operators, thereby reducing mean time to resolution (MTTR) and preventing alert fatigue.

---

## Architecture Diagram Description

```
┌─────────────────┐      ┌──────────────────┐      ┌─────────────────┐
│  Network Syslog │──────▶│   rsyslog        │──────▶│   Ingestor     │
│  UDP/TCP 514    │      │   (Port 514)     │      │   (Port 8080)  │
└─────────────────┘      └──────────────────┘      └────────┬────────┘
                                                              │
┌─────────────────┐      ┌──────────────────┐               │
│  SNMP Traps     │──────▶│   snmptrapd      │               │
│  UDP 162        │      │   → local5       │───────────────┘
└─────────────────┘      └──────────────────┘               │
                                                              ▼
                         ┌──────────────────────────────────────────┐
                         │         Redis (HA with Sentinel)         │
                         │  ┌────────────────┐  ┌────────────────┐ │
                         │  │ ingest_queue   │  │  alert_queue   │ │
                         │  └────────────────┘  └────────────────┘ │
                         └──────────┬──────────────────┬────────────┘
                                    │                  │
                                    ▼                  ▼
                         ┌──────────────────┐  ┌─────────────────┐
                         │   Alerter        │  │  Moog Forwarder │
                         │   (Port 8081)    │  │  (Port 8083)    │
                         └─────────┬────────┘  └────────┬────────┘
                                   │                    │
                                   ▼                    ▼
                         ┌──────────────────┐  ┌─────────────────┐
                         │   PostgreSQL     │  │   Moog AIOps    │
                         │   (Audit Trail)  │  │   (Webhook)     │
                         └──────────────────┘  └─────────────────┘
                                   ▲
                                   │
                         ┌─────────┴────────┐
                         │    Web UI        │
                         │   (Port 8090)    │
                         └──────────────────┘
```
*Figure 1: MUTT High-Level Architecture*

The architecture illustrates a unidirectional data flow designed for reliability and scalability.

1.  **Ingestion:** Network devices send syslog and SNMP trap data to standard collection daemons (`rsyslog`, `snmptrapd`) on the host server. These daemons format the messages into JSON and forward them via HTTP to the **Ingestor Service**. This provides a standardized entry point into the MUTT ecosystem.

2.  **Queuing:** The Ingestor places all incoming messages into a reliable queue (`ingest_queue`) within a High-Availability **Redis** cluster. This queue acts as a central buffer, decoupling the ingestion layer from the processing layer.

3.  **Processing:** The **Alerter Service** consumes messages from the `ingest_queue`. It applies a cached set of rules to each message to determine its disposition.
    *   If a message matches a rule, it is written to the **PostgreSQL** database for audit purposes. If the rule designates it as an alert, it is placed on the `alert_queue` for forwarding.
    *   If a message is unhandled, the Alerter tracks its frequency and generates a "meta-alert" if a certain threshold is breached.

4.  **Forwarding:** The **Moog Forwarder Service** consumes alerts from the `alert_queue`. It is responsible for reliably delivering these alerts to the external **Moog AIOps** platform via its webhook API. This service incorporates rate limiting and a circuit breaker to avoid overwhelming the downstream system.

5.  **Management & Auditing:**
    *   The **Web UI Service** provides a graphical interface for operators to manage alert rules, view the audit log from PostgreSQL, and monitor system metrics.
    *   The **PostgreSQL** database serves as the system of record for all processed events, providing a complete and queryable audit trail.
    *   **HashiCorp Vault** is the external dependency for managing all secrets, including API keys and database credentials.

---

## Component Architecture

Each service in MUTT is a stateless, single-threaded worker designed to be horizontally scalable.

*   **Ingestor Service (`ingestor_service.py`)**
    *   **Role:** Provides a secure, high-throughput HTTP endpoint for event ingestion.
    *   **Why it exists:** To abstract the raw data sources (`rsyslog`, `snmptrapd`) from the internal processing system, enforce a standard message format (JSON), and provide a single point of authentication and backpressure.
    *   **Scalability:** As a stateless web service, it can be scaled horizontally behind a load balancer. Multiple instances share the load of incoming HTTP requests.
    *   **Failure Mode:** If an Ingestor instance fails, the load balancer will redirect traffic to healthy instances. No data is lost as the service is stateless.

*   **Alerter Service (`alerter_service.py`)**
    *   **Role:** The "brain" of MUTT. It consumes events, applies business logic (rules), and decides what to do with them.
    *   **Why it exists:** To separate the core business logic of rule processing from the concerns of ingestion and forwarding. This allows the rules engine to be scaled and updated independently.
    *   **Scalability:** Multiple Alerter instances can run concurrently, each pulling messages from the shared `ingest_queue` using a reliable `BRPOPLPUSH` pattern. This allows for parallel processing of the event stream.
    *   **Failure Mode:** If an Alerter instance crashes mid-process, the message it was handling remains in a dedicated processing list in Redis. A "janitor" process in a new Alerter instance will recover this orphaned message, ensuring no data is lost.

*   **Moog Forwarder Service (`moog_forwarder_service.py`)**
    *   **Role:** Reliably forwards alerts to the external Moog AIOps platform.
    *   **Why it exists:** To isolate the system from the unreliability of external networks and downstream systems. It encapsulates all logic related to external communication, including rate limiting, retries with exponential backoff, and a circuit breaker.
    *   **Scalability:** Can be scaled horizontally. All instances coordinate through Redis to share a global rate limit, preventing the herd of forwarders from overwhelming the Moog API.
    *   **Failure Mode:** Similar to the Alerter, it uses the janitor pattern to recover any messages that were in-flight during a crash. If Moog is down, the circuit breaker will trip, and messages will queue up in the `alert_queue`.

*   **Web UI Service (`web_ui_service.py`)**
    *   **Role:** Provides a user interface and REST API for system management and observability.
    *   **Why it exists:** To give operators a safe and intuitive way to manage rules and view system state without requiring direct access to the database or Redis.
    *   **Scalability:** As a mostly read-only stateless service, it can be scaled horizontally.
    *   **Failure Mode:** Failures are handled by a load balancer. A crash does not impact the core event processing pipeline.

---

## Data Flow Patterns

*   **Event Ingestion Path:**
    1.  `Syslog/SNMP Source` -> `rsyslog/snmptrapd`
    2.  `rsyslog/snmptrapd` -> `Ingestor Service` (HTTP POST)
    3.  `Ingestor Service` -> `Redis:ingest_queue` (LPUSH)

*   **Alert Processing Pipeline:**
    1.  `Alerter Service` <- `Redis:ingest_queue` (BRPOPLPUSH)
    2.  `Alerter Service` processes the message.
    3.  If handled: `Alerter Service` -> `PostgreSQL:event_audit_log` (INSERT)
    4.  If alert: `Alerter Service` -> `Redis:alert_queue` (LPUSH)
    5.  `Moog Forwarder` <- `Redis:alert_queue` (BRPOPLPUSH)
    6.  `Moog Forwarder` -> `Moog AIOps Webhook` (HTTP POST)

*   **Configuration Update Propagation:**
    1.  Operator updates a rule via the `Web UI`.
    2.  `Web UI` -> `PostgreSQL:alert_rules` (UPDATE/INSERT)
    3.  `Web UI` -> `Redis PubSub Channel` (PUBLISH "cache-reload")
    4.  All `Alerter Service` instances receive the message and trigger a reload of their in-memory rule cache from PostgreSQL.

*   **Metrics Collection Flow:**
    1.  Each service exposes a `/metrics` endpoint (Prometheus format).
    2.  The `Ingestor` and `Web UI` also write summary metrics to Redis with a TTL.
    3.  A central **Prometheus** server scrapes the `/metrics` endpoints from all service instances.
    4.  **Grafana** queries Prometheus to display dashboards.

---

## Reliability Patterns

The architecture is built on several key patterns to ensure no data is lost and the system remains available.

*   **BRPOPLPUSH for Reliable Queuing:** This is the cornerstone of the system's reliability. When a worker (Alerter or Forwarder) takes a message, it uses the `BRPOPLPUSH` Redis command. This command *atomically* moves the message from the main queue to a private, per-worker "processing" list. The message is only removed from the processing list upon successful completion.
    *   **Why this matters:** If a worker crashes while processing a message, the message is not lost. It remains safely in the worker's processing list, ready to be recovered.

*   **Janitor Pattern for Crash Recovery:** On startup, every worker runs a "janitor" process. The janitor scans Redis for processing lists belonging to dead workers (identified via an expiring heartbeat key). It moves any "orphaned" messages from these dead lists back to the main queue for another worker to process.
    *   **Why this matters:** This pattern provides self-healing capabilities. The system automatically recovers from worker crashes without manual intervention, ensuring at-least-once processing.

*   **Heartbeat Mechanism:** Each worker maintains a "heartbeat" key in Redis with a short time-to-live (TTL). As long as the worker is alive, it continuously refreshes this key. The absence of a heartbeat key indicates a dead worker, which is the signal for the janitor process to begin recovery.

*   **Dead Letter Queue (DLQ) Strategy:** If a message fails processing repeatedly (e.g., it is malformed) or if an alert cannot be delivered to Moog after several retries, it is moved to a Dead Letter Queue.
    *   **Why this matters:** The DLQ prevents "poison pills" from blocking the processing pipeline. It isolates problematic messages for later inspection and manual remediation, allowing the rest of the system to continue functioning normally.

*   **Backpressure Handling:** The Ingestor service monitors the depth of the `ingest_queue`. If the queue grows beyond a configured threshold, the Ingestor will respond with an `HTTP 503 Service Unavailable` status.
    *   **Why this matters:** This pushes back on the data sources (`rsyslog`), telling them to slow down. `rsyslog` is configured to queue messages on disk and retry, thus preventing data loss even when the central system is overloaded.

---

## Scalability Architecture

The system is designed with a "shared-nothing" microservices approach to allow for simple and effective horizontal scaling.

*   **Horizontal Scaling Approach:** The primary method of scaling is to increase the number of container/pod replicas for each service. Because the services are stateless and coordinate through Redis, adding more instances directly increases the processing capacity of the system.

*   **Stateless Worker Design:** All long-term state is stored externally in Redis, PostgreSQL, or Vault. The workers (Ingestor, Alerter, Forwarder, Web UI) hold no critical state in memory, allowing them to be created or destroyed without data loss. The Alerter's rule cache is considered ephemeral and is rebuilt on startup.

*   **Bottleneck Identification and Mitigation:**
    *   **Ingestor:** CPU-bound. Scale horizontally behind a load balancer.
    - **Alerter:** CPU and Database-bound. Scale horizontally to increase parallel message processing. The ultimate bottleneck is often the write throughput of the PostgreSQL database.
    - **Moog Forwarder:** Network I/O-bound. Scale horizontally. The bottleneck is the rate limit of the downstream Moog AIOps system, which is managed by the shared rate limiter.
    - **Redis:** Can become a bottleneck at very high EPS. Can be scaled vertically or to a Redis Cluster.
    - **PostgreSQL:** Write-heavy workload can be a bottleneck. Can be mitigated with faster storage, connection pool tuning, and eventually, read replicas for the Web UI.
