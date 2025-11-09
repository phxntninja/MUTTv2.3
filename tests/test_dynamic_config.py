#!/usr/bin/env python3
"""
MUTT v2.5 - Dynamic Config Unit Tests

Tests for the dynamic configuration module.

Run with:
    pytest tests/test_dynamic_config.py -v
    pytest tests/test_dynamic_config.py -v --cov=services.dynamic_config
"""

import pytest
import time
from unittest.mock import Mock, MagicMock, patch, call
import sys
import os

# Add services directory to path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'services'))

from dynamic_config import DynamicConfig, DynamicConfigError


class TestDynamicConfigInit:
    """Test suite for DynamicConfig initialization"""

    def test_init_success(self):
        """Test successful initialization"""
        mock_redis = Mock()
        mock_redis.scan_iter.return_value = []

        config = DynamicConfig(mock_redis, prefix="test:config", cache_ttl=10)

        assert config.redis == mock_redis
        assert config.prefix == "test:config"
        assert config.cache_ttl == 10
        assert config.cache == {}
        assert not config.watcher_running

    def test_init_loads_existing_config(self):
        """Test that initialization loads existing config from Redis"""
        mock_redis = Mock()
        mock_redis.scan_iter.return_value = [
            b'test:config:key1',
            b'test:config:key2'
        ]
        mock_redis.get.side_effect = [b'value1', b'value2']

        config = DynamicConfig(mock_redis, prefix="test:config")

        assert len(config.cache) == 2
        assert config.cache['key1']['value'] == 'value1'
        assert config.cache['key2']['value'] == 'value2'


class TestDynamicConfigGet:
    """Test suite for DynamicConfig.get()"""

    def test_get_from_cache_success(self):
        """Test getting value from cache (cache hit)"""
        mock_redis = Mock()
        mock_redis.scan_iter.return_value = []

        config = DynamicConfig(mock_redis)

        # Pre-populate cache
        config.cache['test_key'] = {
            'value': 'cached_value',
            'timestamp': time.time()
        }

        value = config.get('test_key')

        assert value == 'cached_value'
        # Redis should not be called (cache hit)
        mock_redis.get.assert_not_called()

    def test_get_from_redis_on_cache_miss(self):
        """Test getting value from Redis when cache miss"""
        mock_redis = Mock()
        mock_redis.scan_iter.return_value = []
        mock_redis.get.return_value = b'redis_value'

        config = DynamicConfig(mock_redis, prefix="test")

        value = config.get('test_key')

        assert value == 'redis_value'
        mock_redis.get.assert_called_once_with('test:test_key')

        # Value should now be in cache
        assert 'test_key' in config.cache
        assert config.cache['test_key']['value'] == 'redis_value'

    def test_get_returns_default_when_not_found(self):
        """Test that default is returned when key not found"""
        mock_redis = Mock()
        mock_redis.scan_iter.return_value = []
        mock_redis.get.return_value = None

        config = DynamicConfig(mock_redis)

        value = config.get('missing_key', default='default_value')

        assert value == 'default_value'

    def test_get_raises_keyerror_when_not_found_and_no_default(self):
        """Test that KeyError is raised when key not found and no default"""
        mock_redis = Mock()
        mock_redis.scan_iter.return_value = []
        mock_redis.get.return_value = None

        config = DynamicConfig(mock_redis)

        with pytest.raises(KeyError, match="Configuration key not found"):
            config.get('missing_key')

    def test_get_cache_expiry(self):
        """Test that cache expires after TTL"""
        mock_redis = Mock()
        mock_redis.scan_iter.return_value = []
        mock_redis.get.return_value = b'fresh_value'

        config = DynamicConfig(mock_redis, cache_ttl=1)

        # Pre-populate cache with old timestamp
        config.cache['test_key'] = {
            'value': 'old_value',
            'timestamp': time.time() - 2  # 2 seconds ago (expired)
        }

        value = config.get('test_key')

        # Should fetch from Redis (cache expired)
        assert value == 'fresh_value'
        mock_redis.get.assert_called_once()

    def test_get_handles_redis_error(self):
        """Test that Redis errors are handled properly"""
        mock_redis = Mock()
        mock_redis.scan_iter.return_value = []
        mock_redis.get.side_effect = Exception("Redis connection failed")

        config = DynamicConfig(mock_redis)

        with pytest.raises(DynamicConfigError, match="Failed to get config"):
            config.get('test_key')


class TestDynamicConfigSet:
    """Test suite for DynamicConfig.set()"""

    def test_set_success(self):
        """Test setting config value successfully"""
        mock_redis = Mock()
        mock_redis.scan_iter.return_value = []

        config = DynamicConfig(mock_redis, prefix="test")

        config.set('test_key', 'new_value')

        # Should set in Redis
        mock_redis.set.assert_called_once_with('test:test_key', 'new_value')

        # Should publish change notification
        mock_redis.publish.assert_called_once_with('test:updates', 'test_key')

        # Should update local cache
        assert config.cache['test_key']['value'] == 'new_value'

    def test_set_without_notification(self):
        """Test setting config value without PubSub notification"""
        mock_redis = Mock()
        mock_redis.scan_iter.return_value = []

        config = DynamicConfig(mock_redis)

        config.set('test_key', 'value', notify=False)

        mock_redis.set.assert_called_once()
        # Should NOT publish
        mock_redis.publish.assert_not_called()

    def test_set_converts_value_to_string(self):
        """Test that set() converts non-string values to strings"""
        mock_redis = Mock()
        mock_redis.scan_iter.return_value = []

        config = DynamicConfig(mock_redis, prefix="test")

        # Set integer
        config.set('int_key', 123)
        mock_redis.set.assert_called_with('test:int_key', '123')

        # Set boolean
        config.set('bool_key', True)
        mock_redis.set.assert_called_with('test:bool_key', 'True')

    def test_set_handles_redis_error(self):
        """Test that Redis errors on set are handled"""
        mock_redis = Mock()
        mock_redis.scan_iter.return_value = []
        mock_redis.set.side_effect = Exception("Redis write failed")

        config = DynamicConfig(mock_redis)

        with pytest.raises(DynamicConfigError, match="Failed to set config"):
            config.set('test_key', 'value')


class TestDynamicConfigDelete:
    """Test suite for DynamicConfig.delete()"""

    def test_delete_success(self):
        """Test deleting config key successfully"""
        mock_redis = Mock()
        mock_redis.scan_iter.return_value = []

        config = DynamicConfig(mock_redis, prefix="test")

        # Pre-populate cache
        config.cache['test_key'] = {'value': 'value', 'timestamp': time.time()}

        config.delete('test_key')

        # Should delete from Redis
        mock_redis.delete.assert_called_once_with('test:test_key')

        # Should remove from cache
        assert 'test_key' not in config.cache

        # Should publish change notification
        mock_redis.publish.assert_called_once_with('test:updates', 'test_key')


class TestDynamicConfigGetAll:
    """Test suite for DynamicConfig.get_all()"""

    def test_get_all_success(self):
        """Test getting all config values"""
        mock_redis = Mock()
        mock_redis.scan_iter.return_value = []

        config = DynamicConfig(mock_redis)

        # Pre-populate cache
        config.cache = {
            'key1': {'value': 'value1', 'timestamp': time.time()},
            'key2': {'value': 'value2', 'timestamp': time.time()}
        }

        result = config.get_all()

        assert result == {'key1': 'value1', 'key2': 'value2'}


class TestDynamicConfigCallbacks:
    """Test suite for config change callbacks"""

    def test_register_callback(self):
        """Test registering a callback for config changes"""
        mock_redis = Mock()
        mock_redis.scan_iter.return_value = []

        config = DynamicConfig(mock_redis)

        callback = Mock()
        config.register_callback('test_key', callback)

        # Set value to trigger callback
        config.set('test_key', 'new_value')

        # Callback should be called
        callback.assert_called_once_with('test_key', 'new_value')

    def test_multiple_callbacks_for_same_key(self):
        """Test multiple callbacks for the same key"""
        mock_redis = Mock()
        mock_redis.scan_iter.return_value = []

        config = DynamicConfig(mock_redis)

        callback1 = Mock()
        callback2 = Mock()

        config.register_callback('test_key', callback1)
        config.register_callback('test_key', callback2)

        config.set('test_key', 'value')

        # Both callbacks should be called
        callback1.assert_called_once_with('test_key', 'value')
        callback2.assert_called_once_with('test_key', 'value')

    def test_callback_error_doesnt_break_execution(self):
        """Test that callback errors don't break config set"""
        mock_redis = Mock()
        mock_redis.scan_iter.return_value = []

        config = DynamicConfig(mock_redis)

        # Callback that raises exception
        failing_callback = Mock(side_effect=Exception("Callback error"))
        config.register_callback('test_key', failing_callback)

        # Should not raise (error should be logged)
        config.set('test_key', 'value')

        # Value should still be set
        assert config.cache['test_key']['value'] == 'value'


class TestDynamicConfigInvalidateCache:
    """Test suite for cache invalidation"""

    def test_invalidate_cache(self):
        """Test manual cache invalidation"""
        mock_redis = Mock()
        mock_redis.scan_iter.return_value = []

        config = DynamicConfig(mock_redis)

        # Pre-populate cache
        config.cache['test_key'] = {'value': 'value', 'timestamp': time.time()}

        config.invalidate_cache('test_key')

        # Cache should be cleared
        assert 'test_key' not in config.cache


class TestDynamicConfigWatcher:
    """Test suite for config watcher thread"""

    def test_start_watcher(self):
        """Test starting the watcher thread"""
        mock_redis = Mock()
        mock_redis.scan_iter.return_value = []

        config = DynamicConfig(mock_redis)

        config.start_watcher()

        assert config.watcher_running is True
        assert config.watcher_thread is not None
        assert config.watcher_thread.is_alive()

        # Clean up
        config.stop_watcher()

    def test_stop_watcher(self):
        """Test stopping the watcher thread"""
        mock_redis = Mock()
        mock_redis.scan_iter.return_value = []

        config = DynamicConfig(mock_redis)

        config.start_watcher()
        config.stop_watcher()

        assert config.watcher_running is False

    def test_start_watcher_already_running(self):
        """Test that starting watcher twice doesn't create duplicate threads"""
        mock_redis = Mock()
        mock_redis.scan_iter.return_value = []

        config = DynamicConfig(mock_redis)

        config.start_watcher()
        first_thread = config.watcher_thread

        config.start_watcher()  # Try again

        # Should be same thread
        assert config.watcher_thread == first_thread

        # Clean up
        config.stop_watcher()


if __name__ == '__main__':
    pytest.main([__file__, '-v', '--cov=services.dynamic_config'])
