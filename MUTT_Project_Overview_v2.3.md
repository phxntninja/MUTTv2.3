MUTT (Moog/Monitoring Universal-Translation-Toolkit) Project Overview v2.3
Document Version: 2.3
Last Updated: 2025
Status: Production-Ready
1. Project Objective
MUTT is a resilient, horizontally-scalable middleware platform that decouples monitoring sources (SolarWinds, SNMP, Syslog) from Moogsoft AIOps. It provides:

    Zero-alert-loss architecture using Redis queues and dead-letter queues (DLQs)
    Intelligent rule-based processing with prioritized matching, environment-aware handling, and automatic meta-alert generation
    Enterprise-grade security via HashiCorp Vault, mutual-TLS, and API key authentication
    Full observability with Prometheus metrics, structured logging with correlation IDs, and health check endpoints

2. System Architecture (v2.3)
Data Flow Pipeline
Copy

SolarWinds/SNMP/Syslog → [1] Ingest Webhook → Redis (mutt:ingest_queue)
                                                           ↓
                [2] Event Processor (Alerter) ← PostgreSQL (Rules/Cache)
                           ↓
                Redis (mutt:alert_queue)
                           ↓
                [3] Moog Forwarder → Moogsoft API
                           ↓
                [4] Web UI & API Service (Management & Observability)

Component Breakdown
Table
Copy
#	Component	Role	Technology	Key Features
1	Ingest Webhook Service	HTTP receiver for raw monitoring events	Flask/Gunicorn	Validates JSON, adds correlation IDs, pushes to Redis
2	Event Processor Service	Core rule-matching and decision engine	Python worker	BRPOPLPUSH reliability, in-memory cache, Lua atomic operations
3	Moog Forwarder Service	API forwarder with rate limiting	Python worker	Shared Redis rate limiter, exponential backoff, DLQ
4	Web UI & API Service	Management dashboard and API	Flask	Real-time metrics, full CRUD API for rules/hosts/teams
3. Component Deep Dive
Component #1: Ingest Webhook Service (NEW - Required for v2.3)
Purpose: Receive HTTP POST events from monitoring sources and enqueue them.
Deployment: Lightweight Flask app, horizontally scalable behind a load balancer.
Python
Copy

# Minimal implementation example
@app.route('/webhook', methods=['POST'])
def ingest():
    data = request.get_json()
    data['_correlation_id'] = str(uuid.uuid4())
    redis.lpush('mutt:ingest_queue', json.dumps(data))
    return jsonify({"status": "accepted"}), 202

Key Config:

    WEBHOOK_PORT (default: 8080)
    REDIS_HOST, REDIS_PORT, REDIS_PASS (from Vault)
    API_KEY for source authentication (recommended)

Component #2: Event Processor Service (alerter_service.py)
Purpose: Process events from mutt:ingest_queue using "at-least-once" semantics.
Scaling: Run multiple replicas (pods). Each replica is single-threaded for simplicity; scale horizontally.
Core Logic:

    Atomic dequeue: BRPOPLPUSH from mutt:ingest_queue → mutt:processing:alerter:{POD_NAME}
    Cache-based matching: Loads all rules/hosts/teams from PostgreSQL into memory (refreshed every 5 min or on SIGHUP)
    Rule evaluation: Matches against trap_oid, syslog_severity, message content (contains/regex)
    Decision tree:
        Handled events: Audit to PostgreSQL → push to mutt:alert_queue if forwarding required
        Unhandled events: Increment Redis counter → generate meta-alert at threshold (100 events)
    Poison messages: After 3 retries, move to mutt:dlq:alerter with logging

Key Config:

    METRICS_PORT_ALERTER (8081), HEALTH_PORT_ALERTER (8082)
    CACHE_RELOAD_INTERVAL (300s)
    UNHANDLED_THRESHOLD (100), ALERTER_MAX_RETRIES (3)

Component #3: Moog Forwarder Service (moog_forwarder_service.py)
Purpose: Forward alerts to Moogsoft API with global rate limiting and retry logic.
Scaling: Single-threaded pods; horizontal scaling via replicas.
Core Logic:

    Atomic dequeue: BRPOPLPUSH from mutt:alert_queue → mutt:processing:moog:{POD_NAME}
    Shared rate limiting: Redis Lua script enforces MOOG_RATE_LIMIT requests per MOOG_RATE_PERIOD across ALL pods
    Exponential backoff:
        Retry on 5xx, timeouts, connection errors
        Delay: 1s → 2s → 4s → 8s → 16s (capped at MOOG_RETRY_MAX_DELAY)
    Permanent failures: 4xx errors or max retries → move to mutt:dlq:moog

Key Config:

    METRICS_PORT_MOOG (8083), HEALTH_PORT_MOOG (8084)
    MOOG_RATE_LIMIT (50 req/s), MOOG_MAX_RETRIES (5)
    MOOG_WEBHOOK_URL, MOOG_WEBHOOK_TIMEOUT

Component #4: Web UI & API Service (web_ui_service.py)
Purpose: Management interface and real-time observability.
Auth: API key required for all endpoints except /health and /metrics.
Endpoints:

    GET /?api_key=... - Real-time dashboard (Chart.js, auto-refreshes every 10s)
    GET /health - Kubernetes readiness/liveness probe
    GET /metrics - Prometheus scrape endpoint
    /api/v1/rules - CRUD for alert rules (JSON API)
    /api/v1/dev-hosts - CRUD for development host classification
    /api/v1/teams - CRUD for device-to-team assignments
    /api/v1/audit-logs - Paginated audit log viewer with filtering

Key Config:

    SERVER_PORT_WEBUI (8090)
    METRICS_CACHE_TTL (5s)
    WEBUI_API_KEY (from Vault)

4. Configuration (Environment Variables)
All v2.3 services are configured exclusively via environment variables. Secrets are managed by HashiCorp Vault.
Common Variables (All Services)
Table
Copy
Variable	Example	Description
REDIS_HOST	redis.prod.svc	Redis hostname
REDIS_PORT	6379	Redis port
REDIS_TLS_ENABLED	true	Enable TLS
REDIS_CA_CERT_PATH	/etc/mutt/certs/redis-ca.pem	CA certificate
DB_HOST	postgres.prod.svc	PostgreSQL hostname
DB_PORT	5432	PostgreSQL port
DB_NAME	mutt_db	Database name
DB_TLS_ENABLED	true	Enable TLS
VAULT_ADDR	https://vault.prod.svc:8200	Vault URL
VAULT_ROLE_ID	mutt-service-role	AppRole Role ID
VAULT_SECRET_ID_FILE	/etc/mutt/secrets/vault_secret_id	Secret ID file path
LOG_LEVEL	INFO	Logging level
Service-Specific Variables
Event Processor:

    METRICS_PORT_ALERTER=8081, HEALTH_PORT_ALERTER=8082
    CACHE_RELOAD_INTERVAL=300
    UNHANDLED_THRESHOLD=100

Moog Forwarder:

    METRICS_PORT_MOOG=8083, HEALTH_PORT_MOOG=8084
    MOOG_RATE_LIMIT=50, MOOG_RATE_PERIOD=1
    MOOG_WEBHOOK_URL=https://moogsoft.example.com/api/v1/events

Web UI:

    SERVER_PORT_WEBUI=8090
    METRICS_CACHE_TTL=5

5. Security Model

    Secrets Management: HashiCorp Vault KV v2 with AppRole authentication. Tokens auto-renewed in background threads.
    Network Security:
        Mutual TLS for Redis and PostgreSQL connections
        API key authentication for all management endpoints (X-API-KEY header or query param)
    Rate Limiting: Global rate limiter prevents Moogsoft API overwhelm and DDoS.
    Audit Trail: All handled events written to PostgreSQL with correlation IDs for compliance.

6. Deployment
Kubernetes (Recommended)
yaml
Copy

apiVersion: apps/v1
kind: Deployment
metadata:
  name: mutt-alerter
spec:
  replicas: 3
  selector:
    matchLabels:
      app: mutt-alerter
  template:
    metadata:
      labels:
        app: mutt-alerter
    spec:
      containers:
      - name: alerter
        image: mutt/alerter:2.3
        env:
        - name: POD_NAME
          valueFrom:
            fieldRef:
              fieldPath: metadata.name
        - name: REDIS_HOST
          value: "redis.prod.svc"
        # ... other env vars
        ports:
        - containerPort: 8081
          name: metrics
        - containerPort: 8082
          name: health
        livenessProbe:
          httpGet:
            path: /health
            port: 8082
          initialDelaySeconds: 30
        readinessProbe:
          httpGet:
            path: /health
            port: 8082
        volumeMounts:
        - name: vault-secret
          mountPath: /etc/mutt/secrets
          readOnly: true
      volumes:
      - name: vault-secret
        secret:
          secretName: vault-secret-id

Apply same pattern for Moog Forwarder and Web UI services.
Local Development (Docker Compose)
Note: For development only. Uses Vault dev server.
yaml
Copy

version: '3.7'
services:
  redis:
    image: redis:7-alpine
    ports: ["6379:6379"]
    command: redis-server --requirepass devpass
  
  postgres:
    image: postgres:15-alpine
    environment:
      POSTGRES_DB: mutt_db
      POSTGRES_USER: mutt_user
      POSTGRES_PASSWORD: devpass
    ports: ["5432:5432"]
  
  vault:
    image: vault:1.15
    environment:
      VAULT_DEV_ROOT_TOKEN_ID: dev-token
    ports: ["8200:8200"]
    command: vault server -dev
    
  # Run services with env vars pointing to above

7. Monitoring & Alerting
Key Prometheus Alerts
yaml
Copy

groups:
- name: mutt_alerts
  rules:
  - alert: MUTTDlqGrowing
    expr: mutt_alerter_dlq_depth > 100
    for: 5m
    annotations:
      summary: "DLQ depth is growing, potential rule misconfiguration"
  
  - alert: MUTTCacheReloadFailed
    expr: rate(mutt_alerter_cache_reload_failures_total[5m]) > 0
    annotations:
      summary: "Cache reload failures detected"
  
  - alert: MUTTRedisDown
    expr: up{job="mutt-alerter"} == 0
    for: 2m
    annotations:
      summary: "MUTT service is down"

8. Next Steps for Developers

    Setup Vault: Initialize Vault, enable AppRole, write secrets per VAULT_SECRETS_PATH.
    Initialize Database: Run provided schema SQL to create tables.
    Configure Rules: Use Web UI or API to add alert rules, dev hosts, and team mappings.
    Deploy Services: Use Kubernetes manifests (production) or Docker Compose (development).
    Verify: Check health endpoints, review logs for correlation IDs, test with sample webhook.

9. Documentation Index

    This file: High-level architecture and configuration
    Part 2: Event Processor Service source code + operational docs
    Part 3: Moog Forwarder Service source code + operational docs
    Part 4: Web UI & API Service source code + operational docs
    Appendix A: Database schema (coming soon)
    Appendix B: Vault setup guide (coming soon)