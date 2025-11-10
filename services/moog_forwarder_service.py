#!/usr/bin/env python3
if True:
  """
  =====================================================================
  MUTT Moog Forwarder Service (v2.3 - Production Ready)
  =====================================================================
  This service is Component #3 of the MUTT architecture (The "Forwarder").

  It is a long-running worker service that:
  - Pulls alerts from the alert_queue using BRPOPLPUSH
  - Forwards them to Moogsoft via webhook
  - Implements shared rate limiting across all pods
  - Retries failed requests with exponential backoff
  - Moves undeliverable alerts to a dead letter queue

  Key Features (v2.3):
  - Vault integration with background token renewal
  - TLS for Redis
  - Redis-based shared rate limiter (sliding window)
  - BRPOPLPUSH for crash-safe message processing
  - Exponential backoff with configurable max retries
  - Dead letter queue for failed alerts
  - Heartbeat + Janitor pattern for orphan recovery
  - Comprehensive Prometheus metrics
  - Health check HTTP endpoint
  - Graceful shutdown with processing list cleanup
  - Correlation ID tracking

  Author: MUTT Team
  Version: 2.3
  =====================================================================
  """

  import os
  import sys
  import json
  import redis
  import hvac
  import logging
  import signal
  import uuid
  import time
  import threading
  import requests
  from http.server import HTTPServer, BaseHTTPRequestHandler
  from prometheus_client import start_http_server, Counter, Gauge, Histogram
  from typing import Any, Dict, Optional, Tuple
  # Optional DynamicConfig (Phase 1)
  try:
      from dynamic_config import DynamicConfig  # type: ignore
  except Exception:  # pragma: no cover
      DynamicConfig = None
  DYN_CONFIG = None  # type: ignore[var-annotated]

  # Phase 2 Observability (opt-in)
  try:
      from logging_utils import setup_json_logging  # type: ignore
      from tracing_utils import setup_tracing, create_span, set_span_attribute  # type: ignore
  except ImportError:  # pragma: no cover - optional imports
      setup_json_logging = None  # type: ignore
      setup_tracing = None  # type: ignore
      create_span = None  # type: ignore
      set_span_attribute = None  # type: ignore

  # =====================================================================
  # PROMETHEUS METRICS
  # =====================================================================

  METRIC_MOOG_REQUESTS_TOTAL = Counter(
      'mutt_moog_requests_total',
      'Total requests to Moogsoft webhook',
      ['status']  # success, fail_rate_limit, fail_http, fail_retry_exhausted
  )

  METRIC_MOOG_REQUEST_LATENCY = Histogram(
      'mutt_moog_request_latency_seconds',
      'Latency for Moogsoft webhook requests',
      buckets=[0.1, 0.25, 0.5, 1.0, 2.5, 5.0, 10.0, 30.0]
  )

  METRIC_MOOG_DLQ_DEPTH = Gauge(
      'mutt_moog_dlq_depth',
      'Current depth of the Moog dead letter queue'
  )

  METRIC_MOOG_PROCESSING_LIST_DEPTH = Gauge(
      'mutt_moog_processing_list_depth',
      'Current depth of this worker\'s processing list'
  )

  METRIC_MOOG_RATE_LIMIT_HITS = Counter(
      'mutt_moog_rate_limit_hits_total',
      'Total number of times rate limit was hit'
  )

  METRIC_ALERTS_PROCESSED_TOTAL = Counter(
      'mutt_moog_alerts_processed_total',
      'Total alerts processed by the forwarder',
      ['status']  # success, dlq, error
  )

  # =====================================================================
  # LOGGING SETUP
  # =====================================================================

  class CorrelationID:
      """Thread-local storage for correlation IDs."""
      _storage = threading.local()

      @staticmethod
      def set(cid):
          CorrelationID._storage.id = cid

      @staticmethod
      def get():
          return getattr(CorrelationID._storage, 'id', 'system')


  class CorrelationIdFilter(logging.Filter):
      """Automatically adds correlation ID to all log records."""
      def filter(self, record):
          record.correlation_id = CorrelationID.get()
          return True


  # Phase 2: Use JSON logging if available and enabled
  if setup_json_logging is not None:
      logger = setup_json_logging(service_name="moog_forwarder", version="2.3.0")
  else:
      logging.basicConfig(
          level=logging.INFO,
          format='%(asctime)s - %(levelname)s - [%(correlation_id)s] - %(message)s'
      )
      logger = logging.getLogger(__name__)

  # Add correlation ID filter (works with both JSON and text logging)
  logger.addFilter(CorrelationIdFilter())

  # =====================================================================
  # CONSTANTS
  # =====================================================================

  MESSAGE_PREVIEW_LENGTH = 200

  # Lua script for shared rate limiting (sliding window)
  RATE_LIMIT_LUA_SCRIPT = """
  local key = KEYS[1]
  local limit = tonumber(ARGV[1])
  local window = tonumber(ARGV[2])
  local now = tonumber(ARGV[3])

  -- Remove old entries outside the window
  redis.call('ZREMRANGEBYSCORE', key, 0, now - window)

  -- Count current entries in window
  local current = redis.call('ZCARD', key)

  if current < limit then
      -- Add new entry
      redis.call('ZADD', key, now, now .. ':' .. math.random())
      redis.call('EXPIRE', key, window)
      return 1  -- Allowed
  else
      return 0  -- Rate limited
  end
  """

  # =====================================================================
  # CONFIGURATION
  # =====================================================================

  class Config:
      """Service configuration loaded from environment variables."""

      def __init__(self):
          try:
              # Service Identity
              self.POD_NAME = os.environ.get('POD_NAME', f"moog-forwarder-{uuid.uuid4().hex[:6]}")
              self.METRICS_PORT = int(os.environ.get('METRICS_PORT_MOOG', 8083))
              self.HEALTH_PORT = int(os.environ.get('HEALTH_PORT_MOOG', 8084))
              self.LOG_LEVEL = os.environ.get('LOG_LEVEL', 'INFO').upper()
              self.DYNAMIC_CONFIG_ENABLED = os.environ.get('DYNAMIC_CONFIG_ENABLED', 'false').lower() == 'true'

              # Redis Config
              self.REDIS_HOST = os.environ.get('REDIS_HOST', 'localhost')
              self.REDIS_PORT = int(os.environ.get('REDIS_PORT', 6379))
              self.REDIS_TLS_ENABLED = os.environ.get('REDIS_TLS_ENABLED', 'true').lower() == 'true'
              self.REDIS_CA_CERT_PATH = os.environ.get('REDIS_CA_CERT_PATH')
              self.REDIS_MAX_CONNECTIONS = int(os.environ.get('REDIS_MAX_CONNECTIONS', 20))

              # Queue Config
              self.ALERT_QUEUE_NAME = os.environ.get('ALERT_QUEUE_NAME', 'mutt:alert_queue')
              self.MOOG_PROCESSING_LIST_PREFIX = os.environ.get('MOOG_PROCESSING_LIST_PREFIX',
  'mutt:processing:moog')
              self.MOOG_DLQ_NAME = os.environ.get('MOOG_DLQ_NAME', 'mutt:dlq:moog')
              self.BRPOPLPUSH_TIMEOUT = int(os.environ.get('BRPOPLPUSH_TIMEOUT', 5))

              # Heartbeat & Janitor Config
              self.MOOG_HEARTBEAT_PREFIX = os.environ.get('MOOG_HEARTBEAT_PREFIX', 'mutt:heartbeat:moog')
              self.MOOG_HEARTBEAT_INTERVAL = int(os.environ.get('MOOG_HEARTBEAT_INTERVAL', 10))
              self.MOOG_JANITOR_TIMEOUT = int(os.environ.get('MOOG_JANITOR_TIMEOUT', 30))

              # Moogsoft Config
              self.MOOG_WEBHOOK_URL = os.environ.get('MOOG_WEBHOOK_URL',
  'https://moogsoft.example.com/api/v1/events')
              self.MOOG_WEBHOOK_TIMEOUT = int(os.environ.get('MOOG_WEBHOOK_TIMEOUT', 10))

              # Rate Limiting Config (shared across all pods)
              self.MOOG_RATE_LIMIT = int(os.environ.get('MOOG_RATE_LIMIT', 50))  # Max requests
              self.MOOG_RATE_PERIOD = int(os.environ.get('MOOG_RATE_PERIOD', 1))  # Per N seconds
              self.MOOG_RATE_LIMIT_KEY = os.environ.get('MOOG_RATE_LIMIT_KEY', 'mutt:rate_limit:moog')

              # Retry Config
              self.MOOG_MAX_RETRIES = int(os.environ.get('MOOG_MAX_RETRIES', 5))
              self.MOOG_RETRY_BASE_DELAY = float(os.environ.get('MOOG_RETRY_BASE_DELAY', 1.0))  # 1 second
              self.MOOG_RETRY_MAX_DELAY = float(os.environ.get('MOOG_RETRY_MAX_DELAY', 60.0))  # 60 seconds

              # Vault Config
              self.VAULT_ADDR = os.environ.get('VAULT_ADDR')
              self.VAULT_ROLE_ID = os.environ.get('VAULT_ROLE_ID')
              self.VAULT_SECRET_ID_FILE = os.environ.get('VAULT_SECRET_ID_FILE',
  '/etc/mutt/secrets/vault_secret_id')
              self.VAULT_SECRETS_PATH = os.environ.get('VAULT_SECRETS_PATH', 'secret/mutt')
              self.VAULT_TOKEN_RENEW_THRESHOLD = int(os.environ.get('VAULT_TOKEN_RENEW_THRESHOLD', 3600))
              self.VAULT_RENEW_CHECK_INTERVAL = int(os.environ.get('VAULT_RENEW_CHECK_INTERVAL', 300))

              # Validate
              self._validate()

          except Exception as e:
              logger.error(f"FATAL: Configuration error: {e}")
              sys.exit(1)

      def _validate(self):
          """Validate critical configuration values."""
          if not self.VAULT_ADDR:
              raise ValueError("VAULT_ADDR is required but not set")
          if not self.VAULT_ROLE_ID:
              raise ValueError("VAULT_ROLE_ID is required but not set")
          if not self.MOOG_WEBHOOK_URL:
              raise ValueError("MOOG_WEBHOOK_URL is required but not set")

          if self.METRICS_PORT < 1 or self.METRICS_PORT > 65535:
              raise ValueError(f"METRICS_PORT invalid: {self.METRICS_PORT}")

          if self.HEALTH_PORT < 1 or self.HEALTH_PORT > 65535:
              raise ValueError(f"HEALTH_PORT invalid: {self.HEALTH_PORT}")

          if self.MOOG_RATE_LIMIT < 1:
              raise ValueError(f"MOOG_RATE_LIMIT too low: {self.MOOG_RATE_LIMIT}")

          if self.MOOG_MAX_RETRIES < 0:
              raise ValueError(f"MOOG_MAX_RETRIES cannot be negative: {self.MOOG_MAX_RETRIES}")

          logger.setLevel(self.LOG_LEVEL)
          logger.info(f"Configuration validated for worker: {self.POD_NAME}")

  # =====================================================================
  # DYNAMIC CONFIG HELPERS (optional)
  # =====================================================================

  def _init_dynamic_config_if_enabled(config: "Config", redis_client: redis.Redis) -> None:
      """Initialize DynamicConfig watcher if enabled and available."""
      global DYN_CONFIG  # noqa: PLW0603
      if not getattr(config, 'DYNAMIC_CONFIG_ENABLED', False):
          return
      if DynamicConfig is None:
          logger.warning("DynamicConfig not available; skipping init")
          return
      try:
          dyn = DynamicConfig(redis_client, prefix="mutt:config")
          dyn.start_watcher()
          DYN_CONFIG = dyn
          logger.info("Dynamic configuration initialized for Moog Forwarder")
      except Exception as e:
          logger.error(f"Failed to initialize DynamicConfig: {e}")


  def _dyn_get_int(key: str, fallback: int) -> int:
      try:
          if DYN_CONFIG:
              v = DYN_CONFIG.get(key, default=str(fallback))
              return int(v)
      except Exception as e:  # pragma: no cover
          logger.debug(f"DynamicConfig get failed for {key}: {e}")
      return fallback


  def _get_moog_rate_limit(config: "Config") -> int:
      return _dyn_get_int('moog_rate_limit', config.MOOG_RATE_LIMIT)


  def _get_moog_rate_period(config: "Config") -> int:
      return _dyn_get_int('moog_rate_period', config.MOOG_RATE_PERIOD)

  # =====================================================================
  # VAULT SECRET MANAGEMENT
  # =====================================================================

def fetch_secrets(config: "Config") -> Tuple[Any, Dict[str, str]]:
    """Connects to Vault and fetches secrets."""
      try:
          logger.info(f"Connecting to Vault at {config.VAULT_ADDR}...")
          vault_client = hvac.Client(url=config.VAULT_ADDR)

          if not os.path.exists(config.VAULT_SECRET_ID_FILE):
              raise FileNotFoundError(f"Vault secret ID file not found: {config.VAULT_SECRET_ID_FILE}")

          with open(config.VAULT_SECRET_ID_FILE, 'r') as f:
              secret_id = f.read().strip()

          if not secret_id:
              raise ValueError("Vault secret ID file is empty")

          auth_response = vault_client.auth.approle.login(
              role_id=config.VAULT_ROLE_ID,
              secret_id=secret_id
          )

          if not vault_client.is_authenticated():
              raise Exception("Vault authentication failed.")

          logger.info("Successfully authenticated to Vault")
          logger.info(f"Token TTL: {auth_response['auth']['lease_duration']}s")

          response = vault_client.secrets.kv.v2.read_secret_version(
              path=config.VAULT_SECRETS_PATH
          )
          data = response['data']['data']

          secrets = {
              "REDIS_PASS": data.get('REDIS_PASS'),
              "MOOG_API_KEY": data.get('MOOG_API_KEY')
          }

          # Validate required secrets
          if not secrets["REDIS_PASS"]:
              raise ValueError("REDIS_PASS not found in Vault")
          if not secrets["MOOG_API_KEY"]:
              raise ValueError("MOOG_API_KEY not found in Vault")

          logger.info("Successfully loaded secrets from Vault")
          return vault_client, secrets

      except Exception as e:
          logger.error(f"FATAL: Failed to fetch secrets from Vault: {e}")
          sys.exit(1)


def start_vault_token_renewal(config: "Config", vault_client: Any, stop_event: threading.Event) -> threading.Thread:
    """Starts a background daemon thread for Vault token renewal."""

      def renewal_loop():
          logger.info("Vault token renewal thread started")
          while not stop_event.is_set():
              try:
                  stop_event.wait(config.VAULT_RENEW_CHECK_INTERVAL)
                  if stop_event.is_set():
                      break

                  token_info = vault_client.auth.token.lookup_self()['data']
                  ttl = token_info['ttl']
                  renewable = token_info.get('renewable', False)

                  logger.debug(f"Vault token TTL: {ttl}s, Renewable: {renewable}")

                  if renewable and ttl < config.VAULT_TOKEN_RENEW_THRESHOLD:
                      logger.info(f"Renewing Vault token (TTL: {ttl}s)...")
                      renew_response = vault_client.auth.token.renew_self()
                      new_ttl = renew_response['auth']['lease_duration']
                      logger.info(f"Vault token renewed. New TTL: {new_ttl}s")
                  elif not renewable and ttl < config.VAULT_TOKEN_RENEW_THRESHOLD:
                      logger.warning(
                          f"Vault token is not renewable and has {ttl}s remaining! "
                          "Service restart needed."
                      )

              except Exception as e:
                  logger.error(f"Error in Vault token renewal: {e}")

          logger.info("Vault token renewal thread stopped")

      thread = threading.Thread(target=renewal_loop, daemon=True, name="VaultTokenRenewal")
      thread.start()
      return thread

  # =====================================================================
  # REDIS CONNECTION
  # =====================================================================

  from redis_connector import get_redis_pool  # type: ignore

  def connect_to_redis(config: "Config", secrets: Dict[str, str]) -> redis.Redis:
      """Connects to Redis with TLS and connection pooling (dual-password aware)."""
      logger.info(f"Connecting to Redis at {config.REDIS_HOST}:{config.REDIS_PORT}...")

      try:
          pool = get_redis_pool(
              host=config.REDIS_HOST,
              port=config.REDIS_PORT,
              tls_enabled=config.REDIS_TLS_ENABLED,
              ca_cert_path=config.REDIS_CA_CERT_PATH,
              password_current=secrets.get('REDIS_PASS_CURRENT') or secrets.get('REDIS_PASS'),
              password_next=secrets.get('REDIS_PASS_NEXT'),
              max_connections=config.REDIS_MAX_CONNECTIONS,
              logger=logger,
          )
          r = redis.Redis(connection_pool=pool)
          r.ping()
          logger.info("Successfully connected to Redis (dual-password aware)")
          return r

      except Exception as e:
          logger.error(f"FATAL: Could not connect to Redis: {e}")
          sys.exit(1)

  # =====================================================================
  # HEARTBEAT & JANITOR
  # =====================================================================

def start_heartbeat(config: "Config", redis_client: redis.Redis, stop_event: threading.Event) -> threading.Thread:
      """Starts a thread to periodically update this worker's heartbeat."""

      def heartbeat_loop():
          heartbeat_key = f"{config.MOOG_HEARTBEAT_PREFIX}:{config.POD_NAME}"
          interval = config.MOOG_HEARTBEAT_INTERVAL
          logger.info(f"Heartbeat thread started. Updating {heartbeat_key} every {interval}s.")

          while not stop_event.wait(interval):
              try:
                  redis_client.setex(heartbeat_key, config.MOOG_JANITOR_TIMEOUT, "alive")
              except redis.exceptions.RedisError as e:
                  logger.error(f"Failed to send heartbeat: {e}")

          logger.info("Heartbeat thread stopped.")

      thread = threading.Thread(target=heartbeat_loop, daemon=True, name="Heartbeat")
      thread.start()
      return thread


def run_janitor(config: "Config", redis_client: redis.Redis) -> None:
      """
      Recovers orphaned messages from dead workers on startup.
      Uses SCAN instead of KEYS for production safety.
      """
      logger.info("Running janitor process to recover orphaned messages...")
      processing_prefix = config.MOOG_PROCESSING_LIST_PREFIX
      heartbeat_prefix = config.MOOG_HEARTBEAT_PREFIX

      try:
          # Find all active processing lists using SCAN
          processing_lists = []
          cursor = 0

          while True:
              cursor, keys = redis_client.scan(
                  cursor,
                  match=f"{processing_prefix}:*",
                  count=100
              )
              processing_lists.extend(keys)
              if cursor == 0:
                  break

          logger.info(f"Found {len(processing_lists)} processing lists to check")
          recovered_count = 0

          for p_list in processing_lists:
              # Extract pod name from list key
              pod_name = p_list.split(':')[-1]
              heartbeat_key = f"{heartbeat_prefix}:{pod_name}"

              # Check if the worker is alive
              if not redis_client.exists(heartbeat_key):
                  # Worker is dead, recover its messages
                  logger.warning(f"Worker '{pod_name}' is dead. Recovering messages from {p_list}...")

                  list_len = redis_client.llen(p_list)

                  # Atomically move all messages back to alert queue
                  moved = 0
                  while True:
                      msg = redis_client.rpoplpush(p_list, config.ALERT_QUEUE_NAME)
                      if msg is None:
                          break
                      moved += 1
                      recovered_count += 1

                  logger.info(f"Recovered {moved} messages from {p_list} (expected: {list_len})")

          logger.info(f"Janitor process finished. Total recovered: {recovered_count}")

      except redis.exceptions.RedisError as e:
          logger.error(f"Janitor process failed: {e}")
      except Exception as e:
          logger.error(f"Unhandled Janitor error: {e}", exc_info=True)

  # =====================================================================
  # RATE LIMITING
  # =====================================================================

  def check_rate_limit(redis_client: redis.Redis, config: "Config") -> bool:
      """
      Check if we're within rate limit using Redis sliding window.
      Returns True if allowed, False if rate limited.
      """
      try:
          now = int(time.time() * 1000)  # Milliseconds
          window_ms = _get_moog_rate_period(config) * 1000

          allowed = redis_client.eval(
              RATE_LIMIT_LUA_SCRIPT,
              1,  # Number of keys
              config.MOOG_RATE_LIMIT_KEY,
              _get_moog_rate_limit(config),
              window_ms,
              now
          )

          if allowed == 0:
              METRIC_MOOG_RATE_LIMIT_HITS.inc()
              return False

          return True

      except Exception as e:
          logger.error(f"Error checking rate limit: {e}")
          # On error, allow the request (fail open)
          return True

  # =====================================================================
  # MOOG WEBHOOK
  # =====================================================================

def send_to_moog(alert_data: Dict[str, Any], config: "Config", secrets: Dict[str, str]) -> Tuple[bool, bool, str]:
      """
      Sends an alert to Moogsoft webhook.

      Returns:
          (success: bool, should_retry: bool, error_message: str)
      """
      correlation_id = alert_data.get('_correlation_id', 'unknown')
      CorrelationID.set(correlation_id)

      try:
          # Build Moog payload
          payload = {
              "signature": alert_data.get('hostname', 'unknown'),
              "source_id": alert_data.get('hostname', 'unknown'),
              "external_id": correlation_id,
              "manager": "MUTT",
              "source": "MUTT Alerter",
              "class": alert_data.get('team_assignment', 'Unknown'),
              "agent": "MUTT v2.3",
              "agent_location": "Alerter Service",
              "type": "Alert",
              "severity": _map_severity(alert_data.get('severity', 'Warning')),
              "description": alert_data.get('message_body', ''),
              "agent_time": int(time.time())
          }

          # Add custom fields
          if 'raw_json' in alert_data:
              payload['custom_info'] = alert_data['raw_json']

          headers = {
              'Content-Type': 'application/json',
              'Authorization': f"Bearer {secrets['MOOG_API_KEY']}"
          }

          # Send request with latency tracking
          start_time = time.time()

          response = requests.post(
              config.MOOG_WEBHOOK_URL,
              json=payload,
              headers=headers,
              timeout=config.MOOG_WEBHOOK_TIMEOUT,
              verify=True  # Verify SSL certificates
          )

          latency = time.time() - start_time
          METRIC_MOOG_REQUEST_LATENCY.observe(latency)

          # Check response
          if response.status_code == 200 or response.status_code == 201:
              logger.info(f"Successfully sent alert to Moog (latency: {latency:.2f}s)")
              METRIC_MOOG_REQUESTS_TOTAL.labels(status='success').inc()
              return (True, False, None)

          elif response.status_code == 429:
              # Rate limited by Moog (shouldn't happen with our rate limiter)
              logger.warning(f"Moog rate limited us (429). Status: {response.status_code}")
              METRIC_MOOG_REQUESTS_TOTAL.labels(status='fail_rate_limit').inc()
              return (False, True, f"Moog rate limit: {response.status_code}")

          elif response.status_code >= 500:
              # Server error - retry
              logger.error(f"Moog server error: {response.status_code} - {response.text[:200]}")
              METRIC_MOOG_REQUESTS_TOTAL.labels(status='fail_http').inc()
              return (False, True, f"Moog server error: {response.status_code}")

          else:
              # Client error (4xx) - don't retry
              logger.error(f"Moog client error: {response.status_code} - {response.text[:200]}")
              METRIC_MOOG_REQUESTS_TOTAL.labels(status='fail_http').inc()
              return (False, False, f"Moog client error: {response.status_code}")

      except requests.exceptions.Timeout:
          logger.error(f"Moog request timeout after {config.MOOG_WEBHOOK_TIMEOUT}s")
          METRIC_MOOG_REQUESTS_TOTAL.labels(status='fail_http').inc()
          return (False, True, "Timeout")

      except requests.exceptions.ConnectionError as e:
          logger.error(f"Moog connection error: {e}")
          METRIC_MOOG_REQUESTS_TOTAL.labels(status='fail_http').inc()
          return (False, True, f"Connection error: {e}")

      except Exception as e:
          logger.error(f"Unexpected error sending to Moog: {e}", exc_info=True)
          METRIC_MOOG_REQUESTS_TOTAL.labels(status='fail_http').inc()
          return (False, True, f"Unexpected error: {e}")


def _map_severity(severity_str: str) -> int:
      """Map MUTT severity to Moog severity (0-5)."""
      severity_map = {
          'Critical': 5,
          'Major': 4,
          'Warning': 3,
          'Minor': 2,
          'Info': 1,
          'Clear': 0
      }
      return severity_map.get(severity_str, 3)  # Default to Warning

  # =====================================================================
  # CORE PROCESSING LOGIC
  # =====================================================================

  def process_alert(alert_string: str, config: "Config", secrets: Dict[str, str], redis_client: redis.Redis) -> Optional[str]:
      """
      Process a single alert from the queue.

      Returns:
          - alert_string if successful (to LREM from processing list)
          - None if failed and re-queued or sent to DLQ
      """
      try:
          alert_data = json.loads(alert_string)
      except json.JSONDecodeError:
          logger.error(f"Invalid JSON in alert queue, discarding: {alert_string[:MESSAGE_PREVIEW_LENGTH]}")
          METRIC_ALERTS_PROCESSED_TOTAL.labels(status='error').inc()
          return None  # Discard malformed JSON

      # Set correlation ID
      correlation_id = alert_data.get('_correlation_id', 'unknown')
      CorrelationID.set(correlation_id)

      # Get retry count
      retry_count = alert_data.get('_moog_retry_count', 0)

      # --- Check if we've exhausted retries ---
      if retry_count > config.MOOG_MAX_RETRIES:
          logger.error(
              f"Max retries ({config.MOOG_MAX_RETRIES}) exceeded for alert. "
              f"Moving to DLQ: {alert_string[:MESSAGE_PREVIEW_LENGTH]}"
          )
          try:
              redis_client.lpush(config.MOOG_DLQ_NAME, alert_string)
              METRIC_MOOG_REQUESTS_TOTAL.labels(status='fail_retry_exhausted').inc()
              METRIC_ALERTS_PROCESSED_TOTAL.labels(status='dlq').inc()

              # Update DLQ depth metric
              dlq_depth = redis_client.llen(config.MOOG_DLQ_NAME)
              METRIC_MOOG_DLQ_DEPTH.set(dlq_depth)

          except redis.exceptions.RedisError as e:
              logger.error(f"Failed to push to DLQ: {e}")
              # Re-queue to alert queue to avoid data loss
              redis_client.lpush(config.ALERT_QUEUE_NAME, alert_string)

          return None  # Done with this message

      # --- Check rate limit ---
      if not check_rate_limit(redis_client, config):
          logger.debug(f"Rate limit hit. Returning alert to queue for retry.")
          # Don't increment retry count for rate limiting
          # Just return None so it stays in processing list and we'll retry next loop
          return None

      # --- Send to Moog ---
      success, should_retry, error_msg = send_to_moog(alert_data, config, secrets)

      if success:
          # Success! Remove from processing list
          METRIC_ALERTS_PROCESSED_TOTAL.labels(status='success').inc()
          return alert_string

      else:
          # Failed
          if should_retry:
              # Increment retry count and re-queue
              alert_data['_moog_retry_count'] = retry_count + 1

              # Calculate exponential backoff delay
              delay = min(
                  config.MOOG_RETRY_BASE_DELAY * (2 ** retry_count),
                  config.MOOG_RETRY_MAX_DELAY
              )

              logger.warning(
                  f"Alert delivery failed (attempt {retry_count + 1}/{config.MOOG_MAX_RETRIES}). "
                  f"Will retry after {delay:.1f}s. Error: {error_msg}"
              )

              # Sleep before re-queuing
              time.sleep(delay)

              # Re-queue to alert queue
              new_alert_string = json.dumps(alert_data)
              redis_client.lpush(config.ALERT_QUEUE_NAME, new_alert_string)

              METRIC_ALERTS_PROCESSED_TOTAL.labels(status='error').inc()
              return None  # Remove from processing list

          else:
              # Don't retry (client error), send to DLQ
              logger.error(f"Alert delivery failed with non-retryable error. Moving to DLQ. Error: {error_msg}")

              try:
                  redis_client.lpush(config.MOOG_DLQ_NAME, alert_string)
                  METRIC_ALERTS_PROCESSED_TOTAL.labels(status='dlq').inc()

                  dlq_depth = redis_client.llen(config.MOOG_DLQ_NAME)
                  METRIC_MOOG_DLQ_DEPTH.set(dlq_depth)

              except redis.exceptions.RedisError as e:
                  logger.error(f"Failed to push to DLQ: {e}")

              return None

  # =====================================================================
  # HEALTH CHECK HTTP SERVER
  # =====================================================================

  class HealthCheckHandler(BaseHTTPRequestHandler):
      """Simple HTTP handler for health checks."""

      health_check_fn = None

      def do_GET(self):
          if self.path == '/health':
              try:
                  is_healthy, status_code, response = self.health_check_fn()

                  self.send_response(status_code)
                  self.send_header('Content-Type', 'application/json')
                  self.end_headers()
                  self.wfile.write(json.dumps(response).encode())

              except Exception as e:
                  self.send_response(503)
                  self.send_header('Content-Type', 'application/json')
                  self.end_headers()
                  self.wfile.write(json.dumps({
                      "status": "unhealthy",
                      "error": str(e)
                  }).encode())
          else:
              self.send_response(404)
              self.end_headers()

      def log_message(self, format, *args):
          pass  # Suppress default logging


  def start_health_server(config, redis_client):
      """Starts HTTP health check server in background thread."""

      def health_check():
          """Health check logic."""
          errors = []

          # Check Redis
          try:
              redis_client.ping()
          except Exception as e:
              errors.append(f"Redis: {e}")

          # Check Moog webhook reachability (HEAD request)
          try:
              response = requests.head(config.MOOG_WEBHOOK_URL, timeout=2)
          except Exception as e:
              errors.append(f"Moog webhook: {e}")

          if errors:
              return False, 503, {
                  "status": "unhealthy",
                  "service": "mutt-moog-forwarder",
                  "version": "2.3",
                  "pod": config.POD_NAME,
                  "errors": errors
              }
          else:
              return True, 200, {
                  "status": "healthy",
                  "service": "mutt-moog-forwarder",
                  "version": "2.3",
                  "pod": config.POD_NAME
              }

      HealthCheckHandler.health_check_fn = health_check

      def run_server():
          server = HTTPServer(('0.0.0.0', config.HEALTH_PORT), HealthCheckHandler)
          logger.info(f"Health check server started on port {config.HEALTH_PORT}")
          server.serve_forever()

      thread = threading.Thread(target=run_server, daemon=True, name="HealthCheckServer")
      thread.start()
      return thread

  # =====================================================================
  # GRACEFUL SHUTDOWN
  # =====================================================================

  def cleanup_processing_list(config, redis_client):
      """Move messages from our processing list back to alert queue."""
      processing_list = f"{config.MOOG_PROCESSING_LIST_PREFIX}:{config.POD_NAME}"

      try:
          logger.info(f"Cleaning up processing list: {processing_list}")

          moved = 0
          while True:
              msg = redis_client.rpoplpush(processing_list, config.ALERT_QUEUE_NAME)
              if msg is None:
                  break
              moved += 1

          logger.info(f"Moved {moved} messages from processing list back to alert queue")

      except Exception as e:
          logger.error(f"Error cleaning up processing list: {e}")


  def reconnect_with_backoff(connect_fn, max_retries=10):
      """Reconnect to a service with exponential backoff."""
      retry_count = 0

      while retry_count < max_retries:
          try:
              return connect_fn()
          except Exception as e:
              retry_count += 1
              if retry_count >= max_retries:
                  logger.error(f"Max reconnection attempts ({max_retries}) reached. Giving up.")
                  raise

              wait_time = min(2 ** retry_count, 60)
              logger.error(
                  f"Reconnection attempt {retry_count}/{max_retries} failed: {e}. "
                  f"Waiting {wait_time}s..."
              )
              time.sleep(wait_time)

  # =====================================================================
  # MAIN SERVICE LOOP
  # =====================================================================

  def main():
      """Main service entry point."""

      # --- 1. Load Config, Secrets, and Connections ---
      config = Config()

      # Phase 2: Setup distributed tracing if enabled
      if setup_tracing is not None:
          setup_tracing(service_name="moog_forwarder", version="2.3.0")

      vault_client, secrets = fetch_secrets(config)
      redis_client = connect_to_redis(config, secrets)

      # --- 2. Start Background Services ---
      stop_event = threading.Event()

      # Start Vault renewal
      vault_thread = start_vault_token_renewal(config, vault_client, stop_event)

      # Start Prometheus metrics server
      start_http_server(config.METRICS_PORT)
      logger.info(f"Prometheus metrics server started on port {config.METRICS_PORT}")

      # Start health check server
      health_thread = start_health_server(config, redis_client)

      # Start heartbeat
      heartbeat_thread = start_heartbeat(config, redis_client, stop_event)

      # --- 3. Run Janitor ---
      run_janitor(config, redis_client)

      # --- 4. Register Signal Handlers ---
      def graceful_shutdown(signum, frame):
          sig_name = 'SIGTERM' if signum == signal.SIGTERM else 'SIGINT'
          logger.warning(f"{sig_name} received. Initiating graceful shutdown...")

          # Stop all background threads
          stop_event.set()

          # Clean up our processing list
          cleanup_processing_list(config, redis_client)

          logger.info("Shutdown complete. Exiting.")
          sys.exit(0)

      signal.signal(signal.SIGTERM, graceful_shutdown)
      signal.signal(signal.SIGINT, graceful_shutdown)

      # --- 5. Main Processing Loop ---
      logger.info("=" * 70)
      logger.info(f"MUTT Moog Forwarder Service v2.3 - Pod: {config.POD_NAME}")
      logger.info("=" * 70)
      logger.info(f"Moog Webhook: {config.MOOG_WEBHOOK_URL}")
      logger.info(f"Rate Limit: {config.MOOG_RATE_LIMIT} requests per {config.MOOG_RATE_PERIOD}s")
      logger.info(f"Max Retries: {config.MOOG_MAX_RETRIES}")
      logger.info("=" * 70)
      logger.info("Service is now running. Waiting for alerts...")

      processing_list = f"{config.MOOG_PROCESSING_LIST_PREFIX}:{config.POD_NAME}"

      while not stop_event.is_set():
          alert_string = None
          try:
              # --- Atomically pop from alert queue and push to our processing list ---
              alert_string = redis_client.brpoplpush(
                  config.ALERT_QUEUE_NAME,
                  processing_list,
                  timeout=config.BRPOPLPUSH_TIMEOUT
              )

              if alert_string is None:
                  # Timeout, update metrics and loop again
                  try:
                      processing_depth = redis_client.llen(processing_list)
                      METRIC_MOOG_PROCESSING_LIST_DEPTH.set(processing_depth)
                  except:
                      pass
                  continue

              # --- Process the alert ---
              # Phase 2: Wrap processing in a span for distributed tracing
              span_func = create_span if create_span is not None else None
              if span_func:
                  with span_func(
                      "forward_alert_to_moog",
                      attributes={
                          "queue.name": config.ALERT_QUEUE_NAME,
                          "service.instance": config.POD_NAME,
                          "destination": config.MOOG_WEBHOOK_URL,
                      }
                  ):
                      result = process_alert(alert_string, config, secrets, redis_client)
              else:
                  result = process_alert(alert_string, config, secrets, redis_client)

              # --- Clean up the processing list ---
              if result is not None:
                  # Success. Remove the message from our processing list.
                  redis_client.lrem(processing_list, 1, alert_string)
              else:
                  # Failure (re-queued, DLQ, or rate limited).
                  # process_alert() already handled re-queueing/DLQ.
                  # Remove from processing list.
                  redis_client.lrem(processing_list, 1, alert_string)

              # Update processing list depth metric
              try:
                  processing_depth = redis_client.llen(processing_list)
                  METRIC_MOOG_PROCESSING_LIST_DEPTH.set(processing_depth)
              except:
                  pass

          except redis.exceptions.ConnectionError as e:
              logger.error(f"Redis connection lost! Reconnecting... {e}")
              try:
                  redis_client = reconnect_with_backoff(
                      lambda: connect_to_redis(config, secrets)
                  )
              except Exception as reconnect_error:
                  logger.error(f"Failed to reconnect to Redis: {reconnect_error}")
                  logger.error("Exiting service - requires manual intervention")
                  sys.exit(1)

          except Exception as e:
              logger.error(f"CRITICAL: Unhandled error in main loop: {e}", exc_info=True)
              if alert_string:
                  logger.error(f"Last alert: {alert_string[:MESSAGE_PREVIEW_LENGTH]}")
              # Don't LREM. Let the janitor recover it.
              time.sleep(1)

  # =====================================================================
  # SERVICE ENTRY POINT
  # =====================================================================

  if __name__ == "__main__":
      main()

  ---
  Key Features of Moog Forwarder v2.3

  ✅ Reliability

  1. ✅ BRPOPLPUSH for crash-safe message processing
  2. ✅ Heartbeat + Janitor pattern for orphan recovery
  3. ✅ Exponential backoff with configurable max retries
  4. ✅ Dead letter queue for failed alerts
  5. ✅ Graceful shutdown with processing list cleanup

  ✅ Rate Limiting

  6. ✅ Shared rate limiter using Redis (Lua script with sliding window)
  7. ✅ Coordinates across all pods to respect global limit
  8. ✅ Configurable: MOOG_RATE_LIMIT requests per MOOG_RATE_PERIOD seconds

  ✅ Production Ready

  9. ✅ Vault integration with background token renewal
  10. ✅ Redis connection pooling with TLS
  11. ✅ Health check HTTP endpoint (:8084/health)
  12. ✅ Comprehensive Prometheus metrics
  13. ✅ Correlation ID tracking
  14. ✅ SCAN instead of KEYS for janitor

  ✅ Smart Retry Logic

  15. ✅ Retries on server errors (5xx), timeouts, connection errors
  16. ✅ No retry on client errors (4xx) - straight to DLQ
  17. ✅ Exponential backoff: 1s → 2s → 4s → 8s → 16s → 32s → 60s (max)
  18. ✅ Sleep between retries to avoid hammering Moog

  ---
  Environment Variables

  # Service Identity
  POD_NAME=moog-forwarder-pod-1
  METRICS_PORT_MOOG=8083
  HEALTH_PORT_MOOG=8084

  # Redis
  REDIS_HOST=redis.prod.svc
  REDIS_PORT=6379
  REDIS_TLS_ENABLED=true
  REDIS_CA_CERT_PATH=/etc/mutt/certs/redis-ca.pem

  # Moogsoft
  MOOG_WEBHOOK_URL=https://moogsoft.example.com/api/v1/events
  MOOG_WEBHOOK_TIMEOUT=10

  # Rate Limiting (shared across all pods)
  MOOG_RATE_LIMIT=50          # Max 50 requests
  MOOG_RATE_PERIOD=1          # Per 1 second
  MOOG_RATE_LIMIT_KEY=mutt:rate_limit:moog

  # Retry Config
  MOOG_MAX_RETRIES=5
  MOOG_RETRY_BASE_DELAY=1.0   # 1 second
  MOOG_RETRY_MAX_DELAY=60.0   # 60 seconds max

  # Vault
  VAULT_ADDR=https://vault.prod.svc:8200
  VAULT_ROLE_ID=mutt-moog-forwarder-role
  VAULT_SECRET_ID_FILE=/etc/mutt/secrets/vault_secret_id
  VAULT_SECRETS_PATH=secret/mutt

  ---
  Prometheus Metrics

  - mutt_moog_requests_total{status} - Total requests to Moog (success/fail_*)
  - mutt_moog_request_latency_seconds - Webhook latency
  - mutt_moog_dlq_depth - Dead letter queue depth
  - mutt_moog_processing_list_depth - This worker's processing list depth
  - mutt_moog_rate_limit_hits_total - Times rate limit was hit
  - mutt_moog_alerts_processed_total{status} - Alerts processed (success/dlq/error)

  ---
  Production Deployment

  # Run as systemd service or in Kubernetes
  python moog_forwarder_service.py

  # Check health
  curl http://localhost:8084/health

  # Check metrics
  curl http://localhost:8083/metrics | grep mutt_moog

  # Graceful shutdown
  kill -TERM <pid>

  All 4 MUTT services are now complete and production-ready! 🚀
