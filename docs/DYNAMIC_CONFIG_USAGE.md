# Dynamic Configuration Usage Guide

**MUTT v2.5** - Zero-Downtime Configuration Management

---

## Overview

The Dynamic Configuration system enables runtime configuration changes without service restarts. All configuration is stored in Redis and synchronized across all service instances via PubSub.

### Key Benefits

- ✅ **Zero-downtime config changes** - Update settings while services run
- ✅ **Instant propagation** - Changes visible across all instances within seconds
- ✅ **Automatic caching** - 5-second local cache for performance
- ✅ **Change notifications** - React to config changes with callbacks
- ✅ **Thread-safe** - Safe for concurrent access

---

## Quick Start

### 1. Initialize DynamicConfig

```python
from dynamic_config import DynamicConfig
import redis

# Connect to Redis
redis_client = redis.Redis(
    host=os.getenv('REDIS_HOST', 'localhost'),
    port=int(os.getenv('REDIS_PORT', 6379)),
    db=0,
    decode_responses=False
)

# Create config instance
config = DynamicConfig(
    redis_client,
    prefix="mutt:config",  # All keys will be mutt:config:*
    cache_ttl=5  # Local cache TTL in seconds
)

# Start background watcher (enables PubSub updates)
config.start_watcher()
```

### 2. Get Configuration Values

```python
# Get with default fallback
cache_interval = int(config.get('cache_reload_interval', default='300'))

# Get without default (raises KeyError if not found)
try:
    api_key = config.get('api_key')
except KeyError:
    print("API key not configured")

# Get all config as dict
all_config = config.get_all()
print(all_config)
```

### 3. Set Configuration Values

```python
# Set value (broadcasts to all services)
config.set('cache_reload_interval', '600')

# Set without broadcasting (local only)
config.set('debug_mode', 'true', notify=False)
```

### 4. React to Config Changes

```python
# Register callback for specific key
def on_cache_interval_change(key, new_value):
    global CACHE_RELOAD_INTERVAL
    CACHE_RELOAD_INTERVAL = int(new_value)
    print(f"Cache interval updated to {new_value}s")

config.register_callback('cache_reload_interval', on_cache_interval_change)

# Now when ANY service calls config.set('cache_reload_interval', 'X'),
# this callback will be triggered automatically
```

---

## Integration Examples

### Example 1: Ingestor Service

Replace static env vars with dynamic config:

**Before (v2.3):**
```python
# Static configuration (requires restart)
CACHE_RELOAD_INTERVAL = int(os.getenv('CACHE_RELOAD_INTERVAL', '300'))
MAX_INGEST_QUEUE_SIZE = int(os.getenv('MAX_INGEST_QUEUE_SIZE', '100000'))
```

**After (v2.5):**
```python
from dynamic_config import DynamicConfig

# Initialize dynamic config
config = DynamicConfig(redis_client, prefix="mutt:config")
config.start_watcher()

# Get values dynamically (cached for 5s)
def get_cache_interval():
    return int(config.get('cache_reload_interval', default='300'))

def get_max_queue_size():
    return int(config.get('max_ingest_queue_size', default='100000'))

# Use in code
while True:
    cache_interval = get_cache_interval()  # Re-checks every 5s
    # ... rest of logic
```

### Example 2: Alerter Service

Use callbacks for immediate config updates:

```python
from dynamic_config import DynamicConfig

# Global config values
CACHE_RELOAD_INTERVAL = 300
RULE_CACHE = {}

# Initialize
config = DynamicConfig(redis_client, prefix="mutt:config")

# Register callback to update global var immediately
def update_cache_interval(key, value):
    global CACHE_RELOAD_INTERVAL, RULE_CACHE
    CACHE_RELOAD_INTERVAL = int(value)
    RULE_CACHE.clear()  # Force reload with new interval
    logger.info(f"Cache interval updated to {value}s, cache cleared")

config.register_callback('cache_reload_interval', update_cache_interval)
config.start_watcher()

# Now config changes are instant (no 5s cache delay for callbacks)
```

### Example 3: Moog Forwarder Service

Dynamic rate limiting:

```python
from dynamic_config import DynamicConfig

config = DynamicConfig(redis_client, prefix="mutt:config")
config.start_watcher()

# Rate limiter checks config dynamically
def should_rate_limit():
    rate_limit = int(config.get('moog_rate_limit', default='100'))
    current_rate = redis_client.incr('mutt:moog:rate')

    if current_rate == 1:
        redis_client.expire('mutt:moog:rate', 1)

    return current_rate > rate_limit

# Operators can adjust rate limit without restart:
# redis-cli SET mutt:config:moog_rate_limit 200
```

---

## Configuration Management API

### Web UI Endpoints

Add these to `web_ui_service.py`:

```python
@app.route('/api/v1/config', methods=['GET'])
@require_api_key_or_session
def get_all_config():
    """Get all configuration values."""
    all_config = config.get_all()
    return jsonify({
        "config": all_config,
        "count": len(all_config)
    })

@app.route('/api/v1/config/<key>', methods=['GET'])
@require_api_key_or_session
def get_config_value(key):
    """Get specific configuration value."""
    try:
        value = config.get(key)
        return jsonify({"key": key, "value": value})
    except KeyError:
        return jsonify({"error": f"Config key not found: {key}"}), 404

@app.route('/api/v1/config/<key>', methods=['PUT'])
@require_api_key_or_session
def update_config_value(key):
    """Update configuration value."""
    data = request.get_json()
    value = data.get('value')

    if value is None:
        return jsonify({"error": "Missing 'value' in request"}), 400

    # Update config
    config.set(key, value)

    # Log to audit trail
    log_config_change(
        conn=get_db_connection(),
        changed_by=get_current_user(),
        operation='UPDATE',
        table_name='runtime_config',
        record_id=hash(key),
        old_values={'key': key},
        new_values={'key': key, 'value': value},
        reason=data.get('reason'),
        correlation_id=get_correlation_id()
    )

    return jsonify({
        "key": key,
        "value": value,
        "message": "Configuration updated successfully"
    })

@app.route('/api/v1/config/<key>', methods=['DELETE'])
@require_api_key_or_session
def delete_config_value(key):
    """Delete configuration value."""
    config.delete(key)
    return jsonify({"message": f"Configuration deleted: {key}"})
```

---

## Command-Line Management

### Using muttctl (Future)

```bash
# Get config value
muttctl config get cache_reload_interval

# Set config value
muttctl config set cache_reload_interval 600

# List all config
muttctl config list

# Delete config
muttctl config delete old_setting
```

### Using Redis CLI (Current)

```bash
# Get value
redis-cli GET mutt:config:cache_reload_interval

# Set value (all services will see it within 5s)
redis-cli SET mutt:config:cache_reload_interval 600

# Publish change notification (force immediate update)
redis-cli PUBLISH mutt:config:updates cache_reload_interval

# List all config keys
redis-cli KEYS mutt:config:*

# Delete config
redis-cli DEL mutt:config:old_setting
```

---

## Initial Configuration Setup

### Script: `scripts/init_dynamic_config.py`

Load env vars into Redis on first deployment:

```python
#!/usr/bin/env python3
"""Initialize dynamic config from environment variables."""

import os
import redis
from dynamic_config import DynamicConfig

# Connect to Redis
r = redis.Redis(
    host=os.getenv('REDIS_HOST', 'localhost'),
    port=int(os.getenv('REDIS_PORT', 6379)),
    db=0
)

config = DynamicConfig(r, prefix="mutt:config")

# Load from environment
config_mappings = {
    'cache_reload_interval': os.getenv('CACHE_RELOAD_INTERVAL', '300'),
    'max_ingest_queue_size': os.getenv('MAX_INGEST_QUEUE_SIZE', '100000'),
    'moog_rate_limit': os.getenv('MOOG_RATE_LIMIT', '100'),
    'moog_batch_size': os.getenv('MOOG_BATCH_SIZE', '100'),
}

for key, value in config_mappings.items():
    config.set(key, value, notify=False)
    print(f"✅ Set {key} = {value}")

print(f"\n✅ Initialized {len(config_mappings)} config values in Redis")
```

Run on deployment:
```bash
python scripts/init_dynamic_config.py
```

---

## Best Practices

### 1. Use Defaults

Always provide defaults to prevent crashes when config not set:

```python
# Good
cache_interval = int(config.get('cache_reload_interval', default='300'))

# Bad (will crash if not set)
cache_interval = int(config.get('cache_reload_interval'))
```

### 2. Type Conversion

Config values are always strings - convert as needed:

```python
# Integer
max_queue = int(config.get('max_queue_size', default='100000'))

# Boolean
debug_mode = config.get('debug_mode', default='false').lower() == 'true'

# Float
timeout = float(config.get('timeout_seconds', default='30.0'))
```

### 3. Validate Changes

Validate config before applying:

```python
def update_rate_limit(key, value):
    try:
        rate = int(value)
        if rate < 1 or rate > 10000:
            logger.error(f"Invalid rate limit: {value}")
            return

        global MOOG_RATE_LIMIT
        MOOG_RATE_LIMIT = rate
        logger.info(f"Rate limit updated to {rate}")
    except ValueError:
        logger.error(f"Invalid rate limit value: {value}")

config.register_callback('moog_rate_limit', update_rate_limit)
```

### 4. Start Watcher Early

Start watcher during service initialization:

```python
def init_service():
    # Initialize Redis
    redis_client = connect_to_redis()

    # Initialize config
    config = DynamicConfig(redis_client)
    config.start_watcher()  # Start immediately

    # Register callbacks
    setup_config_callbacks(config)

    # Load initial values
    load_initial_config(config)
```

### 5. Graceful Shutdown

Stop watcher on shutdown:

```python
import signal

def shutdown_handler(signum, frame):
    logger.info("Shutting down...")
    config.stop_watcher()
    # ... other cleanup
    sys.exit(0)

signal.signal(signal.SIGTERM, shutdown_handler)
signal.signal(signal.SIGINT, shutdown_handler)
```

---

## Troubleshooting

### Config Changes Not Propagating

**Problem:** Changed config in one service but others don't see it

**Solutions:**
1. Check watcher is running: `config.watcher_running` should be `True`
2. Check Redis connection: `redis-cli PING`
3. Check PubSub channel: `redis-cli PSUBSCRIBE mutt:config:updates`
4. Wait 5 seconds (local cache TTL)

### High Redis Load

**Problem:** Too many Redis GET requests

**Solutions:**
1. Increase cache_ttl: `DynamicConfig(redis_client, cache_ttl=10)`
2. Don't call `config.get()` in tight loops
3. Cache values locally when appropriate

### Config Reset After Restart

**Problem:** Config values disappear after Redis restart

**Solutions:**
1. Enable Redis persistence (AOF or RDB)
2. Run init script on deployment: `scripts/init_dynamic_config.py`
3. Store critical config in both Redis and env vars

---

## Migration from v2.3 to v2.5

### Step 1: Add DynamicConfig to Service

```python
# Add to existing service
from dynamic_config import DynamicConfig

# After Redis connection
config = DynamicConfig(redis_client, prefix="mutt:config")
config.start_watcher()
```

### Step 2: Replace Static Config

```python
# Before
CACHE_RELOAD_INTERVAL = int(os.getenv('CACHE_RELOAD_INTERVAL', '300'))

# After
def get_cache_interval():
    return int(config.get('cache_reload_interval', default='300'))
```

### Step 3: Initialize Config

```bash
# Run once on deployment
python scripts/init_dynamic_config.py
```

### Step 4: Update and Test

```bash
# Test config update
redis-cli SET mutt:config:cache_reload_interval 600

# Verify service sees change (check logs)
docker-compose logs -f ingestor
```

---

## Summary

Dynamic configuration enables:
- ✅ **Zero-downtime updates** - No service restarts needed
- ✅ **Instant propagation** - All instances updated within seconds
- ✅ **Audit trail** - All changes logged for compliance
- ✅ **API management** - Web UI for easy configuration
- ✅ **Production-ready** - Thread-safe, cached, tested

**Next:** See `V2.5_IMPLEMENTATION_PLAN.md` for Phase 2 integration tasks
