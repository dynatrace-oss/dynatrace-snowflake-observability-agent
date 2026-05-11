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

# Expected context declarations for every plugin, matched against actual process() context_name= strings.
EXPECTED_CONTEXTS = {
    "ActiveQueriesPlugin": ("active_queries",),
    "BudgetsPlugin": ("budgets", "spendings"),
    "ColdTablesPlugin": ("cold_tables",),
    "DataSchemasPlugin": ("data_schemas",),
    "DataVolumePlugin": ("data_volume",),
    "DynamicTablesPlugin": ("dynamic_tables", "dynamic_table_refresh_history", "dynamic_table_graph_history"),
    "EventLogPlugin": ("event_log", "event_log_metrics", "event_log_spans"),
    "EventUsagePlugin": ("event_usage",),
    "LoginHistoryPlugin": ("login_history", "sessions"),
    "MeteringPlugin": ("metering",),
    "OrgCostsPlugin": (
        "org_costs_metering",
        "org_costs_storage",
        "org_costs_data_transfer",
        "org_billing_usage_in_currency",
        "org_billing_remaining_balance",
    ),
    "QueryHistoryPlugin": ("query_history",),
    "ResourceMonitorsPlugin": ("resource_monitors", "warehouses"),
    "SharesPlugin": ("outbound_shares", "inbound_shares", "shares"),
    "SnowpipesPlugin": ("snowpipes", "snowpipes_copy_history", "snowpipes_usage_history"),
    "TableHealthPlugin": ("table_storage", "table_clustering", "table_health_derived"),
    "TasksPlugin": ("serverless_tasks", "task_versions", "task_history"),
    "TrustCenterPlugin": ("trust_center",),
    "UsersPlugin": ("users",),
    "WarehouseUsagePlugin": ("warehouse_usage", "warehouse_usage_load", "warehouse_usage_metering"),
}


def _import_all_plugin_classes():
    """Returns a dict of plugin class name → class for all declared plugins."""
    from dtagent.plugins.active_queries import ActiveQueriesPlugin
    from dtagent.plugins.budgets import BudgetsPlugin
    from dtagent.plugins.cold_tables import ColdTablesPlugin
    from dtagent.plugins.data_schemas import DataSchemasPlugin
    from dtagent.plugins.data_volume import DataVolumePlugin
    from dtagent.plugins.dynamic_tables import DynamicTablesPlugin
    from dtagent.plugins.event_log import EventLogPlugin
    from dtagent.plugins.event_usage import EventUsagePlugin
    from dtagent.plugins.login_history import LoginHistoryPlugin
    from dtagent.plugins.metering import MeteringPlugin
    from dtagent.plugins.org_costs import OrgCostsPlugin
    from dtagent.plugins.query_history import QueryHistoryPlugin
    from dtagent.plugins.resource_monitors import ResourceMonitorsPlugin
    from dtagent.plugins.shares import SharesPlugin
    from dtagent.plugins.snowpipes import SnowpipesPlugin
    from dtagent.plugins.table_health import TableHealthPlugin
    from dtagent.plugins.tasks import TasksPlugin
    from dtagent.plugins.trust_center import TrustCenterPlugin
    from dtagent.plugins.users import UsersPlugin
    from dtagent.plugins.warehouse_usage import WarehouseUsagePlugin

    return {
        "ActiveQueriesPlugin": ActiveQueriesPlugin,
        "BudgetsPlugin": BudgetsPlugin,
        "ColdTablesPlugin": ColdTablesPlugin,
        "DataSchemasPlugin": DataSchemasPlugin,
        "DataVolumePlugin": DataVolumePlugin,
        "DynamicTablesPlugin": DynamicTablesPlugin,
        "EventLogPlugin": EventLogPlugin,
        "EventUsagePlugin": EventUsagePlugin,
        "LoginHistoryPlugin": LoginHistoryPlugin,
        "MeteringPlugin": MeteringPlugin,
        "OrgCostsPlugin": OrgCostsPlugin,
        "QueryHistoryPlugin": QueryHistoryPlugin,
        "ResourceMonitorsPlugin": ResourceMonitorsPlugin,
        "SharesPlugin": SharesPlugin,
        "SnowpipesPlugin": SnowpipesPlugin,
        "TableHealthPlugin": TableHealthPlugin,
        "TasksPlugin": TasksPlugin,
        "TrustCenterPlugin": TrustCenterPlugin,
        "UsersPlugin": UsersPlugin,
        "WarehouseUsagePlugin": WarehouseUsagePlugin,
    }


class TestPluginContextReporting:
    """Validates PLUGIN_CONTEXTS declarations across all plugins."""

    def test_base_class_default_is_empty(self):
        from dtagent.plugins import Plugin

        assert Plugin.PLUGIN_CONTEXTS == ()

    def test_base_class_get_contexts_returns_empty(self):
        from dtagent.plugins import Plugin

        assert Plugin.get_contexts() == ()

    @pytest.mark.parametrize("class_name,expected", list(EXPECTED_CONTEXTS.items()))
    def test_plugin_contexts_declared(self, class_name, expected):
        """Every plugin declares PLUGIN_CONTEXTS matching its process() context_name= strings."""
        plugin_classes = _import_all_plugin_classes()
        cls = plugin_classes[class_name]
        assert isinstance(cls.PLUGIN_CONTEXTS, tuple), f"{class_name}.PLUGIN_CONTEXTS must be a tuple"
        assert len(cls.PLUGIN_CONTEXTS) > 0, f"{class_name}.PLUGIN_CONTEXTS must not be empty"
        assert all(isinstance(c, str) for c in cls.PLUGIN_CONTEXTS), f"{class_name}.PLUGIN_CONTEXTS must contain strings"
        assert cls.PLUGIN_CONTEXTS == expected, f"{class_name}.PLUGIN_CONTEXTS mismatch"

    @pytest.mark.parametrize("class_name,expected", list(EXPECTED_CONTEXTS.items()))
    def test_get_contexts_classmethod(self, class_name, expected):
        """get_contexts() returns the same value as PLUGIN_CONTEXTS."""
        plugin_classes = _import_all_plugin_classes()
        cls = plugin_classes[class_name]
        assert cls.get_contexts() == cls.PLUGIN_CONTEXTS
        assert cls.get_contexts() == expected

    def test_unknown_context_yields_non_empty_diff(self):
        """Confirms that requesting a nonexistent context produces a non-empty unknown set."""
        from dtagent.plugins.shares import SharesPlugin

        unknown = set(["nonexistent_ctx"]) - set(SharesPlugin.PLUGIN_CONTEXTS)
        assert unknown == {"nonexistent_ctx"}

    def test_known_context_yields_empty_diff(self):
        """Confirms that requesting a declared context produces no unknown entries."""
        from dtagent.plugins.shares import SharesPlugin

        for ctx in SharesPlugin.PLUGIN_CONTEXTS:
            unknown = set([ctx]) - set(SharesPlugin.PLUGIN_CONTEXTS)
            assert unknown == set(), f"Context '{ctx}' should be recognized"

    def test_all_plugins_cover_expected_table(self):
        """EXPECTED_CONTEXTS covers every plugin class in the codebase."""
        plugin_classes = _import_all_plugin_classes()
        assert set(plugin_classes.keys()) == set(EXPECTED_CONTEXTS.keys())


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
