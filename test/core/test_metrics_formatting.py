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


class TestMetricsFormatting:
    """Test that metrics are properly formatted with list dimensions converted to comma-separated strings."""

    def test_list_dimensions_in_metrics(self):
        """Test that list-type dimensions like db.snowflake.dbs are properly formatted in metric lines."""
        from unittest.mock import Mock, patch
        from dtagent.otel.metrics import Metrics
        from dtagent.otel.semantics import Semantics
        from dtagent.config import Configuration

        # Create a mock configuration
        config = Mock(spec=Configuration)
        config.get = Mock(return_value={})

        # Mock specific config calls
        def mock_get(*args, **kwargs):
            if len(args) > 0 and args[0] == "resource.attributes":
                return {"service.name": "test"}
            if "otel_module" in kwargs:
                if kwargs.get("key") == "max_retries":
                    return 5
                if kwargs.get("key") == "max_batch_size":
                    return 1000000
                if kwargs.get("key") == "retry_delay_ms":
                    return 10000
                if kwargs.get("key") == "api_post_timeout":
                    return 30
            return {}

        config.get.side_effect = mock_get

        # Create a mock semantics
        semantics = Mock(spec=Semantics)
        semantics.get_metric_definition = Mock(return_value="")

        # Create metrics instance
        metrics = Metrics(semantics, config)

        # Test data with list dimensions (simulating what comes from Snowflake)
        query_data = {
            "START_TIME": 1738786435157000000,
            "DIMENSIONS": {
                "db.namespace": "DTAGENT_DB",
                "db.snowflake.dbs": ["DTAGENT_DB"],  # List value
                "db.snowflake.tables": ["DTAGENT_DB.STATUS.MEASUREMENTS", "DTAGENT_DB.CONFIG.SETTINGS"],  # List with multiple values
                "db.user": "SYSTEM",
            },
            "METRICS": {"snowflake.data.scanned": 1024},
        }

        # Mock the _send_metrics to capture the payload
        captured_payload = []

        def capture_send_metrics(payload=None):
            if payload:
                captured_payload.append(payload)
            return 0

        with patch.object(metrics, "_send_metrics", side_effect=capture_send_metrics):
            metrics.report_via_metrics_api(query_data, context_name="test_context")

        # Verify the payload was generated
        assert len(captured_payload) > 0, "No payload was generated"

        payload = captured_payload[0]

        # Verify that list dimensions are converted to comma-separated strings
        # The dimension should be: db.snowflake.dbs="DTAGENT_DB" (not db.snowflake.dbs="['DTAGENT_DB']")
        assert 'db.snowflake.dbs="DTAGENT_DB"' in payload, f'Expected db.snowflake.dbs="DTAGENT_DB" but got: {payload}'

        # Verify that the problematic list representation is NOT present
        assert "['DTAGENT_DB']" not in payload, f"Found problematic list representation ['DTAGENT_DB'] in payload: {payload}"

        # Verify multiple values are joined with commas
        assert (
            'db.snowflake.tables="DTAGENT_DB.STATUS.MEASUREMENTS,DTAGENT_DB.CONFIG.SETTINGS"' in payload
        ), f"Expected comma-separated tables but got: {payload}"

        # Verify the metric line is properly formatted (no parsing errors would occur)
        lines = payload.strip().split("\n")
        metric_line = [line for line in lines if line and not line.startswith("#")][0]

        # Basic validation: metric line should have format: metric_name,dim1="val1",dim2="val2" value
        assert "snowflake.data.scanned," in metric_line, f"Invalid metric line format: {metric_line}"
        assert " 1024" in metric_line, f"Metric value not found in: {metric_line}"


if __name__ == "__main__":
    test = TestMetricsFormatting()
    test.test_list_dimensions_in_metrics()
    print("✓ All tests passed!")
