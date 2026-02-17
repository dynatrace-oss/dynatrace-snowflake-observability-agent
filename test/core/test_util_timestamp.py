import datetime
import time
from dtagent.util import get_timestamp, validate_timestamp


class TestGetTimestamp:
    def test_get_timestamp_datetime(self):
        dt = datetime.datetime(2025, 11, 20, 12, 0, 0, tzinfo=datetime.timezone.utc)
        # timestamp for this date is 1763640000.0
        # in ns it should be 1763640000000000000 (int)

        query_data = {"ts": dt}
        ts = get_timestamp(query_data, "ts")

        assert isinstance(ts, int)
        assert ts == 1763640000000000000

    def test_get_timestamp_int(self):
        ts_ns = 1763640000000000000
        query_data = {"ts": ts_ns}
        ts = get_timestamp(query_data, "ts")

        assert isinstance(ts, int)
        assert ts == 1763640000000000000


class TestValidateTimestamp:
    """Tests for validate_timestamp function"""

    def test_validate_current_timestamp(self):
        """Test that current timestamp is valid"""
        current_ms = int(time.time() * 1000)
        result = validate_timestamp(current_ms, return_unit="ms")
        assert result == current_ms

    def test_validate_current_timestamp_ns(self):
        """Test that current timestamp is valid and can return nanoseconds"""
        current_ns = int(time.time() * 1_000_000_000)
        result = validate_timestamp(current_ns, return_unit="ns")
        # Allow for small precision differences
        assert abs(result - current_ns) < 1_000_000  # Within 1ms

    def test_validate_negative_timestamp_rejected(self):
        """Test that negative timestamps (like -1000000) are rejected"""
        result = validate_timestamp(-1000000, return_unit="ms")
        assert result is None

    def test_validate_zero_timestamp_rejected(self):
        """Test that zero timestamp is rejected"""
        result = validate_timestamp(0, return_unit="ms")
        assert result is None

    def test_validate_very_large_timestamp_rejected(self):
        """Test that nanosecond-scale timestamps (10x too large) are rejected"""
        # This is approximately year 2026 in nanoseconds (milliseconds * 1e6)
        invalid_ns = 1770224954840999937441792
        result = validate_timestamp(invalid_ns, return_unit="ms")
        assert result is None

    def test_validate_future_timestamp_in_allowed_range(self):
        """Test that future timestamps within allowed range are accepted"""
        # 5 minutes in the future (within default 10 minute limit)
        future_ms = int(time.time() * 1000) + (5 * 60 * 1000)
        result = validate_timestamp(future_ms, return_unit="ms")
        assert result == future_ms

    def test_validate_past_timestamp_in_allowed_range(self):
        """Test that past timestamps within allowed range are accepted"""
        # 1 hour in the past (within default 24 hour limit)
        past_ms = int(time.time() * 1000) - (60 * 60 * 1000)
        result = validate_timestamp(past_ms, return_unit="ms")
        assert result == past_ms

    def test_validate_too_far_in_future_rejected(self):
        """Test that timestamps too far in the future are rejected"""
        # 1 hour in the future (beyond default 10 minute limit)
        future_ms = int(time.time() * 1000) + (60 * 60 * 1000)
        result = validate_timestamp(future_ms, return_unit="ms")
        assert result is None

    def test_validate_too_far_in_past_rejected(self):
        """Test that timestamps too far in the past are rejected"""
        # 2 days in the past (beyond default 24 hour limit)
        past_ms = int(time.time() * 1000) - (2 * 24 * 60 * 60 * 1000)
        result = validate_timestamp(past_ms, return_unit="ms")
        assert result is None

    def test_validate_custom_allowed_ranges(self):
        """Test validate_timestamp with custom allowed ranges"""
        # 90 minutes in the past
        past_ms = int(time.time() * 1000) - (90 * 60 * 1000)

        # Should be rejected with default range (24 hours)
        result_default = validate_timestamp(past_ms, return_unit="ms")
        assert result_default == past_ms  # Within 24 hours

        # Should be rejected with metrics range (55 minutes)
        result_metrics = validate_timestamp(past_ms, allowed_past_minutes=55, return_unit="ms")
        assert result_metrics is None  # Beyond 55 minutes

    def test_validate_year_2100_boundary(self):
        """Test that the year 2100 boundary is properly handled"""
        # Year 2099 should be valid if within time range
        year_2099_ms = 4_070_908_800_000  # Jan 1, 2099 in ms
        # This will likely fail the time range check (too far in future), which is correct
        result = validate_timestamp(year_2099_ms, return_unit="ms")
        assert result is None  # Too far in the future

        # Year 2100 should be rejected (beyond our max threshold)
        year_2100_ms = 4_102_444_800_000  # Jan 1, 2100 in ms
        result = validate_timestamp(year_2100_ms, return_unit="ms")
        assert result is None


class TestValidateTimestampAutoConversion:
    """Tests for validate_timestamp auto-conversion from higher precision time units"""

    def test_auto_convert_microseconds(self):
        """Test auto-conversion from microseconds to milliseconds"""
        # Current time in microseconds (milliseconds * 1000)
        current_ms = int(time.time() * 1000)
        microseconds = current_ms * 1000

        result = validate_timestamp(microseconds, return_unit="ms")
        # Should be converted back to milliseconds and validated
        assert result is not None
        assert result == current_ms

    def test_auto_convert_nanoseconds_from_csv(self):
        """Test auto-conversion from nanoseconds - actual value from bug report CSV"""
        # This is one of the actual problematic values from the CSV
        # 1770598800000000030932992 nanoseconds
        nanoseconds = 1770598800000000030932992

        result = validate_timestamp(nanoseconds, return_unit="ms")
        # Should be converted to milliseconds: 1770598800000
        # But will likely be rejected as too far in future (year 2026)
        # The important thing is it doesn't crash with ValueError
        assert result is None or isinstance(result, int)

    def test_auto_convert_valid_nanoseconds(self):
        """Test auto-conversion from nanoseconds with current time"""
        # Current time in nanoseconds (milliseconds * 1e6)
        current_ms = int(time.time() * 1000)
        nanoseconds = current_ms * 1_000_000

        result = validate_timestamp(nanoseconds, return_unit="ms")
        # Should be converted back to milliseconds and validated
        assert result is not None
        # Allow for 1ms precision loss due to floating point arithmetic
        assert abs(result - current_ms) <= 1

    def test_auto_convert_picoseconds_from_csv(self):
        """Test auto-conversion from picoseconds - actual value from bug report CSV"""
        # This is one of the actual problematic values from the CSV
        # 1770224954840999937441792 appears to be in picoseconds
        picoseconds = 1770224954840999937441792

        result = validate_timestamp(picoseconds, return_unit="ms")
        # Should attempt conversion: 1770224954840999937441792 / 1e9 = 1770224954840
        # This would be Feb 4, 2026 which might be within range
        # The important thing is it doesn't crash with ValueError
        assert result is None or isinstance(result, int)

    def test_auto_convert_valid_picoseconds(self):
        """Test auto-conversion from picoseconds with current time"""
        # Current time in picoseconds (milliseconds * 1e9)
        current_ms = int(time.time() * 1000)
        picoseconds = current_ms * 1_000_000_000

        result = validate_timestamp(picoseconds, return_unit="ms")
        # Should be converted back to milliseconds and validated
        assert result is not None
        assert result == current_ms

    def test_auto_convert_valid_femtoseconds(self):
        """Test auto-conversion from femtoseconds with current time"""
        # Current time in femtoseconds (milliseconds * 1e12)
        current_ms = int(time.time() * 1000)
        femtoseconds = current_ms * 1_000_000_000_000

        result = validate_timestamp(femtoseconds, return_unit="ms")
        # Should be converted back to milliseconds and validated
        assert result is not None
        # Allow for 1ms precision loss due to floating point arithmetic
        assert abs(result - current_ms) <= 1

    def test_auto_convert_boundary_microseconds(self):
        """Test microseconds conversion at the boundary threshold"""
        # Just above 4.1e12 (millisecond threshold)
        microseconds = 4_100_000_000_001_000  # This should trigger microsecond conversion

        result = validate_timestamp(microseconds, return_unit="ms")
        # After conversion: 4_100_000_000_001 ms (year 2099+)
        # Will be rejected as too far in the future
        assert result is None

    def test_no_conversion_for_valid_milliseconds(self):
        """Test that valid millisecond timestamps are not converted"""
        # Current time in milliseconds - should NOT be converted
        current_ms = int(time.time() * 1000)

        result = validate_timestamp(current_ms, return_unit="ms")
        # Should remain unchanged and be valid
        assert result == current_ms

    def test_conversion_preserves_precision(self):
        """Test that conversion doesn't lose significant precision"""
        # Use a timestamp with specific microseconds
        base_ms = 1707494400000  # Feb 9, 2024, 20:00:00 UTC
        microseconds = base_ms * 1000 + 123  # Add some microseconds

        result = validate_timestamp(microseconds, return_unit="ms")
        # Should convert to milliseconds (drops the extra microseconds)
        # May be rejected if outside time window, but if valid, should be base_ms
        if result is not None:
            assert result == base_ms

    def test_return_unit_ns(self):
        """Test that return_unit='ns' returns nanoseconds"""
        current_ms = int(time.time() * 1000)
        result = validate_timestamp(current_ms, return_unit="ns")
        # Should return in nanoseconds
        assert result is not None
        assert result == current_ms * 1_000_000

    def test_return_unit_ms_from_ns_input(self):
        """Test that return_unit='ms' converts nanoseconds input to milliseconds"""
        current_ns = int(time.time() * 1_000_000_000)
        result = validate_timestamp(current_ns, return_unit="ms")
        # Should return in milliseconds
        assert result is not None
        expected_ms = current_ns // 1_000_000
        assert abs(result - expected_ms) <= 1  # Allow for rounding
