#!/usr/bin/env python3
#
#
# These materials contain confidential information and
# trade secrets of Dynatrace LLC.  You shall
# maintain the materials as confidential and shall not
# disclose its contents to any third party except as may
# be required by law or regulation.  Use, disclosure,
# or reproduction is prohibited without the prior express
# written permission of Dynatrace LLC.
#
# All Compuware products listed within the materials are
# trademarks of Dynatrace LLC.  All other company
# or product names are trademarks of their respective owners.
#
# Copyright (c) 2024 Dynatrace LLC.  All rights reserved.
#
#

import os


class TestUtil:

    def test_adjust_timestamp(self):
        from dtagent.util import _adjust_timestamp, NANOSECOND_CONVERSION_RATE, _9_MINUTES_IN_SEC, _59_MINUTES_IN_SEC

        now = 1738786435157000192  # 2025-02-05 20:13:55.157 GMT
        min_past = now - _59_MINUTES_IN_SEC * NANOSECOND_CONVERSION_RATE  # now - 59 minutes in nanoseconds
        max_future = now + _9_MINUTES_IN_SEC * NANOSECOND_CONVERSION_RATE  # now + 9 minutes in nanoseconds
        # min_past   1738782895157000200    # 2025-02-05 19:14:55.157 GMT
        # max_future 1738786975157000200    # 2025-02-05 20:22:55.157 GMT

        row_dicts = [
            {
                # span_len   798071000000           # 13 minutes, 18.071 seconds.
                "TIMESTAMP": 1738786435157068725,  # 2025-02-05 20:13:55.157 GMT
                "START_TIME": 1738786435157068725,  # 2025-02-05 20:13:55.157 GMT
                "END_TIME": 1738787233228068725,  # 2025-02-05 20:27:13.228 GMT
                # start_time 1738786435157068725
                # end_time   1738786975157000200
            },
            {
                # span_len   798071000320           # 13 minutes, 18.071 seconds.
                "TIMESTAMP": 1738782785214999808,  # 2025-02-05 19:13:05.215 +0000
                "START_TIME": 1738782785214999808,  # 2025-02-05 19:13:05.215 +0000
                "END_TIME": 1738783583286000128,  # 2025-02-05 19:26:23.286 +0000
                # start_time 1738782895157000200    # 2025-02-05 19:14:55.157 PM
                # end_time   1738783583286000128
            },
        ]

        for row_dict in row_dicts:
            adjusted_row = _adjust_timestamp(row_dict, now=now)

            assert (
                row_dict["END_TIME"] - row_dict["START_TIME"] >= adjusted_row["END_TIME"] - adjusted_row["START_TIME"]
            )
            assert min_past <= adjusted_row["START_TIME"]
            assert min_past <= adjusted_row["TIMESTAMP"]
            assert min_past <= adjusted_row["END_TIME"]
            assert max_future >= adjusted_row["START_TIME"]
            assert max_future >= adjusted_row["TIMESTAMP"]
            assert max_future >= adjusted_row["END_TIME"]

    def test_pack_values_to_json_strings(self):
        from dtagent.util import _pack_values_to_json_strings

        input_dict = {
            "content": "Query operator: WithReference 01ba329b-0412-df37-0051-0c031e0d1da6:9",
            "observed_timestamp": "1738792037000000000",
            "dsoa.run.context": "query_history",
            "dsoa.run.id": "50a37b21c21244a3b158dd50852662ab",
            "snowflake.query.id": "01ba329b-0412-df37-0051-0c031e0d1da6",
            "snowflake.query.accel_est.estimated_query_times": {},
            "snowflake.query.operator.attributes": {"alias": "A"},
            "snowflake.query.operator.id": 9,
            "snowflake.query.operator.parent_ids": [3],
            "snowflake.query.operator.stats": {"input_rows": 20, "output_rows": 20},
            "snowflake.query.operator.time": {"overall_percentage": 0},
            "snowflake.query.operator.type": "WithReference",
            "snowflake.query.step.id": 2,
            "test.array.of.arrays": ["a", 1, ["b", 3, {"k": 4}]],
            "test.dict.of.empty.dicts": {"a": None, "b": {}, "c": {"c1": {}, "c2": None}},
            "timestamp": "1738792037000000000",
        }
        output_dict = {
            "content": "Query operator: WithReference 01ba329b-0412-df37-0051-0c031e0d1da6:9",
            "observed_timestamp": "1738792037000000000",
            "dsoa.run.context": "query_history",
            "dsoa.run.id": "50a37b21c21244a3b158dd50852662ab",
            "snowflake.query.id": "01ba329b-0412-df37-0051-0c031e0d1da6",
            "snowflake.query.operator.attributes": '{"alias": "A"}',
            "snowflake.query.operator.id": 9,
            "snowflake.query.operator.parent_ids": [3],
            "snowflake.query.operator.stats": '{"input_rows": 20, "output_rows": 20}',
            "snowflake.query.operator.time": '{"overall_percentage": 0}',
            "snowflake.query.operator.type": "WithReference",
            "snowflake.query.step.id": 2,
            "test.array.of.arrays": ["a", 1, '["b", 3, {"k": 4}]'],
            "test.dict.of.empty.dicts": """{"a": null, "b": {}, "c": {"c1": {}, "c2": null}}""",
            "timestamp": "1738792037000000000",
        }

        result_dict = _pack_values_to_json_strings(input_dict)

        assert output_dict == result_dict

    def test_cleanup_dict(self):
        from dtagent.util import _cleanup_dict

        input_dict = {
            "content": "Query operator: WithReference 01ba329b-0412-df37-0051-0c031e0d1da6:9",
            "observed_timestamp": "1738792037000000000",
            "dsoa.run.context": "query_history",
            "dsoa.run.id": "50a37b21c21244a3b158dd50852662ab",
            "snowflake.query.id": "01ba329b-0412-df37-0051-0c031e0d1da6",
            "snowflake.query.accel_est.estimated_query_times": {},
            "snowflake.query.operator.attributes": {"alias": "A"},
            "snowflake.query.operator.id": 9,
            "snowflake.query.operator.parent_ids": [3],
            "snowflake.query.operator.stats": {"input_rows": 20, "output_rows": 20},
            "snowflake.query.operator.time": {"overall_percentage": 0},
            "snowflake.query.operator.type": "WithReference",
            "snowflake.query.step.id": 2,
            "test.array.of.arrays": ["a", 1, ["b", 3, {"k": 4}]],
            "test.dict.of.empty.dicts": {"a": None, "b": {}, "c": {"c1": {}, "c2": []}, "d": []},
            "test.array.empty": [],
            "timestamp": "1738792037000000000",
        }
        output_dict = {
            "content": "Query operator: WithReference 01ba329b-0412-df37-0051-0c031e0d1da6:9",
            "observed_timestamp": "1738792037000000000",
            "dsoa.run.context": "query_history",
            "dsoa.run.id": "50a37b21c21244a3b158dd50852662ab",
            "snowflake.query.id": "01ba329b-0412-df37-0051-0c031e0d1da6",
            "snowflake.query.operator.attributes": {"alias": "A"},
            "snowflake.query.operator.id": 9,
            "snowflake.query.operator.parent_ids": [3],
            "snowflake.query.operator.stats": {"input_rows": 20, "output_rows": 20},
            "snowflake.query.operator.time": {"overall_percentage": 0},
            "snowflake.query.operator.type": "WithReference",
            "snowflake.query.step.id": 2,
            "test.array.of.arrays": ["a", 1, ["b", 3, {"k": 4}]],
            "timestamp": "1738792037000000000",
        }

        result_dict = _cleanup_dict(input_dict)

        assert output_dict == result_dict
