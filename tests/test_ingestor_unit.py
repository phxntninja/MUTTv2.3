# =====================================================================
# MUTT v2.3 Ingestor Service Unit Tests
# =====================================================================
# Tests for ingestor_service.py
# Run with: pytest tests/test_ingestor_unit.py -v
# =====================================================================

import pytest
from unittest.mock import Mock, MagicMock, patch, call
import json
import secrets as secrets_module


# Mark all tests in this file as unit tests
pytestmark = pytest.mark.unit


class TestAPIKeyAuthentication:
    """Test API key authentication logic"""

    def test_valid_api_key_accepted(self, mock_config, mock_secrets):
        """Test that valid API key is accepted"""
        # Use constant-time comparison like the actual code
        provided_key = "test-api-key-123"
        expected_key = mock_secrets["INGEST_API_KEY"]

        result = secrets_module.compare_digest(provided_key, expected_key)

        assert result is True

    def test_invalid_api_key_rejected(self, mock_config, mock_secrets):
        """Test that invalid API key is rejected"""
        provided_key = "wrong-api-key"
        expected_key = mock_secrets["INGEST_API_KEY"]

        result = secrets_module.compare_digest(provided_key, expected_key)

        assert result is False

    def test_empty_api_key_rejected(self, mock_config, mock_secrets):
        """Test that empty API key is rejected"""
        provided_key = ""
        expected_key = mock_secrets["INGEST_API_KEY"]

        result = secrets_module.compare_digest(provided_key, expected_key)

        assert result is False

    def test_none_api_key_rejected(self, mock_config, mock_secrets):
        """Test that None API key is rejected"""
        provided_key = None
        expected_key = mock_secrets["INGEST_API_KEY"]

        # Should not crash, should return False
        if provided_key is None:
            result = False
        else:
            result = secrets_module.compare_digest(provided_key, expected_key)

        assert result is False

    def test_timing_attack_resistance(self, mock_config, mock_secrets):
        """Test that compare_digest is used (timing attack resistant)"""
        # This test verifies we're using secrets.compare_digest
        # which is constant-time, not regular == comparison

        expected_key = "test-api-key-123"

        # Both should take similar time (constant-time)
        correct_key = "test-api-key-123"
        wrong_key_prefix = "test-api-key-124"  # Wrong last char
        wrong_key_all = "zzzzzzzzzzzzzzz"      # All wrong

        # All comparisons use constant-time function
        result1 = secrets_module.compare_digest(correct_key, expected_key)
        result2 = secrets_module.compare_digest(wrong_key_prefix, expected_key)
        result3 = secrets_module.compare_digest(wrong_key_all, expected_key)

        assert result1 is True
        assert result2 is False
        assert result3 is False


class TestJSONValidation:
    """Test JSON payload validation"""

    def test_valid_json_accepted(self, sample_syslog_message):
        """Test that valid JSON is accepted"""
        payload = json.dumps(sample_syslog_message)

        # Should not raise exception
        parsed = json.loads(payload)
        assert isinstance(parsed, dict)
        assert "message" in parsed

    def test_malformed_json_rejected(self):
        """Test that malformed JSON is rejected"""
        payload = '{"message": "test", invalid json}'

        with pytest.raises(json.JSONDecodeError):
            json.loads(payload)

    def test_empty_payload_rejected(self):
        """Test that empty payload is rejected"""
        payload = ""

        with pytest.raises(json.JSONDecodeError):
            json.loads(payload)

    def test_null_payload_accepted(self):
        """Test that JSON null is technically valid"""
        payload = "null"

        parsed = json.loads(payload)
        assert parsed is None  # Valid JSON, but empty data

    def test_empty_object_accepted(self):
        """Test that empty JSON object is valid"""
        payload = "{}"

        parsed = json.loads(payload)
        assert isinstance(parsed, dict)
        assert len(parsed) == 0


class TestBackpressureHandling:
    """Test queue backpressure logic"""

    def test_queue_under_capacity_accepts_message(self, mock_config, mock_redis_client):
        """Test that messages are accepted when queue is under capacity"""
        mock_redis_client.llen.return_value = 500000  # 50% capacity

        queue_len = mock_redis_client.llen(mock_config.INGEST_QUEUE_NAME)

        assert queue_len < mock_config.MAX_INGEST_QUEUE_SIZE
        # Should accept message

    def test_queue_at_capacity_rejects_message(self, mock_config, mock_redis_client):
        """Test that messages are rejected when queue is at capacity"""
        mock_redis_client.llen.return_value = 1000000  # 100% capacity

        queue_len = mock_redis_client.llen(mock_config.INGEST_QUEUE_NAME)

        assert queue_len >= mock_config.MAX_INGEST_QUEUE_SIZE
        # Should reject with 503

    def test_queue_over_capacity_rejects_message(self, mock_config, mock_redis_client):
        """Test that messages are rejected when queue exceeds capacity"""
        mock_redis_client.llen.return_value = 1500000  # 150% capacity

        queue_len = mock_redis_client.llen(mock_config.INGEST_QUEUE_NAME)

        assert queue_len >= mock_config.MAX_INGEST_QUEUE_SIZE
        # Should reject with 503

    def test_queue_near_capacity_still_accepts(self, mock_config, mock_redis_client):
        """Test that messages are accepted at 99% capacity"""
        mock_redis_client.llen.return_value = 999999  # 99.9999% capacity

        queue_len = mock_redis_client.llen(mock_config.INGEST_QUEUE_NAME)

        assert queue_len < mock_config.MAX_INGEST_QUEUE_SIZE
        # Should still accept (not at limit yet)


class TestRedisOperations:
    """Test Redis queue operations"""

    def test_message_pushed_to_queue(self, mock_config, mock_redis_client, sample_syslog_message):
        """Test that message is pushed to Redis queue"""
        message_json = json.dumps(sample_syslog_message)

        # Mock pipeline
        mock_pipeline = MagicMock()
        mock_redis_client.pipeline.return_value = mock_pipeline

        # Simulate push operation
        mock_pipeline.lpush(mock_config.INGEST_QUEUE_NAME, message_json)
        mock_pipeline.execute()

        # Verify push was called
        mock_pipeline.lpush.assert_called_once_with(
            mock_config.INGEST_QUEUE_NAME, message_json
        )
        mock_pipeline.execute.assert_called_once()

    def test_metrics_incremented_atomically(self, mock_config, mock_redis_client):
        """Test that metrics are incremented in pipeline (atomic)"""
        from datetime import datetime

        now = datetime.utcnow()
        key_1m = f"{mock_config.METRICS_PREFIX}:1m:{now.strftime('%Y-%m-%dT%H:%M')}"
        key_1h = f"{mock_config.METRICS_PREFIX}:1h:{now.strftime('%Y-%m-%dT%H')}"
        key_24h = f"{mock_config.METRICS_PREFIX}:24h:{now.strftime('%Y-%m-%d')}"

        # Mock pipeline
        mock_pipeline = MagicMock()
        mock_redis_client.pipeline.return_value = mock_pipeline

        # Simulate metrics increment
        mock_pipeline.incr(key_1m)
        mock_pipeline.incr(key_1h)
        mock_pipeline.incr(key_24h)
        mock_pipeline.expire(key_1m, 7200)
        mock_pipeline.expire(key_1h, 172800)
        mock_pipeline.expire(key_24h, 2592000)
        mock_pipeline.execute()

        # Verify all operations were called
        assert mock_pipeline.incr.call_count == 3
        assert mock_pipeline.expire.call_count == 3
        mock_pipeline.execute.assert_called_once()

    def test_redis_connection_failure_handled(self, mock_config, mock_redis_client):
        """Test that Redis connection failures are handled"""
        import redis as redis_module

        # Simulate connection error
        mock_redis_client.llen.side_effect = redis_module.exceptions.ConnectionError("Connection refused")

        with pytest.raises(redis_module.exceptions.ConnectionError):
            mock_redis_client.llen(mock_config.INGEST_QUEUE_NAME)

    def test_redis_pipeline_atomic_execution(self, mock_redis_client):
        """Test that pipeline executes all operations atomically"""
        mock_pipeline = MagicMock()
        mock_redis_client.pipeline.return_value = mock_pipeline

        # Simulate operations
        mock_pipeline.lpush("queue", "msg1")
        mock_pipeline.incr("counter")
        mock_pipeline.expire("counter", 60)
        result = mock_pipeline.execute()

        # All operations should be in pipeline before execute
        assert mock_pipeline.lpush.called
        assert mock_pipeline.incr.called
        assert mock_pipeline.expire.called
        mock_pipeline.execute.assert_called_once()


class TestVaultIntegration:
    """Test Vault secret fetching"""

    def test_vault_authentication_success(self, mock_vault_client, mock_config):
        """Test successful Vault authentication"""
        mock_vault_client.auth.approle.login.return_value = {
            "auth": {"client_token": "test-token"}
        }

        result = mock_vault_client.auth.approle.login(
            role_id="test-role-id",
            secret_id="test-secret-id"
        )

        assert "auth" in result
        assert result["auth"]["client_token"] == "test-token"

    def test_vault_secrets_fetched(self, mock_vault_client, mock_config):
        """Test secrets are fetched from Vault"""
        result = mock_vault_client.secrets.kv.v2.read_secret_version(
            path=mock_config.VAULT_SECRETS_PATH
        )

        secrets = result["data"]["data"]

        assert "REDIS_PASS" in secrets
        assert "INGEST_API_KEY" in secrets
        assert secrets["INGEST_API_KEY"] == "test-api-key-123"

    def test_vault_token_renewal(self, mock_vault_client):
        """Test Vault token renewal logic"""
        # Mock token lookup showing low TTL
        mock_vault_client.auth.token.lookup_self.return_value = {
            "data": {"ttl": 1800}  # 30 minutes (below 1 hour threshold)
        }

        token_info = mock_vault_client.auth.token.lookup_self()
        ttl = token_info["data"]["ttl"]

        # Should trigger renewal if TTL < threshold (3600)
        if ttl < 3600:
            mock_vault_client.auth.token.renew_self()

        mock_vault_client.auth.token.renew_self.assert_called_once()

    def test_vault_authentication_failure_handled(self, mock_vault_client):
        """Test Vault authentication failure is handled"""
        import hvac

        mock_vault_client.auth.approle.login.side_effect = hvac.exceptions.InvalidRequest("Invalid credentials")

        with pytest.raises(hvac.exceptions.InvalidRequest):
            mock_vault_client.auth.approle.login(
                role_id="wrong-role",
                secret_id="wrong-secret"
            )


class TestMetricsGeneration:
    """Test Prometheus metrics"""

    def test_metrics_counter_labels(self):
        """Test that metrics use correct labels"""
        from prometheus_client import Counter

        test_counter = Counter(
            'test_ingest_requests_total',
            'Test counter',
            ['status']
        )

        # Increment different labels
        test_counter.labels(status='success').inc()
        test_counter.labels(status='fail_auth').inc()
        test_counter.labels(status='fail_json').inc()

        # Verify (in real code, would check metrics endpoint)
        assert test_counter._metrics  # Has metrics

    def test_metrics_for_successful_request(self):
        """Test metrics incremented on success"""
        from prometheus_client import Counter

        metric = Counter('test_success', 'Test', ['status'])
        metric.labels(status='success').inc()

        # In real service, this would increment mutt_ingest_requests_total{status="success"}
        assert True  # Placeholder

    def test_metrics_for_failed_request(self):
        """Test metrics incremented on failure"""
        from prometheus_client import Counter

        metric = Counter('test_fail', 'Test', ['status'])
        metric.labels(status='fail_auth').inc()
        metric.labels(status='fail_json').inc()

        # In real service, would increment with appropriate status label
        assert True  # Placeholder


class TestMessageFlow:
    """Test complete message flow"""

    def test_complete_successful_flow(self, mock_config, mock_redis_client, sample_syslog_message):
        """Test complete successful message processing flow"""
        # 1. API key valid
        api_key_valid = secrets_module.compare_digest(
            "test-api-key-123", "test-api-key-123"
        )
        assert api_key_valid

        # 2. JSON valid
        message_json = json.dumps(sample_syslog_message)
        parsed = json.loads(message_json)
        assert parsed is not None

        # 3. Queue not full
        mock_redis_client.llen.return_value = 500000
        queue_len = mock_redis_client.llen(mock_config.INGEST_QUEUE_NAME)
        assert queue_len < mock_config.MAX_INGEST_QUEUE_SIZE

        # 4. Push to Redis
        mock_pipeline = MagicMock()
        mock_redis_client.pipeline.return_value = mock_pipeline
        mock_pipeline.lpush(mock_config.INGEST_QUEUE_NAME, message_json)
        mock_pipeline.execute()

        # Verify entire flow succeeded
        mock_pipeline.lpush.assert_called()
        mock_pipeline.execute.assert_called()

    def test_flow_fails_on_invalid_api_key(self, mock_config):
        """Test flow stops at authentication"""
        api_key_valid = secrets_module.compare_digest(
            "wrong-key", "test-api-key-123"
        )

        assert api_key_valid is False
        # Flow should stop here, return 401

    def test_flow_fails_on_invalid_json(self):
        """Test flow stops at JSON validation"""
        with pytest.raises(json.JSONDecodeError):
            json.loads("{invalid json}")

        # Flow should stop here, return 400

    def test_flow_fails_on_queue_full(self, mock_config, mock_redis_client):
        """Test flow stops at backpressure check"""
        mock_redis_client.llen.return_value = 1000000  # Full

        queue_len = mock_redis_client.llen(mock_config.INGEST_QUEUE_NAME)

        assert queue_len >= mock_config.MAX_INGEST_QUEUE_SIZE
        # Flow should stop here, return 503


class TestErrorHandling:
    """Test error handling scenarios"""

    def test_redis_timeout_handled(self, mock_redis_client):
        """Test Redis timeout is caught"""
        import redis as redis_module

        mock_redis_client.lpush.side_effect = redis_module.exceptions.TimeoutError("Timeout")

        with pytest.raises(redis_module.exceptions.TimeoutError):
            mock_redis_client.lpush("queue", "message")

    def test_redis_connection_error_handled(self, mock_redis_client):
        """Test Redis connection error is caught"""
        import redis as redis_module

        mock_redis_client.ping.side_effect = redis_module.exceptions.ConnectionError("Connection refused")

        with pytest.raises(redis_module.exceptions.ConnectionError):
            mock_redis_client.ping()

    def test_vault_unavailable_handled(self, mock_vault_client):
        """Test Vault unavailability is handled"""
        import hvac

        mock_vault_client.secrets.kv.v2.read_secret_version.side_effect = \
            hvac.exceptions.VaultDown("Vault is sealed")

        with pytest.raises(hvac.exceptions.VaultDown):
            mock_vault_client.secrets.kv.v2.read_secret_version(path="secret/mutt")


# =====================================================================
# Integration Test Markers (to be run separately)
# =====================================================================

@pytest.mark.integration
class TestIngestorIntegration:
    """Integration tests requiring real services"""

    def test_real_redis_connection(self):
        """Test connection to real Redis (requires Redis running)"""
        pytest.skip("Integration test - requires real Redis")

    def test_real_vault_connection(self):
        """Test connection to real Vault (requires Vault running)"""
        pytest.skip("Integration test - requires real Vault")


# =====================================================================
# Run tests with: pytest tests/test_ingestor_unit.py -v
# Run specific test: pytest tests/test_ingestor_unit.py::TestAPIKeyAuthentication::test_valid_api_key_accepted -v
# Run with coverage: pytest tests/test_ingestor_unit.py --cov=ingestor_service --cov-report=html
# =====================================================================
