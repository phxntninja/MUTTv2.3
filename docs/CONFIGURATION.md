# MUTT Configuration

This document provides a detailed overview of the configuration for each of the MUTT services.

## Ingestor Service Configuration

| Variable | Default | Description |
|---|---|---|
| SERVER_PORT_INGESTOR | 8080 | HTTP listen port |
| REDIS_HOST | localhost | Redis hostname |
| REDIS_PORT | 6379 | Redis port |
| REDIS_TLS_ENABLED | true | Enable TLS for Redis |
| REDIS_CA_CERT_PATH | /etc/mutt/certs/ca.pem | Redis TLS CA certificate path |
| REDIS_MAX_CONNECTIONS | 20 | Redis connection pool size |
| MAX_INGEST_QUEUE_SIZE | 1000000 | Queue cap for backpressure |
| INGEST_QUEUE_NAME | mutt:ingest_queue | Redis queue name |
| METRICS_PREFIX | mutt:metrics | Redis metrics key prefix |
| VAULT_ADDR | (required) | Vault server URL |
| VAULT_ROLE_ID | (required) | AppRole role ID |
| VAULT_SECRET_ID_FILE | /etc/mutt/secrets/vault_secret_id | Path to secret ID file |
| VAULT_SECRETS_PATH | secret/mutt | Vault KV path |
| VAULT_TOKEN_RENEW_THRESHOLD | 3600 | Renew token when TTL < N seconds |
| VAULT_RENEW_CHECK_INTERVAL | 300 | Check token TTL every N seconds |
| REQUIRED_MESSAGE_FIELDS | timestamp,message,hostname | Required fields in messages |

## Alerter Service Configuration

| Variable | Default | Description |
|---|---|---|
| POD_NAME | alerter-{random} | Unique worker identifier |
| METRICS_PORT_ALERTER | 8081 | Prometheus metrics port |
| HEALTH_PORT_ALERTER | 8082 | Health check port |
| LOG_LEVEL | INFO | Log level (DEBUG/INFO/WARNING/ERROR) |
| REDIS_HOST | localhost | Redis hostname |
| REDIS_PORT | 6379 | Redis port |
| REDIS_TLS_ENABLED | true | Enable TLS for Redis |
| REDIS_CA_CERT_PATH | - | Redis TLS CA certificate path |
| REDIS_MAX_CONNECTIONS | 20 | Redis connection pool size |
| INGEST_QUEUE_NAME | mutt:ingest_queue | Redis ingest queue name |
| ALERT_QUEUE_NAME | mutt:alert_queue | Redis alert queue name |
| ALERTER_PROCESSING_LIST_PREFIX | mutt:processing:alerter | Processing list prefix |
| ALERTER_HEARTBEAT_PREFIX | mutt:heartbeat:alerter | Heartbeat key prefix |
| ALERTER_HEARTBEAT_INTERVAL | 10 | Heartbeat interval (seconds) |
| ALERTER_JANITOR_TIMEOUT | 30 | Heartbeat expiry for janitor (seconds) |
| ALERTER_DLQ_NAME | mutt:dlq:alerter | Dead letter queue name |
| ALERTER_MAX_RETRIES | 3 | Max retries before DLQ |
| BRPOPLPUSH_TIMEOUT | 5 | BRPOPLPUSH timeout (seconds) |
| DB_HOST | localhost | PostgreSQL hostname |
| DB_PORT | 5432 | PostgreSQL port |
| DB_NAME | mutt_db | Database name |
| DB_USER | mutt_user | Database user |
| DB_TLS_ENABLED | true | Enable TLS for PostgreSQL |
| DB_TLS_CA_CERT_PATH | - | PostgreSQL TLS CA certificate path |
| DB_POOL_MIN_CONN | 2 | Min connections in pool |
| DB_POOL_MAX_CONN | 10 | Max connections in pool |
| CACHE_RELOAD_INTERVAL | 300 | Cache refresh interval (seconds) |
| UNHANDLED_PREFIX | mutt:unhandled | Redis key prefix for unhandled counters |
| UNHANDLED_THRESHOLD | 100 | Events before meta-alert |
| UNHANDLED_EXPIRY_SECONDS | 86400 | Counter expiry (24 hours) |
| UNHANDLED_DEFAULT_TEAM | NETO | Default team for unhandled alerts |
| VAULT_ADDR | (required) | Vault server URL |
| VAULT_ROLE_ID | (required) | AppRole role ID |
| VAULT_SECRET_ID_FILE | /etc/mutt/secrets/vault_secret_id | Path to secret ID file |
| VAULT_SECRETS_PATH | secret/mutt | Vault KV path |

### Backpressure (Dynamic Config)

| Variable | Default | Description |
|---|---|---|
| alerter_queue_warn_threshold | 1000 | Threshold to start warning |
| alerter_queue_shed_threshold | 2000 | Threshold to start shedding |
| alerter_shed_mode | dlq | Shed mode (dlq or defer) |
| alerter_defer_sleep_ms | 250 | Defer sleep time in ms |

## Moog Forwarder Service Configuration

| Variable | Default | Description |
|---|---|---|
| POD_NAME | moog-forwarder-{random} | Unique worker identifier |
| METRICS_PORT_MOOG | 8083 | Prometheus metrics port |
| HEALTH_PORT_MOOG | 8084 | Health check port |
| LOG_LEVEL | INFO | Log level |
| REDIS_HOST | localhost | Redis hostname |
| REDIS_PORT | 6379 | Redis port |
| REDIS_TLS_ENABLED | true | Enable TLS for Redis |
| REDIS_CA_CERT_PATH | - | Redis TLS CA certificate path |
| REDIS_MAX_CONNECTIONS | 20 | Redis connection pool size |
| ALERT_QUEUE_NAME | mutt:alert_queue | Redis alert queue name |
| MOOG_PROCESSING_LIST_PREFIX | mutt:processing:moog | Processing list prefix |
| MOOG_DLQ_NAME | mutt:dlq:moog | Dead letter queue name |
| BRPOPLPUSH_TIMEOUT | 5 | BRPOPLPUSH timeout (seconds) |
| MOOG_HEARTBEAT_PREFIX | mutt:heartbeat:moog | Heartbeat key prefix |
| MOOG_HEARTBEAT_INTERVAL | 10 | Heartbeat interval (seconds) |
| MOOG_JANITOR_TIMEOUT | 30 | Heartbeat expiry for janitor (seconds) |
| MOOG_WEBHOOK_URL | (required) | Moogsoft webhook URL |
| MOOG_WEBHOOK_TIMEOUT | 10 | HTTP request timeout (seconds) |
| MOOG_RATE_LIMIT | 50 | Max requests (shared across all pods) |
| MOOG_RATE_PERIOD | 1 | Per N seconds (shared rate limit window) |
| MOOG_RATE_LIMIT_KEY | mutt:rate_limit:moog | Redis key for rate limiter |
| MOOG_MAX_RETRIES | 5 | Max retries before DLQ |
| MOOG_RETRY_BASE_DELAY | 1.0 | Initial retry delay (seconds) |
| MOOG_RETRY_MAX_DELAY | 60.0 | Max retry delay (seconds) |
| VAULT_ADDR | (required) | Vault server URL |
| VAULT_ROLE_ID | (required) | AppRole role ID |
| VAULT_SECRET_ID_FILE | /etc/mutt/secrets/vault_secret_id | Path to secret ID file |
| VAULT_SECRETS_PATH | secret/mutt | Vault KV path |

## Web UI Service Configuration

| Variable | Default | Description |
|---|---|---|
| SERVER_PORT_WEBUI | 8090 | HTTP listen port |
| LOG_LEVEL | INFO | Log level |
| REDIS_HOST | localhost | Redis hostname |
| REDIS_PORT | 6379 | Redis port |
| REDIS_TLS_ENABLED | true | Enable TLS for Redis |
| REDIS_CA_CERT_PATH | - | Redis TLS CA certificate path |
| REDIS_MAX_CONNECTIONS | 10 | Redis connection pool size |
| METRICS_PREFIX | mutt:metrics | Redis metrics key prefix |
| DB_HOST | localhost | PostgreSQL hostname |
| DB_PORT | 5432 | PostgreSQL port |
| DB_NAME | mutt_db | Database name |
| DB_USER | mutt_user | Database user |
| DB_TLS_ENABLED | true | Enable TLS for PostgreSQL |
| DB_TLS_CA_CERT_PATH | - | PostgreSQL TLS CA certificate path |
| DB_POOL_MIN_CONN | 2 | Min connections in pool |
| DB_POOL_MAX_CONN | 10 | Max connections in pool |
| METRICS_CACHE_TTL | 5 | Metrics cache TTL (seconds) |
| AUDIT_LOG_PAGE_SIZE | 50 | Default page size for audit logs |
| VAULT_ADDR | (required) | Vault server URL |
| VAULT_ROLE_ID | (required) | AppRole role ID |
| VAULT_SECRET_ID_FILE | /etc/mutt/secrets/vault_secret_id | Path to secret ID file |
| VAULT_SECRETS_PATH | secret/mutt | Vault KV path |
| PROMETHEUS_URL | http://localhost:9090 | Prometheus base URL for SLOs |
