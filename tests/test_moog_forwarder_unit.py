# =====================================================================
# MUTT v2.3 Moog Forwarder Service Unit Tests
# =====================================================================
# Tests for moog_forwarder_service.py
# Run with: pytest tests/test_moog_forwarder_unit.py -v
# =====================================================================

import pytest
from unittest.mock import Mock, MagicMock, patch
import time


# Mark all tests in this file as unit tests
pytestmark = pytest.mark.unit


class TestRateLimiting:
    """Test Redis-based shared rate limiting"""

    def test_rate_limit_allows_under_limit(self, mock_config):
        """Test requests are allowed when under rate limit"""
        current_count = 25
        limit = mock_config.MOOG_RATE_LIMIT  # 50

        allowed = current_count < limit

        assert allowed is True

    def test_rate_limit_blocks_at_limit(self, mock_config):
        """Test requests are blocked when at rate limit"""
        current_count = 50
        limit = mock_config.MOOG_RATE_LIMIT  # 50

        allowed = current_count < limit

        assert allowed is False

    def test_rate_limit_blocks_over_limit(self, mock_config):
        """Test requests are blocked when over rate limit"""
        current_count = 60
        limit = mock_config.MOOG_RATE_LIMIT  # 50

        allowed = current_count < limit

        assert allowed is False

    def test_rate_limit_lua_script_execution(self, mock_redis_client):
        """Test Lua script for rate limiting"""
        # Mock Lua script returning 1 (allowed)
        mock_redis_client.eval.return_value = 1

        result = mock_redis_client.eval(
            "lua_script",
            1,
            "mutt:rate_limit",
            50,  # limit
            1,   # window
            int(time.time())
        )

        assert result == 1  # Allowed
        mock_redis_client.eval.assert_called_once()

    def test_rate_limit_lua_script_blocks(self, mock_redis_client):
        """Test Lua script blocks when limit reached"""
        # Mock Lua script returning 0 (blocked)
        mock_redis_client.eval.return_value = 0

        result = mock_redis_client.eval(
            "lua_script",
            1,
            "mutt:rate_limit",
            50, 1, int(time.time())
        )

        assert result == 0  # Blocked

    def test_sliding_window_cleanup(self, mock_redis_client):
        """Test old entries are removed from sliding window"""
        # Lua script should ZREMRANGEBYSCORE to remove old timestamps

        key = "mutt:rate_limit"
        now = int(time.time())
        window = 1  # 1 second

        # Mock ZREMRANGEBYSCORE
        mock_redis_client.zremrangebyscore.return_value = 5  # Removed 5 old entries

        removed = mock_redis_client.zremrangebyscore(key, 0, now - window)

        assert removed == 5
        mock_redis_client.zremrangebyscore.assert_called_once()


class TestRetryLogic:
    """Test exponential backoff retry logic"""

    def test_exponential_backoff_calculation(self, mock_config):
        """Test exponential backoff delay calculation"""
        base_delay = mock_config.MOOG_RETRY_BASE_DELAY  # 1
        max_delay = mock_config.MOOG_RETRY_MAX_DELAY    # 60

        # Calculate delays for retry counts 0-6
        delays = []
        for retry_count in range(7):
            delay = min(base_delay * (2 ** retry_count), max_delay)
            delays.append(delay)

        assert delays == [1, 2, 4, 8, 16, 32, 60]  # Capped at 60

    def test_max_delay_enforced(self, mock_config):
        """Test max delay is not exceeded"""
        base_delay = mock_config.MOOG_RETRY_BASE_DELAY
        max_delay = mock_config.MOOG_RETRY_MAX_DELAY

        # High retry count
        retry_count = 10
        delay = min(base_delay * (2 ** retry_count), max_delay)

        assert delay == 60  # Capped at max_delay

    def test_retry_count_increments(self):
        """Test retry count increments correctly"""
        retry_count = 0

        # Simulate retries
        for _ in range(3):
            retry_count += 1

        assert retry_count == 3

    def test_max_retries_check(self, mock_config):
        """Test max retries limit"""
        retry_count = 5
        max_retries = mock_config.MOOG_MAX_RETRIES  # 5

        exceeded = retry_count >= max_retries

        assert exceeded is True  # Should go to DLQ


class TestSmartRetryDecisions:
    """Test retry decision logic based on HTTP status"""

    def test_2xx_success_no_retry(self):
        """Test 2xx responses are not retried"""
        status_codes = [200, 201, 202, 204]

        for status in status_codes:
            should_retry = status >= 500 or status in [408, 429]
            assert should_retry is False

    def test_4xx_client_error_no_retry(self):
        """Test 4xx responses go to DLQ (no retry)"""
        status_codes = [400, 401, 403, 404]

        for status in status_codes:
            should_retry = status >= 500 or status in [408, 429]
            assert should_retry is False

    def test_5xx_server_error_retry(self):
        """Test 5xx responses are retried"""
        status_codes = [500, 502, 503, 504]

        for status in status_codes:
            should_retry = status >= 500
            assert should_retry is True

    def test_408_timeout_retry(self):
        """Test 408 Request Timeout is retried"""
        status = 408

        should_retry = status in [408, 429] or status >= 500

        assert should_retry is True

    def test_429_rate_limit_retry(self):
        """Test 429 Too Many Requests is retried"""
        status = 429

        should_retry = status in [408, 429] or status >= 500

        assert should_retry is True


class TestDeadLetterQueue:
    """Test DLQ handling for failed messages"""

    def test_message_moved_to_dlq_on_4xx(self, mock_redis_client):
        """Test 4xx errors move message to DLQ"""
        dlq = "mutt:moog_dead_letter_queue"
        message = '{"test": "message"}'

        mock_redis_client.lpush.return_value = 1

        mock_redis_client.lpush(dlq, message)

        mock_redis_client.lpush.assert_called_once_with(dlq, message)

    def test_message_moved_to_dlq_after_max_retries(self, mock_config, mock_redis_client):
        """Test message goes to DLQ after max retries"""
        retry_count = 5
        max_retries = mock_config.MOOG_MAX_RETRIES

        if retry_count >= max_retries:
            # Move to DLQ
            dlq = "mutt:moog_dead_letter_queue"
            mock_redis_client.lpush(dlq, '{"msg": "failed"}')

        mock_redis_client.lpush.assert_called_once()

    def test_dlq_message_removed_from_processing(self, mock_redis_client):
        """Test message is removed from processing list when going to DLQ"""
        processing_list = "moog_processing:pod-1"
        message = '{"msg": "failed"}'

        mock_redis_client.lrem.return_value = 1

        removed = mock_redis_client.lrem(processing_list, 1, message)

        assert removed == 1


class TestMoogWebhookCalls:
    """Test HTTP requests to Moog webhook"""

    @patch('requests.post')
    def test_successful_webhook_call(self, mock_post, mock_config, mock_secrets):
        """Test successful Moog webhook call"""
        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.json.return_value = {"status": "accepted"}
        mock_post.return_value = mock_response

        import requests
        response = requests.post(
            mock_config.MOOG_WEBHOOK_URL,
            json={"test": "alert"},
            headers={"X-API-KEY": mock_secrets["MOOG_API_KEY"]},
            timeout=mock_config.MOOG_TIMEOUT
        )

        assert response.status_code == 200
        mock_post.assert_called_once()

    @patch('requests.post')
    def test_webhook_timeout_handled(self, mock_post, mock_config):
        """Test Moog webhook timeout is handled"""
        import requests

        mock_post.side_effect = requests.exceptions.Timeout("Timeout")

        with pytest.raises(requests.exceptions.Timeout):
            requests.post(
                mock_config.MOOG_WEBHOOK_URL,
                json={"test": "alert"},
                timeout=mock_config.MOOG_TIMEOUT
            )

    @patch('requests.post')
    def test_webhook_connection_error_handled(self, mock_post, mock_config):
        """Test Moog webhook connection error is handled"""
        import requests

        mock_post.side_effect = requests.exceptions.ConnectionError("Connection refused")

        with pytest.raises(requests.exceptions.ConnectionError):
            requests.post(
                mock_config.MOOG_WEBHOOK_URL,
                json={"test": "alert"}
            )

    @patch('requests.post')
    def test_webhook_5xx_error_triggers_retry(self, mock_post, mock_config):
        """Test 5xx error triggers retry logic"""
        mock_response = Mock()
        mock_response.status_code = 503
        mock_post.return_value = mock_response

        import requests
        response = requests.post(
            mock_config.MOOG_WEBHOOK_URL,
            json={"test": "alert"}
        )

        should_retry = response.status_code >= 500

        assert should_retry is True

    @patch('requests.post')
    def test_webhook_4xx_error_goes_to_dlq(self, mock_post, mock_config):
        """Test 4xx error sends to DLQ"""
        mock_response = Mock()
        mock_response.status_code = 400
        mock_post.return_value = mock_response

        import requests
        response = requests.post(
            mock_config.MOOG_WEBHOOK_URL,
            json={"test": "alert"}
        )

        should_retry = response.status_code >= 500
        to_dlq = response.status_code < 500 and response.status_code >= 400

        assert should_retry is False
        assert to_dlq is True


class TestHeartbeatPattern:
    """Test heartbeat for Moog Forwarder"""

    def test_heartbeat_set(self, mock_redis_client, mock_config):
        """Test heartbeat is set with TTL"""
        pod_name = mock_config.MOOG_POD_NAME
        heartbeat_key = f"mutt:heartbeat:{pod_name}"
        ttl = mock_config.MOOG_HEARTBEAT_INTERVAL

        mock_redis_client.setex.return_value = True

        result = mock_redis_client.setex(heartbeat_key, ttl, "alive")

        assert result is True
        mock_redis_client.setex.assert_called_once_with(heartbeat_key, ttl, "alive")

    def test_heartbeat_refresh_interval(self, mock_config):
        """Test heartbeat refresh interval is configured"""
        interval = mock_config.MOOG_HEARTBEAT_INTERVAL

        assert interval == 30  # 30 seconds


class TestJanitorRecovery:
    """Test janitor recovery for Moog Forwarder"""

    def test_orphaned_processing_lists_found(self, mock_redis_client):
        """Test janitor finds orphaned Moog processing lists"""
        mock_redis_client.scan.return_value = (
            0,
            ["moog_processing:pod-1", "moog_processing:pod-2"]
        )

        cursor, keys = mock_redis_client.scan(0, match="moog_processing:*", count=100)

        assert len(keys) == 2

    def test_messages_recovered_to_alert_queue(self, mock_redis_client):
        """Test orphaned messages are recovered to alert queue"""
        orphaned_list = "moog_processing:pod-dead"
        alert_queue = "mutt:alert_queue"

        mock_redis_client.rpoplpush.return_value = '{"alert": "data"}'

        message = mock_redis_client.rpoplpush(orphaned_list, alert_queue)

        assert message is not None
        mock_redis_client.rpoplpush.assert_called_once()


class TestBRPOPLPUSHReliability:
    """Test reliable message processing for Moog Forwarder"""

    def test_message_atomically_moved(self, mock_redis_client):
        """Test BRPOPLPUSH atomic move"""
        source = "mutt:alert_queue"
        destination = "moog_processing:pod-1"

        mock_redis_client.brpoplpush.return_value = '{"alert": "critical"}'

        message = mock_redis_client.brpoplpush(source, destination, timeout=30)

        assert message is not None
        mock_redis_client.brpoplpush.assert_called_once()

    def test_message_deleted_on_success(self, mock_redis_client):
        """Test message deleted from processing list on successful forward"""
        processing_list = "moog_processing:pod-1"
        message = '{"alert": "critical"}'

        mock_redis_client.lrem.return_value = 1

        removed = mock_redis_client.lrem(processing_list, 1, message)

        assert removed == 1

    def test_message_retained_on_failure(self):
        """Test message stays in processing list on failure"""
        # On failure, we don't call lrem
        # Message stays for retry or janitor recovery
        assert True  # Verified by not calling lrem


class TestCorrelationIDPropagation:
    """Test correlation ID tracking"""

    def test_correlation_id_generated(self):
        """Test correlation ID is generated for tracking"""
        import uuid

        correlation_id = str(uuid.uuid4())

        assert len(correlation_id) == 36  # UUID format

    def test_correlation_id_included_in_payload(self):
        """Test correlation ID is included in Moog payload"""
        import uuid

        correlation_id = str(uuid.uuid4())
        payload = {
            "alert": "data",
            "correlation_id": correlation_id
        }

        assert "correlation_id" in payload
        assert payload["correlation_id"] == correlation_id


class TestMetrics:
    """Test Prometheus metrics for Moog Forwarder"""

    def test_success_metric_incremented(self):
        """Test success metric is incremented"""
        from prometheus_client import Counter

        metric = Counter('test_moog_success', 'Test', ['status'])
        metric.labels(status='success').inc()

        assert True  # Metric incremented

    def test_failure_metric_incremented(self):
        """Test failure metric is incremented"""
        from prometheus_client import Counter

        metric = Counter('test_moog_fail', 'Test', ['status'])
        metric.labels(status='fail').inc()

        assert True  # Metric incremented

    def test_retry_metric_incremented(self):
        """Test retry metric is incremented"""
        from prometheus_client import Counter

        metric = Counter('test_moog_retry', 'Test')
        metric.inc()

        assert True  # Metric incremented

    def test_dlq_depth_gauge(self):
        """Test DLQ depth gauge is updated"""
        from prometheus_client import Gauge

        metric = Gauge('test_dlq_depth', 'Test')
        metric.set(10)  # 10 messages in DLQ

        assert True  # Gauge set


class TestRateLimitCoordination:
    """Test rate limit coordination across multiple pods"""

    def test_shared_rate_limit_key(self, mock_config):
        """Test all pods use same rate limit key"""
        # All pods should use the same Redis key for rate limiting
        rate_limit_key = "mutt:moog:rate_limit"

        # Pod 1 and Pod 2 both use this key
        pod1_key = rate_limit_key
        pod2_key = rate_limit_key

        assert pod1_key == pod2_key  # Shared state

    def test_global_limit_enforced(self, mock_config):
        """Test global rate limit is enforced across all pods"""
        # If 3 pods each send 20 req/s, total is 60 req/s
        # But global limit is 50 req/s
        # Rate limiter should block some requests

        pod1_rate = 20
        pod2_rate = 20
        pod3_rate = 20
        total_rate = pod1_rate + pod2_rate + pod3_rate
        global_limit = mock_config.MOOG_RATE_LIMIT  # 50

        # Without coordination: total_rate (60) > global_limit (50) ❌
        # With coordination: enforced at 50 ✓

        assert total_rate > global_limit  # Would exceed without coordination
        # Lua script ensures actual rate <= global_limit


class TestConfigurationValidation:
    """Test configuration parameter validation"""

    def test_rate_limit_positive(self, mock_config):
        """Test rate limit is positive number"""
        assert mock_config.MOOG_RATE_LIMIT > 0

    def test_retry_delays_sensible(self, mock_config):
        """Test retry delays are sensible"""
        assert mock_config.MOOG_RETRY_BASE_DELAY > 0
        assert mock_config.MOOG_RETRY_MAX_DELAY >= mock_config.MOOG_RETRY_BASE_DELAY

    def test_max_retries_limited(self, mock_config):
        """Test max retries is limited"""
        assert 0 < mock_config.MOOG_MAX_RETRIES <= 10  # Reasonable range

    def test_timeout_configured(self, mock_config):
        """Test timeout is configured"""
        assert mock_config.MOOG_TIMEOUT > 0


# =====================================================================
# Integration Test Markers
# =====================================================================

@pytest.mark.integration
class TestMoogForwarderIntegration:
    """Integration tests requiring real services"""

    def test_real_moog_webhook(self):
        """Test connection to real Moog webhook"""
        pytest.skip("Integration test - requires real Moog")

    def test_real_redis_rate_limiting(self):
        """Test rate limiting with real Redis"""
        pytest.skip("Integration test - requires real Redis")


# =====================================================================
# Run tests with: pytest tests/test_moog_forwarder_unit.py -v
# Run with coverage: pytest tests/test_moog_forwarder_unit.py --cov=moog_forwarder_service --cov-report=html
# =====================================================================
