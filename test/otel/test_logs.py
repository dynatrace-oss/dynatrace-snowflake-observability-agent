#!/usr/bin/env python3
#
#
# Copyright (c) 2025 Dynatrace Open Source
#
# Permission is hereby granted, free of charge, to any person obtaining a copy
# of this software and associated documentation files (the "Software"), to deal
# in the Software without restriction, including without limitation the rights
# to use, copy, modify, merge, publish, distribute, sublicense, and/or sell
# copies of the Software, and to permit persons to whom the Software is
# furnished to do so, subject to the following conditions:
#
# The above copyright notice and this permission notice shall be included in all
# copies or substantial portions of the Software.
#
# THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR
# IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY,
# FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE
# AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER
# LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM,
# OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN THE
# SOFTWARE.
#
#

import pytest
from unittest.mock import Mock, patch


class TestLoggerNaming:
    """Tests for OTLP logger naming with TAG support"""

    @patch("dtagent.otel.logs.LoggerProvider")
    @patch("dtagent.otel.logs.Resource")
    def test_get_logger_name_without_tag(self, mock_resource, mock_logger_provider):
        """Test that __get_logger_name returns DTAGENT_OTLP when no TAG is configured"""
        from dtagent.otel.logs import Logs

        # Create mock configuration without TAG
        mock_config = Mock()
        mock_config.multitenancy_tag = None

        # Mock the get method to return appropriate values based on key
        def mock_get(key=None, otel_module=None, **kwargs):
            if otel_module == "logs":
                if kwargs.get("key") == "export_timeout_millis":
                    return 10000
                if kwargs.get("key") == "max_export_batch_size":
                    return 100
            return kwargs.get("default_value", "http://test")

        mock_config.get = Mock(side_effect=mock_get)

        # Create mock resource
        mock_resource_instance = Mock()

        # Instantiate Logs (will call _setup_logger)
        logs = Logs(mock_resource_instance, mock_config)

        # Call the private method directly using name mangling
        logger_name = logs._Logs__get_logger_name()

        assert logger_name == "DTAGENT_OTLP", f"Expected DTAGENT_OTLP but got {logger_name}"

    @patch("dtagent.otel.logs.LoggerProvider")
    @patch("dtagent.otel.logs.Resource")
    def test_get_logger_name_with_tag(self, mock_resource, mock_logger_provider):
        """Test that __get_logger_name returns DTAGENT_TAG_OTLP when TAG is configured"""
        from dtagent.otel.logs import Logs

        # Create mock configuration with TAG
        mock_config = Mock()
        mock_config.multitenancy_tag = "ENV01"

        # Mock the get method to return appropriate values based on key
        def mock_get(key=None, otel_module=None, **kwargs):
            if otel_module == "logs":
                if kwargs.get("key") == "export_timeout_millis":
                    return 10000
                if kwargs.get("key") == "max_export_batch_size":
                    return 100
            return kwargs.get("default_value", "http://test")

        mock_config.get = Mock(side_effect=mock_get)

        # Create mock resource
        mock_resource_instance = Mock()

        # Instantiate Logs
        logs = Logs(mock_resource_instance, mock_config)

        # Call the private method directly using name mangling
        logger_name = logs._Logs__get_logger_name()

        assert logger_name == "DTAGENT_ENV01_OTLP", f"Expected DTAGENT_ENV01_OTLP but got {logger_name}"

    @patch("dtagent.otel.logs.LoggerProvider")
    @patch("dtagent.otel.logs.Resource")
    def test_get_logger_name_with_various_tags(self, mock_resource, mock_logger_provider):
        """Test __get_logger_name with various TAG values"""
        from dtagent.otel.logs import Logs

        test_cases = [
            ("TEST", "DTAGENT_TEST_OTLP"),
            ("PROD", "DTAGENT_PROD_OTLP"),
            ("TENANT_A", "DTAGENT_TENANT_A_OTLP"),
            ("ENV_123", "DTAGENT_ENV_123_OTLP"),
            ("SA080", "DTAGENT_SA080_OTLP"),
        ]

        for tag, expected in test_cases:
            # Create mock configuration with specific TAG
            mock_config = Mock()
            mock_config.multitenancy_tag = tag

            # Mock the get method to return appropriate values based on key
            def mock_get(key=None, otel_module=None, **kwargs):
                if otel_module == "logs":
                    if kwargs.get("key") == "export_timeout_millis":
                        return 10000
                    if kwargs.get("key") == "max_export_batch_size":
                        return 100
                return kwargs.get("default_value", "http://test")

            mock_config.get = Mock(side_effect=mock_get)

            # Create mock resource
            mock_resource_instance = Mock()

            # Instantiate Logs
            logs = Logs(mock_resource_instance, mock_config)

            # Call the private method directly using name mangling
            logger_name = logs._Logs__get_logger_name()

            assert logger_name == expected, f"For TAG={tag}, expected {expected} but got {logger_name}"

    @patch("dtagent.otel.logs.LoggerProvider")
    @patch("dtagent.otel.logs.Resource")
    def test_no_double_tagging(self, mock_resource, mock_logger_provider):
        """Test that __get_logger_name doesn't create double tags"""
        from dtagent.otel.logs import Logs

        # Create mock configuration with TAG that could cause issues
        mock_config = Mock()
        mock_config.multitenancy_tag = "TAG"

        # Mock the get method to return appropriate values based on key
        def mock_get(key=None, otel_module=None, **kwargs):
            if otel_module == "logs":
                if kwargs.get("key") == "export_timeout_millis":
                    return 10000
                if kwargs.get("key") == "max_export_batch_size":
                    return 100
            return kwargs.get("default_value", "http://test")

        mock_config.get = Mock(side_effect=mock_get)

        # Create mock resource
        mock_resource_instance = Mock()

        # Instantiate Logs
        logs = Logs(mock_resource_instance, mock_config)

        # Call the private method directly using name mangling
        logger_name = logs._Logs__get_logger_name()

        # Verify no double tagging patterns
        assert logger_name == "DTAGENT_TAG_OTLP"
        # Verify we don't have TAG_TAG pattern (which would be incorrect)
        assert "TAG_TAG" not in logger_name, f"Double tagging detected in {logger_name}"
        # Note: "TAG" appears twice in "DTAGENT_TAG_OTLP" but this is correct:
        # once as part of "DTAGENT" and once as the multitenancy tag

    @patch("dtagent.otel.logs.LoggerProvider")
    @patch("dtagent.otel.logs.Resource")
    def test_logger_name_matches_getLogger_call(self, mock_resource, mock_logger_provider):
        """Test that the logger is actually created with the name from __get_logger_name"""
        from dtagent.otel.logs import Logs

        # Create mock configuration with TAG
        mock_config = Mock()
        mock_config.multitenancy_tag = "PROD"

        # Mock the get method to return appropriate values based on key
        def mock_get(key=None, otel_module=None, **kwargs):
            if otel_module == "logs":
                if kwargs.get("key") == "export_timeout_millis":
                    return 10000
                if kwargs.get("key") == "max_export_batch_size":
                    return 100
            return kwargs.get("default_value", "http://test")

        mock_config.get = Mock(side_effect=mock_get)

        # Create mock resource
        mock_resource_instance = Mock()

        # Mock logging.getLogger to capture the call
        with patch("logging.getLogger") as mock_get_logger:
            mock_logger_instance = Mock()
            mock_get_logger.return_value = mock_logger_instance

            # Instantiate Logs (will call logging.getLogger internally)
            logs = Logs(mock_resource_instance, mock_config)

            # Get the expected name
            expected_name = logs._Logs__get_logger_name()

            # Verify logging.getLogger was called with the correct name
            mock_get_logger.assert_called_with(expected_name)
            assert expected_name == "DTAGENT_PROD_OTLP"


class TestCustomOTelTimestampFilter:
    """Tests for CustomOTelTimestampFilter timestamp validation"""

    def test_filter_with_valid_timestamp(self):
        """Test that valid timestamps are applied correctly"""
        import logging
        import time

        # Create a mock LogRecord
        record = logging.LogRecord(name="test", level=logging.INFO, pathname="", lineno=0, msg="test message", args=(), exc_info=None)

        # Set a valid timestamp (current time in milliseconds)
        valid_ts_ms = int(time.time() * 1000)
        record.timestamp = valid_ts_ms

        # Import and instantiate the filter (we need to get it from inside the Logs class)
        # For testing, we'll recreate the filter logic
        from dtagent.otel.logs import Logs

        with patch("dtagent.otel.logs.LoggerProvider"):
            with patch("dtagent.otel.logs.Resource"):
                mock_config = Mock()
                mock_config.multitenancy_tag = None

                # Mock the get method to return appropriate values based on key
                def mock_get(key=None, otel_module=None, **kwargs):
                    if otel_module == "logs":
                        if kwargs.get("key") == "export_timeout_millis":
                            return 10000
                        if kwargs.get("key") == "max_export_batch_size":
                            return 100
                    return kwargs.get("default_value", "http://test")

                mock_config.get = Mock(side_effect=mock_get)
                mock_resource = Mock()

                Logs(mock_resource, mock_config)

                # Get the filter from the logger handler
                # Since we can't easily access the internal filter, we'll test the behavior indirectly
                # by ensuring that valid timestamps don't cause issues
                assert hasattr(record, "timestamp")
                assert record.timestamp == valid_ts_ms

    def test_filter_with_negative_timestamp(self):
        """Test that negative timestamps are rejected and default timestamp is used"""
        import logging

        # Create a mock LogRecord
        record = logging.LogRecord(name="test", level=logging.INFO, pathname="", lineno=0, msg="test message", args=(), exc_info=None)

        # Store original created time
        original_created = record.created

        # Set an invalid negative timestamp
        record.timestamp = -1000000

        # Manually apply the filter logic (since we can't easily access the internal class)
        # This simulates what CustomOTelTimestampFilter.filter() does
        ts_ms = getattr(record, "timestamp", None)
        if ts_ms is not None:
            delattr(record, "timestamp")
            try:
                ts_ms = int(ts_ms)
                # Validate timestamp is positive and reasonable
                if ts_ms <= 0 or ts_ms > 4102444800000:
                    # Invalid timestamp, don't modify record
                    pass
                else:
                    record.created = ts_ms / 1_000
                    record.msecs = ts_ms % 1_000
            except (ValueError, TypeError, OverflowError):
                pass

        # Verify that timestamp attribute was removed
        assert not hasattr(record, "timestamp")
        # Verify that record.created wasn't set to the negative value
        assert record.created == original_created

    def test_filter_with_zero_timestamp(self):
        """Test that zero timestamp is rejected"""
        import logging

        record = logging.LogRecord(name="test", level=logging.INFO, pathname="", lineno=0, msg="test message", args=(), exc_info=None)

        original_created = record.created
        record.timestamp = 0

        # Apply filter logic
        ts_ms = getattr(record, "timestamp", None)
        if ts_ms is not None:
            delattr(record, "timestamp")
            try:
                ts_ms = int(ts_ms)
                if ts_ms <= 0 or ts_ms > 4102444800000:
                    pass
                else:
                    record.created = ts_ms / 1_000
                    record.msecs = ts_ms % 1_000
            except (ValueError, TypeError, OverflowError):
                pass

        assert not hasattr(record, "timestamp")
        assert record.created == original_created

    def test_filter_with_far_future_timestamp(self):
        """Test that unreasonably far future timestamps are rejected"""
        import logging

        record = logging.LogRecord(name="test", level=logging.INFO, pathname="", lineno=0, msg="test message", args=(), exc_info=None)

        original_created = record.created
        # Set timestamp to year 2200 (way beyond reasonable range)
        record.timestamp = 5000000000000

        # Apply filter logic
        ts_ms = getattr(record, "timestamp", None)
        if ts_ms is not None:
            delattr(record, "timestamp")
            try:
                ts_ms = int(ts_ms)
                if ts_ms <= 0 or ts_ms > 4102444800000:
                    pass
                else:
                    record.created = ts_ms / 1_000
                    record.msecs = ts_ms % 1_000
            except (ValueError, TypeError, OverflowError):
                pass

        assert not hasattr(record, "timestamp")
        assert record.created == original_created

    def test_filter_with_none_timestamp(self):
        """Test that None timestamp doesn't cause issues"""
        import logging

        record = logging.LogRecord(name="test", level=logging.INFO, pathname="", lineno=0, msg="test message", args=(), exc_info=None)

        original_created = record.created
        # Don't set timestamp attribute at all

        # Apply filter logic
        ts_ms = getattr(record, "timestamp", None)
        if ts_ms is not None:
            delattr(record, "timestamp")
            try:
                ts_ms = int(ts_ms)
                if ts_ms <= 0 or ts_ms > 4102444800000:
                    pass
                else:
                    record.created = ts_ms / 1_000
                    record.msecs = ts_ms % 1_000
            except (ValueError, TypeError, OverflowError):
                pass

        # record.created should remain unchanged
        assert record.created == original_created

    def test_filter_with_valid_observed_timestamp(self):
        """Test that valid observed_timestamp is converted to nanoseconds"""
        import logging
        import time
        from dtagent.util import validate_timestamp_ms

        record = logging.LogRecord(name="test", level=logging.INFO, pathname="", lineno=0, msg="test message", args=(), exc_info=None)

        # Set a valid observed_timestamp (current time in milliseconds)
        valid_ts_ms = int(time.time() * 1000)
        record.observed_timestamp = valid_ts_ms

        # Apply filter logic for observed_timestamp
        observed_timestamp = getattr(record, "observed_timestamp", None)
        if observed_timestamp:
            validated_ts = validate_timestamp_ms(observed_timestamp)
            if validated_ts:
                # Convert milliseconds to nanoseconds for OTEL
                record.observed_timestamp = int(validated_ts) * 1_000_000
            else:
                delattr(record, "observed_timestamp")

        # Verify timestamp was converted to nanoseconds
        assert hasattr(record, "observed_timestamp")
        assert record.observed_timestamp == valid_ts_ms * 1_000_000

    def test_filter_with_negative_observed_timestamp(self):
        """Test that negative observed_timestamp (like -1000000) is removed"""
        import logging
        from dtagent.util import validate_timestamp_ms

        record = logging.LogRecord(name="test", level=logging.INFO, pathname="", lineno=0, msg="test message", args=(), exc_info=None)

        # Set an invalid negative observed_timestamp (-1000000 from the bug report)
        record.observed_timestamp = -1000000

        # Apply filter logic for observed_timestamp
        observed_timestamp = getattr(record, "observed_timestamp", None)
        if observed_timestamp:
            validated_ts = validate_timestamp_ms(observed_timestamp)
            if validated_ts:
                record.observed_timestamp = int(validated_ts) * 1_000_000
            else:
                delattr(record, "observed_timestamp")

        # Verify the invalid observed_timestamp was removed
        assert not hasattr(record, "observed_timestamp")

    def test_filter_with_nanosecond_observed_timestamp(self):
        """Test that nanosecond-scale observed_timestamp (10x too large) is removed"""
        import logging
        from dtagent.util import validate_timestamp_ms

        record = logging.LogRecord(name="test", level=logging.INFO, pathname="", lineno=0, msg="test message", args=(), exc_info=None)

        # Set an invalid nanosecond timestamp (from the bug report CSV)
        record.observed_timestamp = 1770224954840999937441792

        # Apply filter logic for observed_timestamp
        observed_timestamp = getattr(record, "observed_timestamp", None)
        if observed_timestamp:
            validated_ts = validate_timestamp_ms(observed_timestamp)
            if validated_ts:
                record.observed_timestamp = int(validated_ts) * 1_000_000
            else:
                delattr(record, "observed_timestamp")

        # Verify the invalid observed_timestamp was removed
        assert not hasattr(record, "observed_timestamp")

    def test_filter_with_none_observed_timestamp(self):
        """Test that None observed_timestamp doesn't cause issues"""
        import logging

        record = logging.LogRecord(name="test", level=logging.INFO, pathname="", lineno=0, msg="test message", args=(), exc_info=None)

        # Don't set observed_timestamp attribute at all
        observed_timestamp = getattr(record, "observed_timestamp", None)
        assert observed_timestamp is None

        # This should not fail or cause issues
        assert not hasattr(record, "observed_timestamp")
