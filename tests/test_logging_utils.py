#!/usr/bin/env python3
"""
Unit tests for logging_utils.py (Phase 2 Observability)

Tests cover:
- JSON logging enable/disable
- NDJSON format validation
- Correlation ID integration
- Trace context injection
- Error handling and edge cases
- Backwards compatibility
"""

import json
import logging
import os
import sys
import unittest
from io import StringIO
from unittest.mock import patch, MagicMock

# Add services directory to path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "services"))

from logging_utils import (
    setup_json_logging,
    NDJSONFormatter,
    TraceContextFilter,
    get_logger,
)


class TestNDJSONFormatter(unittest.TestCase):
    """Test the NDJSON formatter."""

    def setUp(self):
        """Set up test fixtures."""
        self.formatter = NDJSONFormatter(service_name="test-service", version="1.0.0")

    def test_basic_format(self):
        """Test basic log formatting."""
        record = logging.LogRecord(
            name="test",
            level=logging.INFO,
            pathname="test.py",
            lineno=10,
            msg="Test message",
            args=(),
            exc_info=None,
        )
        record.correlation_id = "test-123"

        output = self.formatter.format(record)

        # Should be valid JSON
        log_entry = json.loads(output)

        # Check required fields
        self.assertIn("timestamp", log_entry)
        self.assertEqual(log_entry["level"], "INFO")
        self.assertEqual(log_entry["message"], "Test message")
        self.assertEqual(log_entry["logger"], "test")
        self.assertEqual(log_entry["service"], "test-service")
        self.assertEqual(log_entry["version"], "1.0.0")
        self.assertEqual(log_entry["correlation_id"], "test-123")
        self.assertIn("module", log_entry)
        self.assertIn("function", log_entry)
        self.assertIn("line", log_entry)
        self.assertIn("thread", log_entry)

    def test_correlation_id_fallback(self):
        """Test correlation ID falls back to 'system' if not present."""
        record = logging.LogRecord(
            name="test",
            level=logging.INFO,
            pathname="test.py",
            lineno=10,
            msg="Test message",
            args=(),
            exc_info=None,
        )
        # No correlation_id attribute

        output = self.formatter.format(record)
        log_entry = json.loads(output)

        self.assertEqual(log_entry["correlation_id"], "system")

    def test_trace_context_fields(self):
        """Test trace_id and span_id are included when present."""
        record = logging.LogRecord(
            name="test",
            level=logging.INFO,
            pathname="test.py",
            lineno=10,
            msg="Test message",
            args=(),
            exc_info=None,
        )
        record.correlation_id = "test-123"
        record.trace_id = "abcd1234567890abcd1234567890abcd"
        record.span_id = "1234567890abcdef"

        output = self.formatter.format(record)
        log_entry = json.loads(output)

        self.assertEqual(log_entry["trace_id"], "abcd1234567890abcd1234567890abcd")
        self.assertEqual(log_entry["span_id"], "1234567890abcdef")

    def test_exception_formatting(self):
        """Test exception info is properly formatted."""
        try:
            raise ValueError("Test error")
        except ValueError:
            exc_info = sys.exc_info()

        record = logging.LogRecord(
            name="test",
            level=logging.ERROR,
            pathname="test.py",
            lineno=10,
            msg="Error occurred",
            args=(),
            exc_info=exc_info,
        )
        record.correlation_id = "test-123"

        output = self.formatter.format(record)
        log_entry = json.loads(output)

        self.assertIn("error", log_entry)
        self.assertEqual(log_entry["error"]["type"], "ValueError")
        self.assertEqual(log_entry["error"]["message"], "Test error")
        self.assertIn("traceback", log_entry["error"])
        self.assertIn("ValueError: Test error", log_entry["error"]["traceback"])

    def test_extra_fields(self):
        """Test that extra fields are included in JSON output."""
        record = logging.LogRecord(
            name="test",
            level=logging.INFO,
            pathname="test.py",
            lineno=10,
            msg="Test message",
            args=(),
            exc_info=None,
        )
        record.correlation_id = "test-123"
        record.event_id = 456
        record.duration_ms = 123.45

        output = self.formatter.format(record)
        log_entry = json.loads(output)

        self.assertEqual(log_entry["event_id"], 456)
        self.assertEqual(log_entry["duration_ms"], 123.45)

    def test_non_serializable_extra_field(self):
        """Test that non-serializable extra fields are converted to strings."""
        record = logging.LogRecord(
            name="test",
            level=logging.INFO,
            pathname="test.py",
            lineno=10,
            msg="Test message",
            args=(),
            exc_info=None,
        )
        record.correlation_id = "test-123"
        record.custom_object = MagicMock()  # Not JSON-serializable

        output = self.formatter.format(record)
        log_entry = json.loads(output)

        # Should be converted to string
        self.assertIn("custom_object", log_entry)
        self.assertIsInstance(log_entry["custom_object"], str)

    def test_pod_name_from_env(self):
        """Test that pod_name is read from POD_NAME environment variable."""
        with patch.dict(os.environ, {"POD_NAME": "test-pod-123"}):
            formatter = NDJSONFormatter(service_name="test", version="1.0.0")
            record = logging.LogRecord(
                name="test",
                level=logging.INFO,
                pathname="test.py",
                lineno=10,
                msg="Test",
                args=(),
                exc_info=None,
            )
            record.correlation_id = "test-123"

            output = formatter.format(record)
            log_entry = json.loads(output)

            self.assertEqual(log_entry["pod_name"], "test-pod-123")


class TestTraceContextFilter(unittest.TestCase):
    """Test the TraceContextFilter."""

    def test_filter_without_otel(self):
        """Test filter works when OpenTelemetry is not available."""
        filter_obj = TraceContextFilter()
        record = logging.LogRecord(
            name="test",
            level=logging.INFO,
            pathname="test.py",
            lineno=10,
            msg="Test",
            args=(),
            exc_info=None,
        )

        # Should not raise an error
        result = filter_obj.filter(record)
        self.assertTrue(result)

    @patch("logging_utils.trace")
    def test_filter_with_otel_active_span(self, mock_trace):
        """Test filter adds trace context when span is active."""
        # Mock active span
        mock_span_context = MagicMock()
        mock_span_context.is_valid = True
        mock_span_context.trace_id = 0xABCD1234567890ABCD1234567890ABCD
        mock_span_context.span_id = 0x1234567890ABCDEF

        mock_span = MagicMock()
        mock_span.is_recording.return_value = True
        mock_span.get_span_context.return_value = mock_span_context

        mock_trace.get_current_span.return_value = mock_span

        filter_obj = TraceContextFilter()
        record = logging.LogRecord(
            name="test",
            level=logging.INFO,
            pathname="test.py",
            lineno=10,
            msg="Test",
            args=(),
            exc_info=None,
        )

        result = filter_obj.filter(record)

        self.assertTrue(result)
        self.assertEqual(
            record.trace_id, "abcd1234567890abcd1234567890abcd"
        )  # 32 char hex
        self.assertEqual(record.span_id, "1234567890abcdef")  # 16 char hex

    @patch("logging_utils.trace")
    def test_filter_with_otel_no_active_span(self, mock_trace):
        """Test filter handles no active span gracefully."""
        mock_span = MagicMock()
        mock_span.is_recording.return_value = False
        mock_trace.get_current_span.return_value = mock_span

        filter_obj = TraceContextFilter()
        record = logging.LogRecord(
            name="test",
            level=logging.INFO,
            pathname="test.py",
            lineno=10,
            msg="Test",
            args=(),
            exc_info=None,
        )

        result = filter_obj.filter(record)

        self.assertTrue(result)
        # Should not have trace fields
        self.assertFalse(hasattr(record, "trace_id"))
        self.assertFalse(hasattr(record, "span_id"))


class TestSetupJsonLogging(unittest.TestCase):
    """Test the setup_json_logging function."""

    def tearDown(self):
        """Clean up logging handlers after each test."""
        logging.getLogger().handlers.clear()
        # Reset environment
        os.environ.pop("LOG_JSON_ENABLED", None)
        os.environ.pop("LOG_LEVEL", None)

    def test_json_logging_disabled_by_default(self):
        """Test that JSON logging is disabled by default."""
        with patch("sys.stdout", new=StringIO()) as fake_stdout:
            logger = setup_json_logging("test-service", "1.0.0")
            logger.info("Test message")

            output = fake_stdout.getvalue()

            # Should be standard text format, not JSON
            self.assertNotIn("{", output)
            self.assertIn("Test message", output)

    def test_json_logging_enabled(self):
        """Test that JSON logging works when enabled."""
        os.environ["LOG_JSON_ENABLED"] = "true"

        with patch("sys.stdout", new=StringIO()) as fake_stdout:
            logger = setup_json_logging("test-service", "1.0.0")

            # Create a log record with correlation_id
            record = logging.LogRecord(
                name="test",
                level=logging.INFO,
                pathname="test.py",
                lineno=10,
                msg="Test message",
                args=(),
                exc_info=None,
            )
            record.correlation_id = "test-123"

            logger.handle(record)
            output = fake_stdout.getvalue()

            # Should contain JSON
            self.assertIn("{", output)
            # Parse and validate
            lines = [line for line in output.strip().split("\n") if line.strip()]
            # Find the test message line (skip setup messages)
            for line in lines:
                if "Test message" in line:
                    log_entry = json.loads(line)
                    self.assertEqual(log_entry["message"], "Test message")
                    self.assertEqual(log_entry["service"], "test-service")
                    self.assertEqual(log_entry["correlation_id"], "test-123")
                    break

    def test_log_level_from_env(self):
        """Test that log level can be set via environment variable."""
        os.environ["LOG_LEVEL"] = "DEBUG"

        logger = setup_json_logging("test-service", "1.0.0")

        self.assertEqual(logger.level, logging.DEBUG)

    def test_log_level_default(self):
        """Test default log level is INFO."""
        logger = setup_json_logging("test-service", "1.0.0")

        self.assertEqual(logger.level, logging.INFO)

    def test_json_enabled_variations(self):
        """Test various ways to enable JSON logging."""
        test_cases = ["true", "True", "TRUE", "1", "yes", "on"]

        for value in test_cases:
            os.environ["LOG_JSON_ENABLED"] = value
            logger = setup_json_logging("test-service", "1.0.0")

            # Check that NDJSON formatter is used
            handler = logger.handlers[0]
            self.assertIsInstance(handler.formatter, NDJSONFormatter)

            # Clean up
            logger.handlers.clear()

    def test_idempotent_setup(self):
        """Test that calling setup_json_logging multiple times is safe."""
        logger1 = setup_json_logging("test-service", "1.0.0")
        handler_count_1 = len(logger1.handlers)

        logger2 = setup_json_logging("test-service", "1.0.0")
        handler_count_2 = len(logger2.handlers)

        # Should not add duplicate handlers
        self.assertEqual(handler_count_1, handler_count_2)
        self.assertIs(logger1, logger2)  # Same logger instance


class TestGetLogger(unittest.TestCase):
    """Test the get_logger convenience function."""

    def test_get_logger(self):
        """Test that get_logger returns a logger instance."""
        logger = get_logger("test.module")

        self.assertIsInstance(logger, logging.Logger)
        self.assertEqual(logger.name, "test.module")


class TestBackwardsCompatibility(unittest.TestCase):
    """Test backwards compatibility with existing logging."""

    def tearDown(self):
        """Clean up."""
        logging.getLogger().handlers.clear()
        os.environ.pop("LOG_JSON_ENABLED", None)

    def test_correlation_id_filter_still_works(self):
        """Test that existing CorrelationIdFilter pattern still works."""
        # This simulates the existing pattern in services
        class MockCorrelationIdFilter(logging.Filter):
            def filter(self, record):
                record.correlation_id = "legacy-123"
                return True

        logger = setup_json_logging("test-service", "1.0.0")
        logger.addFilter(MockCorrelationIdFilter())

        with patch("sys.stdout", new=StringIO()) as fake_stdout:
            logger.info("Test with legacy filter")
            output = fake_stdout.getvalue()

            # Should include correlation ID in standard format
            self.assertIn("legacy-123", output)


if __name__ == "__main__":
    unittest.main()
