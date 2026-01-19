#!/usr/bin/env bats

setup() {
    cd "$BATS_TEST_DIRNAME/../.."
    # Create minimal test config
    TEST_CONFIG_FILE=$(mktemp)
    cat > "$TEST_CONFIG_FILE" << 'EOF'
[
  {
    "PATH": "core.tag",
    "TYPE": "str",
    "VALUE": "TEST"
  }
]
EOF
    export BUILD_CONFIG_FILE="$TEST_CONFIG_FILE"
    TEST_SQL_FILE=$(mktemp)
    mkdir -p build/09_upgrade build/20_plugins
    echo "SELECT 1;" > build/001_test.sql
    # Create test upgrade files with different versions
    echo "-- v0.9.0 upgrade" > build/09_upgrade/v0.9.0.sql
    echo "SELECT 'upgrade 0.9.0';" >> build/09_upgrade/v0.9.0.sql
    echo "-- v0.9.3 upgrade" > build/09_upgrade/v0.9.3.sql
    echo "SELECT 'upgrade 0.9.3';" >> build/09_upgrade/v0.9.3.sql
    echo "-- v1.0.0 upgrade" > build/09_upgrade/v1.0.0.sql
    echo "SELECT 'upgrade 1.0.0';" >> build/09_upgrade/v1.0.0.sql

    # Create test files with plugin markers for testing plugin filtering
    cat > build/00_init.sql << 'EOSQL'
-- Main init code
CREATE SCHEMA IF NOT EXISTS MAIN_SCHEMA;
--%PLUGIN:test_plugin:
CREATE TABLE test_plugin_table (id INT);
--%:PLUGIN:test_plugin
--%PLUGIN:active_plugin:
CREATE TABLE active_plugin_table (id INT);
--%:PLUGIN:active_plugin
EOSQL

    cat > build/10_setup.sql << 'EOSQL'
-- Setup code
CREATE PROCEDURE main_proc() AS BEGIN SELECT 1; END;
--%PLUGIN:test_plugin:
CREATE PROCEDURE test_plugin_proc() AS BEGIN SELECT 2; END;
--%:PLUGIN:test_plugin
EOSQL

    cat > build/30_config.sql << 'EOSQL'
-- Config code
SELECT 'config';
EOSQL

    cat > build/20_plugins/test_plugin.sql << 'EOSQL'
--%PLUGIN:test_plugin:
CREATE OR REPLACE PROCEDURE test_plugin_handler()
RETURNS TABLE()
LANGUAGE PYTHON
AS
$$
def test_plugin_handler():
    return []
$$;
--%:PLUGIN:test_plugin
EOSQL

    cat > build/20_plugins/active_plugin.sql << 'EOSQL'
--%PLUGIN:active_plugin:
CREATE OR REPLACE PROCEDURE active_plugin_handler()
RETURNS TABLE()
LANGUAGE PYTHON
AS
$$
def active_plugin_handler():
    return []
$$;
--%:PLUGIN:active_plugin
EOSQL

    cat > build/70_agents.sql << 'EOSQL'
-- Agent definitions
CREATE PROCEDURE main_agent()
returns object
language python
runtime_version = '3.11'
packages = (
    'requests',
    'pandas',
    'tzlocal',
    'snowflake-snowpark-python',
    'opentelemetry-api',
    'opentelemetry-sdk',
    'opentelemetry-exporter-otlp-proto-http'
)
handler = 'main'
external_access_integrations = (DTAGENT_API_INTEGRATION)
secrets = ('dtagent_token'=DTAGENT_DB.CONFIG.DTAGENT_API_KEY)
execute as caller
as
$$
# -- language=Python
#%PLUGIN:test_plugin:
class TestPlugin(Plugin):
    PLUGIN_NAME = 'test_plugin'

    def process(self, run_id: str, run_proc: bool=True) -> Dict[str, Dict[str, int]]:
        pass
#%:PLUGIN:test_plugin
#%PLUGIN:active_plugin:
class ActivePlugin(Plugin):
    PLUGIN_NAME = 'active_plugin'

    def process(self, run_id: str, run_proc: bool=True) -> Dict[str, Dict[str, int]]:
        pass
#%:PLUGIN:active_plugin

$$
;
END;
EOSQL
}

teardown() {
    rm -f "$TEST_CONFIG_FILE" "$TEST_SQL_FILE"
    rm -f build/001_test.sql build/00_init.sql build/10_setup.sql build/30_config.sql build/70_agents.sql
    rm -rf build/09_upgrade build/20_plugins
    unset BUILD_CONFIG_FILE
}

@test "prepare_deploy_script.sh runs with manual param" {
    export DTAGENT_TOKEN="dt0c01.TEST12345678901234567890.TEST123456789012345678901234567890123456789012345678901234567890"
    run timeout 30 ./scripts/deploy/prepare_deploy_script.sh "$TEST_SQL_FILE" "test" "001_test" "" "manual"
    [ "$status" -eq 0 ]
    [ -s "$TEST_SQL_FILE" ]  # file should not be empty
    grep -q "SELECT 1" "$TEST_SQL_FILE"
}

@test "prepare_deploy_script.sh upgrade scope generates selection of upgrade code" {
    export DTAGENT_TOKEN="dt0c01.TEST12345678901234567890.TEST123456789012345678901234567890123456789012345678901234567890"
    run timeout 30 ./scripts/deploy/prepare_deploy_script.sh "$TEST_SQL_FILE" "test" "upgrade" "0.9.0" "manual"
    [ "$status" -eq 0 ]
    [ -s "$TEST_SQL_FILE" ]

    # Should include v0.9.3 and v1.0.0 (versions > 0.9.0)
    grep -q "upgrade 0.9.3" "$TEST_SQL_FILE"
    grep -q "upgrade 1.0.0" "$TEST_SQL_FILE"

    # Should NOT include v0.9.0 (version <= 0.9.0)
    ! grep -q "upgrade 0.9.0" "$TEST_SQL_FILE"
}

@test "prepare_deploy_script.sh upgrade scope fails without from-version" {
    export DTAGENT_TOKEN="dt0c01.TEST12345678901234567890.TEST123456789012345678901234567890123456789012345678901234567890"
    run timeout 30 ./scripts/deploy/prepare_deploy_script.sh "$TEST_SQL_FILE" "test" "upgrade" "" "manual"
    [ "$status" -ne 0 ]
    [[ "$output" =~ "ERROR: --from-version required for upgrade scope" ]]
}

@test "prepare_deploy_script.sh removes inactive plugins from init scope" {
    # Create config with test_plugin disabled
    cat > "$TEST_CONFIG_FILE" << 'EOF'
[
  {
    "PATH": "core.tag",
    "TYPE": "str",
    "VALUE": "TEST"
  },
  {
    "PATH": "plugins.deploy_disabled_plugins",
    "TYPE": "bool",
    "VALUE": false
  },
  {
    "PATH": "plugins.test_plugin.is_disabled",
    "TYPE": "bool",
    "VALUE": true
  }
]
EOF
    export BUILD_CONFIG_FILE="$TEST_CONFIG_FILE"
    export DTAGENT_TOKEN="dt0c01.TEST12345678901234567890.TEST123456789012345678901234567890123456789012345678901234567890"

    run timeout 30 ./scripts/deploy/prepare_deploy_script.sh "$TEST_SQL_FILE" "test" "init" "" "manual"
    [ "$status" -eq 0 ]

    # Should include main init code and active_plugin
    grep -q "MAIN_SCHEMA" "$TEST_SQL_FILE"
    grep -q "active_plugin_table" "$TEST_SQL_FILE"

    # Should NOT include test_plugin code
    ! grep -q "test_plugin_table" "$TEST_SQL_FILE"
}

@test "prepare_deploy_script.sh removes inactive plugins from plugins scope" {
    # Create config with test_plugin disabled
    cat > "$TEST_CONFIG_FILE" << 'EOF'
[
  {
    "PATH": "core.tag",
    "TYPE": "str",
    "VALUE": "TEST"
  },
  {
    "PATH": "plugins.deploy_disabled_plugins",
    "TYPE": "bool",
    "VALUE": false
  },
  {
    "PATH": "plugins.test_plugin.is_disabled",
    "TYPE": "bool",
    "VALUE": true
  }
]
EOF
    export BUILD_CONFIG_FILE="$TEST_CONFIG_FILE"
    export DTAGENT_TOKEN="dt0c01.TEST12345678901234567890.TEST123456789012345678901234567890123456789012345678901234567890"

    run timeout 30 ./scripts/deploy/prepare_deploy_script.sh "$TEST_SQL_FILE" "test" "plugins" "" "manual"
    [ "$status" -eq 0 ]

    # Should include active_plugin
    grep -q "active_plugin_handler" "$TEST_SQL_FILE"

    # Should NOT include test_plugin
    ! grep -q "test_plugin_handler" "$TEST_SQL_FILE"
}

@test "prepare_deploy_script.sh removes inactive plugins from agents scope" {
    # Create config with test_plugin disabled
    cat > "$TEST_CONFIG_FILE" << 'EOF'
[
  {
    "PATH": "core.tag",
    "TYPE": "str",
    "VALUE": "TEST"
  },
  {
    "PATH": "plugins.deploy_disabled_plugins",
    "TYPE": "bool",
    "VALUE": false
  },
  {
    "PATH": "plugins.test_plugin.is_disabled",
    "TYPE": "bool",
    "VALUE": true
  }
]
EOF
    export BUILD_CONFIG_FILE="$TEST_CONFIG_FILE"
    export DTAGENT_TOKEN="dt0c01.TEST12345678901234567890.TEST123456789012345678901234567890123456789012345678901234567890"

    run timeout 30 ./scripts/deploy/prepare_deploy_script.sh "$TEST_SQL_FILE" "test" "agents" "" "manual"
    [ "$status" -eq 0 ]

    # Should include main agent
    grep -q "main_agent" "$TEST_SQL_FILE"

    # Should NOT include test_plugin_agent
    ! grep -q "class TestPlugin" "$TEST_SQL_FILE"
}

@test "prepare_deploy_script.sh removes inactive plugins from all scope" {
    # Create config with test_plugin disabled
    cat > "$TEST_CONFIG_FILE" << 'EOF'
[
  {
    "PATH": "core.tag",
    "TYPE": "str",
    "VALUE": "TEST"
  },
  {
    "PATH": "plugins.deploy_disabled_plugins",
    "TYPE": "bool",
    "VALUE": false
  },
  {
    "PATH": "plugins.test_plugin.is_disabled",
    "TYPE": "bool",
    "VALUE": true
  }
]
EOF
    export BUILD_CONFIG_FILE="$TEST_CONFIG_FILE"
    export DTAGENT_TOKEN="dt0c01.TEST12345678901234567890.TEST123456789012345678901234567890123456789012345678901234567890"

    run timeout 30 ./scripts/deploy/prepare_deploy_script.sh "$TEST_SQL_FILE" "test" "all" "" "manual"
    [ "$status" -eq 0 ]

    # Should include main code and active_plugin
    grep -q "MAIN_SCHEMA" "$TEST_SQL_FILE"
    grep -q "active_plugin_table" "$TEST_SQL_FILE"
    grep -q "active_plugin_handler" "$TEST_SQL_FILE"
    grep -q "class ActivePlugin" "$TEST_SQL_FILE"

    # Should NOT include test_plugin code anywhere
    ! grep -q "test_plugin_table" "$TEST_SQL_FILE"
    ! grep -q "test_plugin_handler" "$TEST_SQL_FILE"
    ! grep -q "test_plugin_agent" "$TEST_SQL_FILE"
    ! grep -q "class TestPlugin" "$TEST_SQL_FILE"

}