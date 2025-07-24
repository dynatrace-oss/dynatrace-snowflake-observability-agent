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
class TestDataVol:
    def test_data_vol(self):
        from typing import Dict, Generator
        from dtagent.plugins.data_volume import DataVolumePlugin
        from test import _get_session, TestDynatraceSnowAgent
        import test._utils as utils

        PICKLE_NAME = "test/test_data/data_volume.pkl"
        T_DATA = "APP.V_DATA_VOLUME"
        # ======================================================================

        if utils.should_pickle([PICKLE_NAME]):
            utils._pickle_data_history(_get_session(), T_DATA, PICKLE_NAME)

        class TestDataVolumePlugin(DataVolumePlugin):

            def _get_table_rows(self, table_name: str = None) -> Generator[Dict, None, None]:
                return utils._get_unpickled_entries(PICKLE_NAME, limit=2)

        def __local_get_plugin_class(source: str):
            return TestDataVolumePlugin

        from dtagent import plugins

        plugins._get_plugin_class = __local_get_plugin_class

        # ======================================================================
        import logging

        session = _get_session()
        utils._logging_findings(session, TestDynatraceSnowAgent(session), "test_data_volume", logging.INFO, show_detailed_logs=0)


if __name__ == "__main__":
    test_class = TestDataVol()
    test_class.test_data_vol()
