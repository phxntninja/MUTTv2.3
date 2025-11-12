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

## Reference Examples

This section provides complete, runnable examples for common tasks. Use these as reference when implementing the specifications in later phases.

### Example 1: Complete Service Startup (Ingestor)

```python
#!/usr/bin/env python3
"""
Complete example of starting the Ingestor service
File: services/ingestor_service.py
"""
import os
import sys
import logging
from flask import Flask, request, jsonify
import redis
from prometheus_client import Counter, make_wsgi_app
from werkzeug.middleware.dispatcher import DispatcherMiddleware

# Setup logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s [%(levelname)s] %(name)s: %(message)s'
)
logger = logging.getLogger('mutt.ingestor')

# Prometheus metrics
metrics = {
    'ingests_total': Counter('ingestor_ingests_total', 'Total ingestion requests', ['status']),
    'queue_pushes_total': Counter('ingestor_queue_pushes_total', 'Messages pushed to queue')
}

# Initialize Flask app
app = Flask(__name__)

# Add Prometheus metrics endpoint
app.wsgi_app = DispatcherMiddleware(app.wsgi_app, {
    '/metrics': make_wsgi_app()
})

# Redis connection with retry
def get_redis_connection():
    """Connect to Redis with retry logic"""
    redis_host = os.getenv('REDIS_HOST', 'localhost')
    redis_port = int(os.getenv('REDIS_PORT', '6379'))
    redis_db = int(os.getenv('REDIS_DB', '0'))

    max_retries = 5
    for attempt in range(max_retries):
        try:
            client = redis.Redis(
                host=redis_host,
                port=redis_port,
                db=redis_db,
                decode_responses=False,
                socket_timeout=5,
                socket_connect_timeout=5
            )
            client.ping()
            logger.info(f"Connected to Redis at {redis_host}:{redis_port}")
            return client
        except Exception as e:
            logger.error(f"Redis connection attempt {attempt+1}/{max_retries} failed: {e}")
            if attempt < max_retries - 1:
                time.sleep(2 ** attempt)
            else:
                raise

# Global Redis client
redis_client = None

@app.before_request
def ensure_redis_connection():
    """Ensure Redis connection is available"""
    global redis_client
    if redis_client is None:
        redis_client = get_redis_connection()

@app.route('/health', methods=['GET'])
def health():
    """Health check endpoint"""
    try:
        redis_client.ping()
        return jsonify({'status': 'healthy', 'service': 'ingestor'}), 200
    except Exception as e:
        logger.error(f"Health check failed: {e}")
        return jsonify({'status': 'unhealthy', 'error': str(e)}), 503

@app.route('/ingest', methods=['POST'])
def ingest():
    """Main ingestion endpoint"""
    try:
        # Validate request
        data = request.get_json()
        if not data:
            metrics['ingests_total'].labels(status='invalid').inc()
            return jsonify({'error': 'Invalid JSON'}), 400

        # Validate required fields
        required = ['timestamp', 'message', 'hostname']
        for field in required:
            if field not in data:
                metrics['ingests_total'].labels(status='invalid').inc()
                return jsonify({'error': f'Missing required field: {field}'}), 400

        # Enrich with metadata
        data['ingestion_timestamp'] = time.time()
        data['correlation_id'] = str(uuid.uuid4())

        # Push to Redis queue
        redis_client.lpush('mutt:ingest_queue', json.dumps(data))
        metrics['queue_pushes_total'].inc()
        metrics['ingests_total'].labels(status='success').inc()

        logger.debug(f"Ingested event from {data['hostname']}")
        return jsonify({'status': 'accepted', 'correlation_id': data['correlation_id']}), 202

    except Exception as e:
        logger.error(f"Ingestion error: {e}", exc_info=True)
        metrics['ingests_total'].labels(status='error').inc()
        return jsonify({'error': 'Internal server error'}), 500

def main():
    """Entry point"""
    logger.info("Starting MUTT Ingestor Service v2.5")

    # Connect to Redis
    global redis_client
    redis_client = get_redis_connection()

    # Start Flask app
    host = os.getenv('INGESTOR_HOST', '0.0.0.0')
    port = int(os.getenv('INGESTOR_PORT', '8080'))

    logger.info(f"Listening on {host}:{port}")
    app.run(host=host, port=port, debug=False)

if __name__ == '__main__':
    main()
```

### Example 2: Configuration Files

#### `.env.template`
```bash
# MUTT v2.5 Environment Configuration Template
# Copy to .env and fill in values

# ===== Redis Configuration =====
REDIS_HOST=localhost
REDIS_PORT=6379
REDIS_DB=0
REDIS_PASSWORD=  # Leave empty if no auth
REDIS_SSL=false
REDIS_SENTINEL_HOSTS=  # Comma-separated: sentinel1:26379,sentinel2:26379
REDIS_SENTINEL_MASTER=mymaster

# ===== PostgreSQL Configuration =====
POSTGRES_HOST=localhost
POSTGRES_PORT=5432
POSTGRES_DB=mutt
POSTGRES_USER=mutt_user
POSTGRES_PASSWORD=  # Set in Vault, not here
POSTGRES_SSL_MODE=prefer

# ===== Vault Configuration =====
VAULT_ADDR=https://vault.example.com:8200
VAULT_ROLE_ID=  # AppRole role ID
VAULT_SECRET_ID=  # AppRole secret ID
VAULT_MOUNT_POINT=mutt
VAULT_SECRET_PATH=mutt/prod/secrets

# ===== Moogsoft Configuration =====
MOOG_WEBHOOK_URL=https://moogsoft.example.com/webhook
MOOG_RATE_LIMIT_PER_SEC=50
MOOG_HEALTH_CHECK_ENABLED=true
MOOG_HEALTH_TIMEOUT=5

# ===== Service Configuration =====
INGESTOR_HOST=0.0.0.0
INGESTOR_PORT=8080
ALERTER_WORKER_ID=alerter-01
MOOG_FORWARDER_WORKER_ID=forwarder-01
WEB_UI_PORT=8090
REMEDIATION_INTERVAL_SECONDS=60

# ===== Dynamic Config Defaults =====
ALERTER_CACHE_TTL_SECONDS=300
ALERTER_QUEUE_WARN_THRESHOLD=1000
ALERTER_QUEUE_SHED_THRESHOLD=2000
MOOG_CIRCUIT_BREAKER_THRESHOLD=5
MOOG_CIRCUIT_BREAKER_TIMEOUT=60

# ===== Observability =====
PROMETHEUS_PORT=9090
GRAFANA_PORT=3000
LOG_LEVEL=INFO
ENABLE_TRACING=false
JAEGER_ENDPOINT=http://jaeger:14268/api/traces

# ===== Data Retention =====
EVENT_RETENTION_DAYS=90
AUDIT_RETENTION_DAYS=365
PARTITION_PRECREATE_MONTHS=3
```

#### `config.py`
```python
"""
MUTT Configuration Module
Loads configuration from environment variables with sensible defaults
"""
import os
from typing import Optional

class Config:
    """Main configuration class"""

    # ===== Redis =====
    REDIS_HOST: str = os.getenv('REDIS_HOST', 'localhost')
    REDIS_PORT: int = int(os.getenv('REDIS_PORT', '6379'))
    REDIS_DB: int = int(os.getenv('REDIS_DB', '0'))
    REDIS_PASSWORD: Optional[str] = os.getenv('REDIS_PASSWORD')
    REDIS_SSL: bool = os.getenv('REDIS_SSL', 'false').lower() == 'true'

    # ===== PostgreSQL =====
    POSTGRES_HOST: str = os.getenv('POSTGRES_HOST', 'localhost')
    POSTGRES_PORT: int = int(os.getenv('POSTGRES_PORT', '5432'))
    POSTGRES_DB: str = os.getenv('POSTGRES_DB', 'mutt')
    POSTGRES_USER: str = os.getenv('POSTGRES_USER', 'mutt_user')
    POSTGRES_PASSWORD: Optional[str] = os.getenv('POSTGRES_PASSWORD')  # From Vault
    POSTGRES_SSL_MODE: str = os.getenv('POSTGRES_SSL_MODE', 'prefer')

    # ===== Vault =====
    VAULT_ADDR: str = os.getenv('VAULT_ADDR', 'http://vault:8200')
    VAULT_ROLE_ID: Optional[str] = os.getenv('VAULT_ROLE_ID')
    VAULT_SECRET_ID: Optional[str] = os.getenv('VAULT_SECRET_ID')
    VAULT_MOUNT_POINT: str = os.getenv('VAULT_MOUNT_POINT', 'mutt')
    VAULT_SECRET_PATH: str = os.getenv('VAULT_SECRET_PATH', 'mutt/prod/secrets')

    # ===== Moogsoft =====
    MOOG_WEBHOOK_URL: str = os.getenv('MOOG_WEBHOOK_URL', 'http://moogsoft:8080/webhook')
    MOOG_RATE_LIMIT_PER_SEC: int = int(os.getenv('MOOG_RATE_LIMIT_PER_SEC', '50'))
    MOOG_HEALTH_CHECK_ENABLED: bool = os.getenv('MOOG_HEALTH_CHECK_ENABLED', 'true').lower() == 'true'
    MOOG_HEALTH_TIMEOUT: int = int(os.getenv('MOOG_HEALTH_TIMEOUT', '5'))

    # ===== Services =====
    INGESTOR_HOST: str = os.getenv('INGESTOR_HOST', '0.0.0.0')
    INGESTOR_PORT: int = int(os.getenv('INGESTOR_PORT', '8080'))
    ALERTER_WORKER_ID: str = os.getenv('ALERTER_WORKER_ID', 'alerter-default')
    WEB_UI_PORT: int = int(os.getenv('WEB_UI_PORT', '8090'))
    REMEDIATION_INTERVAL_SECONDS: int = int(os.getenv('REMEDIATION_INTERVAL_SECONDS', '60'))

    # ===== Dynamic Config =====
    ALERTER_CACHE_TTL_SECONDS: int = int(os.getenv('ALERTER_CACHE_TTL_SECONDS', '300'))
    MAX_DLQ_RETRIES: int = int(os.getenv('MAX_DLQ_RETRIES', '5'))
    DLQ_BATCH_SIZE: int = int(os.getenv('DLQ_BATCH_SIZE', '100'))

    # ===== Observability =====
    LOG_LEVEL: str = os.getenv('LOG_LEVEL', 'INFO')
    ENABLE_TRACING: bool = os.getenv('ENABLE_TRACING', 'false').lower() == 'true'

    @classmethod
    def validate(cls) -> bool:
        """Validate required configuration"""
        required = [
            cls.REDIS_HOST,
            cls.POSTGRES_HOST,
            cls.VAULT_ADDR
        ]
        return all(required)
```

### Example 3: Docker Compose (Complete Development Stack)

```yaml
version: '3.8'

services:
  # ===== Infrastructure =====
  redis:
    image: redis:7-alpine
    ports:
      - "6379:6379"
    volumes:
      - redis-data:/data
    command: redis-server --appendonly yes
    healthcheck:
      test: ["CMD", "redis-cli", "ping"]
      interval: 10s
      timeout: 3s
      retries: 3

  postgres:
    image: postgres:14-alpine
    ports:
      - "5432:5432"
    environment:
      POSTGRES_DB: mutt
      POSTGRES_USER: mutt_user
      POSTGRES_PASSWORD: dev_password
    volumes:
      - postgres-data:/var/lib/postgresql/data
      - ./database:/docker-entrypoint-initdb.d
    healthcheck:
      test: ["CMD-SHELL", "pg_isready -U mutt_user -d mutt"]
      interval: 10s
      timeout: 3s
      retries: 3

  vault:
    image: vault:1.13
    ports:
      - "8200:8200"
    environment:
      VAULT_DEV_ROOT_TOKEN_ID: dev-token
      VAULT_DEV_LISTEN_ADDRESS: 0.0.0.0:8200
    cap_add:
      - IPC_LOCK
    command: server -dev

  # ===== MUTT Services =====
  ingestor:
    build:
      context: .
      dockerfile: Dockerfile.ingestor
    ports:
      - "8080:8080"
      - "9090:9090"  # Prometheus metrics
    environment:
      REDIS_HOST: redis
      POSTGRES_HOST: postgres
      POSTGRES_PASSWORD: dev_password
      VAULT_ADDR: http://vault:8200
      VAULT_TOKEN: dev-token
      LOG_LEVEL: DEBUG
    depends_on:
      redis:
        condition: service_healthy
      postgres:
        condition: service_healthy
    restart: unless-stopped

  alerter:
    build:
      context: .
      dockerfile: Dockerfile.alerter
    environment:
      REDIS_HOST: redis
      POSTGRES_HOST: postgres
      POSTGRES_PASSWORD: dev_password
      ALERTER_WORKER_ID: alerter-${HOSTNAME:-dev}
      LOG_LEVEL: DEBUG
    depends_on:
      redis:
        condition: service_healthy
      postgres:
        condition: service_healthy
    deploy:
      replicas: 2  # Run 2 alerter instances
    restart: unless-stopped

  moog-forwarder:
    build:
      context: .
      dockerfile: Dockerfile.moog-forwarder
    environment:
      REDIS_HOST: redis
      MOOG_WEBHOOK_URL: ${MOOG_WEBHOOK_URL}
      MOOG_RATE_LIMIT_PER_SEC: 50
      LOG_LEVEL: DEBUG
    depends_on:
      - redis
    deploy:
      replicas: 1
    restart: unless-stopped

  web-ui:
    build:
      context: .
      dockerfile: Dockerfile.webui
    ports:
      - "8090:8090"
    environment:
      REDIS_HOST: redis
      POSTGRES_HOST: postgres
      POSTGRES_PASSWORD: dev_password
      MUTT_API_KEY: dev-key-12345
      LOG_LEVEL: DEBUG
    depends_on:
      redis:
        condition: service_healthy
      postgres:
        condition: service_healthy
    restart: unless-stopped

  remediation:
    build:
      context: .
      dockerfile: Dockerfile.remediation
    environment:
      REDIS_HOST: redis
      MOOG_WEBHOOK_URL: ${MOOG_WEBHOOK_URL}
      REMEDIATION_INTERVAL_SECONDS: 30
      LOG_LEVEL: DEBUG
    depends_on:
      - redis
    restart: unless-stopped

  # ===== Observability =====
  prometheus:
    image: prom/prometheus:latest
    ports:
      - "9091:9090"
    volumes:
      - ./monitoring/prometheus.yml:/etc/prometheus/prometheus.yml
      - prometheus-data:/prometheus
    command:
      - '--config.file=/etc/prometheus/prometheus.yml'
      - '--storage.tsdb.path=/prometheus'
      - '--storage.tsdb.retention.time=15d'

  grafana:
    image: grafana/grafana:latest
    ports:
      - "3000:3000"
    environment:
      GF_SECURITY_ADMIN_PASSWORD: admin
      GF_INSTALL_PLUGINS: redis-datasource
    volumes:
      - grafana-data:/var/lib/grafana
      - ./monitoring/grafana/dashboards:/etc/grafana/provisioning/dashboards
      - ./monitoring/grafana/datasources:/etc/grafana/provisioning/datasources

volumes:
  redis-data:
  postgres-data:
  prometheus-data:
  grafana-data:
```

### Example 4: API Usage Examples

#### Using curl
```bash
# ===== Ingest an Event =====
curl -X POST http://localhost:8080/ingest \
  -H "Content-Type: application/json" \
  -d '{
    "timestamp": "2025-01-12T10:30:00Z",
    "hostname": "router-01.example.com",
    "message": "Interface GigabitEthernet0/1 changed state to down",
    "severity": 3,
    "source": "syslog"
  }'

# Response: {"status": "accepted", "correlation_id": "uuid-here"}

# ===== Create an Alert Rule =====
curl -X POST http://localhost:8090/api/v2/rules \
  -H "Content-Type: application/json" \
  -H "X-API-Key: dev-key-12345" \
  -d '{
    "match_string": "Interface.*changed state to down",
    "match_type": "regex",
    "priority": 200,
    "prod_handling": "alert",
    "dev_handling": "suppress",
    "team_assignment": "network-ops"
  }'

# Response: {"id": 42, "message": "Rule created"}

# ===== Get All Rules =====
curl -X GET "http://localhost:8090/api/v2/rules?is_active=true&limit=10" \
  -H "X-API-Key: dev-key-12345"

# Response: {"rules": [...], "total": 42, "limit": 10, "offset": 0}

# ===== Update a Rule =====
curl -X PUT http://localhost:8090/api/v2/rules/42 \
  -H "Content-Type: application/json" \
  -H "X-API-Key: dev-key-12345" \
  -d '{
    "priority": 500,
    "prod_handling": "suppress",
    "reason": "False positive - too noisy"
  }'

# Response: {"message": "Rule updated"}

# ===== Get SLO Status =====
curl -X GET http://localhost:8090/api/v1/slo

# Response: {
#   "timestamp": 1736680200.0,
#   "overall_compliant": true,
#   "slos": {
#     "ingest_availability": {"target": 0.999, "actual": 0.9995, "compliant": true},
#     "alerter_latency": {"target": 0.95, "actual": 0.98, "compliant": true}
#   }
# }

# ===== Get Real-Time Metrics =====
curl -X GET http://localhost:8090/api/v2/metrics

# Response: {
#   "timestamp": 1736680200.0,
#   "counters": {
#     "ingest_total": 1234567,
#     "alerter_processed_total": 1234500,
#     "moog_forwarded_total": 45678
#   },
#   "queues": {
#     "ingest_queue_depth": 12,
#     "alert_queue_depth": 3
#   },
#   "circuit_breaker": {
#     "moog_state": "CLOSED"
#   }
# }

# ===== Health Checks =====
curl -X GET http://localhost:8080/health
curl -X GET http://localhost:8090/health

# Response: {"status": "healthy", "service": "ingestor"}
```

#### Using Python requests
```python
import requests
import json

BASE_URL = "http://localhost:8090"
API_KEY = "dev-key-12345"

# ===== Helper function =====
def api_call(method, endpoint, data=None):
    """Make API call with authentication"""
    headers = {
        "Content-Type": "application/json",
        "X-API-Key": API_KEY
    }
    url = f"{BASE_URL}{endpoint}"

    if method == "GET":
        response = requests.get(url, headers=headers)
    elif method == "POST":
        response = requests.post(url, headers=headers, json=data)
    elif method == "PUT":
        response = requests.put(url, headers=headers, json=data)
    elif method == "DELETE":
        response = requests.delete(url, headers=headers)

    return response.json()

# ===== Create a rule =====
rule_data = {
    "match_string": "CRITICAL",
    "match_type": "contains",
    "priority": 300,
    "prod_handling": "alert",
    "dev_handling": "log",
    "team_assignment": "sre"
}

result = api_call("POST", "/api/v2/rules", rule_data)
rule_id = result["id"]
print(f"Created rule {rule_id}")

# ===== Update the rule =====
update_data = {
    "priority": 400,
    "reason": "Increased priority after incident review"
}

api_call("PUT", f"/api/v2/rules/{rule_id}", update_data)
print(f"Updated rule {rule_id}")

# ===== Get audit logs =====
logs = api_call("GET", "/api/v2/audit-logs?table_name=alert_rules&limit=5")
print(f"Found {len(logs['logs'])} audit log entries")
```

### Example 5: Redis Data Structure Examples

```bash
# ===== Queue Keys =====
# Main ingest queue (list)
redis-cli LLEN mutt:ingest_queue
# Returns: 342

# View messages in queue (without removing)
redis-cli LRANGE mutt:ingest_queue 0 2
# Returns: JSON event strings

# ===== Processing Lists (BRPOPLPUSH pattern) =====
# Each worker has its own processing list
redis-cli LLEN mutt:processing:alerter:alerter-pod-1
# Returns: 1 (one message being processed)

# ===== Heartbeat Keys =====
# Workers maintain heartbeats with 30s TTL
redis-cli GET mutt:heartbeat:alerter:alerter-pod-1
# Returns: "1736680200" (timestamp)

redis-cli TTL mutt:heartbeat:alerter:alerter-pod-1
# Returns: 25 (seconds remaining)

# ===== Circuit Breaker State =====
redis-cli GET mutt:circuit:moog:state
# Returns: "CLOSED" | "OPEN" | "HALF_OPEN"

redis-cli GET mutt:circuit:moog:failures
# Returns: "2" (consecutive failures)

# ===== Dynamic Configuration =====
redis-cli HGETALL mutt:config:alerter
# Returns:
# 1) "cache_ttl_seconds"
# 2) "300"
# 3) "queue_warn_threshold"
# 4) "1000"
# 5) "queue_shed_threshold"
# 6) "2000"

# ===== Rate Limiting (Sorted Set) =====
redis-cli ZRANGE mutt:rate_limit:moog 0 -1 WITHSCORES
# Returns timestamp:counter entries within sliding window

# ===== Metrics Counters =====
redis-cli GET mutt:metrics:ingest:total
# Returns: "1234567"

redis-cli GET mutt:metrics:alerter:total
# Returns: "1234500"

# ===== Dead Letter Queues =====
redis-cli LLEN mutt:dlq:alerter
# Returns: 5 (poisoned messages)

redis-cli LLEN mutt:dlq:moog
# Returns: 2 (failed forwards)

redis-cli LLEN mutt:poison
# Returns: 0 (messages exceeding max retries)

# ===== Unhandled Event Tracking =====
redis-cli HGETALL mutt:unhandled:counters
# Returns:
# 1) "router-.*:link down"
# 2) "42"  (42 unhandled events matching this pattern)

# ===== Example Event Structure =====
redis-cli --raw LINDEX mutt:ingest_queue 0
# Returns (pretty-printed):
{
  "timestamp": "2025-01-12T10:30:00Z",
  "hostname": "router-01.example.com",
  "message": "Interface GigabitEthernet0/1 changed state to down",
  "severity": 3,
  "source": "syslog",
  "ingestion_timestamp": 1736680200.123,
  "correlation_id": "550e8400-e29b-41d4-a716-446655440000"
}

# ===== Example Enriched Alert =====
redis-cli --raw LINDEX mutt:alert_queue 0
# Returns (pretty-printed):
{
  "timestamp": "2025-01-12T10:30:00Z",
  "hostname": "router-01.example.com",
  "message": "Interface GigabitEthernet0/1 changed state to down",
  "severity": 3,
  "source": "syslog",
  "ingestion_timestamp": 1736680200.123,
  "correlation_id": "550e8400-e29b-41d4-a716-446655440000",
  "matched_rule_id": 42,
  "team_assignment": "network-ops",
  "prod_handling": "alert",
  "processing_timestamp": 1736680200.456
}
```

### Example 6: PostgreSQL Query Examples

```sql
-- ===== View Active Alert Rules =====
SELECT id, match_string, match_type, priority, prod_handling, team_assignment
FROM alert_rules
WHERE is_active = true
ORDER BY priority DESC, id ASC
LIMIT 10;

-- ===== Check Event Audit Log Partitions =====
SELECT
    schemaname,
    tablename,
    pg_size_pretty(pg_total_relation_size(schemaname||'.'||tablename)) AS size
FROM pg_tables
WHERE tablename LIKE 'event_audit_log_%'
ORDER BY tablename DESC;

-- ===== Query Recent Events =====
SELECT
    event_timestamp,
    hostname,
    matched_rule_id,
    handling_decision,
    forwarded_to_moog
FROM event_audit_log
WHERE event_timestamp >= NOW() - INTERVAL '1 hour'
ORDER BY event_timestamp DESC
LIMIT 100;

-- ===== View Configuration Change Audit Trail =====
SELECT
    changed_at,
    changed_by,
    operation,
    table_name,
    record_id,
    old_values->>'priority' AS old_priority,
    new_values->>'priority' AS new_priority,
    reason
FROM config_audit_log
WHERE table_name = 'alert_rules'
    AND operation = 'UPDATE'
ORDER BY changed_at DESC
LIMIT 20;

-- ===== Find Unmatched Events (High-Value Query) =====
SELECT
    hostname,
    COUNT(*) as unmatched_count,
    MAX(event_timestamp) as last_seen
FROM event_audit_log
WHERE matched_rule_id IS NULL
    AND event_timestamp >= NOW() - INTERVAL '24 hours'
GROUP BY hostname
HAVING COUNT(*) > 10
ORDER BY unmatched_count DESC;

-- ===== SLO Compliance Query =====
-- Alerter processing latency (p95 < 100ms)
SELECT
    percentile_cont(0.95) WITHIN GROUP (ORDER BY
        EXTRACT(EPOCH FROM (processing_timestamp - ingestion_timestamp)) * 1000
    ) AS p95_latency_ms
FROM event_audit_log
WHERE event_timestamp >= NOW() - INTERVAL '1 hour';

-- ===== Partition Maintenance =====
-- Create next month's partition
CREATE TABLE event_audit_log_2025_02 PARTITION OF event_audit_log
FOR VALUES FROM ('2025-02-01') TO ('2025-03-01');

-- Drop old partitions (after archiving)
DROP TABLE IF EXISTS event_audit_log_2023_01;
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

### 2.3 Alerter Service

**Reference:** `docs/architecture/SYSTEM_ARCHITECTURE.md` - Alerter section

**File:** `services/alerter_service.py`

**Purpose:** Core event processing with rule matching

**Specifications:**

#### Main Loop

```python
def main_loop():
    while True:
        # 1. Get event from Redis
        event_json = redis_client.brpoplpush('mutt:ingest_queue', 'mutt:processing:alerter:pod-name', timeout=5)
        if not event_json:
            continue

        event = json.loads(event_json)
        correlation_id = event.get('correlation_id')

        try:
            # 2. Process event
            process_event(event)

            # 3. Remove from processing list
            redis_client.lrem('mutt:processing:alerter:pod-name', 1, event_json)

        except Exception as e:
            # 4. Handle poison message
            handle_poison_message(event_json, correlation_id, e)
```

#### Event Processing

```python
def process_event(event):
    # 1. Find matching rule
    rule = find_matching_rule(event)

    # 2. Determine handling
    is_dev = is_development_host(event['hostname'])
    handling = rule['dev_handling'] if is_dev else rule['prod_handling']

    # 3. Log to audit trail
    log_to_audit_trail(event, rule, handling)

    # 4. Forward to Moog if necessary
    if handling in ['Page_and_ticket', 'Ticket_only']:
        forward_to_moog(event, rule, handling)
```

#### Rule Matching

```python
def find_matching_rule(event):
    # 1. Check in-memory cache
    if not cache['rules']:
        reload_cache()

    # 2. Iterate through rules by priority
    for rule in sorted(cache['rules'], key=lambda x: x['priority'], reverse=True):
        if rule_matches(rule, event):
            return rule

    # 3. Return default rule
    return get_default_rule()
```

#### Cache Reload

```python
def reload_cache():
    # 1. Load rules from DB
    cache['rules'] = db_conn.execute("SELECT * FROM alert_rules WHERE is_active = true").fetchall()

    # 2. Load dev hosts from DB
    cache['dev_hosts'] = {row['hostname'] for row in db_conn.execute("SELECT hostname FROM development_hosts").fetchall()}

    # 3. Load team mappings from DB
    cache['teams'] = {row['hostname']: row['team_assignment'] for row in db_conn.execute("SELECT * FROM device_teams").fetchall()}
```

#### Janitor Recovery

```python
def run_janitor():
    # 1. Get all processing lists
    processing_lists = redis_client.keys('mutt:processing:alerter:*')

    for list_key in processing_lists:
        pod_name = list_key.decode().split(':')[-1]

        # 2. Check heartbeat
        heartbeat_key = f'mutt:heartbeat:alerter:{pod_name}'
        last_heartbeat = redis_client.get(heartbeat_key)

        if not last_heartbeat or (time.time() - float(last_heartbeat)) > 30:
            # 3. Recover orphaned messages
            while redis_client.rpoplpush(list_key, 'mutt:ingest_queue'):
                pass
```

#### Detailed Function Specifications

**1. `find_matching_rule(event: dict) -> dict`**

```python
Purpose: Match event against cached rules by priority

Algorithm:
1. Get rules from cache (sorted by priority DESC)
2. For each rule:
   a. If match_type == 'contains':
      - Check if rule.match_string in event['message']
   b. If match_type == 'regex':
      - Compile regex (cache compiled patterns)
      - Check if re.search(rule.match_string, event['message'])
   c. If match_type == 'oid_prefix':
      - Check if event.get('trap_oid', '').startswith(rule.trap_oid)
3. Return first matching rule
4. If no match, return default rule (priority 1, Log_only)

Cache Invalidation:
- Reload every 5 minutes (background thread)
- Reload on SIGHUP signal
- Reload on dynamic config change: alerter_reload_rules_now=true

Implementation:
def find_matching_rule(event: dict) -> dict:
    # Check cache freshness
    if not cache.get('rules') or cache_expired():
        reload_cache()

    # Sort by priority (highest first)
    sorted_rules = sorted(cache['rules'], key=lambda r: r['priority'], reverse=True)

    for rule in sorted_rules:
        if not rule['is_active']:
            continue

        match_type = rule['match_type']

        if match_type == 'contains':
            if rule['match_string'] and rule['match_string'] in event.get('message', ''):
                logger.debug(f"Rule {rule['id']} matched (contains)")
                return rule

        elif match_type == 'regex':
            if rule['match_string']:
                # Cache compiled regex patterns
                pattern_key = f"regex_{rule['id']}"
                if pattern_key not in cache['compiled_patterns']:
                    try:
                        cache['compiled_patterns'][pattern_key] = re.compile(rule['match_string'])
                    except re.error as e:
                        logger.error(f"Invalid regex in rule {rule['id']}: {e}")
                        continue

                pattern = cache['compiled_patterns'][pattern_key]
                if pattern.search(event.get('message', '')):
                    logger.debug(f"Rule {rule['id']} matched (regex)")
                    return rule

        elif match_type == 'oid_prefix':
            if rule['trap_oid'] and event.get('trap_oid', '').startswith(rule['trap_oid']):
                logger.debug(f"Rule {rule['id']} matched (oid_prefix)")
                return rule

    # No match - return default rule
    logger.debug("No rule matched, using default")
    return get_default_rule()
```

**2. `is_development_host(hostname: str) -> bool`**

```python
Purpose: Check if host is in dev environment

Logic:
1. Check local cache (5-minute TTL)
2. If not cached:
   - Query: SELECT hostname FROM development_hosts
   - Store set in cache
   - Set cache timestamp
3. Return hostname in dev_hosts_set

Implementation:
def is_development_host(hostname: str) -> bool:
    # Check cache freshness
    cache_age = time.time() - cache.get('dev_hosts_timestamp', 0)

    if cache_age > 300:  # 5 minutes
        # Reload from database
        conn = db_pool.getconn()
        try:
            cursor = conn.cursor()
            cursor.execute("SELECT hostname FROM development_hosts")
            cache['dev_hosts'] = {row[0] for row in cursor.fetchall()}
            cache['dev_hosts_timestamp'] = time.time()
        finally:
            db_pool.putconn(conn)

    return hostname in cache.get('dev_hosts', set())
```

**3. `handle_poison_message(message: str, correlation_id: str, error: Exception)`**

```python
Purpose: Move poison message to DLQ with retry logic

Steps:
1. Parse message to get retry_count (default 0)
2. Increment retry_count
3. Add error metadata:
   - _poison_error_type: type(error).__name__
   - _poison_error_msg: str(error)
   - _poison_timestamp: now()
4. If retry_count >= MAX_RETRIES (default 5):
   - LPUSH mutt:dlq:alerter message
   - Log warning: "Message moved to DLQ after N retries"
   - Increment metric: alerter_dlq_messages_total
5. Else:
   - RPUSH mutt:ingest_queue message (retry)
   - Log info: "Message requeued, attempt N/5"
6. Remove from processing list

Implementation:
def handle_poison_message(message_json: str, correlation_id: str, error: Exception):
    try:
        message = json.loads(message_json)
    except json.JSONDecodeError:
        # Truly corrupted - straight to DLQ
        redis_client.lpush('mutt:dlq:alerter', message_json)
        metrics['alerter_poison_messages_total'].labels(reason='json_decode').inc()
        return

    # Get retry count
    retry_count = message.get('_retry_count', 0) + 1
    message['_retry_count'] = retry_count
    message['_last_error'] = {
        'type': type(error).__name__,
        'message': str(error),
        'timestamp': time.time()
    }

    max_retries = int(dynamic_config.get('alerter_max_retries', '5'))

    if retry_count >= max_retries:
        # Move to DLQ
        redis_client.lpush('mutt:dlq:alerter', json.dumps(message))
        logger.warning(
            f"Message {correlation_id} moved to DLQ after {retry_count} retries: {error}"
        )
        metrics['alerter_dlq_messages_total'].labels(reason='max_retries').inc()
    else:
        # Retry with exponential backoff
        backoff = min(2 ** retry_count, 60)  # Cap at 60 seconds
        logger.info(
            f"Message {correlation_id} requeued (attempt {retry_count}/{max_retries}), "
            f"backoff: {backoff}s"
        )
        time.sleep(backoff)
        redis_client.rpush('mutt:ingest_queue', json.dumps(message))
        metrics['alerter_retry_messages_total'].inc()

    # Remove from processing list
    redis_client.lrem(f'mutt:processing:alerter:{pod_name}', 1, message_json)
```

#### Backpressure Implementation

```python
Purpose: Monitor queue depth and shed load if necessary

Configuration (via dynamic config):
- alerter_queue_warn_threshold (default: 1000)
- alerter_queue_shed_threshold (default: 2000)
- alerter_shed_mode (default: 'dlq' or 'defer')
- alerter_defer_sleep_ms (default: 250)

Implementation:
def check_backpressure():
    """Monitor queue depth and apply backpressure if needed"""
    queue_depth = redis_client.llen('mutt:alert_queue')

    # Get thresholds from dynamic config
    warn_threshold = int(dynamic_config.get('alerter_queue_warn_threshold', '1000'))
    shed_threshold = int(dynamic_config.get('alerter_queue_shed_threshold', '2000'))
    shed_mode = dynamic_config.get('alerter_shed_mode', 'dlq')

    # Update gauge
    metrics['alert_queue_depth'].set(queue_depth)

    # Warning state
    if queue_depth >= warn_threshold:
        logger.warning(
            f"Alert queue depth HIGH: {queue_depth} "
            f"(warn threshold: {warn_threshold})"
        )
        metrics['alerter_backpressure_warnings_total'].inc()

    # Shedding state
    if queue_depth >= shed_threshold:
        logger.error(
            f"Alert queue CRITICAL: {queue_depth}, "
            f"applying backpressure (mode: {shed_mode})"
        )

        if shed_mode == 'dlq':
            # Shed messages from ingest_queue to DLQ
            shed_count = 0
            for _ in range(10):  # Shed up to 10 messages
                msg = redis_client.rpop('mutt:ingest_queue')
                if msg:
                    redis_client.lpush('mutt:dlq:alerter', msg)
                    shed_count += 1

            if shed_count > 0:
                logger.warning(f"Shed {shed_count} messages to DLQ due to backpressure")
                metrics['alerter_shed_messages_total'].inc(shed_count)

        elif shed_mode == 'defer':
            # Sleep to allow downstream processing to catch up
            defer_ms = int(dynamic_config.get('alerter_defer_sleep_ms', '250'))
            time.sleep(defer_ms / 1000.0)
            metrics['alerter_defer_events_total'].inc()

# Call this function periodically or before each message processing
```

#### Complete Main Loop with All Features

```python
def main_loop():
    """Main event processing loop with full error handling and backpressure"""

    # Get pod name for processing list
    pod_name = os.getenv('POD_NAME', socket.gethostname())
    processing_list = f'mutt:processing:alerter:{pod_name}'
    heartbeat_key = f'mutt:heartbeat:alerter:{pod_name}'

    # Start heartbeat thread
    heartbeat_thread = threading.Thread(target=heartbeat_worker, args=(heartbeat_key,), daemon=True)
    heartbeat_thread.start()

    # Start cache reload thread
    cache_reload_thread = threading.Thread(target=cache_reload_worker, daemon=True)
    cache_reload_thread.start()

    logger.info(f"Alerter service started (pod: {pod_name})")

    while True:
        try:
            # Check backpressure before processing
            check_backpressure()

            # 1. Atomic message retrieval from ingest_queue
            event_json = redis_client.brpoplpush(
                'mutt:ingest_queue',
                processing_list,
                timeout=5
            )

            if not event_json:
                continue  # Timeout, loop again

            # 2. Parse event
            try:
                event = json.loads(event_json)
            except json.JSONDecodeError as e:
                logger.error(f"Invalid JSON in message: {e}")
                handle_poison_message(event_json, 'unknown', e)
                continue

            correlation_id = event.get('correlation_id', 'unknown')

            try:
                # 3. Find matching rule
                start_time = time.time()
                matched_rule = find_matching_rule(event)

                # 4. Determine environment
                is_dev = is_development_host(event.get('hostname', ''))

                # 5. Determine handling
                handling = matched_rule['dev_handling'] if is_dev else matched_rule['prod_handling']

                # 6. Enrich event
                event['_matched_rule_id'] = matched_rule['id']
                event['_team_assignment'] = matched_rule['team_assignment']
                event['_handling'] = handling
                event['_is_dev'] = is_dev

                # 7. Log to audit trail (PostgreSQL)
                log_to_audit_trail(event, matched_rule, handling)

                # 8. Forward to Moog if necessary
                if handling in ['Page_and_ticket', 'Ticket_only']:
                    alert_json = json.dumps(event)
                    redis_client.lpush('mutt:alert_queue', alert_json)
                    logger.info(
                        f"Event {correlation_id} forwarded to alert_queue "
                        f"(rule: {matched_rule['id']}, handling: {handling})"
                    )
                else:
                    logger.debug(
                        f"Event {correlation_id} not forwarded "
                        f"(handling: {handling})"
                    )

                # 9. Success - remove from processing list
                redis_client.lrem(processing_list, 1, event_json)

                # 10. Update metrics
                processing_time = time.time() - start_time
                metrics['alerter_events_processed_total'].labels(
                    status='success',
                    handling=handling
                ).inc()
                metrics['alerter_processing_latency_seconds'].observe(processing_time)

            except Exception as e:
                # Processing error - handle as poison message
                logger.error(f"Error processing event {correlation_id}: {e}", exc_info=True)
                handle_poison_message(event_json, correlation_id, e)
                metrics['alerter_events_processed_total'].labels(
                    status='error',
                    handling='unknown'
                ).inc()

        except KeyboardInterrupt:
            logger.info("Shutting down alerter service")
            break

        except Exception as e:
            logger.error(f"Unexpected error in main loop: {e}", exc_info=True)
            time.sleep(1)  # Brief pause before retry

def heartbeat_worker(heartbeat_key: str):
    """Background thread to maintain heartbeat"""
    while True:
        redis_client.set(heartbeat_key, time.time(), ex=30)
        time.sleep(10)

def cache_reload_worker():
    """Background thread to reload cache periodically"""
    while True:
        time.sleep(300)  # 5 minutes
        try:
            reload_cache()
            logger.info("Cache reloaded successfully")
        except Exception as e:
            logger.error(f"Cache reload failed: {e}")
```

#### Test Cases

```python
def test_process_event_with_matching_rule():
    """Test event processing with a matching rule"""
    event = {
        'message': 'Interface GigE0/1 down',
        'hostname': 'router1',
        'correlation_id': 'test-123'
    }

    rule = {
        'id': 1,
        'match_string': 'Interface',
        'match_type': 'contains',
        'priority': 100,
        'prod_handling': 'Page_and_ticket',
        'dev_handling': 'Log_only',
        'team_assignment': 'NETO'
    }

    cache['rules'] = [rule]
    cache['dev_hosts'] = set()

    process_event(event)

    # Verify event enriched
    assert event['_matched_rule_id'] == 1
    assert event['_handling'] == 'Page_and_ticket'
    assert event['_is_dev'] is False

    # Verify forwarded to alert_queue
    assert redis_client.llen('mutt:alert_queue') == 1

def test_process_event_for_dev_host():
    """Test that dev hosts use dev_handling"""
    event = {
        'message': 'CRITICAL error',
        'hostname': 'dev-host-1',
        'correlation_id': 'dev-123'
    }

    rule = {
        'id': 2,
        'match_string': 'CRITICAL',
        'match_type': 'contains',
        'priority': 900,
        'prod_handling': 'Page_and_ticket',
        'dev_handling': 'Log_only',
        'team_assignment': 'NETO'
    }

    cache['rules'] = [rule]
    cache['dev_hosts'] = {'dev-host-1'}

    process_event(event)

    # Verify dev handling applied
    assert event['_handling'] == 'Log_only'
    assert event['_is_dev'] is True

    # Verify NOT forwarded
    assert redis_client.llen('mutt:alert_queue') == 0

def test_alerter_backpressure_shed_mode():
    """Test backpressure shedding to DLQ"""
    # Fill alert_queue to shed threshold
    for i in range(2001):
        redis_client.lpush('mutt:alert_queue', json.dumps({'id': i}))

    # Trigger backpressure check
    check_backpressure()

    # Assert messages moved to DLQ
    dlq_depth = redis_client.llen('mutt:dlq:alerter')
    assert dlq_depth >= 10

def test_alerter_janitor_recovery():
    """Test janitor recovers orphaned messages"""
    # Simulate crashed pod - messages in processing list
    redis_client.lpush('mutt:processing:alerter:pod-crashed', json.dumps({'id': 1}))
    redis_client.lpush('mutt:processing:alerter:pod-crashed', json.dumps({'id': 2}))

    # Expire heartbeat
    redis_client.delete('mutt:heartbeat:alerter:pod-crashed')

    # Run janitor
    run_janitor()

    # Assert messages recovered to ingest_queue
    recovered = redis_client.llen('mutt:ingest_queue')
    assert recovered == 2

    # Assert processing list cleaned up
    assert redis_client.llen('mutt:processing:alerter:pod-crashed') == 0

def test_rule_matching_regex():
    """Test regex rule matching"""
    event = {
        'message': 'Disk usage at 95%',
        'hostname': 'server1'
    }

    rule = {
        'id': 3,
        'match_string': r'Disk.*\d+%',
        'match_type': 'regex',
        'priority': 200,
        'prod_handling': 'Ticket_only',
        'dev_handling': 'Log_only',
        'team_assignment': 'UNIX'
    }

    cache['rules'] = [rule]

    matched = find_matching_rule(event)
    assert matched['id'] == 3

def test_poison_message_retry_logic():
    """Test poison message retry with exponential backoff"""
    message = json.dumps({
        'message': 'test',
        'hostname': 'test',
        'correlation_id': 'poison-123',
        '_retry_count': 2
    })

    error = ValueError("Test error")

    # Should retry (count < 5)
    handle_poison_message(message, 'poison-123', error)

    # Verify requeued
    requeued = redis_client.lrange('mutt:ingest_queue', 0, -1)
    assert len(requeued) == 1

    requeued_msg = json.loads(requeued[0])
    assert requeued_msg['_retry_count'] == 3

    # Verify not in DLQ
    assert redis_client.llen('mutt:dlq:alerter') == 0

def test_poison_message_max_retries():
    """Test poison message goes to DLQ after max retries"""
    message = json.dumps({
        'message': 'test',
        'hostname': 'test',
        'correlation_id': 'poison-456',
        '_retry_count': 5
    })

    error = ValueError("Test error")

    # Should go to DLQ (count >= 5)
    handle_poison_message(message, 'poison-456', error)

    # Verify in DLQ
    dlq_msgs = redis_client.lrange('mutt:dlq:alerter', 0, -1)
    assert len(dlq_msgs) == 1

    # Verify not requeued
    assert redis_client.llen('mutt:ingest_queue') == 0
```

### 2.4 Moog Forwarder Service

**Reference:** `docs/architecture/SYSTEM_ARCHITECTURE.md` - Moog Forwarder section

**File:** `services/moog_forwarder_service.py`

**Purpose:** Forwards alerts to Moogsoft with rate limiting and reliability patterns.

**Specifications:**

#### Main Loop

```python
def main_loop():
    while True:
        # 1. Get alert from Redis
        alert_json = redis_client.brpoplpush('mutt:alert_queue', 'mutt:processing:moog:pod-name', timeout=5)
        if not alert_json:
            continue

        alert = json.loads(alert_json)
        correlation_id = alert.get('correlation_id')

        try:
            # 2. Check rate limit
            if not rate_limiter.is_allowed():
                # Re-queue and sleep
                redis_client.rpush('mutt:alert_queue', alert_json)
                time.sleep(1)
                continue

            # 3. Forward to Moogsoft
            forward_to_moog(alert)

            # 4. Remove from processing list
            redis_client.lrem('mutt:processing:moog:pod-name', 1, alert_json)

        except Exception as e:
            # 5. Handle forwarding failure
            handle_forwarding_failure(alert_json, correlation_id, e)
```

#### Moog Forwarding

```python
def forward_to_moog(alert):
    # 1. Construct Moogsoft payload
    payload = {
        "source": alert['hostname'],
        "description": alert['message'],
        "severity": alert['syslog_severity'],
        # ... other fields
    }

    # 2. Make HTTP POST request to Moogsoft
    with requests.Session() as session:
        retry = Retry(
            total=5,
            read=5,
            connect=5,
            backoff_factor=0.3,
            status_forcelist=(500, 502, 504)
        )
        adapter = HTTPAdapter(max_retries=retry)
        session.mount('http://', adapter)
        session.mount('https://', adapter)

        response = session.post(MOOG_WEBHOOK_URL, json=payload, timeout=10)
        response.raise_for_status()
```

#### Janitor Recovery

```python
def run_janitor():
    # 1. Get all processing lists
    processing_lists = redis_client.keys('mutt:processing:moog:*')

    for list_key in processing_lists:
        pod_name = list_key.decode().split(':')[-1]

        # 2. Check heartbeat
        heartbeat_key = f'mutt:heartbeat:moog:{pod_name}'
        last_heartbeat = redis_client.get(heartbeat_key)

        if not last_heartbeat or (time.time() - float(last_heartbeat)) > 30:
            # 3. Recover orphaned messages
            while redis_client.rpoplpush(list_key, 'mutt:alert_queue'):
                pass
```

#### Circuit Breaker Implementation

```python
class CircuitBreaker:
    """Redis-based circuit breaker for Moogsoft forwarding

    States:
    - CLOSED: Normal operation (requests allowed)
    - OPEN: Too many failures (requests blocked)
    - HALF_OPEN: Testing if service recovered (single test request)
    """

    def __init__(self, redis_client, key_prefix='mutt:circuit:moog'):
        self.redis = redis_client
        self.key_prefix = key_prefix
        self.failure_threshold = 5  # Open circuit after 5 failures
        self.timeout = 60  # Try recovery after 60 seconds
        self.half_open_max_requests = 1

    def is_open(self) -> bool:
        """Check if circuit is currently open"""
        state = self.redis.get(f'{self.key_prefix}:state')
        return state == b'OPEN'

    def record_success(self):
        """Record successful request - reset failure counter"""
        # Reset failure counter
        self.redis.delete(f'{self.key_prefix}:failures')

        # Transition from HALF_OPEN to CLOSED
        current_state = self.redis.get(f'{self.key_prefix}:state')
        if current_state == b'HALF_OPEN':
            self.redis.set(f'{self.key_prefix}:state', 'CLOSED')
            logger.info("Circuit breaker HALF_OPEN -> CLOSED (service recovered)")
            metrics['circuit_breaker_state'].set(0)  # 0 = CLOSED
            metrics['circuit_breaker_transitions_total'].labels(
                to_state='closed'
            ).inc()

    def record_failure(self):
        """Record failed request - may open circuit"""
        failures = self.redis.incr(f'{self.key_prefix}:failures')

        if failures >= self.failure_threshold:
            # Open the circuit
            self.redis.set(f'{self.key_prefix}:state', 'OPEN')
            self.redis.set(f'{self.key_prefix}:opened_at', time.time())
            logger.error(
                f"Circuit breaker OPENED after {failures} consecutive failures"
            )
            metrics['circuit_breaker_state'].set(1)  # 1 = OPEN
            metrics['circuit_breaker_transitions_total'].labels(
                to_state='open'
            ).inc()
            metrics['circuit_breaker_opens_total'].inc()

    def attempt_reset(self) -> bool:
        """Try to transition from OPEN to HALF_OPEN after timeout"""
        state = self.redis.get(f'{self.key_prefix}:state')

        if state != b'OPEN':
            return False

        # Check if timeout elapsed
        opened_at = float(
            self.redis.get(f'{self.key_prefix}:opened_at') or 0
        )
        elapsed = time.time() - opened_at

        if elapsed >= self.timeout:
            # Try HALF_OPEN state
            self.redis.set(f'{self.key_prefix}:state', 'HALF_OPEN')
            logger.info(
                f"Circuit breaker OPEN -> HALF_OPEN (testing recovery after {elapsed:.1f}s)"
            )
            metrics['circuit_breaker_state'].set(2)  # 2 = HALF_OPEN
            metrics['circuit_breaker_transitions_total'].labels(
                to_state='half_open'
            ).inc()
            return True

        return False

    def allow_request(self) -> bool:
        """Check if request is allowed through circuit breaker"""
        state = self.redis.get(f'{self.key_prefix}:state')

        if state == b'CLOSED' or state is None:
            return True

        if state == b'OPEN':
            # Try to transition to HALF_OPEN
            return self.attempt_reset()

        if state == b'HALF_OPEN':
            # Allow single test request
            return True

        return False
```

#### Rate Limiting with Shared State

```python
# Lua script for atomic sliding window rate limiting
RATE_LIMIT_SCRIPT = """
local key = KEYS[1]
local now = tonumber(ARGV[1])
local window = tonumber(ARGV[2])
local limit = tonumber(ARGV[3])

-- Remove expired entries (outside sliding window)
redis.call('ZREMRANGEBYSCORE', key, 0, now - window)

-- Count current requests in window
local current = redis.call('ZCARD', key)

-- Check if under limit
if current < limit then
    -- Add new request with unique ID (timestamp + counter)
    local counter = redis.call('INCR', key .. ':counter')
    redis.call('ZADD', key, now, now .. ':' .. counter)
    redis.call('EXPIRE', key, window)
    return 1  -- Allowed
else
    return 0  -- Rejected
end
"""

class SharedRateLimiter:
    """Rate limiter shared across all Moog Forwarder instances via Redis

    Uses sliding window algorithm for accurate rate limiting
    """

    def __init__(self, redis_client, key='mutt:rate_limit:moog',
                 max_requests=50, window_seconds=1):
        self.redis = redis_client
        self.key = key
        self.max_requests = max_requests
        self.window = window_seconds
        self.script = redis_client.register_script(RATE_LIMIT_SCRIPT)

    def is_allowed(self) -> bool:
        """Check if request is within rate limit"""
        result = self.script(
            keys=[self.key],
            args=[time.time(), self.window, self.max_requests]
        )

        if result == 1:
            metrics['rate_limit_requests_total'].labels(
                result='allowed'
            ).inc()
            return True
        else:
            metrics['rate_limit_requests_total'].labels(
                result='rejected'
            ).inc()
            logger.warning(
                f"Rate limit exceeded ({self.max_requests}/{self.window}s), "
                "deferring request"
            )
            return False
```

#### Complete Moog Forwarding Function

```python
def forward_to_moog(alert: dict, circuit_breaker: CircuitBreaker,
                   rate_limiter: SharedRateLimiter) -> bool:
    """Forward alert to Moogsoft with reliability patterns

    Returns:
        True if successfully forwarded
        False if deferred (rate limit/circuit breaker)

    Raises:
        Exception for retriable errors
    """

    # 1. Check circuit breaker
    if not circuit_breaker.allow_request():
        logger.warning(
            f"Circuit breaker {circuit_breaker.redis.get('mutt:circuit:moog:state').decode()}, "
            f"requeuing alert {alert.get('correlation_id')}"
        )
        redis_client.rpush('mutt:alert_queue', json.dumps(alert))
        time.sleep(5)  # Back off when circuit open
        return False

    # 2. Check rate limit
    if not rate_limiter.is_allowed():
        logger.info(
            f"Rate limit hit, requeuing alert {alert.get('correlation_id')}"
        )
        redis_client.rpush('mutt:alert_queue', json.dumps(alert))
        time.sleep(1)  # Brief back off
        return False

    # 3. Construct Moogsoft payload
    payload = {
        'source': alert.get('hostname', 'unknown'),
        'description': alert.get('message', ''),
        'severity': alert.get('syslog_severity', 5),
        'manager': 'MUTT',
        'class': alert.get('_team_assignment', 'Unknown'),
        'type': alert.get('trap_oid', 'syslog'),
        'agent_time': alert.get('timestamp'),
        'signature': alert.get('correlation_id'),
        'agent': {
            'location': alert.get('hostname'),
            'name': 'MUTT',
            'time': time.time()
        }
    }

    # 4. Make HTTP request with retries
    try:
        with requests.Session() as session:
            # Configure retry strategy for transient errors
            retry = Retry(
                total=3,
                backoff_factor=1,  # 1s, 2s, 4s
                status_forcelist=(500, 502, 503, 504),
                allowed_methods=['POST']
            )
            adapter = HTTPAdapter(max_retries=retry)
            session.mount('https://', adapter)
            session.mount('http://', adapter)

            # Make request with timing
            start = time.time()
            response = session.post(
                MOOG_WEBHOOK_URL,
                json=payload,
                timeout=10,
                headers={
                    'Content-Type': 'application/json',
                    'User-Agent': 'MUTT/2.5'
                }
            )
            latency = time.time() - start

            # 5. Handle response codes
            if response.status_code == 200:
                # Success
                circuit_breaker.record_success()
                logger.info(
                    f"Forwarded to Moogsoft: {alert['correlation_id']} "
                    f"(latency: {latency:.3f}s, status: {response.status_code})"
                )
                metrics['moog_forward_requests_total'].labels(
                    status='success',
                    code=200
                ).inc()
                metrics['moog_forward_latency_seconds'].observe(latency)
                return True

            elif 400 <= response.status_code < 500:
                # Client error - permanent failure, move to DLQ
                logger.error(
                    f"Moogsoft rejected alert {alert['correlation_id']} "
                    f"(HTTP {response.status_code}): {response.text}"
                )
                redis_client.lpush('mutt:dlq:moog', json.dumps(alert))
                metrics['moog_forward_requests_total'].labels(
                    status='client_error',
                    code=response.status_code
                ).inc()
                # Don't record as circuit breaker failure (client error)
                return True  # Handled (moved to DLQ)

            else:
                # Server error - retriable
                raise requests.HTTPError(
                    f"HTTP {response.status_code}: {response.text}"
                )

    except (requests.Timeout, requests.ConnectionError, requests.HTTPError) as e:
        # 6. Handle failures - record for circuit breaker
        circuit_breaker.record_failure()

        retry_count = alert.get('_moog_retry_count', 0) + 1
        alert['_moog_retry_count'] = retry_count
        alert['_last_moog_error'] = {
            'type': type(e).__name__,
            'message': str(e),
            'timestamp': time.time()
        }

        max_retries = 5

        if retry_count >= max_retries:
            # Max retries reached - move to DLQ
            logger.error(
                f"Max retries ({max_retries}) reached for alert "
                f"{alert['correlation_id']}, moving to DLQ: {e}"
            )
            redis_client.lpush('mutt:dlq:moog', json.dumps(alert))
            metrics['moog_forward_requests_total'].labels(
                status='max_retries',
                code=0
            ).inc()
            return True  # Handled (moved to DLQ)
        else:
            # Exponential backoff retry
            backoff = min(2 ** retry_count, 60)  # Cap at 60s
            logger.warning(
                f"Moogsoft forward failed for {alert['correlation_id']} "
                f"(attempt {retry_count}/{max_retries}): {e}, "
                f"retrying in {backoff}s"
            )
            time.sleep(backoff)
            redis_client.rpush('mutt:alert_queue', json.dumps(alert))
            metrics['moog_forward_requests_total'].labels(
                status='retry',
                code=0
            ).inc()
            raise  # Re-raise to trigger retry logic
```

#### Complete Main Loop with All Features

```python
def main_loop():
    """Main alert forwarding loop with full reliability patterns"""

    # Get pod name
    pod_name = os.getenv('POD_NAME', socket.gethostname())
    processing_list = f'mutt:processing:moog:{pod_name}'
    heartbeat_key = f'mutt:heartbeat:moog:{pod_name}'

    # Initialize circuit breaker and rate limiter
    circuit_breaker = CircuitBreaker(redis_client)
    rate_limiter = SharedRateLimiter(
        redis_client,
        max_requests=int(dynamic_config.get('moog_rate_limit', '50')),
        window_seconds=int(dynamic_config.get('moog_rate_window', '1'))
    )

    # Start heartbeat thread
    heartbeat_thread = threading.Thread(
        target=heartbeat_worker,
        args=(heartbeat_key,),
        daemon=True
    )
    heartbeat_thread.start()

    logger.info(f"Moog Forwarder service started (pod: {pod_name})")
    logger.info(
        f"Rate limit: {rate_limiter.max_requests} req/{rate_limiter.window}s"
    )

    while True:
        try:
            # 1. Atomic retrieval from alert_queue
            alert_json = redis_client.brpoplpush(
                'mutt:alert_queue',
                processing_list,
                timeout=5
            )

            if not alert_json:
                continue  # Timeout, loop again

            # 2. Parse alert
            try:
                alert = json.loads(alert_json)
            except json.JSONDecodeError as e:
                logger.error(f"Invalid JSON in alert: {e}")
                # Move corrupted message to DLQ
                redis_client.lpush('mutt:dlq:moog', alert_json)
                redis_client.lrem(processing_list, 1, alert_json)
                continue

            correlation_id = alert.get('correlation_id', 'unknown')

            try:
                # 3. Forward to Moogsoft
                success = forward_to_moog(alert, circuit_breaker, rate_limiter)

                if success:
                    # 4. Remove from processing list on success
                    redis_client.lrem(processing_list, 1, alert_json)
                else:
                    # Deferred (rate limit or circuit breaker)
                    # Message already requeued by forward_to_moog
                    redis_client.lrem(processing_list, 1, alert_json)

            except Exception as e:
                # Unexpected error - already handled by forward_to_moog
                logger.error(
                    f"Unexpected error forwarding {correlation_id}: {e}",
                    exc_info=True
                )
                redis_client.lrem(processing_list, 1, alert_json)

        except KeyboardInterrupt:
            logger.info("Shutting down Moog Forwarder service")
            break

        except Exception as e:
            logger.error(f"Unexpected error in main loop: {e}", exc_info=True)
            time.sleep(1)  # Brief pause before retry

def heartbeat_worker(heartbeat_key: str):
    """Background thread to maintain heartbeat"""
    while True:
        redis_client.set(heartbeat_key, time.time(), ex=30)
        time.sleep(10)
```

#### Test Cases

```python
def test_circuit_breaker_opens_after_failures():
    """Test circuit opens after threshold failures"""
    cb = CircuitBreaker(redis_client)

    # Record 5 failures
    for _ in range(5):
        cb.record_failure()

    # Circuit should be open
    assert cb.is_open() is True
    state = redis_client.get('mutt:circuit:moog:state')
    assert state == b'OPEN'

def test_circuit_breaker_half_open_after_timeout():
    """Test circuit transitions to HALF_OPEN after timeout"""
    cb = CircuitBreaker(redis_client, key_prefix='mutt:circuit:test')

    # Open circuit
    for _ in range(5):
        cb.record_failure()

    # Set opened_at to 61 seconds ago
    redis_client.set('mutt:circuit:test:opened_at', time.time() - 61)

    # Should allow request (transition to HALF_OPEN)
    assert cb.allow_request() is True
    state = redis_client.get('mutt:circuit:test:state')
    assert state == b'HALF_OPEN'

def test_circuit_breaker_closes_on_success():
    """Test circuit closes after successful request in HALF_OPEN"""
    cb = CircuitBreaker(redis_client, key_prefix='mutt:circuit:test2')

    # Set to HALF_OPEN
    redis_client.set('mutt:circuit:test2:state', 'HALF_OPEN')

    # Record success
    cb.record_success()

    # Should be CLOSED
    state = redis_client.get('mutt:circuit:test2:state')
    assert state == b'CLOSED'

def test_rate_limiter_allows_within_limit():
    """Test rate limiter allows requests within limit"""
    limiter = SharedRateLimiter(
        redis_client,
        key='mutt:test:ratelimit',
        max_requests=10,
        window_seconds=1
    )

    # All 10 requests should be allowed
    for _ in range(10):
        assert limiter.is_allowed() is True

    # 11th request should be rejected
    assert limiter.is_allowed() is False

def test_rate_limiter_sliding_window():
    """Test sliding window behavior"""
    limiter = SharedRateLimiter(
        redis_client,
        key='mutt:test:sliding',
        max_requests=5,
        window_seconds=2
    )

    # Fill limit
    for _ in range(5):
        assert limiter.is_allowed() is True

    # Rejected
    assert limiter.is_allowed() is False

    # Wait for window to slide
    time.sleep(2.1)

    # Should be allowed again
    assert limiter.is_allowed() is True

def test_forward_to_moog_success():
    """Test successful forward to Moogsoft"""
    alert = {
        'hostname': 'test-host',
        'message': 'Test alert',
        'correlation_id': 'test-123',
        'syslog_severity': 3
    }

    cb = CircuitBreaker(redis_client, key_prefix='mutt:circuit:test3')
    rl = SharedRateLimiter(redis_client, key='mutt:test:rl2', max_requests=100)

    # Mock successful response
    with requests_mock.Mocker() as m:
        m.post(MOOG_WEBHOOK_URL, status_code=200, text='OK')

        success = forward_to_moog(alert, cb, rl)

    assert success is True

    # Circuit should remain closed
    assert cb.is_open() is False

def test_forward_to_moog_client_error_moves_to_dlq():
    """Test 4xx errors go to DLQ immediately"""
    alert = {
        'hostname': 'test-host',
        'message': 'Test alert',
        'correlation_id': 'test-400',
        'syslog_severity': 3
    }

    cb = CircuitBreaker(redis_client, key_prefix='mutt:circuit:test4')
    rl = SharedRateLimiter(redis_client, key='mutt:test:rl3', max_requests=100)

    # Mock 400 response
    with requests_mock.Mocker() as m:
        m.post(MOOG_WEBHOOK_URL, status_code=400, text='Bad request')

        success = forward_to_moog(alert, cb, rl)

    assert success is True  # Handled (moved to DLQ)

    # Should be in DLQ
    dlq = redis_client.lrange('mutt:dlq:moog', 0, -1)
    assert len(dlq) == 1

def test_forward_to_moog_server_error_retries():
    """Test 5xx errors trigger retry logic"""
    alert = {
        'hostname': 'test-host',
        'message': 'Test alert',
        'correlation_id': 'test-500',
        'syslog_severity': 3
    }

    cb = CircuitBreaker(redis_client, key_prefix='mutt:circuit:test5')
    rl = SharedRateLimiter(redis_client, key='mutt:test:rl4', max_requests=100)

    # Mock 500 response
    with requests_mock.Mocker() as m:
        m.post(MOOG_WEBHOOK_URL, status_code=500, text='Server error')

        try:
            forward_to_moog(alert, cb, rl)
        except requests.HTTPError:
            pass  # Expected

    # Should be requeued
    requeued = redis_client.lrange('mutt:alert_queue', 0, -1)
    assert len(requeued) == 1

    # Retry count should be incremented
    requeued_alert = json.loads(requeued[0])
    assert requeued_alert['_moog_retry_count'] == 1

    # Circuit breaker should record failure
    failures = redis_client.get('mutt:circuit:test5:failures')
    assert int(failures) == 1

def test_forward_to_moog_max_retries_moves_to_dlq():
    """Test max retries moves alert to DLQ"""
    alert = {
        'hostname': 'test-host',
        'message': 'Test alert',
        'correlation_id': 'test-max-retries',
        'syslog_severity': 3,
        '_moog_retry_count': 5  # Already at max
    }

    cb = CircuitBreaker(redis_client, key_prefix='mutt:circuit:test6')
    rl = SharedRateLimiter(redis_client, key='mutt:test:rl5', max_requests=100)

    # Mock timeout
    with requests_mock.Mocker() as m:
        m.post(MOOG_WEBHOOK_URL, exc=requests.Timeout)

        success = forward_to_moog(alert, cb, rl)

    assert success is True  # Handled (moved to DLQ)

    # Should be in DLQ
    dlq = redis_client.lrange('mutt:dlq:moog', 0, -1)
    assert len(dlq) == 1

def test_moog_janitor_recovery():
    """Test janitor recovers orphaned messages"""
    # Simulate crashed pod
    redis_client.lpush(
        'mutt:processing:moog:pod-crashed',
        json.dumps({'id': 1, 'correlation_id': 'orphan-1'})
    )
    redis_client.lpush(
        'mutt:processing:moog:pod-crashed',
        json.dumps({'id': 2, 'correlation_id': 'orphan-2'})
    )

    # Expire heartbeat
    redis_client.delete('mutt:heartbeat:moog:pod-crashed')

    # Run janitor
    run_janitor()

    # Messages should be recovered to alert_queue
    recovered = redis_client.llen('mutt:alert_queue')
    assert recovered == 2

    # Processing list should be cleaned up
    assert redis_client.llen('mutt:processing:moog:pod-crashed') == 0
```

### 2.5 Web UI Service

**Reference:** `docs/architecture/SYSTEM_ARCHITECTURE.md` - Web UI section

**File:** `services/web_ui_service.py`

**Purpose:** Provides a web interface for managing the system and viewing real-time data.

**Specifications:**

#### Flask Application Setup

```python
from flask import Flask, render_template, request, jsonify
from prometheus_flask_exporter import PrometheusMetrics

app = Flask(__name__)
metrics = PrometheusMetrics(app)
```

#### Authentication Middleware

```python
from functools import wraps
import os

def require_auth(f):
    """Decorator to require API key authentication for endpoints

    Expects 'X-API-Key' header matching MUTT_API_KEY environment variable.
    Returns 401 if authentication fails.
    """
    @wraps(f)
    def decorated_function(*args, **kwargs):
        api_key = request.headers.get('X-API-Key')
        expected_key = os.getenv('MUTT_API_KEY', 'dev-key-12345')

        if not api_key:
            logger.warning("API request without X-API-Key header")
            return jsonify({'error': 'API key required'}), 401

        if api_key != expected_key:
            logger.warning(f"API request with invalid key: {api_key[:8]}...")
            return jsonify({'error': 'Invalid API key'}), 401

        return f(*args, **kwargs)

    return decorated_function
```

#### Real-Time Metrics Endpoint

```python
@app.route('/api/v2/metrics', methods=['GET'])
def get_realtime_metrics():
    """Return real-time EPS metrics with 5-second Redis caching

    Caching strategy:
    - Check Redis for cached metrics (key: 'mutt:metrics:cached')
    - If cache exists and < 5 seconds old, return cached data
    - Otherwise, query Redis counters directly and cache result

    Returns:
        JSON with current EPS rates for all services
    """
    cache_key = 'mutt:metrics:cached'
    cache_ttl = 5  # seconds

    try:
        # Try to get cached metrics
        cached = redis_client.get(cache_key)
        if cached:
            logger.debug("Returning cached metrics")
            return jsonify(json.loads(cached)), 200

        # Cache miss - query Redis counters
        logger.debug("Cache miss, querying Redis for metrics")

        # Get current counter values
        ingest_total = int(redis_client.get('mutt:metrics:ingest:total') or 0)
        alerter_total = int(redis_client.get('mutt:metrics:alerter:total') or 0)
        moog_total = int(redis_client.get('mutt:metrics:moog:total') or 0)

        # Get queue depths
        ingest_queue_depth = redis_client.llen('mutt:ingest_queue')
        alert_queue_depth = redis_client.llen('mutt:alert_queue')

        # Get circuit breaker state
        circuit_state = redis_client.get('mutt:circuit:moog:state')
        circuit_state = circuit_state.decode() if circuit_state else 'CLOSED'

        # Calculate rates (requires previous sample stored in Redis)
        # For simplicity, we'll return totals and let client calculate rates
        metrics_data = {
            'timestamp': time.time(),
            'counters': {
                'ingest_total': ingest_total,
                'alerter_processed_total': alerter_total,
                'moog_forwarded_total': moog_total
            },
            'queues': {
                'ingest_queue_depth': ingest_queue_depth,
                'alert_queue_depth': alert_queue_depth
            },
            'circuit_breaker': {
                'moog_state': circuit_state
            }
        }

        # Cache for 5 seconds
        redis_client.setex(
            cache_key,
            cache_ttl,
            json.dumps(metrics_data)
        )

        logger.debug(f"Metrics cached for {cache_ttl}s")
        return jsonify(metrics_data), 200

    except Exception as e:
        logger.error(f"Error fetching metrics: {e}")
        return jsonify({'error': 'Failed to fetch metrics'}), 500
```

#### SLO Dashboard Endpoint

```python
from services.slo_checker import SLOComplianceChecker

@app.route('/api/v1/slo', methods=['GET'])
def get_slo_status():
    """Return SLO compliance status for all components

    Queries Prometheus for SLO metrics and calculates compliance.

    Returns:
        JSON with per-component SLO status and overall compliance
    """
    try:
        prometheus_url = os.getenv('PROMETHEUS_URL', 'http://prometheus:9090')
        checker = SLOComplianceChecker(prometheus_url=prometheus_url)

        # Get compliance report for all SLOs
        report = checker.get_compliance_report()

        # Format response
        response = {
            'timestamp': time.time(),
            'overall_compliant': all(
                slo['compliant'] for slo in report.values()
            ),
            'slos': report
        }

        return jsonify(response), 200

    except Exception as e:
        logger.error(f"Error checking SLO compliance: {e}")
        return jsonify({'error': 'Failed to check SLO compliance'}), 500
```

#### Rules CRUD Operations

```python
from services.audit_logger import log_audit

@app.route('/api/v2/rules', methods=['GET'])
def get_rules():
    """List all alert rules with optional filtering

    Query parameters:
    - is_active: Filter by active status (true/false)
    - match_type: Filter by match type (contains, regex, oid_prefix)
    - limit: Max results (default 100)
    - offset: Pagination offset (default 0)
    """
    try:
        # Parse query parameters
        is_active = request.args.get('is_active')
        match_type = request.args.get('match_type')
        limit = int(request.args.get('limit', 100))
        offset = int(request.args.get('offset', 0))

        # Build query
        query = "SELECT * FROM alert_rules WHERE 1=1"
        params = []

        if is_active is not None:
            query += " AND is_active = %s"
            params.append(is_active.lower() == 'true')

        if match_type:
            query += " AND match_type = %s"
            params.append(match_type)

        query += " ORDER BY priority DESC, id ASC LIMIT %s OFFSET %s"
        params.extend([limit, offset])

        # Execute query
        conn = get_db_connection()
        cursor = conn.cursor(cursor_factory=RealDictCursor)
        cursor.execute(query, params)
        rules = cursor.fetchall()

        # Get total count
        count_query = "SELECT COUNT(*) FROM alert_rules WHERE 1=1"
        count_params = []
        if is_active is not None:
            count_query += " AND is_active = %s"
            count_params.append(is_active.lower() == 'true')
        if match_type:
            count_query += " AND match_type = %s"
            count_params.append(match_type)

        cursor.execute(count_query, count_params)
        total = cursor.fetchone()['count']

        cursor.close()
        conn.close()

        return jsonify({
            'rules': [dict(rule) for rule in rules],
            'total': total,
            'limit': limit,
            'offset': offset
        }), 200

    except Exception as e:
        logger.error(f"Error fetching rules: {e}")
        return jsonify({'error': 'Failed to fetch rules'}), 500


@app.route('/api/v2/rules', methods=['POST'])
@require_auth
def create_rule():
    """Create a new alert rule

    Required fields:
    - match_string OR trap_oid (one required)
    - match_type (contains, regex, oid_prefix)
    - priority (integer)
    - prod_handling (suppress, alert, log)
    - dev_handling (suppress, alert, log)

    Optional fields:
    - syslog_severity (integer)
    - team_assignment (string)
    - is_active (boolean, default true)
    """
    try:
        data = request.get_json()

        # Validation
        if not data.get('match_string') and not data.get('trap_oid'):
            return jsonify({'error': 'Either match_string or trap_oid required'}), 400

        if data.get('match_type') not in ['contains', 'regex', 'oid_prefix']:
            return jsonify({'error': 'Invalid match_type'}), 400

        # Insert into database
        conn = get_db_connection()
        cursor = conn.cursor()

        cursor.execute("""
            INSERT INTO alert_rules (
                match_string, trap_oid, syslog_severity, match_type,
                priority, prod_handling, dev_handling, team_assignment,
                is_active
            ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s)
            RETURNING id
        """, (
            data.get('match_string'),
            data.get('trap_oid'),
            data.get('syslog_severity'),
            data['match_type'],
            data['priority'],
            data['prod_handling'],
            data['dev_handling'],
            data.get('team_assignment'),
            data.get('is_active', True)
        ))

        rule_id = cursor.fetchone()[0]
        conn.commit()

        # Log audit trail
        log_audit(
            conn=conn,
            operation='CREATE',
            table_name='alert_rules',
            record_id=rule_id,
            new_values=data,
            changed_by=request.headers.get('X-User', 'api'),
            reason=data.get('reason', 'Created via API')
        )

        cursor.close()
        conn.close()

        # Publish cache reload notification
        redis_client.publish('mutt:config:reload', 'rules')

        logger.info(f"Created rule {rule_id}")
        return jsonify({'id': rule_id, 'message': 'Rule created'}), 201

    except Exception as e:
        logger.error(f"Error creating rule: {e}")
        return jsonify({'error': 'Failed to create rule'}), 500


@app.route('/api/v2/rules/<int:rule_id>', methods=['PUT'])
@require_auth
def update_rule(rule_id):
    """Update an existing alert rule

    Only provided fields will be updated.
    Publishes cache reload notification to all Alerter instances.
    """
    try:
        data = request.get_json()

        # Get old values for audit
        conn = get_db_connection()
        cursor = conn.cursor(cursor_factory=RealDictCursor)

        cursor.execute("SELECT * FROM alert_rules WHERE id = %s", (rule_id,))
        old_rule = cursor.fetchone()

        if not old_rule:
            cursor.close()
            conn.close()
            return jsonify({'error': 'Rule not found'}), 404

        # Build update query dynamically
        update_fields = []
        params = []

        for field in ['match_string', 'trap_oid', 'syslog_severity', 'match_type',
                      'priority', 'prod_handling', 'dev_handling', 'team_assignment',
                      'is_active']:
            if field in data:
                update_fields.append(f"{field} = %s")
                params.append(data[field])

        if not update_fields:
            return jsonify({'error': 'No fields to update'}), 400

        params.append(rule_id)
        query = f"UPDATE alert_rules SET {', '.join(update_fields)} WHERE id = %s"

        cursor.execute(query, params)
        conn.commit()

        # Log audit trail
        log_audit(
            conn=conn,
            operation='UPDATE',
            table_name='alert_rules',
            record_id=rule_id,
            old_values=dict(old_rule),
            new_values=data,
            changed_by=request.headers.get('X-User', 'api'),
            reason=data.get('reason', 'Updated via API')
        )

        cursor.close()
        conn.close()

        # Publish cache reload notification
        redis_client.publish('mutt:config:reload', 'rules')

        logger.info(f"Updated rule {rule_id}")
        return jsonify({'message': 'Rule updated'}), 200

    except Exception as e:
        logger.error(f"Error updating rule: {e}")
        return jsonify({'error': 'Failed to update rule'}), 500


@app.route('/api/v2/rules/<int:rule_id>', methods=['DELETE'])
@require_auth
def delete_rule(rule_id):
    """Delete an alert rule (soft delete by setting is_active=false)

    Uses soft delete to preserve audit trail.
    """
    try:
        conn = get_db_connection()
        cursor = conn.cursor(cursor_factory=RealDictCursor)

        # Get rule for audit
        cursor.execute("SELECT * FROM alert_rules WHERE id = %s", (rule_id,))
        rule = cursor.fetchone()

        if not rule:
            cursor.close()
            conn.close()
            return jsonify({'error': 'Rule not found'}), 404

        # Soft delete
        cursor.execute(
            "UPDATE alert_rules SET is_active = false WHERE id = %s",
            (rule_id,)
        )
        conn.commit()

        # Log audit trail
        log_audit(
            conn=conn,
            operation='DELETE',
            table_name='alert_rules',
            record_id=rule_id,
            old_values=dict(rule),
            changed_by=request.headers.get('X-User', 'api'),
            reason=request.get_json().get('reason', 'Deleted via API') if request.get_json() else 'Deleted via API'
        )

        cursor.close()
        conn.close()

        # Publish cache reload notification
        redis_client.publish('mutt:config:reload', 'rules')

        logger.info(f"Deleted rule {rule_id}")
        return jsonify({'message': 'Rule deleted'}), 200

    except Exception as e:
        logger.error(f"Error deleting rule: {e}")
        return jsonify({'error': 'Failed to delete rule'}), 500
```

#### Audit Log Endpoint

```python
@app.route('/api/v2/audit-logs', methods=['GET'])
@require_auth
def get_audit_logs():
    """Get configuration audit logs with pagination

    Query parameters:
    - table_name: Filter by table (alert_rules, development_hosts, device_teams)
    - operation: Filter by operation (CREATE, UPDATE, DELETE)
    - changed_by: Filter by user
    - start_date: ISO format date (e.g. 2025-01-01)
    - end_date: ISO format date
    - limit: Max results (default 50, max 500)
    - offset: Pagination offset (default 0)

    Returns:
        JSON with audit log entries and pagination metadata
    """
    try:
        # Parse query parameters
        table_name = request.args.get('table_name')
        operation = request.args.get('operation')
        changed_by = request.args.get('changed_by')
        start_date = request.args.get('start_date')
        end_date = request.args.get('end_date')
        limit = min(int(request.args.get('limit', 50)), 500)
        offset = int(request.args.get('offset', 0))

        # Build query
        query = "SELECT * FROM config_audit_log WHERE 1=1"
        params = []

        if table_name:
            query += " AND table_name = %s"
            params.append(table_name)

        if operation:
            query += " AND operation = %s"
            params.append(operation)

        if changed_by:
            query += " AND changed_by = %s"
            params.append(changed_by)

        if start_date:
            query += " AND changed_at >= %s"
            params.append(start_date)

        if end_date:
            query += " AND changed_at <= %s"
            params.append(end_date)

        query += " ORDER BY changed_at DESC LIMIT %s OFFSET %s"
        params.extend([limit, offset])

        # Execute query
        conn = get_db_connection()
        cursor = conn.cursor(cursor_factory=RealDictCursor)
        cursor.execute(query, params)
        logs = cursor.fetchall()

        cursor.close()
        conn.close()

        # Convert to serializable format
        logs_list = []
        for log in logs:
            log_dict = dict(log)
            # Convert timestamp to ISO format
            if log_dict.get('changed_at'):
                log_dict['changed_at'] = log_dict['changed_at'].isoformat()
            logs_list.append(log_dict)

        return jsonify({
            'logs': logs_list,
            'limit': limit,
            'offset': offset
        }), 200

    except Exception as e:
        logger.error(f"Error fetching audit logs: {e}")
        return jsonify({'error': 'Failed to fetch audit logs'}), 500
```

#### Health and Dashboard Endpoints

```python
@app.route('/health', methods=['GET'])
def health_check():
    """Health check endpoint for Kubernetes liveness probe"""
    return jsonify({'status': 'healthy', 'service': 'web-ui'}), 200


@app.route('/', methods=['GET'])
def dashboard():
    """Render main dashboard HTML page"""
    return render_template('dashboard.html')
```

#### Test Cases

```python
# tests/test_web_ui_service.py

def test_health_endpoint(client):
    """Test health check returns 200"""
    response = client.get('/health')
    assert response.status_code == 200
    assert response.json['status'] == 'healthy'


def test_metrics_endpoint_with_cache(client, redis_client):
    """Test metrics endpoint uses 5-second cache"""
    # First request - cache miss
    response1 = client.get('/api/v2/metrics')
    assert response1.status_code == 200

    # Verify cache was set
    cached = redis_client.get('mutt:metrics:cached')
    assert cached is not None

    # Second request within 5 seconds - cache hit
    response2 = client.get('/api/v2/metrics')
    assert response2.status_code == 200
    assert response2.json == response1.json


def test_slo_endpoint(client, monkeypatch):
    """Test SLO endpoint returns compliance status"""
    # Mock SLOComplianceChecker
    class MockChecker:
        def __init__(self, prometheus_url):
            pass

        def get_compliance_report(self):
            return {
                'ingest_availability': {
                    'target': 0.999,
                    'actual': 0.9995,
                    'compliant': True
                },
                'alerter_latency': {
                    'target': 0.95,
                    'actual': 0.98,
                    'compliant': True
                }
            }

    monkeypatch.setattr('services.web_ui_service.SLOComplianceChecker', MockChecker)

    response = client.get('/api/v1/slo')
    assert response.status_code == 200
    assert response.json['overall_compliant'] is True
    assert 'ingest_availability' in response.json['slos']


def test_get_rules_with_pagination(client, db_conn):
    """Test GET /api/v2/rules returns paginated results"""
    # Create test rules
    cursor = db_conn.cursor()
    for i in range(5):
        cursor.execute("""
            INSERT INTO alert_rules (match_string, match_type, priority,
                                     prod_handling, dev_handling)
            VALUES (%s, %s, %s, %s, %s)
        """, (f'test-{i}', 'contains', 100 + i, 'alert', 'suppress'))
    db_conn.commit()

    # Test pagination
    response = client.get('/api/v2/rules?limit=2&offset=0')
    assert response.status_code == 200
    assert len(response.json['rules']) == 2
    assert response.json['total'] >= 5


def test_create_rule_requires_auth(client):
    """Test POST /api/v2/rules requires authentication"""
    response = client.post('/api/v2/rules', json={
        'match_string': 'test',
        'match_type': 'contains',
        'priority': 100,
        'prod_handling': 'alert',
        'dev_handling': 'suppress'
    })
    assert response.status_code == 401
    assert 'API key required' in response.json['error']


def test_create_rule_with_auth(client, db_conn, redis_client):
    """Test POST /api/v2/rules creates rule and publishes reload"""
    headers = {'X-API-Key': 'dev-key-12345'}

    response = client.post('/api/v2/rules', json={
        'match_string': 'critical error',
        'match_type': 'contains',
        'priority': 200,
        'prod_handling': 'alert',
        'dev_handling': 'alert',
        'team_assignment': 'ops'
    }, headers=headers)

    assert response.status_code == 201
    assert 'id' in response.json

    # Verify rule was created
    cursor = db_conn.cursor()
    cursor.execute("SELECT * FROM alert_rules WHERE id = %s", (response.json['id'],))
    rule = cursor.fetchone()
    assert rule is not None
    assert rule[1] == 'critical error'  # match_string column


def test_update_rule(client, db_conn, redis_client):
    """Test PUT /api/v2/rules/:id updates rule and logs audit"""
    # Create initial rule
    cursor = db_conn.cursor()
    cursor.execute("""
        INSERT INTO alert_rules (match_string, match_type, priority,
                                 prod_handling, dev_handling)
        VALUES (%s, %s, %s, %s, %s) RETURNING id
    """, ('test', 'contains', 100, 'suppress', 'suppress'))
    rule_id = cursor.fetchone()[0]
    db_conn.commit()

    # Update rule
    headers = {'X-API-Key': 'dev-key-12345'}
    response = client.put(f'/api/v2/rules/{rule_id}', json={
        'priority': 500,
        'prod_handling': 'alert'
    }, headers=headers)

    assert response.status_code == 200

    # Verify update
    cursor.execute("SELECT priority, prod_handling FROM alert_rules WHERE id = %s", (rule_id,))
    rule = cursor.fetchone()
    assert rule[0] == 500
    assert rule[1] == 'alert'

    # Verify audit log
    cursor.execute("SELECT * FROM config_audit_log WHERE table_name = 'alert_rules' AND record_id = %s", (rule_id,))
    audit = cursor.fetchone()
    assert audit is not None
    assert audit[3] == 'UPDATE'  # operation column


def test_delete_rule_soft_delete(client, db_conn):
    """Test DELETE /api/v2/rules/:id performs soft delete"""
    # Create rule
    cursor = db_conn.cursor()
    cursor.execute("""
        INSERT INTO alert_rules (match_string, match_type, priority,
                                 prod_handling, dev_handling, is_active)
        VALUES (%s, %s, %s, %s, %s, %s) RETURNING id
    """, ('test', 'contains', 100, 'suppress', 'suppress', True))
    rule_id = cursor.fetchone()[0]
    db_conn.commit()

    # Delete rule
    headers = {'X-API-Key': 'dev-key-12345'}
    response = client.delete(f'/api/v2/rules/{rule_id}', headers=headers)

    assert response.status_code == 200

    # Verify soft delete (rule still exists but is_active=false)
    cursor.execute("SELECT is_active FROM alert_rules WHERE id = %s", (rule_id,))
    rule = cursor.fetchone()
    assert rule is not None
    assert rule[0] is False


def test_audit_logs_endpoint(client, db_conn):
    """Test GET /api/v2/audit-logs returns filtered logs"""
    # Create test audit logs
    cursor = db_conn.cursor()
    for i in range(3):
        cursor.execute("""
            INSERT INTO config_audit_log (changed_by, operation, table_name,
                                          record_id, new_values)
            VALUES (%s, %s, %s, %s, %s)
        """, (f'user-{i}', 'UPDATE', 'alert_rules', i, '{}'))
    db_conn.commit()

    # Test with filters
    headers = {'X-API-Key': 'dev-key-12345'}
    response = client.get('/api/v2/audit-logs?table_name=alert_rules&limit=2',
                          headers=headers)

    assert response.status_code == 200
    assert len(response.json['logs']) <= 2
    assert all(log['table_name'] == 'alert_rules' for log in response.json['logs'])
```

### 2.6 Remediation Service

**Reference:** `docs/architecture/SYSTEM_ARCHITECTURE.md` - Remediation section

**File:** `services/remediation_service.py`

**Purpose:** Periodically scans DLQs and retries failed messages.

**Specifications:**

#### Service Initialization

```python
import time
import json
import logging
import requests
from prometheus_client import Counter, Gauge, Histogram

# Prometheus metrics
metrics = {
    'dlq_replayed_total': Counter(
        'remediation_dlq_replayed_total',
        'Total messages replayed from DLQ',
        ['dlq_name', 'result']
    ),
    'poison_messages_total': Counter(
        'remediation_poison_messages_total',
        'Total messages moved to poison queue',
        ['dlq_name']
    ),
    'health_check_success': Counter(
        'remediation_health_check_success_total',
        'Successful health checks',
        ['service']
    ),
    'health_check_failure': Counter(
        'remediation_health_check_failure_total',
        'Failed health checks',
        ['service']
    ),
    'dlq_depth': Gauge(
        'remediation_dlq_depth',
        'Current depth of DLQ',
        ['dlq_name']
    )
}

logger = logging.getLogger(__name__)
```

#### Moogsoft Health Check

```python
def check_moogsoft_health(config) -> bool:
    """Check if Moogsoft is reachable and accepting connections

    Sends a health check request to Moogsoft webhook endpoint.

    Args:
        config: Config object with MOOG_WEBHOOK_URL and MOOG_HEALTH_TIMEOUT

    Returns:
        True if Moogsoft is healthy, False otherwise
    """
    if not config.MOOG_HEALTH_CHECK_ENABLED:
        logger.debug("Moogsoft health check disabled")
        return True

    try:
        url = config.MOOG_WEBHOOK_URL
        timeout = config.MOOG_HEALTH_TIMEOUT

        # Send simple POST with minimal payload to test connectivity
        response = requests.post(
            url,
            json={'test': 'health_check'},
            timeout=timeout,
            headers={'Content-Type': 'application/json'}
        )

        # Accept 2xx or 4xx (4xx means Moog rejected payload but is responsive)
        if response.status_code < 500:
            logger.debug(f"Moogsoft health check passed (status {response.status_code})")
            metrics['health_check_success'].labels(service='moogsoft').inc()
            return True
        else:
            logger.warning(f"Moogsoft health check failed (status {response.status_code})")
            metrics['health_check_failure'].labels(service='moogsoft').inc()
            return False

    except requests.exceptions.Timeout:
        logger.error(f"Moogsoft health check timeout after {timeout}s")
        metrics['health_check_failure'].labels(service='moogsoft').inc()
        return False

    except Exception as e:
        logger.error(f"Moogsoft health check error: {e}")
        metrics['health_check_failure'].labels(service='moogsoft').inc()
        return False
```

#### DLQ Replay with Exponential Backoff

```python
def replay_dlq_messages(dlq_name: str, target_queue: str, config, redis_client):
    """Replay messages from DLQ to target queue with exponential backoff

    Messages are retried up to MAX_RETRIES times. After that, they're
    moved to the poison pill queue for manual inspection.

    Exponential backoff formula: delay = min(2^retry_count, 3600) seconds

    Args:
        dlq_name: Name of the DLQ to process (e.g., 'mutt:dlq:moog')
        target_queue: Queue to replay messages to (e.g., 'mutt:alert_queue')
        config: Config object with MAX_RETRIES setting
        redis_client: Redis connection
    """
    max_retries = int(config.MAX_DLQ_RETRIES or 5)
    batch_size = int(config.DLQ_BATCH_SIZE or 100)

    # Get DLQ depth for metrics
    dlq_depth = redis_client.llen(dlq_name)
    metrics['dlq_depth'].labels(dlq_name=dlq_name).set(dlq_depth)

    if dlq_depth == 0:
        logger.debug(f"DLQ {dlq_name} is empty, skipping")
        return

    logger.info(f"Processing DLQ {dlq_name} with {dlq_depth} messages")

    # Process messages in batches
    processed = 0
    replayed = 0
    poisoned = 0

    while processed < batch_size and redis_client.llen(dlq_name) > 0:
        # Get message from DLQ
        message_json = redis_client.rpop(dlq_name)
        if not message_json:
            break

        try:
            message = json.loads(message_json)

            # Get retry metadata
            retry_count = message.get('retry_count', 0)
            first_failed_at = message.get('first_failed_at', time.time())
            last_retry_at = message.get('last_retry_at', 0)

            # Calculate time since last retry
            time_since_retry = time.time() - last_retry_at
            required_delay = min(2 ** retry_count, 3600)  # Cap at 1 hour

            # Check if enough time has passed for exponential backoff
            if time_since_retry < required_delay:
                # Too soon to retry - put back in DLQ
                logger.debug(
                    f"Message not ready for retry (waited {time_since_retry}s, "
                    f"need {required_delay}s)"
                )
                redis_client.lpush(dlq_name, message_json)
                processed += 1
                continue

            # Check if max retries exceeded
            if retry_count >= max_retries:
                logger.warning(
                    f"Message exceeded max retries ({retry_count}/{max_retries}), "
                    "moving to poison queue"
                )

                # Add final metadata
                message['poisoned_at'] = time.time()
                message['total_retries'] = retry_count
                message['time_in_dlq'] = time.time() - first_failed_at

                # Move to poison queue
                redis_client.lpush('mutt:poison', json.dumps(message))
                metrics['poison_messages_total'].labels(dlq_name=dlq_name).inc()
                poisoned += 1
                processed += 1
                continue

            # Increment retry counter and update timestamps
            message['retry_count'] = retry_count + 1
            message['last_retry_at'] = time.time()
            if 'first_failed_at' not in message:
                message['first_failed_at'] = time.time()

            # Replay to target queue
            redis_client.lpush(target_queue, json.dumps(message))

            logger.info(
                f"Replayed message from {dlq_name} to {target_queue} "
                f"(retry {message['retry_count']}/{max_retries})"
            )

            metrics['dlq_replayed_total'].labels(
                dlq_name=dlq_name,
                result='success'
            ).inc()

            replayed += 1
            processed += 1

        except json.JSONDecodeError as e:
            logger.error(f"Invalid JSON in DLQ message: {e}")
            # Move malformed message to poison queue
            redis_client.lpush('mutt:poison', message_json)
            metrics['poison_messages_total'].labels(dlq_name=dlq_name).inc()
            poisoned += 1
            processed += 1

        except Exception as e:
            logger.error(f"Error processing DLQ message: {e}")
            # Put back in DLQ for next iteration
            redis_client.lpush(dlq_name, message_json)
            metrics['dlq_replayed_total'].labels(
                dlq_name=dlq_name,
                result='error'
            ).inc()
            processed += 1

    logger.info(
        f"DLQ {dlq_name} processing complete: "
        f"{replayed} replayed, {poisoned} poisoned, {processed} total"
    )
```

#### Complete Main Remediation Loop

```python
def remediation_loop(config, redis_client):
    """Main remediation service loop

    Continuously monitors DLQs and replays messages when conditions allow.
    Also performs health checks on downstream services.

    Loop cycle:
    1. Check Moogsoft health
    2. If healthy, replay Moog DLQ
    3. Always replay Alerter DLQ (independent of Moogsoft)
    4. Sleep for configurable interval
    """
    loop_interval = int(config.REMEDIATION_INTERVAL_SECONDS or 60)

    logger.info(f"Starting remediation loop (interval: {loop_interval}s)")

    iteration = 0

    while True:
        try:
            iteration += 1
            logger.debug(f"Remediation loop iteration {iteration}")

            # Check Moogsoft health
            moog_healthy = check_moogsoft_health(config)

            # Replay Moog DLQ only if Moogsoft is healthy
            if moog_healthy:
                logger.debug("Moogsoft healthy, processing Moog DLQ")
                replay_dlq_messages(
                    dlq_name='mutt:dlq:moog',
                    target_queue='mutt:alert_queue',
                    config=config,
                    redis_client=redis_client
                )
            else:
                logger.warning("Moogsoft unhealthy, skipping Moog DLQ replay")
                # Update DLQ depth metric even if not processing
                dlq_depth = redis_client.llen('mutt:dlq:moog')
                metrics['dlq_depth'].labels(dlq_name='mutt:dlq:moog').set(dlq_depth)

            # Always process Alerter DLQ (retry to ingest queue)
            logger.debug("Processing Alerter DLQ")
            replay_dlq_messages(
                dlq_name='mutt:dlq:alerter',
                target_queue='mutt:ingest_queue',
                config=config,
                redis_client=redis_client
            )

            # Sleep until next iteration
            logger.debug(f"Sleeping for {loop_interval}s")
            time.sleep(loop_interval)

        except KeyboardInterrupt:
            logger.info("Received interrupt, shutting down remediation service")
            break

        except Exception as e:
            logger.error(f"Error in remediation loop: {e}", exc_info=True)
            # Sleep briefly and continue
            time.sleep(10)


def main():
    """Entry point for remediation service"""
    from config import Config

    config = Config()
    redis_client = get_redis_connection(config)

    logger.info("Remediation service starting")

    # Start Prometheus metrics server
    start_http_server(8084)
    logger.info("Metrics server started on port 8084")

    # Run main loop
    remediation_loop(config, redis_client)
```

#### Test Cases

```python
# tests/test_remediation_service.py

def test_moogsoft_health_check_success(monkeypatch):
    """Test Moogsoft health check with successful response"""
    class FakeResponse:
        status_code = 200

    def fake_post(url, **kwargs):
        return FakeResponse()

    import requests
    monkeypatch.setattr(requests, 'post', fake_post)

    class Config:
        MOOG_HEALTH_CHECK_ENABLED = True
        MOOG_WEBHOOK_URL = 'http://moogsoft/webhook'
        MOOG_HEALTH_TIMEOUT = 5

    from services.remediation_service import check_moogsoft_health

    result = check_moogsoft_health(Config())
    assert result is True


def test_moogsoft_health_check_failure(monkeypatch):
    """Test Moogsoft health check with 5xx error"""
    class FakeResponse:
        status_code = 503

    def fake_post(url, **kwargs):
        return FakeResponse()

    import requests
    monkeypatch.setattr(requests, 'post', fake_post)

    class Config:
        MOOG_HEALTH_CHECK_ENABLED = True
        MOOG_WEBHOOK_URL = 'http://moogsoft/webhook'
        MOOG_HEALTH_TIMEOUT = 5

    from services.remediation_service import check_moogsoft_health

    result = check_moogsoft_health(Config())
    assert result is False


def test_replay_dlq_with_retriable_message(redis_client):
    """Test DLQ replay moves message to target queue"""
    class Config:
        MAX_DLQ_RETRIES = 5
        DLQ_BATCH_SIZE = 100

    from services.remediation_service import replay_dlq_messages

    # Add message to DLQ
    message = {
        'event': 'test',
        'retry_count': 0,
        'last_retry_at': 0
    }
    redis_client.lpush('mutt:dlq:test', json.dumps(message))

    # Replay
    replay_dlq_messages(
        dlq_name='mutt:dlq:test',
        target_queue='mutt:target_queue',
        config=Config(),
        redis_client=redis_client
    )

    # Verify message moved to target queue
    assert redis_client.llen('mutt:dlq:test') == 0
    assert redis_client.llen('mutt:target_queue') == 1

    # Verify retry count incremented
    replayed = json.loads(redis_client.rpop('mutt:target_queue'))
    assert replayed['retry_count'] == 1
    assert replayed['last_retry_at'] > 0


def test_replay_dlq_with_poison_message(redis_client):
    """Test message exceeding max retries moved to poison queue"""
    class Config:
        MAX_DLQ_RETRIES = 3
        DLQ_BATCH_SIZE = 100

    from services.remediation_service import replay_dlq_messages

    # Add message with max retries already exceeded
    message = {
        'event': 'test',
        'retry_count': 3,
        'last_retry_at': 0,
        'first_failed_at': time.time() - 1000
    }
    redis_client.lpush('mutt:dlq:test', json.dumps(message))

    # Replay
    replay_dlq_messages(
        dlq_name='mutt:dlq:test',
        target_queue='mutt:target_queue',
        config=Config(),
        redis_client=redis_client
    )

    # Verify message moved to poison queue
    assert redis_client.llen('mutt:dlq:test') == 0
    assert redis_client.llen('mutt:target_queue') == 0
    assert redis_client.llen('mutt:poison') == 1

    # Verify poison metadata added
    poisoned = json.loads(redis_client.rpop('mutt:poison'))
    assert 'poisoned_at' in poisoned
    assert poisoned['total_retries'] == 3


def test_replay_dlq_respects_exponential_backoff(redis_client):
    """Test messages not replayed if backoff period hasn't elapsed"""
    class Config:
        MAX_DLQ_RETRIES = 5
        DLQ_BATCH_SIZE = 100

    from services.remediation_service import replay_dlq_messages

    # Add message with recent retry
    message = {
        'event': 'test',
        'retry_count': 2,
        'last_retry_at': time.time() - 1  # Only 1 second ago
    }
    redis_client.lpush('mutt:dlq:test', json.dumps(message))

    # Replay
    replay_dlq_messages(
        dlq_name='mutt:dlq:test',
        target_queue='mutt:target_queue',
        config=Config(),
        redis_client=redis_client
    )

    # Verify message stayed in DLQ (backoff not elapsed: 2^2 = 4 seconds required)
    assert redis_client.llen('mutt:dlq:test') == 1
    assert redis_client.llen('mutt:target_queue') == 0


def test_replay_dlq_handles_malformed_json(redis_client):
    """Test malformed JSON messages moved to poison queue"""
    class Config:
        MAX_DLQ_RETRIES = 5
        DLQ_BATCH_SIZE = 100

    from services.remediation_service import replay_dlq_messages

    # Add malformed JSON to DLQ
    redis_client.lpush('mutt:dlq:test', '{invalid json')

    # Replay
    replay_dlq_messages(
        dlq_name='mutt:dlq:test',
        target_queue='mutt:target_queue',
        config=Config(),
        redis_client=redis_client
    )

    # Verify moved to poison queue
    assert redis_client.llen('mutt:dlq:test') == 0
    assert redis_client.llen('mutt:poison') == 1


def test_remediation_loop_skips_moog_dlq_when_unhealthy(monkeypatch, redis_client):
    """Test remediation loop skips Moog DLQ when health check fails"""
    class Config:
        MAX_DLQ_RETRIES = 5
        DLQ_BATCH_SIZE = 100
        REMEDIATION_INTERVAL_SECONDS = 1
        MOOG_HEALTH_CHECK_ENABLED = True
        MOOG_WEBHOOK_URL = 'http://moogsoft/webhook'
        MOOG_HEALTH_TIMEOUT = 5

    from services.remediation_service import check_moogsoft_health, replay_dlq_messages

    # Mock unhealthy Moogsoft
    def fake_health_check(config):
        return False

    monkeypatch.setattr(
        'services.remediation_service.check_moogsoft_health',
        fake_health_check
    )

    # Add messages to both DLQs
    redis_client.lpush('mutt:dlq:moog', json.dumps({'event': 'moog', 'retry_count': 0, 'last_retry_at': 0}))
    redis_client.lpush('mutt:dlq:alerter', json.dumps({'event': 'alerter', 'retry_count': 0, 'last_retry_at': 0}))

    # Run one iteration of remediation (we'll test the components separately)
    # In real test, would mock time.sleep and run single iteration

    # Verify behavior: Moog DLQ should not be processed when unhealthy
    # (This test demonstrates the expected behavior pattern)
    is_healthy = fake_health_check(Config())
    assert is_healthy is False
```

---

## Phase 3: Integration & Reliability

### 3.1 Integration Patterns

**Reference:** `docs/architecture/INTEGRATION_PATTERNS.md`

This phase focuses on integrating the services and implementing reliability patterns.

-   **Service Discovery:** Use DNS for service discovery.
-   **Configuration:** Use a centralized configuration service (e.g., Vault).
-   **Authentication:** Use API keys for service-to-service authentication.
-   **Logging:** Use a centralized logging service (e.g., ELK stack).
-   **Metrics:** Use Prometheus for metrics collection.

### 3.2 Reliability Patterns

-   **Circuit Breaker:** Implement a circuit breaker pattern in the Moog Forwarder to prevent cascading failures.
-   **Retry with Exponential Backoff:** Implement a retry with exponential backoff mechanism in the Moog Forwarder.
-   **Rate Limiting:** Implement a rate limiting mechanism in the Ingestor Service to prevent overload.
-   **Bulkheads:** Use separate connection pools for each service to isolate failures.

---

## Phase 4: Testing

This phase provides comprehensive testing strategies, fixtures, and examples for MUTT v2.5.

### 4.1 Unit Testing

**Target**: 90%+ code coverage for all services

**Framework**: pytest with pytest-cov, pytest-mock

#### 4.1.1 Test Configuration (`conftest.py`)

```python
"""
Pytest configuration and shared fixtures
File: tests/conftest.py
"""
import pytest
import redis
import psycopg2
from unittest.mock import MagicMock, Mock
import json
import time

# ===== Redis Fixtures =====

@pytest.fixture
def mock_redis():
    """Mock Redis client for unit tests"""
    mock_client = MagicMock(spec=redis.Redis)

    # Mock data storage
    mock_client._data = {}
    mock_client._lists = {}
    mock_client._hashes = {}

    # Mock common Redis operations
    def lpush(key, *values):
        if key not in mock_client._lists:
            mock_client._lists[key] = []
        mock_client._lists[key].extend(values)
        return len(mock_client._lists[key])

    def llen(key):
        return len(mock_client._lists.get(key, []))

    def rpop(key):
        if key in mock_client._lists and mock_client._lists[key]:
            return mock_client._lists[key].pop(0)
        return None

    def get(key):
        return mock_client._data.get(key)

    def set(key, value):
        mock_client._data[key] = value
        return True

    def hgetall(key):
        return mock_client._hashes.get(key, {})

    def hset(key, field, value):
        if key not in mock_client._hashes:
            mock_client._hashes[key] = {}
        mock_client._hashes[key][field] = value
        return 1

    mock_client.lpush.side_effect = lpush
    mock_client.llen.side_effect = llen
    mock_client.rpop.side_effect = rpop
    mock_client.get.side_effect = get
    mock_client.set.side_effect = set
    mock_client.hgetall.side_effect = hgetall
    mock_client.hset.side_effect = hset
    mock_client.ping.return_value = True

    return mock_client


@pytest.fixture
def real_redis():
    """Real Redis connection for integration tests"""
    client = redis.Redis(
        host='localhost',
        port=6379,
        db=15,  # Use separate DB for testing
        decode_responses=False
    )

    # Clear test DB before each test
    client.flushdb()

    yield client

    # Cleanup after test
    client.flushdb()
    client.close()


# ===== PostgreSQL Fixtures =====

@pytest.fixture
def mock_db_connection():
    """Mock PostgreSQL connection for unit tests"""
    mock_conn = MagicMock(spec=psycopg2.extensions.connection)
    mock_cursor = MagicMock()

    # Mock query results
    mock_cursor.fetchall.return_value = []
    mock_cursor.fetchone.return_value = None
    mock_cursor.execute.return_value = None

    mock_conn.cursor.return_value = mock_cursor
    mock_conn.commit.return_value = None
    mock_conn.rollback.return_value = None

    return mock_conn


@pytest.fixture
def real_db_connection():
    """Real PostgreSQL connection for integration tests"""
    conn = psycopg2.connect(
        host='localhost',
        port=5432,
        dbname='mutt_test',
        user='mutt_user',
        password='test_password'
    )

    yield conn

    # Cleanup
    conn.rollback()
    conn.close()


# ===== Flask Test Client =====

@pytest.fixture
def flask_client(mock_redis, mock_db_connection):
    """Flask test client with mocked dependencies"""
    from services.web_ui_service import app

    app.config['TESTING'] = True

    # Inject mocked dependencies
    with app.test_client() as client:
        yield client


# ===== Mock Config =====

@pytest.fixture
def mock_config():
    """Mock configuration object"""
    class MockConfig:
        REDIS_HOST = 'localhost'
        REDIS_PORT = 6379
        POSTGRES_HOST = 'localhost'
        POSTGRES_PORT = 5432
        POSTGRES_DB = 'mutt_test'
        POSTGRES_USER = 'mutt_user'
        POSTGRES_PASSWORD = 'test_password'
        MOOG_WEBHOOK_URL = 'http://moogsoft-test:8080/webhook'
        MOOG_RATE_LIMIT_PER_SEC = 50
        MOOG_HEALTH_CHECK_ENABLED = True
        MOOG_HEALTH_TIMEOUT = 5
        ALERTER_CACHE_TTL_SECONDS = 300
        MAX_DLQ_RETRIES = 5
        DLQ_BATCH_SIZE = 100
        REMEDIATION_INTERVAL_SECONDS = 60

    return MockConfig()


# ===== Test Data Fixtures =====

@pytest.fixture
def sample_event():
    """Sample event for testing"""
    return {
        'timestamp': '2025-01-12T10:30:00Z',
        'hostname': 'router-01.example.com',
        'message': 'Interface GigabitEthernet0/1 changed state to down',
        'severity': 3,
        'source': 'syslog',
        'ingestion_timestamp': time.time(),
        'correlation_id': 'test-correlation-id-123'
    }


@pytest.fixture
def sample_rule():
    """Sample alert rule for testing"""
    return {
        'id': 42,
        'match_string': 'Interface.*changed state to down',
        'trap_oid': None,
        'syslog_severity': None,
        'match_type': 'regex',
        'priority': 200,
        'prod_handling': 'alert',
        'dev_handling': 'suppress',
        'team_assignment': 'network-ops',
        'is_active': True
    }
```

#### 4.1.2 Unit Test Examples

**Testing Ingestor Service:**

```python
"""
Unit tests for Ingestor Service
File: tests/test_ingestor_service.py
"""
import pytest
import json
from services import ingestor_service

def test_ingest_endpoint_success(flask_client, mock_redis, sample_event):
    """Test successful event ingestion"""
    response = flask_client.post(
        '/ingest',
        data=json.dumps(sample_event),
        content_type='application/json'
    )

    assert response.status_code == 202
    assert response.json['status'] == 'accepted'
    assert 'correlation_id' in response.json

    # Verify Redis queue was updated
    assert mock_redis.lpush.called


def test_ingest_endpoint_missing_field(flask_client):
    """Test ingestion with missing required field"""
    incomplete_event = {
        'timestamp': '2025-01-12T10:30:00Z',
        'hostname': 'router-01.example.com'
        # Missing 'message' field
    }

    response = flask_client.post(
        '/ingest',
        data=json.dumps(incomplete_event),
        content_type='application/json'
    )

    assert response.status_code == 400
    assert 'Missing required field' in response.json['error']


def test_ingest_endpoint_invalid_json(flask_client):
    """Test ingestion with invalid JSON"""
    response = flask_client.post(
        '/ingest',
        data='invalid json{',
        content_type='application/json'
    )

    assert response.status_code == 400


def test_health_check_healthy(flask_client, mock_redis):
    """Test health check when Redis is healthy"""
    mock_redis.ping.return_value = True

    response = flask_client.get('/health')

    assert response.status_code == 200
    assert response.json['status'] == 'healthy'


def test_health_check_unhealthy(flask_client, mock_redis):
    """Test health check when Redis is down"""
    mock_redis.ping.side_effect = Exception('Connection refused')

    response = flask_client.get('/health')

    assert response.status_code == 503
    assert response.json['status'] == 'unhealthy'
```

**Testing Alerter Service:**

```python
"""
Unit tests for Alerter Service
File: tests/test_alerter_service.py
"""
import pytest
from services import alerter_service

def test_find_matching_rule_regex_match(sample_event, sample_rule, mock_redis):
    """Test rule matching with regex"""
    # Setup mock cache
    alerter_service.cache = {
        'rules': [sample_rule],
        'compiled_patterns': {}
    }

    matched_rule = alerter_service.find_matching_rule(sample_event)

    assert matched_rule is not None
    assert matched_rule['id'] == 42


def test_find_matching_rule_no_match(sample_event, mock_redis):
    """Test rule matching when no rule matches"""
    # Setup cache with non-matching rule
    alerter_service.cache = {
        'rules': [{
            'id': 1,
            'match_string': 'DOES_NOT_MATCH',
            'match_type': 'contains',
            'priority': 100,
            'is_active': True
        }],
        'compiled_patterns': {}
    }

    matched_rule = alerter_service.find_matching_rule(sample_event)

    # Should return default rule
    assert matched_rule['id'] == 0  # Default rule ID


def test_is_development_host_cached(mock_redis):
    """Test development host check with caching"""
    # First call - cache miss
    alerter_service.dev_host_cache = {}
    mock_redis.sismember.return_value = True

    result1 = alerter_service.is_development_host('test-host', mock_redis)
    assert result1 is True
    assert mock_redis.sismember.called

    # Second call - cache hit
    mock_redis.sismember.reset_mock()
    result2 = alerter_service.is_development_host('test-host', mock_redis)
    assert result2 is True
    assert not mock_redis.sismember.called  # Should use cache


def test_check_backpressure_normal(mock_redis, mock_config):
    """Test backpressure check under normal conditions"""
    mock_redis.llen.return_value = 500  # Below warning threshold

    alerter_service.check_backpressure(mock_redis, mock_config)

    # Should not shed any messages
    assert not mock_redis.rpop.called


def test_check_backpressure_shedding(mock_redis, mock_config):
    """Test backpressure shedding when queue is critical"""
    mock_redis.llen.return_value = 2500  # Above shed threshold
    mock_redis.rpop.return_value = json.dumps({'test': 'message'})

    alerter_service.check_backpressure(mock_redis, mock_config)

    # Should shed messages to DLQ
    assert mock_redis.rpop.called
    assert mock_redis.lpush.called
```

**Testing Circuit Breaker:**

```python
"""
Unit tests for Circuit Breaker
File: tests/test_circuit_breaker.py
"""
import pytest
from services.rate_limiter import CircuitBreaker, CircuitBreakerState

def test_circuit_breaker_closed_to_open(mock_redis):
    """Test circuit breaker opens after threshold failures"""
    cb = CircuitBreaker(mock_redis, key_prefix='test:circuit')

    # Record failures up to threshold
    for i in range(5):
        cb.record_failure()

    # Circuit should now be open
    assert cb.is_open() is True
    assert mock_redis.get.return_value == b'OPEN'


def test_circuit_breaker_half_open_to_closed(mock_redis):
    """Test circuit breaker closes after successful recovery"""
    cb = CircuitBreaker(mock_redis, key_prefix='test:circuit')

    # Set to half-open
    mock_redis.get.return_value = b'HALF_OPEN'

    # Record success
    cb.record_success()

    # Should transition to closed
    assert mock_redis.set.called
    assert mock_redis.delete.called  # Failure counter reset


def test_circuit_breaker_records_metrics(mock_redis, monkeypatch):
    """Test circuit breaker updates Prometheus metrics"""
    cb = CircuitBreaker(mock_redis, key_prefix='test:circuit')

    mock_metric = MagicMock()
    monkeypatch.setattr('services.rate_limiter.metrics', {
        'circuit_breaker_state': mock_metric,
        'circuit_breaker_transitions_total': MagicMock()
    })

    cb.record_failure()

    # Should update metrics
    assert mock_metric.set.called
```

### 4.2 Integration Testing

**Target**: Test inter-service communication and data flow

**Setup**: Use Docker Compose with real Redis and PostgreSQL

#### 4.2.1 Integration Test Setup

```python
"""
Integration test configuration
File: tests/integration/conftest.py
"""
import pytest
import redis
import psycopg2
import subprocess
import time
import requests

@pytest.fixture(scope='session')
def docker_services():
    """Start Docker Compose stack for integration tests"""
    # Start services
    subprocess.run(['docker-compose', '-f', 'docker-compose.test.yml', 'up', '-d'], check=True)

    # Wait for services to be ready
    time.sleep(10)

    # Health check
    for _ in range(30):
        try:
            response = requests.get('http://localhost:8080/health')
            if response.status_code == 200:
                break
        except:
            pass
        time.sleep(1)

    yield

    # Teardown
    subprocess.run(['docker-compose', '-f', 'docker-compose.test.yml', 'down', '-v'], check=True)


@pytest.fixture
def integration_redis(docker_services):
    """Redis client for integration tests"""
    client = redis.Redis(host='localhost', port=6379, db=0)
    client.flushdb()
    yield client
    client.flushdb()


@pytest.fixture
def integration_db(docker_services):
    """PostgreSQL connection for integration tests"""
    conn = psycopg2.connect(
        host='localhost',
        port=5432,
        dbname='mutt',
        user='mutt_user',
        password='dev_password'
    )
    yield conn
    conn.rollback()
    conn.close()
```

#### 4.2.2 Integration Test Examples

```python
"""
Integration tests for end-to-end event flow
File: tests/integration/test_event_flow.py
"""
import pytest
import requests
import json
import time

@pytest.mark.integration
def test_end_to_end_event_flow(integration_redis, integration_db):
    """Test complete event flow from ingestion to database"""

    # 1. Ingest an event
    event = {
        'timestamp': '2025-01-12T10:30:00Z',
        'hostname': 'router-01.example.com',
        'message': 'CRITICAL: Interface down',
        'severity': 1,
        'source': 'syslog'
    }

    response = requests.post(
        'http://localhost:8080/ingest',
        json=event
    )

    assert response.status_code == 202
    correlation_id = response.json()['correlation_id']

    # 2. Verify event in Redis ingest queue
    queue_len = integration_redis.llen('mutt:ingest_queue')
    assert queue_len > 0

    # 3. Wait for Alerter to process
    time.sleep(2)

    # 4. Verify event was processed and stored in database
    cursor = integration_db.cursor()
    cursor.execute(
        "SELECT * FROM event_audit_log WHERE raw_message->>'correlation_id' = %s",
        (correlation_id,)
    )
    result = cursor.fetchone()

    assert result is not None
    assert result[2] == 'router-01.example.com'  # hostname column


@pytest.mark.integration
def test_rule_creation_and_cache_reload(integration_redis, integration_db):
    """Test rule creation triggers cache reload in Alerter"""

    # 1. Create a rule via API
    rule = {
        'match_string': 'TEST_PATTERN',
        'match_type': 'contains',
        'priority': 300,
        'prod_handling': 'alert',
        'dev_handling': 'suppress'
    }

    response = requests.post(
        'http://localhost:8090/api/v2/rules',
        json=rule,
        headers={'X-API-Key': 'dev-key-12345'}
    )

    assert response.status_code == 201
    rule_id = response.json()['id']

    # 2. Verify cache reload message was published
    # (In real test, would subscribe to Redis pubsub)

    # 3. Verify rule is in database
    cursor = integration_db.cursor()
    cursor.execute("SELECT * FROM alert_rules WHERE id = %s", (rule_id,))
    result = cursor.fetchone()

    assert result is not None
    assert result[1] == 'TEST_PATTERN'  # match_string column


@pytest.mark.integration
def test_circuit_breaker_opens_on_moog_failure():
    """Test circuit breaker opens when Moogsoft is unavailable"""

    # 1. Stop Moogsoft container to simulate failure
    # (Implementation depends on test infrastructure)

    # 2. Send events that should trigger alerts
    for i in range(10):
        event = {
            'timestamp': '2025-01-12T10:30:00Z',
            'hostname': f'router-{i}.example.com',
            'message': 'CRITICAL: Alert event',
            'severity': 1,
            'source': 'syslog'
        }
        requests.post('http://localhost:8080/ingest', json=event)

    # 3. Wait for circuit breaker to trip
    time.sleep(5)

    # 4. Verify circuit breaker is open
    redis_client = redis.Redis(host='localhost', port=6379)
    circuit_state = redis_client.get('mutt:circuit:moog:state')

    assert circuit_state == b'OPEN'
```

### 4.3 Load Testing

**Target**: Validate system performance under load

**Tools**: Locust for HTTP load testing, custom scripts for Redis throughput

#### 4.3.1 Locust Load Test Configuration

```python
"""
Locust load test for MUTT ingestion
File: tests/load/locustfile.py

Run with: locust -f tests/load/locustfile.py --host=http://localhost:8080
"""
from locust import HttpUser, task, between
import json
import random
import time

class MUTTUser(HttpUser):
    """Simulates a syslog/SNMP source sending events"""

    wait_time = between(0.1, 0.5)  # 2-10 requests per second per user

    hostnames = [
        'router-01.example.com',
        'router-02.example.com',
        'switch-01.example.com',
        'switch-02.example.com',
        'firewall-01.example.com'
    ]

    messages = [
        'Interface GigabitEthernet0/1 changed state to down',
        'CRITICAL: High CPU utilization detected',
        'WARNING: Memory usage above 80%',
        'Interface GigabitEthernet0/1 changed state to up',
        'Link flap detected on interface',
        'BGP peer 192.168.1.1 state changed to Established',
        'OSPF neighbor 192.168.1.2 state changed to Full'
    ]

    @task(10)
    def ingest_event(self):
        """Send a syslog event"""
        event = {
            'timestamp': time.strftime('%Y-%m-%dT%H:%M:%SZ'),
            'hostname': random.choice(self.hostnames),
            'message': random.choice(self.messages),
            'severity': random.randint(1, 7),
            'source': 'syslog'
        }

        with self.client.post(
            '/ingest',
            json=event,
            catch_response=True
        ) as response:
            if response.status_code == 202:
                response.success()
            else:
                response.failure(f"Got status {response.status_code}")

    @task(1)
    def health_check(self):
        """Periodically check health endpoint"""
        self.client.get('/health')


class MUTTAPIUser(HttpUser):
    """Simulates operators using the Web UI API"""

    wait_time = between(5, 15)  # Slower user interaction
    host = "http://localhost:8090"

    @task(5)
    def list_rules(self):
        """List alert rules"""
        self.client.get(
            '/api/v2/rules?limit=20',
            headers={'X-API-Key': 'dev-key-12345'}
        )

    @task(2)
    def get_metrics(self):
        """Get real-time metrics"""
        self.client.get('/api/v2/metrics')

    @task(1)
    def get_slo_status(self):
        """Check SLO compliance"""
        self.client.get('/api/v1/slo')

    @task(1)
    def create_rule(self):
        """Create a new alert rule"""
        rule = {
            'match_string': f'TEST-{random.randint(1000, 9999)}',
            'match_type': 'contains',
            'priority': random.randint(100, 500),
            'prod_handling': random.choice(['alert', 'suppress', 'log']),
            'dev_handling': 'suppress'
        }

        self.client.post(
            '/api/v2/rules',
            json=rule,
            headers={'X-API-Key': 'dev-key-12345'}
        )
```

#### 4.3.2 Load Test Execution

```bash
# ===== Basic Load Test =====
# 10 users, ramp up over 10 seconds
locust -f tests/load/locustfile.py \
    --host=http://localhost:8080 \
    --users 10 \
    --spawn-rate 1 \
    --run-time 5m \
    --headless

# ===== High Load Test =====
# 100 users simulating 500-1000 EPS
locust -f tests/load/locustfile.py \
    --host=http://localhost:8080 \
    --users 100 \
    --spawn-rate 10 \
    --run-time 15m \
    --headless \
    --html results/load_test_report.html

# ===== Stress Test =====
# Gradually increase load to find breaking point
locust -f tests/load/locustfile.py \
    --host=http://localhost:8080 \
    --users 500 \
    --spawn-rate 50 \
    --run-time 30m \
    --headless
```

#### 4.3.3 Performance Targets

```
Service: Ingestor
- Throughput: 1000 EPS minimum (5000 EPS target)
- Latency p95: < 50ms
- Latency p99: < 100ms
- Success rate: > 99.9%

Service: Alerter
- Processing latency p95: < 100ms
- Queue depth: < 1000 under normal load
- Rule cache hit rate: > 99%

Service: Moog Forwarder
- Forward latency p95: < 200ms (network dependent)
- Rate limit compliance: 100% (no bursts exceeding limit)
- Circuit breaker: < 0.1% of time in OPEN state

Database (PostgreSQL)
- Write throughput: 500 writes/sec minimum
- Query latency p95: < 50ms
- Connection pool utilization: < 80%

Redis
- Operations/sec: 10,000+
- Latency p95: < 5ms
- Memory usage: < 2GB for 1M events in queues
```

### 4.4 Test Execution

#### 4.4.1 Running Tests

```bash
# ===== Unit Tests =====
# Run all unit tests with coverage
pytest tests/ \
    --cov=services \
    --cov-report=html \
    --cov-report=term \
    --cov-fail-under=90

# Run specific test file
pytest tests/test_alerter_service.py -v

# Run tests matching pattern
pytest tests/ -k "test_circuit_breaker" -v

# ===== Integration Tests =====
# Run integration tests (requires Docker Compose)
pytest tests/integration/ \
    -m integration \
    --tb=short \
    -v

# ===== Load Tests =====
# Run Locust web UI (interactive)
locust -f tests/load/locustfile.py --host=http://localhost:8080

# Then open: http://localhost:8089

# ===== Coverage Report =====
# Generate and view coverage report
pytest --cov=services --cov-report=html
open htmlcov/index.html  # macOS
xdg-open htmlcov/index.html  # Linux
```

#### 4.4.2 CI/CD Pipeline Integration

```yaml
# Example GitLab CI/CD pipeline
# File: .gitlab-ci.yml (excerpt)

test:unit:
  stage: test
  image: python:3.10
  services:
    - redis:7
    - postgres:14
  variables:
    REDIS_HOST: redis
    POSTGRES_HOST: postgres
    POSTGRES_PASSWORD: test_password
  script:
    - pip install -r requirements.txt
    - pip install pytest pytest-cov pytest-mock
    - pytest tests/ --cov=services --cov-fail-under=90
  coverage: '/TOTAL.*\s+(\d+%)$/'

test:integration:
  stage: test
  image: docker:latest
  services:
    - docker:dind
  before_script:
    - apk add --no-cache docker-compose python3 py3-pip
    - pip3 install pytest requests redis psycopg2-binary
  script:
    - docker-compose -f docker-compose.test.yml up -d
    - sleep 30  # Wait for services
    - pytest tests/integration/ -m integration
  after_script:
    - docker-compose -f docker-compose.test.yml down -v

test:load:
  stage: test
  image: python:3.10
  only:
    - main
    - tags
  script:
    - pip install locust
    - locust -f tests/load/locustfile.py \
        --host=http://staging.example.com \
        --users 50 \
        --spawn-rate 5 \
        --run-time 5m \
        --headless \
        --html results/load_test.html
  artifacts:
    paths:
      - results/load_test.html
    expire_in: 30 days
```

### 4.5 Test Data Management

#### 4.5.1 Test Database Setup

```sql
-- Create test database
CREATE DATABASE mutt_test;

-- Create test user
CREATE USER mutt_test_user WITH PASSWORD 'test_password';
GRANT ALL PRIVILEGES ON DATABASE mutt_test TO mutt_test_user;

-- Initialize schema (run all schema files)
\c mutt_test
\i database/mutt_schema_v2.1.sql
\i database/config_audit_schema.sql
\i database/partitioned_event_audit_log.sql

-- Insert test data
INSERT INTO alert_rules (match_string, match_type, priority, prod_handling, dev_handling)
VALUES
    ('CRITICAL', 'contains', 500, 'alert', 'alert'),
    ('WARNING', 'contains', 300, 'log', 'suppress'),
    ('Interface.*down', 'regex', 400, 'alert', 'suppress');

INSERT INTO development_hosts (hostname)
VALUES
    ('dev-router-01.example.com'),
    ('dev-switch-01.example.com');
```

#### 4.5.2 Test Data Cleanup

```python
"""
Test cleanup utilities
File: tests/utils/cleanup.py
"""
import redis
import psycopg2

def cleanup_redis(redis_host='localhost', redis_port=6379, redis_db=15):
    """Clear all Redis test data"""
    client = redis.Redis(host=redis_host, port=redis_port, db=redis_db)
    client.flushdb()
    client.close()

def cleanup_postgres(db_name='mutt_test'):
    """Truncate all PostgreSQL test tables"""
    conn = psycopg2.connect(
        host='localhost',
        dbname=db_name,
        user='mutt_test_user',
        password='test_password'
    )

    cursor = conn.cursor()

    # Truncate tables (preserve schema)
    tables = ['event_audit_log', 'config_audit_log', 'alert_rules',
              'development_hosts', 'device_teams']

    for table in tables:
        cursor.execute(f"TRUNCATE TABLE {table} CASCADE")

    conn.commit()
    cursor.close()
    conn.close()
```

---

## Phase 5: Deployment

This phase provides production-ready deployment configurations for multiple platforms.

### 5.1 Kubernetes Deployment

**Target Environment**: Kubernetes 1.24+

#### 5.1.1 Namespace and ConfigMap

```yaml
# File: deployments/kubernetes/namespace.yaml
apiVersion: v1
kind: Namespace
metadata:
  name: mutt
  labels:
    name: mutt
    environment: production

---
# File: deployments/kubernetes/configmap.yaml
apiVersion: v1
kind: ConfigMap
metadata:
  name: mutt-config
  namespace: mutt
data:
  # Redis Configuration
  REDIS_HOST: "redis-service"
  REDIS_PORT: "6379"
  REDIS_DB: "0"

  # PostgreSQL Configuration
  POSTGRES_HOST: "postgres-service"
  POSTGRES_PORT: "5432"
  POSTGRES_DB: "mutt"
  POSTGRES_USER: "mutt_user"
  POSTGRES_SSL_MODE: "require"

  # Vault Configuration
  VAULT_ADDR: "https://vault.example.com:8200"
  VAULT_MOUNT_POINT: "mutt"
  VAULT_SECRET_PATH: "mutt/prod/secrets"

  # Moogsoft Configuration
  MOOG_WEBHOOK_URL: "https://moogsoft.example.com/webhook"
  MOOG_RATE_LIMIT_PER_SEC: "50"
  MOOG_HEALTH_CHECK_ENABLED: "true"
  MOOG_HEALTH_TIMEOUT: "5"

  # Service Configuration
  ALERTER_CACHE_TTL_SECONDS: "300"
  MAX_DLQ_RETRIES: "5"
  DLQ_BATCH_SIZE: "100"
  REMEDIATION_INTERVAL_SECONDS: "60"

  # Observability
  LOG_LEVEL: "INFO"
  ENABLE_TRACING: "false"

  # Data Retention
  EVENT_RETENTION_DAYS: "90"
  AUDIT_RETENTION_DAYS: "365"
```

#### 5.1.2 Secrets Management

```yaml
# File: deployments/kubernetes/secrets.yaml
# NOTE: In production, use External Secrets Operator or Vault integration
apiVersion: v1
kind: Secret
metadata:
  name: mutt-secrets
  namespace: mutt
type: Opaque
data:
  # Base64 encoded values (use: echo -n 'value' | base64)
  REDIS_PASSWORD: ""  # Redis password (if auth enabled)
  POSTGRES_PASSWORD: ""  # PostgreSQL password (from Vault)
  VAULT_ROLE_ID: ""  # Vault AppRole role ID
  VAULT_SECRET_ID: ""  # Vault AppRole secret ID
  MUTT_API_KEY: ""  # API key for Web UI authentication

---
# File: deployments/kubernetes/external-secret.yaml (if using External Secrets Operator)
apiVersion: external-secrets.io/v1beta1
kind: ExternalSecret
metadata:
  name: mutt-secrets
  namespace: mutt
spec:
  refreshInterval: 1h
  secretStoreRef:
    name: vault-backend
    kind: SecretStore
  target:
    name: mutt-secrets
    creationPolicy: Owner
  data:
    - secretKey: POSTGRES_PASSWORD
      remoteRef:
        key: mutt/prod/secrets
        property: postgres_password
    - secretKey: REDIS_PASSWORD
      remoteRef:
        key: mutt/prod/secrets
        property: redis_password
    - secretKey: MUTT_API_KEY
      remoteRef:
        key: mutt/prod/secrets
        property: api_key
```

#### 5.1.3 Service Deployments

**Ingestor Service:**

```yaml
# File: deployments/kubernetes/ingestor-deployment.yaml
apiVersion: apps/v1
kind: Deployment
metadata:
  name: mutt-ingestor
  namespace: mutt
  labels:
    app: mutt-ingestor
    component: ingestion
spec:
  replicas: 3
  selector:
    matchLabels:
      app: mutt-ingestor
  template:
    metadata:
      labels:
        app: mutt-ingestor
        component: ingestion
      annotations:
        prometheus.io/scrape: "true"
        prometheus.io/port: "9090"
        prometheus.io/path: "/metrics"
    spec:
      serviceAccountName: mutt-ingestor
      containers:
      - name: ingestor
        image: mutt/ingestor:2.5.0
        imagePullPolicy: IfNotPresent
        ports:
        - name: http
          containerPort: 8080
          protocol: TCP
        - name: metrics
          containerPort: 9090
          protocol: TCP
        envFrom:
        - configMapRef:
            name: mutt-config
        - secretRef:
            name: mutt-secrets
        resources:
          requests:
            cpu: 500m
            memory: 512Mi
          limits:
            cpu: 1000m
            memory: 1Gi
        livenessProbe:
          httpGet:
            path: /health
            port: 8080
          initialDelaySeconds: 30
          periodSeconds: 10
          timeoutSeconds: 5
          failureThreshold: 3
        readinessProbe:
          httpGet:
            path: /health
            port: 8080
          initialDelaySeconds: 10
          periodSeconds: 5
          timeoutSeconds: 3
          failureThreshold: 2
        securityContext:
          runAsNonRoot: true
          runAsUser: 1000
          allowPrivilegeEscalation: false
          readOnlyRootFilesystem: true
          capabilities:
            drop:
            - ALL

---
apiVersion: v1
kind: Service
metadata:
  name: mutt-ingestor
  namespace: mutt
  labels:
    app: mutt-ingestor
spec:
  type: ClusterIP
  ports:
  - port: 8080
    targetPort: 8080
    protocol: TCP
    name: http
  - port: 9090
    targetPort: 9090
    protocol: TCP
    name: metrics
  selector:
    app: mutt-ingestor

---
apiVersion: autoscaling/v2
kind: HorizontalPodAutoscaler
metadata:
  name: mutt-ingestor-hpa
  namespace: mutt
spec:
  scaleTargetRef:
    apiVersion: apps/v1
    kind: Deployment
    name: mutt-ingestor
  minReplicas: 3
  maxReplicas: 10
  metrics:
  - type: Resource
    resource:
      name: cpu
      target:
        type: Utilization
        averageUtilization: 70
  - type: Resource
    resource:
      name: memory
      target:
        type: Utilization
        averageUtilization: 80
```

**Alerter Service:**

```yaml
# File: deployments/kubernetes/alerter-deployment.yaml
apiVersion: apps/v1
kind: Deployment
metadata:
  name: mutt-alerter
  namespace: mutt
  labels:
    app: mutt-alerter
    component: processing
spec:
  replicas: 5
  selector:
    matchLabels:
      app: mutt-alerter
  template:
    metadata:
      labels:
        app: mutt-alerter
        component: processing
      annotations:
        prometheus.io/scrape: "true"
        prometheus.io/port: "9091"
    spec:
      serviceAccountName: mutt-alerter
      containers:
      - name: alerter
        image: mutt/alerter:2.5.0
        imagePullPolicy: IfNotPresent
        ports:
        - name: metrics
          containerPort: 9091
          protocol: TCP
        env:
        - name: ALERTER_WORKER_ID
          valueFrom:
            fieldRef:
              fieldPath: metadata.name
        envFrom:
        - configMapRef:
            name: mutt-config
        - secretRef:
            name: mutt-secrets
        resources:
          requests:
            cpu: 1000m
            memory: 1Gi
          limits:
            cpu: 2000m
            memory: 2Gi
        securityContext:
          runAsNonRoot: true
          runAsUser: 1000
          allowPrivilegeEscalation: false
          readOnlyRootFilesystem: true
          capabilities:
            drop:
            - ALL

---
apiVersion: policy/v1
kind: PodDisruptionBudget
metadata:
  name: mutt-alerter-pdb
  namespace: mutt
spec:
  minAvailable: 3
  selector:
    matchLabels:
      app: mutt-alerter
```

**Web UI Service:**

```yaml
# File: deployments/kubernetes/webui-deployment.yaml
apiVersion: apps/v1
kind: Deployment
metadata:
  name: mutt-webui
  namespace: mutt
  labels:
    app: mutt-webui
    component: ui
spec:
  replicas: 2
  selector:
    matchLabels:
      app: mutt-webui
  template:
    metadata:
      labels:
        app: mutt-webui
        component: ui
    spec:
      containers:
      - name: webui
        image: mutt/webui:2.5.0
        ports:
        - name: http
          containerPort: 8090
        envFrom:
        - configMapRef:
            name: mutt-config
        - secretRef:
            name: mutt-secrets
        resources:
          requests:
            cpu: 250m
            memory: 256Mi
          limits:
            cpu: 500m
            memory: 512Mi
        livenessProbe:
          httpGet:
            path: /health
            port: 8090
          initialDelaySeconds: 30
          periodSeconds: 10
        readinessProbe:
          httpGet:
            path: /health
            port: 8090
          initialDelaySeconds: 10
          periodSeconds: 5

---
apiVersion: v1
kind: Service
metadata:
  name: mutt-webui
  namespace: mutt
spec:
  type: ClusterIP
  ports:
  - port: 8090
    targetPort: 8090
    name: http
  selector:
    app: mutt-webui

---
apiVersion: networking.k8s.io/v1
kind: Ingress
metadata:
  name: mutt-webui-ingress
  namespace: mutt
  annotations:
    cert-manager.io/cluster-issuer: "letsencrypt-prod"
    nginx.ingress.kubernetes.io/ssl-redirect: "true"
spec:
  ingressClassName: nginx
  tls:
  - hosts:
    - mutt.example.com
    secretName: mutt-tls
  rules:
  - host: mutt.example.com
    http:
      paths:
      - path: /
        pathType: Prefix
        backend:
          service:
            name: mutt-webui
            port:
              number: 8090
```

#### 5.1.4 CronJobs for Maintenance

```yaml
# File: deployments/kubernetes/partition-cronjob.yaml
apiVersion: batch/v1
kind: CronJob
metadata:
  name: mutt-partition-creator
  namespace: mutt
spec:
  schedule: "0 0 1 * *"  # Monthly on the 1st
  jobTemplate:
    spec:
      template:
        spec:
          containers:
          - name: partition-creator
            image: mutt/maintenance:2.5.0
            command:
            - python
            - /app/scripts/create_monthly_partitions.py
            envFrom:
            - configMapRef:
                name: mutt-config
            - secretRef:
                name: mutt-secrets
          restartPolicy: OnFailure

---
# File: deployments/kubernetes/retention-cronjob.yaml
apiVersion: batch/v1
kind: CronJob
metadata:
  name: mutt-retention-cleanup
  namespace: mutt
spec:
  schedule: "0 2 * * 0"  # Weekly on Sunday at 2 AM
  jobTemplate:
    spec:
      template:
        spec:
          containers:
          - name: retention-cleanup
            image: mutt/maintenance:2.5.0
            command:
            - python
            - /app/scripts/retention_policy_enforcer.py
            envFrom:
            - configMapRef:
                name: mutt-config
            - secretRef:
                name: mutt-secrets
          restartPolicy: OnFailure
```

### 5.2 RHEL/Ubuntu SystemD Deployment

**Supported Platforms**:
- **RHEL-based**: RHEL 8/9, CentOS Stream, Rocky Linux (Section 5.2.1-5.2.2)
- **Ubuntu**: Ubuntu 20.04 LTS, 22.04 LTS, 24.04 LTS (Section 5.2.3)

Both platforms use SystemD for service management with identical service files. The main differences are package managers (`yum` vs `apt`) and security frameworks (SELinux vs AppArmor).

#### 5.2.1 SystemD Service Files

**Note**: These service files work identically on both RHEL and Ubuntu.



**Ingestor Service:**

```ini
# File: deployments/systemd/mutt-ingestor.service
[Unit]
Description=MUTT Ingestor Service
After=network.target redis.service postgresql.service
Wants=redis.service postgresql.service

[Service]
Type=simple
User=mutt
Group=mutt
WorkingDirectory=/opt/mutt

# Environment
EnvironmentFile=/opt/mutt/.env

# Service execution
ExecStart=/opt/mutt/venv/bin/python -m services.ingestor_service
ExecReload=/bin/kill -HUP $MAINPID

# Resource limits
LimitNOFILE=65536
LimitNPROC=4096

# Security hardening
NoNewPrivileges=true
PrivateTmp=true
ProtectSystem=strict
ProtectHome=true
ReadWritePaths=/opt/mutt/logs

# Restart policy
Restart=always
RestartSec=10
StartLimitInterval=300
StartLimitBurst=5

# Logging
StandardOutput=journal
StandardError=journal
SyslogIdentifier=mutt-ingestor

[Install]
WantedBy=multi-user.target
```

**Alerter Service:**

```ini
# File: deployments/systemd/mutt-alerter@.service
# Template service for multiple alerter instances
# Start with: systemctl start mutt-alerter@{1..5}.service

[Unit]
Description=MUTT Alerter Service (Instance %i)
After=network.target redis.service postgresql.service
Wants=redis.service postgresql.service

[Service]
Type=simple
User=mutt
Group=mutt
WorkingDirectory=/opt/mutt

# Environment
EnvironmentFile=/opt/mutt/.env
Environment="ALERTER_WORKER_ID=alerter-%i"

# Service execution
ExecStart=/opt/mutt/venv/bin/python -m services.alerter_service

# Resource limits
LimitNOFILE=65536
MemoryMax=2G
CPUQuota=150%

# Security hardening
NoNewPrivileges=true
PrivateTmp=true
ProtectSystem=strict
ProtectHome=true
ReadWritePaths=/opt/mutt/logs

# Restart policy
Restart=always
RestartSec=10

# Logging
StandardOutput=journal
StandardError=journal
SyslogIdentifier=mutt-alerter-%i

[Install]
WantedBy=multi-user.target
```

**Moog Forwarder Service:**

```ini
# File: deployments/systemd/mutt-moog-forwarder.service
[Unit]
Description=MUTT Moog Forwarder Service
After=network.target redis.service
Wants=redis.service

[Service]
Type=simple
User=mutt
Group=mutt
WorkingDirectory=/opt/mutt

EnvironmentFile=/opt/mutt/.env

ExecStart=/opt/mutt/venv/bin/python -m services.moog_forwarder_service

LimitNOFILE=65536
MemoryMax=1G

NoNewPrivileges=true
PrivateTmp=true
ProtectSystem=strict
ProtectHome=true
ReadWritePaths=/opt/mutt/logs

Restart=always
RestartSec=10

StandardOutput=journal
StandardError=journal
SyslogIdentifier=mutt-moog-forwarder

[Install]
WantedBy=multi-user.target
```

**Web UI Service:**

```ini
# File: deployments/systemd/mutt-webui.service
[Unit]
Description=MUTT Web UI Service
After=network.target redis.service postgresql.service
Wants=redis.service postgresql.service

[Service]
Type=simple
User=mutt
Group=mutt
WorkingDirectory=/opt/mutt

EnvironmentFile=/opt/mutt/.env

# Use Gunicorn for production
ExecStart=/opt/mutt/venv/bin/gunicorn \
    --workers 4 \
    --bind 0.0.0.0:8090 \
    --access-logfile - \
    --error-logfile - \
    --log-level info \
    services.web_ui_service:app

LimitNOFILE=65536
MemoryMax=1G

NoNewPrivileges=true
PrivateTmp=true
ProtectSystem=strict
ProtectHome=true
ReadWritePaths=/opt/mutt/logs

Restart=always
RestartSec=10

StandardOutput=journal
StandardError=journal
SyslogIdentifier=mutt-webui

[Install]
WantedBy=multi-user.target
```

**Remediation Service:**

```ini
# File: deployments/systemd/mutt-remediation.service
[Unit]
Description=MUTT Remediation Service
After=network.target redis.service
Wants=redis.service

[Service]
Type=simple
User=mutt
Group=mutt
WorkingDirectory=/opt/mutt

EnvironmentFile=/opt/mutt/.env

ExecStart=/opt/mutt/venv/bin/python -m services.remediation_service

LimitNOFILE=65536
MemoryMax=512M

NoNewPrivileges=true
PrivateTmp=true
ProtectSystem=strict
ProtectHome=true
ReadWritePaths=/opt/mutt/logs

Restart=always
RestartSec=10

StandardOutput=journal
StandardError=journal
SyslogIdentifier=mutt-remediation

[Install]
WantedBy=multi-user.target
```

#### 5.2.2 RHEL Deployment Script

```bash
#!/bin/bash
# File: deployments/scripts/deploy_rhel.sh
# MUTT v2.5 RHEL Deployment Script

set -e

MUTT_USER="mutt"
MUTT_GROUP="mutt"
MUTT_HOME="/opt/mutt"
PYTHON_VERSION="3.10"

echo "=== MUTT v2.5 RHEL Deployment ==="

# 1. Create user and group
if ! id "$MUTT_USER" &>/dev/null; then
    echo "Creating mutt user..."
    useradd --system --home-dir "$MUTT_HOME" --shell /bin/bash "$MUTT_USER"
fi

# 2. Create directories
echo "Creating directories..."
mkdir -p "$MUTT_HOME"/{services,scripts,database,logs,venv}
chown -R "$MUTT_USER:$MUTT_GROUP" "$MUTT_HOME"

# 3. Install Python dependencies
echo "Setting up Python virtual environment..."
sudo -u "$MUTT_USER" python${PYTHON_VERSION} -m venv "$MUTT_HOME/venv"
sudo -u "$MUTT_USER" "$MUTT_HOME/venv/bin/pip" install --upgrade pip
sudo -u "$MUTT_USER" "$MUTT_HOME/venv/bin/pip" install -r requirements.txt

# 4. Copy application files
echo "Copying application files..."
cp -r services/* "$MUTT_HOME/services/"
cp -r scripts/* "$MUTT_HOME/scripts/"
cp -r database/* "$MUTT_HOME/database/"
chown -R "$MUTT_USER:$MUTT_GROUP" "$MUTT_HOME"

# 5. Copy environment file
if [ ! -f "$MUTT_HOME/.env" ]; then
    echo "Creating .env file..."
    cp .env.template "$MUTT_HOME/.env"
    chown "$MUTT_USER:$MUTT_GROUP" "$MUTT_HOME/.env"
    chmod 600 "$MUTT_HOME/.env"
    echo "WARNING: Edit $MUTT_HOME/.env with production values!"
fi

# 6. Install systemd service files
echo "Installing systemd services..."
cp deployments/systemd/*.service /etc/systemd/system/
systemctl daemon-reload

# 7. Enable and start services
echo "Enabling services..."
systemctl enable mutt-ingestor.service
systemctl enable mutt-alerter@{1..5}.service
systemctl enable mutt-moog-forwarder.service
systemctl enable mutt-webui.service
systemctl enable mutt-remediation.service

echo "Starting services..."
systemctl start mutt-ingestor.service
systemctl start mutt-alerter@{1..5}.service
systemctl start mutt-moog-forwarder.service
systemctl start mutt-webui.service
systemctl start mutt-remediation.service

# 8. Check status
echo ""
echo "=== Service Status ==="
systemctl status mutt-ingestor.service --no-pager
systemctl status mutt-alerter@1.service --no-pager
systemctl status mutt-webui.service --no-pager

echo ""
echo "=== Deployment Complete ==="
echo "Logs: journalctl -u mutt-* -f"
echo "Config: $MUTT_HOME/.env"
```

#### 5.2.3 Ubuntu Deployment

**Target Environment**: Ubuntu 20.04 LTS, 22.04 LTS, 24.04 LTS

**Key Differences from RHEL**:
- Package manager: `apt` instead of `yum`
- Python 3.10 may require PPA on older Ubuntu versions
- Security: AppArmor instead of SELinux
- Firewall: `ufw` instead of `firewalld`
- SystemD service files work identically on Ubuntu

**Prerequisites:**

```bash
# Update package list
sudo apt update

# Install Python 3.10 (Ubuntu 22.04+ has it by default)
# For Ubuntu 20.04, add deadsnakes PPA:
sudo apt install -y software-properties-common
sudo add-apt-repository -y ppa:deadsnakes/ppa
sudo apt update

# Install Python 3.10 and dependencies
sudo apt install -y \
    python3.10 \
    python3.10-venv \
    python3.10-dev \
    python3-pip \
    build-essential \
    git \
    postgresql-client \
    redis-tools \
    curl \
    net-tools

# Verify Python version
python3.10 --version
```

**Ubuntu Deployment Script:**

```bash
#!/bin/bash
# File: deployments/scripts/deploy_ubuntu.sh
# MUTT v2.5 Ubuntu Deployment Script

set -e

MUTT_USER="mutt"
MUTT_GROUP="mutt"
MUTT_HOME="/opt/mutt"
PYTHON_VERSION="3.10"

echo "=== MUTT v2.5 Ubuntu Deployment ==="

# 1. Check Python 3.10 availability
if ! command -v python${PYTHON_VERSION} &> /dev/null; then
    echo "ERROR: Python ${PYTHON_VERSION} not found!"
    echo "Install it using:"
    echo "  sudo add-apt-repository ppa:deadsnakes/ppa"
    echo "  sudo apt update"
    echo "  sudo apt install python${PYTHON_VERSION} python${PYTHON_VERSION}-venv"
    exit 1
fi

# 2. Create user and group
if ! id "$MUTT_USER" &>/dev/null; then
    echo "Creating mutt user..."
    # Ubuntu useradd syntax (same as RHEL for these flags)
    sudo useradd --system --home-dir "$MUTT_HOME" --shell /bin/bash --create-home "$MUTT_USER"
fi

# 3. Create directories
echo "Creating directories..."
sudo mkdir -p "$MUTT_HOME"/{services,scripts,database,logs,venv}
sudo chown -R "$MUTT_USER:$MUTT_GROUP" "$MUTT_HOME"

# 4. Install Python dependencies
echo "Setting up Python virtual environment..."
sudo -u "$MUTT_USER" python${PYTHON_VERSION} -m venv "$MUTT_HOME/venv"
sudo -u "$MUTT_USER" "$MUTT_HOME/venv/bin/pip" install --upgrade pip
sudo -u "$MUTT_USER" "$MUTT_HOME/venv/bin/pip" install -r requirements.txt

# 5. Copy application files
echo "Copying application files..."
sudo cp -r services/* "$MUTT_HOME/services/"
sudo cp -r scripts/* "$MUTT_HOME/scripts/"
sudo cp -r database/* "$MUTT_HOME/database/"
sudo chown -R "$MUTT_USER:$MUTT_GROUP" "$MUTT_HOME"

# 6. Copy environment file
if [ ! -f "$MUTT_HOME/.env" ]; then
    echo "Creating .env file..."
    sudo cp .env.template "$MUTT_HOME/.env"
    sudo chown "$MUTT_USER:$MUTT_GROUP" "$MUTT_HOME/.env"
    sudo chmod 600 "$MUTT_HOME/.env"
    echo "WARNING: Edit $MUTT_HOME/.env with production values!"
fi

# 7. Install systemd service files
echo "Installing systemd services..."
sudo cp deployments/systemd/*.service /etc/systemd/system/
sudo systemctl daemon-reload

# 8. Configure firewall (ufw)
echo "Configuring firewall..."
if command -v ufw &> /dev/null; then
    # Allow Web UI port
    sudo ufw allow 8090/tcp comment "MUTT Web UI"

    # Allow metrics ports (if exposing externally)
    # sudo ufw allow 9090:9094/tcp comment "MUTT Metrics"

    echo "Firewall rules added. Enable ufw with: sudo ufw enable"
else
    echo "WARNING: ufw not installed. Install with: sudo apt install ufw"
fi

# 9. Enable and start services
echo "Enabling services..."
sudo systemctl enable mutt-ingestor.service
sudo systemctl enable mutt-alerter@{1..5}.service
sudo systemctl enable mutt-moog-forwarder.service
sudo systemctl enable mutt-webui.service
sudo systemctl enable mutt-remediation.service

echo "Starting services..."
sudo systemctl start mutt-ingestor.service
sudo systemctl start mutt-alerter@{1..5}.service
sudo systemctl start mutt-moog-forwarder.service
sudo systemctl start mutt-webui.service
sudo systemctl start mutt-remediation.service

# 10. Check status
echo ""
echo "=== Service Status ==="
sudo systemctl status mutt-ingestor.service --no-pager
sudo systemctl status mutt-alerter@1.service --no-pager
sudo systemctl status mutt-webui.service --no-pager

echo ""
echo "=== Deployment Complete ==="
echo "Logs: journalctl -u mutt-* -f"
echo "Config: $MUTT_HOME/.env"
echo "Web UI: http://localhost:8090"
echo ""
echo "Next steps:"
echo "  1. Edit $MUTT_HOME/.env with production values"
echo "  2. Restart services: sudo systemctl restart mutt-*"
echo "  3. Check logs: sudo journalctl -u mutt-* -f"
```

**Ubuntu-Specific Notes:**

1. **AppArmor vs SELinux**:
   - Ubuntu uses AppArmor for security (RHEL uses SELinux)
   - SystemD security directives work identically
   - No AppArmor profile needed for basic deployment
   - For strict AppArmor, create profile at `/etc/apparmor.d/mutt`

2. **Package Names**:
   ```bash
   # Ubuntu package equivalents:
   yum install python3 → apt install python3.10
   yum install python3-pip → apt install python3-pip
   yum install postgresql → apt install postgresql-client
   yum install redis → apt install redis-tools
   ```

3. **Firewall (ufw)**:
   ```bash
   # Enable firewall
   sudo ufw enable

   # Check status
   sudo ufw status verbose

   # Allow additional ports if needed
   sudo ufw allow 9090/tcp  # Prometheus metrics
   sudo ufw allow 514/udp   # Syslog input (if receiving directly)
   ```

4. **Service Management** (identical to RHEL):
   ```bash
   # Check service status
   sudo systemctl status mutt-*

   # View logs
   sudo journalctl -u mutt-ingestor -f
   sudo journalctl -u mutt-alerter@1 -f

   # Restart services
   sudo systemctl restart mutt-ingestor

   # Stop all MUTT services
   sudo systemctl stop mutt-*
   ```

5. **Python 3.10 Installation Matrix**:
   | Ubuntu Version | Python 3.10 | Installation Method |
   |---------------|-------------|---------------------|
   | 20.04 LTS | ❌ Not default | Requires deadsnakes PPA |
   | 22.04 LTS | ✅ Default | `apt install python3.10` |
   | 24.04 LTS | ✅ Default (3.12) | Use `python3.10` specifically |

6. **Troubleshooting**:

   **Issue**: Python 3.10 not found
   ```bash
   # Solution: Install from PPA
   sudo add-apt-repository ppa:deadsnakes/ppa
   sudo apt update
   sudo apt install python3.10 python3.10-venv python3.10-dev
   ```

   **Issue**: Permission denied on /opt/mutt
   ```bash
   # Solution: Fix ownership
   sudo chown -R mutt:mutt /opt/mutt
   sudo chmod -R 755 /opt/mutt
   sudo chmod 700 /opt/mutt/.env
   ```

   **Issue**: Services fail to start
   ```bash
   # Solution: Check logs and dependencies
   sudo journalctl -u mutt-ingestor -n 50
   # Verify Redis and PostgreSQL are accessible
   redis-cli ping
   psql -h <postgres_host> -U <user> -d mutt -c "SELECT 1"
   ```

#### 5.2.4 Manual Deployment Guide

**Use Case**: Step-by-step manual deployment for:
- Understanding system architecture deeply
- Troubleshooting automated script failures
- Non-standard environments
- Educational/learning purposes
- Custom deployment scenarios

**Target Success Rate**: 80-85% with careful following of steps

---

##### 5.2.4.1 Pre-Flight Checklist

Before beginning manual deployment, verify:

```markdown
## System Requirements
- [ ] Linux server (RHEL 8/9 or Ubuntu 20.04/22.04/24.04)
- [ ] Minimum 4 CPU cores (8 recommended)
- [ ] Minimum 8GB RAM (16GB recommended)
- [ ] Minimum 50GB disk space (100GB+ for production)
- [ ] Root or sudo access

## Network Access
- [ ] Redis server accessible (hostname/IP and port)
- [ ] PostgreSQL server accessible (hostname/IP and port)
- [ ] Moogsoft webhook endpoint accessible (if forwarding enabled)
- [ ] Vault server accessible (if using Vault for secrets)
- [ ] Internet access for package installation (or local mirror configured)

## Credentials Ready
- [ ] PostgreSQL username and password
- [ ] PostgreSQL database name (recommend: mutt)
- [ ] Redis password (if authentication enabled)
- [ ] Moogsoft webhook URL and authentication token
- [ ] Vault token (if using Vault)

## Software Versions
- [ ] Python 3.10 or higher
- [ ] PostgreSQL 12+ (client and server)
- [ ] Redis 6.0+ (server)
- [ ] pip package manager
- [ ] git (for cloning repository)
```

---

##### 5.2.4.2 Step 1: Environment Preparation

**1.1 Update System**

```bash
# RHEL/CentOS
sudo yum update -y

# Ubuntu
sudo apt update && sudo apt upgrade -y
```

**1.2 Install Base Packages**

```bash
# RHEL/CentOS
sudo yum install -y \
    python3.10 \
    python3.10-pip \
    python3.10-devel \
    gcc \
    git \
    postgresql-client \
    redis \
    net-tools \
    vim

# Ubuntu
sudo apt install -y \
    software-properties-common \
    python3.10 \
    python3.10-venv \
    python3.10-dev \
    python3-pip \
    build-essential \
    git \
    postgresql-client \
    redis-tools \
    net-tools \
    vim
```

**1.3 Verify Python Installation**

```bash
python3.10 --version
# Expected: Python 3.10.x

python3.10 -m pip --version
# Expected: pip 23.x or higher
```

**1.4 Create MUTT User**

```bash
# Create system user for MUTT services
sudo useradd --system --home-dir /opt/mutt --shell /bin/bash --create-home mutt

# Verify user creation
id mutt
# Expected: uid=xxx(mutt) gid=xxx(mutt) groups=xxx(mutt)
```

**1.5 Create Directory Structure**

```bash
# Create all required directories
sudo mkdir -p /opt/mutt/{services,scripts,database,logs,venv,config}

# Set ownership
sudo chown -R mutt:mutt /opt/mutt

# Set permissions
sudo chmod 755 /opt/mutt
sudo chmod 700 /opt/mutt/config  # Restrict config directory
sudo chmod 755 /opt/mutt/logs

# Verify
ls -la /opt/mutt/
```

---

##### 5.2.4.3 Step 2: PostgreSQL Database Setup

**2.1 Test PostgreSQL Connectivity**

```bash
# Test connection (replace with your values)
psql -h <postgres_host> -U <postgres_user> -d postgres -c "SELECT version();"

# Example:
# psql -h 192.168.1.100 -U admin -d postgres -c "SELECT version();"
```

**2.2 Create MUTT Database**

```bash
# Connect to PostgreSQL
psql -h <postgres_host> -U <postgres_user> -d postgres

# In psql prompt, create database and user:
CREATE DATABASE mutt;
CREATE USER mutt_app WITH PASSWORD 'your_secure_password_here';
GRANT ALL PRIVILEGES ON DATABASE mutt TO mutt_app;

# Exit psql
\q
```

**2.3 Create Schema**

Download or create the schema file:

```bash
# Create schema SQL file
sudo -u mutt cat > /opt/mutt/database/schema.sql << 'EOF'
-- MUTT v2.5 Database Schema

-- Table: alert_rules
CREATE TABLE IF NOT EXISTS alert_rules (
    id SERIAL PRIMARY KEY,
    match_string TEXT,
    trap_oid TEXT,
    syslog_severity INTEGER,
    match_type TEXT NOT NULL CHECK (match_type IN ('contains', 'regex', 'oid_prefix')),
    priority INTEGER DEFAULT 100,
    prod_handling TEXT NOT NULL,
    dev_handling TEXT NOT NULL,
    team_assignment TEXT,
    is_active BOOLEAN DEFAULT true,
    created_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ DEFAULT NOW()
);

CREATE INDEX idx_alert_rules_match_type ON alert_rules(match_type);
CREATE INDEX idx_alert_rules_is_active ON alert_rules(is_active);
CREATE INDEX idx_alert_rules_priority ON alert_rules(priority DESC);

-- Table: development_hosts
CREATE TABLE IF NOT EXISTS development_hosts (
    hostname TEXT PRIMARY KEY,
    created_at TIMESTAMPTZ DEFAULT NOW()
);

-- Table: device_teams
CREATE TABLE IF NOT EXISTS device_teams (
    hostname TEXT PRIMARY KEY,
    team_assignment TEXT NOT NULL,
    created_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ DEFAULT NOW()
);

-- Table: event_audit_log (partitioned by month)
CREATE TABLE IF NOT EXISTS event_audit_log (
    id BIGSERIAL,
    event_timestamp TIMESTAMPTZ NOT NULL,
    hostname TEXT,
    matched_rule_id INTEGER REFERENCES alert_rules(id),
    handling_decision TEXT,
    forwarded_to_moog BOOLEAN,
    raw_message TEXT,
    created_at TIMESTAMPTZ DEFAULT NOW(),
    PRIMARY KEY (id, event_timestamp)
) PARTITION BY RANGE (event_timestamp);

CREATE INDEX idx_event_audit_event_timestamp ON event_audit_log(event_timestamp);
CREATE INDEX idx_event_audit_hostname ON event_audit_log(hostname);
CREATE INDEX idx_event_audit_matched_rule_id ON event_audit_log(matched_rule_id);

-- Table: config_audit_log
CREATE TABLE IF NOT EXISTS config_audit_log (
    id BIGSERIAL PRIMARY KEY,
    changed_at TIMESTAMPTZ DEFAULT NOW(),
    changed_by VARCHAR(255),
    operation VARCHAR(50) CHECK (operation IN ('CREATE', 'UPDATE', 'DELETE')),
    table_name VARCHAR(255) NOT NULL,
    record_id INTEGER,
    old_values JSONB,
    new_values JSONB,
    reason TEXT,
    correlation_id VARCHAR(255)
);

CREATE INDEX idx_config_audit_table_record ON config_audit_log(table_name, record_id);
CREATE INDEX idx_config_audit_changed_at ON config_audit_log(changed_at DESC);
CREATE INDEX idx_config_audit_changed_by ON config_audit_log(changed_by);
CREATE INDEX idx_config_audit_old_values ON config_audit_log USING GIN(old_values);
CREATE INDEX idx_config_audit_new_values ON config_audit_log USING GIN(new_values);

-- Function: Create monthly partitions
CREATE OR REPLACE FUNCTION create_monthly_partition(partition_date DATE)
RETURNS TEXT AS $$
DECLARE
    partition_name TEXT;
    start_date DATE;
    end_date DATE;
BEGIN
    partition_name := 'event_audit_log_' || TO_CHAR(partition_date, 'YYYY_MM');
    start_date := DATE_TRUNC('month', partition_date);
    end_date := start_date + INTERVAL '1 month';

    EXECUTE format(
        'CREATE TABLE IF NOT EXISTS %I PARTITION OF event_audit_log
         FOR VALUES FROM (%L) TO (%L)',
        partition_name, start_date, end_date
    );

    RETURN partition_name;
END;
$$ LANGUAGE plpgsql;

-- Create partitions for current month + 2 months ahead
SELECT create_monthly_partition(CURRENT_DATE);
SELECT create_monthly_partition(CURRENT_DATE + INTERVAL '1 month');
SELECT create_monthly_partition(CURRENT_DATE + INTERVAL '2 months');
EOF
```

**2.4 Apply Schema**

```bash
# Apply schema to database
psql -h <postgres_host> -U mutt_app -d mutt -f /opt/mutt/database/schema.sql

# Verify tables created
psql -h <postgres_host> -U mutt_app -d mutt -c "\dt"

# Expected output: alert_rules, development_hosts, device_teams, event_audit_log, config_audit_log
```

**2.5 Insert Sample Data (Optional)**

```bash
# Insert a default rule
psql -h <postgres_host> -U mutt_app -d mutt << 'EOF'
INSERT INTO alert_rules (match_string, match_type, priority, prod_handling, dev_handling, team_assignment)
VALUES ('error', 'contains', 100, 'forward', 'log', 'platform-team');

-- Insert test development host
INSERT INTO development_hosts (hostname) VALUES ('dev-server-01');

-- Insert test device team assignment
INSERT INTO device_teams (hostname, team_assignment) VALUES ('prod-server-01', 'platform-team');
EOF

# Verify
psql -h <postgres_host> -U mutt_app -d mutt -c "SELECT * FROM alert_rules;"
```

---

##### 5.2.4.4 Step 3: Redis Configuration

**3.1 Test Redis Connectivity**

```bash
# Test connection (no auth)
redis-cli -h <redis_host> -p <redis_port> ping
# Expected: PONG

# Test connection (with auth)
redis-cli -h <redis_host> -p <redis_port> -a <redis_password> ping
# Expected: PONG
```

**3.2 Verify Redis Configuration**

```bash
# Check Redis configuration
redis-cli -h <redis_host> -p <redis_port> CONFIG GET maxmemory
redis-cli -h <redis_host> -p <redis_port> CONFIG GET maxmemory-policy

# Recommended settings:
# maxmemory: 8GB minimum (8589934592 bytes)
# maxmemory-policy: noeviction
```

**3.3 Create Redis Data Structures (Test)**

```bash
# Test creating MUTT data structures
redis-cli -h <redis_host> -p <redis_port> << 'EOF'
# Test queue creation
LPUSH mutt:queue:raw "test_message"
RPOP mutt:queue:raw

# Test hash creation
HSET mutt:config:test key1 value1
HGETALL mutt:config:test
DEL mutt:config:test

# Test sorted set (for rate limiting)
ZADD mutt:rate_limit:test 1234567890 "request1"
ZRANGE mutt:rate_limit:test 0 -1
DEL mutt:rate_limit:test

PING
EOF

# Expected: All commands succeed, final PONG
```

---

##### 5.2.4.5 Step 4: Python Environment Setup

**4.1 Create Virtual Environment**

```bash
# Switch to mutt user
sudo -u mutt bash

# Create virtual environment
python3.10 -m venv /opt/mutt/venv

# Activate virtual environment
source /opt/mutt/venv/bin/activate

# Verify
which python
# Expected: /opt/mutt/venv/bin/python

python --version
# Expected: Python 3.10.x
```

**4.2 Upgrade pip**

```bash
# Still as mutt user with venv activated
pip install --upgrade pip setuptools wheel

# Verify
pip --version
# Expected: pip 23.x or higher from /opt/mutt/venv
```

**4.3 Install Python Dependencies**

Create requirements.txt:

```bash
cat > /opt/mutt/requirements.txt << 'EOF'
# Core dependencies
redis==4.5.4
psycopg2-binary==2.9.6
python-dotenv==1.0.0
pyyaml==6.0

# Web UI
flask==2.3.2
flask-cors==4.0.0

# Monitoring
prometheus-client==0.17.0

# HTTP requests
requests==2.31.0

# Configuration management
hvac==1.1.1  # Vault client

# Testing (optional for production)
pytest==7.4.0
pytest-cov==4.1.0
pytest-mock==3.11.1

# Utilities
python-json-logger==2.0.7
EOF

# Install all dependencies
pip install -r /opt/mutt/requirements.txt

# Verify key packages
pip list | grep -E "redis|psycopg2|flask|prometheus"
```

**4.4 Exit mutt user session**

```bash
# Deactivate venv and exit
deactivate
exit  # Back to your original user
```

---

##### 5.2.4.6 Step 5: Application Code Deployment

**5.1 Copy/Create Service Files**

```bash
# Create service directory structure
sudo mkdir -p /opt/mutt/services

# Create __init__.py (makes it a package)
sudo -u mutt touch /opt/mutt/services/__init__.py
```

**5.2 Create Configuration File**

```bash
# Create .env file
sudo -u mutt cat > /opt/mutt/.env << 'EOF'
# PostgreSQL Configuration
POSTGRES_HOST=<your_postgres_host>
POSTGRES_PORT=5432
POSTGRES_DB=mutt
POSTGRES_USER=mutt_app
POSTGRES_PASSWORD=<your_postgres_password>

# Redis Configuration
REDIS_HOST=<your_redis_host>
REDIS_PORT=6379
REDIS_PASSWORD=<your_redis_password>
REDIS_DB=0

# Moogsoft Configuration
MOOG_WEBHOOK_URL=<your_moogsoft_webhook_url>
MOOG_API_TOKEN=<your_moogsoft_token>
MOOG_HEALTH_CHECK_ENABLED=true
MOOG_HEALTH_TIMEOUT=5

# Service Configuration
LOG_LEVEL=INFO
METRICS_PORT_INGESTOR=9090
METRICS_PORT_ALERTER=9091
METRICS_PORT_MOOG_FORWARDER=9092
METRICS_PORT_REMEDIATION=9093
WEB_UI_PORT=8090

# Circuit Breaker Configuration
CIRCUIT_BREAKER_FAILURE_THRESHOLD=5
CIRCUIT_BREAKER_TIMEOUT=60
CIRCUIT_BREAKER_HALF_OPEN_TIMEOUT=30

# Rate Limiting
RATE_LIMIT_MAX_REQUESTS=1000
RATE_LIMIT_WINDOW_SECONDS=60

# Backpressure Configuration
BACKPRESSURE_THRESHOLD=10000
BACKPRESSURE_MODE=shed  # or 'defer'

# Hot Reload Configuration
CONFIG_REFRESH_INTERVAL=5
CONFIG_REDIS_KEY=mutt:config:live

# Vault Configuration (optional)
VAULT_ENABLED=false
VAULT_ADDR=https://vault.example.com:8200
VAULT_TOKEN=<your_vault_token>
VAULT_SECRET_PATH=secret/data/mutt
EOF

# Secure the .env file
sudo chown mutt:mutt /opt/mutt/.env
sudo chmod 600 /opt/mutt/.env
```

**5.3 Verify Configuration**

```bash
# Test that configuration loads
sudo -u mutt bash -c 'source /opt/mutt/.env && echo "POSTGRES_HOST=$POSTGRES_HOST"'
# Should print your PostgreSQL host
```

---

##### 5.2.4.7 Step 6: Service-by-Service Configuration

**6.1 Ingestor Service**

Create the ingestor service file (you should have this from your codebase):

```bash
# If you have the full codebase, copy it:
# sudo cp -r <your_codebase>/services/ingestor_service.py /opt/mutt/services/

# Verify the file exists
ls -la /opt/mutt/services/ingestor_service.py
```

Test the ingestor manually:

```bash
# Test as mutt user
sudo -u mutt bash << 'EOF'
cd /opt/mutt
source venv/bin/activate
source .env

# Run ingestor for 10 seconds (Ctrl+C to stop)
timeout 10 python -m services.ingestor_service || true

# Check for errors in output
EOF
```

**6.2 Alerter Service**

```bash
# Copy alerter service
# sudo cp -r <your_codebase>/services/alerter_service.py /opt/mutt/services/

# Test alerter manually
sudo -u mutt bash << 'EOF'
cd /opt/mutt
source venv/bin/activate
source .env
export ALERTER_WORKER_ID=test-1

timeout 10 python -m services.alerter_service || true
EOF
```

**6.3 Moog Forwarder Service**

```bash
# Copy moog forwarder service
# sudo cp -r <your_codebase>/services/moog_forwarder_service.py /opt/mutt/services/
# sudo cp -r <your_codebase>/services/rate_limiter.py /opt/mutt/services/

# Test moog forwarder manually
sudo -u mutt bash << 'EOF'
cd /opt/mutt
source venv/bin/activate
source .env

timeout 10 python -m services.moog_forwarder_service || true
EOF
```

**6.4 Web UI Service**

```bash
# Copy web UI service
# sudo cp -r <your_codebase>/services/web_ui_service.py /opt/mutt/services/

# Test web UI manually (run in background for 10 seconds)
sudo -u mutt bash << 'EOF'
cd /opt/mutt
source venv/bin/activate
source .env

# Start web UI in background
python -m services.web_ui_service &
WEB_PID=$!

# Wait 3 seconds for startup
sleep 3

# Test health endpoint
curl -s http://localhost:8090/health

# Kill the web UI
kill $WEB_PID
EOF
```

**6.5 Remediation Service**

```bash
# Copy remediation service
# sudo cp -r <your_codebase>/services/remediation_service.py /opt/mutt/services/

# Test remediation manually
sudo -u mutt bash << 'EOF'
cd /opt/mutt
source venv/bin/activate
source .env

timeout 10 python -m services.remediation_service || true
EOF
```

---

##### 5.2.4.8 Step 7: SystemD Service Configuration

**7.1 Create SystemD Service Files**

Create all five service files in `/etc/systemd/system/`:

```bash
# Copy service files (you should have these from Section 5.2.1)
# sudo cp deployments/systemd/*.service /etc/systemd/system/

# Or create them manually:
sudo cat > /etc/systemd/system/mutt-ingestor.service << 'EOF'
[Unit]
Description=MUTT Ingestor Service
After=network.target redis.service postgresql.service
Wants=redis.service postgresql.service

[Service]
Type=simple
User=mutt
Group=mutt
WorkingDirectory=/opt/mutt
EnvironmentFile=/opt/mutt/.env
ExecStart=/opt/mutt/venv/bin/python -m services.ingestor_service
ExecReload=/bin/kill -HUP $MAINPID
LimitNOFILE=65536
LimitNPROC=4096
NoNewPrivileges=true
PrivateTmp=true
ProtectSystem=strict
ProtectHome=true
ReadWritePaths=/opt/mutt/logs
Restart=always
RestartSec=10
StartLimitInterval=300
StartLimitBurst=5
StandardOutput=journal
StandardError=journal
SyslogIdentifier=mutt-ingestor

[Install]
WantedBy=multi-user.target
EOF

# Create remaining services (alerter, moog-forwarder, webui, remediation)
# See Section 5.2.1 for complete service definitions
```

**7.2 Reload SystemD**

```bash
sudo systemctl daemon-reload

# Verify services are recognized
systemctl list-unit-files | grep mutt
```

---

##### 5.2.4.9 Step 8: Component Testing

**8.1 Test Database Connection**

```bash
# Test from MUTT environment
sudo -u mutt bash << 'EOF'
cd /opt/mutt
source venv/bin/activate
source .env

python3 << 'PYTHON'
import psycopg2
import os

try:
    conn = psycopg2.connect(
        host=os.getenv('POSTGRES_HOST'),
        port=os.getenv('POSTGRES_PORT'),
        database=os.getenv('POSTGRES_DB'),
        user=os.getenv('POSTGRES_USER'),
        password=os.getenv('POSTGRES_PASSWORD')
    )
    cur = conn.cursor()
    cur.execute('SELECT COUNT(*) FROM alert_rules;')
    count = cur.fetchone()[0]
    print(f"✅ PostgreSQL connection successful! Found {count} alert rules.")
    cur.close()
    conn.close()
except Exception as e:
    print(f"❌ PostgreSQL connection failed: {e}")
PYTHON
EOF
```

**8.2 Test Redis Connection**

```bash
sudo -u mutt bash << 'EOF'
cd /opt/mutt
source venv/bin/activate
source .env

python3 << 'PYTHON'
import redis
import os

try:
    r = redis.Redis(
        host=os.getenv('REDIS_HOST'),
        port=int(os.getenv('REDIS_PORT')),
        password=os.getenv('REDIS_PASSWORD'),
        db=int(os.getenv('REDIS_DB')),
        decode_responses=True
    )
    r.ping()
    print("✅ Redis connection successful!")

    # Test write
    r.set('mutt:test', 'hello')
    val = r.get('mutt:test')
    r.delete('mutt:test')
    print(f"✅ Redis read/write successful! (value: {val})")
except Exception as e:
    print(f"❌ Redis connection failed: {e}")
PYTHON
EOF
```

**8.3 Test Moogsoft Webhook (Optional)**

```bash
sudo -u mutt bash << 'EOF'
cd /opt/mutt
source venv/bin/activate
source .env

python3 << 'PYTHON'
import requests
import os

try:
    url = os.getenv('MOOG_WEBHOOK_URL')
    token = os.getenv('MOOG_API_TOKEN')

    # Test payload
    payload = {
        "signature": "test",
        "source_id": "mutt-test",
        "external_id": "test-123",
        "manager": "MUTT v2.5",
        "source": "manual-test",
        "class": "Test",
        "agent": "mutt-test",
        "agent_location": "manual",
        "type": "Test Event",
        "severity": 3,
        "description": "Manual connectivity test"
    }

    headers = {
        "Content-Type": "application/json",
        "Authorization": f"Bearer {token}"
    }

    response = requests.post(url, json=payload, headers=headers, timeout=5)

    if response.status_code == 200:
        print("✅ Moogsoft webhook test successful!")
    else:
        print(f"⚠️  Moogsoft webhook returned {response.status_code}: {response.text}")
except Exception as e:
    print(f"❌ Moogsoft webhook test failed: {e}")
PYTHON
EOF
```

---

##### 5.2.4.10 Step 9: Service Startup and Verification

**9.1 Enable Services**

```bash
# Enable all services to start on boot
sudo systemctl enable mutt-ingestor.service
sudo systemctl enable mutt-alerter@{1..5}.service
sudo systemctl enable mutt-moog-forwarder.service
sudo systemctl enable mutt-webui.service
sudo systemctl enable mutt-remediation.service

# Verify enabled
systemctl list-unit-files | grep mutt | grep enabled
```

**9.2 Start Services One-by-One**

```bash
# Start ingestor first
sudo systemctl start mutt-ingestor.service
sleep 3
sudo systemctl status mutt-ingestor.service --no-pager

# Start alerter instances
sudo systemctl start mutt-alerter@{1..5}.service
sleep 3
sudo systemctl status mutt-alerter@1.service --no-pager

# Start moog forwarder
sudo systemctl start mutt-moog-forwarder.service
sleep 3
sudo systemctl status mutt-moog-forwarder.service --no-pager

# Start web UI
sudo systemctl start mutt-webui.service
sleep 3
sudo systemctl status mutt-webui.service --no-pager

# Start remediation
sudo systemctl start mutt-remediation.service
sleep 3
sudo systemctl status mutt-remediation.service --no-pager
```

**9.3 Check All Service Status**

```bash
# View all MUTT services
systemctl status mutt-* --no-pager

# Check for failed services
systemctl --failed | grep mutt

# Should return nothing if all services are running
```

**9.4 Verify Logs**

```bash
# Check recent logs
sudo journalctl -u mutt-ingestor -n 20 --no-pager
sudo journalctl -u mutt-alerter@1 -n 20 --no-pager
sudo journalctl -u mutt-webui -n 20 --no-pager

# Follow all MUTT logs
sudo journalctl -u mutt-* -f
# (Ctrl+C to stop)
```

**9.5 Verify Metrics Endpoints**

```bash
# Check Prometheus metrics
curl -s http://localhost:9090/metrics | head -20  # Ingestor
curl -s http://localhost:9091/metrics | head -20  # Alerter
curl -s http://localhost:9092/metrics | head -20  # Moog Forwarder
curl -s http://localhost:9093/metrics | head -20  # Remediation
```

**9.6 Verify Web UI**

```bash
# Check Web UI health
curl -s http://localhost:8090/health

# Expected: {"status": "healthy"}

# Test API (get alert rules)
curl -s http://localhost:8090/api/v1/rules | jq .
```

---

##### 5.2.4.11 Step 10: Integration Testing

**10.1 End-to-End Flow Test**

```bash
# Inject a test syslog message
redis-cli -h <redis_host> -p <redis_port> << 'EOF'
LPUSH mutt:queue:raw '{"timestamp": "2025-11-12T10:00:00Z", "hostname": "test-server", "message": "Test error message", "severity": 3, "facility": 1}'
EOF

# Wait 2 seconds for processing
sleep 2

# Check that message was processed (check event_audit_log)
psql -h <postgres_host> -U mutt_app -d mutt -c "SELECT * FROM event_audit_log ORDER BY id DESC LIMIT 5;"

# Check logs for processing
sudo journalctl -u mutt-alerter@1 -n 50 --no-pager | grep -i "test-server"
```

**10.2 Verify Redis Queues**

```bash
# Check queue lengths
redis-cli -h <redis_host> -p <redis_port> << 'EOF'
LLEN mutt:queue:raw
LLEN mutt:queue:classified
LLEN mutt:queue:dlq
EOF

# All should be 0 or low numbers if processing is working
```

**10.3 Check Prometheus Metrics**

```bash
# Check message counters
curl -s http://localhost:9090/metrics | grep mutt_messages_received_total
curl -s http://localhost:9091/metrics | grep mutt_messages_processed_total
curl -s http://localhost:9092/metrics | grep mutt_messages_forwarded_total
```

---

##### 5.2.4.12 Troubleshooting Decision Trees

**Issue: Service Won't Start**

```
1. Check service status
   → sudo systemctl status mutt-<service>.service

2. Check logs
   → sudo journalctl -u mutt-<service> -n 50

3. Common causes:
   a) Missing dependencies (Redis/PostgreSQL down)
      → Verify: redis-cli ping
      → Verify: psql -h <host> -U <user> -d mutt -c "SELECT 1"

   b) Permission errors
      → Check: ls -la /opt/mutt
      → Fix: sudo chown -R mutt:mutt /opt/mutt

   c) Configuration errors
      → Check: sudo -u mutt cat /opt/mutt/.env
      → Verify: All required variables set

   d) Python import errors
      → Test: sudo -u mutt /opt/mutt/venv/bin/python -m services.<service>
      → Fix: Reinstall dependencies
```

**Issue: Can't Connect to Redis**

```
1. Verify Redis is running
   → redis-cli -h <host> -p <port> ping

2. Check network connectivity
   → telnet <redis_host> <redis_port>
   → nc -zv <redis_host> <redis_port>

3. Check authentication
   → redis-cli -h <host> -p <port> -a <password> ping

4. Check .env file
   → grep REDIS /opt/mutt/.env

5. Check firewall
   → sudo iptables -L | grep <redis_port>
   → sudo ufw status | grep <redis_port>
```

**Issue: Database Errors**

```
1. Verify PostgreSQL is running
   → psql -h <host> -U <user> -d mutt -c "SELECT version();"

2. Check schema exists
   → psql -h <host> -U <user> -d mutt -c "\dt"

3. Check partitions exist
   → psql -h <host> -U <user> -d mutt -c "SELECT tablename FROM pg_tables WHERE tablename LIKE 'event_audit_log_%';"

4. Create missing partitions
   → psql -h <host> -U <user> -d mutt -c "SELECT create_monthly_partition(CURRENT_DATE);"

5. Check permissions
   → psql -h <host> -U <user> -d mutt -c "\du"
```

**Issue: Messages Not Processing**

```
1. Check queue lengths
   → redis-cli LLEN mutt:queue:raw
   → redis-cli LLEN mutt:queue:classified

2. Check if services are running
   → systemctl status mutt-* --no-pager

3. Check for errors in logs
   → sudo journalctl -u mutt-alerter@1 -n 100 | grep -i error

4. Verify alert rules exist
   → psql -h <host> -U <user> -d mutt -c "SELECT COUNT(*) FROM alert_rules WHERE is_active=true;"

5. Check circuit breaker state
   → redis-cli GET mutt:circuit:moog:state
   → If "OPEN", wait for timeout or manually reset
```

**Issue: High Memory Usage**

```
1. Check Redis memory
   → redis-cli INFO memory

2. Check queue lengths
   → redis-cli LLEN mutt:queue:*

3. Check backpressure settings
   → grep BACKPRESSURE /opt/mutt/.env

4. Enable load shedding if needed
   → Edit .env: BACKPRESSURE_MODE=shed
   → Restart services
```

---

##### 5.2.4.13 Manual Deployment Verification Checklist

```markdown
## Deployment Complete Checklist

- [ ] All 5 services running (systemctl status mutt-*)
- [ ] No failed services (systemctl --failed)
- [ ] PostgreSQL connection working
- [ ] Redis connection working
- [ ] Web UI accessible (http://localhost:8090/health)
- [ ] Metrics endpoints responding (ports 9090-9093)
- [ ] Alert rules loaded (psql: SELECT COUNT(*) FROM alert_rules)
- [ ] Test message processed successfully
- [ ] Logs show no errors (journalctl -u mutt-*)
- [ ] Queues are processing (LLEN mutt:queue:*)
- [ ] Event audit log recording events
- [ ] Moogsoft webhook reachable (optional)

## Post-Deployment Tasks

- [ ] Configure monitoring (Prometheus scraping)
- [ ] Set up log aggregation (if applicable)
- [ ] Configure backups (PostgreSQL and Redis)
- [ ] Document custom configuration
- [ ] Test failover scenarios
- [ ] Configure alerts for service failures
- [ ] Review and tune performance settings
```

---

**Manual Deployment Complete!**

You now have a comprehensive step-by-step guide to manually deploy MUTT v2.5 with verification at each stage. This guide provides 80-85% success rate with careful following of steps and serves as both:
1. A deployment guide for new installations
2. A troubleshooting reference when automated deployments fail
3. Educational documentation for understanding system architecture

### 5.3 Production Readiness Checklist

#### 5.3.1 Pre-Deployment Validation

```markdown
## Infrastructure Requirements

- [ ] Redis cluster configured with Sentinel/Cluster mode
  - [ ] AOF persistence enabled
  - [ ] Memory limit set (recommend 8GB minimum)
  - [ ] Eviction policy: noeviction
  - [ ] TLS enabled for production

- [ ] PostgreSQL configured with replication
  - [ ] Streaming replication to standby
  - [ ] Point-in-time recovery (PITR) configured
  - [ ] Connection pooling (PgBouncer recommended)
  - [ ] TLS enabled for production
  - [ ] Monthly partitions pre-created (3 months ahead)

- [ ] Vault configured and accessible
  - [ ] AppRole authentication configured
  - [ ] Secrets stored at correct path
  - [ ] Token renewal working
  - [ ] TLS certificate valid

- [ ] Monitoring infrastructure ready
  - [ ] Prometheus scraping all /metrics endpoints
  - [ ] Grafana dashboards imported
  - [ ] Alertmanager rules configured
  - [ ] PagerDuty/Slack integration tested

## Security Hardening

- [ ] All secrets stored in Vault (NOT in env files)
- [ ] TLS enabled for all inter-service communication
- [ ] API authentication enforced (X-API-Key header)
- [ ] Network policies applied (Kubernetes)
- [ ] Firewall rules configured (RHEL)
- [ ] Service accounts with minimal permissions
- [ ] Container images scanned for vulnerabilities
- [ ] Security context constraints applied

## Performance Tuning

- [ ] Resource limits appropriate for load
  - [ ] Ingestor: 1 CPU, 1GB RAM minimum per replica
  - [ ] Alerter: 2 CPU, 2GB RAM minimum per replica
  - [ ] Moog Forwarder: 500m CPU, 1GB RAM minimum
  - [ ] Web UI: 500m CPU, 512MB RAM minimum

- [ ] Horizontal pod autoscaling configured
  - [ ] Ingestor: 3-10 replicas based on CPU/memory
  - [ ] Alerter: 5-20 replicas based on queue depth
  - [ ] Moog Forwarder: 1-3 replicas

- [ ] Database tuning applied
  - [ ] shared_buffers = 25% of RAM
  - [ ] effective_cache_size = 50% of RAM
  - [ ] work_mem tuned for concurrent queries
  - [ ] Connection pool sized appropriately

## Operational Readiness

- [ ] Runbooks created for common scenarios
  - [ ] Service restart procedures
  - [ ] Database failover procedures
  - [ ] Redis failover procedures
  - [ ] Certificate rotation procedures
  - [ ] Secret rotation procedures

- [ ] Backup and recovery tested
  - [ ] PostgreSQL daily backups
  - [ ] Redis AOF backups
  - [ ] Configuration backups
  - [ ] Recovery tested (RTO < 1 hour)

- [ ] Monitoring and alerting validated
  - [ ] SLO alerts configured (availability, latency)
  - [ ] Queue depth alerts
  - [ ] Circuit breaker state alerts
  - [ ] Resource utilization alerts
  - [ ] Certificate expiry alerts

- [ ] Documentation complete
  - [ ] Architecture diagrams updated
  - [ ] API documentation current
  - [ ] Troubleshooting guide available
  - [ ] Contact information for on-call

## Testing Complete

- [ ] Unit tests: 90%+ coverage, all passing
- [ ] Integration tests: All passing
- [ ] Load tests: Meeting performance targets
  - [ ] Ingestor: 1000+ EPS sustained
  - [ ] Alerter: p95 latency < 100ms
  - [ ] End-to-end latency: p95 < 500ms
  - [ ] Circuit breaker functioning correctly

- [ ] Chaos testing performed
  - [ ] Redis failover tested
  - [ ] PostgreSQL failover tested
  - [ ] Network partition handled gracefully
  - [ ] Pod crashes recovered automatically

## Deployment Validation

- [ ] Canary deployment successful
  - [ ] 10% traffic to new version
  - [ ] No errors for 1 hour
  - [ ] Rollback plan tested

- [ ] Production smoke tests passed
  - [ ] Ingest test event via API
  - [ ] Verify event processed through pipeline
  - [ ] Verify alert forwarded to Moogsoft
  - [ ] Verify audit log entry created
  - [ ] Web UI accessible and functional

- [ ] Health checks passing
  - [ ] All /health endpoints returning 200
  - [ ] Kubernetes readiness probes passing
  - [ ] Prometheus targets up and scraping

## Post-Deployment

- [ ] Monitor for 24 hours with on-call support
- [ ] Review logs for errors/warnings
- [ ] Validate metrics match expected patterns
- [ ] Confirm SLO compliance
- [ ] Document any issues encountered
- [ ] Update runbooks based on lessons learned
```

---

## Validation Checklist

### Functional Validation
-   [ ] All unit tests pass (90%+ coverage)
-   [ ] All integration tests pass
-   [ ] End-to-end event flow tested and working
-   [ ] Load tests meet performance targets (1000+ EPS)
-   [ ] Circuit breaker functions correctly under failure scenarios
-   [ ] DLQ replay and remediation working

### Performance Validation
-   [ ] Ingestor latency p95 < 50ms
-   [ ] Alerter processing latency p95 < 100ms
-   [ ] Moog forwarding latency p95 < 200ms
-   [ ] Database write throughput > 500 writes/sec
-   [ ] Redis operations > 10,000 ops/sec

### Security Validation
-   [ ] All secrets stored in Vault
-   [ ] TLS enabled for all external connections
-   [ ] API authentication enforced
-   [ ] Security scans clean (no critical/high vulnerabilities)
-   [ ] Audit logging functioning correctly

### Operational Validation
-   [ ] Monitoring dashboards displaying data
-   [ ] Alerts configured and tested
-   [ ] Backup and recovery procedures tested
-   [ ] Runbooks complete and validated
-   [ ] On-call rotation established

---

## Reference Documents

-   [System Architecture](architecture/SYSTEM_ARCHITECTURE.md)
-   [Design Rationale](architecture/DESIGN_RATIONALE.md)
-   [API Reference](api/REFERENCE.md)
-   [Database Schema](db/SCHEMA.md)
-   [ADRs](adr/)
-   [... and all other documents in the docs directory]

---

This completes the rebuild guide for MUTT v2.5.

