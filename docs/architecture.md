This document addresses all architectural concerns and incorporates feedback from two expert reviews. The following changes define the v2.1 production-ready architecture.

1. High-Priority: Durability & Stability

1.1. Redis High Availability

SPOF: If Redis crashes, queues are lost.

Solution:

Persistence: Redis configured with AOF (Append Only File) persistence, appendfsync everysec. (1s max data loss).

HA (RHEL): Redis Sentinel for automatic failover. Python services connect to the Sentinel, not a static IP.

HA (OCP): A standard Redis Cluster Operator will be used.

1.2. Backpressure Handling

Issue: ingest_queue can grow unbounded.

Solution:

Queue Capping: The Ingestor will check queue depth (LLEN mutt:ingest_queue) before pushing.

Limit: A new env var MAX_INGEST_QUEUE_SIZE (e.g., 1,000,000) defines the cap.

503 Response: If the queue is full, the Ingestor returns HTTP 503 (Service Unavailable).

Rsyslog: rsyslog.conf's omhttp action will be configured with a retry queue (action.queue.type="LinkedList", action.resumeRetryCount="-1") to handle the 503 and guarantee delivery.

1.3. Message Durability Gaps (Reliable Queues)

Issue: A service crash during processing can lose a message.

Solution:

Ingestor: Sends 200 OK to rsyslog only after a successful LPUSH to Redis. A failed push returns HTTP 500, triggering an rsyslog retry.

Alerter Service (BRPOPLPUSH): This is the core of the "never lose a message" design.

Atomically Move: The service uses BRPOPLPUSH, which moves a message from ingest_queue to a pod-specific alerter_processing:<pod_name> list.

Process: The Alerter processes the message from its local list.

Delete: Only after all work is done (DB audit, push to alert_queue) does the service LREM to delete the message from its processing list.

Moog Forwarder (Retry/DLQ):

Uses the same BRPOPLPUSH pattern (from alert_queue to forwarder_processing:<pod_name>).

If Moog webhook fails (timeout, 5xx), the message is not deleted.

The service implements exponential backoff (see 3.2).

After MOOG_MAX_RETRIES, the message is moved to a moog_dead_letter_queue for manual inspection.

1.4. Janitor Logic (Alerter Startup)

Issue: Crashed Alerter pods leave orphaned alerter_processing lists.

Solution: A "janitor" function runs on every Alerter pod startup.

Heartbeat: Each running Alerter pod will SETEX mutt:heartbeat:<pod_name> 60 "alive" (a 60-second heartbeat).

Find Orphans: The janitor scans Redis for all alerter_processing:* lists.

Check Liveness: For each list (e.g., alerter_processing:pod-xyz), it checks if the corresponding heartbeat key (mutt:heartbeat:pod-xyz) exists.

Recover: If the heartbeat key is missing (meaning the pod is dead), the janitor RPOPLPUSHes all messages from the orphaned list back to the main ingest_queue for reprocessing.

1.5. Unhandled Event Counter Logic

Issue: Race conditions and no expiry on unhandled counters.

Solution:

TTL: When INCR is called on a counter, an EXPIRE (e.g., 3600s) is also set.

Atomic Check: Logic will use a Redis MULTI/EXEC transaction or LUA script for an atomic check-and-set.

Deduplication: When the threshold is met, the key is RENAMEd (e.g., to mutt:unhandled:triggered:...) to prevent duplicate meta-alerts during the expiry window.

1.6. PostgreSQL High Availability

Issue: Postgres is a SPOF. Alerter cache will become stale or fail to load.

Solution:

HA (RHEL): Use streaming replication with an HA manager like Patroni or pg_auto_failover.

HA (OCP): Use a production-grade Postgres operator (e.g., Crunchy Data, Zalando).

Alerter Behavior:

On startup, if the DB is down, the Alerter will fail to load its cache and will exit/crash-loop (this is good behavior, as it cannot function).

During runtime (for cache refresh), if the DB is down, the Alerter will log the error but continue using its stale cache, ensuring events are still processed. It will retry the cache refresh on its next 5-minute interval.

1.7. Error Handling & Malformed Input

Issue: Malformed JSON from rsyslog could poison the queue.

Solution (Ingestor):

try...except JSONDecodeError: If the Ingestor receives invalid JSON, it will log the error and return HTTP 400 (Bad Request). rsyslog will not retry a 4xx error, preventing the bad message from re-queueing.

try...except RedisError: If Redis is down, the Ingestor returns HTTP 503, triggering an rsyslog retry.

2. Medium-Priority: Performance, Security, Observability

2.1. Rule Matching & DB Performance

Issue: Querying the DB for every message is a bottleneck.

Solution:

Caching: On startup, the Alerter Service loads alert_rules, development_hosts, and device_teams into an in-memory Python dictionary for <1ms lookups.

Refresh: The cache is refreshed every 5 minutes and can be triggered by a SIGHUP signal.

Rule Logic: The alert_rules table will be modified:

ADD COLUMN priority INT NOT NULL DEFAULT 100: Lower number wins.

ADD COLUMN match_type VARCHAR(20) NOT NULL DEFAULT 'contains': (enum: contains, regex, oid_prefix).

Algorithm: The Alerter will find all matching rules in the cache and select the one with the lowest priority value.

Connection Pooling: All DB writes (to event_audit_log) will use psycopg2.pool.

2.2. Observability

Issue: Only ingestion metrics are defined.

Solution: All services (Ingestor, Alerter, Moog Forwarder, WebUI) will expose a /metrics endpoint for Prometheus.

New Metrics:

mutt_ingest_queue_depth (Gauge)

mutt_alert_queue_depth (Gauge)

mutt_moog_dlq_depth (Gauge)

mutt_alerter_processing_latency_ms (Histogram)

mutt_moog_requests_total{status="success|fail|retry"} (Counter)

mutt_db_write_latency_ms (Histogram)

mutt_rule_cache_load_success (Gauge)

mutt_unhandled_events_total (Counter)

2.3. Security: Secrets Management

Issue: Passwords in plain text in mutt.env.

Solution:

Primary Store: All secrets ( REDIS_PASS, DB_PASS, INGEST_API_KEY, MOOG_API_KEY) will be stored in HashiCorp Vault.

RHEL: Services will authenticate to Vault using the AppRole method. The VAULT_ROLE_ID and VAULT_SECRET_ID will be the only secrets stored in a secure file on the host.

OCP: Services will use the Kubernetes Auth Method to authenticate to Vault via their ServiceAccount.

Code: All Python services will be updated to use the hvac library to fetch their secrets from Vault at startup.

2.4. Security: Encryption in Transit (TLS)

Issue: Internal traffic is unencrypted.

Solution:

Rsyslog -> Ingestor: omhttp will be configured with usehttps="on" and ca.file to use TLS 1.2+. The Ingestor (Gunicorn) will be configured with a key and cert.

Services -> Redis: Python services will connect to Redis using redis.Redis(..., ssl=True, ssl_cert_reqs='required').

Services -> PostgreSQL: Python services will connect to Postgres using sslmode='require'.

3. Low-Priority: Operational Maturity

3.1. Database Growth

Issue: event_audit_log will grow indefinitely.

Solution: The event_audit_log table will be created using PostgreSQL 12+ native partitioning, partitioned by RANGE(event_timestamp). A separate monthly cron script will create new partitions and drop old ones based on an AUDIT_RETENTION_MONTHS config.

3.2. Rate Limiting Specification

Issue: Local rate limiting fails when Moog Forwarder is scaled.

Solution: A Redis-based shared rate limit will be used.

Config: MOOG_RATE_LIMIT (e.g., "50"), MOOG_RATE_PERIOD (e.g., "1" for seconds).

Implementation: Before sending, the Moog Forwarder will run a Redis transaction to INCR a sliding-window key and check if the count exceeds the limit. If it does, the message is not processed and the pod sleeps, retrying on the next loop. This ensures all pods share a single global rate limit.

Retry Config: MOOG_RETRY_BASE_DELAY (e.g., 1s), MOOG_RETRY_MAX_DELAY (e.g., 60s), MOOG_MAX_RETRIES (e.g., 5).

4.0. Scaling Strategy

Ingestor Service: Horizontally Scalable. It is stateless. Can be scaled to N pods/processes behind a load balancer.

Web UI Service: Horizontally Scalable. It is read-only and stateless.

Alerter Service: Horizontally Scalable. The BRPOPLPUSH pattern on a Redis List is atomic and acts as a load distributor. Multiple pods can safely pull from the ingest_queue without race conditions.

Moog Forwarder: Horizontally Scalable. The Redis-based shared rate limiter (3.2) ensures all pods coordinate to respect the total rate limit sent to Moog.

5.0. Testing Strategy

Unit Tests (pytest): (e.g., test_alerter_unit.py) To test pure logic, such as rule matching, priority selection, and unhandled counter logic, using mock objects for Redis/DB.

Integration Tests (docker-compose): A docker-compose.test.yml will spin up the full stack (Python services, Redis, Postgres) to test the interactions between components.

End-to-End Tests: (e.g., e2e_test_runner.py) To send real UDP packets to the rsyslog service and query the event_audit_log for the expected result.

Chaos Tests: Manually killing the Redis or Alerter pod during a load test to verify the janitor and reliable queueing patterns work as designed.

Load Tests: Using a tool to flood rsyslog to verify backpressure (503s) and find the system's maximum processing EPS.

6.0. Deployment Specifications

RHEL:

PostgreSQL and Redis (with Sentinel) will be installed via dnf and managed as systemd services.

Vault will be run as a separate HA cluster.

Python services will run as systemd services, as previously defined.

OCP:

PostgreSQL, Redis, and Vault will be deployed via their respective HA Operators.

PersistentVolumes will be used for all database/Vault storage.

Python services will be deployed as Deployments, using Kubernetes Secrets (to store Vault auth info) and ConfigMaps (for non-secret config).