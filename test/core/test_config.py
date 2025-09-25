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

import glob
import os
import json


class TestConfig:

    def test_config_load(self):
        from build import prepare_config

        d_config = prepare_config._get_config("./conf/config-template.json")

        assert d_config is not None, "Could not load config"
        assert "CORE" in d_config, "There is no CORE key defined"
        assert "OTEL" in d_config, "There is no OTEL key defined"
        assert "PLUGINS" in d_config, "There is no PLUGINS key defined"
        assert "DYNATRACE_TENANT_ADDRESS" in d_config["CORE"], "There is no core.DYNATRACE_TENANT_ADDRESS present"

    def test_prepare_config_for_ingest(self):

        from build import prepare_config

        d_config = prepare_config._get_config("./test/conf/config-default.json")
        assert d_config is not None, "Could not load config"

        l_config = prepare_config._prepare_config_for_ingest(d_config)

        assert len(l_config) > 0, "We were expecting some data here"

        m_config = {item["PATH"]: item for item in l_config}

        assert "core.dynatrace_tenant_address" in m_config, "<core.dynatrace_tenant_address> key is missing"
        assert "otel.spans.export_timeout_millis" in m_config, "<otel.spans.export_timeout_millis> key is missing"

        assert (
            m_config["core.dynatrace_tenant_address"]["PATH"] == "core.dynatrace_tenant_address"
            and m_config["core.dynatrace_tenant_address"]["VALUE"] == "abc12345.live.dynatrace.com"
            and m_config["core.dynatrace_tenant_address"]["TYPE"] == "str"
        )
        assert (
            m_config["otel.spans.export_timeout_millis"]["PATH"] == "otel.spans.export_timeout_millis"
            and m_config["otel.spans.export_timeout_millis"]["VALUE"] == 10000
            and m_config["otel.spans.export_timeout_millis"]["TYPE"] == "int"
        )

    def test_merge_json_files(self):
        from build import prepare_config

        custom_config_file = "./test/conf/config-merge-test.json"

        if os.path.isfile(custom_config_file):

            l_config = prepare_config._merge_json_files("./conf/config-template.json", custom_config_file)

            assert len(l_config) > 0, "We were expecting some data here"

            m_config = {item["PATH"]: item for item in l_config}

            assert "core.dynatrace_tenant_address" in m_config, "<core.dynatrace_tenant_address> key is missing"
            assert "otel.spans.export_timeout_millis" in m_config, "<otel.spans.export_timeout_millis> key is missing"
            assert "plugins.data_volume.schedule" in m_config, "<plugins.data_volume.schedule> key is missing"

            assert (
                m_config["core.dynatrace_tenant_address"]["PATH"] == "core.dynatrace_tenant_address"
                and m_config["core.dynatrace_tenant_address"]["VALUE"] != "dynatrace.com"
                and m_config["core.dynatrace_tenant_address"]["TYPE"] == "str"
            )
            assert (
                m_config["core.snowflake_account_name"]["PATH"] == "core.snowflake_account_name"
                and m_config["core.snowflake_account_name"]["VALUE"] != "-"
                and m_config["core.snowflake_account_name"]["TYPE"] == "str"
            )
            assert (
                m_config["otel.spans.export_timeout_millis"]["PATH"] == "otel.spans.export_timeout_millis"
                and m_config["otel.spans.export_timeout_millis"]["VALUE"] != 10000
                and m_config["otel.spans.export_timeout_millis"]["TYPE"] == "int"
            )
            assert (
                m_config["plugins.data_volume.schedule"]["PATH"] == "plugins.data_volume.schedule"
                and m_config["plugins.data_volume.schedule"]["VALUE"] == "USING CRON 30 */4 * * * UTC"
                and m_config["plugins.data_volume.schedule"]["TYPE"] == "str"
            )
        else:
            print(f"!!! WARNING: {custom_config_file} does not exist. Define alternative config file.")

    def test_plugin_conf(self):

        d_config_extra_keys = {
            "BUDGETS": ["QUOTA"],
            "DATA_VOLUME": ["INCLUDE", "EXCLUDE"],
            "DYNAMIC_TABLES": ["INCLUDE", "EXCLUDE"],
            "EVENT_LOG": ["MAX_ENTRIES", "RETENTION_HOURS"],
            "QUERY_HISTORY": ["SLOW_QUERIES_THRESHOLD", "SLOW_QUERIES_TO_ANALYZE_LIMIT"],
        }

        for directory in glob.glob("src/dtagent/plugins/*.config"):
            if any(os.scandir(directory)):  # exclude empty dirs
                plugin = os.path.basename(directory).split(".")[0]
                full_path = f"{directory}/{plugin}-config.json"

                assert os.path.isfile(full_path), f"Configuration file {full_path} is missing"

                assert os.path.getsize(full_path), f"Configuration file {full_path} seems to be empty"

                with open(full_path, "r", encoding="utf-8") as conf_file:
                    d_conf = json.load(conf_file)

                plugin_key = plugin.upper()

                assert "PLUGINS" in d_conf, "Plugins key is missing from the configuratio"

                assert plugin_key in d_conf["PLUGINS"], f"{plugin} key is missing from the configuration"

                assert "SCHEDULE" in d_conf["PLUGINS"][plugin_key], f"Schedule is missing from the {plugin} config"

                assert "IS_DISABLED" in d_conf["PLUGINS"][plugin_key], f"is_disabled key is missing from the {plugin_key} config"

                for key in d_config_extra_keys.get(plugin_key, []):
                    assert key in d_conf["PLUGINS"][plugin_key], f"{key} is missing from {plugin} config"

    def test_init(self, pickle_conf: str):
        from test._utils import get_config

        c = get_config(pickle_conf)

        assert c.get("logs.http") is not None
        assert c.get("spans.http") is not None
        assert isinstance(c.get(otel_module="spans", key="export_timeout_millis"), int)
        assert isinstance(c.get(otel_module="spans", key="max_export_batch_size"), int)
        assert c.get("resource.attributes").get("telemetry.exporter.name") == "dynatrace.snowagent"
