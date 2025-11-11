# MUTT v2.5 - Quick Reference Specification Sheet

**Purpose:** Condensed technical specifications for quick reference during rebuild
**Use:** Keep this open while implementing - it's your cheat sheet
**Format:** Tables and quick specs only

---

## System Overview

| **Aspect** | **Specification** |
|-----------|------------------|
| **Name** | MUTT (Multi-Use Telemetry Tool) |
| **Version** | 2.5 (Production-Ready) |
| **Architecture** | Microservices with reliable message queuing |
| **Language** | Python 3.10+ |
| **Message Queue** | Redis 6.0+ (Lists + PubSub) |
| **Database** | PostgreSQL 14+ |
| **Secrets** | HashiCorp Vault 1.8+ |
| **Monitoring** | Prometheus + Grafana |
| **Deployment** | RHEL systemd (primary), Kubernetes (secondary) |

---

## Services & Ports

| **Service** | **Purpose** | **Ports** | **Type** | **Scaling** |
|------------|-------------|-----------|----------|-------------|
| **Ingestor** | HTTP ingestion endpoint | 8080 (HTTP) | HTTP | 10K EPS/instance |
| **Alerter** | Core event processing | 8081 (metrics), 8082 (health) | Worker | Queue depth > 5K |
| **Moog Forwarder** | External system integration | 8083 (metrics), 8084 (health) | Worker | Rate limit hits |
| **Web UI** | Management dashboard | 8090 (HTTP) | HTTP | 100 users/instance |
| **Remediation** | DLQ recovery (self-healing) | 8086 (metrics), 8087 (health) | Worker | Single instance |

---

## Redis Queues & Keys

| **Queue/Key** | **Purpose** | **Type** | **Pattern** |
|--------------|-------------|----------|-------------|
| `mutt:ingest_queue` | Main ingestion queue | List | LPUSH/BRPOPLPUSH |
| `mutt:alert_queue` | Alerts to forward | List | LPUSH/BRPOPLPUSH |
| `mutt:processing:alerter:{pod}` | Alerter processing list | List | Atomic processing |
| `mutt:processing:moog:{pod}` | Moog processing list | List | Atomic processing |
| `mutt:dlq:alerter` | Alerter dead letter queue | List | Poison messages |
| `mutt:dlq:moog` | Moog dead letter queue | List | Failed forwards |
| `mutt:heartbeat:alerter:{pod}` | Alerter heartbeat | String | TTL 30s |
| `mutt:heartbeat:moog:{pod}` | Moog heartbeat | String | TTL 30s |
| `mutt:unhandled:{pattern}` | Unmatched event counters | String | INCR, EXPIRE 24h |
| `mutt:config:*` | Dynamic configuration | String | GET/SET |
| `mutt:config:updates` | Config change notifications | PubSub | PUBLISH |
| `mutt:rate_limit:moog` | Shared rate limiter | Sorted Set | Sliding window |
| `mutt:circuit:moog:state` | Circuit breaker state | String | CLOSED/OPEN/HALF_OPEN |
| `mutt:metrics:*` | Metrics caching | String | TTL 5s |

---

## PostgreSQL Tables

| **Table** | **Purpose** | **Partitioned** | **Cached** | **Indexes** |
|----------|-------------|-----------------|------------|-------------|
| `alert_rules` | Rule definitions | No | Yes (5min) | is_active, priority |
| `development_hosts` | Dev host list | No | Yes (5min) | hostname (unique) |
| `device_teams` | Device-to-team mapping | No | Yes (5min) | hostname (unique) |
| `event_audit_log` | Event audit trail | Yes (monthly) | No | hostname, timestamp, correlation_id |
| `config_audit_log` | Config change audit | No | No | timestamp, table_name, operation, changed_by, correlation_id, record_id |

---

## Core Patterns

### BRPOPLPUSH Pattern
```
Purpose: Reliable message processing (no loss on crash)
Redis: BRPOPLPUSH source processing timeout
On success: LREM processing -1 message
On failure: LPUSH dlq message
Recovery: Janitor scans processing lists on startup
```

### Janitor Recovery
```
On Startup:
1. SCAN for mutt:processing:{service}:*
2. For each processing list:
   a. GET mutt:heartbeat:{service}:{pod}
   b. If heartbeat expired (> 30s old):
      - RPOPLPUSH processing source (recover all messages)
3. Delete stale processing list
```

### Circuit Breaker
```
States: CLOSED (normal) → OPEN (failing) → HALF_OPEN (testing)
Open Threshold: 5 consecutive failures
Open Duration: 60 seconds
Half-Open Test: Single request
Redis Keys:
  - mutt:circuit:moog:state (CLOSED/OPEN/HALF_OPEN)
  - mutt:circuit:moog:failures (failure count)
  - mutt:circuit:moog:opened_at (timestamp)
```

### Backpressure (Alerter)
```
Monitor: LLEN mutt:alert_queue
Thresholds:
  - alerter_queue_warn_threshold (default: 1000) → Log warning
  - alerter_queue_shed_threshold (default: 2000) → Shed load
Modes:
  - dlq: RPOP from ingest_queue, LPUSH to mutt:dlq:alerter
  - defer: Sleep alerter_defer_sleep_ms (default: 250ms)
```

### Dynamic Configuration
```
Storage: Redis (mutt:config:{key})
Cache: 5-second local cache
Invalidation: PubSub on mutt:config:updates
Callbacks: Registered functions execute on change
API: GET/SET/DELETE via Web UI
```

### Rate Limiting (Shared)
```
Algorithm: Sliding window (Redis Sorted Set + Lua)
Key: mutt:rate_limit:moog
Window: configurable (default: 1 second)
Limit: configurable (default: 50 requests/sec)
Scope: Shared across all Moog Forwarder instances
Implementation: Lua script (atomic ZREMRANGEBYSCORE + ZADD + ZCARD)
```

---

## Environment Variables

### Global (All Services)

| **Variable** | **Default** | **Purpose** |
|-------------|-------------|-------------|
| `LOG_LEVEL` | `INFO` | Logging level |
| `LOG_JSON_ENABLED` | `false` | Enable JSON logging |
| `OTEL_ENABLED` | `false` | Enable OpenTelemetry tracing |
| `OTEL_EXPORTER_OTLP_ENDPOINT` | - | OTLP collector endpoint |
| `DYNAMIC_CONFIG_ENABLED` | `false` | Enable dynamic config reads |

### Redis Connection

| **Variable** | **Default** | **Purpose** |
|-------------|-------------|-------------|
| `REDIS_HOST` | `localhost` | Redis hostname |
| `REDIS_PORT` | `6379` | Redis port |
| `REDIS_TLS_ENABLED` | `true` | Use TLS |
| `REDIS_CA_CERT_PATH` | - | TLS CA certificate path |
| `REDIS_MAX_CONNECTIONS` | `20` | Connection pool size |

### PostgreSQL Connection

| **Variable** | **Default** | **Purpose** |
|-------------|-------------|-------------|
| `DB_HOST` | `localhost` | PostgreSQL hostname |
| `DB_PORT` | `5432` | PostgreSQL port |
| `DB_NAME` | `mutt_db` | Database name |
| `DB_USER` | `mutt_user` | Database user |
| `DB_TLS_ENABLED` | `true` | Use TLS |
| `DB_TLS_CA_CERT_PATH` | - | TLS CA certificate path |
| `DB_POOL_MIN_CONN` | `2` | Min connections in pool |
| `DB_POOL_MAX_CONN` | `10` | Max connections in pool |

### Vault Connection

| **Variable** | **Default** | **Purpose** |
|-------------|-------------|-------------|
| `VAULT_ADDR` | - | Vault URL (required) |
| `VAULT_ROLE_ID` | - | AppRole role ID (required) |
| `VAULT_SECRET_ID_FILE` | `/etc/mutt/secrets/vault_secret_id` | Path to secret ID file |
| `VAULT_SECRETS_PATH` | `secret/mutt` | KV path for secrets |
| `VAULT_TOKEN_RENEW_THRESHOLD` | `3600` | Renew when TTL < N seconds |
| `VAULT_RENEW_CHECK_INTERVAL` | `300` | Check token TTL every N seconds |

### Ingestor Service

| **Variable** | **Default** | **Purpose** |
|-------------|-------------|-------------|
| `SERVER_PORT_INGESTOR` | `8080` | HTTP listen port |
| `MAX_INGEST_QUEUE_SIZE` | `1000000` | Queue cap for backpressure |
| `INGEST_QUEUE_NAME` | `mutt:ingest_queue` | Redis queue name |
| `REQUIRED_MESSAGE_FIELDS` | `timestamp,message,hostname` | Required fields for events |

### Alerter Service

| **Variable** | **Default** | **Purpose** |
|-------------|-------------|-------------|
| `POD_NAME` | `alerter-{random}` | Unique worker identifier |
| `METRICS_PORT_ALERTER` | `8081` | Prometheus metrics port |
| `HEALTH_PORT_ALERTER` | `8082` | Health check port |
| `INGEST_QUEUE_NAME` | `mutt:ingest_queue` | Source queue |
| `ALERT_QUEUE_NAME` | `mutt:alert_queue` | Destination queue |
| `ALERTER_PROCESSING_LIST_PREFIX` | `mutt:processing:alerter` | Processing list prefix |
| `ALERTER_HEARTBEAT_PREFIX` | `mutt:heartbeat:alerter` | Heartbeat key prefix |
| `ALERTER_HEARTBEAT_INTERVAL` | `10` | Heartbeat refresh (seconds) |
| `ALERTER_JANITOR_TIMEOUT` | `30` | Heartbeat expiry (seconds) |
| `ALERTER_DLQ_NAME` | `mutt:dlq:alerter` | Dead letter queue name |
| `ALERTER_MAX_RETRIES` | `3` | Max retries before DLQ |
| `BRPOPLPUSH_TIMEOUT` | `5` | BRPOPLPUSH timeout (seconds) |
| `CACHE_RELOAD_INTERVAL` | `300` | Cache refresh interval (seconds) |
| `UNHANDLED_PREFIX` | `mutt:unhandled` | Unhandled counter prefix |
| `UNHANDLED_THRESHOLD` | `100` | Events before meta-alert |
| `UNHANDLED_EXPIRY_SECONDS` | `86400` | Counter expiry (24 hours) |
| `UNHANDLED_DEFAULT_TEAM` | `NETO` | Default team for unhandled |

### Moog Forwarder Service

| **Variable** | **Default** | **Purpose** |
|-------------|-------------|-------------|
| `POD_NAME` | `moog-forwarder-{random}` | Unique worker identifier |
| `METRICS_PORT_MOOG` | `8083` | Prometheus metrics port |
| `HEALTH_PORT_MOOG` | `8084` | Health check port |
| `ALERT_QUEUE_NAME` | `mutt:alert_queue` | Source queue |
| `MOOG_PROCESSING_LIST_PREFIX` | `mutt:processing:moog` | Processing list prefix |
| `MOOG_HEARTBEAT_PREFIX` | `mutt:heartbeat:moog` | Heartbeat key prefix |
| `MOOG_HEARTBEAT_INTERVAL` | `10` | Heartbeat refresh (seconds) |
| `MOOG_JANITOR_TIMEOUT` | `30` | Heartbeat expiry (seconds) |
| `MOOG_DLQ_NAME` | `mutt:dlq:moog` | Dead letter queue name |
| `MOOG_WEBHOOK_URL` | - | Moogsoft webhook URL (required) |
| `MOOG_WEBHOOK_TIMEOUT` | `10` | HTTP request timeout (seconds) |
| `MOOG_RATE_LIMIT` | `50` | Max requests/period (shared) |
| `MOOG_RATE_PERIOD` | `1` | Rate limit window (seconds) |
| `MOOG_RATE_LIMIT_KEY` | `mutt:rate_limit:moog` | Redis rate limiter key |
| `MOOG_MAX_RETRIES` | `5` | Max retries before DLQ |
| `MOOG_RETRY_BASE_DELAY` | `1.0` | Initial retry delay (seconds) |
| `MOOG_RETRY_MAX_DELAY` | `60.0` | Max retry delay (seconds) |

### Web UI Service

| **Variable** | **Default** | **Purpose** |
|-------------|-------------|-------------|
| `SERVER_PORT_WEBUI` | `8090` | HTTP listen port |
| `METRICS_CACHE_TTL` | `5` | Metrics cache TTL (seconds) |
| `AUDIT_LOG_PAGE_SIZE` | `50` | Default pagination size |
| `PROMETHEUS_URL` | `http://localhost:9090` | Prometheus base URL (for SLOs) |

### Remediation Service

| **Variable** | **Default** | **Purpose** |
|-------------|-------------|-------------|
| `POD_NAME` | `remediation-{random}` | Unique worker identifier |
| `METRICS_PORT_REMEDIATION` | `8086` | Prometheus metrics port |
| `HEALTH_PORT_REMEDIATION` | `8087` | Health check port |
| `REMEDIATION_SCAN_INTERVAL` | `60` | DLQ scan interval (seconds) |
| `REMEDIATION_MAX_RETRIES` | `3` | Max replay attempts |
| `REMEDIATION_BACKOFF_BASE` | `60` | Initial backoff (seconds) |

---

## Dynamic Configuration Keys

| **Key** | **Type** | **Default** | **Purpose** |
|---------|----------|-------------|-------------|
| `cache_reload_interval` | int | `300` | Alerter cache refresh (seconds) |
| `max_ingest_queue_size` | int | `100000` | Ingestor queue cap |
| `alerter_queue_warn_threshold` | int | `1000` | Backpressure warning level |
| `alerter_queue_shed_threshold` | int | `2000` | Backpressure shed level |
| `alerter_shed_mode` | str | `dlq` | `dlq` or `defer` |
| `alerter_defer_sleep_ms` | int | `250` | Defer sleep time (milliseconds) |
| `moog_rate_limit` | int | `50` | Rate limit (requests/period) |
| `moog_batch_size` | int | `100` | Batch size for forwarding |
| `slo_window_hours` | int | `24` | SLO evaluation window (hours) |
| `slo_ingest_success_target` | float | `0.995` | Ingestor SLO target (99.5%) |
| `slo_forward_success_target` | float | `0.99` | Forwarder SLO target (99%) |

---

## Prometheus Metrics

### Ingestor (port 8080/metrics)

| **Metric** | **Type** | **Labels** | **Purpose** |
|-----------|----------|-----------|-------------|
| `mutt_ingest_requests_total` | Counter | `status`, `reason` | Total ingestion requests |
| `mutt_ingest_queue_depth` | Gauge | - | Current queue depth |
| `mutt_ingest_latency_seconds` | Histogram | - | Request processing latency |

### Alerter (port 8081/metrics)

| **Metric** | **Type** | **Labels** | **Purpose** |
|-----------|----------|-----------|-------------|
| `mutt_alerter_events_processed_total` | Counter | `status` | Events by status (handled/unhandled/poison/error) |
| `mutt_alerter_processing_latency_seconds` | Histogram | - | Event processing time |
| `mutt_alerter_queue_depth` | Gauge | - | Alert queue depth |
| `mutt_alerter_shed_events_total` | Counter | `mode` | Shed/deferral events |
| `mutt_alerter_cache_rules_count` | Gauge | - | Rules in cache |
| `mutt_alerter_cache_dev_hosts_count` | Gauge | - | Dev hosts in cache |
| `mutt_alerter_cache_teams_count` | Gauge | - | Team mappings in cache |
| `mutt_alerter_dlq_depth` | Gauge | - | Alerter DLQ depth |
| `mutt_alerter_processing_list_depth` | Gauge | - | This worker's processing list depth |
| `mutt_alerter_cache_reload_failures_total` | Counter | - | Failed cache reloads |
| `mutt_db_write_latency_ms` | Histogram | - | Database write latency |

### Moog Forwarder (port 8083/metrics)

| **Metric** | **Type** | **Labels** | **Purpose** |
|-----------|----------|-----------|-------------|
| `mutt_moog_requests_total` | Counter | `status`, `reason` | Moog webhook requests |
| `mutt_moog_request_latency_seconds` | Histogram | - | Webhook request latency |
| `mutt_moog_dlq_depth` | Gauge | - | Moog DLQ depth |
| `mutt_moog_processing_list_depth` | Gauge | - | This worker's processing list depth |
| `mutt_moog_rate_limit_hits_total` | Counter | - | Times rate limit was hit |
| `mutt_moog_alerts_processed_total` | Counter | `status` | Alerts processed (success/dlq/error) |
| `mutt_moog_circuit_state` | Gauge | - | Circuit breaker state (0=CLOSED, 1=OPEN, 2=HALF_OPEN) |

### Web UI (port 8090/metrics)

| **Metric** | **Type** | **Labels** | **Purpose** |
|-----------|----------|-----------|-------------|
| `mutt_webui_api_requests_total` | Counter | `endpoint`, `status` | API requests |
| `mutt_webui_api_latency_seconds` | Histogram | `endpoint` | API latency |
| `mutt_webui_redis_scan_latency_seconds` | Histogram | - | Redis SCAN latency |
| `mutt_webui_db_query_latency_ms` | Histogram | `operation` | DB query latency |

### Remediation (port 8086/metrics)

| **Metric** | **Type** | **Labels** | **Purpose** |
|-----------|----------|-----------|-------------|
| `mutt_remediation_replayed_total` | Counter | `source`, `status` | Replay attempts (alerter/moog, success/fail) |
| `mutt_remediation_dlq_scan_duration_seconds` | Histogram | - | DLQ scan duration |

---

## API Endpoints

### Ingestor Service (port 8080)

| **Endpoint** | **Method** | **Auth** | **Purpose** |
|-------------|----------|----------|-------------|
| `/api/v2/ingest` | POST | X-API-KEY | Ingest events |
| `/health` | GET | None | Health check |
| `/metrics` | GET | None | Prometheus metrics |

### Alerter Service (ports 8081/8082)

| **Endpoint** | **Method** | **Auth** | **Purpose** |
|-------------|----------|----------|-------------|
| `/health` | GET | None | Health check (port 8082) |
| `/metrics` | GET | None | Prometheus metrics (port 8081) |

### Moog Forwarder Service (ports 8083/8084)

| **Endpoint** | **Method** | **Auth** | **Purpose** |
|-------------|----------|----------|-------------|
| `/health` | GET | None | Health check (port 8084) |
| `/metrics` | GET | None | Prometheus metrics (port 8083) |

### Web UI Service (port 8090)

| **Endpoint** | **Method** | **Auth** | **Purpose** |
|-------------|----------|----------|-------------|
| `/` | GET | API key or session | Dashboard (HTML) |
| `/health` | GET | None | Health check |
| `/metrics` | GET | None | Prometheus metrics |
| `/api/v2/metrics` | GET | X-API-KEY | Real-time EPS metrics (JSON) |
| `/api/v1/slo` | GET | X-API-KEY | Component SLO status |
| `/api/v2/rules` | GET | X-API-KEY | List all alert rules |
| `/api/v2/rules` | POST | X-API-KEY | Create alert rule |
| `/api/v2/rules/{id}` | GET | X-API-KEY | Get specific rule |
| `/api/v2/rules/{id}` | PUT | X-API-KEY | Update rule |
| `/api/v2/rules/{id}` | DELETE | X-API-KEY | Delete rule |
| `/api/v2/audit-logs` | GET | X-API-KEY | Get audit logs (paginated) |
| `/api/v2/config-audit` | GET | X-API-KEY | Get config audit logs |
| `/api/v2/dev-hosts` | GET | X-API-KEY | List dev hosts |
| `/api/v2/dev-hosts` | POST | X-API-KEY | Add dev host |
| `/api/v2/dev-hosts/{hostname}` | DELETE | X-API-KEY | Remove dev host |
| `/api/v2/teams` | GET | X-API-KEY | List team mappings |
| `/api/v2/teams` | POST | X-API-KEY | Add team mapping |
| `/api/v2/teams/{hostname}` | PUT | X-API-KEY | Update team mapping |
| `/api/v2/teams/{hostname}` | DELETE | X-API-KEY | Delete team mapping |

### Remediation Service (ports 8086/8087)

| **Endpoint** | **Method** | **Auth** | **Purpose** |
|-------------|----------|----------|-------------|
| `/health` | GET | None | Health check (port 8087) |
| `/metrics` | GET | None | Prometheus metrics (port 8086) |

---

## Authentication

| **Service** | **Method** | **Header** | **Validation** |
|------------|-----------|-----------|---------------|
| Ingestor | API Key | `X-API-KEY` | Constant-time comparison with `INGEST_API_KEY` from Vault |
| Web UI | API Key or Session | `X-API-KEY` or Cookie | Constant-time comparison with `WEBUI_API_KEY` from Vault |
| Alerter | None | - | Worker service (no HTTP endpoints except metrics/health) |
| Moog Forwarder | None | - | Worker service (no HTTP endpoints except metrics/health) |
| Remediation | None | - | Worker service (no HTTP endpoints except metrics/health) |

---

## Retry & Exponential Backoff

### Alerter Service
```
Max Retries: 3 (ALERTER_MAX_RETRIES)
On failure: Increment retry_count
If retry_count > max_retries: LPUSH mutt:dlq:alerter
Else: RPUSH mutt:ingest_queue (back to start)
```

### Moog Forwarder Service
```
Max Retries: 5 (MOOG_MAX_RETRIES)
Base Delay: 1.0 seconds
Max Delay: 60.0 seconds
Formula: min(base * (2 ^ attempt), max_delay)

Retry Schedule:
- Attempt 1: Wait 1s
- Attempt 2: Wait 2s
- Attempt 3: Wait 4s
- Attempt 4: Wait 8s
- Attempt 5: Wait 16s
- Attempt 6+: Wait 60s (capped)

Smart Retry:
- 5xx errors: Retry
- Timeouts: Retry
- Connection errors: Retry
- 4xx errors: DLQ (no retry)
```

### Remediation Service
```
Max Retries: 3 (REMEDIATION_MAX_RETRIES)
Base Backoff: 60 seconds
Formula: base * attempt

Replay Schedule:
- Attempt 1: Wait 60s
- Attempt 2: Wait 120s
- Attempt 3: Wait 180s
- After max: LPUSH mutt:poison:permanent
```

---

## Required Fields

### Event Message (Ingestor)
```json
{
  "timestamp": "ISO 8601 format, required",
  "message": "string, required",
  "hostname": "string, required",
  "source": "syslog or snmp, optional",
  "syslog_severity": "0-7, optional",
  "trap_oid": "string, optional",
  "correlation_id": "UUID, optional (auto-generated)"
}
```

### Alert Rule (Web UI)
```json
{
  "match_string": "string or null",
  "trap_oid": "string or null",
  "syslog_severity": "integer or null",
  "match_type": "contains|regex|oid_prefix, required",
  "priority": "1-1000, required",
  "prod_handling": "Page_and_ticket|Ticket_only|Email_only|Log_only, required",
  "dev_handling": "Ticket_only|Email_only|Log_only|Suppress, required",
  "team_assignment": "string, required",
  "is_active": "boolean, optional (default true)"
}
```

---

## Data Retention

| **Data Type** | **Active Retention** | **Archive Retention** | **Implementation** |
|--------------|---------------------|----------------------|-------------------|
| Event Audit Logs | 90 days | 7 years | PostgreSQL partitions + archive to S3/NFS |
| Config Audit Logs | Indefinite | N/A | PostgreSQL (no deletion) |
| Metrics (Prometheus) | 15 days | N/A | Prometheus TSDB |
| Redis Queues | Transient | N/A | No persistence needed (AOF for recovery only) |

---

## SLO Targets

| **Component** | **SLO Target** | **Error Budget** | **Burn Rate OK** | **Burn Rate Warning** | **Burn Rate Critical** |
|--------------|----------------|------------------|------------------|----------------------|------------------------|
| Ingestor | 99.5% (0.995) | 0.5% | ≤ 1.0 | ≤ 2.0 | > 2.0 |
| Moog Forwarder | 99% (0.99) | 1.0% | ≤ 1.0 | ≤ 2.0 | > 2.0 |

**Prometheus Queries:**

Ingestor Availability:
```promql
sum(rate(mutt_ingest_requests_total{status="success"}[24h]))
  /
sum(rate(mutt_ingest_requests_total[24h]))
```

Forwarder Availability:
```promql
sum(rate(mutt_moog_requests_total{status="success"}[24h]))
  /
sum(rate(mutt_moog_requests_total[24h]))
```

---

## File Paths

### Services
```
services/ingestor_service.py
services/alerter_service.py
services/moog_forwarder_service.py
services/web_ui_service.py
services/remediation_service.py
services/audit_logger.py
services/dynamic_config.py
services/logging_utils.py
services/tracing_utils.py
services/redis_connector.py
services/postgres_connector.py
services/rate_limiter.py
```

### Database
```
database/mutt_schema_v2.1.sql
database/config_audit_schema.sql
database/partitioned_event_audit_log.sql
```

### Scripts
```
scripts/create_monthly_partitions.py
scripts/archive_old_events.py
scripts/init_dynamic_config.py
scripts/muttdev.py
```

### Deployment
```
systemd/mutt-ingestor.service
systemd/mutt-alerter.service
systemd/mutt-moog-forwarder.service
systemd/mutt-webui.service
systemd/mutt-remediation.service

k8s/ingestor-deployment.yaml
k8s/alerter-deployment.yaml
k8s/moog-forwarder-deployment.yaml
k8s/webui-deployment.yaml
k8s/remediation-deployment.yaml
```

---

## Key Dependencies

```
# Core
flask>=2.0
gunicorn>=20.1
redis>=4.0
psycopg2-binary>=2.9
hvac>=1.0
prometheus-client>=0.12
prometheus-flask-exporter>=0.20
requests>=2.28

# Observability (optional)
opentelemetry-api>=1.24
opentelemetry-sdk>=1.24
opentelemetry-exporter-otlp-proto-grpc>=1.24
opentelemetry-instrumentation-flask
opentelemetry-instrumentation-requests
opentelemetry-instrumentation-redis
opentelemetry-instrumentation-psycopg2

# Testing
pytest>=7.0
pytest-cov>=4.0
pytest-mock>=3.10

# Development
black>=23.0
ruff>=0.1.0
mypy>=1.0
```

---

## Vault Secrets

| **Secret Key** | **Purpose** | **Used By** |
|---------------|-------------|-------------|
| `INGEST_API_KEY` | Ingestor authentication | Ingestor |
| `WEBUI_API_KEY` | Web UI authentication | Web UI |
| `MOOG_API_KEY` | Moogsoft webhook auth | Moog Forwarder |
| `REDIS_PASS_CURRENT` | Current Redis password | All services |
| `REDIS_PASS_NEXT` | Next Redis password (during rotation) | All services |
| `DB_PASS_CURRENT` | Current PostgreSQL password | All services (except Ingestor) |
| `DB_PASS_NEXT` | Next PostgreSQL password (during rotation) | All services (except Ingestor) |

**Vault Path:** `secret/mutt` (configurable via `VAULT_SECRETS_PATH`)

---

## Health Check Response Format

```json
{
  "status": "healthy",
  "redis": "connected",
  "postgres": "connected",
  "timestamp": "2025-11-10T12:00:00Z",
  "queue_depth": 12345,
  "version": "2.5",
  "service": "mutt-alerter"
}
```

**HTTP Codes:**
- `200 OK` - All dependencies healthy
- `503 Service Unavailable` - One or more dependencies unhealthy

---

## systemd Service Template

```ini
[Unit]
Description=MUTT {SERVICE_NAME}
After=network.target redis.service postgresql.service
Wants=redis.service postgresql.service

[Service]
Type=simple
User=mutt
Group=mutt
WorkingDirectory=/opt/mutt
Environment="PATH=/opt/mutt/venv/bin:/usr/local/bin:/usr/bin"
EnvironmentFile=/etc/mutt/mutt.env
ExecStart=/opt/mutt/venv/bin/python /opt/mutt/services/{service_name}_service.py
Restart=on-failure
RestartSec=10s
StandardOutput=journal
StandardError=journal

# Security
NoNewPrivileges=true
ProtectSystem=strict
ProtectHome=true
ReadWritePaths=/opt/mutt /var/log/mutt
PrivateTmp=true

[Install]
WantedBy=multi-user.target
```

---

## Quick Commands

### Redis
```bash
# Check queue depth
redis-cli LLEN mutt:ingest_queue

# View processing lists
redis-cli KEYS "mutt:processing:*"

# View DLQ depth
redis-cli LLEN mutt:dlq:alerter

# View config
redis-cli GET mutt:config:cache_reload_interval

# Set config
redis-cli SET mutt:config:cache_reload_interval 600

# Publish config change
redis-cli PUBLISH mutt:config:updates cache_reload_interval
```

### PostgreSQL
```sql
-- Create partition
SELECT create_monthly_partition('2025-11-01');

-- View partitions
SELECT child.relname FROM pg_inherits
JOIN pg_class parent ON pg_inherits.inhparent = parent.oid
JOIN pg_class child ON pg_inherits.inhrelid = child.oid
WHERE parent.relname = 'event_audit_log';

-- Count events
SELECT COUNT(*) FROM event_audit_log;

-- Recent config changes
SELECT * FROM config_audit_log ORDER BY changed_at DESC LIMIT 10;

-- Active rules
SELECT * FROM alert_rules WHERE is_active = true ORDER BY priority DESC;
```

### systemd
```bash
# Start service
sudo systemctl start mutt-ingestor

# Stop service
sudo systemctl stop mutt-ingestor

# Restart service
sudo systemctl restart mutt-ingestor

# View logs
sudo journalctl -u mutt-ingestor -f

# Reload cache (Alerter only)
sudo kill -HUP $(pgrep -f alerter_service)
```

---

**END OF QUICK REFERENCE**

**Use this alongside:**
- `REBUILD_GUIDE.md` - Implementation instructions
- `docs/architecture/` - Detailed architecture docs
- `docs/operations/` - Operations procedures
