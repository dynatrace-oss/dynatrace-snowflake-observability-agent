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

            assert row_dict["END_TIME"] - row_dict["START_TIME"] >= adjusted_row["END_TIME"] - adjusted_row["START_TIME"]
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

    def test_cleanup_data_mixed_types(self):
        """Test that _cleanup_data normalizes mixed-type sequences intelligently"""
        from dtagent.util import _cleanup_data

        # Test case 1: Mixed int and numeric string - should normalize to int
        input_dict = {"mixed_list": [1, "2", 3]}
        result = _cleanup_data(input_dict)
        assert result["mixed_list"] == [1, 2, 3], f"Expected all ints, got {result['mixed_list']}"

        # Test case 2: Mixed with non-numeric string - should normalize to strings
        input_dict = {"mixed_list": [1, "abc", 3]}
        result = _cleanup_data(input_dict)
        assert result["mixed_list"] == ["1", "abc", "3"], f"Expected all strings, got {result['mixed_list']}"

        # Test case 3: Nested mixed types with numeric strings
        input_dict = {
            "value.list": [1, "2", 3],
            "nested": {"inner_list": [1, "2.5", 3]},
        }
        result = _cleanup_data(input_dict)
        assert result["value.list"] == [1, 2, 3], "Should normalize to int"
        assert result["nested"]["inner_list"] == [1, 2.5, 3], "Should normalize to numeric (int/float mix becomes float)"

        # Test case 4: Homogeneous lists should remain unchanged
        input_dict = {
            "all_ints": [1, 2, 3],
            "all_strings": ["a", "b", "c"],
            "all_floats": [1.0, 2.0, 3.0],
        }
        result = _cleanup_data(input_dict)
        assert result["all_ints"] == [1, 2, 3], "Homogeneous int list should not be converted"
        assert result["all_strings"] == ["a", "b", "c"], "Homogeneous string list should not be converted"
        assert result["all_floats"] == [1.0, 2.0, 3.0], "Homogeneous float list should not be converted"

        # Test case 5: Single element or empty lists should not be affected
        input_dict = {
            "single_element": [1],
            "empty_list": [],
        }
        result = _cleanup_data(input_dict)
        assert result["single_element"] == [1]
        assert result["empty_list"] == []

        # Test case 6: Lists with None values mixed with numeric types
        input_dict = {"with_none": [1, None, "2", None, 3]}
        result = _cleanup_data(input_dict)
        assert result["with_none"] == [1, None, 2, None, 3], "Should normalize to int, preserving None"

        # Test case 7: Boolean with numbers should convert to numbers
        input_dict = {"bool_and_int": [True, 1, False, 0]}
        result = _cleanup_data(input_dict)
        # True=1, False=0 in Python, so this should remain as numbers
        assert all(isinstance(x, (int, bool)) for x in result["bool_and_int"]), "Should keep as numeric types"


class TestGetSnowflakeAccountInfo:
    """Test cases for _get_snowflake_account_info function"""

    def test_both_account_and_host_provided(self):
        """Test when both account_name and host_name are explicitly provided"""
        from dtagent.util import _get_snowflake_account_info

        config_dict = {
            "core.snowflake.account_name": "myorg-myaccount",
            "core.snowflake.host_name": "myorg-myaccount.snowflakecomputing.com",
        }

        account_name, host_name = _get_snowflake_account_info(config_dict)

        assert account_name == "myorg-myaccount"
        assert host_name == "myorg-myaccount.snowflakecomputing.com"

    def test_only_account_provided_derives_host(self):
        """Test when only account_name is provided - should derive host_name"""
        from dtagent.util import _get_snowflake_account_info

        config_dict = {"core.snowflake.account_name": "myorg-myaccount", "core.snowflake.host_name": "-"}

        account_name, host_name = _get_snowflake_account_info(config_dict)

        assert account_name == "myorg-myaccount"
        assert host_name == "myorg-myaccount.snowflakecomputing.com"

    def test_only_account_provided_legacy_format(self):
        """Test legacy account.region format - should derive host_name"""
        from dtagent.util import _get_snowflake_account_info

        config_dict = {"core.snowflake.account_name": "abc12345.us-east-1", "core.snowflake.host_name": ""}

        account_name, host_name = _get_snowflake_account_info(config_dict)

        assert account_name == "abc12345.us-east-1"
        assert host_name == "abc12345.us-east-1.snowflakecomputing.com"

    def test_only_host_provided_extracts_account(self):
        """Test when only host_name is provided - should extract account_name"""
        from dtagent.util import _get_snowflake_account_info

        config_dict = {"core.snowflake.account_name": "-", "core.snowflake.host_name": "myorg-myaccount.snowflakecomputing.com"}

        account_name, host_name = _get_snowflake_account_info(config_dict)

        assert account_name == "myorg-myaccount"
        assert host_name == "myorg-myaccount.snowflakecomputing.com"

    def test_only_host_provided_legacy_format(self):
        """Test extracting account from legacy format host_name"""
        from dtagent.util import _get_snowflake_account_info

        config_dict = {"core.snowflake.account_name": "", "core.snowflake.host_name": "abc12345.us-east-1.snowflakecomputing.com"}

        account_name, host_name = _get_snowflake_account_info(config_dict)

        assert account_name == "abc12345.us-east-1"
        assert host_name == "abc12345.us-east-1.snowflakecomputing.com"

    def test_neither_provided_no_session(self):
        """Test when neither is provided and no session - should return empty strings"""
        from dtagent.util import _get_snowflake_account_info

        config_dict = {"core.snowflake.account_name": "-", "core.snowflake.host_name": "-"}

        account_name, host_name = _get_snowflake_account_info(config_dict, session=None)

        assert account_name == ""
        assert host_name == ""

    def test_neither_provided_with_session_queries_snowflake(self):
        """Test when neither is provided but session available - should query Snowflake"""
        from dtagent.util import _get_snowflake_account_info
        from unittest.mock import Mock

        # Mock Snowflake session - simulate a Row object with indexing support
        mock_session = Mock()
        mock_row = Mock()

        def _mock_row_getitem(idx):
            # Simulate Snowflake Row index behavior: integer indices only, with support for -1 as last element.
            if not isinstance(idx, int):
                raise TypeError("Row indices must be integers")
            if idx in (0, -1):
                return "testorg-testaccount"
            raise IndexError("Row index out of range")

        mock_row.__getitem__ = Mock(side_effect=_mock_row_getitem)
        mock_session.sql.return_value.collect.return_value = [mock_row]

        config_dict = {"core.snowflake.account_name": "", "core.snowflake.host_name": ""}

        account_name, host_name = _get_snowflake_account_info(config_dict, session=mock_session)

        assert account_name == "testorg-testaccount"
        assert host_name == "testorg-testaccount.snowflakecomputing.com"
        # Verify SQL was called with correct query
        mock_session.sql.assert_called_once_with(
            "SELECT CURRENT_ORGANIZATION_NAME() || '-' || CURRENT_ACCOUNT_NAME() as account_identifier"
        )

    def test_session_query_fails_gracefully(self):
        """Test when session query fails - should return empty strings"""
        from dtagent.util import _get_snowflake_account_info
        from unittest.mock import Mock
        from snowflake.snowpark.exceptions import SnowparkSQLException

        # Mock session that raises exception
        mock_session = Mock()
        mock_session.sql.side_effect = SnowparkSQLException("Connection error")

        config_dict = {"core.snowflake.account_name": "-", "core.snowflake.host_name": "-"}

        account_name, host_name = _get_snowflake_account_info(config_dict, session=mock_session)

        assert account_name == ""
        assert host_name == ""

    def test_placeholder_values_normalized(self):
        """Test that '-' placeholder values are normalized to empty strings"""
        from dtagent.util import _get_snowflake_account_info

        config_dict = {"core.snowflake.account_name": "-", "core.snowflake.host_name": "-"}

        account_name, host_name = _get_snowflake_account_info(config_dict)

        # Should return empty strings, not "-"
        assert account_name == ""
        assert host_name == ""

    def test_account_already_has_domain_suffix(self):
        """Test when account_name already has .snowflakecomputing.com suffix"""
        from dtagent.util import _get_snowflake_account_info

        config_dict = {"core.snowflake.account_name": "myorg-myaccount.snowflakecomputing.com", "core.snowflake.host_name": ""}

        account_name, host_name = _get_snowflake_account_info(config_dict)

        assert account_name == "myorg-myaccount.snowflakecomputing.com"
        assert host_name == "myorg-myaccount.snowflakecomputing.com"

    def test_non_standard_hostname(self):
        """Test handling of non-standard hostname that doesn't match pattern"""
        from dtagent.util import _get_snowflake_account_info

        config_dict = {"core.snowflake.account_name": "", "core.snowflake.host_name": "custom-hostname.example.com"}

        account_name, host_name = _get_snowflake_account_info(config_dict)

        # Should use the whole hostname as account_name when pattern doesn't match
        assert account_name == "custom-hostname.example.com"
        assert host_name == "custom-hostname.example.com"

    def test_empty_dict(self):
        """Test with empty config dict"""
        from dtagent.util import _get_snowflake_account_info

        config_dict = {}

        account_name, host_name = _get_snowflake_account_info(config_dict)

        assert account_name == ""
        assert host_name == ""

    def test_session_returns_empty_result(self):
        """Test when session query returns empty result set"""
        from dtagent.util import _get_snowflake_account_info
        from unittest.mock import Mock

        mock_session = Mock()
        mock_session.sql.return_value.collect.return_value = []

        config_dict = {"core.snowflake.account_name": "-", "core.snowflake.host_name": "-"}

        account_name, host_name = _get_snowflake_account_info(config_dict, session=mock_session)

        assert account_name == ""
        assert host_name == ""

    def test_real_snowflake_session_queries_account_info(self):
        """Test with real Snowflake session to query account information

        This test runs only when test/credentials.yml is present.
        It verifies that _get_snowflake_account_info can successfully query
        a real Snowflake instance for account details.
        """
        from test import is_local_testing, _get_session, _get_credentials
        from dtagent.util import _get_snowflake_account_info

        # Skip if no credentials available (local testing mode)
        if is_local_testing():
            import pytest

            pytest.skip("Skipping real Snowflake test - no credentials available")

        # Get credentials and session
        credentials = _get_credentials()
        session = _get_session()
        expected_account = credentials.get("account", "")

        # Test with empty config - should query Snowflake
        config_dict = {"core.snowflake.account_name": "", "core.snowflake.host_name": ""}

        account_name, host_name = _get_snowflake_account_info(config_dict, session=session)

        # Verify we got actual values back
        assert account_name != "", "account_name should not be empty"
        assert host_name != "", "host_name should not be empty"
        assert host_name.endswith(".snowflakecomputing.com"), f"host_name should end with .snowflakecomputing.com, got: {host_name}"

        # Verify the account name matches the credentials (case-insensitive)
        # The query returns "org-account" format (e.g., "ORGID-ACCOUNT_NAME")
        # while credentials may have "account.region" format (e.g., "account_name.cloud_region").
        # Check that either the account_name matches expected or the expected account appears in the returned values
        account_name_lower = account_name.lower()
        expected_account_lower = expected_account.lower()
        host_name_lower = host_name.lower()

        # Extract the account part from credentials if it has region format (e.g., "account.region" -> "account")
        expected_account_base = expected_account_lower.split(".")[0] if "." in expected_account_lower else expected_account_lower

        # Verify that the expected account is present in the retrieved values (case-insensitive)
        assert (
            account_name_lower == expected_account_lower  # Exact match
            or expected_account_lower in host_name_lower  # Expected account in host
            or expected_account_base in account_name_lower  # Base account name in retrieved account
            or expected_account_base in host_name_lower  # Base account name in host
        ), f"Expected account '{expected_account}' not found in retrieved account_name '{account_name}' or host_name '{host_name}'"
