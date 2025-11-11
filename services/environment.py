import os

def get_database_config():
    """
    Returns a dictionary with the database configuration.
    """
    return {
        "host": os.environ.get("POSTGRES_HOST", "localhost"),
        "port": int(os.environ.get("POSTGRES_PORT", 5432)),
        "database": os.environ.get("POSTGRES_DB", "mutt"),
        "user": os.environ.get("POSTGRES_USER", "mutt_user"),
        "password": os.environ.get("POSTGRES_PASSWORD", "mutt_password"),
    }

def get_redis_config():
    """
    Returns a dictionary with the Redis configuration.
    """
    return {
        "host": os.environ.get("REDIS_HOST", "localhost"),
        "port": int(os.environ.get("REDIS_PORT", 6379)),
        "db": int(os.environ.get("REDIS_DB", 0)),
        "password": os.environ.get("REDIS_PASSWORD", None),
    }

def get_retention_config():
    """
    Returns a dictionary with the retention configuration.
    """
    return {
        "enabled": os.environ.get("RETENTION_ENABLED", "true").lower() == "true",
        "dry_run": os.environ.get("RETENTION_DRY_RUN", "false").lower() == "true",
        "audit_days": int(os.environ.get("RETENTION_AUDIT_DAYS", 365)),
        "event_audit_days": int(os.environ.get("RETENTION_EVENT_AUDIT_DAYS", 90)),
        "dlq_days": int(os.environ.get("RETENTION_DLQ_DAYS", 30)),
        "batch_size": int(os.environ.get("RETENTION_BATCH_SIZE", 1000)),
    }

def validate_retention_config():
    """
    Validates the retention configuration.
    """
    warnings = []
    config = get_retention_config()
    if not isinstance(config["audit_days"], int) or config["audit_days"] <= 0:
        warnings.append("RETENTION_AUDIT_DAYS must be a positive integer.")
    if not isinstance(config["event_audit_days"], int) or config["event_audit_days"] <= 0:
        warnings.append("RETENTION_EVENT_AUDIT_DAYS must be a positive integer.")
    if not isinstance(config["dlq_days"], int) or config["dlq_days"] <= 0:
        warnings.append("RETENTION_DLQ_DAYS must be a positive integer.")
    if not isinstance(config["batch_size"], int) or config["batch_size"] <= 0:
        warnings.append("RETENTION_BATCH_SIZE must be a positive integer.")
    return warnings
