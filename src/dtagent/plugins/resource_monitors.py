"""Plugin file for processing resource monitors plugin data."""

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
import logging
from datetime import datetime
from typing import Tuple, Dict, Optional, List
from snowflake.snowpark.functions import current_timestamp
from dtagent.util import _unpack_json_dict, EVENT_TIMESTAMP_KEYS_PAYLOAD_NAME, is_regular_mode
from dtagent.plugins import Plugin
from dtagent.context import get_context_name_and_run_id, RUN_PLUGIN_KEY, RUN_RESULTS_KEY, RUN_ID_KEY  # COMPILE_REMOVE
from dtagent.otel.events import EventType

##endregion COMPILE_REMOVE

##region ------------------ MEASUREMENT SOURCE: RESOURCE MONITORS --------------------------------

# Ordered band levels — index encodes ordinal rank (higher = more severe).
_BAND_LEVELS = ["info", "warn", "critical", "exhausted"]

# Alert bands (emit ACTIVE/CLOSED lifecycle events).
_ALERT_BANDS = {"warn", "critical", "exhausted"}

# Default thresholds [info%, warn%, critical%, exhausted%].
_DEFAULT_THRESHOLDS = [50, 80, 90, 100]

# Event type per band.
_BAND_EVENT_TYPE = {
    "info": EventType.CUSTOM_INFO,
    "warn": EventType.CUSTOM_ALERT,
    "critical": EventType.CUSTOM_ALERT,
    "exhausted": EventType.ERROR_EVENT,
}

# Sentinel value stored in state table when no band is active.
_NO_BAND = ""


def _escape_sql_str(value: str) -> str:
    """Escapes single quotes in a string for safe interpolation into SQL string literals."""
    return value.replace("'", "''")


class ResourceMonitorsPlugin(Plugin):
    """Resource monitors plugin class."""

    PLUGIN_NAME = "resource_monitors"

    def __init__(self, **kwargs):
        """Initialises plugin and per-run state variables.

        Args:
            **kwargs: Passed through to the Plugin base class.
        """
        super().__init__(**kwargs)
        self.unattached_rms: int = 0
        self.unmonitored_wh: int = 0
        self.has_account_rm: bool = False
        self._davis_events = None

    ##region ---- event-timestamp helpers ----

    def _prepare_event_timestamps_payload_rm(self, key, ts, row_dict):
        """Prepares event timestamp payload for resource monitors.

        Args:
            key: Event timestamp key.
            ts:  Timestamp value.
            row_dict (Dict): Full row dictionary.

        Returns:
            Tuple[str, Dict, EventType]: title, properties, event type.
        """
        payload = _unpack_json_dict(row_dict, ["DIMENSIONS"])
        return (
            f"Resource monitor {payload.get('snowflake.resource_monitor.name', '')} event: {key}",
            {
                "timestamp": ts,
                EVENT_TIMESTAMP_KEYS_PAYLOAD_NAME: key,
            },
            EventType.CUSTOM_INFO,
        )

    def _process_log_rm(self, row_dict: Dict, __context: Dict, log_level: int) -> bool:  # pylint: disable=unused-argument
        """Processes logging for resource monitors.

        Args:
            row_dict (Dict): Row data dictionary.
            __context (Dict): Context dictionary (unused).
            log_level (int): Log level (unused — custom logic applies).

        Returns:
            bool: Always False; account-level flag is tracked as side-effect.
        """
        if not row_dict.get("IS_ACTIVE", False):
            self.unattached_rms += 1

        self.has_account_rm |= row_dict.get("IS_ACCOUNT_LEVEL", False)
        # we only send a single log per execution if there is no account level monitor set up, so no logging here is necessary
        return False

    def _prepare_event_timestamps_payload_wh(self, key, ts, row_dict):
        """Prepares event timestamp payloads for warehouses in resource monitors plugin.

        Args:
            key: Event timestamp key.
            ts:  Timestamp value.
            row_dict (Dict): Full row dictionary.

        Returns:
            Tuple[str, Dict, EventType]: title, properties, event type.
        """
        payload = _unpack_json_dict(row_dict, ["DIMENSIONS"])

        return (
            f"Warehouse {payload.get('snowflake.warehouse.name', '')} is not monitored",
            {
                "timestamp": ts,
                "snowflake.warehouse.event": key,
            },
            EventType.CUSTOM_INFO,
        )

    def _process_log_wh(self, row_dict: Dict, __context: Dict, log_level: int) -> bool:  # pylint: disable=unused-argument
        """Processes logs for warehouses view in resource monitors.

        Args:
            row_dict (Dict): Row data dictionary.
            __context (Dict): Context dictionary (unused).
            log_level (int): Log level (unused — custom logic applies).

        Returns:
            bool: True if a log was emitted, False otherwise.
        """
        # we use custom log level here, so passed log_level remains unused
        payload = _unpack_json_dict(row_dict, ["DIMENSIONS", "ATTRIBUTES", "METRICS"])

        if payload.get("snowflake.warehouse.is_unmonitored", False):
            self._logs.send_log(
                message=f"Warehouse {payload.get('snowflake.warehouse.name', '')} is not monitored",
                extra=payload,
                log_level=logging.WARN,
                context=__context,
            )
            self.unmonitored_wh += 1
            return True

        return False

    ##endregion

    ##region ---- threshold helpers ----

    @staticmethod
    def _band_level(band: Optional[str]) -> int:
        """Returns ordinal rank of *band* (higher = more severe). None / unknown → -1.

        Args:
            band (Optional[str]): Band name, one of `info|warn|critical|exhausted`, or None.

        Returns:
            int: Ordinal rank; -1 for None or unrecognised values.
        """
        if band in _BAND_LEVELS:
            return _BAND_LEVELS.index(band)
        return -1

    def _load_thresholds(self) -> Tuple[List[int], Dict[str, List[int]]]:
        """Loads threshold configuration from plugin config.

        Returns:
            Tuple[List[int], Dict[str, List[int]]]:
                defaults — list of threshold percentages (monotonically increasing),
                overrides — mapping of UPPERCASE monitor name → threshold list.
        """
        thresh_conf = self._configuration.get(plugin_name=self.PLUGIN_NAME, key="CREDITS_QUOTA_THRESHOLDS", default_value={})
        defaults = list(thresh_conf.get("defaults", _DEFAULT_THRESHOLDS))
        overrides_raw = thresh_conf.get("overrides", {}) or {}
        overrides = {str(k).upper(): list(v) for k, v in overrides_raw.items() if v}
        return defaults, overrides

    @staticmethod
    def _validate_thresholds(thresholds: List[int]) -> bool:
        """Returns True when *thresholds* is a non-empty, strictly increasing list in (0, 100].

        Args:
            thresholds (List[int]): Threshold percentages to validate.

        Returns:
            bool: True if valid; False otherwise.
        """
        if not thresholds:
            return False
        prev = 0
        for v in thresholds:
            if not isinstance(v, (int, float)) or v <= prev or v > 100:
                return False
            prev = v
        return True

    def _resolve_thresholds_for(self, monitor_name: str, defaults: List[int], overrides: Dict[str, List[int]]) -> List[int]:
        """Resolves the threshold list for *monitor_name*.

        Resolution order: per-monitor override → defaults → hardcoded fallback.
        Invalid overrides produce an ERROR log and fall back to defaults.

        Args:
            monitor_name (str): Uppercase resource monitor name.
            defaults (List[int]): Default threshold list from config.
            overrides (Dict[str, List[int]]): Per-monitor override mapping.

        Returns:
            List[int]: Resolved, validated threshold list.
        """
        candidate = overrides.get(monitor_name, defaults)
        if not self._validate_thresholds(candidate):
            logging.getLogger(__name__).error(
                "Invalid threshold override for resource monitor %s: %r — falling back to defaults",
                monitor_name,
                candidate,
            )
            candidate = defaults if self._validate_thresholds(defaults) else _DEFAULT_THRESHOLDS
        return candidate

    @staticmethod
    def _compute_band(used_pct: float, thresholds: List[int]) -> Optional[str]:
        """Returns the highest band crossed by *used_pct* given *thresholds*.

        Band assignment is value-driven using absolute cutoffs:
          - `<thresholds[0]`  → None (below any threshold)
          - `<80`             → ``info``
          - `[80, 90)`        → ``warn``
          - `[90, 100)`       → ``critical``
          - `>=100`           → ``exhausted``

        Args:
            used_pct (float): Current percentage of quota used.
            thresholds (List[int]): Resolved threshold list (monotonically increasing).

        Returns:
            Optional[str]: Highest band name, or None if below the lowest threshold.
        """
        # Sort descending so we pick the highest crossed band first.
        sorted_thresholds = sorted(thresholds, reverse=True)
        for t in sorted_thresholds:
            if used_pct >= t:
                # Determine band label from absolute value.
                if t >= 100:
                    return "exhausted"
                if t >= 90:
                    return "critical"
                if t >= 80:
                    return "warn"
                return "info"
        return None

    @staticmethod
    def _plan_transition(
        curr_band: Optional[str],
        last_band: Optional[str],
    ) -> List[Tuple[str, str, str]]:
        """Pure function: returns a list of (band, direction, status) emit instructions.

        Each instruction tuple contains:
          - band (str): band to emit event at
          - direction (str): ``up`` (entering) or ``down`` (closing)
          - status (str): ``ACTIVE``, ``CLOSED``, or ``""`` (info band — no status)

        Implements the ACTIVE/CLOSED transition state machine from the plan.

        Args:
            curr_band (Optional[str]): Band computed this run; None = below lowest threshold.
            last_band (Optional[str]): Band recorded in state table from last run; None = no state.

        Returns:
            List[Tuple[str, str, str]]: Ordered list of (band, direction, status) emit instructions.
        """
        instructions: List[Tuple[str, str, str]] = []

        curr_rank = ResourceMonitorsPlugin._band_level(curr_band)
        last_rank = ResourceMonitorsPlugin._band_level(last_band)

        if curr_band == last_band:
            # Same band — re-send ACTIVE keepalive if this is an alert band.
            if curr_band in _ALERT_BANDS:
                instructions.append((curr_band, "up", "ACTIVE"))
        elif curr_rank > last_rank:
            # Upward transition.
            # If crossing from an info band to a higher alert band, no close needed for info.
            # Just open the new band.
            status = "ACTIVE" if curr_band in _ALERT_BANDS else ""
            instructions.append((curr_band, "up", status))
        else:
            # Downward transition (curr_rank < last_rank).
            # Close the previous alert band if it was alerting.
            if last_band in _ALERT_BANDS:
                instructions.append((last_band, "down", "CLOSED"))
            # Open the new band if there is one.
            if curr_band is not None:
                status = "ACTIVE" if curr_band in _ALERT_BANDS else ""
                instructions.append((curr_band, "up", status))

        return instructions

    def _read_last_bands(self, monitor_names: List[str]) -> Dict[str, Tuple[Optional[str], Optional[datetime]]]:
        """Reads last-emitted bands and update timestamps for all named monitors.

        Returns an empty mapping when the session is not in regular (Snowflake) mode,
        ensuring safe no-op behaviour in tests.

        Args:
            monitor_names (List[str]): Resource monitor names to look up (UPPERCASE).

        Returns:
            Dict[str, Tuple[Optional[str], Optional[datetime]]]: Mapping from monitor name
                to ``(last_band, last_updated)``. Both are ``None`` when no state row exists.
        """
        if not is_regular_mode(self._session):
            return {}

        result: Dict[str, Tuple[Optional[str], Optional[datetime]]] = {name: (None, None) for name in monitor_names}
        if not monitor_names:
            return result

        quoted = ", ".join(f"'{_escape_sql_str(n)}'" for n in monitor_names)
        rows = self._session.sql(
            f"SELECT MONITOR_NAME, LAST_BAND, LAST_UPDATED FROM STATUS.RESOURCE_MONITOR_THRESHOLD_STATE WHERE MONITOR_NAME IN ({quoted})"
        ).collect()

        for row in rows:
            name = row["MONITOR_NAME"]
            band = row["LAST_BAND"]
            last_updated = row["LAST_UPDATED"]
            result[name] = (band if band else None, last_updated)

        return result

    def _write_band_state(self, monitor_name: str, band: Optional[str], used_pct: float) -> None:
        """Upserts the threshold state for a single resource monitor.

        No-op when the session is not in regular (Snowflake) mode.

        Args:
            monitor_name (str): UPPERCASE resource monitor name.
            band (Optional[str]): Band to persist; None clears the state (deletes row).
            used_pct (float): Current percentage of quota used.
        """
        if not is_regular_mode(self._session):
            return

        safe_name = _escape_sql_str(monitor_name)
        if band is None:
            self._session.sql(f"DELETE FROM STATUS.RESOURCE_MONITOR_THRESHOLD_STATE WHERE MONITOR_NAME = '{safe_name}'").collect()
        else:
            safe_band = _escape_sql_str(band)
            self._session.sql(
                "MERGE INTO STATUS.RESOURCE_MONITOR_THRESHOLD_STATE AS tgt "
                "USING (SELECT $1 AS MONITOR_NAME, $2 AS LAST_BAND, $3 AS LAST_USED_PCT FROM VALUES "
                f"('{safe_name}', '{safe_band}', {used_pct})) AS src "
                "ON tgt.MONITOR_NAME = src.MONITOR_NAME "
                "WHEN MATCHED THEN UPDATE SET tgt.LAST_BAND = src.LAST_BAND, "
                "tgt.LAST_USED_PCT = src.LAST_USED_PCT, tgt.LAST_UPDATED = CURRENT_TIMESTAMP() "
                "WHEN NOT MATCHED THEN INSERT (MONITOR_NAME, LAST_BAND, LAST_USED_PCT) "
                "VALUES (src.MONITOR_NAME, src.LAST_BAND, src.LAST_USED_PCT)"
            ).collect()

    def _cleanup_orphan_state(self, seen_monitors: List[str]) -> None:
        """Deletes state rows for monitors no longer present in Snowflake.

        No-op when the session is not in regular (Snowflake) mode.

        Args:
            seen_monitors (List[str]): UPPERCASE names of all monitors observed this run.
        """
        if not is_regular_mode(self._session) or not seen_monitors:
            return

        quoted = ", ".join(f"'{_escape_sql_str(n)}'" for n in seen_monitors)
        self._session.sql(f"DELETE FROM STATUS.RESOURCE_MONITOR_THRESHOLD_STATE WHERE MONITOR_NAME NOT IN ({quoted})").collect()

    def _prepare_event_payload_threshold(
        self,
        monitor_name: str,
        band: str,
        direction: str,
        status: str,
        used_pct: float,
        rm_level: str,
        thresholds: List[int],
    ) -> Dict:
        """Builds the Davis event payload for a threshold crossing.

        Args:
            monitor_name (str): Resource monitor name.
            band (str): Alert band (``info|warn|critical|exhausted``).
            direction (str): ``up`` or ``down``.
            status (str): ``ACTIVE``, ``CLOSED``, or ``""`` for info.
            used_pct (float): Current percentage of quota used.
            rm_level (str): ``ACCOUNT`` or ``WAREHOUSE``.
            thresholds (List[int]): Resolved threshold list for this monitor.

        Returns:
            Tuple[str, Dict, str]: Event title, properties dict, and status string
                (``"ACTIVE"``, ``"CLOSED"``, or ``""`` for info band).
        """
        if direction == "down":
            # For CLOSED events use the characteristic threshold of the band being closed,
            # not used_pct (which is already below that band).
            band_min = {"exhausted": 100, "critical": 90, "warn": 80, "info": 0}
            threshold_pct = next((t for t in sorted(thresholds) if t >= band_min.get(band, 0)), thresholds[0])
        else:
            threshold_pct = next((t for t in sorted(thresholds, reverse=True) if used_pct >= t), thresholds[0])
        title_prefix = "[ACCOUNT] " if rm_level == "ACCOUNT" else ""
        direction_label = "exceeded" if direction == "up" else "dropped below"
        title = f"{title_prefix}Resource monitor {monitor_name} credits {direction_label} {threshold_pct}% threshold"

        properties = {
            "snowflake.resource_monitor.threshold.level": band,
            "snowflake.resource_monitor.threshold.pct": threshold_pct,
            "snowflake.resource_monitor.threshold.direction": direction,
            "snowflake.credits.quota.used_pct": used_pct,
            "snowflake.resource_monitor.level": rm_level,
            "snowflake.resource_monitor.name": monitor_name,
        }

        return title, properties, status

    def _report_threshold_davis_event(
        self,
        monitor_name: str,
        band: str,
        direction: str,
        status: str,
        used_pct: float,
        rm_level: str,
        thresholds: List[int],
        context: Dict,
    ) -> int:
        """Emits a single threshold Davis event.

        Creates a DavisEvents sender on first call (lazy initialisation) and reuses
        it for the lifetime of the plugin invocation.

        Args:
            monitor_name (str): Resource monitor name.
            band (str): Alert band.
            direction (str): ``up`` or ``down``.
            status (str): ``ACTIVE``, ``CLOSED``, or ``""`` for info band.
            used_pct (float): Current percentage of quota used.
            rm_level (str): ``ACCOUNT`` or ``WAREHOUSE``.
            thresholds (List[int]): Resolved threshold list for this monitor.
            context (Dict): DSOA run context dictionary.

        Returns:
            int: 1 if the event was emitted successfully, 0 otherwise.
        """
        from dtagent.otel.events.davis import DavisEvents  # COMPILE_REMOVE

        if not hasattr(self, "_davis_events") or self._davis_events is None:
            self._davis_events = DavisEvents(self._configuration)

        title, properties, event_status = self._prepare_event_payload_threshold(
            monitor_name, band, direction, status, used_pct, rm_level, thresholds
        )

        event_type = _BAND_EVENT_TYPE.get(band, EventType.CUSTOM_ALERT)

        return self._davis_events.report_via_api(
            query_data={"_MESSAGE": title, **properties},
            event_type=event_type,
            is_data_structured=False,
            context=context,
            title=title,
            additional_payload=properties,
            status=event_status if event_status else None,
        )

    def _process_threshold_for_rm(
        self,
        row_dict: Dict,
        defaults: List[int],
        overrides: Dict[str, List[int]],
        last_bands: Dict[str, Optional[str]],
        context: Dict,
        last_updated_map: Optional[Dict[str, Optional[datetime]]] = None,
    ) -> Tuple[int, Optional[str], str]:
        """Evaluates threshold state for a single resource monitor row and emits events.

        Skips rows where IS_ACTIVE is False or credits quota is zero/negative.
        Emits Davis events per the ACTIVE/CLOSED transition plan, then returns
        updated band and monitor name so the caller can persist state.

        Args:
            row_dict (Dict): Unpacked row from V_RESOURCE_MONITORS.
            defaults (List[int]): Default threshold list.
            overrides (Dict[str, List[int]]): Per-monitor override mapping.
            last_bands (Dict[str, Optional[str]]): Last-emitted bands from state table.
            context (Dict): DSOA run context dictionary.
            last_updated_map (Optional[Dict[str, Optional[datetime]]]): Last state-write
                timestamps per monitor; used for keepalive rate-limiting. None disables
                rate-limiting (safe for tests that do not pass timestamp state).

        Returns:
            Tuple[int, Optional[str], str]:
                events_emitted — number of events sent (>=0),
                new_band — band to persist (None = clear state),
                monitor_name — UPPERCASE resource monitor name (empty str if not found).
        """
        metrics = _unpack_json_dict(row_dict, ["METRICS"])
        dims = _unpack_json_dict(row_dict, ["DIMENSIONS"])
        attrs = _unpack_json_dict(row_dict, ["ATTRIBUTES"])

        monitor_name = str(dims.get("snowflake.resource_monitor.name", "")).upper()
        if not monitor_name:
            return 0, None, ""

        # Skip inactive or quota-less monitors.
        if not row_dict.get("IS_ACTIVE", False):
            return 0, None, monitor_name

        quota = float(metrics.get("snowflake.credits.quota", 0) or 0)
        if quota <= 0:
            return 0, None, monitor_name

        used_pct = float(metrics.get("snowflake.credits.quota.used_pct", 0) or 0)
        rm_level = str(attrs.get("snowflake.resource_monitor.level", "WAREHOUSE")).upper()

        thresholds = self._resolve_thresholds_for(monitor_name, defaults, overrides)
        curr_band = self._compute_band(used_pct, thresholds)
        last_band = last_bands.get(monitor_name)

        instructions = self._plan_transition(curr_band, last_band)

        # Rate-limit same-band keepalive instructions when the last state write is recent.
        if last_updated_map is not None and curr_band == last_band and curr_band in _ALERT_BANDS:
            last_updated = last_updated_map.get(monitor_name)
            if last_updated is not None:
                keepalive_minutes = self._configuration.get(
                    "resource_monitors.credits_quota_thresholds.active_keepalive_timeout_minutes", 60
                )
                elapsed = (datetime.utcnow() - last_updated).total_seconds() / 60
                if elapsed < keepalive_minutes:
                    instructions = [(b, d, s) for b, d, s in instructions if not (d == "up" and s == "ACTIVE" and b == curr_band)]

        events_emitted = 0
        for band, direction, status in instructions:
            emitted = self._report_threshold_davis_event(monitor_name, band, direction, status, used_pct, rm_level, thresholds, context)
            events_emitted += emitted

        # Flush after all instructions for this monitor.
        if hasattr(self, "_davis_events") and self._davis_events is not None:
            events_emitted += self._davis_events.flush_events()

        # Persist state only when events were successfully sent, or when clearing state for
        # a monitor that dropped below all thresholds with no events to send (e.g. info→None).
        no_event_needed = not instructions and curr_band is None and last_band is not None
        if (instructions and events_emitted > 0) or no_event_needed:
            self._write_band_state(monitor_name, curr_band, used_pct)

        return events_emitted, curr_band, monitor_name

    ##endregion

    def process(self, run_id: str, run_proc: bool = True, contexts: Optional[List[str]] = None) -> Dict[str, Dict[str, int]]:
        """Processes the measures on resource monitors.

        Args:
            run_id (str): unique run identifier
            run_proc (bool): indicator whether processing should be logged as completed

        Returns:
            Dict[str,int]: A dictionary with counts of processed telemetry data.

            Example:
            {
            "dsoa.run.results": {
                "resource_monitors": {
                    "entries": entries_cnt,
                    "log_lines": logs_cnt,
                    "metrics": metrics_cnt,
                    "events": events_cnt,
                },
                "warehouses": {
                    "entries": entries_cnt,
                    "log_lines": logs_cnt,
                    "metrics": metrics_cnt,
                    "events": events_cnt,
                },
            },
            "dsoa.run.id": "uuid_string"
            }
        """
        context_name = "resource_monitors"
        results_dict = {}

        if run_proc:
            # we need to refresh the temporary tables with resource monitors and warehouse telemetry
            self._session.call("APP.P_REFRESH_RESOURCE_MONITORS")

        if not contexts or "resource_monitors" in contexts:
            # Pre-load threshold state for all monitors in one SQL call.
            all_rm_rows = list(self._get_table_rows("APP.V_RESOURCE_MONITORS"))
            defaults, overrides = self._load_thresholds()

            # Collect monitor names for state look-up.
            monitor_names: List[str] = []
            for rw in all_rm_rows:
                dims = _unpack_json_dict(rw, ["DIMENSIONS"])
                nm = str(dims.get("snowflake.resource_monitor.name", "")).upper()
                if nm:
                    monitor_names.append(nm)

            raw_state = self._read_last_bands(monitor_names)
            last_bands: Dict[str, Optional[str]] = {k: v[0] for k, v in raw_state.items()}
            last_updated_map: Dict[str, Optional[datetime]] = {k: v[1] for k, v in raw_state.items()}
            threshold_events_cnt = 0
            seen_monitors: List[str] = []

            threshold_context = get_context_name_and_run_id(plugin_name=self._plugin_name, context_name=context_name, run_id=run_id)

            (
                resource_monitors_entries_cnt,
                resource_monitors_logs_cnt,
                resource_monitors_metrics_cnt,
                resource_monitors_events_cnt,
            ) = self._log_entries(
                f_entry_generator=lambda: iter(all_rm_rows),
                context_name=context_name,
                run_uuid=run_id,
                f_event_timestamp_payload_prepare=self._prepare_event_timestamps_payload_rm,
                f_report_log=self._process_log_rm,
                log_completion=False,
            )

            # Threshold evaluation pass.
            for rw in all_rm_rows:
                evts, _new_band, mon_name = self._process_threshold_for_rm(
                    rw, defaults, overrides, last_bands, threshold_context, last_updated_map
                )
                threshold_events_cnt += evts
                if mon_name:
                    seen_monitors.append(mon_name)

            self._cleanup_orphan_state(seen_monitors)

            results_dict["resource_monitors"] = {
                "entries": resource_monitors_entries_cnt,
                "log_lines": resource_monitors_logs_cnt,
                "metrics": resource_monitors_metrics_cnt,
                "events": resource_monitors_events_cnt,
                "davis_events": threshold_events_cnt,
            }

            if not self.has_account_rm:
                # we do not seem to have a account level resource monitor setup - send a warning
                self._logs.send_log(
                    "There is no ACCOUNT level resource monitor setup",
                    log_level=logging.ERROR,
                    context=get_context_name_and_run_id(plugin_name=self._plugin_name, context_name=context_name, run_id=run_id),
                )

        if not contexts or "warehouses" in contexts:
            (
                warehouses_entries_cnt,
                warehouses_logs_cnt,
                warehouses_metrics_cnt,
                warehouses_events_cnt,
            ) = self._log_entries(
                f_entry_generator=lambda: self._get_table_rows("APP.V_WAREHOUSES"),
                context_name=context_name,
                run_uuid=run_id,
                f_event_timestamp_payload_prepare=self._prepare_event_timestamps_payload_wh,
                f_report_log=self._process_log_wh,
                log_completion=False,
            )
            results_dict["warehouses"] = {
                "entries": warehouses_entries_cnt,
                "log_lines": warehouses_logs_cnt,
                "metrics": warehouses_metrics_cnt,
                "events": warehouses_events_cnt,
            }

        if run_proc:
            self._report_execution("resource_monitors", current_timestamp(), None, results_dict, run_id=run_id)

        return self._report_results(results_dict, run_id)


##endregion
