# MUTT - Multi-Use Telemetry Tool

  [![Version](https://img.shields.io/badge/version-2.3-blue.svg)](https://github.com/yourusername/mutt)
  [![License](https://img.shields.io/badge/license-MIT-green.svg)](LICENSE)
  [![Python](https://img.shields.io/badge/python-3.8+-blue.svg)](https://www.python.org/downloads/)

  **MUTT** (Multi-Use Telemetry Tool) is a production-ready, horizontally scalable event processing system for
  syslog and SNMP trap ingestion, intelligent alert routing, and integration with enterprise monitoring platforms
  like Moogsoft.

  ---

  ## 📋 Table of Contents

  - [Overview](#overview)
  - [Architecture](#architecture)
  - [Key Features](#key-features)
  - [Components](#components)
  - [Requirements](#requirements)
  - [Quick Start](#quick-start)
  - [Configuration](#configuration)
    - [Ingestor Service](#ingestor-service-configuration)
    - [Alerter Service](#alerter-service-configuration)
    - [Moog Forwarder Service](#moog-forwarder-service-configuration)
    - [Web UI Service](#web-ui-service-configuration)
  - [API Reference](#api-reference)
  - [Deployment](#deployment)
  - [Monitoring](#monitoring)
  - [Development](#development)
  - [Testing](#testing)
  - [Troubleshooting](#troubleshooting)
  - [Contributing](#contributing)
  - [License](#license)
  - [Observability](#observability)
  - [What’s New in v2.5](#whats-new-in-v25)
  - [API Docs](#api-docs)
  - [Runbook](#runbook)
  - [Dashboards & Alerts](#dashboards--alerts)
  - [Developer CLI](#developer-cli)

  ---

  ## 🎯 Overview

  MUTT provides a robust, fault-tolerant pipeline for processing network events from syslog and SNMP traps. It
  intelligently routes events based on configurable rules, distinguishes between production and development
  environments, and forwards alerts to downstream systems like Moogsoft.

  ### Why MUTT?

  - **Reliability First**: No message loss on crashes (BRPOPLPUSH pattern, Redis AOF, janitor recovery)
  - **Production-Grade**: Vault secrets, TLS encryption, connection pooling, comprehensive metrics
  - **Horizontally Scalable**: All services scale independently with load balancing
  - **Intelligent Routing**: Rule-based alert matching with priority, regex, and environment awareness
  - **Observable**: Prometheus metrics, structured logging, health checks, correlation IDs

  ---

  ## 🏗️ Architecture

  ┌─────────────┐
  │   rsyslog   │ (UDP/TCP Syslog + SNMP Traps)
  └──────┬──────┘
         │ HTTP POST (TLS)
         ▼
  ┌─────────────────────────────────────────────────────────┐
  │              Ingestor Service (Port 8080)                │
  │  - API Key Authentication (constant-time)                │
  │  - Backpressure (Queue Cap + 503)                        │
  │  - Metrics Caching (5s TTL)                              │
  │  - Time-windowed EPS metrics (1m/1h/24h)                 │
  └──────┬──────────────────────────────────────────────────┘
         │ LPUSH
         ▼
  ┌─────────────────────────────────────────────────────────┐
  │                    Redis (HA)                            │
  │  - mutt:ingest_queue (main queue)                        │
  │  - mutt:processing:alerter: (per-worker)            │
  │  - mutt:alert_queue (forwarding queue)                   │
  │  - mutt:processing:moog: (per-worker)               │
  │  - mutt:unhandled:: (counters)               │
  │  - mutt:rate_limit:moog (shared rate limiter)            │
  │  - AOF persistence, Sentinel/Cluster for HA              │
  └──────┬──────────────────────────────────────────────────┘
         │ BRPOPLPUSH (atomic, crash-safe)
         ▼
  ┌─────────────────────────────────────────────────────────┐
  │          Alerter Service (Ports 8081, 8082)              │
  │  - In-Memory Rule Cache (5min refresh + SIGHUP)          │
  │  - Rule Matching: priority, regex, oid_prefix            │
  │  - Prod/Dev Environment Detection                        │
  │  - Unhandled Event Aggregation (Lua script + RENAME)     │
  │  - Heartbeat + Janitor (orphan recovery)                 │
  │  - Poison Message Handling (DLQ)                         │
  │  - PostgreSQL connection pooling                         │
  └──────┬──────────────────────────────────────────────────┘
         │ Writes audit log
         ▼
  ┌─────────────────────────────────────────────────────────┐
  │              PostgreSQL (HA)                             │
  │  - alert_rules (cached by alerter)                       │
  │  - development_hosts (cached by alerter)                 │
  │  - device_teams (cached by alerter)                      │
  │  - event_audit_log (partitioned by month)                │
  │  - Streaming replication (Patroni/Crunchy)               │
  └─────────────────────────────────────────────────────────┘
         │
         │ LPUSH to alert_queue (if forwarding needed)
         ▼
  ┌─────────────────────────────────────────────────────────┐
  │       Moog Forwarder Service (Ports 8083, 8084)          │
  │  - BRPOPLPUSH from alert_queue                           │
  │  - Redis-based shared rate limiter (Lua sliding window)  │
  │  - Exponential backoff (1s → 2s → 4s → 8s → 60s max)    │
  │  - Heartbeat + Janitor (orphan recovery)                 │
  │  - Smart retry logic (retry 5xx, DLQ on 4xx)             │
  │  - Dead letter queue for failed alerts                   │
  └──────┬──────────────────────────────────────────────────┘
         │ HTTPS Webhook (TLS)
         ▼
  ┌─────────────────────────────────────────────────────────┐
  │                   Moogsoft AIOps                         │
  └─────────────────────────────────────────────────────────┘

  ┌─────────────────────────────────────────────────────────┐
  │           Web UI Service (Port 8090)                     │
  │  - Real-time EPS Dashboard (Chart.js)                    │
  │  - Alert Rules CRUD API + Management                     │
  │  - Audit Log Viewer (paginated, filtered)                │
  │  - Dev Host Management                                   │
  │  - Device Team Management                                │
  │  - API Key Authentication                                │
  │  - PostgreSQL + Redis connection pooling                 │
  └─────────────────────────────────────────────────────────┘

  ┌─────────────────────────────────────────────────────────┐
  │               HashiCorp Vault (HA)                       │
  │  - REDIS_PASS, DB_PASS, API keys                         │
  │  - AppRole auth (RHEL) or K8s auth (OCP)                 │
  │  - Background token renewal (all services)               │
  └─────────────────────────────────────────────────────────┘

  ---

  ## ✨ Key Features

  ### Reliability & Durability
  - ✅ **No Message Loss**: BRPOPLPUSH pattern ensures messages survive crashes
  - ✅ **Redis Persistence**: AOF with `appendfsync everysec` (1s max data loss)
  - ✅ **Janitor Recovery**: Automatically recovers orphaned messages on startup (Alerter & Moog Forwarder)
  - ✅ **Backpressure Handling**: Queue caps with HTTP 503 responses for rsyslog retry
  - ✅ **Poison Message DLQ**: Prevents infinite loops from malformed data (Alerter & Moog Forwarder)
  - ✅ **PostgreSQL HA**: Streaming replication with Patroni/Crunchy operators

  ### Performance & Scalability
  - ✅ **In-Memory Caching**: <1ms rule lookups (Alerter - no DB queries per message)
  - ✅ **Connection Pooling**: Redis and PostgreSQL pools for optimal concurrency
  - ✅ **Horizontal Scaling**: All services stateless and independently scalable
  - ✅ **Atomic Operations**: Redis pipelines and Lua scripts for race-free logic
  - ✅ **Partitioned Audit Log**: Monthly PostgreSQL partitions with auto-cleanup
  - ✅ **Metrics Caching**: 5s TTL on Web UI metrics queries reduces Redis load

  ### Security
  - ✅ **Vault Integration**: All secrets stored in HashiCorp Vault
  - ✅ **TLS Everywhere**: Redis, PostgreSQL, and HTTP endpoints encrypted
  - ✅ **API Key Auth**: Constant-time comparison to prevent timing attacks
  - ✅ **Background Token Renewal**: Vault tokens auto-renewed before expiry

  ### Observability
  - ✅ **Prometheus Metrics**: 30+ metrics for queue depth, latency, throughput
  - ✅ **Health Checks**: HTTP endpoints for liveness/readiness probes
  - ✅ **Correlation IDs**: Request tracing through entire pipeline
  - ✅ **Structured Logging**: Automatic correlation ID enrichment

  ### Intelligence
  - ✅ **Advanced Rule Matching**: Priority, contains, regex, OID prefix
  - ✅ **Environment Detection**: Prod vs Dev routing logic
  - ✅ **Unhandled Event Aggregation**: Meta-alerts for unknown event patterns (atomic Lua script + RENAME)
  - ✅ **SIGHUP Cache Reload**: Hot-reload rules without service restart
  - ✅ **Shared Rate Limiting**: Moog Forwarder coordinates rate limit across all pods

  ---

  ## 🧩 Components

  ### 1. **Ingestor Service** (`services/ingestor_service.py`)
  - **Role**: HTTP ingestion endpoint for rsyslog
  - **Port**: 8080 (configurable)
  - **Features**:
    - API key authentication (constant-time comparison)
    - Queue depth checking (backpressure)
    - Time-windowed metrics (1m/1h/24h)
    - Vault secret management with background renewal
    - Prometheus `/metrics` and `/health` endpoints
    - Redis connection pooling with TLS

  ### 2. **Alerter Service** (`services/alerter_service.py`)
  - **Role**: Core event processing logic ("The Brain")
  - **Ports**: 8081 (metrics), 8082 (health)
  - **Features**:
    - BRPOPLPUSH reliable queueing
    - In-memory rule cache (5min refresh + SIGHUP)
    - Rule matching with priority
    - Prod/Dev environment detection
    - Unhandled event detection (Lua script + RENAME deduplication)
    - Heartbeat + Janitor pattern
    - PostgreSQL connection pooling
    - Poison message DLQ with retry counter

  ### 3. **Moog Forwarder Service** (`services/moog_forwarder_service.py`)
  - **Role**: Forwards alerts to Moogsoft with rate limiting
  - **Ports**: 8083 (metrics), 8084 (health)
  - **Features**:
    - BRPOPLPUSH from alert queue
    - **Redis-based shared rate limiter** (Lua sliding window)
    - Exponential backoff + retry logic (configurable)
    - Smart retry: retry on 5xx/timeout, DLQ on 4xx
    - Dead letter queue for failed alerts
    - Heartbeat + Janitor pattern
    - Correlation ID tracking

  ### 4. **Web UI Service** (`services/web_ui_service.py`)
  - **Role**: Management interface and real-time dashboard
  - **Port**: 8090 (configurable)
  - **Features**:
    - Real-time EPS dashboard (Chart.js, 10s refresh)
    - **Alert Rules CRUD** (GET, POST, PUT, DELETE)
    - **Audit Log Viewer** (paginated, filtered by host/rule/date)
    - **Dev Host Management** (GET, POST, DELETE)
    - **Device Team Management** (GET, POST, PUT, DELETE)
    - API key authentication
    - Metrics caching (5s TTL)
    - PostgreSQL + Redis connection pooling

  ---

  ## 📦 Requirements

  ### System Requirements
  - **Python**: 3.8+
  - **Redis**: 6.0+ (with Sentinel or Cluster for HA)
  - **PostgreSQL**: 12+ (with partitioning support)
  - **HashiCorp Vault**: 1.8+

  ### Python Dependencies
  ```txt
  flask>=2.0
  gunicorn>=20.1
  redis>=4.0
  psycopg2-binary>=2.9
  hvac>=1.0
  prometheus-client>=0.12
  prometheus-flask-exporter>=0.20
  requests>=2.28

  Deployment Platforms

  - RHEL 8+: systemd services, Sentinel, Patroni
  - OpenShift/Kubernetes: Operators for Redis, PostgreSQL, Vault

  ---
  🚀 Quick Start

  1. Clone the Repository

  git clone https://github.com/yourusername/mutt.git
  cd mutt

  2. Set Up PostgreSQL

  # Create database and schema
  psql -U postgres < sql/mutt_schema_v2.1.sql

  # Create initial partitions
  psql -U postgres -d mutt_db << EOF
  SELECT create_monthly_partition('2025-11-01');
  SELECT create_monthly_partition('2025-12-01');
  EOF

  3. Configure Vault

  # Enable KV v2 secrets engine
  vault secrets enable -path=secret kv-v2

  # Store secrets
  vault kv put secret/mutt \
    REDIS_PASS="your-redis-password" \
    DB_PASS="your-db-password" \
    INGEST_API_KEY="your-ingest-api-key" \
    MOOG_API_KEY="your-moog-api-key" \
    WEBUI_API_KEY="your-webui-api-key"

  # Create AppRole for each service
  vault auth enable approle

  vault write auth/approle/role/mutt-ingestor \
    token_ttl=1h token_max_ttl=4h secret_id_ttl=0

  vault write auth/approle/role/mutt-alerter \
    token_ttl=1h token_max_ttl=4h secret_id_ttl=0

  vault write auth/approle/role/mutt-moog-forwarder \
    token_ttl=1h token_max_ttl=4h secret_id_ttl=0

  vault write auth/approle/role/mutt-webui \
    token_ttl=1h token_max_ttl=4h secret_id_ttl=0

  4. Install Python Dependencies

  python3 -m venv venv
  source venv/bin/activate
  pip install -r requirements.txt

  5. Configure Environment Variables

  # Copy example config
  cp config/mutt.env.example config/mutt.env

  # Edit with your values
  vi config/mutt.env

  6. Start Services (Development)

  # Terminal 1: Ingestor
  python services/ingestor_service.py

  # Terminal 2: Alerter
  python services/alerter_service.py

  # Terminal 3: Moog Forwarder
  python services/moog_forwarder_service.py

  # Terminal 4: Web UI
  python services/web_ui_service.py

  7. Verify Health

  # Check Ingestor
  curl http://localhost:8080/health

  # Check Alerter
  curl http://localhost:8082/health

  # Check Moog Forwarder
  curl http://localhost:8084/health

  # Check Web UI
  curl http://localhost:8090/health

  # View Dashboard (replace with your API key)
  open "http://localhost:8090/?api_key=your-webui-api-key"

  ---
  ⚙️ Configuration

  Note on Dynamic Configuration (v2.5): Set `DYNAMIC_CONFIG_ENABLED=true` to enable runtime reads from Redis for select settings (e.g., Alerter cache interval, unhandled thresholds; Moog rate limits). When disabled, services use static environment values.

  Development Standards: See `docs/DEVELOPMENT_STANDARDS.md` for Black/isort/Ruff/MyPy usage and local commands.

  Ingestor Service Configuration

  | Variable                    | Default                           | Description                      |
  |-----------------------------|-----------------------------------|----------------------------------|
  | SERVER_PORT_INGESTOR        | 8080                              | HTTP listen port                 |
  | REDIS_HOST                  | localhost                         | Redis hostname                   |
  | REDIS_PORT                  | 6379                              | Redis port                       |
  | REDIS_TLS_ENABLED           | true                              | Enable TLS for Redis             |
  | REDIS_CA_CERT_PATH          | /etc/mutt/certs/ca.pem            | Redis TLS CA certificate path    |
  | REDIS_MAX_CONNECTIONS       | 20                                | Redis connection pool size       |
  | MAX_INGEST_QUEUE_SIZE       | 1000000                           | Queue cap for backpressure       |
  | INGEST_QUEUE_NAME           | mutt:ingest_queue                 | Redis queue name                 |
  | METRICS_PREFIX              | mutt:metrics                      | Redis metrics key prefix         |
  | VAULT_ADDR                  | (required)                        | Vault server URL                 |
  | VAULT_ROLE_ID               | (required)                        | AppRole role ID                  |
  | VAULT_SECRET_ID_FILE        | /etc/mutt/secrets/vault_secret_id | Path to secret ID file           |
  | VAULT_SECRETS_PATH          | secret/mutt                       | Vault KV path                    |
  | VAULT_TOKEN_RENEW_THRESHOLD | 3600                              | Renew token when TTL < N seconds |
  | VAULT_RENEW_CHECK_INTERVAL  | 300                               | Check token TTL every N seconds  |
  | REQUIRED_MESSAGE_FIELDS     | timestamp,message,hostname        | Required fields in messages      |

  ---
  Alerter Service Configuration

  | Variable                       | Default                           | Description                             |
  |--------------------------------|-----------------------------------|-----------------------------------------|
  | POD_NAME                       | alerter-{random}                  | Unique worker identifier                |
  | METRICS_PORT_ALERTER           | 8081                              | Prometheus metrics port                 |
  | HEALTH_PORT_ALERTER            | 8082                              | Health check port                       |
  | LOG_LEVEL                      | INFO                              | Log level (DEBUG/INFO/WARNING/ERROR)    |
  | REDIS_HOST                     | localhost                         | Redis hostname                          |
  | REDIS_PORT                     | 6379                              | Redis port                              |
  | REDIS_TLS_ENABLED              | true                              | Enable TLS for Redis                    |
  | REDIS_CA_CERT_PATH             | -                                 | Redis TLS CA certificate path           |
  | REDIS_MAX_CONNECTIONS          | 20                                | Redis connection pool size              |
  | INGEST_QUEUE_NAME              | mutt:ingest_queue                 | Redis ingest queue name                 |
  | ALERT_QUEUE_NAME               | mutt:alert_queue                  | Redis alert queue name                  |
  | ALERTER_PROCESSING_LIST_PREFIX | mutt:processing:alerter           | Processing list prefix                  |
  | ALERTER_HEARTBEAT_PREFIX       | mutt:heartbeat:alerter            | Heartbeat key prefix                    |
  | ALERTER_HEARTBEAT_INTERVAL     | 10                                | Heartbeat interval (seconds)            |
  | ALERTER_JANITOR_TIMEOUT        | 30                                | Heartbeat expiry for janitor (seconds)  |
  | ALERTER_DLQ_NAME               | mutt:dlq:alerter                  | Dead letter queue name                  |
  | ALERTER_MAX_RETRIES            | 3                                 | Max retries before DLQ                  |
  | BRPOPLPUSH_TIMEOUT             | 5                                 | BRPOPLPUSH timeout (seconds)            |
  | DB_HOST                        | localhost                         | PostgreSQL hostname                     |
  | DB_PORT                        | 5432                              | PostgreSQL port                         |
  | DB_NAME                        | mutt_db                           | Database name                           |
  
  Backpressure (Dynamic Config)
  
  - `alerter_queue_warn_threshold` (default 1000)
  - `alerter_queue_shed_threshold` (default 2000)
  - `alerter_shed_mode` (`dlq` or `defer`, default `dlq`)
  - `alerter_defer_sleep_ms` (default 250)
  | DB_USER                        | mutt_user                         | Database user                           |
  | DB_TLS_ENABLED                 | true                              | Enable TLS for PostgreSQL               |
  | DB_TLS_CA_CERT_PATH            | -                                 | PostgreSQL TLS CA certificate path      |
  | DB_POOL_MIN_CONN               | 2                                 | Min connections in pool                 |
  | DB_POOL_MAX_CONN               | 10                                | Max connections in pool                 |
  | CACHE_RELOAD_INTERVAL          | 300                               | Cache refresh interval (seconds)        |
  | UNHANDLED_PREFIX               | mutt:unhandled                    | Redis key prefix for unhandled counters |
  | UNHANDLED_THRESHOLD            | 100                               | Events before meta-alert                |
  | UNHANDLED_EXPIRY_SECONDS       | 86400                             | Counter expiry (24 hours)               |
  | UNHANDLED_DEFAULT_TEAM         | NETO                              | Default team for unhandled alerts       |
  | VAULT_ADDR                     | (required)                        | Vault server URL                        |
  | VAULT_ROLE_ID                  | (required)                        | AppRole role ID                         |
  | VAULT_SECRET_ID_FILE           | /etc/mutt/secrets/vault_secret_id | Path to secret ID file                  |
  | VAULT_SECRETS_PATH             | secret/mutt                       | Vault KV path                           |

  ---
  Moog Forwarder Service Configuration

  | Variable                    | Default                           | Description                              |
  |-----------------------------|-----------------------------------|------------------------------------------|
  | POD_NAME                    | moog-forwarder-{random}           | Unique worker identifier                 |
  | METRICS_PORT_MOOG           | 8083                              | Prometheus metrics port                  |
  | HEALTH_PORT_MOOG            | 8084                              | Health check port                        |
  | LOG_LEVEL                   | INFO                              | Log level                                |
  | REDIS_HOST                  | localhost                         | Redis hostname                           |
  | REDIS_PORT                  | 6379                              | Redis port                               |
  | REDIS_TLS_ENABLED           | true                              | Enable TLS for Redis                     |
  | REDIS_CA_CERT_PATH          | -                                 | Redis TLS CA certificate path            |
  | REDIS_MAX_CONNECTIONS       | 20                                | Redis connection pool size               |
  | ALERT_QUEUE_NAME            | mutt:alert_queue                  | Redis alert queue name                   |
  | MOOG_PROCESSING_LIST_PREFIX | mutt:processing:moog              | Processing list prefix                   |
  | MOOG_DLQ_NAME               | mutt:dlq:moog                     | Dead letter queue name                   |
  | BRPOPLPUSH_TIMEOUT          | 5                                 | BRPOPLPUSH timeout (seconds)             |
  | MOOG_HEARTBEAT_PREFIX       | mutt:heartbeat:moog               | Heartbeat key prefix                     |
  | MOOG_HEARTBEAT_INTERVAL     | 10                                | Heartbeat interval (seconds)             |
  | MOOG_JANITOR_TIMEOUT        | 30                                | Heartbeat expiry for janitor (seconds)   |
  | MOOG_WEBHOOK_URL            | (required)                        | Moogsoft webhook URL                     |
  | MOOG_WEBHOOK_TIMEOUT        | 10                                | HTTP request timeout (seconds)           |
  | MOOG_RATE_LIMIT             | 50                                | Max requests (shared across all pods)    |
  | MOOG_RATE_PERIOD            | 1                                 | Per N seconds (shared rate limit window) |
  | MOOG_RATE_LIMIT_KEY         | mutt:rate_limit:moog              | Redis key for rate limiter               |
  | MOOG_MAX_RETRIES            | 5                                 | Max retries before DLQ                   |
  | MOOG_RETRY_BASE_DELAY       | 1.0                               | Initial retry delay (seconds)            |
  | MOOG_RETRY_MAX_DELAY        | 60.0                              | Max retry delay (seconds)                |
  | VAULT_ADDR                  | (required)                        | Vault server URL                         |
  | VAULT_ROLE_ID               | (required)                        | AppRole role ID                          |
  | VAULT_SECRET_ID_FILE        | /etc/mutt/secrets/vault_secret_id | Path to secret ID file                   |
  | VAULT_SECRETS_PATH          | secret/mutt                       | Vault KV path                            |

  Retry Behavior (Exponential Backoff):
  - Attempt 1: Wait 1s
  - Attempt 2: Wait 2s
  - Attempt 3: Wait 4s
  - Attempt 4: Wait 8s
  - Attempt 5: Wait 16s
  - Attempt 6: Wait 32s
  - Further attempts: Wait 60s (capped)

  Smart Retry Logic:
  - ✅ Retry: Server errors (5xx), timeouts, connection errors
  - ❌ No Retry (DLQ): Client errors (4xx), max retries exhausted

  ---
  Web UI Service Configuration

  | Variable              | Default                           | Description                        |
  |-----------------------|-----------------------------------|------------------------------------|
  | SERVER_PORT_WEBUI     | 8090                              | HTTP listen port                   |
  | LOG_LEVEL             | INFO                              | Log level                          |
  | REDIS_HOST            | localhost                         | Redis hostname                     |
  | REDIS_PORT            | 6379                              | Redis port                         |
  | REDIS_TLS_ENABLED     | true                              | Enable TLS for Redis               |
  | REDIS_CA_CERT_PATH    | -                                 | Redis TLS CA certificate path      |
  | REDIS_MAX_CONNECTIONS | 10                                | Redis connection pool size         |
  | METRICS_PREFIX        | mutt:metrics                      | Redis metrics key prefix           |
  | DB_HOST               | localhost                         | PostgreSQL hostname                |
  | DB_PORT               | 5432                              | PostgreSQL port                    |
  | DB_NAME               | mutt_db                           | Database name                      |
  | DB_USER               | mutt_user                         | Database user                      |
  | DB_TLS_ENABLED        | true                              | Enable TLS for PostgreSQL          |
  | DB_TLS_CA_CERT_PATH   | -                                 | PostgreSQL TLS CA certificate path |
  | DB_POOL_MIN_CONN      | 2                                 | Min connections in pool            |
  | DB_POOL_MAX_CONN      | 10                                | Max connections in pool            |
  | METRICS_CACHE_TTL     | 5                                 | Metrics cache TTL (seconds)        |
  | AUDIT_LOG_PAGE_SIZE   | 50                                | Default page size for audit logs   |
  | VAULT_ADDR            | (required)                        | Vault server URL                   |
  | VAULT_ROLE_ID         | (required)                        | AppRole role ID                    |
  | VAULT_SECRET_ID_FILE  | /etc/mutt/secrets/vault_secret_id | Path to secret ID file             |
  | VAULT_SECRETS_PATH    | secret/mutt                       | Vault KV path                      |
  | PROMETHEUS_URL        | http://localhost:9090             | Prometheus base URL for SLOs       |

  ---
  📡 API Reference

  Web UI Service Endpoints

  Authentication: All endpoints (except /health and /metrics) require API key:
  # Header
  X-API-KEY: your-api-key

  # Query parameter (for dashboard)
  ?api_key=your-api-key

  Public Endpoints (No Auth)

  | Method | Endpoint | Description                              |
  |--------|----------|------------------------------------------|
  | GET    | /health  | Health check (returns Redis + DB status) |
  | GET    | /metrics | Prometheus metrics                       |

  Dashboard

  | Method | Endpoint | Description                    |
  |--------|----------|--------------------------------|
  | GET    | /        | Real-time EPS dashboard (HTML) |

  Metrics API

  | Method | Endpoint        | Description                             |
  |--------|-----------------|-----------------------------------------|
  | GET    | /api/v1/metrics | Real-time EPS metrics (JSON, cached 5s) |
  | GET    | /api/v1/slo     | Component SLO status (JSON)             |

  SLO Response (example):
  {
    "window_hours": 24,
    "components": {
      "ingestor": {
        "target": 0.995,
        "availability": 0.999,
        "error_budget_remaining": 0.8,
        "burn_rate": 0.2,
        "state": "ok",
        "window_hours": 24
      }
    }
  }

  Response:
  {
    "summary": {
      "current_rate_1m": 1250.45,
      "avg_rate_15m": 1180.32,
      "avg_rate_1h": 1205.67
    },
    "chart_24h": {
      "labels": ["00:00", "01:00", ..., "23:00"],
      "data": [1200.5, 1150.3, ..., 1300.8]
    }
  }

  Alert Rules API

  | Method | Endpoint           | Description           |
  |--------|--------------------|-----------------------|
  | GET    | /api/v1/rules      | List all alert rules  |
  | POST   | /api/v1/rules      | Create new alert rule |
  | GET    | /api/v1/rules/{id} | Get specific rule     |
  | PUT    | /api/v1/rules/{id} | Update rule           |
  | DELETE | /api/v1/rules/{id} | Delete rule           |

  Create Rule Request:
  {
    "match_string": "CRITICAL",
    "trap_oid": null,
    "syslog_severity": null,
    "match_type": "contains",
    "priority": 10,
    "prod_handling": "Page_and_ticket",
    "dev_handling": "Ticket_only",
    "team_assignment": "NETO",
    "is_active": true
  }

  Audit Logs API

  | Method | Endpoint           | Description                |
  |--------|--------------------|----------------------------|
  | GET    | /api/v1/audit-logs | Get audit logs (paginated) |

  Query Parameters:
  - page: Page number (default: 1)
  - limit: Items per page (default: 50, max: 200)
  - hostname: Filter by hostname
  - rule_id: Filter by rule ID
  - start_date: Filter by start date (ISO format)
  - end_date: Filter by end date (ISO format)

  Example:
  curl "http://localhost:8090/api/v1/audit-logs?page=1&limit=50&hostname=router1&start_date=2025-11-01" \
    -H "X-API-KEY: your-key"

  Dev Hosts API

  | Method | Endpoint                     | Description     |
  |--------|------------------------------|-----------------|
  | GET    | /api/v1/dev-hosts            | List dev hosts  |
  | POST   | /api/v1/dev-hosts            | Add dev host    |
  | DELETE | /api/v1/dev-hosts/{hostname} | Remove dev host |

  Device Teams API

  | Method | Endpoint                 | Description         |
  |--------|--------------------------|---------------------|
  | GET    | /api/v1/teams            | List team mappings  |
  | POST   | /api/v1/teams            | Add team mapping    |
  | PUT    | /api/v1/teams/{hostname} | Update team mapping |
  | DELETE | /api/v1/teams/{hostname} | Delete team mapping |

  ---
  🐳 Deployment

  Docker Compose (Development)

  docker-compose up -d

  Production Deployment (Gunicorn)

  Ingestor:
  gunicorn \
    --bind 0.0.0.0:8080 \
    --workers 4 \
    --timeout 30 \
    --graceful-timeout 10 \
    --max-requests 10000 \
    --max-requests-jitter 1000 \
    --access-logfile - \
    --error-logfile - \
    'services.ingestor_service:create_app()'

  Web UI:
  gunicorn \
    --bind 0.0.0.0:8090 \
    --workers 4 \
    --timeout 30 \
    --graceful-timeout 10 \
    'services.web_ui_service:create_app()'

  Alerter & Moog Forwarder (worker services - run directly):
  python services/alerter_service.py
  python services/moog_forwarder_service.py

  Kubernetes Deployment

  All Services:
  # Ingestor Deployment
  apiVersion: apps/v1
  kind: Deployment
  metadata:
    name: mutt-ingestor
  spec:
    replicas: 3
    template:
      spec:
        containers:
        - name: ingestor
          image: mutt/ingestor:2.3
          ports:
          - containerPort: 8080
            name: http

  ---
  # Alerter Deployment
  apiVersion: apps/v1
  kind: Deployment
  metadata:
    name: mutt-alerter
  spec:
    replicas: 3
    template:
      spec:
        containers:
        - name: alerter
          image: mutt/alerter:2.3
          ports:
          - containerPort: 8081
            name: metrics
          - containerPort: 8082
            name: health

  ---
  # Moog Forwarder Deployment
  apiVersion: apps/v1
  kind: Deployment
  metadata:
    name: mutt-moog-forwarder
  spec:
    replicas: 2
    template:
      spec:
        containers:
        - name: moog-forwarder
          image: mutt/moog-forwarder:2.3
          ports:
          - containerPort: 8083
            name: metrics
          - containerPort: 8084
            name: health
          env:
          - name: MOOG_WEBHOOK_URL
            value: "https://moogsoft.example.com/api/v1/events"
          - name: MOOG_RATE_LIMIT
            value: "50"
          - name: MOOG_RATE_PERIOD
            value: "1"

  ---
  # Web UI Deployment
  apiVersion: apps/v1
  kind: Deployment
  metadata:
    name: mutt-webui
  spec:
    replicas: 2
    template:
      spec:
        containers:
        - name: webui
          image: mutt/webui:2.3
          ports:
          - containerPort: 8090
            name: http

  ---
  📊 Monitoring

  Prometheus Metrics

  Ingestor Service (:8080/metrics)

  - mutt_ingest_requests_total{status,reason} - Total ingestion requests (status: success|fail; reason for failures)
  - mutt_ingest_queue_depth - Current queue depth
  - mutt_ingest_latency_seconds - Request processing latency

  Alerter Service (:8081/metrics)

  - mutt_alerter_events_processed_total{status} - Events by status (handled/unhandled/poison/error)
  - mutt_alerter_processing_latency_seconds - Event processing time
  - mutt_alerter_queue_depth - Monitored queue depth (alert queue)
  - mutt_alerter_shed_events_total{mode} - Shed/deferral events
  - mutt_alerter_cache_rules_count - Rules in memory cache
  - mutt_alerter_cache_dev_hosts_count - Dev hosts in cache
  - mutt_alerter_cache_teams_count - Team mappings in cache
  - mutt_db_write_latency_ms - Database write latency
  - mutt_alerter_dlq_depth - Alerter DLQ depth
  - mutt_alerter_processing_list_depth - This worker's processing list depth
  - mutt_alerter_cache_reload_failures_total - Failed cache reloads

  Moog Forwarder Service (:8083/metrics)

  - mutt_moog_requests_total{status,reason} - Moog webhook requests (status: success|fail; reason for failures)
  - mutt_moog_request_latency_seconds - Webhook request latency
  - mutt_moog_dlq_depth - Moog DLQ depth
  - mutt_moog_processing_list_depth - This worker's processing list depth
  - mutt_moog_rate_limit_hits_total - Times rate limit was hit
  - mutt_moog_alerts_processed_total{status} - Alerts processed (success/dlq/error)

  Web UI Service (:8090/metrics)

  - mutt_webui_api_requests_total{endpoint,status} - API requests
  - mutt_webui_api_latency_seconds{endpoint} - API latency
  - mutt_webui_redis_scan_latency_seconds - Redis SCAN latency
  - mutt_webui_db_query_latency_ms{operation} - DB query latency

  SLOs

  - Web UI exposes component SLOs at `GET /api/v1/slo` using Prometheus queries and dynamic targets.
  - Example Prometheus expressions (24h window):

    Ingestor availability
    sum(rate(mutt_ingest_requests_total{status="success"}[24h]))
      /
    sum(rate(mutt_ingest_requests_total[24h]))

    Forwarder availability
    sum(rate(mutt_moog_requests_total{status="success"}[24h]))
      /
    sum(rate(mutt_moog_requests_total[24h]))

  Grafana Dashboard

  Import the pre-built dashboard:
  curl http://localhost:3000/api/dashboards/db \
    -H "Content-Type: application/json" \
    -d @grafana/mutt-dashboard.json

  Alert Rules (Prometheus)

  groups:
    - name: mutt
      rules:
        - alert: MUTTIngestQueueFull
          expr: mutt_ingest_queue_depth > 900000
          for: 5m
          annotations:
            summary: "MUTT ingest queue near capacity"

        - alert: MUTTHighAlerterDLQ
          expr: mutt_alerter_dlq_depth > 100
          for: 10m
          annotations:
            summary: "High number of poison messages in Alerter DLQ"

        - alert: MUTTHighMoogDLQ
          expr: mutt_moog_dlq_depth > 50
          for: 10m
          annotations:
            summary: "High number of failed alerts in Moog DLQ"

        - alert: MUTTMoogRateLimitHit
          expr: rate(mutt_moog_rate_limit_hits_total[5m]) > 10
          for: 5m
          annotations:
            summary: "Moog Forwarder hitting rate limit frequently"

  ---
  🛠️ Development

  Project Structure

  mutt/
  ├── services/ingestor_service.py  # HTTP ingestion endpoint (v2.3)
  ├── services/alerter_service.py   # Core event processor (v2.3)
  ├── services/moog_forwarder_service.py # Moogsoft integration (v2.3)
  ├── services/web_ui_service.py    # Management UI + API (v2.3)
  ├── sql/
  │   └── mutt_schema_v2.1.sql      # Database schema
  ├── config/
  │   ├── mutt.env.example          # Example configuration
  │   └── rsyslog.conf              # rsyslog integration config
  ├── systemd/
  │   ├── mutt-ingestor.service
  │   ├── mutt-alerter.service
  │   ├── mutt-moog-forwarder.service
  │   └── mutt-webui.service
  ├── k8s/
  │   ├── ingestor-deployment.yaml
  │   ├── alerter-deployment.yaml
  │   ├── moog-forwarder-deployment.yaml
  │   ├── webui-deployment.yaml
  │   └── configmap.yaml
  ├── tests/
  │   ├── test_ingestor.py
  │   ├── test_alerter.py
  │   ├── test_moog_forwarder.py
  │   └── test_integration.py
  ├── requirements.txt
  ├── docker-compose.yml
  └── README.md

  Running Tests

  # Unit tests
  pytest tests/test_ingestor.py -v
  pytest tests/test_alerter.py -v
  pytest tests/test_moog_forwarder.py -v

  # Integration tests
  pytest tests/test_integration.py -v

  # Load tests
  locust -f tests/load_test.py --host=http://localhost:8080

  ---
  🧪 Testing

  Manual Testing

  Test Ingestor:
  # Send test event
  curl -X POST http://localhost:8080/ingest \
    -H "X-API-KEY: your-key" \
    -H "Content-Type: application/json" \
    -d '{
      "timestamp": "2025-11-08T12:00:00Z",
      "hostname": "router1",
      "message": "CRITICAL: Interface down",
      "syslog_severity": 1
    }'

  Test Backpressure:
  # Check queue depth
  redis-cli LLEN mutt:ingest_queue

  # Trigger 503 by filling queue (if needed)
  for i in {1..1000000}; do
    redis-cli LPUSH mutt:ingest_queue "test-message-$i"
  done

  Test SIGHUP Cache Reload:
  # Update a rule in database
  psql -U postgres -d mutt_db -c "UPDATE alert_rules SET priority = 5 WHERE id = 1"

  # Trigger cache reload
  kill -HUP $(pgrep -f alerter_service)

  # Check logs for "Cache reload complete"

  Test Moog Rate Limiting:
  # Monitor rate limit hits
  watch -n 1 'curl -s http://localhost:8083/metrics | grep mutt_moog_rate_limit_hits_total'

  # Adjust rate limit
  export MOOG_RATE_LIMIT=10
  export MOOG_RATE_PERIOD=1

  ---
  🔧 Troubleshooting

  Common Issues

  Issue: Services can't connect to Vault
  # Check Vault is accessible
  curl https://vault.example.com:8200/v1/sys/health

  # Check secret ID file exists
  cat /etc/mutt/secrets/vault_secret_id

  # Test Vault login manually
  vault write auth/approle/login \
    role_id=your-role-id \
    secret_id=your-secret-id

  Issue: Messages stuck in processing lists
  # Check for orphaned processing lists
  redis-cli KEYS "mutt:processing:*"

  # Check heartbeat keys
  redis-cli KEYS "mutt:heartbeat:*"

  # Manually trigger janitor (restart service)
  kill -TERM $(pgrep -f alerter_service)
  python services/alerter_service.py

  Issue: High DLQ depth
  # View messages in DLQ
  redis-cli LRANGE mutt:dlq:alerter 0 10

  # Investigate poison messages
  redis-cli LINDEX mutt:dlq:alerter 0

  # Clear DLQ (if needed)
  redis-cli DEL mutt:dlq:alerter

  Issue: Moog rate limiting
  # Check current rate limit settings
  env | grep MOOG_RATE

  # View rate limit key
  redis-cli ZCARD mutt:rate_limit:moog

  # Temporarily increase limit
  export MOOG_RATE_LIMIT=100
  systemctl restart mutt-moog-forwarder

  ---
  🤝 Contributing

  Contributions are welcome! Please follow these guidelines:

  1. Fork the repository
  2. Create a feature branch: git checkout -b feature/amazing-feature
  3. Write tests for your changes
  4. Ensure all tests pass: pytest
  5. Follow code style: black . && pylint *.py
  6. Commit with clear messages: git commit -m "Add amazing feature"
  7. Push to your fork: git push origin feature/amazing-feature
  8. Open a Pull Request

  ---
  📜 License

  This project is licensed under the MIT License - see the LICENSE file for details.

  ---
  🙏 Acknowledgments

  - Inspired by production monitoring challenges in enterprise networks
  - Built on battle-tested open-source technologies (Redis, PostgreSQL, Vault)
  - Designed with insights from the SRE and DevOps communities

  ---
  📞 Support

  - Issues: https://github.com/yourusername/mutt/issues
  - Discussions: https://github.com/yourusername/mutt/discussions
  - Documentation: https://github.com/yourusername/mutt/wiki

  ---
  🗺️ Roadmap

  - v2.4: Kafka integration for high-volume environments
  - v2.5: Machine learning for anomaly detection
  - v2.6: Multi-region deployment support
  - v2.7: OpenTelemetry tracing integration
  - v2.8: GraphQL API for Web UI
  - v2.9: ServiceNow integration (alternative to Moogsoft)
  - v3.0: Native Kubernetes operator for automated deployment

  ---
  Built with ❤️ by the MUTT Team | Version 2.3

  ---
## Observability

See `docs/observability.md` for OpenTelemetry configuration: running without a backend, disabling OTEL, console exporters, and enabling via a Collector or backend.

## What’s New in v2.5

- Dynamic config APIs (view/update at runtime) and history
- Zero‑downtime secret rotation (dual‑password connectors)
- Operator docs: rotation runbook and upgrade guide
- Test hardening and improved reliability around Redis/Postgres connections

More details:
- Current plan: `CURRENT_PLAN.md`
- Phase 3 handoff (canonical): `docs/PHASE_3_HANDOFF_TO_ARCHITECT.md`
- Alerter backpressure guide: `docs/ALERTER_BACKPRESSURE.md`
- SLOs guide and API: `docs/SLOs.md`
- Architect status & review protocol: `docs/ARCHITECT_STATUS_FOR_GEMINI.md`
- Dynamic Config Cheat‑Sheet: `docs/DYNAMIC_CONFIG_CHEATSHEET.md`
- Feature matrix: `docs/FEATURE_MATRIX.md`
- Upgrade guide: `docs/UPGRADE_GUIDE_v2_3_to_v2_5.md`

## API Docs

- Config management endpoints: `docs/API_CONFIG_ENDPOINTS.md`

## Runbook

- On‑Call Runbook: `docs/ONCALL_RUNBOOK.md`

## Dashboards & Alerts

- Grafana dashboard JSON: `docs/grafana/mutt-dashboard-v25.json`
  - Import via Grafana → Dashboards → Import → Upload JSON.
- Grafana provisioning (example):
  - Dashboards provider: `docs/grafana/provisioning/dashboards.yml`
  - Prometheus datasource: `docs/grafana/provisioning/datasources.yml`
  - Mount `docs/grafana` into Grafana container (e.g., `/var/lib/grafana/dashboards`).
- Prometheus alert rules: `docs/prometheus/alerts-v25.yml`
  - Load into your Prometheus/Alertmanager stack; adjust thresholds to your environment.
- Alertmanager example routing: `docs/alertmanager/config-v25.yml`
  - Replace email/webhook with your receivers and global SMTP/webhook config.

## Developer CLI

Use the lightweight helper for common dev tasks:

```bash
# Create .env from template (non-destructive by default)
python scripts/muttdev.py setup

# Show config (db/redis/retention)
python scripts/muttdev.py config --section all

# Suggested log commands for a service
python scripts/muttdev.py logs --service webui --tail 200

# Bring up services with docker-compose (optional list)
python scripts/muttdev.py up webui

# Run quick, targeted tests (Phase 3/4 areas)
python scripts/muttdev.py test --quick

# Run full test suite or filter via -k
python scripts/muttdev.py test
python scripts/muttdev.py test -k retention
 
# Format, lint, and type-check
python scripts/muttdev.py fmt
python scripts/muttdev.py lint
python scripts/muttdev.py type
```
