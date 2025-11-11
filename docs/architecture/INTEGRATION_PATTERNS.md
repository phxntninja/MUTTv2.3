# MUTT Integration Patterns

**Version:** 1.0
**Last Updated:** 2025-11-10
**Status:** Draft
**Audience:** Architects, Engineers
**Prerequisites:** `SYSTEM_ARCHITECTURE.md`

---

## Table of Contents
1. [Inter-Service Communication](#inter-service-communication)
2. [Reliable Messaging Patterns](#reliable-messaging-patterns)
3. [Configuration Management](#configuration-management)
4. [Secret Management Integration](#secret-management-integration)
5. [Database Integration Patterns](#database-integration-patterns)
6. [External System Integration](#external-system-integration)
7. [Observability Integration](#observability-integration)

---

## Inter-Service Communication

All core inter-service communication in MUTT is asynchronous and mediated by Redis. This decouples the services, allowing them to scale and fail independently.

### Redis as Message Bus

*   **Pattern:** Redis Lists are used as point-to-point message queues. This is not a traditional message bus with topics, but rather a set of dedicated queues for passing data between specific services.
*   **Why:** This approach is simple, fast, and leverages Redis's atomic list operations for reliability. It avoids the complexity of managing a full-fledged message broker.

### Queue Naming Conventions

A strict naming convention is used for Redis keys to ensure clarity and prevent collisions.

*   **Queues:** `mutt:{queue_name}` (e.g., `mutt:ingest_queue`, `mutt:alert_queue`)
*   **Processing Lists:** `mutt:processing:{service_name}:{pod_name}` (e.g., `mutt:processing:alerter:alerter-pod-1`)
*   **Heartbeats:** `mutt:heartbeat:{service_name}:{pod_name}` (e.g., `mutt:heartbeat:alerter:alerter-pod-1`)
*   **Rate Limiting:** `mutt:rate_limit:{limiter_name}` (e.g., `mutt:rate_limit:moog`)
*   **Circuit Breakers:** `mutt:circuit:{breaker_name}:(open|failures)` (e.g., `mutt:circuit:moog:open`)

### Message Format Specifications

All messages placed on Redis queues are **JSON strings**. This provides a flexible and universally understood format.

*   **Ingest Queue Message:** A JSON object representing the event received from the source (rsyslog/snmptrapd).
    ```json
    {
      "timestamp": "2025-11-10T12:00:00Z",
      "hostname": "router-01",
      "message": "LINK-DOWN: Interface eth0",
      "syslog_severity": 3,
      "_correlation_id": "uuid-goes-here"
    }
    ```
*   **Alert Queue Message:** A JSON object formatted specifically for the Moog Forwarder, containing all information needed to create an alert.
    ```json
    {
      "api_key": "secret-key-for-moog",
      "hostname": "router-01",
      "team_assignment": "NetOps",
      "severity": "Warning",
      "message_body": "LINK-DOWN: Interface eth0",
      "raw_json": { "...original message..." },
      "_correlation_id": "uuid-goes-here"
    }
    ```

### Correlation ID Propagation

To enable distributed tracing, a **Correlation ID** is used.

1.  The **Ingestor Service** generates a UUID for each incoming request if one is not already present in the `X-Correlation-ID` header.
2.  This ID is added to the log context for all log messages related to that request.
3.  The ID is injected into the JSON message payload under the `_correlation_id` key before it is placed on the `ingest_queue`.
4.  All subsequent services (Alerter, Moog Forwarder) extract this ID from the message and use it in their own log contexts.
5.  This allows operators to trace the entire lifecycle of a single event across multiple services and log streams.

---

## Reliable Messaging Patterns

The following sequence diagram describes the reliable messaging pattern used by the Alerter and Moog Forwarder services.

```
Worker                  Redis
  │                       │
  │── BRPOPLPUSH ─────────▶│ Atomically move message from
  │  (ingest_queue ->      │ ingest_queue to processing:pod-1
  │   processing:pod-1)   │
  │◀──────────────────────│ Returns message
  │                       │
  │  Process message...   │
  │  (may crash here)     │
  │                       │
  │── LREM ───────────────▶│ On success, remove message
  │  (processing:pod-1)   │ from processing list
  │                       │
```
*Figure 2: BRPOPLPUSH Reliable Messaging Pattern*

### BRPOPLPUSH Mechanics

*   **Command:** `BRPOPLPUSH source_queue destination_list timeout`
*   **Action:** This is a blocking, atomic command. It waits for a message to appear on the `source_queue`, pops it, and immediately pushes it onto the `destination_list`.
*   **Why it's reliable:** The pop and push operations are a single atomic unit. There is no possibility of a worker taking a message off the queue and crashing before it can save its state. The message is guaranteed to be in one of the two lists at all times.

### Processing List Pattern

*   Each worker has its own private "processing list" in Redis (e.g., `mutt:processing:alerter:pod-123`).
*   When a worker successfully processes a message from its processing list, it uses the `LREM` command to remove it.
*   If the worker crashes, any in-flight messages remain in its processing list. On restart, a new worker's **Janitor Process** will detect the stale processing list (via the absence of a heartbeat) and move the orphaned messages back to the main queue.

### Retry and Backoff Strategies

*   **Internal Retries (Alerter):** If the Alerter fails to process a message due to a transient error (e.g., a temporary database connection issue), it will re-queue the message back to the `ingest_queue` with an incremented `_retry_count`. If the retry count exceeds a threshold, the message is moved to a Dead Letter Queue (`mutt:dlq:alerter`).
*   **External Retries (Moog Forwarder):** If the Moog Forwarder fails to send an alert to the Moog API due to a retryable error (e.g., a 5xx status code or a timeout), it re-queues the alert to the `alert_queue` and implements an **exponential backoff** delay before the next attempt. This prevents hammering a degraded downstream system.

### Idempotency Considerations

The system provides **at-least-once** delivery guarantees. In rare failure scenarios, it is possible for an event to be processed more than once. The downstream systems are expected to be idempotent or to handle potential duplicates gracefully. For example, Moogsoft's event correlation engine is capable of deduplicating similar events.

---

## Configuration Management

### Dynamic Config Architecture

The Alerter service relies on a set of rules that can change frequently. To avoid requiring a service restart for every rule change, a dynamic configuration pattern is used.

1.  **Source of Truth:** The PostgreSQL `alert_rules` table is the single source of truth for all rules.
2.  **In-Memory Cache:** Each Alerter instance loads all active rules into an in-memory cache on startup for maximum performance.
3.  **Cache Invalidation:** When a rule is updated (e.g., via the Web UI), the cache in each Alerter instance must be invalidated and reloaded.

### Redis PubSub for Invalidation

*   **Pattern:** A Redis Pub/Sub channel (`mutt:config:reload`) is used to notify all Alerter instances of a configuration change.
*   **Flow:**
    1.  An operator uses the **Web UI** to change a rule.
    2.  The Web UI updates the rule in the **PostgreSQL** database.
    3.  Upon successful database commit, the Web UI publishes a message (e.g., `{"reload": "rules"}`) to the `mutt:config:reload` Redis channel.
    4.  All subscribed Alerter instances receive this message and trigger their cache reload logic.

### Configuration Reload Patterns

*   **On-Demand (Pub/Sub):** As described above, this provides near-real-time updates.
*   **On-Demand (SIGHUP):** For manual intervention, sending a `SIGHUP` signal to an Alerter process will also trigger a cache reload.
*   **Periodic Refresh:** As a fallback, each Alerter also automatically reloads its cache from the database every 5 minutes. This ensures eventual consistency even if a Pub/Sub message is missed.

---

## Secret Management Integration

### Vault AppRole Authentication

*   **Pattern:** All services use Vault's **AppRole** authentication method to securely retrieve their secrets.
*   **Flow:**
    1.  On startup, the service reads a `VAULT_ROLE_ID` from its environment variables and a `VAULT_SECRET_ID` from a secure file on disk (`/etc/mutt/secrets/vault_secret_id`).
    2.  It presents these two pieces of information to Vault to authenticate.
    3.  If successful, Vault returns a short-lived Vault token with policies attached that grant access to the service's secrets.

### Token Renewal Mechanism

*   **Pattern:** The Vault token received during authentication is short-lived (e.g., 32 days). To prevent the service from failing when the token expires, each service runs a background thread dedicated to token renewal.
*   **Flow:**
    1.  The background thread wakes up periodically (e.g., every 5 minutes).
    2.  It checks the TTL of the current Vault token.
    3.  If the TTL is below a certain threshold (e.g., 1 hour), it calls Vault's `renew-self` API to extend the token's lease.
    *   **Why this matters:** This ensures the service can maintain access to secrets for its entire lifetime without manual intervention.

---

## Database Integration Patterns

### Connection Pooling Strategy

*   **Pattern:** All services that interact with PostgreSQL (`Alerter`, `Web UI`) use a **threaded connection pool** (`psycopg2.pool.ThreadedConnectionPool`).
*   **Why:** Creating a new database connection is an expensive operation. A connection pool maintains a set of open connections that can be reused by different parts of the application, significantly improving performance and reducing the load on the database. Each thread gets its own connection from the pool, ensuring thread safety.

---

## External System Integration

### Moogsoft Webhook Integration

*   **Pattern:** The Moog Forwarder service integrates with Moog AIOps via a standard webhook (HTTP POST).
*   **Payload:** The forwarder is responsible for transforming the internal alert format into the specific JSON payload required by the Moog API.
*   **Authentication:** Authentication is handled via a Bearer token (`Authorization` header), which is retrieved from Vault.

### Circuit Breaker Pattern (ADR-005)

*   **Pattern:** To prevent cascading failures when Moogsoft is down, the Moog Forwarder implements a Redis-backed **circuit breaker**.
*   **States:**
    1.  **Closed:** Normal operation. Requests are sent to Moog. A counter tracks consecutive failures.
    2.  **Open:** If the failure counter exceeds a threshold, the circuit "opens." For a configured period (e.g., 60 seconds), the forwarder will not attempt to send any requests to Moog. It will immediately re-queue alerts for a later attempt. This allows the downstream system time to recover.
    3.  **Half-Open (Implicit):** After the "open" duration expires, the circuit closes, and the next request is allowed through. If it succeeds, the failure count resets. If it fails, the circuit opens again immediately.
*   **Why this matters:** The circuit breaker prevents the system from wasting resources on requests that are guaranteed to fail, and it reduces the load on a struggling downstream system.

---

## Observability Integration

### Prometheus Metrics Patterns

*   **Exposition:** Every service exposes a `/metrics` endpoint in the Prometheus text-based format.
*   **Metric Types:** A combination of metric types are used:
    *   **Counter:** For tracking cumulative counts (e.g., `mutt_ingest_requests_total`).
    *   **Gauge:** For tracking point-in-time values (e.g., `mutt_ingest_queue_depth`).
    *   **Histogram:** For tracking the distribution of values, typically latency (e.g., `mutt_alerter_processing_latency_seconds`).
*   **Labels:** Labels are used to provide dimensions for metrics (e.g., `status="success"` or `status="fail_auth"`).

### Structured Logging Approach

*   **Format:** All log output is structured as plain text, but with a consistent format that can be easily parsed by log aggregation systems like Splunk or Fluentd.
    `timestamp - log_level - [correlation_id] - message`
*   **Correlation ID:** The inclusion of the `correlation_id` in every log message is the key to effective troubleshooting in this distributed system.
