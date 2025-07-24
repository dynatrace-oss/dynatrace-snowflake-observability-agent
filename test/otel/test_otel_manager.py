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
