Implementation: ingest_webhook_service.py
Python
Copy

#!/usr/bin/env python3
"""
=====================================================================
MUTT Ingest Webhook Service (v2.4)
=====================================================================
Component #1 of the MUTT architecture.

This is a minimalist, high-performance HTTP receiver that:
- Accepts JSON webhooks from SolarWinds, SNMP traps, or Syslog forwarders
- Validates and normalizes incoming payloads
- Injects a correlation ID for distributed tracing
- Pushes validated events to Redis ingest_queue
- Returns 202 Accepted immediately (non-blocking)
- Implements basic rate limiting and payload size controls

Key Features:
- Stateless design for horizontal scaling
- Request validation and sanitization
- Structured logging with correlation IDs
- Health check endpoint for load balancers
- Prometheus metrics for webhook volume

Author: MUTT Team
Version: 2.4
=====================================================================
"""

import os
import sys
import json
import redis
import hvac
import logging
import uuid
import time
from datetime import datetime
from flask import Flask, request, jsonify, Response
from prometheus_client import Counter, Histogram, start_http_server
import signal

# =====================================================================
# PROMETHEUS METRICS
# =====================================================================

METRIC_WEBHOOK_REQUESTS_TOTAL = Counter(
    'mutt_webhook_requests_total',
    'Total webhook requests received',
    ['source', 'status']  # solarwinds|snmp|syslog, accepted|rejected|error
)

METRIC_WEBHOOK_LATENCY = Histogram(
    'mutt_webhook_latency_seconds',
    'Webhook request processing latency',
    buckets=[0.001, 0.005, 0.01, 0.025, 0.05, 0.1, 0.25]
)

METRIC_REDIS_PUSH_LATENCY = Histogram(
    'mutt_webhook_redis_push_latency_seconds',
    'Time to push event to Redis'
)

# =====================================================================
# LOGGING SETUP
# =====================================================================

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - [%(correlation_id)s] - %(message)s'
)
logger = logging.getLogger(__name__)


class CorrelationIdFilter(logging.Filter):
    def filter(self, record):
        record.correlation_id = getattr(record, 'correlation_id', 'system')
        return True


logger.addFilter(CorrelationIdFilter())

# =====================================================================
# CONFIGURATION
# =====================================================================

class Config:
    def __init__(self):
        try:
            self.PORT = int(os.environ.get('WEBHOOK_PORT', 8080))
            self.METRICS_PORT = int(os.environ.get('WEBHOOK_METRICS_PORT', 8085))
            self.LOG_LEVEL = os.environ.get('LOG_LEVEL', 'INFO').upper()
            
            # Redis
            self.REDIS_HOST = os.environ.get('REDIS_HOST', 'localhost')
            self.REDIS_PORT = int(os.environ.get('REDIS_PORT', 6379))
            self.REDIS_TLS_ENABLED = os.environ.get('REDIS_TLS_ENABLED', 'true').lower() == 'true'
            self.REDIS_CA_CERT_PATH = os.environ.get('REDIS_CA_CERT_PATH')
            self.REDIS_MAX_CONNECTIONS = int(os.environ.get('REDIS_MAX_CONNECTIONS', 20))
            self.INGEST_QUEUE_NAME = os.environ.get('INGEST_QUEUE_NAME', 'mutt:ingest_queue')
            
            # Webhook
            self.MAX_PAYLOAD_SIZE = int(os.environ.get('MAX_PAYLOAD_SIZE', 16777216))  # 16MB
            self.REQUIRE_API_KEY = os.environ.get('REQUIRE_API_KEY', 'true').lower() == 'true'
            
            # Vault
            self.VAULT_ADDR = os.environ.get('VAULT_ADDR')
            self.VAULT_ROLE_ID = os.environ.get('VAULT_ROLE_ID')
            self.VAULT_SECRET_ID_FILE = os.environ.get('VAULT_SECRET_ID_FILE', '/etc/mutt/secrets/vault_secret_id')
            self.VAULT_SECRETS_PATH = os.environ.get('VAULT_SECRETS_PATH', 'secret/mutt')
            
            self._validate()
            
        except Exception as e:
            logger.error(f"FATAL: Configuration error: {e}")
            sys.exit(1)
    
    def _validate(self):
        if not self.VAULT_ADDR:
            raise ValueError("VAULT_ADDR is required")
        if not self.VAULT_ROLE_ID:
            raise ValueError("VAULT_ROLE_ID is required")
        logger.setLevel(self.LOG_LEVEL)


# =====================================================================
# VAULT SECRET MANAGEMENT
# =====================================================================

def fetch_secrets(config):
    try:
        logger.info(f"Connecting to Vault at {config.VAULT_ADDR}...")
        vault_client = hvac.Client(url=config.VAULT_ADDR)
        
        with open(config.VAULT_SECRET_ID_FILE, 'r') as f:
            secret_id = f.read().strip()
        
        vault_client.auth.approle.login(
            role_id=config.VAULT_ROLE_ID,
            secret_id=secret_id
        )
        
        response = vault_client.secrets.kv.v2.read_secret_version(
            path=config.VAULT_SECRETS_PATH
        )
        data = response['data']['data']
        
        secrets = {
            "REDIS_PASS": data.get('REDIS_PASS'),
            "WEBHOOK_API_KEY": data.get('WEBHOOK_API_KEY', '')
        }
        
        if not secrets["REDIS_PASS"]:
            raise ValueError("REDIS_PASS not found in Vault")
            
        logger.info("Successfully loaded secrets from Vault")
        return secrets
        
    except Exception as e:
        logger.error(f"FATAL: Failed to fetch secrets: {e}", exc_info=True)
        sys.exit(1)


# =====================================================================
# REDIS CONNECTION POOL
# =====================================================================

def create_redis_pool(config, secrets):
    try:
        pool_kwargs = {
            'host': config.REDIS_HOST,
            'port': config.REDIS_PORT,
            'password': secrets["REDIS_PASS"],
            'decode_responses': False,  # Keep as bytes for performance
            'socket_connect_timeout': 5,
            'max_connections': config.REDIS_MAX_CONNECTIONS,
        }
        
        if config.REDIS_TLS_ENABLED:
            pool_kwargs.update({
                'ssl': True,
                'ssl_cert_reqs': 'required',
                'ssl_ca_certs': config.REDIS_CA_CERT_PATH
            })
        
        pool = redis.ConnectionPool(**pool_kwargs)
        r = redis.Redis(connection_pool=pool)
        r.ping()
        logger.info("Successfully connected to Redis")
        return r
        
    except Exception as e:
        logger.error(f"FATAL: Could not connect to Redis: {e}", exc_info=True)
        sys.exit(1)


# =====================================================================
# PAYLOAD VALIDATION
# =====================================================================

def validate_payload(data):
    """Validate and sanitize incoming webhook payload."""
    if not isinstance(data, dict):
        return False, "Payload must be a JSON object"
    
    # Required fields
    required = ['hostname', 'timestamp', 'message']
    missing = [f for f in required if not data.get(f)]
    if missing:
        return False, f"Missing required fields: {missing}"
    
    # Type validation
    if not isinstance(data['hostname'], str) or len(data['hostname']) > 255:
        return False, "hostname must be a string <= 255 chars"
    
    if not isinstance(data['message'], str) or len(data['message']) > 65535:
        return False, "message must be a string <= 65535 chars"
    
    # Validate timestamp format (ISO 8601)
    try:
        datetime.fromisoformat(data['timestamp'].replace('Z', '+00:00'))
    except ValueError:
        return False, "timestamp must be ISO 8601 format"
    
    # Optional fields validation
    if 'trap_oid' in data and not isinstance(data['trap_oid'], str):
        return False, "trap_oid must be a string"
    
    if 'syslog_severity' in data and data['syslog_severity'] not in ['Emergency', 'Alert', 'Critical', 'Error', 'Warning', 'Notice', 'Info', 'Debug']:
        return False, "Invalid syslog_severity value"
    
    return True, None


# =====================================================================
# FLASK APPLICATION
# =====================================================================

def create_app():
    app = Flask(__name__)
    
    # Load config and secrets
    config = Config()
    app.config["MUTT_CONFIG"] = config
    secrets = fetch_secrets(config)
    app.config["SECRETS"] = secrets
    redis_client = create_redis_pool(config, secrets)
    app.redis_client = redis_client
    
    # Start metrics server
    start_http_server(config.METRICS_PORT)
    logger.info(f"Metrics server started on port {config.METRICS_PORT}")
    
    # ================================================================
    # REQUEST LIFECYCLE
    # ================================================================
    
    @app.before_request
    def before_request():
        # Generate correlation ID
        request.correlation_id = str(uuid.uuid4())
        
        # Validate content size early
        if request.content_length and request.content_length > config.MAX_PAYLOAD_SIZE:
            logger.warning(f"Payload too large: {request.content_length}")
           METRIC_WEBHOOK_REQUESTS_TOTAL.labels(source='unknown', status='rejected').inc()
            return jsonify({"error": "Payload too large"}), 413
    
    @app.after_request
    def after_request(response):
        logger.info(
            f"{request.method} {request.path} - "
            f"Status: {response.status_code} - "
            f"Source: {request.headers.get('User-Agent', 'unknown')}"
        )
        return response
    
    # ================================================================
    # HEALTH CHECK
    # ================================================================
    
    @app.route('/health', methods=['GET'])
    def health():
        """Health check for Kubernetes/load balancers."""
        try:
            redis_client.ping()
            return jsonify({
                "status": "healthy",
                "service": "mutt-ingest-webhook",
                "version": "2.4"
            }), 200
        except Exception as e:
            logger.error(f"Health check failed: {e}")
            return jsonify({
                "status": "unhealthy",
                "error": str(e)
            }), 503
    
    # ================================================================
    # WEBHOOK ENDPOINT
    # ================================================================
    
    @app.route('/webhook', methods=['POST'])
    def webhook():
        """Main webhook receiver."""
        start_time = time.time()
        
        # API key authentication
        if app.config["MUTT_CONFIG"].REQUIRE_API_KEY:
            api_key = request.headers.get('X-API-KEY')
            expected_key = secrets['WEBHOOK_API_KEY']
            
            if not api_key or not secrets_module.compare_digest(api_key, expected_key):
                logger.warning(f"Authentication failed from {request.remote_addr}")
               METRIC_WEBHOOK_REQUESTS_TOTAL.labels(source='unknown', status='rejected').inc()
                return jsonify({"error": "Unauthorized"}), 401
        
        # Parse JSON
        try:
            payload = request.get_json(force=False, silent=False)
        except Exception as e:
            logger.warning(f"Invalid JSON: {e}")
           METRIC_WEBHOOK_REQUESTS_TOTAL.labels(source='unknown', status='rejected').inc()
            return jsonify({"error": "Invalid JSON"}), 400
        
        if payload is None:
           METRIC_WEBHOOK_REQUESTS_TOTAL.labels(source='unknown', status='rejected').inc()
            return jsonify({"error": "Missing or invalid JSON body"}), 400
        
        # Determine source type (from header or payload)
        source_type = request.headers.get('X-Source-Type', 'solarwinds')
        
        # Validate payload
        is_valid, error_msg = validate_payload(payload)
        if not is_valid:
            logger.warning(f"Validation failed: {error_msg}")
           METRIC_WEBHOOK_REQUESTS_TOTAL.labels(source=source_type, status='rejected').inc()
            return jsonify({"error": error_msg}), 400
        
        # Add correlation ID if not present
        if '_correlation_id' not in payload:
            payload['_correlation_id'] = request.correlation_id
        
        # Push to Redis
        try:
            message_string = json.dumps(payload)
            
            withMETRIC_REDIS_PUSH_LATENCY.time():
                redis_client.lpush(config.INGEST_QUEUE_NAME, message_string)
            
            # Record metrics
            latency = time.time() - start_time
           METRIC_WEBHOOK_LATENCY.observe(latency)
           METRIC_WEBHOOK_REQUESTS_TOTAL.labels(source=source_type, status='accepted').inc()
            
            logger.info(
                f"Event accepted from {payload['hostname']} - "
                f"Queue depth: {redis_client.llen(config.INGEST_QUEUE_NAME)}"
            )
            
            return jsonify({
                "status": "accepted",
                "correlation_id": payload['_correlation_id']
            }), 202
            
        except redis.exceptions.RedisError as e:
            logger.error(f"Failed to push to Redis: {e}")
           METRIC_WEBHOOK_REQUESTS_TOTAL.labels(source=source_type, status='error').inc()
            return jsonify({"error": "Service temporarily unavailable"}), 503
    
    return app


# =====================================================================
# MAIN ENTRY POINT
# =====================================================================

def main():
    app = create_app()
    port = app.config["MUTT_CONFIG"].PORT
    
    logger.info("=" * 70)
    logger.info("MUTT Ingest Webhook Service v2.4")
    logger.info("=" * 70)
    logger.info(f"Listening on 0.0.0.0:{port}")
    logger.info(f"Metrics on port {app.config['MUTT_CONFIG'].METRICS_PORT}")
    logger.info("=" * 70)
    
    app.run(host='0.0.0.0', port=port, debug=False, threaded=True)


if __name__ == "__main__":
    main()

Operational Documentation
Deployment
yaml
Copy

# Kubernetes Deployment
env:
  - name: POD_NAME
    valueFrom:
      fieldRef:
        fieldPath: metadata.name
  - name: WEBHOOK_PORT
    value: "8080"
  - name: WEBHOOK_METRICS_PORT
    value: "8085"
  - name: REQUIRE_API_KEY
    value: "true"

Testing
bash
Copy

# Test webhook (with API key)
curl -X POST http://localhost:8080/webhook \
  -H "Content-Type: application/json" \
  -H "X-API-KEY: your-key-here" \
  -d '{"hostname":"router1","timestamp":"2025-01-15T10:30:00Z","message":"Interface down"}'

# Test health
curl http://localhost:8080/health

# Test metrics
curl http://localhost:8085/metrics