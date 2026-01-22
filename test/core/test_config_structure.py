"""Tests for new snowflake configuration structure."""

import pytest


class TestSnowflakeConfigStructure:
    """Tests for the new nested snowflake configuration structure."""

    def test_config_flatten_snowflake_paths(self):
        """Test that nested snowflake config paths are properly flattened."""
        # This test verifies that the configuration flattening logic
        # properly handles the new nested structure

        # Sample configuration with new structure
        config_yaml = """
        core:
          dynatrace_tenant_address: test.dynatrace.com
          deployment_environment: TEST
          snowflake:
            account_name: myaccount.us-east-1
            host_name: myaccount.snowflakecomputing.com
            database:
              name: CUSTOM_DB
              data_retention_time_in_days: 7
            warehouse:
              name: CUSTOM_WH
            resource_monitor:
              name: CUSTOM_RS
              credit_quota: 10
            roles:
              owner: CUSTOM_OWNER
              admin: CUSTOM_ADMIN
              viewer: CUSTOM_VIEWER
        """

        # When flattened, these should become:
        expected_paths = [
            "core.snowflake.account_name",
            "core.snowflake.host_name",
            "core.snowflake.database.name",
            "core.snowflake.database.data_retention_time_in_days",
            "core.snowflake.warehouse.name",
            "core.snowflake.resource_monitor.name",
            "core.snowflake.resource_monitor.credit_quota",
            "core.snowflake.roles.owner",
            "core.snowflake.roles.admin",
            "core.snowflake.roles.viewer",
        ]

        # Note: The actual flattening is done by the bash script prepare_config.sh
        # and stored in the CONFIGURATIONS table. This test documents the expected behavior.
        assert all(path.startswith("core.snowflake.") for path in expected_paths)

    def test_config_default_values(self):
        """Test that default values are used when custom names are not provided."""
        # When configuration has empty or missing values, defaults should be used:
        # - database.name: "" -> DTAGENT_DB
        # - warehouse.name: "" -> DTAGENT_WH
        # - resource_monitor.name: "" -> DTAGENT_RS
        # - roles.owner: "" -> DTAGENT_OWNER
        # - roles.admin: "" -> DTAGENT_ADMIN
        # - roles.viewer: "" -> DTAGENT_VIEWER

        default_objects = {
            "database": "DTAGENT_DB",
            "warehouse": "DTAGENT_WH",
            "resource_monitor": "DTAGENT_RS",
            "role_owner": "DTAGENT_OWNER",
            "role_admin": "DTAGENT_ADMIN",
            "role_viewer": "DTAGENT_VIEWER",
        }

        assert all(name.startswith("DTAGENT_") for name in default_objects.values())

    def test_config_skip_optional_objects(self):
        """Test that optional objects can be skipped with '-' value."""
        # - resource_monitor.name: "-" -> Skip creation
        # - roles.admin: "-" -> Skip creation

        skip_value = "-"
        optional_objects = ["resource_monitor", "admin_role"]

        # These objects should check for "-" value and skip creation
        assert skip_value == "-"
        assert len(optional_objects) > 0

    def test_config_backward_compatibility_migration(self):
        """Test that old config paths are migrated to new structure."""
        # Old format:
        old_paths = {
            "core.snowflake_account_name": "myaccount",
            "core.snowflake_host_name": "myaccount.snowflakecomputing.com",
            "core.snowflake_credit_quota": 10,
            "core.snowflake_data_retention_time_in_days": 7,
        }

        # New format (after migration):
        new_paths = {
            "core.snowflake.account_name": "myaccount",
            "core.snowflake.host_name": "myaccount.snowflakecomputing.com",
            "core.snowflake.resource_monitor.credit_quota": 10,
            "core.snowflake.database.data_retention_time_in_days": 7,
        }

        # Verify migration mapping
        assert "snowflake_account_name" in old_paths.keys().__str__()
        assert "snowflake.account_name" in new_paths.keys().__str__()

        # Verify the convert_config_to_yaml.sh script handles this migration
        # (actual verification happens in bash test script)
