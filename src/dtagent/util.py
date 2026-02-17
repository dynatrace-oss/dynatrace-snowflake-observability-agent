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

import datetime
import json
import os
import re
from enum import Enum
from typing import Any, Dict, List, Literal, Optional, Union, Generator, Tuple

import pandas as pd

##endregion COMPILE_REMOVE

##region --------------------------- HELPER FUNCTIONS ------------------------------------

NANOSECOND_CONVERSION_RATE = 1000 * 1000 * 1000
_59_MINUTES_IN_SEC = 59 * 60
_9_MINUTES_IN_SEC = 9 * 60
EVENT_TIMESTAMP_KEYS_PAYLOAD_NAME = "snowflake.event.trigger"
P_SELECT_QUERY = re.compile(r"^\s*(SELECT|SHOW\s+[^>]*->>\s*SELECT)", re.IGNORECASE | re.DOTALL)


def _esc(v: Any) -> Any:
    r"""Helper function that escapes " with \" if given object is a string, or converts lists to comma-separated strings"""
    if isinstance(v, str):
        return v.replace("\\", "\\\\").replace('"', '\\"')
    if isinstance(v, list):
        # Convert list to comma-separated string, escaping each element
        return ",".join(_esc(str(item)) for item in v)
    return v


def _from_json(val: Any) -> Any:
    """Deserialize val (a str, bytes or bytearray instance containing a JSON document) to a Python object."""
    try:
        return json.loads(val) if isinstance(val, str) else val
    except json.JSONDecodeError:
        return val


def __try_convert_to_numeric(item: Any) -> Any:
    """Try to convert item to numeric type, return original if not possible.

    bool > int > float > str (prefer numeric types when possible)
    """
    result = item
    if item and isinstance(item, str):
        # Check for boolean strings first
        if item.lower() in ("true", "false"):
            return item.lower() == "true"

        try:
            if "." in item or "e" in item.lower():
                # Check if it's a float string first
                result = float(item)
            else:
                result = int(item)
        except (ValueError, TypeError):
            pass  # Keep original item
    return result


def _cleanup_data(value: Any) -> Any:
    """Recursively cleans up dict values"""
    if isinstance(value, dict):
        return {k: _cleanup_data(v) for k, v in value.items()}

    if isinstance(value, list):
        # Check for mixed types BEFORE cleaning to avoid _from_json normalizing types
        # OpenTelemetry requires all elements in a sequence to be of the same type
        if value and len(value) > 1:
            # Determine if we have mixed types in the original list
            types_in_list = {type(item) for item in value if item is not None}
            if len(types_in_list) > 1:
                numeric_converted = [__try_convert_to_numeric(item) for item in value]
                converted_types = {type(item) for item in numeric_converted if item is not None}

                return (
                    # If we can normalize to numeric (int, float, bool are compatible), return directly
                    numeric_converted
                    if converted_types and converted_types.issubset({int, float, bool})
                    # Fallback: normalize to a sequence of strings, handling datetime explicitly
                    else [
                        str(format_datetime(item) if isinstance(item, datetime.datetime) else item)
                        for item in numeric_converted
                        if item is not None
                    ]
                )

        # No mixed types or single element - process normally
        cleaned_list = [_cleanup_data(v) for v in value]
        return cleaned_list

    if isinstance(value, datetime.datetime):
        return format_datetime(value)

    result = _from_json(value)

    if isinstance(result, (datetime.datetime, dict, list)):
        return _cleanup_data(result)

    return result


def _pack_values_to_json_strings(value: Any, level: int = 0, max_list_level: int = 2) -> Union[Dict[str, str], List[str], str]:
    """Recursively convert all values in a dictionary to JSON strings.

    Args:
        value (Any): The original value, which can be a dictionary, list, or other types.
        max_list_level (int, default = 2): Maximum nesting level on which list elements will be parsed separately.
                                            If list is found further than this level, it will be stringified as a whole.

    Returns:
        Union[Dict[str, str], List[str], str]: A new dictionary, list, or value with all values converted to JSON strings.
    """

    def __is_not_empty(v: Any) -> bool:
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
    """Helper function that will ensure we do not run into empty, null, or string values
    when we expect a list to work with
    """
    from itertools import chain

    # packing multiple dicts into a single one
    # getting list from JSON if it is a string
    # getting values from the given dict - if they don't exit they default to an empty list
    return list(chain(*[_from_json(val) for val in [to_unpack.get(key, []) for key in keys] if val is not None and val != ""]))


def _unpack_json_dict(to_unpack: Dict, keys: List) -> Dict:
    """Helper function that will ensure we do not run into empty, null, or string values
    when we expect a dictionary to work with
    """
    from collections import ChainMap

    # packing multiple dicts into a single one
    # getting dict from JSON if it is a string
    return dict(ChainMap(*[_from_json(val) for val in [to_unpack.get(key, {}) for key in keys] if val is not None and val != ""]))


def _clean_key(key: str) -> str:
    """Ensures there are only lowercase alphanumeric and underscore characters in the key"""
    ans = re.sub(r"[^a-zA-Z0-9_\s]", "", key)
    cs = re.sub(r"\s+", "_", ans)
    return cs.lower()


def _cleanup_dict(d: Any, skip_first_level_hidden=False) -> Union[dict, list, str, None]:
    """Cleans up given dictionary from any None or NaN values, and first level keys starting with _ if requested

    Args:
        d (any): The input data, which can be a dictionary, list, or any other type.
        skip_first_level_hidden (bool, optional): If True, it skips keys starting with an underscore at the first level of the dictionary.
                                                  Defaults to False.

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
            k: v
            for k, v in {
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


def _adjust_timestamp(row_dict: Dict, start_time: str = "START_TIME", end_time: str = "END_TIME", now: Optional[int] = None) -> Dict:
    """Updates START_TIME/TIMESTAMP and END_TIME when they are outside the boundaries in
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
            except TypeError as err:
                raise err
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


def validate_timestamp(
    timestamp: int,
    allowed_past_minutes: int = 24 * 60 - 5,
    allowed_future_minutes: int = 10,
    return_unit: Literal["ms", "ns"] = "ms",
    skip_range_validation: bool = False,
) -> Optional[int]:
    """Validates and normalizes timestamps with configurable time windows and automatic unit conversion.

    This function performs multiple validation steps:
    1. Rejects negative timestamps (e.g., sentinel values like -1000000)
    2. Auto-detects input unit and converts to nanoseconds (preserving full precision):
       - Uses threshold of 4.1e15 (year 2100 in milliseconds * 1000)
       - Values > 4.1e15: assumed to be nanoseconds or higher precision
       - Values <= 4.1e15: assumed to be milliseconds or microseconds
       - Automatically converts from femtoseconds/picoseconds/nanoseconds/microseconds → nanoseconds
    3. Optionally validates the timestamp is within the allowed time range from current time
    4. Returns in requested unit (milliseconds or nanoseconds)

    Detection thresholds (based on year 2100):
    - Femtoseconds: > 4.1e21 → divide by 1e6 to get nanoseconds
    - Picoseconds:  > 4.1e18 → divide by 1e3 to get nanoseconds
    - Nanoseconds:  > 4.1e15 → use as-is
    - Microseconds: > 4.1e12 → multiply by 1e3 to get nanoseconds
    - Milliseconds: <= 4.1e12 → multiply by 1e6 to get nanoseconds

    Args:
        timestamp: timestamp to validate (in any supported precision unit)
        allowed_past_minutes: allowed past range in minutes (default: ~24 hours)
        allowed_future_minutes: allowed future range in minutes (default: 10)
        return_unit: unit to return validated timestamp in - "ms" or "ns" (default: "ms")
        skip_range_validation: if True, skip time range validation (useful for observed_timestamp)

    Returns:
        Optional[int]: validated timestamp in requested unit, or None if invalid

    Raises:
        ValueError: if return_unit is neither "ms" nor "ns"

    Examples:
        >>> validate_timestamp(1707494400000, return_unit="ms")  # Milliseconds
        1707494400000
        >>> validate_timestamp(1707494400000000000, return_unit="ns")  # Nanoseconds
        1707494400000000000
        >>> validate_timestamp(1707494400000000000, return_unit="ms")  # ns input, ms output
        1707494400000
        >>> validate_timestamp(-1000000, return_unit="ms")  # Negative sentinel
        None
        >>> validate_timestamp(old_timestamp, skip_range_validation=True)  # For observed_timestamp
        1234567890000000000
    """
    # Validate return_unit parameter
    if return_unit not in ("ms", "ns"):
        raise ValueError(f"return_unit must be 'ms' or 'ns', got '{return_unit}'")

    # Pre-validation: reject negative timestamps (sentinel values like -1000000)
    if timestamp < 0:
        return None

    # Auto-detect and convert to nanoseconds (preserves precision)
    # Year 2100 in milliseconds is approximately 4.1e12
    # Values larger than this are likely higher precision time units
    timestamp_ns = timestamp

    if timestamp > 4_100_000_000_000:
        # Try femtoseconds (divide by 1e6 to get nanoseconds)
        if timestamp > 4_100_000_000_000_000_000_000:
            converted_ts = timestamp // 1_000_000
        # Try picoseconds (divide by 1e3 to get nanoseconds)
        elif timestamp > 4_100_000_000_000_000_000:
            converted_ts = timestamp // 1_000
        # Try nanoseconds (use as-is)
        elif timestamp > 4_100_000_000_000_000:
            converted_ts = timestamp
        # Try microseconds (multiply by 1e3 to get nanoseconds)
        elif timestamp > 4_100_000_000_000:
            converted_ts = timestamp * 1_000
        else:
            converted_ts = -1  # Invalid value

        # Validate the converted timestamp is reasonable (within year 2100 range in nanoseconds)
        if 0 < converted_ts <= 4_100_000_000_000_000_000:
            timestamp_ns = converted_ts
        else:
            return None
    else:
        # Input is in milliseconds, convert to nanoseconds
        timestamp_ns = timestamp * 1_000_000

    # Optionally validate timestamp is within allowed time range
    if not skip_range_validation:
        try:
            timestamp_dt = datetime.datetime.fromtimestamp(timestamp_ns / 1e9, tz=datetime.timezone.utc)
        except (ValueError, OSError, OverflowError):
            return None

        now = get_now_timestamp()
        min_past = now - datetime.timedelta(minutes=allowed_past_minutes)
        max_future = now + datetime.timedelta(minutes=allowed_future_minutes)

        if timestamp_dt < min_past or timestamp_dt > max_future:
            return None

    # Return in requested unit
    if return_unit == "ns":
        return timestamp_ns

    # return_unit == "ms" - convert from nanoseconds to milliseconds
    return timestamp_ns // 1_000_000


def _get_timestamp_in_sec(ts: float = 0, conversion_unit: float = 1, timezone=datetime.timezone.utc) -> datetime.datetime:
    """Returns datetime object based on given timestamp epoch converted, e.g., from nanoseconds to seconds, at given timezone

    Args:
        ts (float, optional): timestamp epoch value. Defaults to 0.
        conversion_unit (float, optional): conversation unit, e.g., 1000 * 1000 * 1000 for nanoseconds to sec. Defaults to 1.
                                            If converting to nanoseconds it is recommended to use NANOSECOND_CONVERSION_RATE const.
        timezone (_type_, optional): timezone. Defaults to datetime.timezone.utc.

    Returns:
        datetime.datetime: _description_
    """
    return datetime.datetime.fromtimestamp(ts / conversion_unit, tz=timezone)


def _get_snowflake_account_info(config_dict: dict, session=None) -> Tuple[str, str]:
    """Returns Snowflake account identifier and host name, deriving them if not provided.

    Resolution priority:
    1. Use values from config if explicitly provided and not "-"
    2. Derive missing values from provided values
    3. Query Snowflake for account info (if session provided and values still missing)

    Args:
        config_dict: Configuration dictionary containing Snowflake connection details
        session: Optional Snowflake session for querying account information

    Returns:
        Tuple[str, str]: (account_name, host_name)
            - account_name: Snowflake account identifier (e.g., 'myorg-myaccount' or 'account.region')
            - host_name: Snowflake host name (e.g., 'myorg-myaccount.snowflakecomputing.com')
    """
    account_name = config_dict.get("core.snowflake.account_name", "")
    host_name = config_dict.get("core.snowflake.host_name", "")

    # Normalize placeholder values to empty strings
    if account_name == "-":
        account_name = ""
    if host_name == "-":
        host_name = ""

    # If we have both values, return them
    if account_name and host_name:
        return account_name, host_name

    # If we have host_name but not account_name, extract account from host
    if host_name and not account_name:
        m = re.match(r"(.*?)\.snowflakecomputing\.com$", host_name)
        account_name = m.group(1) if m else host_name
        return account_name, host_name

    # If we have account_name but not host_name, derive host from account
    if account_name and not host_name:
        if not account_name.endswith(".snowflakecomputing.com"):
            host_name = f"{account_name}.snowflakecomputing.com"
        else:
            host_name = account_name
        return account_name, host_name

    # If we have neither, try to query Snowflake
    if session:
        from snowflake.snowpark.exceptions import SnowparkSQLException

        try:
            result = session.sql("SELECT CURRENT_ORGANIZATION_NAME() || '-' || CURRENT_ACCOUNT_NAME() as account_identifier").collect()
            if result and len(result) > 0:
                # Access the first column of the first row
                row = result[0]
                if row:
                    account_identifier = row[0] if hasattr(row, "__getitem__") else None
                    if account_identifier:
                        return account_identifier, f"{account_identifier}.snowflakecomputing.com"
        except SnowparkSQLException:
            pass  # Fall back to empty strings if query fails

    return account_name, host_name


def _is_not_blank(value: Any) -> bool:
    """Helper function to check whether given value is empty or null."""
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
        for attribute_key, attribute_value in _unpack_json_dict(
            query_data, ["DIMENSIONS", "ATTRIBUTES", "METRICS", "EVENT_TIMESTAMPS"]
        ).items()
        if _is_not_blank(attribute_value)
    }

    return unpacked_payload


def _chunked_iterable(iterable, size: int) -> Generator[List, None, None]:
    """Yields chunks of the given iterable, each of the specified size.

    This function takes an iterable and divides it into smaller lists (chunks) of a given size.
    It uses itertools.islice to efficiently slice the iterator without loading the entire iterable into memory.

    Args:
        iterable: An iterable object (e.g., list, tuple, generator) to be chunked.
        size: An integer specifying the maximum size of each chunk. Must be positive.

    Yields:
        list: A list containing up to 'size' elements from the iterable.
              The last chunk may be smaller if the iterable's length is not divisible by 'size'.

    Raises:
        ValueError: If 'size' is not a positive integer.

    Note:
        This is a generator function, so it yields chunks lazily.
    """
    import itertools

    it = iter(iterable)
    while chunk := list(itertools.islice(it, size)):
        yield chunk


def get_timestamp(query_data: Dict, ts_key: str, default_ts=None) -> Optional[int]:
    """Returns timestamp in nanoseconds from query_data.

    Handles multiple input formats:
    - datetime objects → converted to nanoseconds
    - ISO 8601 strings → parsed and converted to nanoseconds
    - Numeric values → assumed to be nanoseconds (from SQL extract(epoch_nanosecond ...))

    Args:
        query_data: Dictionary containing the timestamp data
        ts_key: Key to retrieve the timestamp from query_data
        default_ts: Default value to return if timestamp not found or invalid

    Returns:
        Optional[int]: timestamp in nanoseconds, or None if not found

    Examples:
        >>> get_timestamp({"ts": 1707494400000000000}, "ts")  # Nanoseconds
        1707494400000000000
        >>> get_timestamp({"ts": datetime(2024, 2, 9)}, "ts")  # datetime object
        1707436800000000000
    """
    ts = query_data.get(ts_key, None)
    if ts is not None and not pd.isna(ts):
        if isinstance(ts, datetime.datetime):
            ts = ensure_timezone_aware(ts)
            return int(ts.timestamp() * 1_000_000_000)  # Convert to nanoseconds
        if isinstance(ts, str):
            try:
                ts = datetime.datetime.fromisoformat(ts.replace("Z", "+00:00"))
                ts = ensure_timezone_aware(ts)
                return int(ts.timestamp() * 1_000_000_000)
            except ValueError:
                pass
        return int(ts)  # Already in nanoseconds from SQL
    return default_ts


def process_timestamps_for_telemetry(data: Dict) -> Tuple[Optional[int], Optional[int]]:
    """Processes timestamp and observed_timestamp for telemetry APIs with proper validation.

    This utility function implements the standard pattern for handling timestamps in telemetry:
    1. Gets timestamp from "timestamp" key in nanoseconds
    2. Gets observed_timestamp from "observed_timestamp" key, falls back to timestamp if not present
    3. Validates timestamp with range checking (for API acceptance) and returns in milliseconds
    4. Validates observed_timestamp WITHOUT range checking (preserves original) and returns in nanoseconds

    Args:
        data: Dictionary containing timestamp data (typically from SQL query results)

    Returns:
        Tuple[Optional[int], Optional[int]]: (timestamp_ms, observed_timestamp_ns)
        - timestamp_ms: validated timestamp in milliseconds (for Dynatrace APIs)
        - observed_timestamp_ns: validated observed_timestamp in nanoseconds (per OTLP standard)
        Either can be None if validation fails or data not present

    Examples:
        >>> process_timestamps_for_telemetry({"timestamp": 1707494400000000000})
        (1707494400000, 1707494400000000000)  # timestamp in ms, observed_timestamp in ns

        >>> process_timestamps_for_telemetry(
        ...     {"timestamp": 1707494400000000000, "observed_timestamp": 1707494300000000000}
        ... )
        (1707494400000, 1707494300000000000)  # Uses explicit observed_timestamp
    """
    # Get timestamp in nanoseconds from SQL
    timestamp_ns = get_timestamp(data, "timestamp")

    # Get observed_timestamp if provided, otherwise fallback to timestamp value
    observed_timestamp_ns = get_timestamp(data, "observed_timestamp", default_ts=timestamp_ns)

    # Validate main timestamp with range checking (for API acceptance) - return in milliseconds
    validated_timestamp_ms = None
    if timestamp_ns:
        validated_timestamp_ms = validate_timestamp(timestamp_ns, return_unit="ms")

    # Validate observed_timestamp WITHOUT range checking (preserve original) - return in nanoseconds
    validated_observed_timestamp_ns = None
    if observed_timestamp_ns:
        validated_observed_timestamp_ns = validate_timestamp(observed_timestamp_ns, return_unit="ns", skip_range_validation=True)

    return validated_timestamp_ms, validated_observed_timestamp_ns


def ensure_timezone_aware(dt: datetime.datetime) -> datetime.datetime:
    """Ensures a datetime object is timezone-aware by adding UTC timezone for naive datetimes.

    Args:
        dt (datetime.datetime): datetime to ensure is timezone-aware

    Returns:
        datetime.datetime: timezone-aware datetime object
    """
    from zoneinfo import ZoneInfo

    if dt.tzinfo is None:
        system_tz = os.environ.get("TZ", "UTC")
        if system_tz in ["UTC", "etc/utc", "Etc/UTC"]:
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
    """Uses format_datetime() to format now() as "%Y-%m-%dT%H:%M:%S.%f{3}Z"."""
    return format_datetime(get_now_timestamp())


def get_now_timestamp() -> datetime.datetime:
    """Returns current timestamp as datetime object"""
    return datetime.datetime.now(datetime.timezone.utc)


def is_select_for_table(table_name_or_query: str) -> bool:
    """Returns True if given table name is in fact a SELECT statement or a SHOW ... ->> SELECT ... statement"""
    return P_SELECT_QUERY.match(table_name_or_query) is not None


def is_regular_mode(session) -> bool:
    """Checks if we are running in regular mode, i.e., not local testing mode"""
    return session.session_id != 1


##endregion

##region --------------------------- HELPER CLASSES ------------------------------------


class StringEnum(str, Enum):
    """Custom implementation of the StrEnum that ensures case of enum values is kept - unlike in StrEnum"""

    def __str__(self):
        """Returns string representation of the enum value keeping the case."""
        return self.name


##endregion
