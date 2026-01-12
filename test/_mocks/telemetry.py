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
import os
import json
import re
import datetime
from typing import Any, Dict, List
from contextlib import contextmanager
from unittest.mock import MagicMock, patch, Mock

from git import Union

from dtagent.context import RUN_ID_KEY, RUN_RESULTS_KEY


class MockTelemetryClient:

    def __init__(self, test_source: str):
        self.test_source = test_source
        if self.test_source:
            self.test_results_dir = f"test/test_results/{self.test_source}/"
            self.expected_results = self._load_test_results()
        else:
            self.test_results_dir = None
            self.expected_results = {}
        self.is_test_results_missing = not self.expected_results
        self.test_results: Dict[str, List[Any]] = {}

    def store_or_test_results(self, disabled_telemetry: List[str] = None) -> None:
        """Store the collected test results into files for future reference."""
        # Remove duplicates while preserving order
        dedup_results = {}
        for telemetry_type, content in self.test_results.items():
            seen = set()
            dedup_results[telemetry_type] = []
            for item in content:
                # Convert dicts to a hashable type for deduplication
                key = json.dumps(item, sort_keys=True) if isinstance(item, dict) else str(item)
                if key not in seen:
                    seen.add(key)
                    dedup_results[telemetry_type].append(item)
        self.test_results = dedup_results

        # store or test results
        if self.is_test_results_missing:
            for telemetry_type, content in self.test_results.items():
                self._save_telemetry_test_data(telemetry_type, content)
        else:
            disabled_telemetry = disabled_telemetry or []
            # otherwise we will test if save_test_results would match expected results
            for telemetry_type, expected_content in self.expected_results.items():
                # skip disabled telemetry types
                if telemetry_type in disabled_telemetry:
                    continue

                actual_content = self.test_results.get(telemetry_type, [])

                # Sort both lists for comparison, handling dicts by serializing with sorted keys
                def sort_key(item):
                    if isinstance(item, dict):
                        return json.dumps(item, sort_keys=True)
                    return str(item)

                sorted_actual = sorted(actual_content, key=sort_key)
                sorted_expected = sorted(expected_content, key=sort_key)
                import difflib

                if telemetry_type == "logs":
                    for entry in sorted_actual:
                        # this should be always present in OTEL logs but is dynamically added by SDK per log
                        assert entry.pop("code.file.path"), "Expected 'code.file.path' in log attributes"
                        assert entry.pop("code.function.name"), "Expected 'code.function.name' in log attributes"
                        assert entry.pop("code.line.number"), "Expected 'code.line.number' in log attributes"

                if sorted_actual != sorted_expected:
                    _, filepath = self._determine_file_name(telemetry_type)
                    if telemetry_type == "metrics":
                        diff = "\n".join(
                            difflib.unified_diff(sorted_expected, sorted_actual, fromfile="expected", tofile="actual", lineterm="")
                        )
                    else:
                        expected_str = json.dumps(sorted_expected, indent=2, sort_keys=True)
                        actual_str = json.dumps(sorted_actual, indent=2, sort_keys=True)
                        diff = "\n".join(
                            difflib.unified_diff(
                                expected_str.splitlines(), actual_str.splitlines(), fromfile="expected", tofile="actual", lineterm=""
                            )
                        )
                        if telemetry_type == "biz_events":
                            if isinstance(sorted_actual, list):
                                for entry in sorted_actual:
                                    entry["data"].pop(RUN_RESULTS_KEY, None)
                            else:
                                sorted_actual["data"].pop(RUN_RESULTS_KEY, None)

                    assert (
                        sorted_actual == sorted_expected
                    ), f"Telemetry type {telemetry_type} does not match expected results from {filepath}:\n\nDiff:\n{diff}"

    @contextmanager
    def mock_telemetry_sending(self):
        with (
            patch("requests.sessions.Session.post") as mock_session_post,
            patch("dtagent.otel.metrics.requests.post") as mock_metrics,
            patch("dtagent.otel.events.generic.requests.post") as mock_generic_events,
            patch("dtagent.otel.events.davis.requests.post") as mock_davis_events,
            patch("dtagent.otel.events.bizevents.requests.post") as mock_bizevents,
            patch("snowflake.snowpark.Session.sql") as mock_sql,
        ):
            # Set up HTTP mocks
            mock_session_post.side_effect = self._side_effect_function
            mock_metrics.side_effect = self._side_effect_function
            mock_generic_events.side_effect = self._side_effect_function
            mock_davis_events.side_effect = self._side_effect_function
            mock_bizevents.side_effect = self._side_effect_function

            # Set up session.sql mock to prevent actual Snowflake calls
            current_time = datetime.datetime.now(datetime.timezone.utc)
            one_hour_ago = current_time - datetime.timedelta(hours=1)
            mock_sql_instance = Mock()
            mock_row = Mock()
            mock_row.__getitem__ = Mock(return_value=one_hour_ago)
            mock_sql_instance.collect.return_value = [mock_row]
            mock_sql.return_value = mock_sql_instance

            yield

    def _load_test_results(self) -> Dict[str, Any]:
        """Load expected test results from files into a dictionary."""
        telemetry_types = ["logs", "spans", "metrics", "events", "biz_events"]
        expected_results = {}
        for telemetry_type in telemetry_types:
            data = self._load_telemetry_test_data(telemetry_type)
            if data is not None:
                expected_results[telemetry_type] = data if telemetry_type != "metrics" else data.split("\n")
        return expected_results

    def _determine_file_name(self, telemetry_type: str) -> tuple[str, str]:
        """Determines file path and extension based on given telemetry type

        Args:
            telemetry_type (str): telemetry type name

        Returns:
            tuple[str, str]: file path and extension for given telemetry type
        """
        ext = "txt" if telemetry_type == "metrics" else "json"
        filepath = os.path.join(self.test_results_dir, f"{telemetry_type}.{ext}") if self.test_results_dir else None
        return ext, filepath

    def _load_telemetry_test_data(self, telemetry_type: str) -> Any:
        """Load telemetry test data from a file.

        Args:
            telemetry_type: The type of telemetry data ("logs", "spans", "metrics", "events", "biz_events").

        Returns:
            The loaded telemetry data.
        """
        ext, filepath = self._determine_file_name(telemetry_type)

        if filepath and os.path.exists(filepath):
            with open(filepath, "r", encoding="utf-8") as f:
                if ext == "json":
                    try:
                        return json.load(f)
                    except json.JSONDecodeError as e:
                        print(f"Error decoding JSON from file {filepath}: {e}")

                return f.read()
        return None

    def _save_telemetry_test_data(self, telemetry_type: str, content: List[Union[str, dict, bytes]]) -> None:
        """Save telemetry test data to a file.

        Args:
            telemetry_type: The type of telemetry data ("logs", "spans", "metrics", "events", "biz_events").
            content: The telemetry data to save.
        """
        ext, filepath = self._determine_file_name(telemetry_type)

        if filepath:
            os.makedirs(os.path.dirname(filepath), exist_ok=True)

            with open(filepath, "w", encoding="utf-8") as f:
                if ext == "json":
                    try:
                        json.dump(content, f, indent=2, default=str)  # Convert non-serializable to string
                    except (TypeError, ValueError, OSError) as e:
                        print(f"Error saving JSON to {filepath}: {e}")
                else:
                    f.write("\n".join(content))

    def _decode_object_from_protobuf(self, protobuf_bytes: bytes, telemetry_type: str = "logs") -> List[Dict[str, Any]]:
        """Decode protobuf logs to extract key-value pairs from log bodies.

        Args:
            protobuf_bytes: The binary protobuf data from OpenTelemetry logs
            telemetry_type: The type of telemetry data ("logs" or "spans").

        Returns:
            A list of dictionaries representing the extracted key-value pairs.
        """
        from opentelemetry.proto.collector.logs.v1.logs_service_pb2 import ExportLogsServiceRequest
        from opentelemetry.proto.collector.trace.v1.trace_service_pb2 import ExportTraceServiceRequest

        def __extract_value(kv_pair):
            """Extracts the value from a key-value pair in protobuf stream based on its type.

            Args:
                    kv_pair: The key-value pair to extract the value from.

            Returns:
                    The extracted value.
            """
            value_field = getattr(kv_pair, "value", kv_pair)
            extracted_value = None
            if value_field.HasField("string_value"):
                extracted_value = value_field.string_value
            elif value_field.HasField("int_value"):
                extracted_value = value_field.int_value
            elif value_field.HasField("double_value"):
                extracted_value = value_field.double_value
            elif value_field.HasField("bool_value"):
                extracted_value = value_field.bool_value
            elif value_field.HasField("bytes_value"):
                extracted_value = value_field.bytes_value.hex()
            elif value_field.HasField("array_value"):
                extracted_value = [__extract_value(v) for v in value_field.array_value.values]
            elif value_field.HasField("kvlist_value"):
                extracted_value = {kv.key: __extract_value(kv) for kv in value_field.kvlist_value.values}
            else:
                extracted_value = str(value_field)

            return extracted_value

        request = ExportLogsServiceRequest() if telemetry_type == "logs" else ExportTraceServiceRequest()
        request.ParseFromString(protobuf_bytes)

        kv_data = []
        for resource in getattr(request, f"resource_{telemetry_type}"):
            for scope in getattr(resource, f"scope_{telemetry_type}"):
                for record in scope.log_records if telemetry_type == "logs" else scope.spans:
                    kv_datum = {}
                    kv_pairs = None
                    if telemetry_type == "logs":
                        kv_pairs = list(record.attributes or [])
                        if record.body.HasField("kvlist_value"):
                            kv_pairs |= record.body.kvlist_value.values
                        else:
                            kv_datum["content"] = __extract_value(record.body)
                    elif telemetry_type == "spans":
                        kv_pairs = record.attributes

                        for event in record.events:
                            event_name = event.name
                            kv_datum[f"event_{event_name}_name"] = event_name
                            for kv_pair in event.attributes:
                                key = f"event_{event_name}_{kv_pair.key}"
                                value = __extract_value(kv_pair)
                                kv_datum[key] = value
                    if kv_pairs:
                        for kv_pair in kv_pairs:
                            key = kv_pair.key
                            value = __extract_value(kv_pair)
                            kv_datum[key] = value

                    if kv_datum:
                        kv_data.append(kv_datum)

        return kv_data

    def _side_effect_function(self, *args, **kwargs):
        """Side effect function to handle telemetry data processing.
        It ensures proper status codes are set for different telemetry types.
        It collects sent telemetry data into test_results for later verification.
        It also checks against expected_results if available.
        """

        def __determine_telemetry_type(url: str, mock_response: MagicMock) -> str:
            """Returns telemetry type based on the URL for the request.
            Sets the correct status code for the mock response.

            Args:
                url (str): The URL for the request.
                mock_response (MagicMock): The mock response object to set the status code on.

            Returns:
                str: The determined telemetry type.
            """
            from dtagent.otel.events.bizevents import BizEvents
            from dtagent.otel.events.generic import GenericEvents
            from dtagent.otel.events.davis import DavisEvents
            from dtagent.otel.logs import Logs
            from dtagent.otel.metrics import Metrics
            from dtagent.otel.spans import Spans

            telemetry_type = None

            if url.endswith(BizEvents.ENDPOINT_PATH):
                telemetry_type = "biz_events"
                mock_response.status_code = 202
            elif url.endswith(GenericEvents.ENDPOINT_PATH):
                telemetry_type = "events"
                mock_response.status_code = 202
            elif url.endswith(DavisEvents.ENDPOINT_PATH):
                telemetry_type = "davis_events"
                mock_response.status_code = 201
            elif url.endswith(Logs.ENDPOINT_PATH):
                telemetry_type = "logs"
                mock_response.status_code = 200
            elif url.endswith(Spans.ENDPOINT_PATH):
                telemetry_type = "spans"
                mock_response.status_code = 200
            elif url.endswith(Metrics.ENDPOINT_PATH):
                telemetry_type = "metrics"
                mock_response.status_code = 202

            return telemetry_type

        def __determine_url_and_data(args, kwargs) -> tuple[str, Any]:
            """Handle both requests.post mocks (args[0] is url) and CustomLoggingSession.send mocks (args[0] is request)

            Args:
                *args: Positional arguments
                **kwargs: Keyword arguments

            Returns:
                tuple[str, Any]: A tuple containing the URL and data for the request.
            """
            if args and hasattr(args[0], "url"):
                url = args[0].url
            elif "url" in kwargs:
                url = kwargs["url"]
            else:
                url = args[0]

            if args and hasattr(args[0], "body"):
                data = args[0].body
            else:
                data = kwargs.get("data", "")

            return url, data

        def __cleanup_telemetry_dict(data_dict: Dict[str, Any]) -> Dict[str, Any]:
            """Remove dynamic fields from telemetry data dictionary for comparison.

            Args:
                data_dict (Dict[str, Any]): The telemetry data dictionary.

            Returns:
                Dict[str, Any]: The cleaned telemetry data dictionary.
            """
            # Remove fields changing values per run
            cleaned_dict = {
                k: __cleanup_telemetry_dict(v) if isinstance(v, dict) else v
                for k, v in data_dict.items()
                if k.lower()
                not in (
                    # update by agent to fit the current run
                    "observed_timestamp",
                    "observed_at",
                    "timestamp",
                    "end_time",
                    "start_time",
                    "time",
                    "starttime",
                    "endtime",
                    "event.start",
                    "event.end",
                    # from event tests
                    "test.ts",
                    "test.event.dtagent.start_time",
                    "test.event.dtagent.end_time",
                    "test.event.dtagent.datetime",
                    # id in biz events and events is unique per event
                    "id",
                    # each agent run has a different run id
                    RUN_ID_KEY,
                    RUN_RESULTS_KEY,
                    "dsoa.task.exec.id",
                    # DSOA versions
                    "app.version",
                    "app.short_version",
                    "telemetry.exporter.version",
                )
            }
            return cleaned_dict

        def __cleanup_metric_lines(lines: str) -> List[str]:
            """Remove dynamic fields from metric lines for comparison and turns a multiline string into a list of lines.

            Args:
                lines (List[str]): The list of metric lines.
            """
            processed_lines = []
            for line in lines.split("\n"):
                if not line.strip().startswith("#"):
                    line = re.sub(r"(\s\d{13})\s*$", " 0", line)
                processed_lines.append(line)
            return processed_lines

        # Use the global test source instead of inspecting the stack
        source_context = self.test_source

        # Determine telemetry_type based on url and set up mock response
        mock_response = MagicMock()
        url, data = __determine_url_and_data(args, kwargs)
        telemetry_type = __determine_telemetry_type(url, mock_response)
        content = None

        # we are going to store the content into test_results
        if data and telemetry_type and source_context:
            if isinstance(data, (dict, str)):
                content = data
            elif isinstance(data, bytes):
                if telemetry_type in ("logs", "spans"):
                    content = self._decode_object_from_protobuf(data, telemetry_type=telemetry_type)
                else:
                    content = data.hex()
            if content:
                if telemetry_type != "metrics" and isinstance(content, (str, bytes)):
                    try:
                        content = json.loads(content)
                    except (json.JSONDecodeError, TypeError) as e:
                        print(f"Error decoding JSON from API call payload {content}: {e}")
                if telemetry_type not in self.test_results:
                    self.test_results[telemetry_type] = []

                if telemetry_type == "metrics" and isinstance(content, str):
                    content = __cleanup_metric_lines(content)

                for item in content if isinstance(content, list) else [content]:
                    if isinstance(item, dict):
                        item = __cleanup_telemetry_dict(item)

                    self.test_results[telemetry_type].append(item)

        if mock_response.status_code >= 300:
            print(f"###### PROBLEM SENDING {telemetry_type} TELEMETRY TO {url}; ERROR CODE: {mock_response.status_code} ######")

        return mock_response
