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
from dtagent.otel.otel_manager import OtelManager
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


_SIGNAL_CODES = {"logs": "l", "spans": "s", "metrics": "m", "events": "e", "davis_events": "d", "biz_events": "b"}


_TASK_PREFIX = "TASK_DTAGENT_"
_TASK_KEY = "tk"  # User-Agent segment holding the task name: the one shortened when a report is too long


def _build_user_agent_reports(
    tasks: Dict[str, int], exports: Dict[str, Dict[str, int]], task_runs: Optional[Dict[str, Dict[str, int]]] = None
) -> List[Dict[str, Any]]:
    """Builds the User-Agent reports of a heartbeat: one for the task runs and one per signal, each complete on its own.

    The User-Agent is very short, so the summary cannot be sent at once; every report carries its type (``hb``) and needs
    no other report to be understood, so the tenant just filters them by type and adds them up.  The period a report ends at is the time the
    request arrived at the tenant.

    * ``hb=t``: ``exp`` / ``ok`` / ``fail`` - expected, succeeded and failed task runs in the configured window (window total)
    * ``hb=<l|s|m|e|d|b>``: ``exp`` / ``dlv`` - records attempted / delivered for the signal since the previous report
    * ``tk=<task>``: ``exp`` / ``ok`` - how many times the task should have run and how many times it succeeded in the configured window
      (``exp`` is left out when the schedule of the task cannot be evaluated); the task name is shortened when the report would be too long

    Args:
        tasks (Dict[str, int]): task run totals, keys ``expected``, ``succeeded`` and ``failed``; empty if no task rows were read
        exports (Dict[str, Dict[str, int]]): ``attempted`` and ``delivered`` totals per signal
        task_runs (Optional[Dict[str, Dict[str, int]]]): ``expected`` (optional), ``succeeded`` and ``failed`` runs per task name

    Returns:
        List[Dict[str, Any]]: User-Agent segments of each report
    """
    reports: List[Dict[str, Any]] = []
    if tasks:
        reports.append({"hb": "t", "exp": tasks.get("expected", 0), "ok": tasks.get("succeeded", 0), "fail": tasks.get("failed", 0)})
    for signal, counts in sorted(exports.items()):
        reports.append({"hb": _SIGNAL_CODES.get(signal, signal), "exp": counts.get("attempted", 0), "dlv": counts.get("delivered", 0)})
    for task, runs in sorted((task_runs or {}).items()):
        if not runs.get("expected") and not runs.get("succeeded") and not runs.get("failed"):
            continue  # a task that is neither expected to run nor ran (e.g. of a disabled plugin) has nothing to report
        report: Dict[str, Any] = {_TASK_KEY: task, "exp": runs.get("expected"), "ok": runs.get("succeeded", 0)}
        reports.append({key: value for key, value in report.items() if value is not None})
    return reports


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

    # what the current run reports, aggregated while the rows are processed, to be sent in the User-Agent
    _ua_tasks: Dict[str, int] = {}
    _ua_exports: Dict[str, Dict[str, int]] = {}
    _ua_task_runs: Dict[str, Dict[str, int]] = {}

    def _get_table_rows(self, t_data: str) -> Generator[Dict, None, None]:
        """Adds the cron/interval based expected_runs to rows delivered by APP.F_HEARTBEAT_INSTRUMENTED();
        rows of the export statistics (APP.F_HEARTBEAT_EXPORTS_INSTRUMENTED()) are passed through as they are,
        remembering the cut-off up to which they report, to mark it as reported once they were delivered
        """
        for row_dict in super()._get_table_rows(t_data):
            if t_data == _T_HEARTBEAT:
                row_dict = self._add_expected_runs(row_dict)
                self._aggregate_tasks(row_dict)
                yield row_dict
                continue
            if t_data == _T_HEARTBEAT_EXPORTS:
                until = _as_dict(row_dict.get("ATTRIBUTES")).get("dsoa.heartbeat.export.reported_until")
                if until:
                    self._export_stats_reported_until = until
                self._aggregate_exports(row_dict)
            yield row_dict

    def _aggregate_tasks(self, row_dict: Dict) -> None:
        """Adds the expected, succeeded and failed runs of a heartbeat row to the totals reported in the User-Agent"""
        metrics = _as_dict(row_dict.get("METRICS"))
        for total, metric in (
            ("expected", "dsoa.heartbeat.expected_runs"),
            ("succeeded", "dsoa.heartbeat.runs.succeeded"),
            ("failed", "dsoa.heartbeat.runs.failed"),
        ):
            self._ua_tasks[total] = self._ua_tasks.get(total, 0) + int(metrics.get(metric) or 0)

        task = _as_dict(row_dict.get("DIMENSIONS")).get("dsoa.heartbeat.task")
        if task:
            runs = {
                "succeeded": int(metrics.get("dsoa.heartbeat.runs.succeeded") or 0),
                "failed": int(metrics.get("dsoa.heartbeat.runs.failed") or 0),
            }
            if metrics.get("dsoa.heartbeat.expected_runs") is not None:
                runs["expected"] = int(metrics["dsoa.heartbeat.expected_runs"])
            self._ua_task_runs[str(task).removeprefix(_TASK_PREFIX).lower()] = runs

    def _aggregate_exports(self, row_dict: Dict) -> None:
        """Adds the attempted and delivered records of an export statistics row to the per-signal totals reported in the User-Agent"""
        metrics = _as_dict(row_dict.get("METRICS"))
        signal = _as_dict(row_dict.get("DIMENSIONS")).get("dsoa.export.signal")
        if not signal:
            return
        counts = self._ua_exports.setdefault(signal, {"attempted": 0, "delivered": 0})
        counts["attempted"] += int(metrics.get("dsoa.heartbeat.export.attempted") or 0)
        counts["delivered"] += int(metrics.get("dsoa.heartbeat.export.delivered") or 0)

    def _report_via_user_agent(self) -> None:
        """Sends the heartbeat summary to the self-monitoring tenant in the User-Agent of dedicated requests, unless this was turned off.

        The User-Agent is too short for the whole summary, so one small, independent request is sent per report (see
        ``_build_user_agent_reports``).  The requests are separate from the exporters, so a rejected one cannot affect the telemetry
        of the heartbeat.  Failures are logged and swallowed.
        """
        from dtagent import LOG  # COMPILE_REMOVE

        if not self._configuration.get("report_via_user_agent", plugin_name=self.PLUGIN_NAME, default_value=True):
            return

        url, token = self._configuration.get("metrics.http"), self._configuration.get("dt.token")
        try:
            reports = _build_user_agent_reports(self._ua_tasks, self._ua_exports, self._ua_task_runs)
            sent = {"overview": 0, "signals": 0, "tasks": 0}
            for report in reports:
                if not OtelManager.send_user_agent_report(url, token, report, shrink_key=_TASK_KEY):
                    LOG.warning("Heartbeat summary was not sent completely in the User-Agent: the remaining reports are skipped")
                    break
                sent["tasks" if _TASK_KEY in report else "overview" if report.get("hb") == "t" else "signals"] += 1
            LOG.info(
                "Heartbeat summary sent in the User-Agent: %d of %d report(s) (overview: %d, signals: %d, tasks: %d of %d known tasks)",
                sum(sent.values()),
                len(reports),
                sent["overview"],
                sent["signals"],
                sent["tasks"],
                len(self._ua_task_runs),
            )
        except Exception as e:  # pylint: disable=broad-except
            LOG.warning("Unable to send the heartbeat summary in the User-Agent: %s", e)

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
        self._ua_tasks, self._ua_exports, self._ua_task_runs = {}, {}, {}

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

        self._report_via_user_agent()

        if results.get("heartbeat_exports", {}).get("entries", 0) > 0 and run_proc:
            self._mark_export_stats_reported(run_id)

        return self._report_results(results, run_id)


##endregion
