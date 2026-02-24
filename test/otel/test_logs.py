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

    @pytest.fixture
    def logs_instance(self):
        """Create a Logs instance for testing"""
        from dtagent.otel.logs import Logs

        with patch("dtagent.otel.logs.LoggerProvider"):
            with patch("dtagent.otel.logs.Resource"):
                mock_config = Mock()
                mock_config.multitenancy_tag = None

                def mock_get(key=None, otel_module=None, **kwargs):
                    if otel_module == "logs":
                        if kwargs.get("key") == "export_timeout_millis":
                            return 10000
                        if kwargs.get("key") == "max_export_batch_size":
                            return 100
                    return kwargs.get("default_value", "http://test")

                mock_config.get = Mock(side_effect=mock_get)
                mock_resource = Mock()

                logs = Logs(mock_resource, mock_config)
                yield logs

    def get_filter(self, logs_instance):
        """Extract the CustomOTelTimestampFilter from the logger"""
        # The filter is added to the handler, which is added to the logger
        if logs_instance._otel_logger and logs_instance._otel_logger.handlers:
            handler = logs_instance._otel_logger.handlers[0]
            if handler.filters:
                return handler.filters[0]
        return None

    def test_filter_with_valid_timestamp(self, logs_instance):
        """Test that valid timestamps are applied correctly"""
        import logging
        import time

        filter_instance = self.get_filter(logs_instance)
        assert filter_instance is not None, "Could not retrieve filter from logger"

        # Create a mock LogRecord
        record = logging.LogRecord(name="test", level=logging.INFO, pathname="", lineno=0, msg="test message", args=(), exc_info=None)

        # Set a valid timestamp (current time in milliseconds)
        valid_ts_ms = int(time.time() * 1000)
        record.timestamp = valid_ts_ms

        # Apply the filter
        result = filter_instance.filter(record)

        # Verify filter returned True
        assert result is True
        # Verify timestamp attribute was removed
        assert not hasattr(record, "timestamp")
        # Verify created and msecs were set correctly
        assert abs(record.created - (valid_ts_ms / 1000)) < 0.001  # Allow small float precision difference
        assert record.msecs == valid_ts_ms % 1000

    def test_filter_with_negative_timestamp(self, logs_instance):
        """Test that negative timestamps are rejected and default timestamp is used"""
        import logging

        filter_instance = self.get_filter(logs_instance)
        assert filter_instance is not None

        record = logging.LogRecord(name="test", level=logging.INFO, pathname="", lineno=0, msg="test message", args=(), exc_info=None)

        # Store original created time
        original_created = record.created

        # Set an invalid negative timestamp
        record.timestamp = -1000000

        # Apply the filter
        filter_instance.filter(record)

        # Verify that timestamp attribute was removed
        assert not hasattr(record, "timestamp")
        # Verify that record.created wasn't set to the negative value
        assert record.created == original_created

    def test_filter_with_zero_timestamp(self, logs_instance):
        """Test that zero timestamp is rejected"""
        import logging

        filter_instance = self.get_filter(logs_instance)
        assert filter_instance is not None

        record = logging.LogRecord(name="test", level=logging.INFO, pathname="", lineno=0, msg="test message", args=(), exc_info=None)

        original_created = record.created
        record.timestamp = 0

        filter_instance.filter(record)

        assert not hasattr(record, "timestamp")
        assert record.created == original_created

    def test_filter_with_far_future_timestamp(self, logs_instance):
        """Test that unreasonably far future timestamps are rejected"""
        import logging

        filter_instance = self.get_filter(logs_instance)
        assert filter_instance is not None

        record = logging.LogRecord(name="test", level=logging.INFO, pathname="", lineno=0, msg="test message", args=(), exc_info=None)

        original_created = record.created
        # Set timestamp to year 2200 (way beyond reasonable range)
        record.timestamp = 5000000000000

        filter_instance.filter(record)

        assert not hasattr(record, "timestamp")
        assert record.created == original_created

    def test_filter_with_none_timestamp(self, logs_instance):
        """Test that None timestamp doesn't cause issues"""
        import logging

        filter_instance = self.get_filter(logs_instance)
        assert filter_instance is not None

        record = logging.LogRecord(name="test", level=logging.INFO, pathname="", lineno=0, msg="test message", args=(), exc_info=None)

        original_created = record.created
        # Don't set timestamp attribute at all

        filter_instance.filter(record)

        # record.created should remain unchanged
        assert record.created == original_created

    def test_filter_with_valid_observed_timestamp(self, logs_instance):
        """Test that valid observed_timestamp is converted to nanoseconds"""
        import logging
        import time

        filter_instance = self.get_filter(logs_instance)
        assert filter_instance is not None

        record = logging.LogRecord(name="test", level=logging.INFO, pathname="", lineno=0, msg="test message", args=(), exc_info=None)

        # Set a valid observed_timestamp (current time in milliseconds)
        valid_ts_ms = int(time.time() * 1000)
        record.observed_timestamp = valid_ts_ms

        filter_instance.filter(record)

        # Verify timestamp was converted to nanoseconds
        assert hasattr(record, "observed_timestamp")
        assert record.observed_timestamp == valid_ts_ms * 1_000_000

    def test_filter_with_negative_observed_timestamp(self, logs_instance):
        """Test that negative observed_timestamp (like -1000000) is removed"""
        import logging

        filter_instance = self.get_filter(logs_instance)
        assert filter_instance is not None

        record = logging.LogRecord(name="test", level=logging.INFO, pathname="", lineno=0, msg="test message", args=(), exc_info=None)

        # Set an invalid negative observed_timestamp (-1000000 from the bug report)
        record.observed_timestamp = -1000000

        filter_instance.filter(record)

        # Verify the invalid observed_timestamp was removed
        assert not hasattr(record, "observed_timestamp")

    def test_filter_with_picosecond_observed_timestamp(self, logs_instance):
        """Test that picosecond-scale observed_timestamp is auto-converted and then to nanoseconds"""
        import logging
        import time

        filter_instance = self.get_filter(logs_instance)
        assert filter_instance is not None

        record = logging.LogRecord(name="test", level=logging.INFO, pathname="", lineno=0, msg="test message", args=(), exc_info=None)

        # Set a picosecond timestamp (current time scaled to picoseconds)
        # This ensures the timestamp is in valid range after conversion
        current_ms = int(time.time() * 1000)
        picosecond_ts = current_ms * 1_000_000_000  # Convert ms to picoseconds

        record.observed_timestamp = picosecond_ts

        filter_instance.filter(record)

        # Verify the timestamp was auto-converted to milliseconds, validated, and converted to nanoseconds
        # The picosecond value should be divided by 1e9 to get milliseconds
        # Then multiplied by 1e6 to get nanoseconds
        assert hasattr(record, "observed_timestamp")
        expected_ns = current_ms * 1_000_000
        assert record.observed_timestamp == expected_ns

    def test_filter_with_out_of_range_picosecond_timestamp(self, logs_instance):
        """Test that out-of-range femtosecond/picosecond timestamp is preserved (skip_range_validation for observed_timestamp)"""
        import logging

        filter_instance = self.get_filter(logs_instance)
        assert filter_instance is not None

        record = logging.LogRecord(name="test", level=logging.INFO, pathname="", lineno=0, msg="test message", args=(), exc_info=None)

        # This specific value from the bug report is detected as femtoseconds (> 4.1e21)
        # With skip_range_validation=True, observed_timestamp preserves original timestamps
        record.observed_timestamp = 1770224954840999937441792

        filter_instance.filter(record)

        # Verify the observed_timestamp was converted (from femtoseconds to nanoseconds) and preserved
        # even though it may be out of typical range (skip_range_validation=True)
        assert hasattr(record, "observed_timestamp")
        # Should be converted from femtoseconds to nanoseconds (divided by 1_000_000)
        assert record.observed_timestamp == 1770224954840999937441792 // 1_000_000

    def test_filter_with_none_observed_timestamp(self, logs_instance):
        """Test that None observed_timestamp doesn't cause issues"""
        import logging

        filter_instance = self.get_filter(logs_instance)
        assert filter_instance is not None

        record = logging.LogRecord(name="test", level=logging.INFO, pathname="", lineno=0, msg="test message", args=(), exc_info=None)

        # Don't set observed_timestamp attribute at all
        filter_instance.filter(record)

        # This should not fail or cause issues
        assert not hasattr(record, "observed_timestamp")

    def test_filter_with_both_timestamp_and_observed_timestamp(self, logs_instance):
        """Test that both timestamp and observed_timestamp are handled correctly together"""
        import logging
        import time

        filter_instance = self.get_filter(logs_instance)
        assert filter_instance is not None

        record = logging.LogRecord(name="test", level=logging.INFO, pathname="", lineno=0, msg="test message", args=(), exc_info=None)

        # Set both valid timestamps
        valid_ts_ms = int(time.time() * 1000)
        record.timestamp = valid_ts_ms
        record.observed_timestamp = valid_ts_ms + 1000  # 1 second later

        filter_instance.filter(record)

        # Verify timestamp was applied to record timing
        assert not hasattr(record, "timestamp")
        assert abs(record.created - (valid_ts_ms / 1000)) < 0.001

        # Verify observed_timestamp was converted to nanoseconds
        assert hasattr(record, "observed_timestamp")
        assert record.observed_timestamp == (valid_ts_ms + 1000) * 1_000_000

    def test_filter_with_string_timestamp(self, logs_instance):
        """Test that string timestamps that can be converted work correctly"""
        import logging
        import time

        filter_instance = self.get_filter(logs_instance)
        assert filter_instance is not None

        record = logging.LogRecord(name="test", level=logging.INFO, pathname="", lineno=0, msg="test message", args=(), exc_info=None)

        # Set a valid timestamp as a string
        valid_ts_ms = int(time.time() * 1000)
        record.timestamp = str(valid_ts_ms)

        filter_instance.filter(record)

        # Verify timestamp was converted and applied
        assert not hasattr(record, "timestamp")
        assert abs(record.created - (valid_ts_ms / 1000)) < 0.001

    def test_filter_with_invalid_string_timestamp(self, logs_instance):
        """Test that invalid string timestamps are handled gracefully"""
        import logging

        filter_instance = self.get_filter(logs_instance)
        assert filter_instance is not None

        record = logging.LogRecord(name="test", level=logging.INFO, pathname="", lineno=0, msg="test message", args=(), exc_info=None)

        original_created = record.created
        # Set an invalid string timestamp
        record.timestamp = "not_a_number"

        filter_instance.filter(record)

        # Verify timestamp was removed but record.created wasn't changed
        assert not hasattr(record, "timestamp")
        assert record.created == original_created
