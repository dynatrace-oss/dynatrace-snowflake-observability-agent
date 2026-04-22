#!/usr/bin/env bats
#
# Tests for inject_suspend_for_excluded_plugins() in prepare_deploy_script.sh.
# Verifies that ALTER TASK IF EXISTS ... SUSPEND statements are injected into the
# deploy script for every disabled plugin, including multi-task and admin-task plugins.
#

setup() {
    cd "$BATS_TEST_DIRNAME/../.."

    # Minimal config: no tag, deploy_disabled_plugins=false
    TEST_CONFIG_FILE=$(mktemp)
    export BUILD_CONFIG_FILE="$TEST_CONFIG_FILE"
    TEST_SQL_FILE=$(mktemp)

    # Build artifacts required by prepare_deploy_script.sh
    mkdir -p build/30_plugins build/09_upgrade

    cat > build/00_init.sql << 'EOSQL'
CREATE SCHEMA IF NOT EXISTS MAIN_SCHEMA;
--%PLUGIN:tasks:
CREATE TABLE tasks_table (id INT);
--%:PLUGIN:tasks
--%PLUGIN:event_log:
CREATE TABLE event_log_table (id INT);
--%:PLUGIN:event_log
--%PLUGIN:snowpipes:
CREATE TABLE snowpipes_table (id INT);
--%:PLUGIN:snowpipes
EOSQL

    cat > build/10_admin.sql << 'EOSQL'
CREATE ROLE IF NOT EXISTS DTAGENT_ADMIN;
EOSQL

    cat > build/20_setup.sql << 'EOSQL'
CREATE PROCEDURE main_proc() AS BEGIN SELECT 1; END;
EOSQL

    cat > build/40_config.sql << 'EOSQL'
SELECT 'config';
EOSQL

    cat > build/30_plugins/tasks.sql << 'EOSQL'
--%PLUGIN:tasks:
CREATE OR REPLACE PROCEDURE tasks_handler() RETURNS TABLE() LANGUAGE PYTHON AS $$ def h(): return [] $$;
--%:PLUGIN:tasks
EOSQL

    cat > build/30_plugins/event_log.sql << 'EOSQL'
--%PLUGIN:event_log:
CREATE OR REPLACE PROCEDURE event_log_handler() RETURNS TABLE() LANGUAGE PYTHON AS $$ def h(): return [] $$;
--%:PLUGIN:event_log
EOSQL

    cat > build/30_plugins/snowpipes.sql << 'EOSQL'
--%PLUGIN:snowpipes:
CREATE OR REPLACE PROCEDURE snowpipes_handler() RETURNS TABLE() LANGUAGE PYTHON AS $$ def h(): return [] $$;
--%:PLUGIN:snowpipes
EOSQL

    cat > build/70_agents.sql << 'EOSQL'
CREATE PROCEDURE main_agent() RETURNS OBJECT LANGUAGE PYTHON RUNTIME_VERSION='3.13' PACKAGES=('requests') HANDLER='main' AS $$ def main(): pass $$;
EOSQL
}

teardown() {
    rm -f "$TEST_CONFIG_FILE" "$TEST_SQL_FILE"
    rm -f build/00_init.sql build/10_admin.sql build/20_setup.sql build/40_config.sql build/70_agents.sql
    rm -rf build/09_upgrade build/30_plugins
    unset BUILD_CONFIG_FILE
}

# Helper: build a minimal config JSON with one disabled plugin
_config_with_disabled() {
    local plugin="$1"
    cat > "$TEST_CONFIG_FILE" << EOF
[
  {"PATH": "plugins.deploy_disabled_plugins", "TYPE": "bool", "VALUE": false},
  {"PATH": "plugins.disabled_by_default",     "TYPE": "bool", "VALUE": false},
  {"PATH": "plugins.${plugin}.is_disabled",   "TYPE": "bool", "VALUE": true}
]
EOF
}

# Helper: build a config JSON with disabled_by_default and one enabled plugin
_config_disabled_by_default_except() {
    local enabled_plugin="$1"
    cat > "$TEST_CONFIG_FILE" << EOF
[
  {"PATH": "plugins.deploy_disabled_plugins",           "TYPE": "bool", "VALUE": false},
  {"PATH": "plugins.disabled_by_default",               "TYPE": "bool", "VALUE": true},
  {"PATH": "plugins.${enabled_plugin}.is_enabled",      "TYPE": "bool", "VALUE": true},
  {"PATH": "plugins.${enabled_plugin}.is_disabled",     "TYPE": "bool", "VALUE": false},
  {"PATH": "plugins.tasks.is_disabled",                 "TYPE": "bool", "VALUE": false},
  {"PATH": "plugins.event_log.is_disabled",             "TYPE": "bool", "VALUE": false},
  {"PATH": "plugins.snowpipes.is_disabled",             "TYPE": "bool", "VALUE": false}
]
EOF
}

@test "no suspend SQL when no plugins are excluded" {
    # All plugins enabled — nothing to exclude
    cat > "$TEST_CONFIG_FILE" << 'EOF'
[
  {"PATH": "plugins.deploy_disabled_plugins", "TYPE": "bool", "VALUE": false},
  {"PATH": "plugins.disabled_by_default",     "TYPE": "bool", "VALUE": false}
]
EOF

    run timeout 30 ./scripts/deploy/prepare_deploy_script.sh "$TEST_SQL_FILE" "test" "all" "" "manual"
    [ "$status" -eq 0 ]

    # No ALTER TASK SUSPEND should appear
    ! grep -qi 'alter task if exists.*suspend' "$TEST_SQL_FILE"
}

@test "suspend SQL injected for single-task disabled plugin (tasks)" {
    _config_with_disabled "tasks"

    run timeout 30 ./scripts/deploy/prepare_deploy_script.sh "$TEST_SQL_FILE" "test" "all" "" "manual"
    [ "$status" -eq 0 ]

    # Should contain suspend for the tasks plugin task
    grep -qi 'alter task if exists.*TASK_DTAGENT_TASKS.*suspend' "$TEST_SQL_FILE"
}

@test "suspend SQL injected for multi-task disabled plugin (snowpipes)" {
    _config_with_disabled "snowpipes"

    run timeout 30 ./scripts/deploy/prepare_deploy_script.sh "$TEST_SQL_FILE" "test" "all" "" "manual"
    [ "$status" -eq 0 ]

    # snowpipes has two tasks: TASK_DTAGENT_SNOWPIPES and TASK_DTAGENT_SNOWPIPES_HISTORY
    grep -qi 'alter task if exists.*TASK_DTAGENT_SNOWPIPES[^_].*suspend' "$TEST_SQL_FILE"
    grep -qi 'alter task if exists.*TASK_DTAGENT_SNOWPIPES_HISTORY.*suspend' "$TEST_SQL_FILE"
}

@test "suspend SQL injected for plugin with admin task (event_log)" {
    _config_with_disabled "event_log"

    run timeout 30 ./scripts/deploy/prepare_deploy_script.sh "$TEST_SQL_FILE" "test" "all" "" "manual"
    [ "$status" -eq 0 ]

    # event_log has main task and admin cleanup task
    grep -qi 'alter task if exists.*TASK_DTAGENT_EVENT_LOG[^_].*suspend' "$TEST_SQL_FILE"
    grep -qi 'alter task if exists.*TASK_DTAGENT_EVENT_LOG_CLEANUP.*suspend' "$TEST_SQL_FILE"
}

@test "suspend SQL uses correct role context (DTAGENT_OWNER)" {
    _config_with_disabled "tasks"

    run timeout 30 ./scripts/deploy/prepare_deploy_script.sh "$TEST_SQL_FILE" "test" "all" "" "manual"
    [ "$status" -eq 0 ]

    # The suspend block must be preceded by a role/db context line
    grep -qi 'use role DTAGENT_OWNER' "$TEST_SQL_FILE"
}

@test "suspend SQL injected even with scope=plugins,agents (no config scope)" {
    _config_with_disabled "tasks"

    run timeout 30 ./scripts/deploy/prepare_deploy_script.sh "$TEST_SQL_FILE" "test" "plugins,agents" "" "manual"
    [ "$status" -eq 0 ]

    grep -qi 'alter task if exists.*TASK_DTAGENT_TASKS.*suspend' "$TEST_SQL_FILE"
}

@test "deploy log reports which plugins will be suspended" {
    _config_with_disabled "tasks"

    run timeout 30 ./scripts/deploy/prepare_deploy_script.sh "$TEST_SQL_FILE" "test" "all" "" "manual"
    [ "$status" -eq 0 ]

    # Output should contain the [deploy] prefix log line
    [[ "$output" =~ "[deploy] Will suspend task for disabled plugin: tasks" ]]
}

@test "no suspend SQL for teardown scope" {
    _config_with_disabled "tasks"

    run timeout 30 ./scripts/deploy/prepare_deploy_script.sh "$TEST_SQL_FILE" "test" "teardown" "" "manual"
    [ "$status" -eq 0 ]

    ! grep -qi 'alter task if exists.*suspend' "$TEST_SQL_FILE"
}
