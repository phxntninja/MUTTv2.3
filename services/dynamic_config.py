#!/usr/bin/env python3
"""
MUTT v2.5 - Dynamic Configuration System

This module provides runtime configuration management using Redis as a backend.
Enables zero-downtime configuration changes without service restarts.

Key Features:
- Redis-backed configuration storage
- Local caching with TTL (5 seconds)
- PubSub for cache invalidation
- Background watcher thread for automatic updates
- Graceful fallback to defaults

Usage:
    from dynamic_config import DynamicConfig

    # Initialize
    config = DynamicConfig(redis_client, prefix="mutt:config")

    # Get configuration value (with caching)
    cache_interval = int(config.get('cache_reload_interval', default='300'))

    # Set configuration value (invalidates cache across all services)
    config.set('cache_reload_interval', '600')

    # Start background watcher for automatic updates
    config.start_watcher()

Author: MUTT Development Team
License: MIT
Version: 2.5.0
"""

import logging
import threading
import time
from typing import Any, Optional, Dict, Callable

logger = logging.getLogger(__name__)


class DynamicConfigError(Exception):
    """Raised when dynamic configuration operations fail."""
    pass


class DynamicConfig:
    """
    Dynamic configuration manager with Redis backend and local caching.

    This class provides runtime configuration management that allows services
    to change configuration values without restarting. Changes are propagated
    to all service instances via Redis PubSub.

    Attributes:
        redis: Redis client instance
        prefix: Key prefix for all config keys (default: "mutt:config")
        cache: Local cache dictionary with TTL
        cache_ttl: Time-to-live for local cache in seconds (default: 5)
        watcher_thread: Background thread for PubSub watching
        watcher_running: Flag to control watcher thread
        change_callbacks: Registered callbacks for config changes
    """

    def __init__(
        self,
        redis_client,
        prefix: str = "mutt:config",
        cache_ttl: int = 5
    ):
        """
        Initialize dynamic configuration manager.

        Args:
            redis_client: Redis client instance (redis.Redis)
            prefix: Prefix for all config keys in Redis (default: "mutt:config")
            cache_ttl: Local cache TTL in seconds (default: 5)

        Example:
            >>> import redis
            >>> r = redis.Redis(host='localhost', port=6379, db=0)
            >>> config = DynamicConfig(r, prefix="mutt:config")
        """
        self.redis = redis_client
        self.prefix = prefix
        self.cache_ttl = cache_ttl
        self.cache: Dict[str, Dict[str, Any]] = {}
        self.cache_lock = threading.Lock()

        # Watcher thread for PubSub
        self.watcher_thread: Optional[threading.Thread] = None
        self.watcher_running = False

        # Callbacks for config changes
        self.change_callbacks: Dict[str, list] = {}
        self.callbacks_lock = threading.Lock()

        # Load all config from Redis on startup
        self.load_all()

        logger.info(
            f"DynamicConfig initialized: prefix={prefix}, "
            f"cache_ttl={cache_ttl}s"
        )

    def get(self, key: str, default: Optional[str] = None) -> str:
        """
        Get configuration value with local caching.

        First checks local cache (5s TTL), then fetches from Redis if cache miss.
        Returns default if key not found in Redis.

        Args:
            key: Configuration key name (without prefix)
            default: Default value if key not found

        Returns:
            Configuration value as string, or default if not found

        Raises:
            KeyError: If key not found and no default provided
            DynamicConfigError: If Redis operation fails

        Example:
            >>> config.get('cache_reload_interval', default='300')
            '600'
        """
        # Check local cache first
        with self.cache_lock:
            if key in self.cache:
                cache_entry = self.cache[key]
                # Check if cache entry is still valid (TTL not expired)
                if time.time() - cache_entry['timestamp'] < self.cache_ttl:
                    logger.debug(f"Config cache hit: {key}={cache_entry['value']}")
                    return cache_entry['value']

        # Cache miss - fetch from Redis
        try:
            redis_key = f"{self.prefix}:{key}"
            value = self.redis.get(redis_key)

            if value is not None:
                # Decode bytes to string
                value = value.decode('utf-8') if isinstance(value, bytes) else value

                # Update local cache
                with self.cache_lock:
                    self.cache[key] = {
                        'value': value,
                        'timestamp': time.time()
                    }

                logger.debug(f"Config loaded from Redis: {key}={value}")
                return value

            # Key not found in Redis
            if default is not None:
                logger.debug(f"Config not found, using default: {key}={default}")
                return default

            raise KeyError(f"Configuration key not found: {key}")

        except Exception as e:
            if isinstance(e, KeyError):
                raise
            logger.error(f"Failed to get config {key} from Redis: {e}")
            raise DynamicConfigError(f"Failed to get config {key}: {e}") from e

    def set(self, key: str, value: str, notify: bool = True) -> None:
        """
        Set configuration value in Redis and update local cache.

        Optionally publishes change notification via PubSub to invalidate
        caches in all service instances.

        Args:
            key: Configuration key name (without prefix)
            value: Configuration value (will be converted to string)
            notify: If True, publish change notification via PubSub (default: True)

        Raises:
            DynamicConfigError: If Redis operation fails

        Example:
            >>> config.set('cache_reload_interval', '600')
            >>> # All services will invalidate their cache and reload this value
        """
        try:
            redis_key = f"{self.prefix}:{key}"
            str_value = str(value)

            # Set in Redis
            self.redis.set(redis_key, str_value)

            # Update local cache
            with self.cache_lock:
                self.cache[key] = {
                    'value': str_value,
                    'timestamp': time.time()
                }

            logger.info(f"Config updated: {key}={str_value}")

            # Publish change notification
            if notify:
                self._publish_change(key)

            # Trigger callbacks
            self._trigger_callbacks(key, str_value)

        except Exception as e:
            logger.error(f"Failed to set config {key}={value}: {e}")
            raise DynamicConfigError(f"Failed to set config {key}: {e}") from e

    def delete(self, key: str, notify: bool = True) -> None:
        """
        Delete configuration key from Redis and local cache.

        Args:
            key: Configuration key name (without prefix)
            notify: If True, publish change notification via PubSub (default: True)

        Raises:
            DynamicConfigError: If Redis operation fails
        """
        try:
            redis_key = f"{self.prefix}:{key}"

            # Delete from Redis
            self.redis.delete(redis_key)

            # Remove from local cache
            with self.cache_lock:
                self.cache.pop(key, None)

            logger.info(f"Config deleted: {key}")

            # Publish change notification
            if notify:
                self._publish_change(key)

        except Exception as e:
            logger.error(f"Failed to delete config {key}: {e}")
            raise DynamicConfigError(f"Failed to delete config {key}: {e}") from e

    def load_all(self) -> int:
        """
        Load all configuration from Redis on startup.

        Scans for all keys with the configured prefix and loads them into
        local cache.

        Returns:
            Number of config keys loaded

        Example:
            >>> count = config.load_all()
            >>> print(f"Loaded {count} config values")
        """
        count = 0
        try:
            pattern = f"{self.prefix}:*"

            # Use SCAN for large keysets (non-blocking)
            for redis_key in self.redis.scan_iter(match=pattern, count=100):
                # Extract key name (remove prefix and ':updates' suffix)
                key_str = redis_key.decode('utf-8') if isinstance(redis_key, bytes) else redis_key
                key_name = key_str.replace(f"{self.prefix}:", "")

                # Skip PubSub channel
                if key_name == 'updates':
                    continue

                # Get value
                value = self.redis.get(redis_key)
                if value:
                    value = value.decode('utf-8') if isinstance(value, bytes) else value

                    with self.cache_lock:
                        self.cache[key_name] = {
                            'value': value,
                            'timestamp': time.time()
                        }
                    count += 1

            logger.info(f"Loaded {count} config values from Redis")
            return count

        except Exception as e:
            logger.error(f"Failed to load config from Redis: {e}")
            raise DynamicConfigError(f"Failed to load config: {e}") from e

    def get_all(self) -> Dict[str, str]:
        """
        Get all configuration values as a dictionary.

        Returns:
            Dictionary of all config key-value pairs

        Example:
            >>> all_config = config.get_all()
            >>> print(all_config)
            {'cache_reload_interval': '600', 'max_queue_size': '100000'}
        """
        result = {}
        with self.cache_lock:
            for key, entry in self.cache.items():
                result[key] = entry['value']
        return result

    def invalidate_cache(self, key: str) -> None:
        """
        Invalidate local cache for a specific key.

        Forces next get() to fetch from Redis.

        Args:
            key: Configuration key to invalidate
        """
        with self.cache_lock:
            self.cache.pop(key, None)
        logger.debug(f"Cache invalidated: {key}")

    def _publish_change(self, key: str) -> None:
        """
        Publish configuration change notification via PubSub.

        All service instances subscribed to the updates channel will
        invalidate their cache for this key.

        Args:
            key: Configuration key that changed
        """
        try:
            channel = f"{self.prefix}:updates"
            self.redis.publish(channel, key)
            logger.debug(f"Published config change: {key}")
        except Exception as e:
            logger.warning(f"Failed to publish config change for {key}: {e}")

    def register_callback(self, key: str, callback: Callable[[str, str], None]) -> None:
        """
        Register a callback to be called when a config value changes.

        Args:
            key: Configuration key to watch
            callback: Function to call with (key, new_value) when changed

        Example:
            >>> def on_cache_interval_change(key, value):
            ...     print(f"Cache interval changed to {value}")
            >>> config.register_callback('cache_reload_interval', on_cache_interval_change)
        """
        with self.callbacks_lock:
            if key not in self.change_callbacks:
                self.change_callbacks[key] = []
            self.change_callbacks[key].append(callback)
        logger.debug(f"Registered callback for config key: {key}")

    def _trigger_callbacks(self, key: str, value: str) -> None:
        """
        Trigger all registered callbacks for a config key.

        Args:
            key: Configuration key that changed
            value: New value
        """
        with self.callbacks_lock:
            callbacks = self.change_callbacks.get(key, [])

        for callback in callbacks:
            try:
                callback(key, value)
            except Exception as e:
                logger.error(f"Error in config change callback for {key}: {e}")

    def start_watcher(self) -> None:
        """
        Start background watcher thread for PubSub notifications.

        The watcher subscribes to config change notifications and automatically
        invalidates local cache when other services update config.

        This enables instant propagation of config changes across all service instances.

        Example:
            >>> config.start_watcher()
            >>> # Now this service will automatically see config changes from other services
        """
        if self.watcher_running:
            logger.warning("Config watcher already running")
            return

        self.watcher_running = True
        self.watcher_thread = threading.Thread(
            target=self._watch_config_changes,
            name="DynamicConfig-Watcher",
            daemon=True
        )
        self.watcher_thread.start()
        logger.info("Config watcher thread started")

    def stop_watcher(self) -> None:
        """
        Stop background watcher thread gracefully.

        Example:
            >>> config.stop_watcher()
        """
        if not self.watcher_running:
            return

        self.watcher_running = False
        if self.watcher_thread:
            self.watcher_thread.join(timeout=5)
        logger.info("Config watcher thread stopped")

    def _watch_config_changes(self) -> None:
        """
        Background thread function to watch for config changes via PubSub.

        Subscribes to the updates channel and invalidates local cache
        when changes are published by other services.
        """
        channel = f"{self.prefix}:updates"
        logger.info(f"Config watcher subscribing to: {channel}")

        try:
            pubsub = self.redis.pubsub()
            pubsub.subscribe(channel)

            # Listen for messages
            for message in pubsub.listen():
                if not self.watcher_running:
                    break

                if message['type'] == 'message':
                    key = message['data']
                    if isinstance(key, bytes):
                        key = key.decode('utf-8')

                    logger.info(f"Config change detected: {key}")
                    self.invalidate_cache(key)

        except Exception as e:
            logger.error(f"Config watcher error: {e}", exc_info=True)
        finally:
            try:
                pubsub.unsubscribe()
                pubsub.close()
            except:
                pass
            logger.info("Config watcher exited")


if __name__ == "__main__":
    # Example usage
    print("MUTT v2.5 Dynamic Configuration")
    print("=" * 60)
    print("\nThis module provides runtime configuration management.")
    print("\nUsage:")
    print("  from dynamic_config import DynamicConfig")
    print("\nSee module docstring for examples.")
