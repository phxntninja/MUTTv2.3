#!/usr/bin/env python3
"""
MUTT v2 - JSON Logging Utilities (Phase 2 Observability)

This module provides structured JSON logging with NDJSON format for improved
observability in production environments. It integrates with existing correlation
ID infrastructure and OpenTelemetry tracing.

Key Features:
- NDJSON (newline-delimited JSON) format
- Opt-in via LOG_JSON_ENABLED environment variable
- Backwards compatible (falls back to standard logging when disabled)
- Automatic correlation ID and trace context injection
- Pod/container metadata support
- Thread-safe

Usage:
    from logging_utils import setup_json_logging

    # At service startup
    logger = setup_json_logging(
        service_name="ingestor",
        version="2.3.0",
        level="INFO"
    )

    # Use logger normally - JSON formatting handled automatically
    logger.info("Processing event", extra={"event_id": 123})

Environment Variables:
    LOG_JSON_ENABLED: Enable JSON logging (default: false)
    LOG_LEVEL: Logging level (default: INFO)
    POD_NAME: Kubernetes pod name for metadata
    SERVICE_VERSION: Service version override

Author: MUTT Development Team
License: MIT
Version: 2.0.0
"""

import os
import json
import logging
import threading
import traceback
from datetime import datetime, timezone
from typing import Any, Dict, Optional


class NDJSONFormatter(logging.Formatter):
    """
    Custom formatter that outputs logs as NDJSON (newline-delimited JSON).

    Each log record is serialized as a single JSON object on one line,
    making it easy to parse by log aggregation systems (ELK, Splunk, etc.).

    Fields included:
    - timestamp: ISO 8601 format with timezone
    - level: Log level (INFO, ERROR, etc.)
    - message: Log message
    - logger: Logger name
    - module: Python module name
    - function: Function name
    - line: Line number
    - thread: Thread ID
    - service: Service name
    - version: Service version
    - pod_name: Kubernetes pod name (if available)
    - correlation_id: Request correlation ID
    - trace_id: OpenTelemetry trace ID (if tracing enabled)
    - span_id: OpenTelemetry span ID (if tracing enabled)
    - error: Exception details (if exception present)
    - extra: Additional fields from log record
    """

    def __init__(self, service_name: str, version: str):
        """
        Initialize NDJSON formatter.

        Args:
            service_name: Name of the service (e.g., "ingestor", "alerter")
            version: Service version (e.g., "2.3.0")
        """
        super().__init__()
        self.service_name = service_name
        self.version = version
        self.pod_name = os.getenv("POD_NAME", "unknown")

    def format(self, record: logging.LogRecord) -> str:
        """
        Format log record as NDJSON.

        Args:
            record: LogRecord to format

        Returns:
            JSON string (single line)
        """
        # Build base log entry
        log_entry: Dict[str, Any] = {
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "level": record.levelname,
            "message": record.getMessage(),
            "logger": record.name,
            "module": record.module,
            "function": record.funcName,
            "line": record.lineno,
            "thread": threading.get_ident(),
            "service": self.service_name,
            "version": self.version,
            "pod_name": self.pod_name,
        }

        # Add correlation ID (from existing CorrelationIdFilter)
        correlation_id = getattr(record, "correlation_id", None)
        if correlation_id:
            log_entry["correlation_id"] = correlation_id
        else:
            # Fallback to "system" if not in request context
            log_entry["correlation_id"] = "system"

        # Add trace context (from OpenTelemetry if enabled)
        trace_id = getattr(record, "trace_id", None)
        span_id = getattr(record, "span_id", None)
        if trace_id:
            log_entry["trace_id"] = trace_id
        if span_id:
            log_entry["span_id"] = span_id

        # Add exception info if present
        if record.exc_info:
            log_entry["error"] = {
                "type": record.exc_info[0].__name__ if record.exc_info[0] else None,
                "message": str(record.exc_info[1]) if record.exc_info[1] else None,
                "traceback": self.formatException(record.exc_info),
            }

        # Add any extra fields from the log call
        # (fields that were passed via `extra={}`)
        for key, value in record.__dict__.items():
            if key not in [
                "name",
                "msg",
                "args",
                "created",
                "filename",
                "funcName",
                "levelname",
                "levelno",
                "lineno",
                "module",
                "msecs",
                "message",
                "pathname",
                "process",
                "processName",
                "relativeCreated",
                "thread",
                "threadName",
                "exc_info",
                "exc_text",
                "stack_info",
                "correlation_id",
                "trace_id",
                "span_id",
            ]:
                # Include custom fields
                try:
                    # Ensure value is JSON-serializable
                    json.dumps(value)
                    log_entry[key] = value
                except (TypeError, ValueError):
                    # Skip non-serializable values
                    log_entry[key] = str(value)

        # Serialize to JSON (single line)
        try:
            return json.dumps(log_entry, default=str)
        except Exception as e:
            # Fallback: return minimal JSON if serialization fails
            return json.dumps(
                {
                    "timestamp": datetime.now(timezone.utc).isoformat(),
                    "level": "ERROR",
                    "message": f"Failed to serialize log record: {e}",
                    "service": self.service_name,
                    "correlation_id": "system",
                }
            )


class TraceContextFilter(logging.Filter):
    """
    Logging filter that injects OpenTelemetry trace context into log records.

    This filter automatically adds trace_id and span_id fields to log records
    when OpenTelemetry tracing is enabled, enabling correlation between logs
    and distributed traces.

    Note: This filter safely handles cases where OpenTelemetry is not available
    or not enabled, making it safe to use unconditionally.
    """

    def filter(self, record: logging.LogRecord) -> bool:
        """
        Add trace context to log record.

        Args:
            record: LogRecord to enrich

        Returns:
            True (always allow the record)
        """
        try:
            # Try to import OpenTelemetry trace module
            from opentelemetry import trace

            # Get current span
            span = trace.get_current_span()
            if span and span.is_recording():
                span_context = span.get_span_context()
                if span_context.is_valid:
                    # Format trace_id and span_id as hex strings
                    record.trace_id = format(span_context.trace_id, "032x")
                    record.span_id = format(span_context.span_id, "016x")
        except (ImportError, Exception):
            # OpenTelemetry not available or not configured - that's OK
            pass

        return True


def setup_json_logging(
    service_name: str,
    version: str,
    level: str = "INFO",
) -> logging.Logger:
    """
    Configure JSON logging for a MUTT service.

    This function sets up structured JSON logging (NDJSON format) when the
    LOG_JSON_ENABLED environment variable is set to "true". Otherwise, it
    falls back to standard text logging for backwards compatibility.

    The function is idempotent - it can be called multiple times safely.

    Args:
        service_name: Name of the service (e.g., "ingestor", "alerter", "web_ui")
        version: Service version string (e.g., "2.3.0")
        level: Logging level as string (default: "INFO")

    Returns:
        Configured logger instance (root logger)

    Environment Variables:
        LOG_JSON_ENABLED: Set to "true" to enable JSON logging (default: false)
        LOG_LEVEL: Override logging level (default: INFO)

    Example:
        >>> logger = setup_json_logging("ingestor", "2.3.0", "INFO")
        >>> logger.info("Service started")
        {"timestamp":"2025-01-09T12:00:00Z","level":"INFO","message":"Service started",...}

        >>> # With LOG_JSON_ENABLED=false (default)
        >>> logger = setup_json_logging("ingestor", "2.3.0")
        >>> logger.info("Service started")
        2025-01-09 12:00:00 - INFO - [correlation_id] - Service started
    """
    # Get configuration from environment
    json_enabled = os.getenv("LOG_JSON_ENABLED", "false").lower() in (
        "true",
        "1",
        "yes",
        "on",
    )
    log_level = os.getenv("LOG_LEVEL", level).upper()

    # Get root logger
    logger = logging.getLogger()

    # Remove existing handlers to avoid duplicates
    logger.handlers.clear()

    # Set log level
    logger.setLevel(getattr(logging, log_level, logging.INFO))

    # Create console handler
    handler = logging.StreamHandler()
    handler.setLevel(logger.level)

    if json_enabled:
        # Use NDJSON formatter for structured logging
        formatter = NDJSONFormatter(service_name=service_name, version=version)
        handler.setFormatter(formatter)

        # Add trace context filter (safe even if OTEL not available)
        logger.addFilter(TraceContextFilter())

        logger.info(
            f"JSON logging enabled for service={service_name} version={version}"
        )
    else:
        # Use standard text formatter (existing format)
        formatter = logging.Formatter(
            "%(asctime)s - %(levelname)s - [%(correlation_id)s] - %(message)s"
        )
        handler.setFormatter(formatter)

        logger.info(f"Standard logging enabled for service={service_name}")

    # Add handler to logger
    logger.addHandler(handler)

    return logger


def get_logger(name: str = __name__) -> logging.Logger:
    """
    Get a named logger instance.

    This is a convenience function for getting loggers in individual modules.
    The logger will inherit the configuration set up by setup_json_logging().

    Args:
        name: Logger name (typically __name__)

    Returns:
        Logger instance

    Example:
        >>> logger = get_logger(__name__)
        >>> logger.info("Processing event")
    """
    return logging.getLogger(name)


if __name__ == "__main__":
    # Example usage and testing
    print("MUTT v2 - JSON Logging Utilities")
    print("=" * 60)
    print("\nExample 1: JSON logging disabled (default)")
    print("-" * 60)

    # Test with JSON disabled
    test_logger = setup_json_logging("test-service", "1.0.0", "INFO")
    test_logger.info("This is a standard text log")

    print("\nExample 2: JSON logging enabled")
    print("-" * 60)

    # Test with JSON enabled
    os.environ["LOG_JSON_ENABLED"] = "true"
    test_logger = setup_json_logging("test-service", "1.0.0", "INFO")
    test_logger.info("This is a JSON log")
    test_logger.info("Event processed", extra={"event_id": 123, "duration_ms": 45})
    test_logger.error("An error occurred", exc_info=Exception("Test error"))

    print("\nDone. See output above for formatting examples.")
