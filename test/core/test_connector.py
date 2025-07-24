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

import logging
from dtagent.util import get_now_timestamp, get_now_timestamp_formatted
from test import _get_creds, _get_session
from test._utils import LocalTelemetrySender, read_clean_json_from_file, telemetry_test_sender
from snowflake import snowpark

LOG = logging.getLogger("DTAGENT_TEST")
LOG.setLevel(logging.DEBUG)


class TestTelemetrySender:
    """Testing TelemetrySender:

    * sending all data from a given (standard structure) view
    * sending data from a given (standard structure) view, excluding metrics
    * sending data from a given (standard structure) view, excluding events
    * sending data from a given (standard structure) view, excluding logs
    * sending all data from a given (standard structure) object
    * sending all data from a given (standard structure) list of objects
    * sending data from a given (standard structure) list of objects, excluding metrics
    * sending data from a given (standard structure) list of objects, excluding events
    * sending data from a given (standard structure) list of objects, excluding logs
    * sending all data from a given (custom structure) view as logs
    * sending all data from a given (custom structure) view as events
    * sending all data from a given (custom structure) view as bizevents
    * sending all data from a given (custom structure) view as logs, events, and bizevents
    """

    def __prepare_view(self, session: snowpark.Session, rows_cnt: int) -> None:
        credentials = _get_creds()

        dtagent_admin = credentials.get("role", "DTAGENT_VIEWER").replace("_VIEWER", "_ADMIN")
        dtagent_db = credentials.get("database", "DTAGENT_DB")
        dtagent_wh = credentials.get("warehouse", "DTAGENT_WH")

        session.sql(f"use role {dtagent_admin}").collect()
        session.sql(f"use warehouse {dtagent_wh}").collect()
        session.sql(f"use database {dtagent_db}").collect()
        session.sql(
            f"""
            create or replace temp view PUBLIC.V_TMP_QUERY_HISTORY as
             select QUERY_ID, substr(QUERY_TEXT, 1, 1000) as QUERY_TEXT, * EXCLUDE (QUERY_ID, QUERY_TEXT) from SNOWFLAKE.ACCOUNT_USAGE.QUERY_HISTORY limit {rows_cnt}
            """
        ).collect()

    def test_viewsend(self):
        import random

        rows_cnt = random.randint(10, 20)

        session = _get_session()
        self.__prepare_view(session, rows_cnt)
        results = telemetry_test_sender(
            session,
            "public.v_tmp_query_history",
            {"auto_mode": False, "logs": True, "events": True, "bizevents": True},
        )

        assert results[0] == rows_cnt  # all
        assert results[1] == rows_cnt  # logs
        assert results[-2] == rows_cnt  # events
        assert results[-1] == rows_cnt  # bizevents

    def test_large_view_send_as_be(self):
        import random

        rows_cnt = random.randint(410, 500)

        LOG.debug("We will send %s rows as BizEvents", rows_cnt)

        session = _get_session()
        self.__prepare_view(session, rows_cnt)
        results = telemetry_test_sender(
            session,
            "public.v_tmp_query_history",
            {"auto_mode": False, "logs": False, "events": False, "bizevents": True},
        )

        LOG.debug("We have sent %d rows as BizEvents", results[-1])

        assert results[0] == rows_cnt  # all
        assert results[1] == 0  # logs
        assert results[-2] == 0  # events
        assert results[-1] == rows_cnt  # bizevents

    def test_dtagent_bizevents(self):

        session = _get_session()

        sender = LocalTelemetrySender(session, {"auto_mode": False, "logs": False, "events": False, "bizevents": True})
        results = sender.send_data(
            [
                {
                    "event.provider": str(sender._configuration.get(context="resource.attributes", key="host.name")),
                    "dsoa.task.exec.id": get_now_timestamp_formatted(),
                    "dsoa.task.name": "test_events",
                    "dsoa.task.exec.status": "FINISHED",
                }
            ]
        )
        sender.teardown()

        assert results[-1] == 1

    def test_automode(self):
        session = _get_session()

        structured_test_data = read_clean_json_from_file("test/test_data/telemetry_structured.json")
        unstructured_test_data = read_clean_json_from_file("test/test_data/telemetry_unstructured.json")

        # sending all data from a given (standard structure) view
        assert (2, 2, 2, 3, 0) == telemetry_test_sender(session, LocalTelemetrySender.T_DATA, {})
        # sending data from a given (standard structure) view, excluding metrics
        assert (2, 2, 0, 3, 0) == telemetry_test_sender(session, LocalTelemetrySender.T_DATA, {"metrics": False})
        # sending data from a given (standard structure) view, excluding events
        assert (2, 2, 2, 0, 0) == telemetry_test_sender(session, LocalTelemetrySender.T_DATA, {"events": False})
        # sending data from a given (standard structure) view, excluding logs
        assert (2, 0, 2, 3, 0) == telemetry_test_sender(session, LocalTelemetrySender.T_DATA, {"logs": False})

        # sending all data from a given (standard structure) object
        assert (1, 1, 1, 2, 0) == telemetry_test_sender(session, structured_test_data[0], {})
        # sending all data from a given (standard structure) view
        assert (2, 2, 2, 3, 0) == telemetry_test_sender(session, structured_test_data, {})
        # sending data from a given (standard structure) view, excluding metrics
        assert (2, 2, 0, 3, 0) == telemetry_test_sender(session, structured_test_data, {"metrics": False})
        # sending data from a given (standard structure) view, excluding events
        assert (2, 2, 2, 0, 0) == telemetry_test_sender(session, structured_test_data, {"events": False})
        # sending data from a given (standard structure) view, excluding logs
        assert (2, 0, 2, 3, 0) == telemetry_test_sender(session, structured_test_data, {"logs": False})

        # sending all data from a given (custom structure) view as logs
        assert (3, 3, 0, 0, 0) == telemetry_test_sender(session, unstructured_test_data, {"auto_mode": False})
        # sending all data from a given (custom structure) view as events
        assert (3, 0, 0, 3, 0) == telemetry_test_sender(
            session, unstructured_test_data, {"auto_mode": False, "logs": False, "events": True}
        )
        # sending all data from a given (custom structure) view as bizevents
        assert (3, 0, 0, 0, 3) == telemetry_test_sender(
            session, unstructured_test_data, {"auto_mode": False, "logs": False, "bizevents": True}
        )
        # sending all data from a given (custom structure) view as logs, events, and bizevents
        assert (3, 3, 0, 3, 3) == telemetry_test_sender(
            session, unstructured_test_data, {"auto_mode": False, "logs": True, "events": True, "bizevents": True}
        )
        # sending single data point from a given (custom structure) view as logs, events, and bizevents
        assert (1, 1, 0, 1, 1) == telemetry_test_sender(
            session, unstructured_test_data[0], {"auto_mode": False, "logs": True, "events": True, "bizevents": True}
        )
        # sending single data point from a given (custom structure) with datetime objects view as logs, events, and bizevents
        assert (1, 1, 0, 1, 1) == telemetry_test_sender(
            session,
            unstructured_test_data[0] | {"observed_at": get_now_timestamp()},
            {"auto_mode": False, "logs": True, "events": True, "bizevents": True},
        )
