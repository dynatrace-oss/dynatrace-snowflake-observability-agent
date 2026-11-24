"""Thread-safe collector of attempted / delivered record counts per plugin and signal during an agent run."""

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

import threading
from typing import Any, Dict, List, Optional, Tuple

##endregion COMPILE_REMOVE

##region ------------------------ EXPORT STATS COLLECTOR ---------------------------------

UNKNOWN_PLUGIN = "unknown"

Attribution = Tuple[str, Optional[str]]  # (plugin, run id)


class ExportStatsCollector:
    """Thread-safe collector of attempted and delivered record counts per ``(plugin, run id, signal)``.

    ``attempted`` counts records handed over for sending (each record once, regardless of retries), ``delivered``
    counts records accepted by Dynatrace.  Counts accumulate over the whole agent run (all plugins) and are persisted
    once, after the exporters were shut down.  The class uses only static methods (same pattern as ``OtelManager``).

    Snapshot row schema::

        {
            "plugin":    str,   # plugin the counts belong to, ``unknown`` if no plugin was set
            "run_id":    str,   # run id of the plugin execution, ``None`` if no plugin was set
            "signal":    str,   # "logs" | "spans" | "metrics" | "events" | "davis_events" | "biz_events"
            "attempted": int,   # records handed over for sending
            "delivered": int,   # records accepted by Dynatrace
        }
    """

    _plugin: str = UNKNOWN_PLUGIN
    _run_id: Optional[str] = None
    _counts: Dict[Tuple[str, Optional[str], str], Dict[str, int]] = {}
    _lock: threading.Lock = threading.Lock()

    @staticmethod
    def set_plugin(plugin_name: str, run_id: Optional[str] = None) -> None:
        """Sets the plugin execution to which subsequently recorded counts are attributed.

        Args:
            plugin_name (str):          Name of the plugin that is about to run.
            run_id (Optional[str]):     Run id of that plugin execution.
        """
        with ExportStatsCollector._lock:
            ExportStatsCollector._plugin = plugin_name or UNKNOWN_PLUGIN
            ExportStatsCollector._run_id = run_id

    @staticmethod
    def get_attribution() -> Attribution:
        """Returns the ``(plugin, run id)`` to which counts are currently attributed.

        Exporters that keep records beyond the plugin run that produced them (e.g. events queued for resending) store this
        and pass it back when recording the outcome, so that attempted and delivered counts end up with the same plugin run.
        """
        with ExportStatsCollector._lock:
            return ExportStatsCollector._plugin, ExportStatsCollector._run_id

    @staticmethod
    def _add(signal: str, attempted: int, delivered: int, attribution: Optional[Attribution] = None) -> None:
        """Adds the given amounts to the counters of the given (default: current) plugin run and the given signal."""
        with ExportStatsCollector._lock:
            plugin, run_id = attribution or (ExportStatsCollector._plugin, ExportStatsCollector._run_id)
            key = (plugin, run_id, signal)
            counts = ExportStatsCollector._counts.setdefault(key, {"attempted": 0, "delivered": 0})
            counts["attempted"] += attempted
            counts["delivered"] += delivered

    @staticmethod
    def add_attempted(signal: str, count: int = 1, attribution: Optional[Attribution] = None) -> None:
        """Records that ``count`` records of the given signal were handed over for sending.

        Args:
            signal (str):                       Exporter signal, e.g. ``logs`` or ``metrics``.
            count (int):                        Number of records.  Non-positive values are ignored.
            attribution (Optional[Attribution]): ``(plugin, run id)`` the records belong to; defaults to the current one.
        """
        if count > 0:
            ExportStatsCollector._add(signal, count, 0, attribution)

    @staticmethod
    def add_delivered(signal: str, count: int = 1, attribution: Optional[Attribution] = None) -> None:
        """Records that ``count`` records of the given signal were accepted by Dynatrace.

        Args:
            signal (str):                       Exporter signal, e.g. ``logs`` or ``metrics``.
            count (int):                        Number of records.  Non-positive values are ignored.
            attribution (Optional[Attribution]): ``(plugin, run id)`` the records belong to; defaults to the current one.
        """
        if count > 0:
            ExportStatsCollector._add(signal, 0, count, attribution)

    @staticmethod
    def get_stats() -> List[Dict[str, Any]]:
        """Returns a snapshot of the collected counts, one entry per ``(plugin, run id, signal)``, sorted by plugin, run id and signal.

        Returns:
            List[Dict[str, Any]]: Copy of the current counts, see the class docstring for the schema.
        """
        with ExportStatsCollector._lock:
            return [
                {"plugin": plugin, "run_id": run_id, "signal": signal, "attempted": counts["attempted"], "delivered": counts["delivered"]}
                for (plugin, run_id, signal), counts in sorted(
                    ExportStatsCollector._counts.items(), key=lambda item: tuple(map(str, item[0]))
                )
            ]

    @staticmethod
    def delivery_confirmed(run_id: str) -> bool:
        """Tells whether the records of a run reached Dynatrace: something was attempted and every signal delivered at least one record.

        A heuristic used to decide whether data kept for later reporting can be considered reported: a signal without any delivered
        record means its requests failed, while a few rejected records (partial success) do not mean the endpoint was unreachable.

        Args:
            run_id (str): Run id of the plugin execution.

        Returns:
            bool: ``True`` if records were attempted and none of the signals ended up with zero delivered records.
        """
        with ExportStatsCollector._lock:
            run_counts = [counts for (_, run, _), counts in ExportStatsCollector._counts.items() if run == run_id]
        return any(counts["attempted"] for counts in run_counts) and all(
            counts["delivered"] > 0 for counts in run_counts if counts["attempted"] > 0
        )

    @staticmethod
    def reset() -> None:
        """Clears all counts and the current plugin.  Call after the counts were persisted."""
        with ExportStatsCollector._lock:
            ExportStatsCollector._counts.clear()
            ExportStatsCollector._plugin = UNKNOWN_PLUGIN
            ExportStatsCollector._run_id = None


##endregion
