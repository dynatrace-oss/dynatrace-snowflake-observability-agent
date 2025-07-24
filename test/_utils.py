import os
import sys
import datetime
from typing import Generator, Dict, List, Optional, Callable, Tuple
import logging
import json
from test import TestDynatraceSnowAgent, _get_session
import fnmatch
import jsonstrip
from snowflake import snowpark
from dtagent.config import Configuration
from dtagent.connector import TelemetrySender
from dtagent import config
from dtagent.util import is_select_for_table

TEST_CONFIG_FILE_NAME = "./test/conf/config-download.json"


def _pickle_data_history(
    session: snowpark.Session, t_data: str, pickle_name: str, operation: Optional[Callable] = None
) -> Generator[Dict, None, None]:
    if is_select_for_table(t_data):
        import pandas as pd

        df_data = session.sql(t_data).collect()
        pd_data = pd.DataFrame(df_data)
    else:
        df_data = session.table(t_data)
        if operation:
            df_data = operation(df_data)
        pd_data = df_data.to_pandas()

    pd_data.to_pickle(pickle_name)
    print("Pickled " + str(pickle_name))


def _logging_findings(
    session: snowpark.Session,
    dtagent: TestDynatraceSnowAgent,
    log_tag: str,
    log_level: logging,
    show_detailed_logs: int,
):

    if log_level != "":
        logging.basicConfig(level=log_level)
    if show_detailed_logs != 0:
        from dtagent import LOG, LL_TRACE

        console_handler = logging.StreamHandler()  # Console handler
        LOG.addHandler(console_handler)
        LOG.setLevel(LL_TRACE)
        console_handler.setLevel(LL_TRACE)

        print(LOG.getEffectiveLevel())

    results = dtagent.process([str(log_tag)], False)
    print(f"!!!! RESULTS = {results}")

    dtagent.teardown()
    session.close()


def _get_unpickled_entries(
    pickle_name: str,
    limit: int = None,
    adjust_ts: bool = True,
    start_time: str = "START_TIME",
    end_time: str = "END_TIME",
) -> Generator[Dict, None, None]:
    import pandas as pd

    pandas_df = pd.read_pickle(pickle_name)

    print(f"Unpickled {pickle_name}")
    #####
    if limit is not None:
        pandas_df = pandas_df.head(limit)

    for _, row in pandas_df.iterrows():
        from dtagent.util import _adjust_timestamp

        row_dict = row.to_dict()
        if adjust_ts:
            _adjust_timestamp(row_dict, start_time=start_time, end_time=end_time)

        yield row_dict


def should_pickle(pickle_files: list) -> bool:

    return (len(sys.argv) > 1 and sys.argv[1] == "-p") or any(not os.path.exists(file_name) for file_name in pickle_files)


class TestConfiguration(Configuration):
    def __init__(self, configuration: dict):
        self._config = configuration


class LocalTelemetrySender(TelemetrySender):
    PICKLE_NAME = "test/test_data/data_volume.pkl"
    T_DATA = "APP.V_DATA_VOLUME"

    def __init__(self, session, params: dict):

        TelemetrySender.__init__(self, session, params)

        self._configuration.get_last_measurement_update = lambda *args, **kwargs: datetime.datetime.fromtimestamp(
            0, tz=datetime.timezone.utc
        )

    def _get_table_rows(self, _table_name: str = None) -> Generator[Dict, None, None]:
        if _table_name == LocalTelemetrySender.T_DATA:
            return _get_unpickled_entries(LocalTelemetrySender.PICKLE_NAME, limit=2)

        return TelemetrySender._get_table_rows(self, _table_name)

    def _flush_logs(self) -> None:
        self._logs._otel_logger_provider.force_flush()


def telemetry_test_sender(session, source, params) -> Tuple[int, int, int, int, int]:
    """
    Returns:
        Tuple[int, int, int, int]: Count of objects, log lines, metrics, events, and bizevents sent
    """
    sender = LocalTelemetrySender(session, params)
    results = sender.send_data(source)
    sender.teardown()

    return results


def get_config(pickle_conf: str) -> TestConfiguration:
    conf = {}
    if not os.path.isfile(TEST_CONFIG_FILE_NAME) or pickle_conf == "y":
        session = _get_session()
        conf_class = config.Configuration(session)
        conf = conf_class._config

        with open(TEST_CONFIG_FILE_NAME, "w", encoding="utf-8") as f:
            json.dump(conf, f, indent=4)
    else:
        with open(TEST_CONFIG_FILE_NAME, "r", encoding="utf-8") as f:
            conf = json.load(f)

    return TestConfiguration(conf)


def read_clean_json_from_file(file_path: str) -> List[Dict]:
    """Reads given file into a dictionary, in case this is JSONC a clean JSON content is provided before turning into dict

    Args:
        file_path (str): path to the file with JSON or JSONC content

    Returns:
        List[Dict]: dictionary based on the content of the JSON/JSONC file
    """
    logging.debug("Reading file: %s", file_path)

    with open(file_path, "r", encoding="utf-8") as file:

        jsonc_str = file.read()
        json_str = jsonstrip.strip(jsonc_str)
        data = json.loads(json_str)

        return data

    return {}


def read_clean_yml_from_file(file_path: str) -> List[Dict]:
    """Reads given file into a dictionary.

    Args:
        file_path (str): path to the file with yaml content

    Returns:
        List[Dict]: dictionary based on the content of the YML/YAML file
    """
    import yaml

    logging.debug("Reading file: %s", file_path)

    with open(file_path, "r", encoding="utf-8") as f:
        data = yaml.safe_load(f)

        return data

    return {}


def find_files(directory: str, filename_pattern: str) -> List[str]:
    """Lists all files with given name in the given directory
    Returns:
        list: List of file paths
    """

    matches = []
    for root, _, files in os.walk(directory):
        for filename in fnmatch.filter(files, filename_pattern):
            matches.append(os.path.join(root, filename))
    return matches


def is_blank(value):
    return value is None or value == ""
