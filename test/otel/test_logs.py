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
