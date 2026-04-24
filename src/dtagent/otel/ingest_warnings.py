"""Thread-safe collector for ingest-quality warnings during a plugin run."""

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
from typing import Any, Dict, List

##endregion COMPILE_REMOVE

##region ------------------------ INGEST WARNING COLLECTOR ---------------------------------


class IngestWarningCollector:
    """Thread-safe collector for ingest-quality warnings during a plugin run.

    Warnings are accumulated across all exporters during a single plugin execution
    and flushed after each plugin completes.  The class uses only static methods
    (same pattern as ``OtelManager``) so no instance is required.

    Warning dict schema::

        {
            "warning_type": str,   # "partial_success" | "lines_invalid" | "attr_trimmed"
            "exporter":     str,   # "logs" | "spans" | "metrics" | "events" | "biz_events"
            "detail":       str,   # human-readable description
            "count":        int,   # number of affected items
        }
    """

    _warnings: List[Dict[str, Any]] = []
    _lock: threading.Lock = threading.Lock()

    @staticmethod
    def add_warning(warning_type: str, exporter: str, detail: str, count: int = 0) -> None:
        """Appends a new ingest-quality warning to the collector.

        Args:
            warning_type (str): Category of the warning.  One of
                ``"partial_success"``, ``"lines_invalid"``, or ``"attr_trimmed"``.
            exporter (str):     Name of the exporter that produced the warning.
                One of ``"logs"``, ``"spans"``, ``"metrics"``, ``"events"``,
                or ``"biz_events"``.
            detail (str):       Human-readable description of the warning.
            count (int):        Number of affected items.  Defaults to ``0``.
        """
        with IngestWarningCollector._lock:
            IngestWarningCollector._warnings.append(
                {
                    "warning_type": warning_type,
                    "exporter": exporter,
                    "detail": detail,
                    "count": count,
                }
            )

    @staticmethod
    def get_warnings() -> List[Dict[str, Any]]:
        """Returns a snapshot of all currently collected warnings.

        Returns:
            List[Dict[str, Any]]: Copy of the current warnings list.
        """
        with IngestWarningCollector._lock:
            return list(IngestWarningCollector._warnings)

    @staticmethod
    def has_warnings() -> bool:
        """Returns ``True`` if at least one warning has been collected.

        Returns:
            bool: Whether any warnings are present.
        """
        with IngestWarningCollector._lock:
            return bool(IngestWarningCollector._warnings)

    @staticmethod
    def reset() -> None:
        """Clears all collected warnings.  Call after each plugin run."""
        with IngestWarningCollector._lock:
            IngestWarningCollector._warnings.clear()


##endregion
