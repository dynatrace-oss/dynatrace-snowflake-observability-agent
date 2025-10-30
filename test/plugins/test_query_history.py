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
from test import TestConfiguration


class TestQueryHist:
    import pytest

    PICKLES = {"APP.V_RECENT_QUERIES": "test/test_data/recent_queries2.pkl"}

    @pytest.mark.xdist_group(name="test_telemetry")
    def test_query_hist(self):
        import logging
        from unittest.mock import patch

        from typing import Dict, Generator

        from snowflake import snowpark
        import pandas as pd
        import test._utils as utils

        from test import TestDynatraceSnowAgent, _get_session
        from dtagent.plugins.query_history import QueryHistoryPlugin

        # ======================================================================

        if utils.should_pickle(self.PICKLES.values()):
            session = _get_session()
            session.call("APP.P_REFRESH_RECENT_QUERIES", log_on_exception=True)
            utils._pickle_all(_get_session(), self.PICKLES)

        from dtagent.otel.spans import Spans

        class TestSpans(Spans):

            def _get_sub_rows(
                self,
                session: snowpark.Session,
                view_name: str,
                parent_row_id_col: str,
                row_id: str,
            ) -> Generator[Dict, None, None]:
                pandas_df = pd.read_pickle(TestQueryHist.PICKLES[view_name])
                print(f"Unpickled for {view_name} at {parent_row_id_col} = {row_id}")

                pandas_df = pandas_df[pandas_df[parent_row_id_col] == row_id]

                for _, row in pandas_df.iterrows():
                    from dtagent.util import _adjust_timestamp

                    row_dict = row.to_dict()
                    _adjust_timestamp(row_dict)
                    yield row_dict

        class TestQueryHistoryPlugin(QueryHistoryPlugin):

            def _get_table_rows(self, t_data: str) -> Generator[Dict, None, None]:
                return utils._safe_get_unpickled_entries(TestQueryHist.PICKLES, t_data, limit=3)

        class TestSpanDynatraceSnowAgent(TestDynatraceSnowAgent):
            from opentelemetry.sdk.resources import Resource

            def _get_spans(self, resource: Resource) -> Spans:
                return TestSpans(resource, self._configuration)

        def __local_get_plugin_class(source: str):
            return TestQueryHistoryPlugin

        from dtagent import plugins

        plugins._get_plugin_class = __local_get_plugin_class

        # ======================================================================

        session = _get_session()
        # when sending spans log level cannot be set, hence "" to omit it in the utils
        _local_configuration = utils.get_config()

        def __execute_test(disabled_telemetry: list):

            for telemetry_type in ("spans", "logs", "metrics", "events"):
                _local_configuration._config["otel"][telemetry_type]["is_disabled"] = telemetry_type in disabled_telemetry

            results = utils._logging_findings(
                session, TestSpanDynatraceSnowAgent(session, _local_configuration), "test_query_history", logging.INFO, False
            )

            assert "test_query_history" in results
            assert "query_history" in results["test_query_history"]
            assert results["test_query_history"]["query_history"].get("entries", 0) == 3
            # assert results["test_query_history"]["query_history"].get("errors", 0) == 0
            assert results["test_query_history"]["query_history"].get("logs", 0) == (3 if "logs" not in disabled_telemetry else 0)
            assert results["test_query_history"]["query_history"].get("spans", 0) == (3 if "spans" not in disabled_telemetry else 0)
            assert results["test_query_history"]["query_history"].get("metrics", 0) >= (3 if "metrics" not in disabled_telemetry else 0)
            assert results["test_query_history"]["query_history"].get("events", 0) == 0

        __execute_test(disabled_telemetry=[])
        __execute_test(disabled_telemetry=["logs"])
        __execute_test(disabled_telemetry=["spans"])
        __execute_test(disabled_telemetry=["metrics"])
        __execute_test(disabled_telemetry=["logs", "metrics"])
        __execute_test(disabled_telemetry=["metrics", "logs"])
        __execute_test(disabled_telemetry=["logs", "spans", "metrics", "events"])


if __name__ == "__main__":
    test_class = TestQueryHist()
    test_class.test_query_hist()
