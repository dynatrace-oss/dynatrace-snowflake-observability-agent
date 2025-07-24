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

import pytest
from dtagent.otel.otel_manager import OtelManager
from test._utils import LocalTelemetrySender, read_clean_json_from_file
from test import _get_session
import os

ENV_VAR_NAME = "DTAGENT_TOKEN"


class TestOtelManager:

    def test_otel_manager_throw_exception(self):
        original_env_var = os.environ.get(ENV_VAR_NAME)
        os.environ[ENV_VAR_NAME] = "invalid_token"

        try:
            max_fails_allowed = 5
            structured_test_data = read_clean_json_from_file("test/test_data/telemetry_structured.json")

            session = _get_session()
            sender = LocalTelemetrySender(session, {"auto_mode": False, "logs": False, "events": True, "bizevents": True, "metrics": True})
            OtelManager.set_max_fail_count(max_fails_allowed)

            with pytest.raises(RuntimeError, match="Too many failed attempts to send data to Dynatrace, aborting run."):
                i = 0
                while i < max_fails_allowed or max_fails_allowed <= OtelManager.get_current_fail_count():
                    sender.send_data(structured_test_data[0])
                    sender._flush_logs()
                    i += 1
                sender.teardown()
                assert max_fails_allowed <= OtelManager.get_current_fail_count()
                OtelManager.verify_communication()
        finally:
            if original_env_var:
                os.environ[ENV_VAR_NAME] = original_env_var
