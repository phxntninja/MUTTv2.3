#!/usr/bin/env python3
"""
Unit tests for tracing_utils.py (Phase 2 Observability)

Tests cover:
- OpenTelemetry setup with OTEL_ENABLED flag
- Safe handling when OTEL packages not installed
- Trace ID extraction
- Trace context propagation
- Manual span creation
- Auto-instrumentation
- No-op behavior when disabled
"""

import os
import sys
import unittest
from unittest.mock import patch, MagicMock, call

# Add services directory to path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "services"))


class TestTracingUtilsWithoutOTEL(unittest.TestCase):
    """Test tracing_utils when OpenTelemetry is not installed."""

    def setUp(self):
        """Set up test - simulate OTEL not available."""
        # We need to reload the module to test the import failure path
        # For now, just test the public API behavior
        pass

    def test_import_without_otel(self):
        """Test that module imports successfully without OpenTelemetry."""
        # This test verifies the try/except import pattern works
        try:
            import tracing_utils

            self.assertIsNotNone(tracing_utils)
        except ImportError:
            self.fail("tracing_utils should import even without OpenTelemetry")


class TestTracingUtilsWithOTEL(unittest.TestCase):
    """Test tracing_utils when OpenTelemetry is available."""

    def setUp(self):
        """Set up test fixtures."""
        # Import here to allow skipping if OTEL not available
        import tracing_utils

        self.tracing_utils = tracing_utils
        # Reset global state
        self.tracing_utils._tracing_enabled = False
        self.tracing_utils._tracer = None

    def tearDown(self):
        """Clean up after each test."""
        # Reset environment
        os.environ.pop("OTEL_ENABLED", None)
        os.environ.pop("OTEL_EXPORTER_OTLP_ENDPOINT", None)
        os.environ.pop("OTEL_SERVICE_NAME", None)
        os.environ.pop("OTEL_RESOURCE_ATTRIBUTES", None)
        os.environ.pop("POD_NAME", None)
        os.environ.pop("SERVICE_VERSION", None)
        # Reset global state
        self.tracing_utils._tracing_enabled = False
        self.tracing_utils._tracer = None

    def test_tracing_disabled_by_default(self):
        """Test that tracing is disabled by default."""
        result = self.tracing_utils.setup_tracing("test-service", "1.0.0")

        self.assertFalse(result)
        self.assertFalse(self.tracing_utils.is_tracing_enabled())

    def test_tracing_enabled(self):
        """Test that tracing can be enabled."""
        # Skip if OTEL not installed
        try:
            import opentelemetry
        except ImportError:
            self.skipTest("OpenTelemetry not installed")

        os.environ["OTEL_ENABLED"] = "true"

        with patch("tracing_utils.OTEL_AVAILABLE", True):
            with patch("tracing_utils.trace") as mock_trace:
                with patch("tracing_utils.TracerProvider") as mock_provider:
                    with patch("tracing_utils.OTLPSpanExporter") as mock_exporter:
                        with patch("tracing_utils.BatchSpanProcessor"):
                            # Mock the provider instance
                            mock_provider_instance = MagicMock()
                            mock_provider.return_value = mock_provider_instance

                            # Mock tracer
                            mock_tracer = MagicMock()
                            mock_trace.get_tracer.return_value = mock_tracer

                            result = self.tracing_utils.setup_tracing("test-service", "1.0.0")

                            self.assertTrue(result)
                            self.assertTrue(self.tracing_utils.is_tracing_enabled())

                            # Verify provider was created
                            mock_provider.assert_called_once()

                            # Verify exporter was created with correct endpoint
                            mock_exporter.assert_called_once()

                            # Verify tracer was obtained
                            mock_trace.get_tracer.assert_called_once()

    def test_custom_otlp_endpoint(self):
        """Test custom OTLP endpoint configuration."""
        # Skip if OTEL not installed
        try:
            import opentelemetry
        except ImportError:
            self.skipTest("OpenTelemetry not installed")

        os.environ["OTEL_ENABLED"] = "true"
        os.environ["OTEL_EXPORTER_OTLP_ENDPOINT"] = "http://collector:4317"

        with patch("tracing_utils.OTEL_AVAILABLE", True):
            with patch("tracing_utils.trace") as mock_trace:
                with patch("tracing_utils.TracerProvider") as mock_provider:
                    with patch("tracing_utils.OTLPSpanExporter") as mock_exporter:
                        with patch("tracing_utils.BatchSpanProcessor"):
                            mock_provider_instance = MagicMock()
                            mock_provider.return_value = mock_provider_instance
                            mock_trace.get_tracer.return_value = MagicMock()

                            self.tracing_utils.setup_tracing("test-service", "1.0.0")

                            # Verify exporter was called with custom endpoint
                            mock_exporter.assert_called_once()
                            call_kwargs = mock_exporter.call_args[1]
                            self.assertEqual(call_kwargs["endpoint"], "http://collector:4317")

    def test_resource_attributes(self):
        """Test that resource attributes are properly set."""
        # Skip if OTEL not installed
        try:
            import opentelemetry
        except ImportError:
            self.skipTest("OpenTelemetry not installed")

        os.environ["OTEL_ENABLED"] = "true"
        os.environ["OTEL_SERVICE_NAME"] = "custom-service"
        os.environ["POD_NAME"] = "test-pod-123"
        os.environ["SERVICE_VERSION"] = "2.0.0"
        os.environ["OTEL_RESOURCE_ATTRIBUTES"] = "env=prod,region=us-west"

        with patch("tracing_utils.OTEL_AVAILABLE", True):
            with patch("tracing_utils.trace") as mock_trace:
                with patch("tracing_utils.TracerProvider") as mock_provider:
                    with patch("tracing_utils.OTLPSpanExporter"):
                        with patch("tracing_utils.BatchSpanProcessor"):
                            with patch("tracing_utils.Resource") as mock_resource:
                                mock_provider_instance = MagicMock()
                                mock_provider.return_value = mock_provider_instance
                                mock_trace.get_tracer.return_value = MagicMock()

                                self.tracing_utils.setup_tracing("test-service", "1.0.0")

                                # Verify Resource.create was called
                                mock_resource.create.assert_called_once()
                                attrs = mock_resource.create.call_args[0][0]

                                # Check custom attributes
                                self.assertIn("env", attrs)
                                self.assertEqual(attrs["env"], "prod")
                                self.assertIn("region", attrs)
                                self.assertEqual(attrs["region"], "us-west")

    def test_get_current_trace_ids_when_disabled(self):
        """Test get_current_trace_ids returns None when tracing disabled."""
        trace_id, span_id = self.tracing_utils.get_current_trace_ids()

        self.assertIsNone(trace_id)
        self.assertIsNone(span_id)

    @patch("tracing_utils.OTEL_AVAILABLE", True)
    @patch("tracing_utils._tracing_enabled", True)
    @patch("tracing_utils.trace")
    def test_get_current_trace_ids_with_active_span(self, mock_trace):
        """Test get_current_trace_ids extracts IDs from active span."""
        # Mock span context
        mock_span_context = MagicMock()
        mock_span_context.is_valid = True
        mock_span_context.trace_id = 0xABCD1234567890ABCD1234567890ABCD
        mock_span_context.span_id = 0x1234567890ABCDEF

        mock_span = MagicMock()
        mock_span.is_recording.return_value = True
        mock_span.get_span_context.return_value = mock_span_context

        mock_trace.get_current_span.return_value = mock_span

        trace_id, span_id = self.tracing_utils.get_current_trace_ids()

        self.assertEqual(trace_id, "abcd1234567890abcd1234567890abcd")
        self.assertEqual(span_id, "1234567890abcdef")

    @patch("tracing_utils.OTEL_AVAILABLE", True)
    @patch("tracing_utils._tracing_enabled", True)
    @patch("tracing_utils.trace")
    def test_get_current_trace_ids_no_active_span(self, mock_trace):
        """Test get_current_trace_ids returns None when no active span."""
        mock_span = MagicMock()
        mock_span.is_recording.return_value = False

        mock_trace.get_current_span.return_value = mock_span

        trace_id, span_id = self.tracing_utils.get_current_trace_ids()

        self.assertIsNone(trace_id)
        self.assertIsNone(span_id)

    def test_extract_tracecontext_when_disabled(self):
        """Test extract_tracecontext returns None when tracing disabled."""
        headers = {"traceparent": "00-abc123-def456-01"}

        context = self.tracing_utils.extract_tracecontext(headers)

        self.assertIsNone(context)

    def test_inject_tracecontext_when_disabled(self):
        """Test inject_tracecontext returns headers unchanged when disabled."""
        headers = {"Content-Type": "application/json"}

        result = self.tracing_utils.inject_tracecontext(headers)

        self.assertEqual(result, headers)
        self.assertEqual(len(result), 1)

    @patch("tracing_utils.OTEL_AVAILABLE", True)
    @patch("tracing_utils._tracing_enabled", True)
    @patch("tracing_utils._tracer")
    @patch("tracing_utils.trace")
    def test_create_span_manual(self, mock_trace, mock_tracer):
        """Test manual span creation."""
        mock_span = MagicMock()
        mock_tracer.start_span.return_value = mock_span

        with self.tracing_utils.create_span(
            "test-operation", attributes={"key": "value"}
        ) as span:
            self.assertIsNotNone(span)

        # Verify span was started and ended
        mock_tracer.start_span.assert_called_once_with("test-operation", kind=None)
        mock_span.set_attribute.assert_called_once_with("key", "value")
        mock_span.end.assert_called_once()

    def test_create_span_with_exception(self):
        """Test that exceptions are recorded in spans."""
        # Skip if OTEL not installed
        try:
            import opentelemetry
        except ImportError:
            self.skipTest("OpenTelemetry not installed")

        mock_span = MagicMock()
        mock_tracer = MagicMock()
        mock_tracer.start_span.return_value = mock_span

        with patch("tracing_utils.OTEL_AVAILABLE", True):
            with patch("tracing_utils._tracing_enabled", True):
                with patch("tracing_utils._tracer", mock_tracer):
                    with patch("tracing_utils.trace"):
                        with patch("opentelemetry.trace.Status") as mock_status:
                            with patch("opentelemetry.trace.StatusCode") as mock_status_code:
                                mock_status_code.ERROR = "ERROR"

                                test_error = ValueError("Test error")

                                try:
                                    with self.tracing_utils.create_span("test-operation") as span:
                                        raise test_error
                                except ValueError:
                                    pass

                                # Verify exception was recorded
                                mock_span.record_exception.assert_called_once_with(test_error)
                                mock_span.set_status.assert_called_once()

    def test_create_span_when_disabled(self):
        """Test create_span is no-op when tracing disabled."""
        with self.tracing_utils.create_span("test-operation") as span:
            self.assertIsNone(span)
        # Should not raise any errors

    @patch("tracing_utils.OTEL_AVAILABLE", True)
    @patch("tracing_utils._tracing_enabled", True)
    @patch("tracing_utils.trace")
    def test_set_span_attribute(self, mock_trace):
        """Test setting attributes on current span."""
        mock_span = MagicMock()
        mock_span.is_recording.return_value = True
        mock_trace.get_current_span.return_value = mock_span

        self.tracing_utils.set_span_attribute("test.key", "test.value")

        mock_span.set_attribute.assert_called_once_with("test.key", "test.value")

    def test_set_span_attribute_when_disabled(self):
        """Test set_span_attribute is no-op when disabled."""
        # Should not raise any errors
        self.tracing_utils.set_span_attribute("test.key", "test.value")

    def test_record_exception(self):
        """Test recording exceptions on current span."""
        # Skip if OTEL not installed
        try:
            import opentelemetry
        except ImportError:
            self.skipTest("OpenTelemetry not installed")

        with patch("tracing_utils.OTEL_AVAILABLE", True):
            with patch("tracing_utils._tracing_enabled", True):
                with patch("tracing_utils.trace") as mock_trace:
                    with patch("opentelemetry.trace.Status") as mock_status:
                        with patch("opentelemetry.trace.StatusCode") as mock_status_code:
                            mock_span = MagicMock()
                            mock_span.is_recording.return_value = True
                            mock_trace.get_current_span.return_value = mock_span
                            mock_status_code.ERROR = "ERROR"

                            test_error = RuntimeError("Test error")
                            self.tracing_utils.record_exception(test_error)

                            mock_span.record_exception.assert_called_once_with(test_error)
                            mock_span.set_status.assert_called_once()

    def test_record_exception_when_disabled(self):
        """Test record_exception is no-op when disabled."""
        # Should not raise any errors
        test_error = RuntimeError("Test error")
        self.tracing_utils.record_exception(test_error)

    def test_auto_instrumentation(self):
        """Test that auto-instrumentation is enabled."""
        # Skip if OTEL not installed
        try:
            import opentelemetry
        except ImportError:
            self.skipTest("OpenTelemetry not installed")

        os.environ["OTEL_ENABLED"] = "true"

        with patch("tracing_utils.OTEL_AVAILABLE", True):
            with patch("tracing_utils.trace") as mock_trace:
                with patch("tracing_utils.TracerProvider") as mock_provider:
                    with patch("tracing_utils.OTLPSpanExporter"):
                        with patch("tracing_utils.BatchSpanProcessor"):
                            with patch("tracing_utils.FlaskInstrumentor") as mock_flask:
                                with patch("tracing_utils.RequestsInstrumentor") as mock_requests:
                                    with patch("tracing_utils.RedisInstrumentor") as mock_redis:
                                        with patch("tracing_utils.Psycopg2Instrumentor") as mock_pg:
                                            mock_provider_instance = MagicMock()
                                            mock_provider.return_value = mock_provider_instance
                                            mock_trace.get_tracer.return_value = MagicMock()

                                            # Mock instrumentor instances
                                            mock_flask_inst = MagicMock()
                                            mock_flask.return_value = mock_flask_inst
                                            mock_requests_inst = MagicMock()
                                            mock_requests.return_value = mock_requests_inst
                                            mock_redis_inst = MagicMock()
                                            mock_redis.return_value = mock_redis_inst
                                            mock_pg_inst = MagicMock()
                                            mock_pg.return_value = mock_pg_inst

                                            self.tracing_utils.setup_tracing("test-service", "1.0.0")

                                            # Verify instrumentors were called
                                            mock_flask_inst.instrument.assert_called_once()
                                            mock_requests_inst.instrument.assert_called_once()
                                            mock_redis_inst.instrument.assert_called_once()
                                            mock_pg_inst.instrument.assert_called_once()

    def test_otel_enabled_variations(self):
        """Test various ways to enable OTEL."""
        # Skip if OTEL not installed
        try:
            import opentelemetry
        except ImportError:
            self.skipTest("OpenTelemetry not installed")

        test_cases = ["true", "True", "TRUE", "1", "yes", "on"]

        for value in test_cases:
            os.environ["OTEL_ENABLED"] = value

            # Mock OTEL_AVAILABLE
            with patch("tracing_utils.OTEL_AVAILABLE", True):
                with patch("tracing_utils.trace"):
                    with patch("tracing_utils.TracerProvider"):
                        with patch("tracing_utils.OTLPSpanExporter"):
                            with patch("tracing_utils.BatchSpanProcessor"):
                                result = self.tracing_utils.setup_tracing(
                                    "test", "1.0.0"
                                )
                                self.assertTrue(
                                    result, f"Failed for OTEL_ENABLED={value}"
                                )

            # Reset
            self.tracing_utils._tracing_enabled = False
            self.tracing_utils._tracer = None


class TestBackwardsCompatibility(unittest.TestCase):
    """Test backwards compatibility when OTEL is disabled."""

    def setUp(self):
        """Set up tests."""
        import tracing_utils

        self.tracing_utils = tracing_utils

    def tearDown(self):
        """Clean up."""
        os.environ.pop("OTEL_ENABLED", None)

    def test_all_functions_safe_when_disabled(self):
        """Test that all public functions are safe no-ops when disabled."""
        # All these should not raise errors
        self.tracing_utils.setup_tracing("test", "1.0.0")
        self.tracing_utils.get_current_trace_ids()
        self.tracing_utils.extract_tracecontext({})
        self.tracing_utils.inject_tracecontext({})
        self.tracing_utils.set_span_attribute("key", "value")
        self.tracing_utils.record_exception(Exception("test"))

        with self.tracing_utils.create_span("test"):
            pass

        # Test passes if no exceptions raised


if __name__ == "__main__":
    # Try to import OpenTelemetry - skip tests if not available
    try:
        import opentelemetry

        HAS_OTEL = True
    except ImportError:
        HAS_OTEL = False
        print("OpenTelemetry not installed - some tests will be skipped")

    unittest.main()
