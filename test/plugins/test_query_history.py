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
class TestQueryHist:
    def test_query_hist(self):
        import logging

        from typing import Dict, Generator

        from snowflake import snowpark
        import pandas as pd
        import test._utils as utils

        from test import TestDynatraceSnowAgent, _get_session
        from dtagent.plugins.query_history import QueryHistoryPlugin

        T_DATA_RECENT_QUERIES = "APP.V_RECENT_QUERIES"
        PICKLE_NAME = "test/test_data/recent_queries2.pkl"

        # ======================================================================

        if utils.should_pickle([PICKLE_NAME]):
            session = _get_session()
            session.call("APP.P_REFRESH_RECENT_QUERIES", log_on_exception=True)
            utils._pickle_data_history(session, T_DATA_RECENT_QUERIES, PICKLE_NAME)

        from dtagent.otel.spans import Spans

        class TestSpans(Spans):

            def _get_sub_rows(
                self,
                session: snowpark.Session,
                view_name: str,
                parent_row_id_col: str,
                row_id: str,
            ) -> Generator[Dict, None, None]:
                pandas_df = pd.read_pickle(PICKLE_NAME)
                print(f"Unpickled for {view_name} at {parent_row_id_col} = {row_id}")

                pandas_df = pandas_df[pandas_df[parent_row_id_col] == row_id]

                for _, row in pandas_df.iterrows():
                    from dtagent.util import _adjust_timestamp

                    row_dict = row.to_dict()
                    _adjust_timestamp(row_dict)
                    yield row_dict

        class TestQueryHistoryPlugin(QueryHistoryPlugin):

            def _get_table_rows(self, table_name: str = None) -> Generator[Dict, None, None]:
                return utils._get_unpickled_entries(PICKLE_NAME, limit=3)

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
        utils._logging_findings(session, TestSpanDynatraceSnowAgent(session), "test_query_history", logging.INFO, show_detailed_logs=0)


if __name__ == "__main__":
    test_class = TestQueryHist()
    test_class.test_query_hist()
