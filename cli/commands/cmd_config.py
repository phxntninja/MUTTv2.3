"""
muttdev config - Manage MUTT configuration

This command provides easy access to dynamic configuration stored in Redis.
"""

import os
import sys
import redis
from typing import Optional


def register(subparsers):
    """Register the config command with argparse."""
    parser = subparsers.add_parser(
        'config',
        help='Manage dynamic configuration',
        description='View and modify MUTT dynamic configuration in Redis'
    )

    subcommands = parser.add_subparsers(dest='subcommand', help='Config subcommand')

    # list subcommand
    list_parser = subcommands.add_parser('list', help='List all configuration values')

    # get subcommand
    get_parser = subcommands.add_parser('get', help='Get a configuration value')
    get_parser.add_argument('key', help='Configuration key')

    # set subcommand
    set_parser = subcommands.add_parser('set', help='Set a configuration value')
    set_parser.add_argument('key', help='Configuration key')
    set_parser.add_argument('value', help='Configuration value')

    # delete subcommand
    delete_parser = subcommands.add_parser('delete', help='Delete a configuration key')
    delete_parser.add_argument('key', help='Configuration key')


def execute(args) -> int:
    """Execute the config command."""
    if not args.subcommand:
        print("Error: No subcommand specified")
        print("Usage: muttdev config <list|get|set|delete>")
        return 1

    # Connect to Redis
    redis_host = os.getenv('REDIS_HOST', 'localhost')
    redis_port = int(os.getenv('REDIS_PORT', '6379'))

    try:
        r = redis.Redis(host=redis_host, port=redis_port, decode_responses=True)
        r.ping()
    except Exception as e:
        print(f"Error: Could not connect to Redis at {redis_host}:{redis_port}")
        print(f"Details: {e}")
        return 1

    prefix = "mutt:config"

    if args.subcommand == 'list':
        return list_configs(r, prefix)
    elif args.subcommand == 'get':
        return get_config(r, prefix, args.key)
    elif args.subcommand == 'set':
        return set_config(r, prefix, args.key, args.value)
    elif args.subcommand == 'delete':
        return delete_config(r, prefix, args.key)

    return 0


def list_configs(r: redis.Redis, prefix: str) -> int:
    """List all configuration values."""
    print("=" * 70)
    print("MUTT Dynamic Configuration")
    print("=" * 70)
    print()

    pattern = f"{prefix}:*"
    keys = list(r.scan_iter(match=pattern))

    if not keys:
        print("No configuration values found")
        return 0

    # Group by category
    configs_by_category = {}

    for key in sorted(keys):
        key_str = key.decode('utf-8') if isinstance(key, bytes) else key
        config_key = key_str.replace(f"{prefix}:", "")

        # Skip the updates channel
        if config_key == 'updates':
            continue

        # Determine category
        category = "general"
        if config_key.startswith("ingest_"):
            category = "ingestor"
        elif config_key.startswith("alerter_"):
            category = "alerter"
        elif config_key.startswith("moog_"):
            category = "moog_forwarder"
        elif config_key.startswith("slo_"):
            category = "slo"
        elif config_key.startswith("event_") or config_key.startswith("config_audit_") or "retention" in config_key:
            category = "retention"
        elif config_key in ["cache_reload_interval", "unhandled_threshold", "unhandled_expiry_seconds"]:
            category = "alerter"

        if category not in configs_by_category:
            configs_by_category[category] = []

        value = r.get(key)
        if isinstance(value, bytes):
            value = value.decode('utf-8')

        configs_by_category[category].append((config_key, value))

    # Print grouped configs
    for category in sorted(configs_by_category.keys()):
        print(f"[{category.upper()}]")
        for key, value in sorted(configs_by_category[category]):
            print(f"  {key} = {value}")
        print()

    total = sum(len(v) for v in configs_by_category.values())
    print(f"Total: {total} configuration values")

    return 0


def get_config(r: redis.Redis, prefix: str, key: str) -> int:
    """Get a single configuration value."""
    redis_key = f"{prefix}:{key}"
    value = r.get(redis_key)

    if value is None:
        print(f"Error: Configuration key '{key}' not found")
        return 1

    if isinstance(value, bytes):
        value = value.decode('utf-8')

    print(f"{key} = {value}")
    return 0


def set_config(r: redis.Redis, prefix: str, key: str, value: str) -> int:
    """Set a configuration value."""
    redis_key = f"{prefix}:{key}"

    # Get old value if exists
    old_value = r.get(redis_key)
    if old_value and isinstance(old_value, bytes):
        old_value = old_value.decode('utf-8')

    # Set new value
    r.set(redis_key, value)

    # Publish change notification
    r.publish(f"{prefix}:updates", key)

    if old_value:
        print(f"✓ Updated '{key}'")
        print(f"  Old: {old_value}")
        print(f"  New: {value}")
    else:
        print(f"✓ Set '{key}' = {value}")

    print()
    print("Note: All running services will pick up this change within ~5 seconds")

    return 0


def delete_config(r: redis.Redis, prefix: str, key: str) -> int:
    """Delete a configuration key."""
    redis_key = f"{prefix}:{key}"

    # Check if exists
    if not r.exists(redis_key):
        print(f"Error: Configuration key '{key}' not found")
        return 1

    # Get value before deleting
    old_value = r.get(redis_key)
    if isinstance(old_value, bytes):
        old_value = old_value.decode('utf-8')

    # Delete
    r.delete(redis_key)

    # Publish change notification
    r.publish(f"{prefix}:updates", key)

    print(f"✓ Deleted '{key}' (was: {old_value})")
    print()
    print("Note: Services will revert to environment variable or hardcoded defaults")

    return 0
