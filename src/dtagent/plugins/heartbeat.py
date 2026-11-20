"""Plugin file for processing heartbeat plugin data."""

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

import json
import re
import logging
import datetime
from typing import Tuple, Dict, Optional, List, Generator, Any
from zoneinfo import ZoneInfo
from croniter import croniter
from dtagent.plugins import Plugin
from dtagent.context import RUN_PLUGIN_KEY, RUN_RESULTS_KEY, RUN_ID_KEY  # COMPILE_REMOVE

##endregion COMPILE_REMOVE

##region ------------------ MEASUREMENT SOURCE: HEARTBEAT --------------------------------

_CRON_PREFIX = re.compile(r"^\s*USING\s+CRON\s+", re.IGNORECASE)
_INTERVAL = re.compile(r"^\s*(\d+)\s+(SECOND|MINUTE|HOUR|DAY)S?\s*$", re.IGNORECASE)
_INTERVAL_SECONDS = {"SECOND": 1, "MINUTE": 60, "HOUR": 3600, "DAY": 86400}
_MAX_CRON_ITERATIONS = 100000  # safety net against pathological schedules / huge windows


def _expected_runs(schedule: Optional[str], window_hours: float, now: Optional[datetime.datetime] = None) -> Optional[int]:
    """Returns the number of runs a task schedule implies within the last window_hours, or None if the schedule is not supported.

    Supported: `USING CRON <5-field expression> <time zone>` and fixed intervals like `30 MINUTES`.
    Not supported (None): schedules depending on other tasks (`AFTER ...`) and anything unparsable.

    Args:
        schedule (Optional[str]): Snowflake task schedule string
        window_hours (float): length of the window ending at `now`
        now (Optional[datetime.datetime]): end of the window, defaults to current UTC time

    Returns:
        Optional[int]: number of scheduled runs in the (now - window_hours, now] window
    """
    if not schedule:
        return None

    interval = _INTERVAL.match(schedule)
    if interval:
        return int(window_hours * 3600) // (int(interval.group(1)) * _INTERVAL_SECONDS[interval.group(2).upper()])

    if not _CRON_PREFIX.match(schedule):
        return None

    # croniter understands neither the USING CRON prefix nor the trailing time zone: strip both, apply the time zone to the window
    *expression, timezone = _CRON_PREFIX.sub("", schedule).split()
    expression = " ".join(expression)
    if not croniter.is_valid(expression):
        return None

    try:
        tz = ZoneInfo(timezone)
    except (KeyError, ValueError, OSError):  # ZoneInfoNotFoundError is a KeyError
        return None

    # window arithmetic in UTC (real elapsed time), then expressed in the schedule's time zone for croniter
    end_utc = now or datetime.datetime.now(datetime.timezone.utc)
    start = (end_utc - datetime.timedelta(hours=window_hours)).astimezone(tz)
    end = end_utc.astimezone(tz)

    runs = 0
    iterator = croniter(expression, start)
    while runs < _MAX_CRON_ITERATIONS and iterator.get_next(datetime.datetime) <= end:
        runs += 1

    return runs


def _as_dict(value: Any) -> Dict:
    """Returns a dict from a dict or a JSON string; anything else gives an empty dict"""
    if isinstance(value, dict):
        return dict(value)
    if isinstance(value, str) and value:
        try:
            parsed = json.loads(value)
            return parsed if isinstance(parsed, dict) else {}
        except json.JSONDecodeError:
            return {}
    return {}


class HeartbeatPlugin(Plugin):
    """Heartbeat plugin class."""

    PLUGIN_NAME = "heartbeat"
    PLUGIN_CONTEXTS: tuple = ("heartbeat",)

    def _get_table_rows(self, t_data: str) -> Generator[Dict, None, None]:
        """Adds the cron/interval based expected_runs to rows delivered by APP.F_HEARTBEAT_INSTRUMENTED()"""
        for row_dict in super()._get_table_rows(t_data):
            yield self._add_expected_runs(row_dict)

    def _add_expected_runs(self, row_dict: Dict) -> Dict:
        """Sets dsoa.heartbeat.expected_runs (metric) and dsoa.heartbeat.schedule_supported (attribute) on a heartbeat row.

        Disabled plugins are expected to run 0 times; tasks with a schedule that cannot be evaluated get no expected_runs.
        """
        attributes = _as_dict(row_dict.get("ATTRIBUTES"))
        metrics = _as_dict(row_dict.get("METRICS"))

        # configured schedule is what should run; fall back to the deployed one for tasks missing from the configuration
        schedule = attributes.get("dsoa.heartbeat.configured_schedule") or attributes.get("dsoa.heartbeat.actual_schedule")
        expected = _expected_runs(schedule, attributes.get("dsoa.heartbeat.window_hours") or 24)

        attributes["dsoa.heartbeat.schedule_supported"] = expected is not None
        if expected is not None:
            metrics["dsoa.heartbeat.expected_runs"] = expected if attributes.get("dsoa.heartbeat.configured_enabled") is not False else 0

        row_dict["ATTRIBUTES"] = attributes
        row_dict["METRICS"] = metrics
        return row_dict

    def get_log_level(self, row_dict: Dict) -> int:
        """ERROR for a missing task; WARN for unexpected, suspended, drifted or unsupported-schedule tasks; INFO otherwise"""
        attributes = _as_dict(row_dict.get("ATTRIBUTES"))

        if attributes.get("dsoa.heartbeat.is_missing"):
            return logging.ERROR
        if (
            any(
                attributes.get(flag)
                for flag in ("dsoa.heartbeat.is_unexpected", "dsoa.heartbeat.is_suspended", "dsoa.heartbeat.has_schedule_drift")
            )
            or attributes.get("dsoa.heartbeat.schedule_supported") is False
        ):
            return logging.WARNING
        return logging.INFO

    def process(self, run_id: str, run_proc: bool = True, contexts: Optional[List[str]] = None) -> Dict[str, Dict[str, int]]:
        """Compares configured and actual agent tasks and their expected and actual runs.

        Args:
            run_id (str): unique run identifier
            run_proc (bool): indicator whether processing should be logged as completed

        Returns:
            Dict[str,int]: A dictionary with telemetry counts for heartbeat.

            Example:
            {
            "dsoa.run.results": {
                "heartbeat": {
                    "entries": entries_cnt,
                    "log_lines": logs_cnt,
                    "metrics": metrics_cnt,
                    "events": events_cnt,
                },
            },
            "dsoa.run.id": "uuid_string"
            }
        """
        t_heartbeat = "call DTAGENT_DB.APP.F_HEARTBEAT_INSTRUMENTED()"

        entries_cnt, logs_cnt, metrics_cnt, events_cnt = self._log_entries(
            lambda: self._get_table_rows(t_heartbeat),
            "heartbeat",
            run_uuid=run_id,
            log_completion=run_proc,
        )

        return self._report_results(
            {
                "heartbeat": {
                    "entries": entries_cnt,
                    "log_lines": logs_cnt,
                    "metrics": metrics_cnt,
                    "events": events_cnt,
                },
            },
            run_id,
        )


##endregion
