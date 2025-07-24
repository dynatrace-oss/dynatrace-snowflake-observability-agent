"""File contatning Configuration class and methods"""

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

    def __init__(self, session: snowpark.Session) -> Dict:
        """
        Returns configuration based on data in config_data.configuration and (currently) hardcoded list of instruments

        {
            'dt.token': YOUR_TOKEN,
            'otlp.http':    'https://DYNATRACE_TENANT_ADDRESS/api/v2/otlp',
            'metrics.http': 'https://DYNATRACE_TENANT_ADDRESS/api/v2/metrics/ingest',
            'events.http': 'https://DYNATRACE_TENANT_ADDRESS/api/v2/events/ingest',
            'bizevents.http': 'https://DYNATRACE_TENANT_ADDRESS/api/v2/bizevents/ingest',
            'resource.attributes': {
                'telemetry.exporter.version': '0.5.123341324',
                'deployment.environment': 'TEST',
                'host.name': 'YOUR_SNOWFLAKE_ACCOUNT.YOUR_AWS_REGION.snowflakecomputing.com',
                'telemetry.exporter.name': 'dynatrace.snowagent',
                'deployment.environment.tag': 'SA080',
            },
            'instruments': {
                'metrics': {
                    'snowflake.data.scanned_from_cache': {
                        'description': 'The percentage of data scanned from the local disk cache. The value ranges from 0.0 to 1.0. Multiply by 100 to get a true percentage.',
                        'unit': 'percent'
                    },
                    ....
                    'snowflake.credits.cloud_services': {
                        'description': 'Number of credits used for cloud services.'
                    },
                    ...
                },
                'dimesion_sets': {
                    'set1': [], ...
                }
            }
        }
        """

        def __rewrite_with_types(config_df: dict) -> dict:
            """
            This function rewrites the pandas dataframe with config to a dict type and assigns desired types to fields.
            List format in configuration table should be as follows to work properly:
                List values must start with `[` and end with `]`, all fields must be seperated with `, `. Values within the list should be enclosed in double quotes (").
                All items within the list must be the same type.
            Args:
                config_df (dict) - pandas dataframe with configuration table contents
            Returns:
                processed_dict (dict) - dictionary with refromatted field types
            """
            import builtins

            __df_unpack = {"int": builtins.int, "list": json.loads, "str": json.loads, "bool": json.loads}

            processed_dict = {row["PATH"]: __df_unpack.get(row["TYPE"], str)(row["VALUE"]) for idx, row in config_df.iterrows()}

            return processed_dict

        def __unpack_prefixed_keys(config: dict, prefix: Optional[str] = None) -> dict:
            """Traverses key path (dot separated) to unpack flat dict into a dictionary where only numbers, strings, or lists are in the values-leaves

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
        from dtagent.util import _get_service_name  # COMPILE_REMOVE

        default_config = {
            "core.dynatrace_tenant_address": "",
            "core.deployment_environment": "TEST",
            "core.snowflake_host_name": "",
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

        instruments_table = "CONFIG.V_INSTRUMENTS"
        instruments_row = session.table(instruments_table).take(None)  # should take the first row or none
        instruments_dict = (
            json.loads(instruments_row[0])
            if instruments_row
            else {"dimensions": {}, "attributes": {}, "event_timestamps": {}, "metrics": {}}
        )

        self._config = {
            "dt.token": os.environ.get("DTAGENT_TOKEN", _snowflake.get_generic_secret_string("dtagent_token")),
            "otlp.http": f"https://{config_dict['core.dynatrace_tenant_address']}/api/v2/otlp",
            "metrics.http": f"https://{config_dict['core.dynatrace_tenant_address']}/api/v2/metrics/ingest",
            "events.http": f"https://{config_dict['core.dynatrace_tenant_address']}/api/v2/events/ingest",
            "bizevents.http": f"https://{config_dict['core.dynatrace_tenant_address']}/api/v2/bizevents/ingest",
            "resource.attributes": {
                "db.system": "snowflake",
                "service.name": _get_service_name(config_dict),
                "deployment.environment": config_dict["core.deployment_environment"],
                "host.name": config_dict["core.snowflake_host_name"],
                "telemetry.exporter.version": f"{VERSION}.{BUILD}",
                "telemetry.exporter.name": "dynatrace.snowagent",
            },
            "otel": __unpack_prefixed_keys(config_dict, "otel."),
            "plugins": __unpack_prefixed_keys(config_dict, "plugins."),
            "instruments": instruments_dict,
        }
        if config_dict.get("core.tag"):
            self._config["resource.attributes"]["deployment.environment.tag"] = config_dict["core.tag"]
        os.environ["OTEL_EXPORTER_OTLP_METRICS_TEMPORALITY_PREFERENCE"] = "delta"

    def get(
        self,
        key: str,
        *,
        context: Optional[str] = None,
        plugin_name: Optional[str] = None,
        otel_module: Optional[str] = None,
        default_value: Optional[Any] = None,
    ) -> any:
        """Returns configuraiton value for the given key in either given context or for the given plugin name

        Args:
            key (str): Configuration key for which to return value
            context (str, optional): First level key under which a dict is kept as a value. Defaults to None.
            plugin_name (str, optional): Name of the key under the "plugins" key in configs; dictionary is expected under that plugin name. Defaults to None.

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
        """
        Checks STATUS.PROCESSED_MEASUREMENTS_LOG to get last update for the given source
        """
        from dtagent.util import _get_timestamp_in_sec  # COMPILE_REMOVE

        last_ts = session.sql(f"select APP.F_LAST_PROCESSED_TS('{source}');").collect()[0][0]

        if last_ts:
            import pytz

            return last_ts.replace(tzinfo=pytz.UTC)

        return _get_timestamp_in_sec()


##endregion
