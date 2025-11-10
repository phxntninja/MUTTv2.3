"""
=====================================================================
MUTT v2.5 Remediation Service Unit Tests
=====================================================================
Tests for services/remediation_service.py
Run with: pytest tests/test_remediation_unit.py -v
=====================================================================
"""

import sys
import os

# Add services directory to path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'services'))

import pytest
import json
from unittest.mock import Mock, MagicMock, patch
import threading

# Mark all tests as unit tests
pytestmark = pytest.mark.unit


# =====================================================================
# FIXTURES
# =====================================================================

@pytest.fixture
def mock_config():
    """Provides a mock Config object."""
    config = Mock()
    config.POD_NAME = "remediation-test"
    config.METRICS_PORT = 8086
    config.HEALTH_PORT = 8087
    config.LOG_LEVEL = "INFO"
    config.REDIS_HOST = "localhost"
    config.REDIS_PORT = 6379
    config.REDIS_DB = 0
    config.ALERTER_DLQ_NAME = "mutt:dlq:alerter"
    config.ALERTER_QUEUE_NAME = "mutt:ingest_queue"
    config.DEAD_LETTER_QUEUE = "mutt:dlq:dead"
    config.REMEDIATION_ENABLED = True
    config.REMEDIATION_INTERVAL = 300
    config.REMEDIATION_BATCH_SIZE = 10
    config.MAX_POISON_RETRIES = 3
    config.MOOG_HEALTH_CHECK_ENABLED = True
    config.MOOG_WEBHOOK_URL = "http://moogsoft.example.com/webhook"
    config.MOOG_HEALTH_TIMEOUT = 5
    config.DYNAMIC_CONFIG_ENABLED = False
    return config


@pytest.fixture
def mock_redis():
    """Provides a mock Redis client."""
    return Mock()


@pytest.fixture
def mock_stop_event():
    """Provides a mock stop event."""
    return threading.Event()


# =====================================================================
# TEST CONFIG
# =====================================================================

class TestRemediationConfig:
    """Tests for Config class."""

    @patch.dict('os.environ', {
        'POD_NAME': 'test-pod',
        'REMEDIATION_INTERVAL': '600',
        'REMEDIATION_BATCH_SIZE': '20',
        'MAX_POISON_RETRIES': '5'
    })
    def test_config_from_environment(self):
        """Test that config loads from environment variables."""
        from remediation_service import Config

        config = Config()

        assert config.POD_NAME == 'test-pod'
        assert config.REMEDIATION_INTERVAL == 600
        assert config.REMEDIATION_BATCH_SIZE == 20
        assert config.MAX_POISON_RETRIES == 5

    def test_config_defaults(self):
        """Test that config has sensible defaults."""
        from remediation_service import Config

        config = Config()

        assert config.METRICS_PORT == 8086
        assert config.HEALTH_PORT == 8087
        assert config.REMEDIATION_ENABLED is True
        assert config.REMEDIATION_INTERVAL == 300
        assert config.REMEDIATION_BATCH_SIZE == 10
        assert config.MAX_POISON_RETRIES == 3


# =====================================================================
# TEST MOOGSOFT HEALTH CHECK
# =====================================================================

class TestMoogsoftHealthCheck:
    """Tests for check_moogsoft_health function."""

    def test_health_check_disabled(self, mock_config):
        """Test health check returns True when disabled."""
        from remediation_service import check_moogsoft_health

        mock_config.MOOG_HEALTH_CHECK_ENABLED = False

        result = check_moogsoft_health(mock_config)

        assert result is True

    def test_health_check_no_url(self, mock_config):
        """Test health check returns True when URL not configured."""
        from remediation_service import check_moogsoft_health

        mock_config.MOOG_WEBHOOK_URL = ''

        result = check_moogsoft_health(mock_config)

        assert result is True

    @patch('remediation_service.requests.post')
    def test_health_check_success(self, mock_post, mock_config):
        """Test successful health check."""
        from remediation_service import check_moogsoft_health

        # Mock successful response
        mock_response = Mock()
        mock_response.status_code = 200
        mock_post.return_value = mock_response

        result = check_moogsoft_health(mock_config)

        assert result is True
        mock_post.assert_called_once()

        # Verify payload structure
        call_args = mock_post.call_args
        payload = call_args[1]['json']
        assert payload['source'] == 'MUTT_HEALTH_CHECK'
        assert 'description' in payload
        assert 'check_id' in payload

    @patch('remediation_service.requests.post')
    def test_health_check_accepts_202(self, mock_post, mock_config):
        """Test health check accepts 202 status."""
        from remediation_service import check_moogsoft_health

        mock_response = Mock()
        mock_response.status_code = 202
        mock_post.return_value = mock_response

        result = check_moogsoft_health(mock_config)

        assert result is True

    @patch('remediation_service.requests.post')
    def test_health_check_failure(self, mock_post, mock_config):
        """Test failed health check."""
        from remediation_service import check_moogsoft_health

        mock_response = Mock()
        mock_response.status_code = 500
        mock_post.return_value = mock_response

        result = check_moogsoft_health(mock_config)

        assert result is False

    @patch('remediation_service.requests.post')
    def test_health_check_timeout(self, mock_post, mock_config):
        """Test health check handles timeout."""
        from remediation_service import check_moogsoft_health
        import requests

        mock_post.side_effect = requests.exceptions.Timeout()

        result = check_moogsoft_health(mock_config)

        assert result is False

    @patch('remediation_service.requests.post')
    def test_health_check_connection_error(self, mock_post, mock_config):
        """Test health check handles connection error."""
        from remediation_service import check_moogsoft_health
        import requests

        mock_post.side_effect = requests.exceptions.ConnectionError()

        result = check_moogsoft_health(mock_config)

        assert result is False


# =====================================================================
# TEST RETRY COUNT EXTRACTION
# =====================================================================

class TestRetryCountExtraction:
    """Tests for get_retry_count function."""

    def test_get_retry_count_present(self):
        """Test extracting retry count from message."""
        from remediation_service import get_retry_count

        message = json.dumps({
            "alert_id": "123",
            "_moog_retry_count": 2
        })

        retry_count = get_retry_count(message)

        assert retry_count == 2

    def test_get_retry_count_absent(self):
        """Test default retry count when field absent."""
        from remediation_service import get_retry_count

        message = json.dumps({
            "alert_id": "123"
        })

        retry_count = get_retry_count(message)

        assert retry_count == 0

    def test_get_retry_count_invalid_json(self):
        """Test handling of invalid JSON."""
        from remediation_service import get_retry_count

        message = "not valid json"

        retry_count = get_retry_count(message)

        assert retry_count == 0


# =====================================================================
# TEST DLQ REPLAY
# =====================================================================

class TestDLQReplay:
    """Tests for replay_dlq_messages function."""

    def test_replay_empty_dlq(self, mock_config, mock_redis):
        """Test replaying from empty DLQ."""
        from remediation_service import replay_dlq_messages

        mock_redis.llen.return_value = 0

        replayed, poison, failed = replay_dlq_messages(mock_config, mock_redis)

        assert replayed == 0
        assert poison == 0
        assert failed == 0
        mock_redis.rpop.assert_not_called()

    def test_replay_normal_message(self, mock_config, mock_redis):
        """Test replaying a normal message (retry count < max)."""
        from remediation_service import replay_dlq_messages

        message = json.dumps({
            "alert_id": "123",
            "_moog_retry_count": 1
        })

        mock_redis.llen.return_value = 1
        mock_redis.rpop.return_value = message.encode('utf-8')

        replayed, poison, failed = replay_dlq_messages(mock_config, mock_redis)

        assert replayed == 1
        assert poison == 0
        assert failed == 0

        # Verify message pushed to alert queue
        mock_redis.lpush.assert_called_once_with(
            mock_config.ALERTER_QUEUE_NAME,
            message.encode('utf-8')
        )

    def test_replay_poison_message(self, mock_config, mock_redis):
        """Test handling poison message (retry count >= max)."""
        from remediation_service import replay_dlq_messages

        mock_config.MAX_POISON_RETRIES = 3

        message = json.dumps({
            "alert_id": "456",
            "_moog_retry_count": 5  # Exceeds max
        })

        mock_redis.llen.return_value = 1
        mock_redis.rpop.return_value = message.encode('utf-8')

        replayed, poison, failed = replay_dlq_messages(mock_config, mock_redis)

        assert replayed == 0
        assert poison == 1
        assert failed == 0

        # Verify message moved to dead letter queue
        mock_redis.lpush.assert_called_once_with(
            mock_config.DEAD_LETTER_QUEUE,
            message.encode('utf-8')
        )

    def test_replay_batch_size_limit(self, mock_config, mock_redis):
        """Test that batch size is respected."""
        from remediation_service import replay_dlq_messages

        mock_config.REMEDIATION_BATCH_SIZE = 2

        messages = [
            json.dumps({"alert_id": f"{i}", "_moog_retry_count": 0})
            for i in range(5)
        ]

        mock_redis.llen.return_value = 5
        mock_redis.rpop.side_effect = [m.encode('utf-8') for m in messages]

        replayed, poison, failed = replay_dlq_messages(mock_config, mock_redis)

        # Should only process batch_size messages
        assert mock_redis.rpop.call_count == 2
        assert replayed == 2

    def test_replay_processing_error(self, mock_config, mock_redis):
        """Test handling of processing error."""
        from remediation_service import replay_dlq_messages

        message = b"invalid json {{{{"

        mock_redis.llen.return_value = 1
        mock_redis.rpop.return_value = message
        # Simulate decode error by making decode() raise
        mock_redis.rpop.return_value = Mock()
        mock_redis.rpop.return_value.decode.side_effect = Exception("Decode error")

        replayed, poison, failed = replay_dlq_messages(mock_config, mock_redis)

        assert replayed == 0
        assert failed == 1

        # Message should be put back in DLQ
        mock_redis.rpush.assert_called_once()


# =====================================================================
# TEST DYNAMIC CONFIG HELPERS
# =====================================================================

class TestDynamicConfigHelpers:
    """Tests for dynamic config helper functions."""

    @patch('remediation_service.DYN_CONFIG', None)
    def test_get_interval_no_dynamic_config(self, mock_config):
        """Test getting interval when dynamic config disabled."""
        from remediation_service import _get_remediation_interval

        mock_config.REMEDIATION_INTERVAL = 600

        result = _get_remediation_interval(mock_config)

        assert result == 600

    @patch('remediation_service.DYN_CONFIG')
    def test_get_interval_with_dynamic_config(self, mock_dyn_config, mock_config):
        """Test getting interval from dynamic config."""
        from remediation_service import _get_remediation_interval

        mock_config.REMEDIATION_INTERVAL = 600
        mock_dyn_config.get.return_value = '300'

        result = _get_remediation_interval(mock_config)

        assert result == 300
        mock_dyn_config.get.assert_called_once_with('remediation_interval', default=600)

    @patch('remediation_service.DYN_CONFIG', None)
    def test_get_batch_size_no_dynamic_config(self, mock_config):
        """Test getting batch size when dynamic config disabled."""
        from remediation_service import _get_batch_size

        mock_config.REMEDIATION_BATCH_SIZE = 20

        result = _get_batch_size(mock_config)

        assert result == 20

    @patch('remediation_service.DYN_CONFIG', None)
    def test_get_max_retries_no_dynamic_config(self, mock_config):
        """Test getting max retries when dynamic config disabled."""
        from remediation_service import _get_max_poison_retries

        mock_config.MAX_POISON_RETRIES = 5

        result = _get_max_poison_retries(mock_config)

        assert result == 5


# =====================================================================
# TEST METRICS
# =====================================================================

class TestRemediationMetrics:
    """Tests that metrics are properly incremented."""

    @patch('remediation_service.METRIC_REPLAY_SUCCESS')
    def test_replay_success_metric(self, mock_metric, mock_config, mock_redis):
        """Test that replay success metric is incremented."""
        from remediation_service import replay_dlq_messages

        message = json.dumps({"alert_id": "123", "_moog_retry_count": 0})

        mock_redis.llen.return_value = 1
        mock_redis.rpop.return_value = message.encode('utf-8')

        replay_dlq_messages(mock_config, mock_redis)

        mock_metric.inc.assert_called_once()

    @patch('remediation_service.METRIC_POISON_MESSAGES')
    def test_poison_message_metric(self, mock_metric, mock_config, mock_redis):
        """Test that poison message metric is incremented."""
        from remediation_service import replay_dlq_messages

        mock_config.MAX_POISON_RETRIES = 3
        message = json.dumps({"alert_id": "456", "_moog_retry_count": 10})

        mock_redis.llen.return_value = 1
        mock_redis.rpop.return_value = message.encode('utf-8')

        replay_dlq_messages(mock_config, mock_redis)

        mock_metric.inc.assert_called_once()

    @patch('remediation_service.METRIC_DLQ_DEPTH')
    def test_dlq_depth_metric(self, mock_metric, mock_config, mock_redis):
        """Test that DLQ depth gauge is set."""
        from remediation_service import replay_dlq_messages

        mock_redis.llen.return_value = 42

        replay_dlq_messages(mock_config, mock_redis)

        mock_metric.labels.assert_called_once_with(dlq_name=mock_config.ALERTER_DLQ_NAME)
        mock_metric.labels().set.assert_called_once_with(42)


if __name__ == '__main__':
    pytest.main([__file__, '-v'])
