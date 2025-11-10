#!/usr/bin/env python3
"""
MUTT v2 - OpenTelemetry Tracing Utilities (Phase 2 Observability)

This module provides distributed tracing integration using OpenTelemetry.
It enables trace correlation across microservices and automatic instrumentation
for common libraries (Flask, Redis, PostgreSQL, HTTP clients).

Key Features:
- Opt-in via OTEL_ENABLED environment variable
- Safe imports (no-op if OpenTelemetry not installed)
- OTLP gRPC exporter for trace data
- Auto-instrumentation: Flask, Requests, Redis, Psycopg2
- Manual span helpers for worker services
- W3C trace context propagation
- Resource attributes (service name, version, pod)

Usage:
    from tracing_utils import setup_tracing, get_current_trace_ids

    # At service startup
    setup_tracing(service_name="ingestor", version="2.3.0")

    # In request handlers (automatic for Flask)
    trace_id, span_id = get_current_trace_ids()
    logger.info("Processing", extra={"trace_id": trace_id})

    # Manual spans for worker services
    from tracing_utils import create_span
    with create_span("process_alert") as span:
        span.set_attribute("alert.id", alert_id)
        # ... processing logic ...

Environment Variables:
    OTEL_ENABLED: Enable OpenTelemetry tracing (default: false)
    OTEL_EXPORTER_OTLP_ENDPOINT: OTLP collector endpoint (default: http://localhost:4317)
    OTEL_SERVICE_NAME: Service name override
    OTEL_RESOURCE_ATTRIBUTES: Additional resource attributes (key1=val1,key2=val2)
    POD_NAME: Kubernetes pod name for metadata
    SERVICE_VERSION: Service version override

Author: MUTT Development Team
License: MIT
Version: 2.0.0
"""

import os
import logging
from typing import Optional, Tuple, Dict, Any
from contextlib import contextmanager

# Safe imports - OpenTelemetry is optional
try:
    from opentelemetry import trace
    from opentelemetry.sdk.trace import TracerProvider
    from opentelemetry.sdk.trace.export import BatchSpanProcessor
    from opentelemetry.exporter.otlp.proto.grpc.trace_exporter import OTLPSpanExporter
    from opentelemetry.sdk.resources import Resource, SERVICE_NAME, SERVICE_VERSION
    from opentelemetry.trace import Status, StatusCode

    # Auto-instrumentation imports
    try:
        from opentelemetry.instrumentation.flask import FlaskInstrumentor
    except ImportError:
        FlaskInstrumentor = None

    try:
        from opentelemetry.instrumentation.requests import RequestsInstrumentor
    except ImportError:
        RequestsInstrumentor = None

    try:
        from opentelemetry.instrumentation.redis import RedisInstrumentor
    except ImportError:
        RedisInstrumentor = None

    try:
        from opentelemetry.instrumentation.psycopg2 import Psycopg2Instrumentor
    except ImportError:
        Psycopg2Instrumentor = None

    OTEL_AVAILABLE = True
except ImportError:
    # OpenTelemetry not installed - define stubs
    OTEL_AVAILABLE = False
    trace = None  # type: ignore
    TracerProvider = None  # type: ignore
    # Safe stubs so tests can patch these attributes
    class _StatusCode:
        ERROR = "ERROR"

    class _Status:
        def __init__(self, status_code=None, description=None):
            self.status_code = status_code
            self.description = description

    StatusCode = _StatusCode  # type: ignore
    Status = _Status  # type: ignore
    BatchSpanProcessor = None  # type: ignore
    OTLPSpanExporter = None  # type: ignore
    # Resource attribute keys as strings for compatibility
    Resource = None  # type: ignore
    SERVICE_NAME = "service.name"  # type: ignore
    SERVICE_VERSION = "service.version"  # type: ignore
    FlaskInstrumentor = None
    RequestsInstrumentor = None
    RedisInstrumentor = None
    Psycopg2Instrumentor = None


logger = logging.getLogger(__name__)

# Global tracer instance
_tracer: Optional[Any] = None
_tracing_enabled = False


def is_tracing_enabled() -> bool:
    """
    Check if OpenTelemetry tracing is enabled.

    Returns:
        True if tracing is enabled and configured
    """
    return _tracing_enabled


def setup_tracing(service_name: str, version: str) -> bool:
    """
    Configure OpenTelemetry distributed tracing for a MUTT service.

    This function sets up the OpenTelemetry SDK with OTLP gRPC exporter and
    enables auto-instrumentation for common libraries. It only activates when
    OTEL_ENABLED is set to "true" and OpenTelemetry packages are installed.

    The function is idempotent - it can be called multiple times safely.

    Args:
        service_name: Name of the service (e.g., "ingestor", "alerter", "web_ui")
        version: Service version string (e.g., "2.3.0")

    Returns:
        True if tracing was successfully enabled, False otherwise

    Environment Variables:
        OTEL_ENABLED: Set to "true" to enable tracing (default: false)
        OTEL_EXPORTER_OTLP_ENDPOINT: OTLP collector endpoint (default: http://localhost:4317)
        OTEL_SERVICE_NAME: Override service name
        OTEL_RESOURCE_ATTRIBUTES: Additional attributes (key1=val1,key2=val2)

    Example:
        >>> setup_tracing("ingestor", "2.3.0")
        True  # If OTEL_ENABLED=true and packages available
        >>> setup_tracing("ingestor", "2.3.0")
        False  # If OTEL_ENABLED=false (default)
    """
    global _tracer, _tracing_enabled

    # Check if tracing should be enabled
    otel_enabled = os.getenv("OTEL_ENABLED", "false").lower() in (
        "true",
        "1",
        "yes",
        "on",
    )

    if not otel_enabled:
        logger.info(f"OpenTelemetry tracing disabled for service={service_name}")
        _tracing_enabled = False
        return False

    if not OTEL_AVAILABLE:
        logger.warning(
            f"OpenTelemetry tracing enabled but packages not installed. "
            f"Install with: pip install opentelemetry-api opentelemetry-sdk "
            f"opentelemetry-exporter-otlp-proto-grpc"
        )
        _tracing_enabled = False
        return False

    try:
        # Get configuration
        otlp_endpoint = os.getenv(
            "OTEL_EXPORTER_OTLP_ENDPOINT", "http://localhost:4317"
        )
        service_name_override = os.getenv("OTEL_SERVICE_NAME", service_name)
        pod_name = os.getenv("POD_NAME", "unknown")
        version_override = os.getenv("SERVICE_VERSION", version)

        # Build resource attributes
        resource_attrs = {
            SERVICE_NAME: service_name_override,
            SERVICE_VERSION: version_override,
            "deployment.environment": os.getenv("DEPLOYMENT_ENV", "production"),
            "service.instance.id": pod_name,
            "telemetry.sdk.language": "python",
        }

        # Parse additional resource attributes from env
        additional_attrs = os.getenv("OTEL_RESOURCE_ATTRIBUTES", "")
        if additional_attrs:
            for pair in additional_attrs.split(","):
                if "=" in pair:
                    key, value = pair.split("=", 1)
                    resource_attrs[key.strip()] = value.strip()

        # Create resource
        resource = Resource.create(resource_attrs)

        # Create tracer provider
        provider = TracerProvider(resource=resource)

        # Create OTLP exporter (gRPC)
        otlp_exporter = OTLPSpanExporter(
            endpoint=otlp_endpoint,
            insecure=not otlp_endpoint.startswith("https"),
        )

        # Add batch span processor
        span_processor = BatchSpanProcessor(otlp_exporter)
        provider.add_span_processor(span_processor)

        # Set global tracer provider
        trace.set_tracer_provider(provider)

        # Get tracer instance
        _tracer = trace.get_tracer(
            instrumenting_module_name=f"mutt.{service_name}",
            instrumenting_library_version=version,
        )

        # Enable auto-instrumentation
        _enable_auto_instrumentation()

        logger.info(
            f"OpenTelemetry tracing enabled: service={service_name_override} "
            f"version={version_override} endpoint={otlp_endpoint}"
        )

        _tracing_enabled = True
        return True

    except Exception as e:
        logger.error(f"Failed to setup OpenTelemetry tracing: {e}", exc_info=True)
        _tracing_enabled = False
        return False


def _enable_auto_instrumentation() -> None:
    """
    Enable auto-instrumentation for common libraries.

    Instruments:
    - Flask (HTTP server)
    - Requests (HTTP client)
    - Redis (cache/queue)
    - Psycopg2 (PostgreSQL)

    This function is called internally by setup_tracing().
    """
    instrumented = []

    try:
        if FlaskInstrumentor is not None:
            FlaskInstrumentor().instrument()
            instrumented.append("Flask")
    except Exception as e:
        logger.warning(f"Failed to instrument Flask: {e}")

    try:
        if RequestsInstrumentor is not None:
            RequestsInstrumentor().instrument()
            instrumented.append("Requests")
    except Exception as e:
        logger.warning(f"Failed to instrument Requests: {e}")

    try:
        if RedisInstrumentor is not None:
            RedisInstrumentor().instrument()
            instrumented.append("Redis")
    except Exception as e:
        logger.warning(f"Failed to instrument Redis: {e}")

    try:
        if Psycopg2Instrumentor is not None:
            Psycopg2Instrumentor().instrument()
            instrumented.append("Psycopg2")
    except Exception as e:
        logger.warning(f"Failed to instrument Psycopg2: {e}")

    if instrumented:
        logger.info(f"Auto-instrumentation enabled: {', '.join(instrumented)}")


def get_current_trace_ids() -> Tuple[Optional[str], Optional[str]]:
    """
    Get the current trace ID and span ID from the active span context.

    This is useful for correlating logs with traces. The IDs are returned
    as hex strings compatible with W3C trace context format.

    Returns:
        Tuple of (trace_id, span_id) as hex strings, or (None, None) if no active span

    Example:
        >>> trace_id, span_id = get_current_trace_ids()
        >>> if trace_id:
        ...     logger.info("Processing", extra={"trace_id": trace_id, "span_id": span_id})
    """
    if not _tracing_enabled or trace is None:
        return None, None

    try:
        span = trace.get_current_span()
        if span and span.is_recording():
            span_context = span.get_span_context()
            if span_context.is_valid:
                trace_id = format(span_context.trace_id, "032x")
                span_id = format(span_context.span_id, "016x")
                return trace_id, span_id
    except Exception as e:
        logger.debug(f"Failed to get trace IDs: {e}")

    return None, None


def extract_tracecontext(headers: Dict[str, str]) -> Optional[Any]:
    """
    Extract W3C trace context from HTTP headers.

    This is useful for propagating trace context from incoming requests
    in worker services that don't use Flask auto-instrumentation.

    Args:
        headers: Dictionary of HTTP headers (e.g., from Flask request.headers)

    Returns:
        Span context object if trace context found, None otherwise

    Example:
        >>> # In a message handler
        >>> headers = message.get("headers", {})
        >>> context = extract_tracecontext(headers)
        >>> if context:
        ...     with start_span("process_message", context=context):
        ...         # Processing with parent trace context
    """
    if not _tracing_enabled or trace is None:
        return None

    try:
        from opentelemetry.propagate import extract

        # Extract context from headers
        context = extract(headers)
        return context
    except Exception as e:
        logger.debug(f"Failed to extract trace context: {e}")
        return None


def inject_tracecontext(headers: Dict[str, str]) -> Dict[str, str]:
    """
    Inject W3C trace context into HTTP headers.

    This is useful for propagating trace context to downstream services
    when making HTTP requests or enqueuing messages.

    Args:
        headers: Dictionary of HTTP headers to inject into

    Returns:
        Updated headers dictionary with trace context

    Example:
        >>> # Before making HTTP request
        >>> headers = {"Content-Type": "application/json"}
        >>> headers = inject_tracecontext(headers)
        >>> response = requests.post(url, headers=headers, json=data)
    """
    if not _tracing_enabled or trace is None:
        return headers

    try:
        from opentelemetry.propagate import inject

        # Inject current context into headers
        inject(headers)
    except Exception as e:
        logger.debug(f"Failed to inject trace context: {e}")

    return headers


@contextmanager
def create_span(
    name: str,
    attributes: Optional[Dict[str, Any]] = None,
    kind: Optional[Any] = None,
):
    """
    Create a manual span for instrumenting code blocks.

    This is useful for worker services that need manual instrumentation
    around processing logic (e.g., message handlers, alert processing).

    Args:
        name: Span name (e.g., "process_alert", "forward_to_moog")
        attributes: Dictionary of span attributes
        kind: Span kind (e.g., SpanKind.INTERNAL, SpanKind.CONSUMER)

    Yields:
        Span object (or no-op if tracing disabled)

    Example:
        >>> with create_span("process_alert", attributes={"alert.id": 123}):
        ...     # Processing logic
        ...     result = process_alert(alert_data)
        ...
        >>> # Span automatically ends and is exported
    """
    if not _tracing_enabled or _tracer is None:
        # No-op context manager when tracing disabled
        yield None
        return

    span = None
    try:
        span = _tracer.start_span(name, kind=kind)

        # Set attributes
        if attributes:
            for key, value in attributes.items():
                # Convert value to string if not a basic type
                if not isinstance(value, (str, int, float, bool)):
                    value = str(value)
                span.set_attribute(key, value)

        # Make span active in context
        token = trace.set_span_in_context(span)

        yield span

    except Exception as e:
        # Record exception in span if we have one
        if span is not None:
            span.set_status(Status(StatusCode.ERROR, str(e)))
            span.record_exception(e)
        raise
    finally:
        # Always end the span if it was created
        if span is not None:
            span.end()


def set_span_attribute(key: str, value: Any) -> None:
    """
    Set an attribute on the current active span.

    This is a convenience function for adding attributes to the current span
    without needing to track the span object.

    Args:
        key: Attribute key
        value: Attribute value (converted to string if needed)

    Example:
        >>> set_span_attribute("user.id", user_id)
        >>> set_span_attribute("http.status_code", 200)
    """
    if not _tracing_enabled or trace is None:
        return

    try:
        span = trace.get_current_span()
        if span and span.is_recording():
            if not isinstance(value, (str, int, float, bool)):
                value = str(value)
            span.set_attribute(key, value)
    except Exception as e:
        logger.debug(f"Failed to set span attribute: {e}")


def record_exception(exception: Exception) -> None:
    """
    Record an exception on the current active span.

    Args:
        exception: Exception to record

    Example:
        >>> try:
        ...     risky_operation()
        ... except Exception as e:
        ...     record_exception(e)
        ...     raise
    """
    if not _tracing_enabled or trace is None:
        return

    try:
        span = trace.get_current_span()
        if span and span.is_recording():
            span.record_exception(exception)
            span.set_status(Status(StatusCode.ERROR, str(exception)))
    except Exception as e:
        logger.debug(f"Failed to record exception: {e}")


if __name__ == "__main__":
    # Example usage and testing
    print("MUTT v2 - OpenTelemetry Tracing Utilities")
    print("=" * 60)

    if not OTEL_AVAILABLE:
        print("\nOpenTelemetry packages not installed.")
        print("Install with:")
        print("  pip install opentelemetry-api opentelemetry-sdk \\")
        print("              opentelemetry-exporter-otlp-proto-grpc")
        print("\nOptional instrumentation:")
        print("  pip install opentelemetry-instrumentation-flask \\")
        print("              opentelemetry-instrumentation-requests \\")
        print("              opentelemetry-instrumentation-redis \\")
        print("              opentelemetry-instrumentation-psycopg2")
    else:
        print("\nOpenTelemetry packages available.")
        print("\nTo enable tracing, set environment variables:")
        print("  export OTEL_ENABLED=true")
        print("  export OTEL_EXPORTER_OTLP_ENDPOINT=http://localhost:4317")
        print("\nExample usage:")
        print("  from tracing_utils import setup_tracing, create_span")
        print("  setup_tracing('my-service', '1.0.0')")
        print("  with create_span('operation'):")
        print("      # your code here")

    print("\nSee module docstring for complete examples.")
