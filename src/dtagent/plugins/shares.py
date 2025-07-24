"""
Plugin file for processing shares plugin data.
"""

##region ------------------------------ IMPORTS  -----------------------------------------
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

import uuid
from typing import Tuple
from dtagent.plugins import Plugin

##endregion COMPILE_REMOVE

##region ------------------ MEASUREMENT SOURCE: SHARES --------------------------------


class SharesPlugin(Plugin):
    """
    Shares plugin class.
    """

    def process(self, run_proc: bool = True) -> Tuple[int, int]:
        """
        Processes data for shares plugin.
        Returns
            outbound_share_entries [int]: number of entries reported from APP.V_OUTBOUND_SHARE_TABLES,
            inbound_share_entries [int]: number of entries reported from APP.V_INBOUND_SHARE_TABLES.
            share_events [int]: number of timestamp events for shares from APP.V_SHARE_EVENTS
        """

        t_outbound_shares = "APP.V_OUTBOUND_SHARE_TABLES"
        t_inbound_shares = "APP.V_INBOUND_SHARE_TABLES"
        t_share_events = "APP.V_SHARE_EVENTS"
        run_id = str(uuid.uuid4().hex)

        if run_proc:
            # call to list inbound and outbound shares to temporary tables
            self._session.call("APP.P_GET_SHARES", log_on_exception=True)

        outbound_share_entries = self._log_entries(
            f_entry_generator=lambda: self._get_table_rows(t_outbound_shares),
            context_name="outbound_shares",
            run_uuid=run_id,
            log_completion=run_proc,
        )[0]

        inbound_share_entries = self._log_entries(
            f_entry_generator=lambda: self._get_table_rows(t_inbound_shares),
            context_name="inbound_shares",
            run_uuid=run_id,
            log_completion=run_proc,
        )[0]

        share_events = self._log_entries(
            f_entry_generator=lambda: self._get_table_rows(t_share_events),
            context_name="shares",
            run_uuid=run_id,
            log_completion=run_proc,
            report_logs=False,
            report_metrics=False,
            report_timestamp_events=True,
        )[-1]

        return outbound_share_entries, inbound_share_entries, share_events
