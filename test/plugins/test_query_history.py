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
    PICKLES = {"APP.V_RECENT_QUERIES": "test/test_data/recent_queries2.pkl"}

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
            @patch("dtagent.otel.events.requests.post")
            @patch("dtagent.otel.bizevents.requests.post")
            def process(self, run_proc: bool = True, mock_bizevents_post=None, mock_events_post=None) -> int:
                from dtagent.otel.otel_manager import OtelManager

                OtelManager.reset_current_fail_count()
                mock_events_post.side_effect = utils.side_effect_function
                mock_bizevents_post.side_effect = utils.side_effect_function
                logging.debug("EXECUTING TestQueryHistoryPlugin.process()")
                return super().process(run_proc)

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
        utils._logging_findings(
            session, TestSpanDynatraceSnowAgent(session, utils.get_config()), "test_query_history", logging.INFO, show_detailed_logs=0
        )


if __name__ == "__main__":
    test_class = TestQueryHist()
    test_class.test_query_hist()
