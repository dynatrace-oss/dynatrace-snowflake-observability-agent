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
        utils._logging_findings(
            session, TestSpanDynatraceSnowAgent(session), "test_query_history", logging.INFO, show_detailed_logs=0
        )


if __name__ == "__main__":
    test_class = TestQueryHist()
    test_class.test_query_hist()
