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
from zoneinfo import ZoneInfo, available_timezones
from croniter import croniter
from dtagent.plugins import Plugin
from dtagent.otel.export_stats import ExportStatsCollector
from dtagent.context import RUN_PLUGIN_KEY, RUN_RESULTS_KEY, RUN_ID_KEY  # COMPILE_REMOVE

##endregion COMPILE_REMOVE

##region ------------------ MEASUREMENT SOURCE: HEARTBEAT --------------------------------

_T_HEARTBEAT = "call DTAGENT_DB.APP.F_HEARTBEAT_INSTRUMENTED()"
_T_HEARTBEAT_EXPORTS = "call DTAGENT_DB.APP.F_HEARTBEAT_EXPORTS_INSTRUMENTED()"

_CRON_PREFIX = re.compile(r"^\s*USING\s+CRON\s+", re.IGNORECASE)
_INTERVAL = re.compile(r"^\s*(\d+)\s+(SECOND|MINUTE|HOUR|DAY)S?\s*$", re.IGNORECASE)
_INTERVAL_SECONDS = {"SECOND": 1, "MINUTE": 60, "HOUR": 3600, "DAY": 86400}
_MAX_CRON_ITERATIONS = 100000  # safety net against pathological schedules / huge windows


def _resolve_timezone(name: str) -> "Optional[ZoneInfo]":
    """Resolves an IANA time zone name case-insensitively (zoneinfo keys are case-sensitive on most file systems).

    Args:
        name (str): time zone name, e.g. `UTC` or `europe/warsaw`

    Returns:
        Optional[ZoneInfo]: the time zone, or None if it is unknown
    """
    try:
        return ZoneInfo(name)
    except (KeyError, ValueError, OSError):  # ZoneInfoNotFoundError is a KeyError
        pass
    by_lower = {key.lower(): key for key in available_timezones()}
    key = by_lower.get(name.lower())
    return ZoneInfo(key) if key else None


def _expected_cron_runs(schedule: str, window_hours: float, now: Optional[datetime.datetime]) -> Optional[int]:
    """Returns the number of runs a `USING CRON <expression> <time zone>` schedule implies within the window, or None if it is invalid.

    Args:
        schedule (str): Snowflake task schedule string starting with `USING CRON`
        window_hours (float): length of the window ending at `now`
        now (Optional[datetime.datetime]): end of the window, defaults to current UTC time

    Returns:
        Optional[int]: number of scheduled runs in the (now - window_hours, now] window
    """
    # croniter understands neither the USING CRON prefix nor the trailing time zone: strip both, apply the time zone to the window
    parts = _CRON_PREFIX.sub("", schedule).split()
    if len(parts) < 2:  # an expression and a time zone are both required
        return None
    *expression, timezone = parts
    expression = " ".join(expression)
    if not croniter.is_valid(expression):
        return None

    tz = _resolve_timezone(timezone)
    if tz is None:
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
        interval_seconds = int(interval.group(1)) * _INTERVAL_SECONDS[interval.group(2).upper()]
        if interval_seconds <= 0:  # e.g. `0 MINUTES` - not a valid schedule
            return None
        return int(window_hours * 3600) // interval_seconds

    if not _CRON_PREFIX.match(schedule):
        return None

    return _expected_cron_runs(schedule, window_hours, now)


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
    PLUGIN_CONTEXTS: tuple = ("heartbeat", "heartbeat_exports")

    # cut-off up to which the export statistics read by the current run report; they are marked as reported once delivered
    _export_stats_reported_until: Optional[str] = None

    def _get_table_rows(self, t_data: str) -> Generator[Dict, None, None]:
        """Adds the cron/interval based expected_runs to rows delivered by APP.F_HEARTBEAT_INSTRUMENTED();
        rows of the export statistics (APP.F_HEARTBEAT_EXPORTS_INSTRUMENTED()) are passed through as they are,
        remembering the cut-off up to which they report, to mark it as reported once they were delivered
        """
        for row_dict in super()._get_table_rows(t_data):
            if t_data == _T_HEARTBEAT:
                yield self._add_expected_runs(row_dict)
                continue
            if t_data == _T_HEARTBEAT_EXPORTS:
                until = _as_dict(row_dict.get("ATTRIBUTES")).get("dsoa.heartbeat.export.reported_until")
                if until:
                    self._export_stats_reported_until = until
            yield row_dict

    def _mark_export_stats_reported(self, run_id: str) -> None:
        """Marks the export statistics reported by this run in STATUS.EXPORT_STATS, so that the next heartbeat does not report them again.

        Rows stay unmarked, and are therefore reported again by the next heartbeat, when nothing was reported or when the delivery of
        this run's telemetry could not be confirmed (see ``ExportStatsCollector.delivery_confirmed``).  Failures are logged and swallowed.

        Args:
            run_id (str): unique run identifier
        """
        from dtagent import LOG  # COMPILE_REMOVE

        until = self._export_stats_reported_until
        if not until:
            return

        # logs are exported by a background thread: delivering them now makes the delivery check below reliable
        self._logs.flush_logs()
        if not ExportStatsCollector.delivery_confirmed(run_id):
            LOG.warning("Export statistics were not marked as reported: delivery of the heartbeat telemetry could not be confirmed")
            return

        try:
            self._session.sql(
                "update DTAGENT_DB.STATUS.EXPORT_STATS set REPORTED_TS = current_timestamp() where REPORTED_TS is null and RUN_TS <= ?::timestamp_ltz",
                params=[until],
            ).collect()
        except Exception as e:  # pylint: disable=broad-except
            LOG.warning("Unable to mark export statistics as reported: %s", e)

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
        """Compares configured and actual agent tasks and their expected and actual runs, and reports export statistics.

        Args:
            run_id (str): unique run identifier
            run_proc (bool): indicator whether processing should be logged as completed
            contexts (Optional[List[str]]): context names to process; ``None`` means all contexts are processed

        Returns:
            Dict[str, Dict[str, int]]: A dictionary with telemetry counts for each processed context.

            Example:
            {
            "dsoa.run.results": {
                "heartbeat": {
                    "entries": entries_cnt,
                    "log_lines": logs_cnt,
                    "metrics": metrics_cnt,
                    "events": events_cnt,
                },
                "heartbeat_exports": {
                    "entries": exports_entries_cnt,
                    "log_lines": exports_logs_cnt,
                    "metrics": exports_metrics_cnt,
                    "events": exports_events_cnt,
                },
            },
            "dsoa.run.id": "uuid_string"
            }
        """
        results: Dict[str, Dict[str, int]] = {}
        self._export_stats_reported_until = None

        if not contexts or "heartbeat" in contexts:
            entries_cnt, logs_cnt, metrics_cnt, events_cnt = self._log_entries(
                lambda: self._get_table_rows(_T_HEARTBEAT),
                "heartbeat",
                run_uuid=run_id,
                log_completion=run_proc,
            )
            results["heartbeat"] = {
                "entries": entries_cnt,
                "log_lines": logs_cnt,
                "metrics": metrics_cnt,
                "events": events_cnt,
            }

        if not contexts or "heartbeat_exports" in contexts:
            entries_cnt, logs_cnt, metrics_cnt, events_cnt = self._log_entries(
                lambda: self._get_table_rows(_T_HEARTBEAT_EXPORTS),
                "heartbeat_exports",
                run_uuid=run_id,
                log_completion=False,
            )
            results["heartbeat_exports"] = {
                "entries": entries_cnt,
                "log_lines": logs_cnt,
                "metrics": metrics_cnt,
                "events": events_cnt,
            }
            if run_proc and entries_cnt > 0:
                self._mark_export_stats_reported(run_id)

        return self._report_results(results, run_id)


##endregion
