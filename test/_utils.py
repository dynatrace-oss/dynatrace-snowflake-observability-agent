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
import sys
import uuid
import datetime
from typing import Any, Generator, Union, Dict, List, Optional, Callable, Tuple
import logging
import json
import yaml
import jsonstrip
from unittest.mock import patch, Mock
from snowflake import snowpark
from dtagent.config import Configuration
from dtagent.connector import TelemetrySender
from dtagent import config
from dtagent.util import is_select_for_table
import test
from test import TestConfiguration
from test._mocks.telemetry import MockTelemetryClient
from build.utils import find_files, get_metric_semantics

TEST_CONFIG_FILE_NAME = "./test/conf/config-download.yml"


def _fixture_json_default(obj):
    """JSON encoder fallback for numpy/pandas types from Snowflake DataFrames.

    Args:
        obj: Object that is not natively JSON-serializable.

    Returns:
        A JSON-serializable Python primitive.

    Raises:
        TypeError: When the type cannot be coerced.
    """
    import math

    try:
        import numpy as np
        import pandas as pd
    except ImportError:
        return str(obj)

    if obj is pd.NaT:
        return None
    if isinstance(obj, np.integer):
        return int(obj)
    if isinstance(obj, np.floating):
        v = float(obj)
        return None if (math.isnan(v) or math.isinf(v)) else v
    if isinstance(obj, np.bool_):
        return bool(obj)
    if isinstance(obj, pd.Timestamp):
        return obj.isoformat()
    if isinstance(obj, (datetime.datetime, datetime.date)):
        return obj.isoformat()
    if isinstance(obj, (bytes, bytearray)):
        import base64

        return base64.b64encode(obj).decode("ascii")
    return str(obj)


def _dump_fixture_row(row_dict: dict) -> str:
    """Serialise a single row dict to a JSON string, replacing NaN/Inf with null.

    Args:
        row_dict: Row dictionary to serialise.

    Returns:
        JSON string representation of the row.
    """
    import math

    cleaned = {k: (None if isinstance(v, float) and (math.isnan(v) or math.isinf(v)) else v) for k, v in row_dict.items()}
    return json.dumps(cleaned, default=_fixture_json_default)


def _generate_fixture(session: snowpark.Session, t_data: str, fixture_path: str, operation: Optional[Callable] = None) -> None:
    """Generate an NDJSON fixture file from a live Snowflake table or SQL query.

    The output path must follow the ``{plugin_name}[_{view_suffix}].ndjson`` convention.

    Args:
        session (snowpark.Session): Active Snowflake Snowpark session.
        t_data (str): Table name or SELECT statement.
        fixture_path (str): Destination ``.ndjson`` file path.
        operation (Optional[Callable]): Optional DataFrame transform applied
            before serialisation (e.g. sorting).
    """
    import pandas as pd  # noqa: PLC0415

    if is_select_for_table(t_data):
        df_data = session.sql(t_data).collect()
        pd_data = pd.DataFrame(df_data)
    else:
        df_data = session.table(t_data)
        if operation:
            df_data = operation(df_data)
        pd_data = df_data.to_pandas()

    rows = [_dump_fixture_row(row.to_dict()) for _, row in pd_data.iterrows()]
    with open(fixture_path, "w", encoding="utf-8") as fh:
        fh.write("\n".join(rows) + ("\n" if rows else ""))
    print(f"Generated fixture {fixture_path} ({len(rows)} rows)")


def _generate_all_fixtures(session: snowpark.Session, fixtures: dict, force: bool = False) -> None:
    """Generate NDJSON fixture files for all tables in the fixtures dictionary.

    Args:
        session (snowpark.Session): Active Snowflake Snowpark session.
        fixtures (dict): Mapping of table names to fixture file paths.
        force (bool, optional): Re-generate even when files already exist. Defaults to False.
    """
    if force or should_generate_fixtures(fixtures.values()):
        for table_name, fixture_path in fixtures.items():
            _generate_fixture(session, table_name, fixture_path)


def _logging_findings(
    session: snowpark.Session, dtagent, log_tag: str, log_level: logging, show_detailed_logs: bool, disabled_telemetry: List[str] = None
) -> Dict[str, Dict[str, int]]:
    from test import is_local_testing

    if log_level != "":
        logging.basicConfig(level=log_level)
    if show_detailed_logs:
        from dtagent import LOG, LL_TRACE

        console_handler = logging.StreamHandler()  # Console handler
        LOG.addHandler(console_handler)
        LOG.setLevel(LL_TRACE)
        console_handler.setLevel(LL_TRACE)

        print(LOG.getEffectiveLevel())

    results = dtagent.process([str(log_tag)], False, disabled_telemetry=disabled_telemetry)
    dtagent.teardown()
    session.close()

    print(f"!!!! RESULTS = {results}")

    return results


def _get_fixture_entries(
    fixture_path: str,
    limit: int = None,
    adjust_ts: bool = True,
    start_time: str = "START_TIME",
    end_time: str = "END_TIME",
) -> Generator[Dict, None, None]:
    """Read fixture rows from an NDJSON file, optionally applying timestamp adjustment.

    Rows are repeated or truncated to satisfy *limit*.  Timestamps are adjusted
    via ``_adjust_timestamp`` so they fall within OTel ingestion bounds.

    No pandas dependency — uses stdlib ``json`` only.

    Args:
        fixture_path (str): Path to the ``.ndjson`` fixture file.
        limit (int, optional): Maximum number of rows to yield; rows are
            repeated when the fixture has fewer rows than *limit*.
        adjust_ts (bool, optional): Whether to adjust timestamps. Defaults to True.
        start_time (str, optional): Name of the start-time column. Defaults to ``START_TIME``.
        end_time (str, optional): Name of the end-time column. Defaults to ``END_TIME``.

    Yields:
        Dict: Row dictionaries from the fixture file.
    """
    from dtagent.util import _adjust_timestamp

    with open(fixture_path, "r", encoding="utf-8") as fh:
        raw_rows = [json.loads(line) for line in fh if line.strip()]

    if not raw_rows:
        return

    if limit is not None and 0 < len(raw_rows) < limit:
        n_full = limit // len(raw_rows)
        remainder = limit % len(raw_rows)
        raw_rows = raw_rows * n_full + raw_rows[:remainder]

    if limit is not None:
        raw_rows = raw_rows[:limit]

    print(f"Loaded fixture {fixture_path} ({len(raw_rows)} rows)")

    for row_dict in raw_rows:
        if adjust_ts:
            _adjust_timestamp(row_dict, start_time=start_time, end_time=end_time)
        yield row_dict


def _safe_get_fixture_entries(fixtures: dict, table_name: str, *args, **kwargs) -> Generator[Dict, None, None]:
    """Safely read fixture entries for *table_name* from the fixtures dictionary.

    Args:
        fixtures (dict): Mapping of table names to ``.ndjson`` fixture file paths.
        table_name (str): Table name key to look up.

    Returns:
        Generator[Dict, None, None]: Fixture rows for the requested table.

    Raises:
        ValueError: If *table_name* is not present in *fixtures*.
    """
    if table_name not in fixtures:
        raise ValueError(f"Unknown table name: {table_name}")
    return _get_fixture_entries(fixtures[table_name], *args, **kwargs)


def should_generate_fixtures(fixture_files) -> bool:
    """Return True when fixture files need to be (re-)generated from Snowflake.

    Generation is requested when the ``-p`` CLI flag is present or when any of
    the listed fixture files do not exist yet.

    Args:
        fixture_files: Iterable of fixture file paths to check.

    Returns:
        True if fixture regeneration is needed.
    """
    return (len(sys.argv) > 1 and sys.argv[1] == "-p") or any(not os.path.exists(f) for f in fixture_files)


def _merge_fixtures_from_tests() -> Dict[str, str]:
    """Merge all FIXTURES dictionaries from test_*.py files in the plugins directory.

    Returns:
        Dict mapping all table names to their corresponding ``.ndjson`` fixture paths.
    """
    import importlib
    import inspect

    fixtures: Dict[str, str] = {}
    plugins_dir = os.path.join(os.path.dirname(__file__), "plugins")
    for filename in os.listdir(plugins_dir):
        if filename.startswith("test_") and filename.endswith(".py"):
            module_name = f"test.plugins.{filename[:-3]}"
            try:
                module = importlib.import_module(module_name)
                for _, member in inspect.getmembers(module):
                    if inspect.isclass(member) and hasattr(member, "FIXTURES"):
                        fixtures.update(member.FIXTURES)
            except ImportError as exc:
                print(f"Could not import {module_name}: {exc}")
    return fixtures


class LocalTelemetrySender(TelemetrySender):
    FIXTURES = _merge_fixtures_from_tests()

    def __init__(self, session: snowpark.Session, params: dict, exec_id: str, limit_results: int = 2, config: TestConfiguration = None):

        self._local_config = config
        self.limit_results = limit_results

        TelemetrySender.__init__(self, session, params, exec_id)

        self._configuration.get_last_measurement_update = lambda *args, **kwargs: datetime.datetime.fromtimestamp(
            0, tz=datetime.timezone.utc
        )
        setattr(self._semantics, "_metric_semantics", get_metric_semantics(gen_metric_description_line=True))

    def _get_config(self, session: snowpark.Session) -> Configuration:
        return self._local_config if self._local_config else TelemetrySender._get_config(self, session)

    def _get_table_rows(self, t_data: str) -> Generator[Dict, None, None]:
        if t_data in self.FIXTURES:
            return _get_fixture_entries(self.FIXTURES[t_data], limit=self.limit_results)

        return TelemetrySender._get_table_rows(self, t_data)

    def _flush_logs(self) -> None:
        self._logs._otel_logger_provider.force_flush()


def telemetry_test_sender(
    session: snowpark.Session, sources: str, params: dict, limit_results: int = 2, config: TestConfiguration = None, test_source: str = None
) -> Tuple[int, int, int, int, int]:
    """Invoke send_data on a LocalTelemetrySender instance using NDJSON fixture data for testing.

    Args:
        session (snowpark.Session): The Snowflake session used to access tables.
        sources (str): The telemetry sources to send data from.
        params (dict): Parameters for the TelemetrySender.
        limit_results (int, optional): Limit on the number of results to process. Defaults to 2.
        config (TestConfiguration, optional): Configuration for the TelemetrySender. Defaults to None.
        test_source (str, optional): The source name for the telemetry test. Defaults to None.

    Returns:
        Tuple[int, int, int, int, int, int]: Count of objects, log lines, metrics, events, bizevents, and davis events sent
    """
    config._config["otel"]["spans"]["max_export_batch_size"] = 1
    config._config["otel"]["logs"]["max_export_batch_size"] = 1

    sender = LocalTelemetrySender(session, params, limit_results=limit_results, config=config, exec_id=str(uuid.uuid4().hex))

    mock_client = MockTelemetryClient(test_source)
    with mock_client.mock_telemetry_sending():
        results = sender.send_data(sources)
        sender._logs.shutdown_logger()
        sender._spans.shutdown_tracer()
    mock_client.store_or_test_results()

    return results


def execute_telemetry_test(
    agent_class,
    disabled_telemetry: List[str],
    base_count: Dict[str, Dict[str, int]],
    test_name: str,
    affecting_types_for_entries: List[str] = None,
):
    """Generalized test function for telemetry plugins.

    Args:
        agent_class: The agent class to instantiate
        test_name: Name of the test
        plugin_key: Key for the plugin in results
        disabled_telemetry: List of disabled telemetry types
        base_count: Base count for expectations for each telemetry type
        affecting_types_for_entries: Telemetry types that affect entries count
        metrics_at_least: Whether metrics should be at least or exactly the expected
    """
    from test import _get_session
    from dtagent.context import RUN_ID_KEY, RUN_RESULTS_KEY

    affecting_types_for_entries = affecting_types_for_entries or ["logs", "metrics", "spans"]

    config = get_config()
    session = _get_session()

    for telemetry_type in ("spans", "logs", "metrics", "events"):
        config._config["otel"][telemetry_type]["is_disabled"] = telemetry_type in disabled_telemetry

    results = _logging_findings(
        session,
        agent_class(session, config),
        test_name,
        logging.INFO,
        False,
        disabled_telemetry,
    )

    assert test_name in results
    assert RUN_RESULTS_KEY in results[test_name]

    for plugin_key in base_count.keys():
        assert plugin_key in results[test_name][RUN_RESULTS_KEY]

        logs_expected = base_count[plugin_key].get("log_lines", 0) if "logs" not in disabled_telemetry else 0
        spans_expected = base_count[plugin_key].get("spans", 0) if "spans" not in disabled_telemetry else 0
        metrics_expected = base_count[plugin_key].get("metrics", 0) if "metrics" not in disabled_telemetry else 0
        events_expected = base_count[plugin_key].get("events", 0) if "events" not in disabled_telemetry else 0
        entries_expected = (
            base_count[plugin_key].get("entries", 0) if (logs_expected + spans_expected + metrics_expected + events_expected > 0) else 0
        )

        assert results[test_name][RUN_RESULTS_KEY][plugin_key].get("entries", 0) == entries_expected
        assert results[test_name][RUN_RESULTS_KEY][plugin_key].get("log_lines", 0) == logs_expected
        assert results[test_name][RUN_RESULTS_KEY][plugin_key].get("spans", 0) == spans_expected
        assert results[test_name][RUN_RESULTS_KEY][plugin_key].get("metrics", 0) == metrics_expected
        assert results[test_name][RUN_RESULTS_KEY][plugin_key].get("events", 0) == events_expected


def get_config(pickle_conf: str = None) -> TestConfiguration:
    conf = {}
    if pickle_conf == "y":  # recreate the config file
        from test import _get_session

        session = _get_session()
        conf_class = config.Configuration(session)
        conf = conf_class._config

        with open(TEST_CONFIG_FILE_NAME, "w", encoding="utf-8") as f:
            yaml.safe_dump(conf, f)

    elif os.path.isfile(TEST_CONFIG_FILE_NAME):  # load existing config file
        with open(TEST_CONFIG_FILE_NAME, "r", encoding="utf-8") as f:
            conf = yaml.safe_load(f)
    else:  # we need to create the config from scratch with dummy settings based on defaults
        from dtagent.otel.metrics import Metrics
        from dtagent.otel.events.generic import GenericEvents
        from dtagent.otel.events.davis import DavisEvents
        from dtagent.otel.events.bizevents import BizEvents
        from dtagent.otel.logs import Logs
        from dtagent.otel.spans import Spans

        dt_url = "dsoa2025.live.dynatrace.com"
        sf_name = "test.dsoa2025"
        plugins = {}
        conf = {
            "dt.token": "dt0c01.XXXXXXXXXXXXXXXXXXXXXXXX.XXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXX",
            "logs.http": f"https://{dt_url}{Logs.ENDPOINT_PATH}",
            "spans.http": f"https://{dt_url}{Spans.ENDPOINT_PATH}",
            "metrics.http": f"https://{dt_url}{Metrics.ENDPOINT_PATH}",
            "events.http": f"https://{dt_url}{GenericEvents.ENDPOINT_PATH}",
            "davis_events.http": f"https://{dt_url}{DavisEvents.ENDPOINT_PATH}",
            "biz_events.http": f"https://{dt_url}{BizEvents.ENDPOINT_PATH}",
            "resource.attributes": Configuration.RESOURCE_ATTRIBUTES
            | {
                "service.name": sf_name,
                "deployment.environment": "TEST",
                "host.name": f"{sf_name}.snowflakecomputing.com",
            },
            "otel": {},
            "plugins": plugins,
        }
        for file_path in find_files("src/dtagent/plugins", "*-config.yml"):
            plugin_conf = lowercase_keys(read_clean_data_from_file(file_path, is_yaml=True))
            plugins.update(plugin_conf.get("plugins", {}))
        otel_config = lowercase_keys(read_clean_data_from_file("src/dtagent.conf/otel-config.yml", is_yaml=True))
        conf["otel"] |= otel_config.get("otel", {})
        conf["plugins"] |= otel_config.get("plugins", {})
        conf["metric_semantics"] = get_metric_semantics()

    return TestConfiguration(conf)


def read_clean_data_from_file(file_path: str, is_yaml: bool = False) -> Union[Dict, List[Dict], Any]:
    """Reads given file (YAML, JSON, JSONC) into a dictionary.
    In case this is JSONC a clean JSON content is provided before turning into dict

    Args:
        file_path (str): path to the file with YAML, JSON or JSONC content

    Returns:
        List[Dict]: dictionary based on the content of the YAML|JSON|JSONC file
    """
    logging.debug("Reading clean json file: %s", file_path)

    with open(file_path, "r", encoding="utf-8") as file:

        data_str = file.read()
        if is_yaml:
            data = yaml.safe_load(data_str)
        else:
            json_str = jsonstrip.strip(data_str)
            data = json.loads(json_str)

        return data

    return {}


def lowercase_keys(data: Any) -> Any:
    """Lowercases recursively all keys in a dictionary (including nested dictionaries and lists)

    Args:
        data (Any): Input data (dict, list, or other)

    Returns:
        Any: Data with all dictionary keys lowercased
    """
    if isinstance(data, dict):
        return {k.lower(): lowercase_keys(v) for k, v in data.items()}

    if isinstance(data, list):
        return [lowercase_keys(item) for item in data]

    return data


def is_blank(value):
    return value is None or value == ""
