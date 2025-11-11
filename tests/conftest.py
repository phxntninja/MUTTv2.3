# =====================================================================
# MUTT v2.3 Pytest Configuration and Fixtures
# =====================================================================
# This file contains shared fixtures and configuration for all tests
# =====================================================================

import pytest
from unittest.mock import MagicMock, Mock
import redis
import psycopg2
from prometheus_client import REGISTRY


# --- Prometheus Metrics Cleanup ---

@pytest.fixture(autouse=True, scope="function")
def cleanup_prometheus_metrics():
    """
    Clean up MUTT-specific Prometheus metrics before each test.

    This prevents 'Duplicated timeseries in CollectorRegistry' errors
    that occur when service modules are imported multiple times during testing.
    Only removes collectors for metrics starting with 'mutt_', preserving
    the default Prometheus collectors (platform, process, gc, etc.).
    """
    yield  # Run the test first

    # After the test, clean up MUTT metrics
    collectors_to_remove = []
    for collector in list(REGISTRY._collector_to_names.keys()):
        try:
            # Get the metric names registered by this collector
            names = REGISTRY._collector_to_names.get(collector, set())
            # Check if any of the names start with 'mutt_'
            if any(name.startswith('mutt_') for name in names):
                collectors_to_remove.append(collector)
        except Exception:
            # Skip collectors that don't have the expected structure
            pass

    # Unregister only MUTT metrics
    for collector in collectors_to_remove:
        try:
            REGISTRY.unregister(collector)
        except Exception:
            # Ignore errors during cleanup
            pass


# --- Mock Configuration ---

@pytest.fixture
def mock_config():
    """Mock configuration object for all services"""
    config = Mock()

    # Common config
    config.REDIS_HOST = "localhost"
    config.REDIS_PORT = 6379
    config.REDIS_TLS_ENABLED = False
    config.REDIS_POOL_MIN_CONN = 2
    config.REDIS_POOL_MAX_CONN = 10

    # Vault config
    config.VAULT_ADDR = "http://localhost:8200"
    config.VAULT_TOKEN = "test-token"
    config.VAULT_SECRETS_PATH = "secret/mutt"
    config.VAULT_TOKEN_RENEW_THRESHOLD = 3600

    # Ingestor config
    config.SERVER_PORT_INGESTOR = 8080
    config.INGEST_QUEUE_NAME = "mutt:ingest_queue"
    config.MAX_INGEST_QUEUE_SIZE = 1000000
    config.METRICS_PREFIX = "mutt:metrics"

    # Alerter config
    config.SERVER_PORT_ALERTER = 8081
    config.SERVER_PORT_ALERTER_METRICS = 8082
    config.ALERT_QUEUE_NAME = "mutt:alert_queue"
    config.ALERTER_POD_NAME = "test-alerter-01"
    config.ALERTER_HEARTBEAT_INTERVAL = 30
    config.ALERTER_RULE_CACHE_REFRESH_INTERVAL = 300
    config.UNHANDLED_EVENT_THRESHOLD = 100
    config.UNHANDLED_EVENT_WINDOW = 3600

    # Database config
    config.DB_HOST = "localhost"
    config.DB_PORT = 5432
    config.DB_NAME = "mutt"
    config.DB_USER = "mutt_app"
    config.DB_PASS = "test_password"
    config.DB_SSL_MODE = "disable"
    config.DB_POOL_MIN_CONN = 2
    config.DB_POOL_MAX_CONN = 10

    # Moog Forwarder config
    config.SERVER_PORT_MOOG_FORWARDER = 8083
    config.SERVER_PORT_MOOG_METRICS = 8084
    config.MOOG_WEBHOOK_URL = "http://moog.example.com/webhook"
    config.MOOG_TIMEOUT = 10
    config.MOOG_RATE_LIMIT = 50
    config.MOOG_RATE_PERIOD = 1
    config.MOOG_RETRY_BASE_DELAY = 1
    config.MOOG_RETRY_MAX_DELAY = 60
    config.MOOG_MAX_RETRIES = 5
    config.MOOG_POD_NAME = "test-moog-01"
    config.MOOG_HEARTBEAT_INTERVAL = 30

    # Web UI config
    config.SERVER_PORT_WEBUI = 8090

    return config


@pytest.fixture
def mock_secrets():
    """Mock secrets object"""
    return {
        "REDIS_PASS": "redis_password",
        "DB_PASS": "db_password",
        "INGEST_API_KEY": "test-api-key-123",
        "WEBUI_API_KEY": "test-api-key-123",
        "MOOG_API_KEY": "moog-api-key"
    }


@pytest.fixture
def mock_redis_client():
    """Mock Redis client"""
    client = MagicMock(spec=redis.Redis)

    # Set up common Redis method returns
    client.ping.return_value = True
    client.llen.return_value = 0
    client.lpush.return_value = 1
    client.brpoplpush.return_value = None
    client.lrem.return_value = 1
    client.setex.return_value = True
    client.incr.return_value = 1
    client.expire.return_value = True
    client.get.return_value = None
    client.set.return_value = True
    client.exists.return_value = 0
    client.scan.return_value = (0, [])
    client.pipeline.return_value = MagicMock()

    return client


@pytest.fixture
def mock_postgres_conn():
    """Mock PostgreSQL connection"""
    conn = MagicMock(spec=psycopg2.extensions.connection)
    cursor = MagicMock(spec=psycopg2.extensions.cursor)

    # Set up cursor
    cursor.fetchall.return_value = []
    cursor.fetchone.return_value = None
    cursor.rowcount = 0

    # Set up connection
    conn.cursor.return_value.__enter__ = Mock(return_value=cursor)
    conn.cursor.return_value.__exit__ = Mock(return_value=False)
    conn.commit.return_value = None

    return conn


@pytest.fixture
def mock_postgres_pool(mock_postgres_conn):
    """Mock PostgreSQL connection pool"""
    pool = MagicMock()
    conn = mock_postgres_conn

    pool.getconn.return_value = conn
    pool.putconn.return_value = None

    return pool


@pytest.fixture
def mock_vault_client():
    """Mock Vault client"""
    vault = MagicMock()

    # Mock authentication
    vault.is_authenticated.return_value = True
    vault.auth.approle.login.return_value = {"auth": {"client_token": "test-token"}}

    # Mock secrets reading
    vault.secrets.kv.v2.read_secret_version.return_value = {
        "data": {
            "data": {
                "REDIS_PASS": "redis_password",
                "DB_PASS": "db_password",
                "INGEST_API_KEY": "test-api-key-123",
                "WEBUI_API_KEY": "test-api-key-123",
                "MOOG_API_KEY": "moog-api-key"
            }
        }
    }

    # Mock token lookup
    vault.auth.token.lookup_self.return_value = {
        "data": {
            "ttl": 7200  # 2 hours
        }
    }

    # Mock token renewal
    vault.auth.token.renew_self.return_value = {"auth": {"client_token": "test-token"}}

    return vault


# --- Sample Data Fixtures ---

@pytest.fixture
def sample_syslog_message():
    """Sample syslog message for testing"""
    return {
        "timestamp": "2025-11-08T12:00:00Z",
        "message": "CRITICAL: System failure detected",
        "hostname": "server-01.example.com",
        "program": "kernel",
        "syslog_severity": 2,
        "source_ip": "192.168.1.100",
        "mutt_type": "syslog"
    }


@pytest.fixture
def sample_snmp_trap():
    """Sample SNMP trap for testing"""
    return {
        "timestamp": "2025-11-08T12:00:00Z",
        "message": "192.168.1.50 .1.3.6.1.6.3.1.1.5.3 ifIndex=2 ifAdminStatus=1 ifOperStatus=2",
        "hostname": "localhost",
        "program": "snmptrapd",
        "syslog_severity": 4,
        "source_ip": "127.0.0.1",
        "mutt_type": "snmp_trap"
    }


@pytest.fixture
def sample_alert_rules():
    """Sample alert rules for testing"""
    return [
        {
            "id": 1,
            "match_string": "CRITICAL",
            "trap_oid": None,
            "syslog_severity": None,
            "match_type": "contains",
            "priority": 10,
            "prod_handling": "Page_and_ticket",
            "dev_handling": "Ticket_only",
            "team_assignment": "NETO",
            "is_active": True
        },
        {
            "id": 2,
            "match_string": "ERROR",
            "trap_oid": None,
            "syslog_severity": None,
            "match_type": "contains",
            "priority": 20,
            "prod_handling": "Ticket_only",
            "dev_handling": "Ignore",
            "team_assignment": "NETO",
            "is_active": True
        },
        {
            "id": 3,
            "match_string": r"LINK-(UP|DOWN)",
            "trap_oid": None,
            "syslog_severity": None,
            "match_type": "regex",
            "priority": 5,
            "prod_handling": "Page_and_ticket",
            "dev_handling": "Ticket_only",
            "team_assignment": "NetOps",
            "is_active": True
        },
        {
            "id": 4,
            "match_string": None,
            "trap_oid": ".1.3.6.1.6.3.1.1.5.3",
            "syslog_severity": None,
            "match_type": "oid_prefix",
            "priority": 15,
            "prod_handling": "Page_and_ticket",
            "dev_handling": "Ignore",
            "team_assignment": "NetOps",
            "is_active": True
        }
    ]


@pytest.fixture
def sample_dev_hosts():
    """Sample development hosts for testing"""
    return ["dev-server-01", "test-server-01", "qa-server-01"]


@pytest.fixture
def sample_device_teams():
    """Sample device teams for testing"""
    return {
        "router1.prod.example.com": "NetOps",
        "switch1.prod.example.com": "NetOps",
        "firewall1.prod.example.com": "Security",
        "server1.prod.example.com": "SysAdmin"
    }


# --- Flask Test Client Fixtures ---

@pytest.fixture
def ingestor_client(monkeypatch):
    """Flask test client for Ingestor service"""
    # Mock Vault and Redis before importing
    with monkeypatch.context() as m:
        # This would be used in integration tests
        # For unit tests, we'll mock at the function level
        pass


# --- Pytest Configuration ---

def pytest_configure(config):
    """Pytest configuration hook"""
    # Add custom markers
    config.addinivalue_line(
        "markers", "unit: Unit tests (mock all external dependencies)"
    )
    config.addinivalue_line(
        "markers", "integration: Integration tests (requires real services)"
    )
    config.addinivalue_line(
        "markers", "slow: Slow tests (>1 second)"
    )


# --- Helper Functions ---

def assert_log_contains(caplog, level, message_fragment):
    """Assert that logs contain a specific message"""
    for record in caplog.records:
        if record.levelname == level and message_fragment in record.message:
            return True
    raise AssertionError(
        f"Log message containing '{message_fragment}' at level '{level}' not found"
    )
