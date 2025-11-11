# MUTT v2.5 - Complete Rebuild Guide

**Purpose:** Step-by-step instructions to rebuild MUTT v2.5 from scratch in any environment
**Audience:** Developers, AI assistants (like Copilot), architects rebuilding the system
**Scope:** Complete specifications WITHOUT actual code - use this to recreate the implementation
**Version:** 2.5 (Production-Ready)

---

## Table of Contents

1. [How to Use This Guide](#how-to-use-this-guide)
2. [Prerequisites & Environment Setup](#prerequisites--environment-setup)
3. [Phase 0: Foundation & Architecture](#phase-0-foundation--architecture)
4. [Phase 1: Database Layer](#phase-1-database-layer)
5. [Phase 2: Core Services](#phase-2-core-services)
6. [Phase 3: Infrastructure Services](#phase-3-infrastructure-services)
7. [Phase 4: Integration & Reliability](#phase-4-integration--reliability)
8. [Phase 5: Observability](#phase-5-observability)
9. [Phase 6: API & Compliance](#phase-6-api--compliance)
10. [Phase 7: Testing](#phase-7-testing)
11. [Phase 8: Deployment](#phase-8-deployment)
12. [Phase 9: Documentation](#phase-9-documentation)
13. [Validation Checklist](#validation-checklist)
14. [Reference Documents](#reference-documents)

---

## How to Use This Guide

### For AI Assistants (Copilot, Claude, etc.)

**Read these documents IN ORDER before coding:**

1. **Architecture Foundation** (READ FIRST)
   - `docs/architecture/SYSTEM_ARCHITECTURE.md` - Understand the system
   - `docs/architecture/DESIGN_RATIONALE.md` - Understand WHY decisions were made
   - `docs/adr/` - All 6 Architecture Decision Records

2. **Technical Specifications**
   - `docs/api/REFERENCE.md` - API specifications
   - `docs/db/SCHEMA.md` - Database schema
   - `docs/code/MODULES.md` - Code organization

3. **This Guide** (YOU ARE HERE)
   - Follow phase-by-phase implementation instructions

4. **Validation**
   - `docs/operations/` - How it should operate
   - Test specifications in each phase below

### For Human Developers

Follow the same reading order, then implement each phase according to the specifications below. Each phase includes:
- ✅ What to build
- 📋 Specifications and requirements
- 🧪 How to test it
- 📚 Reference documentation

### Rebuild Strategy

**DO NOT:**
- Copy existing code
- Skip phases
- Implement without reading architecture docs first

**DO:**
- Read architecture documents thoroughly
- Understand the "why" before the "how"
- Follow the phase order
- Test each phase before moving to next
- Reference ADRs for design decisions

---

## Prerequisites & Environment Setup

### Required Infrastructure

Before starting any code:

**1. Redis 6.0+**
- Configuration: AOF persistence enabled (`appendfsync everysec`)
- TLS support (optional but recommended)
- Sentinel/Cluster for HA (production)

**2. PostgreSQL 14+**
- Partitioning support required
- TLS support (optional but recommended)
- Streaming replication for HA (production)

**3. HashiCorp Vault 1.8+**
- KV v2 secrets engine enabled
- AppRole authentication configured
- Token TTL: 1h, Max TTL: 4h

**4. Prometheus (for monitoring)**
- Version 2.0+
- TSDB retention: 15 days minimum

**5. Python Environment**
- Python 3.10 or 3.12 (tested versions)
- Virtual environment recommended

### Required Python Packages

**Core Dependencies:**
```
flask>=2.0
gunicorn>=20.1
redis>=4.0
psycopg2-binary>=2.9
hvac>=1.0
prometheus-client>=0.12
prometheus-flask-exporter>=0.20
requests>=2.28
```

**Observability (Optional):**
```
opentelemetry-api>=1.24
opentelemetry-sdk>=1.24
opentelemetry-exporter-otlp-proto-grpc>=1.24
opentelemetry-instrumentation-flask
opentelemetry-instrumentation-requests
opentelemetry-instrumentation-redis
opentelemetry-instrumentation-psycopg2
```

**Testing:**
```
pytest>=7.0
pytest-cov>=4.0
pytest-mock>=3.10
```

**Development:**
```
black>=23.0
ruff>=0.1.0
mypy>=1.0
```

### Project Structure

Create this directory structure:

```
mutt/
├── services/                    # All microservices
│   ├── ingestor_service.py
│   ├── alerter_service.py
│   ├── moog_forwarder_service.py
│   ├── web_ui_service.py
│   ├── remediation_service.py
│   ├── audit_logger.py          # Shared utility
│   ├── dynamic_config.py        # Shared utility
│   ├── logging_utils.py         # Shared utility
│   ├── tracing_utils.py         # Shared utility
│   ├── redis_connector.py       # Shared utility
│   ├── postgres_connector.py    # Shared utility
│   └── rate_limiter.py          # Shared utility
├── database/
│   ├── mutt_schema_v2.1.sql
│   ├── config_audit_schema.sql
│   └── partitioned_event_audit_log.sql
├── scripts/
│   ├── create_monthly_partitions.py
│   ├── archive_old_events.py
│   ├── init_dynamic_config.py
│   └── muttdev.py
├── tests/
│   ├── test_ingestor.py
│   ├── test_alerter.py
│   ├── test_moog_forwarder.py
│   ├── test_webui.py
│   ├── test_remediation.py
│   ├── test_audit_logger.py
│   ├── test_dynamic_config.py
│   └── test_integration.py
├── systemd/
│   ├── mutt-ingestor.service
│   ├── mutt-alerter.service
│   ├── mutt-moog-forwarder.service
│   ├── mutt-webui.service
│   └── mutt-remediation.service
├── k8s/
│   ├── ingestor-deployment.yaml
│   ├── alerter-deployment.yaml
│   ├── moog-forwarder-deployment.yaml
│   ├── webui-deployment.yaml
│   └── remediation-deployment.yaml
├── docs/
│   └── (all documentation)
├── .env.template
├── requirements.txt
├── setup.py
└── README.md
```

---

## Phase 0: Foundation & Architecture

### 0.1 Read Architecture Documentation

**Required Reading (in order):**

1. **`docs/architecture/SYSTEM_ARCHITECTURE.md`** (18-20 pages)
   - Understand the 5 microservices
   - Understand the data flow: Ingestor → Alerter → Moog Forwarder
   - Understand the BRPOPLPUSH pattern for reliable queuing
   - Understand the Janitor pattern for crash recovery

2. **`docs/architecture/DESIGN_RATIONALE.md`** (16-18 pages)
   - WHY Redis instead of Kafka
   - WHY single-threaded workers
   - WHY Vault for secrets
   - WHY PostgreSQL for audit logs

3. **All ADRs in `docs/adr/`:**
   - `ADR-001-redis-vs-kafka.md` - Message queue decision
   - `ADR-002-vault-vs-k8s-secrets.md` - Secrets management
   - `ADR-003-single-threaded-workers.md` - Worker architecture
   - `ADR-004-postgres-for-audit-logs.md` - Audit storage
   - `ADR-005-circuit-breaker-moog-forwarder.md` - Reliability pattern
   - `ADR-006-api-versioning.md` - API strategy

### 0.2 Understand Core Patterns

**Pattern 1: BRPOPLPUSH Reliable Queuing**
- **Purpose:** Ensure no message loss on crashes
- **How:** Messages atomically moved from queue to processing list
- **Recovery:** Janitor recovers orphaned messages on startup
- **Redis Commands:**
  - `BRPOPLPUSH source processing timeout` - Atomic pop and push
  - `LPUSH queue message` - Add to queue
  - `LREM processing -1 message` - Remove after processing
  - `LPUSH dlq message` - Move to dead letter queue on poison

**Pattern 2: Janitor Recovery**
- **Purpose:** Recover messages left in processing lists from crashed workers
- **When:** On service startup
- **How:**
  1. Scan for processing lists: `mutt:processing:alerter:*`
  2. Check heartbeat: `GET mutt:heartbeat:alerter:pod-xyz`
  3. If heartbeat expired, recover: `RPOPLPUSH processing source`
- **Heartbeat Refresh:** Every 10 seconds

**Pattern 3: Circuit Breaker**
- **Purpose:** Prevent cascading failures to external systems
- **States:** CLOSED (normal) → OPEN (failing) → HALF_OPEN (testing)
- **Implementation:** Redis-based shared state
- **Keys:**
  - `mutt:circuit:moog:state` - Current state
  - `mutt:circuit:moog:failures` - Failure count
  - `mutt:circuit:moog:opened_at` - When circuit opened

**Pattern 4: Backpressure Handling**
- **Purpose:** Prevent service overload
- **Mechanism:** Queue depth monitoring with shedding
- **Modes:**
  - `dlq` - Move excess to dead letter queue
  - `defer` - Sleep to allow downstream processing
- **Thresholds:** Configurable via dynamic config

**Pattern 5: Dynamic Configuration**
- **Purpose:** Runtime configuration changes without restart
- **Storage:** Redis with PubSub invalidation
- **Cache:** 5-second local cache for performance
- **Callbacks:** Register functions to execute on config change

### 0.3 Study Data Flow

**Complete Event Journey:**

```
1. INGESTION
   rsyslog/SNMP → HTTP POST → Ingestor Service (port 8080)
   ↓
   Validates: timestamp, message, hostname (required fields)
   Enriches: correlation_id, ingestion_timestamp
   ↓
   LPUSH mutt:ingest_queue

2. PROCESSING
   BRPOPLPUSH mutt:ingest_queue → mutt:processing:alerter:{pod_name}
   ↓
   Alerter Service reads from processing list
   ↓
   Matches against rules (in-memory cache, refreshed every 5 min)
   ↓
   If matched:
     - Enriches with rule_id, team_assignment, prod_handling
     - LPUSH mutt:alert_queue
     - LREM mutt:processing:alerter:{pod_name}
   ↓
   If unmatched:
     - Increment counter: INCR mutt:unhandled:{source_pattern}
     - If counter > threshold, create meta-alert
     - LREM mutt:processing:alerter:{pod_name}
   ↓
   If poison (exception):
     - Increment retry_count
     - If retry_count > max_retries:
       - LPUSH mutt:dlq:alerter
     - Else:
       - RPUSH mutt:ingest_queue (retry)

3. FORWARDING
   BRPOPLPUSH mutt:alert_queue → mutt:processing:moog:{pod_name}
   ↓
   Moog Forwarder Service reads from processing list
   ↓
   Check rate limit (shared Redis sliding window)
   ↓
   If rate limit OK:
     - Check circuit breaker state
     - POST to Moogsoft webhook
     - If success:
       - LREM mutt:processing:moog:{pod_name}
     - If 4xx client error:
       - LPUSH mutt:dlq:moog (permanent failure)
     - If 5xx or timeout:
       - Increment retry_count
       - If retry_count > max_retries:
         - LPUSH mutt:dlq:moog
       - Else:
         - Exponential backoff sleep
         - RPUSH mutt:alert_queue (retry)
   ↓
   If rate limited:
     - Sleep briefly
     - RPUSH mutt:alert_queue (defer)

4. REMEDIATION (Self-Healing)
   Periodically (every 60s by default):
   ↓
   Scan DLQs: mutt:dlq:alerter, mutt:dlq:moog
   ↓
   For each message:
     - Check retry history in Redis
     - If retry_count < max_remediation_retries:
       - Exponential backoff wait
       - LPUSH back to original queue
     - Else:
       - LPUSH mutt:poison:permanent (poison pill)
```

### 0.4 Understand Service Responsibilities

**Ingestor Service (Port 8080)**
- **Role:** HTTP ingestion endpoint
- **Responsibilities:**
  - Validate incoming events (required fields)
  - Enrich with correlation_id
  - Backpressure: Check queue depth, return 503 if full
  - Authentication: Validate API key (constant-time comparison)
  - Metrics: Track events/sec (1m, 1h, 24h windows)
  - Push to Redis: `LPUSH mutt:ingest_queue`
- **Scaling:** Add instances behind load balancer at 10,000 EPS per instance
- **Endpoints:**
  - `POST /api/v2/ingest` - Ingest events
  - `GET /health` - Health check
  - `GET /metrics` - Prometheus metrics

**Alerter Service (Ports 8081 metrics, 8082 health)**
- **Role:** Core event processing ("The Brain")
- **Responsibilities:**
  - BRPOPLPUSH from ingest_queue
  - Maintain in-memory rule cache (5min refresh + SIGHUP)
  - Match events against rules (priority-based)
  - Detect production vs. development environments
  - Handle unmatched events (threshold-based meta-alerts)
  - Queue depth monitoring for backpressure
  - Janitor recovery on startup
  - Poison message detection and DLQ handling
- **Scaling:** Scale when queue depth > 5,000 sustained
- **Cache Invalidation:** SIGHUP signal or dynamic config change

**Moog Forwarder Service (Ports 8083 metrics, 8084 health)**
- **Role:** External system integration with reliability
- **Responsibilities:**
  - BRPOPLPUSH from alert_queue
  - Shared rate limiting (Redis sliding window Lua script)
  - Circuit breaker for Moogsoft endpoint
  - Exponential backoff retry (1s → 2s → 4s → 8s → 60s max)
  - Smart retry: 5xx/timeout retry, 4xx DLQ
  - Janitor recovery on startup
  - Poison message detection
- **Scaling:** Scale with rate limit exhaustion
- **Rate Limit:** Shared across all instances via Redis

**Web UI Service (Port 8090)**
- **Role:** Management interface and dashboard
- **Responsibilities:**
  - CRUD API for alert rules
  - Real-time EPS dashboard (Chart.js)
  - Audit log viewer (paginated)
  - Development host management
  - Device team management
  - SLO endpoint (Prometheus queries)
  - Configuration management API
  - Configuration audit viewer
- **Scaling:** Scale at 100 concurrent users per instance
- **Caching:** 5-second cache for metrics queries

**Remediation Service (Ports 8086 metrics, 8087 health)**
- **Role:** Self-healing and DLQ recovery
- **Responsibilities:**
  - Periodic DLQ scanning (configurable interval)
  - Exponential backoff retry for DLQ messages
  - Poison pill detection (max retry limit)
  - Replay to original queues
  - Metrics on replay success/failure
- **Scaling:** Typically single instance (no parallelism needed)
- **Configuration:** Scan interval, max retries, backoff base

---

## Phase 1: Database Layer

### 1.1 Main Schema - PostgreSQL

**Reference:** `docs/db/SCHEMA.md`

**Create these tables in PostgreSQL:**

#### Table: `alert_rules`
```sql
-- Purpose: Store alert routing rules
-- Cached: Yes (5-minute refresh in Alerter service)
-- Indexes: On is_active, priority

Columns:
- id: SERIAL PRIMARY KEY
- match_string: TEXT (nullable) - String to match in message
- trap_oid: TEXT (nullable) - SNMP trap OID prefix
- syslog_severity: INTEGER (nullable) - Syslog severity level
- match_type: TEXT NOT NULL - 'contains', 'regex', 'oid_prefix'
- priority: INTEGER NOT NULL DEFAULT 100 - Higher priority matched first
- prod_handling: TEXT NOT NULL - 'Page_and_ticket', 'Ticket_only', 'Email_only', 'Log_only'
- dev_handling: TEXT NOT NULL - 'Ticket_only', 'Email_only', 'Log_only', 'Suppress'
- team_assignment: TEXT NOT NULL - Team name (e.g., 'NETO', 'UNIX', 'DBA')
- is_active: BOOLEAN NOT NULL DEFAULT true
- created_at: TIMESTAMP DEFAULT NOW()
- updated_at: TIMESTAMP DEFAULT NOW()

Constraints:
- At least one of (match_string, trap_oid, syslog_severity) must be non-null
- match_type must match the populated field
- priority must be between 1 and 1000

Indexes:
- CREATE INDEX idx_alert_rules_active ON alert_rules(is_active) WHERE is_active = true;
- CREATE INDEX idx_alert_rules_priority ON alert_rules(priority DESC);
```

#### Table: `development_hosts`
```sql
-- Purpose: Identify development/test hosts (different handling)
-- Cached: Yes (5-minute refresh in Alerter service)

Columns:
- id: SERIAL PRIMARY KEY
- hostname: TEXT NOT NULL UNIQUE
- description: TEXT
- added_at: TIMESTAMP DEFAULT NOW()

Indexes:
- CREATE UNIQUE INDEX idx_dev_hosts_hostname ON development_hosts(hostname);
```

#### Table: `device_teams`
```sql
-- Purpose: Map devices to teams (override rule-based assignment)
-- Cached: Yes (5-minute refresh in Alerter service)

Columns:
- id: SERIAL PRIMARY KEY
- hostname: TEXT NOT NULL UNIQUE
- team_assignment: TEXT NOT NULL
- updated_at: TIMESTAMP DEFAULT NOW()

Indexes:
- CREATE UNIQUE INDEX idx_device_teams_hostname ON device_teams(hostname);
```

#### Table: `event_audit_log`
```sql
-- Purpose: Audit trail for processed events
-- Partitioning: Monthly partitions (created automatically)
-- Retention: 90 days active + 7-year archive

Columns:
- id: BIGSERIAL PRIMARY KEY
- event_timestamp: TIMESTAMP NOT NULL
- hostname: TEXT NOT NULL
- message: TEXT NOT NULL
- source: TEXT - 'syslog' or 'snmp'
- syslog_severity: INTEGER
- trap_oid: TEXT
- rule_id: INTEGER - References alert_rules(id)
- team_assignment: TEXT
- handling: TEXT - prod_handling or dev_handling
- correlation_id: UUID NOT NULL
- created_at: TIMESTAMP DEFAULT NOW()

Partitioning:
- Partitioned by RANGE on event_timestamp (monthly)
- Function to create partitions: create_monthly_partition(date)
- Automated via cron: scripts/create_monthly_partitions.py

Indexes (on each partition):
- CREATE INDEX idx_event_audit_hostname ON event_audit_log_{YYYYMM}(hostname);
- CREATE INDEX idx_event_audit_timestamp ON event_audit_log_{YYYYMM}(event_timestamp DESC);
- CREATE INDEX idx_event_audit_correlation ON event_audit_log_{YYYYMM}(correlation_id);
```

#### Table: `config_audit_log`
```sql
-- Purpose: Audit trail for all configuration changes
-- Compliance: SOX, GDPR

Columns:
- id: BIGSERIAL PRIMARY KEY
- changed_at: TIMESTAMP NOT NULL DEFAULT NOW()
- changed_by: TEXT NOT NULL - User or service name
- operation: TEXT NOT NULL - 'CREATE', 'UPDATE', 'DELETE'
- table_name: TEXT NOT NULL - Which table/config was changed
- record_id: INTEGER - ID of changed record
- old_values: JSONB - Previous values
- new_values: JSONB - New values
- reason: TEXT - Change justification
- correlation_id: UUID - Request correlation

Indexes:
- CREATE INDEX idx_config_audit_timestamp ON config_audit_log(changed_at DESC);
- CREATE INDEX idx_config_audit_table ON config_audit_log(table_name);
- CREATE INDEX idx_config_audit_operation ON config_audit_log(operation);
- CREATE INDEX idx_config_audit_user ON config_audit_log(changed_by);
- CREATE INDEX idx_config_audit_record ON config_audit_log(table_name, record_id);
- CREATE INDEX idx_config_audit_correlation ON config_audit_log(correlation_id);
```

### 1.2 Database Functions

**Create these PostgreSQL functions:**

#### Function: `create_monthly_partition`
```sql
-- Purpose: Automatically create monthly partitions for event_audit_log
-- Parameters: partition_date DATE
-- Returns: TEXT (partition name or error message)

Logic:
1. Calculate partition name: event_audit_log_{YYYYMM}
2. Calculate partition bounds: first day of month to first day of next month
3. Check if partition already exists
4. If not exists:
   a. CREATE TABLE event_audit_log_{YYYYMM} PARTITION OF event_audit_log
      FOR VALUES FROM (start_date) TO (end_date)
   b. Create indexes on new partition
5. Return partition name

Called by:
- Manual: SELECT create_monthly_partition('2025-11-01');
- Automated: scripts/create_monthly_partitions.py (daily cron)
```

#### Function: `update_updated_at`
```sql
-- Purpose: Trigger function to auto-update updated_at columns
-- Returns: TRIGGER

Logic:
1. Set NEW.updated_at = NOW()
2. Return NEW

Usage:
CREATE TRIGGER update_alert_rules_updated_at
  BEFORE UPDATE ON alert_rules
  FOR EACH ROW EXECUTE FUNCTION update_updated_at();
```

### 1.3 Initial Data

**Seed the database with:**

1. **Default Rule** (catch-all)
   ```sql
   INSERT INTO alert_rules (match_string, match_type, priority, prod_handling, dev_handling, team_assignment)
   VALUES (null, 'contains', 1, 'Log_only', 'Suppress', 'NETO');
   ```

2. **Example Rules**
   ```sql
   -- Critical alerts
   INSERT INTO alert_rules (match_string, match_type, priority, prod_handling, dev_handling, team_assignment)
   VALUES ('CRITICAL', 'contains', 900, 'Page_and_ticket', 'Ticket_only', 'NETO');

   -- Network issues
   INSERT INTO alert_rules (match_string, match_type, priority, prod_handling, dev_handling, team_assignment)
   VALUES ('Interface.*down', 'regex', 800, 'Page_and_ticket', 'Email_only', 'NETO');

   -- Disk space
   INSERT INTO alert_rules (match_string, match_type, priority, prod_handling, dev_handling, team_assignment)
   VALUES ('disk.*full', 'regex', 700, 'Ticket_only', 'Log_only', 'UNIX');
   ```

### 1.4 Test Database Setup

**Validation Checklist:**

```sql
-- Test 1: Verify tables created
SELECT table_name FROM information_schema.tables
WHERE table_schema = 'public'
ORDER BY table_name;
-- Expected: alert_rules, config_audit_log, development_hosts, device_teams, event_audit_log

-- Test 2: Verify indexes
SELECT tablename, indexname FROM pg_indexes
WHERE schemaname = 'public'
ORDER BY tablename, indexname;
-- Expected: All indexes from above

-- Test 3: Test partition creation
SELECT create_monthly_partition('2025-11-01');
SELECT create_monthly_partition('2025-12-01');
-- Expected: event_audit_log_202511, event_audit_log_202512

-- Test 4: Verify partitions
SELECT parent.relname AS parent, child.relname AS child
FROM pg_inherits
JOIN pg_class parent ON pg_inherits.inhparent = parent.oid
JOIN pg_class child ON pg_inherits.inhrelid = child.oid
WHERE parent.relname = 'event_audit_log';
-- Expected: 2 partitions

-- Test 5: Test insert into partitioned table
INSERT INTO event_audit_log (event_timestamp, hostname, message, correlation_id)
VALUES ('2025-11-10 12:00:00', 'test-host', 'Test message', gen_random_uuid());
-- Expected: Success (1 row inserted)

-- Test 6: Verify partition routing
SELECT tableoid::regclass, * FROM event_audit_log WHERE hostname = 'test-host';
-- Expected: Shows partition name (event_audit_log_202511)
```

---

## Phase 2: Core Services

### 2.1 Shared Utilities (Build First)

These utilities are used by all services. Build them before the services.

#### Utility 1: `services/audit_logger.py`

**Purpose:** Centralized audit logging for configuration changes

**Specifications:**

```python
Class: AuditLogger

Methods:
1. log_config_change(
     conn: psycopg2.connection,
     changed_by: str,
     operation: str,  # 'CREATE', 'UPDATE', 'DELETE'
     table_name: str,
     record_id: int,
     old_values: dict,
     new_values: dict,
     reason: str = None,
     correlation_id: str = None
   ) -> None

   Logic:
   - Serialize old_values and new_values to JSONB
   - Insert into config_audit_log table
   - Commit transaction
   - Log success/failure

2. get_audit_history(
     conn: psycopg2.connection,
     table_name: str = None,
     operation: str = None,
     changed_by: str = None,
     start_date: str = None,
     end_date: str = None,
     limit: int = 50,
     offset: int = 0
   ) -> List[dict]

   Logic:
   - Build dynamic WHERE clause based on filters
   - Query config_audit_log with pagination
   - Return list of audit records as dictionaries
```

**Error Handling:**
- Database connection errors → Log and raise
- Serialization errors → Log and raise
- Invalid parameters → Validate and raise ValueError

**Test Cases:**
- Log CREATE operation
- Log UPDATE operation with old/new values
- Log DELETE operation
- Query with filters
- Pagination
- Empty results

#### Utility 2: `services/dynamic_config.py`

**Purpose:** Runtime configuration management with Redis

**Specifications:**

```python
Class: DynamicConfig

Constructor:
__init__(redis_client, prefix="mutt:config", cache_ttl=5)
  - redis_client: Redis connection
  - prefix: Redis key prefix
  - cache_ttl: Local cache TTL in seconds
  - _cache: Dictionary for local caching
  - _last_fetch: Timestamps for cache invalidation
  - _callbacks: Dictionary of registered callbacks
  - _watcher_thread: PubSub listener thread
  - _watcher_running: Boolean flag

Methods:
1. get(key: str, default=None) -> str
   Logic:
   - Check local cache (if < cache_ttl seconds old)
   - If cached, return cached value
   - Else: GET {prefix}:{key} from Redis
   - Update cache
   - Return value or default

2. set(key: str, value: str, notify: bool = True) -> None
   Logic:
   - SET {prefix}:{key} value in Redis
   - Invalidate local cache for key
   - If notify: PUBLISH {prefix}:updates key

3. delete(key: str) -> None
   Logic:
   - DEL {prefix}:{key} from Redis
   - Invalidate local cache for key
   - PUBLISH {prefix}:updates key

4. get_all() -> dict
   Logic:
   - KEYS {prefix}:* (scan for all config keys)
   - GET each key
   - Return as dictionary

5. register_callback(key: str, callback: Callable[[str, str], None]) -> None
   Logic:
   - Store callback in _callbacks[key]
   - Callback signature: callback(key, new_value)

6. start_watcher() -> None
   Logic:
   - Start PubSub listener thread
   - SUBSCRIBE to {prefix}:updates
   - On message received:
     a. Parse key from message
     b. GET new value from Redis
     c. Update local cache
     d. Execute registered callbacks for key
   - Set _watcher_running = True

7. stop_watcher() -> None
   Logic:
   - Stop PubSub listener thread
   - UNSUBSCRIBE from {prefix}:updates
   - Set _watcher_running = False
```

**Thread Safety:** Use threading.Lock for cache access

**Error Handling:**
- Redis connection errors → Log and use cached value
- PubSub errors → Log and continue
- Callback exceptions → Log but don't crash

**Test Cases:**
- Get with default
- Get cached value (< TTL)
- Get fresh value (> TTL)
- Set with notification
- Set without notification
- Delete key
- Get all keys
- Register callback
- Callback execution on change
- Cache invalidation
- PubSub propagation

#### Utility 3: `services/redis_connector.py`

**Purpose:** Redis connection with dual-password fallback for zero-downtime rotation

**Specifications:**

```python
Function: get_redis_connection(
  host: str,
  port: int,
  password_current: str,
  password_next: str = None,
  db: int = 0,
  tls_enabled: bool = False,
  ca_cert_path: str = None,
  max_connections: int = 20
) -> redis.Redis

Logic:
1. Try connecting with password_current
2. If AUTH fails and password_next exists:
   - Try connecting with password_next
   - Log successful fallback
3. If both fail:
   - Raise connection error
4. Return connection pool

Parameters from Vault:
- REDIS_PASS_CURRENT (primary password)
- REDIS_PASS_NEXT (during rotation)
```

**Test Cases:**
- Connect with current password
- Fallback to next password
- Both passwords fail
- TLS connection
- Connection pooling

#### Utility 4: `services/postgres_connector.py`

**Purpose:** PostgreSQL connection with dual-password fallback

**Specifications:**

```python
Function: get_postgres_connection(
  host: str,
  port: int,
  database: str,
  user: str,
  password_current: str,
  password_next: str = None,
  tls_enabled: bool = False,
  ca_cert_path: str = None,
  min_conn: int = 2,
  max_conn: int = 10
) -> psycopg2.pool.SimpleConnectionPool

Logic:
1. Try creating connection pool with password_current
2. If AUTH fails and password_next exists:
   - Try with password_next
   - Log successful fallback
3. If both fail:
   - Raise connection error
4. Return connection pool

Parameters from Vault:
- DB_PASS_CURRENT (primary password)
- DB_PASS_NEXT (during rotation)
```

**Test Cases:**
- Connect with current password
- Fallback to next password
- Both passwords fail
- TLS connection
- Connection pooling

#### Utility 5: `services/rate_limiter.py`

**Purpose:** Shared rate limiting using Redis sliding window

**Specifications:**

```python
Class: RedisSlidingWindowRateLimiter

Constructor:
__init__(redis_client, key_prefix: str, max_requests: int, window_seconds: int)

Methods:
1. is_allowed(identifier: str = "global") -> bool
   Logic:
   - Use Redis Lua script for atomic operation
   - Key: {key_prefix}:{identifier}
   - ZREMRANGEBYSCORE to remove old entries (outside window)
   - ZCARD to count current entries
   - If count < max_requests:
     - ZADD current timestamp
     - EXPIRE window_seconds
     - Return True
   - Else:
     - Return False

Lua Script:
```lua
local key = KEYS[1]
local now = tonumber(ARGV[1])
local window = tonumber(ARGV[2])
local limit = tonumber(ARGV[3])

-- Remove old entries
redis.call('ZREMRANGEBYSCORE', key, 0, now - window)

-- Count current
local current = redis.call('ZCARD', key)

-- Check limit
if current < limit then
  redis.call('ZADD', key, now, now)
  redis.call('EXPIRE', key, window)
  return 1
else
  return 0
end
```

**Test Cases:**
- First request allowed
- Within limit allowed
- Exceed limit blocked
- Old entries removed
- Multiple identifiers independent

#### Utility 6: `services/logging_utils.py`

**Purpose:** Structured JSON logging (opt-in)

**Specifications:**

```python
Function: setup_json_logging(
  service_name: str,
  version: str,
  level: str = "INFO"
) -> None

Logic:
1. Check environment variable: LOG_JSON_ENABLED
2. If disabled: Return (use default logging)
3. If enabled:
   - Create custom JSON formatter
   - Format: NDJSON (one JSON object per line)
   - Fields:
     * timestamp (ISO 8601)
     * level
     * message
     * logger
     * module
     * function
     * line
     * thread
     * service (service_name)
     * version
     * pod_name (from env)
     * correlation_id (from context)
     * trace_id (from OpenTelemetry if enabled)
     * span_id (from OpenTelemetry if enabled)
   - Set as root logger handler

JSON Format Example:
{
  "timestamp": "2025-11-10T12:34:56.789Z",
  "level": "INFO",
  "message": "Event processed successfully",
  "logger": "alerter",
  "module": "alerter_service",
  "function": "process_event",
  "line": 245,
  "thread": "MainThread",
  "service": "mutt-alerter",
  "version": "2.5",
  "pod_name": "alerter-abc123",
  "correlation_id": "550e8400-e29b-41d4-a716-446655440000",
  "trace_id": "4bf92f3577b34da6a3ce929d0e0e4736",
  "span_id": "00f067aa0ba902b7"
}
```

**Test Cases:**
- JSON formatting correct
- Fields populated
- Correlation ID included
- Fallback to plain logging if disabled

#### Utility 7: `services/tracing_utils.py`

**Purpose:** OpenTelemetry distributed tracing (opt-in)

**Specifications:**

```python
Function: setup_tracing(
  service_name: str,
  version: str
) -> None

Logic:
1. Check environment variable: OTEL_ENABLED
2. If disabled: Return (no-op)
3. If enabled:
   - Get OTEL_EXPORTER_OTLP_ENDPOINT from env
   - Create TracerProvider with resource attributes
   - Set OTLP gRPC exporter
   - Instrument Flask, Requests, Redis, Psycopg2
   - Set as global tracer provider

Resource Attributes:
- service.name: service_name
- service.version: version
- deployment.environment: from env
- host.name: hostname

Function: get_current_trace_ids() -> Tuple[str, str]
  Returns: (trace_id, span_id) or (None, None)

Function: extract_tracecontext(flask_request) -> SpanContext
  Extracts W3C traceparent header from Flask request

Function: inject_tracecontext(headers: dict) -> None
  Injects W3C traceparent header for outgoing requests
```

**Test Cases:**
- Setup with OTEL enabled
- No-op when disabled
- Trace ID extraction
- Context propagation
- Auto-instrumentation

### 2.2 Ingestor Service

**Reference:** `docs/architecture/SYSTEM_ARCHITECTURE.md` - Ingestor section

**File:** `services/ingestor_service.py`

**Purpose:** HTTP endpoint for event ingestion

**Specifications:**

#### Flask Application Setup

```python
from flask import Flask, request, jsonify
from prometheus_flask_exporter import PrometheusMetrics

app = Flask(__name__)
metrics = PrometheusMetrics(app)

# Custom metrics
ingest_requests = Counter('mutt_ingest_requests_total', 'Total ingestion requests', ['status', 'reason'])
queue_depth_gauge = Gauge('mutt_ingest_queue_depth', 'Current ingest queue depth')
ingest_latency = Histogram('mutt_ingest_latency_seconds', 'Ingestion request latency')
```

#### Environment Variables

```python
Required:
- SERVER_PORT_INGESTOR (default: 8080)
- REDIS_HOST
- REDIS_PORT
- VAULT_ADDR
- VAULT_ROLE_ID
- VAULT_SECRET_ID_FILE
- VAULT_SECRETS_PATH

Optional:
- REDIS_TLS_ENABLED (default: true)
- REDIS_CA_CERT_PATH
- REDIS_MAX_CONNECTIONS (default: 20)
- MAX_INGEST_QUEUE_SIZE (default: 1000000)
- INGEST_QUEUE_NAME (default: mutt:ingest_queue)
- REQUIRED_MESSAGE_FIELDS (default: timestamp,message,hostname)
```

#### Vault Integration

```python
Function: get_secrets_from_vault() -> dict

Logic:
1. Read ROLE_ID from env
2. Read SECRET_ID from file
3. Authenticate: POST /v1/auth/approle/login
4. Get token from response
5. Read secrets: GET /v1/{VAULT_SECRETS_PATH}
6. Extract:
   - INGEST_API_KEY
   - REDIS_PASS_CURRENT
   - REDIS_PASS_NEXT (optional)
7. Start background token renewal thread
8. Return secrets dict

Background Thread: renew_vault_token()
- Check token TTL every 5 minutes
- If TTL < 1 hour: POST /v1/auth/token/renew-self
- Update token
- Log renewal success/failure
```

#### Endpoints

**1. POST /api/v2/ingest**

```python
Purpose: Ingest events

Authentication: X-API-KEY header (constant-time comparison)

Request Body (JSON):
{
  "timestamp": "2025-11-10T12:00:00Z",  # ISO 8601, required
  "message": "Interface GigE0/1 down",  # string, required
  "hostname": "router1",                # string, required
  "source": "syslog",                   # "syslog" or "snmp", optional
  "syslog_severity": 3,                 # 0-7, optional
  "trap_oid": "1.3.6.1.4.1.9.9.41",    # string, optional
  "correlation_id": "uuid"              # UUID, optional (auto-generated)
}

Validation:
1. Check required fields exist
2. Validate timestamp format (ISO 8601)
3. Validate syslog_severity (0-7 if present)
4. Validate trap_oid format if present

Enrichment:
1. Generate correlation_id if not provided (uuid4)
2. Add ingestion_timestamp (NOW)

Backpressure Check:
1. LLEN mutt:ingest_queue
2. If > MAX_INGEST_QUEUE_SIZE:
   - Return HTTP 503 Service Unavailable
   - Increment ingest_requests{status="fail",reason="queue_full"}
   - Body: {"error": "Queue full, retry later"}

Processing:
1. Serialize event to JSON string
2. LPUSH mutt:ingest_queue {json_string}
3. Update metrics:
   - Increment ingest_requests{status="success",reason=""}
   - Update queue_depth_gauge
   - Observe ingest_latency
4. Return HTTP 200
   - Body: {"status": "accepted", "correlation_id": "..."}

Error Handling:
- Invalid JSON → HTTP 400
- Missing required fields → HTTP 400
- Invalid field values → HTTP 400
- Queue full → HTTP 503
- Redis error → HTTP 500
- Authentication failure → HTTP 401
```

**2. GET /health**

```python
Purpose: Health check endpoint

Response:
{
  "status": "healthy",
  "redis": "connected",
  "timestamp": "2025-11-10T12:00:00Z",
  "queue_depth": 12345
}

Logic:
1. Try Redis PING command
2. If success:
   - LLEN mutt:ingest_queue
   - Return HTTP 200 with stats
3. If failure:
   - Return HTTP 503 with error
```

**3. GET /metrics**

```python
Purpose: Prometheus metrics scrape endpoint

Response: Prometheus text format

Metrics Exposed:
- mutt_ingest_requests_total{status,reason}
- mutt_ingest_queue_depth
- mutt_ingest_latency_seconds
- process_* (Python process metrics)
- http_* (Flask HTTP metrics)
```

#### Main Function

```python
def main():
    # 1. Get secrets from Vault
    secrets = get_secrets_from_vault()

    # 2. Connect to Redis
    redis_client = get_redis_connection(
        host=REDIS_HOST,
        port=REDIS_PORT,
        password_current=secrets['REDIS_PASS_CURRENT'],
        password_next=secrets.get('REDIS_PASS_NEXT'),
        ...
    )

    # 3. Setup logging
    setup_json_logging("mutt-ingestor", "2.5")

    # 4. Setup tracing
    setup_tracing("mutt-ingestor", "2.5")

    # 5. Run Flask app
    app.run(host='0.0.0.0', port=SERVER_PORT_INGESTOR)

if __name__ == '__main__':
    main()
```

#### Test Cases

```python
1. test_ingest_valid_event()
   - POST with valid event
   - Assert HTTP 200
   - Assert event in Redis queue
   - Assert metrics incremented

2. test_ingest_missing_required_field()
   - POST without "message"
   - Assert HTTP 400

3. test_ingest_invalid_timestamp()
   - POST with malformed timestamp
   - Assert HTTP 400

4. test_ingest_queue_full()
   - Fill queue to MAX_INGEST_QUEUE_SIZE + 1
   - POST event
   - Assert HTTP 503

5. test_ingest_invalid_api_key()
   - POST with wrong X-API-KEY
   - Assert HTTP 401

6. test_health_redis_up()
   - GET /health with Redis running
   - Assert HTTP 200
   - Assert "redis": "connected"

7. test_health_redis_down()
   - GET /health with Redis stopped
   - Assert HTTP 503

8. test_metrics_endpoint()
   - GET /metrics
   - Assert Prometheus format
   - Assert expected metrics present

9. test_correlation_id_auto_generation()
   - POST without correlation_id
   - Assert correlation_id in response

10. test_vault_token_renewal()
    - Mock Vault TTL check
    - Wait for renewal trigger
    - Assert token renewed
```

### 2.3 Alerter Service

**Reference:** `docs/architecture/SYSTEM_ARCHITECTURE.md` - Alerter section

**File:** `services/alerter_service.py`

**Purpose:** Core event processing with rule matching

This is the most complex service. Follow the specifications carefully.

*(Due to length, continuing in next response...)*

---

**TO BE CONTINUED:** The rebuild guide continues with detailed specifications for:
- Alerter Service (2.3)
- Moog Forwarder Service (2.4)
- Web UI Service (2.5)
- Remediation Service (2.6)
- Integration patterns
- Testing strategy
- Deployment configurations

**Current Progress:** ~50% complete (Foundation + Database + Shared Utilities + Ingestor)

Would you like me to:
1. Continue with the remaining services in the same detail?
2. Complete this as a multi-part guide?
3. Focus on a specific service or component?
