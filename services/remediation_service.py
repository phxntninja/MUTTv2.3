#!/usr/bin/env python3
"""
=====================================================================
MUTT Remediation Service (Phase 3.2)
=====================================================================
Self-healing service that automatically remediates common failures:
- Replays messages from DLQ when conditions are favorable
- Checks Moogsoft health before replay
- Prevents poison message loops with retry count tracking

Key Features:
- Long-running service with configurable interval
- Poison message protection (moves to dead letter after max retries)
- Moogsoft health checking
- Comprehensive metrics and logging
- Graceful shutdown support

Author: MUTT Team
Version: 2.5
=====================================================================
"""

import os
import sys
import json
import redis
import logging
import signal
import time
import threading
import requests
from typing import Optional, Tuple, Dict, Any
from datetime import datetime, timezone
from prometheus_client import Counter, Gauge, Histogram, start_http_server

# Phase 2: Optional observability imports
try:
    from logging_utils import setup_json_logging
except ImportError:
    setup_json_logging = None

try:
    from tracing_utils import setup_tracing, create_span
except ImportError:
    setup_tracing = None
    create_span = None

# Optional DynamicConfig
try:
    from dynamic_config import DynamicConfig
    DYN_CONFIG = None  # Will be initialized in main()
except ImportError:
    DynamicConfig = None
    DYN_CONFIG = None

# =====================================================================
# LOGGING SETUP
# =====================================================================

logger = logging.getLogger(__name__)

# =====================================================================
# PROMETHEUS METRICS
# =====================================================================

METRIC_REMEDIATION_LOOPS = Counter(
    'mutt_remediation_loops_total',
    'Total remediation loops executed'
)

METRIC_DLQ_DEPTH = Gauge(
    'mutt_remediation_dlq_depth',
    'Current depth of DLQ being monitored',
    ['dlq_name']
)

METRIC_REPLAY_SUCCESS = Counter(
    'mutt_remediation_replay_success_total',
    'Total messages successfully replayed from DLQ'
)

METRIC_REPLAY_FAIL = Counter(
    'mutt_remediation_replay_fail_total',
    'Total messages that failed to replay',
    ['reason']
)

METRIC_POISON_MESSAGES = Counter(
    'mutt_remediation_poison_messages_total',
    'Total poison messages moved to dead letter'
)

METRIC_MOOG_HEALTH_CHECK = Gauge(
    'mutt_remediation_moog_health',
    'Moogsoft health status (1=healthy, 0=unhealthy)'
)

METRIC_REMEDIATION_DURATION = Histogram(
    'mutt_remediation_loop_duration_seconds',
    'Time spent in remediation loop'
)

# =====================================================================
# CONFIGURATION
# =====================================================================

class Config:
    """Remediation service configuration."""

    def __init__(self):
        # Service identity
        self.POD_NAME = os.environ.get('POD_NAME', 'remediation-unknown')
        self.METRICS_PORT = int(os.environ.get('METRICS_PORT_REMEDIATION', 8086))
        self.HEALTH_PORT = int(os.environ.get('HEALTH_PORT_REMEDIATION', 8087))
        self.LOG_LEVEL = os.environ.get('LOG_LEVEL', 'INFO').upper()

        # Redis config
        self.REDIS_HOST = os.environ.get('REDIS_HOST', 'localhost')
        self.REDIS_PORT = int(os.environ.get('REDIS_PORT', 6379))
        self.REDIS_DB = int(os.environ.get('REDIS_DB', 0))

        # DLQ config
        self.ALERTER_DLQ_NAME = os.environ.get('ALERTER_DLQ_NAME', 'mutt:dlq:alerter')
        self.ALERTER_QUEUE_NAME = os.environ.get('INGEST_QUEUE_NAME', 'mutt:ingest_queue')
        self.DEAD_LETTER_QUEUE = os.environ.get('DEAD_LETTER_QUEUE', 'mutt:dlq:dead')

        # Remediation config
        self.REMEDIATION_ENABLED = os.environ.get('REMEDIATION_ENABLED', 'true').lower() == 'true'
        self.REMEDIATION_INTERVAL = int(os.environ.get('REMEDIATION_INTERVAL', 300))  # 5 minutes
        self.REMEDIATION_BATCH_SIZE = int(os.environ.get('REMEDIATION_BATCH_SIZE', 10))
        self.MAX_POISON_RETRIES = int(os.environ.get('MAX_POISON_RETRIES', 3))

        # Moogsoft health check config
        self.MOOG_HEALTH_CHECK_ENABLED = os.environ.get('MOOG_HEALTH_CHECK_ENABLED', 'true').lower() == 'true'
        self.MOOG_WEBHOOK_URL = os.environ.get('MOOG_WEBHOOK_URL', '')
        self.MOOG_HEALTH_TIMEOUT = int(os.environ.get('MOOG_HEALTH_TIMEOUT', 5))

        # Dynamic config support
        self.DYNAMIC_CONFIG_ENABLED = os.environ.get('DYNAMIC_CONFIG_ENABLED', 'false').lower() == 'true'


def _init_dynamic_config(config: Config, redis_client: redis.Redis) -> None:
    """Initialize dynamic configuration if enabled."""
    global DYN_CONFIG
    if DynamicConfig is not None and config.DYNAMIC_CONFIG_ENABLED:
        try:
            DYN_CONFIG = DynamicConfig(redis_client, key_prefix='mutt:config')
            logger.info("Dynamic configuration enabled")
        except Exception as e:
            logger.warning(f"Failed to initialize dynamic config: {e}")
            DYN_CONFIG = None


def _get_remediation_interval(config: Config) -> int:
    """Get remediation interval from dynamic config or static config."""
    if DYN_CONFIG:
        try:
            return int(DYN_CONFIG.get('remediation_interval', default=config.REMEDIATION_INTERVAL))
        except Exception:
            pass
    return config.REMEDIATION_INTERVAL


def _get_batch_size(config: Config) -> int:
    """Get batch size from dynamic config or static config."""
    if DYN_CONFIG:
        try:
            return int(DYN_CONFIG.get('remediation_batch_size', default=config.REMEDIATION_BATCH_SIZE))
        except Exception:
            pass
    return config.REMEDIATION_BATCH_SIZE


def _get_max_poison_retries(config: Config) -> int:
    """Get max poison retries from dynamic config or static config."""
    if DYN_CONFIG:
        try:
            return int(DYN_CONFIG.get('max_poison_retries', default=config.MAX_POISON_RETRIES))
        except Exception:
            pass
    return config.MAX_POISON_RETRIES


# =====================================================================
# HEALTH CHECK ENDPOINT
# =====================================================================

def start_health_check(config: Config, stop_event: threading.Event):
    """Start simple health check HTTP server."""
    from http.server import HTTPServer, BaseHTTPRequestHandler

    class HealthHandler(BaseHTTPRequestHandler):
        def do_GET(self):
            if self.path == '/health':
                self.send_response(200)
                self.send_header('Content-type', 'text/plain')
                self.end_headers()
                self.wfile.write(b'OK')
            else:
                self.send_response(404)
                self.end_headers()

        def log_message(self, format, *args):
            pass  # Suppress logs

    server = HTTPServer(('0.0.0.0', config.HEALTH_PORT), HealthHandler)
    server.timeout = 1

    def serve():
        logger.info(f"Health check server started on port {config.HEALTH_PORT}")
        while not stop_event.is_set():
            server.handle_request()
        logger.info("Health check server stopped")

    thread = threading.Thread(target=serve, daemon=True, name="HealthCheck")
    thread.start()
    return thread


# =====================================================================
# MOOGSOFT HEALTH CHECK
# =====================================================================

_moog_health_cache: Dict[str, Any] = {"status": None, "timestamp": 0}
_MOOG_HEALTH_CACHE_TTL = 60 # seconds

def check_moogsoft_health(config: Config) -> bool:
    """
    Check if Moogsoft is healthy by sending a test event.
    Caches the result for 60 seconds to avoid excessive API calls.

    Returns:
        True if Moogsoft is healthy, False otherwise
    """
    global _moog_health_cache

    # Check cache first
    if (time.time() - _moog_health_cache["timestamp"]) < _MOOG_HEALTH_CACHE_TTL:
        logger.debug("Returning cached Moogsoft health status")
        return _moog_health_cache["status"]

    if not config.MOOG_HEALTH_CHECK_ENABLED or not config.MOOG_WEBHOOK_URL:
        logger.debug("Moogsoft health check disabled or URL not configured")
        _moog_health_cache = {"status": True, "timestamp": time.time()}
        return True  # Assume healthy if checks disabled

    try:
        # Send a test event with special marker
        test_payload = {
            "source": "MUTT_HEALTH_CHECK",
            "description": "Health check probe - auto-close",
            "severity": "clear",
            "check_id": f"health_check_{int(time.time())}",
            "timestamp": datetime.now(timezone.utc).isoformat()
        }

        response = requests.post(
            config.MOOG_WEBHOOK_URL,
            json=test_payload,
            timeout=config.MOOG_HEALTH_TIMEOUT
        )

        # Accept 200, 201, or 202 as success
        is_healthy = response.status_code in (200, 201, 202)

        if is_healthy:
            logger.debug(f"Moogsoft health check passed: {response.status_code}")
            METRIC_MOOG_HEALTH_CHECK.set(1)
        else:
            logger.warning(f"Moogsoft health check failed: {response.status_code}")
            METRIC_MOOG_HEALTH_CHECK.set(0)

        _moog_health_cache = {"status": is_healthy, "timestamp": time.time()}
        return is_healthy

    except requests.exceptions.Timeout:
        logger.warning(f"Moogsoft health check timed out after {config.MOOG_HEALTH_TIMEOUT}s")
        METRIC_MOOG_HEALTH_CHECK.set(0)
        _moog_health_cache = {"status": False, "timestamp": time.time()}
        return False

    except requests.exceptions.ConnectionError as e:
        logger.warning(f"Moogsoft health check connection error: {e}")
        METRIC_MOOG_HEALTH_CHECK.set(0)
        _moog_health_cache = {"status": False, "timestamp": time.time()}
        return False

    except Exception as e:
        logger.error(f"Moogsoft health check failed: {e}")
        METRIC_MOOG_HEALTH_CHECK.set(0)
        _moog_health_cache = {"status": False, "timestamp": time.time()}
        return False


# =====================================================================
# DLQ REPLAY LOGIC
# =====================================================================

def get_retry_count(message: str) -> int:
    """
    Extract retry count from message metadata.

    Messages should have a _moog_retry_count field added by the moog forwarder.
    """
    try:
        data = json.loads(message)
        return data.get('_moog_retry_count', 0)
    except (json.JSONDecodeError, KeyError):
        return 0


def replay_dlq_messages(
    config: Config,
    redis_client: redis.Redis
) -> Tuple[int, int, int]:
    """
    Replay messages from DLQ back to the alert queue.

    Returns:
        Tuple of (replayed_count, poison_count, failed_count)
    """
    replayed_count = 0
    poison_count = 0
    failed_count = 0

    batch_size = _get_batch_size(config)
    max_retries = _get_max_poison_retries(config)

    logger.info(f"Starting DLQ replay (batch_size={batch_size}, max_retries={max_retries})")

    try:
        # Get current DLQ depth
        dlq_depth = redis_client.llen(config.ALERTER_DLQ_NAME)
        METRIC_DLQ_DEPTH.labels(dlq_name=config.ALERTER_DLQ_NAME).set(dlq_depth)

        if dlq_depth == 0:
            logger.debug("DLQ is empty, nothing to replay")
            return (0, 0, 0)

        logger.info(f"DLQ depth: {dlq_depth} messages")

        # Process up to batch_size messages
        for i in range(min(batch_size, dlq_depth)):
            # Pop message from DLQ
            message = redis_client.rpop(config.ALERTER_DLQ_NAME)

            if message is None:
                break

            try:
                # Decode message
                message_str = message.decode('utf-8') if isinstance(message, bytes) else message

                # Check retry count
                retry_count = get_retry_count(message_str)

                if retry_count >= max_retries:
                    # Poison message - move to dead letter
                    logger.warning(
                        f"Poison message detected (retry_count={retry_count}), "
                        f"moving to dead letter: {message_str[:100]}"
                    )
                    redis_client.lpush(config.DEAD_LETTER_QUEUE, message)
                    METRIC_POISON_MESSAGES.inc()
                    poison_count += 1
                else:
                    # Replay to alert queue
                    redis_client.lpush(config.ALERTER_QUEUE_NAME, message)
                    METRIC_REPLAY_SUCCESS.inc()
                    replayed_count += 1
                    logger.info(f"Replayed message (retry_count={retry_count})")

            except Exception as e:
                logger.error(f"Failed to process DLQ message: {e}")
                # Put it back at the front of the DLQ
                redis_client.rpush(config.ALERTER_DLQ_NAME, message)
                METRIC_REPLAY_FAIL.labels(reason='processing_error').inc()
                failed_count += 1

        logger.info(
            f"DLQ replay complete: replayed={replayed_count}, "
            f"poison={poison_count}, failed={failed_count}"
        )

    except Exception as e:
        logger.error(f"DLQ replay failed: {e}")
        METRIC_REPLAY_FAIL.labels(reason='redis_error').inc()

    return (replayed_count, poison_count, failed_count)


# =====================================================================
# MAIN REMEDIATION LOOP
# =====================================================================

def remediation_loop(config: Config, redis_client: redis.Redis, stop_event: threading.Event):
    """Main remediation loop."""
    logger.info("Remediation loop started")

    while not stop_event.is_set():
        loop_start = time.time()

        try:
            METRIC_REMEDIATION_LOOPS.inc()

            # Step 1: Check Moogsoft health
            moog_healthy = check_moogsoft_health(config)

            if not moog_healthy:
                logger.warning("Moogsoft unhealthy, skipping DLQ replay this cycle")
            else:
                # Step 2: Replay DLQ messages
                replayed, poison, failed = replay_dlq_messages(config, redis_client)

                if replayed > 0 or poison > 0:
                    logger.info(
                        f"Remediation cycle complete: replayed={replayed}, "
                        f"poison={poison}, failed={failed}"
                    )

            # Record loop duration
            loop_duration = time.time() - loop_start
            METRIC_REMEDIATION_DURATION.observe(loop_duration)

        except Exception as e:
            logger.error(f"Error in remediation loop: {e}", exc_info=True)

        # Sleep until next cycle (using stop_event.wait for interruptibility)
        interval = _get_remediation_interval(config)
        logger.debug(f"Sleeping for {interval} seconds until next cycle")
        stop_event.wait(interval)

    logger.info("Remediation loop stopped")


# =====================================================================
# SIGNAL HANDLING
# =====================================================================

stop_event = threading.Event()

def signal_handler(signum, frame):
    """Handle shutdown signals gracefully."""
    logger.info(f"Received signal {signum}, initiating graceful shutdown...")
    stop_event.set()

signal.signal(signal.SIGINT, signal_handler)
signal.signal(signal.SIGTERM, signal_handler)


# =====================================================================
# MAIN ENTRY POINT
# =====================================================================

def main():
    """Main service entry point."""
    config = Config()

    # Setup logging
    if setup_json_logging is not None:
        setup_json_logging(
            service_name="remediation",
            log_level=config.LOG_LEVEL
        )
    else:
        logging.basicConfig(
            level=getattr(logging, config.LOG_LEVEL),
            format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
        )

    # Setup tracing
    if setup_tracing is not None:
        setup_tracing(service_name="remediation", version="2.5.0")

    logger.info("=" * 70)
    logger.info(f"MUTT Remediation Service v2.5 - Pod: {config.POD_NAME}")
    logger.info("=" * 70)

    if not config.REMEDIATION_ENABLED:
        logger.warning("Remediation is DISABLED. Exiting.")
        sys.exit(0)

    # Start Prometheus metrics server
    try:
        start_http_server(config.METRICS_PORT)
        logger.info(f"Metrics server started on port {config.METRICS_PORT}")
    except Exception as e:
        logger.error(f"Failed to start metrics server: {e}")
        sys.exit(1)

    # Start health check server
    health_thread = start_health_check(config, stop_event)

    # Connect to Redis
    try:
        redis_client = redis.Redis(
            host=config.REDIS_HOST,
            port=config.REDIS_PORT,
            db=config.REDIS_DB,
            decode_responses=False,
            socket_connect_timeout=5,
            socket_keepalive=True
        )
        redis_client.ping()
        logger.info(f"Connected to Redis at {config.REDIS_HOST}:{config.REDIS_PORT}")
    except Exception as e:
        logger.error(f"Failed to connect to Redis: {e}")
        sys.exit(1)

    # Initialize dynamic config
    _init_dynamic_config(config, redis_client)

    # Start remediation loop
    logger.info(f"Starting remediation loop (interval={config.REMEDIATION_INTERVAL}s)")
    remediation_loop(config, redis_client, stop_event)

    # Cleanup
    logger.info("Shutting down gracefully...")
    health_thread.join(timeout=2)
    logger.info("Shutdown complete")


if __name__ == "__main__":
    main()
