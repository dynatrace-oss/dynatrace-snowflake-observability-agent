#!/usr/bin/env python3
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
"""Performance and memory regression tests for DSOA hot-path functions.

These tests verify that the optimized implementations of _cleanup_dict and
_pack_values_to_json_strings remain within acceptable performance and memory
bounds for high-volume Snowflake accounts.

Slow tests (marked with @pytest.mark.slow) are skipped by default in CI.
Run them explicitly with: pytest -m slow
"""

import tracemalloc
import time
import pytest

# ---------------------------------------------------------------------------
# Shared fixtures
# ---------------------------------------------------------------------------

SAMPLE_ROW = {
    "content": "SELECT * FROM my_table WHERE id = 1",
    "observed_timestamp": "1738792037000000000",
    "dsoa.run.context": "query_history",
    "dsoa.run.id": "50a37b21c21244a3b158dd50852662ab",
    "snowflake.query.id": "01ba329b-0412-df37-0051-0c031e0d1da6",
    "snowflake.query.operator.attributes": {"alias": "A", "nested": {"deep": 1}},
    "snowflake.query.operator.id": 9,
    "snowflake.query.operator.parent_ids": [3, 5, 7],
    "snowflake.query.operator.stats": {"input_rows": 20, "output_rows": 20},
    "snowflake.query.operator.time": {"overall_percentage": 0},
    "snowflake.query.operator.type": "WithReference",
    "snowflake.query.step.id": 2,
    "test.array.of.arrays": ["a", 1, ["b", 3, {"k": 4}]],
    "timestamp": "1738792037000000000",
    "null_field": None,
    "empty_dict": {},
    "empty_list": [],
    "nan_float": float("nan"),
}


# ---------------------------------------------------------------------------
# Unit tests for _is_nan_or_none (always run)
# ---------------------------------------------------------------------------


class TestIsNanOrNone:
    """Tests for the _is_nan_or_none helper — covers all value types."""

    def test_none_is_nan_or_none(self):
        from dtagent.util import _is_nan_or_none

        assert _is_nan_or_none(None) is True

    def test_float_nan_is_nan_or_none(self):
        from dtagent.util import _is_nan_or_none

        assert _is_nan_or_none(float("nan")) is True

    def test_float_zero_is_not_nan(self):
        from dtagent.util import _is_nan_or_none

        assert _is_nan_or_none(0.0) is False

    def test_float_value_is_not_nan(self):
        from dtagent.util import _is_nan_or_none

        assert _is_nan_or_none(3.14) is False

    def test_int_is_not_nan(self):
        from dtagent.util import _is_nan_or_none

        assert _is_nan_or_none(0) is False
        assert _is_nan_or_none(42) is False

    def test_bool_is_not_nan(self):
        from dtagent.util import _is_nan_or_none

        assert _is_nan_or_none(True) is False
        assert _is_nan_or_none(False) is False

    def test_empty_string_is_not_nan(self):
        from dtagent.util import _is_nan_or_none

        assert _is_nan_or_none("") is False

    def test_nan_string_is_not_nan(self):
        from dtagent.util import _is_nan_or_none

        # The string "NaN" is NOT a NaN value — only float NaN is
        assert _is_nan_or_none("NaN") is False

    def test_empty_dict_is_not_nan(self):
        from dtagent.util import _is_nan_or_none

        assert _is_nan_or_none({}) is False

    def test_empty_list_is_not_nan(self):
        from dtagent.util import _is_nan_or_none

        assert _is_nan_or_none([]) is False

    def test_bytes_is_not_nan(self):
        from dtagent.util import _is_nan_or_none

        assert _is_nan_or_none(b"data") is False

    def test_nested_dict_is_not_nan(self):
        from dtagent.util import _is_nan_or_none

        assert _is_nan_or_none({"key": "value"}) is False

    def test_list_with_values_is_not_nan(self):
        from dtagent.util import _is_nan_or_none

        assert _is_nan_or_none([1, 2, 3]) is False

    def test_import_datetime_nat_like(self):
        """Verify that datetime objects are not treated as NaN."""
        import datetime
        from dtagent.util import _is_nan_or_none

        assert _is_nan_or_none(datetime.datetime.now()) is False


# ---------------------------------------------------------------------------
# Benchmark tests (marked slow — skipped in CI by default)
# ---------------------------------------------------------------------------


class TestCleanupDictPerformance:
    """Performance regression tests for _cleanup_dict."""

    @pytest.mark.slow
    def test_cleanup_dict_1000_rows_under_1ms_each(self):
        """_cleanup_dict on 1000 rows must complete in under 1ms per row on average."""
        from dtagent.util import _cleanup_dict

        rows = [dict(SAMPLE_ROW) for _ in range(1000)]

        start = time.perf_counter()
        for row in rows:
            _cleanup_dict(row)
        elapsed = time.perf_counter() - start

        per_row_ms = (elapsed / 1000) * 1000
        assert per_row_ms < 1.0, f"_cleanup_dict too slow: {per_row_ms:.3f}ms per row (limit: 1ms)"

    @pytest.mark.slow
    def test_pack_values_1000_rows_under_1ms_each(self):
        """_pack_values_to_json_strings on 1000 rows must complete in under 1ms per row."""
        from dtagent.util import _pack_values_to_json_strings, _cleanup_dict

        rows = [dict(SAMPLE_ROW) for _ in range(1000)]

        start = time.perf_counter()
        for row in rows:
            _pack_values_to_json_strings(_cleanup_dict(row))
        elapsed = time.perf_counter() - start

        per_row_ms = (elapsed / 1000) * 1000
        assert per_row_ms < 1.0, f"hot-path too slow: {per_row_ms:.3f}ms per row (limit: 1ms)"


class TestHotPathMemory:
    """Memory regression test for the full hot-path at 5000 rows."""

    @pytest.mark.slow
    def test_5000_rows_memory_delta_under_100mb(self):
        """Full hot-path on 5000 rows must not allocate more than 100MB above baseline.

        Exercises _cleanup_dict → _pack_values_to_json_strings end-to-end.
        """
        from dtagent.util import _cleanup_dict, _pack_values_to_json_strings

        rows = [dict(SAMPLE_ROW) for _ in range(5000)]

        tracemalloc.start()
        snapshot_before = tracemalloc.take_snapshot()

        for row in rows:
            _pack_values_to_json_strings(_cleanup_dict(row))

        snapshot_after = tracemalloc.take_snapshot()
        tracemalloc.stop()

        stats = snapshot_after.compare_to(snapshot_before, "lineno")
        total_delta_bytes = sum(s.size_diff for s in stats if s.size_diff > 0)
        total_delta_mb = total_delta_bytes / (1024 * 1024)

        assert total_delta_mb < 100, f"Memory delta too high: {total_delta_mb:.1f}MB (limit: 100MB)"
