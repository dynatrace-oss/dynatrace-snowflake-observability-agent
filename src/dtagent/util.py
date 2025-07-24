"""Collection of utility function for Dynatrace Snowflake Observability Agent"""
##region ------------------------------ IMPORTS  -----------------------------------------
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
import datetime
from typing import Any, Dict, List, Optional, Union
from enum import Enum
import pandas as pd

##endregion COMPILE_REMOVE

##region --------------------------- HELPER FUNCTIONS ------------------------------------

NANOSECOND_CONVERSION_RATE = 1000 * 1000 * 1000
_59_MINUTES_IN_SEC = 59 * 60
_9_MINUTES_IN_SEC = 9 * 60
EVENT_TIMESTAMP_KEYS_PAYLOAD_NAME = "snowflake.event.trigger"

def _esc(v: Any) -> Any:
    """
    Helper function that escapes " with \" if given object is a string
    """
    return v.replace('\\', '\\\\').replace('"', '\\"') if isinstance(v, str) else v


def _from_json(val: Any) -> Any:
    """Deserialize val (a str, bytes or bytearray instance containing a JSON document) to a Python object."""
    try:
        return json.loads(val) if isinstance(val, str) else val
    except json.JSONDecodeError:
        return val


def _cleanup_data(value: Any) -> Any:
    """Recursively cleans up dict values"""
    if isinstance(value, dict):
        return {k: _cleanup_data(v) for k, v in value.items()}
    if isinstance(value, list):
        return [_cleanup_data(v) for v in value]
    if isinstance(value, datetime.datetime):
        return format_datetime(value)

    result = _from_json(value)

    if isinstance(result, (datetime.datetime, dict, list)):
        return _cleanup_data(result)

    return result


def _pack_values_to_json_strings(value: Any, level: int = 0, max_list_level: int = 2) -> Union[Dict[str, str], List[str], str]:
    """
    Recursively convert all values in a dictionary to JSON strings.

    Args:
        value (Any): The original value, which can be a dictionary, list, or other types.
        max_list_level (int, default = 2): Maximum nesting level on which list elements will be parsed seperately.
                                            If list is found further than this level, it will be stringified as a whole.

    Returns:
        Union[Dict[str, str], List[str], str]: A new dictionary, list, or value with all values converted to JSON strings.
    """
    def __is_not_empty(v:Any) -> bool:
        return v is not None and v != {} and v != "{}" and v != [] and v != "[]"

    if isinstance(value, dict) and level == 0:
        packed_dict = {k: _pack_values_to_json_strings(v, level + 1, max_list_level) for k, v in value.items()}
        return {k: v for k, v in packed_dict.items() if __is_not_empty(v)}
    if isinstance(value, list) and level < max_list_level:
        packed_list = [_pack_values_to_json_strings(item, level + 1, max_list_level) for item in value]
        return [v for v in packed_list if __is_not_empty(v)]
    if not isinstance(value, (bool, str, bytes, int, float)):
        return json.dumps(value, default=str)

    return value


def _to_json(content: any) -> str:
    d_content = _cleanup_data(content)
    s_content = json.dumps(d_content, default=str)
    return s_content


def _unpack_json_list(to_unpack: Dict, keys: List) -> List:
    """
    Helper function that will ensure we do not run into empty, null, or string values
    when we expect a list to work with
    """
    from itertools import chain

    return list(chain(
            # packing multiple dicts into a single one
            *[
                # getting list from JSON if it is a string
                _from_json(val)
                for val
                # getting values from the given dict - if they don't exit they default to an empty list
                in [to_unpack.get(key, []) for key in keys]
                if val is not None and val != ''
            ]
        ))


def _unpack_json_dict(to_unpack: Dict, keys: List) -> Dict:
    """
    Helper function that will ensure we do not run into empty, null, or string values
    when we expect a dictionary to work with
    """
    from collections import ChainMap
    return dict(ChainMap(
            # packing multiple dicts into a single one
            *[
                # getting dict from JSON if it is a string
                _from_json(val)
                for val
                # getting values from the given dict - if they don't exit they default to an empty dict
                in [to_unpack.get(key, {}) for key in keys]
                if val is not None and val != ''
            ]
        ))


def _clean_key(key: str) -> str:
    """
    Ensures there are only lowercase alphanumeric and underscore characters in the key
    """
    import re
    ans = re.sub(r'[^a-zA-Z0-9_\s]', '', key)
    cs = re.sub(r'\s+', '_', ans)
    return cs.lower()


def _cleanup_dict(d: Any, skip_first_level_hidden=False) -> Union[dict, list, str, None]:
    """Cleans up given dictionary from any None or NaN values, and first level keys starting with _ if requested

    Args:
        d (any): The input data, which can be a dictionary, list, or any other type.
        skip_first_level_hidden (bool, optional): If True, it skips keys starting with an underscore at the first level of the dictionary. Defaults to False.

    Returns:
        Union[dict, list]: _description_
    """

    def __get_valid_json(json_string: str) -> Union[dict, None]:
        """Deserialize s (a str, bytes or bytearray instance containing a JSON document) to a Python object."""
        try:
            data = json.loads(json_string)
            if isinstance(data, dict):
                return data
            return None
        except (ValueError, TypeError):
            return None

    if isinstance(d, dict):
        return {
            k:v for k,v in
            {
                k: _cleanup_dict(v)
                for k, v in d.items()
                # this is checking if v is not None, NaN, NaF, and not an empty dictionary
                if not pd.isna(pd.Series(v)).all() and not (skip_first_level_hidden and k[0] == "_")
            }.items()
            if v is not None and v != {}
        }
    if isinstance(d, list):
        return [_cleanup_dict(i) for i in d if not pd.isna(pd.Series(i)).all()]
    if isinstance(d, str):
        jd = __get_valid_json(d)
        if jd is not None:
            return _cleanup_dict(jd)  # for the moment we are putting it back as JSON to avoid confusion at Grail side

    return d


def _adjust_timestamp(row_dict: Dict, start_time: str = 'START_TIME', end_time: str = 'END_TIME', now: Optional[int] = None) -> Dict:
    """
    Updates START_TIME/TIMESTAMP and END_TIME when they are outside the boundaries in 
    https://docs.dynatrace.com/docs/ingest-from/opentelemetry/getting-started/traces/ingest#ingestion-limits,
    i.e., should not be 60min in past or 10min in the future.
    The algorithm will attempt to keep period length is intact
    """
    import time

    def __cast_timestamp_to_int(time_key: str):
        if not isinstance(row_dict[time_key], (int, float)):
            try:
                # Ensure the datetime is timezone-aware before calling .timestamp()
                dt = ensure_timezone_aware(row_dict[time_key])
                casted_ts = int(dt.timestamp() * NANOSECOND_CONVERSION_RATE)
            except TypeError as e:
                raise e
            row_dict[time_key] = casted_ts

    now = now or time.time_ns()
    min_past = now - _59_MINUTES_IN_SEC * NANOSECOND_CONVERSION_RATE  # now - 59 minutes in nanoseconds
    max_future = now + _9_MINUTES_IN_SEC * NANOSECOND_CONVERSION_RATE  # now + 9 minutes in nanoseconds

    if start_time in row_dict and end_time in row_dict:
        __cast_timestamp_to_int(end_time)
        __cast_timestamp_to_int(start_time)
        span_len = row_dict[end_time] - row_dict[start_time]
    else:
        span_len = 0

    def __adjust_end_time(time_key: str):
        if end_time in row_dict:
            row_dict[end_time] = row_dict[time_key] + span_len

    def __adjust_time(time_key: str) -> None:
        if time_key in row_dict:
            __cast_timestamp_to_int(time_key)

            if row_dict[time_key] > max_future:
                row_dict[time_key] = max_future - span_len
                __adjust_end_time(time_key)
            if row_dict[time_key] < min_past:
                row_dict[time_key] = min_past
                __adjust_end_time(time_key)

    __adjust_time(start_time)
    __adjust_time("TIMESTAMP")

    if end_time in row_dict:
        __cast_timestamp_to_int(end_time)
        if row_dict[end_time] > max_future:
            if start_time in row_dict:
                row_dict[end_time] = row_dict[start_time] + span_len
            elif "TIMESTAMP" in row_dict:
                row_dict[end_time] = row_dict["TIMESTAMP"] + span_len

            row_dict[end_time] = min(max_future, row_dict[end_time])

    return row_dict


def _check_timestamp_ms(timestamp_ns: int) -> Optional[int]:
    """Checks given timestamp (in ms) whether it is in the range accepted by Dynatrace metrics API, i.e., between [-1h, +10min],
    but to play safe we check [-55min, 0]

    Args:
        timestamp_ns (int): timestamp in ms to check

    Returns:
        Optional[int]: given timestamp or None if timestamp is out of range
    """

    timestamp = datetime.datetime.fromtimestamp(timestamp_ns / 1e3, tz=datetime.timezone.utc)
    now = get_now_timestamp()
    one_hour_ago = now - datetime.timedelta(minutes=55)

    if timestamp < one_hour_ago or timestamp > now:
        return None

    return timestamp_ns


def _get_timestamp_in_sec(ts: float = 0, conversion_unit: float = 1, timezone=datetime.timezone.utc) -> datetime.datetime:
    """Returns datetime object based on given timestamp epoch converted, e.g., from nanoseconds to seconds, at given timezone

    Args:
        ts (float, optional): timestamp epoch value. Defaults to 0.
        conversion_unit (float, optional): conversation unit, e.g., 1000 * 1000 * 1000 for nanosec to sec. Defaults to 1.
                                            If converting to nanoseconds it is recommended to use NANOSECOND_CONVERSION_RATE const.
        timezone (_type_, optional): timezone. Defaults to datetime.timezone.utc.

    Returns:
        datetime.datetime: _description_
    """
    return datetime.datetime.fromtimestamp(ts / conversion_unit, tz=timezone)


def _get_service_name(config_dict: str) -> str:
    """
    Returns snowflake full account name either as account name from config
    or matching given pattern on snowflake host name
    """
    if "core.snowflake_account_name" in config_dict:
        return config_dict["core.snowflake_account_name"]

    import re
    m = re.match(r"(.*?)\.snowflakecomputing\.com$", config_dict["core.snowflake_host_name"])
    return m.group(1) if m else config_dict["core.snowflake_host_name"]


def _is_not_blank(value: Any) -> bool:
    """
    Helper function to check whether given value is empty or null
    """
    return value is not None and str(value).strip() != ""


def _unpack_payload(query_data: Dict) -> Dict:
    """Unpacks given query payload (with standard objects of DIMENSIONS, ATTRIBUTES ...) into a flat map.
    In the process it ensures that only non blank values are set

    Args:
        query_data (Dict): query payload as set of Dynatrace Snowflake Observability Agent view standard objects

    Returns:
        Dict: flattened set of attribute-value map unpacked from the query results
    """

    unpacked_payload = {
        attribute_key: attribute_value
        for attribute_key, attribute_value
        in _unpack_json_dict(
            query_data,
            ["DIMENSIONS", "ATTRIBUTES", "METRICS", "EVENT_TIMESTAMPS"]
        ).items()
        if _is_not_blank(attribute_value)
    }

    return unpacked_payload


def get_timestamp_in_ms(query_data: Dict, ts_key: str, conversion_unit: int = 1e6, default_ts=None):
    """Returns timetamp in miliseconds by converting value retrieved from query_data under given ts_key
    """
    ts = query_data.get(ts_key, None)
    if ts is not None and not pd.isna(ts):
        if isinstance(ts, datetime.datetime):
            # Ensure timezone awareness before converting to timestamp
            ts = ensure_timezone_aware(ts)
            return ts.timestamp() * 1000
        return int(int(ts) / conversion_unit)
    return default_ts


def ensure_timezone_aware(dt: datetime.datetime) -> datetime.datetime:
    """Ensures a datetime object is timezone-aware by adding UTC timezone for naive datetimes.

    Args:
        dt (datetime.datetime): datetime to ensure is timezone-aware

    Returns:
        datetime.datetime: timezone-aware datetime object
    """
    from zoneinfo import ZoneInfo

    if dt.tzinfo is None:
        system_tz = os.environ.get('TZ', 'UTC')
        if system_tz in ['UTC', 'etc/utc', 'Etc/UTC']:
            dt = dt.replace(tzinfo=ZoneInfo("UTC"))
        else:
            local_tz = ZoneInfo("Europe/Warsaw")
            dt = dt.replace(tzinfo=local_tz)
    return dt


def format_datetime(dt: datetime.datetime) -> str:
    """Converts given timestamp into a formatted string in GMT timezone

    Args:
        dt (datetime.datetime): datetime to convert

    Returns:
        str: Timestamp formatted as "%Y-%m-%dT%H:%M:%S.%f{3}Z"
    """
    from zoneinfo import ZoneInfo

    dt = ensure_timezone_aware(dt)
    utc_time = dt.astimezone(ZoneInfo("UTC"))
    return utc_time.strftime("%Y-%m-%dT%H:%M:%S.%f")[:-3] + "Z"

def get_now_timestamp_formatted() -> str:
    """Uses format_datetime() to format now() as "%Y-%m-%dT%H:%M:%S.%f{3}Z" """
    return format_datetime(get_now_timestamp())

def get_now_timestamp() -> datetime.datetime:
    """Returns current timestamp as datetime object"""
    return datetime.datetime.now(datetime.timezone.utc)

def is_select_for_table(table_name_or_query:str) -> bool:
    """Returns True if given table name is in fact a SELECT statement
    """
    return table_name_or_query.lstrip()[:7].upper() == "SELECT "

##endregion

##region --------------------------- HELPER CLASSES ------------------------------------


class StringEnum(str, Enum):
    """Customer implementation of the StrEnum that ensures case of enum values is kept - unlike in StrEnum"""
    def __str__(self):
        return self.name

##endregion
