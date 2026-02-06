"""File with Configuration class and methods"""

##region ------------------------------ IMPORTS  -----------------------------------------
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
import json
import logging
from typing import Any, Dict, Optional
from snowflake import snowpark
from dtagent.version import VERSION, BUILD

##endregion COMPILE_REMOVE

##region --------------------------- CONFIG FUNCTIONS ------------------------------------


class Configuration:
    """Class initializing Configuration from Snowflake config.configurations table"""

    RESOURCE_ATTRIBUTES = {
        "db.system": "snowflake",
        "service.name": "",
        "deployment.environment": "",
        "host.name": "",
        "telemetry.exporter.version": f"{VERSION}.{BUILD}",
        "telemetry.exporter.name": "dynatrace.snowagent",
    }

    def __init__(self, session: snowpark.Session) -> Dict:
        """Returns configuration based on data in config_data.configuration
        {
            'dt.token': YOUR_TOKEN,
            'logs.http':    'https://DYNATRACE_TENANT_ADDRESS/api/v2/otlp/v1/logs',
            'spans.http':    'https://DYNATRACE_TENANT_ADDRESS/api/v2/otlp/v1/traces',
            'metrics.http': 'https://DYNATRACE_TENANT_ADDRESS/api/v2/metrics/ingest',
            'events.http': 'https://DYNATRACE_TENANT_ADDRESS/api/v2/events/ingest',
            'bizevents.http': 'https://DYNATRACE_TENANT_ADDRESS/api/v2/bizevents/ingest',
            'resource.attributes': {
                'telemetry.exporter.version': '0.5.123341324',
                'deployment.environment': 'TEST',
                'host.name': 'YOUR_SNOWFLAKE_ACCOUNT.YOUR_AWS_REGION.snowflakecomputing.com',
                'telemetry.exporter.name': 'dynatrace.snowagent',
                'deployment.environment.tag': 'SA080',
            }
        }
        """
        from dtagent.otel.metrics import Metrics  # COMPILE_REMOVE
        from dtagent.otel.events.generic import GenericEvents  # COMPILE_REMOVE
        from dtagent.otel.events.davis import DavisEvents  # COMPILE_REMOVE
        from dtagent.otel.events.bizevents import BizEvents  # COMPILE_REMOVE
        from dtagent.otel.logs import Logs  # COMPILE_REMOVE
        from dtagent.otel.spans import Spans  # COMPILE_REMOVE

        def __rewrite_with_types(config_df: dict) -> dict:
            """This function rewrites the pandas dataframe with config to a dict type and assigns desired types to fields.

            List format in configuration table should be as follows to work properly:
                List values must start with `[` and end with `]`, all fields must be separated with `, `.
                Values within the list should be enclosed in double quotes (").
                All items within the list must be the same type.

            Args:
                config_df (dict) - pandas dataframe with configuration table contents

            Returns:
                processed_dict (dict) - dictionary with reformatted field types
            """
            import builtins

            __df_unpack = {"int": builtins.int, "list": json.loads, "str": json.loads, "bool": json.loads}

            processed_dict = {row["PATH"]: __df_unpack.get(row["TYPE"], str)(row["VALUE"]) for idx, row in config_df.iterrows()}

            return processed_dict

        def __unpack_prefixed_keys(config: dict, prefix: Optional[str] = None) -> dict:
            """Traverses key path (dot separated) to unpack flat dict into a dictionary where only numbers, strings, or
            lists are in the values-leaves.

            Args:
                config (dict): Dictionary to unpack
                prefix (str, optional): Prefix by which to filter keys to be unpacked. Defaults to None.

            Returns:
                dict: Dictionary unpacked into a full structure
            """
            result = {}
            for key, value in config.items():
                if prefix is None or key.startswith(prefix):
                    no_prefix_key = key if prefix is None else key.replace(prefix, "")
                    key_parts = no_prefix_key.split(".")
                    current_level = result
                    for part in key_parts[:-1]:
                        if part not in current_level:
                            current_level[part] = {}
                        current_level = current_level[part]
                    current_level[key_parts[-1]] = value
            return result

        import _snowflake
        import os
        from dtagent.util import _get_snowflake_account_info  # COMPILE_REMOVE

        default_config = {
            "core.dynatrace_tenant_address": "",
            "core.deployment_environment": "TEST",
            "core.snowflake.account_name": "",
            "core.snowflake.host_name": "",
            "core.log_level": "WARN",
        }
        config_table = "CONFIG.CONFIGURATIONS"

        config_df = session.table(config_table).to_pandas()
        processed_conf = __rewrite_with_types(config_df)

        config_dict = {**default_config, **processed_conf} if processed_conf else default_config

        default_log_level = getattr(logging, config_dict["core.log_level"], logging.WARN)
        if default_log_level != logging.WARN:
            from dtagent import LOG  # COMPILE_REMOVE

            LOG.debug(f"Setting log level to {default_log_level} from config.LOG_LEVEL={config_dict['core.log_level']}")
            LOG.setLevel(default_log_level)

        # Derive account_name and host_name if not provided
        service_name, host_name = _get_snowflake_account_info(config_dict, session)

        self._config = {
            "dt.token": os.environ.get("DTAGENT_TOKEN", _snowflake.get_generic_secret_string("dtagent_token")),
            "logs.http": f"https://{config_dict['core.dynatrace_tenant_address']}{Logs.ENDPOINT_PATH}",
            "spans.http": f"https://{config_dict['core.dynatrace_tenant_address']}{Spans.ENDPOINT_PATH}",
            "metrics.http": f"https://{config_dict['core.dynatrace_tenant_address']}{Metrics.ENDPOINT_PATH}",
            "events.http": f"https://{config_dict['core.dynatrace_tenant_address']}{GenericEvents.ENDPOINT_PATH}",
            "davis_events.http": f"https://{config_dict['core.dynatrace_tenant_address']}{DavisEvents.ENDPOINT_PATH}",
            "biz_events.http": f"https://{config_dict['core.dynatrace_tenant_address']}{BizEvents.ENDPOINT_PATH}",
            "resource.attributes": Configuration.RESOURCE_ATTRIBUTES
            | {
                "service.name": service_name,
                "deployment.environment": config_dict["core.deployment_environment"],
                "host.name": host_name,
            },
            "otel": __unpack_prefixed_keys(config_dict, "otel."),
            "plugins": __unpack_prefixed_keys(config_dict, "plugins."),
        }
        self._multitenancy_tag = config_dict.get("core.tag")
        if self._multitenancy_tag:
            self._config["resource.attributes"]["deployment.environment.tag"] = self._multitenancy_tag
        os.environ["OTEL_EXPORTER_OTLP_METRICS_TEMPORALITY_PREFERENCE"] = "delta"

    @property
    def multitenancy_tag(self) -> Optional[str]:
        """Returns the multitenancy TAG if configured, None otherwise"""
        return self._multitenancy_tag

    def get(
        self,
        key: str,
        *,
        context: Optional[str] = None,
        plugin_name: Optional[str] = None,
        otel_module: Optional[str] = None,
        default_value: Optional[Any] = None,
    ) -> any:
        """Returns configuration value for the given key in either given context or for the given plugin name

        Args:
            key (str):                   Configuration key for which to return value
            context (str, optional):     First level key under which a dict is kept as a value. Defaults to None.
            plugin_name (str, optional): Name of the key under the "plugins" key in configs; dictionary is expected under that plugin name.
                                         Defaults to None.

        Returns:
            any: Value for the given configuration key in given context or plugin.
            * for key="resource.attributes" - the whole dict is returned
            * for key="export_timeout_millis" + context="otel" - the actual value is returned
            * for key="frequency" + plugin_name="data_volume" - also the actual value is returned
            * for key="data_volume" + context="plugins" - the whole dict with configuration for data_volume plugin is returned
        """
        key = key.lower()
        return_key: Optional[Any] = None
        if context is not None:
            return_key = self._config.get(context, {}).get(key, default_value)
        elif plugin_name is not None:
            return_key = self._config.get("plugins", {}).get(plugin_name, {}).get(key, default_value)
        elif otel_module is not None:
            return_key = self._config.get("otel", {}).get(otel_module, {}).get(key, default_value)
        else:
            return_key = self._config.get(key, default_value)
        return return_key

    def get_last_measurement_update(self, session: snowpark.Session, source: str):
        """Checks STATUS.PROCESSED_MEASUREMENTS_LOG to get last update for the given source"""
        from dtagent.util import _get_timestamp_in_sec  # COMPILE_REMOVE

        last_ts = session.sql(f"select STATUS.F_LAST_PROCESSED_TS('{source}');").collect()[0][0]

        if last_ts:
            import pytz

            return last_ts.replace(tzinfo=pytz.UTC)

        return _get_timestamp_in_sec()


##endregion
