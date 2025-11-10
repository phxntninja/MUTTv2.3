# MUTT v2.3 Project Handoff Document
**Multi-Use Telemetry Tool - Production-Ready Implementation**

**Document Version:** 1.0
**Date:** 2025-11-08
**Session Status:** Development Complete - Ready for Deployment Testing
**Architecture Version:** v2.3 (based on v2.1 specification)

---

## Table of Contents
1. [Executive Summary](#executive-summary)
2. [Project Architecture Overview](#project-architecture-overview)
3. [Completed Work Inventory](#completed-work-inventory)
4. [Critical Implementation Details](#critical-implementation-details)
5. [Known Issues and Resolutions](#known-issues-and-resolutions)
6. [File Inventory](#file-inventory)
7. [Deployment Status](#deployment-status)
8. [Testing Strategy](#testing-strategy)
9. [Next Steps](#next-steps)
10. [Technical Debt and Future Enhancements](#technical-debt-and-future-enhancements)
11. [Key Decisions Log](#key-decisions-log)
12. [Troubleshooting Guide](#troubleshooting-guide)

---

## Executive Summary

### Project Purpose
MUTT (Multi-Use Telemetry Tool) is a production-grade event processing system designed for enterprise RHEL and OpenShift environments. It ingests syslog and SNMP trap messages, applies intelligent routing rules, and forwards critical events to Moog AIOps while maintaining a comprehensive audit trail.

### Current Status: **DEVELOPMENT COMPLETE ✅**

All four core services have been developed to v2.3 production-ready standards with comprehensive error handling, security hardening, and operational best practices.

### What's Complete:
- ✅ **Ingestor Service v2.3** - HTTP ingestion with backpressure, Vault integration, TLS support
- ✅ **Alerter Service v2.3** - Core event processing with Lua-based atomic operations
- ✅ **Moog Forwarder Service v2.3** - Shared rate limiting, exponential backoff, smart retry logic
- ✅ **Web UI Service v2.3** - Complete CRUD API + metrics dashboard
- ✅ **PostgreSQL Schema v2.1** - Partitioned tables with helper functions
- ✅ **RHEL Deployment Script** - Automated installation with validation
- ✅ **rsyslog Configuration** - Corrected and production-ready
- ✅ **Comprehensive README.md** - Full documentation with all environment variables
- ✅ **systemd Service Files** - All 4 services with security hardening

### What's Pending:
- ⏳ **Deployment Testing** - Services not yet deployed to actual RHEL server
- ⏳ **Integration Testing** - End-to-end testing with real syslog/SNMP sources
- ⏳ **Vault Setup** - HashiCorp Vault must be configured with AppRole
- ⏳ **TLS Certificates** - Must be generated and placed in `/etc/mutt/certs`
- ⏳ **Database Initialization** - PostgreSQL must be set up with schema
- ⏳ **Performance Testing** - Load testing to determine maximum EPS capacity
- ⏳ **Security Audit** - Third-party review recommended before production

---

## Project Architecture Overview

### High-Level Architecture

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

### Key Architectural Patterns

#### 1. **BRPOPLPUSH Pattern (Reliable Queueing)**
Used in: Alerter Service, Moog Forwarder Service

```python
# Atomic move from main queue to processing list
message = redis_client.brpoplpush(
    source='mutt:ingest_queue',
    destination='alerter_processing:pod-123',
    timeout=30
)

# Process the message...
# Only after success:
redis_client.lrem('alerter_processing:pod-123', 1, message)
```

**Why:** Ensures zero message loss during pod crashes. If a pod dies mid-processing, the message remains in its processing list for recovery.

#### 2. **Heartbeat + Janitor Pattern (Orphan Recovery)**
Used in: Alerter Service, Moog Forwarder Service

```python
# Each pod maintains a heartbeat
redis_client.setex(f'mutt:heartbeat:{pod_name}', 60, 'alive')

# On startup, janitor recovers orphaned messages
for processing_list in orphaned_lists:
    if not heartbeat_exists(processing_list):
        # Recover all messages back to main queue
        while message := redis_client.rpoplpush(processing_list, main_queue):
            pass
```

**Why:** Crashed pods leave messages in their processing lists. Janitor detects dead pods (no heartbeat) and recovers their messages.

#### 3. **Lua Scripts for Atomic Operations**
Used in: Alerter Service (unhandled detection), Moog Forwarder (rate limiting)

```python
# Unhandled event detection - prevents duplicate meta-alerts
UNHANDLED_LUA_SCRIPT = """
local key = KEYS[1]
local triggered_key = KEYS[2]
local threshold = tonumber(ARGV[1])

if redis.call('EXISTS', triggered_key) == 1 then
    return 0  -- Already triggered
end

local count = redis.call('INCR', key)
if count == threshold then
    redis.call('RENAME', key, triggered_key)
    redis.call('EXPIRE', triggered_key, 3600)
    return 1  -- TRIGGER META-ALERT
end
return 0
"""
```

**Why:** Race conditions occur when multiple pods check/increment counters. Lua scripts execute atomically on Redis server.

#### 4. **Shared Rate Limiting (Global Coordination)**
Used in: Moog Forwarder Service

```python
# All pods share a single rate limit using Redis sorted set
RATE_LIMIT_LUA_SCRIPT = """
local key = KEYS[1]
local limit = tonumber(ARGV[1])
local window = tonumber(ARGV[2])
local now = tonumber(ARGV[3])

redis.call('ZREMRANGEBYSCORE', key, 0, now - window)
local current = redis.call('ZCARD', key)

if current < limit then
    redis.call('ZADD', key, now, now .. ':' .. math.random())
    redis.call('EXPIRE', key, window)
    return 1  -- Allowed
else
    return 0  -- Rate limited
end
"""
```

**Why:** Each pod checking local limits doesn't work when scaled horizontally. Redis-based sliding window ensures global rate limit.

#### 5. **Exponential Backoff with Jitter**
Used in: Moog Forwarder Service

```python
delay = min(
    config.MOOG_RETRY_BASE_DELAY * (2 ** retry_count),
    config.MOOG_RETRY_MAX_DELAY
)
# 1s → 2s → 4s → 8s → 16s → 32s → 60s (max)
```

**Why:** Prevents thundering herd problem when Moog is down. Exponential backoff reduces load on failing service.

---

## Completed Work Inventory

### 1. Ingestor Service v2.3
**File:** `ingestor_service.py`

**Key Features:**
- ✅ Vault integration with AppRole authentication
- ✅ Background token renewal thread (checks every 5 min)
- ✅ API key authentication with constant-time comparison (prevents timing attacks)
- ✅ Redis connection pooling (min: 2, max: 10)
- ✅ TLS support for Redis and HTTPS endpoints
- ✅ Backpressure handling (queue cap, returns 503)
- ✅ Malformed JSON detection (returns 400)
- ✅ Prometheus metrics (5 labels: success, fail_auth, fail_json, fail_queue_full, fail_redis)
- ✅ Metrics for Web UI (1m, 1h, 24h counters with TTL)
- ✅ Comprehensive error handling

**Critical Fixes from Original:**
- ❌ **Original Issue:** `api_key == secrets["INGEST_API_KEY"]` → Timing attack vulnerability
- ✅ **Fixed:** `secrets.compare_digest(api_key, expected_key)`
- ❌ **Original Issue:** No Vault token renewal → Service dies after token expires
- ✅ **Fixed:** Background thread checks TTL and renews before expiry
- ❌ **Original Issue:** Global `secrets` dict → Thread safety issues
- ✅ **Fixed:** Encapsulated in `VaultClient` class with locks

**Port:** 8080

---

### 2. Alerter Service v2.3
**File:** `services/alerter_service.py`

**Key Features:**
- ✅ BRPOPLPUSH for crash-safe message processing
- ✅ Heartbeat + Janitor pattern (30s heartbeat, recovers orphans on startup)
- ✅ PostgreSQL connection pooling (ThreadedConnectionPool: 2-10 connections)
- ✅ In-memory rule cache (loaded on startup, refreshes every 5 min)
- ✅ Lua script for atomic unhandled event detection
- ✅ Priority-based rule matching (lowest priority wins)
- ✅ Support for 3 match types: `contains`, `regex`, `oid_prefix`
- ✅ Dual metrics endpoints (8081 for health, 8082 for Prometheus)
- ✅ SIGHUP signal handler for cache refresh
- ✅ SCAN instead of KEYS (production-safe Redis iteration)
- ✅ Correlation ID tracking (thread-local storage)

**Critical Fixes from Original:**
- ❌ **Original Issue:** `logger = logging.getLogger(name)` → Syntax error
- ✅ **Fixed:** `logger = logging.getLogger(__name__)`
- ❌ **Original Issue:** `unhandled_count = redis_client.incr(key); if unhandled_count == threshold` → Race condition
- ✅ **Fixed:** Atomic Lua script with RENAME to prevent duplicate meta-alerts
- ❌ **Original Issue:** No PostgreSQL connection pooling → Database connection exhaustion
- ✅ **Fixed:** `psycopg2.pool.ThreadedConnectionPool`
- ❌ **Original Issue:** Uses `KEYS` command → Blocks Redis in production
- ✅ **Fixed:** Uses `SCAN` with cursor iteration

**Ports:** 8081 (health), 8082 (metrics)

---

### 3. Moog Forwarder Service v2.3
**File:** `moog_forwarder_service.py`

**Created from scratch** (no original to review)

**Key Features:**
- ✅ BRPOPLPUSH pattern with processing lists
- ✅ Heartbeat + Janitor pattern
- ✅ Redis-based shared rate limiter (Lua script with sorted set)
- ✅ Exponential backoff retry: 1s → 2s → 4s → 8s → 16s → 32s → 60s max
- ✅ Smart retry logic (retry 5xx/timeout, DLQ on 4xx)
- ✅ Dead Letter Queue for poison messages
- ✅ Configurable rate limiting (default: 50 req/s globally across all pods)
- ✅ Dual metrics endpoints (8083 for health, 8084 for Prometheus)
- ✅ Correlation ID propagation
- ✅ Vault integration for MOOG_API_KEY
- ✅ Comprehensive metrics (6 custom Prometheus metrics)

**Important Configuration:**
- `MOOG_RATE_LIMIT=50` - Max requests per second (global)
- `MOOG_RATE_PERIOD=1` - Time window in seconds
- `MOOG_MAX_RETRIES=5` - Retries before DLQ
- `MOOG_TIMEOUT=10` - HTTP timeout in seconds

**Ports:** 8083 (health), 8084 (metrics)

---

### 4. Web UI Service v2.3
**File:** `web_ui_service.py`

**Key Features:**
- ✅ Complete CRUD API for all 4 database tables
- ✅ API key authentication on all endpoints (except /health, /metrics, /)
- ✅ Metrics caching (5-second TTL to reduce Redis load)
- ✅ Pagination support (audit logs endpoint)
- ✅ Fixed Chart.js integration (corrected CDN URL)
- ✅ PostgreSQL connection pooling
- ✅ Vault integration for secrets
- ✅ 15+ REST API endpoints

**API Endpoints:**

| Method | Endpoint | Purpose |
|--------|----------|---------|
| GET | `/` | Dashboard HTML (metrics charts) |
| GET | `/health` | Health check (no auth) |
| GET | `/metrics` | Prometheus metrics (no auth) |
| GET | `/api/v1/rules` | List all alert rules |
| POST | `/api/v1/rules` | Create new rule |
| PUT | `/api/v1/rules/<id>` | Update rule |
| DELETE | `/api/v1/rules/<id>` | Delete rule |
| GET | `/api/v1/audit-logs` | List audit logs (paginated) |
| GET | `/api/v1/dev-hosts` | List development hosts |
| POST | `/api/v1/dev-hosts` | Add dev host |
| DELETE | `/api/v1/dev-hosts/<hostname>` | Remove dev host |
| GET | `/api/v1/teams` | List device teams |
| POST | `/api/v1/teams` | Add team mapping |
| PUT | `/api/v1/teams/<hostname>` | Update team |
| DELETE | `/api/v1/teams/<hostname>` | Remove team |
| GET | `/api/v1/metrics/current` | Current ingestion rates |

**Critical Fixes from Original:**
- ❌ **Original Issue:** Broken Chart.js URL (Google search redirect)
- ✅ **Fixed:** `https://cdn.jsdelivr.net/npm/chart.js@4.4.0/dist/chart.umd.min.js`
- ❌ **Original Issue:** JavaScript template literal without backticks
- ✅ **Fixed:** Proper template literal syntax
- ❌ **Original Issue:** Duplicate Prometheus metrics registration
- ✅ **Fixed:** Single initialization with guards
- ❌ **Original Issue:** Only metrics dashboard, no CRUD
- ✅ **Fixed:** Complete REST API for all resources

**Port:** 8090

---

### 5. PostgreSQL Schema v2.1
**File:** `mutt_schema v2.1.sql`

**Tables:**
1. **alert_rules** - Core matching logic (cached by Alerter)
   - Columns: `id`, `match_string`, `trap_oid`, `syslog_severity`, `match_type`, `priority`, `prod_handling`, `dev_handling`, `team_assignment`, `is_active`
   - Indexes: `idx_alert_rules_match_type`, `idx_alert_rules_is_active`

2. **development_hosts** - Dev environment lookup (cached)
   - Columns: `hostname` (PK)

3. **device_teams** - Team assignment lookup (cached)
   - Columns: `hostname` (PK), `team_assignment`

4. **event_audit_log** - Partitioned audit trail
   - Columns: `id`, `event_timestamp`, `hostname`, `matched_rule_id`, `handling_decision`, `forwarded_to_moog`, `raw_message`
   - Partitioning: Monthly by `event_timestamp`
   - Indexes: `idx_audit_log_timestamp`, `idx_audit_log_hostname`, `idx_audit_log_rule_id`

**Helper Functions:**
- `create_monthly_partition(start_date DATE)` - Creates new partition
- `drop_old_partitions(retention_months INTEGER)` - Cleanup old data

**Sample Data:** 4 alert rules, 3 dev hosts, 4 device teams

---

### 6. RHEL Deployment Script
**File:** `deploy_mutt_v2.3.sh`

**What It Does:**
1. ✅ Prerequisites validation (Python version, commands, connectivity)
2. ✅ External service checks (Redis, PostgreSQL, Vault)
3. ✅ System dependency installation (`gcc`, `python3-devel`, etc.)
4. ✅ Service user creation (`mutt` with `/bin/false` shell)
5. ✅ Directory structure creation (including `/etc/mutt/certs`)
6. ✅ Application code deployment
7. ✅ Python virtual environment setup
8. ✅ Requirements.txt with version pinning
9. ✅ TLS certificate directory setup
10. ✅ Environment configuration template
11. ✅ Interactive configuration
12. ✅ Proper permissions (600 for secrets, 700 for dirs)
13. ✅ systemd service file generation (all 4 services)
14. ✅ Firewall configuration (ports 8080-8090)
15. ✅ SELinux warnings with commands
16. ✅ Log rotation setup
17. ✅ Pre-start validation
18. ✅ Service enablement
19. ✅ Optional interactive startup
20. ✅ Health check verification

**Critical Improvements Over Original:**
- Original had no prerequisites check → Now validates everything
- Original used `sudo nano` → Now uses templates and sed
- Original missing TLS certs → Now creates `/etc/mutt/certs` with README
- Original no firewall → Now configures firewalld
- Original no SELinux handling → Now warns with specific commands
- Original no health checks → Now tests `/health` endpoints

**Companion File:** `uninstall_mutt.sh` (cleanup script)

---

### 7. rsyslog Configuration (CORRECTED)
**File:** `99-mutt.conf`

**Critical Fixes from Original:**

| Issue | Original | Corrected |
|-------|----------|-----------|
| JSON escaping | `value=""timestamp":""` | `value="\"timestamp\":\""` |
| Property reference | `$.syslogseverity` | `$syslogseverity` |
| Action type | `type="omfwd"` | `type="omhttp"` |
| TLS | `useHttps="off"` | `usehttps="on"` |
| Batching | Not configured | `batch="on"`, `batch.maxsize="100"` |

**What It Does:**
1. Listens on UDP/TCP 514 for network syslog
2. Receives local SNMP traps from snmptrapd (facility local5)
3. Formats messages as JSON with proper escaping
4. Forwards to Ingestor via HTTPS POST
5. Handles backpressure with LinkedList queue (100k messages)
6. Retries indefinitely on 503 errors
7. Saves queue to disk on shutdown

**Companion File:** `/etc/snmp/snmptrapd.conf` (SNMP trap daemon config)

---

### 8. Documentation
**File:** `README.md`

**Contents:**
- Complete architecture diagram
- Environment variables for all 4 services (60+ variables total)
- Moog Forwarder specifics (rate limiting, retry logic)
- Web UI API reference (15+ endpoints)
- Prometheus metrics (30+ metrics)
- Deployment examples (Docker, Kubernetes, Gunicorn)
- Troubleshooting section

---

### 9. systemd Service Files
**Files:** `mutt-ingestor.service`, `mutt-alerter.service`, `mutt-moog-forwarder.service`, `mutt-webui.service`

**Features:**
- Service dependencies (`After`, `Requires`)
- Security hardening (`NoNewPrivileges`, `ProtectSystem=strict`, `ProtectHome=true`)
- Restart policies (always restart, 10s delay, max 5 retries per 200s)
- Gunicorn for WSGI services (Ingestor, Web UI)
- Proper working directory and environment file loading

---

## Critical Implementation Details

### Security Considerations

#### 1. **Timing Attack Prevention**
**Location:** All services, API key authentication

```python
# ❌ VULNERABLE
if api_key == secrets["INGEST_API_KEY"]:
    # Attacker can measure timing difference to guess key

# ✅ SECURE
import secrets as secrets_module
if secrets_module.compare_digest(api_key, expected_key):
    # Constant-time comparison
```

#### 2. **Vault Token Lifecycle**
**Location:** All services

```python
# Problem: Vault tokens expire (default: 768 hours = 32 days)
# Solution: Background thread checks TTL and renews

def renewal_loop():
    while True:
        time.sleep(300)  # Check every 5 minutes
        token_info = vault_client.auth.token.lookup_self()
        ttl = token_info['data']['ttl']

        if ttl < VAULT_TOKEN_RENEW_THRESHOLD:  # Default: 3600s (1 hour)
            vault_client.auth.token.renew_self()
```

**Why:** If token expires mid-operation, services can't fetch new secrets or renew Redis/DB passwords.

#### 3. **Secrets Management**
- All secrets stored in HashiCorp Vault
- RHEL: AppRole authentication (VAULT_ROLE_ID + VAULT_SECRET_ID file)
- OCP: Kubernetes Auth Method (ServiceAccount)
- Secrets never logged or printed
- API keys use constant-time comparison

---

### Performance Optimizations

#### 1. **Connection Pooling**

**PostgreSQL:**
```python
from psycopg2.pool import ThreadedConnectionPool

pool = ThreadedConnectionPool(
    minconn=2,   # Minimum idle connections
    maxconn=10,  # Maximum connections
    **connection_params
)

# Thread-safe get/put
conn = pool.getconn()
try:
    # Use connection
finally:
    pool.putconn(conn)
```

**Redis:**
```python
redis_pool = redis.ConnectionPool(
    host=config.REDIS_HOST,
    port=config.REDIS_PORT,
    max_connections=10,
    decode_responses=True
)
redis_client = redis.Redis(connection_pool=redis_pool)
```

**Why:** Creating new database connections is expensive (TCP handshake, TLS, auth). Pools reuse connections.

#### 2. **Metrics Caching (Web UI)**
```python
class MetricsCache:
    def __init__(self, ttl=5):
        self.ttl = 5  # 5-second cache
        self.data = None
        self.timestamp = 0

    def get(self):
        if time.time() - self.timestamp > self.ttl:
            # Refresh from Redis
            self.data = fetch_from_redis()
            self.timestamp = time.time()
        return self.data
```

**Why:** Metrics dashboard refreshes every second. Without caching, 1 user = 6 Redis calls/sec. With cache, 1 user = 0.2 Redis calls/sec.

#### 3. **Rule Caching (Alerter)**
```python
# On startup: Load all rules into memory
rule_cache = {
    'alert_rules': [],      # List of rule dicts
    'dev_hosts': set(),     # Set of dev hostnames
    'device_teams': {}      # Hostname -> team mapping
}

# Refresh every 5 minutes
# Lookup: O(1) or O(n) in memory vs O(n) database query per message
```

**Why:** Alerter processes 1000s of events/sec. Database query per event would bottleneck at ~100 EPS.

#### 4. **Batching (rsyslog)**
```
batch="on"
batch.format="newline"
batch.maxsize="100"
```

**Why:** 1 HTTP request per message = high overhead. Batching 100 messages per request = 99% reduction in HTTP overhead.

---

### Reliability Patterns

#### 1. **Message Loss Prevention**

**Problem:** Service crashes mid-processing → message lost

**Solution:** BRPOPLPUSH + Processing Lists
```python
# 1. Atomic move from queue to processing list
msg = redis_client.brpoplpush('ingest_queue', 'processing:pod-1', timeout=30)

# 2. Process (may crash here)
result = process_message(msg)

# 3. Only delete if successful
if result.success:
    redis_client.lrem('processing:pod-1', 1, msg)
else:
    # Message stays in processing list for retry
    pass
```

**Recovery:** Janitor on startup recovers orphaned processing lists

#### 2. **Race Condition Prevention**

**Problem:** Multiple pods incrementing same counter
```python
# ❌ RACE CONDITION
count = redis.get(key)
count += 1
redis.set(key, count)
# Pod A and Pod B both read count=99, both write count=100
```

**Solution:** Lua script (executes atomically on Redis server)
```python
# ✅ ATOMIC
LUA_SCRIPT = """
local count = redis.call('INCR', KEYS[1])
if count == threshold then
    return 1
end
return 0
"""
result = redis_client.eval(LUA_SCRIPT, 1, key, threshold)
```

#### 3. **Duplicate Meta-Alert Prevention**

**Problem:** Counter hits threshold multiple times during TTL window

**Solution:** RENAME in Lua script
```lua
if count == threshold then
    redis.call('RENAME', 'mutt:unhandled:host123', 'mutt:unhandled:triggered:host123')
    return 1  -- Send meta-alert
end
```

Once renamed, subsequent INCRs create a new key (count=1), not triggering threshold again.

---

### Scaling Considerations

#### Horizontal Scaling Support

| Service | Scalable? | Coordination Method |
|---------|-----------|---------------------|
| **Ingestor** | ✅ Yes | Stateless - load balance with HAProxy/OCP Route |
| **Alerter** | ✅ Yes | BRPOPLPUSH acts as load distributor (atomic queue pop) |
| **Moog Forwarder** | ✅ Yes | Redis-based shared rate limiter (Lua script) |
| **Web UI** | ✅ Yes | Stateless (read-only) - load balance |

#### Rate Limiting Math

**Configuration:**
```bash
MOOG_RATE_LIMIT=50      # 50 requests/second (global)
MOOG_RATE_PERIOD=1      # 1-second window
```

**Scaling:**
- 1 pod: Can send up to 50 req/s to Moog
- 3 pods: Still only 50 req/s total (shared limit)
- Each pod coordinates via Redis sorted set

**Why:** Moog has a global rate limit. If each pod has a local 50 req/s limit, 3 pods = 150 req/s → Moog rejects requests.

---

## Known Issues and Resolutions

### Issues Found and Fixed

#### Issue #1: Ingestor v2.2 Missing Token Renewal
**Severity:** Critical
**Found:** During comparison of user's v2.2 with my v2.1
**Impact:** Service stops working after Vault token expires (default: 32 days)
**Resolution:** Added background thread in `VaultClient` class
**Status:** ✅ Fixed in v2.3

#### Issue #2: Alerter Race Condition in Unhandled Counter
**Severity:** High
**Found:** Code review of original Alerter
**Impact:** Duplicate meta-alerts sent, incorrect counts
**Resolution:** Replaced increment + check with atomic Lua script + RENAME
**Status:** ✅ Fixed in v2.3

#### Issue #3: rsyslog JSON Template Syntax Errors
**Severity:** Critical (Blocker)
**Found:** Code review of rsyslog config
**Impact:** rsyslog fails to start, no messages forwarded
**Resolution:** Fixed all quote escaping, replaced `omfwd` with `omhttp`
**Status:** ✅ Fixed in corrected config

#### Issue #4: Web UI Broken Chart.js CDN
**Severity:** High
**Found:** Code review of Web UI
**Impact:** Dashboard charts don't load
**Resolution:** Fixed CDN URL from Google search redirect to actual CDN
**Status:** ✅ Fixed in v2.3

#### Issue #5: Deployment Script Not Scriptable
**Severity:** Medium
**Found:** Review of original deployment script
**Impact:** Manual `nano` steps prevent automation
**Resolution:** Template-based approach with sed replacements
**Status:** ✅ Fixed in improved script

---

### Current Known Issues

#### Issue #A: SELinux Policy Not Defined
**Severity:** Medium
**Impact:** Services may fail to start on enforcing SELinux systems
**Workaround:** Set SELinux to permissive mode or create custom policy
**Status:** ⏳ Documented in deployment script (section 14)

#### Issue #B: TLS Certificate Generation Not Automated
**Severity:** Low
**Impact:** Manual cert generation required before deployment
**Workaround:** Use Let's Encrypt or internal CA
**Status:** ⏳ Documented in `/etc/mutt/certs/README.txt`

#### Issue #C: Database Partition Creation Manual
**Severity:** Low
**Impact:** Admin must run `create_monthly_partition()` function monthly
**Workaround:** Set up cron job to auto-create partitions
**Status:** ⏳ Helper function provided in schema

#### Issue #D: No Automated Testing Suite
**Severity:** Medium
**Impact:** Changes may introduce regressions
**Recommendation:** Implement pytest unit tests + docker-compose integration tests
**Status:** ⏳ Pending (see Testing Strategy section)

---

## File Inventory

### Core Service Files (Python)
| File | Version | Lines | Purpose | Status |
|------|---------|-------|---------|--------|
| `ingestor_service.py` | v2.3 | ~350 | HTTP ingestion, backpressure, Vault integration | ✅ Complete |
| `services/alerter_service.py` | v2.3 | ~900 | Core event processing, rule matching, audit logging | ✅ Complete |
| `moog_forwarder_service.py` | v2.3 | ~750 | Forward to Moog with rate limiting and retry | ✅ Complete |
| `web_ui_service.py` | v2.3 | ~650 | REST API + metrics dashboard | ✅ Complete |

### Configuration Files
| File | Purpose | Status |
|------|---------|--------|
| `mutt_schema v2.1.sql` | PostgreSQL database schema with partitioning | ✅ Complete |
| `99-mutt.conf` | rsyslog configuration (corrected) | ✅ Complete |
| `snmptrapd.conf` | SNMP trap daemon config | ✅ Complete |
| `mutt.env.template` | Environment variable template | ✅ Generated by deploy script |
| `requirements.txt` | Python dependencies with versions | ✅ Generated by deploy script |

### systemd Files
| File | Service | Port(s) | Status |
|------|---------|---------|--------|
| `mutt-ingestor.service` | Ingestor | 8080 | ✅ Generated by deploy script |
| `mutt-alerter.service` | Alerter | 8081, 8082 | ✅ Generated by deploy script |
| `mutt-moog-forwarder.service` | Moog Forwarder | 8083, 8084 | ✅ Generated by deploy script |
| `mutt-webui.service` | Web UI | 8090 | ✅ Generated by deploy script |

### Deployment & Documentation
| File | Purpose | Status |
|------|---------|--------|
| `deploy_mutt_v2.3.sh` | Automated RHEL deployment script | ✅ Complete |
| `uninstall_mutt.sh` | Cleanup/rollback script | ✅ Complete |
| `README.md` | Project documentation | ✅ Complete |
| `HANDOFF.md` | This file | ✅ Complete |

---

## Deployment Status

### Prerequisites Checklist

#### Infrastructure Requirements
- [ ] **RHEL 8/9 Server** - OS installed and accessible
- [ ] **Redis** - Installed and running (HA with Sentinel recommended)
  - Minimum version: 5.0
  - TLS configured (if REDIS_TLS_ENABLED=true)
  - Sentinel configured for automatic failover
- [ ] **PostgreSQL** - Installed and running (HA with Patroni/Zalando recommended)
  - Minimum version: 12 (for native partitioning)
  - Database `mutt` created
  - User `mutt_app` created with appropriate privileges
  - SSL enabled (if DB_SSL_MODE=require)
- [ ] **HashiCorp Vault** - Installed and running
  - AppRole auth method enabled
  - Secrets path `secret/mutt` created
  - Role and Secret ID generated
  - Secrets stored: `REDIS_PASS`, `DB_PASS`, `INGEST_API_KEY`, `WEBUI_API_KEY`, `MOOG_API_KEY`

#### Network Requirements
- [ ] **Firewall Rules** - Ports opened
  - 514/UDP and 514/TCP (rsyslog ingestion)
  - 162/UDP (SNMP traps)
  - 8080/TCP (Ingestor)
  - 8081-8082/TCP (Alerter)
  - 8083-8084/TCP (Moog Forwarder)
  - 8090/TCP (Web UI)
- [ ] **DNS Resolution** - All hostnames resolve
- [ ] **Connectivity** - Server can reach Redis, PostgreSQL, Vault, Moog

#### TLS Certificates
- [ ] **CA Certificate** - `/etc/mutt/certs/ca.pem`
- [ ] **Server Certificate** - `/etc/mutt/certs/server.crt`
- [ ] **Server Key** - `/etc/mutt/certs/server.key` (chmod 600)
- [ ] **Redis CA** - `/etc/mutt/certs/redis-ca.pem` (if separate)
- [ ] **PostgreSQL CA** - `/etc/mutt/certs/postgres-ca.pem` (if separate)

#### File Deployment
- [ ] Copy all 4 Python service files to deployment directory
- [ ] Copy `deploy_mutt_v2.3.sh` to server
- [ ] Make deployment script executable: `chmod +x deploy_mutt_v2.3.sh`

---

### Deployment Steps

#### Phase 1: Database Setup
```bash
# 1. Create database and user
sudo -u postgres psql
CREATE DATABASE mutt;
CREATE USER mutt_app WITH PASSWORD 'your-secure-password';
GRANT ALL PRIVILEGES ON DATABASE mutt TO mutt_app;
\q

# 2. Apply schema
sudo -u postgres psql -d mutt -f mutt_schema_v2.1.sql

# 3. Create initial partitions (for current and next 2 months)
sudo -u postgres psql -d mutt
SELECT create_monthly_partition('2025-11-01');
SELECT create_monthly_partition('2025-12-01');
SELECT create_monthly_partition('2026-01-01');
\q

# 4. Verify
sudo -u postgres psql -d mutt -c "\d+ alert_rules"
sudo -u postgres psql -d mutt -c "SELECT * FROM alert_rules;"
```

#### Phase 2: Vault Setup
```bash
# 1. Enable AppRole auth
vault auth enable approle

# 2. Create policy for MUTT
vault policy write mutt-policy - <<EOF
path "secret/data/mutt" {
  capabilities = ["read", "list"]
}
EOF

# 3. Create AppRole
vault write auth/approle/role/mutt \
    token_policies="mutt-policy" \
    token_ttl=768h \
    token_max_ttl=768h

# 4. Get Role ID
vault read auth/approle/role/mutt/role-id
# Save this as VAULT_ROLE_ID in mutt.env

# 5. Generate Secret ID
vault write -f auth/approle/role/mutt/secret-id
# Save this to /etc/mutt/secrets/vault_secret_id

# 6. Store secrets
vault kv put secret/mutt \
    REDIS_PASS="your-redis-password" \
    DB_PASS="your-db-password" \
    INGEST_API_KEY="generate-random-key-here" \
    WEBUI_API_KEY="generate-random-key-here" \
    MOOG_API_KEY="moog-provided-key"

# 7. Verify
vault kv get secret/mutt
```

#### Phase 3: Application Deployment
```bash
# 1. Run deployment script
sudo ./deploy_mutt_v2.3.sh

# 2. When prompted:
#    - Enter Redis host/port
#    - Enter PostgreSQL host/port
#    - Enter Vault host/port
#    - Confirm connectivity checks
#    - Do NOT start services yet

# 3. Edit configuration
sudo nano /etc/mutt/mutt.env
# Fill in all values, especially:
#   - VAULT_ROLE_ID (from Vault setup step 4)
#   - MOOG_WEBHOOK_URL
#   - DB_PASS (if not using Vault fallback)

# 4. Add Vault Secret ID
sudo nano /etc/mutt/secrets/vault_secret_id
# Paste the Secret ID from Vault setup step 5

# 5. Copy TLS certificates
sudo cp /path/to/ca.pem /etc/mutt/certs/
sudo cp /path/to/server.crt /etc/mutt/certs/
sudo cp /path/to/server.key /etc/mutt/certs/
sudo chown mutt:mutt /etc/mutt/certs/*
sudo chmod 644 /etc/mutt/certs/*.pem /etc/mutt/certs/*.crt
sudo chmod 600 /etc/mutt/certs/*.key

# 6. Set correct permissions
sudo chown -R mutt:mutt /opt/mutt
sudo chown -R mutt:mutt /etc/mutt
sudo chmod 600 /etc/mutt/mutt.env
sudo chmod 600 /etc/mutt/secrets/vault_secret_id
```

#### Phase 4: rsyslog Configuration
```bash
# 1. Copy rsyslog config
sudo cp 99-mutt.conf /etc/rsyslog.d/

# 2. Get Ingestor API key from Vault
INGEST_KEY=$(vault kv get -field=INGEST_API_KEY secret/mutt)

# 3. Replace placeholder in config
sudo sed -i "s/REPLACE_WITH_ACTUAL_KEY/$INGEST_KEY/g" /etc/rsyslog.d/99-mutt.conf

# 4. Set permissions
sudo chmod 600 /etc/rsyslog.d/99-mutt.conf
sudo chown root:root /etc/rsyslog.d/99-mutt.conf

# 5. Validate syntax
sudo rsyslogd -N1 -f /etc/rsyslog.d/99-mutt.conf

# 6. Create log directory
sudo mkdir -p /var/log/mutt
sudo chown syslog:adm /var/log/mutt

# 7. Restart rsyslog (but don't test yet - MUTT services not running)
sudo systemctl restart rsyslog
sudo journalctl -u rsyslog -n 50 --no-pager
```

#### Phase 5: Service Startup
```bash
# 1. Reload systemd
sudo systemctl daemon-reload

# 2. Start services one by one
sudo systemctl start mutt-ingestor.service
sleep 3
sudo systemctl status mutt-ingestor.service

sudo systemctl start mutt-alerter.service
sleep 3
sudo systemctl status mutt-alerter.service

sudo systemctl start mutt-moog-forwarder.service
sleep 3
sudo systemctl status mutt-moog-forwarder.service

sudo systemctl start mutt-webui.service
sleep 3
sudo systemctl status mutt-webui.service

# 3. Check health endpoints
curl http://localhost:8080/health
curl http://localhost:8081/health
curl http://localhost:8083/health
curl http://localhost:8090/health

# 4. Check logs for errors
journalctl -u mutt-ingestor.service -n 100 --no-pager
journalctl -u mutt-alerter.service -n 100 --no-pager
journalctl -u mutt-moog-forwarder.service -n 100 --no-pager
journalctl -u mutt-webui.service -n 100 --no-pager

# 5. If all healthy, enable auto-start
sudo systemctl enable mutt-ingestor.service
sudo systemctl enable mutt-alerter.service
sudo systemctl enable mutt-moog-forwarder.service
sudo systemctl enable mutt-webui.service
```

#### Phase 6: Verification Testing
```bash
# 1. Test Ingestor directly
curl -X POST http://localhost:8080/ingest \
  -H "X-API-KEY: $(vault kv get -field=INGEST_API_KEY secret/mutt)" \
  -H "Content-Type: application/json" \
  -d '{"test": "message", "hostname": "test-host", "message": "TEST MESSAGE"}'

# Expected: {"status": "queued"}

# 2. Check Redis queue
redis-cli LLEN mutt:ingest_queue
# Should show 1

# 3. Wait 5 seconds for Alerter to process
sleep 5

# 4. Check queue again (should be 0)
redis-cli LLEN mutt:ingest_queue

# 5. Check PostgreSQL audit log
sudo -u postgres psql -d mutt -c "SELECT * FROM event_audit_log ORDER BY id DESC LIMIT 5;"

# 6. Test via rsyslog
logger -p local5.warning -t snmptrapd "TEST SNMP TRAP"
logger -p user.error "TEST SYSLOG MESSAGE"

# 7. Check metrics
curl http://localhost:8080/metrics | grep mutt_ingest_requests_total

# 8. Access Web UI
# Open browser: http://<server-ip>:8090
# Use WEBUI_API_KEY from Vault
```

---

## Testing Strategy

### Unit Testing (Not Yet Implemented)

**Recommended Framework:** pytest

**Test Files to Create:**
```
tests/
├── test_ingestor_unit.py
├── test_alerter_unit.py
├── test_moog_forwarder_unit.py
├── test_web_ui_unit.py
├── conftest.py             # Fixtures
└── requirements-test.txt
```

**Example Test Cases:**

```python
# tests/test_alerter_unit.py
import pytest
from unittest.mock import MagicMock, patch

def test_rule_matching_contains():
    """Test that 'contains' match type works correctly"""
    rule = {
        'match_string': 'ERROR',
        'match_type': 'contains',
        'priority': 10
    }
    message = {'message': 'An ERROR occurred in module X'}

    result = match_rule(rule, message)
    assert result is True

def test_rule_matching_regex():
    """Test regex matching"""
    rule = {
        'match_string': r'LINK-(UP|DOWN)',
        'match_type': 'regex',
        'priority': 5
    }
    message = {'message': 'Interface eth0: LINK-DOWN'}

    result = match_rule(rule, message)
    assert result is True

def test_unhandled_event_threshold():
    """Test atomic unhandled event detection"""
    # Mock Redis
    with patch('redis.Redis') as mock_redis:
        # ... test logic
        pass
```

**Run Tests:**
```bash
cd /opt/mutt
source venv/bin/activate
pip install pytest pytest-cov pytest-mock
pytest tests/ -v --cov=. --cov-report=html
```

---

### Integration Testing (Not Yet Implemented)

**Recommended Approach:** docker-compose

**File to Create:** `docker-compose.test.yml`

```yaml
version: '3.8'
services:
  redis:
    image: redis:7-alpine
    ports: ["6379:6379"]

  postgres:
    image: postgres:14-alpine
    environment:
      POSTGRES_DB: mutt
      POSTGRES_USER: mutt_app
      POSTGRES_PASSWORD: test123
    volumes:
      - ./mutt_schema_v2.1.sql:/docker-entrypoint-initdb.d/01-schema.sql

  vault:
    image: vault:1.13
    environment:
      VAULT_DEV_ROOT_TOKEN_ID: root
      VAULT_DEV_LISTEN_ADDRESS: 0.0.0.0:8200
    cap_add: [IPC_LOCK]

  ingestor:
    build: .
    command: python3 ingestor_service.py
    depends_on: [redis, vault]
    environment:
      REDIS_HOST: redis
      VAULT_ADDR: http://vault:8200
      # ... more env vars

  alerter:
    build: .
    command: python3 services/alerter_service.py
    depends_on: [redis, postgres, vault]
```

**Run Integration Tests:**
```bash
docker-compose -f docker-compose.test.yml up -d
sleep 10
python3 tests/integration/test_end_to_end.py
docker-compose -f docker-compose.test.yml down
```

---

### Load Testing (Not Yet Implemented)

**Goal:** Determine maximum sustainable EPS (Events Per Second)

**Recommended Tool:** Apache Bench (ab) or custom Python script

**Test Script Example:**
```python
# tests/load/flood_test.py
import requests
import time
from concurrent.futures import ThreadPoolExecutor

INGESTOR_URL = "http://localhost:8080/ingest"
API_KEY = "your-test-key"
NUM_MESSAGES = 100000
NUM_THREADS = 10

def send_message(i):
    payload = {
        "timestamp": time.strftime("%Y-%m-%dT%H:%M:%SZ"),
        "message": f"Load test message {i}",
        "hostname": f"test-host-{i % 100}",
        "syslog_severity": 3
    }
    response = requests.post(
        INGESTOR_URL,
        json=payload,
        headers={"X-API-KEY": API_KEY}
    )
    return response.status_code

start = time.time()
with ThreadPoolExecutor(max_workers=NUM_THREADS) as executor:
    results = list(executor.map(send_message, range(NUM_MESSAGES)))

duration = time.time() - start
eps = NUM_MESSAGES / duration

print(f"Sent {NUM_MESSAGES} messages in {duration:.2f}s")
print(f"Rate: {eps:.2f} EPS")
print(f"Success: {results.count(200)}")
print(f"Failures: {len(results) - results.count(200)}")
```

**Metrics to Monitor:**
- Ingestor: `mutt_ingest_requests_total{status="success"}`
- Redis: Queue depth, memory usage
- Alerter: Processing latency, database write latency
- PostgreSQL: Connection count, query duration

**Expected Performance (estimated):**
- Single Ingestor pod: ~1,000-2,000 EPS
- Single Alerter pod: ~500-1,000 EPS (bottleneck: DB writes)
- System bottleneck: Likely PostgreSQL writes to event_audit_log

---

### Chaos Testing (Not Yet Implemented)

**Scenarios to Test:**

1. **Redis Crash During Processing**
   - Kill Redis container
   - Verify: Services detect failure, log errors, retry
   - Restart Redis
   - Verify: Services reconnect, janitor recovers orphaned messages

2. **Alerter Crash Mid-Processing**
   - Kill Alerter pod while processing messages
   - Verify: Messages remain in `alerter_processing:<pod_name>` list
   - Start new Alerter pod
   - Verify: Janitor recovers messages to main queue

3. **Network Partition**
   - Block traffic between Alerter and PostgreSQL
   - Verify: Alerter logs errors, message stays in processing list
   - Restore network
   - Verify: Processing resumes

4. **Vault Token Expiry**
   - Set Vault token TTL to 5 minutes
   - Wait for expiry
   - Verify: Background renewal thread renews token before services fail

---

## Next Steps

### Immediate Actions (Before Production)

1. **Deploy to Test Environment** ⏰ Priority: Critical
   - Follow Phase 1-6 of Deployment Steps
   - Validate all services start successfully
   - Verify health endpoints

2. **Create Test Alert Rules** ⏰ Priority: High
   ```sql
   INSERT INTO alert_rules (match_string, match_type, priority, prod_handling, dev_handling, team_assignment)
   VALUES
       ('CRITICAL', 'contains', 10, 'Page_and_ticket', 'Ticket_only', 'NETO'),
       ('LINK-DOWN', 'contains', 5, 'Page_and_ticket', 'Ignore', 'NetOps');
   ```

3. **Generate TLS Certificates** ⏰ Priority: High
   ```bash
   # Self-signed for testing
   openssl req -x509 -newkey rsa:4096 -nodes \
       -keyout /etc/mutt/certs/server.key \
       -out /etc/mutt/certs/server.crt \
       -days 365 -subj "/CN=localhost"
   ```

4. **Run End-to-End Test** ⏰ Priority: Critical
   - Send test syslog via rsyslog
   - Verify message appears in event_audit_log
   - Check if matching rule triggers Moog webhook

5. **Monitor for 24 Hours** ⏰ Priority: High
   - Watch all service logs
   - Monitor Prometheus metrics
   - Check for memory leaks, connection leaks

---

### Short-Term Enhancements (1-2 weeks)

6. **Implement Unit Tests** ⏰ Priority: Medium
   - Write pytest tests for all core functions
   - Target: >80% code coverage
   - Integrate into CI/CD pipeline

7. **Set Up Prometheus + Grafana** ⏰ Priority: Medium
   - Configure Prometheus to scrape all MUTT services
   - Create Grafana dashboards:
     - Ingestion rates (1m, 1h, 24h)
     - Queue depths (ingest, alert, DLQ)
     - Processing latency
     - Error rates by type
     - Moog forward success/failure rates

8. **Create Partition Maintenance Cron** ⏰ Priority: Low
   ```bash
   # /etc/cron.monthly/mutt-partition-create
   #!/bin/bash
   # Create partition for 2 months ahead
   FUTURE_DATE=$(date -d "+2 months" +%Y-%m-01)
   sudo -u postgres psql -d mutt -c "SELECT create_monthly_partition('$FUTURE_DATE');"
   ```

9. **Document Runbook** ⏰ Priority: Medium
   - Service startup/shutdown procedures
   - Troubleshooting common issues
   - Incident response playbook
   - On-call escalation paths

---

### Medium-Term Enhancements (1-3 months)

10. **Implement Integration Tests** ⏰ Priority: Low
    - Create docker-compose test environment
    - Automate end-to-end testing

11. **Performance Tuning** ⏰ Priority: Medium
    - Run load tests to find bottlenecks
    - Optimize database queries (add indexes if needed)
    - Tune PostgreSQL (shared_buffers, work_mem)
    - Tune Redis (maxmemory, eviction policy)

12. **High Availability Setup** ⏰ Priority: High
    - Configure Redis Sentinel (3-node cluster)
    - Configure PostgreSQL streaming replication (Patroni)
    - Implement Vault HA cluster
    - Test failover scenarios

13. **Security Hardening** ⏰ Priority: High
    - Third-party security audit
    - Implement SELinux custom policy
    - Network segmentation (VLANs, firewall rules)
    - Rotate secrets in Vault
    - Set up audit logging (Vault, PostgreSQL)

14. **Add Alerting** ⏰ Priority: High
    ```yaml
    # Prometheus alerts to add
    - alert: MUTTIngestQueueFull
      expr: mutt_ingest_queue_depth > 900000
      for: 5m
      annotations:
        summary: "MUTT ingest queue near capacity"

    - alert: MUTTAlerterDown
      expr: up{job="mutt-alerter"} == 0
      for: 2m
      annotations:
        summary: "MUTT Alerter service is down"

    - alert: MUTTMoogForwardFailures
      expr: rate(mutt_moog_requests_total{status="fail"}[5m]) > 0.1
      for: 5m
      annotations:
        summary: "High Moog forward failure rate"
    ```

---

### Long-Term Enhancements (3-6 months)

15. **Migrate to OpenShift** ⏰ Priority: Low (if required)
    - Create Helm charts
    - Use OCP Operators for Redis, PostgreSQL, Vault
    - Implement Horizontal Pod Autoscaler (HPA)
    - Set up OCP Routes with TLS

16. **Machine Learning Integration** ⏰ Priority: Low
    - Anomaly detection on ingestion rates
    - Auto-tuning of unhandled event thresholds
    - Predictive alerting

17. **Advanced Features** ⏰ Priority: Low
    - Message enrichment (GeoIP, asset inventory lookup)
    - Dynamic rule updates via Web UI (without restart)
    - Multi-tenancy support (team-based isolation)
    - Export audit logs to S3/object storage for long-term retention

---

## Technical Debt and Future Enhancements

### Current Technical Debt

1. **No Automated Partition Management**
   - **Impact:** Admin must remember to create partitions monthly
   - **Effort:** Low (create cron job)
   - **Priority:** Medium

2. **Hardcoded Retry Delays**
   - **Impact:** Can't adjust retry behavior without code change
   - **Effort:** Low (move to config)
   - **Priority:** Low

3. **No Circuit Breaker Pattern**
   - **Impact:** If Moog is down for hours, forwarder keeps retrying uselessly
   - **Effort:** Medium (implement circuit breaker library)
   - **Priority:** Medium

4. **No Graceful Shutdown**
   - **Impact:** SIGTERM kills services immediately, mid-processing messages may be lost
   - **Effort:** Medium (implement signal handlers)
   - **Priority:** High

5. **Metrics Not Persisted**
   - **Impact:** Prometheus scrapes are lost if Prometheus is down
   - **Effort:** Low (use Prometheus remote write)
   - **Priority:** Low

---

### Future Enhancements

#### Feature Request #1: Real-Time Rule Updates
**Description:** Allow Web UI to update alert_rules, and have Alerter reload cache without restart

**Implementation:**
- Add `POST /api/v1/cache/reload` endpoint to Alerter
- Web UI calls this after rule changes
- Alerter reloads cache via signal or HTTP trigger

**Effort:** Medium (2-3 days)

---

#### Feature Request #2: Message Deduplication
**Description:** Prevent duplicate events within a time window (e.g., same message from same host within 60s)

**Implementation:**
- Use Redis SET with TTL
- Key: `mutt:dedup:hash(hostname + message)`
- If key exists, drop message; else, process and create key

**Effort:** Low (1 day)

---

#### Feature Request #3: Regex Testing Tool
**Description:** Web UI tool to test regex patterns against sample messages before creating rules

**Implementation:**
- Add `/api/v1/test-regex` POST endpoint
- Input: `{"pattern": "LINK-(UP|DOWN)", "message": "eth0 LINK-DOWN"}`
- Output: `{"match": true, "groups": ["DOWN"]}`

**Effort:** Low (1 day)

---

#### Feature Request #4: Correlation Engine
**Description:** Detect event sequences (e.g., LINK-DOWN followed by LINK-UP within 5 minutes = flapping)

**Implementation:**
- New service: Correlation Engine
- Subscribes to `alert_queue` via BRPOPLPUSH
- Maintains time-window state machine
- Publishes correlated events to new queue

**Effort:** High (2-3 weeks)

---

## Key Decisions Log

### Decision #1: BRPOPLPUSH vs Streams
**Date:** 2025-11-08
**Context:** How to implement reliable message queuing in Redis
**Options:**
1. Lists with BRPOPLPUSH
2. Redis Streams with consumer groups

**Decision:** Lists with BRPOPLPUSH
**Rationale:**
- Simpler implementation
- v2.1 architecture already specifies this pattern
- Redis Streams requires Redis 5.0+ (not guaranteed in enterprise RHEL repos)
- Proven pattern in production systems

**Trade-offs:**
- Streams offer better features (ACKs, consumer groups, message IDs)
- Lists have no built-in message deduplication

---

### Decision #2: Lua Scripts vs Transactions
**Date:** 2025-11-08
**Context:** How to implement atomic operations in Redis
**Options:**
1. MULTI/EXEC transactions
2. Lua scripts

**Decision:** Lua scripts
**Rationale:**
- Lua scripts are atomic and executed on server (no round-trips)
- MULTI/EXEC requires all operations known upfront (can't branch)
- Lua allows conditional logic (e.g., "if count == threshold then RENAME")

**Trade-offs:**
- Lua scripts are harder to debug
- Script changes require service restart (scripts compiled on first use)

---

### Decision #3: Gunicorn vs uWSGI
**Date:** 2025-11-08
**Context:** Which WSGI server to use for Flask apps
**Options:**
1. Gunicorn
2. uWSGI
3. Flask development server

**Decision:** Gunicorn
**Rationale:**
- Simpler configuration than uWSGI
- Better documentation and community support
- Native systemd integration (Type=notify)
- Flask dev server not suitable for production

**Trade-offs:**
- uWSGI has more advanced features (async workers, caching)
- Gunicorn only supports sync workers for Flask

---

### Decision #4: Single Web UI vs Separate CRUD API
**Date:** 2025-11-08
**Context:** Should Web UI be just a dashboard or full CRUD interface?
**Options:**
1. Metrics dashboard only (original design)
2. Full CRUD API + dashboard

**Decision:** Full CRUD API + dashboard
**Rationale:**
- Operators need to manage rules, dev hosts, teams without database access
- REST API allows integration with other tools (Ansible, Terraform)
- Security: Database credentials not needed for operators

**Trade-offs:**
- More code to maintain
- Need to implement authentication for write operations

---

### Decision #5: TLS Everywhere
**Date:** 2025-11-08
**Context:** v2.1 architecture requires TLS, original rsyslog config had useHttps="off"
**Options:**
1. TLS disabled for localhost communication (simpler)
2. TLS for all communication (architecture requirement)

**Decision:** TLS everywhere
**Rationale:**
- Follows v2.1 architecture specification
- Defense in depth (even localhost traffic encrypted)
- Prevents credential sniffing if server is compromised

**Trade-offs:**
- More complex setup (certificate management)
- Slight performance overhead

---

## Troubleshooting Guide

### Service Won't Start

#### Symptom: `mutt-ingestor.service` fails immediately
**Check:**
```bash
journalctl -u mutt-ingestor.service -n 50 --no-pager
```

**Common Causes:**

1. **Vault authentication failed**
   ```
   ERROR: FATAL: Failed to fetch secrets from Vault: 401 Unauthorized
   ```
   **Fix:** Verify Vault Secret ID file exists and is correct
   ```bash
   cat /etc/mutt/secrets/vault_secret_id
   # Should show actual Secret ID, not "REPLACE_WITH_VAULT_SECRET_ID"
   ```

2. **Redis connection failed**
   ```
   ERROR: FATAL: Could not connect to Redis
   ```
   **Fix:** Check Redis is running and reachable
   ```bash
   redis-cli -h $REDIS_HOST -p $REDIS_PORT ping
   # Should return PONG
   ```

3. **Python module not found**
   ```
   ModuleNotFoundError: No module named 'hvac'
   ```
   **Fix:** Verify virtual environment has all dependencies
   ```bash
   /opt/mutt/venv/bin/pip list | grep hvac
   # If missing:
   /opt/mutt/venv/bin/pip install hvac
   ```

4. **Permission denied**
   ```
   PermissionError: [Errno 13] Permission denied: '/etc/mutt/mutt.env'
   ```
   **Fix:** Check file ownership and permissions
   ```bash
   ls -la /etc/mutt/mutt.env
   # Should be: -rw------- mutt mutt
   sudo chown mutt:mutt /etc/mutt/mutt.env
   sudo chmod 600 /etc/mutt/mutt.env
   ```

---

#### Symptom: `mutt-alerter.service` fails on startup
**Check:**
```bash
journalctl -u mutt-alerter.service -n 50 --no-pager
```

**Common Causes:**

1. **PostgreSQL connection failed**
   ```
   ERROR: FATAL: Failed to connect to PostgreSQL
   ```
   **Fix:** Verify database credentials and connectivity
   ```bash
   psql -h $DB_HOST -p $DB_PORT -U mutt_app -d mutt -c "SELECT 1;"
   ```

2. **Schema not initialized**
   ```
   ERROR: relation "alert_rules" does not exist
   ```
   **Fix:** Apply database schema
   ```bash
   sudo -u postgres psql -d mutt -f mutt_schema_v2.1.sql
   ```

3. **Janitor finds too many orphaned lists**
   ```
   WARNING: Found 100 orphaned processing lists
   ```
   **Fix:** This is normal after a crash. Wait for janitor to complete.
   ```bash
   # Monitor progress
   journalctl -u mutt-alerter.service -f
   ```

---

### Messages Not Processing

#### Symptom: Queue keeps growing, Alerter not processing
**Check:**
```bash
redis-cli LLEN mutt:ingest_queue
# If > 0 and growing:
```

**Common Causes:**

1. **Alerter service not running**
   ```bash
   systemctl status mutt-alerter.service
   # If not active:
   sudo systemctl start mutt-alerter.service
   ```

2. **Alerter stuck in infinite loop**
   ```bash
   journalctl -u mutt-alerter.service -n 100 --no-pager | grep ERROR
   # Look for repeated errors
   ```

3. **Database write failures**
   ```
   ERROR: Failed to insert audit log: connection already closed
   ```
   **Fix:** Check PostgreSQL connection pool
   ```bash
   # Restart Alerter to reset pool
   sudo systemctl restart mutt-alerter.service
   ```

---

#### Symptom: Messages processed but not in event_audit_log
**Check:**
```bash
sudo -u postgres psql -d mutt -c "SELECT COUNT(*) FROM event_audit_log;"
```

**Common Causes:**

1. **No matching rules**
   - Message doesn't match any alert_rule
   - Check if rules exist:
   ```bash
   sudo -u postgres psql -d mutt -c "SELECT * FROM alert_rules WHERE is_active = true;"
   ```

2. **Partition doesn't exist**
   ```
   ERROR: no partition of relation "event_audit_log" found for row
   ```
   **Fix:** Create partition for current month
   ```bash
   sudo -u postgres psql -d mutt -c "SELECT create_monthly_partition(CURRENT_DATE);"
   ```

---

### Web UI Issues

#### Symptom: Dashboard shows no data
**Check browser console:** F12 → Console tab

**Common Causes:**

1. **CORS or authentication error**
   ```
   Failed to load resource: 401 Unauthorized
   ```
   **Fix:** API key not provided or incorrect
   - Check if `?api_key=XXX` is in URL
   - Verify key matches Vault secret

2. **Redis connection failed**
   - Web UI can't fetch metrics from Redis
   ```bash
   journalctl -u mutt-webui.service -n 50 --no-pager | grep Redis
   ```

3. **Chart.js not loading**
   - Check CDN URL is reachable
   ```bash
   curl -I https://cdn.jsdelivr.net/npm/chart.js@4.4.0/dist/chart.umd.min.js
   # Should return 200 OK
   ```

---

### Moog Forwarder Issues

#### Symptom: Alerts not reaching Moog
**Check:**
```bash
redis-cli LLEN mutt:alert_queue
# If > 0:
redis-cli LLEN mutt:moog_dead_letter_queue
# If > 0, check DLQ messages
```

**Common Causes:**

1. **Moog webhook URL incorrect**
   ```bash
   # Check logs
   journalctl -u mutt-moog-forwarder.service -n 100 --no-pager | grep "Moog webhook"
   ```

2. **Moog API key invalid**
   ```
   ERROR: Moog returned 401 Unauthorized
   ```
   **Fix:** Verify API key in Vault
   ```bash
   vault kv get -field=MOOG_API_KEY secret/mutt
   ```

3. **Rate limiting**
   ```
   INFO: Rate limit reached, waiting...
   ```
   **Fix:** This is normal. Increase MOOG_RATE_LIMIT if Moog allows higher rates.

4. **Messages in DLQ**
   ```bash
   redis-cli LRANGE mutt:moog_dead_letter_queue 0 -1
   # Inspect failed messages
   ```
   **Fix:** Determine why Moog rejected (4xx errors), fix data format, re-push

---

### Performance Issues

#### Symptom: High CPU usage
**Check:**
```bash
top -u mutt
# Look for process consuming >80% CPU
```

**Common Causes:**

1. **Regex matching in Alerter**
   - Complex regex patterns are CPU-intensive
   - **Fix:** Use `contains` match type where possible
   - Optimize regex patterns

2. **Tight loop without sleep**
   - Forwarder retrying too quickly
   - **Fix:** Check MOOG_RETRY_BASE_DELAY is set (default: 1)

---

#### Symptom: High memory usage
**Check:**
```bash
ps aux | grep mutt
# Look at RSS column
```

**Common Causes:**

1. **Rule cache too large**
   - Thousands of alert rules loaded in memory
   - **Fix:** This is expected. Monitor for leaks (memory growing over time)

2. **Connection pool leak**
   - Connections not returned to pool
   - **Fix:** Restart service, check for Python exceptions

3. **Redis queue backup**
   - Millions of messages in queue
   - **Fix:** Scale Alerter horizontally or increase processing speed

---

### rsyslog Issues

#### Symptom: rsyslog not starting
**Check:**
```bash
sudo systemctl status rsyslog
journalctl -u rsyslog -n 50 --no-pager
```

**Common Causes:**

1. **Syntax error in config**
   ```
   error during parsing file /etc/rsyslog.d/99-mutt.conf
   ```
   **Fix:** Validate syntax
   ```bash
   sudo rsyslogd -N1 -f /etc/rsyslog.d/99-mutt.conf
   ```

2. **Port 514 already in use**
   ```
   imudp: error during config processing: could not bind socket
   ```
   **Fix:** Check for conflicting services
   ```bash
   sudo lsof -i :514
   ```

---

#### Symptom: Messages not reaching Ingestor
**Check:**
```bash
tail -f /var/log/mutt/rsyslog_http_errors.log
```

**Common Causes:**

1. **Ingestor not running**
   ```bash
   systemctl status mutt-ingestor.service
   ```

2. **API key mismatch**
   ```
   HTTP error 401: Unauthorized
   ```
   **Fix:** Verify API key in rsyslog config matches Vault secret
   ```bash
   grep X-API-KEY /etc/rsyslog.d/99-mutt.conf
   vault kv get -field=INGEST_API_KEY secret/mutt
   # Should match
   ```

3. **TLS certificate error**
   ```
   certificate verify failed
   ```
   **Fix:** Check CA cert path
   ```bash
   ls -la /etc/mutt/certs/ca.pem
   # Should exist and be readable
   ```

---

## Appendix

### Environment Variables Reference

#### Ingestor Service (16 variables)
| Variable | Default | Description |
|----------|---------|-------------|
| `SERVER_PORT_INGESTOR` | 8080 | HTTP port |
| `REDIS_HOST` | localhost | Redis hostname |
| `REDIS_PORT` | 6379 | Redis port |
| `REDIS_TLS_ENABLED` | true | Enable TLS for Redis |
| `REDIS_TLS_CA_CERT` | /etc/mutt/certs/ca.pem | CA certificate path |
| `INGEST_QUEUE_NAME` | mutt:ingest_queue | Redis queue name |
| `MAX_INGEST_QUEUE_SIZE` | 1000000 | Max queue depth (backpressure) |
| `METRICS_PREFIX` | mutt:metrics | Redis key prefix for Web UI metrics |
| `VAULT_ADDR` | (required) | Vault URL |
| `VAULT_ROLE_ID` | (required) | AppRole Role ID |
| `VAULT_SECRET_ID_FILE` | /etc/mutt/secrets/vault_secret_id | Secret ID file path |
| `VAULT_SECRETS_PATH` | secret/mutt | Vault KV path |
| `VAULT_TOKEN_RENEW_THRESHOLD` | 3600 | Renew token when TTL < this (seconds) |
| `REDIS_POOL_MIN_CONN` | 2 | Min Redis connections |
| `REDIS_POOL_MAX_CONN` | 10 | Max Redis connections |

#### Alerter Service (30+ variables)
| Variable | Default | Description |
|----------|---------|-------------|
| `SERVER_PORT_ALERTER` | 8081 | Health endpoint port |
| `SERVER_PORT_ALERTER_METRICS` | 8082 | Prometheus metrics port |
| `REDIS_HOST` | localhost | Redis hostname |
| `REDIS_PORT` | 6379 | Redis port |
| `REDIS_TLS_ENABLED` | true | Enable TLS for Redis |
| `INGEST_QUEUE_NAME` | mutt:ingest_queue | Source queue |
| `ALERT_QUEUE_NAME` | mutt:alert_queue | Destination queue (for Moog) |
| `ALERTER_POD_NAME` | mutt-alerter-01 | Unique pod identifier |
| `ALERTER_HEARTBEAT_INTERVAL` | 30 | Heartbeat frequency (seconds) |
| `ALERTER_RULE_CACHE_REFRESH_INTERVAL` | 300 | Cache refresh (seconds) |
| `UNHANDLED_EVENT_THRESHOLD` | 100 | Meta-alert threshold |
| `UNHANDLED_EVENT_WINDOW` | 3600 | Time window for threshold (seconds) |
| `DB_HOST` | localhost | PostgreSQL hostname |
| `DB_PORT` | 5432 | PostgreSQL port |
| `DB_NAME` | mutt | Database name |
| `DB_USER` | mutt_app | Database user |
| `DB_SSL_MODE` | require | SSL mode (disable/allow/prefer/require/verify-ca/verify-full) |
| `DB_SSL_ROOT_CERT` | /etc/mutt/certs/postgres-ca.pem | PostgreSQL CA cert |
| `DB_POOL_MIN_CONN` | 2 | Min PostgreSQL connections |
| `DB_POOL_MAX_CONN` | 10 | Max PostgreSQL connections |
| `VAULT_ADDR` | (required) | Vault URL |
| ... | ... | (see Ingestor for other Vault vars) |

#### Moog Forwarder Service (25+ variables)
| Variable | Default | Description |
|----------|---------|-------------|
| `SERVER_PORT_MOOG_FORWARDER` | 8083 | Health endpoint port |
| `SERVER_PORT_MOOG_METRICS` | 8084 | Prometheus metrics port |
| `REDIS_HOST` | localhost | Redis hostname |
| `ALERT_QUEUE_NAME` | mutt:alert_queue | Source queue |
| `MOOG_WEBHOOK_URL` | (required) | Moog AIOps webhook URL |
| `MOOG_TIMEOUT` | 10 | HTTP timeout (seconds) |
| `MOOG_RATE_LIMIT` | 50 | Max requests per period |
| `MOOG_RATE_PERIOD` | 1 | Rate limit window (seconds) |
| `MOOG_RETRY_BASE_DELAY` | 1 | Base retry delay (seconds) |
| `MOOG_RETRY_MAX_DELAY` | 60 | Max retry delay (seconds) |
| `MOOG_MAX_RETRIES` | 5 | Retries before DLQ |
| `MOOG_POD_NAME` | mutt-moog-01 | Unique pod identifier |
| `MOOG_HEARTBEAT_INTERVAL` | 30 | Heartbeat frequency (seconds) |
| ... | ... | (see Ingestor for Vault/Redis vars) |

#### Web UI Service (15+ variables)
| Variable | Default | Description |
|----------|---------|-------------|
| `SERVER_PORT_WEBUI` | 8090 | HTTP port |
| `REDIS_HOST` | localhost | Redis hostname (for metrics) |
| `METRICS_PREFIX` | mutt:metrics | Redis key prefix |
| `DB_HOST` | localhost | PostgreSQL hostname (for CRUD) |
| ... | ... | (see Alerter for DB vars) |

---

### Prometheus Metrics Reference

#### Ingestor Metrics
```
mutt_ingest_requests_total{status="success|fail_auth|fail_json|fail_queue_full|fail_redis"}
```

#### Alerter Metrics
```
mutt_alerter_messages_processed_total{status="matched|unmatched"}
mutt_alerter_processing_latency_seconds{quantile="0.5|0.9|0.99"}
mutt_alerter_db_write_latency_seconds{quantile="0.5|0.9|0.99"}
mutt_alerter_rule_cache_load_success
mutt_alerter_unhandled_events_total
mutt_ingest_queue_depth
mutt_alert_queue_depth
```

#### Moog Forwarder Metrics
```
mutt_moog_requests_total{status="success|fail|retry"}
mutt_moog_retry_count_total
mutt_moog_dlq_depth
mutt_moog_forward_latency_seconds{quantile="0.5|0.9|0.99"}
mutt_moog_rate_limit_hits_total
```

#### Web UI Metrics
```
(Standard Flask metrics from prometheus-flask-exporter)
flask_http_request_duration_seconds
flask_http_request_total
```

---

### Contact Information

**Project Owner:** (Fill in)
**Lead Developer:** (Fill in)
**On-Call Rotation:** (Fill in)
**Escalation Path:** (Fill in)

---

### Document Revision History

| Version | Date | Changes | Author |
|---------|------|---------|--------|
| 1.0 | 2025-11-08 | Initial handoff document created | AI Assistant |

---

## End of Handoff Document

**This document is intended to be used as a comprehensive handoff to:**
1. New AI assistant in a fresh session
2. Human developer taking over the project
3. Operations team deploying to production
4. Security/compliance auditors

**Files referenced in this document are assumed to exist in the project directory:**
- `ingestor_service.py` (v2.3)
- `services/alerter_service.py` (v2.3)
- `moog_forwarder_service.py` (v2.3)
- `web_ui_service.py` (v2.3)
- `mutt_schema v2.1.sql`
- `99-mutt.conf` (rsyslog config - corrected)
- `snmptrapd.conf`
- `deploy_mutt_v2.3.sh`
- `uninstall_mutt.sh`
- `README.md`

**Status: All development work complete. Ready for deployment testing phase.**
