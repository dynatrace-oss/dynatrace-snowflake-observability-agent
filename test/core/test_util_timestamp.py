import datetime
from dtagent.util import get_timestamp_in_ms


class TestUtilTimestamp:
    def test_get_timestamp_in_ms_datetime(self):
        dt = datetime.datetime(2025, 11, 20, 12, 0, 0, tzinfo=datetime.timezone.utc)
        # timestamp for this date is 1763640000.0
        # in ms it should be 1763640000000 (int)

        query_data = {"ts": dt}
        ts = get_timestamp_in_ms(query_data, "ts")

        assert isinstance(ts, int)
        assert ts == 1763640000000

    def test_get_timestamp_in_ms_int(self):
        ts_ns = 1763640000000000000
        query_data = {"ts": ts_ns}
        ts = get_timestamp_in_ms(query_data, "ts", conversion_unit=1e6)

        assert isinstance(ts, int)
        assert ts == 1763640000000
